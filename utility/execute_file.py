import os
import subprocess
import locale
from typing import Dict, Union


def execute_python_file(filename: str) -> Dict[str, Union[bool, str]]:
    """
    執行指定的 Python 檔案
    
    Args:
        filename: 要執行的檔案名稱 (例如: "case_case_0_code.py")
    
    Returns:
        包含執行結果的字典
    """
    try:
        # 檢查檔案是否存在
        work_dir = os.path.abspath("code_execution")
        filepath = os.path.join(work_dir, filename)
        
        if not os.path.exists(filepath):
            return {
                "success": False,
                "error": f"檔案不存在: {filename}",
                "stdout": "",
                "stderr": f"File not found: {filepath}"
            }
        
        print(f"[CodeExecutor] 開始執行檔案: {filename}")
        
        # 執行 Python 檔案
        result = subprocess.run(
            ['python', filename],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding=locale.getpreferredencoding(),
            cwd=work_dir,  # 設定工作目錄
            timeout=30  # 30 秒超時
        )
        
        stdout = result.stdout or ""
        stderr = result.stderr or ""
        
        # 判斷是否成功
        success = result.returncode == 0
        
        print(f"[CodeExecutor] 執行完成 - 返回碼: {result.returncode}")
        
        # 格式化輸出
        formatted_output = f"""
# 程式執行結果

## 📁 執行檔案
`{filename}`

## 📊 執行狀態
{'✅ 成功' if success else '❌ 失敗'} (返回碼: {result.returncode})

## 📤 標準輸出
```
{stdout if stdout else '(無輸出)'}
```

## ⚠️ 錯誤輸出
```
{stderr if stderr else '(無錯誤)'}
```
"""
        
        return {
            "success": success,
            "returncode": result.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "formatted_output": formatted_output,
            "filename": filename
        }
        
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": "執行超時 (超過 30 秒)",
            "stdout": "",
            "stderr": "Execution timeout",
            "formatted_output": f"❌ 執行檔案 `{filename}` 超時"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "stdout": "",
            "stderr": str(e),
            "formatted_output": f"❌ 執行檔案 `{filename}` 時發生錯誤: {str(e)}"
        }


def list_available_code_files() -> Dict[str, Union[bool, list]]:
    """
    列出 code_execution 目錄中所有可用的程式碼檔案
    
    Returns:
        包含檔案列表的字典
    """
    try:
        work_dir = os.path.abspath("code_execution")
        
        if not os.path.exists(work_dir):
            os.makedirs(work_dir)
            return {
                "success": True,
                "files": [],
                "message": "code_execution 目錄已建立，但尚無檔案"
            }
        
        # 列出所有 Python 檔案
        all_files = os.listdir(work_dir)
        py_files = [f for f in all_files if f.endswith('.py')]
        
        return {
            "success": True,
            "files": py_files,
            "count": len(py_files),
            "message": f"找到 {len(py_files)} 個 Python 檔案"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "files": []
        }