# 使用 Python 3.13 slim 鏡像
FROM python:3.13-slim

# 設置工作目錄
WORKDIR /app

# 安裝系統依賴
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 安裝 uv 包管理器
RUN pip install uv

# 複製依賴文件
COPY pyproject.toml uv.lock ./

# 使用 uv 安裝依賴
RUN uv sync --frozen --no-install-project

# 複製應用代碼
COPY . .

# 創建非 root 用戶
RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app
USER app

# 暴露端口
EXPOSE 7861

# 設置環境變數
ENV REPORT_API_BASE=http://fin-backend:6677
ENV PYTHONPATH=/app

# 啟動命令
CMD ["uv", "run", "chainlit", "run", "app.py", "--host", "0.0.0.0", "--port", "7861"]