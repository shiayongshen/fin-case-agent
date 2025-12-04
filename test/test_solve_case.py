#!/usr/bin/env python3
"""
測試完整的深入分析流程，包括Z3求解
"""

from pathlib import Path
import sys
import json

# 添加專案根目錄到 Python 路徑
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from find_optimize_result.optimize_single_case import load_case_data, solve_case

def print_section(title):
    """打印分隔符和標題"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)

def test_solve_case():
    """測試 solve_case 函數"""
    print_section("測試 solve_case 函數 (Z3 求解)")
    
    case_id = "case_108"
    print(f"\n📂 正在加載 {case_id} 的數據...")
    
    constraint_spec, facts, varspecs = load_case_data(case_id)
    
    if constraint_spec is None:
        print(f"❌ 加載失敗")
        return False
    
    # ===== 數據加載詳情 =====
    print_section("1️⃣  數據加載詳情")
    print(f"✅ 成功加載 {case_id}")
    print(f"\n📊 約束條件統計:")
    print(f"   - 總約束數: {len(constraint_spec)}")
    
    hard_constraints = [c for c in constraint_spec if c.get('weight', 0) > 0]
    soft_constraints = [c for c in constraint_spec if c.get('weight', 0) == 0]
    
    print(f"   - Hard Constraints (weight > 0): {len(hard_constraints)}")
    print(f"   - Soft Constraints (weight == 0): {len(soft_constraints)}")
    
    print(f"\n📝 事實數據:")
    print(f"   - 事實項目數: {len(facts) if facts else 0}")
    
    print(f"\n🔧 變數規格:")
    print(f"   - 變數個數: {len(varspecs) if varspecs else 0}")
    if varspecs:
        print(f"   - 變數類型分布:")
        type_counts = {}
        for var in varspecs:
            vtype = var.get('type', 'unknown')
            type_counts[vtype] = type_counts.get(vtype, 0) + 1
        for vtype, count in type_counts.items():
            print(f"     • {vtype}: {count}")
    
    # ===== Hard Constraints 詳情 =====
    if hard_constraints:
        print_section("2️⃣  Hard Constraints 詳情")
        print(f"共 {len(hard_constraints)} 個 Hard Constraints:\n")
        for i, constraint in enumerate(hard_constraints, 1):
            print(f"  [{i}] ID: {constraint.get('id', 'N/A')}")
            print(f"      描述: {constraint.get('desc', 'N/A')}")
            print(f"      Weight: {constraint.get('weight', 'N/A')}")
            print(f"      Domain: {constraint.get('domain', 'N/A')}")
            if i < len(hard_constraints):
                print()
    
    # ===== Soft Constraints 詳情 =====
    if soft_constraints:
        print_section("3️⃣  Soft Constraints 詳情")
        print(f"共 {len(soft_constraints)} 個 Soft Constraints:\n")
        for i, constraint in enumerate(soft_constraints[:5], 1):  # 只顯示前5個
            print(f"  [{i}] ID: {constraint.get('id', 'N/A')}")
            print(f"      描述: {constraint.get('desc', 'N/A')}")
            print(f"      Domain: {constraint.get('domain', 'N/A')}")
            print()
        if len(soft_constraints) > 5:
            print(f"  ... 還有 {len(soft_constraints) - 5} 個 Soft Constraints")
    
    # ===== 執行求解 =====
    print_section("4️⃣  Z3 求解過程")
    print(f"🔍 正在執行 Z3 求解...\n")
    
    initial_facts, suggested_model = solve_case(constraint_spec, facts, varspecs)
    
    if initial_facts is None:
        print(f"❌ 求解失敗或無解")
        return False
    
    print(f"✅ 求解成功！\n")
    
    # ===== 求解結果統計 =====
    print_section("5️⃣  求解結果統計")
    print(f"📋 初始事實:")
    print(f"   - 項目數: {len(initial_facts)}")
    print(f"   - 內存大小: ~{len(json.dumps(initial_facts)) / 1024:.2f} KB")
    
    print(f"\n🎯 建議模型:")
    print(f"   - 項目數: {len(suggested_model)}")
    print(f"   - 內存大小: ~{len(json.dumps(suggested_model)) / 1024:.2f} KB")
    
    # ===== 詳細變更分析 =====
    print_section("6️⃣  詳細變更分析")
    
    changes = []
    for key in sorted(suggested_model.keys()):
        initial_val = initial_facts.get(key, "N/A")
        suggested_val = suggested_model.get(key, "N/A")
        
        if str(initial_val) != str(suggested_val):
            changes.append({
                'key': key,
                'initial': initial_val,
                'suggested': suggested_val
            })
    
    print(f"📊 變更摘要:")
    print(f"   - 需要變更的項目數: {len(changes)}")
    print(f"   - 變更比例: {len(changes) / len(suggested_model) * 100:.2f}%\n")
    
    if changes:
        print(f"📝 具體變更項目 (前20個):\n")
        for i, change in enumerate(changes[:20], 1):
            print(f"  [{i}] {change['key']}")
            print(f"      初始值: {change['initial']}")
            print(f"      建議值: {change['suggested']}")
            print()
        
        if len(changes) > 20:
            print(f"  ... 還有 {len(changes) - 20} 項變更")
    else:
        print(f"   無需任何變更，模型已符合所有約束！")
    
    return True

if __name__ == "__main__":
    try:
        result = test_solve_case()
        if result:
            print_section("✅ 測試通過！")
            exit(0)
        else:
            print_section("❌ 測試失敗")
            exit(1)
    except Exception as e:
        print_section("❌ 測試異常")
        print(f"錯誤信息: {e}\n")
        import traceback
        traceback.print_exc()
        exit(1)
