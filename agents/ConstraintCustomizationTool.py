"""
Constraint Customization Tool
Allows users to customize company state by fixing, bounding, or modifying variables
before re-running Z3 constraint solving
"""

from typing import Dict, List, Optional, Union
import json


class ConstraintCustomizationTool:
    """
    工具：允許用戶自定義企業狀態約束條件
    
    支持的操作：
    1. 固定值（FIX）：將某個變數固定為特定值
    2. 下界（LOWER_BOUND）：設置變數的最小值
    3. 上界（UPPER_BOUND）：設置變數的最大值
    4. 範圍（RANGE）：設置變數的值域範圍
    """
    
    def __init__(self):
        self.customizations: Dict[str, Dict] = {}
    
    def add_fix_constraint(self, variable_name: str, value: Union[int, float, bool]) -> Dict:
        """
        固定一個變數的值
        
        Args:
            variable_name: 變數名稱
            value: 要固定的值
            
        Returns:
            操作結果
        """
        self.customizations[variable_name] = {
            "type": "FIX",
            "value": value,
            "description": f"將 {variable_name} 固定為 {value}"
        }
        
        return {
            "status": "success",
            "operation": "FIX",
            "variable": variable_name,
            "value": value,
            "message": f"✓ 已將 {variable_name} 固定為 {value}"
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
        self.customizations[variable_name] = {
            "type": "LOWER_BOUND",
            "lower_bound": lower_bound,
            "description": f"將 {variable_name} 的下界設置為 {lower_bound}"
        }
        
        return {
            "status": "success",
            "operation": "LOWER_BOUND",
            "variable": variable_name,
            "lower_bound": lower_bound,
            "message": f"✓ 已將 {variable_name} 的下界設置為 >= {lower_bound}"
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
        self.customizations[variable_name] = {
            "type": "UPPER_BOUND",
            "upper_bound": upper_bound,
            "description": f"將 {variable_name} 的上界設置為 {upper_bound}"
        }
        
        return {
            "status": "success",
            "operation": "UPPER_BOUND",
            "variable": variable_name,
            "upper_bound": upper_bound,
            "message": f"✓ 已將 {variable_name} 的上界設置為 <= {upper_bound}"
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
        
        self.customizations[variable_name] = {
            "type": "RANGE",
            "lower_bound": lower_bound,
            "upper_bound": upper_bound,
            "description": f"將 {variable_name} 的值域設置為 [{lower_bound}, {upper_bound}]"
        }
        
        return {
            "status": "success",
            "operation": "RANGE",
            "variable": variable_name,
            "lower_bound": lower_bound,
            "upper_bound": upper_bound,
            "message": f"✓ 已將 {variable_name} 的值域設置為 [{lower_bound}, {upper_bound}]"
        }
    
    def remove_customization(self, variable_name: str) -> Dict:
        """
        移除對某個變數的自定義約束
        
        Args:
            variable_name: 變數名稱
            
        Returns:
            操作結果
        """
        if variable_name in self.customizations:
            del self.customizations[variable_name]
            return {
                "status": "success",
                "message": f"✓ 已移除 {variable_name} 的自定義約束"
            }
        else:
            return {
                "status": "warning",
                "message": f"⚠ {variable_name} 沒有設置自定義約束"
            }
    
    def get_customizations(self) -> Dict:
        """
        獲取所有已設置的自定義約束
        
        Returns:
            自定義約束字典
        """
        return self.customizations.copy()
    
    def get_customizations_summary(self) -> str:
        """
        獲取自定義約束的摘要（用於展示）
        
        Returns:
            格式化的摘要字符串
        """
        if not self.customizations:
            return "目前沒有設置任何自定義約束"
        
        summary = "📋 已設置的自定義約束：\n\n"
        for var, constraint in self.customizations.items():
            summary += f"- {constraint['description']}\n"
        
        return summary
    
    def reset_customizations(self) -> Dict:
        """
        重置所有自定義約束
        
        Returns:
            操作結果
        """
        count = len(self.customizations)
        self.customizations.clear()
        
        return {
            "status": "success",
            "message": f"✓ 已重置所有自定義約束（移除 {count} 項）"
        }
    
    def build_constraint_dict_for_solver(self, case_id: str) -> Dict:
        """
        構建用於 Z3 求解器的約束字典
        
        Returns:
            包含自定義約束的字典，供 Z3 求解器使用
        """
        return {
            "case_id": case_id,
            "custom_constraints": self.customizations,
            "constraint_count": len(self.customizations)
        }
    
    def validate_customization(self, variable_name: str, 
                              current_value: Union[int, float, bool],
                              suggested_value: Union[int, float, bool]) -> Dict:
        """
        驗證自定義約束是否與建議值相容
        
        Args:
            variable_name: 變數名稱
            current_value: 當前值
            suggested_value: Z3 建議值
            
        Returns:
            驗證結果
        """
        if variable_name not in self.customizations:
            return {"status": "ok", "message": "無自定義約束"}
        
        constraint = self.customizations[variable_name]
        constraint_type = constraint.get("type")
        
        if constraint_type == "FIX":
            fixed_value = constraint.get("value")
            if suggested_value == fixed_value:
                return {"status": "compatible", "message": f"✓ 建議值 {suggested_value} 符合固定值約束"}
            else:
                return {
                    "status": "conflict",
                    "message": f"⚠ 衝突：您要求固定為 {fixed_value}，但 Z3 建議 {suggested_value}"
                }
        
        elif constraint_type == "LOWER_BOUND":
            lower = constraint.get("lower_bound")
            if lower is not None and suggested_value >= lower:
                return {"status": "compatible", "message": f"✓ 建議值 {suggested_value} 符合下界約束 >= {lower}"}
            elif lower is not None:
                return {
                    "status": "conflict",
                    "message": f"⚠ 衝突：您要求 >= {lower}，但 Z3 建議 {suggested_value}"
                }
        
        elif constraint_type == "UPPER_BOUND":
            upper = constraint.get("upper_bound")
            if upper is not None and suggested_value <= upper:
                return {"status": "compatible", "message": f"✓ 建議值 {suggested_value} 符合上界約束 <= {upper}"}
            elif upper is not None:
                return {
                    "status": "conflict",
                    "message": f"⚠ 衝突：您要求 <= {upper}，但 Z3 建議 {suggested_value}"
                }
        
        elif constraint_type == "RANGE":
            lower = constraint.get("lower_bound")
            upper = constraint.get("upper_bound")
            if lower is not None and upper is not None and lower <= suggested_value <= upper:
                return {
                    "status": "compatible",
                    "message": f"✓ 建議值 {suggested_value} 符合值域約束 [{lower}, {upper}]"
                }
            elif lower is not None and upper is not None:
                return {
                    "status": "conflict",
                    "message": f"⚠ 衝突：您要求值域 [{lower}, {upper}]，但 Z3 建議 {suggested_value}"
                }
        
        return {"status": "unknown", "message": "未知的約束類型"}


# 全局工具實例
constraint_tool = ConstraintCustomizationTool()


def get_constraint_tool() -> ConstraintCustomizationTool:
    """獲取全局約束自定義工具實例"""
    return constraint_tool
