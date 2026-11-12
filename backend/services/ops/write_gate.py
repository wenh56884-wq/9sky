"""写数据风控闸门（§8.3）：8 条判定规则，短路命中即停。

设计要点：
- **默认 table_whitelist 为空 → 全部拒绝**，必须由租户/超管在配置里显式开启可写表。
- 判定顺序短路：命中即返回，不继续后续检查。
- 返回结构统一：
  - 拒绝：``{"ok": False, "reject_reason": "...", "hits": [...]}``
  - 通过：``{"ok": True, "risk": "L1|L2|L3", "required_role": n, "estimated_rows": n}``

8 条判定顺序：
  1. 单语句（无分号分隔）→ 拒绝
  2. 首关键字 ∈ {INSERT, UPDATE, DELETE} → 拒绝（DDL 一律拒绝）
  3. 命中 forbid_statements / 注释符 / INTO OUTFILE → 拒绝
  4. 目标表 ∈ table_whitelist → 拒绝：表 x 未开启写入
  5. UPDATE/DELETE 必须带 WHERE → 拒绝（不是升级，是拒绝）
  6. SET/INSERT 的列 ∉ column_blacklist → 拒绝：敏感列 x 禁止写入
  7. 影响行数 ≤ 对应级别上限 → 超限升级到下一级；>5000 不受理
  8. 不跨库 → 拒绝
"""
from __future__ import annotations

import json
import os
import re

RISK_L1, RISK_L2, RISK_L3 = "L1", "L2", "L3"

# 级别 → 批准人角色映射（§8.5）
RISK_ROLE = {RISK_L1: 1, RISK_L2: 2, RISK_L3: 3}

POLICY = {
    # 默认为空 → 全部拒绝。必须由租户/超管在配置里显式开启可写表。
    # 格式：{"库名.表名": {"columns": ["允许列", ...]}}
    "table_whitelist": {},
    "column_blacklist": [  # 敏感列，任何情况下禁止写
        "national_id", "patient_name", "phone", "mobile",
        "bank_card", "id_card", "password", "salary",
    ],
    "max_rows": {RISK_L1: 50, RISK_L2: 1000, RISK_L3: 5000},
    "forbid_without_where": ["UPDATE", "DELETE"],
    "forbid_statements": [
        "DROP", "TRUNCATE", "ALTER", "GRANT", "CREATE USER", "LOAD DATA",
    ],
    # 金额类列名模式（命中即升级 L3，§8.5）
    "amount_column_patterns": [
        r"amount", r"total", r"fee", r"cost", r"money",
        r"balance", r"price", r"revenue", r"salary",
    ],
}

# 允许的写操作首关键字
_WRITE_OPERATIONS = {"INSERT", "UPDATE", "DELETE"}

_THREE_DBS = (
    "financial_asset_management",
    "healthcare_analytics_competition",
    "telecom_operations_db",
)


def _load_whitelist() -> dict:
    """从环境变量 WRITE_TABLE_WHITELIST 加载写表白名单（JSON 格式）。

    格式：{"库名.表名": {"columns": ["允许列", ...]}}
    环境变量未设置或解析失败时返回空 dict（安全默认：全部拒绝）。
    """
    raw = (os.getenv("WRITE_TABLE_WHITELIST") or "").strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        if not isinstance(data, dict):
            return {}
        # 只保留结构正确的条目
        result = {}
        for table, spec in data.items():
            if isinstance(spec, dict) and "columns" in spec:
                cols = [str(c) for c in (spec.get("columns") or [])]
                result[str(table)] = {"columns": cols}
        return result
    except (json.JSONDecodeError, TypeError, ValueError):
        return {}


def get_whitelist() -> dict:
    """获取当前生效的写表白名单。

    从环境变量 WRITE_TABLE_WHITELIST 加载条目并**合并**到 POLICY["table_whitelist"]，
    支持运行时变更；环境变量未设置时保持现有配置不变（安全默认：空 {} → 全部拒绝）。
    """
    loaded = _load_whitelist()
    for table, spec in loaded.items():
        POLICY["table_whitelist"][table] = spec
    return dict(POLICY["table_whitelist"])



def _strip_literals_and_comments(sql: str) -> str:
    """抹掉字符串字面量、反引号标识符与注释，只保留语法骨架。"""
    s = re.sub(r"'[^']*'|\"[^\"]*\"", " ", sql)
    s = re.sub(r"`[^`]*`", " ", s)
    s = re.sub(r"/\*.*?\*/", " ", s, flags=re.S)
    s = re.sub(r"--[^\n]*", " ", s)
    s = re.sub(r"#[^\n]*", " ", s)
    return s


def _detect_operation(sql: str) -> str:
    """提取首关键字（INSERT/UPDATE/DELETE 等）。"""
    probe = _strip_literals_and_comments(sql).strip()
    if not probe:
        return ""
    return probe.split(None, 1)[0].upper()


def _detect_table(sql: str) -> str:
    """从语句中提取目标表名（含库名限定，返回 库名.表名 或 表名）。"""
    probe = _strip_literals_and_comments(sql)
    m = re.search(
        r"\b(?:INSERT\s+INTO|UPDATE|DELETE\s+FROM)\s+"
        r"([`]?[A-Za-z_][\w]*[`]?(?:\s*\.\s*[`]?[A-Za-z_][\w]*[`]?)?)",
        probe, re.IGNORECASE,
    )
    if not m:
        return ""
    return m.group(1).strip().replace("`", "")


def _detect_columns(sql: str, operation: str) -> list[str]:
    """提取 INSERT 的列或 UPDATE SET 的列。"""
    probe = _strip_literals_and_comments(sql)
    cols: list[str] = []
    if operation == "INSERT":
        m = re.search(
            r"\bINSERT\s+INTO\s+[\w.`]+\s*\(([^)]+)\)", probe, re.IGNORECASE
        )
        if m:
            cols = [c.strip().strip("`") for c in m.group(1).split(",") if c.strip()]
    elif operation == "UPDATE":
        m = re.search(
            r"\bSET\s+(.+?)(?:\bWHERE\b|$)", probe, re.IGNORECASE | re.DOTALL
        )
        if m:
            for part in m.group(1).split(","):
                part = part.strip()
                if not part:
                    continue
                cm = re.match(r"([`]?[A-Za-z_][\w]*[`]?)\s*=", part)
                if cm:
                    cols.append(cm.group(1).strip("`"))
    return cols


def _has_where(sql: str, operation: str) -> bool:
    """UPDATE/DELETE 是否带 WHERE。"""
    if operation not in ("UPDATE", "DELETE"):
        return True
    probe = _strip_literals_and_comments(sql)
    return bool(re.search(r"\bWHERE\b", probe, re.IGNORECASE))


def _detect_cross_db(sql: str) -> bool:
    """是否跨库（引用了多个业务库的表）。"""
    probe = _strip_literals_and_comments(sql)
    dbs = set(re.findall(
        r"\b(" + "|".join(_THREE_DBS) + r")\s*\.\s*\w+", probe, re.IGNORECASE,
    ))
    return len(dbs) > 1


def _detect_cross_table(sql: str) -> bool:
    """是否跨表（同一语句操作多张表 → 升级 L3）。"""
    probe = _strip_literals_and_comments(sql)
    tables = re.findall(
        r"\b(?:INSERT\s+INTO|UPDATE|DELETE\s+FROM)\s+[`]?[\w]*[`]?"
        r"(?:\s*\.\s*[`]?[A-Za-z_][\w]*[`]?)?",
        probe, re.IGNORECASE,
    )
    names: set[str] = set()
    for t in tables:
        tm = re.search(r"([\w]+)\s*\.\s*([\w]+)|([\w]+)$", t, re.IGNORECASE)
        if tm:
            names.add((tm.group(2) or tm.group(3) or "").lower())
    names.discard("")
    return len(names) > 1


def _has_amount_column(columns: list[str]) -> bool:
    """SET/INSERT 的列是否含金额类列（命中即升级 L3）。"""
    for col in columns:
        col_lower = col.lower()
        for pat in POLICY["amount_column_patterns"]:
            if re.search(pat, col_lower):
                return True
    return False


def _risk_for_rows(est: int) -> str:
    """根据影响行数判定风险级别。"""
    if est <= POLICY["max_rows"][RISK_L1]:
        return RISK_L1
    if est <= POLICY["max_rows"][RISK_L2]:
        return RISK_L2
    return RISK_L3


def evaluate(
    sql: str,
    database: str = "",
    table: str = "",
    estimated_rows: int | None = None,
) -> dict:
    """风控闸门：8 条判定顺序，短路命中即停。

    Args:
        sql: 待评估的写 SQL。
        database: 目标库名（用于表白名单匹配）。
        table: 目标表名（用于表白名单匹配；留空则从 SQL 解析）。
        estimated_rows: 影响行数预估（由调用方用 SELECT COUNT(*) 真算后传入）。

    Returns:
        拒绝：``{"ok": False, "reject_reason": "...", "hits": [...]}``
        通过：``{"ok": True, "risk": "L1|L2|L3", "required_role": n, "estimated_rows": n}``
    """
    stmt = (sql or "").strip()

    # 加载写表白名单（从 WRITE_TABLE_WHITELIST 环境变量，支持运行时变更）
    get_whitelist()

    # 规则 1：单语句（无分号分隔）
    probe = _strip_literals_and_comments(stmt)
    body = probe.rstrip(";").strip()
    if ";" in body:
        return {"ok": False, "reject_reason": "只允许单条语句，不支持分号分隔的多语句",
                "hits": ["single_statement"]}

    # 规则 2：首关键字 ∈ {INSERT, UPDATE, DELETE}
    operation = _detect_operation(stmt)
    if operation not in _WRITE_OPERATIONS:
        return {"ok": False, "reject_reason": f"只允许 INSERT/UPDATE/DELETE，不允许 {operation or '空语句'}",
                "hits": ["operation_not_allowed"]}

    # 规则 3：命中 forbid_statements / INTO OUTFILE
    for kw in POLICY["forbid_statements"]:
        if re.search(rf"\b{re.escape(kw)}\b", probe, re.IGNORECASE):
            return {"ok": False, "reject_reason": f"命中禁止语句 {kw}",
                    "hits": ["forbid_statements"]}
    if re.search(r"INTO\s+OUTFILE", probe, re.IGNORECASE):
        return {"ok": False, "reject_reason": "禁止 SELECT ... INTO OUTFILE",
                "hits": ["forbid_statements"]}

    # 规则 4：目标表 ∈ table_whitelist
    tbl = table or _detect_table(stmt)
    tbl_key = tbl if "." in tbl else (f"{database}.{tbl}" if database else tbl)
    if tbl_key not in POLICY["table_whitelist"]:
        return {"ok": False, "reject_reason": f"表 {tbl_key} 未开启写入",
                "hits": ["table_not_whitelisted"]}

    # 规则 5：UPDATE/DELETE 必须带 WHERE
    if not _has_where(stmt, operation):
        return {"ok": False, "reject_reason": f"{operation} 未带 WHERE 条件，已拒绝",
                "hits": ["forbid_without_where"]}

    # 规则 6：SET/INSERT 的列 ∉ column_blacklist
    cols = _detect_columns(stmt, operation)
    blacklist = [c.lower() for c in POLICY["column_blacklist"]]
    for col in cols:
        if col.lower() in blacklist:
            return {"ok": False, "reject_reason": f"敏感列 {col} 禁止写入",
                    "hits": ["sensitive_column"]}

    # 规则 7：影响行数 ≤ 对应级别上限；>5000 不受理
    est = estimated_rows if estimated_rows is not None else 0
    if est > POLICY["max_rows"][RISK_L3]:
        return {"ok": False, "reject_reason": f"影响行数 {est} 超过上限 {POLICY['max_rows'][RISK_L3]}，不受理，请拆批",
                "hits": ["rows_over_limit"]}
    risk = _risk_for_rows(est)

    # 跨表 / 含金额列 → 升级 L3（§8.5）
    if _detect_cross_table(stmt) or _has_amount_column(cols):
        risk = RISK_L3

    # 规则 8：不跨库
    if _detect_cross_db(stmt):
        return {"ok": False, "reject_reason": "禁止跨库写操作",
                "hits": ["cross_database"]}

    return {
        "ok": True,
        "risk": risk,
        "required_role": RISK_ROLE[risk],
        "estimated_rows": est,
    }
