"""写数据执行器与审批测试（§8.11 验收用例）。

覆盖用例：#8 sql_hash 篡改、#9 幂等、#10 连接失败、#11 撤销、
#12 行数不符回滚、#13 角色鉴权、#14 before_json 最小化。
"""
import json
from unittest.mock import patch

import pytest

from services.ops import hitl, write_executor
from services.ops.write_executor import _ChangeLogStore, _sql_hash


# ───────────────────────── fixture ─────────────────────────

@pytest.fixture
def temp_store(tmp_path, monkeypatch):
    """临时 change_log 存储，避免污染真实数据库。"""
    db_path = tmp_path / "test_change_log.sqlite3"
    store = _ChangeLogStore(db_path=db_path)
    monkeypatch.setattr(write_executor, "_store", store)
    return store


@pytest.fixture
def temp_hitl_manager(tmp_path, monkeypatch):
    """临时审批存储的 ApprovalManager。"""
    db_path = tmp_path / "test_approvals.sqlite3"
    monkeypatch.setattr(hitl, "APPROVALS_DB", db_path)
    return hitl.ApprovalManager()


class _FakeCursor:
    """模拟 pymysql 游标，覆盖执行器所需的全部调用。"""

    def __init__(self, pk_col="customer_id", description_cols=None,
                 before_rows=None, rowcount=1, write_raises=False):
        self._pk_col = pk_col
        self._description = description_cols
        self._before_rows = before_rows or []
        self._rowcount = rowcount
        self._write_raises = write_raises

    def execute(self, sql, params=None):
        if self._write_raises:
            upper = sql.strip().upper()
            if upper.startswith("UPDATE ") and " SET " in upper:
                raise RuntimeError("Connection killed during execution")

    def fetchone(self):
        return (self._pk_col,) if self._pk_col else None

    def fetchall(self):
        return self._before_rows

    @property
    def description(self):
        return self._description

    @property
    def rowcount(self):
        return self._rowcount

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class _FakeConn:
    """模拟 pymysql 连接。"""

    def __init__(self, cursor):
        self._cursor = cursor
        self.commit_called = False
        self.rollback_called = False

    def cursor(self):
        return self._cursor

    def begin(self):
        pass

    def commit(self):
        self.commit_called = True

    def rollback(self):
        self.rollback_called = True

    def close(self):
        pass


def _make_mock_conn(affected_rows=1, before_rows=None,
                    pk_col="customer_id",
                    description_cols=None,
                    write_raises=False):
    """构造 mock MySQL 连接，覆盖执行器所需的全部调用。"""
    cursor = _FakeCursor(
        pk_col=pk_col, description_cols=description_cols,
        before_rows=before_rows, rowcount=affected_rows,
        write_raises=write_raises,
    )
    return _FakeConn(cursor)


def _make_proposal(**overrides):
    sql = "UPDATE customers SET status='停用' WHERE customer_id='C001'"
    proposal = {
        "proposal_id": "wp_test_001",
        "database": "telecom_operations_db",
        "table": "customers",
        "operation": "UPDATE",
        "sql": sql,
        "sql_hash": _sql_hash(sql),
        "where_clause": "customer_id='C001'",
        "reason": "测试",
        "estimated_rows": 1,
        "risk": "L1",
        "required_role": 1,
        "idempotency_key": _sql_hash(sql),
    }
    proposal.update(overrides)
    return proposal


# ───────────────────────── 用例 8：sql_hash 篡改 ─────────────────────────

def test_sql_hash_mismatch_rejected(temp_store):
    """用例8：审批后篡改 SQL → sql_hash 不匹配，拒绝执行。"""
    proposal = _make_proposal()
    proposal["sql"] = "UPDATE customers SET status='篡改' WHERE customer_id='C001'"
    # sql_hash 仍是原始值，与篡改后的 SQL 不匹配
    with patch("core.agent.db_connect") as mock_dc:
        result = write_executor.execute(proposal, "appr_001", "user1", "tester")
    assert not result["ok"]
    assert result["status"] == "failed"
    assert "sql_hash" in result["message"]
    # 失败记录已写入 change_log
    entries = temp_store.list_history()
    assert any(e["status"] == "failed" for e in entries)


# ───────────────────────── 用例 9：幂等 ─────────────────────────

def test_idempotency_single_execution(temp_store):
    """用例9：同一 idempotency_key 提交两次 → 只落库一次。"""
    proposal = _make_proposal()
    mock_conn = _make_mock_conn(
        affected_rows=1,
        before_rows=[("C001", "在网")],
        description_cols=[("customer_id",), ("status",)],
    )
    with patch("core.agent.db_connect", return_value=mock_conn):
        result1 = write_executor.execute(proposal, "appr_001", "user1")
        result2 = write_executor.execute(proposal, "appr_001", "user1")
    assert result1["ok"]
    assert result2["ok"]
    assert result2.get("idempotent_replay") is True
    assert result2["change_id"] == result1["change_id"]
    # change_log 只有一条 applied 记录
    applied = [e for e in temp_store.list_history() if e["status"] == "applied"]
    assert len(applied) == 1


def test_hitl_write_idempotency(temp_hitl_manager):
    """用例9（hitl 层）：同一 sql_hash 10 分钟内重复提交 → 返回原草案。"""
    proposal = {
        "proposal_id": "wp_test_009",
        "sql_hash": "sha256:same_hash",
        "idempotency_key": "sha256:same_hash",
        "required_role": 1,
        "risk": "L1",
        "database": "telecom_operations_db",
        "table": "customers",
        "operation": "UPDATE",
    }
    ap1 = temp_hitl_manager.create_write("thread1", proposal, operator_id="user1")
    ap2 = temp_hitl_manager.create_write("thread1", proposal, operator_id="user1")
    assert ap1.id == ap2.id


# ───────────────────────── 用例 10：连接失败 ─────────────────────────

def test_execute_connection_failure(temp_store):
    """用例10：执行中连接被 kill → 事务回滚，change_log.status=failed。"""
    proposal = _make_proposal()
    mock_conn = _make_mock_conn(
        affected_rows=1,
        before_rows=[("C001", "在网")],
        description_cols=[("customer_id",), ("status",)],
        write_raises=True,
    )
    with patch("core.agent.db_connect", return_value=mock_conn):
        result = write_executor.execute(proposal, "appr_001", "user1")
    assert not result["ok"]
    assert result["status"] == "failed"
    assert result.get("error_id")
    # change_log 有 failed 记录，error_id 可查
    failed = [e for e in temp_store.list_history() if e["status"] == "failed"]
    assert len(failed) == 1
    assert failed[0]["error_id"] == result["error_id"]


# ───────────────────────── 用例 11：撤销 ─────────────────────────

def test_revert_restored(temp_store):
    """用例11：撤销刚应用的变更 → 数据回到 before_json，status=reverted。"""
    proposal = _make_proposal()
    mock_conn = _make_mock_conn(
        affected_rows=1,
        before_rows=[("C001", "在网")],
        description_cols=[("customer_id",), ("status",)],
    )
    with patch("core.agent.db_connect", return_value=mock_conn):
        exec_result = write_executor.execute(proposal, "appr_001", "user1")
    assert exec_result["ok"]
    change_id = exec_result["change_id"]

    # 撤销
    with patch("core.agent.db_connect", return_value=mock_conn):
        revert_result = write_executor.revert(change_id, "user2", "admin")
    assert revert_result["ok"]
    assert revert_result["status"] == "reverted"

    # 原记录 status=reverted
    entry = temp_store.get(change_id)
    assert entry["status"] == "reverted"
    assert entry["reverted_at"] is not None


# ───────────────────────── 用例 12：行数不符回滚 ─────────────────────────

def test_rows_mismatch_rollback(temp_store):
    """用例12：affected_rows 与预估差 >20% → 自动回滚并告警。"""
    proposal = _make_proposal(estimated_rows=1)
    mock_conn = _make_mock_conn(
        affected_rows=5,  # 与预估 1 差 400% > 20%
        before_rows=[("C001", "在网")],
        description_cols=[("customer_id",), ("status",)],
    )
    with patch("core.agent.db_connect", return_value=mock_conn):
        result = write_executor.execute(proposal, "appr_001", "user1")
    assert not result["ok"]
    assert result["status"] == "failed"
    assert "20%" in result["message"]
    # 事务已回滚（commit 未调用）
    assert mock_conn.commit_called is False
    assert mock_conn.rollback_called is True


# ───────────────────────── 用例 13：角色鉴权 ─────────────────────────

def test_hitl_write_required_role_check(temp_hitl_manager):
    """用例13：role=1 批 L3 → ApprovalForbidden（403）。"""
    proposal = {
        "proposal_id": "wp_test_013",
        "database": "telecom_operations_db",
        "table": "customers",
        "operation": "UPDATE",
        "sql": "UPDATE customers SET status='x' WHERE customer_id='C001'",
        "sql_hash": "sha256:test013",
        "risk": "L3",
        "required_role": 3,
        "estimated_rows": 2000,
        "idempotency_key": "sha256:test013",
    }
    ap = temp_hitl_manager.create_write("thread1", proposal, operator_id="user1")
    # role=1 尝试批准 L3 → 拒绝
    with pytest.raises(hitl.ApprovalForbidden):
        temp_hitl_manager.resolve(ap.id, "approve",
                                  user_id="user1", user_role=1)
    # role=3 可以批准
    result = temp_hitl_manager.resolve(ap.id, "approve",
                                       user_id="user3", user_role=3)
    assert result is not None


# ───────────────────────── 用例 14：before_json 最小化 ─────────────────────────

def test_before_json_only_pk_and_changed_cols(temp_store):
    """用例14：before_json 只含主键与被改列，无整行。"""
    proposal = _make_proposal()
    mock_conn = _make_mock_conn(
        affected_rows=1,
        before_rows=[("C001", "在网")],
        description_cols=[("customer_id",), ("status",)],
    )
    with patch("core.agent.db_connect", return_value=mock_conn):
        result = write_executor.execute(proposal, "appr_001", "user1")
    assert result["ok"]
    entry = temp_store.get(result["change_id"])
    before = json.loads(entry["before_json"])
    assert len(before) == 1
    row = before[0]
    # 只含主键 customer_id 与被改列 status，不含其他列
    assert set(row.keys()) == {"customer_id", "status"}
    assert row["customer_id"] == "C001"


# ───────────────────────── hitl 写审批 payload ─────────────────────────

def test_hitl_write_payload_retrieval(temp_hitl_manager):
    """get_write_payload 返回完整草案（执行器用）。"""
    proposal = {
        "proposal_id": "wp_test_payload",
        "sql_hash": "sha256:payload",
        "idempotency_key": "sha256:payload",
        "required_role": 2,
        "risk": "L2",
        "database": "telecom_operations_db",
        "table": "customers",
        "operation": "UPDATE",
        "sql": "UPDATE customers SET status='x' WHERE customer_id='C001'",
        "estimated_rows": 10,
    }
    ap = temp_hitl_manager.create_write("thread1", proposal, operator_id="user1")
    payload = temp_hitl_manager.get_write_payload(ap.id)
    assert payload is not None
    assert payload["sql_hash"] == "sha256:payload"
    assert payload["required_role"] == 2


def test_hitl_write_list_pending_filters_by_role(temp_hitl_manager):
    """list_pending_writes 按角色过滤：required_role <= min_role。"""
    l1 = {"proposal_id": "wp_l1", "sql_hash": "h1", "required_role": 1,
          "risk": "L1", "database": "d", "table": "t", "operation": "UPDATE"}
    l3 = {"proposal_id": "wp_l3", "sql_hash": "h3", "required_role": 3,
          "risk": "L3", "database": "d", "table": "t", "operation": "UPDATE"}
    ap1 = temp_hitl_manager.create_write("t", l1, operator_id="u1")
    ap3 = temp_hitl_manager.create_write("t", l3, operator_id="u1")
    # role=1 只看得到 L1
    items_r1 = temp_hitl_manager.list_pending_writes(min_role=1)
    ids_r1 = {i["id"] for i in items_r1}
    assert ap1.id in ids_r1
    assert ap3.id not in ids_r1
    # role=3 看得到全部
    items_r3 = temp_hitl_manager.list_pending_writes(min_role=3)
    ids_r3 = {i["id"] for i in items_r3}
    assert ap1.id in ids_r3
    assert ap3.id in ids_r3
