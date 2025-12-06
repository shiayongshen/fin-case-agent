import os
import pdfplumber
import re
import json
import pandas as pd

def extract_text_with_pdfplumber(pdf_file):
    """
    使用 pdfplumber 從 PDF 提取純文本
    """
    text = ""
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            # 若某頁返回 None 則跳過
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return text

def split_articles_and_clauses_with_merge(text):
    """
    將文本分割為條文與款，過濾掉非條文部分（如「第 四 節」），並清理多餘空白
    """
    articles = {}
    current_article = None
    current_clause = None

    lines = text.split("\n")
    for line in lines:
        line = line.strip()  # 去除行首和行尾空白
        line = re.sub(r"\s+", " ", line)  # 將多個空格替換為單一空格
        if not line:  # 跳過空行
            continue

        # 排除節的標題（如「第 四 節」或「某某章節」）
        if re.match(r"^第\s*[一二三四五六七八九十]+\s*節", line):
            continue

        # 匹配條文（支持 107-1 條這種格式）
        article_match = re.match(r"第\s*([\d\-]+)\s*條", line)
        if article_match:
            current_article = article_match.group(1)
            articles[current_article] = {"title": line.strip(), "clauses": [], "content": ""}
            current_clause = None
        elif current_article:
            # 匹配款（支持 1. 或 1、等格式）
            clause_match = re.match(r"^\s*(\d+)[\.\、]?\s*(.*)", line)
            if clause_match:
                clause_text = clause_match.group(2)
                articles[current_article]["clauses"].append(clause_text.strip())
                current_clause = clause_text
            else:
                # 如果是條文或款的延續行，合併到當前內容
                if current_clause:
                    # 合併到當前款
                    articles[current_article]["clauses"][-1] += line
                    articles[current_article]["clauses"][-1] = re.sub(r"\s+", "", articles[current_article]["clauses"][-1])
                else:
                    # 合併到條文描述
                    articles[current_article]["content"] += line
                    articles[current_article]["content"] = re.sub(r"\s+", "", articles[current_article]["content"])
    return articles

def save_to_json(data, output_file):
    """
    將結構化數據保存為 JSON
    """
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def save_to_csv(data, output_file):
    """
    將結構化數據保存為 CSV
    """
    rows = []
    for article_id, content in data.items():
        title = content["title"]
        clauses = content.get("clauses", [])
        full_content = content.get("content", "")
        rows.append({"條文": title, "款列表": " | ".join(clauses), "全文": full_content})
    df = pd.DataFrame(rows)
    df.to_csv(output_file, index=False, encoding="utf-8")

def process_pdf_file(pdf_path):
    """
    處理單個 PDF 文件：提取文本、分割條文及款
    """
    text = extract_text_with_pdfplumber(pdf_path)
    articles = split_articles_and_clauses_with_merge(text)
    return articles

# 指定存放 PDF 的資料夾路徑
# 獲取當前腳本所在目錄
current_dir = os.path.dirname(os.path.abspath(__file__))
pdf_folder = os.path.join(current_dir, "article")
output_folder = os.path.join(current_dir, "processed_data")

# 檢查 PDF 資料夾是否存在
if not os.path.exists(pdf_folder):
    print(f"錯誤：找不到資料夾 {pdf_folder}")
    exit(1)

# 如果輸出資料夾不存在，則建立
if not os.path.exists(output_folder):
    os.makedirs(output_folder)
    print(f"✅ 已建立輸出資料夾: {output_folder}")

# 遍歷資料夾中所有的 PDF 文件
for file_name in os.listdir(pdf_folder):
    if file_name.lower().endswith(".pdf"):
        pdf_path = os.path.join(pdf_folder, file_name)
        articles = process_pdf_file(pdf_path)
        
        # 根據 PDF 檔名（不含副檔名）生成輸出文件名稱
        base_name = os.path.splitext(file_name)[0]
        output_json = os.path.join(output_folder, f"{base_name}.json")
        output_csv = os.path.join(output_folder, f"{base_name}.csv")
        
        save_to_json(articles, output_json)
        save_to_csv(articles, output_csv)
        
        print(f"✅ 已將 {file_name} 的數據保存為")
        print(f"   JSON: {output_json}")
        print(f"   CSV:  {output_csv}")
