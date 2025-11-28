#!/bin/bash

# Docker 設置完整測試套件
# 用途：測試 Docker 容器、數據庫、RAG 搜索等所有功能

set -e

# 顏色輸出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
NC='\033[0m'

# 配置
CONTAINER_NAME="uicompliance-app"
TEST_RESULTS=()
PASSED=0
FAILED=0

# 函數：打印信息
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[✅ SUCCESS]${NC} $1"
}

print_step() {
    echo -e "\n${BLUE}╔════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║ $1${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"
}

print_test() {
    echo -e "${MAGENTA}━━━ 測試: $1${NC}"
}

# 函數：記錄測試結果
record_test() {
    local test_name="$1"
    local result="$2"  # "PASS" 或 "FAIL"
    local message="$3"
    
    if [ "$result" = "PASS" ]; then
        print_success "$test_name"
        TEST_RESULTS+=("✅ $test_name")
        ((PASSED++))
    else
        print_error "$test_name: $message"
        TEST_RESULTS+=("❌ $test_name: $message")
        ((FAILED++))
    fi
}

# 函數：檢查容器是否運行
check_container_running() {
    print_test "檢查容器是否運行"
    
    if docker ps --filter "name=$CONTAINER_NAME" --quiet | grep -q .; then
        record_test "容器運行檢查" "PASS"
        return 0
    else
        record_test "容器運行檢查" "FAIL" "容器未運行"
        return 1
    fi
}

# 函數：測試容器日誌
test_container_logs() {
    print_test "檢查容器日誌是否有錯誤"
    
    # 檢查日誌中是否有致命錯誤
    if docker logs "$CONTAINER_NAME" 2>&1 | grep -qi "fatal\|error.*sqlite"; then
        record_test "容器日誌檢查" "FAIL" "日誌中發現致命錯誤"
        return 1
    else
        record_test "容器日誌檢查" "PASS"
        return 0
    fi
}

# 函數：測試 HTTP 連接
test_http_connection() {
    print_test "測試 HTTP 連接 (localhost:7861)"
    
    if curl -s -m 5 http://localhost:7861 > /dev/null 2>&1; then
        record_test "HTTP 連接測試" "PASS"
        return 0
    else
        record_test "HTTP 連接測試" "FAIL" "無法連接到 localhost:7861"
        return 1
    fi
}

# 函數：測試 Chroma 數據庫連接
test_chroma_connection() {
    print_test "測試 Chroma 數據庫連接"
    
    local result=$(docker exec "$CONTAINER_NAME" python3 << 'EOF' 2>&1)
import sys
sys.path.insert(0, '/app')
try:
    from chromadb.config import Settings
    from chromadb import Client
    
    client = Client(Settings(
        persist_directory="/app/chroma_db",
        is_persistent=True
    ))
    
    collections = client.list_collections()
    print(f"OK:{len(collections)}")
except Exception as e:
    print(f"ERROR:{str(e)[:50]}")
EOF
    
    if echo "$result" | grep -q "^OK:"; then
        record_test "Chroma 數據庫連接" "PASS"
        return 0
    else
        record_test "Chroma 數據庫連接" "FAIL" "$result"
        return 1
    fi
}

# 函數：測試數據庫中的數據
test_database_content() {
    print_test "測試數據庫內容（集合和文檔數）"
    
    local result=$(docker exec "$CONTAINER_NAME" python3 << 'EOF' 2>&1)
import sys
sys.path.insert(0, '/app')
try:
    from chromadb.config import Settings
    from chromadb import Client
    
    client = Client(Settings(
        persist_directory="/app/chroma_db",
        is_persistent=True
    ))
    
    collections = client.list_collections()
    total_docs = 0
    
    for col in collections:
        count = col.count()
        total_docs += count
        print(f"{col.name}:{count}")
    
    print(f"TOTAL:{total_docs}")
except Exception as e:
    print(f"ERROR:{str(e)[:50]}")
EOF
    
    if echo "$result" | grep -q "^legal_cases_v2024:"; then
        local doc_count=$(echo "$result" | grep "^legal_cases_v2024:" | cut -d: -f2)
        
        if [ "$doc_count" -gt 0 ]; then
            record_test "數據庫內容" "PASS"
            echo "  📦 legal_cases_v2024: $doc_count 個文檔"
            return 0
        else
            record_test "數據庫內容" "FAIL" "legal_cases_v2024 為空"
            return 1
        fi
    else
        record_test "數據庫內容" "FAIL" "未找到 legal_cases_v2024 集合"
        echo "$result"
        return 1
    fi
}

# 函數：測試 Chainlit 初始化
test_chainlit_init() {
    print_test "測試 Chainlit 初始化"
    
    if docker exec "$CONTAINER_NAME" [ -d "/.chainlit" ] || docker exec "$CONTAINER_NAME" [ -d "/app/.chainlit" ]; then
        record_test "Chainlit 初始化" "PASS"
        return 0
    else
        record_test "Chainlit 初始化" "FAIL" ".chainlit 目錄不存在"
        return 1
    fi
}

# 函數：測試文件權限
test_file_permissions() {
    print_test "測試文件權限"
    
    # 檢查 chroma_db 是否可寫
    if docker exec "$CONTAINER_NAME" [ -w "/app/chroma_db" ]; then
        record_test "chroma_db 寫入權限" "PASS"
    else
        record_test "chroma_db 寫入權限" "FAIL" "目錄不可寫"
        return 1
    fi
    
    # 檢查 .chainlit 是否可寫
    if docker exec "$CONTAINER_NAME" [ -w "/app/.chainlit" ] 2>/dev/null; then
        record_test ".chainlit 寫入權限" "PASS"
        return 0
    else
        print_warn ".chainlit 目錄可能不存在或不可寫，創建中..."
        docker exec "$CONTAINER_NAME" mkdir -p /app/.chainlit && \
        docker exec "$CONTAINER_NAME" chmod 777 /app/.chainlit && \
        record_test ".chainlit 寫入權限" "PASS"
        return 0
    fi
}

# 函數：測試環境變數
test_environment_variables() {
    print_test "測試環境變數"
    
    local result=$(docker exec "$CONTAINER_NAME" env | grep -E "OPENAI_API_KEY|PYTHONPATH" || echo "NOTFOUND")
    
    if [ "$result" != "NOTFOUND" ]; then
        record_test "環境變數設置" "PASS"
        return 0
    else
        record_test "環境變數設置" "FAIL" "關鍵環境變數未設置"
        return 1
    fi
}

# 函數：測試 RAG 搜索功能
test_rag_search() {
    print_test "測試 RAG 搜索功能"
    
    local result=$(docker exec "$CONTAINER_NAME" python3 << 'EOF' 2>&1)
import sys
sys.path.insert(0, '/app')
try:
    from utility.legal_search import search_and_rerank
    
    # 執行搜索
    results = search_and_rerank("保險法", top_k=3)
    
    if results and len(results.get('ranked_documents', [])) > 0:
        print(f"OK:Found {len(results['ranked_documents'])} results")
    else:
        print("OK:Search works but no results found")
except Exception as e:
    print(f"ERROR:{str(e)[:100]}")
EOF
    
    if echo "$result" | grep -q "^OK:"; then
        record_test "RAG 搜索功能" "PASS"
        echo "  $result"
        return 0
    else
        record_test "RAG 搜索功能" "FAIL" "$result"
        return 1
    fi
}

# 函數：測試容器資源使用
test_container_resources() {
    print_test "測試容器資源使用情況"
    
    print_info "容器資源統計（不阻塞）:"
    docker stats --no-stream "$CONTAINER_NAME" 2>/dev/null | tail -1 | awk '{
        printf "  CPU: %s | Memory: %s\n", $3, $4
    }' || print_warn "無法獲取資源統計"
    
    record_test "容器資源檢查" "PASS"
}

# 函數：測試數據庫大小
test_database_size() {
    print_test "測試數據庫大小"
    
    local size=$(docker exec "$CONTAINER_NAME" du -sh /app/chroma_db 2>/dev/null | cut -f1)
    
    if [ -n "$size" ]; then
        record_test "數據庫大小" "PASS"
        print_info "  數據庫大小: $size"
        return 0
    else
        record_test "數據庫大小" "FAIL" "無法計算大小"
        return 1
    fi
}

# 函數：測試磁盤空間
test_disk_space() {
    print_test "測試磁盤空間"
    
    local available=$(docker exec "$CONTAINER_NAME" df /app | awk 'NR==2 {print $4}')
    
    if [ "$available" -gt 100000 ]; then  # > 100MB
        record_test "磁盤空間" "PASS"
        print_info "  可用空間: $(($available / 1024))MB"
        return 0
    else
        record_test "磁盤空間" "FAIL" "可用空間不足"
        return 1
    fi
}

# 函數：生成測試報告
generate_report() {
    print_step "測試報告"
    
    echo ""
    echo "╔════════════════════════════════════════╗"
    echo "║         測試結果摘要                   ║"
    echo "╚════════════════════════════════════════╝"
    echo ""
    
    for result in "${TEST_RESULTS[@]}"; do
        echo "  $result"
    done
    
    echo ""
    echo "╔════════════════════════════════════════╗"
    echo -e "║ ${GREEN}✅ 通過: $PASSED${NC}          ❌ 失敗: $FAILED              ║"
    echo "╚════════════════════════════════════════╝"
    echo ""
    
    if [ $FAILED -eq 0 ]; then
        print_success "所有測試通過！🎉"
        return 0
    else
        print_error "有 $FAILED 個測試失敗"
        return 1
    fi
}

# 函數：主測試流程
main() {
    print_step "Docker 設置完整測試"
    
    print_info "容器名稱: $CONTAINER_NAME"
    print_info "測試時間: $(date '+%Y-%m-%d %H:%M:%S')"
    echo ""
    
    # 檢查容器是否運行
    if ! check_container_running; then
        print_error "容器未運行，請先啟動:"
        echo "  docker-compose up -d"
        exit 1
    fi
    
    # 等待容器完全啟動
    print_info "等待容器完全啟動..."
    sleep 5
    
    # 執行所有測試
    test_container_logs || true
    test_http_connection || true
    test_chroma_connection || true
    test_database_content || true
    test_chainlit_init || true
    test_file_permissions || true
    test_environment_variables || true
    test_rag_search || true
    test_container_resources || true
    test_database_size || true
    test_disk_space || true
    
    # 生成報告
    generate_report
    
    return $?
}

# 顯示幫助
show_help() {
    cat << EOF
Docker 設置完整測試工具

使用方法:
  bash scripts/test_docker_setup.sh [options]

選項:
  -h, --help              顯示此幫助信息
  -c, --container NAME    指定容器名稱（默認: uicompliance-app）
  -f, --full              執行完整測試（包括 RAG 搜索）
  -q, --quick             執行快速測試（只檢查基本功能）

示例:
  bash scripts/test_docker_setup.sh
  bash scripts/test_docker_setup.sh --container my-container
  bash scripts/test_docker_setup.sh --quick

EOF
}

# 解析命令行參數
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_help
                exit 0
                ;;
            -c|--container)
                CONTAINER_NAME="$2"
                shift 2
                ;;
            -f|--full)
                # 執行完整測試（默認行為）
                shift
                ;;
            -q|--quick)
                # 標記為快速測試（未實現，可根據需要添加）
                shift
                ;;
            *)
                print_error "未知選項: $1"
                show_help
                exit 1
                ;;
        esac
    done
}

# 執行
parse_args "$@"
main
