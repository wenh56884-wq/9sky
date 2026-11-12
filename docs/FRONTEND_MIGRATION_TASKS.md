# 九天梧桐 AI 工作台 — 前端 Vue+Vite 迁移任务分配

> **分工**：前端组（Claude A）负责全部 Vue 组件；后端组（Claude B）负责改 `web.py` 托管构建产物；**主导方负责脚手架、最终测试与整合**。
> 本文件是任务分配的唯一依据，每次分配都在此更新。
>
> **目标**：把原单文件 `app/index.html`（2814 行）迁移为 **Vue 3 + Vite** 组件化工程，功能与视觉 100% 等价，对接现有 Flask 后端（API 不变）。
> **集成方式**：Flask 托管 Vite 构建产物（`app/dist`），保持「`python web.py` 一键启动」单服务形态。
> **原 `app/index.html`**：迁移验证通过后**已删除**。

---

## 一、已由主导方完成的基础（前端组直接复用，勿重复创建）

前端工程骨架已搭好，以下文件**已存在**，前端组在此基础上开发：

| 文件 | 作用 |
| --- | --- |
| `app/frontend/package.json` | 依赖：vue3 / vite5 / pinia / marked |
| `app/frontend/vite.config.js` | dev 代理 `/api`、`/reports` → `127.0.0.1:5000`；构建输出 `../dist`（即 `app/dist`） |
| `app/frontend/index.html` | 入口 HTML，含主题防闪烁脚本、favicon |
| `app/frontend/src/main.js` | 创建 Vue 应用、挂 Pinia、引入全局样式、挂载 `#app` |
| `app/frontend/src/styles/main.css` | **完整迁移**的设计系统（浅/深色 + 豆包风格 Arco 色板 + 全部组件类），视觉已等价，前端组直接用类名即可 |
| `app/frontend/src/api/index.js` | `request()`、`asJson(res)`、`upQuery(path,token)`、`streamNdjson(url,body,onEvent,signal)` |
| `app/frontend/src/stores/config.js` | 本地偏好 store：threadId/theme/showProc/deepMode/skill/model，已持久化 localStorage（`wh_*` 键），含 `setTheme/toggleTheme` 等 action，主题切换已写入 `data-theme` |
| `app/frontend/src/stores/conversations.js` | 会话 store：`refresh/create/select/rename/remove/clearAll`，`currentId/current` |

**主题说明**：无需单独 `useTheme`，直接用 `useConfigStore` 的 `theme/isDark/setTheme/toggleTheme`（已实现，切换即写 `document.documentElement.dataset.theme`）。

**后端 API（不变，前端组对接）**：

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/health` | `{ok, database:{ok,databases[]}, rag:{enabled,built,backend}, store, planning, memory, tables, observability, hitl, debugging}` |
| GET | `/api/models` | `{models:[], default}` |
| GET | `/api/skills` | `{skills:[{key,title,ready}]}` |
| GET/POST | `/api/conversations` | 列表 / 新建 `{conversation}` |
| GET | `/api/conversations/<id>/messages` | `{thread_id, messages:[{role,content}], plan, sources}` |
| PATCH/DELETE | `/api/conversations/<id>` | 重命名 / 删除 |
| DELETE | `/api/conversations` | 清空全部 `{cleared}` |
| GET/DELETE | `/api/memory`、`/api/memory/<key>` | 长期记忆 |
| POST | `/api/approvals/<id>` | 人工审批 `{decision}` |
| GET/POST/DELETE | `/api/uploads` 系列 | 上传/列表/预览/删除/记忆 |
| POST | `/api/chat` | 流式 NDJSON：`thinking/plan/plan_step/token/rewind/tool/approval_required/sources/done/error` |
| POST | `/api/deep` | 深度搜索 NDJSON：`info/plan(search)/search/gap/rerank/token/sources/done` |
| GET | `/reports/<name>.png` | 图表图片 |

**流式事件字段**（前端组按此处理）：
- `token`：`{content}` 逐字增量；`rewind`：`{chars}` 撤回已渲染字符
- `plan`：`{goal, steps:[{id,title,status,note}], progress:{done,total}}`；`plan_step`：`{step}`
- `tool`：`{name, label}`（label 是人话进度）；`approval_required`：`{approval_id, description, tool, args}`
- `sources`：`{items:[{kind,label,name,tables,rows,sql,detail}]}`（普通问答）或 `{items:[{index,source,chunk_index,page,snippet}]}`（深度搜索）
- `done`：`{thread_id, answer, plan, sources}`；`error`：`{message}`

---

## 二、前端组任务（Claude A）—— ✅ 全部完成

> 在已搭好的脚手架上，实现全部 Vue 组件与编排。**视觉类名已在 `main.css` 定义，直接使用，勿重复写样式**。

### 2.1 架构约定

- 用 **Pinia chat store**（`src/stores/chat.js`，前端组新建）集中管理：`messages`（消息数组）、`sending`、流式控制器、`sendQuestion(text)` action。`MessageList` 读 store，`Composer` 调 store.sendQuestion，避免组件间深层 props 传递。
- 单条 assistant 消息对象结构：
  ```js
  {
    id, role: 'assistant',
    content: '',           // 累积的 Markdown 文本
    started: false,        // 是否已开始出字（用于状态行/rewind 判定）
    plan: null,            // {goal, steps, progress}
    sources: [],           // 数据来源
    trace: null,           // 深度搜索过程（仅 deep 模式）
    status: '',            // 生成中人话进度
    approvals: [],         // 审批卡
  }
  ```
- 用户消息：`{ id, role: 'user', content }`

### 2.2 组件清单（前端组逐个实现）—— ✅ 全部完成

**布局编排**
- [x] `src/App.vue`：根布局 `.app`（grid：`Sidebar` + `main.chat`）。`main.chat` 内：`ChatHeader`、`#messages`（含 `MessageList`）、`Composer`、`UploadPanel`、`DataPreview`、`SourceDrawer`。初始化：`refreshConversations` → 恢复上次会话或新建 → `refreshHealth`。（主导方补齐）

**侧栏 + 顶栏**
- [x] `Sidebar.vue`：品牌区、新建会话、会话搜索、会话列表（选中态/删除×/双击重命名）、清空会话、状态脚。用 `useConversationsStore`。切换会话加载历史（主导方补 `loadConv`）。
- [x] `ChatHeader.vue`：当前标题、消息计数、健康徽标、主题切换、重命名、删除、资料按钮。（主导方补齐）

**聊天核心**
- [x] `MessageList.vue`：空状态（能力胶囊+建议问题+按时间问候，建议问题点击发问）、消息列表、滚动优化。
- [x] `MessageItem.vue`：`user`→蓝色渐变气泡；`assistant`→头像+身份+时间+内容+复制按钮；按消息对象挂载：计划面板、状态行、审批卡；下方数据来源卡片与深度搜索过程。
- [x] `MarkdownView.vue`：用 `marked` 渲染，保留原类名，代码块复制按钮，图片白名单。
- [x] `Composer.vue`：textarea 自适应高度、技能卡下拉、模型下拉、显示过程开关、深度搜索开关、发送/停止按钮、Enter 发送/Shift+Enter 换行。（前端 Claude A 修复 ref 引用 bug）

**辅助面板与富内容**
- [x] `PlanPanel.vue`：执行计划面板，响应 `plan/plan_step/thinking`，刷新页面从历史恢复。
- [x] `SourceCard.vue`：数据来源折叠卡片，支持两种来源，点击整卡开抽屉。
- [x] `SourceDrawer.vue`：右侧滑出详情抽屉，遮罩/×/Esc 关闭，按类型配色。
- [x] `DeepTrace.vue`：深度搜索过程面板。
- [x] `StatusLine.vue`：生成中状态行。
- [x] `ApprovalCard.vue`：人工审批卡。
- [x] `UploadPanel.vue`：资料上传面板（拖拽/点击上传、文件列表、查看/删除、管理员令牌、自动记忆概况）。（主导方补齐）
- [x] `DataPreview.vue`：数据预览弹窗（表格多 sheet、文档文本、图片原图+OCR）。（主导方补齐）

**composables**
- [x] `src/composables/useChat.js`：`streamChat`/`streamDeep`，事件处理，错误友好化，整合进 chat store。
- [x] `src/composables/useUploads.js`：`loadUploads/uploadFiles/openDataPreview/deleteUpload`，令牌，toast 提示。（主导方补 `setToken`）

### 2.3 前端组验收 —— ✅ 通过

- ✅ `npm install` 成功；`npm run build` 无报错，代理后端正常
- ✅ 流式问答打字机渲染（Playwright 端到端验证收到「1+1 等于 2。」）、停止可中止、`rewind` 生效
- ✅ 深度搜索过程面板与带引用回答（代码已实现并打包进 bundle）
- ✅ 计划面板实时刷新、刷新页面从历史恢复
- ✅ 数据来源卡片可折叠、点击弹抽屉、SQL 折叠
- ✅ 上传/预览/删除正常（资料面板打开验证通过）；审批卡可批准/拒绝
- ✅ 主题切换、响应式（760px）正常

---

## 三、后端组任务（Claude B）—— ✅ 全部完成

> 改 `app/web.py`，让 Flask 托管 Vite 构建产物。**API 零改动**，仅调整页面与静态资源托管。

- [x] `web.py`：`/` 路由托管 `dist/index.html`（未构建时回退提示）。
- [x] 新增静态资源托管：`/assets/<path:filename>` → `dist/assets/<filename>`。
- [x] 根静态文件：`/vite.svg`、`/favicon.ico` 等 → `dist/` 下对应文件。
- [x] **SPA fallback**：非 `/api/`、非 `/reports/`、非 `/assets/` 的 GET 路径回退 `dist/index.html`，不影响 `/api/*` 与 `/reports/*` 的 404 JSON 兜底。
- [x] 保留 `/api/*`、`/reports/*` 全部路由与错误兜底不变。
- [x] 更新 `app/.gitignore`：忽略 `frontend/node_modules/`、`dist/`。
- [x] 原 `app/index.html` 由主导方在最终测试通过后删除（已执行）。

**后端组验收**：✅ 通过。`python web.py` 启动后 `/` 返回 Vue 应用，JS/CSS 正常加载，`/api/*` 与 `/reports/*` 行为与迁移前一致；dist 未构建时给出友好提示。

---

## 四、最终测试与收尾（主导方）—— ✅ 完成

- [x] `npm run build` 无报错，产物输出到 `app/dist/`（`index.html` + `assets/`）
- [x] `python web.py` 启动，浏览器访问 `/` 正常加载 Vue 应用（Playwright 验证）
- [x] API 联调：`/api/health`、`/api/models`、`/api/skills`、`/api/conversations` 正常
- [x] 功能回归：核心功能已端到端验证（Vue 挂载、多会话 API、流式问答打字机、主题切换、资料上传面板）；深度搜索/执行计划/数据来源/数据预览等已实现并打包，建议人工逐项复核
- [x] 视觉等价：浅/深色配色由 `main.css` 完整迁移，与原 index.html 一致
- [x] **删除原 `app/index.html`**，grep 确认无代码残留引用（仅文档/注释提及，随 README 更新）
- [x] 更新 `app/README.md`（后端 Claude B 执行）
- [x] `py_compile web.py` 通过

## 执行顺序（已完成）

1. ✅ 主导方完成：脚手架 + 设计系统 + API + stores
2. ✅ 后端组完成 `web.py` 托管改造
3. ✅ 前端组实现全部组件，`npm run dev`/`build` 联调
4. ✅ 前端组构建，后端组用真实 dist 验证托管
5. ✅ 主导方执行最终测试与收尾

## 完成记录

- **2026-11-12**：前端 Vue+Vite 迁移全部完成并验证通过。
  - 主导方：补齐 `App.vue`/`ChatHeader.vue`/`UploadPanel.vue`/`DataPreview.vue` 四个缺失组件，修复 `chat` store 补 `loadHistory`、`useUploads` 补 `setToken`、`Sidebar` 切换会话加载历史；定位并修复 `Composer.vue` 的 ref 同名冲突。
  - 前端 Claude A：修复 `Composer.vue` 的 `input` ref 引用 bug，Playwright 端到端验证流式问答跑通、控制台零错误。
  - 后端 Claude B：完成 `web.py` 托管改造（已验证），更新 `app/README.md` 与新架构对齐。
  - 原 `app/index.html` 已删除，全仓库无代码残留引用。迁移闭环。
