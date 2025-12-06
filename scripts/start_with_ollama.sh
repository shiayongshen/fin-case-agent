#!/bin/bash

# ================================
# UI Compliance - Ollama 啟動腳本
# ================================

# 色彩定義
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 設定
VENV_PATH=".venv"
OLLAMA_MODEL="${OLLAMA_MODEL:-llama3.2:1b}"
OLLAMA_BASE_URL="${OLLAMA_BASE_URL:-http://localhost:11434}"

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║         UI Compliance - Ollama Deployment Script           ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}\n"

# ===== 檢查 Ollama 安裝 =====
echo -e "${YELLOW}[1/5] 檢查 Ollama 是否已安裝...${NC}"
if ! command -v ollama &> /dev/null; then
    echo -e "${RED}❌ Ollama 未安裝${NC}"
    echo -e "   請訪問 ${BLUE}https://ollama.ai${NC} 進行安裝"
    echo -e "   macOS: ${BLUE}brew install ollama${NC}"
    echo -e "   Linux: ${BLUE}curl -fsSL https://ollama.ai/install.sh | sh${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Ollama 已安裝 $(ollama --version)${NC}\n"

# ===== 檢查虛擬環境 =====
echo -e "${YELLOW}[2/5] 檢查 Python 虛擬環境...${NC}"
if [ ! -d "$VENV_PATH" ]; then
    echo -e "${RED}❌ 虛擬環境不存在${NC}"
    echo -e "   請先運行: ${BLUE}python -m venv .venv${NC}"
    exit 1
fi
echo -e "${GREEN}✅ 虛擬環境存在${NC}\n"

# ===== 啟動 Ollama 服務 =====
echo -e "${YELLOW}[3/5] 啟動 Ollama 服務...${NC}"
if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Ollama 服務已運行${NC}\n"
else
    echo -e "${YELLOW}🚀 正在啟動 Ollama 服務...${NC}"
    ollama serve > /tmp/ollama.log 2>&1 &
    OLLAMA_PID=$!
    
    # 等待服務啟動
    echo -e "${YELLOW}   等待服務啟動...${NC}"
    for i in {1..30}; do
        if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
            echo -e "${GREEN}✅ Ollama 服務已啟動 (PID: $OLLAMA_PID)${NC}\n"
            break
        fi
        echo -n "."
        sleep 1
    done
    
    if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
        echo -e "${RED}❌ Ollama 服務啟動失敗${NC}"
        echo -e "   請檢查日誌: ${BLUE}tail -f /tmp/ollama.log${NC}"
        exit 1
    fi
fi

# ===== 檢查模型 =====
echo -e "${YELLOW}[4/5] 檢查模型 '$OLLAMA_MODEL'...${NC}"
if ollama list 2>/dev/null | grep -q "^$OLLAMA_MODEL"; then
    echo -e "${GREEN}✅ 模型已下載${NC}\n"
else
    echo -e "${YELLOW}⬇️  下載模型 '$OLLAMA_MODEL'...${NC}"
    echo -e "   這可能需要幾分鐘...${NC}"
    
    if ollama pull "$OLLAMA_MODEL"; then
        echo -e "${GREEN}✅ 模型下載完成${NC}\n"
    else
        echo -e "${RED}❌ 模型下載失敗${NC}"
        echo -e "   請嘗試手動下載: ${BLUE}ollama pull $OLLAMA_MODEL${NC}"
        exit 1
    fi
fi

# ===== 啟動應用 =====
echo -e "${YELLOW}[5/5] 啟動應用...${NC}\n"

# 激活虛擬環境
source "$VENV_PATH/bin/activate"

# 設定 Ollama 環境變數
export USE_OLLAMA=true
export OLLAMA_MODEL="$OLLAMA_MODEL"
export OLLAMA_BASE_URL="$OLLAMA_BASE_URL"

echo -e "${GREEN}環境配置:${NC}"
echo -e "  USE_OLLAMA: ${BLUE}true${NC}"
echo -e "  OLLAMA_MODEL: ${BLUE}$OLLAMA_MODEL${NC}"
echo -e "  OLLAMA_BASE_URL: ${BLUE}$OLLAMA_BASE_URL${NC}"
echo ""

echo -e "${GREEN}🚀 啟動應用...${NC}"
echo -e "   訪問地址: ${BLUE}http://localhost:8000${NC}\n"

# 啟動 Chainlit
chainlit run app.py

# 清理
if [ ! -z "$OLLAMA_PID" ]; then
    echo -e "\n${YELLOW}清理 Ollama 進程...${NC}"
    kill $OLLAMA_PID 2>/dev/null
    echo -e "${GREEN}✅ 清理完成${NC}"
fi
