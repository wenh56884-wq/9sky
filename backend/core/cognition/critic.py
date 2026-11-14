"""答案批评家（Agent Critic）—— 防幻觉机制的终答守门人。

设计要点
--------
现有 Reflexion（reasoning.py）只核对「计划是否完成」，不核对「内容是否真实」。
本模块补上后者：终答交给用户之前，把**回答正文**与**本轮工具真实返回**一起交给
Critic 审查，重点核对每一个具体数字（金额 / 数量 / 比率 / 日期 / 排名）：

- 回答里的数字能在工具结果里找到出处 → 通过；
- 找不到出处、或与出处明显不符 → 判为幻觉，带指令退回重答；
- Critic 自身调用失败 / 超时 / 输出不可解析 → **放行**（宁可漏判，不可因守门人
  故障把所有回答都拦死；防幻觉是增强项，不是可用性前提）。

为什么用「数字核对」做主判定：编造口径、编造列名、编造结论都会先体现在
"说出了一个工具结果里不存在的数字"。数字有硬出处，最容易机械验证、误判率最低。
定性描述（"整体呈上升趋势"）交给提示词层的 ANSWER_DISCIPLINE 约束，不做强拦截。

流程（agent.stream_ask 终答轮调用）：
  1. critique(goal, answer, tool_results) → {"verdict": "pass"|"hallucination",
     "problems": [{"quote", "reason"}], "instruction": "..."}
  2. verdict=pass → 原回答放行；
  3. verdict=hallucination → 上层撤回已流出的文本，按 instruction 重答（有预算上限）。

开关与预算：``CRITIC_ENABLED``（默认开）、``CRITIC_MAX_ROUNDS``（默认 1 次重答）。
本模块不直接调 LLM，通过 complete(system, user) 回调注入，可离线单测。
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field

# 模型调用回调：(system, user) -> 纯文本
Complete = callable  # noqa: F821  (运行时由 agent.py 注入真实签名)

VERDICT_PASS = "pass"
VERDICT_HALLUCINATION = "hallucination"

# 抽取「具体数字」的正则：带单位的金额、百分数、整数/小数计数、ISO 日期。
# 用于把工具结果压成"数字出处清单"，让 Critic 只核对可机械验证的部分。
_NUM_RE = re.compile(
    r"(?<![\w.])(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)\s*(?:%|万元|元|万|亿|人|条|笔|次|个|名|家|台|单|月租)?(?![\w.])"
)
_DATE_RE = re.compile(r"\b\d{4}[-/年]\d{1,2}(?:[-/月]\d{1,2}日?)?\b")


def _env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        return max(minimum, min(int(os.getenv(name, str(default))), maximum))
    except (TypeError, ValueError):
        return default


def enabled() -> bool:
    raw = (os.getenv("CRITIC_ENABLED") or "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def max_rounds() -> int:
    return _env_int("CRITIC_MAX_ROUNDS", 1, minimum=0, maximum=3)


@dataclass
class CriticReport:
    """一次审查的结构化结论。"""

    verdict: str = VERDICT_PASS          # pass | hallucination | error
    problems: list[dict] = field(default_factory=list)   # [{"quote","reason"}]
    instruction: str = ""                # 判幻觉时给重答的修正指令
    detail: str = ""                     # 一句话说明（进调试日志/度量）

    @property
    def ok(self) -> bool:
        # error = Critic 自身故障/输出不可信 → fail-open 放行，不拦死正常回答
        return self.verdict != VERDICT_HALLUCINATION


def _tool_digest(tool_results: list[dict], char_budget: int = 6000) -> str:
    """把本轮工具返回压成审查素材：工具名 + 截断后的原始文本。

    工具结果里含真实数字，是核对出处的唯一依据；超长时按块截尾，
    保证整体素材不超过 char_budget（Critic 输入过大本身就会稀释注意力）。
    """
    blocks: list[str] = []
    used = 0
    for item in tool_results[-8:]:        # 只看最近 8 次工具调用，足够覆盖终答依据
        name = str(item.get("name") or "tool")
        text = " ".join(str(item.get("result") or "").split())
        if not text:
            continue
        quota = max(200, (char_budget - used) // max(1, len(tool_results[-8:]) - len(blocks)))
        text = text[:quota]
        used += len(text) + len(name) + 8
        blocks.append(f"[{name}] {text}")
        if used >= char_budget:
            break
    return "\n".join(blocks) if blocks else "（本轮没有工具返回——回答若含任何具体数据，即属无出处）"


def _numbers_in(text: str) -> set[str]:
    """抽出文本里的具体数字（归一化去逗号），供提示词引用。"""
    out = {m.group(1).replace(",", "") for m in _NUM_RE.finditer(text or "")}
    out |= set(_DATE_RE.findall(text or ""))
    return out


def worth_checking(answer: str, tool_results: list[dict]) -> bool:
    """便宜预检：本轮有工具结果、或回答里出现具体数字时才值得花一次模型调用。

    纯闲聊（无工具、无数字）直接跳过，不为「你好」多付一次 LLM 费用；
    而「没调工具却报出具体数字」正是最典型的幻觉，必须送审。
    """
    return bool(tool_results) or bool(_numbers_in(answer))


CRITIC_SYSTEM = (
    "你是答案批评家（Critic），负责在回答交付给用户前做防幻觉核对。\n"
    "你会看到：① 用户的问题与 Agent 准备给出的回答；② 本轮各工具的真实返回结果。\n"
    "你的唯一任务：核对回答里的**每一个具体数字**（金额/数量/比率/日期/排名/预测值）"
    "是否能在工具返回结果里找到出处、且数值一致。\n"
    "判定规则：\n"
    "- 回答中的数字在工具结果中存在且一致 → 无问题；\n"
    "- 数字在工具结果中找不到、或与结果明显不符（如结果 37 说成 73、结果没有该值却给出了具体值）"
    "→ 判幻觉；\n"
    "- 工具明确返回失败/为空，回答却给出了具体数字 → 判幻觉；\n"
    "- 以下情况**不算**幻觉，不要拦截：对数字的定性概括（\"增长了\"\"占比较小\"）、"
    "基于工具结果做的一步算术（合计/差值/比率，数值可由结果推出）、单位换算、"
    "回答里的年份等背景时间、以及工具结果为空时如实说明\"没有查到\"；\n"
    "- 没有任何数字问题 → 一律放行，不要为了\"显得严格\"而拦下诚实的回答。\n"
    "只输出一个 JSON 对象：\n"
    '{"verdict": "pass" 或 "hallucination", '
    '"problems": [{"quote": "回答中的原句片段", "reason": "哪里对不上"}], '
    '"instruction": "若判幻觉：一句话告诉 Agent 必须怎么改（删掉/修正哪些数字，如实说明没查到）"}\n'
    "不要输出 JSON 以外的任何文字。"
)


def critique(complete, question: str, answer: str, tool_results: list[dict]) -> CriticReport:
    """审查一份终答。Critic 调用失败/解析失败时放行（verdict=error，ok=True）。"""
    if not enabled():
        return CriticReport(verdict=VERDICT_PASS, detail="critic disabled")
    digest = _tool_digest(tool_results)
    answer_nums = sorted(_numbers_in(answer))
    user = (
        f"用户问题：{question}\n\n"
        f"Agent 准备给出的回答：\n{(answer or '（空）')[:2500]}\n\n"
        f"回答中出现的具体数字（供逐个核对）：{('、'.join(answer_nums)) if answer_nums else '（无具体数字）'}\n\n"
        f"本轮工具的真实返回结果：\n{digest}"
    )
    try:
        raw = complete(CRITIC_SYSTEM, user)
        data = json.loads(_strip_fence(raw or ""))
    except Exception as exc:                      # 守门人自身故障 → 放行，不拦死正常回答
        return CriticReport(verdict="error", detail=f"critic unavailable: {exc}")
    if not isinstance(data, dict):
        return CriticReport(verdict="error", detail="critic output not a JSON object")
    verdict = str(data.get("verdict") or "").strip().lower()
    problems = []
    for p in (data.get("problems") or [])[:6]:
        if isinstance(p, dict) and (p.get("quote") or p.get("reason")):
            problems.append({"quote": str(p.get("quote") or "")[:120],
                             "reason": str(p.get("reason") or "")[:160]})
    instruction = str(data.get("instruction") or "").strip()[:300]
    if verdict == VERDICT_HALLUCINATION:
        # 有了具体问题才拦；只给结论不给依据的判罚视为不可靠，放行
        if not problems:
            return CriticReport(verdict="error", detail="hallucination verdict without problems")
        return CriticReport(verdict=VERDICT_HALLUCINATION, problems=problems,
                            instruction=instruction or "回答中的部分数字在工具结果中找不到出处，请删除或修正这些数字，如实说明数据缺失。")
    return CriticReport(verdict=VERDICT_PASS, detail="no numeric fabrication found")


def _strip_fence(text: str) -> str:
    """容忍模型给 JSON 包上 ```json 围栏。"""
    s = (text or "").strip()
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z]*\s*", "", s)
        s = re.sub(r"\s*```$", "", s)
    return s.strip()


# --------------------------------------------------------------------------- #
# 自检：python -m core.cognition.critic
# --------------------------------------------------------------------------- #
def _selftest() -> int:
    def check(name, got, want):
        status = "PASS" if got == want else "FAIL"
        print(f"  [{status}] {name}: got={got!r} want={want!r}")
        return got == want

    ok = True

    # 数字抽取
    nums = _numbers_in("上月收入 1,234.5 万元，环比 -8.2%，共 37 个客户；2024-08/2024-09 对比。")
    ok &= check("数字抽取含金额", "1234.5" in nums, True)
    ok &= check("数字抽取含百分数", "8.2" in nums, True)
    ok &= check("数字抽取含计数", "37" in nums, True)
    ok &= check("数字抽取含日期", any("2024-08" in n for n in nums), True)

    # 幻觉判定：回答数字不在工具结果里
    def fake_complete_hallu(system: str, user: str) -> str:
        return json.dumps({"verdict": "hallucination",
                           "problems": [{"quote": "收入 999 万元", "reason": "工具结果是 512 万元"}],
                           "instruction": "改为 512 万元"})

    report = critique(fake_complete_hallu, "上月收入多少",
                      "上月收入 999 万元。", [{"name": "execute_sql", "result": "512.00 万元"}])
    ok &= check("幻觉判定 verdict", report.verdict, VERDICT_HALLUCINATION)
    ok &= check("幻觉判定不通过", report.ok, False)

    # 诚实回答放行
    def fake_complete_pass(system: str, user: str) -> str:
        return json.dumps({"verdict": "pass", "problems": [], "instruction": ""})

    report = critique(fake_complete_pass, "上月收入多少",
                      "上月收入 512 万元。", [{"name": "execute_sql", "result": "512.00 万元"}])
    ok &= check("正常回答放行", report.ok, True)

    # Critic 自身故障 → 放行（不拦死）
    def fake_complete_boom(system: str, user: str) -> str:
        raise RuntimeError("api down")

    report = critique(fake_complete_boom, "q", "a", [{"name": "t", "result": "1"}])
    ok &= check("守门人故障放行", report.ok, True)

    # 无依据的判罚 → 放行（不可靠判罚不拦截）
    def fake_complete_lazy(system: str, user: str) -> str:
        return json.dumps({"verdict": "hallucination", "problems": [], "instruction": "重写"})

    report = critique(fake_complete_lazy, "q", "a", [{"name": "t", "result": "1"}])
    ok &= check("无依据判罚放行", report.ok, True)

    print("critic selftest:", "ALL PASS" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(_selftest())
