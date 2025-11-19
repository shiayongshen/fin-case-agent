#!/usr/bin/env python3
"""
測試 find_case_files 函數是否能正確找到案例文件
"""

from pathlib import Path
import sys

# 添加 find_optimize_result 到 Python 路徑
sys.path.insert(0, str(Path(__file__).parent / "find_optimize_result"))

from optimize_single_case import find_case_files, load_case_data

def test_find_case_files():
    """測試 find_case_files 函數"""
    print("=" * 70)
    print("測試 find_case_files 函數")
    print("=" * 70)
    
    # 測試 case_2
    case_id = "case_2"
    print(f"\n正在尋找 {case_id} 的文件...")
    
    constraint_spec_path, facts_path, varspecs_path = find_case_files(case_id)
    
    if constraint_spec_path is None:
        print(f"❌ 找不到 {case_id} 的文件")
        return False
    
    print(f"✅ 找到文件:")
    print(f"   Constraint spec: {constraint_spec_path}")
    print(f"   Facts: {facts_path}")
    print(f"   Varspecs: {varspecs_path}")
    
    # 驗證文件存在
    if not constraint_spec_path.exists():
        print(f"❌ 文件不存在: {constraint_spec_path}")
        return False
    if not facts_path.exists():
        print(f"❌ 文件不存在: {facts_path}")
        return False
    if not varspecs_path.exists():
        print(f"❌ 文件不存在: {varspecs_path}")
        return False
    
    print(f"✅ 所有文件都存在")
    return True

def test_load_case_data():
    """測試 load_case_data 函數"""
    print("\n" + "=" * 70)
    print("測試 load_case_data 函數")
    print("=" * 70)
    
    case_id = "case_2"
    print(f"\n正在加載 {case_id} 的數據...")
    
    constraint_spec, facts, varspecs = load_case_data(case_id)
    
    if constraint_spec is None:
        print(f"❌ 加載失敗")
        return False
    
    print(f"✅ 加載成功")
    print(f"   Constraint spec 項目數: {len(constraint_spec)}")
    print(f"   Facts 項目數: {len(facts)}")
    print(f"   Varspecs 項目數: {len(varspecs)}")
    
    return True

if __name__ == "__main__":
    result1 = test_find_case_files()
    result2 = test_load_case_data()
    
    if result1 and result2:
        print("\n✅ 所有測試通過！")
        exit(0)
    else:
        print("\n❌ 測試失敗")
        exit(1)
