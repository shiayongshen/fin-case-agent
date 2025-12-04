"""
API Key Settings Management
這個文件提供 API Key 的保存和加載功能（純 Python，無 Chainlit 依賴）
"""

import os
import json
from pathlib import Path
from typing import Optional


# 全局 API Key 配置文件位置
CONFIG_FILE = Path.home() / ".uicompliance" / "config.json"
CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)


def load_config() -> dict:
    """加載配置文件"""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"[Config] 加載配置失敗: {e}")
    return {}


def save_config(config: dict) -> bool:
    """保存配置文件"""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        # 設置文件權限為 600（僅所有者可讀寫）
        os.chmod(CONFIG_FILE, 0o600)
        return True
    except Exception as e:
        print(f"[Config] 保存配置失敗: {e}")
        return False


def get_global_api_key() -> Optional[str]:
    """
    獲取全局 API Key
    優先順序：環境變數 > 配置文件 > None
    """
    # 1. 環境變數優先
    env_key = os.getenv("OPENAI_API_KEY")
    if env_key and env_key.startswith("sk-"):
        return env_key
    
    # 2. 配置文件
    config = load_config()
    api_key = config.get("api_key")
    if api_key and api_key.startswith("sk-"):
        return api_key
    
    # 3. 都沒有，返回 None
    return None


def set_global_api_key(api_key: str) -> bool:
    """設置全局 API Key 到配置文件"""
    config = load_config()
    config["api_key"] = api_key
    if save_config(config):
        os.environ["OPENAI_API_KEY"] = api_key
        return True
    return False
