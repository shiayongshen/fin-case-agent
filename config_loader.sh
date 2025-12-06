#!/bin/bash
# =========================================
# UI Compliance - 環境配置加載器
# =========================================
#
# 使用方法：
#   source config_loader.sh ollama
#   source config_loader.sh openai
#   source config_loader.sh production

# 獲取配置名稱（默認為開發）
CONFIG_NAME="${1:-development}"

# 定義顏色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}UI Compliance - 環境配置加載器${NC}"
echo -e "${BLUE}========================================${NC}\n"

case "$CONFIG_NAME" in
  "ollama" | "local" | "dev" | "development")
    echo -e "${GREEN}✅ 加載配置: Ollama (本地開發)${NC}\n"
    
    export USE_OLLAMA=true
    export OLLAMA_MODEL=mistral
    export OLLAMA_BASE_URL=http://localhost:11434
    export OPENAI_API_KEY=
    
    echo -e "${BLUE}環境變數:${NC}"
    echo "  USE_OLLAMA: ${YELLOW}true${NC}"
    echo "  OLLAMA_MODEL: ${YELLOW}$OLLAMA_MODEL${NC}"
    echo "  OLLAMA_BASE_URL: ${YELLOW}$OLLAMA_BASE_URL${NC}"
    echo ""
    echo -e "${YELLOW}提示:${NC}"
    echo "  1. 在另一個終端中運行: ollama serve"
    echo "  2. 然後啟動應用: chainlit run app.py"
    ;;
    
  "openai" | "cloud")
    echo -e "${GREEN}✅ 加載配置: OpenAI API (雲端)${NC}\n"
    
    export USE_OLLAMA=false
    export OPENAI_API_KEY="${OPENAI_API_KEY:-sk-your-key-here}"
    export OPENAI_MODEL=gpt-4.1-mini
    
    echo -e "${BLUE}環境變數:${NC}"
    echo "  USE_OLLAMA: ${YELLOW}false${NC}"
    echo "  OPENAI_API_KEY: ${YELLOW}${OPENAI_API_KEY:0:10}...${NC}"
    echo "  OPENAI_MODEL: ${YELLOW}$OPENAI_MODEL${NC}"
    echo ""
    
    if [ "$OPENAI_API_KEY" == "sk-your-key-here" ]; then
      echo -e "${RED}⚠️  警告: API Key 未設定!${NC}"
      echo -e "${YELLOW}  設定 API Key:${NC}"
      echo "    export OPENAI_API_KEY=sk-your-actual-key"
      echo "    source config_loader.sh openai"
    else
      echo -e "${GREEN}✅ API Key 已設定${NC}"
    fi
    echo ""
    echo -e "${YELLOW}提示:${NC}"
    echo "  啟動應用: chainlit run app.py"
    ;;
    
  "production" | "prod")
    echo -e "${GREEN}✅ 加載配置: 生產環境 (OpenAI)${NC}\n"
    
    export USE_OLLAMA=false
    export OPENAI_API_KEY="${PROD_OPENAI_API_KEY:-sk-prod-key-here}"
    export OPENAI_MODEL=gpt-4-turbo
    
    echo -e "${BLUE}環境變數:${NC}"
    echo "  USE_OLLAMA: ${YELLOW}false${NC}"
    echo "  OPENAI_API_KEY: ${YELLOW}${OPENAI_API_KEY:0:10}...${NC}"
    echo "  OPENAI_MODEL: ${YELLOW}gpt-4-turbo (高質量)${NC}"
    echo ""
    
    if [ "$OPENAI_API_KEY" == "sk-prod-key-here" ]; then
      echo -e "${RED}❌ 錯誤: 生產 API Key 未設定!${NC}"
      echo -e "${YELLOW}  請設定環境變數:${NC}"
      echo "    export PROD_OPENAI_API_KEY=sk-actual-key"
      exit 1
    fi
    
    echo -e "${YELLOW}提示:${NC}"
    echo "  啟動應用: chainlit run app.py --host 0.0.0.0 --port 8000"
    echo "  監控日誌: tail -f chainlit.log"
    ;;
    
  "team" | "enterprise")
    echo -e "${GREEN}✅ 加載配置: 團隊/企業 (Ollama 伺服器)${NC}\n"
    
    export USE_OLLAMA=true
    export OLLAMA_MODEL=neural-chat
    export OLLAMA_BASE_URL="${TEAM_OLLAMA_URL:-http://ollama-server.internal:11434}"
    export OPENAI_API_KEY=
    
    echo -e "${BLUE}環境變數:${NC}"
    echo "  USE_OLLAMA: ${YELLOW}true${NC}"
    echo "  OLLAMA_MODEL: ${YELLOW}$OLLAMA_MODEL (對話優化)${NC}"
    echo "  OLLAMA_BASE_URL: ${YELLOW}$OLLAMA_BASE_URL${NC}"
    echo ""
    echo -e "${YELLOW}提示:${NC}"
    echo "  確保 Ollama 伺服器正在運行"
    echo "  啟動應用: chainlit run app.py --host 0.0.0.0"
    ;;
    
  "llama3" | "lightweight")
    echo -e "${GREEN}✅ 加載配置: 輕量級 (Llama 3.2)${NC}\n"
    
    export USE_OLLAMA=true
    export OLLAMA_MODEL=llama3.2:1b
    export OLLAMA_BASE_URL=http://localhost:11434
    export OPENAI_API_KEY=
    
    echo -e "${BLUE}環境變數:${NC}"
    echo "  USE_OLLAMA: ${YELLOW}true${NC}"
    echo "  OLLAMA_MODEL: ${YELLOW}llama3.2:1b (超輕量)${NC}"
    echo "  OLLAMA_BASE_URL: ${YELLOW}$OLLAMA_BASE_URL${NC}"
    echo ""
    echo -e "${YELLOW}提示:${NC}"
    echo "  最快啟動，最少資源消耗"
    echo "  質量: 基礎任務可用"
    echo "  下載模型: ollama pull llama3.2:1b"
    ;;
    
  "high-quality" | "gpt4")
    echo -e "${GREEN}✅ 加載配置: 高質量 (GPT-4 Turbo)${NC}\n"
    
    export USE_OLLAMA=false
    export OPENAI_API_KEY="${OPENAI_API_KEY:-sk-your-key-here}"
    export OPENAI_MODEL=gpt-4-turbo
    
    echo -e "${BLUE}環境變數:${NC}"
    echo "  USE_OLLAMA: ${YELLOW}false${NC}"
    echo "  OPENAI_API_KEY: ${YELLOW}${OPENAI_API_KEY:0:10}...${NC}"
    echo "  OPENAI_MODEL: ${YELLOW}gpt-4-turbo (最佳質量)${NC}"
    echo ""
    echo -e "${YELLOW}提示:${NC}"
    echo "  用於複雜法律分析"
    echo "  成本: 較高（但質量最佳）"
    echo "  推薦用於生產關鍵任務"
    ;;
    
  "help" | "-h" | "--help" | "")
    if [ "$CONFIG_NAME" == "" ]; then
      CONFIG_NAME="help"
    fi
    
    echo -e "${BLUE}使用方法:${NC}"
    echo "  source config_loader.sh <配置名稱>\n"
    
    echo -e "${BLUE}可用配置:${NC}"
    echo "  ${YELLOW}ollama${NC} (local, dev, development)"
    echo "    └─ Ollama 本地開發配置"
    echo ""
    echo "  ${YELLOW}openai${NC} (cloud)"
    echo "    └─ OpenAI API 雲端配置"
    echo ""
    echo "  ${YELLOW}production${NC} (prod)"
    echo "    └─ 生產環境配置（高質量）"
    echo ""
    echo "  ${YELLOW}team${NC} (enterprise)"
    echo "    └─ 團隊/企業 Ollama 伺服器配置"
    echo ""
    echo "  ${YELLOW}llama3${NC} (lightweight)"
    echo "    └─ 輕量級模型配置"
    echo ""
    echo "  ${YELLOW}high-quality${NC} (gpt4)"
    echo "    └─ 高質量 GPT-4 Turbo 配置"
    echo ""
    
    echo -e "${BLUE}快速開始:${NC}"
    echo "  1. 本地開發:"
    echo "     source config_loader.sh ollama"
    echo "     ./start_with_ollama.sh"
    echo ""
    echo "  2. 使用 OpenAI:"
    echo "     export OPENAI_API_KEY=sk-..."
    echo "     source config_loader.sh openai"
    echo "     chainlit run app.py"
    echo ""
    echo "  3. 生產部署:"
    echo "     export PROD_OPENAI_API_KEY=sk-prod-key"
    echo "     source config_loader.sh production"
    echo "     chainlit run app.py --host 0.0.0.0"
    echo ""
    
    echo -e "${BLUE}驗證配置:${NC}"
    echo "  source config_loader.sh ollama"
    echo "  echo \$OLLAMA_MODEL"
    echo "  python test_agent_ollama.py"
    echo ""
    ;;
    
  *)
    echo -e "${RED}❌ 未知配置: $CONFIG_NAME${NC}\n"
    echo -e "${YELLOW}可用選項:${NC}"
    echo "  ollama, openai, production, team, llama3, high-quality"
    echo ""
    echo -e "${YELLOW}獲得幫助:${NC}"
    echo "  source config_loader.sh help"
    echo ""
    exit 1
    ;;
esac

echo -e "\n${GREEN}✅ 配置已加載${NC}\n"
echo -e "${BLUE}現在可以運行:${NC}"
echo "  ${YELLOW}chainlit run app.py${NC}"
echo ""
