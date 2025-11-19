# fin-network 集成說明

## 🔄 更新內容

### docker-compose.yml
已修改為使用 `fin-network`：

```yaml
networks:
  - default       # Docker Compose 內部網路
  - fin-network   # 外部網路（連接 fin-backend）
```

### 環境變數
- `REPORT_API_BASE` 預設為 `http://fin-backend:6677`
- 可透過 `.env` 或環境變數覆蓋

## 🚀 一鍵啟動

### 1. 建立 fin-network （首次）
```bash
docker network create fin-network
```

### 2. 構建並啟動
```bash
docker-compose build
docker-compose up -d
```

### 3. 檢查狀態
```bash
docker-compose ps
```

## 📡 API 集成

應用現在可以發送請求到 `http://fin-backend:6677`：

### Python 範例
```python
import httpx

async def upload_report(report_content: str, title: str):
    url = "http://fin-backend:6677/report/generated/fin-case"
    payload = {
        "report": report_content,
        "title": title
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload)
        return response.json()
```

### 可用端點
- `POST /report/generated/fin-tax` - 上傳稅務報告
- `POST /report/generated/fin-case` - 上傳案例報告
- `POST /report/generated/fin-alpha-modeling` - 上傳 Alpha 建模報告
- `POST /report/generated/fin-alpha-mining` - 上傳 Alpha 挖掘報告（支援圖片）
- `POST /report/generate` - 生成報告

詳細 API 文檔見 fin-backend 服務文檔。

## 🔧 故障排除

### 容器無法連接 fin-backend
```bash
# 檢查網路是否存在
docker network ls | grep fin-network

# 檢查容器是否加入網路
docker network inspect fin-network

# 從容器內測試連接
docker-compose exec compliance-app curl -v http://fin-backend:6677
```

### 重新構建
```bash
docker-compose down -v
docker-compose build --no-cache
docker-compose up -d
```
