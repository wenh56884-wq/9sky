# 九天梧桐 AI 工作台 — 登录 / 权限等级 / 人机协同 / 审批层次 优化任务分配

> **分工**：后端组（Claude B）负责认证、权限、HITL 扩展、审批层次、接口鉴权、数据模型；前端组（Claude A）负责登录界面、权限控制、审批层次界面、用户管理界面。**主导方负责方案、接口契约、最终测试与整合**。
> 本文件是任务分配的唯一依据，每次分配都在此更新。
>
> **背景**：项目已重组为四域结构（`backend/`、`frontend/`、`infra/`、`docs/`）。后端现状：仅 `ADMIN_TOKEN` 固定令牌（仅 3 个上传写操作，未设则全放行）、**无用户体系/登录/会话**、**无角色/权限**、HITL 单层单工具（仅 forget）且内存态（重启丢失）无鉴权、**无审批层次**。需新增四大能力。

---

## 一、已确认的架构决策

| 决策项 | 选定方案 |
| --- | --- |
| 权限等级 | **4 级**：访客(0) / 普通用户(1) / 管理员(2) / 超级管理员(3) |
| 审批层次 | **风险分级双级**：低风险操作单级审批（操作者本人确认），高风险操作双级（操作者触发→管理员审批） |
| 登录认证 | **本地账号密码**：bcrypt 哈希存储，登录签发会话令牌，首次启动自动创建超管账号 |
| 协同范围 | **扩展多工具**：除 `forget` 外，将写报告/出图等有副作用的 Agent 工具纳入审批保护 |

---

## 二、权限等级定义（4 级）

角色用整数 `role` 表示：0 访客、1 普通用户、2 管理员、3 超级管理员。

| 角色 | 等级 | 能力 |
| --- | --- | --- |
| 访客 | 0 | 仅访问 `/`、`/assets/*`、`/api/health`、`/api/auth/login`；看不到聊天与工作台 |
| 普通用户 | 1 | 问答（`/api/chat`、`/api/deep`）、查看会话/记忆、查看技能卡/模型、上传文件预览、深度搜索 |
| 管理员 | 2 | 普通用户全部 + 会话管理（新建/重命名/删除/清空）、上传/删除文件、清表格记忆、**处理审批**、查看待审批列表 |
| 超级管理员 | 3 | 全部权限 + **用户管理**（增删改用户、改角色、改密码、重置密码）、系统配置 |

**未登录 = 访客（0）**。打开应用未登录时前端显示登录界面；登录后按角色进入工作台。

---

## 三、数据模型（后端新建，不污染现有 4 个库）

### 3.1 `backend/data/auth.sqlite3`（认证库，新建）
**users 表**
| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | TEXT PK | uuid |
| username | TEXT UNIQUE | 用户名 |
| password_hash | TEXT | bcrypt 哈希 |
| role | INTEGER | 0/1/2/3 |
| created_at | TEXT | ISO 时间 |
| last_login | TEXT | 最后登录时间 |

**sessions 表**
| 字段 | 类型 | 说明 |
| --- | --- | --- |
| token | TEXT PK | 会话令牌（uuid，服务端存储，支持登出/踢人） |
| user_id | TEXT | 关联 users.id |
| created_at | TEXT | 创建时间 |
| expires_at | TEXT | 过期时间（默认 7 天，可配置） |

### 3.2 `backend/data/approvals.sqlite3`（审批库，新建，替代 hitl 内存态）
**approvals 表**
| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | TEXT PK | 审批 uuid |
| thread_id | TEXT | 会话 id |
| tool | TEXT | 工具名 |
| args | TEXT | JSON 字符串 |
| description | TEXT | 人话描述 |
| risk_level | TEXT | `low` / `high` |
| stage | TEXT | `awaiting_operator` / `awaiting_admin` / `done` |
| decision | TEXT | approve/reject/timeout（done 后） |
| operator_id | TEXT | 触发操作者用户 id |
| approver_id | TEXT | 审批人用户 id |
| created_at | TEXT | 创建时间 |
| resolved_at | TEXT | 决策时间 |

**持久化要求**：审批落盘，重启不丢失；`hitl.py` 的内存 `_pending` 改为读写此库（保留内存索引加速查询）。

---

## 四、接口规范（前后端共同遵循的契约）

### 4.1 认证接口（新增，后端实现）

| 方法 | 路径 | 鉴权 | 说明 |
| --- | --- | --- | --- |
| POST | `/api/auth/login` | 公开 | body `{username, password}`，成功返回 `{token, user:{id,username,role}}`；失败 401 |
| POST | `/api/auth/logout` | ≥1 | 销毁当前 token |
| GET | `/api/auth/me` | ≥1 | 返回 `{user:{id,username,role}}` |
| POST | `/api/auth/change-password` | ≥1 | body `{old_password, new_password}` |
| GET | `/api/auth/users` | ≥3 | 用户列表（超管） |
| POST | `/api/auth/users` | ≥3 | body `{username, password, role}`，创建用户（超管） |
| PATCH | `/api/auth/users/<id>` | ≥3 | body `{role?, password?}`，改角色/重置密码（超管） |
| DELETE | `/api/auth/users/<id>` | ≥3 | 删除用户（超管，不可删自己/最后一个超管） |

**首次启动**：`auth.sqlite3` 的 users 表为空时，从 `.env` 读 `ADMIN_USERNAME`/`ADMIN_PASSWORD`（默认 `admin`/`admin123`），自动创建 role=3 超管。首次登录后前端提示改密。

**令牌传递**：请求头 `Authorization: Bearer <token>`。

### 4.2 现有接口鉴权矩阵（后端改造）

| 接口 | 方法 | 最低角色 | 变化 |
| --- | --- | --- | --- |
| `/` `/assets/*` | GET | 公开 | 不变 |
| `/reports/*` | GET | ≥1 | 加登录 |
| `/api/health` | GET | 公开 | 不变（访客可见） |
| `/api/models` `/api/skills` | GET | ≥1 | 加登录 |
| `/api/conversations` | GET | ≥1 | 加登录 |
| `/api/conversations` | POST | ≥2 | 加管理员 |
| `/api/conversations/<id>/messages` | GET | ≥1 | 加登录 |
| `/api/conversations/<id>` | PATCH/DELETE | ≥2 | 加管理员 |
| `/api/conversations` | DELETE | ≥2 | 加管理员 |
| `/api/memory` | GET | ≥1 | 加登录 |
| `/api/memory/<key>` | DELETE | ≥2 | 加管理员 |
| `/api/uploads` | GET | ≥1 | 加登录 |
| `/api/uploads` | POST | ≥2 | 加管理员（取代 ADMIN_TOKEN） |
| `/api/uploads/<name>/preview` `/content` | GET | ≥1 | 加登录 |
| `/api/uploads/<name>` | DELETE | ≥2 | 加管理员 |
| `/api/uploads/memory` | GET/DELETE | ≥2 | 加管理员 |
| `/api/chat` `/api/deep` | POST | ≥1 | 加登录 |

**ADMIN_TOKEN 兼容**：保留 `ADMIN_TOKEN` 校验作为兜底（设置了则上传写操作仍需令牌），但主要鉴权走用户体系。未设置 `ADMIN_TOKEN` 时，鉴权完全走用户角色。

### 4.3 审批层次接口（后端改造）

| 方法 | 路径 | 鉴权 | 说明 |
| --- | --- | --- | --- |
| GET | `/api/approvals` | ≥2 | 待审批列表（管理员/超管），返回 `{items:[{id,thread_id,tool,description,risk_level,stage,operator,created_at}]}` |
| POST | `/api/approvals/<id>` | 按层级 | body `{decision, message?, args?}`。低风险单级：操作者本人可批；高风险双级：需 ≥ 管理员。决策 approve/reject/edit（edit 带 args） |

**审批决策鉴权**：
- `stage=awaiting_operator`（低风险）：仅 `operator_id` 对应用户可决策
- `stage=awaiting_admin`（高风险）：需 role ≥ 2 的管理员/超管决策
- 已 done/timeout：404

### 4.4 流式事件扩展（后端）
`/api/chat` 的 `approval_required` 事件增加字段：
```json
{"type":"approval_required","approval_id":"...","thread_id":"...","tool":"forget","args":{},"description":"...","risk_level":"high","stage":"awaiting_admin","allowed_decisions":["approve","reject","edit"]}
```
前端据此显示审批卡（高风险标注"需管理员审批"）。

---

## 五、人机协同与审批层次设计（后端核心）

### 5.1 受保护工具清单（扩展，可配置）
在 `hitl.py` 中扩展 `protected_tools` 与风险等级表：

| 工具 | 风险等级 | 审批层级 | 说明 |
| --- | --- | --- | --- |
| `forget` | high | 双级 | 删除跨会话长期记忆，不可逆 |
| `forecast_metric` | low | 单级 | 写预测报告文件（有副作用但可逆） |
| `plot_last_result` | low | 单级 | 写图表 PNG 文件 |

后续可按"有副作用（写文件/删数据）"原则扩展。查询/分析类只读工具不保护。

### 5.2 双级审批流转
- **低风险（单级）**：工具调用触发 → `stage=awaiting_operator` → 操作者本人 approve/reject/edit → 执行
- **高风险（双级）**：工具调用触发 → `stage=awaiting_admin`（操作者不能自批）→ 管理员 approve/reject/edit → 执行
- 超时：`stage` 等待超 `HITL_TIMEOUT_SECONDS` → 自动 `decision=timeout`，拒绝执行

### 5.3 Agent 接入
两条路径都复用 `hitl` 闸门，扩展 `requires_approval()` 接受风险等级判断，`create()` 写入 `approvals.sqlite3` 并按风险定 `stage`。`core/agent.py` 的流式循环（`4328-4352`）与 `HumanInTheLoopMiddleware` 配置同步更新工具登记。

### 5.4 /api/health 扩展
`hitl` 字段增加：`protected_tools`（扩展后清单）、`risk_levels`（工具→风险映射）、`pending`（待审批数）、`persisted`（true，审批已落盘）。

---

## 六、前后端分工

### 后端 Claude B 任务
1. **认证模块**：`backend/services/ops/auth.py`（登录/登出/改密/用户管理逻辑）、`auth_store.py`（auth.sqlite3 读写、bcrypt 哈希、会话令牌、首次建超管）。
2. **权限中间件**：`@require_auth`、`@require_role(min_role)` 装饰器，接入 `web.py` 全部路由（按 §4.2 矩阵）。
3. **HITL 扩展与持久化**：`hitl.py` 升级——审批落盘 `approvals.sqlite3`、扩展受保护工具与风险等级、双级流转、审批列表接口。
4. **接口改造**：新增 `/api/auth/*`；`/api/approvals` 列表接口；`approval_required` 事件加字段；`/api/health` 扩展 hitl 字段。
5. **配置**：`.env`/`.env.example` 新增 `ADMIN_USERNAME`、`ADMIN_PASSWORD`、`SESSION_TTL_HOURS`、`BCRYPT_ROUNDS`；保留 `HITL_*`。
6. **依赖**：`requirements.txt` 加 `bcrypt`（或用 `passlib[bcrypt]`）。
7. **保留**：`ADMIN_TOKEN` 兜底校验；现有 API 行为（除鉴权外）不变。

### 前端 Claude A 任务
1. **登录界面**：`frontend/src/views/LoginView.vue`，未登录时 App 显示登录页；登录/登出；首次登录（默认密码）提示改密。
2. **认证接入**：`frontend/src/api/` 封装 `/api/auth/*`；store 管理 token/当前用户；请求拦截器带 `Authorization: Bearer`；401 自动跳登录。
3. **权限控制**：按角色（0/1/2/3）控制界面——访客只见登录/健康；普通用户隐藏"资料"上传、会话删除等；管理员见审批中心；超管见用户管理。组件级 `v-if`/禁用。
4. **审批层次界面**：`ApprovalCard.vue` 升级——显示风险等级与当前阶段（操作者确认/待管理员审批）；高风险标注"需管理员审批"；管理员见审批列表入口。
5. **用户管理界面**（超管）：`frontend/src/views/UserManage.vue`——用户列表、增删改、改角色、重置密码。
6. **工作台适配**：侧栏/顶栏按角色显示功能项；健康徽标对访客可见。
7. **视觉**：登录页、用户管理页沿用豆包风格（`main.css` 已有设计系统，新增类名按规范添加）。

---

## 七、验收标准

**后端**
- `npm` 无关；`python -m py_compile` 全通过；`backend/web.py` 启动正常
- 首次启动自动建超管；登录/登出/改密/用户管理 CRUD 正常
- 各接口按角色鉴权：访客被拒（401/403）、普通用户不能会话删除、非超管不能用户管理
- 审批：forget 触发高风险双级（需管理员批）、预测/出图低风险单级；审批落盘重启不丢；超时自动拒绝
- `/api/health` 含扩展的 hitl 字段

**前端**
- `npm run build` 通过；未登录显示登录页；登录后按角色进入工作台
- 各角色界面功能边界正确（普通用户看不到管理员功能）
- 审批卡显示风险等级与阶段；管理员可见审批列表与处理入口
- 超管可见用户管理页，CRUD 正常
- 主题切换、响应式正常

**整体**
- `python web.py` 启动，浏览器访问 `/` → 登录 → 按角色使用；审批链路端到端跑通（触发 forget → 管理员审批 → 执行/拒绝）
- 权限矩阵逐项验证通过

## 八、执行顺序建议

1. 主导方完成本文档（接口契约、数据模型、权限矩阵）—— ✅ 已完成
2. **后端 Claude B** 先落地：认证模块 + 权限中间件 + HITL 持久化与双级 + 接口改造（前端依赖其接口契约）
3. **前端 Claude A** 按接口契约并行开发：登录 + 权限控制 + 审批界面 + 用户管理
4. 后端完成后，前端联调（登录、审批链路、权限边界）
5. 主导方最终测试与整合（端到端验证权限矩阵、审批层次、登录流程）

## 完成记录

- **2026-11-12**：优化方案确立。4 级权限（访客/用户/管理员/超管）、风险分级双级审批、本地账号密码登录、扩展多工具协同。任务分配文档完成，并行派发后端 Claude B（认证/权限/HITL 扩展/审批层次/接口鉴权）与前端 Claude A（登录/权限控制/审批层次界面/用户管理）。
- **2026-11-12（完成）**：前后端均已完成并验证。
  - **后端 Claude B**：新建 `auth_store.py`/`auth.py`（auth.sqlite3、bcrypt、会话令牌、首次建超管、`@require_auth`/`@require_role`）；升级 `hitl.py`（审批落盘 approvals.sqlite3、扩展受保护工具 forget=high/forecast_metric=low/plot_last_result=low、双级流转、按阶段鉴权、超时拒绝）；改造 `agent.py`（HITL 动态注册、`approval_required` 加 risk_level/stage）；改造 `web.py`（`/api/auth/*`、`/api/approvals`、全路由按 §4.2 矩阵加鉴权、ADMIN_TOKEN 兜底）；`.env` 新增 4 项配置、requirements 加 bcrypt。py_compile 通过；鉴权矩阵、审批双级/单级/超时/落盘重启均实测通过；35 项自检 + 端到端审批流 PASS。
  - **前端 Claude A**：新增 LoginView（登录+首次改密）、UserManage（超管用户管理）、ApprovalCenter（审批中心抽屉）、auth store/api、useNav；改造 App.vue（登录/访客无权限/用户管理/工作台分流）、Sidebar/ChatHeader（按角色显示功能项）、ApprovalCard（风险等级+阶段+按角色决策）、api/index.js（Bearer 鉴权+401 跳登录）、useChat（透传 risk_level/stage）、main.css。`npm run build` 通过，后端可托管。
  - **主导方端到端测试**：Playwright+Edge 浏览器验证——登录页显示、超管登录进入工作台（含用户管理/审批入口）、创建普通用户、登出回登录页、普通用户权限边界（无用户管理入口），**全部通过，控制台零错误**。
  - **遗留**：后端验证产生的测试用户 `user1` 与测试审批记录仍存于 `auth.sqlite3`/`approvals.sqlite3`（不影响功能，admin 超管完好）；清理需授权执行 `DELETE FROM users WHERE username='user1'; DELETE FROM approvals;`。
