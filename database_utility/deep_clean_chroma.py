#!/usr/bin/env python3
"""
安全清理 Chroma 集合
只刪除 legal_cases 相關的集合
保留: law_articles_csv, law_articles_csv_version1
"""

import os
import shutil
import signal
import sys
from contextlib import contextmanager
from chromadb import Client
from chromadb.config import Settings
from dotenv import load_dotenv

load_dotenv()

# 設置超時時間（秒）
OPERATION_TIMEOUT = 30
LIST_TIMEOUT = 60

class TimeoutException(Exception):
    pass

@contextmanager
def timeout_handler(seconds):
    """跨平台超時處理器"""
    def signal_handler(signum, frame):
        raise TimeoutException(f"操作超時（{seconds}秒）")
    
    # 只在 Unix 系統上設置信號處理器
    if sys.platform != "win32":
        old_handler = signal.signal(signal.SIGALRM, signal_handler)
        signal.alarm(seconds)
    
    try:
        yield
    finally:
        if sys.platform != "win32":
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)

print("="*80)
print("🧹 安全清理 Chroma 集合（保留 law_articles*）")
print("="*80)

# 需要保留的集合
PRESERVE_COLLECTIONS = {"law_articles_csv", "law_articles_csv_version1", "law_articles"}

# 單一 client 實例（避免重複創建導致的鎖定）
client = None

try:
    print("\n[初始化] 建立 Chroma 連接...")
    with timeout_handler(OPERATION_TIMEOUT):
        client = Client(Settings(
            persist_directory="chroma_db",
            is_persistent=True
        ))
    print("  ✅ 連接成功")
except TimeoutException as e:
    print(f"  ⏱️ {e}")
    sys.exit(1)
except Exception as e:
    print(f"  ❌ 連接失敗: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n[步驟 1] 列出並刪除 legal_cases 相關集合...")
try:
    with timeout_handler(LIST_TIMEOUT):
        collections = client.list_collections()
    print(f"  找到 {len(collections)} 個集合")
    
    deleted_count = 0
    preserved_count = 0
    
    for coll in collections:
        print(f"    - {coll.name}", end="", flush=True)
        
        # 如果集合名稱包含 "legal_cases"（不區分大小寫）
        if "legal_cases" in coll.name.lower():
            try:
                with timeout_handler(OPERATION_TIMEOUT):
                    client.delete_collection(name=coll.name)
                print(" ✅ 已刪除")
                deleted_count += 1
            except TimeoutException as e:
                print(f" ⏱️ 刪除超時")
            except Exception as e:
                print(f" ❌ 刪除失敗: {str(e)[:50]}")
        # 如果集合在保留列表中
        elif coll.name in PRESERVE_COLLECTIONS:
            try:
                with timeout_handler(OPERATION_TIMEOUT):
                    count = coll.count() if hasattr(coll, 'count') else "未知"
                print(f" ✅ 保留 (文檔數: {count})")
                preserved_count += 1
            except TimeoutException:
                print(f" ✅ 保留 (計數超時)")
                preserved_count += 1
            except Exception as e:
                print(f" ✅ 保留 (計數失敗: {str(e)[:30]})")
                preserved_count += 1
        else:
            print()
    
    print(f"\n  摘要: 已刪除 {deleted_count} 個集合，保留 {preserved_count} 個集合")
        
except TimeoutException as e:
    print(f"  ⏱️ 列表操作超時: {e}")
except Exception as e:
    print(f"  ❌ Chroma API 操作失敗: {e}")
    import traceback
    traceback.print_exc()
finally:
    if client is not None:
        try:
            client = None
        except:
            pass

# 驗證結果
print("\n[步驟 2] 驗證清理結果...")
try:
    with timeout_handler(OPERATION_TIMEOUT):
        client = Client(Settings(
            persist_directory="chroma_db",
            is_persistent=True
        ))
    
    with timeout_handler(LIST_TIMEOUT):
        collections = client.list_collections()
    print(f"  現在有 {len(collections)} 個集合:")
    
    for coll in collections:
        if coll.name in PRESERVE_COLLECTIONS:
            try:
                with timeout_handler(OPERATION_TIMEOUT):
                    count = coll.count() if hasattr(coll, 'count') else "未知"
                print(f"    ✅ {coll.name} (文檔數: {count})")
            except TimeoutException:
                print(f"    ✅ {coll.name} (計數超時)")
            except Exception as e:
                print(f"    ✅ {coll.name} (計數失敗)")
        else:
            print(f"    - {coll.name}")
    
except TimeoutException as e:
    print(f"  ⏱️ 驗證超時: {e}")
except Exception as e:
    print(f"  ❌ 驗證失敗: {e}")
finally:
    if client is not None:
        try:
            client = None
        except:
            pass

print("\n" + "="*80)
print("✅ 清理完成")
print("="*80)
