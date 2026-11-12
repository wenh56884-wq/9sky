# `backend/reports/` —— 报表与导出产物

> **本目录只提交这个 README，生成的报表不入库。**

## 里面放什么

Agent 生成的分析报告落盘位置，典型形态：

- `*.md` —— 结构化分析报告
- `*.csv` / `*.xlsx` —— 明细导出
- `*.png` / `*.svg` —— 图表快照

## 为什么不入库

- 报告正文就是**查询结果本身**，等于把业务库的数据抄了一份进 Git。
- 每跑一次就多一批，仓库会持续膨胀，且历史提交无法回收。

`.gitignore` 已排除本目录内容。目录本身在仓库里存在，是为了让服务首次启动时无需 `mkdir`、也让接手的人一眼看出报表落在哪。

## 相关

- 报表生成入口：`backend/services/analytics/`
- 只读 SQL 校验：`backend/core/agent.py` 的 `_validate_readonly`
