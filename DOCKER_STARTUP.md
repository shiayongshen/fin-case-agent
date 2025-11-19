# Docker 啟動指南

## 前置要求

- Docker 已安裝
- Docker Compose 已安裝
- **`.env` 檔案已配置** （包含 `OPENAI_API_KEY`）
- **`fin-network` 網路已建立** （用於連接 `fin-backend`）

### 建立 fin-network （如果還未建立）

```bash
docker network create fin-network
```

## 快速啟動

### 1. 構建鏡像
```bash
docker-compose build
```
**作用**：根據 Dockerfile 構建 Docker 鏡像
- 安裝 Python 3.13 環境
- 安裝系統依賴和 uv 包管理器
- 安裝 pyproject.toml 中的所有 Python 依賴
- 創建非 root 用戶

### 2. 啟動容器
```bash
docker-compose up -d
```
**作用**：以後台模式啟動容器
- `-d`：Detached 模式（後台運行）
- 容器名稱：`compliance_demo_app`
- 暴露端口：`7861`

### 3. 檢查容器狀態
```bash
docker-compose ps
```
**作用**：檢查容器是否正常運行

### 4. 查看日誌
```bash
docker-compose logs -f compliance-app
```
**作用**：實時查看容器日誌
- `-f`：Follow 模式（持續監控）

### 5. 停止容器
```bash
docker-compose down
```
**作用**：停止並移除容器

## 完整工作流程

### 首次啟動（一次性操作）
```bash
# 1. 進入項目目錄
cd /Users/vincenthsia/uicompliance

# 2. 確認 .env 檔案存在且包含 OPENAI_API_KEY
cat .env

# 3. 確認 fin-network 已建立
docker network ls | grep fin-network

# 4. 構建鏡像
docker-compose build

# 5. 啟動容器
docker-compose up -d

# 6. 等待應用啟動（約 40 秒）並檢查狀態
docker-compose ps
```

### 日常使用
```bash
# 啟動
docker-compose up -d

# 查看狀態
docker-compose ps

# 查看日誌
docker-compose logs -f compliance-app

# 停止
docker-compose down
```

## 常用命令

| 命令 | 作用 |
|------|------|
| `docker-compose build` | 構建鏡像 |
| `docker-compose up -d` | 啟動容器（後台） |
| `docker-compose down` | 停止容器 |
| `docker-compose ps` | 查看容器狀態 |
| `docker-compose logs -f` | 查看實時日誌 |
| `docker-compose exec compliance-app bash` | 進入容器 |
| `docker-compose restart` | 重啟容器 |

## 容器配置說明

- **鏡像**：Python 3.13 slim
- **工作目錄**：`/app`
- **入口點**：`chainlit run app.py --host 0.0.0.0 --port 7861`
- **端口**：7861
- **持久化數據**：
  - `chroma_db`：向量數據庫
  - `outputs`：分析輸出檔案
  - `chainlit.db`：Chainlit 數據庫

## 環境變數

- `OPENAI_API_KEY`：OpenAI API 密鑰（**必需**）
- `REPORT_API_BASE`：後端 API 地址
  - 預設：`http://fin-backend:6677`（Docker 內部連接）
  - 可覆蓋：`export REPORT_API_BASE=http://your-backend:port`
- `PYTHONPATH`：Python 路徑（預設：`/app`）

## 網路配置說明

應用同時連接到兩個網路：

1. **default**：Docker Compose 內部網路（用於容器內通訊）
2. **fin-network**：外部網路（用於連接 `fin-backend` 服務）

這樣的配置允許應用：
- 向 `fin-backend:6677` 發送 API 請求（如上傳報告）
- 隔離於其他應用的內部通訊

## API 集成說明

應用可以使用以下端點上傳生成的報告到 fin-backend：

### 上傳稅務報告
```bash
curl -X POST 'http://fin-backend:6677/report/generated/fin-tax' \
  -H 'Content-Type: application/json' \
  -d '{
    "report": "report-content...",
    "title": "report-title"
  }'
```

### 上傳案例報告
```bash
curl -X POST 'http://fin-backend:6677/report/generated/fin-case' \
  -H 'Content-Type: application/json' \
  -d '{
    "report": "report-content...",
    "title": "report-title"
  }'
```

### 上傳 Alpha 建模報告
```bash
curl -X POST 'http://fin-backend:6677/report/generated/fin-alpha-modeling' \
  -H 'Content-Type: application/json' \
  -d '{
    "report": "report-content...",
    "title": "report-title"
  }'
```

更多端點詳情見 fin-backend API 文檔。

## 故障排除

### 容器無法啟動
```bash
# 查看詳細錯誤
docker-compose logs compliance-app
```

### 重新構建鏡像
```bash
# 強制重新構建（不使用緩存）
docker-compose build --no-cache
```

### 清理所有資源
```bash
# 移除容器、網路、卷
docker-compose down -v
```

### 檢查 API 連通性
```bash
# 進入容器測試
docker-compose exec compliance-app curl -f http://localhost:7861/health
```

## 訪問應用

應用啟動後，訪問：
```
http://localhost:7861
```
