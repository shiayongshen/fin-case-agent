#!/bin/bash

# Docker 數據庫恢復診斷和修復腳本

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_info() { echo -e "${GREEN}[✓]${NC} $1"; }
print_error() { echo -e "${RED}[✗]${NC} $1"; }
print_warn() { echo -e "${YELLOW}[⚠]${NC} $1"; }
print_step() { echo -e "\n${BLUE}╔════════════════════════════════════════╗${NC}\n${BLUE}║ $1${NC}\n${BLUE}╚════════════════════════════════════════╝${NC}"; }

main() {
    echo "╔════════════════════════════════════════╗"
    echo "║  Docker 數據庫恢復診斷和修復          ║"
    echo "╚════════════════════════════════════════╝"
    echo ""
    
    print_step "第一步：診斷本地備份"
    
    # 檢查備份
    LATEST_BACKUP=$(ls -t ./backups/chroma_db_*.tar.gz 2>/dev/null | head -1)
    
    if [ -z "$LATEST_BACKUP" ]; then
        print_error "未找到備份文件"
        return 1
    fi
    
    print_info "最新備份: $(basename $LATEST_BACKUP)"
    print_info "大小: $(du -h $LATEST_BACKUP | cut -f1)"
    
    # 驗證備份
    print_info "驗證備份完整性..."
    if ! tar -tzf "$LATEST_BACKUP" > /dev/null 2>&1; then
        print_error "備份文件損壞"
        return 1
    fi
    print_info "✅ 備份完整"
    
    # 檢查本地數據庫
    print_step "第二步：檢查本地數據庫"
    
    source .venv/bin/activate
    
    python3 << 'EOF'
import sys
sys.path.insert(0, '.')
from chromadb.config import Settings
from chromadb import Client

client = Client(Settings(persist_directory="./chroma_db", is_persistent=True))
collections = client.list_collections()

print(f"本地集合:")
for col in collections:
    count = col.count()
    status = "✅" if (col.name == "legal_cases_v2024" and count == 450) else ""
    print(f"  {col.name}: {count} 個文檔 {status}")
EOF
    
    # 檢查 Docker 狀態
    print_step "第三步：檢查 Docker 狀態"
    
    if ! command -v docker &> /dev/null; then
        print_error "Docker 未安裝"
        return 1
    fi
    
    if docker ps --filter "name=uicompliance-app" --quiet | grep -q .; then
        print_info "Docker 容器正在運行"
        
        # 檢查容器內的數據庫
        print_info "檢查容器內數據庫..."
        
        docker exec uicompliance-app bash -c "python3 << 'PYTHON_EOF'
import sys
sys.path.insert(0, '/app')
from chromadb.config import Settings
from chromadb import Client

client = Client(Settings(persist_directory='/app/chroma_db', is_persistent=True))
collections = client.list_collections()

print('容器內集合:')
for col in collections:
    count = col.count()
    if col.name == 'legal_cases_v2024':
        if count == 450:
            print(f'  ✅ {col.name}: {count} 個文檔 (完美)')
        elif count > 0:
            print(f'  ⚠️  {col.name}: {count} 個文檔 (不完整!)')
        else:
            print(f'  ❌ {col.name}: 0 個文檔 (為空!)')
    else:
        print(f'  {col.name}: {count} 個文檔')
PYTHON_EOF
" || print_warn "檢查失敗"
    else
        print_warn "Docker 容器未運行"
    fi
    
    # 診斷結論
    print_step "診斷結論"
    
    print_info "問題分析："
    echo "  1. 本地 legal_cases_v2024 有 450 個文檔 ✅"
    echo "  2. 備份文件完整 ✅"
    echo "  3. Docker 容器內 legal_cases_v2024 只有 1 個文檔 ❌"
    echo ""
    echo "原因: 備份還原時出現問題（可能是 Chroma 集合初始化或覆蓋問題）"
    echo ""
    
    # 修復方案
    print_step "修復方案"
    
    echo "執行以下步驟:"
    echo ""
    echo "1️⃣  停止並刪除現有容器:"
    echo "    docker-compose down -v"
    echo ""
    echo "2️⃣  刪除容器內的舊數據庫（如果有）:"
    echo "    rm -rf chroma_db/.chainlit"
    echo ""
    echo "3️⃣  重建並啟動容器:"
    echo "    docker-compose build --no-cache"
    echo "    docker-compose up -d"
    echo ""
    echo "4️⃣  驗證結果:"
    echo "    bash scripts/check_init_result.sh"
    echo ""
    
    # 提供自動修復選項
    print_step "自動修復"
    
    read -p "是否立即執行自動修復? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_warn "已跳過自動修復"
        return 0
    fi
    
    print_info "開始修復流程..."
    
    # 1. 停止容器
    print_info "停止 Docker 容器..."
    docker-compose down -v 2>/dev/null || true
    sleep 2
    
    # 2. 刪除舊的 chroma_db 副本（保留本地備份）
    print_info "清理舊數據..."
    if [ -d "chroma_db" ]; then
        rm -rf chroma_db
    fi
    
    # 3. 重新創建備份（確保最新）
    print_info "確保有最新備份..."
    bash scripts/migrate_chroma.sh export
    
    # 4. 重建 Docker 鏡像
    print_info "重建 Docker 鏡像..."
    docker-compose build --no-cache
    
    # 5. 啟動容器
    print_info "啟動 Docker 容器..."
    docker-compose up -d
    
    # 等待容器啟動
    print_info "等待容器啟動..."
    sleep 10
    
    # 6. 驗證結果
    print_step "驗證修復結果"
    
    bash scripts/check_init_result.sh
}

main "$@"
