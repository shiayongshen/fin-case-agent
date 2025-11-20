#!/bin/bash

# 檢查 init_database.sh 執行結果
# 用途：驗證初始化腳本是否成功，檢查關鍵結果

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

print_section() {
    echo -e "\n${MAGENTA}━━━ $1${NC}"
}

# 函數：模擬 init_database.sh 的執行
simulate_init() {
    print_step "模擬 init_database.sh 執行"
    
    print_info "這個腳本會執行以下步驟："
    echo "  1️⃣  修複目錄權限"
    echo "  2️⃣  查找最新備份"
    echo "  3️⃣  驗證備份文件完整性"
    echo "  4️⃣  還原數據庫"
    echo "  5️⃣  驗證還原結果"
    echo "  6️⃣  啟動應用程序"
    echo ""
}

# 函數：檢查目錄權限
check_directory_permissions() {
    print_section "檢查目錄權限"
    
    # 檢查 .chainlit 目錄
    if [ -d "/app/.chainlit" ] 2>/dev/null || [ -d "./.chainlit" ]; then
        print_info ".chainlit 目錄存在"
        if [ -d "./.chainlit" ]; then
            if [ -w "./.chainlit" ]; then
                print_info ".chainlit 目錄可寫"
            else
                print_warn ".chainlit 目錄不可寫"
            fi
        fi
    else
        print_warn ".chainlit 目錄不存在（Docker 容器內創建）"
    fi
    
    # 檢查 chroma_db 目錄
    if [ -d "./chroma_db" ]; then
        print_info "chroma_db 目錄存在"
        if [ -w "./chroma_db" ]; then
            print_info "chroma_db 目錄可寫"
        else
            print_warn "chroma_db 目錄不可寫"
        fi
    fi
    
    # 檢查 logs 目錄
    if [ -d "./logs" ]; then
        print_info "logs 目錄存在"
        if [ -w "./logs" ]; then
            print_info "logs 目錄可寫"
        fi
    else
        print_warn "logs 目錄不存在"
    fi
}

# 函數：檢查備份文件
check_backup_file() {
    print_section "檢查備份文件"
    
    if [ ! -d "./backups" ]; then
        print_error "backups 目錄不存在"
        return 1
    fi
    
    LATEST_BACKUP=$(ls -t ./backups/chroma_db_*.tar.gz 2>/dev/null | head -1)
    
    if [ -z "$LATEST_BACKUP" ]; then
        print_error "未找到備份文件"
        return 1
    fi
    
    print_info "找到最新備份: $(basename $LATEST_BACKUP)"
    
    SIZE=$(du -h "$LATEST_BACKUP" | cut -f1)
    MTIME=$(stat -f %Sm -t '%Y-%m-%d %H:%M:%S' "$LATEST_BACKUP" 2>/dev/null || stat -c %y "$LATEST_BACKUP" | cut -d. -f1)
    
    echo "  📦 文件大小: $SIZE"
    echo "  📅 修改時間: $MTIME"
    
    # 驗證備份完整性
    print_info "驗證備份文件完整性..."
    if tar -tzf "$LATEST_BACKUP" > /dev/null 2>&1; then
        print_info "✅ 備份文件完整"
        
        # 統計備份中的內容
        FILE_COUNT=$(tar -tzf "$LATEST_BACKUP" | wc -l)
        echo "  📂 包含文件數: $FILE_COUNT"
    else
        print_error "❌ 備份文件損壞"
        return 1
    fi
}

# 函數：檢查還原結果（數據庫）
check_database_restored() {
    print_section "檢查數據庫還原結果"
    
    if [ ! -d "./chroma_db" ]; then
        print_warn "數據庫目錄不存在（可能還未還原）"
        return 1
    fi
    
    FILE_COUNT=$(find ./chroma_db -type f 2>/dev/null | wc -l)
    DB_SIZE=$(du -sh ./chroma_db 2>/dev/null | cut -f1)
    
    print_info "數據庫目錄: ./chroma_db"
    echo "  📂 文件數: $FILE_COUNT"
    echo "  💾 大小: $DB_SIZE"
    
    # 檢查集合
    print_info "檢查數據庫集合..."
    
    source .venv/bin/activate 2>/dev/null || true
    
    python3 << 'EOF' 2>&1 || print_warn "無法連接到數據庫"
import sys
sys.path.insert(0, '.')

try:
    from chromadb.config import Settings
    from chromadb import Client
    
    client = Client(Settings(
        persist_directory="./chroma_db",
        is_persistent=True
    ))
    
    collections = client.list_collections()
    print(f"  ✅ 找到 {len(collections)} 個集合:")
    
    for col in collections:
        count = col.count()
        print(f"     • {col.name}: {count} 個文檔")
        
        # 特別檢查 legal_cases_v2024
        if col.name == 'legal_cases_v2024':
            if count == 450:
                print(f"       ✅ 完美！包含全部 450 個案例")
            elif count > 400:
                print(f"       ⚠️  幾乎完整（{count}/450）")
            elif count > 0:
                print(f"       ❌ 不完整（{count}/450）")
            else:
                print(f"       ❌ 為空！")
    
except Exception as e:
    print(f"  ❌ 連接失敗: {str(e)[:50]}")
    sys.exit(1)
EOF
}

# 函數：檢查應用配置
check_application_config() {
    print_section "檢查應用配置"
    
    # 檢查 app.py
    if [ -f "./app.py" ]; then
        print_info "app.py 存在"
    else
        print_error "app.py 不存在"
    fi
    
    # 檢查 chainlit.md
    if [ -f "./chainlit.md" ]; then
        print_info "chainlit.md 存在"
    else
        print_error "chainlit.md 不存在"
    fi
    
    # 檢查 .env
    if [ -f "./.env" ]; then
        print_info ".env 配置文件存在"
        
        if grep -q "OPENAI_API_KEY" .env; then
            print_info "OPENAI_API_KEY 已配置"
        else
            print_warn "OPENAI_API_KEY 未配置"
        fi
    else
        print_warn ".env 配置文件不存在（在 Docker 容器中設置）"
    fi
    
    # 檢查 pyproject.toml
    if [ -f "./pyproject.toml" ]; then
        print_info "pyproject.toml 存在"
    else
        print_error "pyproject.toml 不存在"
    fi
}

# 函數：檢查 Docker 狀態（如果有）
check_docker_status() {
    print_section "檢查 Docker 狀態"
    
    if ! command -v docker &> /dev/null; then
        print_warn "Docker 未安裝"
        return 0
    fi
    
    CONTAINER_NAME="uicompliance-app"
    
    if docker ps --filter "name=$CONTAINER_NAME" --quiet | grep -q .; then
        print_info "Docker 容器正在運行"
        
        # 檢查容器日誌
        print_info "檢查容器初始化日誌..."
        echo ""
        
        docker logs "$CONTAINER_NAME" 2>&1 | grep -E "init|還原|數據庫|啟動|ERROR|FATAL" | tail -10 || echo "  (無相關日誌)"
    else
        print_warn "Docker 容器未運行"
    fi
}

# 函數：生成執行結果報告
generate_result_report() {
    print_step "執行結果總結"
    
    # 統計檢查結果
    local total_checks=0
    local passed_checks=0
    
    # 檢查各項內容
    echo "╔════════════════════════════════════════╗"
    echo "║         初始化結果檢查清單             ║"
    echo "╚════════════════════════════════════════╝"
    echo ""
    
    # 1. 備份文件
    if [ -f "$(ls -t ./backups/chroma_db_*.tar.gz 2>/dev/null | head -1)" ]; then
        echo -e "${GREEN}✅${NC} 備份文件存在"
        ((passed_checks++))
    else
        echo -e "${RED}❌${NC} 備份文件不存在"
    fi
    ((total_checks++))
    
    # 2. 數據庫目錄
    if [ -d "./chroma_db" ]; then
        echo -e "${GREEN}✅${NC} 數據庫目錄已還原"
        ((passed_checks++))
    else
        echo -e "${YELLOW}⚠${NC} 數據庫目錄不存在"
    fi
    ((total_checks++))
    
    # 3. 集合數據
    if python3 << 'EOF' 2>/dev/null
import sys
sys.path.insert(0, '.')
try:
    from chromadb.config import Settings
    from chromadb import Client
    client = Client(Settings(persist_directory="./chroma_db", is_persistent=True))
    collections = client.list_collections()
    for col in collections:
        if col.name == 'legal_cases_v2024' and col.count() == 450:
            exit(0)
    exit(1)
except:
    exit(1)
EOF
    then
        echo -e "${GREEN}✅${NC} legal_cases_v2024 包含 450 個案例"
        ((passed_checks++))
    else
        echo -e "${YELLOW}⚠${NC} legal_cases_v2024 不完整或未還原"
    fi
    ((total_checks++))
    
    # 4. 應用配置
    if [ -f "./app.py" ] && [ -f "./chainlit.md" ]; then
        echo -e "${GREEN}✅${NC} 應用配置文件完整"
        ((passed_checks++))
    else
        echo -e "${YELLOW}⚠${NC} 應用配置文件缺失"
    fi
    ((total_checks++))
    
    # 5. 環境配置
    if [ -f "./.env" ] || [ -z "$OPENAI_API_KEY" ]; then
        echo -e "${GREEN}✅${NC} 環境配置已就位"
        ((passed_checks++))
    else
        echo -e "${YELLOW}⚠${NC} 環境配置缺失"
    fi
    ((total_checks++))
    
    echo ""
    echo "╔════════════════════════════════════════╗"
    echo -e "║ ${GREEN}通過: $passed_checks${NC}/$total_checks                      ║"
    echo "╚════════════════════════════════════════╝"
    echo ""
    
    # 建議
    if [ $passed_checks -eq $total_checks ]; then
        print_info "所有檢查通過！✅"
        print_info "可以開始執行初始化:"
        echo "  docker-compose up -d"
    else
        print_warn "有 $((total_checks - passed_checks)) 項檢查未通過"
        print_info "建議:"
        if [ ! -f "$(ls -t ./backups/chroma_db_*.tar.gz 2>/dev/null | head -1)" ]; then
            echo "  1. 創建備份: bash scripts/migrate_chroma.sh export"
        fi
        if [ ! -d "./chroma_db" ]; then
            echo "  2. 還原數據庫: bash scripts/migrate_chroma.sh restore <backup_file>"
        fi
    fi
}

# 函數：顯示下一步步驟
show_next_steps() {
    print_step "下一步建議"
    
    cat << 'EOF'
如果 init_database.sh 已執行，您現在應該有：

1️⃣  已還原的 Chroma 數據庫
    ✅ 450 個法律案例
    ✅ 3000+ 個法律條文
    ✅ 完整的元數據

2️⃣  已配置的應用環境
    ✅ app.py 準備好
    ✅ .chainlit 目錄初始化
    ✅ logs 目錄創建

3️⃣  可以啟動應用
    ✅ 本地: python -m utility.rag
    ✅ Docker: docker-compose up -d

4️⃣  可以驗證結果
    ✅ 本地: bash scripts/verify_database_content.sh local
    ✅ Docker: bash scripts/verify_database_content.sh docker

常見問題排查：

⚠️  如果看到 "sqlite3.OperationalError: attempt to write a readonly database"
    → 執行: docker exec -it uicompliance-app chmod -R 777 /app/.chainlit /app/chroma_db

⚠️  如果看到 "Collection does not exist"
    → 檢查備份文件是否完整: bash scripts/verify_database_content.sh local

⚠️  如果數據庫為空 (0 個文檔)
    → 重新嵌入: python3 database_utility/embed_cases_to_chroma.py

EOF
}

# 主程序
main() {
    echo "╔════════════════════════════════════════╗"
    echo "║  init_database.sh 執行結果檢查工具    ║"
    echo "╚════════════════════════════════════════╝"
    echo ""
    
    # 執行檢查
    simulate_init
    check_directory_permissions
    check_backup_file
    check_database_restored
    check_application_config
    check_docker_status
    generate_result_report
    show_next_steps
    
    echo ""
    echo "╔════════════════════════════════════════╗"
    echo "║     檢查完成                           ║"
    echo "╚════════════════════════════════════════╝"
}

main "$@"
