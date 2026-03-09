import os
import importlib
import contextlib
import sys
from typing import Dict, Optional
from dotenv import load_dotenv

load_dotenv()

def _maybe_patch_openai_with_langfuse() -> bool:
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY")
    if not (public_key and secret_key):
        return False

    if os.getenv("LANGFUSE_BASE_URL") and not os.getenv("LANGFUSE_HOST"):
        os.environ["LANGFUSE_HOST"] = os.getenv("LANGFUSE_BASE_URL", "")

    try:
        lf_openai = importlib.import_module("langfuse.openai")
        if hasattr(lf_openai, "openai"):
            sys.modules["openai"] = lf_openai.openai
            print("[Langfuse] OpenAI SDK patched for tracing.")
            return True
        print("[Langfuse] openai wrapper not found in langfuse.openai.")
    except Exception as exc:
        print(f"[Langfuse] Failed to patch OpenAI SDK: {exc}")
    return False

LANGFUSE_PATCHED = _maybe_patch_openai_with_langfuse()
_LANGFUSE_CLIENT = None

import chainlit as cl
from chainlit.input_widget import TextInput, Select, InputWidget
from openai import AsyncOpenAI
from autogen import AssistantAgent
from chainlit.data.sql_alchemy import SQLAlchemyDataLayer
from chainlit.data.storage_clients.base import BaseStorageClient
from agents import ChatManager, BaseUserProxy, HostAgent, SearchCaseAgent, DeepAnalysisAgent, SummaryAgent, SearchLawAgent, CustomizeConstraintAgent
from utility.legal_search import legal_article_search,search_and_rerank
from utility.execute_file import list_available_code_files, execute_python_file
from utility.api_key_manager import get_global_api_key, set_global_api_key
import httpx
from datetime import datetime
import asyncio
import uuid

def _lf_safe_str(value: Optional[str], max_len: int = 200) -> Optional[str]:
    if value is None:
        return None
    s = str(value)
    s = s.encode("ascii", "ignore").decode("ascii")
    if len(s) > max_len:
        s = s[:max_len]
    return s or None

def _get_langfuse_client():
    global _LANGFUSE_CLIENT
    if _LANGFUSE_CLIENT is None:
        from langfuse import Langfuse
        _LANGFUSE_CLIENT = Langfuse()
    return _LANGFUSE_CLIENT

def _langfuse_trace_context(
    *,
    user_id: Optional[str],
    session_id: Optional[str],
    tags: Optional[list[str]] = None,
    metadata: Optional[dict[str, str]] = None,
    trace_name: Optional[str] = None,
):
    if not LANGFUSE_PATCHED:
        return contextlib.nullcontext()

    try:
        lf = _get_langfuse_client()
        safe_metadata = {}
        for k, v in (metadata or {}).items():
            k_s = _lf_safe_str(k)
            v_s = _lf_safe_str(v)
            if k_s and v_s:
                safe_metadata[k_s] = v_s

        return lf.propagate_attributes(
            user_id=_lf_safe_str(user_id),
            session_id=_lf_safe_str(session_id),
            tags=[t for t in [_lf_safe_str(x) for x in (tags or [])] if t],
            metadata=safe_metadata,
            trace_name=_lf_safe_str(trace_name),
        )
    except Exception as exc:
        print(f"[Langfuse] Failed to set trace metadata: {exc}")
        return contextlib.nullcontext()

# ===== 預設配置 =====
# 優先順序：環境變數 > 全局配置文件 > 預設值
DEFAULT_API_KEY = os.getenv("OPENAI_API_KEY") or get_global_api_key() or ""
DEFAULT_MODEL = "gpt-4.1-mini"

# 支援的模型列表
AVAILABLE_MODELS = [
    "gpt-4.1-mini",
    "gpt-4.1",
    "gpt-4o",
    "gpt-4o-mini", 
    "gpt-4-turbo",
    "gpt-4",
    "gpt-3.5-turbo",
    "o1-preview",
    "o1-mini",
]

# 初始化全域客戶端（會在設定更新時重新建立）
client = AsyncOpenAI(api_key=DEFAULT_API_KEY) if DEFAULT_API_KEY else None

def get_llm_config(api_key: Optional[str] = None, model: Optional[str] = None) -> dict:
    """
    取得 LLM 配置
    支持 OpenAI 和 Ollama
    
    Args:
        api_key: OpenAI API Key 或 Ollama 標記
        model: 模型名稱
    
    Returns:
        llm_config 字典
    """
    import os
    
    # 檢查是否使用 Ollama
    use_ollama = os.getenv("USE_OLLAMA", "false").lower() == "true"
    
    if use_ollama:
        # Ollama 配置
        ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        ollama_model = os.getenv("OLLAMA_MODEL", "mistral")
        
        # ⭐ 關鍵：Ollama 的 API 相容 OpenAI，但需要在基礎 URL 中添加 /v1
        # Ollama 實際端點：http://localhost:11434/v1/chat/completions
        # AutoGen 會自動添加 /chat/completions，所以基礎 URL 需要包含 /v1
        if not ollama_base_url.endswith("/v1"):
            ollama_base_url = f"{ollama_base_url.rstrip('/')}/v1"
        
        print(f"[LLM Config] 🦙 使用 Ollama")
        print(f"   模型: {ollama_model}")
        print(f"   服務地址: {ollama_base_url}")
        
        return {
            "config_list": [{
                "model": ollama_model,
                "api_key": "ollama",  # Ollama 不需要真實的 API key
                "base_url": ollama_base_url,
                "api_type": "openai",  # Ollama 相容 OpenAI API
            }],
            "temperature": 0.7,
            "timeout": 120,
            "max_tokens": 2048,
        }
    else:
        # OpenAI 配置（原有邏輯）
        # 優先順序：參數 > session > 環境變數/預設值
        final_api_key = api_key
        final_model = model
        
        if not final_api_key:
            try:
                final_api_key = cl.user_session.get("openai_api_key") or DEFAULT_API_KEY
            except:
                final_api_key = DEFAULT_API_KEY
        
        if not final_model:
            try:
                final_model = cl.user_session.get("openai_model") or DEFAULT_MODEL
            except:
                final_model = DEFAULT_MODEL
        
        print(f"[LLM Config] 🔑 使用 OpenAI")
        print(f"   模型: {final_model}")
        
        return {
            "config_list": [{
                "model": final_model,
                "api_key": final_api_key
            }]
        }

# 初始 llm_config（會在 on_chat_start 時根據使用者設定更新）
llm_config = get_llm_config()

# ===== 深入分析工具函數 =====
def Z3CodeExecution(case_id: str) -> Dict:
    """
    執行案例 Z3 求解的工具函數
    
    Args:
        case_id: 案例 ID，如 'case_0'
    
    Returns:
        包含求解結果的字典，包含 status, case_id, initial_facts, suggested_model 等
    """
    try:
        deep_analysis_agent = cl.user_session.get("deep_analysis_agent")
        if not deep_analysis_agent:
            return {
                'status': 'error',
                'case_id': case_id,
                'error_message': '深入分析 Agent 未初始化'
            }
        
        # 只執行 Z3 求解，不生成報告
        result = deep_analysis_agent.perform_deep_analysis_core(case_id)
        
        # 如果求解成功，保存結果到 session，供 constraint_customization_agent 使用
        if result.get('status') == 'success':
            initial_facts = result.get('initial_facts', {})
            suggested_model = result.get('suggested_model', {})
            
            # 生成結構化分析數據（變數變化列表）
            analysis_data = deep_analysis_agent._generate_structured_analysis_data(
                case_id, initial_facts, suggested_model
            )
            
            # 保存到 session（包括結構化數據和原始 Z3 結果）
            cl.user_session.set("latest_deep_analysis_result", analysis_data)
            # ⭐ 新增：同時存儲原始的 Z3 求解結果
            cl.user_session.set("latest_z3_solving_result", result)
            print(f"[DeepAnalysisTool] 已保存分析結果到 session，案例: {case_id}")
            print(f"[DeepAnalysisTool] ✅ 已同時保存原始 Z3 求解結果（initial_facts 和 suggested_model）")
        
        return result
    
    except Exception as e:
        return {
            'status': 'error',
            'case_id': case_id,
            'error_message': f'Z3 求解執行出錯: {str(e)}'
        }


# ===== 應用自定義約束工具函數 =====
def CustomizeZ3constraintExecution(case_id: Optional[str] = None, constraints: Optional[Dict] = None) -> Dict:
    """
    應用自定義約束並執行 Z3 重新求解的工具函數
    
    Args:
        case_id: 案例 ID，如 'case_0'。如果為 None，會自動從 session 中提取
        constraints: 自定義約束字典，格式如下：
                    {
                        "variable_name": {
                            "type": "FIX|LOWER_BOUND|UPPER_BOUND|RANGE",
                            "value": <值>,           # 用於 FIX
                            "lower_bound": <值>,     # 用於 LOWER_BOUND 或 RANGE
                            "upper_bound": <值>      # 用於 UPPER_BOUND 或 RANGE
                        }
                    }
    
    Returns:
        包含新求解結果的字典
    """
    try:
        from utility.ConstraintCustomizationTool import get_apply_constraints_tool
        
        # 如果 case_id 未提供，從 session 中自動提取
        actual_case_id: Optional[str] = case_id
        if not actual_case_id:
            z3_result = cl.user_session.get("latest_z3_solving_result")
            if z3_result:
                actual_case_id = z3_result.get("case_id")
            if not actual_case_id:
                actual_case_id = cl.user_session.get("current_case_id")
            if not actual_case_id:
                return {
                    'status': 'error',
                    'error_message': '無法找到 case_id，請確保已執行過深入分析'
                }
            print(f"[apply_custom_constraints_tool] ✅ 從 session 自動提取 case_id: {actual_case_id}")
        
        # 如果 constraints 未提供，返回錯誤
        if not constraints:
            return {
                'status': 'error',
                'error_message': '未提供約束條件'
            }
        
        # 獲取工具實例
        tool = get_apply_constraints_tool()
        
        # 設置 case ID
        tool.set_case_id(actual_case_id)
        
        # 添加所有約束
        for var_name, constraint_def in constraints.items():
            constraint_type = constraint_def.get("type")
            
            if constraint_type == "FIX":
                tool.add_fix_constraint(var_name, constraint_def.get("value"))
            
            elif constraint_type == "LOWER_BOUND":
                # 相容多種鍵名格式
                value = constraint_def.get("lower_bound") or constraint_def.get("value")
                tool.add_lower_bound(var_name, value)
            
            elif constraint_type == "UPPER_BOUND":
                # 相容多種鍵名格式
                value = constraint_def.get("upper_bound") or constraint_def.get("value")
                tool.add_upper_bound(var_name, value)
            
            elif constraint_type == "RANGE":
                # 相容多種鍵名格式：min/max、lower_bound/upper_bound
                lower = constraint_def.get("lower_bound") or constraint_def.get("min")
                upper = constraint_def.get("upper_bound") or constraint_def.get("max")
                tool.add_range_constraint(var_name, lower, upper)
        
        # 應用約束並執行求解
        result = tool.apply_constraints_and_resolve()
        
        # 如果求解成功，保存結果到 session
        if result.get("status") == "success":
            solving_result = result.get("solving_result", {})
            if solving_result:
                initial_facts = solving_result.get("initial_facts", {})
                suggested_model = solving_result.get("suggested_model", {})
                
                # 生成結構化分析數據
                deep_analysis_agent = cl.user_session.get("deep_analysis_agent")
                if deep_analysis_agent:
                    analysis_data = deep_analysis_agent._generate_structured_analysis_data(
                        actual_case_id, initial_facts, suggested_model
                    )
                    
                    # 保存到 session（包括結構化數據和原始 Z3 結果）
                    cl.user_session.set("latest_deep_analysis_result", analysis_data)
                    # ⭐ 新增：同時存儲原始的 Z3 求解結果
                    cl.user_session.set("latest_z3_solving_result", solving_result)
                    print(f"[ApplyConstraintsTool] 已保存新的分析結果到 session")
                    print(f"[ApplyConstraintsTool] ✅ 已同時保存原始 Z3 求解結果（initial_facts 和 suggested_model）")
        
        return result
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            'status': 'error',
            'error_message': f'應用自定義約束時出錯: {str(e)}'
        }


# DummyStorageClient 實作所有必須方法
class DummyStorageClient(BaseStorageClient):
    async def upload_file(self, object_key: str, data, mime: str = "", overwrite: bool = True, content_disposition: str | None = None) -> dict:
        return {}
    async def get_read_url(self, object_key: str, expire: int = 3600) -> str:
        return ""
    async def delete_file(self, object_key: str) -> bool:
        return True
    async def close(self) -> None:
        return

@cl.data_layer
def get_data_layer():
    dummy = DummyStorageClient()
    db_path = os.getenv("CHAINLIT_DB_PATH", "./chainlit.db")
    data_layer = SQLAlchemyDataLayer(
        conninfo=f"sqlite+aiosqlite:///{db_path}",
        storage_provider=dummy
    )
    return data_layer

@cl.header_auth_callback
async def header_auth_callback(headers) -> cl.User | None:
    return cl.User(
        identifier="shared_user",
        metadata={"role": "user", "provider": "auto"}
    )

async def stream_completion(prompt: str):
    # 取得當前的 client
    current_client = cl.user_session.get("openai_client") or client
    current_model = cl.user_session.get("openai_model") or DEFAULT_MODEL
    
    if not current_client:
        yield "❌ 請先設定 OpenAI API Key"
        return
        
    stream = await current_client.chat.completions.create(
        model=current_model,
        messages=[{"role": "user", "content": prompt}],
        stream=True,
    )
    async for chunk in stream:
        delta = chunk.choices[0].delta
        if delta and delta.content:
            yield delta.content



async def show_api_key_input_dialog():
    """顯示 API Key 輸入對話框"""
    response = await cl.AskUserMessage(
        content="🔐 **需要設置 OpenAI API Key**\n\n請輸入您的 OpenAI API Key (sk-proj-...):",
        timeout=300
    ).send()
    
    if response:
        try:
            new_api_key = response.get("output", "").strip() if isinstance(response, dict) else str(response).strip()
            
            if new_api_key:
                # 驗證 API Key 格式
                if not new_api_key.startswith("sk-"):
                    await cl.Message(
                        content="⚠️ **警告**：API Key 應以 'sk-' 開頭。仍將嘗試使用此 Key。"
                    ).send()
                
                # 保存 API Key
                set_global_api_key(new_api_key)
                os.environ["OPENAI_API_KEY"] = new_api_key
                
                await cl.Message(
                    content="✅ **API Key 已設置**\n\nAPI Key 已保存到本地配置文件。應用程式已準備就緒。"
                ).send()
                
                # 重新加載全局 API Key 變數
                global DEFAULT_API_KEY
                DEFAULT_API_KEY = new_api_key
                
        except Exception as e:
            await cl.Message(
                content=f"❌ **設置失敗**：{str(e)}"
            ).send()




@cl.on_chat_start
async def start_chat():
    """初始化對話"""
    global client, DEFAULT_API_KEY
    
    # 檢查 API Key - 需要是有效的 OpenAI Key（以 sk- 開頭）
    api_key = DEFAULT_API_KEY
    
    # 驗證 API Key 是否有效（不是預設的佔位符）
    is_valid_api_key = (
        api_key 
        and api_key.startswith("sk-") 
        and len(api_key) > 20
        and "your-api" not in api_key.lower()
        and "placeholder" not in api_key.lower()
    )
    
    # 如果沒有有效的 API Key，先彈出設置對話框
    while not is_valid_api_key:
        await show_api_key_input_dialog()
        
        # 重新讀取 API Key
        api_key = os.getenv("OPENAI_API_KEY") or get_global_api_key()
        DEFAULT_API_KEY = api_key
        
        # 再次驗證
        is_valid_api_key = (
            api_key 
            and api_key.startswith("sk-") 
            and len(api_key) > 20
            and "your-api" not in api_key.lower()
            and "placeholder" not in api_key.lower()
        )
        
        if not is_valid_api_key:
            await cl.Message(
                content="❌ **無效的 API Key**\n\n請確保輸入的是有效的 OpenAI API Key（以 sk- 開頭）。"
            ).send()
    
    # ===== 設定 Chat Settings 介面 =====
    # 只允許選擇模型，API Key 通過設置對話框管理
    settings = await cl.ChatSettings(
        [
            Select(
                id="openai_model",
                label="🤖 OpenAI Model",
                values=AVAILABLE_MODELS,
                initial_value=DEFAULT_MODEL,
                description="選擇要使用的 OpenAI 模型"
            ),
        ]
    ).send()
    
    # 從設定中取得模型
    model = settings.get("openai_model") or DEFAULT_MODEL
    
    # 保存設定到 session
    cl.user_session.set("openai_model", model)
    
    # 建立 OpenAI 客戶端
    openai_client = AsyncOpenAI(api_key=api_key)
    cl.user_session.set("openai_client", openai_client)
    
    # 更新全域 client（用於某些全域函數）
    client = openai_client
    
    # 取得 LLM 配置
    current_llm_config = get_llm_config(api_key, model)
    cl.user_session.set("llm_config", current_llm_config)
    
    print(f"[App] 使用模型: {model}")
    if api_key:
        masked_key = f"{api_key[:8]}...{api_key[-4:]}" if len(api_key) > 12 else "***"
        print(f"[App] API Key: {masked_key}")
    else:
        print("[App] ⚠️ API Key 未設置")
    
    # 創建 Agents（使用當前的 llm_config）
    host = HostAgent(current_llm_config)
    search = SearchCaseAgent(current_llm_config)
    summary = SummaryAgent(current_llm_config)
    deep_analysis = DeepAnalysisAgent(current_llm_config)
    legal_retrieval = SearchLawAgent(current_llm_config)
    constraint_customization = CustomizeConstraintAgent(current_llm_config)
    user_proxy = BaseUserProxy()
    
    print("[App] 註冊工具函數...")
    
    # 保存 deep_analysis agent 到 session 供工具函數使用
    cl.user_session.set("deep_analysis_agent", deep_analysis)

    # 註冊工具函數給 legal_retrieval_agent
    legal_retrieval.register_function(
        legal_article_search,
        user_proxy.get_proxy(),
        "搜索相關法條。當使用者要求查詢法律、法條時使用此函數。"
    )
    
    # host.register_function(
    #     search_and_rerank,
    #     user_proxy.get_proxy(),
    #     "搜索並重新排序案例。當使用者要求搜索案例時使用此函數。"
    # )
    
    # 註冊工具函數給 search_agent
    search.register_function(
        search_and_rerank,
        user_proxy.get_proxy(),
"""搜索並重排法律案例結果，支持三種模式：

【模式 1】按案例 ID 精確搜索 - 當用戶提供 case_id 時使用
  示例: search_and_rerank(query="case_59", metadata_filters={"case_id": "case_59"})

【模式 2】按內容關鍵詞搜索 - 當用戶提供法律概念或事實時使用  
  示例: search_and_rerank(query="資本不足", top_k=3)

【模式 3】複合搜索 - 內容搜索 + 元數據過濾
  示例: search_and_rerank(query="違規", metadata_filters={"status": "active"})

【參數說明】
  - query (str): 搜索查詢，可以是 case_id、法律概念或事實描述
  - top_k (int, 預設=1): 返回結果的數量
  - metadata_filters (dict | None): 元數據過濾條件
    * 案例 ID 過濾: {"case_id": "case_59"}
    * 複合條件: {"$and": [{"case_id": "case_0"}, {"status": "active"}]}
    * 範圍過濾: {"field": {"$gte": value, "$lte": value}}

【返回值】字典，包含以下鍵：
  - 'ids': 案例 ID 列表
  - 'ranked_documents': 排序後的文檔內容
  - 'ranked_metadatas': 排序後的元數據
  - 'scores': 相關性分數
  - 'extracted_codes': 提取的代碼片段"""
    )
    
    # 註冊工具函數給 deep_analysis_agent
    deep_analysis.register_function(
        Z3CodeExecution,
        user_proxy.get_proxy(),
        """執行 Z3 深入分析求解，生成完整的分析報告。

參數：
- case_id (str): 案例 ID，如 'case_0' 或 'case_405'

返回值：
- status: 'success' 或 'error'
- case_id: 案例編號
- initial_facts: 原始事實集合（字典）
- suggested_model: Z3 求解結果/建議模型
- analysis_report: 完整的分析報告（Markdown 格式）
- variable_changes: 變數變化列表（與建議值的對比）

使用場景：
- 用戶要求對某個案例進行深入分析
- 需要查看 Z3 求解的詳細結果
- 為後續的約束自定義提供基礎數據"""
    )
    
    # 註冊工具函數給 constraint_customization_agent
    constraint_customization.register_function(
        CustomizeZ3constraintExecution,
        user_proxy.get_proxy(),
        """應用自定義約束條件並執行 Z3 重新求解，返回新的求解結果。

參數：
- case_id (str, optional): 案例 ID，如 'case_0'。若不提供則自動從 session 提取
- constraints (dict): 自定義約束字典，格式為：
  {
    "variable_name": {
      "type": "FIX|LOWER_BOUND|UPPER_BOUND|RANGE",
      "value": <值>,              # 用於 FIX 類型
      "lower_bound": <值>,        # 用於 LOWER_BOUND 或 RANGE
      "upper_bound": <值> 或 "max": <值>  # 用於 UPPER_BOUND 或 RANGE
    }
  }

約束類型說明：
- FIX: 將變數固定為特定值
- LOWER_BOUND: 設定變數最小值（>= value）
- UPPER_BOUND: 設定變數最大值（<= value）
- RANGE: 設定變數上下界範圍（value_min <= var <= value_max）

返回值：
- status: 'success' 或 'error'
- message: 操作結果訊息
- solving_result: 新的 Z3 求解結果
  - initial_facts: 新的初始事實
  - suggested_model: 新的建議模型

使用場景：
- 用戶想調整某些變數的值或範圍
- 基於深入分析結果進行進一步的約束優化
- 測試不同的約束組合以找到最佳方案"""
    )
    
    # 創建 ChatManager（使用當前的 llm_config）
    chat_manager = ChatManager(
        agents=[host, search, summary, deep_analysis, legal_retrieval, constraint_customization],
        user_proxy=user_proxy,
        llm_config=current_llm_config,
        max_round=100
    )
    
    # 檢查是否有需要恢復的群組訊息
    group_messages = cl.user_session.get("group_chat_messages", [])
    
    # ⭐ 調試：檢查 session 中保存的訊息
    print(f"\n[App] ⭐ DEBUG: session 中的 group_chat_messages 有 {len(group_messages) if group_messages else 0} 條訊息")  # type: ignore
    if group_messages:
        for i, msg in enumerate(group_messages[:5]):  # 只顯示前 5 條
            if isinstance(msg, dict):
                name = msg.get("name", "?")
                role = msg.get("role", "?")
                content = str(msg.get("content", ""))[:60]
            else:
                name = getattr(msg, "name", "?")
                role = getattr(msg, "role", "?")
                content = str(getattr(msg, "content", ""))[:60]
            print(f"  [{i}] name={name}, role={role}, content={content}...")
    print()
    
    # ⭐ 改進的邏輯：如果 chat_manager 是新建立的，且有歷史訊息要恢復，就恢復
    # 檢查新建立的 chat_manager 是否為空（新實例的話應該是空的）
    if group_messages and len(chat_manager.group_chat.messages) == 0:
        print("[App] 新建立的 chat_manager 偵測到有對話歷史要恢復...")
        await chat_manager.restore_conversation_history(group_messages)
        print(f"[App] 已恢復 {len(group_messages)} 條群組訊息到新 agents")
    elif group_messages and len(chat_manager.group_chat.messages) > 0:
        print("[App] chat_manager 已有訊息，跳過恢復（可能已在本會話中恢復過）")
    else:
        print("[App] 沒有可恢復的群組訊息")
    
    # 儲存到 session
    cl.user_session.set("chat_manager", chat_manager)
    
    # 恢復 message_history（如果存在的話，否則初始化為空）
    if not cl.user_session.get("message_history"):
        cl.user_session.set("message_history", [])

    # Langfuse trace metadata (per session)
    if LANGFUSE_PATCHED:
        user = cl.user_session.get("user")
        user_id = getattr(user, "identifier", None) or "shared_user"
        cl.user_session.set("langfuse_user_id", user_id)
        if not cl.user_session.get("langfuse_session_id"):
            cl.user_session.set("langfuse_session_id", str(uuid.uuid4()))
    
    # 設置側邊欄按鈕和信息
    await setup_sidebar()
    
    
    # await cl.Message(content="👋 您好!我是金融合規助理。").send()

async def setup_sidebar():
    """設置側邊欄"""
    try:
        # 初始化 action_map
        cl.user_session.set("action_map", {})
        cl.user_session.set("upload_ready", True)
        print("[App] ✅ 側邊欄設置完成")
    except Exception as e:
        print(f"[App] 設置失敗: {e}")




@cl.on_settings_update
async def on_settings_update(settings):
    """
    處理使用者更改設定
    當使用者在設定面板中更改模型時觸發
    """
    global client
    
    model = settings.get("openai_model") or DEFAULT_MODEL
    api_key = DEFAULT_API_KEY
    
    print(f"[Settings] 設定更新 - 模型: {model}")
    
    # 驗證 API Key
    if not api_key:
        await cl.Message(
            content="⚠️ **API Key 不能為空**\n\n請重新設置 API Key。"
        ).send()
        return
    
    # 保存新設定到 session
    cl.user_session.set("openai_model", model)
    
    # 建立新的 OpenAI 客戶端
    openai_client = AsyncOpenAI(api_key=api_key)
    cl.user_session.set("openai_client", openai_client)
    
    # 更新全域 client
    client = openai_client
    
    # 更新 LLM 配置
    new_llm_config = get_llm_config(api_key, model)
    cl.user_session.set("llm_config", new_llm_config)
    
    # 重新建立 ChatManager 以使用新的設定
    try:
        # 取得 deep_analysis_agent
        deep_analysis = cl.user_session.get("deep_analysis_agent")
        
        # 創建新的 Agents
        host = HostAgent(new_llm_config)
        search = SearchCaseAgent(new_llm_config)
        summary = SummaryAgent(new_llm_config)
        
        # 如果 deep_analysis 不存在，重新創建
        if not deep_analysis:
            deep_analysis = DeepAnalysisAgent(new_llm_config)
            cl.user_session.set("deep_analysis_agent", deep_analysis)
        
        legal_retrieval = SearchLawAgent(new_llm_config)
        constraint_customization = CustomizeConstraintAgent(new_llm_config)
        user_proxy = BaseUserProxy()
        
        # 註冊工具函數
        legal_retrieval.register_function(
            legal_article_search,
            user_proxy.get_proxy(),
            "搜索相關法條。當使用者要求查詢法律、法條時使用此函數。"
        )
        search.register_function(
            search_and_rerank,
            user_proxy.get_proxy(),
"""
    搜索並重排結果，支持 metadata 過濾
    
    Args:
        query: 搜索查詢
        top_k: 返回的結果數量
        metadata_filters: metadata 過濾條件，格式為字典
                         例如: {"case_id": "case_0"}
                         或多條件: {"$and": [{"case_id": "case_0"}, {"status": "active"}]}
                         支持 Chroma 的所有過濾語法
    
    Returns:
        包含排序後的文檔、metadata 和 ID 的字典
"""
        )
        deep_analysis.register_function(
            Z3CodeExecution,
            user_proxy.get_proxy(),
            """執行 Z3 深入分析求解，生成完整的分析報告。

參數：
- case_id (str): 案例 ID，如 'case_0' 或 'case_405'

返回值：
- status: 'success' 或 'error'
- case_id: 案例編號
- initial_facts: 原始事實集合（字典）
- suggested_model: Z3 求解結果/建議模型
- analysis_report: 完整的分析報告（Markdown 格式）
- variable_changes: 變數變化列表（與建議值的對比）

使用場景：
- 用戶要求對某個案例進行深入分析
- 需要查看 Z3 求解的詳細結果
- 為後續的約束自定義提供基礎數據"""
        )
        constraint_customization.register_function(
            CustomizeZ3constraintExecution,
            user_proxy.get_proxy(),
            """應用自定義約束條件並執行 Z3 重新求解，返回新的求解結果。

參數：
- case_id (str, optional): 案例 ID，如 'case_0'。若不提供則自動從 session 提取
- constraints (dict): 自定義約束字典，格式為：
  {
    "variable_name": {
      "type": "FIX|LOWER_BOUND|UPPER_BOUND|RANGE",
      "value": <值>,              # 用於 FIX 類型
      "lower_bound": <值>,        # 用於 LOWER_BOUND 或 RANGE
      "upper_bound": <值> 或 "max": <值>  # 用於 UPPER_BOUND 或 RANGE
    }
  }

約束類型說明：
- FIX: 將變數固定為特定值
- LOWER_BOUND: 設定變數最小值（>= value）
- UPPER_BOUND: 設定變數最大值（<= value）
- RANGE: 設定變數上下界範圍（value_min <= var <= value_max）

返回值：
- status: 'success' 或 'error'
- message: 操作結果訊息
- solving_result: 新的 Z3 求解結果
  - initial_facts: 新的初始事實
  - suggested_model: 新的建議模型

使用場景：
- 用戶想調整某些變數的值或範圍
- 基於深入分析結果進行進一步的約束優化
- 測試不同的約束組合以找到最佳方案"""
        )
        
        # 創建新的 ChatManager
        chat_manager = ChatManager(
            agents=[host, search, summary, deep_analysis, legal_retrieval, constraint_customization],
            user_proxy=user_proxy,
            llm_config=new_llm_config,
            max_round=100
        )
        
        # 保存到 session（會覆蓋舊的 chat_manager）
        cl.user_session.set("chat_manager", chat_manager)
        
        await cl.Message(
            content=f"✅ **設定已更新**\n\n- 模型：`{model}`\n\n系統已準備就緒，請開始對話！"
        ).send()
        
        print("[Settings] ✅ ChatManager 已重新建立")
        
    except Exception as e:
        print(f"[Settings] ❌ 重建 ChatManager 失敗: {e}")
        await cl.Message(
            content=f"⚠️ 設定已保存，但系統更新失敗：{str(e)}\n\n請嘗試刷新頁面。"
        ).send()



async def handle_upload_summary():
    """
    處理上傳對話摘要的請求
    這個函數由 custom.js 按鈕觸發
    """
    try:
        print(f"[UploadSummary] 開始上傳對話摘要")
        
        # 禁用輸入
        cl.user_session.set("disable_input", True)
        
        # 顯示生成中
        status_msg = await cl.Message(content="📝 正在生成對話摘要...").send()
        
        # 獲取對話記錄
        message_history = cl.user_session.get("message_history", [])
        
        if not message_history:
            await cl.Message(content="❌ 沒有對話記錄可上傳。").send()
            cl.user_session.set("disable_input", False)
            return
        
        # 生成摘要
        print(f"[UploadSummary] 生成摘要，對話記錄數: {len(message_history)}")
        summary = await generate_conversation_summary(message_history)
        
        # 更新狀態
        status_msg.content = "📤 正在上傳摘要到系統..."
        await status_msg.update()
        
        # 生成標題
        title = f"對話摘要 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        # 上傳報告
        upload_success = await upload_report_to_fin_case(summary, title)
        
        # 更新狀態消息
        if upload_success:
            status_msg.content = "✅ 對話摘要已成功上傳到系統！"
        else:
            status_msg.content = "❌ 對話摘要上傳失敗，請稍後重試。"
        await status_msg.update()
        
        # 重新啟用輸入
        cl.user_session.set("disable_input", False)
        
    except Exception as e:
        print(f"[UploadSummary] 上傳失敗: {e}")
        await cl.Message(content=f"❌ 上傳失敗: {str(e)}").send()
        cl.user_session.set("disable_input", False)

async def add_upload_button_to_last_message():
    """
    為最後一條訊息添加上傳按鈕，確保頁面上只會有一個按鈕。
    """
    try:
        last_message_id = cl.user_session.get("_last_agent_message_id")
        last_message_content = cl.user_session.get("_last_agent_message_content") or ""

        if not last_message_id:
            print("[App] ⚠️ 沒有找到最後一條訊息")
            return

        # 清理舊按鈕 - 清理所有舊訊息的所有按鈕
        action_map = cl.user_session.get("action_map") or {}
        for msg_id, action_ids in list(action_map.items()):
            if msg_id != last_message_id:
                for action_id in action_ids:
                    try:
                        # 創建一個通用的 action 物件來移除
                        a = cl.Action(name="", payload={}, label="")
                        a.id = action_id
                        a.forId = msg_id
                        await a.remove()
                        print(f"[App] 已移除舊按鈕 {action_id} from message {msg_id}")
                    except Exception as e:
                        print(f"[App] 移除舊按鈕 {action_id} 失敗: {e}")
                del action_map[msg_id]

        # 清理完畢，更新 session
        cl.user_session.set("action_map", action_map)

        # 新增按鈕到最新訊息
        upload_action = cl.Action(
            name="quick_upload",
            label="📤 上傳對話摘要",
            payload={"action": "upload"}
        )

        # 強制更新該訊息內容和按鈕
        msg = cl.Message(
            id=last_message_id,
            content=last_message_content,
            actions=[upload_action]
        )
        await msg.update()  # 這會刷新 UI

        # 更新 mapping
        action_map[last_message_id] = [upload_action.id]
        cl.user_session.set("action_map", action_map)

        print("[App] ✅ 新按鈕已成功添加到最後訊息，舊的全部清理完畢。")

    except Exception as e:
        print(f"[App] 添加按鈕失敗: {e}")


# ===== 報告相關函數 =====

async def generate_conversation_summary(message_history: list) -> str:
    """
    使用 LLM 根據對話記錄生成摘要
    
    Args:
        message_history: 對話歷史列表
        
    Returns:
        生成的摘要文本
    """
    if not message_history:
        return "# 對話摘要\n\n（無對話記錄）"
    
    # 格式化對話記錄
    conversation_text = "\n\n".join([
        f"**{msg.get('role', 'unknown')}**: {msg.get('content', '')}"
        for msg in message_history
    ])
    
    prompt = f"""請根據以下對話記錄生成一份專業的摘要報告。報告應該以 Markdown 格式提供，包括以下部分：

## 摘要要求
1. **對話概述** - 簡要說明本次對話的主要目的和內容
2. **關鍵發現** - 列出所有重要的發現或結論
3. **法律依據** - 列出涉及的相關法條（如果有）
4. **案例參考** - 列出涉及的案例（如果有）
5. **建議** - 提供專業建議

## 對話記錄
{conversation_text}

請生成專業、結構清晰的摘要報告："""
    
    try:
        # 取得當前的 client 和 model
        current_client = cl.user_session.get("openai_client") or client
        current_model = cl.user_session.get("openai_model") or DEFAULT_MODEL
        
        if not current_client:
            return "# 對話摘要\n\n_摘要生成失敗：未設定 OpenAI API Key_"
        
        response = await current_client.chat.completions.create(
            model=current_model,
            messages=[
                {
                    "role": "system",
                    "content": "你是一位資深的金融合規專家。請根據對話記錄生成專業的摘要報告。"
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.5,
            max_tokens=2000
        )
        
        summary = response.choices[0].message.content or "# 對話摘要\n\n_摘要生成失敗：無返回內容_"
        return summary
    except Exception as e:
        print(f"[ERROR] 摘要生成失敗: {e}")
        return f"# 對話摘要\n\n_摘要生成失敗: {str(e)}_"

async def upload_report_to_fin_case(report_content: str, title: str = "對話摘要報告") -> bool:
    """
    上傳報告到 FinCase API
    
    Args:
        report_content: 報告內容（Markdown 格式）
        title: 報告標題，如果不提供則使用預設值
        
    Returns:
        是否上傳成功
    """
    final_title = title if title else f"對話摘要報告 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    
    base_url = os.getenv("REPORT_API_BASE", "http://118.163.52.174:15678/api")
    url = f"{base_url}/report/generated/fin-case"
    
    payload = {
        "report": report_content,
        "title": final_title
    }
    
    try:
        print(f"[Report] 開始上傳報告到: {url}")
        print(f"[Report] 報告標題: {final_title}")
        
        async with httpx.AsyncClient(timeout=30.0) as client_http:
            response = await client_http.post(url, json=payload)
            response.raise_for_status()
            
            result = response.json()
            
            if result.get("status") == "success":
                print(f"[Report] ✅ 報告上傳成功!")
                print(f"[Report] 報告 ID: {result.get('reportId')}")
                return True
            else:
                print(f"[Report] ⚠️ 上傳返回異常: {result}")
                return False
                
    except Exception as e:
        print(f"[Report] ❌ 上傳失敗: {e}")
        return False

async def _show_upload_report_button(message_history: list):
    """
    保留此函數以向後相容，但不使用
    在對話完成後顯示上傳報告按鈕
    
    Args:
        message_history: 對話歷史
    """
    # 此函數已被移除，上傳功能現在通過固定的 action callback 提供
    pass

@cl.on_message
async def on_message(msg: cl.Message):
    """處理用戶訊息"""
    # 清除恢復對話標記，因為現在是繼續對話
    cl.user_session.set("is_resumed_conversation", False)
    
    # 從 Chainlit Message 物件中提取文本內容
    user_input = msg.content if isinstance(msg, cl.Message) else str(msg)
    
    # 檢查是否是上傳命令
    if user_input.strip() == "【上傳對話摘要】":
        print(f"[DEBUG] 收到上傳命令")
        await handle_upload_summary()
        return
    
    # 檢查輸入是否被禁用
    if cl.user_session.get("disable_input", False):
        print(f"[DEBUG] 用戶輸入已被禁用，忽略訊息: {user_input}")
        await cl.Message(content="⏳ 系統正在處理中，請稍候...").send()
        return
    
    # 取得 ChatManager
    chat_manager = cl.user_session.get("chat_manager")
    message_history = cl.user_session.get("message_history") or []
    
    # 如果 chat_manager 不存在，自動初始化系統
    if not chat_manager:
        print("[DEBUG] ChatManager 不存在，開始自動初始化...")
        await start_chat()
        chat_manager = cl.user_session.get("chat_manager")
        
        if not chat_manager:
            await cl.Message(content="❌ 系統初始化失敗，請刷新頁面後重試。").send()
            return
        
        print("[DEBUG] 系統已自動初始化完成")
    
    # 🔍 Debug: 列印當前狀態
    print(f"\n[DEBUG] 收到訊息: {user_input}")
    conversation_state = cl.user_session.get("conversation_state", "initial")
    print(f"[DEBUG] 當前 conversation_state: {conversation_state}")
    try:
        print(f"[DEBUG] 當前訊息數: {len(chat_manager.group_chat.messages)}")
        print(f"[DEBUG] last_processed_count: {chat_manager.last_processed_count}")
    except AttributeError:
        print(f"[DEBUG] 無法獲取 ChatManager 狀態")
    
    # 檢查當前對話狀態，如果處於等待狀態，添加狀態標記
    if conversation_state == "waiting_for_legal_content" and user_input.strip():
        # 用戶提供了法條內容，添加狀態標記
        processed_input = f"【狀態:waiting_for_legal_content】{user_input}"
        print(f"[DEBUG] 添加法條內容狀態標記: {processed_input}")
    elif conversation_state == "waiting_for_case_content" and user_input.strip():
        # 用戶提供了案例內容，添加狀態標記
        processed_input = f"【狀態:waiting_for_case_content】{user_input}"
        print(f"[DEBUG] 添加案例內容狀態標記: {processed_input}")
    else:
        # 正常處理
        processed_input = user_input
    
    # 確保 processed_input 是字符串
    processed_input = str(processed_input)
    print(f"[DEBUG] 最終處理訊息類型: {type(processed_input)}, 值: {processed_input}")
    
    try:
        # Langfuse trace metadata per request
        lf_user_id = cl.user_session.get("langfuse_user_id") or "shared_user"
        lf_session_id = cl.user_session.get("langfuse_session_id")
        lf_tags = ["autogen", "chainlit", "uicompliance"]
        lf_metadata = {
            "model": _lf_safe_str(cl.user_session.get("openai_model") or DEFAULT_MODEL),
            "conversation_state": _lf_safe_str(conversation_state),
        }

        with _langfuse_trace_context(
            user_id=lf_user_id,
            session_id=lf_session_id,
            tags=lf_tags,
            metadata=lf_metadata,
            trace_name="autogen_chat",
        ):
            # 使用串流模式處理對話
            result = await chat_manager.initiate_chat_with_streaming(
                message=processed_input,
                stream_delay=0.001
            )
        
        # 🔍 Debug: 檢查結果格式
        print(f"[DEBUG] 對話結果類型: {type(result)}")
        if result is None:
            print(f"[ERROR] ChatManager 返回了 None")
            result = {
                "success": False,
                "error": "ChatManager 返回了 None",
                "messages": {
                    "host_responses": [],
                    "search_results": [],
                    "analysis_results": [],
                    "system_messages": []
                }
            }
        elif not isinstance(result, dict):
            print(f"[ERROR] ChatManager 返回了非字典類型: {result}")
            result = {
                "success": False,
                "error": f"ChatManager 返回了非字典類型: {type(result)}",
                "messages": {
                    "host_responses": [],
                    "search_results": [],
                    "analysis_results": [],
                    "system_messages": []
                }
            }
        
        # 🔍 Debug: 列印結果
        print(f"[DEBUG] 對話結果: success={result.get('success', 'MISSING')}")
        
        # 修正：檢查 messages 是否為字典
        if isinstance(result.get('messages'), dict):
            print(f"[DEBUG] 訊息類別: {list(result['messages'].keys())}")
        else:
            print(f"[DEBUG] 訊息格式: {type(result.get('messages'))}")
        
        # 儲存歷史
        if result.get("success", False):
            message_history.append({"role": "user", "content": processed_input})
            
            # 儲存所有 Agent 的回應
            messages = result.get("messages", {})
            if isinstance(messages, dict):
                for category, msg_list in messages.items():
                    for msg_data in msg_list:
                        message_history.append({
                            "role": msg_data["role"],
                            "content": msg_data["content"]
                        })
            
            cl.user_session.set("message_history", message_history)
            
            # 保存完整的群組對話訊息（用於恢復）
            group_messages = chat_manager.get_all_messages()
            
            # ⭐ 修復：在保存前修正訊息的 role
            # autogen 的 GroupChat 可能把所有訊息都設成 user，我們需要根據 name 推導正確的 role
            for msg in group_messages:
                if isinstance(msg, dict):
                    name = msg.get("name", "")
                    current_role = msg.get("role", "user")
                    
                    # ⭐ 根據 name 推導正確的 role
                    if name in ["user_proxy", "interactive_user", ""]:
                        msg["role"] = "user"
                    elif current_role == "user" and name and name not in ["user_proxy"]:
                        # 如果是 agent 名稱但被標成 user，改成 assistant
                        msg["role"] = "assistant"
            
            # ⭐ 調試：列印修正後的訊息
            print(f"\n[DEBUG] 修正後的群組訊息結構（共 {len(group_messages)} 條）:")
            for i, msg in enumerate(group_messages):
                if isinstance(msg, dict):
                    name = msg.get("name", "MISSING")
                    role = msg.get("role", "MISSING")
                    content = str(msg.get("content", ""))[:80]
                else:
                    name = getattr(msg, "name", "MISSING")
                    role = getattr(msg, "role", "MISSING")
                    content = str(getattr(msg, "content", ""))[:80]
                print(f"  [{i}] name={name}, role={role}, content={content}...")
            print()
            
            cl.user_session.set("group_chat_messages", group_messages)
            print(f"[DEBUG] 已保存 {len(group_messages)} 條群組訊息到 session")
        else:
            # 處理錯誤情況
            error_msg = result.get("error", "未知錯誤")
            await cl.Message(content=f"❌ 處理時發生錯誤: {error_msg}").send()
        
        try:
            print(f"[DEBUG] 對話完成，總訊息數: {len(chat_manager.group_chat.messages)}\n")
        except AttributeError:
            print(f"[DEBUG] 對話完成\n")
        
        # 對話完成後，添加上傳報告按鈕
        await add_upload_button_to_last_message()
        
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"[ERROR] {error_detail}")
        await cl.Message(content=f"❌ 錯誤: {str(e)}").send()

async def _handle_search_confirmation(action, confirm_flag, lock_flag, processing_message, trigger_message):
    """處理搜索確認動作的通用函數（修正版：確保按鈕消失 + 清除訊息狀態）"""
    msg_updated_successfully = False
    try:
        print(f"[ActionHandler] {confirm_flag} clicked. action.id={getattr(action,'id',None)}, forId={getattr(action,'forId',None)}")

        cl.user_session.set("disable_input", True)
        print(f"[ActionHandler] 用戶輸入已禁用")

        msg_id = getattr(action, "forId", None)
        if not msg_id:
            action_map = cl.user_session.get("action_map") or {}
            for mid, a_ids in action_map.items():
                if action.id in a_ids:
                    msg_id = mid
                    print(f"[ActionHandler] 從 action_map 找到 msg_id: {msg_id}")
                    break

        # ✅ 記錄該訊息已清除
        cleaned_msg_ids = cl.user_session.get("_cleaned_message_ids") or []
        if msg_id and msg_id not in cleaned_msg_ids:
            cleaned_msg_ids.append(msg_id)
            cl.user_session.set("_cleaned_message_ids", cleaned_msg_ids)
            print(f"[ActionHandler] ✅ 記錄已清除訊息ID: {msg_id}")

        # 更新原訊息 - 正確移除按鈕
        if msg_id:
            try:
                # 在清空 action_map 之前獲取該訊息的按鈕
                action_map = cl.user_session.get("action_map") or {}
                a_ids = action_map.get(msg_id, [])
                
                # 移除所有按鈕
                for aid in a_ids:
                    try:
                        # 創建 action 物件來移除
                        a = cl.Action(name="", payload={}, label="")
                        a.id = aid
                        a.forId = msg_id
                        await a.remove()
                        print(f"[ActionHandler] 已移除按鈕 {aid} from message {msg_id}")
                    except Exception as e:
                        print(f"[ActionHandler] 移除按鈕 {aid} 失敗: {e}")
                
                # 清空 action_map，避免重複按鈕
                cl.user_session.set("action_map", {})
                print(f"[ActionHandler] 清空 action_map")
                
                # 先更新訊息移除按鈕
                msg = cl.Message(id=msg_id, content="", actions=[])
                await msg.update()
                
                # 然後更新內容
                msg = cl.Message(content=f"✅ 已確認，{processing_message}... ⏳", id=msg_id, actions=[])
                await msg.update()
                msg_updated_successfully = True
                print(f"[ActionHandler] ✅ 按鈕已移除並更新訊息")
            except Exception as e:
                print(f"[ActionHandler] 更新訊息失敗: {e}")
                msg_updated_successfully = False
        else:
            print(f"[ActionHandler] ⚠️ 找不到 msg_id")
    except Exception as e:
        print(f"[ActionHandler] ❌ 更新按鈕失敗: {e}")

    if not msg_updated_successfully:
        await cl.Message(content=f"✅ 已確認，{processing_message}... ⏳").send()

    # 執行搜索
    chat_manager = cl.user_session.get("chat_manager")
    if chat_manager:
        try:
            cl.user_session.set("conversation_state", "initial")
            print(f"[ActionHandler] 開始執行搜索: {trigger_message}")
            await chat_manager.initiate_chat_with_streaming(trigger_message)
        except Exception as e:
            print(f"[ActionHandler] ❌ 搜索出錯: {e}")
        finally:
            # ✅ 清空清除列表與輸入鎖
            cl.user_session.set("_cleaned_message_ids", [])
            cl.user_session.set("disable_input", False)
            print(f"[ActionHandler] ✅ 已清除清除列表並重新啟用輸入")


@cl.on_stop
async def on_stop():
    """
    處理用戶點擊停止按鈕
    """
    try:
        print("[App] 用戶點擊中斷按鈕")
        
        # 獲取 ChatManager
        chat_manager = cl.user_session.get("chat_manager")
        
        if chat_manager:
            # 中斷對話
            was_interrupted = chat_manager.interrupt_chat()
            
            if was_interrupted:
                print("[App] 已成功中斷對話任務")
                await cl.Message(content="⏹️ 對話已被中斷，系統停止執行。").send()
            else:
                print("[App] 沒有進行中的任務可中斷")
                await cl.Message(content="⚠️ 目前沒有進行中的處理任務。").send()
        else:
            print("[App] ChatManager 不存在")
    
    except Exception as e:
        print(f"[App] 中斷處理出錯: {e}")
        import traceback
        traceback.print_exc()


@cl.on_chat_resume
async def on_chat_resume(thread):
    """恢復對話"""
    print("[App] 恢復對話中...")
    
    # 設置標記表示這是恢復的對話
    cl.user_session.set("is_resumed_conversation", True)
    
    # 恢復簡單的 message_history（用於上傳等功能）
    message_history = []
    if thread.get("steps"):
        for step in thread["steps"]:
            if step.get("type") == "user_message":
                message_history.append({"role": "user", "content": step.get("output", "")})
            elif step.get("type") == "assistant_message":
                message_history.append({"role": "assistant", "content": step.get("output", "")})
    cl.user_session.set("message_history", message_history)
    print(f"[App] 恢復了 {len(message_history)} 條消息歷史")
    
    # 確保 chat_manager 被初始化並恢復狀態
    if not cl.user_session.get("chat_manager"):
        print("[App] 在恢復時初始化 chat_manager...")
        await start_chat()
        print("[App] chat_manager 初始化完成")
    
    # 注意：group_chat_messages 會在 start_chat 時由 session 恢復



@cl.action_callback("confirm_analysis")
async def on_confirm_analysis(action):
    """使用者確認要進行深入分析"""
    await _handle_confirmation(action, "analysis_confirmed", "analysis_locked", "開始進行深入分析")

@cl.action_callback("cancel_analysis")
async def on_cancel_analysis(action):
    """使用者取消深入分析"""
    await _handle_cancellation(action, "analysis_locked", "已取消分析")

@cl.action_callback("confirm_legal_search")
async def on_confirm_legal_search(action):
    """使用者確認要搜索法條"""
    search_content = cl.user_session.get("search_content", "")
    await _handle_search_confirmation(action, "legal_search_confirmed", "legal_search_locked", f"開始搜索相關法條", "【啟動法條搜索】")

@cl.action_callback("confirm_case_search")
async def on_confirm_case_search(action):
    """使用者確認要搜索案例"""
    search_content = cl.user_session.get("search_content", "")
    await _handle_search_confirmation(action, "case_search_confirmed", "case_search_locked", f"開始搜索案例", "【啟動案例分析】")

@cl.action_callback("cancel_legal_search")
async def on_cancel_legal_search(action):
    """使用者取消法條搜索"""
    await _handle_cancellation(action, "legal_search_locked", "已取消法條搜索")

@cl.action_callback("cancel_case_search")
async def on_cancel_case_search(action):
    """使用者取消案例搜索"""
    await _handle_cancellation(action, "case_search_locked", "已取消案例搜索")

@cl.action_callback("confirm_deep_analysis")
async def on_confirm_deep_analysis(action):
    """使用者確認要進行深入分析"""
    await _handle_confirmation(action, "deep_analysis_confirmed", "deep_analysis_locked", "開始進行深入分析")

@cl.action_callback("cancel_deep_analysis")
async def on_cancel_deep_analysis(action):
    """使用者取消深入分析"""
    await _handle_cancellation(action, "deep_analysis_locked", "已取消深入分析")

@cl.action_callback("upload_conversation_summary")
async def on_upload_conversation_summary(action):
    """
    使用者點擊上傳對話摘要按鈕
    """
    try:
        print(f"[UploadAction] 開始上傳對話摘要")
        
        # 禁用輸入
        cl.user_session.set("disable_input", True)
        
        # 顯示生成中
        status_msg = await cl.Message(content="📝 正在生成對話摘要...").send()
        
        # 獲取對話記錄
        message_history = cl.user_session.get("message_history", [])
        
        if not message_history:
            await cl.Message(content="❌ 沒有對話記錄可上傳。").send()
            cl.user_session.set("disable_input", False)
            return
        
        # 生成摘要
        print(f"[UploadAction] 生成摘要，對話記錄數: {len(message_history)}")
        summary = await generate_conversation_summary(message_history)
        
        # 更新狀態
        status_msg.content = "📤 正在上傳摘要到系統..."
        await status_msg.update()
        
        # 生成標題
        title = f"對話摘要 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        # 上傳報告
        upload_success = await upload_report_to_fin_case(summary, title)
        
        # 移除 upload 按鈕
        try:
            msg_id = getattr(action, "forId", None)
            if not msg_id:
                action_map = cl.user_session.get("action_map") or {}
                if action_map:
                    for mid, a_ids in action_map.items():
                        if action.id in a_ids:
                            msg_id = mid
                            break
            
            if msg_id:
                action_map = cl.user_session.get("action_map") or {}
                a_ids = action_map.get(msg_id, [])
                for aid in a_ids:
                    try:
                        a = cl.Action(name=action.name, payload=action.payload, label=action.label)
                        a.id = aid
                        a.forId = msg_id
                        await a.remove()
                    except Exception:
                        pass
                
                # 更新訊息
                if upload_success:
                    msg = cl.Message(
                        content="✅ 對話摘要已成功上傳到系統！",
                        id=msg_id,
                        actions=[]
                    )
                else:
                    msg = cl.Message(
                        content="❌ 對話摘要上傳失敗，請稍後重試。",
                        id=msg_id,
                        actions=[]
                    )
                await msg.update()
                
                if msg_id in action_map:
                    del action_map[msg_id]
                    cl.user_session.set("action_map", action_map)
        except Exception as e:
            print(f"[UploadAction] 移除按鈕失敗: {e}")
            if upload_success:
                await cl.Message(content="✅ 對話摘要已成功上傳到系統！").send()
            else:
                await cl.Message(content="❌ 對話摘要上傳失敗，請稍後重試。").send()
        
        # 重新啟用輸入
        cl.user_session.set("disable_input", False)
        
    except Exception as e:
        print(f"[UploadAction] 上傳失敗: {e}")
        await cl.Message(content=f"❌ 上傳失敗: {str(e)}").send()
        cl.user_session.set("disable_input", False)

@cl.action_callback("quick_upload")
async def on_quick_upload(action):
    """
    快速上傳按鈕的 callback
    """
    try:
        print(f"[QuickUpload] 開始快速上傳對話摘要")
        
        # 禁用輸入
        cl.user_session.set("disable_input", True)
        
        # 顯示生成中
        status_msg = await cl.Message(content="📝 正在生成對話摘要...").send()
        
        # 獲取對話記錄
        message_history = cl.user_session.get("message_history", [])
        
        if not message_history:
            await cl.Message(content="❌ 沒有對話記錄可上傳。").send()
            cl.user_session.set("disable_input", False)
            return
        
        # 生成摘要
        print(f"[QuickUpload] 生成摘要，對話記錄數: {len(message_history)}")
        summary = await generate_conversation_summary(message_history)
        
        # 更新狀態
        status_msg.content = "📤 正在上傳摘要到系統..."
        await status_msg.update()
        
        # 生成標題
        title = f"對話摘要 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        # 上傳報告
        upload_success = await upload_report_to_fin_case(summary, title)
        
        # 更新狀態消息
        if upload_success:
            status_msg.content = "✅ 對話摘要已成功上傳到系統！"
        else:
            status_msg.content = "❌ 對話摘要上傳失敗，請稍後重試。"
        await status_msg.update()
        
        # 重新啟用輸入
        cl.user_session.set("disable_input", False)
        
    except Exception as e:
        print(f"[QuickUpload] 上傳失敗: {e}")
        await cl.Message(content=f"❌ 上傳失敗: {str(e)}").send()
        cl.user_session.set("disable_input", False)

@cl.action_callback("apply_custom_constraints")
async def on_apply_custom_constraints(action):
    """
    應用自定義約束的 callback
    """
    try:
        print(f"[ApplyConstraints] 開始應用自定義約束")
        
        # 禁用輸入
        cl.user_session.set("disable_input", True)
        
        # 顯示處理中
        status_msg = await cl.Message(content="⚙️ 正在應用自定義約束並執行 Z3 求解...").send()
        
        # 從 session 獲取案例 ID 和約束
        case_id = cl.user_session.get("current_analysis_case_id") or "case_0"
        constraints = cl.user_session.get("pending_constraints") or {}
        
        if not constraints:
            await cl.Message(content="❌ 沒有設置自定義約束。").send()
            cl.user_session.set("disable_input", False)
            return
        
        print(f"[ApplyConstraints] Case ID: {case_id}")
        print(f"[ApplyConstraints] 約束數: {len(constraints)}")
        
        # 執行工具
        result = CustomizeZ3constraintExecution(case_id, constraints)
        
        # 更新狀態消息
        if result.get("status") == "success":
            status_msg.content = "✅ 自定義約束已成功應用！\n\n"
            status_msg.content += f"已應用 {result.get('constraints_count', 0)} 個約束\n"
            status_msg.content += "Z3 求解已完成，新的分析結果已保存。"
            
            print(f"[ApplyConstraints] 執行成功")
        else:
            error_msg = result.get("error_message", result.get("message", "未知錯誤"))
            status_msg.content = f"❌ 執行失敗：{error_msg}"
            
            print(f"[ApplyConstraints] 執行失敗: {error_msg}")
        
        await status_msg.update()
        
        # 重新啟用輸入
        cl.user_session.set("disable_input", False)
        
    except Exception as e:
        print(f"[ApplyConstraints] 異常: {e}")
        import traceback
        traceback.print_exc()
        await cl.Message(content=f"❌ 執行異常: {str(e)}").send()
        cl.user_session.set("disable_input", False)

@cl.action_callback("upload_analysis_report")
async def on_upload_analysis_report(action):
    """
    上傳深入分析報告的 callback
    """
    try:
        print(f"[AnalysisUpload] 開始上傳深入分析報告")
        
        # 禁用輸入
        cl.user_session.set("disable_input", True)
        
        # 獲取已保存的分析報告
        report_content = cl.user_session.get("current_analysis_report")
        case_id = cl.user_session.get("current_analysis_case_id", "unknown")
        
        if not report_content:
            await cl.Message(content="❌ 沒有分析報告可上傳。").send()
            cl.user_session.set("disable_input", False)
            return
        
        # 顯示處理中
        status_msg = await cl.Message(content="📤 正在上傳分析報告...").send()
        
        # 生成標題
        title = f"深入分析報告 - {case_id} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        # 上傳報告
        upload_success = await upload_report_to_fin_case(report_content, title)
        
        # 更新狀態消息
        if upload_success:
            status_msg.content = "✅ 深入分析報告已成功上傳到系統！"
        else:
            status_msg.content = "❌ 深入分析報告上傳失敗，請稍後重試。"
        await status_msg.update()
        
        # 重新啟用輸入
        cl.user_session.set("disable_input", False)
        
    except Exception as e:
        print(f"[AnalysisUpload] 上傳失敗: {e}")
        await cl.Message(content=f"❌ 上傳失敗: {str(e)}").send()
        cl.user_session.set("disable_input", False)

@cl.action_callback("upload_summary")
async def on_upload_summary(action):
    """
    上傳摘要的 callback
    """
    try:
        print(f"[SummaryUpload] 開始上傳摘要")
        
        # 禁用輸入
        cl.user_session.set("disable_input", True)
        
        # 獲取已保存的摘要內容
        summary_content = cl.user_session.get("current_summary", cl.user_session.get("current_analysis_report"))
        case_id = cl.user_session.get("current_analysis_case_id", "unknown")
        
        if not summary_content:
            await cl.Message(content="❌ 沒有摘要可上傳。").send()
            cl.user_session.set("disable_input", False)
            return
        
        # 顯示處理中
        status_msg = await cl.Message(content="📤 正在上傳摘要...").send()
        
        # 生成標題
        title = f"摘要 - {case_id} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        # 上傳摘要
        upload_success = await upload_report_to_fin_case(summary_content, title)
        
        # 更新狀態消息
        if upload_success:
            status_msg.content = "✅ 摘要已成功上傳到系統！"
        else:
            status_msg.content = "❌ 摘要上傳失敗，請稍後重試。"
        await status_msg.update()
        
        # 重新啟用輸入
        cl.user_session.set("disable_input", False)
        
    except Exception as e:
        print(f"[SummaryUpload] 上傳失敗: {e}")
        await cl.Message(content=f"❌ 上傳失敗: {str(e)}").send()
        cl.user_session.set("disable_input", False)


async def _extract_case_id_from_chat() -> Optional[str]:
    """
    從 group chat 歷史中提取最新的案例搜尋結果的 case_id
    
    Returns:
        case_id 或 None
    """
    try:
        chat_manager = cl.user_session.get("chat_manager")
        if not chat_manager:
            print("[DeepAnalysis] 無法取得 ChatManager")
            return None
        
        # 遍歷 group chat 消息歷史，尋找搜尋結果中的 case_id
        messages = chat_manager.group_chat.messages
        
        # 從後向前遍歷以找到最新的搜尋結果
        for i in range(len(messages) - 1, -1, -1):
            msg = messages[i]
            
            # 查找包含搜尋結果的消息（通常由 search_agent 或 user_proxy 發送）
            content = msg.get('content', '')
            
            # 檢查是否包含 case_id 的跡象
            if 'case_' in content or '"case_' in content or "'case_" in content:
                print(f"[DeepAnalysis] 在消息中找到 case 參考: {content[:100]}...")
                
                # 嘗試解析 JSON 格式的結果（如果是 ranked_ids 或類似結構）
                import re
                case_matches = re.findall(r'case_\d+', content)
                if case_matches:
                    case_id = case_matches[0]  # 取第一個找到的
                    print(f"[DeepAnalysis] 提取到 case_id: {case_id}")
                    return case_id
        
        print("[DeepAnalysis] 未找到 case_id")
        return None
    
    except Exception as e:
        print(f"[DeepAnalysis] 提取 case_id 失敗: {e}")
        return None

async def _handle_confirmation(action, confirm_flag, lock_flag, processing_message):
    """處理確認動作的通用函數"""
    msg_updated_successfully = False
    try:
        print(f"[ActionHandler] {confirm_flag} clicked. action.id={getattr(action,'id',None)}, forId={getattr(action,'forId',None)}")
        
        # 立即禁用用戶輸入，防止重複操作
        cl.user_session.set("disable_input", True)
        print(f"[ActionHandler] 用戶輸入已禁用")
        
        # 使用 action.forId 取得該訊息 id
        processing_content = f"✅ 已確認，{processing_message}... ⏳"
        msg_id = getattr(action, "forId", None)

        # 如果 forId 不在 action 物件上，嘗試從 session 的 action_map 找到
        if not msg_id:
            action_map = cl.user_session.get("action_map") or {}
            if action_map:
                for mid, a_ids in action_map.items():
                    if action.id in a_ids:
                        msg_id = mid
                        print(f"[ActionHandler] 從 action_map 找到 msg_id: {msg_id}")
                        break

        # 立即清空整個 action_map，防止舊按鈕殘留
        print(f"[ActionHandler] 清空 action_map 以移除所有舊按鈕")
        cl.user_session.set("action_map", {})

        if msg_id:
            try:
                # 設定 session 鎖
                cl.user_session.set(lock_flag, True)
                print(f"[ActionHandler] {lock_flag} set True")
                
                # 更新原訊息：移除按鈕並更新內容
                try:
                    msg = cl.Message(content=processing_content, id=msg_id, actions=[])
                    await msg.update()
                    print(f"[ActionHandler] ✅ 訊息已更新，按鈕已移除")
                    msg_updated_successfully = True
                except Exception as e:
                    print(f"[ActionHandler] ⚠️ 訊息更新失敗: {e}")
                    msg_updated_successfully = False
                    
            except Exception as e:
                print(f"[ActionHandler] ❌ 更新訊息時出錯: {e}")
                msg_updated_successfully = False
        else:
            print(f"[ActionHandler] ⚠️ 未找到 msg_id")
            msg_updated_successfully = False
            
    except Exception as e:
        print(f"[ActionHandler] ❌ 無法更新按鈕狀態: {e}")
        msg_updated_successfully = False

    # 如果訊息更新失敗，發送新訊息表示已開始處理
    if not msg_updated_successfully:
        await cl.Message(content=f"✅ 已確認，{processing_message}... ⏳").send()

    # 觸發對應的處理邏輯
    chat_manager = cl.user_session.get("chat_manager")
    if chat_manager:
        try:
            # 在觸發之前，重置對話狀態
            cl.user_session.set("conversation_state", "initial")
            print(f"[ActionHandler] 重置對話狀態為 initial")
            
            if "legal_search" in confirm_flag:
                # 法條搜索：直接調用工具
                print(f"[ActionHandler] 執行法條搜索")
                result = await chat_manager.initiate_chat_with_streaming(
                    message="【啟動法條搜索】",
                    stream_delay=0.01
                )
            elif "case_search" in confirm_flag:
                # 案例搜索：轉到search_agent
                print(f"[ActionHandler] 執行案例搜索")
                result = await chat_manager.initiate_chat_with_streaming(
                    message="【啟動案例分析】",
                    stream_delay=0.01
                )
            elif "deep_analysis" in confirm_flag:
                # 深入分析：提取 case_id 並直接設定 deep_analysis_agent 為下一個 speaker
                print(f"[ActionHandler] 提取 case_id 並設定 deep_analysis_agent 為下一個 speaker")
                case_id = await _extract_case_id_from_chat()
                if case_id:
                    print(f"[ActionHandler] 找到 case_id: {case_id}")
                    chat_manager.manager.next_agent = chat_manager._get_agent_by_name("deep_analysis_agent")
                    # 發送包含 case_id 的觸發消息
                    result = await chat_manager.initiate_chat_with_streaming(
                        message=f"【啟動深入分析】 {case_id}",
                        stream_delay=0.01
                    )
                else:
                    print(f"[ActionHandler] 未找到 case_id，無法進行深入分析")
                    await cl.Message(content="❌ 無法找到要分析的案例，請先進行案例搜索。").send()
                    cl.user_session.set("disable_input", False)
                    return
            else:
                # 一般分析
                print(f"[ActionHandler] 執行一般分析")
                result = await chat_manager.initiate_chat_with_streaming(
                    message="是",
                    stream_delay=0.01
                )
            
            print(f"[ActionHandler] 處理完成")
            
            # 完成後短暫延遲
            await asyncio.sleep(0.3)
            
        except Exception as e:
            print(f"[ActionHandler] ❌ 執行出錯: {e}")
        finally:
            # 處理完成後，清除 session 的旗標
            try:
                cl.user_session.set(confirm_flag, False)
                cl.user_session.set(lock_flag, False)
                cl.user_session.set("disable_input", False)
                print(f"[ActionHandler] ✅ 已清除所有旗標，用戶輸入已重新啟用")
            except Exception as e:
                print(f"[ActionHandler] ⚠️ 無法清除 session 旗標: {e}")

async def _handle_cancellation(action, lock_flag, cancel_message):
    """處理取消動作的通用函數"""
    # 如果已被鎖定，則忽略取消請求
    locked = cl.user_session.get(lock_flag)
    if locked:
        print(f"[ActionHandler] {lock_flag} is True -> ignoring cancel")
        await cl.Message(content=f"目前正在處理，無法取消。⏳").send()
        return

    # 將按鈕設為不可點以防止重複操作，並顯示已取消的狀態
    try:
        cancelled_content = f"❌ {cancel_message}。如需其他協助，請隨時提出！"

        msg_id = getattr(action, "forId", None)
        if not msg_id:
            action_map = cl.user_session.get("action_map") or {}
            if action_map:
                for mid, a_ids in action_map.items():
                    if action.id in a_ids:
                        msg_id = mid
                        break

        if msg_id:
            try:
                action_map = cl.user_session.get("action_map") or {}
                a_ids = action_map.get(msg_id, [])
                for aid in a_ids:
                    try:
                        a = cl.Action(name=action.name, payload=action.payload, label=action.label)
                        a.id = aid
                        a.forId = msg_id
                        await a.remove()
                    except Exception:
                        pass

                msg = cl.Message(content=cancelled_content, id=msg_id, actions=[])
                await msg.update()
                if msg_id in action_map:
                    del action_map[msg_id]
                    cl.user_session.set("action_map", action_map)
            except Exception as e:
                print(f"[ActionHandler] 移除 actions 發生錯誤: {e}")
                await cl.Message(content=cancelled_content).send()
        else:
            await cl.Message(content=cancelled_content).send()
    except Exception as e:
        print(f"[ActionHandler] 無法更新按鈕狀態: {e}")
        await cl.Message(content=f"❌ {cancel_message}。如需其他協助，請隨時提出！").send()
    
    # 取消操作後，重置對話狀態
    try:
        cl.user_session.set("conversation_state", "initial")
        print(f"[ActionHandler] 取消操作後重置對話狀態為 initial")
    except Exception as e:
        print(f"[ActionHandler] 無法重置對話狀態: {e}")
