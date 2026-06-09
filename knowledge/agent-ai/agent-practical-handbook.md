# Agent 技术实战学习手册 — 每天学透一个模块

> 创建日期: 2026-06-08  
> 作者: Ryan

---

## 📅 学习路径（4周，每天1个核心模块）

| 周 | 模块 | 预计时间 | 要求 |
|---|------|---------|------|
| 第1周 | Agent 原理与 ReAct | 30min/天 + 动手验证 | 能手写 ReAct 循环 |
| 第2周 | RAG 系统深度 | 30min/天 + 代码调试 | 能跑通 RAG 示例 |
| 第3周 | 多 Agent 协作 | 30min/天 + 架构设计 | 能画出协作流程图 |
| 第4周 | 生产级系统 | 30min/天 + 性能调优 | 能优化关键接口 |

---

## 第1天：Agent 核心架构（30min 阅读 + 15min 验证）

### 📖 核心概念（精读这部分）

**Agent 是什么？**
```
Agent = LLM(大脑) + Memory(记忆) + Tools(工具) + Planning(规划)

关键区别:
- Chatbot: 用户问 → 模型答（单次交互）
- Agent: 用户问 → Agent 思考 → 选工具 → 执行 → 观察 → 再思考 → 最终答（循环）
```

**为什么需要 Agent？**
- Chatbot 只能回答训练数据内的问题
- Agent 能通过工具获取实时信息
- Agent 能处理多步骤复杂任务

### 🔍 源码级理解（看这段代码）

```python
# 这是 LangChain AgentExecutor 的核心逻辑（简化版）
class SimpleAgent:
    def __init__(self, llm, tools):
        self.llm = llm
        self.tools = tools
        self.max_steps = 10  # 最多执行10步
        
    def run(self, question):
        """
        Agent 执行循环
        
        关键逻辑:
        1. 让 LLM 决定下一步做什么
        2. 如果 LLM 说"完成"，返回答案
        3. 如果 LLM 说"调用工具"，执行工具
        4. 把工具结果喂给 LLM，继续循环
        """
        history = []  # 记录对话历史
        
        for step in range(self.max_steps):
            # Step 1: 让 LLM 思考
            prompt = self.build_prompt(question, history)
            response = self.llm.chat(prompt)
            
            # Step 2: 解析 LLM 的输出
            if response.is_answer():
                return response.answer  # LLM 决定回答
            
            # Step 3: 执行工具
            tool_name = response.tool_name
            tool_input = response.tool_input
            tool_result = self.tools.execute(tool_name, tool_input)
            
            # Step 4: 记录到历史
            history.append({
                "thought": response.thought,
                "action": f"{tool_name}({tool_input})",
                "result": tool_result
            })
        
        return "任务执行失败：超过最大步数"
```

### 🧠 理解检查（自测，答不上来就说明没懂）

**问题 1**: 为什么需要 `max_steps` 限制？
<details>
<summary>点击查看思考方向</summary>

- LLM 可能陷入循环（一直调用同一个工具）
- 防止 token 耗尽（每次循环都消耗 token）
- 避免无限等待
</details>

**问题 2**: `history` 里存了什么？为什么重要？
<details>
<summary>点击查看思考方向</summary>

- 存了：LLM 的思考过程、调用的工具、工具的结果
- 重要原因：LLM 没有记忆，每次对话都要给它完整上下文
- 如果 history 太长，会超出 token 限制
</details>

### ⚡ 动手验证（15min）

**任务**: 安装 LangChain，运行一个简单 Agent

```bash
pip install langchain langchain-openai
```

```python
from langchain_openai import ChatOpenAI
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.tools import tool

# 1. 定义工具
@tool
def get_weather(city: str) -> str:
    """获取城市天气"""
    return f"{city}的天气是晴天，温度25度"

# 2. 创建 LLM
llm = ChatOpenAI(model="gpt-3.5-turbo")

# 3. 创建 Agent
tools = [get_weather]
agent = create_tool_calling_agent(llm, tools, None)
executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

# 4. 运行
result = executor.invoke({"input": "北京天气怎么样？"})
print(result["output"])
```

**观察要点**:
- 看 verbose 输出，LLM 是怎么思考的
- 看它调用了哪个工具
- 看工具结果怎么影响下一步决策

---

## 第2天：ReAct 模式深度（30min 阅读 + 20min 调试）

### 📖 ReAct 是什么？

```
ReAct = Reason（推理）+ Act（行动）

传统 Chain-of-Thought:
思考 → 思考 → 思考 → 答案（纯内部推理）

ReAct 模式:
思考 → 行动 → 观察 → 思考 → 行动 → 观察 → 答案（推理+外部交互）

优势:
1. 能获取实时信息（联网、查数据库）
2. 能纠正错误推理（观察结果反馈）
3. 能处理多步骤任务
```

### 🔍 ReAct 循环源码分析

```python
class ReActLoop:
    """
    ReAct 核心循环
    
    执行流程图解:
    
    ┌─────────────────────────────────────────────────────┐
    │                  ReAct 循环                         │
    ├─────────────────────────────────────────────────────┤
    │                                                     │
    │  1. 构建 Prompt                                     │
    │     ┌───────────────────────────┐                   │
    │     │ 任务描述                   │                   │
    │     │ 历史记录 (thought/action/observation) │           │
    │     │ 可用工具列表               │                   │
    │     └───────────┬───────────────┘                   │
    │                 ▼                                   │
    │  2. LLM 推理                                        │
    │     ┌───────────────────────────┐                   │
    │     │ Thought: 我需要查天气       │                   │
    │     │ Action: get_weather        │                   │
    │     │ Action Input: {"city": "北京"} │               │
    │     └───────────┬───────────────┘                   │
    │                 ▼                                   │
    │  3. 执行工具                                        │
    │     ┌───────────────────────────┐                   │
    │     │ 调用 get_weather("北京")   │                   │
    │     │ 返回: "北京天气晴天25度"    │                   │
    │     └───────────┬───────────────┘                   │
    │                 ▼                                   │
    │  4. 记录观察                                        │
    │     ┌───────────────────────────┐                   │
    │     │ Observation: 北京天气晴天25度 │                 │
    │     └───────────┬───────────────┘                   │
    │                 ▼                                   │
    │  5. 回到步骤1（循环）                                │
    │         ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─                   │
    │                                                     │
    │  终止条件:                                           │
    │  - LLM 输出 Final Answer                            │
    │  - 达到最大步数                                      │
    │  - 超时                                             │
    └─────────────────────────────────────────────────────┘
    """
    pass
```

### 🧠 理解检查

**问题 1**: ReAct 和 Chain-of-Thought 的区别？
<details>
<summary>查看答案</summary>

- CoT: 纯内部推理，LLM 自己思考
- ReAct: 推理+行动，LLM 思考后调用工具，根据工具结果继续思考
- 关键区别：ReAct 能获取外部信息
</details>

**问题 2**: 如果工具执行失败，ReAct 怎么处理？
<details>
<summary>查看答案</summary>

- 工具返回错误信息作为 Observation
- LLM 看到错误，会调整策略（换工具、改参数、直接回答）
- 这就是 ReAct 能"纠正错误"的原因
</details>

### ⚡ 动手验证

**任务**: 对比 CoT 和 ReAct 的效果

```python
# 测试 1: 纯 CoT（不能联网）
cot_answer = llm.chat("2024年奥运会在哪里举办？请推理")
print("CoT 答案:", cot_answer)

# 测试 2: ReAct（能联网搜索）
# 需要安装 langchain-community
from langchain.tools import Tool
from langchain.agents import initialize_agent

search_tool = Tool(
    name="google_search",
    func=lambda q: "2024年奥运会在巴黎举办",  # 模拟搜索
    description="搜索互联网信息"
)

agent = initialize_agent(
    tools=[search_tool],
    llm=llm,
    agent_type="tool-calling",
    verbose=True
)

react_answer = agent.run("2024年奥运会在哪里举办？")
print("ReAct 答案:", react_answer)
```

---

## 第3天：RAG 系统原理（30min 阅读 + 20min 调试）

### 📖 RAG 是什么？

```
RAG = Retrieval-Augmented Generation（检索增强生成）

问题: LLM 训练数据有截止时间，不知道最新信息
解决: 先检索相关知识，再让 LLM 基于知识回答

流程:
用户问题 → 向量化 → 检索相似文档 → 组装上下文 → LLM 生成答案
```

### 🔍 RAG 核心组件

```python
class SimpleRAG:
    """
    简化版 RAG 系统
    
    核心步骤:
    1. 文档切片 (Chunking)
    2. 向量化 (Embedding)
    3. 存储到向量数据库
    4. 查询时检索
    5. 组装 Prompt
    6. LLM 生成
    """
    
    def __init__(self):
        self.embedder = OpenAIEmbeddings()
        self.vector_db = FAISS()
        
    def ingest(self, documents: List[str]):
        """
        文档摄入流程
        
        1. 切片: 把长文档切成小块（500-1000 tokens）
        2. 向量化: 每个块转换成向量
        3. 存储: 存入向量数据库
        """
        chunks = self.chunk_documents(documents)
        embeddings = self.embedder.embed_documents(chunks)
        self.vector_db.add_documents(chunks, embeddings)
    
    def query(self, question: str) -> str:
        """
        查询流程
        
        1. 向量化问题
        2. 检索相似文档（Top-K）
        3. 组装 Prompt
        4. LLM 生成
        """
        # 1. 向量化问题
        question_embedding = self.embedder.embed_query(question)
        
        # 2. 检索相似文档
        relevant_docs = self.vector_db.similarity_search(
            question_embedding, 
            k=3  # 返回最相关的3个文档
        )
        
        # 3. 组装 Prompt
        context = "\n\n".join([doc.page_content for doc in relevant_docs])
        prompt = f"""基于以下上下文回答问题:

上下文:
{context}

问题: {question}

请给出准确的答案。"""
        
        # 4. LLM 生成
        response = llm.chat(prompt)
        return response
    
    def chunk_documents(self, documents: List[str]) -> List[str]:
        """
        文档切片策略
        
        常用策略:
        - 固定长度: 每 500 tokens 切一块
        - 按段落: 按空行切分
        - 语义切分: 按句子边界切分
        
        关键参数:
        - chunk_size: 每块大小（500-1000）
        - chunk_overlap: 重叠部分（100-200）
        - 重叠目的: 保持语义连续性
        """
        chunks = []
        for doc in documents:
            # 简单实现：按句子切分
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

### 🧠 理解检查

**问题 1**: 为什么需要文档切片？为什么要有 overlap？
<details>
<summary>查看答案</summary>

- 切片原因: LLM 有 token 限制，不能一次性加载全部文档
- overlap 原因: 保持语义连续性，避免关键信息被切断
- 如果没有 overlap，跨句子的关键信息可能丢失
</details>

**问题 2**: RAG 的局限性是什么？
<details>
<summary>查看答案</summary>

- 检索可能失败（找不到相关文档）
- 检索可能不准确（返回不相关文档）
- LLM 可能被错误信息误导
- 无法处理需要复杂推理的问题
</details>

### ⚡ 动手验证

```python
from langchain_chroma import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter

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
print("切片结果:", chunks)

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

## 第4天：RAG 优化策略（30min 阅读 + 30min 调优）

### 📖 RAG 常见问题与优化

```
RAG 问题清单:
├─ 检索不准确 → 优化检索策略
├─ 上下文太长 → 上下文压缩
├─ 回答不一致 → 增加重排序
└─ 响应慢 → 缓存+并行

优化策略:
1. 查询扩展: 生成多个相关查询
2. 重排序: 对检索结果重新排序
3. 上下文压缩: 只保留最相关信息
4. 混合检索: 向量+关键词联合检索
```

### 🔍 查询扩展源码

```python
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
        related = llm.chat(prompt).split('\n')
        
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

### 🧠 理解检查

**问题 1**: 为什么查询扩展能提高检索准确率？
<details>
<summary>查看答案</summary>

- 用户的问题可能表述不清
- 文档可能使用不同的术语
- 多个查询能从不同角度检索
- 提高召回率（Recall）
</details>

**问题 2**: 重排序（Rerank）的作用是什么？
<details>
<summary>查看答案</summary>

- 向量检索返回 Top-K 文档
- 但这些文档可能不够准确
- 重排序模型对 (query, doc) 对打分
- 重新排序后取 Top-N
- 精度更高，但速度更慢
</details>

### ⚡ 动手验证

```python
# 测试查询扩展的效果
from langchain.retrievers import BM25Retriever, EnsembleRetriever

# 1. 向量检索
vector_retriever = vectorstore.as_retriever(
    search_type="similarity",
    search_kwargs={"k": 5}
)

# 2. BM25 关键词检索
bm25_retriever = BM25Retriever.from_documents(documents)
bm25_retriever.k = 5

# 3. 混合检索
ensemble_retriever = EnsembleRetriever(
    retrievers=[vector_retriever, bm25_retriever],
    weights=[0.7, 0.3]
)

# 4. 对比效果
print("向量检索:")
for doc in vector_retriever.invoke("什么是 RAG?"):
    print(" -", doc.page_content[:50])

print("\n混合检索:")
for doc in ensemble_retriever.invoke("什么是 RAG?"):
    print(" -", doc.page_content[:50])
```

---

## 第5天：多 Agent 协作模式（30min 阅读 + 20min 设计）

### 📖 多 Agent 协作是什么？

```
单 Agent: 一个 LLM + 工具
多 Agent: 多个专业 Agent 协作

为什么需要多 Agent？
- 复杂任务需要分工
- 不同 Agent 可以专注不同领域
- 可以并行执行提高效率
- 可以互相审查提高质量
```

### 🔍 多 Agent 协作模式

```
协作模式对比:

1. 链式协作 (Pipeline)
   Agent1 → Agent2 → Agent3
   适用: 线性流程，如 研究→写作→编辑

2. 树状协作 (Tree)
        Manager
       /    |    \
    A1     A2    A3
   / \    / \    / \
  B1 B2  B3 B4  B5 B6
   适用: 并行探索，如 多路径调研

3. 图状协作 (Graph)
   A1 ↔ A2 ↔ A3
   ↑    ↓    ↑
   A4 ← A5 → A6
   适用: 复杂交互，如 辩论、谈判

4. 竞争协作 (Competition)
   A1 提案 → A2 审查 → A3 改进
   适用: 质量提升，如 代码审查
```

### 🧠 理解检查

**问题 1**: 什么场景适合用多 Agent？
<details>
<summary>查看答案</summary>

- 任务可以分解为多个子任务
- 子任务需要不同专业知识
- 需要互相审查提高质量
- 需要并行执行提高效率
</details>

**问题 2**: 多 Agent 的缺点是什么？
<details>
<summary>查看答案</summary>

- Token 消耗大（每个 Agent 都要调用 LLM）
- 延迟高（多个 Agent 串行执行）
- 协调复杂（需要定义通信协议）
- 错误传播（一个 Agent 出错影响整体）
</details>

### ⚡ 动手验证

使用 AutoGen 实现简单多 Agent 系统：

```python
# pip install pyautogen
import autogen

# 1. 创建 Agent
user_proxy = autogen.UserProxyAgent(
    name="User",
    human_input_mode="NEVER",
    code_execution_config=False
)

researcher = autogen.AssistantAgent(
    name="Researcher",
    llm_config={"config_list": [{"model": "gpt-4", "api_key": "..."}]},
    system_message="你是一个研究专家，负责收集信息。"
)

writer = autogen.AssistantAgent(
    name="Writer",
    llm_config={"config_list": [{"model": "gpt-4", "api_key": "..."}]},
    system_message="你是一个写作专家，负责撰写报告。"
)

# 2. 启动对话
user_proxy.initiate_chat(
    researcher,
    message="请研究 Python 的 GMP 调度器原理"
)
# researcher 会回复研究结果

# 3. 传递给 Writer
writer.send(
    researcher.last_message()["content"],
    user_proxy
)
```

---

## 第6-7天：生产级系统设计（40min 阅读 + 30min 调优）

### 📖 生产级 Agent 系统的关键挑战

```
生产环境 vs 原型:
├─ 并发: 1 用户 → 1000+ 用户
├─ 延迟: 2s → 200ms P99
├─ 可靠性: 偶尔失败 → 99.9% 可用
├─ 成本: 不考虑 → 严格控制
└─ 安全: 不验证 → 严格审计

核心挑战:
1. 并发控制
2. 缓存策略
3. 限流降级
4. 监控告警
5. 成本控制
```

### 🔍 缓存策略源码

```python
class AgentCache:
    """
    Agent 缓存系统
    
    缓存策略:
    1. 查询缓存: 相同问题直接返回
    2. 工具结果缓存: 相同工具调用缓存
    3. 中间结果缓存: ReAct 循环中间状态
    
    缓存失效:
    - TTL (Time To Live)
    - 主动失效
    - LRU (最近最少使用)
    """
    
    def __init__(self, ttl=3600, max_size=10000):
        self.cache = {}  # {hash: (result, expire_time)}
        self.ttl = ttl
        self.max_size = max_size
        
    def get(self, key: str):
        """获取缓存"""
        if key in self.cache:
            result, expire_time = self.cache[key]
            if time.time() < expire_time:
                return result
            else:
                del self.cache[key]  # 过期删除
        return None
    
    def set(self, key: str, value):
        """设置缓存"""
        # LRU 淘汰
        if len(self.cache) >= self.max_size:
            self._evict_lru()
        
        self.cache[key] = (value, time.time() + self.ttl)
    
    def _evict_lru(self):
        """淘汰最久未使用的缓存"""
        oldest_key = min(self.cache, key=lambda k: self.cache[k][1])
        del self.cache[oldest_key]
    
    def cache_key(self, question: str) -> str:
        """生成缓存键"""
        import hashlib
        return hashlib.md5(question.encode()).hexdigest()
```

### 🧠 理解检查

**问题 1**: 为什么 Agent 系统需要缓存？
<details>
<summary>查看答案</summary>

- LLM 调用成本高（每次 0.01-0.1 元）
- LLM 调用耗时长（每次 1-3 秒）
- 很多问题是重复的
- 缓存可以大幅降低成本和延迟
</details>

**问题 2**: 缓存的 Key 怎么设计？
<details>
<summary>查看答案</summary>

- 简单方案: 用户问题原文的 hash
- 复杂方案: 用户问题 + 历史对话 + 工具参数的 hash
- 关键: 相同输入必须生成相同 Key
</details>

### ⚡ 动手验证

```python
import time
from functools import lru_cache

# 1. 测试缓存效果
@lru_cache(maxsize=100)
def expensive_operation(query: str) -> str:
    """模拟 LLM 调用"""
    time.sleep(2)  # 模拟 2 秒延迟
    return f"这是 {query} 的答案"

# 2. 第一次调用（缓存未命中）
start = time.time()
result1 = expensive_operation("什么是 Python?")
print(f"第一次调用: {time.time()-start:.2f}s")

# 3. 第二次调用（缓存命中）
start = time.time()
result2 = expensive_operation("什么是 Python?")
print(f"第二次调用: {time.time()-start:.2f}s")

# 4. 不同问题（缓存未命中）
start = time.time()
result3 = expensive_operation("什么是 Java?")
print(f"不同问题: {time.time()-start:.2f}s")
```

---

## ✅ 学习验收标准

完成 7 天后，你应该能：

- [ ] 手写 ReAct 循环代码
- [ ] 解释 RAG 的完整流程
- [ ] 画出多 Agent 协作流程图
- [ ] 设计缓存策略
- [ ] 优化 RAG 检索准确率
- [ ] 分析 Agent 系统性能瓶颈

**每项都做到，才算真正掌握。**
