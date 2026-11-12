"""写数据工具（§8.4）：``propose_write`` —— 只出草案，绝不执行。

设计要点：
- **只生成变更草案，不修改数据库**。真正执行需要相应角色批准。
- ``estimated_rows`` 用 ``SELECT COUNT(*)`` 真算，不估。
- ``preview`` 先过 ``sanitize`` 打码（展示用），执行时用原值。
- 草案生成后写一条 ``pending`` 审批单（kind=write）。
- 同一 ``sql_hash`` 10 分钟内重复提交，返回原草案（防 Agent 反复重试）。
"""
from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import datetime, timedelta

from langchain_core.tools import tool

from services.ops import hitl, sanitize
from services.ops.write_gate import RISK_L1, RISK_L2, RISK_L3, evaluate

# 风险 → 超时时长（§8.5）
_RISK_TIMEOUT = {
    RISK_L1: timedelta(minutes=10),
    RISK_L2: timedelta(minutes=30),
    RISK_L3: timedelta(hours=2),
}

_SAMPLE_LIMIT = 20


def _sql_hash(sql: str) -> str:
    return "sha256:" + hashlib.sha256((sql or "").strip().encode("utf-8")).hexdigest()


def _extract_where(sql: str, operation: str) -> str:
    """从 UPDATE/DELETE 语句中提取 WHERE 子句。"""
    if operation not in ("UPDATE", "DELETE"):
        return ""
    m = re.search(r"\bWHERE\b(.+)$", sql, re.IGNORECASE | re.DOTALL)
    return m.group(1).strip().rstrip(";") if m else ""


def _parse_set_values(sql: str) -> dict[str, str]:
    """从 UPDATE 语句中解析 SET col=val 对（值为 SQL 字面量字符串）。"""
    m = re.search(r"\bSET\s+(.+?)(?:\bWHERE\b|$)", sql, re.IGNORECASE | re.DOTALL)
    if not m:
        return {}
    values: dict[str, str] = {}
    for part in m.group(1).split(","):
        part = part.strip()
        cm = re.match(r"([`]?[A-Za-z_][\w]*[`]?)\s*=\s*(.+)", part)
        if cm:
            values[cm.group(1).strip("`")] = cm.group(2).strip()
    return values


def _parse_sql_literal(val_str: str):
    """把 SQL 字面量字符串解析为 Python 值。"""
    val_str = val_str.strip()
    if val_str.upper() == "NULL":
        return None
    if (val_str.startswith("'") and val_str.endswith("'")) or (
        val_str.startswith('"') and val_str.endswith('"')
    ):
        return val_str[1:-1].replace("''", "'")
    try:
        return int(val_str)
    except ValueError:
        try:
            return float(val_str)
        except ValueError:
            return val_str


def _get_pk_column(conn, database: str, table: str) -> str | None:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT COLUMN_NAME FROM information_schema.KEY_COLUMN_USAGE "
            "WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s AND CONSTRAINT_NAME='PRIMARY' "
            "ORDER BY ORDINAL_POSITION LIMIT 1",
            (database, table),
        )
        row = cur.fetchone()
        return row[0] if row else None


def _compute_estimated_rows(conn, database: str, table: str,
                            operation: str, where_clause: str) -> int:
    """用 SELECT COUNT(*) 真算影响行数。"""
    if operation == "INSERT":
        return 1
    if not where_clause:
        return 0
    count_sql = f"SELECT COUNT(*) FROM {database}.{table} WHERE {where_clause}"
    with conn.cursor() as cur:
        cur.execute(count_sql)
        row = cur.fetchone()
        return int(row[0]) if row else 0


def _compute_preview(conn, database: str, table: str, operation: str,
                     sql: str, where_clause: str) -> dict:
    """计算变更前后预览（展示用，过脱敏）。"""
    pk_col = _get_pk_column(conn, database, table)
    set_values = _parse_set_values(sql) if operation == "UPDATE" else {}

    if operation == "UPDATE":
        select_cols = []
        if pk_col:
            select_cols.append(pk_col)
        for c in set_values:
            if c not in select_cols:
                select_cols.append(c)
        if not select_cols:
            select_cols = ["*"]
    elif operation == "DELETE":
        select_cols = [pk_col] if pk_col else ["*"]
    else:  # INSERT
        select_cols = []

    before_rows: list[list] = []
    after_rows: list[list] = []
    columns: list[str] = []

    if operation in ("UPDATE", "DELETE") and where_clause:
        select_sql = f"SELECT {', '.join(select_cols)} FROM {database}.{table} WHERE {where_clause} LIMIT {_SAMPLE_LIMIT}"
        with conn.cursor() as cur:
            cur.execute(select_sql)
            col_names = [desc[0] for desc in cur.description] if cur.description else select_cols
            rows = cur.fetchall()[:_SAMPLE_LIMIT]
        columns = col_names
        before_rows = [list(r) for r in rows]
        # 脱敏
        masked_cols = []
        masked_headers, masked_before, masked_cols = sanitize.mask_rows(columns, before_rows)
        columns = masked_headers
        before_rows = masked_before
        # after = before 但 SET 列替换为新值
        after_rows = []
        for row in before_rows:
            new_row = list(row)
            for i, col in enumerate(columns):
                if col in set_values:
                    new_val = _parse_sql_literal(set_values[col])
                    new_row[i] = sanitize.mask_text(str(new_val)) if new_val is not None else None
            after_rows.append(new_row)
        if operation == "DELETE":
            after_rows = []
    elif operation == "INSERT":
        # 从 INSERT 语句解析列与值
        m = re.search(
            r"\bINSERT\s+INTO\s+[\w.`]+\s*\(([^)]+)\)\s*VALUES\s*\((.+)\)",
            sql, re.IGNORECASE | re.DOTALL,
        )
        if m:
            cols = [c.strip().strip("`") for c in m.group(1).split(",")]
            vals_str = m.group(2)
            # 简单按逗号分割（不处理嵌套括号，够用于预览）
            vals = [_parse_sql_literal(v.strip()) for v in vals_str.split(",")]
            columns = cols
            after_vals = [sanitize.mask_text(str(v)) if v is not None else None for v in vals]
            after_rows = [after_vals]
            before_rows = []

    return {
        "columns": columns,
        "before": before_rows,
        "after": after_rows,
        "sample_limit": _SAMPLE_LIMIT,
    }


@tool
def propose_write(database: str, table: str, operation: str, sql: str, reason: str = "") -> str:
    """提交一条数据变更草案（不会立即执行）。

    仅当用户明确要求修改/新增/删除业务数据时调用。
    operation 只能是 INSERT / UPDATE / DELETE。
    UPDATE/DELETE 必须提供精确 WHERE，并说明变更原因 reason。
    返回草案 ID、影响行数预估、变更前后预览；真正执行需要相应角色批准。
    """
    op = (operation or "").strip().upper()
    if op not in ("INSERT", "UPDATE", "DELETE"):
        return json.dumps({
            "ok": False,
            "reject_reason": f"operation 只能是 INSERT/UPDATE/DELETE，收到 {operation}",
        }, ensure_ascii=False)

    # 延迟导入，避免与 core.agent 循环依赖
    from core.agent import db_connect

    # 用只读连接计算预估行数与预览
    try:
        conn = db_connect(database=database, mode="read")
    except Exception as exc:
        return json.dumps({
            "ok": False,
            "reject_reason": f"数据库连接失败：{exc}",
        }, ensure_ascii=False)

    try:
        where_clause = _extract_where(sql, op)
        estimated_rows = _compute_estimated_rows(conn, database, table, op, where_clause)

        # 风控闸门
        gate_result = evaluate(sql, database=database, table=table,
                               estimated_rows=estimated_rows)
        if not gate_result.get("ok"):
            return json.dumps(gate_result, ensure_ascii=False)

        risk = gate_result["risk"]
        required_role = gate_result["required_role"]

        # 预览（脱敏）
        preview = _compute_preview(conn, database, table, op, sql, where_clause)
    except Exception as exc:
        return json.dumps({
            "ok": False,
            "reject_reason": f"草案计算失败：{exc}",
        }, ensure_ascii=False)
    finally:
        try:
            conn.close()
        except Exception:
            pass

    # 生成草案
    sql_hash = _sql_hash(sql)
    proposal_id = f"wp_{datetime.now().strftime('%Y%m%d')}_{uuid.uuid4().hex[:6]}"
    expires_at = (datetime.now() + _RISK_TIMEOUT.get(risk, timedelta(minutes=10))).strftime(
        "%Y-%m-%dT%H:%M:%S"
    )
    proposal = {
        "proposal_id": proposal_id,
        "database": database,
        "table": table,
        "operation": op,
        "sql": sql,
        "sql_hash": sql_hash,
        "where_clause": where_clause,
        "reason": reason,
        "estimated_rows": estimated_rows,
        "risk": risk,
        "required_role": required_role,
        "preview": preview,
        "expires_at": expires_at,
        "idempotency_key": sql_hash,
    }

    # 创建写审批单（kind=write）
    approval = hitl.manager.create_write(
        thread_id="", proposal=proposal, operator_id=""
    )
    proposal["approval_id"] = approval.id

    return json.dumps(proposal, ensure_ascii=False)


propose_write_tool = propose_write
