#!/usr/bin/env python3
"""
測試完整的深入分析流程，包括Z3求解
"""

from pathlib import Path
import sys

# 添加 find_optimize_result 到 Python 路徑
sys.path.insert(0, str(Path(__file__).parent / "find_optimize_result"))

from optimize_single_case import load_case_data, solve_case

def test_solve_case():
    """測試 solve_case 函數"""
    print("=" * 70)
    print("測試 solve_case 函數 (Z3 求解)")
    print("=" * 70)
    
    case_id = "case_2"
    print(f"\n正在加載 {case_id} 的數據...")
    
    constraint_spec, facts, varspecs = load_case_data(case_id)
    
    if constraint_spec is None:
        print(f"❌ 加載失敗")
        return False
    
    print(f"\n正在執行 Z3 求解...")
    print(f"   Hard Constraints (weight > 0): {sum(1 for c in constraint_spec if c.get('weight', 0) > 0)}")
    print(f"   Soft Constraints (weight == 0): {sum(1 for c in constraint_spec if c.get('weight', 0) == 0)}")
    
    initial_facts, suggested_model = solve_case(constraint_spec, facts, varspecs)
    
    if initial_facts is None:
        print(f"❌ 求解失敗或無解")
        return False
    
    print(f"\n✅ 求解成功")
    print(f"   初始事實項目數: {len(initial_facts)}")
    print(f"   建議模型項目數: {len(suggested_model)}")
    
    # 顯示一些改變
    changes = 0
    for key in suggested_model:
        if str(initial_facts.get(key, "N/A")) != str(suggested_model.get(key, "N/A")):
            changes += 1
    
    print(f"   需要變更的項目數: {changes}")
    
    return True

if __name__ == "__main__":
    try:
        result = test_solve_case()
        if result:
            print("\n✅ 測試通過！")
            exit(0)
        else:
            print("\n❌ 測試失敗")
            exit(1)
    except Exception as e:
        print(f"\n❌ 測試異常: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
