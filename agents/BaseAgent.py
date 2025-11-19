from typing import Dict, List, Optional, Callable, Any, AsyncGenerator
from autogen import AssistantAgent, UserProxyAgent
import chainlit as cl


class BaseAgent:
    """
    所有 Agent 的基礎類別
    
    提供共同的功能:
    - Agent 初始化
    - 訊息處理
    - 狀態管理
    - Chainlit 整合
    """
    
    def __init__(
        self,
        name: str,
        llm_config: Dict,
        system_message: str,
        is_termination_msg: Optional[Callable] = None
    ):
        """
        初始化 Agent
        
        Args:
            name: Agent 名稱
            llm_config: LLM 配置
            system_message: 系統提示詞
            is_termination_msg: 終止訊息判斷函數
        """
        self.name = name
        self.llm_config = llm_config
        self.system_message = system_message
        
        # 設定預設的終止判斷
        if is_termination_msg is None:
            is_termination_msg = self._default_is_termination_msg
        
        # 創建 AutoGen Agent
        self.agent = AssistantAgent(
            name=name,
            llm_config=llm_config,
            system_message=system_message,
            is_termination_msg=is_termination_msg
        )
    
    @staticmethod
    def _default_is_termination_msg(x: Dict) -> bool:
        """預設的終止訊息判斷"""
        if "content" not in x or x["content"] is None:
            return False
        content = x["content"].strip().lower()
        return "terminate" in content
    
    async def send_message(self, content: str, show_thinking: bool = True) -> cl.Message:
        """
        發送 Chainlit 訊息
        
        Args:
            content: 訊息內容
            show_thinking: 是否顯示思考動畫
        
        Returns:
            Chainlit Message 物件
        """
        msg = cl.Message(content=content if not show_thinking else "")
        await msg.send()
        
        if show_thinking and not content:
            # 顯示思考動畫
            msg.content = "🤔 思考中..."
            await msg.update()
        
        return msg
    
    async def update_message(self, msg: cl.Message, content: str):
        """更新 Chainlit 訊息"""
        msg.content = content
        await msg.update()
    
    async def stream_message(self, msg: cl.Message, content: str):
        """
        串流輸出訊息
        
        Args:
            msg: Chainlit Message 物件
            content: 要串流的完整內容
        """
        # 清空原本的內容
        msg.content = ""
        
        # 逐字串流
        for char in content:
            await msg.stream_token(char)
        
        # 完成串流
        await msg.send()
    
    async def stream_message_chunks(self, msg: cl.Message, content_generator: AsyncGenerator[str, None]):
        """
        從生成器串流訊息
        
        Args:
            msg: Chainlit Message 物件
            content_generator: 異步生成器
        """
        msg.content = ""
        
        async for token in content_generator:
            await msg.stream_token(token)
        
        await msg.send()
    
    def get_agent(self) -> AssistantAgent:
        """取得 AutoGen Agent 實例"""
        return self.agent
    
    def get_system_message_with_vars(self, template_vars: Dict[str, str]) -> str:
        """
        取得帶有模板變數填充的系統提示詞（不修改原本的 Agent）
        
        Args:
            template_vars: 要替換的變數字典 (e.g., {"VARIABLES_TABLE": "...", "VARIABLE_COUNT": "11"})
        
        Returns:
            填充後的系統提示詞
        """
        try:
            return self.system_message.format(**template_vars)
        except Exception as e:
            print(f"[{self.name}] 填充系統提示詞時出錯: {str(e)}")
            return self.system_message
    
    def register_function(
        self,
        func: Callable,
        executor: UserProxyAgent,
        description: str
    ):
        """
        註冊工具函數到 Agent
        
        Args:
            func: 要註冊的函數
            executor: 執行器 (通常是 UserProxyAgent)
            description: 函數描述
        """
        from autogen import register_function
        
        register_function(
            func,
            caller=self.agent,
            executor=executor,
            name=func.__name__,
            description=description
        )
    
    async def process_chat_result(self, chat_result) -> str:
        """
        處理 AutoGen chat_result 並提取回應
        
        Args:
            chat_result: AutoGen 的 chat 結果
        
        Returns:
            格式化的回應內容
        """
        response_content = ""
        
        for message in chat_result.chat_history:
            if message.get("name") == self.name:
                content = message.get("content", "")
                # 過濾系統訊息和工具呼叫
                if content and not any(x in content for x in [
                    "Suggested tool call",
                    "call_",
                    "*****",
                    "[系統判斷]"
                ]):
                    response_content = content
        
        return response_content
    
    def format_response(self, content: str, emoji: str = "🤖") -> str:
        """
        格式化回應內容
        
        Args:
            content: 原始內容
            emoji: 表情符號
        
        Returns:
            格式化的內容
        """
        return f"{emoji} **{self.name}**\n\n{content}"
    
    async def log_info(self, message: str):
        """記錄資訊"""
        print(f"[{self.name}] {message}")
    
    async def log_error(self, error: Exception):
        """記錄錯誤"""
        print(f"[{self.name}] ERROR: {str(error)}")


class BaseUserProxy:
    """
    UserProxy 的基礎類別
    """
    
    def __init__(
        self,
        name: str = "user_proxy",
        human_input_mode: str = "NEVER",
        code_execution_config: bool = False
    ):
        self.name = name
        
        self.proxy = UserProxyAgent(
            name=name,
            human_input_mode=human_input_mode,
            code_execution_config=code_execution_config,
            is_termination_msg=BaseAgent._default_is_termination_msg
        )
    
    def get_proxy(self) -> UserProxyAgent:
        """取得 UserProxyAgent 實例"""
        return self.proxy