# `infra/sql/` —— 三个业务库的建库脚本

> **本目录只提交这个 README 与说明，`.sql` 转储不入库。**

## 里面放什么（需要时手动放入）

| 文件 | 对应数据库 | 体量 | 说明 |
|---|---|---|---|
| `financial_asset_management.sql` | 金融资产管理库 | 约 380MB | 建库 + 建表 + 全量数据 |
| `healthcare_analytics_competition.sql` | 医疗分析库 | 约 107MB | 同上 |
| `telecom_operations_db.sql` | 通信运营商库 | 约 80MB | 同上 |

这三个库是「MySQL 业务库直查问答」的数据底座，缺了它们，`execute_sql` / `list_tables` / `schema` 三个工具会连得上库但没有表。

## 为什么不入库

**单个文件超过 GitHub 的 100MB 硬上限**，`380MB` 那份推上去会被服务端直接拒收，而且一旦进了历史就再也删不干净（仓库体积不可逆）。

另外，转储内容包含业务明细数据，本质上和「数据库」同级，属于不该公开的东西。

## 怎么获取

按优先级：

1. **GitHub Release 附件**（单文件上限 2GB）—— 推荐，与仓库同一入口
2. 内网网盘 / 公司共享盘
3. 找维护者要原始转储

**不要用 Git LFS**：当前账户 LFS 配额未知，超额会导致推送中断，且清理麻烦。

## 导库步骤（放入文件后）

```bash
# 1. 确认内置 MySQL 已启动（双击 启动.bat，或看 infra/scripts/setup_and_start.ps1）
# 2. 导入，注意端口与 root 口令取 backend/.env 的值
mysql -h 127.0.0.1 -P 3306 -u root -p < financial_asset_management.sql
mysql -h 127.0.0.1 -P 3306 -u root -p < healthcare_analytics_competition.sql
mysql -h 127.0.0.1 -P 3306 -u root -p < telecom_operations_db.sql

# 3. 验证
mysql -h 127.0.0.1 -P 3306 -u root -p -e "show databases;"
```

导完后 `backend/.env` 里的 `DB_NAME` / `DB_PORT` 要与实际一致（历史上出现过 3306 与 3307 不一致导致「服务起来了但工具全报连库失败」）。
