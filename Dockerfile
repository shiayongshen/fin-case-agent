FROM python:3.13-slim

WORKDIR /app

# 安裝系統依賴
RUN apt-get update && apt-get install -y \
    build-essential \
    tar \
    gzip \
    bash \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 安裝 uv 包管理器
RUN pip install uv

# 複製依賴文件
COPY pyproject.toml uv.lock ./

# 使用 uv 安裝依賴
RUN uv sync --frozen --no-install-project

# 複製應用代碼
COPY . .

# 給初始化腳本執行權限
RUN chmod +x /app/scripts/init_database.sh

# ✅ 關鍵：只創建 .chainlit 和 logs 目錄
# 注意：不要在此創建 chroma_db 目錄，讓 init_database.sh 負責還原它
RUN mkdir -p /app/.chainlit \
    && mkdir -p /app/logs \
    && chmod -R 777 /app/.chainlit \
    && chmod -R 777 /app/logs

# 使用 root 用戶運行（解決權限問題）
# 或者設置正確的用戶權限
# RUN useradd --create-home --shell /bin/bash app \
#     && chown -R app:app /app
# USER app

# 暴露端口
EXPOSE 7861

# 設置環境變數
ENV REPORT_API_BASE=http://fin-backend:6677
ENV PYTHONPATH=/app
ENV CHAINLIT_AUTH_DISABLED=true

# 使用初始化腳本作為入口點
ENTRYPOINT ["/bin/bash", "/app/scripts/init_database.sh"]