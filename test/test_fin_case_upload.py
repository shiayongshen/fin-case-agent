#!/usr/bin/env python3
"""
測試報告上傳到 FinCase API 的腳本
"""

import asyncio
import httpx
import os
from datetime import datetime

# 從環境變數讀取 API BASE URL，預設為本地測試
BASE_URL = os.getenv("REPORT_API_BASE", "http://118.163.52.174:15678/api")

async def test_upload_report_fin_case():
    """測試上傳報告到 FinCase API"""
    
    # 生成測試報告
    test_report = f"""# 測試報告

## 報告生成時間
{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## 報告內容
這是一份測試報告，用來驗證 FinCase API 上傳功能是否正常工作。

### 測試信息
- API Base URL: {BASE_URL}
- 報告類型: FinCase
- 測試狀態: 進行中

## 結論
報告上傳測試成功！
"""
    
    url = f"{BASE_URL}/report/generated/fin-case"
    payload = {
        "report": test_report,
        "title": f"測試報告 - {datetime.now().strftime('%Y%m%d_%H%M%S')}"
    }
    
    print(f"[TEST] 開始上傳測試報告到: {url}")
    print(f"[TEST] 報告標題: {payload['title']}")
    print("-" * 60)
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, timeout=30.0)
            response.raise_for_status()
            result = response.json()
            
            print("[SUCCESS] ✅ 報告上傳成功！")
            print(f"[RESPONSE] {result}")
            print("-" * 60)
            
            if result.get("status") == "success":
                print(f"✨ 報告 ID: {result.get('reportId')}")
                print(f"📝 訊息: {result.get('msg')}")
            else:
                print(f"⚠️  上傳返回異常: {result}")
            
            return result
            
    except httpx.HTTPStatusError as e:
        print(f"[ERROR] ❌ HTTP 錯誤: {e.response.status_code}")
        print(f"[ERROR] 回應: {e.response.text}")
        return None
    except Exception as e:
        print(f"[ERROR] ❌ 上傳失敗: {e}")
        return None

async def test_upload_with_custom_title():
    """測試上傳報告並設定自訂標題"""
    
    test_report = """# 自訂標題報告

## 概述
這是一份帶有自訂標題的測試報告。

## 功能
- ✓ 報告生成
- ✓ 自訂標題
- ✓ API 上傳
"""
    
    url = f"{BASE_URL}/report/generated/fin-case"
    payload = {
        "report": test_report,
        "title": "我的自訂報告標題"
    }
    
    print("\n[TEST 2] 測試帶自訂標題的報告上傳")
    print(f"[TEST] 目標 URL: {url}")
    print(f"[TEST] 報告標題: {payload['title']}")
    print("-" * 60)
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, timeout=30.0)
            response.raise_for_status()
            result = response.json()
            
            print("[SUCCESS] ✅ 自訂標題報告上傳成功！")
            print(f"[RESPONSE] {result}")
            
            return result
            
    except Exception as e:
        print(f"[ERROR] ❌ 上傳失敗: {e}")
        return None

async def main():
    """主測試函數"""
    print("=" * 60)
    print("FinCase 報告上傳 API 測試")
    print("=" * 60)
    print(f"API Base URL: {BASE_URL}\n")
    
    # 測試 1: 基本上傳
    result1 = await test_upload_report_fin_case()
    
    # 測試 2: 自訂標題上傳
    result2 = await test_upload_with_custom_title()
    
    print("\n" + "=" * 60)
    print("測試完成！")
    print("=" * 60)
    
    if result1 and result2:
        print("✨ 所有測試均成功完成！")
    else:
        print("⚠️  部分測試失敗，請檢查 API 連接情況。")

if __name__ == "__main__":
    asyncio.run(main())
