#!/bin/bash

# Docker 容器內數據庫初始化腳本
# 用途：在容器啟動時自動還原 Chroma 數據庫，然後啟動應用

set -e  # 遇到錯誤立即退出

# 顏色輸出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'  # No Color

# 配置
PROJECT_DIR="/app"
CHROMA_DB_DIR="${PROJECT_DIR}/chroma_db"
BACKUP_DIR="${PROJECT_DIR}/backups"
BACKUP_FILE=""  # 將在下面尋找最新的備份
CHAINLIT_DB_DIR="${PROJECT_DIR}/.chainlit"
CHAINLIT_DB_PATH="${CHAINLIT_DB_DIR}/chainlit.db"

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

print_step() {
    echo -e "\n${BLUE}==== $1 ====${NC}"
}

# 函數：查找最新的備份文件
find_latest_backup() {
    if [ ! -d "$BACKUP_DIR" ]; then
        return 1
    fi
    
    # 查找最新的 .tar.gz 備份文件
    local latest_backup=$(ls -t "$BACKUP_DIR"/chroma_db_*.tar.gz 2>/dev/null | head -1)
    
    if [ -z "$latest_backup" ]; then
        return 1
    fi
    
    echo "$latest_backup"
}

# 函數：驗證備份文件完整性
verify_backup() {
    local backup_file="$1"
    
    print_info "驗證備份文件完整性..."
    
    if ! tar -tzf "$backup_file" > /dev/null 2>&1; then
        print_error "備份文件損壞或格式不正確: $backup_file"
        return 1
    fi
    
    print_info "✅ 備份文件驗證成功"
    return 0
}



# 函數：還原數據庫
restore_database() {
    local backup_file="$1"
    
    print_step "還原 Chroma 數據庫"
    
    if [ ! -f "$backup_file" ]; then
        print_error "備份文件不存在: $backup_file"
        return 1
    fi
    
    # 驗證備份
    if ! verify_backup "$backup_file"; then
        return 1
    fi
    
    # 提取備份時使用 --overwrite 選項覆蓋現有文件
    # 這樣可以避免 "Device or resource busy" 的問題
    print_info "提取備份文件中..."
    if [ -d "$CHROMA_DB_DIR" ]; then
        print_warn "數據庫目錄已存在，將用新備份覆蓋..."
    fi
    
    if ! tar -xzf "$backup_file" -C "$PROJECT_DIR" --overwrite 2>/dev/null || ! tar -xzf "$backup_file" -C "$PROJECT_DIR"; then
        print_error "提取備份文件失敗"
        return 1
    fi
    
    # 驗證提取結果
    if [ ! -d "$CHROMA_DB_DIR" ]; then
        print_error "提取後數據庫目錄不存在"
        return 1
    fi
    
    # 統計文件數和大小
    local file_count=$(find "$CHROMA_DB_DIR" -type f 2>/dev/null | wc -l)
    local dir_size=$(du -sh "$CHROMA_DB_DIR" 2>/dev/null | cut -f1)
    
    print_info "✅ 數據庫還原成功！"
    print_info "  📁 目錄: $CHROMA_DB_DIR"
    print_info "  📊 文件數: $file_count"
    print_info "  💾 大小: $dir_size"
    
    return 0
}

# 函數：創建空數據庫目錄
create_empty_database() {
    print_step "創建空數據庫目錄"
    
    if [ -d "$CHROMA_DB_DIR" ]; then
        print_warn "數據庫目錄已存在"
        return 0
    fi
    
    print_info "創建目錄: $CHROMA_DB_DIR"
    mkdir -p "$CHROMA_DB_DIR"
    
    print_info "✅ 空數據庫目錄已創建"
    return 0
}

# 函數：列出可用的備份
list_backups() {
    print_step "可用的備份文件"
    
    if [ ! -d "$BACKUP_DIR" ]; then
        print_warn "備份目錄不存在"
        return 1
    fi
    
    local backup_count=$(ls -1 "$BACKUP_DIR"/chroma_db_*.tar.gz 2>/dev/null | wc -l)
    
    if [ $backup_count -eq 0 ]; then
        print_warn "未找到任何備份文件"
        return 1
    fi
    
    print_info "找到 $backup_count 個備份文件："
    ls -lh "$BACKUP_DIR"/chroma_db_*.tar.gz | awk '{printf "  📦 %s (%s)\n", $9, $5}'
    
    return 0
}

# 函數：啟動應用
start_application() {
    print_step "啟動應用程序"
    
    print_info "啟動命令: uv run chainlit run app.py --host 0.0.0.0 --port 7861"
    
    # 啟動應用
    exec uv run chainlit run app.py --host 0.0.0.0 --port 7861
}

# 函數：初始化對話資料庫
init_conversation_db() {
    print_step "初始化對話資料庫 (chainlit.db)"

    if [ ! -f "${PROJECT_DIR}/database_utility/init_db.py" ]; then
        print_warn "未找到 database_utility/init_db.py，跳過初始化"
        return 0
    fi

    # 確保 chainlit.db 檔案存在且可寫
    mkdir -p "$CHAINLIT_DB_DIR"
    if [ -d "$CHAINLIT_DB_PATH" ]; then
        print_error "chainlit.db 是資料夾，無法初始化"
        return 1
    fi
    if [ ! -f "$CHAINLIT_DB_PATH" ]; then
        print_info "建立空的 chainlit.db"
        touch "$CHAINLIT_DB_PATH"
    fi

    print_info "執行: uv run python database_utility/init_db.py"
    if ! CHAINLIT_DB_PATH="$CHAINLIT_DB_PATH" uv run python database_utility/init_db.py; then
        print_error "初始化對話資料庫失敗"
        return 1
    fi

    print_info "✅ 對話資料庫初始化完成"
    return 0
}

# 函數：主初始化流程
main() {
    print_step "Chroma 數據庫初始化"
    
    print_info "項目目錄: $PROJECT_DIR"
    print_info "Chroma 數據庫: $CHROMA_DB_DIR"
    print_info "備份目錄: $BACKUP_DIR"
    
    # 嘗試尋找最新備份
    BACKUP_FILE=$(find_latest_backup)
    
    if [ -z "$BACKUP_FILE" ]; then
        print_warn "未找到備份文件"
        list_backups || true
        
        print_warn "將創建空數據庫"
        if ! create_empty_database; then
            print_error "創建空數據庫失敗"
            exit 1
        fi
    else
        print_info "找到最新備份: $BACKUP_FILE"
        print_info "文件大小: $(du -h "$BACKUP_FILE" | cut -f1)"
        
        # 還原數據庫
        if ! restore_database "$BACKUP_FILE"; then
            print_error "數據庫還原失敗"
            print_warn "將嘗試創建空數據庫繼續啟動"
            
            if ! create_empty_database; then
                print_error "創建空數據庫也失敗了"
                exit 1
            fi
        fi
    fi
    
    # 檢查數據庫目錄
    if [ ! -d "$CHROMA_DB_DIR" ]; then
        print_error "數據庫目錄不存在且無法創建"
        exit 1
    fi
    
    print_info "數據庫初始化完成 ✅"

    # 初始化對話資料庫
    if ! init_conversation_db; then
        print_warn "對話資料庫初始化失敗，仍嘗試啟動應用"
    fi

    # 將 DB 路徑傳給應用
    export CHAINLIT_DB_PATH="$CHAINLIT_DB_PATH"
    
    # 啟動應用
    start_application
}

# 執行主程序
main "$@"
