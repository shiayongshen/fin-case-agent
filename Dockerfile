# 使用 NVIDIA CUDA 基礎映像（支援 GPU 加速）
FROM nvidia/cuda:12.1.0-cudnn8-runtime-ubuntu22.04

WORKDIR /app

# 設置非交互式安裝
ENV DEBIAN_FRONTEND=noninteractive

# 安裝 Python 3.11 和系統依賴（Ubuntu 22.04 原生支援 3.11）
RUN apt-get update && apt-get install -y \
    python3.11 \
    python3.11-venv \
    python3.11-dev \
    python3-pip \
    build-essential \
    tar \
    gzip \
    bash \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf /usr/bin/python3.11 /usr/bin/python3 \
    && ln -sf /usr/bin/python3.11 /usr/bin/python

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
# CUDA 相關環境變數
ENV NVIDIA_VISIBLE_DEVICES=all
ENV NVIDIA_DRIVER_CAPABILITIES=compute,utility

# 使用初始化腳本作為入口點
ENTRYPOINT ["/bin/bash", "/app/scripts/init_database.sh"]