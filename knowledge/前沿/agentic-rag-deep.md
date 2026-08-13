# Agentic RAG 进阶 - 资深专家深度实现

## 一、架构演进

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     RAG 演进路径                                           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   RAG 1.0 (基础版)                                                       │
│   ├── 文档切分 → Embedding → 向量检索 → LLM生成                           │
│   └── 缺点: 单路召回，质量不稳定                                          │
│                                                                         →
│   RAG 2.0 (增强版)                                                        │
│   ├── 多路召回: 向量+关键词+图谱                                           │
│   ├── 重排序: Cross-Encoder                                              │
│   └── 优点: 召回率提升                                                     │
│                                                                         →
│   RAG 3.0 (Agentic版)                                                      │
│   ├── 多Agent协作: Query理解Agent + 检索Agent + 生成Agent                   │
│   ├── 自主决策: 决定何时检索、何时回答                                       │
│   ├── 工具调用: 搜索、计算、代码执行                                        │
│   └── 优点: 灵活智能，适合复杂场景                                          │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、Agentic RAG 实现

```python
from langgraph import Graph, State
from typing import TypedDict, List, Optional

class RAGState(TypedDict):
    query: str
    documents: List[str]
    context: str
    answer: str
    should_retrieve: bool
    tools_called: List[str]

class AgenticRAG:
    """Agentic RAG 系统"""
    
    def __init__(self, llm, retriever, tools):
        self.llm = llm
        self.retriever = retriever
        self.tools = tools
        
    def build_graph(self) -> Graph:
        """构建Agent图"""
        graph = Graph()
        
        # 节点定义
        graph.add_node("query_understanding", self.query_understanding)
        graph.add_node("retrieve", self.retrieve_documents)
        graph.add_node("generate", self.generate_answer)
        graph.add_node("tool_call", self.call_tools)
        
        # 边定义
        graph.add_edge("query_understanding", "should_retrieve")
        graph.add_conditional_edges(
            "should_retrieve",
            self.decide_retrieve,
            {"yes": "retrieve", "no": "generate"}
        )
        graph.add_edge("retrieve", "generate")
        graph.add_edge("generate", "tool_call")
        
        return graph
    
    def query_understanding(self, state: RAGState) -> RAGState:
        """查询理解"""
        prompt = f"""分析用户查询: {state['query']}
        判断是否需要检索文档，返回JSON:
        {{
            "intent": "查询意图",
            "should_retrieve": true/false,
            "keywords": ["关键词列表"]
        }}"""
        
        response = self.llm.invoke(prompt)
        # 解析response...
        return state
    
    def retrieve_documents(self, state: RAGState) -> RAGState:
        """检索文档"""
        docs = self.retriever.search(state['query'], top_k=5)
        state['documents'] = docs
        state['context'] = "\n".join(docs)
        return state
    
    def generate_answer(self, state: RAGState) -> RAGState:
        """生成答案"""
        prompt = f"""基于以下上下文回答问题:
        查询: {state['query']}
        上下文: {state['context']}
        
        请给出准确、简洁的回答。"""
        
        answer = self.llm.invoke(prompt)
        state['answer'] = answer
        return state
    
    def call_tools(self, state: RAGState) -> RAGState:
        """工具调用"""
        # 根据答案决定是否调用工具
        # ...
        return state
```

## 三、面试高频题

### Q1: RAG vs Agentic RAG 有什么区别？

```
A:
1. RAG: 被动检索，固定流程
2. Agentic RAG: 主动决策，动态调整
```

### Q2: 如何处理检索失败？

```
A:
1. 多路召回: 向量+关键词+图谱
2. 查询改写: 优化原始查询
3.  fallback: 直接回答或引导
```

## 四、自测题

1. 解释RAG演进路径
2. 如何实现Agentic RAG？
3. 如何处理检索失败？

---

## 参考文档

- [LangGraph](https://langchain-ai.github.io/langgraph/)
- [LlamaIndex Agents](https://docs.llamaindex.ai/en/stable/module_guides/using_agents/)
