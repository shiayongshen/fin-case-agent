import os
import pandas as pd
import json
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))  # 若確定可讀取就這樣用

def get_law_clause(law_name, clause_number):
    """
    根據法規名稱與條文編號，擷取對應的法條內容。
    :param law_name: 法規名稱 (對應檔名)
    :param clause_number: 條文編號 (例如 15，代表「第 15 條」)
    :return: 條文內容或錯誤訊息
    """
    file_path = f"{law_name}.csv"  # 檔案路徑
    if not os.path.exists(file_path):
        return f"找不到對應的法規檔案：{law_name}.csv"
    
    df = pd.read_csv(file_path)
    clause_title = f"第 {clause_number} 條"
    
    filtered_df = df[df["條文"] == clause_title]
    if filtered_df.empty:
        return f"{law_name} 中找不到 {clause_title}"
    
    # 合併 款列表 和 全文
    clause_text = ""
    if "款列表" in filtered_df.columns and not pd.isna(filtered_df.iloc[0]["款列表"]):
        clause_text += filtered_df.iloc[0]["款列表"] + "\n"
    if "全文" in filtered_df.columns and not pd.isna(filtered_df.iloc[0]["全文"]):
        clause_text += filtered_df.iloc[0]["全文"]
    
    return clause_text.strip() if clause_text else "條文內容缺失"

import time
from openai import RateLimitError

def analyze_case_with_openai(case_text):
    """
    使用 OpenAI API 分析法律案例，找出相關法規與條文。
    :param case_text: 法律案例描述
    :return: 相關法規及條文的 JSON 格式
    """

    max_retries = 5
    retry_delay = 10
    
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": """你是一個法律專家，請根據輸入的案例，找出相關的法規名稱與條文編號。若為xx法第幾之幾條，則為輸出x-x條，不用管是第幾項，只需要輸出哪一條即可，請你不需要在前面加上```json，請直接輸出，並請你忽略訴願法與行政執行法
                     格式如下：{
                    "法律案例": "案例描述",
                    "相關法規": [
                        {
                        "法規名稱": "某某法",
                        "條文": ["15", "20-1"]
                        },
                        {
                        "法規名稱": "另一個法",
                        "條文": ["3", "7"]
                        }
                    ]}"""},
                    {"role": "user", "content": case_text}
                ],
                temperature=0
            )

            extracted_data = response.choices[0].message.content
            print(extracted_data)
            try:
                return json.loads(extracted_data or "{}")
            except json.JSONDecodeError:
                print("OpenAI 返回的結果無法解析為 JSON，正在重新嘗試...")
                time.sleep(retry_delay)
        except RateLimitError:
            print(f"API 遇到速率限制，等待 {retry_delay} 秒後重試 (第 {attempt+1} 次)...")
            time.sleep(retry_delay)
            retry_delay *= 2
    return {"error": "超過最大重試次數，請稍後再試"}
    
def get_full_law_details(case_text):
    """
    分析案例，並查詢對應的法條完整內容。
    :param case_text: 法律案例描述
    :return: 含有法規條文內容的 JSON
    """
    law_data = analyze_case_with_openai(case_text)
    if "error" in law_data:
        return law_data
    
    law_details = []
    for law in law_data.get("相關法規", []):
        law_name = law["法規名稱"]
        for clause in law["條文"]:
            clause_text = get_law_clause(law_name, clause)
            law_details.append(f"{law_name} 第 {clause} 條: {clause_text}")
    return {
        "法律案例": case_text,
        "相關法條": "\n".join(law_details)
    }


def process_case_json(file_path):
    """
    讀取 JSON 檔案，解析案例並查找相關法條，並將結果存入 CSV 檔案。
    :param file_path: JSON 檔案路徑
    """
    with open(file_path, "r", encoding="utf-8") as file:
        case_data = json.load(file)
    
    results = []
    for case in case_data:
        case_text = case["content"]
        result = get_full_law_details(case_text)
        results.append(result)
    
    output_csv_path = "processed_casesv3.csv"
    df = pd.DataFrame(results)
    df.to_csv(output_csv_path, index=False, encoding="utf-8-sig")
    
    print(f"處理完成，結果已儲存至 {output_csv_path}")

def main():
    """
    主函數，允許使用者選擇處理單一案例或批量處理 JSON，並將結果存入 CSV。
    """
    print("選擇操作模式：1) 單一案例輸入  2) 批量處理 JSON")
    mode = input("請輸入模式編號 (1 或 2)：").strip()
    
    if mode == "1":
        print("請輸入法律案例描述，每次輸入不受字數限制，輸入 'EOF' 送出，'exit' 退出。")
        while True:
            try:
                case_text = ""
                print("請輸入完整的法律案例，按 Enter 送出 (連續輸入多行，輸入 'EOF' 送出)：")
                while True:
                    line = input()
                    if line.strip().lower() == "eof":
                        break
                    case_text += line + "\n"
                
                if not case_text.strip():
                    print("請輸入有效的法律案例描述。")
                    continue
                if case_text.lower().strip() == 'exit':
                    print("程序結束。")
                    break
                
                result = get_full_law_details(case_text)
                print(json.dumps(result, ensure_ascii=False, indent=4))
            except Exception as e:
                print(f"發生錯誤: {e}")
    elif mode == "2":
        json_path = "case.json"
        if os.path.exists(json_path):
            process_case_json(json_path)
        else:
            print(f"找不到檔案: {json_path}")
    else:
        print("無效的輸入，請重新執行程式。")

if __name__ == "__main__":
    main()
