from typing import Dict, List, Optional, Callable
from autogen import GroupChat, GroupChatManager
import chainlit as cl
import asyncio
from .BaseAgent import BaseAgent, BaseUserProxy


class ChatManager:
    """
    群組對話管理器
    負責協調多個 Agent 之間的對話流程
    """
    
    def __init__(
        self,
        agents: List[BaseAgent],
        user_proxy: BaseUserProxy,
        llm_config: Dict,
        max_round: int = 25,
        speaker_selection_method: Optional[Callable] = None
    ):
        self.agents = agents
        self.user_proxy = user_proxy  # 用於執行工具
        self.llm_config = llm_config
        self.max_round = max_round
        
        # ⭐ 新增：創建用於等待用戶輸入的 proxy（與工具執行 proxy 分開）
        # 注意：改為 human_input_mode="NEVER" 以避免 terminal 阻塞
        # 用戶輸入將通過 Chainlit UI 的 @cl.on_message() 進行處理
        self.user_input_proxy = BaseUserProxy(
            name="interactive_user",
            human_input_mode="NEVER",  # 改為 NEVER，避免 terminal 阻塞
            code_execution_config=False
        )
        
        # 建立 Agent 實例列表 (包含兩個 proxy)
        self.agent_instances = [agent.get_agent() for agent in agents]
        self.agent_instances.append(user_proxy.get_proxy())  # 工具執行 proxy
        self.agent_instances.append(self.user_input_proxy.get_proxy())  # 用戶輸入 proxy
        
        # 使用自定義或預設的狀態轉換
        if speaker_selection_method is None:
            speaker_selection_method = self._default_state_transition
        
        # 建立 GroupChat
        self.group_chat = GroupChat(
            agents=self.agent_instances,
            messages=[],
            max_round=max_round,
            speaker_selection_method=speaker_selection_method
        )
        
        # 建立 GroupChatManager
        self.manager = GroupChatManager(
            groupchat=self.group_chat,
            llm_config=llm_config,
            is_termination_msg=self._is_termination_msg
        )
        
        # 追蹤已處理的訊息數量
        self.last_processed_count = 0
        # 保存完整對話歷史
        self.full_conversation_history = []
        # 追蹤當前執行的對話任務
        self.current_chat_task: Optional[asyncio.Task] = None
        # 中斷標誌
        self.is_interrupted = False
    
    def _is_termination_msg(self, x: Dict) -> bool:
        """判斷是否為終止訊息"""
        if "content" not in x or x["content"] is None:
            return False
        
        content = x["content"].strip()
        
        termination_keywords = [
            "TERMINATE",
            "REPORT_COMPLETE",
            "SUMMARY_COMPLETE",
            "【退出自定義】",  # 用戶退出自定義
            "【約束設置完成】",  # 約束設置完成
        ]
        
        return any(keyword in content for keyword in termination_keywords)
    
    def _default_state_transition(self, last_speaker, groupchat):
        """預設的狀態轉換邏輯（含 constraint_customization 長流程支援）"""
        import chainlit as cl

        # 取得 pending search query（優先）
        pending_query = cl.user_session.get("pending_search_query")
        if pending_query:
            print(f"[StateTransition] 發現待處理搜索查詢: {pending_query}")
            cl.user_session.set("pending_search_query", None)
            return self._get_autogen_agent_by_name("search_agent")

        messages = groupchat.messages

        if not messages:
            return self._get_autogen_agent_by_name("host_agent")

        named_messages = [msg for msg in messages if 'name' in msg]

        if not named_messages:
            return "auto"

        last_message = named_messages[-1]
        last_content = last_message.get('content', '') or ''

        # ⭐ 改用消息本身的 name 鍵值，而不是 last_speaker 物件的屬性
        # 因為 last_speaker 物件可能有不同的名稱表示方式
        last_speaker_name = last_message.get('name', '')
        
        if not last_speaker_name:
            # 備用方案：從 last_speaker 物件獲取
            if hasattr(last_speaker, 'name'):
                last_speaker_name = last_speaker.name
            else:
                last_speaker_name = str(last_speaker)

        print(f"[StateTransition] last_speaker: {last_speaker_name}")
        print(f"[StateTransition] last_content: {str(last_content)[:200]}...")

        # --- 會話狀態優先機制（若 session 設定為 constraint_customization，則固定交給該 agent） ---
        conv_state = cl.user_session.get("conversation_state", "initial")
        print(f"[StateTransition] [debug] conversation_state: {conv_state}")
        print(f"[StateTransition] [debug] last_speaker_name type: {type(last_speaker_name)}, value: '{last_speaker_name}'")
        if conv_state == "constraint_customization":
            # agent 自行負責交互直到明確結束（agent 必須輸出結束標記）
            # 區分三種終止情況（由 LLM 在回應末尾添加標記）：
            # 1. 【約束設置完成】+ 工具呼叫 → 交給 user_proxy 執行工具
            # 2. 【退出自定義】 → 直接交給 host_agent 並恢復初始狀態
            # 3. 其他情況 → 繼續交給 constraint_customization_agent，由 LLM 決定是否等待用戶輸入
            
            if last_speaker_name == "constraint_customization_agent":
                # constraint_customization_agent 應該總是输出标记（【待確認約束】、【需要澄清】、【約束設置完成】、【退出自定義】）
                # 並且必須跟著 TERMINATE 來停止對話
                # ⭐ 先檢查是否有工具呼叫（優先級最高）
                if isinstance(last_message, dict) and "tool_calls" in last_message and last_message["tool_calls"]:
                    print("[StateTransition] ✅ constraint_customization_agent 有工具呼叫，轉交 user_proxy 執行")
                    return self.user_proxy.get_proxy()
    
                # ⭐ 關鍵檢查：檢查是否有任何結束標記
                has_end_marker = isinstance(last_content, str) and any(
                    tag in str(last_content) 
                    for tag in ["【待確認約束】", "【需要澄清】", "【約束設置完成】", "【退出自定義】"]
                )
                
                # ⭐ 新增：檢查是否是工具執行完後呈現的結果（無標記但有求解結果）
                is_result_presentation = isinstance(last_content, str) and (
                    "求解" in str(last_content) or 
                    "已應用" in str(last_content) or 
                    "已成功" in str(last_content) or
                    "繼續調整" in str(last_content) or
                    "下一步" in str(last_content)
                )
                
                if not has_end_marker and not is_result_presentation:
                    # ⚠️ Agent 既沒有標記也沒有呈現結果，檢查是否無限循環
                    agent_call_count = 0
                    for msg in reversed(named_messages):
                        if msg.get("name") == "constraint_customization_agent":
                            agent_call_count += 1
                        else:
                            break
                    
                    if agent_call_count >= 3:
                        # ⚠️ 偵測到無限循環
                        print(f"[StateTransition] ⚠️ constraint_customization_agent 已連續調用 {agent_call_count} 次，強制停止")
                        return None
                    
                    # 如果只調用了 1-2 次，再給一次機會
                    print(f"[StateTransition] ⚠️ constraint_customization_agent 未輸出標記或結果（調用 {agent_call_count} 次），再調用一次")
                    return self._get_autogen_agent_by_name("constraint_customization_agent")
                
                # ✅ Agent 有輸出標記或呈現了結果，現在檢查具體情況
                
                # 1️⃣ 待確認約束 或 需要澄清 → 停止對話，等待用戶在 Chainlit UI 輸入
                if "【待確認約束】" in str(last_content) or "【需要澄清】" in str(last_content):
                    print("[StateTransition] ✅ constraint_customization_agent 輸出了確認標記，停止對話等待用戶輸入")
                    return None
                
                # 2️⃣ 約束設置完成 → 準備執行工具或停止對話
                if "【約束設置完成】" in str(last_content):
                    # 檢查是否有工具呼叫
                    if isinstance(last_message, dict) and "tool_calls" in last_message and last_message["tool_calls"]:
                        print("[StateTransition] ✅ 約束設置完成且有工具呼叫，轉交 user_proxy 執行")
                        return self.user_proxy.get_proxy()
                    print("[StateTransition] ✅ 約束設置完成，停止對話等待用戶確認")
                    return None
                
                # 3️⃣ 進行深度分析比較 → 轉給 deep_analysis_agent
                if "進行深度分析比較" in str(last_content) or "進行分析比較" in str(last_content) or "深度分析比較" in str(last_content):
                    print("[StateTransition] ✅ 用戶要求進行深度分析比較，轉給 deep_analysis_agent")
                    return self._get_autogen_agent_by_name("deep_analysis_agent")
                
                # 4️⃣ 退出自定義 → 轉給 host_agent，恢復初始狀態
                if "【退出自定義】" in str(last_content):
                    print("[StateTransition] ✅ 用戶退出自定義，恢復初始狀態並轉給 host_agent")
                    cl.user_session.set("conversation_state", "initial")
                    return self._get_autogen_agent_by_name("host_agent")
                
                # 預設：停止對話，等待用戶輸入
                print("[StateTransition] ✅ constraint_customization_agent 已發出提示，停止對話等待用戶輸入")
                return None

            # 若非 constraint_customization_agent 發言但仍在此狀態，檢查是否是 user_proxy
            print(f"[StateTransition] [debug] 未進入 constraint_customization_agent 分支，last_speaker_name='{last_speaker_name}'")
            
            # ⭐ 特殊情況：user_proxy 在 constraint_customization 狀態下的輸入
            if last_speaker_name == "user_proxy":
                print(f"[StateTransition] [debug] constraint_customization 狀態下收到 user_proxy 輸入")
                
                # 檢查前一個發言者
                if len(named_messages) >= 2:
                    previous_agent_name = named_messages[-2].get('name')
                    print(f"[StateTransition] [debug] 前一個發言者: {previous_agent_name}")
                    
                    # 如果前一個是 constraint_customization_agent，檢查該消息是否包含【退出自定義】
                    if previous_agent_name == "constraint_customization_agent":
                        previous_message_content = named_messages[-2].get('content', '')
                        if isinstance(previous_message_content, str) and '【退出自定義】' in previous_message_content:
                            print(f"[StateTransition] [debug] 檢測到前一個消息包含【退出自定義】，改變狀態為 'initial'")
                            cl.user_session.set("conversation_state", "initial")
                            print(f"[StateTransition] ✅ constraint_customization_agent 已輸出【退出自定義】，轉給 host_agent")
                            return self._get_autogen_agent_by_name("host_agent")
                    
                    # 檢查是否是工具結果
                    is_tool_result = isinstance(last_content, dict) and 'status' in last_content
                    
                    if is_tool_result:
                        print(f"[StateTransition] User proxy 執行完自定義約束工具，返回 constraint_customization_agent 呈現結果")
                        return self._get_autogen_agent_by_name("constraint_customization_agent")
                
                # 預設：user_proxy 的新輸入交給 constraint_customization_agent 處理
                print("[StateTransition] user_proxy 輸入轉給 constraint_customization_agent 判斷")
                return self._get_autogen_agent_by_name("constraint_customization_agent")
            
            print("[StateTransition] 未知發言者，交由 constraint_customization_agent 繼續")
            return self._get_autogen_agent_by_name("constraint_customization_agent")

        # --- Host agent 關鍵標記處理（保留既有行為） ---
        if last_speaker_name == "host_agent":
            # 深入分析
            if "【啟動深入分析】" in last_content:
                print(f"[StateTransition] 偵測到深入分析需求，轉交給 deep_analysis_agent")
                return self._get_autogen_agent_by_name("deep_analysis_agent")

            # Host 顯式要求啟動自定義約束（Host 負責決定何時輸出此標記）
            if "【啟動自定義約束】" in last_content or "啟動自定義約束" in last_content:
                print(f"[StateTransition] 偵測到自定義約束需求（Host 觸發），切換會話狀態並轉交 constraint_customization_agent")
                cl.user_session.set("conversation_state", "constraint_customization")
                
                # ⭐ 在轉交前，注入完整的變數列表到聊天消息
                print("[StateTransition] 準備注入變數列表...")
                self._update_constraint_agent_with_variables()
                print(f"[StateTransition] 注入完成，group_chat.messages 總數: {len(self.group_chat.messages)}")
                
                return self._get_autogen_agent_by_name("constraint_customization_agent")

            # 若 Host 顯示要確認自定義（相容舊標記）
            if "【確認自定義約束】" in last_content:
                print(f"[StateTransition] 自定義約束已確認（Host 標記），轉交給 constraint_customization_agent")
                cl.user_session.set("conversation_state", "constraint_customization")
                return self._get_autogen_agent_by_name("constraint_customization_agent")

            # 案例搜索 / 法條搜索
            if "【啟動案例分析】" in last_content:
                print(f"[StateTransition] 偵測到明確的案例分析啟動標記，轉交給 search_agent")
                return self._get_autogen_agent_by_name("search_agent")

            if "【啟動法條搜索】" in last_content:
                print(f"[StateTransition] 偵測到明確的法條搜索啟動標記，轉交給 legal_retrieval_agent")
                return self._get_autogen_agent_by_name("legal_retrieval_agent")

            # 若有結構化工具呼叫（tool_calls）
            if isinstance(last_message, dict) and "tool_calls" in last_message and last_message["tool_calls"]:
                print(f"[StateTransition] 偵測到結構化工具呼叫，轉交給 user_proxy")
                return self.user_proxy.get_proxy()

            if last_content and ("Suggested tool call" in str(last_content) or "tool_calls" in str(last_content) or "Calling function:" in str(last_content)):
                print(f"[StateTransition] 偵測到工具呼叫訊息，轉交給 user_proxy")
                return self.user_proxy.get_proxy()

            # 若 host 在等待用戶確認（保留按鈕等待行為）
            waiting_tags = ["【等待法條確認】", "【等待案例確認】", "【等待深入分析確認】", "【等待自定義狀態確認】",
                            "[等待法條確認]", "[等待案例確認]", "[等待深入分析確認]", "[等待自定義狀態確認]"]
            if any(tag in str(last_content) for tag in waiting_tags):
                print(f"[StateTransition] 等待使用者確認操作，停止對話等待用戶輸入")
                return None

            # 檢查 host 是否在詢問用戶是否希望自定義狀態（隱含的等待狀態）
            if "是否希望自定義調整企業狀態" in str(last_content) or "是否想自定義" in str(last_content) or "是否希望自定義" in str(last_content):
                print(f"[StateTransition] Host 詢問用戶是否自定義，停止對話等待用戶回應")
                return None

            # 其餘 host 回應：停止對話，等待用戶的下一步輸入
            print(f"[StateTransition] Host 完成回應，停止對話等待用戶的下一步輸入")
            return None

        # --- user_proxy 回傳後的路由（工具執行結果處理） ---
        print(f"[StateTransition] [debug] Checking user_proxy routing: last_speaker_name='{last_speaker_name}' (type: {type(last_speaker_name)})")
        if last_speaker_name == "user_proxy":
            print(f"[StateTransition] [debug] ✅ Entered user_proxy routing block")
            # ⭐ 如果 user_proxy 是初始消息（例如"你好"），交給 host_agent 處理
            if len(named_messages) == 1 and last_speaker_name == "user_proxy":
                print(f"[StateTransition] user_proxy 初始消息，交給 host_agent 處理用戶查詢")
                return self._get_autogen_agent_by_name("host_agent")
            
            # ⭐ 檢查前一個說話者是否是 constraint_customization_agent（不論當前狀態）
            # 這樣即使【退出自定義】已經改變了狀態，仍然能正確處理
            if len(named_messages) >= 2:
                previous_agent_name = named_messages[-2].get('name')
                print(f"[StateTransition] [debug] 前一個發言者: {previous_agent_name}")
                
                # 如果前一個是 constraint_customization_agent，檢查是用戶輸入還是工具結果
                if previous_agent_name == "constraint_customization_agent":
                    # ⭐ 先檢查前一個 constraint_customization_agent 的消息是否包含【退出自定義】
                    # 如果包含，說明已經退出了，不應該再轉回去
                    previous_message_content = named_messages[-2].get('content', '')
                    if isinstance(previous_message_content, str) and '【退出自定義】' in previous_message_content:
                        print(f"[StateTransition] ✅ constraint_customization_agent 已輸出【退出自定義】，用戶新輸入應轉給 host_agent")
                        return self._get_autogen_agent_by_name("host_agent")
                    
                    # 檢查是否是工具結果（包含 'status' 等鍵值）
                    is_tool_result = isinstance(last_content, dict) and 'status' in last_content
                    
                    if is_tool_result:
                        # 工具執行結果，返回給 constraint_customization_agent 呈現結果
                        print(f"[StateTransition] User proxy 執行完自定義約束工具，返回 constraint_customization_agent 呈現結果")
                        return self._get_autogen_agent_by_name("constraint_customization_agent")
                    else:
                        # 用戶輸入（「繼續調整」、「退出」等），需要讓 constraint_customization_agent 判斷
                        # 但先檢查對話狀態：如果已經不在 constraint_customization 狀態，說明已經退出過但沒有顯示標記
                        conv_state = cl.user_session.get("conversation_state", "initial")
                        if conv_state != "constraint_customization":
                            # 狀態已改為 initial，說明已經完成自定義，轉給 host_agent
                            print(f"[StateTransition] 對話狀態已為 {conv_state}，用戶新輸入轉給 host_agent")
                            return self._get_autogen_agent_by_name("host_agent")
                        
                        # 還在 constraint_customization 狀態，轉回 constraint_customization_agent 判斷
                        print(f"[StateTransition] 用戶輸入轉給 constraint_customization_agent 判斷意圖")
                        return self._get_autogen_agent_by_name("constraint_customization_agent")
            
            # ⭐ 檢查是否在 constraint_customization 狀態且等待用戶輸入
            conv_state = cl.user_session.get("conversation_state", "initial")
            if conv_state == "constraint_customization":
                # 檢查前一個說話者是否是 constraint_customization_agent
                if len(named_messages) >= 2:
                    previous_agent_name = named_messages[-2].get('name')
                    if previous_agent_name == "constraint_customization_agent":
                        print(f"[StateTransition] ⭐ constraint_customization_agent 等待中，user_proxy 回應，停止對話")
                        return None
            
            # 深入分析工具剛執行完，回到 deep_analysis_agent 產生最終回應
            if isinstance(last_content, str) and ("📊 深入分析報告" in last_content or "⚠️ 需要變更" in last_content or "✅ 維持現狀" in last_content):
                if len(named_messages) >= 2:
                    previous_agent_name = named_messages[-2].get('name')
                    if previous_agent_name == "deep_analysis_agent":
                        print(f"[StateTransition] User proxy 返回深入分析工具結果，切換回 deep_analysis_agent 生成最終回應")
                        return self._get_autogen_agent_by_name("deep_analysis_agent")
                print(f"[StateTransition] 深入分析工具執行完成，結束對話等待用戶新查詢")
                return None

            # 一般工具結果回傳後根據 previous_agent_name 決定下一個 agent
            if last_content and not any(keyword in str(last_content) for keyword in ["Suggested tool call", "Calling function:", "TERMINATE"]):
                if len(named_messages) >= 2:
                    previous_agent_name = named_messages[-2].get('name')
                    if previous_agent_name == "host_agent":
                        print(f"[StateTransition] User proxy 執行完 host 的工具，返回 host_agent")
                        return self._get_autogen_agent_by_name("host_agent")
                    elif previous_agent_name == "search_agent":
                        print(f"[StateTransition] User proxy 執行完搜尋，轉給 summary_agent 生成摘要")
                        return self._get_autogen_agent_by_name("summary_agent")
                    elif previous_agent_name == "code_executor":
                        print(f"[StateTransition] User proxy 執行完程式碼，返回 code_executor")
                        return self._get_autogen_agent_by_name("code_executor")
                    elif previous_agent_name == "deep_analysis_agent":
                        print(f"[StateTransition] User proxy 執行完深入分析工具，切換回 deep_analysis_agent")
                        return self._get_autogen_agent_by_name("deep_analysis_agent")
            else:
                print(f"[StateTransition] User proxy 一般回應，轉交給 host_agent")
                return self._get_autogen_agent_by_name("host_agent")
        
        # --- user_input_proxy 回傳後的路由（等待用戶輸入的結果） ---
        # 注意：由於改為 human_input_mode="NEVER"，user_input_proxy 不會被狀態轉換選中
        # 用戶輸入現在通過 Chainlit UI 的 @cl.on_message() 進行處理

        # --- summary_agent / deep_analysis_agent 既有處理（保留） ---
        if last_speaker_name == "summary_agent":
            # 情況1：摘要生成完成且找到相關案例 ✅
            if "SUMMARY_COMPLETE" in str(last_content) or "【等待深入分析確認】" in str(last_content):
                print(f"[StateTransition] 摘要生成完成，停止對話等待用戶確認是否深入分析")
                return None
            
            # 情況2：搜索結果無關 - 交給 HostAgent 決定後續
            # 由 LLM 輸出標記供 HostAgent 判斷
            if "【建議重新搜索】" in str(last_content) or "【建議進行分析】" in str(last_content) or "【建議結束】" in str(last_content):
                print(f"[StateTransition] SummaryAgent 判斷搜索結果無關，轉交 HostAgent 決定後續")
                return self._get_autogen_agent_by_name("host_agent")
            
            # 情況3：其他情況（包括無相關案例的抱歉說明）
            # 停止對話，等待用戶回應下一步意願
            if "抱歉，目前找不到" in str(last_content) or "無相關案例" in str(last_content):
                print(f"[StateTransition] SummaryAgent 告知無相關案例，停止對話等待用戶決定")
                return None
            
            # 預設：結束對話
            print(f"[StateTransition] SummaryAgent 完成，結束對話")
            return None

        if last_speaker_name == "deep_analysis_agent":
            if ("ANALYSIS_COMPLETE" in str(last_content) or "分析報告" in str(last_content) or "📊 深入分析報告" in str(last_content) or "⚠️ 需要變更" in str(last_content) or "✅ 維持現狀" in str(last_content)):
                if "[當前狀態:等待自定義狀態確認]" in str(last_content):
                    print(f"[StateTransition] 深入分析報告已完成並包含自定義確認標記，停止對話等待用戶選擇")
                    return None
                else:
                    print(f"[StateTransition] 深入分析報告已完成但無確認標記，結束對話")
                    return None
            return self.user_proxy.get_proxy()

        # --- constraint_customization_agent 結束判定（一般情況） ---
        if last_speaker_name == "constraint_customization_agent":
            # 如果 agent 輸出工具呼叫或確認標記，交由 user_proxy 執行工具
            if isinstance(last_message, dict) and ("tool_calls" in last_message and last_message["tool_calls"]):
                print(f"[StateTransition] 自定義約束已確認（結構化呼叫），轉交給 user_proxy 執行工具")
                return self.user_proxy.get_proxy()
            if isinstance(last_content, str) and ("Calling function:" in last_content or "【確認自定義約束】" in last_content or "【約束設置完成】" in last_content):
                print(f"[StateTransition] 自定義約束已確認（文本呼叫），轉交給 user_proxy 執行工具")
                return self.user_proxy.get_proxy()

            # 如果 agent 輸出了等待標記，停止對話等待用戶輸入
            if "【待確認約束】" in str(last_content) or "【需要澄清】" in str(last_content):
                print(f"[StateTransition] ✅ constraint_customization_agent 輸出了標記，停止對話等待用戶輸入")
                # 返回 None 表示停止對話
                return None
            
            # 如果 agent 還在列出/引導，則停等使用者回應
            if "已設置的自定義約束" in str(last_content) or "請選擇要調整的變數" in str(last_content) or "請問您要調整" in str(last_content):
                print(f"[StateTransition] constraint_customization_agent 等待用戶輸入或確認，停止對話")
                return None

            # 否則預設停止等待
            print(f"[StateTransition] 自定義約束 Agent 提示已發出，停止對話等待用戶輸入")
            return None

        # --- Code Executor / Default fallback ---
        if last_speaker_name == "code_executor":
            if "EXECUTION_COMPLETE" in str(last_content):
                print(f"[StateTransition] 給host agent 進行後續分析")
                return self._get_autogen_agent_by_name("host_agent")

        print(f"[StateTransition] 使用自動選擇")
        return "auto"

    def _get_agent_by_name(self, name: str):
        """根據名稱取得 Agent 實例"""
        # 優先從 BaseAgent 實例中查找
        for agent in self.agents:
            if agent.name == name:
                return agent
        
        # 如果找不到，則從 AutoGen agent 實例中查找
        for agent_instance in self.agent_instances:
            if hasattr(agent_instance, 'name') and agent_instance.name == name:
                return agent_instance
        return None
    
    def _get_autogen_agent_by_name(self, name: str):
        """根據名稱取得 AutoGen Agent 實例（用於 GroupChat speaker selection）"""
        # 優先從 BaseAgent 實例中查找並獲取 AutoGen agent
        for agent in self.agents:
            if agent.name == name:
                return agent.get_agent()
        
        # 如果找不到，則從 AutoGen agent 實例中查找
        for agent_instance in self.agent_instances:
            if hasattr(agent_instance, 'name') and agent_instance.name == name:
                return agent_instance
        return None
    
    def _extract_and_store_case_id(self, message_content: str) -> Optional[str]:
        """
        從消息內容中提取 case_id 並存儲到 session
        格式: 【⭐ 案例 ID: case_X 】
        
        Args:
            message_content: 消息內容
            
        Returns:
            提取到的 case_id，如果未找到則返回 None
        """
        import re
        import chainlit as cl
        
        if not isinstance(message_content, str):
            return None
        
        # 查找格式: 【⭐ 案例 ID: case_X 】 或其他變體
        patterns = [
            r'【⭐\s*案例\s*ID:\s*(\w+)\s*】',
            r'案例 ID:\s*(\w+)',
            r'case_id:\s*(\w+)',
            r'case_id = "(\w+)"'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, message_content)
            if match:
                case_id = match.group(1)
                if case_id.startswith('case_'):
                    stored_case_id = case_id
                else:
                    stored_case_id = f'case_{case_id}'
                
                # 存儲到 session
                cl.user_session.set("current_case_id", stored_case_id)
                print(f"[ChatManager] ✅ 從消息中提取並存儲 case_id: {stored_case_id}")
                return stored_case_id
        
        return None
    
    def _inject_variables_context_to_group_chat(self):
        """
        向群組對話注入變數列表上下文
        這樣 constraint_customization_agent 可以根據真實的分析結果展示變數
        """
        import chainlit as cl
        
        try:
            # 從會話中獲取最新的深入分析結果
            latest_analysis = cl.user_session.get("latest_deep_analysis_result")
            
            print(f"[ChatManager] 嘗試注入變數上下文，latest_analysis: {latest_analysis is not None}")
            
            if not latest_analysis:
                print("[ChatManager] ❌ 沒有找到分析結果，跳過變數注入")
                return
            
            print(f"[ChatManager] ✅ 找到分析結果，controllable_changes 數量: {len(latest_analysis.get('controllable_changes', []))}")
            
            # 提取原始的可調整變數列表（保持英文，由 constraint_customization_agent 負責翻譯）
            controllable_changes = latest_analysis.get("controllable_changes", [])
            
            # 格式化為簡單的英文表格（agent 會自己翻譯）
            variables_lines = ["| Variable Name | From | To |", "|---|---|---|"]
            for var_info in controllable_changes:
                var_name = var_info.get("name", "unknown")
                from_val = var_info.get("from", "N/A")
                to_val = var_info.get("to", "N/A")
                variables_lines.append(f"| {var_name} | {from_val} | {to_val} |")
            
            variables_table = "\n".join(variables_lines)
            
            print(f"[ChatManager] 原始英文變數表:\n{variables_table[:200]}...")
            
            # 向群組對話添加一條消息，包含變數列表（英文原始數據）
            # 由 constraint_customization_agent 負責翻譯成中文
            context_message = {
                "role": "user",
                "content": f"""【系統上下文：可調整變數列表】

以下是本次深入分析中發現的原始可調整變數列表（英文）：

{variables_table}

請根據這些原始變數數據，翻譯成中文後展示給用戶，協助用戶進行自定義設置。""",
                "name": "chat_manager"  # ⭐ 改為 chat_manager，這樣就不會被過濾掉
            }
            
            self.group_chat.messages.append(context_message)
            print(f"[ChatManager] ✅ 已向群組對話注入變數列表上下文 (訊息總數: {len(self.group_chat.messages)})")
        
        except Exception as e:
            import traceback
            print(f"[ChatManager] ❌ 注入變數上下文時出錯: {str(e)}")
            traceback.print_exc()
    
    def _update_constraint_agent_with_variables(self):
        """
        直接在聊天消息中注入完整的變數列表和 case_id
        同時注入原始的 Z3 求解結果（initial_facts 和 suggested_model）
        確保 constraint_customization_agent 能看到完整的數據
        """
        import chainlit as cl
        import json
        
        try:
            # 第一步：從會話中獲取原始 Z3 求解結果
            z3_result = cl.user_session.get("latest_z3_solving_result")
            latest_analysis = cl.user_session.get("latest_deep_analysis_result")
            
            if not z3_result or not z3_result.get("initial_facts"):
                print("[ChatManager] ❌ 沒有找到 Z3 求解結果，無法注入完整數據")
                return
            
            # 提取數據
            case_id = z3_result.get("case_id")
            initial_facts = z3_result.get("initial_facts", {})
            suggested_model = z3_result.get("suggested_model", {})
            
            if not case_id:
                print("[ChatManager] ❌ 無法提取 case_id")
                return
            
            print(f"[ChatManager] ✅ 找到 case_id: {case_id}")
            print(f"[ChatManager] ✅ Z3 初始事實數據包含 {len(initial_facts)} 個變數")
            print(f"[ChatManager] ✅ Z3 建議模型包含 {len(suggested_model)} 個變數")
            
            # 第二步：獲取結構化的可調整變數列表
            controllable_changes = latest_analysis.get("controllable_changes", []) if latest_analysis else []
            variable_count = len(controllable_changes)
            
            print(f"[ChatManager] ✅ 獲得 {variable_count} 個可調整變數")
            
            # 第三步：生成完整的數據消息
            # 包含：case_id, initial_facts, suggested_model, 以及人類可讀的變數表格
            
            # 直接從 Z3 結果中動態生成變數表格（不硬編碼翻譯）
            variables_lines = ["| 變數名稱 | 當前值 | 建議值 |", "|---|---|---|"]
            for var_info in controllable_changes:
                var_name = var_info.get("name", "unknown")
                from_val = var_info.get("from", "N/A")
                to_val = var_info.get("to", "N/A")
                
                variables_lines.append(f"| {var_name} | {from_val} | {to_val} |")
            
            variables_table = "\n".join(variables_lines)
            
            # 構建簡潔的消息 - 直接提供變數列表和 Z3 原始數據
            variable_list_text = f"""⭐⭐⭐ 【本次案例 ID】⭐⭐⭐
案例 ID: {case_id}
變數總數: {variable_count} 個

【所有可調整的變數及其當前值 → 建議值】

{variables_table}

【完整 Z3 初始事實（initial_facts）】
```json
{json.dumps(initial_facts, ensure_ascii=False, indent=2)}
```

【完整 Z3 建議模型（suggested_model）】
```json
{json.dumps(suggested_model, ensure_ascii=False, indent=2)}
```

【說明】
您看到的表格包含了本次 Z3 求解結果中的所有 {variable_count} 個可調整變數。
每個變數顯示了：
- 變數名稱（英文）
- 當前值（Z3 初始狀態，來自 initial_facts）
- 建議值（Z3 優化後建議，來自 suggested_model）

同時提供了完整的 JSON 數據，以便查看所有細節。

【約束類型說明】
1. FIX：變數固定為某個具體值
2. LOWER_BOUND：變數不可低於某個值
3. UPPER_BOUND：變數不可高於某個值
4. RANGE：變數必須在上下界之間

【接下來】
您可以：
1. 要求查看所有變數（已顯示在上表）
2. 對某個變數設定約束
3. 或提出其他需求

⚠️ 【重要】當調用工具時，case_id 會自動使用：{case_id}，您無需擔心。"""

            variable_message = {
                "role": "user",  # ⭐ 改為 "user" 角色，確保 AutoGen 正確保留
                "name": "user_proxy",
                "content": variable_list_text
            }
            
            # 在聊天歷史中插入這個消息
            self.group_chat.messages.append(variable_message)
            print(f"[ChatManager] ✅ 已向群組對話注入完整 Z3 求解結果和變數列表 ({variable_count} 個變數，case_id: {case_id})")
            print(f"[ChatManager] 📝 constraint_customization_agent 現在可以訪問完整的初始事實和建議模型數據")
        
        except Exception as e:
            import traceback
            print(f"[ChatManager] ❌ 執行求解或注入變數時出錯: {str(e)}")
            traceback.print_exc()
    


    # -------------------------------------------------------------
    # 入口：啟動帶有串流輸出的群組對話
    # -------------------------------------------------------------
    async def initiate_chat_with_streaming(
        self,
        message: str,
        stream_delay: float = 0.001
    ):   
        """
        最終重構版本 — 支援 AutoGen GroupChat + Chainlit Streaming
        內容包含：
        ✔ constraint_customization_agent 停等邏輯
        ✔ host_agent 停等邏輯（法條 / 案例 / 深入分析）
        ✔ 工具呼叫等待＆工具結果顯示
        ✔ 摘要／深入分析的「📤 上傳」按鈕
        ✔ 正常 Agent 訊息串流輸出
        ✔ 不顯示五筆記憶、不插入 context_summary
        """
        import chainlit as cl
        import asyncio

        conversation_state = cl.user_session.get("conversation_state", "initial")

        # 1. 產生實際要送給 AutoGen 的訊息（不再加五條對話）
        enhanced_message = self._prepare_user_message(message, conversation_state)

        # 2. 檢查是否有 direct-response 工具（例如清除按鈕之類）
        direct = await self._check_direct_response(message)
        if direct:
                return direct

        try:
            # -------------------------------------------------------------
            # 啟動 AutoGen 的 initiate_chat（在背景 thread 跑）
            # -------------------------------------------------------------
            start_cnt = len(self.group_chat.messages)

            chat_task = asyncio.create_task(
                asyncio.to_thread(
                    self.user_proxy.get_proxy().initiate_chat,
                    self.manager,
                    message=enhanced_message,
                    clear_history=False
                )
            )
            self.current_chat_task = chat_task

            processed = set()
            current_tool_msg = None
            tool_agent_name = None

            # -------------------------------------------------------------
            # 主輪詢：每 0.2s 檢查 GroupChat 是否有新訊息
            # -------------------------------------------------------------
            while not chat_task.done():
                await asyncio.sleep(0.2)

                all_msgs = self.group_chat.messages
                cur_cnt = len(all_msgs)

                if cur_cnt > start_cnt:
                    # 處理所有新增的項目
                    for idx in range(start_cnt, cur_cnt):
                        if idx in processed:
                            continue
                        msg = all_msgs[idx]
                        agent = msg.get("name", "")
                        content_raw = msg.get("content", "")
                        content = "" if content_raw is None else str(content_raw)

                        # -----------------------------
                        # trash message 過濾
                        # -----------------------------
                        if self._is_trash_message(agent, content):
                            processed.add(idx)
                            continue

                        # -----------------------------
                        # 處理工具呼叫
                        # -----------------------------
                        if self._is_tool_call_message(msg):
                            processed.add(idx)
                            tool_agent_name = agent
                            current_tool_msg = await self._show_tool_waiting(agent)
                            continue

                        # -----------------------------
                        # 工具執行結果（發送者是 user_proxy，且有 pending tool）
                        # -----------------------------
                        if agent == "user_proxy" and current_tool_msg:
                            processed.add(idx)
                            await self._handle_tool_result(
                                agent_name=tool_agent_name,
                                content=content,
                                current_tool_msg=current_tool_msg,
                                tool_sources=None
                            )
                            tool_agent_name = None
                            current_tool_msg = None
                            continue
                        
                        # -----------------------------
                        # user_proxy 的一般訊息：不顯示在 UI
                        # -----------------------------
                        if agent == "user_proxy":
                            processed.add(idx)
                            continue
                        # -----------------------------
                        # constraint_customization_agent 特殊邏輯
                        # -----------------------------
                        if agent == "constraint_customization_agent":
                            # ★ 先把訊息顯示給前端（stream）
                            await self._stream_normal_agent_message(agent, content, stream_delay)
                            processed.add(idx)

                            # ★ 若有 tag → 停止等待使用者
                            if any(t in content for t in ["【需要澄清】", "【待確認約束】", "【約束設置完成】", "【退出自定義】"]):
                                print("[STREAM] 偵測到自定義約束 tag → 停止 AutoGen 等待使用者輸入")
                                # 不 return None（會讓結果=none），只 break 跳出 while
                                break

                            continue
                        # -----------------------------
                        # host_agent 停等（法條／案例／深入分析）
                        # -----------------------------
                        if agent == "host_agent" and self._has_waiting_confirmation_tag(content):
                            processed.add(idx)
                            await self._show_waiting_confirmation(agent, content)
                            continue

                        # -----------------------------
                        # 上傳按鈕相關（摘要／深入分析）
                        # -----------------------------
                        if await self._handle_upload_buttons_if_any(agent, content):
                            processed.add(idx)
                            continue

                        # -----------------------------
                        # 一般 agent 訊息串流
                        # -----------------------------
                        processed.add(idx)
                        await self._stream_normal_agent_message(agent, content, stream_delay)

                    start_cnt = cur_cnt

            # -------------------------------------------------------------
            # 任務完成後取回結果
            # -------------------------------------------------------------
            chat_result = await chat_task
            self.current_chat_task = None

            return await self._process_chat_result(chat_result)

        except Exception as e:
            import traceback
            err = traceback.format_exc()
            print(err)
            return self._empty_result(str(e))

    # -------------------------------------------------------------
    # Helper: 準備送給 AutoGen 的使用者訊息（移除五筆記憶）
    # -------------------------------------------------------------
    def _prepare_user_message(self, message, state):
        if state == "constraint_customization":
            return message

        waiting = [
            "waiting_for_legal_content",
            "waiting_for_case_content",
            "waiting_for_legal_confirmation",
            "waiting_for_case_confirmation",
            "waiting_for_deep_analysis_confirmation"
        ]
        if state in waiting:
            return f"[當前狀態:{state}] {message}"

        return message

    # -------------------------------------------------------------
    # Helper: 過濾垃圾訊息
    # -------------------------------------------------------------
    def _is_trash_message(self, agent, content):
        if not content or not content.strip():
            return True
        if content.strip().lower() == "none":
            return True
        if agent == "code_executor" and "EXECUTION_COMPLETE" not in content:
            return True
        return False

    # -------------------------------------------------------------
    # Helper: 是否為工具呼叫
    # -------------------------------------------------------------
    def _is_tool_call_message(self, msg):
        c = str(msg.get("content", "") or "")
        if "Tool:" in c or '"tool_name"' in c:
            return True
        if msg.get("tool", None):
            return True
        return False

    # -------------------------------------------------------------
    # Helper: 顯示工具使用中
    # -------------------------------------------------------------
    async def _show_tool_waiting(self, agent):
        import chainlit as cl
        m = cl.Message(content="🔧 **正在使用工具**\n\n⏳ 處理中，請稍候...")
        await m.send()
        return m

    # -------------------------------------------------------------
    # Helper: 工具結果輸出
    # -------------------------------------------------------------
    async def _handle_tool_result(self, agent_name, content, current_tool_msg, tool_sources):
        import chainlit as cl

        if not content:
            current_tool_msg.content = "⚠️ 工具未返回結果"
            await current_tool_msg.update()
            return

        # 深入分析報告：直接顯示 + 按鈕
        if agent_name == "deep_analysis_agent" and (
            "📊" in content or "需要變更" in content or "維持現狀" in content
        ):
            current_tool_msg.content = f"✅ 工具執行完成\n\n{content}"
            await current_tool_msg.update()

            # ⭐ 保存報告內容到 session，供上傳按鈕使用
            cl.user_session.set("current_analysis_report", content)
            print(f"[ChatManager] ✅ 已保存深入分析報告到 session，長度: {len(content)} 字符")

            upload = cl.Action(
                name="upload_analysis_report",
                label="📤 上傳報告",# 📤 上傳報告
                payload={"action": "upload"}
            )
            current_tool_msg.actions = [upload]
            await current_tool_msg.update()
            return

        # 自定義約束工具執行結果：直接顯示 + 按鈕
        if agent_name == "constraint_customization_agent" and (
            "✅" in content or "已完成" in content or "求解" in content
        ):
            current_tool_msg.content = f"✅ 工具執行完成\n\n{content}"
            await current_tool_msg.update()

            # ⭐ 保存報告內容到 session，供上傳按鈕使用
            cl.user_session.set("current_analysis_report", content)
            print(f"[ChatManager] ✅ 已保存自定義約束執行報告到 session，長度: {len(content)} 字符")

            upload = cl.Action(
                name="upload_analysis_report",
                label="📤 上傳報告",#📤 上傳報告
                payload={"action": "upload"}
            )
            current_tool_msg.actions = [upload]
            await current_tool_msg.update()
            return

        # 一般工具輸出右側
        current_tool_msg.content = "✅ 工具執行完成\n\n📄 結果已儲存，右側查看"
        await current_tool_msg.update()

        side = cl.Text(
            name=f"{agent_name}_result",
            content=str(content),
            display="side"
        )
        await side.send(for_id=current_tool_msg.id)

    # -------------------------------------------------------------
    # Helper: constraint_customization_agent 的四個 tag（不顯示）
    # -------------------------------------------------------------
    def _handle_constraint_state(self, content, cl):
        tags = ["【需要澄清】", "【待確認約束】", "【約束設置完成】", "【退出自定義】"]
        return any(tag in content for tag in tags)

    def _get_constraint_marker(self, content):
        tags = ["【需要澄清】", "【待確認約束】", "【約束設置完成】", "【退出自定義】"]
        for t in tags:
            if t in content:
                return t
        return None
    # -------------------------------------------------------------
    # Helper: host_agent 停等標記
    # -------------------------------------------------------------
    def _has_waiting_confirmation_tag(self, content):
        tags = ["等待法條確認", "等待案例確認", "等待深入分析確認"]
        return any(t in content for t in tags)

    # -------------------------------------------------------------
    # Helper: 等待確認 UI
    # -------------------------------------------------------------
    async def _show_waiting_confirmation(self, agent, content):
        import chainlit as cl

        msg = cl.Message(content=f"🤖 **{agent}**\n\n{content}")
        await msg.send()
        msg.actions = [
            cl.Action(name="confirm", label="✅ 是", payload={"action": "yes"}),
            cl.Action(name="cancel", label="❌ 否", payload={"action": "no"}),
        ]
        await msg.update()

    # -------------------------------------------------------------
    # Helper: 顯示摘要或深入分析的上傳按鈕
    # -------------------------------------------------------------
    async def _handle_upload_buttons_if_any(self, agent, content):
        import chainlit as cl

        # 深入分析
        if agent == "deep_analysis_agent" and (
            "📊" in content or "需要變更" in content or "維持現狀" in content
        ):
            msg = cl.Message(content=f"📊 **深入分析結果**\n\n{content}")
            await msg.send()

            # ⭐ 保存消息 ID 和內容
            cl.user_session.set("_last_agent_message_id", msg.id)
            cl.user_session.set("_last_agent_message_content", msg.content)
            # ⭐ 保存報告內容供上傳使用
            cl.user_session.set("current_analysis_report", content)
            print(f"[ChatManager] ✅ 已保存深入分析報告到 session，長度: {len(content)} 字符")

            msg.actions = [
                cl.Action(
                    name="upload_analysis_report",
                    label="📤 上傳報告", #
                    payload={"action": "upload"}
                )
            ]
            await msg.update()
            return True

        # 自定義約束執行結果
        if agent == "constraint_customization_agent" and (
            "重新求解" in content or "新模型" in content or "變數已更新" in content
        ):
            msg = cl.Message(content=f"⚙️ **自定義約束結果**\n\n{content}")
            await msg.send()

            # ⭐ 保存消息 ID 和內容
            cl.user_session.set("_last_agent_message_id", msg.id)
            cl.user_session.set("_last_agent_message_content", msg.content)
            # ⭐ 保存報告內容供上傳使用
            cl.user_session.set("current_analysis_report", content)
            print(f"[ChatManager] ✅ 已保存自定義約束報告到 session，長度: {len(content)} 字符")

            msg.actions = [
                cl.Action(
                    name="upload_analysis_report",
                    label="📤 上傳結果",
                    payload={"action": "upload"}
                )
            ]
            await msg.update()
            return True

        # 摘要
        if agent == "summary_agent" and "SUMMARY_COMPLETE" in content:
            msg = cl.Message(content=f"📝 **摘要完成**\n\n{content}")
            await msg.send()

            # ⭐ 保存消息 ID 和內容
            cl.user_session.set("_last_agent_message_id", msg.id)
            cl.user_session.set("_last_agent_message_content", msg.content)
            # ⭐ 保存摘要內容供上傳使用
            cl.user_session.set("current_summary", content)
            print(f"[ChatManager] ✅ 已保存摘要到 session，長度: {len(content)} 字符")

            msg.actions = [
                cl.Action(
                    name="upload_summary",
                    label="📤 上傳摘要",
                    payload={"action": "upload"}
                )
            ]
            await msg.update()
            return True

        return False

    # -------------------------------------------------------------
    # Helper: 一般 Agent 的串流輸出
    # -------------------------------------------------------------
    async def _stream_normal_agent_message(self, agent, content, delay):
        import chainlit as cl
        emoji = "🤖"
        text = f"{emoji} **{agent}**\n\n{content}"

        m = cl.Message(content="")
        await m.send()

        for ch in text:
            await m.stream_token(ch)
            await asyncio.sleep(delay)
        await m.update()

        # ⭐ 新增：保存最後一條消息 ID 和內容，供上傳按鈕使用
        cl.user_session.set("_last_agent_message_id", m.id)
        cl.user_session.set("_last_agent_message_content", text)

        # ⭐ 新增：檢測並保存深入分析報告和自定義約束報告
        if agent == "deep_analysis_agent":
            # 檢查是否包含深入分析報告的標籤
            if any(tag in content for tag in ["📊 深入分析報告", "⚠️ 需要變更", "✅ 維持現狀", "改善措施", "推薦狀態"]):
                cl.user_session.set("current_analysis_report", content)
                print(f"[ChatManager] ✅ 已保存深入分析報告到 session（來自 agent message），長度: {len(content)} 字符")
        
        if agent == "constraint_customization_agent":
            # 檢查是否包含約束設置完成的標籤
            if any(tag in content for tag in ["重新求解", "新模型", "變數已更新", "【約束設置完成】"]):
                cl.user_session.set("current_analysis_report", content)
                print(f"[ChatManager] ✅ 已保存自定義約束報告到 session（來自 agent message），長度: {len(content)} 字符")

    # -------------------------------------------------------------
    # Helper: 回傳空結果
    # -------------------------------------------------------------
    def _empty_result(self, err):
        return {
            "success": False,
            "error": err,
            "messages": {
                "host_responses": [],
                "search_results": [],
                "analysis_results": [],
                "system_messages": []
            }
        }
        
    def _is_tool_call_message(self, msg: dict) -> bool:
        """判斷訊息是否為工具呼叫"""
        # if not msg:
        #     return False

        # content = msg.get("content", "")
        # # 情況一：文字提示
        # if isinstance(content, str) and any(k in content for k in [
        #     "Suggested tool call",
        #     "Calling function",
        #     "TOOL CALL ID",
        #     "Executing function"
        # ]):
        #     return True
        
        # 情況二：JSON 結構化呼叫
        if "tool_calls" in msg and msg["tool_calls"]:
            return True
        content = str(msg)
        if not content or not isinstance(content, str):
            return False
        
        tool_call_keywords = [
            "Suggested tool call",
            "tool_calls",
            "call_",
            "EXECUTING FUNCTION",
            "Calling function"
        ]
        return any(keyword in content for keyword in tool_call_keywords)

    
    def _format_search_summary(self, search_results: dict, tool_name: str) -> str:
        """
        格式化搜索結果摘要
        
        Args:
            search_results: 搜索結果字典
            tool_name: 工具名稱
            
        Returns:
            格式化的摘要字符串
        """
        documents = search_results.get("ranked_documents", [])
        metadatas = search_results.get("ranked_metadatas", [])
        
        if not documents:
            return "未找到相關案例。"
        
        # 取第一個結果進行摘要
        doc = documents[0]
        metadata = metadatas[0] if metadatas else {}
        
        # 從文檔內容中提取關鍵信息
        # 這裡可以根據實際內容進行更智能的提取
        punished_person = "新光金融控股股份有限公司"  # 預設值
        issue_date = "中華民國113年4月23日"  # 預設值
        violation = "子公司資本適足率未達規定等級，未善盡增資義務"  # 簡要描述
        punishment = "予以糾正，並調降董事長薪酬50%"  # 簡要描述
        
        # 嘗試從metadata中提取更準確的信息
        if metadata:
            case_summary = metadata.get("case_summary", "")
            if "受處分人" in case_summary:
                # 簡單的文本提取邏輯
                lines = case_summary.split('\n')
                for line in lines:
                    if "受處分人" in line:
                        punished_person = line.replace("受處分人：", "").strip()
                    elif "發文日期" in line:
                        issue_date = line.replace("發文日期：", "").strip()
        
        # 檢查是否包含程式碼
        has_code = any("z3code" in str(metadata) and metadata.get("z3code") for metadata in metadatas)
        
        # 格式化摘要
        summary = f"""📋 **案例摘要**

**受處分人**: {punished_person}
**發文日期**: {issue_date}
**違規重點**: {violation}
**處分內容**: {punishment}

{f"**注意**: 此案例包含相關程式碼分析。" if has_code else ""}

**查詢結果**: 找到 {len(documents)} 個相關案例。

是否要進行深入分析？"""
        
        return summary
    
    def _extract_tool_name(self, content) -> str:
        """從工具呼叫訊息中提取工具名稱"""
        if not content:
            return "未知工具"

        # 確保 content 是字串
        content_str = str(content) if content else ""

        # 嘗試從各種格式提取工具名稱
        import re

        # 匹配 "Calling function: tool_name" 格式（新格式）
        match = re.search(r'Calling function:\s*(\w+)', content_str)
        if match:
            tool_name = match.group(1)
            tool_name_map = {
                "legal_article_search": "法條搜尋",
                "search_and_rerank": "案例搜尋",
                "list_available_code_files": "列出程式碼檔案",
                "execute_python_file": "執行程式碼",
                "perform_deep_analysis_tool": "深入分析",
                "apply_custom_constraints_tool": "應用自定義約束",
            }
            return tool_name_map.get(tool_name, tool_name)

        # 匹配 "Suggested tool call (call_xxx): tool_name" 格式
        match = re.search(r'Suggested tool call.*?:\s*(\w+)', content_str)
        if match:
            tool_name = match.group(1)
            # 轉換為中文名稱
            tool_name_map = {
                "legal_article_search": "法條搜尋",
                "search_and_rerank": "案例搜尋",
                "list_available_code_files": "列出程式碼檔案",
                "execute_python_file": "執行程式碼",
                "perform_deep_analysis_tool": "深入分析",
                "apply_custom_constraints_tool": "應用自定義約束",
            }
            return tool_name_map.get(tool_name, tool_name)

        # 匹配 "): 工具名稱" 格式
        match = re.search(r'\):\s*(\w+)', content_str)
        if match:
            tool_name = match.group(1)
            tool_name_map = {
                "legal_article_search": "法條搜尋",
                "search_and_rerank": "案例搜尋",
                "list_available_code_files": "列出程式碼檔案",
                "execute_python_file": "執行程式碼",
                "perform_deep_analysis_tool": "深入分析",
                "apply_custom_constraints_tool": "應用自定義約束",
            }
            return tool_name_map.get(tool_name, tool_name)

        # 匹配 "tool_calls" 中的函數名
        match = re.search(r'"name":\s*"([^"]+)"', content_str)
        if match:
            tool_name = match.group(1)
            tool_name_map = {
                "legal_article_search": "法條搜尋",
                "search_and_rerank": "案例搜尋",
                "list_available_code_files": "列出程式碼檔案",
                "execute_python_file": "執行程式碼",
                "perform_deep_analysis_tool": "深入分析",
                "apply_custom_constraints_tool": "應用自定義約束",
            }
            return tool_name_map.get(tool_name, tool_name)

        return "未知工具"
    
    def _get_emoji_for_agent(self, agent_name: str) -> str:
        """根據 Agent 名稱取得對應的 emoji"""
        emoji_map = {
            "host_agent": "🤖",
            "search_agent": "🔍",
            "summary_agent": "📋",
            "case_analyst": "📊",
            "code_analyst": "💻",
            "law_analyst": "⚖️",
            "legal_analyst": "📚",
            "report_generator": "📝",
            "user_proxy": "👤",
            "chat_manager": "👨‍💼"
        }
        return emoji_map.get(agent_name, "🤖")

    async def _cleanup_active_waiting_messages(self):
        """清理所有活躍的等待訊息按鈕"""
        import chainlit as cl
        
        active_waiting_ids = cl.user_session.get("active_waiting_message_ids") or []
        if not active_waiting_ids:
            return
        
        print(f"[ChatManager] 清理 {len(active_waiting_ids)} 個活躍等待訊息")
        
        for waiting_msg_id in active_waiting_ids:
            try:
                # 移除按鈕
                action_map = cl.user_session.get("action_map") or {}
                if waiting_msg_id in action_map:
                    for action_id in action_map[waiting_msg_id]:
                        try:
                            # 創建 action 物件來移除
                            a = cl.Action(name="", payload={}, label="")
                            a.id = action_id
                            a.forId = waiting_msg_id
                            await a.remove()
                            print(f"[ChatManager] 已清理舊等待訊息按鈕: {waiting_msg_id}")
                        except Exception as e:
                            print(f"[ChatManager] 清理按鈕失敗: {e}")
                del action_map[waiting_msg_id]
                cl.user_session.set("action_map", action_map)
            except Exception as e:
                print(f"[ChatManager] 清理等待訊息失敗: {e}")
        
        # 清空活躍等待列表
        cl.user_session.set("active_waiting_message_ids", [])
        print(f"[ChatManager] 已清空活躍等待訊息列表")

    async def _process_chat_result(self, chat_result) -> Dict:
        """處理對話結果"""
        all_messages = self.group_chat.messages
        
        # 分類訊息
        categorized_messages = {
            "host_responses": [],
            "search_results": [],
            "analysis_results": [],
            "system_messages": []
        }
        
        for message in all_messages:
            role = message.get("name", "unknown")
            content = message.get("content", "")
            
            if not content.strip() or role == "user_proxy":
                continue
            
            # 過濾系統訊息
            if self._is_system_message(content):
                continue
            
            # 分類訊息
            if role == "host_agent":
                categorized_messages["host_responses"].append({
                    "role": role,
                    "content": content
                })
            elif role == "search_agent":
                categorized_messages["search_results"].append({
                    "role": role,
                    "content": content
                })
            elif "analyst" in role or role in ["deep_analysis_agent", "summary_agent", "constraint_customization_agent"]:
                # ⭐ 修復：包含所有分析相關的 agent
                categorized_messages["analysis_results"].append({
                    "role": role,
                    "content": content
                })
            else:
                # ⭐ 新增：其他 agent 的消息也加入（legal_retrieval_agent 等）
                categorized_messages["analysis_results"].append({
                    "role": role,
                    "content": content
                })
        
        return {
            "success": True,
            "messages": categorized_messages,
            "all_messages": all_messages
        }
    
    def _is_system_message(self, content: str) -> bool:
        """判斷是否為系統訊息 - 只過濾不需要顯示的訊息"""
        if not content:
            return True
        
        # 只有完全由系統標記組成的訊息才視為系統訊息
        # 避免誤過濾包含表格或正常內容的訊息
        content_lower = content.lower()
        
        # 檢查是否是純系統訊息（開頭或結尾帶有系統標記）
        system_only_patterns = [
            content.startswith("*****") and content.endswith("*****"),
            "next speaker:" in content_lower and len(content) < 100,
            "terminating run" in content_lower,
            content.strip().startswith("TOOL CALL ID:"),
        ]
        
        if any(system_only_patterns):
            return True
        
        return False

    def reset(self):
        """重置對話狀態"""
        self.group_chat.messages = []
        self.last_processed_count = 0
        self.full_conversation_history = []
        self.is_interrupted = False
        self.current_chat_task = None
        print("[ChatManager] 對話狀態已重置")
    
    def restore_conversation_history(self, messages: List[Dict]) -> None:
        """
        恢復對話歷史到群組對話中
        
        Args:
            messages: 要恢復的訊息列表，每個訊息應包含 'name', 'content' 等字段
        """
        if not messages:
            print("[ChatManager] 沒有要恢復的訊息")
            return
        
        print(f"[ChatManager] 開始恢復 {len(messages)} 條訊息")
        
        # 清空現有訊息
        self.group_chat.messages = []
        self.last_processed_count = 0
        self.full_conversation_history = []
        
        # 恢復訊息
        for i, msg in enumerate(messages):
            try:
                # 確保訊息格式正確
                restored_msg = {
                    "name": msg.get("name", "user_proxy"),
                    "content": msg.get("content", ""),
                }
                
                # 如果有額外的字段，也復製過來
                for key in msg:
                    if key not in ["name", "content"]:
                        restored_msg[key] = msg[key]
                
                self.group_chat.messages.append(restored_msg)
                self.full_conversation_history.append(restored_msg)
                
            except Exception as e:
                print(f"[ChatManager] 恢復訊息 {i} 失敗: {e}")
        
        print(f"[ChatManager] 成功恢復 {len(self.group_chat.messages)} 條訊息")
    
    def get_all_messages(self) -> List[Dict]:
        """
        獲取所有群組對話訊息（用於保存）
        
        Returns:
            訊息列表
        """
        return self.group_chat.messages.copy()
    
    def interrupt_chat(self) -> bool:
        """
        中斷正在進行的對話
        
        Returns:
            True 如果成功中斷，False 如果沒有進行中的任務
        """
        if self.current_chat_task and not self.current_chat_task.done():
            print("[ChatManager] 中斷訊號已發送，設置 is_interrupted 標誌")
            self.is_interrupted = True
            
            # 嘗試取消任務
            if not self.current_chat_task.cancelled():
                self.current_chat_task.cancel()
                print("[ChatManager] 任務已取消")
            
            return True
        else:
            print("[ChatManager] 沒有進行中的任務可中斷")
            return False
    
    def get_conversation_history(self) -> List[Dict]:
        """取得完整對話歷史"""
        return self.full_conversation_history

    async def _check_direct_response(self, message: str) -> Optional[Dict]:
        """
        檢查是否需要直接處理某些訊息（標記觸發）
        
        Args:
            message: 用戶訊息
            
        Returns:
            如果需要直接處理，返回處理結果，否則返回 None
        """
        import chainlit as cl

        # 保留：明確標記觸發（host agent 會輸出這些標記）
        if message.strip() in ["【啟動案例分析】", "【啟動深入分析】", "【啟動法條搜索】", "【啟動自定義約束】"]:
            print(f"[ChatManager] 偵測到標記觸發: {message}")
            # 由 GroupChat 的狀態轉換邏輯處理，這裡只回傳標記內容供上層流程使用
            return {"content": message.strip()}

        # 只接受簡單肯定回覆（在 host_agent 最近發出等待確認訊息時視為按鈕點擊）
        affirmatives = {}
        msg_norm = message.strip().lower()
        try:
            last_agent_content = cl.user_session.get("_last_agent_message_content", "") or ""
        except Exception:
            last_agent_content = ""

        waiting_tags = ["等待自定義", "等待自定義狀態確認", "【等待自定義狀態確認】",
                        "等待深入分析確認", "【等待深入分析確認】",
                        "等待法條確認", "等待案例確認", "【等待法條確認】", "【等待案例確認】"]

        if msg_norm in affirmatives and any(tag in last_agent_content for tag in waiting_tags):
            print("[ChatManager] 偵測到使用者以文字確認，視為按鈕點擊（保留相容行為）")
            return {"content": "【啟動自定義約束】", "metadata": {"trigger": "affirmative"}}

        # 其餘情況不做自動啟動，交由 host agent 判定是否輸出啟動標記
        return None
    
    async def _process_chat_result_with_direct_response(self, direct_result: Dict, agent_name: str) -> Dict:
        """
        處理直接回應的結果
        
        Args:
            direct_result: 直接處理的結果
            agent_name: agent 名稱
            
        Returns:
            處理後的結果
        """
        import chainlit as cl
        
        content = direct_result.get("content", "")
        
        # 檢查是否是等待確認的訊息
        if isinstance(content, str) and any(tag in content for tag in ["[等待法條確認]", "[等待案例確認]", "[等待深入分析確認]", "[等待法條內容]", "[等待案例內容]", "【等待法條確認】", "【等待案例確認】", "【等待深入分析確認】", "【等待法條內容】", "【等待案例內容】"]):
            # 初始化變數
            confirm_label = "✅ 是，繼續"
            cancel_label = "❌ 否，取消"
            confirm_action = "confirm_analysis"
            cancel_action = "cancel_analysis"
            
            # 判斷是否需要顯示按鈕
            needs_buttons = not any(tag in content for tag in ["[等待法條內容]", "[等待案例內容]", "【等待法條內容】", "【等待案例內容】"])
            
            if needs_buttons:
                # 根據標記決定按鈕類型
                if "[等待深入分析確認]" in content or "【等待深入分析確認】" in content:
                    confirm_label = "✅ 是，進行深入分析"
                    cancel_label = "❌ 否，結束"
                    confirm_action = "confirm_deep_analysis"
                    cancel_action = "cancel_deep_analysis"
            
            # 移除標記後顯示
            display_content = content.replace("[等待法條確認]", "").replace("[等待案例確認]", "").replace("[等待深入分析確認]", "").replace("[等待法條內容]", "").replace("[等待案例內容]", "").replace("【等待法條確認】", "").replace("【等待案例確認】", "").replace("【等待深入分析確認】", "").replace("【等待法條內容】", "").replace("【等待案例內容】", "").strip()
            
            emoji = self._get_emoji_for_agent(agent_name)
            formatted_content = f"{emoji} **{agent_name}**\n\n{display_content}"
            
            # 創建訊息
            cl_msg = cl.Message(content="")
            await cl_msg.send()
            
            # 串流輸出
            for char in formatted_content:
                await cl_msg.stream_token(char)
            
            await cl_msg.update()
            
            if needs_buttons:
                # 添加按鈕
                actions = [
                    cl.Action(
                        name=confirm_action,
                        label=confirm_label,
                        payload={"action": "confirm"}
                    ),
                    cl.Action(
                        name=cancel_action,
                        label=cancel_label,
                        payload={"action": "cancel"}
                    )
                ]
                
                cl_msg.actions = actions
                await cl_msg.update()
                
                # 儲存按鈕信息
                action_ids = [a.id for a in actions]
                action_map = cl.user_session.get("action_map") or {}
                action_map[cl_msg.id] = action_ids
                cl.user_session.set("action_map", action_map)
                
                active_waiting_ids = cl.user_session.get("active_waiting_message_ids") or []
                if cl_msg.id not in active_waiting_ids:
                    active_waiting_ids.append(cl_msg.id)
                    cl.user_session.set("active_waiting_message_ids", active_waiting_ids)
        
        else:
            # 普通訊息，直接顯示
            emoji = self._get_emoji_for_agent(agent_name)
            formatted_content = f"{emoji} **{agent_name}**\n\n{content}"
            
            cl_msg = cl.Message(content="")
            await cl_msg.send()
            
            for char in formatted_content:
                await cl_msg.stream_token(char)
            
            await cl_msg.update()
        
        # 返回標準格式的結果
        return {
            "success": True,
            "messages": {
                "host_responses": [],
                "search_results": [],
                "analysis_results": [],
                "system_messages": []
            },
            "all_messages": self.group_chat.messages
        }