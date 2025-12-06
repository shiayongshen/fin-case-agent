from selenium import webdriver
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup
import requests
import time
import json
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 初始化 Selenium 瀏覽器
driver = webdriver.Chrome()
driver.get("https://www.fsc.gov.tw/ch/home.jsp?id=131&parentpath=0%2C2&mcustomize=")  # 替換為實際目標網址

# 基本 URL 用於處理相對路徑
base_url = "https://www.fsc.gov.tw/ch/"  # 替換為目標網站的基礎 URL

# 用於儲存結果的清單
data_list = []

try:
    while True:
        # 等待頁面加載完成
        time.sleep(2)  # 可根據頁面載入速度調整

        # 獲取當前頁面 HTML
        html = driver.page_source

        # 使用 BeautifulSoup 分析 HTML
        soup = BeautifulSoup(html, "html.parser")

        # 擷取當前頁面的所有連結並使用 requests 進行內容抓取
        for li in soup.find_all("li", {"role": "row"}):
            a_tag = li.find("a")  # 查找 <a> 標籤
            if a_tag and a_tag.get("href"):
                href = a_tag["href"]
                # 處理相對路徑
                full_url = href if href.startswith("http") else base_url + href

                # 使用 requests 獲取詳細頁面的內容
                try:
                    response = requests.get(full_url, verify=False, timeout=10)
                    if response.status_code == 200:
                        detail_soup = BeautifulSoup(response.text, "html.parser")
                        maincontent = detail_soup.find("div", class_="maincontent")  # 找到主內容區域

                        if maincontent:
                            # 提取標題
                            subject = maincontent.find("h3").get_text(strip=True) if maincontent.find("h3") else None

                            # 提取日期
                            date = maincontent.find("div", class_="date").get_text(strip=True) if maincontent.find("div", class_="date") else None

                            # 提取內文
                            page_edit = maincontent.find("div", class_="page-edit")
                            content = page_edit.get_text(separator="\n", strip=True) if page_edit else None

                            # 保存數據為字典
                            data = {
                                "url": full_url,
                                "subject": subject,
                                "date": date,
                                "content": content,
                            }
                            data_list.append(data)
                        else:
                            print(f"主內容未找到: {full_url}")
                    else:
                        print(f"無法訪問: {full_url}，狀態碼: {response.status_code}")
                except Exception as e:
                    print(f"請求失敗: {full_url}，錯誤原因: {e}")

        # 嘗試找到「下一頁」按鈕
        try:
            next_button = driver.find_element(By.CLASS_NAME, "next")  # 根據實際按鈕的 class 名稱
            next_button.click()  # 點擊「下一頁」
        except Exception as e:
            print("找不到下一頁按鈕，爬取完成")
            break

except Exception as e:
    print(f"發生錯誤: {e}")

finally:
    driver.quit()  # 關閉瀏覽器

# 將結果保存為 JSON 文件
with open("output.json", "w", encoding="utf-8") as f:
    json.dump(data_list, f, ensure_ascii=False, indent=4)

print("資料已保存至 output.json")
