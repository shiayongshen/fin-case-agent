import sys
import os

# 支持作為腳本直接運行或作為模塊導入
try:
    from .search_deep_laws import LegalSearchEngine
except ImportError:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from search_deep_laws import LegalSearchEngine

from chromadb import Client
from chromadb.config import Settings
from chromadb.utils import embedding_functions
import torch
from FlagEmbedding import FlagReranker
from dotenv import load_dotenv
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
COLLECTION_NAME = "legal_cases_v2024"  # 與 embed_cases_to_chroma.py 保持一致
def initialize_reranker():
    """初始化 reranker，自動檢測 CUDA/MPS 可用性"""
    if torch.cuda.is_available():
        device = "cuda"
        use_fp16 = True
        print(f"✅ 檢測到 CUDA GPU: {torch.cuda.get_device_name(0)}")
    elif torch.backends.mps.is_available():
        device = "mps"
        use_fp16 = False  # MPS 目前對 FP16 支援不穩定
        print("🍎 檢測到 Apple MPS GPU，加速模式啟用")
    else:
        device = "cpu"
        use_fp16 = False
        print("⚠️ 未檢測到 GPU，使用 CPU 模式")

    reranker = FlagReranker(
        "BAAI/bge-reranker-v2-m3",
        use_fp16=use_fp16,
        device=device
    )
    return reranker
try:
    legal_search_engine = LegalSearchEngine()
    legal_search_available = True
except Exception as e:
    print(f"法條搜索引擎初始化失敗: {e}")
    legal_search_available = False

def legal_article_search(query: str, top_k: int = 5, rerank_top_n: int = 3, hybrid_alpha: float = 0.5) -> str:
    """法條搜索功能"""
    if not legal_search_available:
        return "法條搜索引擎未正確初始化，請檢查資料庫配置。"
    
    try:
        legal_search_engine.hybrid_alpha = hybrid_alpha
        results = legal_search_engine.search(
            query=query, 
            top_k=top_k, 
            rerank_top_n=rerank_top_n
        )
        
        if not results:
            return "未找到相關法條。"
        
        formatted_output = f"# 法條查詢結果\n\n**查詢：** {query}\n\n"
        
        for i, result in enumerate(results):
            metadata = result.get("metadata", {})
            law_name = metadata.get("法律名稱", "未知法律")
            article = metadata.get("條", "未知條款")
            score = result.get("score", 0)
            
            formatted_output += f"## 結果 {i+1}\n"
            formatted_output += f"**相關度：** {score:.3f}\n\n"
            formatted_output += f"**法律：** {law_name}\n\n"
            formatted_output += f"**條文：** {article}\n\n"
            formatted_output += f"**內容：**\n```\n{result['content']}\n```\n\n---\n\n"
        
        return formatted_output
        
    except Exception as e:
        return f"搜索時發生錯誤：{str(e)}"


def search_and_rerank(query: str, top_k=1):
    """
    搜索並重排結果
    
    Args:
        query: 搜索查詢
        top_k: 返回的結果數量
    
    Returns:
        包含排序後的文檔、metadata 和 ID 的字典
    """
    reranker = initialize_reranker()
    collection = get_chroma_collection()
    
    # 獲取前 top_k * 2 個結果用於重排
    search_results = collection.query(
        query_texts=[query],
        n_results=top_k * 2
    )
    
    documents = search_results['documents'][0] if search_results['documents'] else []
    metadatas = search_results['metadatas'][0] if search_results['metadatas'] else []
    ids = search_results['ids'][0] if search_results['ids'] else []
    
    if not documents:
        return {
            'ranked_documents': [], 
            'ranked_metadatas': [], 
            'ids': [],
            'extracted_codes': []
        }
    
    # 使用 reranker 計算相關性分數
    ranking_scores = []
    for doc in documents:
        # FlagReranker 需要傳入 (query, document) 元組對
        try:
            score = reranker.compute_score([(query, doc)])
            # compute_score 返回一個列表，取第一個元素
            if isinstance(score, (list, tuple)):
                ranking_scores.append(float(score[0]))
            else:
                ranking_scores.append(float(score))
        except Exception as e:
            print(f"⚠️  計算分數失敗: {e}")
            ranking_scores.append(0.0)
    
    # 按分數排序
    indexed_scores = list(enumerate(ranking_scores))
    sorted_indexed_scores = sorted(indexed_scores, key=lambda x: x[1], reverse=True)
    
    # 取前 top_k 個結果
    ranked_indices = [idx for idx, _ in sorted_indexed_scores[:top_k]]
    
    ranked_documents = [documents[i] for i in ranked_indices]
    ranked_metadatas = [metadatas[i] for i in ranked_indices]
    ranked_ids = [ids[i] for i in ranked_indices]
    ranked_scores = [ranking_scores[i] for i in ranked_indices]
    
    # 提取代碼（如果 metadata 中有 z3code）
    extracted_codes = []
    for i, metadata in enumerate(ranked_metadatas):
        if metadata and 'z3code' in metadata:
            code = metadata.get('z3code', '')
            if code and code.strip():
                # 為每個程式碼片段創建檔案
                filename = f"case_{ranked_ids[i]}_code.py"
                filepath = os.path.join("code_execution", filename)
                
                # 確保目錄存在
                os.makedirs("code_execution", exist_ok=True)
                
                # 寫入程式碼檔案
                try:
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(code)
                    
                    extracted_codes.append({
                        'case_id': ranked_ids[i],
                        'filename': filename,
                        'filepath': filepath,
                        'code': code
                    })
                except Exception as e:
                    print(f"⚠️  寫入代碼文件失敗 ({filename}): {e}")
    print(ranked_ids)
    return {
        'ranked_documents': ranked_documents, 
        'ranked_metadatas': ranked_metadatas, 
        'ids': ranked_ids,
        'scores': ranked_scores,
        'extracted_codes': extracted_codes
    }
    
def get_chroma_collection():
    """獲取或創建 Chroma 集合
    使用 OpenAI embedding 函數 (text-embedding-ada-002)
    """
    client = Client(Settings(
        persist_directory="./chroma_db",
        is_persistent=True
    ))
    
    embedding_func = embedding_functions.OpenAIEmbeddingFunction(
        api_key=OPENAI_API_KEY,
        model_name="text-embedding-ada-002"
    )
    
    try:
        # 嘗試獲取現有集合
        print(f"[連接] 嘗試獲取集合: {COLLECTION_NAME}")
        collection = client.get_collection(
            name=COLLECTION_NAME,
            embedding_function=embedding_func
        )
        print(f"✅ 已獲取集合: {COLLECTION_NAME} ({collection.count()} 個文檔)")
        return collection
    except Exception as get_error:
        print(f"⚠️  無法獲取現有集合: {get_error}")
        print(f"   嘗試創建新集合: {COLLECTION_NAME}")
        try:
            # 創建新集合（使用 OpenAI embedding）
            collection = client.get_or_create_collection(
                name=COLLECTION_NAME,
                embedding_function=embedding_func,
                metadata={"hnsw:space": "cosine"}
            )
            print(f"✅ 已創建新集合: {COLLECTION_NAME}")
            return collection
        except Exception as create_error:
            print(f"❌ 創建集合失敗: {create_error}")
            # 最後的降級方案：嘗試無 embedding function 獲取
            try:
                collection = client.get_collection(name=COLLECTION_NAME)
                print(f"✅ 已獲取集合（無 embedding function）: {COLLECTION_NAME}")
                return collection
            except Exception as fallback_error:
                print(f"❌ 所有方案都失敗: {fallback_error}")
                return None