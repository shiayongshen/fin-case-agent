#!/usr/bin/env python3
"""
測試 search_and_rerank 函數的診斷腳本
逐步檢查各個環節以診斷問題
"""

import os
import sys
from dotenv import load_dotenv
from chromadb import Client
from chromadb.config import Settings
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

print("="*80)
print("🔍 search_and_rerank 診斷測試")
print("="*80)

# 1. 檢查 Chroma 連接
print("\n[步驟 1] 檢查 Chroma 連接...")
try:
    client = Client(Settings(
        persist_directory="chroma_db",
        is_persistent=True
    ))
    print("✅ Chroma 連接成功")
except Exception as e:
    print(f"❌ Chroma 連接失敗: {e}")
    sys.exit(1)

# 2. 列出所有集合
print("\n[步驟 2] 列出所有 Chroma 集合...")
try:
    collections = client.list_collections()
    print(f"✅ 找到 {len(collections)} 個集合:")
    for coll in collections:
        print(f"   - {coll.name}")
except Exception as e:
    print(f"❌ 列出集合失敗: {e}")
    sys.exit(1)

# 3. 檢查目標集合 legal_cases_v2024
print("\n[步驟 3] 檢查目標集合 legal_cases_v2024...")
try:
    target_collection = client.get_collection("legal_cases_v2024")
    print(f"✅ 成功獲取集合 legal_cases_v2024")
    
    # 獲取集合元數據
    count = target_collection.count()
    print(f"   - 文件數量: {count}")
    
    # 獲取集合的元數據
    metadata = target_collection.metadata
    print(f"   - 集合元數據: {metadata}")
    
except Exception as e:
    print(f"❌ 無法獲取 legal_cases_v2024: {e}")
    sys.exit(1)

# 4. 測試嵌入函數
print("\n[步驟 4] 測試 OpenAI 嵌入函數...")
try:
    embedding_fn = OpenAIEmbeddingFunction(
        api_key=OPENAI_API_KEY,
        model_name='text-embedding-ada-002'
    )
    print("✅ OpenAI 嵌入函數初始化成功")
    
    # 測試生成一個嵌入
    test_embedding = embedding_fn(["測試文本"])
    embedding_dim = len(test_embedding[0]) if test_embedding else 0
    print(f"   - 嵌入維度: {embedding_dim}")
    
    if embedding_dim != 1536:
        print(f"   ⚠️  警告: 預期維度為 1536，但得到 {embedding_dim}")
    
except Exception as e:
    print(f"❌ 嵌入函數測試失敗: {e}")
    sys.exit(1)

# 5. 檢查集合的嵌入維度
print("\n[步驟 5] 檢查集合中文件的嵌入維度...")
try:
    # 取得集合中的所有文件
    all_docs = target_collection.get()
    
    if all_docs and all_docs.get('ids'):
        print(f"   - 集合中有 {len(all_docs['ids'])} 個文件")
        
        # 顯示前幾個文件的 ID 和元數據
        metadatas = all_docs.get('metadatas') or []
        for i, (doc_id, metadata) in enumerate(zip(all_docs['ids'][:3], metadatas[:3])):
            print(f"     {i+1}. ID: {doc_id}")
            if metadata:
                print(f"        元數據: {metadata}")
    else:
        print("   ⚠️  集合中沒有文件")
        
except Exception as e:
    print(f"❌ 檢查集合文件失敗: {e}")

# 6. 測試集合查詢 (不使用嵌入)
print("\n[步驟 6] 測試集合基本查詢...")
try:
    # 先用不需要嵌入的方式查詢
    all_results = target_collection.get()
    print(f"✅ 基本查詢成功，找到 {len(all_results['ids'])} 個文件")
    
except Exception as e:
    print(f"❌ 基本查詢失敗: {e}")

# 7. 測試帶嵌入的查詢
print("\n[步驟 7] 測試帶嵌入的查詢...")
try:
    query = "資本不足"
    print(f"   - 查詢文本: {query}")
    
    # 首先生成查詢嵌入
    query_embedding = embedding_fn([query])
    print(f"   - 查詢嵌入維度: {len(query_embedding[0])}")
    
    # 然後進行集合查詢
    search_results = target_collection.query(
        query_texts=[query],
        n_results=5
    )
    
    print(f"✅ 查詢成功")
    print(f"   - 返回 {len(search_results['ids'][0])} 個結果")
    
    if search_results['ids'][0]:
        documents = (search_results.get('documents') or [[]])[0] or []
        metadatas = (search_results.get('metadatas') or [[]])[0] or []
        
        for i, (doc_id, doc, metadata) in enumerate(zip(
            search_results['ids'][0][:3],
            documents[:3],
            metadatas[:3]
        )):
            print(f"     {i+1}. ID: {doc_id}")
            if doc:
                print(f"        內容: {doc[:100]}...")
            if metadata:
                print(f"        元數據: {metadata}")
    
except Exception as e:
    print(f"❌ 查詢失敗: {e}")
    import traceback
    traceback.print_exc()

# 8. 測試完整的 search_and_rerank 函數
print("\n[步驟 8] 測試完整的 search_and_rerank 函數...")
try:
    from utility.legal_search import search_and_rerank
    
    query = "資本不足的案例"
    print(f"   - 查詢: {query}")
    
    results = search_and_rerank(query, top_k=5)
    
    print(f"✅ search_and_rerank 成功")
    print(f"   - 返回的排序文件數: {len(results['ranked_documents'])}")
    print(f"   - 返回的 IDs: {results['ids']}")
    
    if results['ranked_documents']:
        for i, (doc, metadata, doc_id) in enumerate(zip(
            results['ranked_documents'],
            results['ranked_metadatas'],
            results['ids']
        )):
            print(f"     {i+1}. ID: {doc_id}")
            print(f"        內容: {doc[:100]}...")
            print(f"        元數據: {metadata}")
    
except Exception as e:
    print(f"❌ search_and_rerank 失敗: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*80)
print("🔍 診斷測試完成")
print("="*80)
