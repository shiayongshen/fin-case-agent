# UI Compliance 金融法規遵循分析系統

一個基於 AI 的金融法規遵循分析平台，使用 Chainlit、AutoGen 和 Z3 Solver 提供智能的法規分析服務。

## 功能特點

- 🔍 **智能案例搜索**：基於向量檢索的金融案例搜索
- 📊 **深入法規分析**：使用 Z3 Solver 進行形式化驗證
- 🤖 **多代理協作**：AutoGen 驅動的多代理對話系統
- 💬 **即時聊天界面**：Chainlit 提供的現代化 UI

## 本地開發

### 環境準備

```bash
# 安裝 uv 包管理器
pip install uv

# 安裝依賴
uv sync

# 激活虛擬環境
source .venv/bin/activate  # Linux/Mac
# 或
.venv\Scripts\activate     # Windows
```

### 數據庫初始化

```bash
# 刪除舊資料庫
rm -f chainlit.db

# 重新初始化
python database_utility/init_db.py
```

### 啟動應用

```bash
# 啟動應用
chainlit run app.py
```

應用將在 http://localhost:7861 上運行。

## Docker 部署

### 環境變數

複製環境變數模板並填入你的配置：

```bash
cp .env.example .env
# 編輯 .env 文件，設置 OPENAI_API_KEY 等變數
```

### 使用 Docker Compose

```bash
# 構建並啟動服務
make build && make up

# 或直接使用 docker compose
docker compose up -d --build

# 查看日誌
make logs

# 停止服務
make down
```

### 常用 Docker 命令

```bash
# 完全重建
make rebuild

# 進入容器
make shell

# 查看服務狀態
make status

# 清理所有資源
make clean
```

### 卷掛載說明

- `chroma_db`: ChromaDB 向量數據庫持久化
- `code_execution`: 代碼執行結果
- `./outputs`: 分析輸出文件
- `./chainlit.db`: Chainlit 數據庫

## 環境變數

| 變數名 | 說明 | 預設值 |
|--------|------|--------|
| `OPENAI_API_KEY` | OpenAI API 金鑰 | 必需 |
| `REPORT_API_BASE` | 後端 API 地址 | `http://fin-backend:6677` |
| `CHAINLIT_PORT` | 應用端口 | `7861` |

## 項目結構

```
uicompliance/
├── agents/                 # AI 代理模組
│   ├── BaseAgent.py       # 基礎代理類
│   ├── ChatManager.py     # 對話管理器
│   ├── HostAgent.py       # 主控代理
│   ├── SearchAgent.py     # 搜索代理
│   └── DeepAnalysisAgent.py # 深入分析代理
├── utility/               # 工具模組
│   └── legal_search.py    # 法律搜索功能
├── chroma_db/            # 向量數據庫
├── outputs/              # 分析輸出
├── public/               # 靜態資源
├── Dockerfile            # Docker 鏡像定義
├── docker-compose.yml    # Docker Compose 配置
├── pyproject.toml        # 項目配置
└── app.py               # 主應用入口
```

## 開發說明

### 添加新功能

1. 在 `agents/` 目錄下添加新的代理類
2. 在 `utility/` 目錄下添加工具函數
3. 更新 `ChatManager.py` 中的狀態轉換邏輯
4. 更新 `app.py` 中的路由和處理邏輯

### 測試

```bash
# 運行測試
python -m pytest test/

# 或使用 uv
uv run pytest test/
```

## 部署注意事項

- 確保 `fin-backend` 服務在 `fin-network` 網絡中可用
- 配置適當的 OpenAI API 金鑰
- 監控 ChromaDB 數據庫的磁盤使用情況
- 定期備份重要的數據卷

## 授權

本項目採用 MIT 授權。
