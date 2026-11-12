# `backend/data/` —— 运行时数据根目录

> **本目录只提交这个 README，其余内容一律不入库。**
> 原因：这里全是运行时产物与真实用户数据，公开到仓库等于泄露。

## 里面放什么（首启动/使用时自动生成）

| 名称 | 类型 | 内容 | 能否重建 |
|---|---|---|---|
| `conversations.json` | 文件 | 会话列表与消息历史（真实提问原文） | 否，删了会话就没了 |
| `checkpoints.sqlite3`（+ `-shm` / `-wal`） | 文件 | LangGraph Checkpointer，每轮对话的上下文快照 | 否，删了多轮记忆断掉 |
| `memory.sqlite3` | 文件 | 长期记忆（`remember` / `recall` 工具写入） | 否 |
| `tables.sqlite3` | 文件 | 已导入表格的索引与元数据（非结构化表格查询用） | 可，重新导入数据文件即可 |
| `vector.sqlite3` | 文件 | 知识库向量索引 | 可，重建知识库即恢复 |
| `table_memory.json` | 文件 | 表格字段的口语化别名缓存 | 可，重新学习即恢复 |
| `uploads/` | 目录 | 用户上传的原始文件，见 `uploads/README.md` | 否 |
| `非结构化数据/` | 目录 | 非结构化检索评测样本，见该目录 README | 否 |

## 绝对不能提交的东西

- 全部 `.sqlite3` 及其 `-wal` / `-shm`（含对话、记忆、向量，属隐私核心）
- `conversations.json`（真实提问常含公司名、业务数字、人名）
- `uploads/` 下的任何用户文件（可能是合同、报表、病历、客户名单）

以上已由仓库根 `.gitignore` 拦截，**不要用 `git add -f` 绕过**。规则说明见 [`docs/REPO-PUSH.md`](../../docs/REPO-PUSH.md) §3。

## 换机器 / 重新部署时

删空本目录（保留 README）即可，服务首启动会自动重建表结构。
如果要保留历史会话，把整个目录拷到新机器同一路径，不要只拷 `conversations.json`（与 checkpointer 不一致会错位）。
