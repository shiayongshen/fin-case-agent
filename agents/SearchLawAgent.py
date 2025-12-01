from typing import Dict
from .BaseAgent import BaseAgent


class SearchLawAgent(BaseAgent):
    """
    法條檢索 Agent
    負責搜索法律條文資料庫
    """

    def __init__(self, llm_config: Dict):
        system_message = """
你是一個專門負責搜索法律條文資料庫的代理。

【重要規則】
1. 當接收到 "【啟動法條搜索】" 標記時，立即從 session 中獲取搜索查詢並執行搜索，不要詢問用戶
2. 當用戶沒有提供具體查詢時，只詢問用戶的需求，不要呼叫任何工具
3. 當接收到具體的搜索查詢時，立即使用 legal_article_search 函數執行搜索
4. 搜索完成後，必須按照指定格式返回結果

【標記觸發規則】
當收到 "【啟動法條搜索】" 標記時：
1. 從 session 的 "search_content" 中獲取搜索查詢
2. 立即使用 legal_article_search 函數執行搜索
3. 不要詢問用戶任何問題，直接執行搜索

【搜索執行規則】
當用戶提供具體查詢（如"資本充足率"、"違規處分"、"金融法"等）時：
1. 立即使用 legal_article_search 函數搜索相關法條
2. 整理搜索結果成法條摘要格式
3. 提取關鍵信息（法條名稱、內容摘要、相關規定）
4. 以友善方式說明法條重點

【強制輸出格式】
搜索完成後必須按照以下格式返回：

📚 **法條檢索結果**

**查詢內容**: [用戶的搜索查詢]

[法條搜索結果的詳細內容]

SEARCH_COMPLETE

【注意事項】
- 收到 "【啟動法條搜索】" 標記時立即執行搜索，不要等待用戶輸入
- 只有在沒有標記且沒有具體查詢時才詢問用戶需求
- 不要預測或假設用戶意圖
- 必須等待用戶明確提供搜索內容（除非收到標記）
"""

        super().__init__(
            name="legal_retrieval_agent",
            llm_config=llm_config,
            system_message=system_message
        )

        # 在初始化時註冊法條搜索工具
        self._register_legal_tools()

    def _register_legal_tools(self):
        """註冊法條搜索相關的工具函數"""
        try:
            from utility.legal_search import legal_article_search
            from autogen import UserProxyAgent

            # 創建臨時的 user_proxy 來註冊函數
            temp_proxy = UserProxyAgent(
                name="temp_proxy",
                human_input_mode="NEVER",
                code_execution_config=False
            )

            # 註冊法條搜索函數
            self.register_function(
                legal_article_search,
                temp_proxy,
                "搜索法律條文，使用指定的查詢字符串"
            )

            print("[LegalRetrievalAgent] 已註冊法條搜索工具函數")

        except Exception as e:
            print(f"[LegalRetrievalAgent] 註冊工具函數失敗: {e}")

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
        if query.strip() == "【啟動法條搜索】":
            # 從 session 中獲取搜索查詢
            import chainlit as cl
            search_query = cl.user_session.get("search_content", "")

            if not search_query:
                return {
                    "content": "❌ 無法獲取搜索查詢，請重新開始法條搜索流程。",
                    "intent": "error",
                    "message": None
                }

            await self.log_info(f"收到標記觸發，開始搜索法條: {search_query}")

            # 直接調用法條搜索函數
            try:
                from utility.legal_search import legal_article_search

                # 執行搜索
                search_result = legal_article_search(search_query)

                # 格式化結果
                formatted_result = self._format_legal_search_result(search_result, search_query)

                return {
                    "content": formatted_result,
                    "intent": "legal_search_result",
                    "message": None
                }

            except Exception as e:
                await self.log_error(e)
                return {
                    "content": f"❌ 法條搜索過程中發生錯誤: {str(e)}",
                    "intent": "error",
                    "message": None
                }

        # 其他情況，返回 None 讓 AutoGen 處理
        return {
            "content": None,
            "intent": "general",
            "message": None
        }

    def _format_legal_search_result(self, search_result: str, query: str) -> str:
        """
        格式化法條搜索結果

        Args:
            search_result: 搜索結果字符串
            query: 搜索查詢

        Returns:
            格式化的結果字符串
        """
        try:
            if not search_result or search_result.strip() == "":
                return f"📚 **法條檢索結果**\n\n**查詢內容**: {query}\n\n未找到相關法條。\n\nSEARCH_COMPLETE"

            # 格式化結果
            formatted_result = "📚 **法條檢索結果**\n\n"
            formatted_result += f"**查詢內容**: {query}\n\n"
            formatted_result += f"{search_result}\n\n"
            formatted_result += "SEARCH_COMPLETE"

            return formatted_result

        except Exception as e:
            print(f"[LegalRetrievalAgent] 格式化法條搜索結果失敗: {e}")
            return f"法條搜索完成，但處理結果時發生錯誤: {str(e)}\n\nSEARCH_COMPLETE"

    async def search_legal_articles(self, query: str, user_proxy, search_func) -> Dict:
        """
        搜尋法條

        Args:
            query: 搜尋查詢
            user_proxy: UserProxyAgent
            search_func: 搜尋函數

        Returns:
            搜尋結果
        """
        await self.log_info(f"開始搜尋法條: {query}")

        # 註冊搜尋函數
        self.register_function(
            search_func,
            user_proxy.get_proxy(),
            "搜索法律條文"
        )

        # 發送搜尋中訊息
        search_msg = await self.send_message("📚 正在搜尋相關法條...")

        try:
            # 啟動搜尋
            chat_result = user_proxy.get_proxy().initiate_chat(
                self.agent,
                message=f"請搜尋與以下問題相關的法條：{query}",
                max_turns=2
            )

            # 提取結果
            response = await self.process_chat_result(chat_result)

            # 更新訊息
            formatted_response = self.format_response(response, "📚")
            await self.update_message(search_msg, formatted_response)

            return {
                "content": response,
                "success": True,
                "message": search_msg
            }

        except Exception as e:
            await self.log_error(e)
            error_msg = f"法條搜尋時發生錯誤: {str(e)}"
            await self.update_message(search_msg, error_msg)
            return {
                "content": error_msg,
                "success": False,
                "message": search_msg
            }