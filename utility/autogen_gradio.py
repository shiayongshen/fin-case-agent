import os
import gradio as gr
from typing import List, Dict, Union, Any

from gradio_look import extract_softs_from_code,extract_softs_description_and_varnames
from autogen import *
from search_deep_laws import LegalSearchEngine
from chromadb import Client, Settings
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
from FlagEmbedding import FlagReranker
from autogen.coding import DockerCommandLineCodeExecutor, LocalCommandLineCodeExecutor
from fpdf import FPDF
import os
from datetime import datetime
from src.soft_extractor import extract_softs_from_file
from src.modify_constraint import modify_constraints_api
from dotenv import load_dotenv
from utils import initialize_reranker
import asyncio
from concurrent.futures import ThreadPoolExecutor

load_dotenv()

AUTOGEN_USE_DOCKER = False  
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "your_openai_api_key_here")
OPENAI_MODEL="gpt-4.1-mini"
global extracted_codes
extracted_codes =[]
# 1. Configuration: LLM + Reranker
llm_config = { "config_list": [{ "model": OPENAI_MODEL, "api_key": OPENAI_API_KEY }] }
llm_config_o3 = { "config_list": [{ "model": OPENAI_MODEL, "api_key": OPENAI_API_KEY }] }
reranker = initialize_reranker()

try:
    legal_search_engine = LegalSearchEngine()
    legal_search_available = True
except Exception as e:
    print(f"法條搜索引擎初始化失敗: {e}")
    legal_search_available = False

def get_extracted_codes():
    """獲取已提取的程式碼列表"""
    global extracted_codes
    return extracted_codes

def save_conversation_to_pdf(user_query: str, conversation_output: str) -> str:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # 使用可顯示中文的字型（需先下載 .ttf 檔並放在同目錄）
    font_path = "NotoSansTC-VariableFont_wght.ttf"  # 或 ArialUnicodeMS.ttf
    pdf.add_font('Noto', '', font_path, uni=True)
    pdf.set_font("Noto", size=12)

    pdf.multi_cell(0, 10, f"使用者提問：{user_query}\n\n")
    pdf.multi_cell(0, 10, conversation_output)

    os.makedirs("pdf_outputs", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"legal_chat_{timestamp}.pdf"
    file_path = os.path.join("pdf_outputs", filename)
    pdf.output(file_path)

    return file_path

def legal_article_search(query: str, top_k: int, rerank_top_n: int, hybrid_alpha: float) -> str:
    """法條搜索功能"""
    if not legal_search_available:
        return "法條搜索引擎未正確初始化，請檢查資料庫配置。"
    
    try:
        # 更新混合搜索權重
        legal_search_engine.hybrid_alpha = hybrid_alpha
        
        # 執行搜索
        results = legal_search_engine.search(
            query=query, 
            top_k=top_k, 
            rerank_top_n=rerank_top_n
        )
        
        if not results:
            return "未找到相關法條。"
        
        # 格式化結果
        formatted_output = f"# 法條查詢結果\n\n"
        formatted_output += f"**查詢：** {query}\n\n"
        formatted_output += f"**搜索參數：** Top-K={top_k}, 重排序數量={rerank_top_n}, 混合權重={hybrid_alpha}\n\n"
        
        for i, result in enumerate(results):
            metadata = result.get("metadata", {})
            law_name = metadata.get("法律名稱", "未知法律")
            article = metadata.get("條", "未知條款")
            score = result.get("score", 0)
            sources = result.get("sources", [])
            
            formatted_output += f"## 結果 {i+1}\n"
            formatted_output += f"**相關度：** {score:.3f} \n\n"
            formatted_output += f"**法律：** {law_name} \n\n"
            formatted_output += f"**條文：** {article} \n\n"
            if sources:
                formatted_output += f"**搜索來源：** {', '.join(sources)} \n\n"
            formatted_output += f"**內容：**\n```\n{result['content']}\n```\n\n"
            formatted_output += "---\n\n"
        
        return formatted_output
        
    except Exception as e:
        return f"搜索時發生錯誤：{str(e)}"


def get_related_laws_analysis(query, top_k, rerank_top_n):
    """獲取相關法條分析"""
    if not legal_search_available:
        return "法條搜索引擎未正確初始化。"
    
    try:
        direct_relevant, indirectly_relevant = legal_search_engine.get_related_laws(
            query=query,
            top_k=top_k,
            rerank_top_n=rerank_top_n
        )
        
        output = f"# 法條相關性分析\n\n"
        output += f"**查詢：** {query}\n\n"
        
        if direct_relevant:
            output += f"## 🎯 直接相關法條 ({len(direct_relevant)} 條)\n\n"
            for i, result in enumerate(direct_relevant):
                metadata = result.get("metadata", {})
                law_name = metadata.get("法律名稱", "未知法律")
                article = metadata.get("條", "未知條款")
                score = result.get("score", 0)
                
                output += f"### {i+1}. {law_name}  {article} \n"
                output += f"**相關度：** {score:.3f} \n"
                output += f"**內容：** {result['content'][:200]}...\n\n"
        
        if indirectly_relevant:
            output += f"## 🔗 間接相關法條 ({len(indirectly_relevant)} 條)\n\n"
            for i, result in enumerate(indirectly_relevant):
                metadata = result.get("metadata", {})
                law_name = metadata.get("法律名稱", "未知法律")
                article = metadata.get("條", "未知條款")
                score = result.get("score", 0)
                
                output += f"### {i+1}. {law_name} 第 {article} 條\n"
                output += f"**相關度：** {score:.3f}\n"
                output += f"**內容：** {result['content'][:150]}...\n\n"
        
        if not direct_relevant and not indirectly_relevant:
            output += "未找到相關法條。\n"
        
        return output
        
    except Exception as e:
        return f"分析時發生錯誤：{str(e)}"


def get_chroma_collection():
    client = Client(Settings(
        persist_directory="chroma_db",
        is_persistent=True
    ))
    embedding_function = OpenAIEmbeddingFunction(
        api_key=OPENAI_API_KEY,
        model_name='text-embedding-ada-002'
    )
    return client.get_collection("legal_casesv1", embedding_function=embedding_function)

def search_and_rerank(query: str, top_k=5):
    extracted_codes = [] 
    collection = get_chroma_collection()
    search_results = collection.query(
        query_texts=[query],
        n_results=top_k * 2
    )
    
    documents = search_results['documents'][0]
    metadatas = search_results['metadatas'][0]
    ids = search_results['ids'][0]
    
    if not documents:
        return {'ranked_documents': [], 'ranked_metadatas': [], 'ids': []}
    
    ranking_scores = []
    for doc in documents:
        score = reranker.compute_score([query, doc])
        ranking_scores.append(score)
    
    indexed_scores = list(enumerate(ranking_scores))
    sorted_indexed_scores = sorted(indexed_scores, key=lambda x: x[1], reverse=True)
    ranked_indices = [idx for idx, _ in sorted_indexed_scores[:1]]
    
    ranked_documents = [documents[i] for i in ranked_indices]
    ranked_metadatas = [metadatas[i] for i in ranked_indices]
    ranked_ids = [ids[i] for i in ranked_indices]
    for i, metadata in enumerate(ranked_metadatas):
        if metadata and 'z3code' in metadata:
            code = metadata['z3code']
            if code and code.strip():
                # 為每個程式碼片段創建檔案
                filename = f"case_{ranked_ids[i]}_code.py"
                filepath = os.path.join("code_execution", filename)
                
                # 確保目錄存在
                os.makedirs("code_execution", exist_ok=True)
                
                # 寫入程式碼檔案
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(code)
                
                extracted_codes.append({
                    'case_id': ranked_ids[i],
                    'filename': filename,
                    'filepath': filepath,
                    'code': code
                })
    
    return {
        'ranked_documents': ranked_documents, 
        'ranked_metadatas': ranked_metadatas, 
        'ids': ranked_ids,
        'extracted_codes': extracted_codes
    }



# 修改所有的 is_termination_msg
def is_termination_msg(x):
    """檢查是否為終止訊息"""
    if "content" not in x or x["content"] is None:
        return False  # 空訊息不終止
    
    content = x["content"].strip().lower()
    
    # 檢查是否包含 terminate (不區分大小寫)
    if "terminate" in content:
        return True
    
    return False

def read_soft_config(filename: str) -> str:
    filepath = os.path.join("code_execution", filename)
    with open(filepath, "r", encoding="utf-8") as f:
        code_string = f.read()
    return extract_softs_from_code(code_string)


def get_softs_labels_and_vars(filename: str):
    filepath = os.path.join("code_execution", filename)
    with open(filepath, "r", encoding="utf-8") as f:
        code_string = f.read()
    return extract_softs_description_and_varnames(code_string)

initializer = UserProxyAgent(
    name="Init",
    human_input_mode="NEVER",
    code_execution_config=False,
    
)

host_agent = AssistantAgent(
    name="host_agent",
    llm_config=llm_config,
    system_message="""
你是金融判例Agent，負責判斷使用者輸入，你的任務是第一線跟User對話，你必須專業且具有一個金融知識者的一個sense。

你有以下能力：
1. **法條查詢**：當使用者詢問特定法律條文、法規內容時，你可以使用 `legal_article_search` 函數查詢相關法條
2. **案例分析**：當使用者需要分析具體的金融裁罰案例時，啟動完整的分析流程

請根據使用者問題類型做出判斷：

**法條查詢類問題**（直接回答，不啟動分析）：
- 詢問特定法律條文內容
- 詢問法規規定
- 需要法條依據
- 例如："公司法第156條規定什麼？"、"資本適足率的法律規定是什麼？"

**案例分析類問題**（需要啟動分析流程）：
- 詢問具體裁罰案例
- 需要案例比對分析
- 涉及程式碼執行與合規檢查
- 例如："有沒有類似的裁罰案例？"、"幫我分析這個違規情況"

**一般對話**：
- 打招呼、日常閒聊：自然回覆，不啟動分析

---

**判斷流程**：
1. 如果是法條查詢類問題 → 使用 `legal_article_search` 函數查詢並回答 -> 當你搜索到法條之後，你的回應必須要有引用來源
2. 如果是案例分析類問題 → 確認使用者意願後，回覆 "[系統判斷] 啟動分析流程"
3. 如果是一般對話 → 自然回應

請保持專業、友善的對話風格。
""",
    is_termination_msg=is_termination_msg,
)

report_generator = AssistantAgent(
    name="report_generator",
    llm_config=llm_config,
    system_message="""
    你是一位專業的報告生成專家，負責將所有分析結果整合成一份完整的 Markdown 格式總報告。

    **你的任務：**
    1. 收集所有代理的分析結果
    2. 生成結構化的 Markdown 報告
    3. 確保報告格式清晰、專業

    **報告結構：**
    # 金融合規案例分析總報告
    
    ## 執行摘要
    [簡要概述分析結果和主要發現]
    
    ## 案例背景分析
    [來自案例分析師的內容]
    
    ## 程式碼分析結果
    [來自程式碼分析師的內容]
    
    ## 法條合規分析
    [來自法律分析師的內容]
    
    ## 綜合結論與建議
    [整合性建議和決策支援]
    
    ## 風險評估矩陣
    [風險等級和改善優先順序]
    
    ## 行動方案
    [具體的執行步驟和時程規劃]


    請確保報告內容專業、結構清晰，使用適當的 Markdown 語法格式化。
    完成後請說 "REPORT_COMPLETE"。
    """,
    is_termination_msg=lambda x: "content" in x and x["content"] is not None and "REPORT_GENERATED" in x["content"],
)



legal_analyst = AssistantAgent(
    is_termination_msg=is_termination_msg,
    name="legal_assistant",
    llm_config=llm_config_o3,
    system_message="""
    你是一位資深的金融法規與科技應用綜合分析師，負責統整所有專門代理人的分析結果。

    **你將接收到併發分析代理提供的三個專門分析師的報告：**
    1. **案例分析師**：案例背景與違規行為分析
    2. **程式碼分析師**：Z3求解器結果與改善建議分析  
    3. **法律分析師**：法條違規點與合規要求分析

    這些分析是併發執行的，因此你會同時收到所有分析結果。

    **你的任務是整合這些專業觀點，撰寫完整的綜合分析報告：**

    ## 問題背景
    - 整合案例分析師的背景描述

    ## 案例摘要  
    - 綜合案例的核心違規行為和影響

    ## 程式改善機制分析
    - 整合程式碼分析師的改善建議
    - 並說明透過什麼樣的改善可以讓其變成合規

    ## 法條合規分析
    - 整合法律分析師的法規分析
    - 明確指出合規改善方向

    ## 結論與建議
    - 提供整合性的決策建議
    - 強調技術改善與法規合規的結合

    請確保：
    - 避免重複各分析師已詳述的內容
    - 著重於跨領域的整合與洞察
    - 提供可執行的綜合建議
    """,
)

# 完成後請回覆 "TERMINATE"。

search_agent = AssistantAgent(
    name="search_agent",
    llm_config=llm_config,
    system_message="""
    你是一個專門負責搜索法律案例資料庫的代理。
    當收到法律問題時，你需要：
    1. 使用 search_and_rerank 函數搜索相關案例
    2. 將搜索結果整理並傳遞給下一個代理
    3. 如果搜索到的案例包含程式碼，請標註出來
    
    搜索完成後，請說 "搜索完成，案例已找到" 並將結果傳遞給程式執行代理。
    """,
    is_termination_msg=is_termination_msg,
)

find_code_agent = AssistantAgent(
    name="find_code_agent",
    llm_config=llm_config,
    system_message="""
    當搜索代理找到包含程式碼的案例時，你需要參考下面的格式，注意，工作目錄請不需要更動，你需要更改的只有要執行哪一個python檔案，請你注意縮排並確保格式正確：
    ```python
import os
import subprocess
import locale

def main():
    result = subprocess.run(
        ['python', 'case_case_2_code.py'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding=locale.getpreferredencoding()  # 依系統自動選擇 cp950/gbk/utf-8
    )
    return result.stdout

if __name__ == "__main__":
    output = main()
    print(output)

    ```
    這種格式的程式碼，run的是前面我們搜索到的python檔案，你不需要另外書寫z3-solver的程式碼，你也不需要另外解釋。
    """,
    is_termination_msg=is_termination_msg,
)
work_dir = os.path.abspath("code_execution")
executor = LocalCommandLineCodeExecutor(work_dir=work_dir)
code_executor = UserProxyAgent(
    name="code_executor",
    human_input_mode="NEVER",
    is_termination_msg=is_termination_msg,
    code_execution_config={
        "executor": executor,
        "last_n_messages": 1,
    }
)

debug_agent = AssistantAgent(
    name="debug_agent",
    llm_config=llm_config,
    system_message="""
    你是一個專門負責程式除錯的代理。
    當程式執行出現錯誤時，你需要：
    1. 提供修正後的程式碼
    2. 將修正結果回傳給程式執行代理重新執行
    
    除錯完成後，請說明問題所在和解決方案。
    """,
    is_termination_msg=is_termination_msg,
)

case_analyst = AssistantAgent(
    name="case_analyst",
    llm_config=llm_config,
    system_message="""
    你是一位專精於金融法規與合規案例分析的顧問。

    **你的專門任務：分析金融裁罰案例的背景與違規行為**

    請根據搜索代理提供的金融裁罰案例資料，重點分析：
    - 違規行為的具體類型與發生背景
    - 被裁罰機構的具體作為或疏失
    - 金管會或主管機關的裁罰理由和依據
    - 此案例反映的制度性風險或內控缺陷

    請將內容條理清晰地整理，重點明確，為後續的程式碼分析和法律分析提供基礎。
    
    **注意：你只負責案例背景分析，不需要分析程式碼或法條內容。**
    """,
    is_termination_msg=is_termination_msg,
)

code_analyst = AssistantAgent(
    name="code_analyst",
    llm_config=llm_config,
    system_message="""
    你是一位精通金融科技應用、模型推論與財務風控的分析師。

    **你的專門任務：分析Z3求解器程式碼的執行結果與改善建議**

    你會接收到程式執行代理的執行結果，該程式使用Z3求解器分析金融案例的可能改善方案。

    請重點分析：
    1. **變數對比分析**：對比「預設值」與「求解建議值」，指出哪些變數有明顯改善方向
    2. **金融意涵解讀**：解釋這些變數的實際意義（如資本適足率、風險資本、合規行為等）
    3. **布林變數解讀**：說明 `True`/`False` 的改變代表哪些可執行的行動方向
    4. **改善可行性**：評估這些數值調整在實務上的可行性

    請以專業但易懂的方式回覆，著重於「輸出數據的實務解讀」。

    **注意：你只負責程式碼執行結果分析，不需要分析案例背景或法條內容。**
    """,
    is_termination_msg=is_termination_msg,
)

law_analyst = AssistantAgent(
    name="law_analyst",
    llm_config=llm_config,
    system_message="""
    你是一位專業的金融法規分析師。

    **你的專門任務：從法規角度解析案例中的違法點與合規要求**

    請根據案例內容和相關法條，專門分析：
    - **違法認定**：案例中具體違反了哪些法條條文（條號與內容）
    - **法規義務**：該法條對金融機構或從業人員規定了什麼義務
    - **違規構成**：案例中的作為或不作為如何構成法規違反
    - **合規標準**：根據法條要求，機構應如何調整以符合規範

    請以法律邏輯清晰的方式進行解釋，引用具體條文並逐句對應違規行為。

    **注意：你只負責法律法規分析，不需要分析程式碼執行結果或重複案例背景。**
    """,
    is_termination_msg=is_termination_msg,
)
case_summarizer = AssistantAgent(
    name="case_summarizer",
    llm_config=llm_config,
    system_message="""
你是一位法律資訊整理員，負責將前一位代理人提供的大量案例資料進行摘要。

請從中萃取出：
- 案例名稱或裁罰機構（若有）
- 裁罰原因或爭點類型（如：未落實洗錢防制）
- 涉及的金融行為或缺失行為
- 是否提及適用法條（可列出條號或條文名稱）

請將摘要控制在 200~300 字內，重點清楚，避免引述過長段落。

**完成摘要後，請在最後加上：**
"案例摘要已完成。是否要繼續進行深度分析？請輸入 '繼續分析' 來進行程式碼執行和法律分析，或輸入 '結束' 來停止分析。"

並請說 "SUMMARY_COMPLETE"。
    """,
    # 移除終止檢查，讓它能正常完成摘要並等待用戶確認
    is_termination_msg=lambda x: False  # 永不自動終止
)

user_confirmation_agent = UserProxyAgent(
    name="user_confirmation",
    human_input_mode="ALWAYS",  # 總是需要人工輸入
    code_execution_config=False,
    system_message="""
請根據案例摘要決定是否要繼續分析：
- 輸入 '繼續分析' 來進行詳細的程式碼執行和法律分析
- 輸入 '結束' 來停止分析流程
    """,
    is_termination_msg=lambda x: "content" in x and x["content"] is not None and any(keyword in x["content"].lower() for keyword in ["結束", "stop", "end"]),
)

user_proxy = UserProxyAgent(
    is_termination_msg=lambda x: "content" in x
    and x["content"] is not None
    and x["content"].rstrip().endswith("TERMINATE"),
    name="user_proxy",
    code_execution_config=False,
    human_input_mode="NEVER",
)
softs_parser = AssistantAgent(
    name="softs_parser",
    llm_config=llm_config,
    system_message="""
    你會接收到一個 Python 檔案名稱（如 case_123_code.py），請呼叫 `read_soft_config` 與 `get_softs_labels_and_vars` 函數獲得 soft constraints 區塊的內容與變數資訊。
    請以條列清單顯示有哪些變數可調整，並提示使用者可以輸入上下界、變為硬約束或略過。
    """
)


constraint_editor = AssistantAgent(
    name="constraint_editor",
    llm_config=llm_config,
    system_message="""
    你會根據使用者輸入的自然語言（如「將A設為硬約束」「B上下限 50~100」）來結構化成 json 指令，再傳遞給執行 Agent。
    """
)

register_function(
    read_soft_config,
    caller=softs_parser,
    executor=user_proxy,
    name="read_soft_config",
    description="讀取指定檔案中的 soft constraint 區塊程式碼"
)

register_function(
    get_softs_labels_and_vars,
    caller=softs_parser,
    executor=user_proxy,
    name="get_softs_labels_and_vars",
    description="回傳指定檔案中 soft constraint 的中文標籤與變數名"
)



register_function(
    search_and_rerank,
    caller=search_agent,
    executor=user_proxy,
    name="search_and_rerank",
    description="Re‐rank a list of candidate documents based on FlagReranker scores."
)


# 註冊函數給 host_agent
register_function(
    legal_article_search,
    caller=host_agent,
    executor=user_proxy,
    name="legal_article_search",
    description="搜索相關法條。當使用者詢問特定法律條文、法規內容或需要法條依據時使用此功能。"
)

# register_function(
#     get_extracted_codes,
#     caller=find_code_agent,
#     executor=user_proxy,
#     name="get_extracted_codes",
#     description="獲取從法律案例中提取的程式碼列表"
# )


###############################Phase 2

modify_agent = AssistantAgent(
    name="modify_agent",
    llm_config=llm_config,
    system_message="""
    你是一個約束修改代理，負責處理使用者的約束修改指令。

    你會接收到：
    1. 使用者的自然語言修改指令
    2. 當前的約束清單（包含變數名、描述、預設值）
    3. 目標檔案名稱

    你需要：
    1. 理解使用者的自然語言指令
    2. 將指令轉換為結構化的參數格式
    3. 調用 modify_constraints_tool 來執行修改
    4. 解釋修改結果

    支援的修改類型及對應參數：
    - **設為硬約束**：「將 [變數名] 設為硬約束」
      → 使用參數：hard_constraint_variables: ["變數名"]
      
    - **設定範圍**：「將 [變數名] 範圍設為 [下限] 到 [上限]」（僅適用於數值變數）
      → 使用參數：
         range_constraint_variables: ["變數名"]
         range_min_values: [下限]
         range_max_values: [上限]
      
    - **固定數值**：「將 [變數名] 固定為 [數值]」（僅適用於數值變數）
      → 使用參數：fixed_value_variables: {"變數名": 數值}
      
    - **固定布林值**：「將 [變數名] 設為 True/False」（僅適用於布林變數）
      → 使用參數：fixed_value_variables: {"變數名": True 或 False}
      
    - **移除約束**：「移除 [變數名] 的約束」
      → 使用參數：remove_variables: ["變數名"]

    **重要提示**：
    - **布林變數**（如 has_signed_contract, guesthouse_audit_covered）只能設為 True 或 False
    - **數值變數**（如 risk_capital, net_worth_ratio）可以設定範圍或固定值
    - 對於布林值，使用 Python 的 True/False（不要加引號）
    - 對於數值，直接使用數字，不要加引號
    - 變數名必須與約束清單中的名稱完全匹配

    **布林變數特殊處理**：
    系統會自動偵測布林類型的變數，並使用 `s.add(變數 == True/False)` 的方式處理，
    而非使用範圍約束，以避免型態錯誤。

    請根據使用者指令調用相應的工具函數，並詳細解釋修改結果。
    """,
    is_termination_msg=is_termination_msg,
)

def modify_constraints_tool(
    filename: str,
    remove_variables: List[str] = None,
    hard_constraint_variables: List[str] = None,
    range_constraint_variables: List[str] = None,
    range_min_values: List[float] = None,
    range_max_values: List[float] = None,
    fixed_value_variables: Dict[str, Union[float, bool]] = None
) -> Dict[str, Union[bool, str, List, Dict]]:
    """
    根據分離的變數列表修改約束設定
    
    Args:
        filename (str): 目標檔案名稱，例如 "case_case_0_code.py"
        remove_variables (List[str], optional): 要移除的變數名列表
        hard_constraint_variables (List[str], optional): 要設為硬約束的變數名列表
        range_constraint_variables (List[str], optional): 要設定範圍約束的變數名列表
        range_min_values (List[float], optional): 對應範圍約束的最小值列表
        range_max_values (List[float], optional): 對應範圍約束的最大值列表
        fixed_value_variables (Dict[str, Union[float, bool]], optional): 要固定為特定值的變數字典
    
    Returns:
        Dict: 執行結果
    """
    try:
        # 讀取目標檔案，檢查變數類型
        filepath = os.path.join("code_execution", filename)
        with open(filepath, 'r', encoding='utf-8') as f:
            code_content = f.read()
        
        # 檢測哪些變數是布林類型（Bool()）
        bool_variables = set()
        import re
        bool_pattern = r'(\w+)\s*=\s*Bool\('
        for match in re.finditer(bool_pattern, code_content):
            bool_variables.add(match.group(1))
        
        print(f"[DEBUG] 偵測到的布林變數: {bool_variables}")
        
        # 處理固定值變數
        if fixed_value_variables:
            if range_constraint_variables is None:
                range_constraint_variables = []
            if range_min_values is None:
                range_min_values = []
            if range_max_values is None:
                range_max_values = []
            
            for var_name, fixed_value in fixed_value_variables.items():
                # 檢查是否為布林變數
                if var_name in bool_variables:
                    # 布林變數不能使用範圍約束！
                    # 改為直接在程式碼中加入 s.add() 約束
                    print(f"[DEBUG] {var_name} 是布林變數，無法使用範圍約束")
                    
                    # 這裡我們需要用不同的方式處理
                    # 暫時跳過，稍後用特殊處理
                    continue
                else:
                    # 數值變數：使用範圍約束
                    if isinstance(fixed_value, bool):
                        numeric_value = float(1 if fixed_value else 0)
                    else:
                        numeric_value = float(fixed_value)
                    
                    range_constraint_variables.append(var_name)
                    range_min_values.append(numeric_value)
                    range_max_values.append(numeric_value)
        
        # 調用 API
        result = modify_constraints_api(
            filename=filename,
            remove_variables=remove_variables,
            hard_constraint_variables=hard_constraint_variables,
            range_constraint_variables=range_constraint_variables,
            range_min_values=range_min_values,
            range_max_values=range_max_values
        )
        
        # 如果有布林變數的固定值，需要額外處理
        if fixed_value_variables:
            bool_fixed_vars = {k: v for k, v in fixed_value_variables.items() if k in bool_variables}
            
            if bool_fixed_vars:
                # 讀取修改後的檔案
                modified_filename = result.get('updated_file', filename)
                modified_filepath = os.path.join("code_execution", modified_filename)
                
                with open(modified_filepath, 'r', encoding='utf-8') as f:
                    modified_code = f.read()
                
                # 在 s.check() 之前插入布林約束
                for var_name, bool_value in bool_fixed_vars.items():
                    # 構造約束語句
                    if bool_value:
                        constraint_line = f"s.add({var_name} == True)  # 固定為 True\n"
                    else:
                        constraint_line = f"s.add({var_name} == False)  # 固定為 False\n"
                    
                    # 在 s.check() 前插入
                    modified_code = modified_code.replace(
                        'if s.check() == sat:',
                        f'{constraint_line}if s.check() == sat:'
                    )
                
                # 寫回檔案
                with open(modified_filepath, 'w', encoding='utf-8') as f:
                    f.write(modified_code)
                
                # 更新結果訊息
                result['message'] += f"\n額外處理了 {len(bool_fixed_vars)} 個布林變數的固定值。"
                result['modified_items'].extend([
                    f"設定布林變數 {var} = {val}" for var, val in bool_fixed_vars.items()
                ])
        
        return result
        
    except Exception as e:
        return {
            "success": False,
            "error": f"執行約束修改時發生錯誤: {str(e)}"
        }
    

constraint_host_agent = AssistantAgent(
    name="constraint_host",
    llm_config=llm_config,
    system_message="""
你是約束修改模式的協調代理，負責判斷使用者的意圖。

**你會接收到：**
1. 使用者的輸入
2. 當前可用的約束變數清單

**你需要判斷使用者意圖並做出相應處理：**

### 📌 意圖分類

1. **詢問類問題**（回答問題，不執行修改）：
   - 詢問變數的意義：「pre_CAR 是什麼意思？」
   - 詢問當前設定：「目前有哪些約束？」
   - 詢問修改方式：「我該如何設定硬約束？」
   - 詢問影響範圍：「修改這個變數會有什麼影響？」
   
   → **處理方式**：直接回答問題，不調用修改工具

2. **執行修改類指令**（需要執行修改）：
   - 明確的修改指令：「將 X 設為硬約束」
   - 範圍設定：「將 X 範圍設為 A 到 B」
   - 固定數值：「將 X 固定為 C」
   - 移除約束：「移除 X 的約束」
   
   → **處理方式**：回覆 "[執行修改] 啟動修改流程"，並將指令傳遞給 modify_agent

3. **一般對話**：
   - 打招呼、感謝、確認
   
   → **處理方式**：自然回應

**判斷原則：**
- 包含「將」、「設為」、「固定」、「範圍」、「移除」等動詞 → 執行修改
- 包含「什麼」、「如何」、「為什麼」等疑問詞 → 回答問題
- 包含變數名但沒有動作詞 → 詢問該變數的資訊

請保持專業、友善的對話風格，並確保使用者清楚了解每個約束變數的意義。
    """,
    is_termination_msg=is_termination_msg,
)

parallel_analyzer = AssistantAgent(
    name="parallel_analyzer",
    llm_config=llm_config,
    system_message="""
    你是併發分析協調代理，負責同時啟動三個專門分析師進行併發分析。

    **你的任務：**
    1. 接收程式執行代理的結果
    2. 從對話歷史中提取搜索結果和程式執行結果
    3. 調用 execute_parallel_analysis 函數啟動併發分析：
       - 案例分析師：分析案例背景與違規行為
       - 程式碼分析師：分析 Z3 求解器結果
       - 法律分析師：分析法條違規點
    4. 將併發分析的結果整合並返回

    **重要**：你需要從對話歷史中找到：
    - search_agent 提供的搜索結果
    - code_executor 提供的程式執行結果
    
    然後調用 execute_parallel_analysis(search_results, code_execution_results) 函數。

    請在收到程式執行結果後，立即分析對話歷史，提取必要資訊並啟動併發分析。
    """,
    is_termination_msg=lambda x: "content" in x and x["content"] is not None and "PARALLEL_ANALYSIS_COMPLETE" in x["content"],
)

# 重新註冊函數

def execute_parallel_analysis(search_results: str, code_execution_results: str) -> str:
    """
    併發執行三個分析師的分析任務
    
    Args:
        search_results: 搜索結果的字符串表示
        code_execution_results: 程式執行結果的字符串表示
    
    Returns:
        包含三個分析師結果的格式化字符串
    """
    def run_case_analysis():
        """執行案例分析"""
        try:
            # 創建臨時的 messages 來執行案例分析
            temp_messages = [
                {
                    "role": "user", 
                    "content": f"請分析以下搜索到的案例背景：\n{search_results}"
                }
            ]
            
            # 直接調用案例分析師
            response = case_analyst.generate_reply(
                messages=temp_messages,
                sender=user_proxy
            )
            return ("case_analyst", response)
        except Exception as e:
            return ("case_analyst", f"案例分析時發生錯誤：{str(e)}")

    def run_code_analysis():
        """執行程式碼分析"""
        try:
            temp_messages = [
                {
                    "role": "user", 
                    "content": f"請分析以下程式執行結果：\n{code_execution_results}"
                }
            ]
            
            response = code_analyst.generate_reply(
                messages=temp_messages,
                sender=user_proxy
            )
            return ("code_analyst", response)
        except Exception as e:
            return ("code_analyst", f"程式碼分析時發生錯誤：{str(e)}")

    def run_law_analysis():
        """執行法律分析"""
        try:
            temp_messages = [
                {
                    "role": "user", 
                    "content": f"請從法律角度分析以下案例：\n案例資料：{search_results}\n程式執行結果：{code_execution_results}"
                }
            ]
            
            response = law_analyst.generate_reply(
                messages=temp_messages,
                sender=user_proxy
            )
            return ("law_analyst", response)
        except Exception as e:
            return ("law_analyst", f"法律分析時發生錯誤：{str(e)}")

    # 使用 ThreadPoolExecutor 併發執行
    with ThreadPoolExecutor(max_workers=3) as executor:
        # 提交三個分析任務
        future_case = executor.submit(run_case_analysis)
        future_code = executor.submit(run_code_analysis)
        future_law = executor.submit(run_law_analysis)
        
        # 等待所有任務完成並收集結果
        case_result = future_case.result()
        code_result = future_code.result()
        law_result = future_law.result()
    
    # 格式化結果為字符串
    formatted_results = f"""
# 併發分析結果

## 案例分析結果
**分析師：** {case_result[0]}
**內容：**
{case_result[1]}

---

## 程式碼分析結果
**分析師：** {code_result[0]}
**內容：**
{code_result[1]}

---

## 法律分析結果
**分析師：** {law_result[0]}
**內容：**
{law_result[1]}

PARALLEL_ANALYSIS_COMPLETE
"""
    
    return formatted_results


# 註冊併發分析函數
register_function(
    execute_parallel_analysis,
    caller=parallel_analyzer,
    executor=user_proxy,
    name="execute_parallel_analysis",
    description="併發執行三個分析師的分析任務，返回格式化的分析結果"
)
# ==============================================================================
# 新增：結果分析 Agent
# ==============================================================================
result_analyst = AssistantAgent(
    name="result_analyst",
    llm_config=llm_config,
    system_message="""
    你是一位結果分析師，專門負責解讀約束修改後的執行結果。

    你會收到一個包含執行結果的 JSON 物件。你的任務是：
    1.  **總結修改狀態**：說明修改是否成功，以及新的程式碼檔案儲存在哪裡（參考 `updated_file`）。
    2.  **列出具體變更**：根據 `modified_items` 清單，清楚地條列出所有被修改的約束項目。
    3.  **解釋執行結果**：分析 `execution_result` 和 `reasoning_result`，用白話文解釋求解器找到了什麼樣的解（例如 "SAT" 表示找到可行解，"UNSAT" 表示無解），並呈現關鍵的輸出日誌。
    4.  **提供後續建議**：根據結果，建議使用者可以進行下一步分析或再次修改。

    請以清晰、有條理的方式呈現你的分析報告。完成後請回覆 "TERMINATE"。
    """,
    is_termination_msg=is_termination_msg,
)


# 註冊工具函數給 modify_agent
register_function(
    modify_constraints_tool,
    caller=modify_agent,
    executor=user_proxy,
    name="modify_constraints_tool",
    description="根據 JSON 格式的修改指令執行約束修改。工具會自動解析自然語言指令並轉換為結構化格式。"
)

def extract_summary(messages, include_roles=["legal_assistant", "code_executor", "user_proxy"]):
    """
    從上層 messages 中擷取出重要角色的對話歷史，用於 nested group 的 context 準備。
    """
    summary_messages = []
    for msg in messages:
        role = msg.get("name")
        content = msg.get("content", "").strip()
        if role in include_roles and content:
            summary_messages.append({
                "name": role,
                "content": content
            })
    return summary_messages


# def build_soft_group():
#     soft_gc = GroupChat(
#         agents=[softs_parser, constraint_editor, softs_executor],
#         messages=[],
#         max_round=10
#     )
#     return GroupChatManager(
#         name="group_soft_editor",
#         groupchat=soft_gc,
#         llm_config=llm_config,
#         is_termination_msg=is_termination_msg
#     )
analysts = [case_analyst, code_analyst, law_analyst]



def state_transition(last_speaker, groupchat):
    messages = groupchat.messages
    named_messages = [msg for msg in messages if 'name' in msg]
    
    # 檢查是否是繼續分析的請求
    if len(named_messages) >= 1:
        last_message_content = named_messages[-1].get('content', '').lower()
        if '繼續分析' in last_message_content:
            return find_code_agent
        # 新增：檢查是否要進入約束修改
        elif '約束修改' in last_message_content:
            return None  # 停止自動轉換，準備進入 nested chat
    
    # 檢查前一個發言者
    if len(named_messages) >= 2:
        previous_agent_name = named_messages[-2]['name']
        if previous_agent_name == "search_agent":
            return case_summarizer 
    
    # 檢查前一個發言者
    if len(named_messages) >= 2:
        previous_agent_name = named_messages[-2]['name']
        if previous_agent_name == "host_agent" and last_speaker == user_proxy:
            return host_agent
            
    # 🔧 修正：處理 host_agent 的工具呼叫
    if last_speaker is host_agent:
        last_message = groupchat.messages[-1]
        content = last_message.get("content", "")
        tool_call_present = (
            "Suggested tool call" in content or
            "call_" in content or
            ("tool_calls" in last_message)
        )

        if tool_call_present:
            print("[DEBUG] Detected tool call from host_agent → transferring to user_proxy")
            return user_proxy
        elif "[系統判斷] 啟動分析流程" in content:
            return initializer
        else:
            return None
    
    # 🔧 新增：處理 user_proxy 執行完 host_agent 的工具後
    if last_speaker is user_proxy:
        # 檢查前一個發言者是否是 host_agent
        if len(named_messages) >= 2:
            previous_agent_name = named_messages[-2].get('name')
            if previous_agent_name == "host_agent":
                # 工具執行完畢 → 返回 host_agent 讓它回覆結果
                return host_agent
        
    if last_speaker is initializer:
        return search_agent
    elif last_speaker is case_summarizer:
        if len(named_messages) >= 1:
            last_content = named_messages[-1].get('content', '')
            if 'SUMMARY_COMPLETE' in last_content:
                return None
        return None
    elif last_speaker is code_executor:
        if "exitcode: 1" in messages[-1]["content"]:
            return debug_agent
        else:
            # 修改：程式執行完成後啟動併發分析
            return legal_analyst  # 新增的併發分析代理
    elif last_speaker is parallel_analyzer:  # 新增
        return legal_analyst
    elif last_speaker is legal_analyst:
        return report_generator
    elif last_speaker is report_generator:
        # 報告生成完成後，檢查是否包含 REPORT_COMPLETE
        if len(named_messages) >= 1:
            last_content = named_messages[-1].get('content', '')
            if 'REPORT_COMPLETE' in last_content:
                return None  # 停止自動轉換，等待用戶選擇
        return None
    elif last_speaker is find_code_agent:
        return code_executor
    elif last_speaker is debug_agent:
        return code_executor
    else:
        return "auto"


chat_history = []

def create_group_chat():
    return GroupChat(
        agents=[host_agent, initializer, user_proxy, find_code_agent, search_agent, code_executor, debug_agent, parallel_analyzer, legal_analyst, case_summarizer, report_generator],
        messages=[],
        max_round=25,
        speaker_selection_method=state_transition,
         allow_repeat_speaker=[host_agent],
    )

        
def legal_query_interface(user_query, history, continue_analysis=False):
    """Gradio interface function for legal queries with group chat"""
    try:
        # 檢查是否處於約束修改模式
        if getattr(legal_query_interface, 'in_constraint_mode', False):
            # 檢查是否要退出約束修改模式
            if any(keyword in user_query for keyword in ['完成修改', '結束修改', '退出']):
                legal_query_interface.in_constraint_mode = False
                delattr(legal_query_interface, 'constraint_manager')
                delattr(legal_query_interface, 'constraints_info')
                delattr(legal_query_interface, 'constraints_data')
                
                exit_msg = "✅ 已退出約束修改模式。"
                history.append([user_query, exit_msg])
                return history, "", "約束修改模式已結束", gr.update(visible=False), gr.update(visible=False), None
            
            # 處理使用者輸入（可能是問題或修改指令）
            file_state = getattr(legal_query_interface, 'current_file_state', None)
            constraint_manager = getattr(legal_query_interface, 'constraint_manager', None)
            constraints_info = getattr(legal_query_interface, 'constraints_info', '')
            constraints_data = getattr(legal_query_interface, 'constraints_data', [])
            
            if not file_state or not constraint_manager:
                error_msg = "❌ 約束修改模式狀態異常，請重新啟動。"
                history.append([user_query, error_msg])
                legal_query_interface.in_constraint_mode = False
                return history, "", error_msg, gr.update(visible=False), gr.update(visible=False), None
            
            try:
                # 準備初始訊息給 constraint_host（精簡版，不包含完整清單）
                initial_message = f"""
使用者輸入：{user_query}

目標檔案：{file_state}

可用約束變數數量：{len(constraints_data)} 個

請根據使用者的問題判斷意圖：
- 如果是詢問約束清單 → 直接列出所有可用的約束變數
- 如果是詢問特定變數 → 提供該變數的詳細資訊
- 如果是修改指令 → 回覆 "[執行修改]" 並轉交給修改代理

約束變數資訊：
{constraints_info}
"""
                
                # 啟動 Nested Chat，從 constraint_host 開始
                chat_result = constraint_host_agent.initiate_chat(
                    constraint_manager,
                    message=initial_message
                )
                
                # 格式化 Nested Chat 的結果
                nested_output = ""
                for message in chat_result.chat_history:
                    role = message.get("name", "unknown")
                    content = message.get("content", "")
                    
                    if role == "constraint_host":
                        # 只顯示 host 的實際回覆，過濾系統訊息
                        if not any(x in content for x in ["[執行修改]", "Suggested tool call", "call_"]):
                            nested_output += f"**🤖 約束協調代理：**\n{content}\n\n---\n\n"
                    # elif role == "modify_agent":
                    #     nested_output += f"**✏️ 修改代理：**\n{content}\n\n---\n\n"
                    elif role == "result_analyst":
                        nested_output += f"**📊 結果分析師：**\n{content}\n\n---\n\n"
                    elif role == "user_proxy":
                        if content.strip():
                            nested_output += f"**⚙️ 執行結果：**\n{content}\n\n---\n\n"
                
                # 更新歷史記錄
                history.append([user_query, nested_output])
                
                return (
                    history,
                    "",  # 清空輸入框
                    "您可以繼續詢問問題或輸入修改指令，或輸入「完成修改」退出。",
                    gr.update(visible=False),
                    gr.update(visible=False),
                    file_state
                )
                
            except Exception as e:
                error_msg = f"❌ 處理時發生錯誤：{str(e)}"
                history.append([user_query, error_msg])
                return (
                    history,
                    "",
                    error_msg,
                    gr.update(visible=False),
                    gr.update(visible=False),
                    file_state
                )
        
        # 檢查是否是約束修改請求
        if any(keyword in user_query for keyword in ['設為硬約束', '範圍設為', '固定為', '移除', '設為 True', '設為 False']):
            # 獲取當前檔案狀態
            current_file_state = getattr(legal_query_interface, 'current_file_state', None)
            
            if not current_file_state:
                history.append([user_query, "❌ 無可用的程式碼檔案，請先完成案例分析。"])
                return history, "", "錯誤：無可用檔案", gr.update(visible=False), gr.update(visible=False), None
            
            # 處理約束修改
            return handle_constraint_modification(user_query, history, current_file_state, None)
        # 修正：檢查是否為分析觸發指令
        is_analysis_trigger = any(keyword in user_query.lower() for keyword in ['繼續分析', '約束修改'])
        
        # 修正：只有在沒有現有 GroupChat 時才創建新的
        if not hasattr(legal_query_interface, 'current_group_chat_manager'):
            # 創建新的 GroupChat
            group_chat = create_group_chat()
            group_chat_manager = GroupChatManager(
                groupchat=group_chat,
                llm_config=llm_config,
                is_termination_msg=lambda x: "content" in x and x["content"] is not None and (
                    "TERMINATE" in x["content"] or 
                    "REPORT_GENERATED" in x["content"] or 
                    "SUMMARY_COMPLETE" in x["content"] or
                    "REPORT_COMPLETE" in x["content"]
                ),
            )
            legal_query_interface.current_group_chat_manager = group_chat_manager
            
            # 初始化消息計數
            legal_query_interface.last_processed_message_count = 0
            
            # 重置全局變量（僅在第一次創建時）
            global extracted_codes
            extracted_codes = []
        
        # 使用現有的 group_chat_manager
        group_chat_manager = legal_query_interface.current_group_chat_manager
        
        # 如果是繼續分析的請求
        if continue_analysis:
            chat_result = user_proxy.send(
                message="繼續分析",
                recipient=group_chat_manager,
                request_reply=True
            )
        elif is_analysis_trigger:
            # 處理特定的分析觸發指令
            chat_result = user_proxy.send(
                message=user_query,
                recipient=group_chat_manager,
                request_reply=True
            )
        else:
            # 正常的對話
            chat_result = user_proxy.send(
                message=user_query,
                recipient=group_chat_manager,
                request_reply=True
            )
        
        # 獲取完整的對話歷史 - 保持系統內部記憶
        chat_messages = group_chat_manager.groupchat.messages
        
        # 提取最終報告和檢查狀態
        final_report = ""
        conversation_output = ""
        needs_confirmation = False
        needs_constraint_modification = False
        current_file_state = None
        
        # 新增：只顯示最近的相關對話
        display_start_index = getattr(legal_query_interface, 'last_processed_message_count', 0)
        
        # 只處理新的消息來更新顯示
        new_messages = chat_messages[display_start_index:]
        
        # 更新已處理的消息計數
        legal_query_interface.last_processed_message_count = len(chat_messages)
        
        # 檢查是否有重要的 Agent 發言（如 host_agent 的簡短回應）
        display_messages = []
        
        # 特殊處理：只顯示關鍵 Agent 的新回應
        for message in new_messages:
            role = message.get("name", "unknown")
            content = message.get("content", "")
            
            # 檢查各種狀態
            if role == "case_summarizer" and "SUMMARY_COMPLETE" in content:
                needs_confirmation = True
                content = content.replace("SUMMARY_COMPLETE", "").strip()
            
            # 檢查是否需要約束修改確認
            if role == "report_generator" and "REPORT_COMPLETE" in content:
                needs_constraint_modification = True
                continue_analysis = False  
                content = content.replace("REPORT_COMPLETE", "").strip()
                
                print('needs_constraint_modification set to True')
            
            # 保存最終報告
            if role == "report_generator":
                if "REPORT_GENERATED" in content or "REPORT_COMPLETE" in content:
                    final_report = content.replace("REPORT_GENERATED", "").replace("REPORT_COMPLETE", "").strip()
                else:
                    final_report = content.strip()
            elif role == "legal_assistant" and not final_report:
                final_report = f"# 綜合分析報告\n\n{content.strip()}"
            
            if role in ["host_agent", "case_summarizer", "legal_assistant", "report_generator"]:
                # 過濾掉系統判斷訊息和工具呼叫，只顯示實際回應
                if role == "host_agent":
                    # 過濾以下內容：
                    # 1. 系統判斷訊息
                    # 2. 工具呼叫（Suggested tool call）
                    # 3. 工具呼叫結果的技術細節
                    if any(keyword in content for keyword in [
                        "[系統判斷]",
                        "Suggested tool call",
                        "call_",
                        "Arguments:",
                        "***** Suggested"
                    ]):
                        continue
                    # 如果內容太短或只包含特殊符號，也跳過
                    if len(content.strip()) < 10 or content.strip().startswith("*****"):
                        continue
                    # 顯示實際的回應內容
                    display_messages.append(f"**🤖 Host Agent：**\n{content}\n\n")
                elif role == "case_summarizer":
                    display_messages.append(f"**📄 案例摘要Agent：**\n{content}\n\n")
                elif role == "legal_assistant":
                    display_messages.append(f"**⚖️ 結論分析Agent：**\n{content}\n\n")

        
        # 合併顯示內容
        conversation_output = "---\n\n".join(display_messages) if display_messages else ""
        
        # 設置默認報告
        if not final_report:
            if needs_confirmation:
                final_report = "案例摘要已完成，等待用戶確認是否繼續分析..."
            elif needs_constraint_modification:
                final_report = "分析報告已完成，等待用戶確認是否進行約束修改..."
            else:
                final_report = "分析進行中，總報告將在所有代理完成工作後顯示..."
        
        # 更新歷史記錄 - 只添加新內容
        if not continue_analysis and conversation_output.strip():
            history.append([user_query, conversation_output])
        elif continue_analysis and conversation_output.strip():
            if history:
                # 更新最後一條記錄而不是添加新的
                history[-1][1] += conversation_output
        
        if continue_analysis:
            return history, "", final_report, gr.update(visible=False), gr.update(visible=False), current_file_state

        if needs_confirmation and not continue_analysis:
            return history, "", final_report, gr.update(visible=True), gr.update(visible=False), current_file_state
        if needs_constraint_modification:
            print("[DEBUG] 偵測到需要約束修改")
            # 從對話歷史中提取檔案名稱
            for message in reversed(chat_messages):
                content = message.get('content', '')
                if '.py' in content and 'case' in content:
                    import re
                    # 修改正則表達式以匹配實際的檔案名格式
                    # 匹配 case_case_X_code.py 或 case_X_code.py
                    match = re.search(r'(case_[^/\s]+\.py)', content)
                    if match:
                        current_file_state = match.group(1)
                        legal_query_interface.current_file_state = current_file_state
                        print(f'[DEBUG] 找到檔案: {current_file_state}')
                        break
            
            if not current_file_state:
                print('[DEBUG] 警告：未找到程式碼檔案')
            else:
                print(f'Current file state for constraint modification: {current_file_state}')

            return (
                    history,
                    "",  # 清空輸入框
                    final_report,
                    gr.update(visible=False),  # 隱藏繼續分析按鈕
                    gr.update(visible=True),   # 顯示約束修改按鈕區
                    current_file_state
                )
        else:
            return history, "", final_report, gr.update(visible=False), gr.update(visible=False), current_file_state

    except Exception as e:
        error_message = f"發生錯誤：{str(e)}"
        if not continue_analysis:
            history.append([user_query, error_message])
        return history, "", f"# 錯誤報告\n\n{error_message}", gr.update(visible=False), gr.update(visible=False), None

# 新增清除對話的函數
def clear_conversation():
    """清除對話歷史和重置狀態"""
    # 清除 GroupChatManager
    if hasattr(legal_query_interface, 'current_group_chat_manager'):
        delattr(legal_query_interface, 'current_group_chat_manager')
    
    # 清除文件狀態
    if hasattr(legal_query_interface, 'current_file_state'):
        delattr(legal_query_interface, 'current_file_state')
    
    # 清除消息計數
    if hasattr(legal_query_interface, 'last_processed_message_count'):
        delattr(legal_query_interface, 'last_processed_message_count')
    
    # 清除新對話開始位置
    if hasattr(legal_query_interface, 'new_conversation_start'):
        delattr(legal_query_interface, 'new_conversation_start')
    
    # 重置全局變量
    global extracted_codes
    extracted_codes = []
    
    # 返回空的聊天歷史和重置的UI狀態
    return (
        [],  # 清空聊天歷史
        "",  # 清空輸入框
        "分析完成後，總報告將顯示在此處",  # 重置報告顯示
        gr.update(visible=False),  # 隱藏確認按鈕
        gr.update(visible=False),  # 隱藏約束修改按鈕
        None  # 重置文件狀態
    )
def continue_analysis_action(history):
    """繼續分析的動作"""
    # 先在聊天框中顯示正在分析的狀態
    history.append(["系統", "正在分析中，請稍候..."])
    
    # 調用 legal_query_interface 進行分析
    updated_history, query_input, final_report, _, constraint_modification_row, file_state = legal_query_interface("", history, continue_analysis=True)
    
    # 確保確認按鈕區域被隱藏
    return (
        updated_history,
        query_input, 
        final_report, 
        gr.update(visible=False),  # 強制隱藏確認按鈕區域
        constraint_modification_row,  # 保持約束修改按鈕的原始狀態
        file_state
    )
def stop_analysis_action():
    """停止分析的動作"""
    return gr.update(visible=False), gr.update(visible=False)



def format_search_results(query):
    """Format search results for display"""
    try:
        results = search_and_rerank(query, top_k=5)
        
        if not results['ranked_documents']:
            return "未找到相關案例。"
        
        formatted_output = f"## 查詢：{query}\n\n"
        
        for i, (doc, metadata, doc_id) in enumerate(zip(
            results['ranked_documents'], 
            results['ranked_metadatas'], 
            results['ids']
        )):
            formatted_output += f"### 案例 {i+1}\n"
            formatted_output += f"**ID：** {doc_id}\n"
            formatted_output += f"**內容：** {doc[:500]}...\n"
            if metadata:
                formatted_output += f"**元資料：** {metadata}\n"
            formatted_output += "\n---\n\n"
        
        return formatted_output
        
    except Exception as e:
        return f"搜尋時發生錯誤：{str(e)}"


# Gradio Interface
with gr.Blocks(title="Financial Compliance Agent", theme=gr.themes.Soft()) as demo: 
    with gr.Row():
        gr.Markdown("# 🏛️ Financial Compliance Agent")

    manager_state = gr.State(value=None)
    with gr.Tab("🤖 多 AGENT 金融判例分析"):
        file_state = gr.State(value=None)
        
        
        with gr.Row():
            with gr.Column(scale=1):
                chatbot = gr.Chatbot(
                    label="多代理對話歷史",
                    height=800,
                    show_label=True
                )
        with gr.Row():
            query_input = gr.Textbox(
                label="請輸入您的法律問題",
                placeholder="例如：請幫我找出與『資本適足率不足』相關的最新判決案例",
                lines=2,
                scale=4
            )
            submit_btn = gr.Button("提交查詢", variant="primary", scale=1)
        clear_btn = gr.Button("清除對話", variant="secondary")
        
        with gr.Row(visible=False) as constraint_modification_row:
            with gr.Column():
                gr.Markdown("### 🛠️ 進階分析選項")
                gr.Markdown("分析報告已完成！您可以選擇進行約束修改分析，調整程式碼中的約束條件並重新計算最佳解。")
                
            with gr.Column():
                constraint_modify_btn = gr.Button("✏️ 約束修改分析", variant="primary")
                skip_modify_btn = gr.Button("⏭️ 完成分析", variant="secondary")
        # 新增確認按鈕區域
        with gr.Row(visible=False) as confirmation_row:
            
            with gr.Column():
                gr.Markdown("### 是否要繼續進行深度分析？")
                gr.Markdown("案例摘要已完成，您可以選擇繼續進行程式碼執行和法律分析，或者停止在此階段。")
                
            with gr.Column():
                continue_btn = gr.Button("✅ 繼續分析", variant="primary")
                stop_btn = gr.Button("❌ 停止分析", variant="secondary")
            
        
        with gr.Row():
            with gr.Column(scale=1):
                final_report_display = gr.Markdown(
                    label="📋 總分析報告",
                    value="分析完成後，總報告將顯示在此處",
                    height=600
                )
        
        def create_constraint_nested_chat(file_state):
            """
            建立約束修改的 Nested Chat，包含 host agent 來判斷意圖
            """
            return GroupChat(
                agents=[constraint_host_agent, modify_agent, result_analyst, user_proxy],
                messages=[],
                max_round=15,  # 增加輪數以支援對話
                speaker_selection_method=constraint_state_transition  # 使用自定義的狀態轉換
            )

        
                        
                
        def constraint_state_transition(last_speaker, groupchat):
            """
            約束修改 Nested Chat 的狀態轉換邏輯
            """
            messages = groupchat.messages
            
            print(f"[DEBUG] Last speaker: {last_speaker.name if hasattr(last_speaker, 'name') else last_speaker}")
            
            if not messages:
                return constraint_host_agent
            
            last_message = messages[-1] if messages else {}
            last_content = last_message.get('content', '').strip()
            
            print(f"[DEBUG] Last content: {last_content[:100]}...")
            
            if last_speaker is constraint_host_agent:
                if "[執行修改]" in last_content:
                    print("[DEBUG] Detected modification request, routing to modify_agent")
                    return modify_agent
                else:
                    return None
            
            if len(messages) >= 2:
                previous_agent_name = messages[-2]['name']
                if previous_agent_name == "modify_agent":
                    return result_analyst 
            
            # elif last_speaker is user_proxy:
            #     print("[DEBUG] Routing to result_analyst")
            #     return result_analyst
            
            elif last_speaker is result_analyst:
                if "TERMINATE" in last_content:
                    return None
                else:
                    print("[DEBUG] Routing back to constraint_host")
                    return constraint_host_agent
            
            return "auto"
                
        
        def handle_constraint_modification_start(history, file_state):
            """
            啟動約束修改流程並顯示約束清單
            """
            if not file_state:
                error_msg = "❌ 無可用的程式碼檔案進行約束修改。"
                history.append(["系統", error_msg])
                return history, "", gr.update(visible=False), file_state
            
            # 檢查檔案是否存在
            filepath = os.path.join("code_execution", file_state)
            if not os.path.exists(filepath):
                print(f"[DEBUG] 檔案不存在: {filepath}")
                
                # 嘗試尋找實際存在的檔案
                try:
                    files = os.listdir("code_execution")
                    py_files = [f for f in files if f.endswith('_code.py')]
                    print(f"[DEBUG] code_execution 目錄中的檔案: {py_files}")
                    
                    if py_files:
                        file_state = py_files[-1]
                        filepath = os.path.join("code_execution", file_state)
                        print(f"[DEBUG] 改用檔案: {file_state}")
                        legal_query_interface.current_file_state = file_state
                    else:
                        error_msg = "❌ code_execution 目錄中沒有可用的程式碼檔案。"
                        history.append(["系統", error_msg])
                        return history, "", gr.update(visible=False), file_state
                except Exception as e:
                    error_msg = f"❌ 檢查檔案時發生錯誤：{str(e)}"
                    history.append(["系統", error_msg])
                    return history, "", gr.update(visible=False), file_state
            
            try:
                # 獲取約束資訊
                soft_config = read_soft_config(file_state)
                labels_and_vars = get_softs_labels_and_vars(file_state)
                
                # 解析約束內容
                import re
                constraint_lines = soft_config.split('\n')
                constraints_data = []
                
                for line in constraint_lines:
                    match = re.search(r'"([^"]+)",\s*(\w+),\s*([^,)]+)', line)
                    if match:
                        description = match.group(1)
                        var_name = match.group(2)
                        default_value = match.group(3).strip()
                        
                        constraints_data.append({
                            'description': description,
                            'var_name': var_name,
                            'default_value': default_value
                        })
                
                # 格式化約束資訊顯示
                constraint_info = f"""
# 🔧 約束修改模式

## 📁 目標檔案
**檔案：** `{file_state}`

---

## 🎯 可調整的約束變數

| 🏷️ 變數描述 | 🔤 變數名 | 📌 當前預設值 |
|------------|----------|---------------|
"""

                for constraint in constraints_data:
                    desc = constraint['description']
                    var_name = constraint['var_name']
                    default_val = constraint['default_value']
                    
                    # 處理布林值顯示
                    if default_val.lower() in ['true', 'false']:
                        display_val = f"{'✅ True' if default_val.lower() == 'true' else '❌ False'}"
                    else:
                        display_val = default_val
                    
                    constraint_info += f"| {desc} | `{var_name}` | {display_val} |\n"
                
                constraint_info += """

---

## 💡 修改指令說明

| 🎯 操作 | 📝 指令格式 | 💭 範例 |
|--------|-------------|---------|
| **設為硬約束** | `將 [變數名] 設為硬約束` | 將 pre_CAR 設為硬約束 |
| **設定範圍** | `將 [變數名] 範圍設為 [下限] 到 [上限]` | 將 risk_capital 範圍設為 100 到 500 |
| **固定數值** | `將 [變數名] 固定為 [數值]` | 將 net_worth_ratio 固定為 3.5 |
| **移除約束** | `移除 [變數名] 的約束` | 移除 asset_risk 的約束 |
| **設定布林** | `將 [變數名] 設為 True/False` | 將 has_signed_contract 設為 True |

---

## ✍️ 您可以：
- 💬 **詢問問題**：「pre_CAR 是什麼意思？」、「目前有哪些約束？」
- ✏️ **執行修改**：直接輸入修改指令（參考上表）
- 🚪 **退出模式**：輸入「完成修改」或「結束修改」

💡 **提示：** 您可以隨時詢問變數的意義或修改方式，系統會先回答您的問題，不會直接執行修改。
        """
                
                # 建立約束修改的 Nested Group Chat
                constraint_group = create_constraint_nested_chat(file_state)
                constraint_manager = GroupChatManager(
                    name="constraint_modifier",
                    groupchat=constraint_group,
                    llm_config=llm_config,
                    is_termination_msg=is_termination_msg,
                )
                
                # 準備詳細的約束資訊給 constraint_host
                constraints_info = f"""
        目標檔案：{file_state}

        可用的約束變數清單：
        """
                for constraint in constraints_data:
                    constraints_info += f"- 變數名: {constraint['var_name']}, 描述: {constraint['description']}, 預設值: {constraint['default_value']}\n"
                
                # 儲存約束資訊和管理器到全局狀態
                legal_query_interface.constraint_manager = constraint_manager
                legal_query_interface.constraints_info = constraints_info
                legal_query_interface.constraints_data = constraints_data
                legal_query_interface.in_constraint_mode = True
                
                print(f"[DEBUG] 約束修改模式已啟用，目標檔案: {file_state}")
                
                # 顯示約束清單
                history.append(["🔧 約束編輯器", constraint_info])
                
                return (
                    history,
                    "",  # 清空輸入框，準備接收指令或問題
                    gr.update(visible=False),  # 隱藏約束修改按鈕區
                    file_state
                )
                
            except Exception as e:
                error_msg = f"❌ 讀取約束資訊時發生錯誤：{str(e)}"
                history.append(["系統", error_msg])
                print(f"[DEBUG] 錯誤詳情: {str(e)}")
                return history, "", gr.update(visible=False), file_state


        def handle_constraint_modification(msg, history, file_state, manager_state):
            """
            處理約束修改指令，啟動 Nested Chat
            """
            if not file_state:
                error_msg = "❌ 無可用的程式碼檔案。"
                history.append(["系統", error_msg])
                return history, "", gr.update(visible=False), file_state, manager_state
            
            try:
                # 獲取當前約束清單
                soft_config = read_soft_config(file_state)
                labels_and_vars = get_softs_labels_and_vars(file_state)
                
                # 解析約束資訊
                import re
                constraint_lines = soft_config.split('\n')
                constraints_data = []
                
                for line in constraint_lines:
                    match = re.search(r'"([^"]+)",\s*(\w+),\s*([^,)]+)', line)
                    if match:
                        description = match.group(1)
                        var_name = match.group(2)
                        default_value = match.group(3).strip()
                        
                        constraints_data.append({
                            'description': description,
                            'var_name': var_name,
                            'default_value': default_value
                        })
                
                # 建立約束修改的 Nested Group Chat
                constraint_group = create_constraint_nested_chat(file_state)
                constraint_manager = GroupChatManager(
                    name="constraint_modifier",
                    groupchat=constraint_group,
                    llm_config=llm_config,
                    is_termination_msg=is_termination_msg,
                )
                
                # 準備詳細的約束資訊給 modify_agent
                constraints_info = "可用的約束變數清單：\n"
                for constraint in constraints_data:
                    constraints_info += f"- 變數名: {constraint['var_name']}, 描述: {constraint['description']}, 預設值: {constraint['default_value']}\n"
                
                initial_message = f"""
請處理以下約束修改指令：

目標檔案：{file_state}
使用者指令：{msg}

{constraints_info}

請根據使用者的自然語言指令，將其轉換為適當的 JSON 格式，然後調用 modify_constraints_tool 執行修改。

支援的指令格式：
- "將 [變數名] 設為硬約束" → hard_constraints
- "將 [變數名] 範圍設為 [數字] 到 [數字]" → range_constraints  
- "將 [變數名] 固定為 [數值/True/False]" → value_changes
- "移除 [變數名] 的約束" → remove_constraints

請確保變數名與上述清單中的變數名完全匹配。
                """
                
                # 啟動 Nested Chat，從 modify_agent 開始
                chat_result = modify_agent.initiate_chat(
                    constraint_manager,
                    message=initial_message
                )
                
                # 格式化 Nested Chat 的結果
                nested_output = ""
                for message in chat_result.chat_history:
                    role = message.get("name", "unknown")
                    content = message.get("content", "")
                    
                    # if role == "modify_agent":
                    #     nested_output += f"**✏️ 修改代理：**\n{content}\n\n---\n\n"
                    if role == "result_analyst":
                        nested_output += f"**📊 結果分析師：**\n{content}\n\n---\n\n"
                    elif role == "user_proxy":
                        if content.strip():  # 只顯示非空內容
                            nested_output += f"**⚙️ 執行結果：**\n{content}\n\n---\n\n"
                
                # 更新歷史記錄
                history.append([msg, nested_output])
                
                return (
                    history,
                    "",                             # 清空輸入框
                    gr.update(visible=True),        # 顯示 action_radio 讓使用者選擇下一步
                    file_state,
                    manager_state
                )
                
            except Exception as e:
                error_msg = f"❌ 約束修改時發生錯誤：{str(e)}"
                history.append(["系統", error_msg])
                return (
                    history,
                    "",
                    gr.update(visible=False),
                    file_state,
                    manager_state
                )
            
                
        def skip_modify_and_clear():
            """
            完成分析並清除所有記錄
            """
            # 清除 GroupChatManager
            if hasattr(legal_query_interface, 'current_group_chat_manager'):
                delattr(legal_query_interface, 'current_group_chat_manager')
            
            # 清除文件狀態
            if hasattr(legal_query_interface, 'current_file_state'):
                delattr(legal_query_interface, 'current_file_state')
            
            # 清除消息計數
            if hasattr(legal_query_interface, 'last_processed_message_count'):
                delattr(legal_query_interface, 'last_processed_message_count')
            
            # 清除新對話開始位置
            if hasattr(legal_query_interface, 'new_conversation_start'):
                delattr(legal_query_interface, 'new_conversation_start')
            
            # 重置全局變量
            global extracted_codes
            extracted_codes = []
            
            # 返回清空的UI狀態
            return (
                [],  # 清空聊天歷史
                "",  # 清空輸入框
                "# ✅ 分析已完成\n\n所有記錄已清除，您可以開始新的查詢。",  # 重置報告顯示
                gr.update(visible=False),  # 隱藏確認按鈕
                gr.update(visible=False),  # 隱藏約束修改按鈕
                None  # 重置文件狀態
            )
        submit_btn.click(
            fn=legal_query_interface,
            inputs=[query_input, chatbot],
            outputs=[chatbot, query_input, final_report_display, confirmation_row, constraint_modification_row, file_state],
        )

        query_input.submit(
            fn=legal_query_interface,
            inputs=[query_input, chatbot],
            outputs=[chatbot, query_input, final_report_display, confirmation_row, constraint_modification_row, file_state],
        )
        
        continue_btn.click(
            fn=continue_analysis_action,
            inputs=[chatbot],
            outputs=[chatbot, query_input, final_report_display, confirmation_row, constraint_modification_row, file_state],
        )
        
        stop_btn.click(
            fn=stop_analysis_action,
            outputs=[confirmation_row, constraint_modification_row]
        )
        constraint_modify_btn.click(
            fn=lambda history, file_state: handle_constraint_modification_start(history, file_state),
            inputs=[chatbot, file_state],
            outputs=[chatbot, query_input, constraint_modification_row, file_state]
        )

        skip_modify_btn.click(
            fn=skip_modify_and_clear,
            outputs=[chatbot, query_input, final_report_display, confirmation_row, constraint_modification_row, file_state]
        )

        skip_modify_btn.click(
            fn=skip_modify_and_clear,
            outputs=[chatbot, query_input, final_report_display, confirmation_row, constraint_modification_row, file_state]
        )



    with gr.Tab("📖 使用說明"):
        gr.Markdown("""
        ## 📖 多代理系統說明
        
        ### 🤖 代理角色
        
        1. **🔍 搜索代理 (Search Agent)**
           - 負責搜索法律案例資料庫
           - 使用 RAG + Reranker 技術找出最相關的案例
        
        2. **💻 程式執行代理 (Code Executor Agent)**
           - 負責執行案例中包含的程式碼
           - 安全執行並記錄結果
        
        3. **🐛 除錯代理 (Debug Agent)**
           - 當程式執行出錯時進行除錯
           - 提供修正建議和解決方案
        
        4. **⚖️ 法律分析師 (Legal Analyst Agent)**
           - 整合所有資訊進行最終法律分析
           - 提供專業的法律建議和解釋
        
        ### 🔄 工作流程
        
        1. 使用者提出法律問題
        2. 搜索代理搜索相關案例
        3. 程式執行代理執行案例中的程式碼
        4. 如有錯誤，除錯代理進行修正
        5. 法律分析師提供最終分析報告
        
        ### ⚠️ 注意事項
        - 本系統僅供參考，不構成法律建議
        - 如需專業法律諮詢，請聯繫律師
        - 程式執行在安全環境中進行
        """)

if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=7861,
        share=True,
        debug=True
    )