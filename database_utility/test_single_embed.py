#!/usr/bin/env python3
"""
測試單個案例的 embedding 和存儲
用於診斷卡住的問題
"""
import os
import sys
import time
import threading
import sqlite3
import shutil
from dotenv import load_dotenv
import tiktoken
from openai import OpenAI
import chromadb
from chromadb.config import Settings
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
EMBEDDING_MODEL = "text-embedding-ada-002"
MAX_TOKENS = 8150
CHROMA_DB_PATH = "./chroma_db"
COLLECTION_NAME = "legal_cases_v2024"

# 初始化
print("[1] 初始化 OpenAI 客戶端...")
client = OpenAI(api_key=OPENAI_API_KEY, timeout=60)
print("  ✅ 完成\n")

print("[2] 初始化 tiktoken...")
encoding = tiktoken.encoding_for_model("text-embedding-ada-002")
print("  ✅ 完成\n")

# 清理鎖定
print("[3] 清理可能的 SQLite 鎖定...")
db_path = os.path.join(CHROMA_DB_PATH, "chroma.sqlite3")
wal_path = db_path + "-wal"
shm_path = db_path + "-shm"

if os.path.exists(wal_path):
    try:
        os.remove(wal_path)
        print(f"  ✅ 已刪除 WAL 文件")
    except Exception as e:
        print(f"  ⚠️  刪除 WAL 失敗: {e}")

if os.path.exists(shm_path):
    try:
        os.remove(shm_path)
        print(f"  ✅ 已刪除 SHM 文件")
    except Exception as e:
        print(f"  ⚠️  刪除 SHM 失敗: {e}")

print()

# 連接 Chroma
print("[4] 連接 Chroma...")
chroma_settings = Settings(
    persist_directory=CHROMA_DB_PATH,
    is_persistent=True
)
chroma_client = chromadb.Client(chroma_settings)
print("  ✅ 完成\n")

# 創建 embedding 函數
print("[5] 創建 OpenAI embedding 函數...")
embedding_function = OpenAIEmbeddingFunction(
    api_key=OPENAI_API_KEY,
    model_name=EMBEDDING_MODEL
)
print("  ✅ 完成\n")

# 獲取或創建集合
print("[6] 獲取集合...")
try:
    collection = chroma_client.get_collection(
        name=COLLECTION_NAME,
        embedding_function=embedding_function
    )
    print(f"  ✅ 已獲取 {COLLECTION_NAME}\n")
except Exception:
    print(f"  創建新集合 {COLLECTION_NAME}...")
    collection = chroma_client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=embedding_function,
        metadata={"hnsw:space": "cosine"}
    )
    print(f"  ✅ 已創建\n")

# 測試案例文本
test_case_id = "test_case_0"
test_case_text = """
法院判決書
案號：108 年訴字第 1234 號
當事人：原告 甲○○ 被告 乙○○
事實摘要：本案涉及買賣契約糾紛，原告主張被告未依約給付款項，
被告辯稱已於約定期限內給付，並提出銀行轉帳証明。法院經審理，
認定被告確已給付，原告請求駁回。

法律問題：買賣契約是否成立、給付是否遲延。

判決結論：原告之訴駁回。被告應給付訴訟費用。

相關法條：民法第 345 條（買賣）、民法第 422 條（給付遲延）
""" * 3  # 重複三次讓文本更長

print("[7] 測試 embedding...")
print(f"  案例文本長度: {len(test_case_text)} 字")

# 截斷
tokens = encoding.encode(test_case_text)
token_count = len(tokens)
print(f"  Token 數: {token_count}")

if token_count > MAX_TOKENS:
    truncated_tokens = tokens[:MAX_TOKENS]
    embedding_text = encoding.decode(truncated_tokens)
    print(f"  已截斷至 {MAX_TOKENS} tokens")
else:
    embedding_text = test_case_text

print(f"\n  調用 OpenAI embedding API...")
print(f"  (超時設置: 60秒)", flush=True)

try:
    start_time = time.time()
    response = client.embeddings.create(
        input=embedding_text,
        model=EMBEDDING_MODEL,
        timeout=60
    )
    elapsed = time.time() - start_time
    
    embedding = response.data[0].embedding
    print(f"  ✅ 完成 ({elapsed:.1f}秒)")
    print(f"  Embedding 維度: {len(embedding)}\n")
except Exception as e:
    print(f"  ❌ 失敗: {e}\n")
    sys.exit(1)

# 測試存儲
print("[8] 測試存儲到 Chroma...")
metadata = {
    "case_id": test_case_id,
    "token_count": token_count,
    "related_laws": "民法第 345 條、民法第 422 條"
}

print(f"  案例 ID: {test_case_id}")
print(f"  Embedding 維度: {len(embedding)}")
print(f"  Document 長度: {len(embedding_text)}")
print(f"  Metadata: {metadata}")
print(f"\n  調用 collection.add()...", flush=True)

try:
    start_time = time.time()
    
    # 用線程帶超時執行
    result = {"done": False, "error": None}
    
    def store_in_thread():
        try:
            print(" [線程] add() 開始", flush=True)
            collection.add(
                ids=[test_case_id],
                embeddings=[embedding],
                documents=[embedding_text],
                metadatas=[metadata]
            )
            print(" [線程] add() 完成", flush=True)
            result["done"] = True
        except Exception as e:
            print(f" [線程] 異常: {e}", flush=True)
            result["error"] = e
    
    thread = threading.Thread(target=store_in_thread, daemon=False)
    thread.start()
    thread.join(timeout=30)  # 30 秒超時
    
    if thread.is_alive():
        elapsed = time.time() - start_time
        print(f" ⏱️  超時！(已等待 {elapsed:.1f}秒)")
        print(f"\n⚠️  問題診斷:")
        print(f"  - collection.add() 卡住")
        print(f"  - Chroma SQLite 數據庫可能被鎖定")
        print(f"  - 或者數據太大無法處理")
        sys.exit(1)
    
    elapsed = time.time() - start_time
    
    if result["error"]:
        print(f" ❌ 異常: {result['error']}")
        sys.exit(1)
    
    print(f"\n  ✅ 完成 ({elapsed:.1f}秒)\n")
    
except Exception as e:
    print(f"  ❌ 異常: {e}\n")
    sys.exit(1)

# 驗證
print("[9] 驗證...")
try:
    count = collection.count()
    print(f"  ✅ 集合現有 {count} 個文檔\n")
except Exception as e:
    print(f"  ⚠️  計數失敗: {e}\n")

print("="*60)
print("✅ 測試成功！")
print("="*60)
print("\n結論:")
print("  - OpenAI embedding API 正常")
print("  - Chroma 存儲正常")
print("  - 問題可能出在 embed_cases_to_chroma.py 的其他部分\n")
