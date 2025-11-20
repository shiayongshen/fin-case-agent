#!/bin/bash

# 數據庫內容驗證腳本
# 用途：檢查還原後的數據庫是否包含預期的數據

set -e

# 顏色輸出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
NC='\033[0m'

print_info() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[⚠]${NC} $1"
}

print_step() {
    echo -e "\n${BLUE}╔════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║ $1${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"
}

# 函數：驗證本地數據庫
verify_local_database() {
    print_step "驗證本地數據庫"
    
    if [ ! -d "chroma_db" ]; then
        print_error "本地 chroma_db 目錄不存在"
        return 1
    fi
    
    print_info "本地數據庫路徑: $(pwd)/chroma_db"
    
    # 使用虛擬環境中的 Python
    source .venv/bin/activate 2>/dev/null || true
    
    python3 << 'EOF'
import sys
import os
sys.path.insert(0, '.')

from chromadb.config import Settings
from chromadb import Client

print("\n[本地數據庫詳細檢查]")

try:
    client = Client(Settings(
        persist_directory="./chroma_db",
        is_persistent=True
    ))
    
    collections = client.list_collections()
    
    print(f"\n✅ 找到 {len(collections)} 個集合:\n")
    
    expected_collections = {
        'legal_cases_v2024': 450,  # 應該有 450 個法律案例
        'law_articles': 3000,      # 大約 3000 個法律條文
    }
    
    total_docs = 0
    
    for col in collections:
        count = col.count()
        total_docs += count
        
        # 檢查是否是預期的集合
        if col.name in expected_collections:
            expected = expected_collections[col.name]
            status = "✅" if count >= expected * 0.8 else "⚠️"
            print(f"{status} {col.name}")
            print(f"   📊 文檔數: {count} (預期: ~{expected})")
        else:
            print(f"📦 {col.name}")
            print(f"   📊 文檔數: {count}")
        
        # 顯示集合詳細信息
        try:
            sample = col.get(limit=1)
            if sample and sample['documents']:
                print(f"   📄 樣本文檔長度: {len(sample['documents'][0])} 字符")
                if sample['metadatas']:
                    print(f"   🏷️  元數據鍵: {list(sample['metadatas'][0].keys())}")
        except:
            pass
        
        print()
    
    # 檢查關鍵集合
    print("\n[集合驗證結果]")
    
    legal_cases_found = False
    law_articles_found = False
    
    for col in collections:
        if col.name == 'legal_cases_v2024':
            legal_cases_found = True
            count = col.count()
            if count > 0:
                print(f"✅ legal_cases_v2024: 包含 {count} 個文檔")
                
                # 驗證元數據
                sample = col.get(limit=1)
                if sample and sample['metadatas']:
                    metadata = sample['metadatas'][0]
                    required_fields = ['case_id', 'token_count', 'related_laws', 'case_summary']
                    missing = [f for f in required_fields if f not in metadata]
                    
                    if missing:
                        print(f"   ⚠️  缺失的元數據字段: {missing}")
                    else:
                        print(f"   ✅ 元數據完整: {required_fields}")
            else:
                print(f"❌ legal_cases_v2024: 集合為空！")
        
        if col.name.startswith('law_articles'):
            law_articles_found = True
            count = col.count()
            if count > 0:
                print(f"✅ {col.name}: 包含 {count} 個文檔")
            else:
                print(f"⚠️  {col.name}: 集合為空")
    
    if not legal_cases_found:
        print(f"❌ 未找到 legal_cases_v2024 集合！")
    
    if not law_articles_found:
        print(f"⚠️  未找到任何 law_articles 集合")
    
    print(f"\n📈 總計: {total_docs} 個文檔")
    
    # 性能檢查
    print("\n[性能檢查]")
    try:
        # 測試搜索性能
        import time
        start = time.time()
        col = collections[0]
        result = col.query(query_texts=["test"], n_results=5)
        elapsed = time.time() - start
        
        print(f"✅ 搜索響應時間: {elapsed:.3f} 秒")
        if elapsed > 1.0:
            print(f"   ⚠️  響應時間較長，可能需要優化")
    except Exception as e:
        print(f"⚠️  搜索測試失敗: {e}")
    
except Exception as e:
    print(f"❌ 數據庫連接失敗: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
EOF
}

# 函數：驗證 Docker 中的數據庫
verify_docker_database() {
    local container="${1:-uicompliance-app}"
    
    print_step "驗證 Docker 中的數據庫"
    
    if ! docker ps --filter "name=$container" --quiet | grep -q .; then
        print_error "容器 '$container' 未運行"
        return 1
    fi
    
    print_info "容器名稱: $container"
    
    docker exec "$container" python3 << 'EOF'
import sys
sys.path.insert(0, '/app')

from chromadb.config import Settings
from chromadb import Client

print("\n[容器數據庫詳細檢查]")

try:
    client = Client(Settings(
        persist_directory="/app/chroma_db",
        is_persistent=True
    ))
    
    collections = client.list_collections()
    
    print(f"\n✅ 找到 {len(collections)} 個集合:\n")
    
    for col in collections:
        count = col.count()
        
        print(f"📦 {col.name}")
        print(f"   📊 文檔數: {count}")
        
        # 顯示集合詳細信息
        try:
            sample = col.get(limit=1)
            if sample and sample['documents']:
                print(f"   📄 樣本文檔長度: {len(sample['documents'][0])} 字符")
                if sample['metadatas']:
                    print(f"   🏷️  元數據鍵: {list(sample['metadatas'][0].keys())}")
        except:
            pass
        
        print()
    
    # 驗證關鍵集合
    print("[集合驗證結果]")
    
    legal_cases_found = False
    
    for col in collections:
        if col.name == 'legal_cases_v2024':
            legal_cases_found = True
            count = col.count()
            if count > 0:
                print(f"✅ legal_cases_v2024: 包含 {count} 個文檔 (預期: 450)")
                
                # 檢查是否有足夠的數據
                if count >= 450:
                    print(f"   ✅ 文檔數量達到預期！")
                elif count >= 400:
                    print(f"   ⚠️  文檔數量接近但未達到預期")
                else:
                    print(f"   ❌ 文檔數量不足 (只有 {count}/450)")
            else:
                print(f"❌ legal_cases_v2024: 集合為空！")
    
    if not legal_cases_found:
        print(f"❌ 未找到 legal_cases_v2024 集合！")
    
except Exception as e:
    print(f"❌ 數據庫連接失敗: {e}")
    sys.exit(1)
EOF
}

# 函數：比較備份和當前數據庫
compare_backup_and_database() {
    print_step "比較備份文件和當前數據庫"
    
    # 找最新的備份
    LATEST_BACKUP=$(ls -t ./backups/chroma_db_*.tar.gz 2>/dev/null | head -1)
    
    if [ -z "$LATEST_BACKUP" ]; then
        print_warn "未找到備份文件"
        return 1
    fi
    
    print_info "最新備份: $(basename $LATEST_BACKUP)"
    print_info "備份大小: $(du -h $LATEST_BACKUP | cut -f1)"
    print_info "備份時間: $(stat -f %Sm -t '%Y-%m-%d %H:%M:%S' $LATEST_BACKUP)"
    
    # 統計備份中的文件數
    echo ""
    print_info "備份文件統計:"
    FILE_COUNT=$(tar -tzf "$LATEST_BACKUP" | wc -l)
    echo "  📂 文件數: $FILE_COUNT"
    
    # 統計當前數據庫文件
    if [ -d "chroma_db" ]; then
        echo ""
        print_info "當前數據庫統計:"
        CURRENT_FILE_COUNT=$(find chroma_db -type f | wc -l)
        echo "  📂 文件數: $CURRENT_FILE_COUNT"
        
        # 比較
        echo ""
        if [ "$FILE_COUNT" -eq "$CURRENT_FILE_COUNT" ]; then
            print_info "✅ 備份和當前數據庫文件數相同"
        else
            print_warn "⚠️  文件數不相同 (備份: $FILE_COUNT, 當前: $CURRENT_FILE_COUNT)"
        fi
    fi
}

# 函數：生成數據庫報告
generate_report() {
    print_step "數據庫內容報告"
    
    cat << EOF

📋 數據庫應包含的預期內容：

1. legal_cases_v2024 集合
   ├─ 文檔數: 450 個法律案例
   ├─ 向量維度: 1536 (OpenAI text-embedding-ada-002)
   └─ 元數據欄位:
      ├─ case_id: 案例ID (如 "case_0", "case_1", ...)
      ├─ token_count: Token 數量
      ├─ related_laws: 相關法條
      └─ case_summary: 案例摘要 (前 500 字符)

2. law_articles_* 集合
   ├─ law_articles: 3084 個法律條文
   ├─ law_articles_csv: 3058 個法律條文
   ├─ law_articles_csv_version1: 4119 個法律條文
   └─ 用於法律條文搜索

✅ 驗證檢查清單：
   □ legal_cases_v2024 集合存在
   □ legal_cases_v2024 包含 450 個文檔
   □ 每個文檔都有完整的元數據
   □ 向量已正確嵌入
   □ 至少一個 law_articles* 集合存在
   □ 數據庫連接性能良好

⚠️  常見問題：
   • legal_cases_v2024 為空 → 需要重新運行 embed_cases_to_chroma.py
   • 集合不存在 → 備份文件不完整或損壞
   • 文檔數少於 450 → 備份是在嵌入完成前創建的
   • 無法連接 → Chroma 數據庫初始化失敗

EOF
}

# 主程序
main() {
    echo "╔════════════════════════════════════════╗"
    echo "║   數據庫內容驗證工具                   ║"
    echo "╚════════════════════════════════════════╝"
    echo ""
    
    local mode="${1:-local}"
    
    case "$mode" in
        local)
            verify_local_database
            compare_backup_and_database
            ;;
        docker)
            local container="${2:-uicompliance-app}"
            verify_docker_database "$container"
            ;;
        both)
            verify_local_database
            echo ""
            local container="${2:-uicompliance-app}"
            verify_docker_database "$container"
            ;;
        report)
            generate_report
            ;;
        *)
            cat << EOF
使用方法:
  bash scripts/verify_database_content.sh [mode] [container]

模式:
  local         驗證本地數據庫（默認）
  docker        驗證 Docker 中的數據庫
  both          同時驗證本地和 Docker
  report        顯示預期數據內容報告

示例:
  bash scripts/verify_database_content.sh local
  bash scripts/verify_database_content.sh docker
  bash scripts/verify_database_content.sh docker my-container
  bash scripts/verify_database_content.sh report

EOF
            ;;
    esac
    
    echo ""
    echo "╔════════════════════════════════════════╗"
    echo "║     驗證完成                           ║"
    echo "╚════════════════════════════════════════╝"
}

main "$@"
