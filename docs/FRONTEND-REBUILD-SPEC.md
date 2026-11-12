# 九天梧桐 AI 工作台 · 前端重建施工规格（唯一真相源）

> 版本：v1.0 ｜ 撰写基准：2026-11-12 的代码快照 ｜ 适用对象：执行改造的 AI / 工程师
> 本文是**施工图**，不是设计评论。按 §13 的顺序执行，每一步都能独立 `npm run build` 通过。
> 与本文冲突的旧文档（`docs/FRONTEND-DESIGN.md`）一律作废，以本文为准。

---

## 0. 这份文档怎么用

### 0.1 给执行者的元指令

1. **只改本文 §8 列出的文件**。§4 列出的契约一个字都不能动。
2. 每完成一个小节就 `cd frontend && npm run build`，**构建失败立即停下修**，不要继续往下写。
3. 不要"顺手优化"未被点名的文件。不要升级依赖版本（除本文明确要求新增的 1 个包）。
4. 不要引入 UI 框架（Element / Arco / Ant Design / Tailwind）。全部手写 CSS，原因是：现有样式已按类名深度耦合，引入框架会产生第三套设计系统——这正是当前问题本身。
5. 遇到本文没写到的细节，选择**更少动、更保守**的做法，并在代码注释里写 `// SPEC §x.y 未覆盖`。

### 0.2 三条铁律

| 铁律 | 说明 |
|---|---|
| **不重命名已有 CSS 变量** | 只重设它们的值。`--accent`、`--panel`、`--line` 等被 8 个子组件引用，改名必然漏改导致样式塌陷。新变量用新名字（`--brand-600`、`--space-4`）。 |
| **不重命名已有 class** | `data-src`、`ds-item`、`up-panel`、`src-drawer` 等类名被未改造的子组件直接使用。新组件用新类名。 |
| **不动后端** | 本文所有改动纯前端。需要后端新能力的地方（§9 中标 🔶）**一期不做**，只用前端方案替代，并在代码里写明。 |

---

### 0.3 开工前的仓库前置校验（**必做，不通过不许动手**）

本文所有路径都以**四域结构**为准：`backend/` `frontend/` `infra/` `docs/`。
远程仓库 `https://github.com/wenh56884-wq/bigdata` 的 `main` 分支是 **2026-09-28 的旧版扁平结构**（`core/` `services/` `web.py` `index.html`），与本文不兼容。

执行前必须确认：

```bash
# 1. 确认在正确的工作目录（含四域结构）
test -f frontend/src/components/MessageItem.vue && test -f backend/core/agent.py \
  && echo "OK: 四域结构" || echo "STOP: 目录不对，去 docs/§15.2 取 v2 分支"

# 2. 确认分支（若是 clone 下来的仓库）
git branch --show-current          # 期望 v2；若是 main，说明是旧快照

# 3. 确认基线与本文一致
wc -l frontend/src/styles/main.css  # 期望 991（改动前基线）
wc -l frontend/src/components/MessageItem.vue  # 期望 93
```

三条任一不符 → **停止执行**，回到 §15.2 取正确快照。在旧结构上照本文施工，会出现"照着文档改，文件根本不存在"的连锁错误。

---

## 1. 已锁定的三个决策

上一版留了三个待定项，本次直接定死。理由一并写出，避免执行者再纠结。

| 决策 | 锁定值 | 理由 |
|---|---|---|
| 主色 | **`#2F52E0` 靛蓝**（单色，不用渐变） | 与白底对比度 6.7:1，达 WCAG AA；比 `#165dff` 更沉稳，适合政企/医疗类租户；单色便于租户换色（只换一个色值即可推导整条色阶，见 §11）。渐变只保留给 Logo 图形。 |
| 助手消息形态 | **去掉气泡，改为文档流**（无底色、无边框，仅顶部 meta 行） | 长答案在气泡里换行窄、截图花。文档流是 Claude / ChatGPT 现行做法，也是"专业工具"的视觉信号。用户消息保留实色气泡做左右区分。 |
| 移动端 | **PC 优先，移动端做"可用降级"**（侧栏改抽屉 + 顶栏汉堡），不做像素级适配 | 交付形态是 Windows 桌面发布包（`启动.bat` 拉起本地服务），手机访问是边缘场景。省下的工时投到会话管理与错误恢复上。 |

---

## 2. 现状事实清单（带行号，供执行者核对）

| 编号 | 事实 | 证据位置 |
|---|---|---|
| F1 | `main.css` 里存在**两套完整的设计系统**：第一套 7–79 行（靛紫渐变），第二套 461–524 行（注释写"豆包风格 · Arco 色板"） | `frontend/src/styles/main.css:7` / `:461` |
| F2 | `--accent` 被定义两次（`#5b6cff` → 后被 `#165dff` 覆盖），第一套的 526 行之前规则**全部失效** | `main.css:8`、`:462` |
| F3 | 526–990 行是第二套的覆盖层，用后置声明硬压前一套，文件顺序即优先级 | `main.css:526-990` |
| F4 | 复制按钮用全局选择器找 DOM，且用 `textContent` 覆盖，会把 SVG 图标永久抹掉 | `MessageItem.vue:24-28`、`:69-72` |
| F5 | 时间戳在组件挂载时 `new Date()`，**所有历史消息显示同一时刻** | `MessageItem.vue:14-19` |
| F6 | 后端历史消息只返回 `{role, content}`，**没有时间戳字段** | `backend/core/agent.py:2951-2971`（`to_plain_messages`） |
| F7 | 后端只保存"最近一轮"的 plan 与 sources，但前端把它们塞给了**每一条**历史 assistant 消息 | `backend/web.py:129-140`；`stores/chat.js:43-49` |
| F8 | `error` 事件带 `error_id`，前端丢弃了它，用户截图报障时无任何可追溯信息 | `backend/web.py:316-330`（事件说明）；`composables/useChat.js:109-118` |
| F9 | 9 处原生 `alert`/`confirm`，与商业产品观感冲突，且 `confirm` 阻塞渲染线程 | `Sidebar.vue:43,50,63,65,71,73,85`；`ChatHeader.vue:38`；`useUploads.js:87` |
| F10 | 输入框回车发送**未判断输入法合成状态**（`isComposing`），中文用户按回车选词会误发送 | `Composer.vue:31-36` |
| F11 | `#messages` 上有 `aria-live="polite"`，流式输出时屏幕阅读器会逐字朗读 | `MessageList.vue:74` |
| F12 | `marked` 渲染结果直接 `v-html`，**未做 HTML 净化**，模型输出或检索到的文档含脚本即可执行 | `MarkdownView.vue:41-47`、`:80` |
| F13 | 外部链接未加 `target`，点击后整页跳走，SPA 状态全丢 | `MarkdownView.vue:18-39`（未配置 link 渲染） |
| F14 | 消息列表用 `deep: true` 监听整个数组，**每个 token 触发一次全量 diff** | `MessageList.vue:59-66` |
| F15 | 技能卡 / 模型下拉靠命令式 `appendChild` / `innerHTML` 填充，与 Vue 响应式脱钩 | `Composer.vue:51-90` |
| F16 | 侧栏 `.side` 与 `.conv-list` 同时 `overflow-y:auto`，双滚动容器 | `main.css:99`、`:120` |
| F17 | 切换会话时先 `clearMessages()` 再异步拉取，期间闪现空状态；拉取失败则永久空白 | `Sidebar.vue:26-30` |
| F18 | 生成中切换会话：流继续写入已卸载的消息对象，`sending` 卡在 `true`，新会话输入框一直禁用 | `stores/chat.js:80-119` |
| F19 | 品牌标识为圆形渐变 + 蓝紫气泡 + "试试这样问"，与通用 AI 助手高度雷同，租户无法替换 | `index.html` favicon；`MessageList.vue:34-39`；`main.css:691-694` |
| F20 | 无"再答一次 / 导出对话 / 反馈 / 设置 / 快捷键"能力 | 全局缺失 |

---

## 3. 目标形态

一句话：**从"能对话的页面"变成"能卖的工作台"**。四个可见变化：

1. 左侧是可管理的会话空间（分组、搜索、折叠、悬停操作），不是一列标题。
2. 中间是文档流阅读区（820px 行宽、清晰层级、可复制、可再答、可导出）。
3. 底部是完整工具条（附件、技能卡、模型、深度搜索、过程开关、发送/停止）。
4. 右上角有设置入口（主题、字号、动效、默认行为、服务状态），全站零原生弹窗。

---

## 4. 不可破坏的契约（改错即故障）

### 4.1 流式事件名（后端 → 前端）

`/api/chat`：`thinking` `plan` `plan_step` `tool` `approval_required` `rewind` `token` `sources` `done` `error`
`/api/deep`：`info` `plan` `search` `gap` `rerank` `token` `sources` `done` `error`
处理位置：`composables/useChat.js` 的 `applyChatEvent` / `applyDeepEvent`。
**允许新增字段读取（如 `error_id`），禁止改名、禁止删除已处理的 case。**

### 4.2 HTTP 接口（不得新增、不得改 method）

```
GET    /api/health
GET    /api/models
GET    /api/skills
GET    /api/conversations
POST   /api/conversations
GET    /api/conversations/<id>/messages   → { thread_id, messages[{role,content}], plan, sources }
PATCH  /api/conversations/<id>
DELETE /api/conversations/<id>
DELETE /api/conversations
POST   /api/chat   (NDJSON)
POST   /api/deep   (NDJSON)
GET/POST/DELETE /api/uploads...
POST   /api/approvals/<id>
GET    /api/memory, DELETE /api/memory/<key>
```

> **关于 `/api/auth/*`**：`OPTIMIZATION_TASKS.md` §4.1 规划了 8 个认证接口，前端 `api/auth.js` / `stores/auth.js` 与后端 `services/ops/auth.py` / `auth_store.py` 都已存在，但 **`backend/web.py` 至今没有挂载任何 `/api/auth/*` 路由**（实测 grep 为空）——属于"服务层写好、出口没接"的并行开发中间态。本规格**不实现鉴权**，边界见 §4.6。

### 4.3 localStorage 键（用户已有偏好，改了等于清空用户设置）
`wh_thread_id` `wh_theme` `wh_show_process` `wh_deep_mode` `wh_db_skill` `wh_model`
新增键统一 `wh_` 前缀：`wh_font_scale` `wh_reduce_motion` `wh_sidebar_collapsed` `wh_feedback`

### 4.4 Pinia store 对外签名（组件依赖）

```
conversations: list, currentId, current, loading, renamingId
               refresh(), create(), select(id,{silent})→data, rename(id,title), remove(id),
               startRename(id), cancelRename(), clearAll()
chat:          messages, sending, isEmpty, lastMessage
               setMessages(list,plan,sources), loadHistory(data), loadConversation(id),
               clearMessages(), addUserMessage(t), addAssistantMessage(), sendQuestion(t), stop()
config:        threadId, theme, isDark, showProc, deepMode, skill, model
               setThreadId/setTheme/toggleTheme/setShowProc/setDeepMode/setSkill/setModel
```
**可以新增 action，不能改已有 action 的参数顺序与返回值语义**（`useChat.js` 依赖 `sendQuestion` 内部流程）。

### 4.5 必须保留的 class（被未改造的子组件使用）

```
上传面板   up-mask up-panel open up-head up-close up-body up-drop up-drop-in up-token
          up-list up-item up-meta up-name up-sub up-actions up-view up-del up-empty up-mem up-toast
资料预览   data-preview data-preview-mask show data-preview-head data-preview-title data-preview-close
          data-preview-info data-preview-tabs data-preview-tab active data-preview-content
          data-preview-note data-table-wrap data-table data-preview-text data-preview-section
          data-preview-image data-preview-empty
来源抽屉   src-drawer-mask src-drawer open sd-head sd-title sd-close sd-body sd-sec sd-label
          sd-kv sd-chips sd-chip sd-text sd-sql
来源卡片   data-src folded ds-head ds-head-icon ds-count ds-caret ds-list ds-item ds-badge
          ds-main ds-name ds-sub ds-body ds-chip ds-pill ds-note ds-sql ds-more
          k-database k-tables k-knowledge k-forecast k-chart
过程面板   plan-panel plan-head plan-title plan-goal plan-progress plan-steps plan-step
          ps-icon ps-title ps-note st-pending st-doing st-done st-failed st-skipped plan-thinking
          deep-trace dt-head dt-chip dt-row hit deep-err ai-status pulse
审批卡     approval-card approval-actions approve approval-result
散件       tbl-wrap codeblock cb-head cb-lang copy-code md-img markdown-view
```

---

### 4.6 鉴权：并行开工中，本规格的边界

**实测现状（2026-11-12 17:05）**

| 位置 | 状态 |
|---|---|
| `backend/services/ops/auth.py`（131 行） | 已存在 |
| `backend/services/ops/auth_store.py`（242 行） | 已存在 |
| `backend/web.py` 的 `/api/auth/*` 路由 | **不存在**（有服务层、无出口） |
| `frontend/src/api/auth.js`（58 行） | 已存在，客户端契约已写全 |
| `frontend/src/stores/auth.js`（139 行） | 已存在 |
| `frontend/src/composables/useNav.js`（20 行） | 已存在 |
| `frontend/src/api/index.js` | 已被并行方修改（含令牌注入） |

角色模型见 `OPTIMIZATION_TASKS.md`：0 访客 / 1 普通用户 / 2 管理员 / 3 超管。

**五条边界（违反会造成两套登录逻辑打架）**

1. 本规格只负责**登录后的工作台界面**。登录页、用户管理页、权限按钮显隐，均不在本文范围。
2. **禁止删除或改写** `api/auth.js`、`stores/auth.js`、`useNav.js`、`services/ops/auth*.py`——属并行工作流。
3. `api/index.js` 是唯一交叉点：本文只允许在其中补 `asJson` / `streamNdjson` 的 401 文案，**不得移除已有的 Bearer 注入**。动它之前先完整读一遍当前内容（它已被改过，本文写作时的版本已过期）。
4. 若并行方先合入，`App.vue` 可能已被包一层登录判定。此时 §8.4 的 `.app` 结构应作为**"登录后组件"**嵌入，不要把 `.app` 写成根节点唯一形态。
5. 设置抽屉里若出现"退出登录"，必须调用 `stores/auth` 现成的 `logout()`，不要自建登出逻辑。

---

## 5. 设计系统 v2（唯一一套）

### 5.1 Token 总则

- **一处定义**：整份 `main.css` 只允许存在 **1 个 `:root`** 和 **1 个 `:root[data-theme="dark"]`**。
- **旧变量改值不改名**：`--bg --panel --panel-2 --ink --muted --muted-2 --line --line-2 --accent --accent-2 --grad --grad-soft --bubble-user --bubble-user-text --ai-card --code-bg --code-text --th-bg --chip-hover --shadow-sm --shadow-md --shadow-lg --ok --err --ring --scrollbar --ds-*` 全部保留，只换值。
- **新增变量**：`--brand-50..900`、`--surface-3`、`--ink-3`、`--ink-4`、`--space-1..10`、`--radius-xs..full`、`--z-*`、`--dur-*`、`--ease`、`--font-sans`、`--font-mono`。

### 5.2 Token 全文（直接复制，不要改写数值）

```css
:root {
  /* ===== 品牌色阶（租户换色只改 --brand-600，其余由 §11.2 的 JS 推导） ===== */
  --brand-50:  #EFF3FF;
  --brand-100: #DEE7FF;
  --brand-200: #C3D2FF;
  --brand-300: #9CB2FF;
  --brand-400: #6D8DF7;
  --brand-500: #4A6CF0;
  --brand-600: #2F52E0;   /* 主色：按钮 / 链接 / 选中态 */
  --brand-700: #2440B8;
  --brand-800: #1D3391;
  --brand-900: #182A73;

  /* ===== 中性色（浅色主题） ===== */
  --bg:        #F5F6FA;   /* 应用画布 */
  --sidebar:   #FAFBFD;
  --surface:   #FFFFFF;
  --surface-2: #F0F2F7;
  --surface-3: #E9ECF3;
  --ink:       #12141A;
  --ink-2:     #3A4050;
  --ink-3:     #616879;
  --ink-4:     #8B92A3;
  --line:      #E4E7EF;
  --line-2:    #D2D7E3;

  /* ===== 旧变量别名（必须保留，供既有选择器与子组件使用） ===== */
  --panel: var(--surface);
  --panel-2: var(--surface-2);
  --muted: var(--ink-3);
  --muted-2: var(--ink-4);
  --accent: var(--brand-600);
  --accent-2: var(--brand-500);
  --accent-weak: var(--brand-50);
  --hover: var(--surface-2);
  --grad: linear-gradient(140deg, var(--brand-500) 0%, var(--brand-700) 100%);
  --grad-soft: linear-gradient(140deg, var(--brand-50) 0%, #F4F1FF 100%);
  --bubble-user: var(--brand-600);
  --bubble-user-text: #FFFFFF;
  --ai-card: transparent;
  --chip-hover: var(--brand-50);
  --th-bg: var(--surface-2);

  /* ===== 代码块（深底恒定，不随主题反转） ===== */
  --code-bg: #12141C;
  --code-text: #E7EAF3;

  /* ===== 语义色 ===== */
  --ok: #12A150;
  --warn: #D97706;
  --err: #DC2B2B;
  --ok-bg: #E8F7EF;
  --warn-bg: #FDF3E7;
  --err-bg: #FDECEC;

  /* ===== 阴影（一律低对比、大扩散，禁用硬投影） ===== */
  --shadow-sm: 0 1px 2px rgba(16,20,32,.06), 0 1px 3px rgba(16,20,32,.04);
  --shadow-md: 0 8px 24px -8px rgba(16,20,32,.14);
  --shadow-lg: 0 24px 56px -20px rgba(16,20,32,.22);
  --ring: 0 0 0 3px rgba(47,82,224,.16);
  --scrollbar: rgba(18,20,26,.18);

  /* ===== 数据来源配色（子组件按 k-* 取用，保留变量名） ===== */
  --ds-db: #2F52E0;    --ds-db-bg: #EFF3FF;
  --ds-tab: #0E8074;   --ds-tab-bg: #E6F6F3;
  --ds-kb: #7A3FD8;    --ds-kb-bg: #F3EDFE;
  --ds-ml: #B45309;    --ds-ml-bg: #FDF3E7;
  --ds-chart: #0F8A5F; --ds-chart-bg: #E8F7EF;

  /* ===== 字号 / 字距 / 行高 ===== */
  --font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC",
               "Hiragino Sans GB", "Microsoft YaHei", "Noto Sans SC", sans-serif;
  --font-mono: "SFMono-Regular", "Cascadia Mono", Consolas, "Liberation Mono", monospace;
  --text-2xs: 11px;
  --text-xs:  12px;
  --text-sm:  13px;
  --text-md:  14px;
  --text-lg:  15px;
  --text-xl:  18px;
  --text-2xl: 22px;
  --text-3xl: 28px;

  /* ===== 间距（4 的倍数，不得出现 7px / 13px 这类手工值） ===== */
  --space-1: 4px;  --space-2: 8px;  --space-3: 12px; --space-4: 16px;
  --space-5: 20px; --space-6: 24px; --space-7: 32px; --space-8: 40px;
  --space-9: 48px; --space-10: 64px;

  /* ===== 圆角 ===== */
  --radius-xs: 6px; --radius-sm: 8px; --radius-md: 12px;
  --radius-lg: 16px; --radius-xl: 20px; --radius-full: 999px;

  /* ===== 动效 ===== */
  --dur-fast: 120ms; --dur-base: 180ms; --dur-slow: 260ms;
  --ease: cubic-bezier(.2,.7,.3,1);

  /* ===== 层级（全站唯一来源，禁止随手写 z-index） ===== */
  --z-content: 0; --z-header: 10; --z-composer: 20; --z-fab: 30;
  --z-drawer-mask: 100; --z-drawer: 110; --z-modal-mask: 200; --z-modal: 210;
  --z-toast: 300; --z-tooltip: 400;
}

:root[data-theme="dark"] {
  --brand-50:  #1A2140;
  --brand-100: #1E2A55;
  --brand-200: #26376F;
  --brand-300: #3550A0;
  --brand-400: #5C7BEE;
  --brand-500: #7C93FF;
  --brand-600: #7C93FF;   /* 暗色下主色提亮，保证在深底上可读 */
  --brand-700: #9AABFF;
  --brand-800: #B9C4FF;
  --brand-900: #D6DDFF;

  --bg:        #0C0E13;
  --sidebar:   #10131A;
  --surface:   #14171F;
  --surface-2: #1B1F29;
  --surface-3: #232835;
  --ink:       #F1F4FA;
  --ink-2:     #C7CCD9;
  --ink-3:     #9299AA;
  --ink-4:     #6B7284;
  --line:      #232833;
  --line-2:    #313848;

  --accent: var(--brand-600);
  --accent-2: var(--brand-500);
  --accent-weak: rgba(124,147,255,.14);
  --grad-soft: linear-gradient(140deg, rgba(124,147,255,.16) 0%, rgba(160,123,255,.12) 100%);
  --bubble-user: #2B49C4;
  --ai-card: transparent;
  --chip-hover: rgba(124,147,255,.12);
  --th-bg: var(--surface-2);
  --code-bg: #0A0C11;
  --code-text: #DFE4F0;

  --ok: #34D399; --warn: #FBBF24; --err: #F87171;
  --ok-bg: rgba(52,211,153,.14);
  --warn-bg: rgba(251,191,36,.14);
  --err-bg: rgba(248,113,113,.14);

  --shadow-sm: 0 1px 2px rgba(0,0,0,.5);
  --shadow-md: 0 8px 24px -8px rgba(0,0,0,.6);
  --shadow-lg: 0 24px 56px -20px rgba(0,0,0,.7);
  --ring: 0 0 0 3px rgba(124,147,255,.28);
  --scrollbar: rgba(255,255,255,.16);

  --ds-db: #93A7FF;    --ds-db-bg: rgba(147,167,255,.16);
  --ds-tab: #45D6C4;   --ds-tab-bg: rgba(69,214,196,.14);
  --ds-kb: #B79BFA;    --ds-kb-bg: rgba(183,155,250,.16);
  --ds-ml: #F5B851;    --ds-ml-bg: rgba(245,184,81,.14);
  --ds-chart: #4ADE9B; --ds-chart-bg: rgba(74,222,155,.14);
}
```

> ⚠️ `--ai-card: transparent` 是因为助手消息改为文档流（无卡片）。`PlanPanel` / `DeepTrace` / `SourceCard` 有自己的底色，不受影响。

### 5.3 标度使用规则

| 场景 | 取值 |
|---|---|
| 正文 | `--text-lg`(15px) / `line-height: 1.75` |
| 长文档段落 | 15px / 1.8，段间距 12px |
| UI 文本（按钮、标签） | `--text-sm`(13px) / 500 |
| 辅助信息（时间、计数） | `--text-xs`(12px) / `--ink-4` |
| 页面标题 | `--text-2xl`(22px) / 600 / -0.01em |
| 字重上限 | **600**（中文 700 会糊，禁止使用） |
| 按钮高度 | 主按钮 36px，工具条按钮 30px，图标按钮 32×32 |
| 卡片内边距 | 16px；面板 12–14px；消息区行宽 820px |

### 5.4 对比度自检（WCAG AA）

| 前景 / 背景 | 比值 | 结论 |
|---|---|---|
| `#12141A` / `#FFFFFF` | 18.9:1 | ✅ |
| `#616879` / `#FFFFFF` | 5.5:1 | ✅ 正文辅助 |
| `#8B92A3` / `#FFFFFF` | 3.4:1 | ⚠️ 仅限占位符/禁用态 |
| `#FFFFFF` / `#2F52E0` | 6.7:1 | ✅ 按钮文字、用户气泡 |
| `#F1F4FA` / `#14171F` | 14.8:1 | ✅ 暗色正文 |
| `#9299AA` / `#14171F` | 6.1:1 | ✅ 暗色辅助 |

**红线**：任何新增文字组合，正文低于 4.5:1、图标/大字低于 3:1 一律重选色。

---

## 6. CSS 重建规格

### 6.1 执行方式

**一次性重写 `frontend/src/styles/main.css`**，不要"在末尾追加覆盖层"——那正是 F1/F3 的病根。重写后文件结构固定为：

```
§1  tokens            ← §5.2 全文，唯一 :root
§2  reset / base      ← box-sizing、滚动条、focus-visible、selection、::placeholder
§3  layout            ← .app / .chat / 尺寸变量
§4  sidebar           ← .side .brand .new-chat .conv-search .conv-* .side-foot
§5  header            ← .chat-head .head-btn .icon-btn .badge-btn
§6  messages          ← #messages .msgs-inner .msg .user-bubble .ai-box .ai-card .ai-content .typing
§7  markdown          ← .md-* .tbl-wrap .codeblock .cb-* .copy-code
§8  process panels    ← .plan-panel .deep-trace .ai-status .approval-card（保留原类名与结构）
§9  sources           ← .data-src .ds-* .src-drawer .sd-*
§10 composer          ← .composer .composer-inner #question .composer-bar .skill-select .send .stop
§11 overlays          ← .up-* .data-preview-*（照抄现有效果，仅替换变量）
§12 new: toast/confirm/settings/shortcuts/menu/skeleton/fab
§13 responsive        ← 900px / 640px 两档
§14 reduced-motion
```

### 6.2 每个选择器的必守规则（节选关键项）

| 选择器 | 必须满足 |
|---|---|
| `.app` | `grid-template-columns: 264px 1fr`；折叠态 `64px 1fr`；`height:100dvh`；`overflow:hidden` |
| `.side` | `overflow: hidden`（**只允许 `.conv-list` 滚动**，修 F16）；`display:flex; flex-direction:column; min-height:0` |
| `.conv-list` | `flex:1; min-height:0; overflow-y:auto; overflow-x:hidden` |
| `.conv` | 高度 34px；`border-radius:8px`；hover 显隐 `.conv-actions`（`opacity` 切换，不用 `visibility` 以免占位跳动） |
| `.new-chat` | 36px 高；实色 `--brand-600`；hover 加深 6%（`filter: brightness(.96)`，**不用更亮的渐变**） |
| `.chat-head` | 56px；`position:sticky; top:0`；`backdrop-filter: blur(12px)` + 90% 透明底；边框仅下边 1px |
| `#messages` | `flex:1; min-height:0; overflow-y:auto; overscroll-behavior:contain`；`scroll-behavior:smooth` 仅在非 reduced-motion 下启用 |
| `.msgs-inner` | `max-width: 820px; margin:0 auto; padding: 24px 24px 32px` |
| `.msg` | `margin-bottom: 28px`；`content-visibility:auto; contain-intrinsic-size: 0 120px`（长会话性能，见 §12.3） |
| `.msg.user` | `justify-content:flex-end` |
| `.user-bubble` | `max-width:min(78%, 560px)`；`background:var(--bubble-user)`；`border-radius:14px 14px 4px 14px`；**无阴影** |
| `.ai-box` | `max-width: calc(100% - 44px)`；`padding-top:0` |
| `.ai-card` | `background:transparent; border:0; padding:0; box-shadow:none; border-radius:0` |
| `.ai-content` | `font-size:15px; line-height:1.78`；首尾段落 `margin:0` 修正保留 |
| `.composer-inner` | `border-radius:14px`；`box-shadow: var(--shadow-md)`；focus-within 用 `--ring` |
| `.send` | 32×32 圆形；实色 `--brand-600`；disabled 用 `--surface-3` + `--ink-4` |
| `.stop` | 与 `.send` 同尺寸同位，`display:none` / `.show{display:grid}` |
| `.src-drawer` / `.up-panel` | 宽度 420 / 400；`z-index: var(--z-drawer)`；遮罩 `var(--z-drawer-mask)` |
| `.data-preview-mask` | `z-index: var(--z-modal-mask)`；卡片 `var(--z-modal)` |

### 6.3 禁止项（出现即返工）

```css
/* 禁止 */ 第二个 :root                            /* 禁止 */ !important（除 reduced-motion）
/* 禁止 */ 渐变按钮 / 渐变气泡（Logo 除外）        /* 禁止 */ 多重阴影堆叠"玻璃拟态"
/* 禁止 */ 手写 z-index 数字（必须用 --z-*）        /* 禁止 */ 颜色字面量（必须走变量）
/* 禁止 */ font-weight: 700+（中文）               /* 禁止 */ .side 与 .conv-list 同时可滚
```

允许例外：Markdown 内部元素（`blockquote`/`table`）、代码块配色、`prefers-reduced-motion` 块可以使用字面量。

---

## 7. 布局与层级

```
┌──────────────┬──────────────────────────────────────────────┐
│ Sidebar 264  │ Header 56（sticky，模糊底）                    │
│ (折叠 64)    ├──────────────────────────────────────────────┤
│              │ Messages  820px 居中，可滚动                    │
│  brand       │   ├ 空状态（无消息）                           │
│  new-chat    │   └ 消息流                                     │
│  search      │                                              │
│  分组列表     ├──────────────────────────────────────────────┤
│              │ Composer 820px 居中（sticky bottom，渐变遮罩）  │
│  footer      │                                              │
└──────────────┴──────────────────────────────────────────────┘
```

**层级表**（必须与 `--z-*` 一致）：内容 0 < 顶栏 10 < 输入区 20 < 回到底部按钮 30 < 抽屉 100/110 < 模态 200/210 < Toast 300 < Tooltip 400。

**断点**：`>900px` 双栏；`≤900px` 侧栏转抽屉（`position:fixed; transform:translateX(-100%)`，`.open` 归位），header 出现汉堡按钮；`≤640px` 消息区内边距 16px、输入区工具条换行、隐藏次要文案。

---

## 8. 逐文件改造规格

> 顺序即施工顺序。每个文件改完先 `npm run build`。

### 8.1 新增 `frontend/src/brand.js`（先做，后面组件都引用它）

```js
// 租户品牌配置：构建期默认值 + 运行期 window.__JTW_BRAND__ 覆盖
// 运维改品牌不必重新构建：在 dist/index.html 的 <head> 里注入
// <script>window.__JTW_BRAND__={tenantName:'XX医院',mark:'X',accent:'#0E8074'}</script>
const DEFAULTS = {
  tenantName: '九天梧桐',
  productName: 'AI 工作台',
  mark: '梧',
  tagline: '业务数据 · 知识库 · 预测',
  accent: '#2F52E0',
  version: '2.0.0',
  support: '',
  examples: [
    { text: '医疗库 2025 年每月总收入趋势', tip: '自然语言直接查三个业务库' },
    { text: '预测医疗库未来 6 个月的收入并生成报告', tip: 'Sklearn 月度预测 + Markdown 报告' },
    { text: '三个数据库分别预测并生成预测报告', tip: '一键跑全部库默认指标' },
    { text: '记住：我喜欢简洁的回答', tip: '跨会话长期记忆，新会话也生效' },
  ],
  capabilities: [
    { icon: 'database', label: '数据库直查' },
    { icon: 'search', label: '知识库问答' },
    { icon: 'chart', label: '机器学习预测' },
    { icon: 'brain', label: '跨会话记忆' },
  ],
}
export const brand = { ...DEFAULTS, ...(window.__JTW_BRAND__ || {}) }
export function fullName() { return brand.tenantName + ' ' + brand.productName }
```

### 8.2 新增 `frontend/src/styles/theme.js`（品牌色 → 整条色阶）

```js
// 只给一个主色，推导 50..900；不依赖 color-mix，浏览器兼容性最好
function hexToRgb(hex) {
  const h = hex.replace('#', '').trim()
  const s = h.length === 3 ? h.split('').map((c) => c + c).join('') : h
  const n = parseInt(s, 16)
  return { r: (n >> 16) & 255, g: (n >> 8) & 255, b: n & 255 }
}
const mix = (c, target, w) => Math.round(c + (target - c) * w)
function scale(hex) {
  const { r, g, b } = hexToRgb(hex)
  const toWhite = (w) => `rgb(${mix(r,255,w)}, ${mix(g,255,w)}, ${mix(b,255,w)})`
  const toBlack = (w) => `rgb(${mix(r,0,w)}, ${mix(g,0,w)}, ${mix(b,0,w)})`
  return {
    50: toWhite(0.94), 100: toWhite(0.88), 200: toWhite(0.74), 300: toWhite(0.54),
    400: toWhite(0.28), 500: toWhite(0.10), 600: hex,
    700: toBlack(0.16), 800: toBlack(0.30), 900: toBlack(0.44),
  }
}
export function applyBrandColor(hex) {
  if (!/^#([0-9a-f]{3}|[0-9a-f]{6})$/i.test(hex || '')) return
  const s = scale(hex)
  const root = document.documentElement
  Object.entries(s).forEach(([k, v]) => root.style.setProperty('--brand-' + k, v))
}
```
调用点：`main.js` 里 `applyBrandColor(brand.accent)`，**必须在挂载前**执行，避免首屏闪色。

### 8.3 `frontend/src/main.js`

```js
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import './styles/main.css'
import { brand } from './brand'
import { applyBrandColor } from './styles/theme'

applyBrandColor(brand.accent)
document.title = brand.tenantName + ' ' + brand.productName
createApp(App).use(createPinia()).mount('#app')
```

### 8.4 `frontend/src/App.vue`

结构改为（新增 4 个全局层，全部挂载在 `.app` 之后，避免被 grid 影响）：

```vue
<template>
  <div class="app" :class="{ 'side-collapsed': config.sidebarCollapsed }">
    <Sidebar />
    <main class="chat">
      <ChatHeader />
      <MessageList />
      <Composer />
      <UploadPanel />
      <DataPreview />
      <SourceDrawer />
    </main>
    <SettingsDrawer />
    <ShortcutHelp />
    <ConfirmHost />
    <ToastHost />
  </div>
</template>
```
`onMounted` 逻辑保持不变（恢复上次会话），仅在 `catch` 中 `toast.error('会话加载失败，请检查后端服务')`，禁止静默失败。

### 8.5 `frontend/src/components/Sidebar.vue`（重写）

**结构**：`brand 行（logo + 名称 + 折叠按钮）` → `new-chat` → `search（含 ⌘K 提示）` → `分组列表` → `footer（状态 + 设置 + 版本）`。

**要点**
1. 分组：按 `updated_at` 分「今天 / 昨天 / 近 7 天 / 更早」，组长是小号大写标签（`--text-2xs` + `--ink-4` + `letter-spacing:.08em`），空组不渲染。
   ```js
   function bucketOf(ts) {
     const d = new Date(ts || 0), now = new Date()
     const day = 86400000
     const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime()
     if (d.getTime() >= startOfToday) return '今天'
     if (d.getTime() >= startOfToday - day) return '昨天'
     if (d.getTime() >= startOfToday - 7 * day) return '近 7 天'
     return '更早'
   }
   ```
   > `updated_at` 的格式必须先看 `backend/data/conversations.json` 实际值（`_now()` 产出）。若不是可被 `new Date()` 解析的 ISO 串，退化为不分组、只显示单列表——**不允许猜**。
2. 会话行 hover 显示两个图标按钮：重命名（铅笔）、删除（垃圾桶），用 `opacity` 过渡。删除按钮走 `confirmDialog`，不用 `confirm()`。
3. 删除后修正 `config.threadId`：`conv.remove(id)` 后若 `conv.list.length` 则 `config.setThreadId(conv.list[0].id)` 并载入，否则新建（修 P0 遗留：`Sidebar.remove` 未回写 threadId）。
4. 折叠态：`.side-collapsed` 时隐藏文字、只剩图标，按钮加 `title`；状态存 `wh_sidebar_collapsed`。
5. footer 三点：状态圆点 + 文案（点击刷新 `/api/health`）、设置齿轮（打开 SettingsDrawer）、`v{{brand.version}}`。

### 8.6 `frontend/src/components/ChatHeader.vue`（重写）

| 区域 | 内容 |
|---|---|
| 左 | 移动端汉堡；会话标题（`max-width: 46ch` 省略号）；`· N 条消息` |
| 中右 | 模型徽章（`config.model` 短名，如 `deepseek-chat` → `DeepSeek`）；健康徽章（点击刷新，dot 颜色 `--ok` / `--err`） |
| 右 | 导出按钮（下拉：复制全文 / 导出 Markdown）；主题切换；更多菜单（重命名 / 删除会话 / 资料上传 / 设置） |

**必须**：所有下拉用自建 `.menu`（`position:absolute; z-index: var(--z-header)`），点击外部关闭（`document.addEventListener('pointerdown')` + `closest('.menu-root')` 判定），Esc 关闭。

### 8.7 `frontend/src/components/MessageList.vue`（重写）

1. **滚动修复（F14）**：删掉 `deep: true` 的全量监听，改为两条轻量 watch：
   ```js
   watch(() => chat.messages.length, () => scrollBottom(true), { flush: 'post' })
   watch(() => {
     const last = chat.messages[chat.messages.length - 1]
     return last ? last.content.length : 0
   }, () => scrollBottom(false), { flush: 'post' })
   ```
2. **回到底部**：`userScrolledUp` 为真时显示 FAB（`.scroll-fab`，36×36 圆形，`--z-fab`），点击 `el.scrollTop = el.scrollHeight`；流式期间有新内容时 FAB 上显示小圆点。
3. **加载骨架**：新增 `chat.loadingHistory`（store 新增 state，`loadHistory` 前后置位）。为真时渲染 3 条 `.skeleton-msg`（灰块 + shimmer），替代当前的空状态闪现（F17）。
4. **空状态**：hero（logo + 问候语）+ 4 个能力胶囊 + 4 张示例卡（2×2 网格，来自 `brand.examples`）。文案去掉"试试这样问"，改为"从一个真实问题开始"。
5. **无会话**：`conv.list` 为空且非 loading 时，渲染"还没有会话"卡片 + 主按钮"新建对话"。
6. 移除 `aria-live="polite"`（F11），改为 `<div class="sr-only" role="status" aria-live="polite">{{ liveStatus }}</div>`，只在"开始生成 / 生成结束 / 出错"三个时刻更新文案。
7. 绑定重试：`<MessageItem v-for="m in chat.messages" :key="m.id" :message="m" @retry="chat.retry" />`。

### 8.8 `frontend/src/components/MessageItem.vue`（重写）

**模板骨架**

```vue
<!-- 用户消息 -->
<div class="msg user" :class="{ editing }">
  <div class="bubble-wrap">
    <div v-if="!editing" class="user-bubble">{{ message.content }}</div>
    <textarea v-else v-model="draft" class="edit-box" rows="3"
              @keydown.esc="cancelEdit" @keydown.meta.enter="submitEdit"
              @keydown.ctrl.enter="submitEdit"></textarea>
    <div class="bubble-actions">
      <button class="mini-btn" @click="copy(message.content)">复制</button>
      <button class="mini-btn" @click="startEdit">编辑</button>
    </div>
  </div>
</div>

<!-- 助手消息 -->
<div class="msg assistant">
  <div class="ai-box">
    <div class="role">
      <span class="avatar-sm">{{ brand.mark }}</span>
      <span class="who">{{ brand.tenantName }}</span>
      <span v-if="message.time" class="time">{{ message.time }}</span>
    </div>
    <PlanPanel v-if="message.plan" :plan="message.plan" />
    <StatusLine v-if="message.status" :status="message.status" />
    <ApprovalCard v-for="a in message.approvals" :key="a.approval_id" :approval="a" />
    <DeepTrace v-if="message.trace" :trace="message.trace" />
    <div class="ai-card">
      <div v-if="message.typing && !message.content" class="ai-content">
        <span class="typing"><i></i><i></i><i></i></span>
      </div>
      <template v-else>
        <MarkdownView :content="message.content" />
        <div v-if="message.errorId" class="err-block">
          <div class="err-title">这一次没跑完</div>
          <div class="err-msg">{{ message.errorText }}</div>
          <div class="err-meta">错误编号 <code>{{ message.errorId }}</code>（报障时请提供）</div>
          <div class="err-actions">
            <button class="mini-btn" @click="copyError">复制错误信息</button>
            <button class="mini-btn" @click="$emit('retry', message)">重试</button>
          </div>
        </div>
      </template>
      <div class="msg-actions">
        <button class="mini-btn" @click="copy(message.content)">{{ copied ? '已复制' : '复制' }}</button>
        <button class="mini-btn" @click="$emit('retry', message)">再答一次</button>
        <button class="mini-btn" @click="copyForTicket">复制反馈</button>
      </div>
    </div>
    <SourceCard v-if="!message.trace && message.sources && message.sources.length" :items="message.sources" />
    <!-- 深度来源块保持原结构不变 -->
  </div>
</div>
```

**必须修的三处**

0. **引入品牌**：`import { brand } from '../brand'`（模板里用到 `brand.mark` / `brand.tenantName`）；`defineEmits(['retry'])`。
1. **复制（F4）**：`copied` 用 `ref(false)` + 组件内 `setTimeout`，按钮文案由数据驱动，**不再 `querySelector`，不再改 `textContent`**，SVG 不会被抹掉；`onBeforeUnmount` 清定时器。
2. **时间（F5）**：删除 `const time = ref(clock())`。改为 `message.time` 字段：发送时写入 `HH:mm`，历史消息（`setMessages` 构造）`time: ''`，模板 `v-if="message.time"` 不渲染（F6：后端无时间戳，**禁止伪造**）。
3. **错误块（F8）**：`message.errorId` / `message.errorText` 由 `useChat.js` 写入；`copyError` 复制 `问题 + 回答 + 错误编号`。

**新增 emit**：`retry`（由 `MessageList` 转给 `chat.retry(message)`）。

### 8.9 `frontend/src/components/Composer.vue`（重写）

**必须修**

1. **输入法（F10）**：
   ```js
   function onKeydown(e) {
     if (e.key !== 'Enter' || e.shiftKey) return
     if (e.isComposing || e.keyCode === 229) return   // 中文输入法选词状态，放行
     e.preventDefault()
     if (canSend.value) submit()
   }
   ```
2. **下拉改响应式（F15）**：`const skills = ref([])` / `const models = ref([])`，模板 `<option v-for>`，删除 `appendChild` / `innerHTML`。
3. **发送前无会话自愈**：`canSend` 不再要求 `conv.currentId`；`submit()` 里若 `!conv.currentId` 先 `await conv.create()`。避免"首屏新建失败 → 输入框永久禁用"的死局。

**工具条布局**：`[＋附件] [技能卡] [模型] [深度搜索] [显示过程] ...... [字数] [发送/停止]`
- 附件按钮 → 打开 `UploadPanel`（复用 `useUploads().openPanel`）。
- 字数：`text.length > 800` 时显示 `N / 4000`，超 4000 禁用发送并提示。
- `placeholder` 随状态变：无会话 `开始提问…`；深度搜索 `描述你要研究的问题…`；默认 `给{{brand.tenantName}}发送消息…（Enter 发送，Shift+Enter 换行）`。
- 底部一行 `.composer-foot`：`--text-2xs` / `--ink-4`，左侧显示当前模式（`深度搜索 · 3 轮检索` / `技能卡：医疗库` / `自动识别`），右侧 `Enter 发送 · Shift+Enter 换行`。

### 8.10 `frontend/src/components/MarkdownView.vue`（小改，2 处）

1. **安全（F12）**：新增依赖 `dompurify`（`npm i dompurify@^3`），
   ```js
   import DOMPurify from 'dompurify'
   const html = computed(() => {
     if (!props.content) return ''
     let out = marked.parse(props.content)
     out = out.replace(/<table>/g, '<div class="tbl-wrap"><table>')
              .replace(/<\/table>/g, '</table></div>')
     return DOMPurify.sanitize(out, { ADD_ATTR: ['target', 'rel'] })
   })
   ```
   > 若执行环境无法安装依赖（离线），降级方案：在 `marked.use({ renderer: { html: ({ text }) => escapeHtml(text) } })` 中禁用原始 HTML。**二者必选其一，不允许裸 `v-html`。**
2. **外链（F13）**：`renderer.link` 补 `target="_blank" rel="noopener noreferrer"`。
   ```js
   link({ href, title, tokens }) {
     const text = this.parser.parseInline(tokens)
     const t = title ? ` title="${escapeHtml(title)}"` : ''
     return `<a href="${escapeHtml(href || '#')}"${t} target="_blank" rel="noopener noreferrer">${text}</a>`
   }
   ```

### 8.11 `frontend/src/stores/chat.js`（改 5 处）

1. **骨架字段**：`assistantSkeleton()` 增加 `time: nowHHmm()`、`errorId: ''`、`errorText: ''`；`addUserMessage` 也写 `time`。
2. **历史 plan/sources 只挂最后一条（F7）**：
   ```js
   setMessages(list, plan, sources) {
     const arr = (list || []).map((m) => m.role === 'assistant'
       ? { ...assistantSkeleton(), id: nextId(), content: m.content || '', started: !!m.content,
           typing: false, time: '', plan: null, sources: [] }
       : { id: nextId(), role: 'user', content: m.content || '', time: '' })
     const lastAi = [...arr].reverse().find((m) => m.role === 'assistant')
     if (lastAi) { lastAi.plan = plan || null; lastAi.sources = sources || [] }
     this.messages = arr
   }
   ```
3. **切会话即中止（F18）**：新增 `abortForSwitch()`，`Sidebar.loadConv` 与 `Header.remove` 在切换前调用；`sending` 归位，并 `toast.info('已停止上一个会话的生成')`。
4. **新增 `retry(message)` / `regenerate()`**：
   ```js
   // 一期语义：把上一条用户提问作为新的一轮重新发送（后端无"截断历史"接口）
   async retry(message) {
     const idx = this.messages.indexOf(message)
     if (idx < 1) return
     const prevUser = [...this.messages.slice(0, idx)].reverse().find((m) => m.role === 'user')
     if (!prevUser) return
     this.messages.splice(idx, 1)          // 只移除界面上的失败气泡，不动后端历史
     await this.sendQuestion(prevUser.content, { silentUser: true })
   }
   ```
   `sendQuestion(text, opts)` 新增第二参数 `{ silentUser }`：为真时不再 `addUserMessage`。
   > **文案必须叫"再答一次"，不能叫"重新生成"**——后端每轮都会追加历史，叫"重新生成"会让用户以为历史被替换。这是诚实性要求。

5. **新增 `loadingHistory`**：`state` 增加 `loadingHistory: false`；`loadHistory(data)` 与 `loadConversation(id)` 在请求前后 `true / false`（`finally` 复位）。供 `MessageList` 渲染骨架屏，替代切换会话时的空状态闪现（F17）。

### 8.12 `frontend/src/composables/useChat.js`（改 2 处）

1. 两个 catch 分支与 `final.type === 'error'` 分支，统一写：`message.errorId = final.error_id || ''`、`message.errorText = detail`，并把原 blockquote 里的技术细节改为短句（错误块已单独承载 detail）。
2. `tool` 事件的 `showProc` 分支维持现状；`status` 文案中文化保持。

### 8.13 `frontend/src/stores/config.js`（新增 5 项）

`sidebarCollapsed`、`fontScale`（`'compact' | 'standard' | 'large'` → 根字号 14/15/16）、`reduceMotion`、`feedbackMode`、`defaultDeep`。全部持久化，键名见 §4.3。
`fontScale` 应用方式：`document.documentElement.style.setProperty('--text-lg', '16px')` 一类，**不要用 `zoom` 或 `transform: scale`**（会破坏滚动与定位）。

### 8.14 新增 6 个组件

| 文件 | 职责 | 关键实现 |
|---|---|---|
| `components/ToastHost.vue` | 顶部居中轻提示 | `composables/useToast.js` 导出模块级 `reactive([])`；`push({type,text,ms=2600})`；`<TransitionGroup name="toast">`；`--z-toast`；最多同时 3 条，超出丢弃最旧 |
| `components/ConfirmHost.vue` | 替代 `confirm()` | `const { confirmDialog } = useConfirm()`；**函数名必须叫 `confirmDialog`**（不叫 `confirm`，避免遮蔽全局）；签名 `confirmDialog({ title, text, okText='确定', danger=false }) → Promise<boolean>`；遮罩点击 = false；Esc = false；打开时 focus 到取消按钮 |
| `components/SettingsDrawer.vue` | 设置 | 右侧 380px 抽屉。分组：外观（主题三选：浅色/深色/跟随系统、字号三档、减少动效）/ 对话（默认深度搜索、默认显示过程、默认技能卡）/ 数据（清空本地偏好，`confirm` 二次确认）/ 关于（版本、服务地址 `location.origin`、`/api/health` 原始摘要、复制诊断信息） |
| `components/ShortcutHelp.vue` | 快捷键面板 | 居中模态，`?` 或 `Ctrl/Cmd + /` 打开；表格列出 `Enter` / `Shift+Enter` / `Ctrl+K` / `Ctrl+/` / `Esc` / `Ctrl+Shift+E`（导出） |
| `components/MessageMenu.vue` | 消息操作条 | 可复用：复制 / 再答 / 反馈；hover 才显示，`focus-within` 也显示（键盘可达） |
| `components/EmptyState.vue` | 空状态 | 从 `MessageList` 抽出，接收 `examples` `capabilities`，点击示例 → `chat.sendQuestion` |

**Toast / Confirm 的 CSS 归 §12**（`main.css` 末尾新增段落），不要写进组件的 `<style scoped>`——项目当前无 scoped 样式约定，混用会造成优先级混乱。

### 8.15 新增 `frontend/src/utils/export.js`

```js
export function toMarkdown(messages, meta = {}) {
  const head = [
    '# ' + (meta.title || '对话记录'),
    '',
    '- 导出时间：' + new Date().toLocaleString('zh-CN'),
    '- 会话 ID：`' + (meta.threadId || '') + '`',
    '',
    '---',
    '',
  ].join('\n')
  const body = messages.map((m) => {
    const who = m.role === 'user' ? '## 我' : '## ' + (meta.assistantName || '助手')
    return who + '\n\n' + (m.content || '').trim() + '\n'
  }).join('\n')
  return head + body
}
export function download(filename, text) {
  const blob = new Blob([text], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
```
文件名：`${会话标题}-${yyyyMMdd-HHmm}.md`，标题里的 `/ \ : * ? " < > |` 替换为 `-`。

---

## 9. 功能补齐清单

| 优先级 | 功能 | 现状 | 方案 | 涉及文件 | 验收 |
|---|---|---|---|---|---|
| **P0** | 复制按钮正确 | 改错元素、抹图标 | §8.8 | MessageItem | 连点 3 条消息，只有被点的那条变"已复制"，图标仍在 |
| **P0** | 历史消息时间 | 全显示挂载时刻 | §8.8 / §8.11 | MessageItem, chat.js | 刷新后历史消息不显示时间 |
| **P0** | 历史 plan/sources 错配 | 每条都挂最后一轮 | §8.11 | chat.js | 5 轮对话刷新后，只有最后一条有来源卡 |
| **P0** | 中文输入法误发送 | 无 `isComposing` | §8.9 | Composer | 拼音选词回车不发送 |
| **P0** | 零原生弹窗 | 9 处 | §8.14 | Toast/Confirm + 4 处调用点 | `grep -rn "alert(\|confirm(" src` 结果为 0（`confirmDialog` 除外） |
| **P0** | Markdown 净化 + 外链 | 裸 v-html | §8.10 | MarkdownView, package.json | 回答含 `<img onerror=alert(1)>` 不弹窗；点链接新标签打开 |
| **P0** | 错误编号可见 | 丢弃 | §8.12 / §8.8 | useChat, MessageItem | 断网发送后界面显示 `错误编号 xxxx` 且可复制 |
| **P1** | 再答一次 | 无 | §8.11 | chat.js, MessageItem | 点后新增一轮，历史条数 +2 |
| **P1** | 导出对话 Markdown | 无 | §8.15 | utils/export, ChatHeader | 下载文件含全部问答、标题正确 |
| **P1** | 会话分组 + 悬停操作 | 平铺 | §8.5 | Sidebar | 今天/更早分组正确；hover 出现铅笔与删除 |
| **P1** | 侧栏折叠 | 无 | §8.5 | Sidebar, App, config | 折叠后 64px，刷新保持 |
| **P1** | 设置抽屉 | 无 | §8.14 | SettingsDrawer | 改字号立即生效且持久化 |
| **P1** | 切会话中止生成 | 卡死（F18） | §8.11 | chat.js, Sidebar | 生成中切会话：新会话可立即发送 |
| **P1** | 回到底部 + 新消息提示 | 无 | §8.7 | MessageList | 上滚后出 FAB，点击回底 |
| **P1** | 加载骨架 | 空状态闪现 | §8.7 | MessageList, chat.js | 切会话时看到骨架而非问候语 |
| **P1** | 移动端抽屉侧栏 | 横向滚动条 | §7 | Sidebar, ChatHeader | 375px 宽下侧栏为抽屉，汉堡可开 |
| **P1** | 租户品牌化 | 硬编码 | §11 | brand.js, theme.js | 改 `window.__JTW_BRAND__` 后标题/Logo/主色/示例全变 |
| **P2** | 反馈（👍/👎） | 无 | 🔶 需后端接口，**一期不做**；改为"复制反馈"（问题+回答+错误编号） | MessageItem | 复制内容可直接贴进工单 |
| **P2** | 会话置顶 / 归档 | 无 | 🔶 需后端字段，不做 | — | — |
| **P2** | 消息搜索 | 无 | 二期（前端全文检索 `messages`） | — | — |
| **P2** | 真时间戳 | 后端无字段 | 🔶 可选后端增强：`to_plain_messages` 增加 `ts`，`web.py` 透传 | agent.py, web.py | 若做，历史消息显示真实时间 |

🔶 = 需要后端改动，一期明确不做。执行者不得自行加接口。

---

## 10. 状态机与边界（逐条验收）

| 场景 | 期望行为 |
|---|---|
| 首屏无任何会话 | 自动建 1 个；失败则显示"新建对话"按钮 + 顶部 Toast 报错，输入框仍可用（点击发送时自愈） |
| 连点发送 | 第二次被 `sending` 拦截；按钮同时切为停止态 |
| 生成中按 Esc | 停止生成，写入"已停止"提示，`sending` 复位 |
| 生成中切换会话 | 自动 abort + Toast 提示，新会话输入可用（F18） |
| 生成中删除当前会话 | abort → 删除 → 选中下一个或新建 |
| 流中断（后端挂掉） | 保留已生成内容 + 错误块（含 error_id）+ 重试 |
| 回答为空（`done.answer` 为空且无 token） | 显示"我这次没组织出回答" + 再答一次按钮 |
| 会话切换接口 404 | 移除该会话、Toast 报错、回退到第一个会话（不空白） |
| 后端 500 带 error_id | 错误块展示编号，可复制 |
| 超长输入 > 4000 字 | 显示计数、禁用发送、提示"请分段提问" |
| 深色模式 + 代码块 | 代码块始终深底，不二次反转 |
| 缩放 200% | 布局不横向滚动（820px 内容区自动收窄） |

---

## 11. 多租户品牌化（商业化的关键一步）

### 11.1 三层覆盖

| 层 | 手段 | 是否需要重新构建 |
|---|---|---|
| 构建期 | 改 `brand.js` 的 `DEFAULTS` | 是 |
| 运行期 | `dist/index.html` 注入 `window.__JTW_BRAND__` | **否**（运维可直接改） |
| 部署期 | 每个租户一份 `dist` + 一份注入脚本 | 否 |

### 11.2 注入示例（运维手册可直接抄）

```html
<!-- dist/index.html，放在 </head> 前 -->
<script>
window.__JTW_BRAND__ = {
  tenantName: '重庆某三甲医院',
  productName: '数据智能助手',
  mark: '医',
  tagline: '运营数据 · 病案知识库 · 收入预测',
  accent: '#0E8074',
  support: '信息科 内线 8123',
  examples: [
    { text: '统计 2025 年各科室门诊量', tip: '直连业务库' },
    { text: '查一下最新的医保结算政策', tip: '知识库检索' }
  ]
}
</script>
```

### 11.3 硬性要求

1. 界面中**不得出现**"豆包""Doubao""Arco"字样（注释也不留）。
2. Logo 图形统一为 `brand.mark` 渲染的方形圆角块（`--radius-md`），**不再用圆形渐变**，避免与通用助手雷同。
3. favicon 用同色块 + 首字（`index.html` 的 data URI 同步替换）。
4. 空状态、占位符、侧栏 tagline、导出文件头、错误提示里的产品名，**全部走 `brand.*`**，禁止字面量。
5. 租户换色后，用户气泡、按钮、选中态、链接、来源卡主色必须同步（因为它们都引用 `--brand-*`）。

---

## 12. 可访问性与性能

### 12.1 可访问性（必须）

1. 所有图标按钮带 `aria-label`；纯装饰 SVG 加 `aria-hidden="true"`。
2. 焦点环：`:focus-visible { outline: 2px solid var(--brand-600); outline-offset: 2px }`，**不要 `outline:none`**。
3. 抽屉/模态打开时：`role="dialog" aria-modal="true"`，焦点移入，`Tab` 循环限制在内部，`Esc` 关闭，关闭后焦点归还触发元素。
4. 消息区不再整体 `aria-live`（F11），用独立 `role="status"` 播报关键节点。
5. 对比度按 §5.4；禁止纯色差区分状态（成功/失败同时用图标或文字）。
6. `prefers-reduced-motion: reduce` 时关闭所有动画与 `scroll-behavior: smooth`。

### 12.2 键盘

| 键 | 行为 |
|---|---|
| `Enter` | 发送（输入法合成中放行） |
| `Shift+Enter` | 换行 |
| `Esc` | 关闭最上层浮层；无浮层时停止生成 |
| `Ctrl/Cmd+K` | 聚焦会话搜索 |
| `Ctrl/Cmd+Shift+O` | 新建对话 |
| `Ctrl/Cmd+Shift+E` | 导出当前对话 |
| `Ctrl/Cmd+/` 或 `?` | 快捷键面板 |

### 12.3 性能

1. `.msg { content-visibility: auto; contain-intrinsic-size: 0 120px }` —— 200 条以上消息滚动不掉帧。
2. 滚动监听用 `requestAnimationFrame` 节流（现有实现已用，保留）。
3. 流式追加文本只触发最后一次 watch（§8.7），消除全量 deep diff。
4. `backdrop-filter` 只用于 header 与遮罩，且面积不超过视口 15%（低端集显会掉帧）。
5. 构建产物体积目标：JS < 220KB（gzip）、CSS < 30KB（gzip）。`dompurify` 约 +22KB gzip，可接受；不得再引入其他运行时依赖。

---

## 13. 施工顺序与门禁

| 阶段 | 内容 | 门禁（全部满足才进下一阶段） |
|---|---|---|
| **P0-1 地基**（约 2h） | `brand.js`、`styles/theme.js`、`main.js`、重写 `main.css`（§5–§7） | `npm run build` 通过；`grep -c "^:root" src/styles/main.css` = 1；页面在 1024/1440/1920 三档无错位 |
| **P0-2 骨架**（约 3h） | `App.vue`、`Sidebar.vue`、`ChatHeader.vue` | 新建/切换/重命名/删除/清空全部走 Toast+Confirm；无 `alert`/`confirm` |
| **P0-3 消息**（约 3h） | `MessageList.vue`、`MessageItem.vue`、`chat.js`、`useChat.js` | §10 表格前 8 行逐条手测通过；复制/时间/plan 错配三项修复 |
| **P0-4 输入与安全**（约 2h） | `Composer.vue`、`MarkdownView.vue`、新增依赖 | 中文输入法测试通过；`<img onerror>` 不执行；外链新标签 |
| **P1 增强**（约 3h） | `SettingsDrawer`、`ToastHost`、`ConfirmHost`、`ShortcutHelp`、`EmptyState`、`utils/export.js` | 导出文件可正常打开；字号/主题/动效持久化 |
| **P2 打磨**（约 2h） | 移动端抽屉、骨架屏、FAB、动画曲线、暗色细节 | 375px 可用；暗色下无"白块"；reduced-motion 生效 |

**提交粒度**：每个阶段至少 1 个独立提交，信息格式 `feat(ui): 阶段名 + 主要变化`。没有 git 的话，先在 `frontend/` 下 `git init` 再动手——**没有回滚点的重构不许开工**。

---

## 14. 验收清单

### 14.1 构建与静态检查

```bash
cd frontend
npm run build                 # 必须 0 error 0 warning（体积告警需说明）
grep -c "^:root" src/styles/main.css          # 期望 1
grep -c 'data-theme="dark"' src/styles/main.css  # 期望 1
grep -rn "alert(\|confirm(" src | grep -v confirmDialog   # 期望 0
grep -rn "document.querySelector" src          # 期望 0
grep -rn "豆包\|Doubao\|Arco" src              # 期望 0
grep -rn "!important" src/styles/main.css      # 期望 ≤ 4（仅 reduced-motion）
```

### 14.2 人工验收（逐项打勾）

- [ ] 首屏 1.5s 内出现骨架或空状态，无白屏
- [ ] 新建 → 提问 → 流式出字 → 完成，全程无布局跳动
- [ ] 生成中：发送变停止，点击可中断，中断文案正确
- [ ] 生成中切换会话：不卡死，有提示
- [ ] 中文输入法回车选词不误发
- [ ] 任意一条消息复制：只该条变"已复制"，1.4s 后复原，图标不消失
- [ ] 刷新页面：历史消息无时间（诚实），最后一条有来源卡，其余没有
- [ ] 断网发送：出现错误块 + 错误编号，可复制
- [ ] 删除会话：弹自定义确认框，取消无副作用，确认后自动选中下一个
- [ ] 导出 Markdown：文件内容完整，标题与文件名对得上
- [ ] 深色模式：无白底残留、无低对比文字、代码块正常
- [ ] 1420px / 1024px / 375px 三档：无横向滚动、无重叠
- [ ] 键盘走查：Tab 能走完侧栏→顶栏→消息操作→输入框，焦点环可见
- [ ] 换 `window.__JTW_BRAND__` 后：标题、Logo、主色、示例卡、导出文件头全部变化
- [ ] 界面中无第三方产品名痕迹

### 14.3 回归红线（回归即阻断发布）

1. 会话列表读不出来 / 切换后消息空白
2. 发送后无任何返回（`sending` 卡死）
3. Markdown 表格、代码块、图片渲染异常
4. 上传面板、资料预览、来源抽屉、审批卡样式塌陷（§4.5 类名被误删）
5. 暗色模式下出现白底黑字块

---

## 15. 回滚、仓库与交付约定

### 15.1 回滚

- 仓库：`https://github.com/wenh56884-wq/bigdata`，工作分支 `v2`。
- 开工前打基线：`git add -A && git commit -m "chore: 前端改造前基线"`。
- 某个阶段门禁没过：`git restore frontend/src/styles/main.css`（或 `git restore frontend/`）回到上一提交，**不要带着失败状态继续叠加**。
- `main.css` 是唯一的全局视觉入口，回滚它即可恢复旧视觉；组件改动按文件粒度回滚。
- 回滚后必须重跑 `npm run build` 与 §14.3 的四条红线，再继续。

### 15.2 仓库与推送约定

**分支策略（重要）**

| 分支 | 内容 | 说明 |
|---|---|---|
| `main` | 2026-09-28 的**旧扁平结构**（`core/` `services/` `web.py` `index.html`） | 仅作历史归档，**不要在其上施工**，也不要强推覆盖 |
| `v2` | 当前四域结构（`backend/` `frontend/` `infra/` `docs/`） | 唯一活跃分支；本文所有改动推到这里 |

**每次改完都推送（用户的常驻要求）**

```bash
cd "C:/Users/22124/Desktop/发布包/九天梧桐AI工作台"
git add -A
git commit -m "feat(ui): 阶段2 侧栏分组与折叠"     # 约定见下
git push origin v2
```

提交信息规范：`type(scope): 说明`，`type` ∈ `feat|fix|style|docs|chore|refactor`，`scope` ∈ `ui|chat|sidebar|composer|docs|repo`。
一次提交只做一件事，信息里不写"update""修改"这类无信息量的词。

**推送前必跑的三条**

```bash
cd frontend && npm run build && cd ..        # 构建不通过不许推
git status --short                           # 确认没有意外文件
git diff --cached --stat | tail -3           # 确认改动范围符合预期
```

### 15.3 不入库清单（隐私与体积红线）

`.gitignore` 已落地，**不要用 `git add -f` 绕过**。已排除并说明原因：

| 排除项 | 原因 |
|---|---|
| `backend/.env`、`**/.env.bak_*` | 真实 API Key 与数据库密码 |
| `backend/data/`（`conversations.json`、`checkpoints.sqlite3`、`uploads/`） | 用户对话记录、上传文件，**隐私核心** |
| `backend/knowledge/自动学习/` | 自动沉淀的真实提问 + 会话 ID |
| `frontend/node_modules/` | 40MB 依赖 |
| `infra/runtime/`、`infra/mysql/` | 892MB + 1.1GB 内置运行时 |
| `infra/sql/*.sql` | 单文件 80/107/380MB，**超过 GitHub 100MB 单文件上限，推送必被拒** |
| `docs/*.pdf` | 516KB 二进制，不便审计且可由 `build_techdoc.py` 重建 |
| `.workbuddy/` | 工作区私有记忆 |
| `*.sqlite3`、`reports/`、`__pycache__/` | 运行时产物 |

**已核可公开、但需知情的三类**

1. `backend/.env.example` 中 `DB_PASSWORD=123456`、`infra/scripts/*.ps1` 中 `$DbPass = "123456"`：这是**本地内置 MySQL 的默认初始密码**，不是个人隐私，且服务只监听 `127.0.0.1`。若要彻底消除，需把脚本改为从 `backend/.env` 读取（3 行改动 + 需重测一键启动），属独立小任务，不要在本次前端改造里顺手改。
2. `backend/services/ops/sanitize.py` 与 `backend/eval/tests/_test_reason_and_data.py` 中的 `13812345678` / `320102199001011234` / `王小明`：**脱敏模块的测试夹具**，合成数据，非真实记录。若租户合规要求零示例，可替换为同长度伪值，但需同步改断言。
3. `backend/knowledge/*.md`：数据库 schema 与 NL→SQL 题库，含字段名（`national_id`、`patient_name`）与题目中的示例人名，**不含真实记录值**。

**大文件怎么办**：三份 SQL 转储与运行时压缩包走 GitHub Release 附件（单文件上限 2GB）或内网网盘，仓库里只留 `infra/sql/README.md` 说明获取方式；不要在仓库里放 LFS（当前账户 LFS 配额未知，易触发推送失败）。

### 15.4 明确不做（防止过度改造）

| 不做 | 原因 |
|---|---|
| 换 UI 框架（Element/Arco/AntD/Tailwind） | 会产生第三套设计系统，且与 8 个子组件的既有 class 冲突 |
| 引入虚拟滚动库 | `content-visibility` 已够用，多一个依赖多一份风险 |
| 把 `agent.py` 拆分 | 属后端重构，本期与前端无关 |
| 新增后端接口（反馈、置顶、搜索、截断历史） | 一期用前端方案替代；加接口会引入两侧版本耦合 |
| 重写上传/预览/来源/审批组件 | 它们功能正常，只跟随新 token 变色即可 |
| 实现登录页 / 权限显隐 | 属并行工作流，见 §4.6 |
| 引入 i18n | 单语言交付，收益为负 |
| PWA / 离线缓存 | 本地服务形态下无意义，且缓存会干扰版本更新 |
| 把 `infra/sql/*.sql` 塞进仓库 | 超出 GitHub 单文件上限，必然推送失败 |

---

## 16. 附：给执行 AI 的自检提问

动手前先回答这五个问题，答不上来说明你没读懂：

1. 为什么不能给 `--accent` 改名？（答：8 个子组件在用，改名必漏）
2. 历史消息为什么不显示时间？（答：后端 `to_plain_messages` 只返回 role/content）
3. "再答一次"为什么不叫"重新生成"？（答：后端每轮追加历史，叫重新生成会误导）
4. 助手消息为什么去掉气泡？（答：长文档阅读与专业感，同时减少渐变撞脸）
5. 换租户主色时，需要改几个变量？（答：只改 `--brand-600`，其余由 §8.2 推导）

---

**文档结束。执行时若发现与代码不一致，以代码为准，并在本文对应小节追加"实测修正"批注，不要静默改动。**
