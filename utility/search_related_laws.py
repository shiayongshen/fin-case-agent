import os
import json
import argparse
from typing import List, Dict, Any, Tuple
import logging
import re
import numpy as np
from rank_bm25 import BM25Okapi
# 向量資料庫
from chromadb import Client, Settings
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
from FlagEmbedding import FlagReranker
from dotenv import load_dotenv
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# 設定日誌
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 安全地讀取API金鑰
def get_openai_api_key():
    api_key = OPENAI_API_KEY
    return api_key

class LegalSearchEngine:
    def __init__(self, 
                 persist_directory: str = "./chroma_db",
                 collection_name: str = "law_articles_csv",
                 reranker_model: str = "BAAI/bge-reranker-v2-m3",
                 use_fp16: bool = False,
                 hybrid_alpha: float = 0.8):  # 混合搜尋權重
        """
        初始化法律搜尋引擎
        
        Args:
            persist_directory: Chroma資料庫存儲位置
            collection_name: 集合名稱
            reranker_model: 重排序模型名稱
            use_fp16: 是否使用FP16精度
            hybrid_alpha: 混合搜尋中向量搜尋的權重 (0-1)，BM25的權重為 1-hybrid_alpha
        """
        # 初始化Chroma客戶端
        self.client = Client(Settings(
            persist_directory=persist_directory,
            is_persistent=True
        ))
        
        # 混合搜尋參數
        self.hybrid_alpha = hybrid_alpha
        
        # 初始化OpenAI嵌入函數
        self.embedding_function = OpenAIEmbeddingFunction(
            api_key=get_openai_api_key(),
            model_name="text-embedding-ada-002"
        )
        
        # 獲取集合
        try:
            self.collection = self.client.get_collection(
                collection_name, 
                embedding_function=self.embedding_function
            )
            logger.info(f"成功連接到集合: {collection_name}")
            
            # 讀取所有文件用於BM25
            self.initialize_bm25()
            
        except Exception as e:
            logger.error(f"連接集合失敗: {str(e)}")
            raise
        
        # 初始化重排序模型
        try:
            import torch
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
            self.reranker = FlagReranker(reranker_model, use_fp16=use_fp16, device=device)
            logger.info(f"成功載入重排序模型: {reranker_model} 到設備: {device}")
        except Exception as e:
            logger.error(f"載入重排序模型失敗: {str(e)}")
            raise
    
    def initialize_bm25(self):
        """初始化BM25搜尋索引"""
        try:
            # 獲取全部文檔
            result = self.collection.get()
            
            if not result['documents']:
                logger.warning("未找到文檔，無法初始化BM25")
                return
                
            self.all_documents = result['documents']
            self.all_metadatas = result['metadatas']
            self.all_ids = result['ids']
            
            # 為BM25準備文檔 - 分詞
            tokenized_docs = []
            for doc in self.all_documents:
                # 簡單的分詞，可依需求調整
                tokens = self.tokenize(doc)
                tokenized_docs.append(tokens)
                
            # 創建BM25索引
            self.bm25 = BM25Okapi(tokenized_docs)
            logger.info(f"成功初始化BM25索引，共 {len(tokenized_docs)} 個文檔")
            
        except Exception as e:
            logger.error(f"初始化BM25索引失敗: {str(e)}")
            # 設置為None，後續使用時再檢查
            self.bm25 = None
    
    def tokenize(self, text: str) -> List[str]:
        """簡單的中文分詞處理"""
        # 清理文本（去除標點符號）
        text = re.sub(r'[^\w\s]', ' ', text)
        # 針對中文特性，我們可以使用字符級分詞
        # 這裡使用簡單的空格分詞，實際應用可能需要結巴分詞等工具
        tokens = text.split()
        # 確保字符級切分
        char_tokens = []
        for token in tokens:
            if len(token) > 1:  # 對於多字符詞，拆分成單字符
                for char in token:
                    char_tokens.append(char)
            else:
                char_tokens.append(token)
        return char_tokens
    
    def bm25_search(self, query: str, top_k: int = 15) -> List[Dict[str, Any]]:
        """使用BM25進行搜尋"""
        if self.bm25 is None:
            logger.warning("BM25索引未初始化，僅使用向量搜尋")
            return []
            
        # 查詢分詞
        query_tokens = self.tokenize(query)
        
        # BM25搜尋
        bm25_scores = self.bm25.get_scores(query_tokens)
        
        # 對分數進行排序
        top_indices = np.argsort(bm25_scores)[::-1][:top_k]
        
        # 收集結果
        results = []
        for idx in top_indices:
            if bm25_scores[idx] > 0:  # 僅返回有匹配的結果
                results.append({
                    "id": self.all_ids[idx],
                    "content": self.all_documents[idx],
                    "metadata": self.all_metadatas[idx],
                    "score": float(bm25_scores[idx]),  # numpy float轉為Python float
                    "source": "bm25"
                })
                
        logger.info(f"BM25搜尋找到 {len(results)} 個結果")
        return results

    def vector_search(self, query: str, top_k: int = 15) -> List[Dict[str, Any]]:
        """使用向量搜尋"""
        try:
            search_results = self.collection.query(
                query_texts=[query],
                n_results=top_k
            )
            
            documents = search_results['documents'][0]
            metadatas = search_results['metadatas'][0]
            ids = search_results['ids'][0]
            
            if not documents:
                logger.warning("未找到相關結果")
                return []
                
            logger.info(f"向量搜尋找到 {len(documents)} 個結果")
            
            results = []
            for i in range(len(documents)):
                results.append({
                    "id": ids[i],
                    "content": documents[i],
                    "metadata": metadatas[i],
                    "score": 1.0,  # 初始分數，稍後會被重新排序
                    "source": "vector"
                })
                
            return results
            
        except Exception as e:
            logger.error(f"向量搜尋過程出錯: {str(e)}")
            return []

    def search(self, query: str, top_k: int = 15, rerank_top_n: int = 5) -> List[Dict[str, Any]]:
        """
        混合搜尋結合BM25與向量搜尋
        """
        logger.info(f"執行混合搜尋: {query}")
        
        # 執行BM25搜尋
        bm25_results = self.bm25_search(query, top_k)
        
        # 執行向量搜尋
        vector_results = self.vector_search(query, top_k)
        
        # 合併結果
        combined_results = {}
        
        # 添加BM25結果，歸一化分數
        if bm25_results:
            max_bm25_score = max([r["score"] for r in bm25_results]) if bm25_results else 1.0
            for r in bm25_results:
                doc_id = r["id"]
                norm_score = r["score"] / max_bm25_score
                combined_results[doc_id] = {
                    "id": doc_id,
                    "content": r["content"],
                    "metadata": r["metadata"],
                    "bm25_score": norm_score,
                    "vector_score": 0.0,
                    "sources": ["bm25"]
                }
        
        # 添加向量搜尋結果
        for r in vector_results:
            doc_id = r["id"]
            if doc_id in combined_results:
                combined_results[doc_id]["sources"].append("vector")
                combined_results[doc_id]["vector_score"] = 1.0  # 暫時設為1.0，後續會重新排序
            else:
                combined_results[doc_id] = {
                    "id": doc_id,
                    "content": r["content"],
                    "metadata": r["metadata"],
                    "bm25_score": 0.0,
                    "vector_score": 1.0,  # 暫時設為1.0，後續會重新排序
                    "sources": ["vector"]
                }
        
        # 轉換為列表
        all_results = list(combined_results.values())
        
        # 使用重排序模型重新排序
        if all_results:
            try:
                # 獲取文檔內容
                docs = [r["content"] for r in all_results]
                
                # 使用重排序模型計算相關性得分
                ranking_scores = []
                for doc in docs:
                    score = self.reranker.compute_score([query, doc])
                    if isinstance(score, list):
                        score = score[0] if score else 0.0
                    ranking_scores.append(score)
                
                # 更新向量分數
                for i, score in enumerate(ranking_scores):
                    all_results[i]["vector_score"] = score
                
                # 計算混合得分
                for r in all_results:
                    r["final_score"] = self.hybrid_alpha * r["vector_score"] + \
                                      (1 - self.hybrid_alpha) * r["bm25_score"]
                
                # 按混合分數排序
                all_results.sort(key=lambda x: x["final_score"], reverse=True)
                
                # 截取前N個結果
                all_results = all_results[:rerank_top_n]
                
                # 為返回結果標準化
                for i, r in enumerate(all_results):
                    r["rank"] = i + 1
                    r["score"] = r["final_score"]  # 使用最終得分作為score
                
                logger.info(f"完成混合搜尋與重排序，返回前 {len(all_results)} 個結果")
                
            except Exception as e:
                logger.error(f"重排序過程出錯: {str(e)}")
                # 簡單地按BM25與向量搜尋來源排序
                for r in all_results:
                    sources = r["sources"]
                    r["score"] = 1.0 if "bm25" in sources and "vector" in sources else \
                                0.8 if "vector" in sources else \
                                0.6 if "bm25" in sources else 0.0
                
                # 排序並截取
                all_results.sort(key=lambda x: x["score"], reverse=True)
                all_results = all_results[:rerank_top_n]
        
        return all_results
    
    def get_related_laws(self, query: str, top_k: int = 10, rerank_top_n: int = 5) -> Tuple[List[Dict], List[Dict]]:
        results = self.search(query, top_k, rerank_top_n)
        
        # 區分直接相關和間接相關法條
        direct_relevant = []
        indirectly_relevant = []
        
        for result in results:
            score = result["score"]
            if isinstance(score, list):
                score = score[0] if score else 0.0
            
            # 得分高於閾值的視為直接相關
            if score > 0.75:
                direct_relevant.append(result)
            else:
                indirectly_relevant.append(result)
        
        return direct_relevant, indirectly_relevant

    def format_results(self, results: List[Dict]) -> str:
        """格式化搜尋結果為易讀的文字"""
        formatted = []
        
        for i, result in enumerate(results):
            metadata = result["metadata"]
            law_name = metadata.get("法律名稱", "未知法律")
            article = metadata.get("條", "未知條款")
            
            # 獲取搜尋來源信息
            sources = result.get("sources", [])
            source_info = f"[來源: {', '.join(sources)}]" if sources else ""
            
            formatted.append(f"結果 {i+1} [相關度: {result['score']:.2f}] {source_info}")
            formatted.append(f"法律: {law_name} 第 {article} 條")
            formatted.append(f"內容:\n{result['content']}\n")
            formatted.append("-" * 80)
        
        return "\n".join(formatted)


def main():
    parser = argparse.ArgumentParser(description='法律文本向量搜尋工具')
    parser.add_argument('query', nargs='?', default='', help='搜尋查詢')
    parser.add_argument('--top-k', type=int, default=15, help='初始檢索的結果數量')
    parser.add_argument('--rerank-top-n', type=int, default=5, help='重排序後返回的結果數量')
    parser.add_argument('--collection', default='law_articles', help='集合名稱')
    parser.add_argument('--persist-dir', default='./chroma_db', help='Chroma資料庫目錄')
    parser.add_argument('--output', help='輸出檔案路徑')
    
    args = parser.parse_args()
    
    # 初始化搜尋引擎
    try:
        search_engine = LegalSearchEngine(
            persist_directory=args.persist_dir,
            collection_name=args.collection
        )
        
        # 如果沒有提供查詢，則進入互動模式
        if not args.query:
            print("歡迎使用法律文本向量搜尋工具")
            print("請輸入您的查詢 (輸入 'q' 退出):")
            
            while True:
                query = input("> ")
                if query.lower() == 'q':
                    break
                    
                direct_relevant, indirectly_relevant = search_engine.get_related_laws(
                    query, args.top_k, args.rerank_top_n
                )
                
                print("\n直接相關法條:")
                print(search_engine.format_results(direct_relevant))
                
                if indirectly_relevant:
                    print("\n間接相關法條:")
                    print(search_engine.format_results(indirectly_relevant))
                
                print("\n請輸入新的查詢 (輸入 'q' 退出):")
        else:
            # 直接執行單次查詢
            direct_relevant, indirectly_relevant = search_engine.get_related_laws(
                args.query, args.top_k, args.rerank_top_n
            )
            
            results = {
                "query": args.query,
                "direct_relevant": direct_relevant,
                "indirectly_relevant": indirectly_relevant
            }
            
            # 輸出結果
            if args.output:
                with open(args.output, 'w', encoding='utf-8') as f:
                    json.dump(results, f, ensure_ascii=False, indent=2)
                print(f"結果已保存至 {args.output}")
            else:
                print("\n直接相關法條:")
                print(search_engine.format_results(direct_relevant))
                
                if indirectly_relevant:
                    print("\n間接相關法條:")
                    print(search_engine.format_results(indirectly_relevant))
    
    except Exception as e:
        logger.error(f"執行過程中出錯: {str(e)}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())