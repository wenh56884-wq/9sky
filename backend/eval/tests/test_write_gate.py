"""写数据风控闸门测试（§8.11 验收用例）。

覆盖用例：#1 无 WHERE、#2 非白名单表、#3 敏感列、#4 影响 2000 行判 L3，
以及多语句/DDL/INTO OUTFILE/跨库/超限等攻击用例。
"""
import pytest

from services.ops import write_gate
from services.ops.write_gate import POLICY, RISK_L1, RISK_L2, RISK_L3, evaluate


@pytest.fixture(autouse=True)
def _clean_policy():
    """每个测试前后清理 table_whitelist，避免副作用。"""
    saved = dict(POLICY["table_whitelist"])
    POLICY["table_whitelist"].clear()
    yield
    POLICY["table_whitelist"].clear()
    POLICY["table_whitelist"].update(saved)


def _wl(db, table, cols=None):
    """添加表白名单。"""
    POLICY["table_whitelist"][f"{db}.{table}"] = {"columns": cols or []}


# ---- 用例 1：UPDATE 无 WHERE ----
def test_no_where_update_rejected():
    _wl("telecom_operations_db", "customers")
    result = evaluate(
        "UPDATE customers SET status='x'",
        database="telecom_operations_db", table="customers", estimated_rows=1,
    )
    assert not result["ok"]
    assert "WHERE" in result["reject_reason"]
    assert "forbid_without_where" in result["hits"]


# ---- 用例 2：非白名单表 ----
def test_table_not_whitelisted_rejected():
    result = evaluate(
        "UPDATE customers SET status='x' WHERE customer_id='C001'",
        database="telecom_operations_db", table="customers", estimated_rows=1,
    )
    assert not result["ok"]
    assert "未开启写入" in result["reject_reason"]
    assert "table_not_whitelisted" in result["hits"]


# ---- 用例 3：敏感列 ----
def test_sensitive_column_rejected():
    _wl("telecom_operations_db", "customers")
    result = evaluate(
        "UPDATE customers SET phone='13800138000' WHERE customer_id='C001'",
        database="telecom_operations_db", table="customers", estimated_rows=1,
    )
    assert not result["ok"]
    assert "敏感列" in result["reject_reason"]
    assert "sensitive_column" in result["hits"]


def test_sensitive_column_insert_rejected():
    _wl("telecom_operations_db", "customers")
    result = evaluate(
        "INSERT INTO customers (customer_id, national_id) VALUES ('C003', '110101199001011234')",
        database="telecom_operations_db", table="customers", estimated_rows=1,
    )
    assert not result["ok"]
    assert "敏感列" in result["reject_reason"]


# ---- 用例 4：影响 2000 行判 L3 ----
def test_2000_rows_l3():
    _wl("telecom_operations_db", "customers")
    result = evaluate(
        "UPDATE customers SET status='停用' WHERE status='在网'",
        database="telecom_operations_db", table="customers", estimated_rows=2000,
    )
    assert result["ok"]
    assert result["risk"] == RISK_L3
    assert result["required_role"] == 3


def test_rows_over_limit_rejected():
    """影响行数 >5000 → 不受理。"""
    _wl("telecom_operations_db", "customers")
    result = evaluate(
        "UPDATE customers SET status='x' WHERE status='在网'",
        database="telecom_operations_db", table="customers", estimated_rows=6000,
    )
    assert not result["ok"]
    assert "超过上限" in result["reject_reason"]
    assert "rows_over_limit" in result["hits"]


# ---- 攻击用例：多语句 ----
def test_multiple_statements_rejected():
    _wl("telecom_operations_db", "customers")
    result = evaluate(
        "UPDATE customers SET status='x' WHERE customer_id='C001'; "
        "DELETE FROM customers WHERE customer_id='C002'",
        database="telecom_operations_db", table="customers", estimated_rows=1,
    )
    assert not result["ok"]
    assert "single_statement" in result["hits"]


# ---- 攻击用例：DDL ----
def test_ddl_rejected():
    result = evaluate("CREATE TABLE foo (id INT)", database="telecom_operations_db")
    assert not result["ok"]
    assert "operation_not_allowed" in result["hits"]


def test_drop_statement_rejected():
    """DROP 作为首关键字 → 被操作检查拒绝（非 INSERT/UPDATE/DELETE）。"""
    _wl("telecom_operations_db", "customers")
    result = evaluate("DROP TABLE customers", database="telecom_operations_db")
    assert not result["ok"]
    assert "operation_not_allowed" in result["hits"]


def test_forbid_statement_in_subquery_rejected():
    """写操作中含 INTO OUTFILE 子查询 → 被 forbid_statements 拒绝。"""
    _wl("telecom_operations_db", "customers")
    result = evaluate(
        "UPDATE customers SET status='x' WHERE customer_id IN "
        "(SELECT id FROM other INTO OUTFILE '/tmp/x')",
        database="telecom_operations_db", table="customers", estimated_rows=1,
    )
    assert not result["ok"]
    assert "forbid_statements" in result["hits"]


# ---- 攻击用例：INTO OUTFILE ----
def test_into_outfile_rejected():
    """写操作中含 INTO OUTFILE → 被 forbid_statements 拒绝。"""
    _wl("telecom_operations_db", "customers")
    result = evaluate(
        "UPDATE customers SET status='x' WHERE customer_id IN "
        "(SELECT id FROM other INTO OUTFILE '/tmp/x')",
        database="telecom_operations_db", table="customers", estimated_rows=1,
    )
    assert not result["ok"]
    assert "forbid_statements" in result["hits"]


# ---- 攻击用例：跨库 ----
def test_cross_database_rejected():
    _wl("telecom_operations_db", "customers")
    _wl("financial_asset_management", "products")
    result = evaluate(
        "UPDATE telecom_operations_db.customers c "
        "JOIN financial_asset_management.products p ON c.id=p.id "
        "SET c.status='x' WHERE c.customer_id='C001'",
        database="telecom_operations_db", table="customers", estimated_rows=1,
    )
    assert not result["ok"]
    assert "cross_database" in result["hits"]


# ---- 正向用例：合法 INSERT ----
def test_valid_insert_l1():
    _wl("telecom_operations_db", "customers")
    result = evaluate(
        "INSERT INTO customers (customer_id, customer_name) VALUES ('C003', '新客户')",
        database="telecom_operations_db", table="customers", estimated_rows=1,
    )
    assert result["ok"]
    assert result["risk"] == RISK_L1
    assert result["required_role"] == 1


# ---- 正向用例：合法 UPDATE L1 ----
def test_valid_update_l1():
    _wl("telecom_operations_db", "customers")
    result = evaluate(
        "UPDATE customers SET status='停用' WHERE customer_id='C001'",
        database="telecom_operations_db", table="customers", estimated_rows=2,
    )
    assert result["ok"]
    assert result["risk"] == RISK_L1


# ---- 正向用例：合法 UPDATE L2 ----
def test_valid_update_l2():
    _wl("telecom_operations_db", "customers")
    result = evaluate(
        "UPDATE customers SET status='停用' WHERE status='在网'",
        database="telecom_operations_db", table="customers", estimated_rows=100,
    )
    assert result["ok"]
    assert result["risk"] == RISK_L2
    assert result["required_role"] == 2


# ---- 正向用例：DELETE 带 WHERE ----
def test_delete_with_where_passes():
    _wl("telecom_operations_db", "customers")
    result = evaluate(
        "DELETE FROM customers WHERE customer_id='C001'",
        database="telecom_operations_db", table="customers", estimated_rows=1,
    )
    assert result["ok"]
    assert result["risk"] == RISK_L1


# ---- 超管运行时配置白名单（PUT /api/writes/whitelist 的服务层） ----
def test_normalize_whitelist_rejects_bad_key():
    with pytest.raises(ValueError, match="表名不合法"):
        write_gate.normalize_whitelist({"customers": {"columns": []}})
    with pytest.raises(ValueError, match="表名不合法"):
        write_gate.normalize_whitelist({"db.customers; DROP": {"columns": []}})


def test_normalize_whitelist_rejects_bad_columns():
    with pytest.raises(ValueError, match="columns 必须是数组"):
        write_gate.normalize_whitelist({"db.customers": {"columns": "a,b"}})
    with pytest.raises(ValueError, match="列名不合法"):
        write_gate.normalize_whitelist({"db.customers": {"columns": ["ok", "bad col"]}})


def test_save_whitelist_persists_and_denies_by_default(tmp_path, monkeypatch):
    monkeypatch.setattr(write_gate, "WHITELIST_FILE", tmp_path / "write_whitelist.json")
    # 保存后立即生效
    saved = write_gate.save_whitelist({"telecom_operations_db.customers": {"columns": ["customer_status"]}})
    assert "telecom_operations_db.customers" in saved
    result = evaluate("UPDATE customers SET customer_status='停用' WHERE customer_id='C1'",
                      database="telecom_operations_db", table="customers", estimated_rows=1)
    assert result["ok"]
    # 清空 → 全部拒绝
    write_gate.save_whitelist({})
    result = evaluate("UPDATE customers SET customer_status='停用' WHERE customer_id='C1'",
                      database="telecom_operations_db", table="customers", estimated_rows=1)
    assert not result["ok"]
    assert "table_not_whitelisted" in result["hits"]


# ---- 批量新增：多行 VALUES 解析与分级 ----
def test_insert_row_count_multi_rows():
    assert write_gate.insert_row_count(
        "INSERT INTO t (a,b) VALUES (1,'x'),(2,'y'),(3,'z')"
    ) == 3


def test_insert_parser_ignores_commas_and_parens_in_strings():
    sql = "INSERT INTO t (a,b) VALUES (1, 'a,b'), (2, 'c(d)')"
    cols, rows = write_gate.parse_insert(sql)
    assert cols == ["a", "b"]
    assert len(rows) == 2
    assert rows[0][1] == "'a,b'"
    assert rows[1][1] == "'c(d)'"


def test_insert_set_form_supported():
    parsed = write_gate.parse_insert("INSERT INTO t SET a=1, b='x'")
    assert parsed is not None
    cols, rows = parsed
    assert cols == ["a", "b"]
    assert len(rows) == 1


def test_insert_select_rejected():
    _wl("telecom_operations_db", "customers")
    result = evaluate(
        "INSERT INTO customers (customer_id) SELECT customer_id FROM customers",
        database="telecom_operations_db", table="customers",
    )
    assert not result["ok"]
    assert "insert_not_supported" in result["hits"]


def test_batch_insert_100_rows_is_l2():
    _wl("telecom_operations_db", "customers")
    values = ",".join(f"('C{i:04d}')" for i in range(100))
    sql = f"INSERT INTO customers (customer_id) VALUES {values}"
    result = evaluate(sql, database="telecom_operations_db", table="customers")
    assert result["ok"]
    assert result["estimated_rows"] == 100
    assert result["risk"] == RISK_L2
    assert result["required_role"] == 2


def test_batch_insert_over_5000_rejected():
    _wl("telecom_operations_db", "customers")
    values = ",".join(f"('C{i}')" for i in range(5001))
    sql = f"INSERT INTO customers (customer_id) VALUES {values}"
    result = evaluate(sql, database="telecom_operations_db", table="customers")
    assert not result["ok"]
    assert "rows_over_limit" in result["hits"]
