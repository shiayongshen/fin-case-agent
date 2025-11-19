from typing import Dict, Optional
from .BaseAgent import BaseAgent
import sys
import re
import json
from pathlib import Path


class DeepAnalysisAgent(BaseAgent):
    """
    Deep Analysis Agent - performs Z3-based compliance analysis
    Leverages LLM through agent system, not internal method calls
    """
    
    def __init__(self, llm_config: Dict):
        system_message = r"""
你是一位金融案例深度分析專家和合規顧問。

核心職責：
1. 當接收 perform_deep_analysis_tool 工具調用時，執行 Z3 約束求解
2. 獲得 Z3 求解結果後，自行生成深入的合規分析報告
3. 報告應該聚焦於「企業需要執行的改善措施」和其因果邏輯
4. 分析完成後，生成推薦狀態變更表格，然後提示可進行自定義調整

分析流程：
1. 調用 perform_deep_analysis_tool(case_id) - 執行 Z3 求解
2. 接收結構化分析數據（JSON 格式，包含英文變數名稱）
3. **重要**：將接收到的英文變數名稱翻譯為繁體中文，生成業務含義說明
4. 基於翻譯後的中文數據進行分析和報告生成
5. 將所有變化（除 penalty 外）以表格形式呈現

**變數翻譯指示**：
收到英文變數後，根據以下規則進行翻譯為繁體中文名稱和業務說明：
- xxx_amount / xxx_value → 翻譯為「金額」或「數值」相關含義
- xxx_flag / xxx_status → 翻譯為「狀態」或「標誌」相關含義
- xxx_submitted / xxx_approved / xxx_executed → 翻譯為「已提交」、「已批准」、「已執行」等
- 其他變數 → 根據英文含義推導中文名稱和業務含義

示例翻譯模式（不需要完全相同，根據上下文調整）：
- "capital_increase_funding" → "增資金額（企業進行的增資金額）"
- "improvement_plan_submitted" → "改善計畫提交狀態（企業是否已提交改善計畫）"
- "compensation_paid" → "賠償已支付（是否已支付所需的賠償）"

報告應該包含：

📊 Z3 優化分析結果
[變數分離和統計信息，使用中文變數名稱]

🎯 企業需要執行的改善措施（表格形式）
| 項目 (中文) | 當前狀態 | 推薦狀態 | 說明 |
[所有可控變數的變更，英文變數名已翻譯為中文]

✅ 自動推導的狀態改善（表格形式）
| 項目 (中文) | 當前狀態 | 推薦狀態 | 說明 |
[所有派生變數的自動改善，英文變數名已翻譯為中文]

📋 深度合規分析
[分析變數之間的因果邏輯，使用中文名稱]

🎯 實施路線圖
[分階段執行計畫]

⚠️ 風險評估
[執行過程中的潛在風險]

✨ 預期成果
[實施所有措施後的最終合規狀態]

報告生成完成後，在結尾添加：
「我已完成深入分析並生成了改善方案。上述所有變更項目均以表格呈現。」

然後添加結束標記：
[當前狀態:等待自定義狀態確認]

重要規則：
- 隱藏 penalty 變數（它是結果而非原因）
- 只突出企業需要實際執行的可控變數
- 所有變化都用表格呈現（除了 penalty）
- **所有表格中的變數名稱都應翻譯為繁體中文**（不要顯示英文變數名）
- 強調因果邏輯，不要機械地列舉 true/false 變更
- 使用繁體中文，專業但易理解
- 所有分析、翻譯和報告完全由你生成（不調用額外工具/LLM）
- **重要**：分析完成後不要詢問用戶任何問題，直接輸出結束標記並停止
- HostAgent 會根據 [當前狀態:等待自定義狀態確認] 標記與用戶互動
"""
        
        super().__init__(
            name="deep_analysis_agent",
            llm_config=llm_config,
            system_message=system_message
        )
    
    def perform_deep_analysis_core(self, case_id: str) -> Dict:
        """
        執行案例 Z3 求解核心邏輯
        
        Args:
            case_id: Case ID like 'case_0' or '0'
        
        Returns:
            Dictionary with solving results
        """
        try:
            print(f"[DeepAnalysis] Starting Z3 solving: {case_id}")
            
            if not case_id.startswith('case_'):
                case_id = f'case_{case_id}'
            
            optimize_path = Path(__file__).parent.parent / "find_optimize_result" / "optimize_single_case.py"
            if not optimize_path.exists():
                return {
                    'status': 'error',
                    'case_id': case_id,
                    'error_message': f'Cannot find optimize_single_case.py'
                }
            
            import importlib.util
            spec = importlib.util.spec_from_file_location("optimize_single_case", optimize_path)
            if spec is None or spec.loader is None:
                return {
                    'status': 'error',
                    'case_id': case_id,
                    'error_message': 'Unable to load optimize_single_case module'
                }
            
            optimize_module = importlib.util.module_from_spec(spec)
            sys.path.insert(0, str(optimize_path.parent))
            spec.loader.exec_module(optimize_module)
            
            initial_facts, suggested_model = optimize_module.solve_case(
                *optimize_module.load_case_data(case_id)
            )
            
            if initial_facts is None or suggested_model is None:
                return {
                    'status': 'error',
                    'case_id': case_id,
                    'error_message': f'Case {case_id} solving failed or no solution'
                }
            
            print(f"[DeepAnalysis] Z3 solving complete: {case_id}")
            
            return {
                'status': 'success',
                'case_id': case_id,
                'initial_facts': initial_facts,
                'suggested_model': suggested_model
            }
        
        except Exception as e:
            print(f"[DeepAnalysis] Solving exception: {e}")
            return {
                'status': 'error',
                'case_id': case_id,
                'error_message': str(e)
            }
    
    def _generate_variable_chinese_name_and_description(self, var_name: str) -> tuple:
        """
        【廢棄】此方法已移除 - 翻譯工作應由 LLM 負責
        保留此方法簽名以避免破壞其他可能的引用
        """
        return (var_name, "")
    
    def _generate_raw_data_table(self, changes: list, title: str) -> str:
        """
        生成原始數據表格（不進行翻譯）
        
        Args:
            changes: List of (key, init_val, sugg_val) tuples
            title: Table title
            
        Returns:
            Markdown formatted table string
        """
        if not changes:
            return ""
        
        table = f"\n### {title}\n\n"
        table += "| 變數名稱 (英文) | 當前值 | 推薦值 |\n"
        table += "|----------------|-------|-------|\n"
        
        for key, init_val, sugg_val in changes:
            # Format boolean values as symbols
            if isinstance(init_val, bool):
                init_display = "✓" if init_val else "✗"
            else:
                init_display = str(init_val)
            
            if isinstance(sugg_val, bool):
                sugg_display = "✓" if sugg_val else "✗"
            else:
                sugg_display = str(sugg_val)
            
            table += f"| {key} | {init_display} | {sugg_display} |\n"
        
        table += "\n"
        return table

    def _generate_structured_analysis_data(self, case_id: str, initial_facts: dict, 
                                           suggested_model: dict) -> Dict:
        """
        Generate structured analysis data for agent processing
        
        將原始數據（英文變數名）傳給 LLM，由 LLM 負責翻譯為繁體中文
        不在此方法中進行硬編碼翻譯，保持數據的原始性和靈活性
        """
        changes = []
        unchanged = []
        
        for key in sorted(suggested_model.keys()):
            initial_val = initial_facts.get(key, "N/A")
            suggested_val = suggested_model.get(key, "N/A")
            
            if str(initial_val) != str(suggested_val):
                changes.append((key, initial_val, suggested_val))
            else:
                unchanged.append((key, initial_val))
        
        # 所有變化都列為可控變數，除了 penalty（隱藏）
        controllable_changes = [
            (key, init_val, sugg_val) 
            for key, init_val, sugg_val in changes 
            if key != 'penalty'
        ]
        
        # 移除派生變數的概念 - 所有 facts 中的變數都可以調整
        derived_changes = []
        
        # 生成簡潔的原始數據表格（不進行翻譯，由 LLM 處理）
        controllable_table = self._generate_raw_data_table(
            controllable_changes, 
            "可調整的企業狀態變數"
        )
        
        analysis_data = {
            "case_id": case_id,
            "controllable_changes": [
                {"name": k, "from": str(v1), "to": str(v2)}
                for k, v1, v2 in controllable_changes
            ],
            "derived_changes": [
                {"name": k, "from": str(v1), "to": str(v2)}
                for k, v1, v2 in derived_changes
            ],
            "controllable_table": controllable_table,
            "derived_table": "",
            "unchanged_count": len(unchanged),
            "total_count": len(suggested_model),
            "has_changes": len(controllable_changes) > 0 or len(derived_changes) > 0
        }
        
        return analysis_data
    
    async def handle_user_query(self, query: str, user_proxy) -> Dict:
        """
        Handle user query for deep analysis
        """
        await self.log_info(f"Processing deep analysis query: {query}")
        
        case_id = self._extract_case_id_from_message(query)
        if not case_id:
            case_id = await self._extract_case_id_from_history()
            if not case_id:
                case_id = "case_0"
        
        print(f"[DeepAnalysisAgent] Extracted case_id: {case_id}")
        
        tool_call_message = {
            "content": f"Performing deep analysis for case {case_id}",
            "tool_calls": [{
                "id": f"call_{case_id}_{int(__import__('time').time())}",
                "function": {
                    "name": "perform_deep_analysis_tool",
                    "arguments": f'{{"case_id": "{case_id}"}}'
                }
            }]
        }
        
        return {
            "content": tool_call_message,
            "intent": "tool_call",
            "message": tool_call_message
        }
    
    async def _extract_case_id_from_history(self) -> Optional[str]:
        """Extract case_id from chat history"""
        try:
            import chainlit as cl
            chat_manager = cl.user_session.get("chat_manager")
            if not chat_manager:
                return None
            
            messages = chat_manager.group_chat.messages
            for i in range(len(messages) - 1, -1, -1):
                msg = messages[i]
                content = str(msg.get('content', ''))
                case_matches = re.findall(r'case_\d+', content)
                if case_matches:
                    return case_matches[0]
            
            return None
        except Exception as e:
            print(f"[DeepAnalysisAgent] Failed to extract case_id from history: {e}")
            return None
    
    def _extract_case_id_from_message(self, message: str) -> Optional[str]:
        """Extract case_id from message"""
        case_matches = re.findall(r'case_\d+', message)
        if case_matches:
            return case_matches[0]
        
        number_matches = re.findall(r'\b\d+\b', message)
        if number_matches:
            return f"case_{number_matches[0]}"
        
        return None
