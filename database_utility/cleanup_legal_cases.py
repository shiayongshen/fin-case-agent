#!/usr/bin/env python3
"""
清理舊的 legal_cases 集合，只保留 legal_cases_v2024
保留 law_articles_csv 相關集合
"""
import chromadb
from chromadb.config import Settings

CHROMA_DB_PATH = "./chroma_db"

print("🔍 正在掃描 Chroma 集合...\n")

# 初始化 Chroma
chroma_settings = Settings(
    persist_directory=CHROMA_DB_PATH,
    is_persistent=True
)
chroma_client = chromadb.Client(chroma_settings)

# 列出所有集合
all_collections = chroma_client.list_collections()
print(f"找到 {len(all_collections)} 個集合:\n")

# 分類集合
to_delete = []
to_keep = []

for collection in all_collections:
    name = collection.name
    count = collection.count() if hasattr(collection, 'count') else 0
    
    # 判斷是否要刪除
    if name.startswith('legal_cases') and name != 'legal_cases_v2024':
        to_delete.append(name)
        print(f"❌ 將刪除: {name} (文檔數: {count})")
    elif name.startswith('law_articles_csv'):
        to_keep.append(name)
        print(f"✅ 保留: {name} (文檔數: {count})")
    elif name == 'legal_cases_v2024':
        to_keep.append(name)
        print(f"✅ 保留: {name} (文檔數: {count})")
    else:
        to_keep.append(name)
        print(f"✅ 保留: {name} (文檔數: {count})")

print(f"\n{'='*60}")
print(f"📊 統計:")
print(f"  要刪除: {len(to_delete)} 個")
print(f"  要保留: {len(to_keep)} 個")
print(f"{'='*60}\n")

# 確認刪除
if to_delete:
    confirm = input("確認刪除上述集合嗎？(yes/no): ").strip().lower()
    
    if confirm == 'yes':
        for name in to_delete:
            try:
                chroma_client.delete_collection(name=name)
                print(f"✅ 已刪除: {name}")
            except Exception as e:
                print(f"❌ 刪除 {name} 失敗: {e}")
        
        print(f"\n✅ 清理完成！")
        print(f"   保留集合: {', '.join(to_keep)}")
    else:
        print("已取消刪除")
else:
    print("✅ 沒有需要刪除的集合")
    print(f"   保留集合: {', '.join(to_keep)}")
