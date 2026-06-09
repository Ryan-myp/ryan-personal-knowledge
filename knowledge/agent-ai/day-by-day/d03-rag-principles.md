# Day 3: RAG 系统原理 — 检索增强生成

> 学习目标: 理解 RAG 完整流程，能解释每个组件的作用

---

## 一、RAG 是什么？为什么需要它？

### 1.1 问题背景

```
LLM 的局限性:
├─ 训练数据有截止时间（不知道最新信息）
├─ 私有数据无法访问（公司文档、个人笔记）
└─ 幻觉问题（编造事实）

解决方案: RAG
Retrieval-Augmented Generation = 检索增强生成

核心思想:
用户问题 → 检索相关知识 → 组装上下文 → LLM 生成答案
```

### 1.2 RAG 完整流程图

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

---

## 二、RAG 的 5 个核心组件

### 组件 1: 文档切片 (Chunking)

```
为什么需要切片？
- LLM 有 token 限制（GPT-4 约 128K）
- 不能一次性加载全部文档
- 需要切成小块，每次只检索相关的

切片策略:
┌─────────────────────────────────────────────────────┐
│ 1. 固定长度切片                                        │
│    每 500 tokens 切一块                               │
│    优点: 简单                                          │
│    缺点: 可能切断语义                                   │
│                                                     │
│ 2. 按段落切片                                          │
│    按空行/换行符切分                                   │
│    优点: 保持段落完整性                                 │
│    缺点: 段落可能太长或太短                             │
│                                                     │
│ 3. 语义切片（推荐）                                     │
│    按句子边界切分，保证每块有完整语义                    │
│    优点: 语义连续                                      │
│    缺点: 实现复杂                                      │
└─────────────────────────────────────────────────────┘

关键参数:
- chunk_size: 每块大小（500-1000 tokens）
- chunk_overlap: 重叠部分（100-200 tokens）
- 重叠目的: 保持语义连续性，避免关键信息被切断
```

### 组件 2: 向量化 (Embedding)

```
什么是 Embedding？
- 把文本转换成数字向量
- 语义相似的文本，向量也相似
- 常用模型: text-embedding-ada-002 (1536维)

为什么需要向量化？
- 向量数据库用向量相似度搜索
- "北京天气" 和 "北京气温" 的向量很接近
- 即使用词不同也能匹配到

Embedding 过程:
"什么是 RAG？"
    ↓
[0.12, -0.34, 0.56, ..., 0.23]  (1536个数字)
```

### 组件 3: 向量数据库

```
常用向量数据库对比:
┌──────────┬──────────┬──────────┬──────────┐
│ 数据库   │ 速度     │ 规模     │ 特点     │
├──────────┼──────────┼──────────┼──────────┤
│ FAISS    │ 快       │ 单机     │ 内存型   │
│ Redis    │ 很快     │ 单机     │ 内存型   │
│ pgvector │ 中       │ 可分布式 │ PostgreSQL │
│ Milvus   │ 快       │ 分布式   │ 大规模   │
└──────────┴──────────┴──────────┴──────────┘

搜索算法:
- 精确搜索: 遍历所有向量，准确但慢
- HNSW: 近似最近邻，快且准确（推荐）
- IVF: 倒排索引，适合大数据
```

### 组件 4: 重排序 (Reranking)

```
为什么要重排序？
- 向量检索返回 Top-K（比如 10 个）
- 但这些可能不够准确
- 重排序模型对 (query, doc) 对打分
- 重新排序后取 Top-N（比如 5 个）

重排序流程:
原始检索结果（10个）
    ↓
CrossEncoder 打分
    ↓
排序
    ↓
取 Top-5
```

### 组件 5: 上下文组装

```
Prompt 组装:
┌─────────────────────────────────────────────────────┐
│ 你是一位专业的问答助手。请基于以下上下文回答问题。      │
│                                                     │
│ 上下文:                                             │
│ -------------------------------------------------   │
│ [文档1的内容]                                      │
│ -------------------------------------------------   │
│ [文档2的内容]                                      │
│ -------------------------------------------------   │
│ [文档3的内容]                                      │
│ -------------------------------------------------   │
│                                                     │
│ 问题: {question}                                    │
│                                                     │
│ 要求:                                               │
│ 1. 只基于提供的上下文回答问题                         │
│ 2. 如果上下文中没有相关信息，说明"抱歉..."           │
│ 3. 回答要准确、详细                                  │
└─────────────────────────────────────────────────────┘
```

---

## 三、源码级理解

### 3.1 完整的 RAG 实现

```python
class SimpleRAG:
    """简化版 RAG 系统"""
    
    def __init__(self):
        self.embedder = OpenAIEmbeddings()
        self.vector_db = FAISS()
        
    def ingest(self, documents: List[str]):
        """
        文档入库流程
        
        1. 切片
        2. 向量化
        3. 存储
        """
        # 1. 切片
        chunks = self.chunk_documents(documents)
        
        # 2. 向量化
        embeddings = self.embedder.embed_documents(chunks)
        
        # 3. 存储
        self.vector_db.add_embeddings(chunks, embeddings)
    
    def query(self, question: str) -> str:
        """
        查询流程
        
        1. 向量化问题
        2. 检索相似文档
        3. 组装 Prompt
        4. LLM 生成
        """
        # 1. 向量化问题
        question_embedding = self.embedder.embed_query(question)
        
        # 2. 检索（返回最相关的3个文档）
        relevant_docs = self.vector_db.similarity_search(
            question_embedding,
            k=3
        )
        
        # 3. 组装上下文
        context = "\n\n".join([doc.page_content for doc in relevant_docs])
        
        # 4. 组装 Prompt
        prompt = f"""
        基于以下上下文回答问题:
        
        上下文:
        {context}
        
        问题: {question}
        
        请给出准确的答案。
        """
        
        # 5. LLM 生成
        response = llm.chat(prompt)
        return response
    
    def chunk_documents(self, documents: List[str]) -> List[str]:
        """
        文档切片
        
        策略:
        - 按句子切分
        - 每块 500 tokens
        - 重叠 100 tokens
        """
        chunks = []
        for doc in documents:
            sentences = doc.split('. ')
            current_chunk = ""
            for sentence in sentences:
                if len(current_chunk) + len(sentence) < 500:
                    current_chunk += sentence + ". "
                else:
                    chunks.append(current_chunk.strip())
                    current_chunk = sentence + ". "
            if current_chunk:
                chunks.append(current_chunk.strip())
        return chunks
```

---

## 四、自测

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

## 五、动手验证

```python
# 1. 准备文档
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

# 3. 创建向量数据库
vectorstore = Chroma.from_texts(
    texts=chunks,
    embedding=OpenAIEmbeddings()
)

# 4. 检索
results = vectorstore.similarity_search("什么是 RAG?", k=2)
for r in results:
    print("文档:", r.page_content)
```

---

*今天花 30 分钟读完 + 20 分钟调试 = 真正理解 RAG*
