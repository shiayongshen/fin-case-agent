#!/bin/bash

# 快速測試腳本 - 簡潔版本

CONTAINER="${1:-uicompliance-app}"

echo "╔════════════════════════════════════════╗"
echo "║     Docker 快速測試                    ║"
echo "╚════════════════════════════════════════╝"
echo ""

# 檢查容器
echo "🔍 檢查容器狀態..."
if ! docker ps --filter "name=$CONTAINER" --quiet | grep -q .; then
    echo "❌ 容器未運行: $CONTAINER"
    exit 1
fi
echo "✅ 容器運行中"

# 測試數據庫連接
echo ""
echo "🔍 檢查數據庫..."
docker exec "$CONTAINER" python3 << 'EOF'
import sys
sys.path.insert(0, '/app')
from chromadb.config import Settings
from chromadb import Client

try:
    client = Client(Settings(persist_directory="/app/chroma_db", is_persistent=True))
    for col in client.list_collections():
        print(f"  ✅ {col.name}: {col.count()} 個文檔")
except Exception as e:
    print(f"  ❌ {e}")
    sys.exit(1)
EOF

# 測試 HTTP 連接
echo ""
echo "🔍 檢查 HTTP 服務..."
if curl -s -m 3 http://localhost:7861 > /dev/null; then
    echo "✅ HTTP 服務運行中 (http://localhost:7861)"
else
    echo "⚠️  無法連接到 HTTP 服務（但可能還在啟動中）"
fi

# 檢查日誌
echo ""
echo "🔍 檢查日誌..."
if docker logs "$CONTAINER" 2>&1 | grep -qi "fatal\|critical error"; then
    echo "❌ 日誌中發現致命錯誤"
    docker logs "$CONTAINER" | tail -20
else
    echo "✅ 沒有發現致命錯誤"
fi

echo ""
echo "╔════════════════════════════════════════╗"
echo "║         快速測試完成！               ║"
echo "╚════════════════════════════════════════╝"
