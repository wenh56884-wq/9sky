# 仓库与推送约定（唯一权威页）

> 本页是仓库地址、分支、推送流程与隐私红线的**单点定义**。任何文档、脚本、AI 会话与本页冲突时，以本页为准。
> 最后更新：2026-11-12

---

## 1. 唯一远程仓库

| 项 | 值 |
|---|---|
| 仓库地址 | `https://github.com/wenh56884-wq/9sky` |
| 可见性 | public（公开仓库 → **任何入库内容都视为已公开**） |
| 默认分支 | `main`（访客打开链接看到的就是它） |
| 历史仓库 | `wenh56884-wq/bigdata` —— **已停用，不要再推**，仅作旧记录 |

因为仓库是公开的，本页第 3 节的红线不是“建议”，是**硬约束**：一旦推上去，等同于对外发布，删掉也会有缓存与 fork 残留。

---

## 2. 每次改动都推送（用户的常驻要求）

用户明确要求：**后续所有改动都要推送到上面这个仓库**。不是“里程碑才推”，是每次改完就推。

```bash
cd "C:/Users/22124/Desktop/发布包/九天梧桐AI工作台"

git add -A
git status --short                    # 必须人工看一眼：有没有 .env / data / *.sql 混进来
git commit -m "docs: 说明改动内容"     # 信息规范见 §4
git push origin main
```

首次在新机器上推送（仓库已存在、本地还没有远端时）：

```bash
git init -b main
git remote add origin https://github.com/wenh56884-wq/9sky.git
git add -A && git commit -m "chore: 初始导入"
git push -u origin main
```

---

## 3. 绝不入库的数据（隐私与体积红线）

### 3.1 隐私类 —— 推上去就是泄露

| 类别 | 具体路径 / 形态 | 为什么危险 |
|---|---|---|
| 密钥与口令 | `backend/.env`、`**/.env.bak_*`、任何 `sk-…`、Bearer Token、私钥 | 公开仓库 = 全网可读；GitHub 上有专门的爬虫在扫 `sk-` 前缀 |
| 数据库密码 | `backend/.env` 的 `DB_PASSWORD` | 与内网 MySQL 口令复用时会波及别的系统 |
| 用户对话记录 | `backend/data/conversations.json`、`checkpoints.sqlite3` | 真实提问常含公司名、人名、业务数字 |
| 用户上传文件 | `backend/data/uploads/` | 可能是合同、报表、病历、客户名单 |
| 自动沉淀问答 | `backend/knowledge/自动学习/`、`backend/knowledge/问答记录/` | 含真实提问原文与会话 ID |
| 运行日志 | `*.log`、`logs/` | 常把请求体、SQL、异常栈里的业务数据一起写进去 |
| 个人标识 | 手机号、身份证号、邮箱、真实姓名 + 工号、住址 | 即便是测试数据也统一用假值，见 §3.3 |
| 本机绝对路径 | `C:\Users\<真实用户名>\…`、`/Users/<name>/…` | 泄露账号名与目录结构 |

### 3.2 体积类 —— 推不上去，或把仓库撑爆

| 类别 | 具体路径 | 体量 / 原因 |
|---|---|---|
| 数据库转储 | `infra/sql/*.sql` | 单文件 **380MB / 107MB / 80MB**，超过 GitHub 单文件 100MB 硬上限，**推送必被拒** |
| 内置运行时 | `infra/runtime/` | 约 892MB |
| 内置 MySQL | `infra/mysql/` | 约 1.1GB（含 data 目录） |
| 前端依赖 | `frontend/node_modules/` | 约 41MB，可由 `npm ci` 重建 |
| 运行时数据 | `backend/data/`、`*.sqlite3`、`reports/` | 首启动自动重建 |
| 二进制文档 | `docs/*.pdf` | 可由 `backend/build_techdoc.py` 重建，不便审计 |
| 工作区记忆 | `.workbuddy/` | 私有，且含本机路径 |

> 需要这些大文件时：走 **GitHub Release 附件**（单文件上限 2GB）或内网网盘，仓库里只留一份 `README` 说明获取方式。
> **不要用 Git LFS** —— 当前账户配额未知，超额会导致推送中断且难以回退。

### 3.3 可以公开、但要知情的三类

这三类**当前已在仓库里**，判断为可公开，记录在此以免下次重复争论：

1. **本地内置 MySQL 的初始口令** `123456`（出现在 `backend/.env.example` 与 `infra/scripts/*.ps1`）。
   它不是个人口令，且服务只监听 `127.0.0.1`。若要彻底消除，需把脚本改为从 `backend/.env` 读取（约 3 行 + 需重测一键启动）。
2. **脱敏模块的测试夹具**：`13812345678` / `320102199001011234` / `王小明`（在 `backend/services/ops/sanitize.py` 与 `backend/eval/tests/`）。
   这是合成数据，用于验证脱敏规则。若租户合规要求“仓库内零示例”，替换为同长度伪值并同步改断言即可。
3. **知识库示例文档** `backend/knowledge/*.md`：数据库 schema 与 NL→SQL 题库，含字段名（`national_id`、`patient_name`）与题目里的示例人名，**不含任何真实记录值**。

### 3.4 已经落地在哪里

红线由仓库根 `.gitignore` 执行，已覆盖上述全部路径。**禁止用 `git add -f` 绕过**；确需例外时，先在本页第 3 节登记理由。

---

## 4. 提交信息规范

格式：`type(scope): 说明`

- `type` ∈ `feat | fix | style | docs | chore | refactor | perf`
- `scope` ∈ `ui | chat | sidebar | composer | backend | docs | repo`
- 一次提交只做一件事；不写“update”“修改”这类无信息量的词。

示例：
```
feat(ui): 侧栏按日期分组并支持折叠
fix(chat): 中文输入法回车不再误发送
docs: 新增仓库与推送约定
```

---

## 5. 推送前自检（四条，30 秒）

```bash
# ① 有没有隐私文件混进暂存区（应无输出）
git diff --cached --name-only | grep -E "\.env$|/data/|\.sqlite3|自动学习|\.sql$|node_modules|\.pdf$"

# ② 有没有密钥形态（应无输出）
git grep --cached -n -E "sk-[A-Za-z0-9_-]{16,}|BEGIN (RSA|OPENSSH) PRIVATE KEY"

# ③ 有没有个人标识（应无输出，测试夹具除外，见 §3.3）
git grep --cached -n -E "\b1[3-9][0-9]{9}\b|\b[0-9]{17}[0-9Xx]\b"

# ④ 体量与文件数是否正常（参考基线：约 120 个文件 / 约 2MB）
git ls-files | wc -l
git ls-files -z | du -ch --files0-from=- | tail -1
```

四条全过再 `git push`。若 ①②③ 有输出，**停下**，先 `git rm --cached <文件>` 并从 `.gitignore` 补规则，再重新提交。

---

## 6. 事故处理

### 6.1 密钥已经推上去了

推上去的那一刻就当作已泄露。顺序不能颠倒：

1. **先去控制台轮换/吊销密钥**（OpenAI、DeepSeek 等），再处理仓库。
2. 删掉仓库里的文件并提交（`git rm --cached backend/.env`），补 `.gitignore`。
3. 如果历史里还有，用 `git filter-repo --path backend/.env --invert-paths` 重写历史后强推。
4. 通知已知的使用方（如有）。

> 只做第 2 步是不够的：旧 commit 仍可被 `git log -p` 翻出来。

### 6.2 大文件导致推送失败

GitHub 拒收后，本地 commit 已生成但推不上去。处理：

```bash
git rm --cached infra/sql/xxx.sql          # 从索引移除，保留工作区文件
echo "infra/sql/*.sql" >> .gitignore
git commit --amend                          # 或新开一次提交
```

若已经进了历史（多次提交），同样用 `git filter-repo` 清理，否则仓库体积不可逆。

### 6.3 推错了分支

- 不要 `git push --force` 到 `main`，除非确认没有他人协作。
- 先 `git revert` 生成反向提交，保住可追溯性。

---

## 7. 当前基线快照（2026-11-12）

| 指标 | 值 |
|---|---|
| 跟踪文件数 | 约 120 |
| 仓库体积 | 约 2.0MB |
| 目录结构 | `backend/` `frontend/` `infra/` `docs/` |
| 已排除 | 见 §3.1 / §3.2 |

**基线明显偏离（如突然变成 300 个文件 / 50MB）时，先查是不是 `.gitignore` 失效或误加 `-f`，不要直接推。**

---

## 8. 给后续 AI 的执行摘要

1. 仓库只有一个：`https://github.com/wenh56884-wq/9sky`，分支 `main`。
2. 每次改完就推，不攒。
3. 推之前跑 §5 的四条自检，有输出就停。
4. 任何 `.env` / 数据文件 / SQL 转储 / 上传文件 / 自动学习记录，**一律不入库**，不要用 `-f` 绕。
5. 需要改这份规则时，改的是本页，不是散落在别处的副本。
