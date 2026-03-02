# 🧮 SMT Generation 模塊

自動將法律案例轉換為 SMT-LIB 求解器格式的綜合系統。

---

## 🎯 概述

**目標**：將法律案例自動轉換為形式化的 SMT 約束系統

**流程**：法條解析 → 約束生成 → 事實映射 → Z3 求解 → SMT2 導出

**主要特性**：
- ✅ 自動法條解析和補完
- ✅ 約束驗證和自動修復
- ✅ Z3 約束求解
- ✅ 成本跟蹤和統計
- ✅ 詳細的檢查點記錄
- ✅ SMT2 格式導出

---

## 🏗️ 架構

```
smt_generation/
├── main.py                  # 主流程協調器
├── config.py                # 配置管理
├── utils.py                 # 工具函數
├── agents/                  # Agent 系統
│   ├── orchestrator.py      # Agent 建立
│   ├── statute_parser.py    # 法條解析 Agent
│   ├── varspec_agent.py     # 變數規格 Agent
│   ├── case_mapper.py       # 案例映射 Agent
│   └── prompt.py            # 提示詞模板
├── core/                    # 核心模塊
│   ├── repair_pipeline.py   # 修復流程
│   └── checker.py           # 約束檢查
├── dataset/                 # 數據集
│   └── updated_processed_cases.csv
├── outputs/                 # 輸出結果
│   ├── case_*.constraint_spec.json
│   ├── case_*.varspecs.json
│   ├── case_*.facts.json
│   ├── case_*.stats.json
│   ├── case_*.model.txt
│   ├── case_*.smt2
│   ├── case_*.log
│   └── pipeline_statistics.xlsx
└── README.md                # 本文件
```

---

## 🚀 快速開始

### 前置要求

```bash
# Python 版本
python --version  # 需要 3.10+

# 依賴檢查
pip list | grep -E "autogen|z3|pandas|openpyxl"
```

### 基本執行

```bash
# 1. 設定環境變數
export OPENAI_API_KEY=sk-...
export OPENAI_MODEL=gpt-4o-mini  # 可選，默認 gpt-4o-mini

# 2. 執行主程序
cd /Users/vincenthsia/uicompliance
python smt_generation/main.py
```

### 執行特定案例

```bash
# 在 main.py 最後修改
if __name__ == "__main__":
    # 只執行 case_324, case_429, case_454
    fail_list_path = [324, 429, 454]
    main(failed_indices=fail_list_path)
```

---

## 📊 詳細步驟

### 完整流程圖

```
輸入數據
  ↓
┌─────────────────────────────────────────┐
│ Step 1: Law Parser (法條解析)           │
│ 使用 LLM 解析相關法條                    │
│ 輸出: ConstraintSpec[]                  │
└─────────────────────────────────────────┘
  ↓
┌─────────────────────────────────────────┐
│ Step 2: Law Completion (補完)           │
│ 使用 LLM 補完缺失的約束                  │
│ 輸出: 完整約束列表                       │
└─────────────────────────────────────────┘
  ↓
┌─────────────────────────────────────────┐
│ Step 3: JSON Validation                 │
│ 確保 JSON 格式有效                       │
└─────────────────────────────────────────┘
  ↓
┌─────────────────────────────────────────┐
│ Step 4: VarSpec Extraction              │
│ 使用 LLM 生成變數規格                    │
│ 輸出: varspecs[]                        │
└─────────────────────────────────────────┘
  ↓
┌─────────────────────────────────────────┐
│ Step 5: Constraints Parseable Check     │
│ 驗證約束是否可被 Z3 解析                 │
│ 如失敗: 自動修復 (最多 3 輪)             │
└─────────────────────────────────────────┘
  ↓
┌─────────────────────────────────────────┐
│ Step 6: Consistency Check               │
│ 檢查約束之間的一致性                     │
│ 如失敗: 使用 LLM 修復                    │
└─────────────────────────────────────────┘
  ↓
┌─────────────────────────────────────────┐
│ Step 7: Case Mapper (案例映射)          │
│ 使用 LLM 將案例映射到事實                │
│ 輸出: facts{}                           │
│ 驗證: Z3 檢查                           │
│ 如失敗: 自動修復                        │
└─────────────────────────────────────────┘
  ↓
┌─────────────────────────────────────────┐
│ Step 8: Case+Law Hard Check             │
│ Z3 檢查案例是否違反約束 (UNSAT)         │
│ 如失敗: 嘗試修復或調整事實               │
└─────────────────────────────────────────┘
  ↓
┌─────────────────────────────────────────┐
│ Step 9: Z3 Optimize                     │
│ 求解優化問題                            │
│ 生成模型                                 │
└─────────────────────────────────────────┘
  ↓
┌─────────────────────────────────────────┐
│ Step 10: SMT2 Export                    │
│ 導出為 SMT-LIB 2.6 格式                 │
└─────────────────────────────────────────┘
  ↓
輸出結果
  ├── JSON 規格文件
  ├── 統計信息
  ├── SMT2 文件
  └── 日誌
```

---

## 📁 文件說明

### 核心文件

#### `main.py` - 主程序

**功能**：
- 協調整個 pipeline
- 管理 PipelineStats 統計
- 生成輸出文件和 Excel 報告

**主要類**：
```python
class PipelineStats:
    """記錄每個案例的執行統計"""
    - checkpoints: dict          # 檢查點狀態
    - agent_calls: list          # Agent 呼叫記錄
    - repair_attempts: int       # 修復次數
    - success: bool              # 是否成功
```

**關鍵函數**：
```python
def run_pipeline(team, case_id, case_text, statute_text)
    # 執行完整流程

def main(failed_indices=None)
    # 處理所有或特定案例
```

**輸出**：
- 4 個 JSON 文件（per case）
- 統計 Excel 文件
- 詳細日誌

---

#### `config.py` - 配置

**配置項**：
```python
OPENAI_API_KEY          # API 金鑰
OPENAI_MODEL            # 模型名稱（默認: gpt-4o-mini）
llm_config              # LLM 配置字典
```

**驗證**：
- 檢查 API Key 是否存在
- 提供默認模型
- 清晰的錯誤提示

---

#### `utils.py` - 工具函數

**主要函數**：

```python
# Token 計算
count_tokens(text, model="gpt-4")
get_reply_with_tokens(agent, messages)

# JSON 處理
ensure_json_valid(team, json_str)
clean_json_response(response)
safe_json_loads(text)

# 約束檢查
check_constraints_parseable(constraints, z3_vars, build_expr)
check_constraints_consistency(constraints, z3_vars, build_expr)
consistency_check_with_repair(team, constraints, z3_vars, ...)

# 修復
auto_fix_constraints(constraints, varspecs)
repair_sat_to_unsat(team, constraints, facts, ...)
repair_case_law_constraints(team, constraints, facts, ...)

# Z3 操作
z3_optimize_case(constraints, facts, z3_vars, build_expr)
export_to_smt2(case_id, constraints, varspecs, ...)

# 成本計算
calculate_cost(input_tokens, output_tokens)
```

---

#### `agents/orchestrator.py` - Agent 管理

**功能**：建立和管理所有 Agent

```python
def build_team(llm_config):
    return {
        "parser": make_statute_parser(llm_config),
        "varspec": make_varspec_agent(llm_config),
        "mapper": make_case_mapper_agent(llm_config),
    }
```

**Agent 類型**：
- **StatuteParser**: 解析法條
- **VarSpecAgent**: 提取變數規格
- **CaseMapperAgent**: 映射案例到事實

---

### 輔助文件

#### `agents/statute_parser.py`
- 法條解析 Agent 的提示詞和邏輯

#### `agents/varspec_agent.py`
- 變數規格生成的提示詞

#### `agents/case_mapper.py`
- 案例映射的提示詞和邏輯

#### `core/repair_pipeline.py`
- 約束修復的核心邏輯

#### `core/checker.py`
- Z3 約束檢查器

---

## ⚙️ 配置

### 環境變數

```bash
# 必需
OPENAI_API_KEY=sk-...                    # OpenAI API 金鑰

# 可選
OPENAI_MODEL=gpt-4o-mini                 # 模型名稱
USE_OLLAMA=false                         # 使用 Ollama
OLLAMA_BASE_URL=http://localhost:11434   # Ollama 地址
```

### 設定方式

**方法 1：.env 檔案**
```bash
cat > .env << 'EOF'
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
EOF
```

**方法 2：環境變數**
```bash
export OPENAI_API_KEY=sk-...
export OPENAI_MODEL=gpt-4o-mini
python smt_generation/main.py
```

**方法 3：修改 config.py**
```python
llm_config = {
    "config_list": [
        {
            "model": "gpt-4o-mini",
            "api_key": "sk-...",
        }
    ],
    "temperature": 0,
    "seed": 42,
}
```

---

## 📤 輸出結果

### 生成的文件

每個案例生成 4 個文件（`case_{id}.*`）：

#### 1. `constraint_spec.json` - 約束規格
```json
[
  {
    "id": "constraint_1",
    "description": "資本適足率不能低於...",
    "expression": "capital_ratio >= 0.08",
    "type": "inequality",
    "variables": ["capital_ratio"]
  },
  ...
]
```

#### 2. `varspecs.json` - 變數規格
```json
[
  {
    "name": "capital_ratio",
    "type": "Real",
    "domain": "(0, 1)",
    "description": "資本適足率"
  },
  ...
]
```

#### 3. `facts.json` - 案例事實
```json
{
  "capital_ratio": 0.05,
  "violation_count": 2,
  "stop_profit_distribution": false,
  ...
}
```

#### 4. `stats.json` - 執行統計
```json
{
  "case_id": "case_324",
  "success": true,
  "total_time_sec": 45.3,
  "repair_attempts": 1,
  "total_agent_calls": 5,
  "total_input_tokens": 2543,
  "total_output_tokens": 1234,
  "total_cost_usd": 0.024567,
  "step1_law_parser": "PASS",
  "step2_completion": "PASS",
  ...
}
```

### 附加文件

#### `model.txt` - Z3 模型
```
capital_ratio = 0.05
violation_count = 2
stop_profit_distribution = false
...
```

#### `case_{id}.smt2` - SMT2 格式
```smt2
(set-logic QF_LRA)
(declare-fun capital_ratio () Real)
(declare-fun violation_count () Int)
...
(assert (>= capital_ratio 0.08))
(assert (<= violation_count 5))
...
(check-sat)
(get-model)
```

#### `case_{id}.log` - 詳細日誌
完整的執行日誌，包含所有步驟的输出

### 統計報告

#### `pipeline_statistics.xlsx` - Excel 報告

**Sheet 1: Summary**
- 每個案例的詳細統計
- 檢查點狀態
- 錯誤信息

**Sheet 2: Overall**
- 總體統計
- 成功率
- 平均耗時
- 總成本

**Sheet 3: Checkpoints**
- 每個檢查點的通過率
- 失敗統計

---

## 🐛 常見問題

### Q1: API 金鑰錯誤
```
ValidationError: API key is not valid
```

**解決**：
```bash
echo $OPENAI_API_KEY  # 確認 API key 存在
export OPENAI_API_KEY=sk-...
```

### Q2: 模型不存在
```
model_not_found_error
```

**解決**：
```bash
# 檢查可用模型
export OPENAI_MODEL=gpt-4o-mini  # 使用更新的模型
# 或查看帳戶的可用模型
```

### Q3: 超時錯誤
```
TimeoutError: API request timed out
```

**解決**：
- 增加超時時間（config.py）
- 使用更小的批次
- 檢查網路連接

### Q4: Z3 解析失敗
```
Z3 exception: invalid expression
```

**解決**：
- 檢查約束語法
- 運行自動修復
- 查看日誌中的詳細錯誤

### Q5: 記憶體不足
```
MemoryError: Unable to allocate ...
```

**解決**：
- 減少批次大小
- 關閉其他應用
- 使用 32GB+ RAM 的機器

---

## 📈 效能參考

### 單個案例耗時

| 步驟 | 耗時 | 說明 |
|------|------|------|
| Step 1-2 | 20-60 秒 | LLM 解析和補完 |
| Step 3-4 | 10-30 秒 | JSON 和變數提取 |
| Step 5-6 | 30-300 秒 | 約束檢查和修復 |
| Step 7 | 20-60 秒 | 案例映射 |
| Step 8 | 30-120 秒 | Z3 檢查 |
| Step 9-10 | 10-60 秒 | 優化和導出 |
| **總計** | **2-10 分鐘** | 平均 5 分鐘 |

### 成本估計

| 模型 | 輸入價格 | 輸出價格 | 平均成本/案例 |
|------|---------|---------|-------------|
| gpt-4o-mini | $0.15/1M | $0.6/1M | $0.01-0.05 |
| gpt-4o | $2.5/1M | $10/1M | $0.05-0.20 |
| gpt-4-turbo | $10/1M | $30/1M | $0.10-0.40 |

**估計**：
- 100 個案例 × $0.03 = $3
- 500 個案例 × $0.03 = $15

---

## 💡 最佳實踐

### ✅ DO（應該做）

```
✅ 使用 gpt-4o-mini 進行開發測試
✅ 批量處理前先測試單個案例
✅ 定期檢查 Excel 統計報告
✅ 監控 API 使用量和成本
✅ 備份輸出結果
✅ 查看詳細日誌用於調試
✅ 使用檢查點狀態了解進度
```

### ❌ DON'T（不應該做）

```
❌ 不要同時執行多個 main.py
❌ 不要修改已生成的 JSON 文件
❌ 不要忽視錯誤信息
❌ 不要在沒有備份的情況下運行
❌ 不要使用過期的 API key
❌ 不要刪除 outputs 目錄
❌ 不要修改核心 Agent 提示詞
```

---

## 📚 相關文檔

- [主 README](../README.md)
- [資料前處理指南](../data_preprocess/Preprocessing_Guildline.md)
- [Ollama 快速啟動](../OLLAMA_QUICKSTART.md)
- [OpenAI vs Ollama 對比](../OLLAMA_VS_OPENAI_GUIDE.md)

---

## 🔧 進階配置

### 自訂 Agent 提示詞

編輯 `agents/` 中的相應文件：

```python
# agents/statute_parser.py
PARSER_SYS_PROMPT = """
你是法律專家...
"""

# agents/varspec_agent.py
VARSPEC_SYS_PROMPT = """
你是變數規格設計師...
"""
```

### 自訂修復策略

編輯 `utils.py` 中的修復函數：

```python
def auto_fix_constraints(constraints, varspecs):
    # 自訂修復邏輯
    ...
```

### 自訂檢查策略

編輯 `core/checker.py`：

```python
def check_constraints_parseable(constraints, z3_vars, build_expr):
    # 自訂檢查邏輯
    ...
```

---

## 🚀 性能優化

### 1. 並行處理（未來功能）

```python
from concurrent.futures import ThreadPoolExecutor

with ThreadPoolExecutor(max_workers=4) as executor:
    futures = [executor.submit(run_pipeline, ...) for case in cases]
    results = [f.result() for f in futures]
```

### 2. 快取搜索結果

```python
# 在 utils.py 中添加快取
from functools import lru_cache

@lru_cache(maxsize=1000)
def get_constraint_suggestion(constraint_text):
    ...
```

### 3. 使用更快的模型

```bash
export OPENAI_MODEL=gpt-4o-mini  # 更快
# 而不是
export OPENAI_MODEL=gpt-4         # 更慢但更準確
```

---

## 📞 支援

### 調試步驟

1. **檢查日誌**
   ```bash
   tail -f smt_generation/outputs/case_*.log
   ```

2. **運行單個案例**
   ```python
   main(failed_indices=[324])
   ```

3. **查看統計**
   ```bash
   open smt_generation/outputs/pipeline_statistics.xlsx
   ```

4. **檢查 SMT2 文件**
   ```bash
   z3 smt_generation/outputs/case_324.smt2
   ```

