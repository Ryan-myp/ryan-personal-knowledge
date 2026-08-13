# LlamaIndex RAG 架构深度蒸馏

> 来源：LlamaIndex 官方源码
> 蒸馏日期：2026-01-15
> 核心价值：RAG 系统架构 + 检索增强生成设计

---

## 一、Query Engine 架构

### 1.1 核心组件

**源码摘录**（`retriever_query_engine.py`）：
```python
class RetrieverQueryEngine(BaseQueryEngine):
    """
    Retriever query engine.
    
    Components:
    1. Retriever - 检索相关文档
    2. Response Synthesizer - 合成最终回答
    3. Node Postprocessors - 后处理检索结果
    """
    
    def __init__(
        self,
        retriever: BaseRetriever,
        response_synthesizer: Optional[BaseSynthesizer] = None,
        node_postprocessors: Optional[List[BaseNodePostprocessor]] = None,
    ):
        self._retriever = retriever
        self._response_synthesizer = response_synthesizer or 
            get_response_synthesizer(llm=Settings.llm)
        self._node_postprocessors = node_postprocessors or []
```

**设计意图**：
```
问题：如何将检索和生成解耦？

方案：
1. Retriever 负责检索
   - Vector store retrieval
   - Keyword search
   - Hybrid retrieval
   
2. Response Synthesizer 负责生成
   - Refine: 逐步完善回答
   - Compact: 合并节点后生成
   - Simple: 直接使用第一个节点
   
3. Node Postprocessors 负责后处理
   - 过滤不相关节点
   - 重排序
   - 截断
```

### 1.2 查询执行流程

```python
def query(self, query_str: str) -> Response:
    # Step 1: 检索相关节点
    nodes = self._retriever.retrieve(QueryBundle(query_str))
    
    # Step 2: 后处理
    nodes = self._apply_node_postprocessors(nodes, query_bundle)
    
    # Step 3: 合成回答
    response = self._response_synthesizer.synthesize(
        query=query_str,
        nodes=nodes,
    )
    
    return response
```

**实战配置**：
```python
from llama_index.core import VectorStoreIndex, Settings
from llama_index.llms.openai import OpenAI

# 配置 LLM
Settings.llm = OpenAI(model="gpt-4o")
Settings.embed_model = "text-embedding-3-small"

# 创建索引
index = VectorStoreIndex.from_documents(documents)

# 创建检索器
retriever = index.as_retriever(
    similarity_top_k=5,
    vector_store_query_mode="mmr",  # MMR 去重
)

# 创建 Query Engine
query_engine = index.as_query_engine(
    retriever=retriever,
    response_mode="refine",  # 逐步完善
    text_qa_template=custom_qa_template,
)

# 执行查询
response = query_engine.query("什么是实时竞价系统？")
```

---

## 二、Response Synthesizer 模式

### 2.1 Refine 模式

```python
class Refine(BaseSynthesizer):
    """
    Refine synthesizer:
    1. Generate initial answer from first node
    2. Refine answer with each subsequent node
    3. Continuously improve the answer
    """
    
    def synthesize(self, query, nodes, **kwargs) -> Response:
        answer = None
        for node in nodes:
            if answer is None:
                # First node: generate initial answer
                answer = self._llm.predict(
                    self._template,
                    query_str=query,
                    ctx_str=node.text,
                )
            else:
                # Subsequent nodes: refine answer
                answer = self._llm.predict(
                    self._refine_template,
                    existing_answer=answer,
                    ctx_str=node.text,
                )
        return Response(answer)
```

**适用场景**：
```
✅ 需要逐步完善答案的复杂问题
✅ 多文档综合回答
✅ 需要推理链的问题

配置示例：
response_mode="refine"
refine_template="现有回答: {existing_answer}\n\n补充信息: {ctx_str}\n\n请改进回答："
```

### 2.2 Compact 模式

```python
class CompactAndRefine(BaseSynthesizer):
    """
    Compact synthesizer:
    1. Concatenate all nodes into single context
    2. Generate answer from combined context
    3. More efficient for simple queries
    """
    
    def synthesize(self, query, nodes, **kwargs) -> Response:
        # Combine all node texts
        combined_text = self._merge_nodes(nodes)
        
        # Generate single answer
        answer = self._llm.predict(
            self._template,
            query_str=query,
            ctx_str=combined_text,
        )
        return Response(answer)
```

**适用场景**：
```
✅ 简单事实查询
✅ 上下文窗口有限
✅ 需要快速响应

配置示例：
response_mode="compact"
```

---

## 三、Node Postprocessors

### 3.1 常用后处理器

```python
# 1. 相似度阈值过滤
from llama_index.core.postprocessor import SimilarityPostprocessor

postprocessor = SimilarityPostprocessor(
    similarity_cutoff=0.7  # 只保留相似度 > 0.7 的节点
)

# 2. 文本长度截断
from llama_index.core.postprocessor import LongContextReorder

postprocessor = LongContextReorder(
    min_token=100,    # 最少 token 数
    max_token=500     # 最大 token 数
)

# 3. Embedding 过滤
from llama_index.core.postprocessor import SentenceTransformerRerank

postprocessor = SentenceTransformerRerank(
    model='cross-encoder/ms-marco-MiniLM-L-6-v2',
    top_n=3  # 只保留 Top 3
)
```

### 3.2 组合使用

```python
# 多后处理器组合
postprocessors = [
    SimilarityPostprocessor(similarity_cutoff=0.7),
    LongContextReorder(min_token=100, max_token=500),
    SentenceTransformerRerank(model='cross-encoder/ms-marco-MiniLM-L-6-v2', top_n=3),
]

query_engine = index.as_query_engine(
    retriever=retriever,
    node_postprocessors=postprocessors,
)
```

---

## 四、生产级 RAG 架构

### 4.1 多路召回

```python
from llama_index.core.vector_stores import (
    VectorStoreInfo,
    VectorStoreQueryMode,
)

# 多路检索
retriever = index.as_retriever(
    vector_store_query_mode=VectorStoreQueryMode.HYBRID,  # 混合检索
    similarity_top_k=5,
    sparse_top_k=3,  # Sparse 检索
)
```

### 4.2 自适应检索

```python
from llama_index.core.indices.query.query_transform import (
    HyDEQueryTransform,
)

# HyDE: 假设性文档嵌入
hydeqt = HyDEQueryTransform(include_original=True)

query_engine = index.as_query_engine(
    retriever=retriever,
    query_transform=hydeqt,
)
```

### 4.3 元数据过滤

```python
# 基于元数据的过滤
retriever = index.as_retriever(
    filters={
        "doc_type": "technical",
        "year": 2024,
        "category": "advertising"
    }
)
```

---

## 五、性能优化

### 5.1 检索优化

```python
# 1. 调整 top_k
retriever = index.as_retriever(similarity_top_k=10)

# 2. 使用 MMR 去重
retriever = index.as_retriever(
    vector_store_query_mode="mmr",
    mmr_threshold=0.5,
)

# 3. 启用缓存
from llama_index.core.settings import Settings
Settings.embed_model = CacheEmbedding(
    embed_model="text-embedding-3-small",
    cache_size=10000
)
```

### 5.2 生成优化

```python
# 1. 流式输出
response = query_engine.query(
    "什么是实时竞价？",
    streaming=True,
)
for text in response.response_gen:
    print(text, end="", flush=True)

# 2. 减少 token 使用
response = query_engine.query(
    "什么是实时竞价？",
    mode="compact",  # 合并上下文
)
```

---

## 六、核心洞察总结

```
1. RAG 架构设计
   - Retriever + Synthesizer + Postprocessors
   - 解耦设计，可灵活组合
   
2. 响应模式选择
   - Refine: 逐步完善，适合复杂问题
   - Compact: 高效简洁，适合简单查询
   
3. 生产级优化
   - 多路召回提升准确率
   - 后处理过滤提升质量
   - 缓存加速检索
```

---

**核心价值**：LlamaIndex 的核心价值在于"模块化设计"——Retriever、Synthesizer、Postprocessor 可以独立替换和组合，适应不同场景需求。
EOF
echo "✅ LlamaIndex 深度文档已创建"