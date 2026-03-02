# 使用輕量 Python 基礎映像（無 torch 版本）
FROM python:3.11-slim

WORKDIR /app

# 設置非交互式安裝
ENV DEBIAN_FRONTEND=noninteractive

# 安裝系統依賴
RUN apt-get update && apt-get install -y \
    build-essential \
    tar \
    gzip \
    bash \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# 安裝 uv 包管理器
RUN pip install uv

# 複製依賴文件（只複製 pyproject.toml，不使用舊的 lock 檔案）
COPY pyproject.toml ./

# 使用 uv 安裝依賴（重新生成 lock 檔案）
# 不使用全局 CUDA 索引，避免其他套件從 PyTorch 索引安裝
RUN uv lock && uv sync --no-install-project

# 複製應用代碼
COPY . .

# 給初始化腳本執行權限
RUN chmod +x /app/scripts/init_database.sh

# 創建 .chainlit 和 logs 目錄
RUN mkdir -p /app/.chainlit \
    && mkdir -p /app/logs \
    && chmod -R 777 /app/.chainlit \
    && chmod -R 777 /app/logs


# 暴露端口
EXPOSE 7861

# 設置環境變數
ENV REPORT_API_BASE=http://fin-backend:6677
ENV PYTHONPATH=/app
ENV CHAINLIT_AUTH_DISABLED=true
# 使用初始化腳本作為入口點
ENTRYPOINT ["/bin/bash", "/app/scripts/init_database.sh"]
