#!/bin/bash

# Chroma 數據庫遷移腳本
# 用途：壓縮並導出 Chroma 數據庫，或從備份恢復

set -e  # 遇到錯誤立即退出

# 顏色輸出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 配置
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CHROMA_DB_DIR="${PROJECT_DIR}/chroma_db"
BACKUP_DIR="${PROJECT_DIR}/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
ARCHIVE_NAME="chroma_db_${TIMESTAMP}.tar.gz"
ARCHIVE_PATH="${BACKUP_DIR}/${ARCHIVE_NAME}"

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

# 函數：導出數據庫
export_database() {
    print_info "開始導出 Chroma 數據庫..."
    
    if [ ! -d "$CHROMA_DB_DIR" ]; then
        print_error "Chroma 數據庫目錄不存在: $CHROMA_DB_DIR"
        exit 1
    fi
    
    # 創建備份目錄
    mkdir -p "$BACKUP_DIR"
    
    # 檢查數據庫大小
    db_size=$(du -sh "$CHROMA_DB_DIR" | cut -f1)
    print_info "數據庫大小: $db_size"
    
    # 壓縮數據庫
    print_info "壓縮中... (這可能需要一些時間)"
    tar -czf "$ARCHIVE_PATH" -C "$PROJECT_DIR" chroma_db
    
    archive_size=$(du -sh "$ARCHIVE_PATH" | cut -f1)
    print_info "✅ 導出成功！"
    print_info "備份文件: $ARCHIVE_PATH"
    print_info "壓縮後大小: $archive_size"
}

# 函數：恢復數據庫
restore_database() {
    local archive_file="$1"
    
    if [ -z "$archive_file" ]; then
        print_error "請指定備份文件路徑"
        echo "用法: $0 restore <backup_file>"
        exit 1
    fi
    
    if [ ! -f "$archive_file" ]; then
        print_error "備份文件不存在: $archive_file"
        exit 1
    fi
    
    print_info "開始恢復數據庫..."
    print_warn "警告：現有的 chroma_db 將被刪除！"
    read -p "確認繼續嗎？(y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_warn "已取消"
        exit 1
    fi
    
    # 刪除現有數據庫
    if [ -d "$CHROMA_DB_DIR" ]; then
        print_info "刪除現有數據庫..."
        rm -rf "$CHROMA_DB_DIR"
    fi
    
    # 解壓備份
    print_info "解壓中..."
    tar -xzf "$archive_file" -C "$PROJECT_DIR"
    
    print_info "✅ 恢復成功！"
    print_info "數據庫路徑: $CHROMA_DB_DIR"
}

# 函數：列出備份
list_backups() {
    if [ ! -d "$BACKUP_DIR" ]; then
        print_warn "備份目錄不存在"
        return
    fi
    
    print_info "可用的備份："
    ls -lh "$BACKUP_DIR"/chroma_db_*.tar.gz 2>/dev/null | awk '{print $9, "(" $5 ")"}' || print_warn "沒有找到備份文件"
}

# 函數：檢查數據庫狀態
check_status() {
    print_info "檢查數據庫狀態..."
    
    if [ ! -d "$CHROMA_DB_DIR" ]; then
        print_warn "Chroma 數據庫不存在"
        return
    fi
    
    db_size=$(du -sh "$CHROMA_DB_DIR" | cut -f1)
    file_count=$(find "$CHROMA_DB_DIR" -type f | wc -l)
    
    print_info "數據庫路徑: $CHROMA_DB_DIR"
    print_info "數據庫大小: $db_size"
    print_info "文件數量: $file_count"
}

# 函數：上傳到遠程服務器
upload_to_remote() {
    local remote_user="$1"
    local remote_host="$2"
    local remote_path="$3"
    
    if [ -z "$remote_user" ] || [ -z "$remote_host" ] || [ -z "$remote_path" ]; then
        print_error "用法: $0 upload <user> <host> <remote_path>"
        echo "例如: $0 upload ubuntu 192.168.1.100 /home/ubuntu/uicompliance/"
        exit 1
    fi
    
    if [ ! -f "$ARCHIVE_PATH" ]; then
        print_warn "未找到最近的備份，先創建備份..."
        export_database
    fi
    
    print_info "上傳到遠程服務器: $remote_user@$remote_host:$remote_path"
    scp "$ARCHIVE_PATH" "${remote_user}@${remote_host}:${remote_path}/"
    
    print_info "✅ 上傳成功！"
    print_info "在遠程服務器上執行:"
    echo "  cd $remote_path"
    echo "  bash scripts/migrate_chroma_db.sh restore $(basename $ARCHIVE_PATH)"
}

# 函數：從遠程下載
download_from_remote() {
    local remote_user="$1"
    local remote_host="$2"
    local remote_backup_file="$3"
    
    if [ -z "$remote_user" ] || [ -z "$remote_host" ] || [ -z "$remote_backup_file" ]; then
        print_error "用法: $0 download <user> <host> <remote_backup_file>"
        echo "例如: $0 download ubuntu 192.168.1.100 /home/ubuntu/uicompliance/backups/chroma_db_20250101_000000.tar.gz"
        exit 1
    fi
    
    mkdir -p "$BACKUP_DIR"
    
    print_info "從遠程下載: $remote_user@$remote_host:$remote_backup_file"
    scp "${remote_user}@${remote_host}:${remote_backup_file}" "$BACKUP_DIR/"
    
    local downloaded_file=$(basename "$remote_backup_file")
    print_info "✅ 下載成功！"
    print_info "執行恢復:"
    echo "  bash scripts/migrate_chroma_db.sh restore backups/$downloaded_file"
}

# 主程序
main() {
    local command="${1:-help}"
    
    case "$command" in
        export)
            export_database
            ;;
        restore)
            restore_database "$2"
            ;;
        list)
            list_backups
            ;;
        status)
            check_status
            ;;
        upload)
            upload_to_remote "$2" "$3" "$4"
            ;;
        download)
            download_from_remote "$2" "$3" "$4"
            ;;
        help|*)
            cat << EOF
Chroma 數據庫遷移工具

使用方法:
  bash scripts/migrate_chroma_db.sh <command> [options]

命令:
  export                   導出數據庫為壓縮文件
  restore <file>           從備份文件恢復數據庫
  list                     列出所有備份文件
  status                   檢查數據庫狀態
  upload <user> <host> <path>    上傳到遠程服務器 (需要 SSH 訪問)
  download <user> <host> <file>  從遠程下載備份
  help                     顯示此幫助信息

示例:
  # 導出當前數據庫
  bash scripts/migrate_chroma_db.sh export

  # 恢復最近的備份
  bash scripts/migrate_chroma_db.sh list
  bash scripts/migrate_chroma_db.sh restore backups/chroma_db_20250101_000000.tar.gz

  # 上傳到遠程 Docker 服務器
  bash scripts/migrate_chroma_db.sh upload ubuntu 192.168.1.100 /home/ubuntu/uicompliance/

  # 從遠程下載備份
  bash scripts/migrate_chroma_db.sh download ubuntu 192.168.1.100 /home/ubuntu/uicompliance/backups/chroma_db_*.tar.gz

EOF
            ;;
    esac
}

# 運行主程序
main "$@"