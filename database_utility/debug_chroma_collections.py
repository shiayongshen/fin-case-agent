#!/usr/bin/env python3
"""
詳細檢查 Chroma 集合的嵌入維度信息
"""

import os
from chromadb import Client
from chromadb.config import Settings

print("="*80)
print("🔍 Chroma 集合詳細信息診斷")
print("="*80)

client = Client(Settings(
    persist_directory="chroma_db",
    is_persistent=True
))

collections = client.list_collections()

for coll in collections:
    print(f"\n集合名稱: {coll.name}")
    print(f"  - ID: {coll.id}")
    print(f"  - 元數據: {coll.metadata}")
    
    # 獲取集合中的文件
    try:
        all_data = coll.get()
        doc_count = len(all_data.get('ids', []))
        print(f"  - 文件數量: {doc_count}")
        
        # 如果有文件，嘗試取得第一個嵌入來檢查維度
        embeddings = all_data.get('embeddings')
        if embeddings and len(embeddings) > 0:
            first_embedding = embeddings[0]
            if first_embedding:
                embedding_dim = len(first_embedding)
                print(f"  - 嵌入維度: {embedding_dim}")
            else:
                print(f"  - 嵌入維度: 未知 (沒有嵌入)")
        else:
            print(f"  - 嵌入維度: 未知 (沒有嵌入)")
    except Exception as e:
        print(f"  - 無法取得文件信息: {e}")

print("\n" + "="*80)
