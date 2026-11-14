"""认证与用户体系数据层：`auth.sqlite3` 读写、bcrypt 哈希、会话令牌、首次建超管。

独立于现有 4 个库（checkpoints / memory / tables / vector），不污染既有数据。
首次启动 users 表为空时，从 `.env` 读 `ADMIN_USERNAME`/`ADMIN_PASSWORD` 自动创建
role=3 超级管理员。

约束（业务规则硬约束，所有入口都绕不过）：
- **超级管理员全局唯一**：禁止再建第二个超管（``create_user``）；禁止直接把用户
  升为超管（``update_user_role``）；唯一超管可通过 ``promote_super`` 原子禅让
  （同事务内旧超管降为管理员、新超管生效，不出现双超管/零超管窗口）。
- **输入边界**：用户名 3~32 字符且限安全字符集；密码 6~72 字节（bcrypt 算法
  只取前 72 字节，超长不拒绝会造成「设置了长密码却登不上」的隐性 bug）。
"""
from __future__ import annotations

import os
import re
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

# 用户名规则：3~32 个字符；允许中文、字母、数字、下划线、连字符，且至少含一个
# 字母/数字/中文（避免纯符号 "---" 这类无意义用户名）。用 re.UNICODE 语义，
# \w 在 str 模式下天然覆盖中文。
_USERNAME_RE = re.compile(r"^(?=.*\w)[\w\-]{3,32}$", re.UNICODE)

# bcrypt 算法硬限制：只处理密码的前 72 字节，超长部分被静默丢弃——
# 必须在入口显式拒绝，否则用户「设置成功却永远登不上」
_BCRYPT_MAX_BYTES = 72


def validate_username(username: str) -> str:
    """校验并归一用户名：去首尾空白，检查长度与字符集。不合法抛 ValueError。"""
    name = (username or "").strip()
    if not name:
        raise ValueError("用户名不能为空")
    if len(name) < 3:
        raise ValueError("用户名至少 3 个字符")
    if len(name) > 32:
        raise ValueError("用户名最多 32 个字符")
    if not _USERNAME_RE.match(name):
        raise ValueError("用户名只能包含中文、字母、数字、下划线或连字符")
    return name


def validate_password(password: str) -> str:
    """校验密码：非空、非纯空白、6~72 字节（UTF-8 计）。不合法抛 ValueError。"""
    pwd = password or ""
    if not pwd.strip():
        raise ValueError("密码不能为空")
    if len(pwd.strip()) < 6:
        raise ValueError("密码至少 6 位")
    size = len(pwd.encode("utf-8"))
    if size > _BCRYPT_MAX_BYTES:
        raise ValueError(f"密码过长（UTF-8 编码后 {size} 字节，上限 {_BCRYPT_MAX_BYTES} 字节），请缩短后重试")
    return pwd


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

    def create_user(self, username: str, password: str, role: int = ROLE_USER,
                    *, _bootstrap: bool = False) -> dict:
        """创建用户。role=3 仅允许 ``bootstrap_admin`` 首次建站时经 ``_bootstrap`` 旁路创建；
        其余任何入口（超管建用户、注册）都不能产生第二个超管。"""
        username = validate_username(username)
        password = validate_password(password)
        role = int(role)
        if role not in ROLE_NAMES:
            raise ValueError("角色非法，必须是 0/1/2/3")
        if role == ROLE_SUPER and not _bootstrap:
            # 硬约束：超级管理员全局唯一，禁止再建第二个（超管只能由 promote_super 禅让产生）
            raise ValueError("超级管理员已存在且全局唯一，不能创建第二个超管；如需交接请由现任超管执行「禅让」")
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
            row = conn.execute("SELECT role FROM users WHERE id=?", (user_id,)).fetchone()
            if not row:
                raise ValueError("用户不存在")
            # 硬约束：谁都不能被直接改成超管（唯一超管只能由 promote_super 禅让产生）；
            # 唯一超管也不能被降级（否则系统会陷入「零超管、无人可批 L3」的死锁）
            if role == ROLE_SUPER:
                raise ValueError("不能把用户直接提升为超级管理员；超管唯一，只能由现任超管执行「禅让」")
            if row["role"] == ROLE_SUPER and role != ROLE_SUPER:
                raise ValueError("不能降级唯一超级管理员；如需交接请先执行「禅让」")
            cur = conn.execute("UPDATE users SET role=? WHERE id=?", (role, user_id))
            conn.commit()
            return cur.rowcount > 0

    def promote_super(self, old_super_id: str, successor_id: str) -> dict:
        """超管禅让：唯一超管把身份移交指定用户，事务内原子完成。

        旧超管降为管理员（role=2），继任者升为超管（role=3）。
        同一事务提交，任何时刻库里都恰好有一个超管，不存在双超管或零超管窗口。
        """
        with self._lock, self._connect() as conn:
            old_row = conn.execute("SELECT id, role FROM users WHERE id=?", (old_super_id,)).fetchone()
            if not old_row:
                raise ValueError("当前用户不存在")
            if old_row["role"] != ROLE_SUPER:
                raise ValueError("只有现任超级管理员才能执行禅让")
            new_row = conn.execute("SELECT id, role FROM users WHERE id=?", (successor_id,)).fetchone()
            if not new_row:
                raise ValueError("继任用户不存在")
            if successor_id == old_super_id:
                raise ValueError("不能禅让给自己")
            if new_row["role"] == ROLE_SUPER:
                raise ValueError("继任者已是超级管理员")
            conn.execute("UPDATE users SET role=? WHERE id=?", (ROLE_ADMIN, old_super_id))
            conn.execute("UPDATE users SET role=? WHERE id=?", (ROLE_SUPER, successor_id))
            # 禅让后旧超管的所有会话立即失效，防止其仍以超管身份残留操作
            conn.execute("DELETE FROM sessions WHERE user_id=?", (old_super_id,))
            conn.commit()
        return self.get_user(successor_id)  # type: ignore[return-value]

    def update_user_password(self, user_id: str, new_password: str) -> bool:
        new_password = validate_password(new_password)
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
        """users 表为空时，从环境变量创建首个超管（默认 admin/admin123）。

        唯一允许创建 role=3 的入口（``_bootstrap=True`` 旁路）：仅当库中尚无任何
        用户时执行；此后超管只能通过 ``promote_super`` 禅让产生。
        """
        if self.count_users() > 0:
            return None
        username = (os.getenv("ADMIN_USERNAME") or "admin").strip() or "admin"
        password = (os.getenv("ADMIN_PASSWORD") or "admin123").strip() or "admin123"
        user = self.create_user(username, password, role=ROLE_SUPER, _bootstrap=True)
        return user


# 模块级单例：导入即建表 + 首次启动建超管
store = AuthStore()
store.bootstrap_admin()
