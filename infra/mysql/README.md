# `infra/mysql/` —— 内置 MySQL 引擎

> **本目录只提交这个 README，MySQL 程序与数据文件一律不入库。**

## 里面放什么

发布包自带的 MySQL（约 1.1GB，含程序 + 数据目录）：

```
infra/mysql/bin/mysqld.exe
infra/mysql/my.ini            # 端口、datadir、字符集
infra/mysql/data/             # 三个业务库的实际数据文件 ← 企业数据，绝不入库
```

## 为什么不入库

| 内容 | 原因 |
|---|---|
| `bin/` 等程序文件 | 体积大、二进制不可 review |
| `data/` 数据库文件 | **就是企业数据本身**（金融 / 医疗 / 通信三库的物理文件），比 SQL 转储更敏感 |
| `my.ini` 里的口令 | 本地默认口令虽非个人隐私，但不应随公开仓库扩散 |

## 怎么获取

从内网网盘或 Release 附件取 `mysql.zip` 解压到本目录。
`my.ini` 的端口必须与 `backend/.env` 的 `DB_PORT` 一致（历史事故：一处 3306、一处 3307，导致服务起来了但工具全报连库失败）。

## 想换个版本怎么办

改 `infra/scripts/setup_and_start.ps1` 里的 `mysqld` 路径即可，本目录只是默认约定位置。
