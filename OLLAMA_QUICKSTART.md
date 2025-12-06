# 🦙 Ollama 快速啟動指南

5 分鐘內開始使用 Ollama 運行 UI Compliance 應用。

---

## ⚡ 超快速開始（3 步）

### 1️⃣ 啟動 Ollama 服務
```bash
ollama serve
```
在終端中保持運行，不要關閉。

### 2️⃣ 運行啟動腳本（在新終端）
```bash
cd /Users/vincenthsia/uicompliance
chmod +x start_with_ollama.sh
./start_with_ollama.sh
```

### 3️⃣ 打開瀏覽器
```
訪問: http://localhost:8000
```

✅ **完成！** 開始使用應用。

---

## 📦 前置要求

### 系統需求

```
✅ 最小配置
  • macOS / Linux / Windows
  • 4GB RAM (推薦 8GB+)
  • 5GB 磁碟空間
  
✅ 推薦配置
  • 16GB+ RAM
  • GPU (可選但更快)
  • 20GB+ 磁碟空間
```

### 已安裝軟體

- ✅ Python 3.10+
- ✅ 虛擬環境 (.venv)
- ❓ Ollama (如未安裝，見下文)

---

## 🔧 安裝 Ollama

### macOS

```bash
# 使用 Homebrew（推薦）
brew install ollama

# 或訪問官網下載
# https://ollama.ai
```

### Linux

```bash
# 一行安裝
curl -fsSL https://ollama.ai/install.sh | sh

# 或訪問官網下載
# https://ollama.ai
```

### Windows

1. 訪問 https://ollama.ai
2. 下載 Windows 版本
3. 執行安裝程式

### 驗證安裝

```bash
ollama --version
# 應輸出: ollama version X.X.X
```

---

## 🚀 方法 A：自動化啟動（推薦）

最簡單的方式，一個命令完成所有操作。

### 第 1 步：打開兩個終端

**終端 1** - 保持 Ollama 運行：
```bash
ollama serve
```

**終端 2** - 啟動應用：
```bash
cd /Users/vincenthsia/uicompliance
chmod +x start_with_ollama.sh
./start_with_ollama.sh
```

### 自動化腳本會：
```
✅ 檢查 Ollama 是否已安裝
✅ 檢查虛擬環境
✅ 啟動 Ollama 服務（如需要）
✅ 下載模型（首次）
✅ 設定環境變數
✅ 啟動 Chainlit 應用
```

### 等待看到

```
╔════════════════════════════════════════════════════════════╗
║         UI Compliance - Ollama Deployment Script           ║
╚════════════════════════════════════════════════════════════╝

[1/5] 檢查 Ollama 是否已安裝...
✅ Ollama 已安裝

[2/5] 檢查 Python 虛擬環境...
✅ 虛擬環境存在

[3/5] 啟動 Ollama 服務...
✅ Ollama 服務已連接

[4/5] 檢查模型 'mistral'...
✅ 模型已下載

[5/5] 啟動應用...

✅ 啟動應用...
   訪問地址: http://localhost:8000

🚀 啟動應用...
```

### 訪問應用

打開瀏覽器：
```
http://localhost:8000
```

---

## 🔧 方法 B：手動啟動

適合想要更多控制的用戶。

### 第 1 步：啟動 Ollama（終端 1）

```bash
ollama serve
```

應該看到：
```
2025-12-06 12:34:56 listening on 127.0.0.1:11434
```

### 第 2 步：下載模型（終端 2）

```bash
# 首次需要下載模型
ollama pull mistral

# 或其他選擇
ollama pull llama3.2:1b      # 超輕量
ollama pull llama2            # 通用
ollama pull neural-chat      # 對話優化
```

等待下載完成（取決於網路和模型大小）：
```
pulling manifest
pulling c0d504adf6e2
pulling 73550f05dff4
pulling 2c7de0dfe0f9
pulling 8e9477e87a40
pulling f3c4ddf77dbf
pulling 7c4f5b0e8a90
verifying sha256 digest
writing manifest
success
```

### 第 3 步：啟動應用（終端 2）

```bash
# 進入項目目錄
cd /Users/vincenthsia/uicompliance

# 激活虛擬環境
source .venv/bin/activate

# 設定 Ollama 環境變數
export USE_OLLAMA=true
export OLLAMA_MODEL=mistral
export OLLAMA_BASE_URL=http://localhost:11434

# 啟動應用
chainlit run app.py
```

### 第 4 步：訪問應用

打開瀏覽器：
```
http://localhost:8000
```

---

## 📋 快速命令參考

### 檢查 Ollama

```bash
# 查看服務是否運行
curl http://localhost:11434/api/tags

# 列出已下載的模型
ollama list

# 查看模型詳情
ollama show mistral
```

### 管理模型

```bash
# 下載新模型
ollama pull llama2

# 刪除模型
ollama rm mistral

# 更新模型
ollama pull mistral  # 自動獲取最新版本
```

### 管理服務

```bash
# 啟動服務
ollama serve

# 停止服務（在運行的終端按 Ctrl+C）
# 或
killall ollama

# 後台運行
tmux new-session -d -s ollama "ollama serve"
tmux attach -t ollama  # 連接
tmux kill-session -t ollama  # 終止
```

---

## 🎯 模型選擇

### 首次推薦

```
🟢 mistral (4.1GB)
   • 速度：⚡⚡⚡ 快
   • 質量：⭐⭐⭐ 中
   • 推薦：最平衡的選擇
   
   ollama pull mistral
```

### 其他選擇

```
🔵 llama3.2:1b (1.3GB)
   • 速度：⚡⚡⚡ 最快
   • 質量：⭐⭐ 基礎
   • 推薦：超輕量，快速演示
   
   ollama pull llama3.2:1b

🟡 llama2 (3.8GB)
   • 速度：⚡⚡⚡ 快
   • 質量：⭐⭐⭐ 中
   • 推薦：通用任務
   
   ollama pull llama2

🟠 neural-chat (4.1GB)
   • 速度：⚡⚡ 中
   • 質量：⭐⭐⭐⭐ 良好
   • 推薦：對話優化
   
   ollama pull neural-chat

🔴 dolphin-mixtral (26GB)
   • 速度：⚡ 較慢
   • 質量：⭐⭐⭐⭐⭐ 最優
   • 推薦：需要高質量（需要 GPU）
   
   ollama pull dolphin-mixtral
```

---

## 🔄 切換模型

### 方法 1：環境變數

```bash
# 設定不同的模型
export OLLAMA_MODEL=llama2

# 重啟應用
chainlit run app.py
```

### 方法 2：編輯 .env 文件

```bash
# 編輯 .env
cat > .env << 'EOF'
USE_OLLAMA=true
OLLAMA_MODEL=llama2
OLLAMA_BASE_URL=http://localhost:11434
EOF

# 啟動應用
chainlit run app.py
```

---

## ✅ 驗證設置

### 檢查 1：Ollama 服務

```bash
# 應返回已加載的模型列表
curl http://localhost:11434/api/tags

# 預期輸出：
# {"models":[{"name":"mistral:latest",...}]}
```

### 檢查 2：模型列表

```bash
ollama list

# 預期輸出：
# NAME              ID              SIZE    MODIFIED
# mistral:latest    2b79e5d5f5f5    4.1GB   1 min ago
```

### 檢查 3：應用日誌

啟動應用後，應看到：
```
[LLM Config] 🦙 使用 Ollama
   模型: mistral
   服務地址: http://localhost:11434
```

### 檢查 4：運行測試

```bash
python test_agent_ollama.py

# 應該通過所有測試並顯示：
# ✅ Ollama 服務已連接
# ✅ 所有 Agent 已準備就緒
```

---

## 🐛 常見問題

### Q1：Ollama 連接失敗

```bash
# 檢查服務
curl http://localhost:11434/api/tags

# 如果失敗，啟動服務
ollama serve

# 在另一個終端檢查
curl http://localhost:11434/api/tags
```

### Q2：模型下載太慢

```bash
# 檢查網路連接
ping ollama.ai

# 嘗試較小的模型
ollama pull llama3.2:1b

# 或手動指定鏡像（中國用戶）
export OLLAMA_MODELS=~/.ollama/models
ollama pull mistral
```

### Q3：應用啟動很慢

```bash
# 首次加載模型較慢，請耐心等候
# 可以在另一個終端檢查：
ollama list

# 如果顯示模型，說明下載完成
# 等待應用完全加載

# 或使用更輕量的模型
export OLLAMA_MODEL=llama3.2:1b
```

### Q4：記憶體不足

```bash
# 使用輕量模型
ollama pull llama3.2:1b
export OLLAMA_MODEL=llama3.2:1b

# 限制 CPU 執行緒
export OLLAMA_NUM_THREAD=2
ollama serve
```

### Q5：應用無法連接 Ollama

```bash
# 檢查基礎 URL
echo $OLLAMA_BASE_URL
# 應顯示：http://localhost:11434

# 驗證 Ollama 運行
ollama list

# 重新啟動 Ollama
killall ollama
ollama serve
```

---

## 🎓 首次使用提示

### 新手步驟

1. **安裝 Ollama**
   ```bash
   brew install ollama  # macOS
   ```

2. **啟動服務**
   ```bash
   ollama serve
   ```

3. **下載模型**
   ```bash
   ollama pull mistral
   ```

4. **啟動應用**
   ```bash
   ./start_with_ollama.sh
   ```

5. **訪問應用**
   ```
   http://localhost:8000
   ```

### 第一個查詢

在應用中試試：
- 輸入一個簡單問題
- 觀察 Ollama 的回應
- 檢查終端日誌

---

## 📊 效能期望

在 MacBook Pro M1 16GB 上的實際響應時間：

| 任務 | 時間 |
|------|------|
| 簡單回應 | 2-3 秒 |
| 案例搜索 | 3-5 秒 |
| 深度分析 | 5-10 秒 |
| 首次模型加載 | 10-30 秒 |

**注意**：首次運行時，模型會被加載到記憶體，可能需要 10-30 秒。後續調用會快得多。

---

## 🔌 配置 Ollama 遠端服務（進階）

### 在遠端伺服器運行 Ollama

```bash
# 遠端伺服器
ollama serve --bind 0.0.0.0:11434
```

### 本地應用連接遠端

```bash
# 本地應用
export OLLAMA_BASE_URL=http://192.168.1.100:11434
export USE_OLLAMA=true

chainlit run app.py
```

---

## 🚀 下一步

### ✅ 基本操作完成後

1. **測試功能**
   - 搜索案例
   - 執行分析
   - 查詢法條

2. **調整配置**
   - 選擇更合適的模型
   - 優化效能
   - 設定超時

3. **了解更多**
   - 閱讀 [完整對比指南](./OLLAMA_VS_OPENAI_GUIDE.md)
   - 查看 [Agent 支援文檔](./AGENT_OLLAMA_SUPPORT.md)
   - 研究 [部署指南](./OLLAMA_DEPLOYMENT.md)

### 📚 相關文件

| 文件 | 說明 |
|------|------|
| `OLLAMA_VS_OPENAI_GUIDE.md` | 詳細對比（何時用 Ollama/OpenAI） |
| `OLLAMA_VS_OPENAI_QUICK_REFERENCE.md` | 快速參考卡 |
| `AGENT_OLLAMA_SUPPORT.md` | Agent 系統集成 |
| `config_loader.sh` | 環境變數管理工具 |
| `test_agent_ollama.py` | 配置測試腳本 |

---

## 💾 文件位置參考

```
/Users/vincenthsia/uicompliance/
├── start_with_ollama.sh          # 🚀 自動化啟動腳本
├── config_loader.sh              # ⚙️ 環境配置管理
├── test_agent_ollama.py          # 🧪 測試工具
├── .env.ollama.example           # 📋 環境變數範本
├── app.py                        # 🔧 主應用（已支援 Ollama）
├── OLLAMA_QUICKSTART.md          # ⚡ 本文件
├── OLLAMA_VS_OPENAI_GUIDE.md    # 📖 詳細對比
└── AGENT_OLLAMA_SUPPORT.md      # 🏗️ 架構文檔
```

---

## ⏱️ 預估時間

```
首次設置：
  ├─ 安裝 Ollama：5 分鐘
  ├─ 下載模型：10-20 分鐘（取決於網路）
  ├─ 啟動應用：2 分鐘
  └─ 總計：20-30 分鐘

後續啟動：
  ├─ 啟動 Ollama：30 秒
  ├─ 啟動應用：2 分鐘
  └─ 總計：2.5 分鐘
```

---

## 💡 最佳實踐

### ✅ DO（應該做）

```
✅ 在開發時使用 Ollama
✅ 保持 Ollama 服務運行
✅ 為不同任務嘗試不同模型
✅ 定期檢查 Ollama 日誌
✅ 使用環境變數管理配置
```

### ❌ DON'T（不應該做）

```
❌ 不要關閉 Ollama 服務而啟動應用
❌ 不要在同一終端中同時運行兩個應用
❌ 不要忽視模型下載進度
❌ 不要修改 Ollama 基礎 URL（除非遠端）
```

---

## 🆘 获得帮助

### 快速診斷

```bash
# 運行完整檢查
python test_agent_ollama.py

# 查看應用日誌
chainlit run app.py 2>&1 | grep -i "ollama\|error"

# 檢查 Ollama 連接
curl http://localhost:11434/api/tags
```

### 查閱文檔

- 📖 [詳細對比指南](./OLLAMA_VS_OPENAI_GUIDE.md)
- ⚡ [快速參考](./OLLAMA_VS_OPENAI_QUICK_REFERENCE.md)
- 🦙 [Agent 支援](./AGENT_OLLAMA_SUPPORT.md)

---

## 記住這些

```
🦙 Ollama = 免費 + 本地 + 快速設置
🔑 OpenAI = 最高質量 + 企業級 + 需要 API Key

開始學習？用 Ollama！
進入生產？考慮 OpenAI！
```

---

## 快速命令速查

```bash
# 最常用命令
ollama serve                    # 啟動服務
ollama pull mistral            # 下載模型
ollama list                    # 查看模型
./start_with_ollama.sh        # 自動啟動應用
chainlit run app.py           # 手動啟動應用
python test_agent_ollama.py   # 測試配置
```

---

**祝您使用愉快！🎉**

有任何問題，請查閱相關文檔或執行 `python test_agent_ollama.py`。

最後更新：2025-12-06
