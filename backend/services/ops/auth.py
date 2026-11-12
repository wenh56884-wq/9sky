"""认证与权限：登录/登出/改密/用户管理 + Flask 鉴权装饰器。

鉴权矩阵（§4.2）通过两个装饰器落地：
- ``@require_auth``：要求已登录（最低角色 1），把当前用户挂到 ``flask.g``。
- ``@require_role(min_role)``：要求角色不低于 ``min_role``。

令牌经请求头 ``Authorization: Bearer <token>`` 传递，服务端存储（支持登出/踢人）。
"""
from __future__ import annotations

from functools import wraps

from flask import g, jsonify, request

from services.ops.auth_store import (
    ROLE_NAMES,
    store,
    verify_password,
)


def public_user(user: dict | None) -> dict | None:
    """剥离 password_hash 等敏感字段，返回可下发前端的用户对象。"""
    if not user:
        return None
    return {
        "id": user.get("id"),
        "username": user.get("username"),
        "role": user.get("role"),
        "role_name": ROLE_NAMES.get(user.get("role"), "未知"),
        "created_at": user.get("created_at"),
        "last_login": user.get("last_login"),
    }


# ------------------------------- 认证逻辑 ------------------------------- #
def login(username: str, password: str) -> dict:
    user = store.get_user_by_username((username or "").strip())
    if not user or not verify_password(password or "", user["password_hash"]):
        raise ValueError("用户名或密码错误")
    store.touch_last_login(user["id"])
    token, expires = store.create_session(user["id"])
    return {"token": token, "expires_at": expires, "user": public_user(user)}


def logout(token: str) -> bool:
    return store.delete_session(token)


def me(token: str) -> dict | None:
    user = store.get_session_user(token)
    return public_user(user) if user else None


def change_password(user_id: str, old_password: str, new_password: str) -> None:
    user = store.get_user(user_id)
    if not user:
        raise ValueError("用户不存在")
    if not verify_password(old_password or "", user["password_hash"]):
        raise ValueError("原密码错误")
    store.update_user_password(user_id, new_password)


# ------------------------------- 用户管理 ------------------------------- #
def list_users() -> list[dict]:
    return [public_user(u) for u in store.list_users()]


def create_user(username: str, password: str, role: int = 1) -> dict:
    user = store.create_user(username, password, int(role))
    return public_user(user)  # type: ignore[arg-type]


def update_user(user_id: str, role: int | None = None, password: str | None = None) -> dict:
    user = store.get_user(user_id)
    if not user:
        raise ValueError("用户不存在")
    if role is not None:
        store.update_user_role(user_id, int(role))
    if password:
        store.update_user_password(user_id, password)
    return public_user(store.get_user(user_id))  # type: ignore[arg-type]


def delete_user(user_id: str, *, self_id: str | None = None) -> None:
    store.delete_user(user_id, self_id=self_id)


# ------------------------------- 鉴权装饰器 ------------------------------- #
def _extract_token() -> str | None:
    header = request.headers.get("Authorization", "")
    if not header:
        return None
    parts = header.split(None, 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip() or None
    return None


def _auth_required(min_role: int):
    """装饰器工厂：校验 Bearer 令牌 → 加载用户 → 检查角色。"""

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            token = _extract_token()
            if not token:
                return jsonify({"error": "未登录或缺少令牌。"}), 401
            user = store.get_session_user(token)
            if not user:
                return jsonify({"error": "登录已失效，请重新登录。"}), 401
            g.current_user = public_user(user)
            g.current_user_id = user["id"]
            g.current_token = token
            if int(user["role"]) < min_role:
                return jsonify({"error": "权限不足，需要更高角色。"}), 403
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def require_auth(fn):
    """要求已登录（最低角色 1）。用法：``@require_auth``。"""
    return _auth_required(1)(fn)


def require_role(min_role: int):
    """要求角色不低于 ``min_role``。用法：``@require_role(2)``。"""
    return _auth_required(int(min_role))
