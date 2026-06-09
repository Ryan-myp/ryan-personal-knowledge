# Day 4: RAG 优化策略 — 让检索更准确

> 学习目标: 掌握 RAG 的常见问题和优化方法

---

## 一、RAG 常见问题

```
RAG 问题清单:
├─ 检索不准确 → 返回不相关文档
├─ 上下文太长 → 超出 token 限制
├─ 回答不一致 → 同问题不同答案
└─ 响应慢 → 延迟过高
```

### 问题 1: 检索不准确

```
原因:
- 用户问题和文档用词不同
- 文档太长，关键信息被淹没
- 向量表示不够好

解决: 查询扩展 + 重排序
```

### 问题 2: 上下文太长

```
原因:
- 检索太多文档
- 每个文档太长

解决: 上下文压缩
- 只保留最相关的句子
- 摘要化不重要的部分
```

---

## 二、查询扩展

```
查询扩展原理:
用户问题可能表述不清 → 生成多个相关查询 → 提高召回率

扩展策略:
1. 同义词扩展: 天气 → 气温、气候
2. 相关问题: 北京天气 → 北京气温、北京降水
3. 改写问题: 更清晰的表述

示例:
原始问题: "北京天气怎么样？"
扩展后:
- "北京天气怎么样？"
- "北京今天气温"
- "北京降水情况"
- "北京气温多少度"
```

### 源码实现

```python
class QueryExpander:
    """查询扩展器"""
    
    def expand(self, query: str) -> List[str]:
        """生成多个相关查询"""
        # 使用 LLM 生成相关问题
        prompt = f"""
        用户问题: {query}
        请生成 3 个相关问题，帮助检索更多信息:
        1. 
        2. 
        3. 
        """
        related = llm.chat(prompt).split('\n')
        return [query] + related
```

---

## 三、上下文压缩

```
上下文压缩策略:
1. 句子级过滤: 只保留最相关的句子
2. 摘要化: 对长文档生成摘要
3. 重要性排序: 按相关性打分

示例:
原始上下文:
[文档1] RAG 是检索增强生成...
[文档2] LLM 是大语言模型...
[文档3] 向量数据库存储...

压缩后:
RAG 是检索增强生成技术。
向量数据库用于存储。
```

---

## 四、动手验证

```python
# 测试查询扩展的效果
from langchain.retrievers import BM25Retriever, EnsembleRetriever

# 向量检索
vector_retriever = vectorstore.as_retriever(
    search_type="similarity",
    search_kwargs={"k": 5}
)

# BM25 关键词检索
bm25_retriever = BM25Retriever.from_documents(documents)
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

## 五、自测

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
上下文压缩的常用方法？
<details>
<summary>查看答案</summary>

1. 句子级过滤
2. 摘要化
3. 重要性排序
</details>

---

*今天花 30 分钟读完 + 30 分钟调优 = 掌握 RAG 优化*
