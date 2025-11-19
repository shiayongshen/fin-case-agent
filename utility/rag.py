#!/usr/bin/env python3
"""
RAG 搜索主程序
可以直接運行或作為模塊導入
"""
import sys
import os

# 支持作為腳本直接運行或作為模塊導入
try:
    from .legal_search import search_and_rerank
except ImportError:
    # 直接運行時，使用絕對導入
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from legal_search import search_and_rerank


def main():
    print("="*70)
    print("🔍 RAG 搜索測試")
    print("="*70)
    
    query = "保險法資本適足率"
    print(f"\n[查詢] {query}\n")
    
    result = search_and_rerank(query, top_k=3)
    
    print(f"\n[結果統計]")
    print(f"  - 找到 {len(result['ids'])} 個相關結果")
    
    print(result)
if __name__ == "__main__":
    main()