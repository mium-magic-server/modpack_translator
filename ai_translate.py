import itertools
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TypedDict

import json_repair
from chromadb import Settings
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.prompts import PromptTemplate
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langgraph.graph import START, StateGraph
from pydantic import SecretStr

from config import openai_embed_base_url, openai_api_key, openai_embed_model, openai_llm_base_url, openai_llm_model


def chunk_dict(d, size=100):
    """将字典按 size 分组，返回一个生成器"""
    items = iter(d.items())
    for _ in range(0, len(d), size):
        yield dict(itertools.islice(items, size))


def build_translate_embed(merged_en2zh_file, db_dir="chroma"):
    # 1. 读取 JSON 文件
    with open(merged_en2zh_file, "r", encoding="utf-8") as f:
        translation_map = json.load(f)

    # 2. 格式化为 key=value 字符串
    documents = [Document(f"{key}={value}") for key, value in translation_map.items()]

    # 3. 创建向量知识库
    embeddings = OpenAIEmbeddings(base_url=openai_embed_base_url, api_key=SecretStr(openai_api_key), model=openai_embed_model, dimensions=768, check_embedding_ctx_length=False)
    return Chroma.from_documents(documents, embeddings, persist_directory=db_dir, client_settings=Settings(is_persistent=True))


def load_translate_embed(db_dir="chroma"):
    embeddings = OpenAIEmbeddings(base_url=openai_embed_base_url, api_key=SecretStr(openai_api_key), model=openai_embed_model, dimensions=768, check_embedding_ctx_length=False)
    return Chroma(collection_name="langchain", embedding_function=embeddings, persist_directory=db_dir, client_settings=Settings(is_persistent=True))

def retrieve_related_words(vectorstore, search_keywords):
    retrieved_docs = list()
    for word in search_keywords:
        docs = vectorstore.similarity_search(word, k=5)
        retrieved_docs.append("\n".join([doc.page_content for doc in docs]))
    return "\n".join(retrieved_docs)

def translate_json(untranslated_file, output_file, db_dir="chroma", max_workers=4):
    vectorstore = load_translate_embed(db_dir)

    llm = ChatOpenAI(base_url=openai_llm_base_url, api_key=SecretStr(openai_api_key), model=openai_llm_model, temperature=0)

    prompt = PromptTemplate.from_template("""
<task>
你是一个翻译助手，将文本翻译为简体中文内容，可以参考下方的翻译记录进行翻译，对于已经有译名的词汇尽量保留原样，没有译名的词汇请参考类似翻译风格翻译。
你需要保留原本的翻译键名，并输出 **规范的 JSON**，不要包含任何解释。
</task>
<untranslated>
待翻译内容:
{question}
</untranslated>
<reference>
翻译参考:
{context}
</reference>
""")

    # Define state for application
    class State(TypedDict):
        question: dict
        context: set[str]
        answer: str

    # Define application steps
    def retrieve(state: State):
        retrieved_docs = set()
        for word in state["question"].values():
            docs = vectorstore.similarity_search(word, k=3)
            retrieved_docs.update([doc.page_content for doc in docs])
        return {"context": retrieved_docs}

    def generate(state: State):
        docs_content = "\n\n".join(state["context"])
        messages = prompt.invoke({"question": json.dumps(state["question"], ensure_ascii=False, indent=2), "context": docs_content})
        response = llm.invoke(messages)
        return {"answer": response.content}

    # Compile application and test
    graph_builder = StateGraph(State).add_sequence([retrieve, generate])
    graph_builder.add_edge(START, "retrieve")
    graph = graph_builder.compile()

    def translate(msg: dict):
        answer: str = graph.invoke({"question": msg}).get("answer")
        return json_repair.loads(answer.removeprefix('```json\n').removesuffix('\n```').strip())

    with open(untranslated_file, "r", encoding="utf-8") as f:
        untranslated = json.load(f)

    results = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        for chunk in chunk_dict(untranslated, 100):
            future = executor.submit(translate, chunk)
            futures.append(future)

        for future in as_completed(futures):
            result = future.result()
            json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
            print()
            results.update(result)
            processed = len(results)
            print(f'{processed} / {len(untranslated)}')

    results = dict(sorted(results.items()))
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

def translate_document(vectorstore, input_document):
    llm = ChatOpenAI(base_url=openai_llm_base_url, api_key=SecretStr(openai_api_key), model=openai_llm_model, temperature=0)

    extract_prompt = PromptTemplate.from_template("""
<task>
你是一个专业的实体提取专家。
请提取下面文章中的**名词**，输出为纯文本格式，一行一个，不要包含任何多余的解释和标志。
</task>
<input_document>
{input_document}
</input_document>
""")

    prompt = PromptTemplate.from_template("""
<任务>
你是一个翻译助手，将文本翻译为简体中文内容，可以参考下方的翻译记录进行翻译，对于已经有译名的词汇尽量保留原样，没有译名的词汇请参考类似翻译风格翻译。
你需要保留原文的特殊标记，这些是占位符，请直接输出翻译后的文本，不要输出多余内容，**不要包含任何解释和说明**。
</任务>
<待翻译内容>
{input_document}
</待翻译内容>
<翻译参考>
{context}
</翻译参考>
""")

    # Define state for application
    class State(TypedDict):
        input_document: str
        words_to_search: list[str]
        context: set[str]
        answer: str

    def extract_keywords(state: State):
        query = state["input_document"]
        messages = extract_prompt.invoke({"input_document": query})
        response = llm.invoke(messages)
        response_text = response.content
        words = response_text.splitlines()
        return {"words_to_search": words}

    # Define application steps
    def retrieve(state: State):
        retrieved_docs = set()
        for word in state["words_to_search"]:
            docs = vectorstore.similarity_search(word, k=5)
            retrieved_docs.update([doc.page_content for doc in docs])
        return {"context": retrieved_docs}

    def generate(state: State):
        docs_content = "\n\n".join(state["context"])
        messages = prompt.invoke({"input_document": state["input_document"], "context": docs_content})
        response = llm.invoke(messages)
        return {"answer": response.content}

    graph_builder = StateGraph(State).add_sequence([extract_keywords, retrieve, generate])
    graph_builder.add_edge(START, "extract_keywords")
    graph = graph_builder.compile()
    answer = graph.invoke({"input_document": input_document}).get("answer")
    return answer.strip()