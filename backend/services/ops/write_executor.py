"""写数据执行器与撤销（§8.7）：9 步流程 + 变更留痕。

设计要点：
- **执行前校验 sql_hash**：防审批后 SQL 被篡改。
- **幂等检查**：idempotency_key 24h 内已执行 → 直接返回上次结果，不重复落库。
- **用 jt_write 连接**（白名单表读写，无 DDL 权限），开事务。
- **记录 before**：UPDATE 存"主键 + 被改列"前值；DELETE 存整行（撤销必需）；
  INSERT 存主键值。不存无关敏感列（最小化原则）。
- **行数比对**：|affected - estimated| / max(estimated,1) > 20% → ROLLBACK，记 failed。
- **任何异常** → ROLLBACK + change_log(status=failed) + error_id。
- **撤销**：用 before_json 生成反向 SQL，执行后 status=reverted，新增一条 revert 记录。

9 步流程：
  ① 校验 sql_hash == 审批单里的 sql_hash
  ② 幂等检查：idempotency_key 24h 内已执行 → 返回上次结果
  ③ 用 jt_write 连接，开启事务
  ④ SELECT ... FOR UPDATE 锁定目标行
  ⑤ 记录 before（主键 + 被改列前值）
  ⑥ 执行，取 affected_rows
  ⑦ 比对：差值 >20% → ROLLBACK，记 failed
  ⑧ COMMIT → 写 change_log（status=applied）
  ⑨ 任何异常 → ROLLBACK，写 change_log（status=failed）+ error_id
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from services.ops import debugging
from services.ops.write_gate import _detect_columns, _detect_operation, _detect_table

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
CHANGE_LOG_DB = DATA_DIR / "change_log.sqlite3"


def _now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def _sql_hash(sql: str) -> str:
    return "sha256:" + hashlib.sha256((sql or "").strip().encode("utf-8")).hexdigest()


def _is_within_hours(iso_time: str, hours: int) -> bool:
    if not iso_time:
        return False
    try:
        dt = datetime.strptime(iso_time, "%Y-%m-%dT%H:%M:%S")
        return (datetime.now() - dt) <= timedelta(hours=hours)
    except (ValueError, TypeError):
        return False


class WriteExecutorError(Exception):
    """写执行器错误（校验失败、执行失败等）。"""


class _ChangeLogStore:
    """``change_log.sqlite3`` 读写：变更留痕，重启不丢失。"""

    def __init__(self, db_path: Path | None = None) -> None:
        self._db_path = Path(db_path or CHANGE_LOG_DB)
        self._lock = threading.RLock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self._db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        return conn

    def _init_db(self) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS change_log (
                    id              TEXT PRIMARY KEY,
                    proposal_id     TEXT NOT NULL,
                    approval_id     TEXT,
                    actor_id        TEXT NOT NULL,
                    actor_name      TEXT,
                    approver_id     TEXT,
                    approver_name   TEXT,
                    db_name         TEXT NOT NULL,
                    table_name      TEXT NOT NULL,
                    operation       TEXT NOT NULL,
                    sql_text        TEXT NOT NULL,
                    sql_hash        TEXT NOT NULL,
                    where_clause    TEXT,
                    estimated_rows  INTEGER,
                    affected_rows   INTEGER,
                    before_json     TEXT,
                    after_json      TEXT,
                    status          TEXT,
                    error_id        TEXT,
                    idempotency_key TEXT UNIQUE,
                    applied_at      TEXT,
                    reverted_at     TEXT
                )"""
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_change_log_status ON change_log(status)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_change_log_table ON change_log(db_name, table_name)"
            )
            conn.commit()

    def insert(self, entry: dict) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """INSERT INTO change_log
                    (id, proposal_id, approval_id, actor_id, actor_name, approver_id,
                     approver_name, db_name, table_name, operation, sql_text, sql_hash,
                     where_clause, estimated_rows, affected_rows, before_json, after_json,
                     status, error_id, idempotency_key, applied_at, reverted_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    entry["id"], entry["proposal_id"], entry.get("approval_id"),
                    entry["actor_id"], entry.get("actor_name"), entry.get("approver_id"),
                    entry.get("approver_name"), entry["db_name"], entry["table_name"],
                    entry["operation"], entry["sql_text"], entry["sql_hash"],
                    entry.get("where_clause"), entry.get("estimated_rows"),
                    entry.get("affected_rows"), entry.get("before_json"),
                    entry.get("after_json"), entry.get("status"),
                    entry.get("error_id"), entry.get("idempotency_key"),
                    entry.get("applied_at"), entry.get("reverted_at"),
                ),
            )
            conn.commit()

    def find_by_idempotency(self, key: str) -> dict | None:
        if not key:
            return None
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM change_log WHERE idempotency_key=? ORDER BY applied_at DESC LIMIT 1",
                (key,),
            ).fetchone()
            return dict(row) if row else None

    def get(self, change_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM change_log WHERE id=?", (change_id,)).fetchone()
            return dict(row) if row else None

    def update_status(self, change_id: str, status: str, reverted_at: str | None = None) -> bool:
        with self._lock, self._connect() as conn:
            if reverted_at:
                cur = conn.execute(
                    "UPDATE change_log SET status=?, reverted_at=? WHERE id=?",
                    (status, reverted_at, change_id),
                )
            else:
                cur = conn.execute(
                    "UPDATE change_log SET status=? WHERE id=?", (status, change_id)
                )
            conn.commit()
            return cur.rowcount > 0

    def list_history(self, limit: int = 50, offset: int = 0,
                     status: str | None = None) -> list[dict]:
        sql = "SELECT * FROM change_log"
        params: list = []
        if status:
            sql += " WHERE status=?"
            params.append(status)
        sql += " ORDER BY applied_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
            out = []
            for r in rows:
                d = dict(r)
                if d.get("before_json"):
                    d["before"] = json.loads(d["before_json"])
                if d.get("after_json"):
                    d["after"] = json.loads(d["after_json"])
                out.append(d)
            return out


_store = _ChangeLogStore()


def _get_pk_column(conn, database: str, table: str) -> str | None:
    """查询表的主键列名。"""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT COLUMN_NAME FROM information_schema.KEY_COLUMN_USAGE "
            "WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s AND CONSTRAINT_NAME='PRIMARY' "
            "ORDER BY ORDINAL_POSITION LIMIT 1",
            (database, table),
        )
        row = cur.fetchone()
        return row[0] if row else None


def _record_before(conn, database: str, table: str, operation: str,
                   sql: str, where_clause: str) -> str:
    """记录变更前的值（before_json）。

    - UPDATE：SELECT 主键 + 被改列 WHERE where_clause
    - DELETE：SELECT * WHERE where_clause（撤销需整行）
    - INSERT：无 before，返回 "[]"
    """
    if operation == "INSERT":
        return "[]"
    pk_col = _get_pk_column(conn, database, table)
    if operation == "UPDATE":
        cols = _detect_columns(sql, "UPDATE")
        select_cols = [pk_col] if pk_col else []
        for c in cols:
            if c not in select_cols:
                select_cols.append(c)
        if not select_cols:
            select_cols = ["*"]
    else:  # DELETE
        select_cols = ["*"]
    select_sql = f"SELECT {', '.join(select_cols)} FROM {database}.{table}"
    if where_clause:
        select_sql += f" WHERE {where_clause}"
    with conn.cursor() as cur:
        cur.execute(select_sql)
        col_names = [desc[0] for desc in cur.description] if cur.description else []
        rows = cur.fetchall()
    before = [dict(zip(col_names, row)) for row in rows]
    return json.dumps(before, ensure_ascii=False, default=str)


def execute(
    proposal: dict,
    approval_id: str,
    actor_id: str,
    actor_name: str = "",
    approver_id: str = "",
    approver_name: str = "",
) -> dict:
    """执行一条已批准的写变更（9 步流程）。

    Returns:
        {"ok": True, "change_id": ..., "affected_rows": n, "status": "applied"}
        或 {"ok": False, "status": "failed", "error_id": ..., "message": ...}
    """
    database = proposal.get("database", "")
    table = proposal.get("table", "")
    operation = proposal.get("operation", "").upper()
    sql = proposal.get("sql", "")
    estimated_rows = int(proposal.get("estimated_rows", 0) or 0)
    idempotency_key = proposal.get("idempotency_key") or proposal.get("sql_hash") or ""

    # ① 校验 sql_hash
    expected_hash = proposal.get("sql_hash", "")
    actual_hash = _sql_hash(sql)
    if actual_hash != expected_hash:
        error_id = debugging.record_error(
            WriteExecutorError("sql_hash 不匹配，拒绝执行"), context="write_execute"
        )
        _store.insert({
            "id": uuid.uuid4().hex,
            "proposal_id": proposal.get("proposal_id", ""),
            "approval_id": approval_id,
            "actor_id": actor_id, "actor_name": actor_name,
            "approver_id": approver_id, "approver_name": approver_name,
            "db_name": database, "table_name": table, "operation": operation,
            "sql_text": sql, "sql_hash": actual_hash,
            "where_clause": proposal.get("where_clause"),
            "estimated_rows": estimated_rows, "affected_rows": 0,
            "before_json": None, "after_json": None,
            "status": "failed", "error_id": error_id,
            "idempotency_key": idempotency_key or None,
            "applied_at": _now_iso(), "reverted_at": None,
        })
        return {"ok": False, "status": "failed", "error_id": error_id,
                "message": "sql_hash 不匹配，拒绝执行"}

    # ② 幂等检查：24h 内已执行 → 返回上次结果
    if idempotency_key:
        existing = _store.find_by_idempotency(idempotency_key)
        if existing and _is_within_hours(existing.get("applied_at", ""), 24):
            return {"ok": True, "change_id": existing["id"],
                    "affected_rows": existing.get("affected_rows", 0),
                    "status": existing.get("status", "applied"),
                    "idempotent_replay": True}

    # ③ 用 jt_write 连接，开启事务
    try:
        from core.agent import db_connect
        conn = db_connect(database=database, mode="write")
        conn.begin()  # 开启事务
    except Exception as exc:
        error_id = debugging.record_error(exc, context="write_connect")
        return {"ok": False, "status": "failed", "error_id": error_id,
                "message": f"写连接失败：{debugging.safe_message(exc)}"}

    change_id = uuid.uuid4().hex
    try:
        where_clause = proposal.get("where_clause", "")

        # ④ SELECT ... FOR UPDATE 锁定目标行（UPDATE/DELETE）
        if operation in ("UPDATE", "DELETE") and where_clause:
            lock_sql = f"SELECT 1 FROM {database}.{table} WHERE {where_clause} LIMIT 1 FOR UPDATE"
            with conn.cursor() as cur:
                cur.execute(lock_sql)

        # ⑤ 记录 before
        before_json = _record_before(conn, database, table, operation, sql, where_clause)

        # ⑥ 执行，取 affected_rows
        with conn.cursor() as cur:
            affected = cur.execute(sql)
            affected_rows = cur.rowcount

        # ⑦ 比对：|affected - estimated| / max(estimated,1) > 20% → ROLLBACK
        if estimated_rows > 0:
            diff_ratio = abs(affected_rows - estimated_rows) / max(estimated_rows, 1)
            if diff_ratio > 0.2:
                conn.rollback()
                error_id = debugging.record_error(
                    WriteExecutorError(
                        f"affected_rows({affected_rows}) 与预估({estimated_rows})差值超20%"
                    ),
                    context="write_rows_mismatch",
                )
                _store.insert({
                    "id": change_id, "proposal_id": proposal.get("proposal_id", ""),
                    "approval_id": approval_id,
                    "actor_id": actor_id, "actor_name": actor_name,
                    "approver_id": approver_id, "approver_name": approver_name,
                    "db_name": database, "table_name": table, "operation": operation,
                    "sql_text": sql, "sql_hash": actual_hash,
                    "where_clause": where_clause,
                    "estimated_rows": estimated_rows, "affected_rows": affected_rows,
                    "before_json": before_json, "after_json": None,
                    "status": "failed", "error_id": error_id,
                    "idempotency_key": idempotency_key or None,
                    "applied_at": _now_iso(), "reverted_at": None,
                })
                return {"ok": False, "status": "failed", "error_id": error_id,
                        "message": "affected_rows 与预估差值超 20%，已回滚"}

        # ⑧ COMMIT → 写 change_log（status=applied）
        conn.commit()
        _store.insert({
            "id": change_id, "proposal_id": proposal.get("proposal_id", ""),
            "approval_id": approval_id,
            "actor_id": actor_id, "actor_name": actor_name,
            "approver_id": approver_id, "approver_name": approver_name,
            "db_name": database, "table_name": table, "operation": operation,
            "sql_text": sql, "sql_hash": actual_hash,
            "where_clause": where_clause,
            "estimated_rows": estimated_rows, "affected_rows": affected_rows,
            "before_json": before_json, "after_json": None,
            "status": "applied", "error_id": None,
            "idempotency_key": idempotency_key or None,
            "applied_at": _now_iso(), "reverted_at": None,
        })
        return {"ok": True, "change_id": change_id,
                "affected_rows": affected_rows, "status": "applied"}

    except Exception as exc:
        # ⑨ 任何异常 → ROLLBACK，写 change_log（status=failed）+ error_id
        try:
            conn.rollback()
        except Exception:
            pass
        error_id = debugging.record_error(exc, context="write_execute")
        _store.insert({
            "id": change_id, "proposal_id": proposal.get("proposal_id", ""),
            "approval_id": approval_id,
            "actor_id": actor_id, "actor_name": actor_name,
            "approver_id": approver_id, "approver_name": approver_name,
            "db_name": database, "table_name": table, "operation": operation,
            "sql_text": sql, "sql_hash": actual_hash,
            "where_clause": proposal.get("where_clause"),
            "estimated_rows": estimated_rows, "affected_rows": 0,
            "before_json": None, "after_json": None,
            "status": "failed", "error_id": error_id,
            "idempotency_key": idempotency_key or None,
            "applied_at": _now_iso(), "reverted_at": None,
        })
        return {"ok": False, "status": "failed", "error_id": error_id,
                "message": debugging.safe_message(exc)}
    finally:
        try:
            conn.close()
        except Exception:
            pass


def revert(change_id: str, actor_id: str, actor_name: str = "") -> dict:
    """撤销一条已应用的变更（§8.7）。

    用 before_json 生成反向 SQL，执行后 status=reverted，新增一条 revert 记录。
    applied 24 小时内可 revert。
    """
    entry = _store.get(change_id)
    if not entry:
        return {"ok": False, "message": "变更记录不存在"}
    if entry.get("status") != "applied":
        return {"ok": False, "message": f"当前状态 {entry.get('status')} 不可撤销"}
    if not _is_within_hours(entry.get("applied_at", ""), 24):
        return {"ok": False, "message": "变更超过 24 小时，不可撤销"}

    before = json.loads(entry.get("before_json") or "[]")
    if not before:
        return {"ok": False, "message": "无 before 数据，无法撤销"}

    database = entry["db_name"]
    table = entry["table_name"]
    operation = entry["operation"]
    pk_col = None

    try:
        from core.agent import db_connect
        conn = db_connect(database=database, mode="write")
        conn.begin()
        pk_col = _get_pk_column(conn, database, table)
    except Exception as exc:
        error_id = debugging.record_error(exc, context="write_revert_connect")
        return {"ok": False, "status": "failed", "error_id": error_id,
                "message": f"撤销连接失败：{debugging.safe_message(exc)}"}

    try:
        reverse_sqls: list[str] = []
        if operation == "UPDATE" and pk_col:
            # 反向 UPDATE：SET 被改列 = 前值 WHERE 主键 = ...
            for row in before:
                set_parts = []
                for k, v in row.items():
                    if k == pk_col:
                        continue
                    set_parts.append(f"{k}={_sql_literal(v)}")
                if not set_parts:
                    continue
                reverse_sqls.append(
                    f"UPDATE {database}.{table} SET {', '.join(set_parts)} "
                    f"WHERE {pk_col}={_sql_literal(row.get(pk_col))}"
                )
        elif operation == "DELETE":
            # 反向 INSERT：用 before_json 的整行还原
            col_names = list(before[0].keys())
            for row in before:
                vals = ", ".join(_sql_literal(row.get(c)) for c in col_names)
                cols = ", ".join(col_names)
                reverse_sqls.append(
                    f"INSERT INTO {database}.{table} ({cols}) VALUES ({vals})"
                )
        elif operation == "INSERT" and pk_col:
            # 反向 DELETE：删除刚插入的行
            for row in before:
                reverse_sqls.append(
                    f"DELETE FROM {database}.{table} WHERE {pk_col}={_sql_literal(row.get(pk_col))}"
                )

        if not reverse_sqls:
            conn.rollback()
            return {"ok": False, "message": "无法生成反向 SQL"}

        total_affected = 0
        with conn.cursor() as cur:
            for rsql in reverse_sqls:
                cur.execute(rsql)
                total_affected += cur.rowcount

        conn.commit()

        # 原记录 status=reverted
        _store.update_status(change_id, "reverted", _now_iso())

        # 新增一条 revert 记录
        revert_id = uuid.uuid4().hex
        _store.insert({
            "id": revert_id,
            "proposal_id": entry.get("proposal_id", ""),
            "approval_id": entry.get("approval_id"),
            "actor_id": actor_id, "actor_name": actor_name,
            "approver_id": "", "approver_name": "",
            "db_name": database, "table_name": table,
            "operation": f"REVERT_{operation}",
            "sql_text": "; ".join(reverse_sqls),
            "sql_hash": _sql_hash("; ".join(reverse_sqls)),
            "where_clause": None,
            "estimated_rows": len(before),
            "affected_rows": total_affected,
            "before_json": json.dumps(before, ensure_ascii=False, default=str),
            "after_json": None,
            "status": "applied",
            "error_id": None,
            "idempotency_key": None,
            "applied_at": _now_iso(),
            "reverted_at": None,
        })
        return {"ok": True, "change_id": revert_id,
                "reverted_change_id": change_id,
                "affected_rows": total_affected, "status": "reverted"}

    except Exception as exc:
        try:
            conn.rollback()
        except Exception:
            pass
        error_id = debugging.record_error(exc, context="write_revert")
        return {"ok": False, "status": "failed", "error_id": error_id,
                "message": debugging.safe_message(exc)}
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _sql_literal(value) -> str:
    """把 Python 值转成 SQL 字面量（用于生成反向 SQL）。"""
    if value is None:
        return "NULL"
    if isinstance(value, (int, float)):
        return str(value)
    s = str(value).replace("'", "''")
    return f"'{s}'"


def history(limit: int = 50, offset: int = 0, status: str | None = None) -> list[dict]:
    """变更历史（分页）。"""
    return _store.list_history(limit=limit, offset=offset, status=status)
