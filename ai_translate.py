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

def chunk_list(lst, chunk_size):
    """
    将一个大列表分割成多个小块，每个小块的大小为 chunk_size。

    :param lst: 要分割的列表
    :param chunk_size: 每个小块的大小
    :return: 生成器，每个元素是一个小块（子列表）
    """
    for i in range(0, len(lst), chunk_size):
        yield lst[i:i + chunk_size]

def load_translate_embed(db_dir="chroma"):
    embeddings = OpenAIEmbeddings(base_url=openai_embed_base_url, api_key=SecretStr(openai_api_key), model=openai_embed_model, dimensions=768, check_embedding_ctx_length=False)
    return Chroma(collection_name="langchain", embedding_function=embeddings, persist_directory=db_dir, client_settings=Settings(is_persistent=True))

def build_translate_embed(merged_en2zh_file, db_dir="chroma"):
    # 1. 读取 JSON 文件
    with open(merged_en2zh_file, "r", encoding="utf-8") as f:
        translation_map = json.load(f)

    # 2. 格式化为 key=value 字符串
    documents = [Document(f"{key}={value}", id=key) for key, value in translation_map.items() if len(key) > 0]

    # 3. 删除已存在的术语
    vector_storage = load_translate_embed(db_dir)
    ids = [doc.id for doc in documents]
    vector_storage.delete(ids)

    # 4. 添加新的术语
    for chunk in chunk_list(documents, 4096):
        vector_storage.add_documents(chunk)

    return vector_storage

def retrieve_related_words(vectorstore, search_keywords):
    retrieved_docs = list()
    for word in search_keywords:
        docs = vectorstore.similarity_search(word, k=5)
        retrieved_docs.append("\n".join([doc.page_content for doc in docs]))
    return "\n".join(retrieved_docs)

def translate_json(untranslated_file, output_file, db_dir="chroma", max_workers=8):
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
        docs_content = "\n".join(state["context"])
        messages = prompt.invoke({"question": json.dumps(state["question"], ensure_ascii=False, indent=2), "context": docs_content})
        response_text = ""
        for delta in llm.stream(messages):
            response_text += delta.content
        return {"answer": response_text}

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

def translate_document(input_document, db_dir="chroma"):
    vectorstore = load_translate_embed(db_dir)
    llm = ChatOpenAI(base_url=openai_llm_base_url, api_key=SecretStr(openai_api_key), model=openai_llm_model, temperature=0, max_retries=10)

    extract_prompt = PromptTemplate.from_template("""
<task>
你是一个专业的实体提取专家。
下面是一些和 Minecraft 某个模组相关的说明文章，
请提取下面文章中所有可能有翻译歧义的单词和短语，尤其是专有名词和形容词，
**你需要尽可能找到所有的单词和短语，避免任何遗漏。**
输出为纯文本格式，一行一个单词，不要包含任何多余的解释和标志。
</task>
<input_document>
{input_document}
</input_document>
""")

    prompt = PromptTemplate.from_template("""
# 任务
你是一个专业的 Minecraft 模组翻译助手，请根据游戏设定和背景，将文本翻译为 **简体中文内容**，
可以参考下方的翻译记录进行翻译，对于已经有译名的词汇尽量保留原样，没有译名的词汇请参考类似翻译风格翻译。
翻译风格请保持自然并符合中文表达习惯，可以调整语序和适当润色。
文档开头的 --- 标注请保留格式，这些是元数据的一部分，其中的 title 和 categories 等说明需要翻译为中文，其余的类似标识符的部分请保留原样。
文档中的 XML 标签如 &lt;ItemImage&gt; 等标签请保留原样，只有描述部分可以翻译。
你需要保留原文的特殊标记，这些是占位符，请直接输出翻译后的文本，不要输出多余内容，**不要包含任何解释和说明**。

# 待翻译内容

```markdown
{input_document}
```
# 翻译参考

```text
{context}
```
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
        response_text = ""
        for delta in llm.stream(messages):
            response_text += delta.content
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
        docs_content = "\n".join(state["context"])
        messages = prompt.invoke({"input_document": state["input_document"], "context": docs_content})
        response_text = ""
        for delta in llm.stream(messages):
            response_text += delta.content
        return {"answer": response_text}

    graph_builder = StateGraph(State).add_sequence([extract_keywords, retrieve, generate])
    graph_builder.add_edge(START, "extract_keywords")
    graph = graph_builder.compile()
    answer = graph.invoke({"input_document": input_document}).get("answer")
    return answer.removeprefix('```markdown\n').removesuffix('\n```').strip()

def translate_dict(untranslated: dict, db_dir="chroma", max_workers=8):
    vectorstore = load_translate_embed(db_dir)
    llm = ChatOpenAI(base_url=openai_llm_base_url, api_key=SecretStr(openai_api_key), model=openai_llm_model)

    extract_prompt = PromptTemplate.from_template("""
<task>
你是一个专业的实体提取专家。
下面是一些和 Minecraft 某个模组相关的语言文件，
请提取下面语言配置文件中所有的单词和短语，尤其是专有名词和形容词，
请注意提取出的单词不要带有颜色和格式控制符号，如 &a 等。
**你需要尽可能找到所有的单词和短语，避免任何遗漏。**
输出为纯文本格式，一行一个单词，不要包含任何多余的解释和标志。
</task>
<input_document>
{input_document}
</input_document>
""")

    prompt = PromptTemplate.from_template("""
# 任务
你是一个专业的 Minecraft 模组翻译助手，请根据游戏设定和背景，将文件内容翻译为 **简体中文内容**，
可以参考下方的翻译记录进行翻译，对于已经有译名的词汇尽量保留原样，没有译名的词汇请参考类似翻译风格翻译。
翻译风格请保持自然并符合中文表达习惯，可以调整语序和适当润色。
文件中的颜色和格式控制符号如 &a 等请保留原样，图片引用也保留原样，只翻译文本。
可以翻译的文本要尽可能翻译。人名、作品名等专有名词，如果有翻译参考，也要翻译，如果没有参考，可以按照没有歧义的风格翻译。

你需要保留原本的**翻译键名**，保留原始的结构，保留颜色代码，保留以 {{}} 包裹的占位符，并输出规范的 json，不要包含任何解释

# 待翻译内容

```json
{input_document}
```
# 翻译参考

```text
{context}
```
""")

    # Define state for application
    class State(TypedDict):
        question: dict
        words_to_search: list[str]
        context: set[str]
        answer: str

    def extract_keywords(state: State):
        query = state["question"]
        query_values = []
        for value in query.values():
            if isinstance(value, str):
                query_values.append(value)
            elif isinstance(value, list):
                query_values.extend(value)
        search_document = json.dumps(query_values, ensure_ascii=False)
        messages = extract_prompt.invoke({"input_document": search_document})
        response_text = ""
        for delta in llm.stream(messages):
            response_text += delta.content
        words = response_text.splitlines()
        return {"words_to_search": words}

    # Define application steps
    def retrieve(state: State):
        retrieved_docs = set()
        for chunk in chunk_dict(state["question"], 10):
            docs = []
            for key, value in chunk.items():
                if isinstance(value, str):
                    s_docs = vectorstore.similarity_search(value, k=2)
                    docs.extend(s_docs)
                elif isinstance(value, list):
                    for content in value:
                        s_docs = vectorstore.similarity_search(content, k=2)
                        docs.extend(s_docs)
            retrieved_docs.update([doc.page_content for doc in docs])
        for word in state["words_to_search"]:
            docs = vectorstore.similarity_search(word, k=5)
            retrieved_docs.update([doc.page_content for doc in docs])
        return {"context": retrieved_docs}

    def generate(state: State):
        docs_content = "\n".join(state["context"])
        query = state["question"]
        input_document = json.dumps(query, ensure_ascii=False)
        messages = prompt.invoke({"input_document": input_document, "context": docs_content})
        response_text = ""
        for delta in llm.stream(messages):
            response_text += delta.content
        return {"answer": response_text}

    graph_builder = StateGraph(State).add_sequence([extract_keywords, retrieve, generate])
    graph_builder.add_edge(START, "extract_keywords")
    graph = graph_builder.compile()

    def translate(msg: dict):
        answer: str = graph.invoke({"question": msg}).get("answer")
        return json_repair.loads(answer.removeprefix('```json\n').removesuffix('\n```').strip())

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

    return results