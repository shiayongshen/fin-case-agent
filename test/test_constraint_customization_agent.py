import asyncio
import json

try:
    import chainlit as cl
except Exception:
    # 測試環境可能沒有安裝 chainlit，提供一個簡單替代 shim
    class _CLShim:
        def __init__(self):
            self.user_session = None

    cl = _CLShim()

from agents.ConstraintCustomizationAgent import CustomizeConstraintAgent


class SimpleSession:
    def __init__(self):
        self._d = {}

    def get(self, k, default=None):
        return self._d.get(k, default)

    def set(self, k, v):
        self._d[k] = v


async def run_tests():
    # 替換 chainlit 的 session 為簡單模擬
    cl.user_session = SimpleSession()

    # 建立 agent
    agent = CustomizeConstraintAgent(llm_config={})

    # 設定案例與分析結果
    cl.user_session.set("current_analysis_case_id", "case_0")
    cl.user_session.set("latest_deep_analysis_result", {
        "controllable_changes": [
            {"name": "x", "from": 1, "to": 2},
            {"name": "y", "from": 5, "to": 10}
        ],
        "derived_changes": []
    })

    # 1) 模擬 LLM 回傳 add_constraint
    parsed_add = {
        "action": "add_constraint",
        "parsed_constraints": [
            {"var": "x", "type": "FIX", "value": 10, "raw_text": "x=10"}
        ],
        "message": "已暫存 x=10"
    }

    res = await agent.process_llm_parse_result(parsed_add)
    assert res["intent"] == "pending_constraints_shown"
    pending = cl.user_session.get("pending_constraints")
    assert pending is not None
    assert isinstance(pending.get("parsed"), list)
    assert pending.get("parsed")[0]["var"] == "x"

    print("add_constraint test passed")

    # 2) 模擬 LLM 回傳 confirm
    parsed_confirm = {"action": "confirm", "parsed_constraints": [], "message": "確認套用"}
    res2 = await agent.process_llm_parse_result(parsed_confirm)
    assert res2["intent"] == "tool_call"
    assert "Calling function: apply_custom_constraints_tool" in res2["content"]
    assert "【約束設置完成】" in res2["content"]

    print("confirm test passed")

    print("ALL TESTS PASSED")


if __name__ == '__main__':
    asyncio.run(run_tests())
