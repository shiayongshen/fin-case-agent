#!/usr/bin/env python3
"""
修復 Chroma 集合：刪除舊的 legal_cases_v2024（384 維度）
重新建立使用 text-embedding-ada-002 的集合
"""

import os
from chromadb import Client
from chromadb.config import Settings
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
from dotenv import load_dotenv

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

print("="*80)
print("🔧 修復 Chroma 集合")
print("="*80)

# 初始化 Chroma
client = Client(Settings(
    persist_directory="chroma_db",
    is_persistent=True
))

# 1. 列出現有集合
print("\n[步驟 1] 列出現有集合...")
collections = client.list_collections()
print(f"找到 {len(collections)} 個集合：")
for coll in collections:
    print(f"  - {coll.name}")

# 2. 刪除舊的 legal_cases_v2024
print("\n[步驟 2] 刪除舊的 legal_cases_v2024 集合...")
try:
    client.delete_collection(name="legal_cases_v2024")
    print("✅ 已刪除 legal_cases_v2024")
except Exception as e:
    print(f"⚠️  無法刪除 legal_cases_v2024: {e}")

# 3. 驗證刪除
print("\n[步驟 3] 驗證刪除...")
collections = client.list_collections()
remaining_names = [coll.name for coll in collections]
if "legal_cases_v2024" in remaining_names:
    print("❌ legal_cases_v2024 仍然存在")
else:
    print("✅ legal_cases_v2024 已成功刪除")

# 4. 建立新的集合（使用 text-embedding-ada-002）
print("\n[步驟 4] 建立新的 legal_cases_v2024 集合...")
try:
    embedding_function = OpenAIEmbeddingFunction(
        api_key=OPENAI_API_KEY,
        model_name="text-embedding-ada-002"
    )
    
    collection = client.get_or_create_collection(
        name="legal_cases_v2024",
        embedding_function=embedding_function,
        metadata={"hnsw:space": "cosine"}
    )
    
    print(f"✅ 已建立新集合: legal_cases_v2024")
    print(f"   - 嵌入模型: text-embedding-ada-002")
    print(f"   - 預期維度: 1536")
    print(f"   - 當前文件數: {collection.count()}")
    
except Exception as e:
    print(f"❌ 建立集合失敗: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*80)
print("✅ 集合修復完成")
print("="*80)
