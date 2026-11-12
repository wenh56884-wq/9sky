# 九天梧桐 AI 工作台 · 交付提示词（给 Claude 执行）

> **这份文件是唯一任务书。** 你（Claude）拿到它之后，不需要再问我任何背景问题，按 §9 的顺序施工，按 §11 自检，按 §13 汇报。
> 事实基线：仓库 `https://github.com/wenh56884-wq/9sky`，分支 `main`，commit `33d23a3`，134 个跟踪文件。
> 文中所有行号以该 commit 为准；你改过代码后，行号会漂移，**请按符号名搜索，不要迷信行号**。

---

## 0. 一句话说明这个产品

一个**本地运行的、面向企业租户的 AI 数据工作台**：用户登录后可以用自然语言问业务数据，Agent 通过 ReAct 循环调用工具（只读 SQL、Python 沙箱、RAG 知识库、表格查询）回答问题，危险操作走人工审批（HITL），全程可溯源。

**它已经不是玩具**：鉴权、用户管理、审批中心、只读 SQL 校验、沙箱、数据溯源都已落地。
**它还不是能卖的产品**：一键启动是断的、界面是两套样式叠加出来的、错误处理靠 `alert()`、没有测试。

你的任务是把"能跑"变成"敢卖"。

---

## 1. 你的角色与成功标准

你是**同时具备三种能力的人**：

- **前端工程师**：把视觉做到商业产品水准，且不破坏已有功能
- **Python 后端工程师**：修交付链路、收敛架构、补工程化
- **交付负责人**：每个阶段结束后，项目必须是**可运行、可回滚、可交付**的状态

**成功标准（四条，缺一条算失败）**

1. 双击 `启动.bat`，从零到能用，全程无人工干预，无红色报错
2. 界面在 1440×900 与 1920×1080 下都像商业产品，不是"AI 生成的页面"
3. 所有改动都能通过 `npm run build`、能通过 §11 的四条红线
4. 每个阶段结束都推送到 `9sky`，且**没有泄露任何企业数据**

---

## 2. 项目事实（先读，不要猜）

### 2.1 技术栈

| 层 | 技术 | 说明 |
|---|---|---|
| 后端 | Flask 2.x + Python 3.13 | 单文件 `backend/web.py`（599 行）暴露全部 API |
| Agent | LangChain 1.x ReAct + LangGraph Checkpointer | 核心引擎 `backend/core/agent.py`（4664 行） |
| 前端 | Vue 3 `<script setup>` + Pinia + Vite | `frontend/src/`，无 Vue Router，用自研 `useNav` 切视图 |
| 数据库 | MySQL 8（内置绿色版） | 三个业务库：金融 / 医疗 / 通信 |
| 本地存储 | SQLite + JSON | 会话、记忆、向量索引、表格索引 |
| 样式 | 单文件 `frontend/src/styles/main.css`（1231 行） | **无 UI 框架**，纯手写 CSS 变量 |

### 2.2 目录职责（改动前必须知道这段）

```
backend/          Flask 服务 + Agent 引擎（代码，全入库）
  core/           agent.py 引擎、cognition/ 规划
  services/       ops/（鉴权·审批·脱敏）datasource/（上传·表格）knowledge/（RAG）analytics/（统计·沙箱）
  eval/           离线评测脚本 + 题库（代码与题库入库，运行结果不入库）
  skills/         技能卡（tables/general/database）
  knowledge/      示例知识库（入库）；uploads/ 与 自动学习/ 不入库
  data/           运行时数据（只入库 README）
frontend/src/     Vue 源码（全入库）
frontend/dist/    Vite 产物（不入库，后端托管它）
infra/            mysql/ runtime/ sql/ scripts/（只入库 scripts 与各目录 README）
docs/            设计文档（全入库）
```

### 2.3 启动链路（当前是断的，见 P0-1）

```
启动.bat  →  infra\scripts\setup_and_start.ps1  →  MySQL → 后端 web.py → 打开浏览器
停止.bat  →  infra\scripts\stop_all.ps1
```

- 后端默认 `127.0.0.1:5000`
- MySQL 端口 **3306**（`infra/mysql/my.ini`、`backend/.env` 已统一）
- MySQL 运行目录固定 `C:\ProgramData\JiuTianWuTong`（纯英文路径，规避中文用户名问题）

### 2.4 鉴权现状（**已实现，不要重写**）

- Bearer Token：`Authorization: Bearer <token>`，服务端存会话，支持登出/踢人
- 角色：`1` 普通用户 / `2` 管理员 / `3` 超级管理员（`ROLE_NAMES` 在 `services/ops/auth_store.py`）
- 已落地路由：`/api/auth/{login,logout,me,change-password,users}` + `/api/approvals` + 上传全套
- `backend/web.py` 全部业务路由**都已加** `@require_auth` 或 `@require_role(n)`
- 前端：`stores/auth.js`、`api/auth.js`（自动注入 Bearer、401 回登录页）、`views/LoginView.vue`、`views/UserManage.vue`、`components/ApprovalCenter.vue`

**这意味着**：`docs/OPTIMIZATION.md` 与 `docs/FRONTEND-REBUILD-SPEC.md` 里"鉴权未实现、只画了客户端的线"的段落**已过期**。看到这类描述一律以代码为准，并顺手修正文档。

### 2.5 流式协议（改前端时必须遵守）

`POST /api/chat` 返回 **NDJSON**（每行一个 JSON 对象），事件类型见 `backend/web.py` 中 `/api/chat` 的注释。前端解析在 `frontend/src/composables/useChat.js`。
**不要改事件名，不要改成 SSE，不要改字段名** —— 这是前后端唯一契约。

---

## 3. 五条铁律（违反任意一条，本次交付判定失败）

### 铁律一：仓库只有一个，每次改完就推

```bash
cd "C:/Users/22124/Desktop/发布包/九天梧桐AI工作台"
git add -A
git status --short          # 必须人工看一眼
git commit -m "type(scope): 说明"
git push origin main
```

- 远程：`https://github.com/wenh56884-wq/9sky`，分支 `main`，**公开仓库**
- 提交信息：`type(scope): 说明`，`type` ∈ `feat|fix|style|docs|chore|refactor|perf`
- 一次提交只做一件事；不写"update""修改"这类无信息量的词
- **不攒提交**。完成一个可验证的小步就推一次

### 铁律二：企业数据不进，代码全进，目录要留

用户的原话：**「企业数据不要放，代码放；但文件目录要进，才知道这里放什么东西。」**

| 必须入库 | 必须排除 |
|---|---|
| 所有 `.py` `.vue` `.js` `.css` `.html` `.ps1` `.bat` `.md` | `.env` 及任何密钥、私钥、Token |
| 各数据目录里的 `README.md`（说明用途的占位文件） | `*.sqlite3`、`conversations.json`、`table_memory.json` |
| 题库与示例知识库（只有题目和 SQL，无结果数据） | `backend/data/uploads/` 用户上传文件 |
| 构建脚本、启动脚本、SQL 的**说明** | `backend/knowledge/自动学习/` 真实问答记录 |
| | `infra/sql/*.sql`（380/107/80MB，超 GitHub 单文件上限，推送必被拒） |
| | `infra/runtime/`、`infra/mysql/`（约 2GB 二进制与数据） |
| | `frontend/node_modules/`、`frontend/dist/`、`backend/reports/` 产物 |

**Git 的坑（已经踩过一次，别再踩）**：父目录被整条排除后，里面的文件用 `!` 也无法重新纳入。所以必须写成：

```gitignore
backend/data/*
!backend/data/README.md
!backend/data/uploads/            # 先放行子目录
!backend/data/uploads/README.md   # 再放行子目录里的说明
```

不确定某文件为什么被忽略时，用 `git check-ignore -v <路径>` 精准定位是哪条规则命中。
**禁止 `git add -f`** 绕过红线；确需例外，先改 `docs/REPO-PUSH.md` 登记理由。

### 铁律三：不破坏既有契约

以下四类东西**改名 = 制造隐蔽 bug**：

1. **CSS 变量与类名**：`--accent`、`--panel`、`ds-item`、`up-panel`、`msg-actions` 等被 8 个不改造的子组件（上传面板、数据预览、来源抽屉、来源卡、计划面板、深度追踪、状态行、审批卡）深度引用。**只重设值，不改名**；需要新变量就用新名字。
2. **localStorage 键**：改了等于清空用户已有偏好（主题、字号等）。
3. **接口路径与字段**：前端 `api/index.js` 与 `web.py` 一一对应。
4. **NDJSON 事件名**：见 §2.5。

### 铁律四：不加依赖、不换框架（除非本文明确要求）

- **禁止**换 UI 框架（Element / Arco / AntD / Tailwind）——会生成第三套设计系统，与既有 class 全面冲突
- **禁止**引入虚拟滚动库、i18n、PWA、状态机库
- **禁止**改后端架构（拆 `agent.py` 属独立任务，不在本次范围）
- **唯一允许新增的前端依赖**：`dompurify`（安全修复必需，见 P1-F12）

### 铁律五：每次改完必须能构建

```bash
cd frontend && npm run build     # 不通过不许提交
```

后端改动跑一遍冒烟：`python -c "import web"` 在 `backend/` 下无异常。

---

## 4. 现状诊断（已验证，带证据）

> 这一节是"为什么改"，不是"改什么"。施工项在 §5。

### 4.1 已经做好、**不要重做**的部分

| 能力 | 位置 | 评价 |
|---|---|---|
| 只读 SQL 校验 | `core/agent.py` `_validate_readonly` | 拦截 DROP/DELETE/UPDATE，做得对 |
| Python 沙箱 | `services/analytics/pysandbox.py` | 受限执行，够用 |
| 人工审批 HITL | `services/ops/hitl.py` + `/api/approvals` | 完整 |
| 数据溯源 | 每轮记录 sources，前端 `SourceDrawer` | 卖点，别动 |
| RAG 知识库 | `services/knowledge/` | 可用 |
| 鉴权与用户管理 | `services/ops/auth.py` + 前端三件套 | 已落地 |
| 深色/浅色主题 | `main.css` 变量层 | 结构在，但被两套系统污染 |

### 4.2 P0 · 交付阻断（不修就别谈美化）

| 编号 | 问题 | 证据 | 后果 |
|---|---|---|---|
| **P0-1** | 一键启动必失败 | `infra/scripts/setup_and_start.ps1:11` `$Root = Split-Path -Parent $PSScriptRoot` → `$Root` 实际等于 `infra/`；但第 12 行 `$PyExe = Join-Path $Root "infra\runtime\python\python.exe"` → 变成 `infra\infra\runtime\...`，第 51 行预检 `Fatal "缺少 runtime\python"` | 双击 `启动.bat` 直接红字退出，用户第一眼就是"这软件坏了" |
| **P0-2** | 预检提示文案是旧版路径 | 同上文件第 52 行仍写 `app\web.py`、第 54 行仍写 `data_sql\$f` | 排障时误导自己 |
| **P0-3** | `stop_all.ps1:7` 的 `$Root` 语义不同 | 它只用于匹配 python 进程路径（`runtime` 正好在 `infra/` 下），**恰好是对的** | 两个脚本同名变量含义相反，下次搬迁必错 |

### 4.3 P1 · 前端真实缺陷（不是审美问题，是 bug）

| 编号 | 问题 | 位置 | 影响 |
|---|---|---|---|
| **B1** | 复制按钮用全局 `document.querySelector('.msg-actions .mini-btn.copied')` 定位，且 `textContent='已复制'` 会把 SVG 抹掉 | `components/MessageItem.vue:24` | 多条消息时改的是页面上**第一条**；图标**永久消失** |
| **B2** | 时间戳在挂载时 `new Date()` 生成 | `components/MessageItem.vue:14,17` | 刷新后**所有历史消息显示同一时刻** |
| **F10** | 回车发送未判断输入法合成状态 | `components/Composer.vue:32` `if (e.key === 'Enter' && !e.shiftKey)` | **中文用户按回车选词就误发送**，对国内租户是致命体验 |
| **F12** | `marked` 输出裸 `v-html`，未净化 | `components/MarkdownView.vue:43,80` | 模型输出含 `<img onerror=...>` 即可执行脚本，**XSS 漏洞** |
| **F13** | 外链无 `target="_blank"` | `components/MarkdownView.vue` 的 renderer | 点外链整个 SPA 跳走，会话状态全丢 |
| **F18** | 生成中切换会话，流仍写入已卸载对象，`sending` 卡在 `true` | `stores/chat.js` 的 `sendQuestion` | 新会话输入框一直禁用，**只能刷新页面** |
| **B3** | 侧栏 `.side` 与 `.conv-list` 都是 `overflow-y:auto` | `main.css` | 双滚动容器，滚轮跳动 |
| **B4** | 删除当前会话后 `currentId` 残留 | `stores/conversations.js` | 右侧空白但输入框可用，状态不一致 |
| **U1** | 10 处原生 `alert()` / `confirm()` | `ChatHeader.vue:44`、`Sidebar.vue:47,54,67,69,75,77,89` 等 | 商业产品大忌：无法样式化、阻塞线程、移动端样式丑 |
| **F20** | 助手消息用气泡包裹长文档 | `MessageList.vue` / `main.css` | 880px 内容区里再套气泡，长答案换行过窄，截图难看 |

### 4.4 P2 · 设计系统污染

`frontend/src/styles/main.css` 共 1231 行，**两套设计系统叠加**：

- 第 8 行 `--accent: #5b6cff`、第 45 行 `--accent: #7d8cff`（旧单文件 SPA 的靛紫）
- 第 479 行 `--accent: #165dff`、第 513 行 `--accent: #4c88ff`（注释写着"豆包风格 · Arco 色板"）

后一套覆盖前一套，**前 470 行基本是死代码**。改颜色前你得先猜哪一遍生效。
更麻烦的是：`--accent` 被三个不同作用域重定义，改主题色时会出现"一半蓝一半紫"。

### 4.5 P3 · 工程化缺失

| 项 | 现状 |
|---|---|
| 测试 | `backend/eval/tests/` 下 5 个文件叫 `_test_*.py`，pytest 默认只认 `test_*.py` / `*_test.py` → **一个都收不到**，等于没有测试 |
| 日志 | `backend/core` + `services` 有 152 处 `print()`，全项目只有 `debugging.py` 一处 `logging` |
| 异常 | 95 处 `except Exception:`，多处 `pass` 静默吞掉 |
| 依赖 | `requirements.txt` 全是 `>=`，不可复现 |
| 静态检查 | 无 ruff / eslint / CI |
| 生产服务器 | `app.run()` 开发服务器跑在"发布包"里 |

---

## 5. 施工清单（按 §9 的顺序做，不要跳）

### 阶段 0 · 建基线（15 分钟，必须先做）

仓库已有 git 历史，但你要确认工作区干净：

```bash
cd "C:/Users/22124/Desktop/发布包/九天梧桐AI工作台"
git status --short          # 有未提交改动先 commit 或 stash
git tag pre-delivery-$(date +%Y%m%d)   # 打标签，出事能回滚
```

**为什么不能跳**：`main.css` 是唯一视觉入口，没有回滚点，重构失败就全盘皆输。

---

### 阶段 1 · 修交付链（P0，预计半天）

#### P0-1 修 `$Root`

**文件**：`infra/scripts/setup_and_start.ps1:11`

```powershell
# 改前
$Root = Split-Path -Parent $PSScriptRoot          # → 得到 infra\
# 改后
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path   # → 得到项目根
```

改完必须验证**四个**派生路径同时正确：

| 变量 | 期望值 | 验证命令 |
|---|---|---|
| `$PyExe` | `<项目根>\infra\runtime\python\python.exe` | `Test-Path $PyExe` |
| `$AppDir` | `<项目根>\backend` | `Test-Path (Join-Path $AppDir "web.py")` |
| `$SqlDir` | `<项目根>\infra\sql` | `Test-Path (Join-Path $SqlDir "telecom_operations_db.sql")` |
| 第 67/71 行 `robocopy` 源 | `<项目根>\infra\mysql` | 目录存在 |

#### P0-2 修预检文案

同文件第 52 行 `"缺少 app\web.py"` → `"缺少 backend\web.py"`；第 54 行 `"缺少数据文件 data_sql\$f"` → `"缺少数据文件 infra\sql\$f"`。
**理由**：报错信息是给运维看的，写错路径等于把人往错方向指。

#### P0-3 给两个脚本的变量改名，消除歧义

- `setup_and_start.ps1`：`$Root` → `$ProjectRoot`（全文替换，7 处）
- `stop_all.ps1`：`$Root` → `$InfraRoot`（2 处），并在注释里写明"只用于匹配进程路径，不是项目根"

**验收**：双击 `启动.bat` → 看到 `[1/5] 发布包完整性检查通过` → 浏览器自动打开且能登录；双击 `停止.bat` → 后端与 MySQL 进程都消失（`Get-Process mysqld,python` 为空）。

---

### 阶段 2 · 设计系统收口（P2，预计一天）

#### 2.1 清掉重复的变量层

**只做一件事：合并成一套。** 目标状态 `main.css` 结构：

```
1. @layer 或分区注释：Tokens（:root + [data-theme="dark"]）
2. Reset / 基础排版
3. 布局骨架（app / side / main / header）
4. 组件（button / input / card / bubble / list / modal / toast）
5. 子组件兼容层（上传、预览、来源、审批既有 class）
6. 工具类（sr-only / ellipsis / scroll-thin）
```

删掉第 479–513 行那套"豆包风格"的重复定义，保留其**有效规则**并入统一变量层。判断"有效"的方法：`grep` 该变量在组件里的引用，有引用就必须保留语义。

#### 2.2 Token 规格（锁定，不要再选色）

```css
:root {
  /* 品牌主色：靛蓝，白底对比度 6.7:1（AA 通过） */
  --brand-50:#eef2ff; --brand-100:#e0e7ff; --brand-200:#c7d2fe;
  --brand-300:#a5b4fc; --brand-400:#818cf8; --brand-500:#4f63e8;
  --brand-600:#2f52e0;  /* ← 主色，唯一需要改的一个 */
  --brand-700:#2540b8; --brand-800:#1e3491; --brand-900:#1a2b73;

  /* 中性色：9 级灰阶，不要用纯黑纯白 */
  --ink-900:#0f1115; --ink-800:#1c1f26; --ink-700:#2b3038;
  --ink-600:#4a5058; --ink-500:#6b7280; --ink-400:#9aa1ab;
  --ink-300:#c9ced6; --ink-200:#e5e7eb; --ink-100:#f2f4f7; --ink-50:#f8fafc;

  /* 语义色 */
  --ok:#12a150; --warn:#e08b00; --danger:#d92d20; --info:#1570ef;

  /* 圆角：三档，不要出现第四种 */
  --r-sm:6px; --r-md:10px; --r-lg:16px; --r-full:999px;

  /* 阴影：三档，克制使用 */
  --sh-1:0 1px 2px rgba(16,24,40,.06);
  --sh-2:0 4px 12px rgba(16,24,40,.08);
  --sh-3:0 12px 32px rgba(16,24,40,.12);

  /* 间距：4 的倍数 */
  --s-1:4px; --s-2:8px; --s-3:12px; --s-4:16px;
  --s-5:20px; --s-6:24px; --s-8:32px; --s-10:40px;

  /* 字号：1.2 倍率 */
  --t-xs:12px; --t-sm:13px; --t-base:14px; --t-md:15px;
  --t-lg:17px; --t-xl:20px; --t-2xl:26px;

  /* 兼容层：值指向新 token，名字不变（铁律三） */
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

**注意**：`--accent` 必须保留这个名字（8 个子组件在用），只把它指向 `--brand-600`。

#### 2.3 布局规格

| 区域 | 规格 |
|---|---|
| 侧栏 | 宽 268px，可折叠到 0（`transform: translateX(-100%)`，不要 `display:none`，否则丢动画） |
| 顶栏 | 高 58px，`sticky top:0`，`backdrop-filter: blur(8px)`，底边 1px `--ink-200` |
| 内容区 | 最大宽 880px，居中，左右 `padding: 0 32px`；**滚动容器只有一个**（`.conv-list` 不设 `overflow`） |
| 输入区 | `sticky bottom:0`，上方渐隐遮罩 24px，容器最大宽同内容区 |
| 消息间距 | 同角色之间 12px，换角色 28px |
| 响应式 | `<900px` 侧栏改抽屉（遮罩 + 滑入）；`<640px` 内容 padding 降到 16px |

#### 2.4 助手消息去气泡（F20）

- 用户消息：右对齐、`--brand-600` 底、白字、`--r-lg`、最大宽 72%
- 助手消息：**无气泡**，左对齐、透明底、`--ink-900` 字，段落间距 `--s-4`，左侧 2px `--ink-200` 竖线作为视觉锚点（高度自适应）
- 原因：长文档在气泡里换行过窄，且截图时"一片色块"没有专业感

#### 2.5 空状态

不要"试试这样问"这种模仿别人的文案。改成**场景卡**（3 列，图标 + 标题 + 一句话 + 点击填充输入框）：

| 卡片 | 文案 | 填充的提示词 |
|---|---|---|
| 查业务数据 | 用自然语言问你的业务库 | `上个月各地区的销售额排名前 10` |
| 分析上传表格 | 拖入表格，直接问 | `这份表格里哪个品类的毛利率最低？` |
| 查制度文档 | 在知识库里找答案 | `出差住宿标准是多少？` |

---

### 阶段 3 · 修前端缺陷（P1，预计一天）

按此顺序做，每修完一组就跑构建 + 推送。

#### 3.1 B1 复制按钮（`MessageItem.vue`）

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

#### 3.2 B2 时间戳

后端 `to_plain_messages` 只返回 `{role, content}`，**没有时间戳**。所以：

- 历史消息**不显示时间**（诚实优于伪造）
- 只有本轮新消息显示 `formatTime(Date.now())`
- 若产品确需时间，那是**后端改造项**（给消息加 `created_at` 并迁移存量），不要在本次做

#### 3.3 F10 输入法（`Composer.vue`）

```js
function onKeydown(e) {
  if (e.key !== 'Enter' || e.shiftKey) return
  if (e.isComposing || e.keyCode === 229) return   // 中文输入法合成中
  e.preventDefault()
  send()
}
```

**验收**：拼音输入 `nihao` 后按回车选词，不发送；再按回车才发送。

#### 3.4 F12 XSS（`MarkdownView.vue`）

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

**验收**：让模型输出 `<img src=x onerror=alert(1)>`，页面只显示破图，不弹窗。

#### 3.5 F13 外链

渲染器里给 `a` 标签统一加 `target="_blank" rel="noopener noreferrer"`，且只允许 `http/https/mailto` 协议（`javascript:` 直接降级为文本）。

#### 3.6 F18 会话切换竞态（`stores/chat.js`）

```js
let runSeq = 0
async function sendQuestion(text) {
  const myRun = ++runSeq
  const threadAtSend = currentId.value
  // ...流式读取循环里：
  if (myRun !== runSeq || threadAtSend !== currentId.value) return  // 已切换，静默丢弃
}
```

`finally` 里**必须** `sending.value = false`，且只在 `myRun === runSeq` 时执行，避免旧轮次把新轮次的状态改掉。

#### 3.7 U1 替换 10 处 `alert/confirm`

新增两个组件 + 一个 composable：

- `components/ToastHost.vue` + `composables/useToast.js`：`toast.success/error/info(msg)`，右下角堆叠，3.5s 自动消失，可手动关
- `components/ConfirmHost.vue` + `composables/useConfirm.js`：`const ok = await confirm({title, text, okText, danger})`，返回 `Promise<boolean>`

规则：Esc = 取消，遮罩点击 = 取消，打开时焦点在"取消"按钮（防误操作），删除类操作按钮用 `--danger`。

**验收**：`grep -rn "alert(\|confirm(" frontend/src` 结果必须为 0。

#### 3.8 B3 / B4

- B3：`.side` 不设 `overflow`，只让 `.conv-list` 滚动；`min-height:0` 加在 flex 子项上
- B4：删除会话后若 `currentId` 指向已删项，自动切到下一条；没有下一条则新建空会话

---

### 阶段 4 · 功能补齐（P1，预计两天）

| 编号 | 功能 | 实现要点 | 验收 |
|---|---|---|---|
| **N1** | 消息操作条 | 复制 / **再答一次** / 赞 / 踩 | 四个按钮都有 hover 态；「再答一次」见下方说明 |
| **N2** | 导出对话 | 前端把当前会话拼成 Markdown，`Blob` + `a.download` 下载 | 文件名含会话标题与日期 |
| **N3** | 设置抽屉 | 主题（浅/深/跟随系统）、字号（小/标准/大 → 改 `--t-base`）、显示过程开关、快捷键说明、服务状态 | 三项偏好持久化到 localStorage，刷新后保持 |
| **N4** | 快捷键 | `Ctrl/Cmd+K` 搜索会话、`Ctrl/Cmd+/` 打开设置、`Esc` 关闭浮层、`Ctrl/Cmd+Enter` 发送 | 输入框聚焦时 `Ctrl+K` 不劫持 |
| **N5** | 侧栏会话搜索 | 前端本地过滤标题（无需后端接口） | 输入即筛，无结果有提示 |
| **N6** | 侧栏按日期分组 | 今天 / 昨天 / 近 7 天 / 更早 | 分组标题 sticky |
| **N7** | 错误气泡带 `error_id` | 后端 500 返回的 `error_id` 显示在气泡里 + 「复制错误 ID」按钮 | 用户能把它贴给运维 |
| **N8** | 排队提示 | 后端 `stream_ask` 用全局锁（见 §6.2），第二个请求会静默卡住 → 前端显示"正在回答上一条，已排队" | 双标签页并发时不再像死机 |

> **N1 的「再答一次」不能叫「重新生成」**：后端每轮都会追加历史，叫"重新生成"会让用户以为历史被替换。这是诚实性要求，不是措辞偏好。

---

### 阶段 5 · 企业级能力（P2，预计两天，按租户价值排序）

| 编号 | 能力 | 为什么值钱 | 施工要点 |
|---|---|---|---|
| **E1** | 多租户品牌化 | 同一套代码卖多家，只换主色与 Logo | 新建 `frontend/src/brand.js` 导出 `{name, logo, primary}`；`theme.js` 用 `primary` 推导 50–900 色阶 → 写入 CSS 变量；构建期可改，运行期支持 `window.__JTW_BRAND__` 覆盖（运维不用重新构建） |
| **E2** | 审计日志 | 金融/医疗租户合规刚需 | 记录"谁在什么时候问了什么、调了哪些工具、看了哪些表"；`backend/services/ops/audit.py` + 表格展示；**不含答案全文**（体积与隐私） |
| **E3** | 会话归属与隔离 | 多人共用一台机器时不串数据 | `conversations.json` 增加 `owner_id`；列表接口按当前用户过滤；管理员可看全部 |
| **E4** | 首启动引导 | 交付体验 | 首次登录走 3 步向导：配置模型 Key → 测试连库 → 导入知识库；每步可跳过 |
| **E5** | 模型切换可见 | 信任感 | 顶栏显示当前模型徽章，点击可切（`/api/models` 已存在） |

**E1 的关键约束**：租户只提供一个色值，**不许让实施人员改 20 个变量**。推导函数必须保证深色模式下对比度仍达 AA。

---

### 阶段 6 · 工程化（P3，预计一天，可与阶段 5 并行）

| 项 | 做法 | 验收 |
|---|---|---|
| 测试可收集 | 5 个 `_test_*.py` 改名为 `test_*.py`；加 `backend/pytest.ini` 设 `testpaths=eval/tests` | `pytest --collect-only` 能看到全部用例 |
| 冒烟四条 | ① `/api/health` 返回 200 ② 完整一轮 chat 有 NDJSON 输出 ③ 上传后 preview 可取 ④ `_validate_readonly` 拒绝 `DROP TABLE` | 四条全绿才算过 |
| 日志 | 新建 `backend/core/logging_setup.py`：控制台 + 轮转文件 `logs/app.log`（10MB×5）；`ERROR` 带 `error_id` 关联 | `print` 只保留在 CLI 入口 |
| 异常 | `except Exception:` 全部改为 `except Exception as e: logger.exception(...)`；确属可忽略的加注释说明为什么 | 数量从 95 降到"有注释的少数" |
| 依赖锁 | `pip freeze > backend/requirements.lock.txt`；`rapidocr-onnxruntime` 拆成 optional | 新机器 `pip install -r requirements.lock.txt` 可复现 |
| 静态检查 | 后端加 `ruff`（`select=E,F,I`），前端加 `eslint` + `prettier` | 提交前能跑，不要求 0 warning，但新增代码必须干净 |
| 生产服务器 | `waitress-serve --port=5000 web:app`；`app.run` 仅开发用 | 发布包内不再出现 Werkzeug dev server 警告 |

---

## 6. 后端注意事项（本次不改架构，但要知道）

### 6.1 全局可变状态有三套并存

- `_ROUND_SOURCES`（模块级 list + 锁）
- `_LAST_QUERY_CTX`（contextvar）
- `set_current_thread`（全局）

**本期不重构**，但你要知道：任何"给所有请求加一层上下文"的想法都会踩到这里，先改成统一 `ContextVar` 再说。

### 6.2 整个服务是"单飞"的

`ChatService.stream_ask` / `stream_deep` 用 `with self._lock:` **把整个流式回合包住**，锁持有到最后一个 token。第二个用户/标签页会静默卡住。

**本期决策**：保持单用户桌面形态（这是产品定位），但必须：
1. 在 `README.md` 明确写"同一时刻仅支持一轮问答"
2. 前端加排队提示（N8）

若要改成多用户，那是**独立项目**：把本轮上下文从全局态改为请求态，锁只保护 checkpointer 落盘那几行。

### 6.3 不允许在本次做的事

- 拆 `core/agent.py`（4664 行）——收益大但风险高，单独排期
- 换 Web 框架
- 引入消息队列 / Celery
- 重写沙箱

---

## 7. 视觉质量的具体判据（避免"AI 味"）

租户判断"好不好看"只看几秒，这几个细节决定成败：

| 判据 | 错误做法 | 正确做法 |
|---|---|---|
| 渐变 | 到处用蓝紫渐变当装饰 | **不用装饰性渐变**；只有品牌 Logo 允许 1 处渐变 |
| 阴影 | 每个卡片都带大阴影 | 只有浮层（抽屉/弹窗/Toast）用 `--sh-3`，卡片用 `--sh-1` 或不用 |
| 圆角 | 8px/12px/14px/16px 混用 | 只有 `--r-sm/md/lg/full` 四档 |
| 边框 | 灰边框 + 阴影同时上 | 二选一：有阴影不加边框，有边框不加阴影 |
| 图标 | 混用 emoji、SVG、字体图标 | **统一 SVG**（stroke 1.5px，24×24，`currentColor`） |
| 空状态 | "试试这样问"式模仿 | 场景卡，写给"这个行业的用户"看 |
| 加载 | 转圈 spinner 转三秒 | **骨架屏**（消息区 3 行灰条）+ 首字到达即替换 |
| 文案 | "智能助手为您服务" | 说人话："上个月销售额环比降了 8%，主要来自华东" |
| 对比度 | 浅灰字 `#999` on 白 | 正文 `--ink-900`，辅助 `--ink-500`（4.5:1 以上） |
| 动效 | 什么都在动 | 只给"出现/消失"加 150–200ms `ease-out`；不做弹跳 |

---

## 8. 可访问性与性能（不许牺牲）

- 所有可点元素有 `:focus-visible` 描边（2px `--brand-600`，offset 2px）
- 图标按钮必须有 `aria-label`
- 模态：`role="dialog"` + `aria-modal` + 焦点陷阱 + Esc 关闭
- 流式输出的 `aria-live` **不能挂在整段文本上**（会把整段反复朗读），只用一个 `sr-only` 状态节点，在"开始/结束/出错"三个时刻更新
- 长列表：`content-visibility: auto` + `contain-intrinsic-size`（不要引入虚拟滚动库）
- 首屏体积：`dist` 主包 gzip 后 < 300KB（当前若超，按路由/组件动态 import 拆分，但不要引 router）

---

## 9. 施工顺序（严格按此，每阶段结束必须可交付）

```
阶段0 建基线 ──→ 阶段1 交付链 ──→ 【门禁1：双击启动能跑】
                                        ↓
                                  阶段2 设计系统 ──→ 阶段3 缺陷修复 ──→ 【门禁2：构建通过 + 10 个 bug 清零】
                                                                              ↓
                                                                        阶段4 功能补齐 ──→ 阶段5 企业级 ──→ 【门禁3：验收清单全过】
                                                                                                                  ↓
                                                                                                            阶段6 工程化 ──→ 推送
```

**每个门禁的硬标准**

| 门禁 | 必须满足 | 不满足怎么办 |
|---|---|---|
| 门禁1 | 双击 `启动.bat` → MySQL 起 → 后端起 → 浏览器打开可登录 | 停下来修，不要继续做前端 |
| 门禁2 | `npm run build` 通过；`grep alert/confirm` 为 0；B1/B2/F10/F12/F13/F18/B3/B4 全部可复现验证 | 停下来修 |
| 门禁3 | §10 清单全勾选 | 停下来修 |

**每完成一个阶段**：`git push origin main`。**不要攒到最后一起推**。

---

## 10. 验收清单（逐条勾选，交付时贴出来）

### 交付链路

- [ ] 双击 `启动.bat`：`[1/5] 发布包完整性检查通过` → 自动打开浏览器 → 能登录
- [ ] 双击 `停止.bat`：`mysqld` 与 `python` 进程都消失
- [ ] 预检失败时的提示文案路径正确（无 `app\` / `data_sql\` 残留）
- [ ] 全新机器（无 `runtime`、无 `mysql`）能走完自动下载安装

### 界面

- [ ] 1440×900 与 1920×1080 下布局无横向滚动条、无元素重叠
- [ ] 浅色/深色切换后所有文字可读（对比度 ≥ 4.5:1）
- [ ] 侧栏折叠动画流畅，折叠后内容区自适应
- [ ] 只有一套设计系统：`grep -c "accent:" main.css` 语义上只有一处定义源
- [ ] 空状态是三张场景卡，点击能填充输入框
- [ ] 消息区骨架屏在首字到达前显示，到达后无跳动
- [ ] 长答案（>2000 字）滚动流畅，无卡顿

### 功能

- [ ] 中文输入法回车选词不误发送
- [ ] 多条消息时点复制，改的是**这一条**，图标不消失
- [ ] 刷新后历史消息不显示伪造时间
- [ ] 模型输出 `<img onerror>` 不执行脚本
- [ ] 点外部链接新开标签页，原会话不丢
- [ ] 生成中切会话，回来时输入框可用（不卡 `sending`）
- [ ] 删除当前会话后自动切到下一条
- [ ] `grep -rn "alert(\|confirm(" frontend/src` 为 0
- [ ] 「再答一次」按钮存在且行为正确（追加而非替换）
- [ ] 导出对话得到可读的 `.md` 文件
- [ ] 设置里改主题/字号，刷新后保持

### 安全与数据

- [ ] `git ls-tree -r --name-only origin/main | grep -E "\.env$|\.sqlite3|conversations\.json|\.sql$|自动学习/.+\.md$"` 无输出
- [ ] 10 个数据目录的 `README.md` 都在仓库里
- [ ] 磁盘上所有代码文件都在索引中（无遗漏）
- [ ] 未登录访问 `/api/chat` 返回 401
- [ ] 普通用户（role=1）访问 `/api/auth/users` 返回 403

### 工程

- [ ] `pytest --collect-only` 能收集到用例
- [ ] 四条冒烟测试全绿
- [ ] `logs/app.log` 有轮转，500 错误带 `error_id`

---

## 11. 自检命令（每次推送前跑，30 秒）

```bash
cd "C:/Users/22124/Desktop/发布包/九天梧桐AI工作台"

# ① 构建
(cd frontend && npm run build) || exit 1

# ② 隐私：不能有输出
git diff --cached --name-only | grep -E "\.env$|\.sqlite3|conversations\.json|\.sql$|自动学习/问答记录|node_modules|\.pdf$" || echo "PASS-隐私"

# ③ 密钥：不能有输出
git grep --cached -n -E "sk-[A-Za-z0-9_-]{16,}|BEGIN (RSA|OPENSSH) PRIVATE KEY" || echo "PASS-密钥"

# ④ 原生弹窗：结果必须为 0
grep -rn "alert(\|confirm(" frontend/src | wc -l

# ⑤ 体量基线：约 134 文件 / 2.3MB
git ls-files | wc -l
git ls-files -z | du -ch --files0-from=- 2>/dev/null | tail -1
```

---

## 12. 明确不做（防止过度改造）

| 不做 | 原因 |
|---|---|
| 换 UI 框架 | 会生成第三套设计系统，与 8 个子组件 class 全面冲突 |
| 引入 Vue Router | 现有 `useNav` 够用，加 router 要改所有跳转 |
| 引入虚拟滚动库 | `content-visibility` 已够用 |
| 拆 `agent.py` | 独立任务，风险与收益不匹配本次交付 |
| 重写上传/预览/来源/审批组件 | 功能正常，只跟随新 token 变色 |
| 引入 i18n | 单语言交付 |
| 加 PWA / 离线缓存 | 本地服务形态下无意义，且缓存妨碍版本更新 |
| 用 `git add -f` 绕过忽略 | 会泄露企业数据 |
| 给历史消息伪造时间戳 | 后端没这数据，伪造比不显示更糟 |
| 把「再答一次」写成「重新生成」 | 后端每轮追加历史，措辞会误导 |

---

## 13. 汇报格式（每阶段结束时给我）

```
## 阶段 N 完成

改了什么（按文件）
- frontend/src/components/Composer.vue：加 isComposing 判断（F10）
- ...

怎么验证的
- 手动：输入 nihao 回车选词 → 未发送 ✓
- 命令：grep alert → 0

遗留 / 需要决策
- B2 若要显示时间，需后端加 created_at（约 20 行 + 数据迁移），做不做？

已推送
- commit abc1234 → 9sky/main
```

**如果你不确定某件事该不该做，不要猜，把它列在"需要决策"里问我。**
**如果你发现本文档与代码不一致，以代码为准，并在文档对应处追加"实测修正"批注，不要静默改。**

---

## 14. 最后：三条最容易翻车的地方

1. **`main.css` 是唯一视觉入口，动它之前必须打标签**。1231 行里有一半是死代码，删错一处会让某个子组件样式塌陷，而你不会立刻发现（因为那个组件要特定操作才显示）。
2. **改 `.gitignore` 之后必须验证**。Git 的"父目录排除后无法重新纳入"这条规则，已经让 4 份 README 静默丢失过一次。改完用 `git check-ignore -v <路径>` 逐个确认。
3. **「看起来变好了」不等于「没坏」**。每改一个组件，都要走一遍它的原始路径：上传文件 → 预览 → 问表格 → 看来源 → 触发审批。这些子组件不改造，但它们共享同一套 token。

祝顺利。交付的标准不是"我改完了"，是"租户第一眼就想用"。
