#!/usr/bin/env python3
"""
演示 search_and_rerank 的 metadata filter 功能
展示如何按 case_id 和其他條件篩選搜索結果
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utility.legal_search import (
    search_and_rerank, 
    build_case_id_filter,
    build_composite_filter,
    build_range_filter
)

def demo_basic_search():
    """演示 1: 基本搜索（不使用過濾）"""
    print("=" * 80)
    print("演示 1: 基本搜索（不過濾）")
    print("=" * 80)
    
    query = "內線交易"
    results = search_and_rerank(query=query, top_k=3)
    
    print(f"\n查詢: {query}")
    print(f"找到 {len(results['ids'])} 個結果\n")
    
    for i, (case_id, score) in enumerate(zip(results['ids'], results['scores']), 1):
        print(f"{i}. Case ID: {case_id}, Score: {score:.4f}")
    
    return results


def demo_case_id_filter():
    """演示 2: 按 case_id 搜索"""
    print("\n" + "=" * 80)
    print("演示 2: 按 case_id 搜索（精確查找特定案例）")
    print("=" * 80)
    
    # 先從第一個演示中獲取一個 case_id
    demo_results = demo_basic_search()
    results = None
    
    if demo_results['ids']:
        target_case_id = demo_results['ids'][0]
        
        # 使用 case_id filter
        filter_dict = build_case_id_filter(target_case_id)
        query = "內線交易"
        
        print(f"\n搜索 case_id = {target_case_id}")
        results = search_and_rerank(query=query, top_k=5, metadata_filters=filter_dict)
        
        print(f"找到 {len(results['ids'])} 個結果\n")
        
        for i, case_id in enumerate(results['ids'], 1):
            print(f"{i}. Case ID: {case_id}")
    
    return results


def demo_composite_filter():
    """演示 3: 複合條件過濾"""
    print("\n" + "=" * 80)
    print("演示 3: 複合條件過濾（多個 metadata 字段）")
    print("=" * 80)
    
    # 假設我們知道一些可用的 metadata 字段
    # 這個演示顯示語法，實際字段需要根據您的數據調整
    
    filter_dict = build_composite_filter(
        case_status="active"  # 可以根據需要調整字段名和值
    )
    
    query = "銀行法 違規"
    
    print(f"\n查詢: {query}")
    print(f"過濾條件: {filter_dict}")
    
    try:
        results = search_and_rerank(query=query, top_k=3, metadata_filters=filter_dict)
        print(f"找到 {len(results['ids'])} 個結果\n")
        
        for i, case_id in enumerate(results['ids'], 1):
            print(f"{i}. Case ID: {case_id}")
    except Exception as e:
        print(f"搜索失敗: {e}")
        print("（這可能是因為 metadata 字段不存在，請檢查實際的 metadata 結構）")
    
    return None


def demo_range_filter():
    """演示 4: 範圍過濾"""
    print("\n" + "=" * 80)
    print("演示 4: 範圍過濾（用於數值型 metadata）")
    print("=" * 80)
    
    # 假設有一個 penalty_weight 字段，我們想要搜索特定範圍內的案例
    filter_dict = build_range_filter("penalty_weight", min_val=0.5, max_val=1.0)
    
    query = "證券交易"
    
    print(f"\n查詢: {query}")
    print(f"過濾條件: penalty_weight 在 0.5 到 1.0 之間")
    print(f"Filter dict: {filter_dict}")
    
    try:
        results = search_and_rerank(query=query, top_k=3, metadata_filters=filter_dict)
        print(f"找到 {len(results['ids'])} 個結果\n")
        
        for i, case_id in enumerate(results['ids'], 1):
            print(f"{i}. Case ID: {case_id}")
    except Exception as e:
        print(f"搜索失敗: {e}")
        print("（這可能是因為 metadata 字段不存在或類型不匹配）")
    
    return None


def demo_custom_filter():
    """演示 5: 自定義 Chroma 過濾語法"""
    print("\n" + "=" * 80)
    print("演示 5: 自定義高級過濾（使用 Chroma 原生語法）")
    print("=" * 80)
    
    # Chroma 支持的過濾語法示例：
    # - {"field": "value"} - 精確匹配
    # - {"field": {"$eq": "value"}} - 等於
    # - {"field": {"$ne": "value"}} - 不等於
    # - {"field": {"$gt": 5}} - 大於
    # - {"field": {"$gte": 5}} - 大於等於
    # - {"$and": [condition1, condition2]} - 邏輯與
    # - {"$or": [condition1, condition2]} - 邏輯或
    
    custom_filter = {
        "$or": [
            {"case_id": "case_0"},
            {"case_id": "case_1"},
            {"case_id": "case_2"}
        ]
    }
    
    query = "內線交易"
    
    print(f"\n查詢: {query}")
    print(f"過濾條件: case_id 在 [case_0, case_1, case_2] 中")
    print(f"Filter dict: {custom_filter}")
    
    try:
        results = search_and_rerank(query=query, top_k=3, metadata_filters=custom_filter)
        print(f"找到 {len(results['ids'])} 個結果\n")
        
        for i, case_id in enumerate(results['ids'], 1):
            print(f"{i}. Case ID: {case_id}")
    except Exception as e:
        print(f"搜索失敗: {e}")
    
    return None


def main():
    """主函數"""
    print("\n")
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 78 + "║")
    print("║" + "  search_and_rerank Metadata Filter 功能演示".center(78) + "║")
    print("║" + " " * 78 + "║")
    print("╚" + "=" * 78 + "╝")
    print("\n此演示展示如何使用 metadata filter 功能進行高級搜索\n")
    
    try:
        # 運行演示
        demo_basic_search()
        demo_case_id_filter()
        demo_composite_filter()
        demo_range_filter()
        demo_custom_filter()
        
        print("\n" + "=" * 80)
        print("✅ 所有演示完成")
        print("=" * 80)
        print("\n💡 API 使用總結:")
        print("-" * 80)
        print("1. 基本搜索:")
        print("   results = search_and_rerank(query='搜索詞')")
        print()
        print("2. 按 case_id 搜索:")
        print("   filter = build_case_id_filter('case_0')")
        print("   results = search_and_rerank(query='搜索詞', metadata_filters=filter)")
        print()
        print("3. 複合過濾:")
        print("   filter = build_composite_filter(case_id='case_0', status='active')")
        print("   results = search_and_rerank(query='搜索詞', metadata_filters=filter)")
        print()
        print("4. 範圍過濾:")
        print("   filter = build_range_filter('penalty', min_val=0.5, max_val=1.0)")
        print("   results = search_and_rerank(query='搜索詞', metadata_filters=filter)")
        print()
        print("5. 自定義過濾 (Chroma 原生語法):")
        print("   filter = {'$or': [{'case_id': 'case_0'}, {'case_id': 'case_1'}]}")
        print("   results = search_and_rerank(query='搜索詞', metadata_filters=filter)")
        print("=" * 80)
        
        return 0
    
    except Exception as e:
        print(f"\n❌ 演示過程中發生錯誤: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
