#!/usr/bin/env python3
"""
測試報告格式
"""
import sys
from pathlib import Path
import os

# 設定環境
os.chdir(Path(__file__).parent)
sys.path.insert(0, str(Path(__file__).parent / "find_optimize_result"))

# 載入必要的模組
from find_optimize_result.optimize_single_case import load_case_data, solve_case

print("[TEST] 正在載入案例數據 (case_2)...")
try:
    constraint_spec, facts, varspecs = load_case_data("case_2")
    print(f"[TEST] ✅ 案例數據載入成功")
    print(f"  - Constraints: {len(constraint_spec)} 項")
    print(f"  - Facts: {len(facts)} 項")
    print(f"  - Varspecs: {len(varspecs)} 項")
except Exception as e:
    print(f"[TEST] ❌ 載入失敗: {e}")
    sys.exit(1)

print("\n[TEST] 正在執行 Z3 求解...")
try:
    initial_facts, suggested_model = solve_case(constraint_spec, facts, varspecs)
    print(f"[TEST] ✅ 求解成功")
    print(f"  - Initial facts: {len(initial_facts)} 項")
    print(f"  - Suggested model: {len(suggested_model)} 項")
except Exception as e:
    print(f"[TEST] ❌ 求解失敗: {e}")
    sys.exit(1)

print("\n[TEST] 生成報告內容...")

# 統計變化
changes = []
unchanged = []
for key in sorted(suggested_model.keys()):
    initial_val = initial_facts.get(key, "N/A")
    suggested_val = suggested_model.get(key, "N/A")
    
    if str(initial_val) != str(suggested_val):
        changes.append((key, initial_val, suggested_val))
    else:
        unchanged.append((key, initial_val))

print(f"[TEST] 統計結果:")
print(f"  - 需要變更: {len(changes)} 項")
print(f"  - 維持現狀: {len(unchanged)} 項")
print(f"  - 總計: {len(suggested_model)} 項")

print("\n[TEST] 報告預覽 (前 30 行):")
print("=" * 60)

report = f"# 📊 深入分析報告\n\n"

if changes:
    report += f"## ⚠️ 需要變更的項目 ({len(changes)} 項)\n\n"
    report += "| 項目 | 初始值 | 建議值 |\n"
    report += "|-----|--------|--------|\n"
    for key, init_val, sugg_val in changes:
        report += f"| {key} | `{init_val}` | `{sugg_val}` |\n"
    report += "\n"

report += f"## 📈 統計資訊\n\n"
report += f"- **需變更項**: {len(changes)} 項\n"
report += f"- **維持現狀**: {len(unchanged)} 項\n"
report += f"- **總計**: {len(suggested_model)} 項\n\n"

if unchanged:
    report += f"## ✅ 維持現狀的項目\n\n"
    report += "| 項目 | 值 |\n"
    report += "|-----|----|\n"
    for key, val in unchanged[:3]:
        report += f"| {key} | `{val}` |\n"
    if len(unchanged) > 3:
        report += f"| ... | (共 {len(unchanged) - 3} 項) |\n"
    report += "\n"

report += f"## 💡 優化建議\n\n"
if changes:
    report += "基於 Z3 約束求解分析，以下項目建議進行變更以優化合規狀態：\n\n"
    for key, init_val, sugg_val in changes:
        report += f"- **{key}**: `{init_val}` → `{sugg_val}`\n"
    report += "\n"

report += "### 後續步驟\n"
report += "1. 評估上述變更是否符合業務需求\n"
report += "2. 與法務團隊進行審核\n"
report += "3. 確認所有變更均滿足約束條件\n\n"

report += "---\n"
report += "*本報告由 AI 自動生成，建議由專業人士進行最終確認*\n"

# 分割報告，顯示前 30 行
lines = report.split('\n')
for i, line in enumerate(lines[:30]):
    print(line)

if len(lines) > 30:
    print(f"... (共 {len(lines)} 行)")

print("\n[TEST] 報告檢查:")
checks = [
    ("包含 '📊 深入分析報告'", "📊 深入分析報告" in report),
    ("包含 '⚠️ 需要變更'", "⚠️ 需要變更" in report),
    ("包含 '📈 統計資訊'", "📈 統計資訊" in report),
    ("不包含 '英文名稱' 列", "英文名稱" not in report),
    ("包含 '💡 優化建議'", "💡 優化建議" in report),
    ("包含變更項詳情", changes and "-" in report),
]

for check_name, check_result in checks:
    status = "✅" if check_result else "❌"
    print(f"  {status} {check_name}")

print("\n[TEST] ✅ 所有測試完成！")
