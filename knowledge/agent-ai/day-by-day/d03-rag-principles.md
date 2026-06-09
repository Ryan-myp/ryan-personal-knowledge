# Day 3: RAG 系统 — 从入门到源码级

> 学习目标: 先理解 RAG 是什么、怎么用，再深入源码

---

## 第一部分：入门引导（5 分钟速览）

### 3.1 RAG 是什么？

```
RAG = Retrieval-Augmented Generation = 检索增强生成

问题: LLM 训练数据有截止时间，不知道最新信息。
问题: LLM 不知道你的私有数据（公司文档、个人笔记）。
问题: LLM 会幻觉（编造事实）。

解决方案: RAG

核心思想:
用户问题 → 检索相关知识 → 组装上下文 → LLM 生成答案

类比:
你考试前复习 → 先查资料（检索）→ 再看问题（查询）→ 结合资料回答（生成）
```

### 3.2 RAG 完整流程图

```
┌─────────────────────────────────────────────────────────────┐
│                    RAG 系统完整流程                           │
│                                                             │
│  ┌──────────┐                                               │
│  │ 文档入库  │                                               │
│  └────┬─────┘                                               │
│       │                                                     │
│       ▼                                                     │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │  文档切片    │→│  向量化       │→│  存储到向量数据库  │  │
│  │ (Chunking)  │  │ (Embedding)  │  │   (FAISS/Redis)  │  │
│  └─────────────┘  └──────────────┘  └──────────────────┘  │
│                                                             │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  用户提问: "什么是 RAG？"                               │ │
│  └──────────────────────┬─────────────────────────────────┘ │
│                         │                                   │
│                         ▼                                   │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │  问题向量化  │→│  向量检索     │→│  获取 Top-K 文档  │  │
│  └─────────────┘  └──────────────┘  └──────────────────┘  │
│                         │                                   │
│                         ▼                                   │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  组装 Prompt:                                         │ │
│  │  "基于以下上下文回答问题:                               │ │
│  │   上下文: [文档1]\n[文档2]\n[文档3]                    │ │
│  │   问题: 什么是 RAG？"                                  │ │
│  └──────────────────────┬─────────────────────────────────┘ │
│                         │                                   │
│                         ▼                                   │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  LLM 生成答案                                          │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 3.3 RAG 的 5 个核心组件

| 组件 | 作用 | 简单理解 |
|------|------|----------|
| **文档切片** | 把长文档切成小块 | 把书撕成章节 |
| **向量化** | 把文本转换成数字 | 给每章编个号码 |
| **向量数据库** | 存储和检索向量 | 建个目录 |
| **重排序** | 对检索结果重新排序 | 挑最相关的 |
| **上下文组装** | 把相关知识拼成 Prompt | 整理复习资料 |

### 3.4 快速体验

```python
# 安装依赖
pip install langchain langchain-chroma chromadb

# 1. 准备文档
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma

documents = [
    "RAG 是一种检索增强生成的技术。",
    "它通过检索相关知识来增强 LLM 的回答能力。",
    "RAG 的核心组件包括向量化、向量数据库和重排序。"
]

# 2. 切片
splitter = RecursiveCharacterTextSplitter(
    chunk_size=100,
    chunk_overlap=20
)
chunks = splitter.split_text("\n".join(documents))
print("切片结果:", chunks)

# 3. 创建向量数据库
embeddings = OpenAIEmbeddings()
vectorstore = Chroma.from_texts(
    texts=chunks,
    embedding=embeddings
)

# 4. 检索
results = vectorstore.similarity_search("什么是 RAG?", k=2)
for r in results:
    print("文档:", r.page_content)
```

运行后你会看到：

```
切片结果: ['RAG 是一种检索增强生成的技术。', '它通过检索相关知识来增强 LLM 的回答能力。', 'RAG 的核心组件包括向量化、向量数据库和重排序。']
文档: RAG 是一种检索增强生成的技术。
文档: RAG 的核心组件包括向量化、向量数据库和重排序。
```

### 3.5 关键概念总结

| 概念 | 说明 |
|------|------|
| **Chunking** | 文档切片，把长文档切成小块 |
| **Embedding** | 向量化，把文本转换成数字向量 |
| **Vector Store** | 向量数据库，存储和检索向量 |
| **Similarity Search** | 相似度搜索，找最相关的文档 |
| **Reranking** | 重排序，对检索结果重新排序 |

---

## 第二部分：源码级深度剖析

### 3.6 文档切片源码

```python
# langchain_text_splitters/recursive_character.py
# 递归字符文本拆分器

class RecursiveCharacterTextSplitter(TextSplitter):
    """
    递归字符文本拆分器
    
    策略:
    1. 尝试按大的分隔符切分（如段落）
    2. 如果太大，尝试按小的分隔符切分（如句子）
    3. 如果还太大，按字符切分
    
    常用分隔符:
    - ["\n\n", "\n", " ", ""]
    - 先按段落切，再按行切，再按词切，最后按字符切
    """
    
    def __init__(
        self,
        separators: Optional[List[str]] = None,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        length_function: Callable[[str], int] = len,
        keep_separator: bool = True,
    ):
        self._separators = separators or ["\n\n", "\n", " ", ""]
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap
        self._length_function = length_function
        self._keep_separator = keep_separator
    
    def split_text(self, text: str) -> List[str]:
        """
        分割文本
        
        流程:
        1. 遍历分隔符（从大到小）
        2. 用当前分隔符切分
        3. 如果块太大，递归切分
        4. 添加重叠部分
        """
        return self._split_text(text, self._separators)
    
    def _split_text(self, text: str, separators: List[str]) -> List[str]:
        """递归切分"""
        final_chunks = []
        
        # 获取当前分隔符
        separator = separators[-1]
        new_separators = separators[:-1] if len(separators) > 1 else []
        
        # 用分隔符切分
        splits = _split_text_with_regex(text, separator, self._keep_separator)
        
        # 对每个部分递归处理
        good_split = _split_text_with_size(splits, self._chunk_size, self._length_function)
        
        for s in good_split:
            if self._length_function(s) > self._chunk_size:
                # 如果还太大，用更小的分隔符递归切分
                if new_separators:
                    for s in self._split_text(s, new_separators):
                        final_chunks.append(s)
                else:
                    # 没有更小的分隔符了，直接切
                    for s in splits:
                        final_chunks.append(s)
            else:
                final_chunks.append(s)
        
        return final_chunks
```

### 3.7 向量化源码

```python
# langchain_community/embeddings/openai.py
# OpenAI 嵌入模型

class OpenAIEmbeddings(BaseEmbeddings):
    """
    OpenAI 嵌入模型
    
    原理:
    1. 把文本转换成 token IDs
    2. 通过 Transformer 模型
    3. 取最后一个 hidden state 作为向量
    4. L2 归一化
    
    模型: text-embedding-ada-002
    维度: 1536
    """
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        批量嵌入文档
        
        流程:
        1. 批量发送请求到 OpenAI API
        2. 接收向量响应
        3. 返回向量列表
        """
        # 批量处理（每次最多 2048 个文本）
        all_embeddings = []
        for i in range(0, len(texts), 2048):
            batch = texts[i:i+2048]
            response = self.client.create(input=batch, model=self.model)
            
            # 提取向量
            batch_embeddings = [e["embedding"] for e in response.data]
            all_embeddings.extend(batch_embeddings)
        
        return all_embeddings
    
    def embed_query(self, text: str) -> List[float]:
        """嵌入单个查询"""
        response = self.client.create(input=[text], model=self.model)
        return response.data[0]["embedding"]
```

### 3.8 向量数据库源码

```python
# langchain_community/vectorstores/chroma.py
# Chroma 向量数据库

class Chroma(BasePydanticVectorStore):
    """
    Chroma 向量数据库
    
    特点:
    - 嵌入式数据库，无需额外服务
    - 支持 HNSW 索引
    - 支持余弦相似度、L2、内积
    
    核心参数:
    - collection_name: 集合名称
    - embedding_function: 嵌入函数
    - distance_func: 距离函数（cosine/l2/ip）
    """
    
    def __init__(
        self,
        collection_name: str = "",
        embedding_function: Optional[Embeddings] = OpenAIEmbeddings(),
        persist_directory: Optional[str] = None,
        collection_metadata: Optional[Dict] = None,
        host: Optional[str] = None,
        port: Optional[str] = None,
        database: str = "main",
        tenant: str = "default_tenant",
        database_type: str = "chroma",
    ):
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            embedding_function=embedding_function,
            metadata=collection_metadata,
        )
    
    def similarity_search(
        self,
        query: str,
        k: int = 4,
        filter: Optional[Dict[str, str]] = None,
    ) -> List[Document]:
        """
        相似度搜索
        
        流程:
        1. 将查询文本向量化
        2. 在向量数据库中搜索最近邻
        3. 返回相关文档
        
        HNSW 算法:
        - Hierarchical Navigable Small World
        - 构建多层图结构
        - 从顶层开始搜索，逐层逼近
        - 时间复杂度: O(log N)
        """
        # 1. 向量化查询
        query_embedding = self._embedding_function.embed_query(query)
        
        # 2. 搜索最近邻
        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=k,
            include=["documents", "metadatas", "distances"],
        )
        
        # 3. 构建文档对象
        documents = []
        for i, doc in enumerate(results["documents"][0]):
            documents.append(
                Document(
                    page_content=doc,
                    metadata=results["metadatas"][0][i] if results["metadatas"] else {},
                )
            )
        
        return documents
```

### 3.9 重排序源码

```python
# langchain/retrievers/retriever_utils.py
# 重排序器

class ContextualCompressionRetriever(BaseRetriever):
    """
    上下文压缩检索器
    
    原理:
    1. 先用向量检索返回 Top-K
    2. 再用重排序器对结果重新排序
    3. 返回 Top-N
    
    重排序模型:
    - Cross-Encoder: 对 (query, doc) 对联合编码
    - 精度更高，但速度更慢
    """
    
    def _get_relevant_documents(
        self,
        query: str,
        *,
        run_manager: CallbackManagerForRetrieverAction,
        **kwargs: Any,
    ) -> List[Document]:
        """
        获取相关文档
        
        流程:
        1. 向量检索
        2. 重排序
        3. 压缩上下文
        """
        # 1. 向量检索
        initial_docs = self.base_retriever.invoke(query)
        
        # 2. 重排序
        if self.compressors:
            for compressor in self.compressors:
                initial_docs = compressor.compress_documents(
                    initial_docs, query
                )
        
        # 3. 返回结果
        return initial_docs
```

### 3.10 上下文组装源码

```python
# langchain/chains/retrieval.py
# 检索链

def create_retrieval_chain(
    retriever: BaseRetriever,
    llm: BaseLanguageModel,
    combine_docs_chain: Runnable,
) -> Runnable:
    """
    创建检索链
    
    流程:
    1. 检索相关文档
    2. 组装 Prompt
    3. LLM 生成答案
    """
    
    def format_docs(docs):
        """格式化文档为字符串"""
        return "\n\n".join([doc.page_content for doc in docs])
    
    # 组装 Prompt
    prompt = ChatPromptTemplate.from_messages([
        ("system", "你是一位专业的问答助手。请基于以下上下文回答问题。\n\n上下文:\n{context}"),
        ("human", "{question}"),
    ])
    
    # 创建链
    chain = (
        {"context": retriever | format_docs, "question": RunnablePassthrough()}
        | prompt
        | llm
    )
    
    return chain
```

---

## 第三部分：自测

### 问题 1
为什么需要文档切片？
<details>
<summary>查看答案</summary>

1. LLM 有 token 限制
2. 不需要一次性加载全部文档
3. 每次只检索相关的
4. 节省成本和延迟
</details>

### 问题 2
什么是 Embedding？为什么需要它？
<details>
<summary>查看答案</summary>

Embedding 是把文本转换成数字向量。

需要的原因:
- 向量数据库用向量相似度搜索
- 语义相似的文本，向量也相似
- "北京天气" 和 "北京气温" 能匹配到
</details>

### 问题 3
重排序的作用是什么？
<details>
<summary>查看答案</summary>

- 向量检索返回 Top-K（如 10 个）
- 但这些可能不够准确
- 重排序模型对 (query, doc) 对打分
- 重新排序后取 Top-N（如 5 个）
- 精度更高
</details>

---

## 第四部分：动手验证

### 4.1 测试不同切片大小的效果

```python
from langchain_text_splitters import RecursiveCharacterTextSplitter

# 测试不同切片大小
texts = ["这是一段很长的文本，包含很多信息。"] * 10

for chunk_size in [50, 100, 200, 500]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=10
    )
    chunks = splitter.split_text(" ".join(texts))
    print(f"chunk_size={chunk_size}: {len(chunks)} chunks")
```

**观察**: 切片越小，chunk 越多，但可能切断语义。

### 4.2 测试向量检索效果

```python
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import OpenAIEmbeddings

# 创建向量数据库
embeddings = OpenAIEmbeddings()
vectorstore = Chroma.from_texts(
    texts=["RAG 是检索增强生成。", "LLM 是大语言模型。", "向量数据库存储向量。"],
    embedding=embeddings
)

# 检索
results = vectorstore.similarity_search("什么是 RAG?", k=2)
for r in results:
    print("文档:", r.page_content)
```

---

*今天花 60-90 分钟：前 5 分钟入门，40 分钟源码分析，15 分钟动手验证*
*答不出自测题？回去重读对应章节。*
