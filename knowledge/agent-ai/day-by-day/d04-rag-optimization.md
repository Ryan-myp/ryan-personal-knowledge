# Day 4: RAG 优化 — 从入门到源码级

> 学习目标: 先理解 RAG 优化是什么、为什么需要，再深入源码

---

## 第一部分：入门引导（5 分钟速览）

### 4.1 RAG 常见问题

```
RAG 系统常见问题:

1. 检索不准确
   - 用户问题和文档用词不同
   - 文档太长，关键信息被淹没
   - 向量表示不够好

2. 上下文太长
   - 检索太多文档
   - 每个文档太长
   - 超出 token 限制

3. 回答不一致
   - 同问题不同答案
   - 依赖检索结果排序

4. 响应慢
   - 向量检索慢
   - LLM 生成慢
   - 重排序慢
```

### 4.2 RAG 优化策略总览

```
RAG 优化策略:
├─ 查询扩展: 生成多个相关查询
├─ 重排序: 对检索结果重新排序
├─ 上下文压缩: 只保留最相关信息
├─ 混合检索: 向量+关键词联合检索
└─ 缓存: 缓存常见查询结果
```

### 4.3 查询扩展是什么？

```
查询扩展原理:
用户问题可能表述不清 → 生成多个相关查询 → 提高召回率

示例:
原始问题: "北京天气怎么样？"
扩展后:
- "北京天气怎么样？"（原始）
- "北京今天气温"（同义词）
- "北京降水情况"（相关问题）
- "北京气温多少度"（改写）

优势:
- 从不同角度检索
- 提高召回率（Recall）
- 减少漏检
```

### 4.4 上下文压缩是什么？

```
上下文压缩策略:
1. 句子级过滤: 只保留最相关的句子
2. 摘要化: 对长文档生成摘要
3. 重要性排序: 按相关性打分

示例:
原始上下文:
[文档1] RAG 是检索增强生成技术。它通过检索相关知识来增强 LLM 的回答能力。RAG 的核心组件包括向量化、向量数据库和重排序。
[文档2] LLM 是大语言模型，如 GPT-4、Claude 等。
[文档3] 向量数据库用于存储和检索向量。

压缩后:
RAG 是检索增强生成技术。
向量数据库用于存储。
```

### 4.5 快速体验

```python
# 安装依赖
pip install langchain langchain-community

from langchain.retrievers import BM25Retriever, EnsembleRetriever
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

# 1. 准备文档
loader = TextLoader("example.txt")
documents = loader.load()
splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
docs = splitter.split_documents(documents)

# 2. 向量检索
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import OpenAIEmbeddings

vectorstore = FAISS.from_documents(docs, OpenAIEmbeddings())
vector_retriever = vectorstore.as_retriever(
    search_type="similarity",
    search_kwargs={"k": 5}
)

# 3. BM25 关键词检索
bm25_retriever = BM25Retriever.from_documents(docs)
bm25_retriever.k = 5

# 4. 混合检索
ensemble_retriever = EnsembleRetriever(
    retrievers=[vector_retriever, bm25_retriever],
    weights=[0.7, 0.3]
)

# 5. 对比效果
print("向量检索:")
for doc in vector_retriever.invoke("什么是 RAG?"):
    print(" -", doc.page_content[:50])

print("\n混合检索:")
for doc in ensemble_retriever.invoke("什么是 RAG?"):
    print(" -", doc.page_content[:50])
```

### 4.6 关键概念总结

| 概念 | 说明 |
|------|------|
| **查询扩展** | 生成多个相关查询，提高召回率 |
| **重排序** | 对检索结果重新排序，提高精度 |
| **上下文压缩** | 只保留最相关信息，节省 token |
| **混合检索** | 向量+关键词联合检索，互补优势 |
| **缓存** | 缓存常见查询结果，降低成本 |

---

## 第二部分：源码级深度剖析

### 4.7 查询扩展源码

```python
# langchain/retrievers/query_expander.py
# 查询扩展器

class QueryExpander:
    """
    查询扩展器
    
    原理: 用户的问题可能表述不清，
    生成多个相关查询能提高检索准确率
    
    扩展策略:
    1. 同义词扩展: 天气 → 气温、气候
    2. 相关问题: 北京天气 → 北京气温、北京降水
    3. 改写问题: 更清晰的表述
    """
    
    def __init__(self, llm=None):
        self.llm = llm or ChatOpenAI(model="gpt-3.5-turbo")
    
    def expand(self, query: str) -> List[str]:
        """
        查询扩展实现
        
        返回: [原始查询, 扩展查询1, 扩展查询2, ...]
        """
        # 方式 1: 使用 LLM 生成相关问题
        prompt = f"""
        用户问题: {query}
        
        请生成 3 个相关问题，帮助检索更多信息:
        1. 
        2. 
        3. 
        """
        related = self.llm.chat(prompt).split('\n')
        
        # 方式 2: 简单改写
        paraphrased = self._paraphrase(query)
        
        # 合并去重
        all_queries = [query] + related + paraphrased
        return list(set(all_queries))
    
    def _paraphrase(self, query: str) -> List[str]:
        """简单改写（实际应使用 LLM）"""
        # 这里只是示例，实际应调用 LLM
        return [
            query.replace("什么", "如何"),
            query.replace("怎么", "为何")
        ]
```

### 4.8 重排序源码

```python
# langchain/retrievers/rerank.py
# 重排序器

class CrossEncoderReranker:
    """
    交叉编码器重排序器
    
    原理:
    ├── 输入: (query, document) 对
    ├── 处理: 联合编码 + 交互层
    └── 输出: 相关性分数
    
    优势:
    ├── 精度高: 考虑 query-doc 交互
    └── 速度慢: O(n²) 复杂度
    """
    
    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        self.model = AutoModelForSequenceClassification.from_pretrained(model_name)
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
    
    def rerank(self, query: str, documents: List[Document], top_k: int = 5) -> List[Document]:
        """
        重排序实现
        
        流程:
        1. 构建 (query, doc) 对
        2. 联合编码
        3. 计算相关性分数
        4. 排序并返回 top_k
        """
        # 1. 构建输入对
        pairs = [(query, doc.page_content) for doc in documents]
        
        # 2. 编码
        inputs = self.tokenizer(
            pairs,
            padding=True,
            truncation=True,
            return_tensors="pt",
            max_length=512
        )
        
        # 3. 模型推理
        with torch.no_grad():
            scores = self.model(**inputs).logits.squeeze()
        
        # 4. 排序
        scored_docs = list(zip(scores.cpu().numpy(), documents))
        scored_docs.sort(key=lambda x: x[0], reverse=True)
        
        # 5. 返回 top_k
        return [doc for score, doc in scored_docs[:top_k]]
```

### 4.9 混合检索源码

```python
# langchain/retrievers/ensemble.py
# 混合检索器

class EnsembleRetriever(BaseRetriever):
    """
    混合检索器
    
    原理: 结合向量检索和关键词检索的优势
    
    向量检索:
    - 优点: 语义匹配，能处理同义词
    - 缺点: 对精确匹配不敏感
    
    关键词检索:
    - 优点: 精确匹配，对专有名词敏感
    - 缺点: 无法处理同义词
    
    混合: 加权融合，互补优势
    """
    
    def __init__(
        self,
        retrievers: List[BaseRetriever],
        weights: List[float] = None,
    ):
        self.retrievers = retrievers
        self.weights = weights or [1.0 / len(retrievers)] * len(retrievers)
    
    def _get_relevant_documents(
        self,
        query: str,
        *,
        run_manager: CallbackManagerForRetrieverAction,
    ) -> List[Document]:
        """
        混合检索实现
        
        流程:
        1. 各检索器独立检索
        2. 对结果进行 RRF 融合
        3. 返回融合后的结果
        """
        # 1. 各检索器独立检索
        all_results = []
        for retriever in self.retrievers:
            results = retriever.invoke(query)
            all_results.append(results)
        
        # 2. RRF 融合
        fused_results = self._rrf_fusion(all_results, k=60)
        
        # 3. 返回结果
        return fused_results
    
    def _rrf_fusion(
        self,
        all_results: List[List[Document]],
        k: int = 60,
    ) -> List[Document]:
        """
        RRF (Reciprocal Rank Fusion) 融合
        
        原理:
        - 对每个文档，计算其在各检索结果中的排名
        - 分数 = Σ (1 / (k + rank))
        - 按分数排序
        
        优势:
        - 无需训练
        - 对排名敏感
        - 计算简单
        """
        # 统计每个文档的得分
        doc_scores = defaultdict(float)
        
        for results, weight in zip(all_results, self.weights):
            for rank, doc in enumerate(results):
                doc_scores[doc] += weight / (k + rank)
        
        # 排序
        sorted_docs = sorted(doc_scores.items(), key=lambda x: x[1], reverse=True)
        
        return [doc for doc, score in sorted_docs]
```

### 4.10 上下文压缩源码

```python
# langchain/retrievers/document_compressors.py
# 上下文压缩器

class LLMChainExtractor(BaseDocumentTransformer):
    """
    基于 LLM 的上下文压缩器
    
    原理:
    1. 对每个文档，让 LLM 提取与查询最相关的部分
    2. 去除无关内容
    3. 返回压缩后的文档
    
    优势:
    - 只保留最相关信息
    - 节省 token
    - 提高回答质量
    
    缺点:
    - 额外调用 LLM
    - 增加延迟
    """
    
    def __init__(self, llm=None):
        self.llm = llm or ChatOpenAI(model="gpt-3.5-turbo")
    
    def compress_documents(
        self,
        documents: List[Document],
        query: str,
    ) -> List[Document]:
        """
        压缩文档
        
        流程:
        1. 对每个文档，提取与查询相关的部分
        2. 返回压缩后的文档
        """
        compressed = []
        for doc in documents:
            # 构建 Prompt
            prompt = f"""
            请从以下文档中提取与查询最相关的部分。
            
            查询: {query}
            
            文档:
            {doc.page_content}
            
            请只返回相关内容，如果无关请返回"无相关内容"。
            """
            
            # LLM 提取
            response = self.llm.chat(prompt)
            
            if "无相关内容" not in response:
                compressed.append(
                    Document(
                        page_content=response,
                        metadata=doc.metadata,
                    )
                )
        
        return compressed
```

---

## 第三部分：自测

### 问题 1
查询扩展的作用是什么？
<details>
<summary>查看答案</summary>

- 用户问题可能表述不清
- 文档可能使用不同术语
- 多个查询从不同角度检索
- 提高召回率
</details>

### 问题 2
重排序的优势和缺点是什么？
<details>
<summary>查看答案</summary>

优势:
- 精度高：考虑 query-doc 交互

缺点:
- 速度慢：O(n²) 复杂度
</details>

### 问题 3
RRF 融合的公式是什么？
<details>
<summary>查看答案</summary>

分数 = Σ (1 / (k + rank))

其中：
- k 是常数（通常 60）
- rank 是文档在检索结果中的排名
- 对所有检索器的结果求和
</details>

---

## 第四部分：动手验证

### 4.1 测试查询扩展的效果

```python
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(model="gpt-3.5-turbo")

# 查询扩展
query = "北京天气怎么样？"
prompt = f"""
用户问题: {query}
请生成 3 个相关问题:
1. 
2. 
3. 
"""
related = llm.chat(prompt).split('\n')
print("扩展查询:", related)
```

### 4.2 测试混合检索效果

```python
from langchain.retrievers import BM25Retriever, EnsembleRetriever

# 向量检索
vector_retriever = vectorstore.as_retriever(
    search_type="similarity",
    search_kwargs={"k": 5}
)

# BM25 关键词检索
bm25_retriever = BM25Retriever.from_documents(docs)
bm25_retriever.k = 5

# 混合检索
ensemble_retriever = EnsembleRetriever(
    retrievers=[vector_retriever, bm25_retriever],
    weights=[0.7, 0.3]
)

# 对比效果
print("向量检索:")
for doc in vector_retriever.invoke("什么是 RAG?"):
    print(" -", doc.page_content[:50])

print("\n混合检索:")
for doc in ensemble_retriever.invoke("什么是 RAG?"):
    print(" -", doc.page_content[:50])
```

---

*今天花 60-90 分钟：前 5 分钟入门，40 分钟源码分析，15 分钟动手验证*
*答不出自测题？回去重读对应章节。*
