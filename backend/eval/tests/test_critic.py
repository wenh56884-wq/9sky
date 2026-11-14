"""Agent Critic 防幻觉机制测试。

覆盖：
- 数字/日期抽取（金额千分位、百分数、日期）；
- 幻觉判定：回答数字在工具结果中无出处 → 拦截并给出修正指令；
- 诚实回答放行；
- Critic 故障 / 输出不可解析 / 无依据判罚 → fail-open 放行（不拦死正常回答）；
- 开关与重答预算的环境变量边界。
"""
import json

import pytest

from core.cognition import critic


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv("CRITIC_ENABLED", raising=False)
    monkeypatch.delenv("CRITIC_MAX_ROUNDS", raising=False)


def _complete(payload):
    """构造一个返回固定 JSON 的 complete 回调。"""
    def fn(system, user):
        return json.dumps(payload, ensure_ascii=False)
    return fn


# ------------------------------- 数字抽取 ------------------------------- #
def test_numbers_extracted():
    nums = critic._numbers_in("上月收入 1,234.5 万元，环比 -8.2%，共 37 个客户。")
    assert "1234.5" in nums
    assert "8.2" in nums
    assert "37" in nums


def test_dates_extracted():
    nums = critic._numbers_in("对比 2024-08 与 2024-09 的数据")
    assert any("2024-08" in n for n in nums)
    assert any("2024-09" in n for n in nums)


# ------------------------------- 判定逻辑 ------------------------------- #
def test_hallucination_blocks():
    report = critic.critique(
        _complete({"verdict": "hallucination",
                   "problems": [{"quote": "收入 999 万元", "reason": "工具结果是 512 万元"}],
                   "instruction": "把 999 改成 512"}),
        "上月收入多少", "上月收入 999 万元。",
        [{"name": "execute_sql", "result": "512.00 万元"}],
    )
    assert report.verdict == critic.VERDICT_HALLUCINATION
    assert not report.ok
    assert report.problems and "999" in report.problems[0]["quote"]
    assert report.instruction


def test_pass_allows():
    report = critic.critique(
        _complete({"verdict": "pass", "problems": [], "instruction": ""}),
        "上月收入多少", "上月收入 512 万元。",
        [{"name": "execute_sql", "result": "512.00 万元"}],
    )
    assert report.ok


def test_critic_crash_is_fail_open():
    def boom(system, user):
        raise RuntimeError("provider down")

    report = critic.critique(boom, "q", "答案 42", [])
    assert report.ok                      # 守门人故障不拦回答
    assert report.verdict == "error"


def test_invalid_json_is_fail_open():
    report = critic.critique(lambda s, u: "不是 JSON", "q", "答案", [])
    assert report.ok


def test_hallucination_without_problems_is_fail_open():
    """只给判罚、不给依据 → 判定不可靠，放行。"""
    report = critic.critique(
        _complete({"verdict": "hallucination", "problems": [], "instruction": "重写"}),
        "q", "答案", [{"name": "t", "result": "1"}],
    )
    assert report.ok


def test_code_fence_tolerated():
    def fenced(system, user):
        return '```json\n{"verdict": "pass", "problems": []}\n```'

    report = critic.critique(fenced, "q", "答案", [])
    assert report.ok


# ------------------------------- 开关与预算 ------------------------------- #
def test_disabled_bypasses_llm():
    import os
    os.environ["CRITIC_ENABLED"] = "0"
    try:
        called = {"n": 0}

        def fn(system, user):
            called["n"] += 1
            return "{}"

        report = critic.critique(fn, "q", "a", [])
        assert report.ok
        assert called["n"] == 0
    finally:
        os.environ.pop("CRITIC_ENABLED", None)


@pytest.mark.parametrize("raw,expected", [("0", 0), ("1", 1), ("3", 3), ("9", 3), ("-1", 0), ("abc", 1)])
def test_max_rounds_bounds(raw, expected, monkeypatch):
    monkeypatch.setenv("CRITIC_MAX_ROUNDS", raw)
    assert critic.max_rounds() == expected


def test_tool_digest_empty_note():
    assert "没有工具返回" in critic._tool_digest([])


# ------------------------------- 便宜预检 ------------------------------- #
def test_worth_checking_skips_pure_chat():
    assert critic.worth_checking("你好呀，今天过得怎么样？", []) is False


def test_worth_checking_checks_numbers_without_tools():
    # 没调工具却报出具体数字 → 最典型的幻觉，必须送审
    assert critic.worth_checking("上月收入是 512 万元。", []) is True


def test_worth_checking_checks_tool_rounds():
    assert critic.worth_checking("总共 37 人。", [{"name": "execute_sql", "result": "37"}]) is True
