"""注册、输入边界与「唯一超级管理员」约束测试。

覆盖：
- 用户名/密码边界（长度、字符集、bcrypt 72 字节上限、纯空白）；
- 开放注册固定 role=1、重名拒绝、注册开关、限速；
- 超管唯一：禁止建第二个超管、禁止提升为超管、禁止降级唯一超管、禅让原子性；
- 注册/建用户请求体传 role 无效（提权只能走超管接口）。

全部使用临时 sqlite 库，不触碰真实 data/auth.sqlite3。
"""
import io
import os

import pytest

from services.ops.auth_store import (
    ROLE_ADMIN,
    ROLE_SUPER,
    ROLE_USER,
    AuthStore,
    validate_password,
    validate_username,
)
from services.ops import auth as auth_service


@pytest.fixture()
def store(tmp_path, monkeypatch):
    """把服务层的 store 换成临时库，避免污染真实用户数据。"""
    temp = AuthStore(tmp_path / "auth.sqlite3")
    monkeypatch.setattr(auth_service, "store", temp)
    # 限速计数是模块级列表：每个用例清零，避免相互影响
    monkeypatch.setattr(auth_service, "_REG_HITS", [])
    monkeypatch.setenv("REG_RATE_LIMIT", "100")
    monkeypatch.setenv("REG_ENABLED", "1")
    return temp


@pytest.fixture()
def bootstrapped(store):
    user = store.bootstrap_admin()
    assert user and user["role"] == ROLE_SUPER
    return user


# ------------------------------- 输入边界 ------------------------------- #
@pytest.mark.parametrize("name", ["", "  ", "ab", "x" * 33, "bad name", "user@host", "---", "a/b"])
def test_validate_username_rejects(name):
    with pytest.raises(ValueError):
        validate_username(name)


@pytest.mark.parametrize("name", ["abc", "张三丰", "user_01", "user-name", "x" * 32])
def test_validate_username_accepts(name):
    assert validate_username(name) == name.strip()


@pytest.mark.parametrize("pwd", ["", "   ", "12345", "x" * 73, "中" * 30])
def test_validate_password_rejects(pwd):
    with pytest.raises(ValueError):
        validate_password(pwd)


@pytest.mark.parametrize("pwd", ["123456", "x" * 72, "中" * 24])   # 72 字节边界内
def test_validate_password_accepts(pwd):
    assert validate_password(pwd) == pwd


# ------------------------------- 开放注册 ------------------------------- #
def test_register_creates_role_user(store):
    user = auth_service.register("新同事", "abc123")
    assert user["role"] == ROLE_USER
    assert user["username"] == "新同事"
    # 注册即入库，可正常登录
    result = auth_service.login("新同事", "abc123")
    assert result["user"]["role"] == ROLE_USER
    assert result["token"]


def test_register_ignores_role_and_confirm_mismatch(store):
    user = auth_service.register("普通用户", "abc123", confirm="abc123")
    assert user["role"] == ROLE_USER
    with pytest.raises(ValueError, match="不一致"):
        auth_service.register("另一个人", "abc123", confirm="abc124")


def test_register_duplicate_rejected(store):
    auth_service.register("重复名", "abc123")
    with pytest.raises(ValueError, match="已存在"):
        auth_service.register("重复名", "abc123")


def test_register_disabled(store, monkeypatch):
    monkeypatch.setenv("REG_ENABLED", "0")
    with pytest.raises(PermissionError):
        auth_service.register("关了注册", "abc123")


def test_register_rate_limited(store, monkeypatch):
    monkeypatch.setenv("REG_RATE_LIMIT", "2")
    auth_service.register("限速甲", "abc123")
    auth_service.register("限速乙", "abc123")
    with pytest.raises(RuntimeError, match="频繁"):
        auth_service.register("限速丙", "abc123")


# --------------------------- 唯一超级管理员约束 --------------------------- #
def test_cannot_create_second_super(bootstrapped):
    with pytest.raises(ValueError, match="超级管理员已存在"):
        auth_service.create_user("超管二号", "abc123", ROLE_SUPER)


def test_cannot_promote_to_super(bootstrapped):
    u = auth_service.register("想升超管", "abc123")
    with pytest.raises(ValueError, match="禅让"):
        auth_service.update_user(u["id"], role=ROLE_SUPER)


def test_cannot_demote_only_super(bootstrapped):
    with pytest.raises(ValueError, match="不能降级唯一超级管理员"):
        auth_service.update_user(bootstrapped["id"], role=ROLE_ADMIN)


def test_cannot_delete_only_super(bootstrapped):
    with pytest.raises(ValueError, match="最后一个超级管理员"):
        auth_service.delete_user(bootstrapped["id"])


def test_super_can_assign_admin(bootstrapped):
    u = auth_service.register("升管理员", "abc123")
    updated = auth_service.update_user(u["id"], role=ROLE_ADMIN)
    assert updated["role"] == ROLE_ADMIN


def test_promote_super_transfers_atomically(bootstrapped, store):
    successor = auth_service.register("继任者", "abc123")
    old_token, _ = store.create_session(bootstrapped["id"])

    result = auth_service.promote_super(bootstrapped["id"], successor["id"])

    assert result["role"] == ROLE_SUPER
    assert store.get_user(bootstrapped["id"])["role"] == ROLE_ADMIN
    # 禅让后旧超管会话立即失效
    assert store.get_session_user(old_token) is None
    # 任何时刻恰好一个超管
    supers = [u for u in store.list_users() if u["role"] == ROLE_SUPER]
    assert len(supers) == 1 and supers[0]["id"] == successor["id"]


def test_promote_super_requires_current_super(bootstrapped):
    admin = auth_service.register("管理员甲", "abc123")
    auth_service.update_user(admin["id"], role=ROLE_ADMIN)
    other = auth_service.register("普通人乙", "abc123")
    with pytest.raises(ValueError, match="只有现任超级管理员"):
        auth_service.promote_super(admin["id"], other["id"])


def test_bootstrap_only_when_empty(bootstrapped, store):
    # users 表非空时不再创建第二个超管
    assert store.bootstrap_admin() is None
    supers = [u for u in store.list_users() if u["role"] == ROLE_SUPER]
    assert len(supers) == 1
