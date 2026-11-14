"""propose_write 工具层测试：批量新增的预览与影响行数。"""
from core.tools.write_tools import _compute_estimated_rows, _compute_preview


def test_insert_preview_multiple_rows():
    """多行 VALUES：预览展示全部行（上限 20），列名与值逐一对应。"""
    sql = ("INSERT INTO customers (customer_id, status, note) VALUES "
           "('C001','在网','首条'), ('C002','停用','第二条'), ('C003','在网','第三条')")
    preview = _compute_preview(None, "telecom_operations_db", "customers",
                               "INSERT", sql, "")
    assert preview["columns"] == ["customer_id", "status", "note"]
    assert len(preview["after"]) == 3
    assert preview["before"] == []
    assert preview["after"][1] == ["C002", "停用", "第二条"]


def test_insert_preview_respects_sample_limit():
    sql = "INSERT INTO t (a) VALUES " + ",".join(f"({i})" for i in range(25))
    preview = _compute_preview(None, "d", "t", "INSERT", sql, "")
    assert len(preview["after"]) == preview["sample_limit"] == 20


def test_estimated_rows_matches_values_groups():
    sql = "INSERT INTO t (a,b) VALUES (1,'x'),(2,'y'),(3,'z')"
    assert _compute_estimated_rows(None, "d", "t", "INSERT", "", sql) == 3


def test_estimated_rows_update_unchanged():
    # UPDATE 仍依赖调用方用 SELECT COUNT(*) 真算的结果（这里没有连接，返回 0 仅为占位）
    assert _compute_estimated_rows(None, "d", "t", "UPDATE", "", "UPDATE t SET a=1 WHERE id=1") == 0
