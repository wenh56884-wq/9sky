"""流式 Agent 的人工审批闸门（Human-in-the-Loop）：落盘 + 风险分级双级流转。

设计要点（§5）：
- **受保护工具**：有副作用（写文件 / 删数据）的 Agent 工具纳入审批，风险分低/高两级。
- **双级流转**：低风险单级（操作者本人确认，``awaiting_operator``）；
  高风险双级（操作者触发 → 管理员审批，``awaiting_admin``，操作者不能自批）。
- **持久化**：审批落盘 ``data/approvals.sqlite3``，重启不丢失；内存 ``_pending`` 仅作加速索引。
- **超时**：等待超过 ``HITL_TIMEOUT_SECONDS`` 自动 ``decision=timeout``，拒绝执行。
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
APPROVALS_DB = DATA_DIR / "approvals.sqlite3"

# 风险等级
RISK_LOW = "low"
RISK_HIGH = "high"

# 审批阶段
STAGE_OPERATOR = "awaiting_operator"  # 低风险：等待操作者本人
STAGE_ADMIN = "awaiting_admin"        # 高风险：等待管理员
STAGE_DONE = "done"                   # 已决策 / 已超时


def _timeout_seconds() -> int:
    try:
        return max(30, min(int(os.getenv("HITL_TIMEOUT_SECONDS", "300")), 3600))
    except ValueError:
        return 300


def enabled() -> bool:
    return os.getenv("HITL_ENABLED", "1").strip().lower() not in {"0", "false", "no", "off"}


# 受保护工具与风险等级（§5.1）：有副作用的工具纳入审批；只读工具不保护
PROTECTED_TOOLS: dict[str, str] = {
    "forget": RISK_HIGH,            # 删除跨会话长期记忆，不可逆
    "forecast_metric": RISK_LOW,    # 写预测报告文件，有副作用但可逆
    "plot_last_result": RISK_LOW,   # 写图表 PNG 文件，有副作用但可逆
}

_DESCRIPTIONS = {
    "forget": "此操作将删除跨会话长期记忆，删除后无法恢复。请确认是否执行。",
    "forecast_metric": "此操作将生成预测报告文件（有副作用但可逆）。请确认是否执行。",
    "plot_last_result": "此操作将生成图表 PNG 文件（有副作用但可逆）。请确认是否执行。",
}


def description_for(tool: str) -> str:
    return _DESCRIPTIONS.get(tool, "此操作有副作用，请确认是否执行。")


def risk_level(tool_name: str) -> str:
    return PROTECTED_TOOLS.get(tool_name, RISK_LOW)


class ApprovalError(Exception):
    """审批操作错误（决策非法等）。"""


class ApprovalForbidden(ApprovalError):
    """审批决策权限不足（阶段与角色/操作者不匹配）。"""


@dataclass
class PendingApproval:
    id: str
    thread_id: str
    tool: str
    args: dict
    description: str
    risk_level: str
    stage: str
    operator_id: str
    created_at: float = field(default_factory=time.monotonic)
    event: threading.Event = field(default_factory=threading.Event)
    decision: dict | None = None
    # 写数据变更审批扩展列（§8.5）
    kind: str = "tool"               # tool | write
    payload_json: str | None = None  # 草案全文（含 sql_hash）
    required_role: int = 1           # 1/2/3
    expires_at: str | None = None
    idempotency_key: str | None = None


def _now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def _is_within_minutes(iso_time: str, minutes: int) -> bool:
    """判断 ISO 时间字符串是否在最近 N 分钟内（幂等复用判定）。"""
    if not iso_time:
        return False
    try:
        dt = datetime.strptime(iso_time, "%Y-%m-%dT%H:%M:%S")
        return (datetime.now() - dt).total_seconds() <= minutes * 60
    except (ValueError, TypeError):
        return False


def _stage_for_risk(risk: str) -> str:
    return STAGE_ADMIN if risk == RISK_HIGH else STAGE_OPERATOR


def _safe_args(raw) -> dict:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}


class _ApprovalStore:
    """``approvals.sqlite3`` 读写：审批落盘，重启不丢失。"""

    def __init__(self, db_path: Path | None = None) -> None:
        self._db_path = Path(db_path or APPROVALS_DB)
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
                """CREATE TABLE IF NOT EXISTS approvals (
                    id TEXT PRIMARY KEY,
                    thread_id TEXT,
                    tool TEXT,
                    args TEXT,
                    description TEXT,
                    risk_level TEXT,
                    stage TEXT,
                    decision TEXT,
                    operator_id TEXT,
                    approver_id TEXT,
                    created_at TEXT,
                    resolved_at TEXT
                )"""
            )
            # 迁移：为旧库补充写能力相关列（§8.5）
            existing = {row[1] for row in conn.execute("PRAGMA table_info(approvals)").fetchall()}
            for col, col_type in [
                ("kind", "TEXT DEFAULT 'tool'"),
                ("payload_json", "TEXT"),
                ("required_role", "INTEGER DEFAULT 1"),
                ("expires_at", "TEXT"),
                ("idempotency_key", "TEXT"),
            ]:
                if col not in existing:
                    conn.execute(f"ALTER TABLE approvals ADD COLUMN {col} {col_type}")
            # idempotency_key 唯一索引（部分索引：NULL 不参与）
            conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_approvals_idempotency "
                "ON approvals(idempotency_key) WHERE idempotency_key IS NOT NULL"
            )
            conn.commit()

    def insert(self, ap: PendingApproval, created_at_iso: str) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """INSERT INTO approvals
                    (id, thread_id, tool, args, description, risk_level, stage,
                     decision, operator_id, approver_id, created_at, resolved_at,
                     kind, payload_json, required_role, expires_at, idempotency_key)
                    VALUES (?,?,?,?,?,?,?,NULL,?,NULL,?,NULL,?,?,?,?,?)""",
                (
                    ap.id, ap.thread_id, ap.tool,
                    json.dumps(ap.args, ensure_ascii=False),
                    ap.description, ap.risk_level, ap.stage,
                    ap.operator_id, created_at_iso,
                    ap.kind, ap.payload_json, ap.required_role,
                    ap.expires_at, ap.idempotency_key,
                ),
            )
            conn.commit()

    def resolve(self, approval_id: str, decision: str, message: str, args: dict,
                approver_id: str, resolved_at_iso: str) -> bool:
        with self._lock, self._connect() as conn:
            cur = conn.execute(
                """UPDATE approvals
                    SET stage=?, decision=?, approver_id=?, resolved_at=?
                    WHERE id=? AND decision IS NULL""",
                (STAGE_DONE, decision, approver_id, resolved_at_iso, approval_id),
            )
            conn.commit()
            return cur.rowcount > 0

    def load(self, approval_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM approvals WHERE id=?", (approval_id,)).fetchone()
            return dict(row) if row else None

    def find_by_idempotency(self, key: str) -> dict | None:
        """按幂等键查找未决策的审批单（用于防 Agent 反复重试）。"""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM approvals WHERE idempotency_key=? AND decision IS NULL "
                "ORDER BY created_at DESC LIMIT 1",
                (key,),
            ).fetchone()
            return dict(row) if row else None

    def list_pending(self, kind: str | None = None) -> list[dict]:
        sql = "SELECT * FROM approvals WHERE decision IS NULL"
        params: list = []
        if kind:
            sql += " AND kind=?"
            params.append(kind)
        sql += " ORDER BY created_at DESC"
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
            out = []
            for r in rows:
                d = dict(r)
                d["args"] = _safe_args(d.get("args"))
                out.append(d)
            return out

    def count_pending(self) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS c FROM approvals WHERE decision IS NULL"
            ).fetchone()
            return int(row["c"])


class ApprovalManager:
    """进程内审批协调器：内存索引加速 + 落盘持久化。审批等待期间不执行受保护工具。"""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._pending: dict[str, PendingApproval] = {}
        self._store = _ApprovalStore()

    def create(self, thread_id: str, tool: str, args: dict, description: str = "",
               operator_id: str = "") -> PendingApproval:
        """创建一条审批：按风险定阶段，落盘 + 入内存索引。"""
        risk = PROTECTED_TOOLS.get(tool, RISK_LOW)
        stage = _stage_for_risk(risk)
        ap = PendingApproval(
            id=uuid.uuid4().hex,
            thread_id=thread_id or "",
            tool=tool,
            args=dict(args or {}),
            description=description or description_for(tool),
            risk_level=risk,
            stage=stage,
            operator_id=operator_id or "",
        )
        with self._lock:
            self._pending[ap.id] = ap
        self._store.insert(ap, _now_iso())
        return ap

    def create_write(self, thread_id: str, proposal: dict, operator_id: str = "") -> PendingApproval:
        """创建一条写数据变更审批单（kind=write）。

        幂等：同一 idempotency_key（或 sql_hash）10 分钟内重复提交，返回原草案，
        防止 Agent 反复重试生成多条审批单。
        """
        key = proposal.get("idempotency_key") or proposal.get("sql_hash") or ""
        if key:
            existing = self._store.find_by_idempotency(key)
            if existing and _is_within_minutes(existing.get("created_at", ""), 10):
                return self._rebuild_write_from_row(existing)
        risk = proposal.get("risk", "L1")
        required_role = int(proposal.get("required_role", 1))
        expires_at = proposal.get("expires_at")
        stage = STAGE_OPERATOR if required_role <= 1 else STAGE_ADMIN
        ap = PendingApproval(
            id=uuid.uuid4().hex,
            thread_id=thread_id or "",
            tool="propose_write",
            args={},
            description=proposal.get("summary")
            or f"{proposal.get('database')}.{proposal.get('table')} {proposal.get('operation', '')}",
            risk_level=risk,
            stage=stage,
            operator_id=operator_id or "",
            kind="write",
            payload_json=json.dumps(proposal, ensure_ascii=False),
            required_role=required_role,
            expires_at=expires_at,
            idempotency_key=key or None,
        )
        with self._lock:
            self._pending[ap.id] = ap
        self._store.insert(ap, _now_iso())
        return ap

    def _rebuild_write_from_row(self, row: dict) -> PendingApproval:
        """从库行重建写审批单（幂等复用时不重复落盘）。"""
        ap = PendingApproval(
            id=row["id"],
            thread_id=row.get("thread_id") or "",
            tool=row.get("tool") or "propose_write",
            args={},
            description=row.get("description") or "",
            risk_level=row.get("risk_level") or "L1",
            stage=row.get("stage") or STAGE_OPERATOR,
            operator_id=row.get("operator_id") or "",
            kind="write",
            payload_json=row.get("payload_json"),
            required_role=int(row.get("required_role") or 1),
            expires_at=row.get("expires_at"),
            idempotency_key=row.get("idempotency_key"),
        )
        with self._lock:
            self._pending[ap.id] = ap
        return ap

    def wait(self, request: PendingApproval, timeout_seconds: float | None = None) -> dict:
        """阻塞等待审批决策；超时则自动拒绝。支持跨线程/重启后经库落盘的决策。

        timeout_seconds 为空时用 HITL_TIMEOUT_SECONDS（默认 300s）；写草案按自身
        expires_at 传入剩余时长，避免「风险等级给了 2 小时、聊天流 5 分钟就判死」。
        """
        timeout = _timeout_seconds() if timeout_seconds is None else max(1.0, float(timeout_seconds))
        deadline = time.monotonic() + timeout
        while True:
            if request.event.is_set():
                return request.decision or {
                    "decision": "timeout",
                    "message": "审批超时，受保护操作未执行。",
                    "args": {},
                }
            # 兜底：决策可能已被 resolve 写入库（同进程事件未命中 / 重启后重建索引）
            db_row = self._store.load(request.id)
            if db_row and db_row.get("decision"):
                decision = {
                    "decision": db_row["decision"],
                    "message": "",
                    "args": _safe_args(db_row.get("args")),
                }
                request.decision = decision
                request.event.set()
                return decision
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                decision = {
                    "decision": "timeout",
                    "message": "审批超时，受保护操作未执行。",
                    "args": {},
                }
                request.decision = decision
                self._store.resolve(request.id, "timeout", decision["message"],
                                    decision["args"], "", _now_iso())
                with self._lock:
                    self._pending.pop(request.id, None)
                return decision
            request.event.wait(min(0.5, remaining))

    def resolve(self, approval_id: str, decision: str, message: str = "", args: dict | None = None,
                *, user_id: str | None = None, user_role: int | None = None) -> dict | None:
        """对一条待审批做决策。按阶段鉴权：低风险仅操作者本人、高风险需管理员。"""
        decision = str(decision or "").strip().lower()
        if decision not in {"approve", "reject", "edit"}:
            raise ApprovalError("decision 只能是 approve、reject 或 edit")
        if decision == "edit" and not isinstance(args, dict):
            raise ApprovalError("编辑审批必须提供 args 对象")
        with self._lock:
            request = self._pending.get(approval_id)
            if request is None:
                # 不在内存（如重启后），从库加载并重建索引
                row = self._store.load(approval_id)
                if row is None or row.get("decision"):
                    return None
                request = PendingApproval(
                    id=row["id"],
                    thread_id=row.get("thread_id") or "",
                    tool=row.get("tool") or "",
                    args=_safe_args(row.get("args")),
                    description=row.get("description") or "",
                    risk_level=row.get("risk_level") or RISK_LOW,
                    stage=row.get("stage") or STAGE_OPERATOR,
                    operator_id=row.get("operator_id") or "",
                    kind=row.get("kind") or "tool",
                    payload_json=row.get("payload_json"),
                    required_role=int(row.get("required_role") or 1),
                    expires_at=row.get("expires_at"),
                    idempotency_key=row.get("idempotency_key"),
                )
                self._pending[request.id] = request
            if request.decision is not None or request.stage == STAGE_DONE:
                return None
            # 阶段鉴权
            if request.kind == "write":
                # 写审批：按 required_role 鉴权（角色只从 token 反查，不来自请求体）
                if user_role is None or int(user_role) < request.required_role:
                    raise ApprovalForbidden(f"写变更需角色≥{request.required_role}审批。")
            elif request.stage == STAGE_OPERATOR:
                if not user_id or request.operator_id != user_id:
                    raise ApprovalForbidden("低风险审批仅触发操作者本人可决策。")
            elif request.stage == STAGE_ADMIN:
                if user_role is None or int(user_role) < 2:
                    raise ApprovalForbidden("高风险审批需管理员（角色≥2）决策。")
            request.decision = {
                "decision": decision,
                "message": str(message or "").strip(),
                "args": dict(args or {}),
            }
            request.event.set()
        self._store.resolve(request.id, decision, request.decision["message"],
                            request.decision["args"], user_id or "", _now_iso())
        return {"id": request.id, "thread_id": request.thread_id, "tool": request.tool, "decision": decision}

    def list_pending(self) -> list[dict]:
        """待审批列表（管理员/超管用）。"""
        rows = self._store.list_pending()
        return [
            {
                "id": r["id"],
                "thread_id": r["thread_id"],
                "tool": r["tool"],
                "description": r["description"],
                "risk_level": r["risk_level"],
                "stage": r["stage"],
                "operator_id": r["operator_id"],
                "created_at": r["created_at"],
            }
            for r in rows
        ]

    def list_pending_writes(self, min_role: int = 1) -> list[dict]:
        """待审批的写草案（按角色过滤：required_role <= min_role，§8.5）。"""
        rows = self._store.list_pending(kind="write")
        result = []
        for r in rows:
            req_role = int(r.get("required_role") or 1)
            if req_role <= min_role:
                result.append({
                    "id": r["id"],
                    "thread_id": r["thread_id"],
                    "tool": r["tool"],
                    "description": r["description"],
                    "risk_level": r["risk_level"],
                    "stage": r["stage"],
                    "operator_id": r["operator_id"],
                    "required_role": req_role,
                    "expires_at": r.get("expires_at"),
                    "payload": _safe_args(r.get("payload_json")),
                    "created_at": r["created_at"],
                })
        return result

    def get_write_payload(self, proposal_id: str) -> dict | None:
        """获取写草案的完整 payload（执行器用，含 sql_hash 等）。"""
        row = self._store.load(proposal_id)
        if not row or row.get("kind") != "write":
            return None
        return _safe_args(row.get("payload_json"))

    def get_record(self, approval_id: str) -> dict | None:
        """读取审批单原始记录（含 approver_id / decision / expires_at），用于审计与过期校验。"""
        return self._store.load(approval_id)

    def summary(self) -> dict:
        with self._lock:
            pending = len(self._pending)
        return {
            "enabled": enabled(),
            "protected_tools": list(PROTECTED_TOOLS.keys()),
            "risk_levels": dict(PROTECTED_TOOLS),
            "pending": pending,
            "persisted": True,
            "timeout_seconds": _timeout_seconds(),
        }


manager = ApprovalManager()


def requires_approval(tool_name: str) -> bool:
    return enabled() and tool_name in PROTECTED_TOOLS
