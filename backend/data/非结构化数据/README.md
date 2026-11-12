# `backend/data/非结构化数据/` —— 表格 / 多步检索评测样本

> **本目录只提交这个 README，样本数据不入库。**

## 里面放什么

用于离线评测 NL→Table 与多步检索能力的题目与参考答案，成对出现：

| 文件 | 内容 |
|---|---|
| `Multi-step_Retrieval-数据.md` | 多步检索任务的题目描述与数据说明 |
| `Multi-step_Retrieval_task.json` | 对应的结构化任务定义与标准答案 |
| `Table_Domain-specific_Operations-数据.md` | 领域特定表格操作（增删改查、字段运算）样本 |
| `Table_Domain-specific_Operations_task.json` | 对应答案 |
| `Table_Query-数据.md` | 表格自然语言查询样本 |
| `Table_Query_task.json` | 对应答案 |
| `样例答案.json` | 输出格式的样例参考 |

这些文件被 `backend/eval/` 下的评测脚本读取，用来算准确率。

## 为什么不入库

- 样本中可能含**真实业务表格的行数据**（哪怕脱敏过，字段组合也可能反推到个人）。
- 评测集属于**内部基准**，公开后会让指标失去意义。
- 体量偏大且会持续增长。

`.gitignore` 已排除 `backend/data/非结构化数据/*`，只保留本 README。

## 新机器上要不要紧

不影响服务启动，只影响「跑离线评测」这一个场景。需要评测时从内网网盘或 Release 附件取回放到本目录即可。
