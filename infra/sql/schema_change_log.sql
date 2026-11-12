-- ============================================================
--  九天梧桐 AI 工作台 · 变更留痕表 DDL（§8.6）
--  纯结构、无数据。运行时数据存于 backend/data/change_log.sqlite3（不入库）。
-- ============================================================

CREATE TABLE IF NOT EXISTS change_log (
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
  before_json     TEXT,      -- 仅"主键 + 被改列"的前值，不存整行
  after_json      TEXT,
  status          TEXT,      -- applied | reverted | failed | rejected
  error_id        TEXT,
  idempotency_key TEXT UNIQUE,
  applied_at      TEXT,
  reverted_at     TEXT
);

-- 常用查询索引
CREATE INDEX IF NOT EXISTS idx_change_log_status ON change_log(status);
CREATE INDEX IF NOT EXISTS idx_change_log_table ON change_log(db_name, table_name);
CREATE INDEX IF NOT EXISTS idx_change_log_applied ON change_log(applied_at);
