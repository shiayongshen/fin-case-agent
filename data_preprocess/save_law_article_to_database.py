import json
import openai
from chromadb import Client
from chromadb.config import Settings
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
import os
import hashlib
from dotenv import load_dotenv  # 如果使用 .env 文件


load_dotenv()

openai_api_key = os.getenv("OPENAI_API_KEY")
if openai_api_key:
    openai.api_key = openai_api_key
    print("OPENAI_API_KEY is ready")
else:
    print("OPENAI_API_KEY environment variable not found")
    exit(1)  # 無法繼續運行

def generate_hash(text):
    """
    根據給定的文本生成 SHA-256 哈希值。
    """
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

def process_and_store_in_chroma(json_file, chroma_dir, collection_name):
    """
    將 JSON 文件中的條文嵌入存入 Chroma，並使用哈希值作為 ID。
    """
    # 初始化 Chroma 客戶端
    chroma_client = Client(Settings(
        persist_directory=chroma_dir,  # 嵌入存儲目錄
        is_persistent=True
    ))
    embedding_function = OpenAIEmbeddingFunction(
        api_key=openai_api_key, 
        model_name='text-embedding-ada-002'
    )
    
    # 創建或獲取集合
    collection = chroma_client.get_or_create_collection(name=collection_name, embedding_function=embedding_function)

    # 讀取 JSON 文件
    with open(json_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 遍歷條文並生成嵌入
    for article_id, article_data in data.items():
        title = article_data.get("title", "")
        content = article_data.get("content", "").strip()
        clauses = article_data.get("clauses", [])
        # 將條文內容和款合併為一個文本
        full_text = content
        if clauses:
            full_text += "\n" + "\n".join(clauses)

        if full_text.strip():
            print(f"生成嵌入：{title}")
            
            # 生成哈希值作為 ID，可以根據需要選擇使用不同的文本來生成哈希
            unique_text = title + full_text  # 確保基於唯一的內容生成哈希
            hashed_id = generate_hash(unique_text)
            
            # 將數據添加到 Chroma
            collection.add(
                ids=[hashed_id],
                documents=[full_text],
                metadatas=[{"title": f"保險法 {title}"}],
            )
    
    print(f"所有條文嵌入已存入 Chroma 資料庫 {chroma_dir}")

# 主程式
json_file = "insurance_law.json"   # 包含條文的 JSON 文件
chroma_dir = "/Users/vincenthsia/Desktop/AI＿constraint/chroma"  # 嵌入資料存儲目錄
collection_name = "article_1"   # Chroma 集合名稱

process_and_store_in_chroma(json_file, chroma_dir, collection_name)

#prompt:請你結合裁罰情境與下面提供有用的法律條文產生python z3 solver code，並加上繁體中文的註解，並將法律條文用assert_and_track的方式加入Constraint，再將案例的變數放進去裡面求解。
