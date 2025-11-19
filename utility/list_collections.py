#!/usr/bin/env python3
"""列出 Chroma 數據庫中的所有集合"""
from chromadb import Client
from chromadb.config import Settings

chroma_settings = Settings(
    persist_directory="./chroma_db",
    is_persistent=True
)

client = Client(chroma_settings)
collections = client.list_collections()

print(f"✅ 找到 {len(collections)} 個集合:\n")
for coll in collections:
    try:
        count = coll.count()
        print(f"  - {coll.name}: {count} 個文檔")
    except Exception as e:
        print(f"  - {coll.name}: (計數失敗: {e})")

if not collections:
    print("  ⚠️  數據庫為空")
