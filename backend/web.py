"""Flask Web 服务：为多会话（多重对话）Agent 提供 HTTP 接口（/api/chat 为流式 NDJSON）。"""

import json
import os
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from flask import Flask, Response, g, jsonify, request, send_from_directory

from core.agent import (
    ChatService,
    available_models,
    db_skill_cards,
    delete_memory,
    list_memories,
    resolve_model,
    search_memories,
)
from services.ops import hitl, debugging
from services.ops import write_executor
from services.ops import auth as auth_service
from services.ops.auth import require_auth, require_role

app = Flask(__name__)
# 上传大小上限（要略大于单文件上限，留给 multipart 的开销）
app.config["MAX_CONTENT_LENGTH"] = int(
    float(os.getenv("UPLOAD_MAX_MB", "1024")) * 1024 * 1024 * 1.2)
service = ChatService()


def _json_payload() -> dict:
    """Return a JSON object without raising on missing/invalid content type."""
    payload = request.get_json(silent=True)
    return payload if isinstance(payload, dict) else {}


# ----- 前端构建产物托管（Vite 构建输出到 frontend/dist，由 Flask 单服务托管）-----
# 默认指向同级 frontend/dist；可用 DIST_DIR 环境变量覆盖（绝对路径，或相对后端根的路径）
DIST_DIR = Path(os.getenv("DIST_DIR") or (PROJECT_ROOT.parent / "frontend" / "dist"))

_MISSING_DIST_HINT = (
    "<!doctype html><html><head><meta charset=\"utf-8\"><title>前端尚未构建</title>"
    "<style>body{font-family:system-ui,'Microsoft YaHei',sans-serif;max-width:680px;margin:80px auto;"
    "padding:0 24px;line-height:1.7;color:#1f2329}code,pre{background:#f2f3f5;border-radius:4px}"
    "code{padding:2px 6px}pre{padding:12px;overflow:auto}</style></head><body>"
    "<h2>前端尚未构建</h2>"
    "<p>检测到 <code>frontend/dist</code> 不存在，Vue 前端产物尚未生成，无法展示工作台页面。</p>"
    "<p>请先在 <code>frontend</code> 目录执行：</p>"
    "<pre><code>npm install\nnpm run build</code></pre>"
    "<p>构建完成后产物会输出到 <code>frontend/dist</code>，刷新本页即可访问工作台。</p>"
    "</body></html>"
)


def _is_within(path: Path, base: Path) -> bool:
    """判断 path 是否位于 base 目录内（防目录穿越）。"""
    try:
        path.resolve().relative_to(base.resolve())
        return True
    except ValueError:
        return False


def _spa_index():
    """返回 Vite 构建的 index.html；未构建时返回友好提示（避免开发期直接 500 崩溃）。"""
    index_file = DIST_DIR / "index.html"
    if index_file.is_file():
        return send_from_directory(DIST_DIR, "index.html")
    return Response(_MISSING_DIST_HINT, status=503, mimetype="text/html; charset=utf-8")


@app.get("/")
def index():
    """根路径：托管 Vite 构建的 index.html（未构建时给出构建提示）。"""
    return _spa_index()


@app.get("/assets/<path:filename>")
def assets(filename):
    """托管 Vite 构建的 JS/CSS 资源（dist/assets/）。"""
    return send_from_directory(DIST_DIR / "assets", filename)


@app.get("/api/health")
def health():
    return jsonify({"ok": True, **service.info()})


# ------------------------------- 认证接口 ------------------------------- #
@app.post("/api/auth/login")
def auth_login():
    """公开接口：账号密码登录，签发会话令牌。"""
    payload = _json_payload()
    try:
        result = auth_service.login(
            payload.get("username", ""), payload.get("password", "")
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 401
    return jsonify(result)


@app.post("/api/auth/logout")
@require_auth
def auth_logout():
    auth_service.logout(g.current_token)
    return jsonify({"ok": True})


@app.get("/api/auth/me")
@require_auth
def auth_me():
    return jsonify({"user": g.current_user})


@app.post("/api/auth/change-password")
@require_auth
def auth_change_password():
    payload = _json_payload()
    try:
        auth_service.change_password(
            g.current_user_id, payload.get("old_password", ""), payload.get("new_password", "")
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"ok": True})


@app.get("/api/auth/users")
@require_role(3)
def auth_users_list():
    """用户列表（超管）。"""
    return jsonify({"users": auth_service.list_users()})


@app.post("/api/auth/users")
@require_role(3)
def auth_users_create():
    payload = _json_payload()
    try:
        user = auth_service.create_user(
            payload.get("username", ""), payload.get("password", ""), payload.get("role", 1)
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"user": user}), 201


@app.patch("/api/auth/users/<user_id>")
@require_role(3)
def auth_users_patch(user_id):
    payload = _json_payload()
    try:
        user = auth_service.update_user(
            user_id, role=payload.get("role"), password=payload.get("password")
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"user": user})


@app.delete("/api/auth/users/<user_id>")
@require_role(3)
def auth_users_delete(user_id):
    try:
        auth_service.delete_user(user_id, self_id=g.current_user_id)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"deleted": user_id})


@app.get("/api/models")
@require_auth
def model_list():
    """只暴露强推理/强代码模型白名单，默认模型排第一。"""
    return jsonify({"models": available_models(), "default": resolve_model()})


@app.get("/api/skills")
@require_auth
def skill_list():
    """列出可手动选择的数据查询技能卡（库 key + 中文名 + 就绪状态），供前端下拉选择。"""
    return jsonify({"skills": db_skill_cards()})


@app.get("/reports/<path:filename>")
@require_auth
def reports_file(filename):
    """供网页展示 reports/ 目录下的图表 PNG（只放行顶层 *.png，防目录穿越）。"""
    name = Path(filename).name
    if name != filename or not re.fullmatch(r"[A-Za-z0-9_\-]+\.png", name):
        return jsonify({"error": "资源不存在"}), 404
    target = PROJECT_ROOT / "reports" / name
    if not target.is_file():
        return jsonify({"error": "资源不存在"}), 404
    resp = send_from_directory(PROJECT_ROOT / "reports", name)
    resp.headers["Cache-Control"] = "no-cache"
    return resp


# --------------------------- 会话（thread）管理 --------------------------- #
@app.get("/api/conversations")
@require_auth
def list_conversations():
    return jsonify({"conversations": service.list_conversations()})


@app.post("/api/conversations")
@require_role(2)
def create_conversation():
    title = (_json_payload().get("title") or "").strip()
    return jsonify({"conversation": service.new_conversation(title or None)}), 201


@app.get("/api/conversations/<thread_id>/messages")
@require_auth
def conversation_messages(thread_id):
    """会话完整历史 + 最近的执行计划（plan），便于刷新页面后仍能看到计划进度。"""
    item = service.store.get(thread_id)
    if not item:
        return jsonify({"error": "会话不存在。"}), 404
    return jsonify({
        "thread_id": thread_id,
        "messages": service.history(thread_id),
        "plan": item.get("plan"),
        "sources": item.get("sources") or [],   # 最近一轮的数据来源，界面在回答下方展示
    })


@app.patch("/api/conversations/<thread_id>")
@require_role(2)
def rename_conversation(thread_id):
    title = (_json_payload().get("title") or "").strip()
    if not title:
        return jsonify({"error": "标题不能为空。"}), 400
    item = service.rename_conversation(thread_id, title)
    if not item:
        return jsonify({"error": "会话不存在。"}), 404
    return jsonify({"conversation": item})


@app.delete("/api/conversations")
@require_role(2)
def clear_conversations():
    """一键清空全部会话（元数据 + Checkpointer 里的对话历史；跨会话长期记忆保留）。"""
    return jsonify({"cleared": service.clear_conversations()})


@app.delete("/api/conversations/<thread_id>")
@require_role(2)
def delete_conversation(thread_id):
    item = service.delete_conversation(thread_id)
    if not item:
        return jsonify({"error": "会话不存在。"}), 404
    return jsonify({"deleted": thread_id})


# ----------------------- 跨会话长期记忆（Store）----------------------- #
@app.get("/api/memory")
@require_auth
def memory_list():
    """列出全局共享 Store 里的跨会话记忆。

    可选参数 q：按相关度检索（如 /api/memory?q=报销 标准）；不传则返回最近的若干条。
    """
    query = (request.args.get("q") or "").strip()
    if query:
        limit = request.args.get("limit", type=int) or 8
        return jsonify({"query": query, "memories": search_memories(query, limit=max(1, min(limit, 50)))})
    return jsonify({"memories": list_memories()})


@app.delete("/api/memory/<key>")
@require_role(2)
def memory_delete(key):
    delete_memory(key)
    return jsonify({"deleted": key})


@app.get("/api/approvals")
@require_role(2)
def approval_list():
    """待审批列表（管理员/超管）。"""
    return jsonify({"items": hitl.manager.list_pending()})


@app.post("/api/approvals/<approval_id>")
@require_auth
def approval_decide(approval_id):
    """批准、拒绝或编辑一条正在等待的 Agent 受保护操作。

    按层级鉴权：低风险单级仅操作者本人可决策；高风险双级需管理员（角色≥2）。
    """
    payload = _json_payload()
    try:
        result = hitl.manager.resolve(
            approval_id,
            payload.get("decision") or "",
            payload.get("message") or "",
            payload.get("args"),
            user_id=g.current_user_id,
            user_role=g.current_user.get("role"),
        )
    except hitl.ApprovalForbidden as exc:
        return jsonify({"error": str(exc)}), 403
    except (hitl.ApprovalError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 400
    if result is None:
        return jsonify({"error": "审批不存在、已处理或已超时。"}), 404
    return jsonify({"approval": result})


# ------------------------------ 写数据能力（§8.5） ------------------------------ #
@app.get("/api/writes/pending")
@require_auth
def writes_pending():
    """我能批的写草案（按角色过滤：required_role <= 我的角色）。"""
    role = int(g.current_user.get("role", 1))
    return jsonify({"items": hitl.manager.list_pending_writes(min_role=role)})


@app.post("/api/writes/<proposal_id>/decide")
@require_auth
def writes_decide(proposal_id):
    """批准或拒绝一条写草案。按 required_role 鉴权（角色只从 token 反查）。"""
    payload = _json_payload()
    decision = (payload.get("decision") or "").strip().lower()
    if decision not in {"approve", "reject"}:
        return jsonify({"error": "decision 只能是 approve 或 reject"}), 400
    try:
        result = hitl.manager.resolve(
            proposal_id,
            decision,
            payload.get("message") or "",
            None,
            user_id=g.current_user_id,
            user_role=g.current_user.get("role"),
        )
    except hitl.ApprovalForbidden as exc:
        return jsonify({"error": str(exc)}), 403
    except (hitl.ApprovalError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 400
    if result is None:
        return jsonify({"error": "草案不存在、已处理或已超时。"}), 404

    # 批准后执行写变更
    if decision == "approve":
        proposal = hitl.manager.get_write_payload(proposal_id)
        if proposal:
            exec_result = write_executor.execute(
                proposal,
                approval_id=proposal_id,
                actor_id=g.current_user_id,
                actor_name=g.current_user.get("username", ""),
                approver_id=g.current_user_id,
                approver_name=g.current_user.get("username", ""),
            )
            return jsonify({"approval": result, "execution": exec_result})
    return jsonify({"approval": result})


@app.get("/api/writes/history")
@require_role(2)
def writes_history():
    """变更历史（分页，管理员/超管）。"""
    try:
        limit = int(request.args.get("limit", 50))
        offset = int(request.args.get("offset", 0))
    except (TypeError, ValueError):
        limit, offset = 50, 0
    status = request.args.get("status") or None
    return jsonify({"items": write_executor.history(limit=limit, offset=offset, status=status)})


@app.post("/api/writes/<change_id>/revert")
@require_role(2)
def writes_revert(change_id):
    """撤销一条已应用的变更（L2 起需二次审批，此处由路由层角色守卫）。"""
    try:
        result = write_executor.revert(
            change_id,
            actor_id=g.current_user_id,
            actor_name=g.current_user.get("username", ""),
        )
    except Exception as exc:
        return jsonify(debugging.error_payload(exc, context="writes_revert")), 500
    if not result.get("ok"):
        return jsonify({"error": result.get("message", "撤销失败")}), 400
    return jsonify(result)


# -------------------- 管理员上传：统一目录 + 落盘即解析 -------------------- #
@app.get("/api/uploads")
@require_auth
def upload_list():
    """列出统一上传目录（data/uploads）里的文件。"""
    try:
        from services.datasource import table_memory, uploads
        return jsonify({
            "directory": str(uploads.directory()),
            "files": uploads.list_files(),
            "memory": table_memory.summary(),
        })
    except Exception as exc:
        return jsonify(debugging.error_payload(exc, context="upload_list")), 500


@app.post("/api/uploads")
@require_role(2)
def upload_create():
    """管理员上传表格文件：存进统一目录 → **立即解析 → 写记忆 → 重建索引**。

    multipart/form-data，字段名 file（可多文件重复该字段）。
    若配置了 ADMIN_TOKEN，则需附带 ?token=xxx 或 X-Admin-Token 头。
    """
    token = (os.getenv("ADMIN_TOKEN") or "").strip()
    if token:
        given = (request.args.get("token") or request.headers.get("X-Admin-Token") or "").strip()
        if given != token:
            return jsonify({"error": "需要管理员令牌。"}), 401
    files = request.files.getlist("file")
    if not files:
        return jsonify({"error": "没有收到文件（字段名应为 file）。"}), 400
    try:
        from services.datasource import uploads
        saved, failed = [], []
        for item in files:
            try:
                saved.append(uploads.save(item.filename or "", item.read()))
            except Exception as exc:
                failed.append({"name": item.filename, "error": str(exc)})
        return jsonify({"saved": saved, "failed": failed}), 201
    except Exception as exc:
        return jsonify(debugging.error_payload(exc, context="upload_create")), 500


@app.get("/api/uploads/<path:name>/preview")
@require_auth
def upload_preview(name):
    """查看上传后的实际内容：表格行列、文档正文或图片 OCR 文本。"""
    try:
        from services.datasource import uploads
        return jsonify(uploads.preview(name))
    except FileNotFoundError:
        return jsonify({"error": "文件不存在。"}), 404
    except Exception as exc:
        return jsonify(debugging.error_payload(exc, context="upload_preview")), 500


@app.get("/api/uploads/<path:name>/content")
@require_auth
def upload_image_content(name):
    """仅以内联方式返回已上传图片，供资料预览弹窗展示原图。"""
    try:
        from services.datasource import uploads
        target = uploads.image_file(name)
        if not target:
            return jsonify({"error": "图片不存在。"}), 404
        response = send_from_directory(uploads.directory(), target.name)
        response.headers["Cache-Control"] = "private, no-store"
        return response
    except Exception as exc:
        return jsonify(debugging.error_payload(exc, context="upload_content")), 500


@app.delete("/api/uploads/<path:name>")
@require_role(2)
def upload_delete(name):
    """删除上传的文件（连带清记忆、重建索引）。"""
    token = (os.getenv("ADMIN_TOKEN") or "").strip()
    if token:
        given = (request.args.get("token") or request.headers.get("X-Admin-Token") or "").strip()
        if given != token:
            return jsonify({"error": "需要管理员令牌。"}), 401
    try:
        from services.datasource import uploads
        if not uploads.delete(name):
            return jsonify({"error": "文件不存在。"}), 404
        return jsonify({"deleted": name})
    except Exception as exc:
        return jsonify(debugging.error_payload(exc, context="upload_delete")), 500


@app.get("/api/uploads/memory")
@require_role(2)
def upload_memory():
    """查看表格自动记忆（数据卡片 + 问答经验）的概况，便于管理员确认「学到了什么」。"""
    try:
        from services.datasource import table_memory
        return jsonify(table_memory.summary())
    except Exception as exc:
        return jsonify(debugging.error_payload(exc, context="upload_memory")), 500


@app.delete("/api/uploads/memory")
@require_role(2)
def upload_memory_clear():
    token = (os.getenv("ADMIN_TOKEN") or "").strip()
    if token:
        given = (request.args.get("token") or request.headers.get("X-Admin-Token") or "").strip()
        if given != token:
            return jsonify({"error": "需要管理员令牌。"}), 401
    from services.datasource import table_memory
    table_memory.clear()
    return jsonify({"cleared": True})


# ------------------------------ 对话问答 ------------------------------ #
@app.post("/api/chat")
@require_auth
def chat():
    """流式问答：响应体为 NDJSON，每行一个事件（UTF-8）：

        {"type": "thinking",  "message": "..."}   过程提示（如“正在制定执行计划”）
        {"type": "plan",      "goal", "steps", "progress"}      本轮执行计划（复杂任务才有）
        {"type": "plan_step", "step": {...}}       计划某一步的状态变化（进度条）
        {"type": "token", "content": "字增量"}     前端逐字拼成完整回答
        {"type": "tool",  "name": "calculator"}    模型开始调用某工具
        {"type": "approval_required", ...}            高风险工具暂停，等待人工批准/拒绝
        {"type": "write_proposal", ...}               写数据变更草案生成，等待审批
        {"type": "write_applied", ...}                写变更已批准并执行完成
        {"type": "write_rejected", ...}               写变更被拒绝或超时，未改动数据
        {"type": "done",  "thread_id", "answer", "plan"}        本轮结束
        {"type": "error", "message": "...", "error_id": "..."}  中途出错（本回合不入历史）

    前端对不认识的事件类型直接忽略即可，老版本页面不会因为多出 plan 事件而报错。
    """
    payload = _json_payload()
    question = (payload.get("question") or "").strip()
    thread_id = (payload.get("thread_id") or "").strip() or None
    skill = (payload.get("skill") or "").strip()  # 前端手动指定的数据技能卡；空串=自动识别
    model = (payload.get("model") or "").strip()

    # stream_ask() 在返回生成器前完成校验与 Agent 预热，
    # 参数/配置错误在此以正常状态码返回，而不是中途断流
    try:
        events = service.stream_ask(
            thread_id, question, skill=skill, model=model, operator_id=g.current_user_id
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify(debugging.error_payload(exc, context="chat")), 500

    def generate():
        for event in events:
            yield json.dumps(event, ensure_ascii=False) + "\n"

    return Response(
        generate(),
        mimetype="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/deep")
@require_auth
def deep_search():
    """深度搜索（Deep Research 式）：拆子问题 → 多轮检索 → 查漏补缺 → 带引用综合回答。

    与 /api/chat 同款的 NDJSON 流，额外会先产出研究过程事件：
        {"type": "info",    ...}                            深度搜索开始 / 引擎情况
        {"type": "plan",    "queries": ["子查询1", ...]}    子问题拆解
        {"type": "search",  "query": ..., "hits": n, "engines": ..., "round": 1|2}
        {"type": "gap",     "queries": [...]}                查漏补缺（可无）
        {"type": "rerank",  "count": n}                      LLM 相关度重排（可无）
        {"type": "token",   "content": "..."}                综合回答正文增量
        {"type": "sources", "items": [{index/source/chunk/page/score}]}
        {"type": "done",    "thread_id": ..., "answer": ..., "sources": [...]}
    """
    payload = _json_payload()
    question = (payload.get("question") or "").strip()
    thread_id = (payload.get("thread_id") or "").strip() or None
    model = (payload.get("model") or "").strip()

    try:
        events = service.stream_deep(thread_id, question, model=model)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify(debugging.error_payload(exc, context="deep")), 500

    def generate():
        for event in events:
            yield json.dumps(event, ensure_ascii=False) + "\n"

    return Response(
        generate(),
        mimetype="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# -------------------- API 路径的统一 JSON 错误兜底 --------------------
# 为什么要有：前端把响应当 JSON 解析，Flask 默认的 404/413/500 是 HTML 错误页，
# 前端会报「Unexpected token '<'」这种让人摸不着头脑的错。兜底成 JSON 后，
# 前端能直接把原因（旧进程没重启 / 文件超限 / 服务内部错误）说清楚。
def _json_error(status: int, message: str):
    if request.path.startswith("/api/"):
        return jsonify({"error": message}), status
    return None                      # 非 API 路径走 Flask 默认错误页


@app.errorhandler(404)
def _not_found(_e):
    # /api/*、/reports/*：保持 JSON 错误兜底不变（接口/资源不存在的语义与迁移前一致）
    if request.path.startswith("/api/"):
        return jsonify({"error": "接口不存在。若刚更新过代码，请重启 python web.py。"}), 404
    if request.path.startswith("/reports/"):
        return jsonify({"error": "资源不存在"}), 404
    # SPA 单视图容错：非 API / 报告的 GET 请求
    if request.method == "GET":
        # /assets/* 缺失资源不回退（应正常 404，避免把 JS 404 误当页面返回）
        if request.path.startswith("/assets/"):
            return _e
        # 根静态文件（vite.svg / favicon.ico 等）：dist 下存在则返回该文件
        rel = request.path.lstrip("/")
        candidate = DIST_DIR / rel
        if _is_within(candidate, DIST_DIR) and candidate.is_file():
            return send_from_directory(DIST_DIR, rel)
        # 其余路径回退到 SPA index.html（单视图容错，避免刷新子路径 404）
        return _spa_index()
    return _e


@app.errorhandler(405)
def _bad_method(_e):
    hit = _json_error(405, "请求方法不对（该路径不支持此方法）。")
    return hit if hit is not None else _e


@app.errorhandler(413)
def _too_large(_e):
    limit = app.config.get("MAX_CONTENT_LENGTH", 0)
    hint = f"（上限约 {limit / 1024 / 1024:.0f} MB，可用 UPLOAD_MAX_MB 调整）" if limit else ""
    hit = _json_error(413, f"上传内容超过大小上限{hint}。")
    return hit if hit is not None else _e


@app.errorhandler(500)
def _server_error(_e):
    if request.path.startswith("/api/"):
        return jsonify(debugging.error_payload(_e, context="flask_500")), 500
    return _e


if __name__ == "__main__":
    import socket
    import threading
    import time
    import webbrowser

    host = os.getenv("HOST", "127.0.0.1")
    try:
        port = int(os.getenv("PORT", "5000"))
    except (TypeError, ValueError):
        port = 5000
    if not 1 <= port <= 65535:
        port = 5000

    def open_browser_when_ready() -> None:
        """轮询直到服务端口可连接，再打开浏览器，避免服务未就绪时页面报“无法访问”。"""
        url = f"http://{host}:{port}"
        for _ in range(100):  # 最多等待 30 秒
            with socket.socket() as probe:
                if probe.connect_ex((host, port)) == 0:
                    print(f"[九天梧桐] 服务已就绪，正在打开浏览器：{url}", flush=True)
                    webbrowser.open(url)
                    return
            time.sleep(0.3)
        print(f"[九天梧桐] 服务迟迟未就绪，未自动打开浏览器，请手动访问：{url}", flush=True)

    # NO_BROWSER=1 可跳过自动打开；调试重载模式下只在真正监听端口的子进程里开
    if os.getenv("NO_BROWSER") != "1" and os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        threading.Thread(target=open_browser_when_ready, daemon=True).start()

    app.run(host=host, port=port, debug=os.getenv("FLASK_DEBUG", "0") == "1")
