#!/usr/bin/env python3
"""
測試深入分析訊息流程
驗證【啟動深入分析】訊息是否正確路由到 deep_analysis_agent
"""

from agents.ChatManager import ChatManager
from agents import HostAgent, SearchAgent, CodeExecutorAgent, DeepAnalysisAgent, BaseUserProxy

# 模擬測試
llm_config = {
    "config_list": [{
        "model": "gpt-4o-mini",
        "api_key": "test-key"
    }]
}

def test_state_transition():
    """測試狀態轉換邏輯"""
    
    # 建立 agents
    host = HostAgent(llm_config)
    search = SearchAgent(llm_config)
    code_executor = CodeExecutorAgent(llm_config)
    deep_analysis = DeepAnalysisAgent(llm_config)
    user_proxy = BaseUserProxy()
    
    # 建立 ChatManager
    chat_manager = ChatManager(
        agents=[host, search, code_executor, deep_analysis],
        user_proxy=user_proxy,
        llm_config=llm_config,
        max_round=25
    )
    
    print("=" * 60)
    print("測試情況 1：host_agent 建議調用深入分析")
    print("=" * 60)
    
    # 模擬訊息流 - Case 1: Host Agent 最後一個發言
    # 當 host_agent 發送包含 "【啟動深入分析】" 的訊息
    test_msg_1 = {
        "name": "host_agent",
        "content": "【啟動深入分析】 case_id: case_2",
        "role": "assistant"
    }
    
    chat_manager.group_chat.messages.append(test_msg_1)
    
    # 以 host_agent 作為 last_speaker
    next_speaker_1 = chat_manager._default_state_transition(
        chat_manager._get_agent_by_name("host_agent"), 
        chat_manager.group_chat
    )
    
    print(f"\n輸入訊息: {test_msg_1['content']}")
    print(f"來自: {test_msg_1['name']}")
    print(f"預期下一個發言者: deep_analysis_agent")
    
    result_1 = False
    if hasattr(next_speaker_1, 'name'):
        actual_speaker_1 = next_speaker_1.name
        print(f"實際下一個發言者: {actual_speaker_1}")
        if actual_speaker_1 == "deep_analysis_agent":
            print("✅ 情況 1 測試通過！")
            result_1 = True
        else:
            print(f"❌ 情況 1 測試失敗！")
    
    # 情況 2：user_proxy 發送 "【啟動深入分析】"
    print("\n" + "=" * 60)
    print("測試情況 2：user_proxy 轉發深入分析訊息")
    print("=" * 60)
    
    # 清空並重新測試
    chat_manager.group_chat.messages = []
    
    test_msg_2 = {
        "name": "user_proxy",
        "content": "【啟動深入分析】 case_id: case_2",
        "role": "user"
    }
    
    chat_manager.group_chat.messages.append(test_msg_2)
    
    # 以 user_proxy 作為 last_speaker
    next_speaker_2 = chat_manager._default_state_transition(
        chat_manager.user_proxy.get_proxy(), 
        chat_manager.group_chat
    )
    
    print(f"\n輸入訊息: {test_msg_2['content']}")
    print(f"來自: {test_msg_2['name']}")
    print(f"預期下一個發言者: deep_analysis_agent")
    
    result_2 = False
    if hasattr(next_speaker_2, 'name'):
        actual_speaker_2 = next_speaker_2.name
        print(f"實際下一個發言者: {actual_speaker_2}")
        if actual_speaker_2 == "deep_analysis_agent":
            print("✅ 情況 2 測試通過！")
            result_2 = True
        else:
            print(f"❌ 情況 2 測試失敗！")
    elif next_speaker_2 is None:
        print("實際下一個發言者: None（結束對話）")
        print("❌ 情況 2 測試失敗！")
    
    return result_1 and result_2

if __name__ == "__main__":
    try:
        result = test_state_transition()
        exit(0 if result else 1)
    except Exception as e:
        print(f"\n❌ 測試異常: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
