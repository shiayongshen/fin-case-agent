"""
診斷 Chroma 向量維度問題
"""
import chromadb
from chromadb.config import Settings
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
import os
from dotenv import load_dotenv

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

print("=" * 60)
print("🔍 Chroma 向量維度診斷工具")
print("=" * 60)

# 初始化 Chroma
chroma_settings = Settings(
    persist_directory="./chroma_db",
    is_persistent=True
)
chroma_client = chromadb.Client(chroma_settings)

# 列出所有集合
print("\n📋 已存在的集合：")
collections = chroma_client.list_collections()
for collection in collections:
    print(f"  - {collection.name}")

# 檢查每個集合的維度
print("\n📊 檢查集合詳情：")
for collection in collections:
    try:
        # 嘗試不指定嵌入函數獲取集合
        coll = chroma_client.get_collection(collection.name)
        count = coll.count()
        print(f"\n集合: {collection.name}")
        print(f"  文檔數: {count}")
        
        # 取第一個向量查看維度
        if count > 0:
            data = coll.get(limit=1)
            if data and data.get('embeddings') and len(data['embeddings']) > 0:
                embedding_dim = len(data['embeddings'][0])
                print(f"  向量維度: {embedding_dim}")
            else:
                print(f"  向量維度: 無法獲取")
    except Exception as e:
        print(f"\n集合: {collection.name}")
        print(f"  ❌ 錯誤: {e}")

# 現在嘗試用 text-embedding-ada-002 訪問新集合
print("\n\n🔧 嘗試用 text-embedding-ada-002 訪問集合：")
embedding_fn = OpenAIEmbeddingFunction(
    api_key=OPENAI_API_KEY,
    model_name='text-embedding-ada-002'
)

try:
    # 嘗試獲取或創建集合
    test_coll = chroma_client.get_collection(  # type: ignore
        name="legal_cases_v2024",
        embedding_function=embedding_fn  # type: ignore
    )
    print(f"✅ 成功獲取集合 'legal_cases_v2024'（使用 text-embedding-ada-002）")
    print(f"   文檔數: {test_coll.count()}")
    
    # 嘗試搜索
    print(f"\n🔍 嘗試搜索 '資本不足的案例'...")
    results = test_coll.query(
        query_texts=['資本不足的案例'],
        n_results=3
    )
    
    if results and results['documents'] and len(results['documents']) > 0:
        print(f"✅ 搜索成功！找到 {len(results['documents'][0])} 個結果")
        for i, doc in enumerate(results['documents'][0]):
            print(f"\n  結果 {i+1}:")
            print(f"    內容: {doc[:100]}...")
            if results['metadatas'] and len(results['metadatas']) > 0:
                metadata = results['metadatas'][0][i] if i < len(results['metadatas'][0]) else {}
                print(f"    case_id: {metadata.get('case_id', 'N/A')}")
    else:
        print(f"❌ 搜索無結果")
        
except Exception as e:
    print(f"❌ 無法獲取或搜索集合 'legal_cases_v2024': {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("💡 建議：")
print("  1. 如果舊集合使用了不同的嵌入模型，需要使用相同模型")
print("  2. 可以刪除舊集合或使用不同的集合名稱")
print("  3. 確保所有應用使用相同的嵌入函數配置")
print("=" * 60)
