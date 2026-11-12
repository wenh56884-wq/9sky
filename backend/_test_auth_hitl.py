"""后端 Claude B 自检：认证 + 审批双级/超时/落盘逻辑（不依赖 LLM）。"""
import os
import sys
import threading
import time

BACKEND = r"C:\Users\22124\Desktop\发布包\九天梧桐AI工作台\backend"
sys.path.insert(0, BACKEND)
os.chdir(BACKEND)

from services.ops import auth, hitl
from services.ops.auth_store import store

PASS = 0
FAIL = 0


def check(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name} {extra}")


print("== 认证模块 ==")
# 首次启动建超管（若已存在则跳过）
check("users 表存在超管", store.count_users() >= 1, f"count={store.count_users()}")
admin = store.get_user_by_username("admin")
check("默认超管 admin 存在", admin is not None and admin["role"] == 3)

# 登录
try:
    res = auth.login("admin", "admin123")
    check("admin 登录成功拿到 token", bool(res.get("token")))
    admin_token = res["token"]
    admin_id = res["user"]["id"]
except Exception as e:
    check("admin 登录", False, str(e))
    raise

# 错误密码
try:
    auth.login("admin", "wrong")
    check("错误密码被拒", False)
except ValueError:
    check("错误密码被拒", True)

# me
me = auth.me(admin_token)
check("me 返回 admin", me and me["username"] == "admin" and me["role"] == 3)

# 普通用户 CRUD
u = auth.create_user("tester", "test123", role=1)
check("创建普通用户 tester", u and u["role"] == 1)
tester_token = auth.login("tester", "test123")["token"]
tester_id = u["id"]

# 改密
auth.change_password(tester_id, "test123", "newpass456")
try:
    auth.login("tester", "test123")
    check("旧密码改密后失效", False)
except ValueError:
    check("旧密码改密后失效", True)
check("新密码可登录", bool(auth.login("tester", "newpass456")["token"]))

# 用户列表 / 改角色 / 删除保护
users = auth.list_users()
check("用户列表含 admin+tester", len(users) >= 2)
auth.update_user(tester_id, role=2)
check("改角色为管理员", auth.me(auth.login("tester", "newpass456")["token"])["role"] == 2)
try:
    store.delete_user(admin_id, self_id=None)
    # admin 是唯一超管时不能删
    check("不能删最后一个超管", False)
except ValueError:
    check("不能删最后一个超管", True)
try:
    store.delete_user(admin_id, self_id=admin_id)
    check("不能删自己", False)
except ValueError:
    check("不能删自己", True)

# 登出
auth.logout(tester_token)
check("登出后令牌失效", auth.me(tester_token) is None)

print("== 审批模块：风险分级 + 双级流转 ==")
# 高风险（forget）
ap_high = hitl.manager.create("t1", "forget", {"target": "手机号"}, "", operator_id=admin_id)
check("forget 高风险", ap_high.risk_level == "high")
check("forget 阶段 awaiting_admin", ap_high.stage == "awaiting_admin")

# 低风险（forecast_metric）
ap_low = hitl.manager.create("t1", "forecast_metric", {"metric": "x"}, "", operator_id=admin_id)
check("forecast_metric 低风险", ap_low.risk_level == "low")
check("forecast_metric 阶段 awaiting_operator", ap_low.stage == "awaiting_operator")

# plot_last_result 低风险
ap_plot = hitl.manager.create("t1", "plot_last_result", {}, "", operator_id=admin_id)
check("plot_last_result 低风险单级", ap_plot.risk_level == "low" and ap_plot.stage == "awaiting_operator")

# 低风险：操作者本人可批
r = hitl.manager.resolve(ap_low.id, "approve", user_id=admin_id, user_role=3)
check("低风险操作者自批 approve", r and r["decision"] == "approve")

# 低风险：非操作者（即使管理员）不可批
ap_low2 = hitl.manager.create("t1", "forecast_metric", {}, "", operator_id=admin_id)
try:
    hitl.manager.resolve(ap_low2.id, "approve", user_id="someone-else", user_role=3)
    check("低风险非操作者被拒(403)", False)
except hitl.ApprovalForbidden:
    check("低风险非操作者被拒(403)", True)

# 高风险：普通用户(role=1)不可批
ap_high2 = hitl.manager.create("t1", "forget", {"target": "x"}, "", operator_id=admin_id)
try:
    hitl.manager.resolve(ap_high2.id, "approve", user_id="u1", user_role=1)
    check("高风险普通用户被拒(403)", False)
except hitl.ApprovalForbidden:
    check("高风险普通用户被拒(403)", True)

# 高风险：管理员(role=2)可批
r = hitl.manager.resolve(ap_high2.id, "approve", user_id="u2", user_role=2)
check("高风险管理员可批", r and r["decision"] == "approve")

# 已 done 再批 -> 404 (None)
r = hitl.manager.resolve(ap_high2.id, "approve", user_id="u2", user_role=2)
check("已处理审批再批返回 None(404)", r is None)

# 非法决策
try:
    hitl.manager.resolve(hitl.manager.create("t","forget",{},"",operator_id=admin_id).id, "bogus")
    check("非法决策被拒", False)
except hitl.ApprovalError:
    check("非法决策被拒", True)

print("== 审批落盘：重启不丢 ==")
# 新建一条待审批，模拟重启（新 ApprovalManager 实例读同一库）
ap_persist = hitl.manager.create("t2", "forget", {"target": "y"}, "", operator_id=admin_id)
before = hitl.manager.list_pending()
check("重启前待审批含该条", any(i["id"] == ap_persist.id for i in before))

# 模拟重启：重建 manager（新实例，内存空，从库加载）
hitl.manager = hitl.ApprovalManager()
after = hitl.manager.list_pending()
check("重启后审批仍存在（落盘不丢）", any(i["id"] == ap_persist.id for i in after))
# 重启后管理员仍可批
r = hitl.manager.resolve(ap_persist.id, "approve", user_id="u2", user_role=2)
check("重启后管理员可批", r and r["decision"] == "approve")

print("== 审批超时自动拒绝 ==")
# 临时把超时压到 1 秒
hitl._timeout_seconds = lambda: 1
ap_to = hitl.manager.create("t3", "forget", {"target": "z"}, "", operator_id=admin_id)
t0 = time.monotonic()
dec = hitl.manager.wait(ap_to)
elapsed = time.monotonic() - t0
check("超时返回 decision=timeout", dec["decision"] == "timeout", f"dec={dec}")
check("超时耗时约 1s", 0.8 <= elapsed < 5, f"elapsed={elapsed:.2f}")
# 超时后该审批决策为 timeout，再 resolve 返回 None
row = hitl.manager._store.load(ap_to.id)
check("超时后库中 decision=timeout", row["decision"] == "timeout")
r = hitl.manager.resolve(ap_to.id, "approve", user_id="u2", user_role=2)
check("超时后 resolve 返回 None(404)", r is None)

print("== /api/health hitl 字段 ==")
summ = hitl.manager.summary()
check("summary protected_tools 含三工具", set(summ["protected_tools"]) == {"forget", "forecast_metric", "plot_last_result"})
check("summary risk_levels 映射", summ["risk_levels"]["forget"] == "high" and summ["risk_levels"]["forecast_metric"] == "low")
check("summary persisted=True", summ["persisted"] is True)
check("summary 含 pending 字段", "pending" in summ)

print(f"\n结果：PASS={PASS} FAIL={FAIL}")
sys.exit(1 if FAIL else 0)
