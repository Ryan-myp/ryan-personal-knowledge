# RAG 4.0 生产实践

## 一、架构演进

```
RAG 1.0: 简单检索 + 生成
RAG 2.0: 检索增强 + 重排序
RAG 3.0: 多路召回 + 混合检索
RAG 4.0: 全链路优化 + 评估闭环
```

## 二、关键技术

### 2.1 多路召回

```python
class MultiPathRetriever:
    def __init__(self):
        self.vector_store = VectorStore()  # 向量检索
        self.keyword = KeywordSearch()    # 关键词检索
        self.graph = KnowledgeGraph()     # 图谱检索
        self.re_ranker = CrossEncoder()   # 重排序
    
    async def retrieve(self, query: str, k: int = 10) -> List[Document]:
        # 多路召回
        vector_docs = await self.vector_store.search(query, k=5)
        keyword_docs = self.keyword.search(query, k=5)
        graph_docs = self.graph.query(query, k=3)
        
        # 合并去重
        all_docs = merge_unique(vector_docs + keyword_docs + graph_docs)
        
        # 重排序
        ranked = self.re_ranker.rerank(query, all_docs[:15])
        
        return ranked[:k]
```

### 2.2 HyDE (假设文档嵌入)

```python
class HyDERetriever:
    def __init__(self, llm):
        self.llm = llm
        self.embedder = EmbeddingModel()
    
    async def retrieve(self, question: str) -> List[Document]:
        # 生成假设性答案
        hypothetical_answer = await self.llm.generate(
            f"假设你知道答案，请给出{question}的完整回答"
        )
        
        # 用假设答案检索
        embeddings = self.embedder.embed(hypothetical_answer)
        docs = self.vector_store.search(embeddings, k=5)
        
        return docs
```

## 三、评估指标

| 指标 | 说明 | 目标值 |
|------|------|--------|
| 召回率 | 相关文档被检索的比例 | > 0.8 |
| 精确率 | 检索结果中相关的比例 | > 0.7 |
| F1 | 召回率和精确率的调和平均 | > 0.75 |
| MRR | 平均倒数排名 | > 0.8 |
| RAGAS | 综合质量评分 | > 0.7 |

## 四、最佳实践

1. **查询理解**
   - 意图识别
   - 查询改写
   - 查询扩展

2. **检索优化**
   - 元数据过滤
   - 稀疏+密集混合
   - 分块策略优化

3. **生成优化**
   - 上下文压缩
   - 提示工程
   - 链式推理

---

**参考**: RAGAS框架, LangChain文档
