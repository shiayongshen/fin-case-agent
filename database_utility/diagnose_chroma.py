#!/usr/bin/env python3
"""
診斷 Chroma 數據庫問題
檢查是否有鎖定或損壞
"""
import os
import sys
import threading
import time
from chromadb import Client
from chromadb.config import Settings
from dotenv import load_dotenv

load_dotenv()

CHROMA_DB_PATH = "./chroma_db"
COLLECTION_NAME = "legal_cases_v2024"
TIMEOUT = 30

def test_with_timeout(func, timeout=30, operation_name="操作"):
    """在線程中執行並設置超時"""
    result = {"value": None, "exception": None, "done": False}
    
    def wrapper():
        try:
            print(f"[{operation_name}] 線程開始...", flush=True)
            result["value"] = func()
            print(f"[{operation_name}] ✅ 完成", flush=True)
            result["done"] = True
        except Exception as e:
            print(f"[{operation_name}] ❌ 異常: {e}", flush=True)
            result["exception"] = e
            result["done"] = True
    
    thread = threading.Thread(target=wrapper, daemon=False)  # 改為 non-daemon
    thread.start()
    thread.join(timeout=timeout)
    
    if thread.is_alive():
        print(f"[{operation_name}] ⏱️ 超時！線程仍在運行", flush=True)
        return None, TimeoutError(f"{operation_name} 超時")
    
    if result["exception"]:
        return None, result["exception"]
    
    return result["value"], None

print("="*80)
print("🔍 Chroma 數據庫診斷")
print("="*80)

# 1. 測試基本連接
print("\n[步驟 1] 測試 Chroma 客戶端連接...")
def connect_chroma():
    chroma_settings = Settings(
        persist_directory=CHROMA_DB_PATH,
        is_persistent=True
    )
    return Client(chroma_settings)

client_result, client_error = test_with_timeout(
    connect_chroma,
    timeout=TIMEOUT,
    operation_name="連接客戶端"
)

if client_error:
    print(f"  ❌ 連接失敗: {client_error}")
    sys.exit(1)

chroma_client = client_result
print(f"  ✅ 連接成功")

# 2. 測試列表集合
print("\n[步驟 2] 列表所有集合...")
def list_collections():
    collections = chroma_client.list_collections()
    return collections

list_result, list_error = test_with_timeout(
    list_collections,
    timeout=TIMEOUT,
    operation_name="列表集合"
)

if list_error:
    print(f"  ❌ 列表失敗: {list_error}")
else:
    print(f"  ✅ 找到 {len(list_result)} 個集合:")
    for coll in list_result:
        print(f"    - {coll.name}")

# 3. 測試獲取特定集合
print(f"\n[步驟 3] 獲取集合 '{COLLECTION_NAME}'...")
def get_collection():
    try:
        return chroma_client.get_collection(name=COLLECTION_NAME)
    except Exception:
        return chroma_client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"}
        )

get_result, get_error = test_with_timeout(
    get_collection,
    timeout=TIMEOUT,
    operation_name="獲取集合"
)

if get_error:
    print(f"  ❌ 獲取失敗: {get_error}")
    sys.exit(1)

collection = get_result
print(f"  ✅ 獲取成功")

# 4. 測試計數
print(f"\n[步驟 4] 計數集合文檔...")
def count_collection():
    return collection.count()

count_result, count_error = test_with_timeout(
    count_collection,
    timeout=TIMEOUT,
    operation_name="計數"
)

if count_error:
    print(f"  ❌ 計數失敗: {count_error}")
else:
    print(f"  ✅ 集合包含 {count_result} 個文檔")

# 5. 測試添加單個文檔
print(f"\n[步驟 5] 測試添加文檔...")
def add_test_doc():
    collection.add(
        ids=["test_doc"],
        documents=["This is a test document"],
        metadatas=[{"test": True}]
    )
    return True

add_result, add_error = test_with_timeout(
    add_test_doc,
    timeout=TIMEOUT,
    operation_name="添加文檔"
)

if add_error:
    print(f"  ❌ 添加失敗: {add_error}")
    print("\n⚠️  問題診斷:")
    if "database is locked" in str(add_error).lower():
        print("  - Chroma SQLite 數據庫被鎖定")
        print("  - 可能有其他進程在訪問數據庫")
        print("  - 嘗試停止其他進程或重啟應用")
    else:
        print(f"  - 未知錯誤: {add_error}")
else:
    print(f"  ✅ 添加成功")

# 6. 清理測試文檔
print(f"\n[步驟 6] 清理測試文檔...")
def delete_test_doc():
    collection.delete(ids=["test_doc"])
    return True

delete_result, delete_error = test_with_timeout(
    delete_test_doc,
    timeout=TIMEOUT,
    operation_name="刪除文檔"
)

if delete_error:
    print(f"  ❌ 刪除失敗: {delete_error}")
else:
    print(f"  ✅ 清理成功")

print("\n" + "="*80)
print("✅ 診斷完成")
print("="*80)
print("\n💡 如果在 '添加文檔' 步驟失敗，問題原因:")
print("  1. Chroma SQLite 數據庫被鎖定 → 停止其他進程")
print("  2. 磁盤空間不足 → 清理磁盤")
print("  3. 權限問題 → 檢查 chroma_db 文件夾權限")
print("  4. 數據庫損壞 → 刪除 chroma_db 並重新初始化\n")
