# 九天梧桐 AI 工作台 · 交付任务书（给 Claude 执行）

> **这份文件是唯一任务书，既是设计文档也是执行提示词。** 拿到后不需要再问背景，按 §16 的顺序施工，按 §18 自检，按 §20 汇报。
>
> **事实基线**：仓库 `https://github.com/wenh56884-wq/9sky`，分支 `main`，commit `c315e1e`，135 个跟踪文件。
> 文中行号以该 commit 为准；改过代码后行号会漂移，**请按符号名搜索，不要迷信行号**。
>
> **版本 v2（2026-11-12）**：相对 v1 新增「写数据能力」（§8），并修正"鉴权未实现"的过期结论。

---

## 目录

| 节 | 内容 | 紧急度 |
|---|---|---|
| §0–2 | 产品定位 / 你的角色 / 项目事实 | 必读 |
| §3 | 五条铁律（违反即失败） | 必读 |
| §4 | 现状诊断（P0 阻断 / 9 个 bug / 工程化缺失） | 必读 |
| §5 | 施工总览与依赖关系 | 必读 |
| §6–7 | 阶段 0 基线 / 阶段 1 交付链 | P0 |
| **§8** | **阶段 2 写数据能力（企业客户核心诉求）** | **P0** |
| §9–10 | 阶段 3 设计系统 / 阶段 4 前端缺陷 | P1 |
| §11–13 | 阶段 5 功能 / 阶段 6 企业级 / 阶段 7 工程化 | P1–P2 |
| §14–15 | 视觉判据 / 可访问性与性能 | P1 |
| §16–21 | 门禁 / 验收 / 自检 / 禁止 / 汇报 / 易翻车点 | 全程 |

---

## 0. 一句话说明这个产品

一个**本地运行的、面向企业租户的 AI 数据工作台**：用户登录后用自然语言问业务数据，Agent 通过 ReAct 循环调用工具（只读 SQL、Python 沙箱、RAG 知识库、表格查询）回答问题；**本期要新增：经超级管理员审批的数据增删改**。

**它不是玩具**：鉴权、用户管理、审批中心、只读 SQL 校验、沙箱、数据溯源都已落地。
**它还不是能卖的产品**：一键启动是断的、界面是两套样式叠加的、错误处理靠 `alert()`、没有测试、**没有任何写数据能力**。

---

## 1. 你的角色与成功标准

你是**同时具备三种能力的人**：前端工程师（视觉到商业水准且不破坏功能）、Python 后端工程师（修交付链路、建写能力、补工程化）、交付负责人（每个阶段结束项目都必须是可运行、可回滚、可交付的状态）。

**成功标准（四条，缺一条算失败）**

1. 双击 `启动.bat`，从零到能用，全程无人工干预、无红色报错
2. 界面在 1440×900 与 1920×1080 下都像商业产品
3. **普通用户发起的写操作，没经过超管批准就一定不会落库**
4. 每个阶段结束都推送到 `9sky`，且没有泄露任何企业数据

---

## 2. 项目事实（先读，不要猜）

### 2.1 技术栈

| 层 | 技术 | 说明 |
|---|---|---|
| 后端 | Flask 2.x + Python 3.13 | `backend/web.py`（599 行）暴露全部 API |
| Agent | LangChain 1.x ReAct + LangGraph Checkpointer | `backend/core/agent.py`（4664 行，26 个工具） |
| 前端 | Vue 3 `<script setup>` + Pinia + Vite | `frontend/src/`，无 Vue Router，用自研 `useNav` 切视图 |
| 数据库 | MySQL 8（内置绿色版） | 三库：`financial_asset_management` / `healthcare_analytics_competition` / `telecom_operations_db` |
| 本地存储 | SQLite + JSON | 会话、记忆、向量索引、表格索引、审批单 |
| 样式 | 单文件 `frontend/src/styles/main.css`（1231 行） | **无 UI 框架**，纯手写 CSS 变量 |

### 2.2 目录职责

```
backend/          Flask 服务 + Agent 引擎（代码，全入库）
  core/           agent.py 引擎、cognition/ 规划
  services/       ops/（鉴权·审批·脱敏·可观测）datasource/ knowledge/ analytics/
  eval/           离线评测脚本 + 题库（入库；运行结果不入库）
  skills/         技能卡（tables/general/database）
  knowledge/      示例知识库（入库）；uploads/、自动学习/ 不入库
  data/           运行时数据（只入库 README）
frontend/src/     Vue 源码（全入库）
frontend/dist/    Vite 产物（不入库，后端托管它）
infra/            mysql/ runtime/ sql/ scripts/（只入库 scripts 与各目录 README）
docs/            设计文档（全入库）
```

### 2.3 启动链路（当前是断的，见 P0-1）

```
启动.bat  →  infra\scripts\setup_and_start.ps1  →  MySQL → 后端 web.py → 浏览器
停止.bat  →  infra\scripts\stop_all.ps1
```

后端默认 `127.0.0.1:5000`；MySQL 端口 **3306**；MySQL 运行目录固定 `C:\ProgramData\JiuTianWuTong`（纯英文路径，规避中文用户名问题）。

### 2.4 鉴权与角色（**已实现，不要重写**）

- Bearer Token：`Authorization: Bearer <token>`，服务端存会话，支持登出/踢人
- 角色：`0` 访客 / `1` 普通用户 / `2` 管理员 / `3` 超级管理员（`ROLE_NAMES` 在 `services/ops/auth_store.py:30`）
- 已落地路由：`/api/auth/{login,logout,me,change-password,users}` + `/api/approvals` + 上传全套
- `web.py` 全部业务路由**都已加** `@require_auth` / `@require_role(n)`
- 前端：`stores/auth.js`、`api/auth.js`（自动注入 Bearer、401 回登录页）、`views/LoginView.vue`、`views/UserManage.vue`、`components/ApprovalCenter.vue`

> `docs/OPTIMIZATION.md` 与 `docs/FRONTEND-REBUILD-SPEC.md` 里"鉴权未实现"的段落已过期，看到一律以代码为准，并顺手加"实测修正"批注。

### 2.5 Agent 能力现状（**本期的起点**）

26 个工具，**全部只读**：

| 类别 | 工具 |
|---|---|
| 数据库读 | `execute_sql`、`list_database_tables`、`get_table_schema`、`get_db_skill`、`analyze_query` |
| 分析 | `plot_last_result`、`run_python`、`analyze_data`、`detect_data_anomalies`、`cluster_data`、`forecast_metric` |
| 表格 | `list_table_sets`、`find_table`、`describe_table`、`query_tables`、`query_table_python` |
| 知识库 | `search_knowledge` |
| 记忆 | `remember`、`recall`、`forget` |
| 规划 | `plan_task`、`update_plan` |
| 基础 | `calculator`、`get_current_time`、`word_count` |

**写能力的真实起点是零**，不是"改造"。`_validate_readonly`（`agent.py:287`）用关键字黑名单拒绝一切非 SELECT；`hitl.PROTECTED_TOOLS` 只保护 3 个工具（`forget` 高、`forecast_metric` 低、`plot_last_result` 低），**数据写完全不在审批范围内**；`DB_USER=root`。

### 2.6 流式协议（改前端时必须遵守）

`POST /api/chat` 返回 **NDJSON**（每行一个 JSON 对象），事件类型见 `web.py` 中 `/api/chat` 的注释，前端解析在 `composables/useChat.js`。
**不要改事件名、不要改成 SSE、不要改字段名**。新增写能力相关事件时只能**追加**新类型。

---

## 3. 五条铁律（违反任意一条，本次交付判定失败）

### 铁律一：仓库只有一个，每次改完就推

```bash
cd "C:/Users/22124/Desktop/发布包/九天梧桐AI工作台"
git add -A && git status --short      # 必须人工看一眼
git commit -m "type(scope): 说明"
git push origin main
```

- 远程 `https://github.com/wenh56884-wq/9sky`，分支 `main`，**公开仓库**
- `type` ∈ `feat|fix|style|docs|chore|refactor|perf`；一次提交只做一件事；不写"update""修改"
- **不攒提交**，完成一个可验证的小步就推一次

### 铁律二：企业数据不进，代码全进，目录要留

用户原话：**「企业数据不要放，代码放；但文件目录要进，才知道这里放什么东西。」**

| 必须入库 | 必须排除 |
|---|---|
| 所有 `.py .vue .js .css .html .ps1 .bat .md` | `.env` 及任何密钥、私钥、Token |
| 各数据目录的 `README.md`（说明用途） | `*.sqlite3`、`conversations.json`、`table_memory.json` |
| 题库与示例知识库（只有题目和 SQL，无结果数据） | `backend/data/uploads/` 用户上传文件 |
| 启动脚本、SQL 的**说明** | `backend/knowledge/自动学习/` 真实问答记录 |
| | `infra/sql/*.sql`（380/107/80MB，超 GitHub 单文件上限） |
| | `infra/runtime/`、`infra/mysql/`（约 2GB） |
| | `frontend/node_modules/`、`frontend/dist/`、`backend/reports/` 产物 |

**Git 的坑（已经踩过一次）**：父目录被整条排除后，里面的文件用 `!` 也无法重新纳入。必须写成：

```gitignore
backend/data/*
!backend/data/README.md
!backend/data/uploads/            # 先放行子目录
!backend/data/uploads/README.md   # 再放行子目录里的说明
```

不确定时用 `git check-ignore -v <路径>` 定位。**禁止 `git add -f` 绕过**。

> ⚠️ 本期新增注意：`data/change_log.sqlite3`、`data/audit.sqlite3` 属运行时数据，已在 `*.sqlite3` 规则内，**不要为它们加例外**。但 `change_log` 的**表结构 DDL** 要写进 `infra/sql/schema_change_log.sql`（纯结构、无数据）并入库。

### 铁律三：不破坏既有契约

1. **CSS 变量与类名**：`--accent`、`--panel`、`ds-item`、`up-panel`、`msg-actions` 等被 8 个不改造的子组件深度引用。**只重设值，不改名**。
2. **localStorage 键**：改了等于清空用户已有偏好。
3. **接口路径与字段**：前端 `api/index.js` 与 `web.py` 一一对应。
4. **NDJSON 事件名**：只能追加，不能修改。

### 铁律四：不加依赖、不换框架

- **禁止**换 UI 框架（Element/Arco/AntD/Tailwind）——会生成第三套设计系统
- **禁止**引入 Vue Router、虚拟滚动库、i18n、PWA、状态机库
- **禁止**在本次拆 `agent.py`（4664 行，风险与收益不匹配）
- **允许新增**：前端 `dompurify`（XSS 修复必需）；后端 `pytest`、`ruff`（工程化）

### 铁律五：每次改完必须能构建

```bash
cd frontend && npm run build            # 不通过不许提交
cd backend && python -c "import web"    # 无异常
```

---

## 4. 现状诊断（已验证，带证据）

### 4.1 已经做好、**不要重做**

| 能力 | 位置 | 评价 |
|---|---|---|
| 只读 SQL 校验 | `agent.py:287 _validate_readonly` | 思路对（单语句 + 前缀白名单），但对写操作不可复用 |
| Python 沙箱 | `services/analytics/pysandbox.py` | 受限执行，够用 |
| 人工审批 HITL | `services/ops/hitl.py`（343 行）+ `/api/approvals` | 已落盘、双级、有超时，**可扩展为写审批** |
| 数据溯源 | 每轮记 sources，前端 `SourceDrawer` | 卖点，别动 |
| RAG 知识库 | `services/knowledge/` | 可用 |
| 鉴权与用户管理 | `services/ops/auth.py` + 前端三件套 | 已落地 |
| 脱敏 | `services/ops/sanitize.py` | 已有手机号/身份证/邮箱规则 |

### 4.2 P0 · 交付阻断

| 编号 | 问题 | 证据 | 后果 |
|---|---|---|---|
| **P0-0** | **Agent 无任何写数据能力** | 26 工具全只读；`PROTECTED_TOOLS` 只有 forget/forecast/plot | 企业客户第一需求（改数据）无法满足 |
| **P0-1** | 一键启动必失败 | `infra/scripts/setup_and_start.ps1:11` `$Root = Split-Path -Parent $PSScriptRoot` → 实际等于 `infra/`；第 12 行 `Join-Path $Root "infra\runtime\python\python.exe"` → `infra\infra\runtime\...`，第 51 行预检 `Fatal "缺少 runtime\python"` | 客户第一眼"这软件坏了" |
| **P0-2** | 数据库用 root | `backend/.env.example:294 DB_USER=root` | 一旦开写 = 全库最高权限，无兜底 |
| **P0-3** | 预检文案是旧版路径 | 同文件 52 行 `app\web.py`、54 行 `data_sql\$f` | 排障被误导 |
| **P0-4** | 会话无归属 | `conversations.json` 无 `owner_id` | 多人共用一台机器串数据，过不了"数据隔离"条款 |

### 4.3 P1 · 前端真实缺陷（不是审美，是 bug）

| 编号 | 问题 | 位置 | 影响 |
|---|---|---|---|
| **B1** | 复制按钮用全局 `document.querySelector('.msg-actions .mini-btn.copied')`，且 `textContent` 会抹掉 SVG | `MessageItem.vue:24` | 多条消息时改第一条；图标永久消失 |
| **B2** | 时间戳挂载时 `new Date()` | `MessageItem.vue:14,17` | 刷新后所有历史消息同一时刻 |
| **F10** | 回车发送未判输入法 | `Composer.vue:32` | 中文用户选词就误发送 |
| **F12** | `marked` 输出裸 `v-html` | `MarkdownView.vue:43,80` | XSS |
| **F13** | 外链无 `target="_blank"` | `MarkdownView.vue` renderer | 点外链 SPA 跳走、状态全丢 |
| **F18** | 生成中切会话，流仍写已卸载对象 | `chat.js` `sendQuestion` | `sending` 卡 true，输入框永久禁用 |
| **B3** | 侧栏 `.side` 与 `.conv-list` 双滚动容器 | `main.css` | 滚轮跳动 |
| **B4** | 删当前会话后 `currentId` 残留 | `conversations.js` | 右侧空白但可输入 |
| **U1** | 10 处原生 `alert/confirm` | `ChatHeader.vue:44`、`Sidebar.vue:47,54,67,69,75,77,89` 等 | 无法样式化、阻塞线程 |

### 4.4 P2 · 设计系统污染

`main.css` 1231 行里 **两套设计系统叠加**：`--accent` 在 8 / 45 / 479 / 513 行被定义 4 次，后一套（注释"豆包风格 · Arco 色板"）覆盖前一套，前 470 行基本是死代码。改主题色会出现"一半蓝一半紫"。

### 4.5 P3 · 工程化缺失

| 项 | 现状 |
|---|---|
| 测试 | `eval/tests/` 下 5 个文件叫 `_test_*.py`，pytest 默认只认 `test_*.py` → **一个都收不到** |
| 日志 | `core` + `services` 有 **152 处 `print()`**，全项目只有 `debugging.py` 一处 `logging` |
| 异常 | **95 处 `except Exception:`**，多处 `pass` 静默吞掉 |
| 依赖 | `requirements.txt` 全是 `>=`，不可复现 |
| 静态检查 | 无 ruff / eslint / CI |
| 生产服务器 | `app.run()` 开发服务器跑在"发布包"里 |

---

## 5. 施工总览

```
阶段0 基线
  └→ 阶段1 交付链 ──────────────【门禁1】双击能启动
        └→ 阶段2 写数据能力 ─────【门禁2】未审批的写一定落不了库
              ├→ 阶段3 设计系统 ─┐
              │     └→ 阶段4 缺陷┴→【门禁3】构建通过 + 9 个 bug 清零
              │           └→ 阶段5 功能 ─→ 阶段6 企业级 ─【门禁4】验收清单全过
              └→ 阶段7 工程化（可与 5/6 并行）────────────────→ 推送
```

**依赖说明**：阶段 2 必须在阶段 3 之前，因为写能力 UI（变更卡、审批中心）要用新 token；阶段 3 之前必须先有阶段 1 的可运行环境，否则改了看不到效果。

---

## 6. 阶段 0 · 建基线（15 分钟，不能跳）

```bash
cd "C:/Users/22124/Desktop/发布包/九天梧桐AI工作台"
git pull origin main
git status --short              # 有未提交改动先 commit
git tag pre-delivery-$(date +%Y%m%d)
```

**为什么不能跳**：`main.css` 是唯一视觉入口，没有回滚点，重构失败就全盘皆输。

---

## 7. 阶段 1 · 修交付链（P0，半天）

### 7.1 修 `$Root`

**文件** `infra/scripts/setup_and_start.ps1:11`

```powershell
# 改前
$Root = Split-Path -Parent $PSScriptRoot          # → 得到 infra\
# 改后
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path   # → 项目根
```

改完验证**四个**派生路径同时正确：

| 变量 | 期望 | 验证 |
|---|---|---|
| `$PyExe` | `<根>\infra\runtime\python\python.exe` | `Test-Path $PyExe` |
| `$AppDir` | `<根>\backend` | `Test-Path (Join-Path $AppDir "web.py")` |
| `$SqlDir` | `<根>\infra\sql` | 目录存在 |
| 第 67/71 行 `robocopy` 源 | `<根>\infra\mysql` | 目录存在 |

### 7.2 修预检文案

52 行 `"缺少 app\web.py"` → `"缺少 backend\web.py"`；54 行 `"缺少数据文件 data_sql\$f"` → `"缺少数据文件 infra\sql\$f"`。

### 7.3 变量改名，消除歧义

- `setup_and_start.ps1`：`$Root` → `$ProjectRoot`（7 处）
- `stop_all.ps1`：`$Root` → `$InfraRoot`（2 处），注释写明"只用于匹配进程路径，不是项目根"

**门禁 1**：双击 `启动.bat` → `[1/5] 发布包完整性检查通过` → 浏览器打开能登录；双击 `停止.bat` → `mysqld` 与 `python` 进程都消失。

---

## 8. 阶段 2 · 写数据能力（★ 本期核心，3–4 天）

> **本节是全文档最重要的部分。** 目标：让 Agent 能对业务库做增删改，且**没有超管批准就绝不可能落库**。

### 8.1 先纠正一个产品语义

用户的表述是"智能体可以找超级管理员对数据进行增删改"。实现上**必须**理解为：

> Agent 发现本次变更超出自己的权限 → 自动生成变更草案 → 系统按风险等级路由给对应角色 → **由超管本人点击批准** → 才执行。

**绝对禁止**的三种做法：

| 禁止 | 为什么 |
|---|---|
| Agent 声称"已获超管授权"就执行 | 等于没有权限系统 |
| Agent 能读取/传入 `user_role` 参数 | 角色只能从 token 反查，不能来自请求体 |
| 超管不在线时"自动通过" | 宁可挂起/超时拒绝，不可放行 |

### 8.2 三个 MySQL 专用账号（**先做这个，否则后面的防护都是纸糊的**）

现有 `_validate_readonly` 是**字符串黑名单**，对写操作不可复用（挡不住 `SELECT ... INTO OUTFILE`、存储过程、编码绕过）。真正的兜底在数据库引擎层：

```sql
-- 只读账号：Agent 默认用这个
CREATE USER 'jt_read'@'localhost' IDENTIFIED BY '<随机强口令>';
GRANT SELECT ON financial_asset_management.* TO 'jt_read'@'localhost';
GRANT SELECT ON healthcare_analytics_competition.* TO 'jt_read'@'localhost';
GRANT SELECT ON telecom_operations_db.* TO 'jt_read'@'localhost';

-- 写账号：只对白名单表，且没有 DDL、没有 DROP
CREATE USER 'jt_write'@'localhost' IDENTIFIED BY '<随机强口令>';
GRANT SELECT, INSERT, UPDATE, DELETE ON financial_asset_management.<白名单表> TO 'jt_write'@'localhost';
-- 逐表授权；不给 *.*，不给 CREATE/ALTER/DROP/GRANT/FILE

-- 管理账号：仅超管提权会话使用
CREATE USER 'jt_admin'@'localhost' IDENTIFIED BY '<随机强口令>';
GRANT ALL ON financial_asset_management.* TO 'jt_admin'@'localhost';
```

配套改造：

- `backend/.env.example` 增加 `DB_USER_READ` / `DB_USER_WRITE` / `DB_USER_ADMIN`
- `db_connect()` 增加 `mode` 参数：`read`（默认，保持现有行为）/ `write` / `admin`
- `setup_and_start.ps1` 首次建库时执行上面的 GRANT，口令随机生成并写入 `backend/.env`
- **`DB_USER=root` 只保留给运维手工排障，服务进程不得使用**

### 8.3 风控闸门 `write_gate`

**新文件** `backend/services/ops/write_gate.py`

```python
RISK_L1, RISK_L2, RISK_L3 = "L1", "L2", "L3"

POLICY = {
    # 默认为空 → 全部拒绝。必须由租户/超管在配置里显式开启可写表。
    "table_whitelist": {},          # {"库名.表名": {"columns": [...allow...]}}
    "column_blacklist": [           # 敏感列，任何情况下禁止写
        "national_id", "patient_name", "phone", "mobile",
        "bank_card", "id_card", "password", "salary",
    ],
    "max_rows": {"L1": 50, "L2": 1000, "L3": 5000},
    "forbid_without_where": ["UPDATE", "DELETE"],
    "forbid_statements": ["DROP", "TRUNCATE", "ALTER", "GRANT", "CREATE USER", "LOAD DATA"],
}
```

**判定顺序（短路，命中即停）**

| 序 | 检查 | 不通过的处理 |
|---|---|---|
| 1 | 单语句（无分号分隔） | 拒绝 |
| 2 | 首关键字 ∈ {INSERT, UPDATE, DELETE} | 拒绝（DDL 一律拒绝） |
| 3 | 命中 `forbid_statements` / 注释符 / `INTO OUTFILE` | 拒绝 |
| 4 | 目标表 ∈ `table_whitelist` | 拒绝：`表 x 未开启写入` |
| 5 | `UPDATE`/`DELETE` 必须带 `WHERE` | 拒绝（**不是升级，是拒绝**） |
| 6 | `SET`/`INSERT` 的列 ∉ `column_blacklist` | 拒绝：`敏感列 x 禁止写入` |
| 7 | 影响行数 ≤ 对应级别上限 | 超限升级到下一级 |
| 8 | 不跨库 | 拒绝 |

返回结构：

```python
{"ok": False, "reject_reason": "UPDATE 未带 WHERE 条件，已拒绝", "hits": ["forbid_without_where"]}
{"ok": True, "risk": "L2", "required_role": 2, "estimated_rows": 37}
```

### 8.4 新工具 `propose_write`（**只出草案，绝不执行**）

**新文件** `backend/core/tools/write_tools.py`，注册进 `TOOLS`（`agent.py:2278`）

```python
@tool
def propose_write(database: str, table: str, operation: str, sql: str, reason: str = "") -> str:
    """提交一条数据变更草案（不会立即执行）。

    仅当用户明确要求修改/新增/删除业务数据时调用。
    operation 只能是 INSERT / UPDATE / DELETE。
    UPDATE/DELETE 必须提供精确 WHERE，并说明变更原因 reason。
    返回草案 ID、影响行数预估、变更前后预览；真正执行需要相应角色批准。
    """
```

返回给前端的 JSON（同时作为审批单 payload）：

```json
{
  "proposal_id": "wp_20261112_a1b2c3",
  "database": "telecom_operations_db",
  "table": "customers",
  "operation": "UPDATE",
  "sql": "UPDATE customers SET status='停用' WHERE customer_id IN ('C001','C002')",
  "sql_hash": "sha256:9f2a…",
  "where_clause": "customer_id IN ('C001','C002')",
  "reason": "客户要求注销",
  "estimated_rows": 2,
  "risk": "L1",
  "required_role": 1,
  "preview": {
    "columns": ["customer_id", "customer_name", "status"],
    "before": [["C001", "张三（已脱敏）", "在网"], ["C002", "李四（已脱敏）", "在网"]],
    "after":  [["C001", "张三（已脱敏）", "停用"], ["C002", "李四（已脱敏）", "停用"]],
    "sample_limit": 20
  },
  "expires_at": "2026-11-12T19:30:00"
}
```

**硬要求**

- `estimated_rows` 必须用 `SELECT COUNT(*)` 真算，不能估
- `preview` 必须先过 `sanitize` 打码（展示用），**执行时用原值**
- 草案生成后**不改库**，只写一条 `pending` 审批单
- 同一 `sql_hash` 10 分钟内重复提交，返回原草案（防 Agent 反复重试）

### 8.5 审批路由（"智能体找超管"的正确实现）

复用现有 `hitl`（`services/ops/hitl.py`），**扩展而不是重写**。

**表结构扩展**（`approvals.sqlite3`）

```sql
ALTER TABLE approvals ADD COLUMN kind TEXT DEFAULT 'tool';        -- tool | write
ALTER TABLE approvals ADD COLUMN payload_json TEXT;               -- 草案全文（含 sql_hash）
ALTER TABLE approvals ADD COLUMN required_role INTEGER DEFAULT 1; -- 1/2/3
ALTER TABLE approvals ADD COLUMN expires_at TEXT;
ALTER TABLE approvals ADD COLUMN idempotency_key TEXT;
```

**级别 → 角色映射**

| 风险 | 影响行数 | 批准人 | 超时时长 |
|---|---|---|---|
| L1 | ≤50，单表且有 WHERE | 操作者本人（角色 ≥1） | 10 分钟 |
| L2 | ≤1000 | 管理员（角色 ≥2） | 30 分钟 |
| L3 | ≤5000 / 跨表 / 含金额列 | **超级管理员（角色 3）** | 2 小时 |
| 超限 | >5000 | 不受理，提示拆批 | — |

**路由与通知**

1. `GET /api/approvals` 按当前角色过滤：`required_role <= 我的角色`
2. 超管登录后顶栏显示待审批红点（轮询 10s 或复用现有健康检查节拍）
3. 审批单挂起时显示倒计时；**超时自动 `rejected`**，原因写回对话流
4. 超管离线超过 `expires_at` → 自动拒绝，Agent 回复"变更未获批准，已取消"

**新增接口**

| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| `GET` | `/api/writes/pending` | role ≥1 | 我能批的写草案（按角色过滤） |
| `POST` | `/api/writes/<proposal_id>/decide` | role ≥ required_role | `{decision: approve/reject, message}` |
| `GET` | `/api/writes/history` | role ≥2 | 变更历史（分页） |
| `POST` | `/api/writes/<change_id>/revert` | role ≥2 | 撤销（L2 起需二次审批） |

### 8.6 变更留痕 `change_log`

**DDL 入库**：`infra/sql/schema_change_log.sql`（纯结构、无数据）

```sql
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
```

**为什么 `before_json` 不存整行**：整行会把敏感数据抄进本地库第二份，违背最小化原则。只存主键与被改列的前值，撤销时足够还原。

### 8.7 执行器与撤销

**新文件** `backend/services/ops/write_executor.py`

```
① 校验 sql_hash == 审批单里的 sql_hash（防审批后被篡改）
② 幂等检查：idempotency_key 24h 内已执行 → 直接返回上次结果
③ 用 jt_write 连接，开启事务
④ SELECT ... FOR UPDATE 锁定目标行（行数少时开）
⑤ 记录 before（主键 + 被改列前值）
⑥ 执行，取 affected_rows
⑦ 比对：|affected - estimated| / max(estimated,1) > 20% → ROLLBACK，记 failed
⑧ COMMIT → 写 change_log（status=applied）
⑨ 任何异常 → ROLLBACK，写 change_log（status=failed）+ error_id
```

**撤销**：用 `before_json` 生成反向 UPDATE，**同样走审批**（L2 起），执行后 `status=reverted`，并新增一条 `revert` 记录（不复用原行）。

### 8.8 前端变更卡

**新组件** `frontend/src/components/WriteProposalCard.vue`

| 区域 | 内容 |
|---|---|
| 头部 | 库.表名 · 操作标签（新增/修改/删除，颜色区分）· 风险徽章（L1 灰 / L2 橙 / L3 红） |
| 主体 | 影响行数（大字）· 变更原因 · 可折叠 SQL（等宽字体） |
| 差异表 | Before / After 双列，**被改单元格高亮**；超过 20 行显示"仅显示前 20 行" |
| 底部 | 驳回 · 修改后重提 · **批准执行**（按角色禁用并显示"需超管批准"） |
| 状态 | pending（倒计时）/ approved / rejected / applied / failed / reverted |

**审批中心增强** `ApprovalCenter.vue`：加 tab（工具审批 / 数据变更 / 变更历史）；列表项显示 `谁 · 何时 · 想改什么`；快捷键 `J/K` 上下、`A` 批准、`R` 驳回。

**对话流内表现**：`propose_write` 被调用后，聊天区插入变更卡并**暂停流式**，等审批结果；批准后继续输出执行结果，驳回则输出"已取消，未改动任何数据"。

### 8.9 权限矩阵（直接定死，不要再讨论）

| 角色 | 读 | L1 写 | L2 写 | L3 写 | DDL | 审批他人 | 撤销 |
|---|---|---|---|---|---|---|---|
| 0 访客 | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| 1 普通用户 | ✓ | 自己确认 | 需管理员 | 需超管 | ✗ | ✗ | ✗ |
| 2 管理员 | ✓ | ✓ | 自审 | 需超管 | ✗ | L1/L2 | ✓（需 L2 审批） |
| 3 超级管理员 | ✓ | ✓ | ✓ | ✓ | ✓（提权会话） | 全部 | ✓ |

### 8.10 状态机

```
草案 pending ──approve──→ approved ──执行成功──→ applied ──revert──→ reverted
   │                         │
   │                         └──执行失败──→ failed（可重试一次，需重新审批）
   ├──reject──→ rejected
   └──超时───→ expired（等同 rejected）
```

规则：`rejected` / `expired` 不允许再 approve；`applied` 24 小时内可 revert。

### 8.11 验收用例（**必须逐条跑，含攻击用例**）

| # | 用例 | 期望 |
|---|---|---|
| 1 | 让 Agent `UPDATE customers SET status='x'`（无 WHERE） | 被拒，返回"未带 WHERE"，**不生成审批单** |
| 2 | 改不在白名单的表 | 拒绝：表未开启写入 |
| 3 | 写 `national_id` / `phone` 列 | 拒绝：敏感列禁止写入 |
| 4 | 影响 2000 行 | 判 L3，`required_role=3` |
| 5 | 普通用户请求 L3 | 审批单可见但按钮禁用，提示"需超管批准" |
| 6 | 普通用户伪造 `{"user_role":3}` 提交 | 无效：角色只从 token 反查 |
| 7 | 超管 2 小时未处理 | 自动 expired，数据未变 |
| 8 | 审批通过后篡改 SQL 再执行 | `sql_hash` 不匹配 → 拒绝执行 |
| 9 | 同一 `idempotency_key` 提交两次 | 只落库一次 |
| 10 | 执行中 kill 数据库连接 | 事务回滚，`change_log.status=failed`，`error_id` 可查 |
| 11 | 撤销刚应用的变更 | 数据回到 `before_json`，`status=reverted` |
| 12 | 审批通过但 `affected_rows` 与预估差 >20% | 自动回滚并告警 |
| 13 | 用 role=1 直接调 `/api/writes/xxx/decide` 批 L3 | 403 |
| 14 | 查看 `change_log.before_json` | 只含主键与被改列，无整行 |

### 8.12 写能力明确不做

| 不做 | 原因 |
|---|---|
| DDL（建表/改表/删表） | 风险与收益不匹配，让运维在命令行做 |
| 跨库事务 | 三库无强一致需求，反而引入分布式复杂度 |
| 批量导入（CSV→表） | 属数据工程，应走 ETL 而不是 Agent |
| 物理删除优先 | 有 `is_deleted` 字段时应提示改用软删 |
| 无审批的"自动修复" | 永远不做 |

---

## 9. 阶段 3 · 设计系统收口（1 天）

### 9.1 合并成一套

`main.css` 目标结构：

```
1. Tokens（:root + [data-theme="dark"]）
2. Reset / 基础排版
3. 布局骨架（app / side / main / header）
4. 组件（button / input / card / bubble / list / modal / toast / badge）
5. 子组件兼容层（上传、预览、来源、审批既有 class）
6. 工具类（sr-only / ellipsis / scroll-thin）
```

删掉 479–513 行那套重复定义，把其中的**有效规则**并进统一变量层。判断"有效"的方法：`grep` 该变量在组件里的引用，有引用就必须保留语义。

### 9.2 Token（锁定，不要再选色）

```css
:root {
  --brand-50:#eef2ff; --brand-100:#e0e7ff; --brand-200:#c7d2fe;
  --brand-300:#a5b4fc; --brand-400:#818cf8; --brand-500:#4f63e8;
  --brand-600:#2f52e0;   /* ← 主色，换租户只改这一个 */
  --brand-700:#2540b8; --brand-800:#1e3491; --brand-900:#1a2b73;

  --ink-900:#0f1115; --ink-800:#1c1f26; --ink-700:#2b3038;
  --ink-600:#4a5058; --ink-500:#6b7280; --ink-400:#9aa1ab;
  --ink-300:#c9ced6; --ink-200:#e5e7eb; --ink-100:#f2f4f7; --ink-50:#f8fafc;

  --ok:#12a150; --warn:#e08b00; --danger:#d92d20; --info:#1570ef;

  --r-sm:6px; --r-md:10px; --r-lg:16px; --r-full:999px;
  --sh-1:0 1px 2px rgba(16,24,40,.06);
  --sh-2:0 4px 12px rgba(16,24,40,.08);
  --sh-3:0 12px 32px rgba(16,24,40,.12);
  --s-1:4px; --s-2:8px; --s-3:12px; --s-4:16px;
  --s-5:20px; --s-6:24px; --s-8:32px; --s-10:40px;
  --t-xs:12px; --t-sm:13px; --t-base:14px; --t-md:15px;
  --t-lg:17px; --t-xl:20px; --t-2xl:26px;

  /* 兼容层：名字不变，值指向新 token（铁律三） */
  --accent: var(--brand-600);
  --panel: #ffffff;
}

[data-theme="dark"] {
  --ink-900:#f5f6f8; --ink-800:#e8eaee; --ink-700:#cdd2da;
  --ink-600:#a8afba; --ink-500:#8b929e; --ink-400:#6b7280;
  --ink-300:#4a5058; --ink-200:#2a2f37; --ink-100:#1c2027; --ink-50:#14171c;
  --panel:#171a20;
  --brand-600:#5b7cfa;   /* 深色下提亮，保证对比度 */
}
```

### 9.3 布局

| 区域 | 规格 |
|---|---|
| 侧栏 | 宽 268px，折叠用 `transform: translateX(-100%)`（不要 `display:none`，否则丢动画） |
| 顶栏 | 高 58px，`sticky top:0`，`backdrop-filter: blur(8px)`，底边 1px `--ink-200` |
| 内容区 | 最大宽 880px 居中，左右 padding 32px；**滚动容器只有一个** |
| 输入区 | `sticky bottom:0`，上方 24px 渐隐遮罩，宽度同内容区 |
| 消息间距 | 同角色 12px，换角色 28px |
| 响应式 | `<900px` 侧栏改抽屉；`<640px` padding 降到 16px |

### 9.4 助手消息去气泡

用户消息右对齐、`--brand-600` 底、白字、最大宽 72%；助手消息**无气泡**、左对齐、透明底、左侧 2px `--ink-200` 竖线。
理由：长文档在气泡里换行过窄，截图"一片色块"没有专业感。

### 9.5 空状态改场景卡

三张卡（图标 + 标题 + 一句话 + 点击填充输入框）：查业务数据 / 分析上传表格 / 查制度文档。
不要用"试试这样问"这种模仿别人的文案。

---

## 10. 阶段 4 · 修前端缺陷（1 天）

### 10.1 B1 复制按钮

```js
const copied = ref(false)
let timer = null
async function copy() {
  await navigator.clipboard.writeText(props.msg.content)
  copied.value = true
  clearTimeout(timer)
  timer = setTimeout(() => (copied.value = false), 1500)
}
onBeforeUnmount(() => clearTimeout(timer))
```

模板用 `{{ copied ? '已复制' : '' }}` + `<svg v-if="!copied">`，**不要 `querySelector`，不要改 `textContent`**。

### 10.2 B2 时间戳

后端 `to_plain_messages` 只返回 `{role, content}`，**没有时间戳**。所以：历史消息**不显示时间**（诚实优于伪造）；只有本轮新消息显示。
若产品确需时间，是**后端改造项**（加 `created_at` + 迁移存量），不要在本次做。

### 10.3 F10 输入法

```js
function onKeydown(e) {
  if (e.key !== 'Enter' || e.shiftKey) return
  if (e.isComposing || e.keyCode === 229) return   // 中文输入法合成中
  e.preventDefault()
  send()
}
```

验收：拼音输入 `nihao` 回车选词不发送，再回车才发送。

### 10.4 F12 XSS

```bash
cd frontend && npm i dompurify
```

```js
import DOMPurify from 'dompurify'
const html = computed(() =>
  DOMPurify.sanitize(marked.parse(props.content), {
    ADD_ATTR: ['target'],
    FORBID_TAGS: ['script', 'iframe', 'object', 'embed', 'form'],
    FORBID_ATTR: ['onerror', 'onload', 'onclick'],
  })
)
```

验收：输出 `<img src=x onerror=alert(1)>` 只显示破图，不弹窗。

### 10.5 F13 外链

渲染器里 `a` 标签统一加 `target="_blank" rel="noopener noreferrer"`；只允许 `http/https/mailto`，`javascript:` 降级为文本。

### 10.6 F18 竞态

```js
let runSeq = 0
async function sendQuestion(text) {
  const myRun = ++runSeq
  const threadAtSend = currentId.value
  // 流式循环里：
  if (myRun !== runSeq || threadAtSend !== currentId.value) return
}
```

`finally` 里**必须** `sending.value = false`，且只在 `myRun === runSeq` 时执行。

### 10.7 U1 替换 10 处 `alert/confirm`

- `components/ToastHost.vue` + `composables/useToast.js`：`toast.success/error/info(msg)`，右下角堆叠，3.5s 自动消失
- `components/ConfirmHost.vue` + `composables/useConfirm.js`：`const ok = await confirm({title,text,okText,danger})`

规则：Esc = 取消，遮罩点击 = 取消，打开时焦点在"取消"，删除类按钮用 `--danger`。
验收：`grep -rn "alert(\|confirm(" frontend/src` 结果为 **0**。

### 10.8 B3 / B4

- B3：`.side` 不设 `overflow`，只让 `.conv-list` 滚动；flex 子项加 `min-height:0`
- B4：删会话后若 `currentId` 指向已删项，自动切下一条；没有则新建空会话

---

## 11. 阶段 5 · 功能补齐（2 天）

| 编号 | 功能 | 要点 | 验收 |
|---|---|---|---|
| N1 | 消息操作条 | 复制 / **再答一次** / 赞 / 踩 | 四个按钮都有 hover 态 |
| N2 | 导出对话 | 前端拼 Markdown + `Blob` 下载 | 文件名含标题与日期 |
| N3 | 设置抽屉 | 主题 / 字号 / 显示过程 / 快捷键 / 服务状态 | 偏好持久化，刷新保持 |
| N4 | 快捷键 | `Ctrl+K` 搜索、`Ctrl+/` 设置、`Esc` 关浮层、`Ctrl+Enter` 发送 | 输入框聚焦时 `Ctrl+K` 不劫持 |
| N5 | 会话搜索 | 前端本地过滤标题 | 输入即筛 |
| N6 | 按日期分组 | 今天/昨天/近 7 天/更早 | 分组标题 sticky |
| N7 | 错误气泡带 `error_id` | 显示 + 复制按钮 | 用户能贴给运维 |
| N8 | 排队提示 | 全局锁导致第二个请求静默卡住 → 显示"已排队" | 双标签页不再像死机 |
| N9 | 变更历史页 | 读 `/api/writes/history`，表格 + 状态筛选 | 能按人/时间/表筛选 |

> **N1 的「再答一次」不能叫「重新生成」**：后端每轮追加历史，叫"重新生成"会让用户以为历史被替换。这是诚实性要求。

---

## 12. 阶段 6 · 企业级能力（2 天）

| 编号 | 能力 | 为什么值钱 | 要点 |
|---|---|---|---|
| E1 | 多租户品牌化 | 一套代码卖多家 | `frontend/src/brand.js` 导出 `{name, logo, primary}`；`theme.js` 用 `primary` 推导 50–900 色阶；支持 `window.__JTW_BRAND__` 运行期覆盖（运维不用重新构建） |
| E2 | 审计日志 | 金融/医疗合规刚需 | `services/ops/audit.py` + `data/audit.sqlite3`；记 who/when/what/工具/表/结果，**不存答案全文** |
| E3 | 会话归属隔离 | 多人共用不串数据 | `conversations.json` 加 `owner_id`；列表按当前用户过滤；管理员可看全部 |
| E4 | 首启动引导 | 交付体验 | 3 步向导：配 Key → 测连库 → 导知识库，每步可跳过 |
| E5 | 模型切换可见 | 信任感 | 顶栏模型徽章，点击可切（`/api/models` 已存在） |

**E1 硬约束**：租户只提供一个色值，不许让实施人员改 20 个变量；推导函数必须保证深色下对比度仍达 AA。

---

## 13. 阶段 7 · 工程化（1 天，可与 5/6 并行）

| 项 | 做法 | 验收 |
|---|---|---|
| 测试可收集 | 5 个 `_test_*.py` 改名 `test_*.py`；加 `backend/pytest.ini` 设 `testpaths=eval/tests` | `pytest --collect-only` 看到全部用例 |
| 冒烟四条 | ① `/api/health` 200 ② 完整一轮 chat 有 NDJSON ③ 上传后 preview 可取 ④ `_validate_readonly` 拒 `DROP` | 全绿 |
| **写能力测试** | 把 §8.11 的 14 条用例写成 `test_write_gate.py` + `test_write_executor.py` | 14 条全过 |
| 日志 | `backend/core/logging_setup.py`：控制台 + 轮转文件 `logs/app.log`（10MB×5）；`ERROR` 带 `error_id` | `print` 只留 CLI 入口 |
| 异常 | `except Exception:` 改为 `logger.exception(...)`；可忽略的加注释说明 | 95 处收敛到少数 |
| 依赖锁 | `pip freeze > backend/requirements.lock.txt`；`rapidocr-onnxruntime` 拆 optional | 新机器可复现 |
| 静态检查 | 后端 `ruff`（`select=E,F,I`），前端 `eslint` + `prettier` | 新增代码干净 |
| 生产服务器 | `waitress-serve --port=5000 web:app`；`app.run` 仅开发 | 发布包无 dev server 警告 |

---

## 14. 视觉质量判据（避免"AI 味"）

| 判据 | 错误 | 正确 |
|---|---|---|
| 渐变 | 到处蓝紫渐变当装饰 | **不用装饰性渐变**，只有 Logo 允许 1 处 |
| 阴影 | 每个卡片都大阴影 | 只有浮层用 `--sh-3`，卡片用 `--sh-1` 或不用 |
| 圆角 | 8/12/14/16 混用 | 只有 `--r-sm/md/lg/full` 四档 |
| 边框 | 边框 + 阴影同时上 | 二选一 |
| 图标 | emoji / SVG / 字体图标混用 | 统一 SVG（stroke 1.5，24×24，`currentColor`） |
| 空状态 | "试试这样问"式模仿 | 场景卡，写给这个行业的用户 |
| 加载 | 转圈三秒 | 骨架屏 3 行灰条，首字到达即替换 |
| 文案 | "智能助手为您服务" | "上个月销售额环比降了 8%，主要来自华东" |
| 对比度 | `#999` 灰字 | 正文 `--ink-900`，辅助 `--ink-500`（≥4.5:1） |
| 动效 | 什么都在动 | 只给出现/消失加 150–200ms `ease-out`，不弹跳 |

---

## 15. 可访问性与性能

- 可点元素有 `:focus-visible` 描边（2px `--brand-600`，offset 2px）
- 图标按钮必须有 `aria-label`
- 模态：`role="dialog"` + `aria-modal` + 焦点陷阱 + Esc 关闭
- 流式输出**不能**把 `aria-live` 挂在整段文本上（会反复朗读），只用一个 `sr-only` 状态节点，在"开始/结束/出错"三个时刻更新
- 长列表：`content-visibility: auto` + `contain-intrinsic-size`（不引入虚拟滚动库）
- 首屏 `dist` 主包 gzip < 300KB

---

## 16. 施工顺序与门禁

| 门禁 | 必须满足 | 不满足怎么办 |
|---|---|---|
| **门禁 1**（阶段 1 后） | 双击 `启动.bat` → MySQL 起 → 后端起 → 浏览器可登录 | 停下来修，不要继续 |
| **门禁 2**（阶段 2 后） | §8.11 的 14 条用例全过；未审批的写一定落不了库 | 停下来修 |
| **门禁 3**（阶段 3/4 后） | `npm run build` 通过；`grep alert/confirm` 为 0；9 个 bug 全部可复现验证 | 停下来修 |
| **门禁 4**（阶段 5/6 后） | §17 清单全勾选 | 停下来修 |

**每完成一个阶段**：`git push origin main`。不要攒到最后一起推。

---

## 17. 验收清单（逐条勾选，交付时贴出来）

### 交付链路
- [ ] 双击 `启动.bat`：`[1/5] 发布包完整性检查通过` → 自动打开浏览器 → 能登录
- [ ] 双击 `停止.bat`：`mysqld` 与 `python` 进程都消失
- [ ] 预检失败文案路径正确（无 `app\` / `data_sql\` 残留）
- [ ] 全新机器（无 runtime、无 mysql）能走完自动安装

### 写数据能力
- [ ] 无 WHERE 的 UPDATE/DELETE 被拒，且**不生成审批单**
- [ ] 非白名单表、敏感列被拒
- [ ] 影响 2000 行 → `required_role=3`，普通用户看到按钮禁用
- [ ] 超管批准后数据真的变了，`change_log` 有记录
- [ ] 超管 2 小时未处理 → 自动 expired，数据未变
- [ ] 审批后篡改 SQL → `sql_hash` 不匹配，拒绝执行
- [ ] 同一幂等键提交两次 → 只落库一次
- [ ] 撤销后数据回到 before
- [ ] `before_json` 只含主键与被改列，无整行
- [ ] 服务进程连接数据库用的**不是 root**
- [ ] `jt_write` 账号尝试 `DROP TABLE` → 数据库层拒绝

### 界面
- [ ] 1440×900 与 1920×1080 无横向滚动条、无元素重叠
- [ ] 浅/深色切换后文字可读（≥4.5:1）
- [ ] 只有一套设计系统（`--accent` 只有一个定义源）
- [ ] 空状态三张场景卡，点击填充输入框
- [ ] 变更卡 Before/After 差异高亮正确
- [ ] 长答案（>2000 字）滚动流畅

### 功能
- [ ] 中文输入法回车选词不误发送
- [ ] 多条消息复制改的是这一条，图标不消失
- [ ] 刷新后不显示伪造时间
- [ ] `<img onerror>` 不执行脚本
- [ ] 外链新开标签，原会话不丢
- [ ] 生成中切会话，回来输入框可用
- [ ] 删当前会话自动切下一条
- [ ] `grep -rn "alert(\|confirm(" frontend/src` 为 0
- [ ] 导出对话得到可读 `.md`

### 安全与数据
- [ ] `git ls-tree -r --name-only origin/main | grep -E "\.env$|\.sqlite3|conversations\.json|\.sql$|自动学习/.+\.md$"` 无输出
- [ ] 10 个数据目录的 `README.md` 都在仓库里
- [ ] 磁盘上所有代码文件都在索引中
- [ ] 未登录访问 `/api/chat` → 401
- [ ] role=1 访问 `/api/auth/users` → 403
- [ ] role=1 批准 L3 写 → 403

### 工程
- [ ] `pytest --collect-only` 能收集到用例
- [ ] 冒烟四条 + 写能力 14 条全绿
- [ ] `logs/app.log` 有轮转，500 错误带 `error_id`

---

## 18. 自检命令（每次推送前跑，30 秒）

```bash
cd "C:/Users/22124/Desktop/发布包/九天梧桐AI工作台"

# ① 构建
(cd frontend && npm run build) || exit 1

# ② 隐私：不能有输出
git diff --cached --name-only | grep -E "\.env$|\.sqlite3|conversations\.json|\.sql$|自动学习/问答记录|node_modules|\.pdf$" || echo "PASS-隐私"

# ③ 密钥：不能有输出
git grep --cached -n -E "sk-[A-Za-z0-9_-]{16,}|BEGIN (RSA|OPENSSH) PRIVATE KEY" || echo "PASS-密钥"

# ④ 原生弹窗：必须为 0
grep -rn "alert(\|confirm(" frontend/src | wc -l

# ⑤ 根账号：服务进程不得用 root
grep -rn "DB_USER=root" backend/.env 2>/dev/null && echo "⚠️ 仍在用 root" || echo "PASS-账号"

# ⑥ 体量基线：约 135 文件 / 2.3MB
git ls-files | wc -l
git ls-files -z | du -ch --files0-from=- 2>/dev/null | tail -1
```

---

## 19. 明确不做

| 不做 | 原因 |
|---|---|
| 换 UI 框架 | 会生成第三套设计系统，与 8 个子组件 class 冲突 |
| 引入 Vue Router | 现有 `useNav` 够用，加 router 要改所有跳转 |
| 引入虚拟滚动库 | `content-visibility` 够用 |
| 拆 `agent.py` | 独立任务，风险与收益不匹配本次交付 |
| 重写上传/预览/来源/审批组件 | 功能正常，只跟随新 token 变色 |
| i18n / PWA / 离线缓存 | 单语言本地服务，收益为负 |
| DDL 写能力 | 让运维做，不做进 Agent |
| `git add -f` 绕过忽略 | 会泄露企业数据 |
| 伪造历史消息时间戳 | 后端没这数据 |
| 把「再答一次」写成「重新生成」 | 会误导用户以为历史被替换 |
| 无审批的写操作 | 永远不做 |

---

## 20. 汇报格式（每阶段结束时）

```
## 阶段 N 完成

改了什么（按文件）
- backend/services/ops/write_gate.py：新建，8 条判定规则
- frontend/src/components/WriteProposalCard.vue：新建，含 Before/After 差异表
- ...

怎么验证的
- 用例 #1 无 WHERE UPDATE → 拒绝，未生成审批单 ✓
- 用例 #8 篡改 SQL → hash 不匹配，拒绝执行 ✓
- 命令：grep alert → 0

遗留 / 需要决策
- L3 超时 2 小时是否够？金融客户可能要求 24h

已推送
- commit abc1234 → 9sky/main
```

**不确定的事不要猜，列在"需要决策"里问我。**
**发现文档与代码不一致，以代码为准，并在对应处追加"实测修正"批注，不要静默改。**

---

## 21. 三个最容易翻车的地方

1. **`main.css` 是唯一视觉入口，动它之前必须打标签**。1231 行里一半是死代码，删错一处会让某个子组件样式塌陷，而你不会立刻发现（那个组件要特定操作才显示）。
2. **写能力的防线不能只写在 Python 里**。字符串黑名单挡不住 `SELECT ... INTO OUTFILE`、存储过程、编码绕过。**数据库账号权限才是最后一道墙**，`jt_write` 必须真的没有 DDL 权限。
3. **改 `.gitignore` 之后必须验证**。Git 的"父目录排除后无法重新纳入"规则，已经让 4 份 README 静默丢失过一次。改完用 `git check-ignore -v <路径>` 逐个确认。

---

交付的标准不是"我改完了"，是"租户第一眼就想用，且敢把生产数据交给你改"。
