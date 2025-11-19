#!/usr/bin/env python3
"""
測試完整的深入分析流程
模擬實際的訊息流：user_proxy -> deep_analysis_agent -> perform_deep_analysis_tool
"""

from agents.ChatManager import ChatManager
from agents import HostAgent, SearchAgent, CodeExecutorAgent, DeepAnalysisAgent, BaseUserProxy

llm_config = {
    "config_list": [{
        "model": "gpt-4o-mini",
        "api_key": "test-key"
    }]
}

def test_complete_flow():
    """測試完整的深入分析流程"""
    
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
    
    print("=" * 80)
    print("完整流程測試：模擬【啟動深入分析】的訊息路由")
    print("=" * 80)
    
    # 模擬訊息流
    test_messages = [
        {
            "name": "user_proxy",
            "content": "【啟動深入分析】 case_id: case_2",
            "role": "user"
        },
    ]
    
    for msg in test_messages:
        chat_manager.group_chat.messages.append(msg)
    
    # 獲取當前訊息
    current_msg = chat_manager.group_chat.messages[-1]
    
    # 模擬狀態轉換
    print(f"\n✉️  當前訊息: {current_msg['content']}")
    print(f"📍 來自: {current_msg['name']}")
    
    # 確定下一個發言者
    next_speaker = chat_manager._default_state_transition(
        user_proxy.get_proxy(),
        chat_manager.group_chat
    )
    
    print(f"↓")
    
    if hasattr(next_speaker, 'name'):
        print(f"🤖 下一個發言者: {next_speaker.name}")
        
        # 驗證
        if next_speaker.name == "deep_analysis_agent":
            print("\n✅ 路由正確！")
            print("\n流程驗證：")
            print("  1. user_proxy 接收到【啟動深入分析】訊息 ✓")
            print("  2. ChatManager 狀態轉換檢測到觸發詞 ✓")
            print("  3. 訊息被正確路由到 deep_analysis_agent ✓")
            print("\n📝 DeepAnalysisAgent 應該：")
            print("  - 解析 case_id: case_2")
            print("  - 建議調用 perform_deep_analysis_tool")
            print("  - user_proxy 執行工具")
            print("  - 返回分析報告")
            print("\n❌ 不應該發生：")
            print("  - 調用 legal_article_search（法條搜尋）")
            print("  - 調用 search_and_rerank（案例搜尋）")
            
            return True
        else:
            print(f"\n❌ 路由錯誤！訊息被路由到 {next_speaker.name} 而不是 deep_analysis_agent")
            return False
    else:
        print(f"🤖 下一個發言者: None（結束對話）")
        print(f"\n❌ 路由錯誤！訊息流程中止了")
        return False

if __name__ == "__main__":
    try:
        result = test_complete_flow()
        exit(0 if result else 1)
    except Exception as e:
        print(f"\n❌ 測試異常: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
