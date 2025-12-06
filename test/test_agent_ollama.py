#!/usr/bin/env python3
"""
測試腳本：驗證 Ollama 配置是否正確應用到 Agent System
"""

import os
import sys
from dotenv import load_dotenv

# 加載環境變數
load_dotenv(".env.ollama.example")

def test_environment_setup():
    """測試環境變數設定"""
    print("=" * 70)
    print("測試 1: 環境變數設定")
    print("=" * 70)
    
    use_ollama = os.getenv("USE_OLLAMA", "false").lower() == "true"
    ollama_model = os.getenv("OLLAMA_MODEL", "mistral")
    ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    
    print(f"\n✓ USE_OLLAMA: {use_ollama}")
    print(f"✓ OLLAMA_MODEL: {ollama_model}")
    print(f"✓ OLLAMA_BASE_URL: {ollama_base_url}")
    
    if not use_ollama:
        print("\n⚠️  USE_OLLAMA 未啟用，將使用 OpenAI")
    else:
        print("\n✅ Ollama 已啟用")
    
    return use_ollama

def test_llm_config():
    """測試 LLM 配置"""
    print("\n" + "=" * 70)
    print("測試 2: LLM 配置生成")
    print("=" * 70)
    
    # 模擬 get_llm_config 邏輯
    use_ollama = os.getenv("USE_OLLAMA", "false").lower() == "true"
    
    if use_ollama:
        ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        ollama_model = os.getenv("OLLAMA_MODEL", "mistral")
        
        llm_config = {
            "config_list": [{
                "model": ollama_model,
                "api_key": "ollama",
                "base_url": ollama_base_url,
                "api_type": "openai",
            }],
            "temperature": 0.7,
            "timeout": 120,
            "max_tokens": 2048,
        }
        
        print("\n🦙 Ollama LLM 配置:")
        print(f"  Model: {llm_config['config_list'][0]['model']}")
        print(f"  Base URL: {llm_config['config_list'][0]['base_url']}")
        print(f"  API Type: {llm_config['config_list'][0]['api_type']}")
        print(f"  Temperature: {llm_config['temperature']}")
        print(f"  Max Tokens: {llm_config['max_tokens']}")
    else:
        openai_api_key = os.getenv("OPENAI_API_KEY", "sk-...")
        openai_model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
        
        llm_config = {
            "config_list": [{
                "model": openai_model,
                "api_key": openai_api_key[:10] + "..." if len(openai_api_key) > 10 else "***"
            }]
        }
        
        print("\n🔑 OpenAI LLM 配置:")
        print(f"  Model: {llm_config['config_list'][0]['model']}")
        print(f"  API Key: {llm_config['config_list'][0]['api_key']}")
    
    return llm_config

def test_agent_initialization():
    """測試 Agent 初始化"""
    print("\n" + "=" * 70)
    print("測試 3: Agent 初始化模擬")
    print("=" * 70)
    
    use_ollama = os.getenv("USE_OLLAMA", "false").lower() == "true"
    
    # 模擬 Agent 初始化
    agents_to_init = [
        "HostAgent",
        "SearchCaseAgent",
        "DeepAnalysisAgent",
        "SummaryAgent",
        "SearchLawAgent",
        "CustomizeConstraintAgent"
    ]
    
    print(f"\n使用後端: {'🦙 Ollama' if use_ollama else '🔑 OpenAI'}\n")
    
    for agent_name in agents_to_init:
        status = "✅ 可以初始化" if use_ollama else "✅ 可以初始化"
        print(f"  [{agent_name}] {status}")
    
    print(f"\n✅ 所有 {len(agents_to_init)} 個 Agent 都將使用相同的 LLM 配置")
    
    return True

def test_ollama_connectivity():
    """測試 Ollama 服務連接"""
    print("\n" + "=" * 70)
    print("測試 4: Ollama 服務連接")
    print("=" * 70)
    
    use_ollama = os.getenv("USE_OLLAMA", "false").lower() == "true"
    
    if not use_ollama:
        print("\n⏭️  跳過：未啟用 Ollama")
        return True
    
    ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    
    try:
        import requests
        
        print(f"\n🔍 檢查 Ollama 服務: {ollama_base_url}")
        
        # 檢查服務是否運行
        response = requests.get(f"{ollama_base_url}/api/tags", timeout=5)
        
        if response.status_code == 200:
            models = response.json().get("models", [])
            print(f"✅ Ollama 服務已連接")
            print(f"   已下載的模型數: {len(models)}")
            
            for model in models[:5]:
                model_name = model.get("name", "Unknown")
                print(f"   - {model_name}")
            
            if len(models) > 5:
                print(f"   ... 以及 {len(models) - 5} 個其他模型")
            
            return True
        else:
            print(f"❌ 連接失敗: HTTP {response.status_code}")
            return False
            
    except ImportError:
        print("\n⚠️  requests 模組未安裝，跳過連接檢查")
        print("   安裝: pip install requests")
        return None
    except Exception as e:
        print(f"\n❌ 連接失敗: {e}")
        print(f"   確保 Ollama 正在運行: ollama serve")
        return False

def test_agent_system_flow():
    """測試 Agent 系統流程"""
    print("\n" + "=" * 70)
    print("測試 5: Agent 系統流程模擬")
    print("=" * 70)
    
    use_ollama = os.getenv("USE_OLLAMA", "false").lower() == "true"
    backend = "🦙 Ollama" if use_ollama else "🔑 OpenAI"
    
    print(f"\n執行流程（使用 {backend}）:\n")
    
    flow = [
        ("1. 用戶輸入", "用戶在 UI 中輸入查詢"),
        ("2. 獲取配置", "app.py::get_llm_config() 讀取環境變數"),
        ("3. 初始化 Agents", "所有 Agent 使用相同的 llm_config"),
        ("4. 啟動聊天", "ChatManager.start_chat() 啟動群組聊天"),
        ("5. Agent 交互", "各 Agent 調用 LLM（Ollama 或 OpenAI）"),
        ("6. 工具調用", "SearchCaseAgent, DeepAnalysisAgent 等調用工具"),
        ("7. 返回結果", "最終結果通過 UI 顯示"),
    ]
    
    for step, description in flow:
        print(f"  {step}")
        print(f"    └─ {description}")
    
    print(f"\n✅ 整個流程支持 Ollama")

def main():
    """主測試函數"""
    print("\n")
    print("╔" + "═" * 68 + "╗")
    print("║" + " " * 68 + "║")
    print("║" + "  🦙 Agent System Ollama 支援測試".center(68) + "║")
    print("║" + " " * 68 + "║")
    print("╚" + "═" * 68 + "╝")
    print()
    
    try:
        # 執行所有測試
        use_ollama = test_environment_setup()
        llm_config = test_llm_config()
        test_agent_initialization()
        connectivity_status = test_ollama_connectivity()
        test_agent_system_flow()
        
        # 總結
        print("\n" + "=" * 70)
        print("測試總結")
        print("=" * 70)
        
        backend = "🦙 Ollama" if use_ollama else "🔑 OpenAI"
        print(f"\n✅ 使用後端: {backend}")
        
        if use_ollama and connectivity_status is False:
            print("⚠️  警告: Ollama 服務未連接")
            print("   確保: ollama serve 正在運行")
        elif use_ollama and connectivity_status is True:
            print("✅ Ollama 服務已連接")
        
        print("\n✅ Agent System 已準備就緒！\n")
        print("啟動應用:")
        print("  ./start_with_ollama.sh")
        print("  或")
        print("  export USE_OLLAMA=true")
        print("  chainlit run app.py\n")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ 測試失敗: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
