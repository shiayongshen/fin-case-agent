"""
Apply Custom Constraints Tool
用於應用用戶自定義的約束，並觸發新的 Z3 求解
"""

from typing import Dict, List, Optional, Union
import json


class Z3ConstraintCustomization:
    """
    工具：應用自定義約束並執行新的 Z3 求解
    
    功能：
    1. 接收用戶自定義的約束設定
    2. 解析並驗證約束的有效性
    3. 觸發新的 Z3 求解過程
    4. 返回更新後的求解結果
    """
    
    def __init__(self):
        """初始化工具"""
        self.custom_constraints: Dict[str, Dict] = {}
        self.case_id: Optional[str] = None
        self.last_solving_result: Optional[Dict] = None
    
    def set_case_id(self, case_id: str) -> None:
        """
        設置當前工作的 case ID
        
        Args:
            case_id: Case ID，如 'case_0' 或 '0'
        """
        if not case_id.startswith('case_'):
            case_id = f'case_{case_id}'
        self.case_id = case_id
        print(f"[ApplyCustomConstraintsTool] Case ID 設置為: {case_id}")
    
    def add_fix_constraint(self, variable_name: str, value: Union[int, float, bool]) -> Dict:
        """
        固定一個變數的值
        
        Args:
            variable_name: 變數名稱
            value: 要固定的值
            
        Returns:
            操作結果
        """
        self.custom_constraints[variable_name] = {
            "type": "FIX",
            "value": value,
            "description": f"將 {variable_name} 固定為 {value}"
        }
        
        print(f"[ApplyCustomConstraintsTool] 已添加固定值約束: {variable_name} = {value}")
        
        return {
            "status": "success",
            "operation": "FIX",
            "variable": variable_name,
            "value": value
        }
    
    def add_lower_bound(self, variable_name: str, lower_bound: Union[int, float]) -> Dict:
        """
        設置變數的下界
        
        Args:
            variable_name: 變數名稱
            lower_bound: 下界值
            
        Returns:
            操作結果
        """
        self.custom_constraints[variable_name] = {
            "type": "LOWER_BOUND",
            "lower_bound": lower_bound,
            "description": f"將 {variable_name} 的下界設置為 {lower_bound}"
        }
        
        print(f"[ApplyCustomConstraintsTool] 已添加下界約束: {variable_name} >= {lower_bound}")
        
        return {
            "status": "success",
            "operation": "LOWER_BOUND",
            "variable": variable_name,
            "lower_bound": lower_bound
        }
    
    def add_upper_bound(self, variable_name: str, upper_bound: Union[int, float]) -> Dict:
        """
        設置變數的上界
        
        Args:
            variable_name: 變數名稱
            upper_bound: 上界值
            
        Returns:
            操作結果
        """
        self.custom_constraints[variable_name] = {
            "type": "UPPER_BOUND",
            "upper_bound": upper_bound,
            "description": f"將 {variable_name} 的上界設置為 {upper_bound}"
        }
        
        print(f"[ApplyCustomConstraintsTool] 已添加上界約束: {variable_name} <= {upper_bound}")
        
        return {
            "status": "success",
            "operation": "UPPER_BOUND",
            "variable": variable_name,
            "upper_bound": upper_bound
        }
    
    def add_range_constraint(self, variable_name: str, 
                            lower_bound: Union[int, float],
                            upper_bound: Union[int, float]) -> Dict:
        """
        設置變數的值域範圍
        
        Args:
            variable_name: 變數名稱
            lower_bound: 下界
            upper_bound: 上界
            
        Returns:
            操作結果
        """
        if lower_bound > upper_bound:
            return {
                "status": "error",
                "message": f"錯誤：下界 {lower_bound} 不能大於上界 {upper_bound}"
            }
        
        self.custom_constraints[variable_name] = {
            "type": "RANGE",
            "lower_bound": lower_bound,
            "upper_bound": upper_bound,
            "description": f"將 {variable_name} 的值域設置為 [{lower_bound}, {upper_bound}]"
        }
        
        print(f"[ApplyCustomConstraintsTool] 已添加值域約束: {lower_bound} <= {variable_name} <= {upper_bound}")
        
        return {
            "status": "success",
            "operation": "RANGE",
            "variable": variable_name,
            "lower_bound": lower_bound,
            "upper_bound": upper_bound
        }
    
    def get_custom_constraints(self) -> Dict:
        """
        獲取所有已設置的自定義約束
        
        Returns:
            自定義約束字典
        """
        return self.custom_constraints.copy()
    
    def apply_constraints_and_resolve(self) -> Dict:
        """
        應用約束並執行 Z3 新求解
        
        該方法會：
        1. 驗證約束的有效性
        2. 執行新的 Z3 求解過程
        3. 返回更新後的求解結果
        
        Returns:
            包含求解結果的字典
        """
        if not self.case_id:
            return {
                "status": "error",
                "message": "未設置 case_id，無法執行求解"
            }
        
        if not self.custom_constraints:
            return {
                "status": "warning",
                "message": "尚未設置任何自定義約束"
            }
        
        print(f"[ApplyCustomConstraintsTool] 開始應用約束並重新求解")
        print(f"[ApplyCustomConstraintsTool] Case ID: {self.case_id}")
        print(f"[ApplyCustomConstraintsTool] 約束數: {len(self.custom_constraints)}")
        
        # 執行 Z3 求解（需要整合到主要的求解流程中）
        result = self._execute_z3_solving_with_constraints()
        
        return result
    
    def _execute_z3_solving_with_constraints(self) -> Dict:
        """
        執行帶有自定義約束的 Z3 求解
        
        該方法會調用 optimize_single_case 模組，傳入自定義約束
        
        Returns:
            求解結果
        """
        try:
            import sys
            from pathlib import Path
            import importlib.util
            
            # 動態加載 optimize_single_case 模組
            optimize_path = Path(__file__).parent.parent / "find_optimize_result" / "optimize_single_case.py"
            
            if not optimize_path.exists():
                return {
                    "status": "error",
                    "message": f"無法找到 optimize_single_case.py"
                }
            
            spec = importlib.util.spec_from_file_location("optimize_single_case", optimize_path)
            if spec is None or spec.loader is None:
                return {
                    "status": "error",
                    "message": "無法加載 optimize_single_case 模組"
                }
            
            optimize_module = importlib.util.module_from_spec(spec)
            sys.path.insert(0, str(optimize_path.parent))
            spec.loader.exec_module(optimize_module)
            
            # 加載案例數據
            constraint_spec, facts, varspecs = optimize_module.load_case_data(self.case_id)
            
            if constraint_spec is None:
                return {
                    "status": "error",
                    "message": f"無法加載 {self.case_id} 的數據"
                }
            
            # 將自定義約束轉換為 Z3 表達式並添加到 constraint_spec
            updated_constraint_spec = self._add_custom_constraints_to_spec(
                constraint_spec, 
                varspecs
            )
            
            # 執行求解
            initial_facts, suggested_model = optimize_module.solve_case(
                updated_constraint_spec,
                facts,
                varspecs
            )
            
            if initial_facts is None or suggested_model is None:
                return {
                    "status": "error",
                    "message": f"約束下無可行解"
                }
            
            # 儲存求解結果
            self.last_solving_result = {
                "case_id": self.case_id,
                "initial_facts": initial_facts,
                "suggested_model": suggested_model,
                "custom_constraints_applied": self.custom_constraints.copy()
            }
            
            print(f"[ApplyCustomConstraintsTool] Z3 求解完成")
            
            return {
                "status": "success",
                "message": "自定義約束已應用，Z3 求解完成",
                "case_id": self.case_id,
                "constraints_count": len(self.custom_constraints),
                "solving_result": self.last_solving_result
            }
            
        except Exception as e:
            print(f"[ApplyCustomConstraintsTool] 求解過程出錯: {e}")
            import traceback
            traceback.print_exc()
            
            return {
                "status": "error",
                "message": f"求解過程出錯: {str(e)}"
            }
    
    def _add_custom_constraints_to_spec(self, constraint_spec: list, varspecs: list) -> list:
        """
        將自定義約束轉換為 Z3 表達式並添加到約束規格中
        
        Args:
            constraint_spec: 原始約束規格列表
            varspecs: 變數規格列表
            
        Returns:
            更新後的約束規格列表
        """
        # 建立變數名稱到類型的映射
        var_types = {v["name"]: v.get("type", "Int") for v in varspecs}
        
        new_constraints = []
        
        for var_name, constraint in self.custom_constraints.items():
            constraint_type = constraint.get("type")
            
            if constraint_type == "FIX":
                # 轉換為: var_name == value
                value = constraint.get("value")
                expr = ["EQ", ["VAR", var_name], value]
                new_constraints.append({
                    "id": f"custom_fix_{var_name}",
                    "expr": expr,
                    "weight": 1,  # Hard constraint
                    "description": f"自定義約束：{var_name} = {value}"
                })
            
            elif constraint_type == "LOWER_BOUND":
                # 轉換為: var_name >= lower_bound
                lower = constraint.get("lower_bound")
                expr = ["GE", ["VAR", var_name], lower]
                new_constraints.append({
                    "id": f"custom_lower_{var_name}",
                    "expr": expr,
                    "weight": 1,
                    "description": f"自定義約束：{var_name} >= {lower}"
                })
            
            elif constraint_type == "UPPER_BOUND":
                # 轉換為: var_name <= upper_bound
                upper = constraint.get("upper_bound")
                expr = ["LE", ["VAR", var_name], upper]
                new_constraints.append({
                    "id": f"custom_upper_{var_name}",
                    "expr": expr,
                    "weight": 1,
                    "description": f"自定義約束：{var_name} <= {upper}"
                })
            
            elif constraint_type == "RANGE":
                # 轉換為: lower_bound <= var_name <= upper_bound
                lower = constraint.get("lower_bound")
                upper = constraint.get("upper_bound")
                
                # 添加下界約束
                expr_lower = ["GE", ["VAR", var_name], lower]
                new_constraints.append({
                    "id": f"custom_range_lower_{var_name}",
                    "expr": expr_lower,
                    "weight": 1,
                    "description": f"自定義約束：{var_name} >= {lower}"
                })
                
                # 添加上界約束
                expr_upper = ["LE", ["VAR", var_name], upper]
                new_constraints.append({
                    "id": f"custom_range_upper_{var_name}",
                    "expr": expr_upper,
                    "weight": 1,
                    "description": f"自定義約束：{var_name} <= {upper}"
                })
        
        # 合併原始約束和新約束
        updated_spec = constraint_spec + new_constraints
        
        print(f"[ApplyCustomConstraintsTool] 已添加 {len(new_constraints)} 個自定義約束到規格中")
        
        return updated_spec
    
    def reset(self) -> Dict:
        """
        重置所有約束和狀態
        
        Returns:
            操作結果
        """
        count = len(self.custom_constraints)
        self.custom_constraints.clear()
        self.last_solving_result = None
        
        print(f"[ApplyCustomConstraintsTool] 已重置所有約束（移除 {count} 項）")
        
        return {
            "status": "success",
            "message": f"已重置所有約束（移除 {count} 項）"
        }
    
    def get_constraints_summary(self) -> str:
        """
        獲取約束的摘要
        
        Returns:
            格式化的摘要字符串
        """
        if not self.custom_constraints:
            return "目前沒有設置任何自定義約束"
        
        summary = "📋 已設置的自定義約束：\n\n"
        for i, (var, constraint) in enumerate(self.custom_constraints.items(), 1):
            summary += f"{i}. {constraint['description']}\n"
        
        return summary


# 全局工具實例
apply_constraints_tool = Z3ConstraintCustomization()


def get_apply_constraints_tool() -> Z3ConstraintCustomization:
    """獲取全局應用約束工具實例"""
    return apply_constraints_tool
