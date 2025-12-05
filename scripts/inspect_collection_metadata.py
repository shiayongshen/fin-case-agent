#!/usr/bin/env python3
"""
檢查 Chroma collection 的 metadata 結構
並將一筆完整資料存成 JSON 文件
"""

import sys
import os
import json
from pathlib import Path

# 支持腳本直接運行
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utility.legal_search import get_chroma_collection

def inspect_collection():
    """檢查 collection 的 metadata 結構"""
    print("=" * 70)
    print("🔍 Chroma Collection Metadata 檢查工具")
    print("=" * 70)
    
    # 獲取 collection
    collection = get_chroma_collection()
    
    if not collection:
        print("❌ 無法獲取 collection")
        return None, set()
    
    # 獲取總數量
    total_count = collection.count()
    print(f"\n📊 Collection 總文檔數: {total_count}\n")
    
    if total_count == 0:
        print("⚠️  Collection 為空，沒有可檢查的數據")
        return None, set()
    
    # 獲取前 5 筆資料來分析 metadata 結構
    print("📋 正在獲取前 5 筆資料來分析 metadata 結構...\n")
    results = collection.get(limit=5)
    
    # 分析 metadata 結構
    metadata_keys = set()
    sample_data = None
    
    if results['metadatas']:
        for i, metadata in enumerate(results['metadatas']):
            if metadata:
                metadata_keys.update(metadata.keys())
                if sample_data is None:
                    doc = results['documents'][i] if results['documents'] and i < len(results['documents']) else None
                    sample_data = {
                        'index': i,
                        'id': results['ids'][i],
                        'metadata': metadata,
                        'document_preview': doc[:200] if doc else None
                    }
    
    # 顯示找到的 metadata 鍵
    print("🔑 找到的 Metadata 鍵:")
    print("-" * 70)
    for i, key in enumerate(sorted(metadata_keys), 1):
        print(f"{i}. {key}")
    print()
    
    # 顯示第一筆資料的詳細信息
    if sample_data:
        print("📝 第一筆資料詳細信息:")
        print("-" * 70)
        print(f"ID: {sample_data['id']}")
        print(f"\nMetadata:")
        for key, value in sample_data['metadata'].items():
            if isinstance(value, str) and len(value) > 100:
                print(f"  {key}: {value[:100]}...")
            else:
                print(f"  {key}: {value}")
        print(f"\nDocument Preview (前 200 字):")
        if sample_data['document_preview']:
            print(f"  {sample_data['document_preview']}")
    
    return results, metadata_keys

def save_sample_to_json(results, metadata_keys):
    """將第一筆資料完整保存為 JSON"""
    if not results or not results['ids']:
        print("\n❌ 沒有數據可保存")
        return
    
    # 構建完整的第一筆資料
    sample_record = {
        "id": results['ids'][0],
        "document": results['documents'][0],
        "metadata": results['metadatas'][0] if results['metadatas'] else {},
        "metadata_keys": sorted(list(metadata_keys)),
        "retrieval_info": {
            "total_records": results.get('total_records', 'unknown'),
            "collection_name": "legal_cases_v2024"
        }
    }
    
    # 保存為 JSON
    output_path = Path(__file__).parent / "outputs" / "collection_sample.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(sample_record, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ 樣本資料已保存到: {output_path}")
    print(f"   文件大小: {output_path.stat().st_size} bytes")
    
    return output_path

def main():
    """主函數"""
    try:
        results, metadata_keys = inspect_collection()
        
        if results and metadata_keys:
            print("\n" + "=" * 70)
            output_path = save_sample_to_json(results, metadata_keys)
            
            print("\n📊 Summary:")
            print(f"  - Metadata 鍵數量: {len(metadata_keys)}")
            print(f"  - 檢查的文檔數: {len(results['ids'])}")
            print(f"  - 已保存樣本文件")
            print("=" * 70)
        else:
            print("\n❌ 無法獲取有效的結果")
            return 1
    
    except Exception as e:
        print(f"\n❌ 發生錯誤: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
