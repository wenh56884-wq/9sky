# 九天梧桐 AI 工作台 · 优化建议与实施方案

> **评估快照**：2026-11-12 16:37（代码现状，非设计文档）
> **评估范围**：`backend/`（17,443 行 Python）、`frontend/`(2,098 行 Vue/JS)、`infra/scripts/`、根入口 `.bat`、`.env`、依赖与测试
> **本文性质**：只给诊断与方案，未改动任何业务代码。落地时按批次执行，每批有独立验收标准。
> **图例**：🔴 阻断交付 ｜ 🟠 有明确风险 ｜ 🟡 影响可维护性 ｜ 🟢 已具备，保持

---

## 零、现状速览

| 维度 | 现状 | 评价 |
|---|---|---|
| 代码注释 | 「为什么这么做」讲得很透（如 `pysandbox.py` 解释为何 join 超时杀不死线程） | 🟢 少见的高水准 |
| 安全护栏 | `_validate_readonly` 只读 SQL 校验、软沙箱、数据脱敏 `sanitize`、HITL 审批 | 🟢 该有的都有 |
| 可观测性 | `error_id` 机制、LangSmith 可选接入 | 🟡 后端有，用户侧看不到 |
| 分层结构 | `core/` + `services/{datasource,knowledge,analytics,ops}` 四域清晰 | 🟢 方向对 |
| 单文件体量 | `core/agent.py` **4,653 行** | 🟡 认知负担重 |
| 并发模型 | 全服务单一 RLock，一轮问答独占 | 🔴 单飞（单人可用，多人必卡） |
| 日志 | 152 处 `print()`，仅 1 处 `logging` | 🟡 无级别、无轮转、无法检索 |
| 测试 | 5 个 `_test_*.py`，pytest **收集不到** | 🔴 等于没有 |
| 交付链路 | 脚本已搬迁，但 `$Root` 少算一级 | 🔴 双击仍启动失败 |
| 发布包卫生 | 明文密钥 + 30MB 运行时数据 + 41MB node_modules | 🟠 安全与体积双输 |
| 文档入口 | `README.md` **153KB / 1,987 行** | 🟡 等于没有入口 |

**总判断**：代码层是「良」，交付层是「不可用」。先花半天把交付链路打通，再谈架构。

---

## 一、🟢 已在本轮修复（不必重做，仅登记）

| 项 | 原问题 | 现状 |
|---|---|---|
| 脚本目录双层嵌套 | `infra/scripts/scripts/setup_and_start.ps1` | 已上提至 `infra/scripts/`，与 `启动.bat` 路径一致 ✅ |
| 数据库端口三处不一致 | `my.ini`/脚本 3307，`.env`/`agent.py` 3306 | 已统一为 3306 ✅ |
| 脚本内部旧 `app/` 布局 | `$AppDir=$Root\app`、`$SqlDir=$Root\data_sql` | 已改为 `backend`、`infra\sql` ✅ |

> 遗留文案：`setup_and_start.ps1:52` 的报错仍写「缺少 app\web.py」、`:54` 仍写「缺少数据文件 data_sql\…」。只影响排障可读性，顺手改掉。

---

## 二、🔴 P0 · 阻断级（不修就不能发）

### P0-1 启动脚本 `$Root` 少算一级 —— 双击必然失败

**证据**
```powershell
# infra/scripts/setup_and_start.ps1:11
$Root   = Split-Path -Parent $PSScriptRoot     # → …\九天梧桐AI工作台\infra  ❌
$PyExe  = Join-Path $Root "infra\runtime\python\python.exe"
#        → …\infra\infra\runtime\python\python.exe  → 不存在
```
脚本从 `infra/scripts/scripts/` 上提到 `infra/scripts/` 后，`Split-Path -Parent` 只上溯了一级，落到 `infra/` 而不是项目根。第 51 行预检随即 `Fatal "缺少 runtime\python（发布包不完整）"`。

同一错误波及 `:58` 磁盘空间检查、`:67/:71` MySQL 模板 robocopy 源目录。

**方案**（二选一，推荐 A）
- **A（改一行）**：`$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)`
- **B（更稳）**：`$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path`，避免相对路径含中文/空格时的解析歧义

**同时处理**：`stop_all.ps1:7` 的 `$Root` 同名变量语义不同（它用来匹配 python 进程路径，而 `infra\runtime\python\python.exe` 恰好在 `infra` 下，属**偶然正确**）。建议改名为 `$InfraRoot` 并加注释，避免下次搬迁又错。

**验收**：全新目录解压 → 双击 `启动.bat` → 控制台依次出现 `[1/5]…[5/5]` → 浏览器自动打开 `http://127.0.0.1:5000` → `/api/health` 返回 `ok:true`；双击 `停止.bat` → python 与 mysqld 进程均消失。

---

### P0-2 发布包内携带明文密钥

**证据**
- `backend/.env` 含真实 `OPENAI_API_KEY`、`DEEPSEEK_API_KEY`、`DB_PASSWORD=123456`
- `backend/.gitignore` 已忽略 `.env`（版本安全 ✅），但**发布压缩包是整目录打包**，密钥随包流出去
- `backend/.env.example` 有 17KB 说明，却没承担「首启动生成」的职责

**方案**
1. 打包脚本排除 `.env`，只留 `.env.example`；
2. `web.py` 启动时若 `.env` 缺失 → 生成到 `%APPDATA%\JiuTianWuTong\.env`，并从 `.env.example` 拷贝注释骨架；
3. 配置读取顺序：`环境变量 > 用户目录 .env > 包内 .env`（包内那份仅开发用）；
4. **立即轮换**已进包的两个 API Key（当作已泄露处理）。

**验收**：删掉 `backend/.env` 后双击启动，程序不崩，前端首屏引导填写 Key；`grep -r "sk-" 发布包` 无命中。

---

### P0-3 上传/删除接口在未配 token 时完全开放

**证据**
```python
# backend/web.py:228 / :279 / :305
token = (os.getenv("ADMIN_TOKEN") or "").strip()
if token:                    # ← token 为空 = 直接跳过校验
```
`backend/.env` 确实没配 `ADMIN_TOKEN`，即 `POST /api/uploads`、`DELETE /api/uploads/<name>`、`DELETE /api/uploads/memory` 三个写接口零鉴权。

当前 `HOST` 默认 `127.0.0.1`，风险有限；但只要有人把 `HOST` 改成 `0.0.0.0`（局域网共享很常见），就是任意文件写入 + 数据删除。

**方案**：改为「默认拒绝非本机」——
```python
def _admin_ok() -> bool:
    token = (os.getenv("ADMIN_TOKEN") or "").strip()
    if token:                                  # 配了 token：比 token
        return given == token
    return request.remote_addr in ("127.0.0.1", "::1")   # 没配 token：只放行本机
```
**验收**：`curl -X POST http://<局域网IP>:5000/api/uploads` 返回 403；本机仍 201。

---

## 三、🟠 P1 · 架构与并发（决定产品定位）

### P1-1 整个服务是「单飞」的：一轮问答独占全局锁

**证据**
```python
# backend/core/agent.py:4238（stream_ask）、:4440（stream_deep）
with self._lock:            # RLock 一直持有到最后一个 token
    for _ in range(MAX_STEPS):
        ...
```
加上三套**进程级**共享状态：`_ROUND_SOURCES`（模块级 list，`agent.py:348`）、`set_current_thread()`（全局，`:1912`）、`_LAST_QUERY_CTX`（contextvar，`:321`）—— 前者与后者机制不统一，且都假设「同一时刻只有一轮在跑」。

**后果**：第二个标签页/第二个用户在第一个回答结束前**静默卡住**（前端无任何提示，用户会判定为「软件卡死」）。一次复杂问答含规划+多轮工具+自检，30–90 秒很常见。

**方案（先定产品定位，再选实现）**
- **定位 A：单用户桌面工作台** → 保留现状，但必须做两件事：
  1. README 显式写明「同一时刻仅支持一轮问答」；
  2. 前端在 `streaming=true` 时禁用发送并提示「上一轮回答中，请稍候」。
- **定位 B：多人/多标签并发** → 分三步：
  1. 把 `_ROUND_SOURCES`、`current_thread`、`_LAST_QUERY_CTX` 统一收进 `contextvars.ContextVar`（ctx 对象一次装齐）；
  2. `self._lock` 缩到只保护 checkpointer 落盘（约 5 行），不再包住模型调用；
  3. `service` 保持单例无状态，会话隔离靠 `thread_id`（现在已经是这么设计的，改动量可控）。

**验收（B 方案）**：两个终端同时 `curl /api/chat`，两个流交错吐字，总耗时 ≈ 单轮耗时而非 2 倍。

---

### P1-2 `core/agent.py` 4,653 行，一个文件装了整个系统

**现状**：DB 连接与 SQL、图表渲染、技能卡匹配、记忆 CRUD、规划运行时、LLM 工厂与渠道降级、深度搜索、ConversationStore、ChatService、CLI 全在同一文件。

**拆分方案**（按依赖方向，先抽叶子再抽枝干，每步可独立回归）

| 新文件 | 内容（现 agent.py 行号） | 估计行数 |
|---|---|---|
| `core/tools/db_tools.py` | `db_connect`/`execute_sql`/`get_table_schema`/`list_database_tables`/`plot_last_result`（184–795） | ~600 |
| `core/tools/table_tools.py` | `find_table`/`describe_table`/`query_tables`/`analyze_table_query`（1988–2404） | ~420 |
| `core/tools/memory_tools.py` | `remember`/`recall`/`forget`/`list_memories`/`search_memories`（1638–1907） | ~270 |
| `core/llm/factory.py` | `available_models`/`resolve_model`/`resolve_provider`/`build_llm`/渠道冷却（2704–2872） | ~170 |
| `core/runtime/planning.py` | `create_task_plan`/`_prepare_plan`/`_apply_reflection`/digest（3084–3414） | ~330 |
| `core/runtime/deep_search.py` | `_iter_deep_search`/`smart_search`/rerank（3449–3783） | ~330 |
| `core/conversation.py` | `ConversationStore`/`ChatService`（3783–4487） | ~700 |
| `core/agent.py`（保留） | `TOOLS` 注册表 + `build_system_prompt` + `create_agent` + `main` | ~400 |

**约束**：拆分期间保持 `from core.agent import X` 的对外接口不变（在各新文件末尾重新导出），前端与 `web.py` 零改动。

**验收**：`web.py` 只改 import 行；拆分前后跑同一组 10 条问句，答案与工具调用序列一致。

---

### P1-3 同步锁 + 流式生成器：线程被网络等待占住

Flask 默认多线程模式下，每个流式请求占用一个线程直到结束，且持锁。即使维持单用户，也建议：
- 生产用 `waitress`（Windows 友好、纯 Python、无需编译），`threads=8`；
- 或明确 `threaded=False` 并在文档说明，避免「看起来能并发、其实排队」的错觉。

---

## 四、🟡 P2 · 工程质量（决定三个月后还能不能改）

### P2-1 测试等于不存在

**证据**
- 命名 `_test_eval_core.py` / `_test_spreadsheet.py` —— pytest 默认只匹配 `test_*.py` 与 `*_test.py`，**一个都收不到**；
- 5 个文件中仅 2 个有 `if __name__ == "__main__"`；
- `_test_vectordb.py:5` 的 docstring 还写「跑法（在 app/ 目录下）」，迁移后已失效；
- 无 `pytest.ini` / `pyproject.toml` / CI。

**方案**
1. 全部改名 `test_*.py`；
2. 根放 `pytest.ini`：`testpaths = backend/eval/tests`、`pythonpath = backend`；
3. **先补 4 条冒烟**（成本半天，收益最大）：
   - `test_health`：`/api/health` 200 且含 `checkpointer` 字段
   - `test_chat_once`：mock LLM，`/api/chat` 返回 NDJSON 且末行为 `done`
   - `test_upload_preview`：上传 xlsx → `preview` 返回列名
   - `test_readonly_guard`：`_validate_readonly("DROP TABLE x")` 抛 `ValueError`
4. 把 `eval/accuracy_last.json` 与 `accuracy_prev.json` 的比较纳入 CI 门禁（已有 baseline，只差执行）。

**验收**：`pytest -q` 输出 `≥4 passed`，且故意改坏一个函数能被捕获。

### P2-2 日志体系缺失

**证据**：`backend/core` + `backend/services` 共 **152 处 `print()`**；全项目仅 `services/ops/debugging.py:37` 一处 `getLogger`；`backend/.env` 里 `LOG_FILE` 是注释状态。

**方案**
- 新增 `services/ops/logging_setup.py`：统一格式 `%(asctime)s %(levelname)s [%(request_id)s] %(name)s: %(message)s`，`RotatingFileHandler`（10MB × 5）+ 控制台双输出；
- `print()` 分级替换：用户可见提示 → `info`；工具调用 → `debug`；异常 → `exception` 并带 `error_id`；
- CLI 入口（`agent.py:main`）保留 `print`，那是给人看的。

**验收**：`logs/agent.log` 里一次问答可按 `request_id` 串起「规划→工具→自检→落盘」全链路。

### P2-3 异常被静默吞掉

**证据**：`backend/` 内 **95 处 `except Exception:`**，典型如 `agent.py:4041` `delete_thread` 失败 `pass`、`web.py:270` 多处。

**方案**：分两类处理
- **确实可忽略**（旧版本不支持某 API）→ 保留 `pass`，但补一行注释说明「什么情况下会走到这里、为什么安全」；
- **可能隐藏真实故障**（删会话、写记忆、重建索引）→ 至少 `logger.warning`，并把 `error_id` 带回前端。

### P2-4 依赖不可复现

**证据**：`backend/requirements.txt` 全部 `>=`，含 `langchain>=1.0.0`、`langgraph>=1.0.0` 这类大跨度；`rapidocr-onnxruntime>=1.4.0` 属重依赖（onnx + 模型权重）。

**方案**
- 生成锁文件：`uv pip compile requirements.in -o requirements.txt`（或 `pip freeze`）；
- 分层：`requirements.txt`（核心）+ `requirements-ocr.txt`（OCR，optional）+ `requirements-dev.txt`（pytest/ruff）；
- 发布包体积评估：OCR 权重与 onnx runtime 约占首装 200MB+，若终端用户不需要识图，默认不装。

### P2-5 无静态门禁

无 ruff / eslint / prettier / CI。建议最小配置：`ruff check backend`（E,F,I,UP）、`eslint + prettier`（frontend），本地 pre-commit 钩子即可，不上 CI 也有收益。

---

## 五、🟠 P3 · 发布包卫生与文档

| 项 | 问题 | 方案 |
|---|---|---|
| 运行时数据进包 | `backend/data` 约 30MB（`tables.sqlite3` 14.5MB、`vector.sqlite3` 4.4MB、`uploads/`） | 打包前清空为 `.gitkeep`，首启动自建；`checkpoints.sqlite3`/`conversations.json` 必删（含历史问答） |
| 遗留目录 | `backend/data/非结构化数据` 与规范冲突（规范说并入 `backend/eval/data/`） | 移入 `backend/eval/data/` 或删除 |
| 前端依赖进包 | `frontend/node_modules` 约 41MB | 删除；只保留 `dist/` |
| README 不可读 | 153KB / 1,987 行，无目录导航 | 拆为 `README.md`（≤150 行）+ `docs/ARCHITECTURE.md` + `docs/API.md` + `docs/CHANGELOG.md` |
| 构建脚本位置 | `backend/build_techdoc.py` 812 行在后端根 | 移 `tools/build_techdoc.py` |
| 迁移文档未归档 | `docs/MIGRATION.md`、`docs/FRONTEND_MIGRATION_TASKS.md` | 迁移已完成，移入 `docs/archive/` |
| 评测结果散落 | `backend/eval/accuracy_last.json`、`accuracy_prev.json` 在目录根 | 移 `backend/eval/reports/` |

**API 文档现成素材**：`web.py:316-370` 已经把 `/api/chat`、`/api/deep` 的 NDJSON 事件表写全（`thinking/plan/plan_step/token/rewind/tool/sources/done/error`），直接搬进 `docs/API.md` 即可，不用重写。

---

## 六、🟡 P4 · 产品体验（有则更好）

| 编号 | 问题 | 建议 |
|---|---|---|
| P4-1 | `error_id` 后端生成了，前端只取 `message`（`useChat.js:110`） | 在错误气泡里显示「错误编号：xxx」，排障时用户能直接报号 |
| P4-2 | 首启动无「模型连通性自检」 | `/api/health` 加一次极轻量 ping（带 2s 超时、结果缓存 60s），前端首屏用状态条显示「模型 已连通 / Key 无效 / 网络不通」 |
| P4-3 | 刷新/关页丢失本轮回答 | 建议把 streaming 中的部分答案每 2s 落一份 draft 到会话元数据，重进可「继续查看」 |
| P4-4 | 单飞时前端静默 | 见 P1-1 定位 A 第 2 条 |
| P4-5 | 向量检索为全量矩阵点积（`vectordb.py:364` `self._matrix`） | 当前语料规模（4.4MB sqlite）完全够用；若知识库 > 10 万段再考虑 ANN，现在不必优化，但值得在文档写明上限 |

---

## 七、文件级改动清单（落地时照此执行）

### 需新建
```
backend/services/ops/logging_setup.py      # 日志初始化（P2-2）
backend/core/tools/{db,table,memory}_tools.py   # 拆分（P1-2）
backend/core/llm/factory.py                     # 拆分（P1-2）
backend/core/runtime/{planning,deep_search}.py  # 拆分（P1-2）
backend/core/conversation.py                    # 拆分（P1-2）
pytest.ini                                      # P2-1
backend/requirements-dev.txt                    # P2-4
docs/ARCHITECTURE.md / docs/API.md / docs/CHANGELOG.md   # P3
tools/build_techdoc.py                          # 由 backend/ 移入
```

### 需修改
```
infra/scripts/setup_and_start.ps1:11   $Root 上溯两级                       🔴 P0-1
infra/scripts/setup_and_start.ps1:52   "缺少 app\web.py" → "缺少 backend\web.py"  🟡 文案
infra/scripts/setup_and_start.ps1:54   "data_sql\…" → "infra\sql\…"            🟡 文案
infra/scripts/stop_all.ps1:7,18        $Root → $InfraRoot（语义改名）          🟠 P0-1
backend/web.py:228,279,305             统一 _admin_ok() 鉴权                    🔴 P0-3
backend/web.py:447                     生产入口换 waitress                      🟡 P1-3
backend/core/agent.py:4238,4440        锁粒度收窄（若选定位 B）                 🟠 P1-1
backend/core/agent.py:348,1912,321     全局态 → contextvars（若选定位 B）       🟠 P1-1
backend/requirements.txt               == 锁定 / 拆分 extra                    🟡 P2-4
frontend/src/composables/useChat.js:110 展示 error_id                          🟡 P4-1
README.md                              拆分为入口 + 三份 docs                   🟡 P3
```

### 需删除 / 迁移
```
frontend/node_modules/                删（发布前）
backend/.env                          移出包，改首启动生成                🔴 P0-2
backend/data/*.sqlite3, conversations.json, uploads/   清空，首启动自建
backend/data/非结构化数据/             移 backend/eval/data/
docs/MIGRATION.md, FRONTEND_MIGRATION_TASKS.md   移 docs/archive/
backend/eval/accuracy_*.json          移 backend/eval/reports/
```

---

## 八、三批落地节奏

### 第一批 · 半天 · 只修交付（不做完不准发）
- [ ] P0-1 `$Root` 上溯两级 + 两条 Fatal 文案 + `$InfraRoot` 改名
- [ ] P0-2 `.env` 移出包 + 首启动生成 + 轮换已泄露 Key
- [ ] P0-3 上传接口默认只放行本机

**出口标准**：全新目录解压 → 双击启动 → 浏览器可用 → 停止脚本干净退出 → 包内 `grep` 不到任何密钥。

### 第二批 · 1–2 天 · 安全与可维护
- [ ] P2-1 测试改名 + `pytest.ini` + 4 条冒烟
- [ ] P2-2 统一日志 + `request_id`
- [ ] P2-4 依赖锁定 + 分层
- [ ] P0 遗留文案、P3 发布包清场（node_modules / 运行时数据）
- [ ] P4-1 前端展示 `error_id`

**出口标准**：`pytest -q` 全绿；`logs/agent.log` 可按 `request_id` 追全链路；发布包体积下降 ≥40%。

### 第三批 · 按需 · 架构
- [ ] P1-1 产品定位决策 → 要么写进 README，要么上 contextvars 改造
- [ ] P1-2 `agent.py` 按表拆分（8 个文件，接口不变）
- [ ] P1-3 waitress 生产入口
- [ ] P3 README 拆分 + `docs/API.md`（素材已现成）

**出口标准**：`agent.py` ≤ 500 行；并发方案与产品定位一致且写进文档；新同事能只读 `docs/ARCHITECTURE.md` 就找到改代码的位置。

---

## 九、不建议做的事（避免过度工程）

1. **不要**为了「架构好看」把 Flask 换成 FastAPI + 前端换 TS —— 当前 2,098 行前端、477 行 web 层，收益远小于迁移风险。
2. **不要**现在上向量数据库（Milvus/pgvector）—— 4.4MB 语料的矩阵点积在毫秒级，纯属自找运维。
3. **不要**引入 Celery/Redis 做异步队列 —— 单机单用户的问答流，锁 + 线程已够；等真有多人需求再按 P1-1 定位 B 走。
4. **不要**重写 `pysandbox` 或 `sanitize` —— 这两处实现质量高于常见水平，重写只会引入新洞。
