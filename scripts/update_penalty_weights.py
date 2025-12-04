#!/usr/bin/env python3
"""
修改所有 case_*.constraint_spec.json 檔案中的 penalty_default_false 和 penalty_conditions 的 weight 為 1
"""

import json
import glob
from pathlib import Path

def update_penalty_weights(json_file):
    """
    更新單個 JSON 檔案中 penalty_default_false 和 penalty_conditions 的 weight
    """
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 確保是列表
        if not isinstance(data, list):
            print(f"❌ {json_file}: 不是陣列格式，跳過")
            return False
        
        updated = False
        for item in data:
            # 檢查是否是我們要修改的項目
            if isinstance(item, dict) and 'id' in item:
                item_id = item['id']
                if item_id in ['meta:penalty_default_false', 'meta:penalty_conditions']:
                    old_weight = item.get('weight')
                    if old_weight != 1:
                        item['weight'] = 1
                        print(f"  ✅ 更新 {item_id}: weight {old_weight} → 1")
                        updated = True
                    else:
                        print(f"  ℹ️  {item_id}: weight 已為 1，無需更新")
        
        if updated:
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"💾 {json_file}: 已保存\n")
        else:
            print(f"⏭️  {json_file}: 無需修改\n")
        
        return updated
    
    except json.JSONDecodeError as e:
        print(f"❌ {json_file}: JSON 解析錯誤 - {e}")
        return False
    except Exception as e:
        print(f"❌ {json_file}: 錯誤 - {e}")
        return False

def main():
    """主函數"""
    # 找到所有 case_*.constraint_spec.json 檔案
    output_dir = Path(__file__).parent.parent / "outputs"
    pattern = str(output_dir / "case_*.constraint_spec.json")
    
    files = sorted(glob.glob(pattern))
    
    if not files:
        print(f"❌ 找不到任何 case_*.constraint_spec.json 檔案在 {output_dir}")
        return
    
    print(f"📁 在 {output_dir} 找到 {len(files)} 個檔案\n")
    print("=" * 60)
    
    updated_count = 0
    for json_file in files:
        print(f"📄 處理: {Path(json_file).name}")
        if update_penalty_weights(json_file):
            updated_count += 1
    
    print("=" * 60)
    print(f"\n✅ 完成！共修改了 {updated_count} 個檔案")

if __name__ == "__main__":
    main()
