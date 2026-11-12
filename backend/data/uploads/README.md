# `backend/data/uploads/` —— 用户上传的原始文件

> **本目录只提交这个 README，上传的文件一律不入库。**
> 这是整个项目隐私风险最高的目录：它装的是租户亲手放进去的真实业务文件。

## 里面放什么

用户在对话框里通过附件上传的原始文件，按上传时生成的 `file_id` 命名，典型形态：

- `.xlsx` / `.xls` / `.csv` —— 业务报表、明细表
- `.md` / `.txt` / `.pdf` —— 制度文档、说明书、合同
- 上传后由 `backend/services/datasource/` 解析，解析结果进入 `backend/data/tables.sqlite3` 与 `vector.sqlite3`

## 为什么不能提交

- 可能是**合同、报价单、客户名单、病历、工资表**，一旦公开仓库即为泄露事故。
- 文件名本身也含信息（公司名、人名、日期），即便内容是示例数据也不宜公开。
- 大文件会撑爆仓库体积。

`.gitignore` 已排除 `backend/data/uploads/*`，只保留本 README。

## 清理策略（建议由运维执行，不要写进代码）

| 场景 | 做法 |
|---|---|
| 演示环境交付前 | 清空本目录，保留 README |
| 租户退租 | 清空本目录 + 删除 `tables.sqlite3` / `vector.sqlite3` 中对应索引 |
| 定期清理 | 建议按 30 天保留，超出部分人工确认后删除 |

删除文件后，`tables.sqlite3` 里的表格索引会变成孤儿记录，需同时调用一次重建（见 `backend/services/datasource/`）。
