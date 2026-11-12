"""认证与用户体系数据层：`auth.sqlite3` 读写、bcrypt 哈希、会话令牌、首次建超管。

独立于现有 4 个库（checkpoints / memory / tables / vector），不污染既有数据。
首次启动 users 表为空时，从 `.env` 读 `ADMIN_USERNAME`/`ADMIN_PASSWORD` 自动创建
role=3 超级管理员。
"""
from __future__ import annotations

import os
import sqlite3
import threading
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import bcrypt
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

DATA_DIR = PROJECT_ROOT / "data"
AUTH_DB = DATA_DIR / "auth.sqlite3"

# 角色用整数表示：0 访客 / 1 普通用户 / 2 管理员 / 3 超级管理员
ROLE_VISITOR = 0
ROLE_USER = 1
ROLE_ADMIN = 2
ROLE_SUPER = 3
ROLE_NAMES = {0: "访客", 1: "普通用户", 2: "管理员", 3: "超级管理员"}


def _now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def _bcrypt_rounds() -> int:
    try:
        return max(4, min(int(os.getenv("BCRYPT_ROUNDS", "12")), 31))
    except ValueError:
        return 12


def hash_password(password: str) -> str:
    """bcrypt 哈希（自带盐），返回可存库的字符串。"""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=_bcrypt_rounds())).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """校验明文密码与 bcrypt 哈希是否匹配。"""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def _session_ttl_hours() -> int:
    try:
        return max(1, min(int(os.getenv("SESSION_TTL_HOURS", "168")), 8760))
    except ValueError:
        return 168


class AuthStore:
    """线程安全的 auth.sqlite3 访问层。"""

    def __init__(self, db_path: Path | None = None) -> None:
        self._db_path = Path(db_path or AUTH_DB)
        self._lock = threading.RLock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self._db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        return conn

    def _init_db(self) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    role INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    last_login TEXT
                )"""
            )
            conn.execute(
                """CREATE TABLE IF NOT EXISTS sessions (
                    token TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )"""
            )
            conn.commit()

    # ------------------------------- users ------------------------------- #
    def count_users(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()
            return int(row["c"])

    def create_user(self, username: str, password: str, role: int = ROLE_USER) -> dict:
        username = (username or "").strip()
        if not username:
            raise ValueError("用户名不能为空")
        if not password:
            raise ValueError("密码不能为空")
        role = int(role)
        if role not in ROLE_NAMES:
            raise ValueError("角色非法，必须是 0/1/2/3")
        with self._lock, self._connect() as conn:
            existing = conn.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
            if existing:
                raise ValueError("用户名已存在")
            uid = uuid.uuid4().hex
            conn.execute(
                "INSERT INTO users (id, username, password_hash, role, created_at) VALUES (?,?,?,?,?)",
                (uid, username, hash_password(password), role, _now_iso()),
            )
            conn.commit()
        return self.get_user(uid)  # type: ignore[return-value]

    def get_user(self, user_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
            return dict(row) if row else None

    def get_user_by_username(self, username: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
            return dict(row) if row else None

    def list_users(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, username, role, created_at, last_login FROM users ORDER BY role DESC, created_at"
            ).fetchall()
            return [dict(r) for r in rows]

    def update_user_role(self, user_id: str, role: int) -> bool:
        role = int(role)
        if role not in ROLE_NAMES:
            raise ValueError("角色非法，必须是 0/1/2/3")
        with self._lock, self._connect() as conn:
            cur = conn.execute("UPDATE users SET role=? WHERE id=?", (role, user_id))
            conn.commit()
            return cur.rowcount > 0

    def update_user_password(self, user_id: str, new_password: str) -> bool:
        if not new_password:
            raise ValueError("密码不能为空")
        with self._lock, self._connect() as conn:
            cur = conn.execute(
                "UPDATE users SET password_hash=? WHERE id=?", (hash_password(new_password), user_id)
            )
            conn.commit()
            return cur.rowcount > 0

    def delete_user(self, user_id: str, *, self_id: str | None = None) -> bool:
        """删除用户并连带清会话。保护：不能删自己、不能删最后一个超管。"""
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
            if not row:
                return False
            if self_id and user_id == self_id:
                raise ValueError("不能删除自己")
            if row["role"] == ROLE_SUPER:
                admin_count = conn.execute(
                    "SELECT COUNT(*) AS c FROM users WHERE role=?", (ROLE_SUPER,)
                ).fetchone()["c"]
                if int(admin_count) <= 1:
                    raise ValueError("不能删除最后一个超级管理员")
            conn.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
            conn.execute("DELETE FROM users WHERE id=?", (user_id,))
            conn.commit()
            return True

    def touch_last_login(self, user_id: str) -> None:
        with self._lock, self._connect() as conn:
            conn.execute("UPDATE users SET last_login=? WHERE id=?", (_now_iso(), user_id))
            conn.commit()

    # ------------------------------ sessions ------------------------------ #
    def create_session(self, user_id: str) -> tuple[str, str]:
        token = uuid.uuid4().hex
        expires = datetime.now() + timedelta(hours=_session_ttl_hours())
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO sessions (token, user_id, created_at, expires_at) VALUES (?,?,?,?)",
                (token, user_id, _now_iso(), expires.strftime("%Y-%m-%dT%H:%M:%S")),
            )
            conn.commit()
        return token, expires.strftime("%Y-%m-%dT%H:%M:%S")

    def get_session_user(self, token: str) -> dict | None:
        """根据令牌取用户；令牌无效或已过期返回 None（过期会话顺手清理）。"""
        if not token:
            return None
        with self._connect() as conn:
            row = conn.execute(
                "SELECT s.token, s.expires_at, u.id, u.username, u.password_hash, u.role, "
                "u.created_at, u.last_login "
                "FROM sessions s JOIN users u ON u.id = s.user_id WHERE s.token=?",
                (token,),
            ).fetchone()
            if not row:
                return None
            expires = row["expires_at"]
            if expires and expires < _now_iso():
                conn.execute("DELETE FROM sessions WHERE token=?", (token,))
                conn.commit()
                return None
            return dict(row)

    def delete_session(self, token: str) -> bool:
        if not token:
            return False
        with self._lock, self._connect() as conn:
            cur = conn.execute("DELETE FROM sessions WHERE token=?", (token,))
            conn.commit()
            return cur.rowcount > 0

    def bootstrap_admin(self) -> dict | None:
        """users 表为空时，从环境变量创建首个超管（默认 admin/admin123）。"""
        if self.count_users() > 0:
            return None
        username = (os.getenv("ADMIN_USERNAME") or "admin").strip() or "admin"
        password = (os.getenv("ADMIN_PASSWORD") or "admin123").strip() or "admin123"
        user = self.create_user(username, password, role=ROLE_SUPER)
        return user


# 模块级单例：导入即建表 + 首次启动建超管
store = AuthStore()
store.bootstrap_admin()
