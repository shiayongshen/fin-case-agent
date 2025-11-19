"""
將案例存入向量資料庫
直接 embedding 整個案例文本（超過 token 限制則截斷）
"""
import csv
import os
import sys
import time
import threading
import sqlite3
import shutil
from datetime import datetime
from dotenv import load_dotenv
import tiktoken
from openai import OpenAI
import chromadb
from chromadb.config import Settings
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction

load_dotenv()

# ===== 配置 =====
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
EMBEDDING_MODEL = "text-embedding-ada-002"
MAX_TOKENS = 8150
CHROMA_DB_PATH = "./chroma_db"
COLLECTION_NAME = "legal_cases_v2024"  # 與 RAG 搜索對應
# 超時設置
EMBEDDING_TIMEOUT = 60  # OpenAI embedding 超時（秒）
CHROMA_TIMEOUT = 30    # Chroma 操作超時（秒）
MAX_RETRIES = 2        # 最大重試次數

class TimeoutException(Exception):
    pass

def run_with_timeout(func, args=(), timeout=30, operation_name="操作"):
    """
    在線程中運行函數並設置超時
    使用線程而不是信號，更穩定
    """
    result = {"value": None, "exception": None}
    
    def wrapper():
        try:
            result["value"] = func(*args)
        except Exception as e:
            result["exception"] = e
    
    thread = threading.Thread(target=wrapper, daemon=True)
    thread.start()
    thread.join(timeout=timeout)
    
    if thread.is_alive():
        # 線程仍在運行 = 超時
        print(f" ⏱️ 超時（{timeout}秒）", end="", flush=True)
        raise TimeoutException(f"{operation_name}超時")
    
    if result["exception"]:
        raise result["exception"]
    
    return result["value"]

# 初始化
client = OpenAI(api_key=OPENAI_API_KEY, timeout=EMBEDDING_TIMEOUT)
encoding = tiktoken.encoding_for_model("text-embedding-ada-002")

# ===== 重要：清理可能的 Chroma SQLite 鎖定 =====
print("[CLEANUP] 檢查 Chroma 數據庫鎖定情況...")
db_path = os.path.join(CHROMA_DB_PATH, "chroma.sqlite3")
wal_path = db_path + "-wal"
shm_path = db_path + "-shm"

if os.path.exists(db_path):
    # 嘗試檢查是否被鎖定
    try:
        conn = sqlite3.connect(db_path, timeout=2)  # 2秒超時
        conn.execute("SELECT 1")
        conn.close()
        print(f"  ✅ 數據庫可訪問")
    except sqlite3.OperationalError as e:
        if "database is locked" in str(e):
            print(f"  ⚠️  數據庫被鎖定，清理 WAL 文件...")
            # 刪除 WAL 和 SHM 文件（只在確定沒有進程使用時）
            try:
                if os.path.exists(wal_path):
                    os.remove(wal_path)
                    print(f"    ✅ 已刪除 WAL 文件")
                if os.path.exists(shm_path):
                    os.remove(shm_path)
                    print(f"    ✅ 已刪除 SHM 文件")
            except Exception as cleanup_error:
                print(f"    ⚠️  清理失敗: {cleanup_error}")
        else:
            print(f"  ⚠️  數據庫錯誤: {e}")

# 初始化 Chroma
chroma_settings = Settings(
    persist_directory=CHROMA_DB_PATH,
    is_persistent=True
)

print("[INFO] 初始化 Chroma 數據庫...")
try:
    chroma_client = run_with_timeout(
        lambda: chromadb.Client(chroma_settings),
        timeout=CHROMA_TIMEOUT,
        operation_name="Chroma 初始化"
    )
    print("  ✅ Chroma 客戶端已創建")
except TimeoutException:
    print("  ⏱️ Chroma 初始化超時")
    sys.exit(1)
except Exception as e:
    print(f"  ❌ 初始化失敗: {e}")
    sys.exit(1)

# 創建 OpenAI 嵌入函數
embedding_function = OpenAIEmbeddingFunction(
    api_key=OPENAI_API_KEY,
    model_name=EMBEDDING_MODEL
)

# 創建或獲取集合
print("[INFO] 連接到集合...")
try:
    def get_collection():
        try:
            return chroma_client.get_collection(  # type: ignore
                name=COLLECTION_NAME,
                embedding_function=embedding_function  # type: ignore
            )
        except Exception:
            print(f"  [INFO] 創建新集合: {COLLECTION_NAME}")
            return chroma_client.get_or_create_collection(  # type: ignore
                name=COLLECTION_NAME,
                embedding_function=embedding_function,  # type: ignore
                metadata={"hnsw:space": "cosine"}
            )
    
    collection = run_with_timeout(
        get_collection,
        timeout=CHROMA_TIMEOUT,
        operation_name="集合連接"
    )
    print(f"  ✅ 已獲取現有集合: {COLLECTION_NAME}")
except TimeoutException:
    print("  ⏱️ 集合連接超時")
    sys.exit(1)
except Exception as e:
    print(f"  ❌ 連接失敗: {e}")
    sys.exit(1)


def truncate_to_tokens(text: str, max_tokens: int = MAX_TOKENS) -> tuple:
    """
    將文本截斷到指定的 token 數
    
    Args:
        text: 原始文本
        max_tokens: 最大 token 數
    
    Returns:
        (截斷後的文本, token_count)
    """
    try:
        tokens = encoding.encode(text)
        
        if len(tokens) <= max_tokens:
            return text, len(tokens)
        
        # 截斷到 max_tokens
        truncated_tokens = tokens[:max_tokens]
        truncated_text = encoding.decode(truncated_tokens)
        
        return truncated_text, len(truncated_tokens)
    except Exception as e:
        print(f"[ERROR] 截斷文本失敗: {e}")
        return text[:1000], 0  # 降級方案


def embed_and_store_batch(cases: list) -> tuple:
    """
    批量 embedding 和存儲
    cases: [(case_id, case_text, related_laws), ...]
    返回: (成功數, 失敗數)
    """
    successful = 0
    failed = 0
    
    ids = []
    documents = []
    embeddings = []
    metadatas = []
    
    print(f"\n[BATCH] 準備 {len(cases)} 個案例的 embedding...")
    
    # 第一步：所有案例都進行 embedding
    for idx, (case_id, case_text, related_laws) in enumerate(cases):
        try:
            # 截斷
            embedding_text, token_count = truncate_to_tokens(case_text, MAX_TOKENS)
            
            print(f"  [{idx+1}/{len(cases)}] {case_id}: {token_count} tokens", end="", flush=True)
            
            # OpenAI embedding（帶重試）
            embedding = None
            for attempt in range(MAX_RETRIES):
                try:
                    def do_embedding():
                        response = client.embeddings.create(
                            input=embedding_text,
                            model=EMBEDDING_MODEL
                        )
                        return response.data[0].embedding
                    
                    embedding = run_with_timeout(
                        do_embedding,
                        timeout=EMBEDDING_TIMEOUT,
                        operation_name=f"{case_id} embedding"
                    )
                    print(" ✅")
                    break
                    
                except TimeoutException:
                    if attempt < MAX_RETRIES - 1:
                        print(f" ⏱️ 重試", end="", flush=True)
                        time.sleep(2)
                    else:
                        print(f" ⏱️ 放棄")
                        failed += 1
                        break
                
                except Exception as e:
                    if attempt < MAX_RETRIES - 1:
                        print(f" ❌ 重試", end="", flush=True)
                        time.sleep(1)
                    else:
                        print(f" ❌ 失敗")
                        failed += 1
                        break
            
            if embedding is None:
                continue
            
            # 準備批量添加的數據
            ids.append(case_id)
            documents.append(embedding_text)
            embeddings.append(embedding)
            metadatas.append({
                "case_id": case_id,
                "token_count": token_count,
                "related_laws": related_laws,
                "case_summary": case_text[:500]
            })
            
            successful += 1
            
        except Exception as e:
            print(f" ❌ {str(e)[:50]}")
            failed += 1
    
    # 第二步：批量存儲到 Chroma
    if ids:
        print(f"\n[BATCH] 存儲 {len(ids)} 個 embedding 到 Chroma...")
        try:
            def do_batch_store():
                collection.add(
                    ids=ids,
                    documents=documents,
                    embeddings=embeddings,
                    metadatas=metadatas
                )
            
            run_with_timeout(
                do_batch_store,
                timeout=CHROMA_TIMEOUT * len(ids),  # 根據數量增加超時
                operation_name="批量存儲"
            )
            print(f"  ✅ 已存儲 {len(ids)} 個向量\n")
        except TimeoutException:
            print(f"  ⏱️ 批量存儲超時，嘗試逐個添加...")
            for i, (case_id, doc, embedding, metadata) in enumerate(
                zip(ids, documents, embeddings, metadatas)
            ):
                try:
                    print(f"    [{i+1}/{len(ids)}] {case_id}", end="", flush=True)
                    
                    def do_single_store():
                        collection.add(
                            ids=[case_id],
                            documents=[doc],
                            embeddings=[embedding],
                            metadatas=[metadata]
                        )
                    
                    run_with_timeout(
                        do_single_store,
                        timeout=CHROMA_TIMEOUT,
                        operation_name=f"{case_id} 存儲"
                    )
                    print(" ✅")
                except Exception as e:
                    print(f" ❌ {str(e)[:30]}")
        except Exception as e:
            print(f"  ❌ 批量存儲失敗: {e}\n")
    
    return successful, failed


def main():
    """主函數"""
    csv_path = "./updated_processed_cases.csv"
    
    if not os.path.exists(csv_path):
        print(f"[ERROR] CSV 文件不存在: {csv_path}")
        return
    
    print(f"[INFO] 開始讀取 CSV: {csv_path}\n")
    
    successful = 0
    failed = 0
    skipped = 0
    max_cases = 450  # 最多處理 450 筆
    batch_size = 10  # 每批 10 個案例
    
    try:
        # 讀取 CSV（使用 utf-8-sig 移除 BOM）
        batch = []
        idx = 0
        
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                if idx >= max_cases:  # 達到限制
                    print(f"\n[INFO] 已達到限制 ({max_cases} 筆)，停止處理")
                    # 處理最後一批
                    if batch:
                        batch_success, batch_failed = embed_and_store_batch(batch)
                        successful += batch_success
                        failed += batch_failed
                    break
                
                # 獲取行數據
                case_text = row.get("法律案例") or ""
                related_laws = row.get("相關法條") or ""
                
                # 清理數據
                case_text = case_text.strip() if case_text else ""
                related_laws = related_laws.strip() if related_laws else ""
                
                if not case_text:
                    print(f"[SKIP] 第 {idx + 2} 行: 案例文本為空")
                    skipped += 1
                    idx += 1
                    continue
                
                # 生成案例編號
                case_id = f"case_{idx}"
                batch.append((case_id, case_text, related_laws))
                idx += 1
                
                # 當批次滿了，進行批量處理
                if len(batch) >= batch_size:
                    batch_success, batch_failed = embed_and_store_batch(batch)
                    successful += batch_success
                    failed += batch_failed
                    batch = []
                    
                    # 進度提示
                    print(f"\n[PROGRESS] 已處理 {idx} 個案例 (✅{successful} ❌{failed} ⏭️{skipped})\n", flush=True)
            
            # 處理最後一批
            if batch:
                batch_success, batch_failed = embed_and_store_batch(batch)
                successful += batch_success
                failed += batch_failed
        
        # 最終統計
        print(f"\n{'='*60}")
        print(f"[SUMMARY]")
        print(f"  ✅ 成功: {successful}")
        print(f"  ❌ 失敗: {failed}")
        print(f"  ⏭️  跳過: {skipped}")
        print(f"  📊 總計: {successful + failed + skipped}")
        print(f"  💾 Chroma 集合: {COLLECTION_NAME}")
        print(f"  📁 資料庫路徑: {CHROMA_DB_PATH}")
        
        # 獲取集合計數（帶超時）
        try:
            def get_count():
                return collection.count()
            
            total_vectors = run_with_timeout(
                get_count,
                timeout=CHROMA_TIMEOUT,
                operation_name="計數"
            )
            print(f"  📈 向量總數: {total_vectors}")
        except TimeoutException:
            print(f"  📈 向量總數: (計數超時)")
        except Exception as e:
            print(f"  📈 向量總數: (計數失敗: {str(e)[:30]})")
        
        print(f"{'='*60}\n")
    
    except KeyboardInterrupt:
        print(f"\n\n[WARNING] 用戶中斷操作")
        print(f"[PARTIAL SUMMARY]")
        print(f"  ✅ 成功: {successful}")
        print(f"  ❌ 失敗: {failed}")
        print(f"  ⏭️  跳過: {skipped}")
    except Exception as e:
        print(f"\n[ERROR] 主程序異常: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

