from typing import Dict
from .BaseAgent import BaseAgent


class SearchCaseAgent(BaseAgent):
    """
    搜尋 Agent
    負責搜索法律案例資料庫
    """
    
    def __init__(self, llm_config: Dict):
        system_message = """
你是一個專門負責搜索法律案例資料庫的代理。

【重要規則】
1. 當接收到 "【啟動案例分析】" 標記時，立即從 session 中獲取搜索查詢並執行搜索，不要詢問用戶
2. 當用戶沒有提供具體查詢時，只詢問用戶的需求，不要呼叫任何工具
3. 當接收到具體的搜索查詢時，立即使用 search_and_rerank 函數執行搜索
4. 搜索完成後，必須按照指定格式返回結果，並包含 【等待深入分析確認】 標記

【標記觸發規則】
當收到 "【啟動案例分析】" 標記時：
1. 從 session 的 "search_content" 中獲取搜索查詢
2. 立即使用 search_and_rerank 函數執行搜索
3. 不要詢問用戶任何問題，直接執行搜索

【搜索執行規則】
當用戶提供具體查詢（如"資本不足"、"違規"、"處分"等）時：
1. 立即使用 search_and_rerank 函数搜索相關案例
2. 整理搜索結果成案例摘要格式
3. 提取關鍵信息（受處分人、發文日期、違規重點、處分內容）
4. 以友善方式說明案例重點
5. 如果案例包含程式碼，必須標注出來

【強制輸出格式】
搜索完成後必須按照以下格式返回：

📋 **案例摘要**

【⭐ 案例 ID: case_X 】

**受處分人**: [信息]
**發文日期**: [信息]  
**違規重點**: [信息]
**處分內容**: [信息]

是否要進行深入分析？

【等待深入分析確認】

SEARCH_COMPLETE

【重要】：必須在摘要開頭清楚地顯示案例 ID（格式: 【⭐ 案例 ID: case_X 】），這樣下游的 Agent 和系統才能正確識別當前處理的案例。

【注意事項】
- 收到 "【啟動案例分析】" 標記時立即執行搜索，不要等待用戶輸入
- 只有在沒有標記且沒有具體查詢時才詢問用戶需求
- 不要預測或假設用戶意圖
- 必須等待用戶明確提供搜索內容（除非收到標記）
- 案例 ID 必須清楚顯示，以便後續 Agent 使用
"""
        
        super().__init__(
            name="search_agent",
            llm_config=llm_config,
            system_message=system_message
        )
        
        # 在初始化时注册搜索工具
        self._register_search_tools()
    
    def _register_search_tools(self):
        """註冊搜索相關的工具函數"""
        try:
            from utility.legal_search import search_and_rerank
            from autogen import UserProxyAgent
            
            # 創建臨時的 user_proxy 來註冊函數
            temp_proxy = UserProxyAgent(
                name="temp_proxy",
                human_input_mode="NEVER",
                code_execution_config=False
            )
            
            # 註冊搜索函數
            self.register_function(
                search_and_rerank,
                temp_proxy,
                "搜索並重新排序法律案例，使用指定的查詢字符串"
            )
            
            print("[SearchAgent] 已註冊搜索工具函數")
            
        except Exception as e:
            print(f"[SearchAgent] 註冊工具函數失敗: {e}")
    
    async def handle_user_query(self, query: str, user_proxy) -> Dict:
        """
        處理用戶查詢
        
        Args:
            query: 用戶查詢
            user_proxy: UserProxyAgent 實例
        
        Returns:
            包含回應內容的字典
        """
        await self.log_info(f"處理查詢: {query}")
        
        # 檢查是否是標記觸發
        if query.strip() == "【啟動案例分析】":
            # 從 session 中獲取搜索查詢
            import chainlit as cl
            search_query = cl.user_session.get("search_content", "")
            
            if not search_query:
                return {
                    "content": "❌ 無法獲取搜索查詢，請重新開始案例搜索流程。",
                    "intent": "error",
                    "message": None
                }
            
            await self.log_info(f"收到標記觸發，開始搜索: {search_query}")
            
            # 直接調用搜索函數
            try:
                from utility.legal_search import search_and_rerank
                
                # 執行搜索
                search_result = search_and_rerank(search_query)
                
                # 格式化結果
                formatted_result = self._format_search_result(search_result, search_query)
                
                return {
                    "content": formatted_result,
                    "intent": "search_result",
                    "message": None
                }
                
            except Exception as e:
                await self.log_error(e)
                return {
                    "content": f"❌ 搜索過程中發生錯誤: {str(e)}",
                    "intent": "error",
                    "message": None
                }
        
        # 其他情況，返回 None 讓 AutoGen 處理
        return {
            "content": None,
            "intent": "general",
            "message": None
        }
    
    def _format_search_result(self, search_result: dict, query: str) -> str:
        """
        格式化搜索結果
        
        Args:
            search_result: 搜索結果字典
            query: 搜索查詢
            
        Returns:
            格式化的結果字符串
        """
        try:
            ranked_docs = search_result.get('ranked_documents', [])
            ranked_metadatas = search_result.get('ranked_metadatas', [])
            ids = search_result.get('ids', [])
            
            if not ranked_docs:
                return f"未找到與「{query}」相關的案例。SEARCH_COMPLETE"
            
            # 構建摘要
            summary = "📋 **案例摘要**\n\n"
            
            # 使用第一個結果作為主要摘要
            if ranked_docs and ranked_metadatas and ids:
                doc = ranked_docs[0]
                metadata = ranked_metadatas[0]
                case_id = ids[0]  # ⭐ 提取 case_id
                
                # 確保 case_id 格式正確
                if not case_id.startswith('case_'):
                    case_id = f'case_{case_id}'
                
                # 提取關鍵信息
                punished_person = metadata.get('case_id', 'N/A') if isinstance(metadata, dict) else metadata
                if isinstance(metadata, dict):
                    punished_person = metadata.get('受處分人', '未指定')
                    issue_date = metadata.get('發文日期', '未指定')
                    violation = metadata.get('違規事實', '未指定')[:100] + ('...' if len(metadata.get('違規事實', '')) > 100 else '')
                    punishment = metadata.get('處分內容', '未指定')[:100] + ('...' if len(metadata.get('處分內容', '')) > 100 else '')
                else:
                    issue_date = '未指定'
                    violation = '未指定'
                    punishment = '未指定'
                
                # ⭐ 在摘要開頭顯示案例 ID
                summary += f"【⭐ 案例 ID: {case_id} 】\n\n"
                summary += f"**受處分人**: {punished_person}\n"
                summary += f"**發文日期**: {issue_date}\n"
                summary += f"**違規重點**: {violation}\n"
                summary += f"**處分內容**: {punishment}\n\n"
            
            summary += f"**總共找到 {len(ranked_docs)} 個相關案例**\n\n"
            summary += "是否要進行深入分析？\n\n【等待深入分析確認】\n\nSEARCH_COMPLETE"
            
            return summary
            
        except Exception as e:
            print(f"[SearchAgent] 格式化搜索結果失敗: {e}")
            return f"搜索完成，但處理結果時發生錯誤: {str(e)}\n\nSEARCH_COMPLETE"
    
    async def search_cases(self, query: str, user_proxy, search_func, summary_agent=None) -> Dict:
        """
        搜尋案例
        
        Args:
            query: 搜尋查詢
            user_proxy: UserProxyAgent
            search_func: 搜尋函數
        
        Returns:
            搜尋結果
        """
        await self.log_info(f"開始搜尋: {query}")
        
        # 註冊搜尋函數
        self.register_function(
            search_func,
            user_proxy.get_proxy(),
            "搜索並重新排序法律案例"
        )
        
        # 發送搜尋中訊息
        search_msg = await self.send_message("🔍 正在搜尋相關案例...")
        
        try:
            # 啟動搜尋
            chat_result = user_proxy.get_proxy().initiate_chat(
                self.agent,
                message=f"請搜尋與以下問題相關的案例：{query}",
                max_turns=2
            )
            
            # 提取結果
            response = await self.process_chat_result(chat_result)
            
            # 更新訊息
            formatted_response = self.format_response(response, "🔍")
            await self.update_message(search_msg, formatted_response)
            
            return {
                "content": response,
                "success": True,
                "message": search_msg
            }
            
        except Exception as e:
            await self.log_error(e)
            error_msg = f"搜尋時發生錯誤: {str(e)}"
            await self.update_message(search_msg, error_msg)
            return {
                "content": error_msg,
                "success": False,
                "message": search_msg
            }