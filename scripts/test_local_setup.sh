#!/bin/bash

# 本地環境完整測試腳本
# 用途：測試本地開發環境（不使用 Docker）

set -e

# 顏色輸出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_info() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

print_step() {
    echo -e "\n${BLUE}━━━ $1${NC}"
}

PASSED=0
FAILED=0

echo "╔════════════════════════════════════════╗"
echo "║     本地環境完整測試                   ║"
echo "╚════════════════════════════════════════╝"
echo ""

# 1. 檢查 Python 版本
print_step "檢查 Python 版本"
if command -v python3 &> /dev/null; then
    VERSION=$(python3 --version)
    print_info "$VERSION"
    ((PASSED++))
else
    print_error "未找到 Python"
    ((FAILED++))
fi

# 2. 檢查虛擬環境
print_step "檢查虛擬環境"
if [ -d ".venv" ]; then
    print_info "虛擬環境存在"
    ((PASSED++))
else
    print_error "虛擬環境不存在，執行: python3 -m venv .venv"
    ((FAILED++))
fi

# 3. 檢查依賴
print_step "檢查 Python 依賴"
python3 << 'EOF'
import importlib

required_modules = [
    'chromadb',
    'openai',
    'chainlit',
    'torch',
    'FlagEmbedding',
    'tiktoken'
]

missing = []
for module in required_modules:
    try:
        importlib.import_module(module)
        print(f"  ✅ {module}")
    except ImportError:
        print(f"  ❌ {module} (缺失)")
        missing.append(module)

if missing:
    print(f"\n[ERROR] 缺失 {len(missing)} 個依賴")
    print("執行: pip install -r requirements.txt")
    exit(1)
else:
    print(f"\n✅ 所有依賴已安裝")
EOF

# 4. 檢查 Chroma 數據庫
print_step "檢查 Chroma 數據庫"
if [ -d "chroma_db" ]; then
    print_info "數據庫目錄存在"
    
    python3 << 'EOF'
import sys
sys.path.insert(0, '.')
from chromadb.config import Settings
from chromadb import Client

try:
    client = Client(Settings(persist_directory="./chroma_db", is_persistent=True))
    collections = client.list_collections()
    
    print(f"  ✅ 找到 {len(collections)} 個集合:")
    total_docs = 0
    for col in collections:
        count = col.count()
        total_docs += count
        print(f"     - {col.name}: {count} 個文檔")
    
    if total_docs == 0:
        print(f"\n  ⚠️  警告：數據庫為空，需要執行嵌入:")
        print(f"     python3 database_utility/embed_cases_to_chroma.py")
    else:
        print(f"\n  ✅ 總共: {total_docs} 個文檔")
        
except Exception as e:
    print(f"  ❌ 連接失敗: {e}")
    sys.exit(1)
EOF
    ((PASSED++))
else
    print_error "數據庫目錄不存在"
    ((FAILED++))
fi

# 5. 檢查備份文件
print_step "檢查備份文件"
if [ -d "backups" ]; then
    BACKUP_COUNT=$(ls -1 backups/chroma_db_*.tar.gz 2>/dev/null | wc -l)
    if [ $BACKUP_COUNT -gt 0 ]; then
        print_info "找到 $BACKUP_COUNT 個備份文件"
        ls -lh backups/chroma_db_*.tar.gz | awk '{print "  " $9 " (" $5 ")"}'
        ((PASSED++))
    else
        print_error "備份目錄為空"
        ((FAILED++))
    fi
else
    print_error "備份目錄不存在"
    ((FAILED++))
fi

# 6. 檢查環境變數
print_step "檢查環境變數"
if [ -f ".env" ]; then
    if grep -q "OPENAI_API_KEY" .env; then
        print_info "✅ OPENAI_API_KEY 已設置"
        ((PASSED++))
    else
        print_error "OPENAI_API_KEY 未在 .env 中設置"
        ((FAILED++))
    fi
else
    print_error ".env 文件不存在，請複製 .env.example"
    ((FAILED++))
fi

# 7. 測試 RAG 搜索
print_step "測試 RAG 搜索功能"
python3 << 'EOF'
import sys
sys.path.insert(0, '.')

try:
    from utility.legal_search import search_and_rerank
    
    print("  測試查詢: '保險法' ...")
    results = search_and_rerank("保險法", top_k=3)
    
    if results.get('ranked_documents'):
        print(f"  ✅ 找到 {len(results['ranked_documents'])} 個結果")
        for i, doc in enumerate(results['ranked_documents'][:3], 1):
            preview = doc[:100].replace('\n', ' ')
            print(f"     {i}. {preview}...")
    else:
        print(f"  ⚠️  未找到結果（數據庫可能為空）")
        
except Exception as e:
    print(f"  ❌ 測試失敗: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
EOF

if [ $? -eq 0 ]; then
    ((PASSED++))
else
    ((FAILED++))
fi

# 8. 檢查腳本文件
print_step "檢查 Shell 腳本"
SCRIPTS=(
    "scripts/migrate_chroma.sh"
    "scripts/init_database.sh"
    "scripts/docker_exec.sh"
    "scripts/test_docker_setup.sh"
)

for script in "${SCRIPTS[@]}"; do
    if [ -f "$script" ] && [ -x "$script" ]; then
        print_info "$(basename $script) ✅"
    else
        print_error "$(basename $script) ❌"
        ((FAILED++))
    fi
done
((PASSED++))

# 9. 檢查 Git
print_step "檢查 Git 狀態"
if [ -d ".git" ]; then
    BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")
    UNCOMMITTED=$(git status -s | wc -l)
    
    print_info "分支: $BRANCH"
    if [ $UNCOMMITTED -gt 0 ]; then
        print_info "未提交的變更: $UNCOMMITTED 個"
    else
        print_info "工作目錄乾淨"
    fi
    ((PASSED++))
else
    print_error "未初始化 Git 倉庫"
    ((FAILED++))
fi

# 10. 檢查 Docker
print_step "檢查 Docker 環境"
if command -v docker &> /dev/null; then
    print_info "Docker 已安裝"
    
    if docker ps &> /dev/null; then
        print_info "Docker 守護程序運行中"
        
        if [ -f "docker-compose.yml" ]; then
            print_info "docker-compose.yml 存在"
        fi
        ((PASSED++))
    else
        print_error "Docker 守護程序未運行"
        ((FAILED++))
    fi
else
    print_error "Docker 未安裝"
    ((FAILED++))
fi

# 總結報告
echo ""
echo "╔════════════════════════════════════════╗"
echo -e "║ ${GREEN}✅ 通過: $PASSED${NC}     ${RED}❌ 失敗: $FAILED${NC}           ║"
echo "╚════════════════════════════════════════╝"
echo ""

if [ $FAILED -eq 0 ]; then
    print_info "所有測試通過！🎉"
    exit 0
else
    print_error "有 $FAILED 個測試失敗，請檢查上面的錯誤信息"
    exit 1
fi
