from typing import Dict
from .BaseAgent import BaseAgent


class CodeExecutorAgent(BaseAgent):
    """
    程式碼執行 Agent
    負責執行搜尋到的案例程式碼
    """
    
    def __init__(self, llm_config: Dict):
        system_message = """
你是程式碼執行專家,負責執行搜尋到的案例程式碼。

當搜尋代理找到包含程式碼的案例時,你需要:
1. 使用 `list_available_code_files` 查看可用的程式碼檔案
2. 使用 `execute_python_file` 執行指定的檔案
3. 將執行結果整理並傳遞給分析團隊

**重要規則**:
- 檔案名稱格式通常為: `case_case_X_code.py` 或 `case_X_code.py`
- 執行前先確認檔案存在
- 如果執行失敗,提供詳細的錯誤資訊
- 執行成功後,說明 "程式執行完成,結果如下" 並顯示輸出

執行完成後,請說 "EXECUTION_COMPLETE"。
"""
        
        super().__init__(
            name="code_executor",
            llm_config=llm_config,
            system_message=system_message
        )