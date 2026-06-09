# Agent 技术深度指南 — 从原理到生产级系统设计

> 创建日期: 2026-06-08
> 作者: Ryan
> 标签: #Agent #AIAgent #RAG #ReAct #多Agent #生产级

---

## 一、Agent 核心原理 — 源码级理解

### 1.1 Agent 的本质

```
Agent = LLM(推理) + Memory(记忆) + Tools(工具) + Planning(规划)

不是简单的"聊天机器人"，而是能够：
1. 理解复杂任务
2. 自主规划步骤
3. 调用外部工具
4. 管理记忆上下文
5. 迭代优化结果
```

### 1.2 核心组件深度解析

#### 1.2.1 LLM 作为 Agent 大脑

```python
# LLM 在 Agent 中的角色
class AgentBrain:
    def __init__(self, model="gpt-4"):
        self.model = model
        self.temperature = 0.7  # 创造性 vs 确定性
        
    def reason(self, context: str, task: str) -> str:
        """推理：分析任务并生成思考"""
        prompt = f"""
        你是一个智能助手。当前任务: {task}
        上下文信息: {context}
        
        请逐步分析:
        1. 任务的目标是什么？
        2. 需要哪些信息？
        3. 应该采取什么行动？
        
        思考过程:
        """
        return self.model.generate(prompt, temperature=0.3)
    
    def decide(self, context: str) -> str:
        """决策：选择最佳行动"""
        prompt = f"""
        上下文: {context}
        
        从以下行动中选择一个:
        - search: 搜索信息
        - calculate: 执行计算
        - code: 编写代码
        - answer: 直接回答
        
        只返回行动名称，不要其他内容。
        """
        return self.model.generate(prompt, temperature=0.1)
```

**关键点**：
- temperature 控制创造性：推理时用 0.3，决策时用 0.1
- Prompt 工程比调参更重要：结构化提示词提升 30%+ 效果

#### 1.2.2 记忆系统架构

```python
# 三级记忆架构
class AgentMemory:
    def __init__(self):
        # 短期记忆：最近 N 轮对话
        self.short_term = deque(maxlen=50)
        
        # 长期记忆：向量数据库
        self.long_term = VectorDB(embedding_model="text-embedding-ada-002")
        
        # 工作记忆：当前任务上下文
        self.working = {}
        
    def store(self, experience: dict):
        """存储经验"""
        # 短期记忆：直接添加
        self.short_term.append(experience)
        
        # 长期记忆：向量化后存储
        embedding = self.get_embedding(experience["content"])
        self.long_term.add(
            id=experience["id"],
            embedding=embedding,
            metadata={
                "timestamp": experience["timestamp"],
                "topic": experience["topic"],
                "importance": experience["importance"]
            }
        )
        
    def retrieve(self, query: str, k: int = 5) -> list:
        """检索记忆"""
        # 1. 从短期记忆中检索
        recent = list(self.short_term)[-20:]
        
        # 2. 从长期记忆中检索
        query_embedding = self.get_embedding(query)
        similar = self.long_term.search(
            embedding=query_embedding, 
            k=k
        )
        
        # 3. 合并并排序
        all_memories = recent + similar
        return self.rank_by_relevance(all_memories, query)
    
    def get_embedding(self, text: str) -> list:
        """获取文本向量"""
        return self.model.embed(text)
```

**为什么需要三级记忆？**
- 短期记忆：低延迟访问最近上下文
- 长期记忆：支持跨会话的知识积累
- 工作记忆：当前任务的状态管理

#### 1.2.3 工具调用机制

```python
# 工具调用实现
class ToolRegistry:
    def __init__(self):
        self.tools = {}
        
    def register(self, name: str, func: callable, description: str):
        """注册工具"""
        self.tools[name] = {
            "func": func,
            "description": description,
            "parameters": self.get_parameters(func)
        }
        
    def get_available_tools(self) -> list:
        """获取可用工具列表"""
        return [
            {
                "name": name,
                "description": tool["description"],
                "parameters": tool["parameters"]
            }
            for name, tool in self.tools.items()
        ]
    
    def execute(self, tool_name: str, **kwargs) -> str:
        """执行工具"""
        if tool_name not in self.tools:
            raise ValueError(f"Unknown tool: {tool_name}")
        
        tool = self.tools[tool_name]
        try:
            result = tool["func"](**kwargs)
            return str(result)
        except Exception as e:
            return f"Tool execution failed: {str(e)}"

# 示例工具
@tool_registry.register(
    "search_web",
    search_web_function,
    "搜索互联网获取最新信息"
)
def search_web_function(query: str, max_results: int = 5) -> str:
    """网络搜索工具"""
    results = web_search(query, max_results)
    return format_search_results(results)

@tool_registry.register(
    "execute_python",
    execute_python_code,
    "执行Python代码并返回结果"
)
def execute_python_code(code: str) -> str:
    """代码执行工具"""
    try:
        # 安全执行代码
        local_vars = {}
        exec(code, {}, local_vars)
        return str(local_vars)
    except Exception as e:
        return f"Code execution error: {str(e)}"
```

---

## 二、ReAct 模式 — 深度实现

### 2.1 ReAct 核心原理

```
ReAct = Reason(推理) + Act(行动)

传统 Chain-of-Thought:
思考 → 思考 → 思考 → 答案

ReAct 模式:
思考 → 行动 → 观察 → 思考 → 行动 → 观察 → 答案

优势：
1. 利用外部信息纠正错误推理
2. 实时反馈优化决策
3. 处理复杂多步骤任务
```

### 2.2 完整实现

```python
class ReActAgent:
    def __init__(self, llm, memory, tools):
        self.llm = llm
        self.memory = memory
        self.tools = tools
        self.max_steps = 10
        
    def run(self, task: str) -> str:
        """执行 ReAct 循环"""
        context = self.initialize_context(task)
        
        for step in range(self.max_steps):
            # 1. 思考
            thought = self.think(context)
            
            # 2. 决定是否行动
            if self.should_finish(context):
                break
                
            # 3. 选择工具
            action, action_input = self.select_action(context)
            
            # 4. 执行行动
            observation = self.execute_action(action, action_input)
            
            # 5. 更新上下文
            context = self.update_context(
                context, 
                thought, 
                action, 
                action_input, 
                observation
            )
            
            # 6. 记录到记忆
            self.memory.store({
                "step": step,
                "thought": thought,
                "action": action,
                "observation": observation
            })
        
        # 生成最终答案
        return self.generate_answer(context)
    
    def think(self, context: str) -> str:
        """思考过程"""
        prompt = f"""
        当前任务: {context['task']}
        已执行步骤: {context['steps']}
        当前观察: {context['observation']}
        
        请分析当前状态并决定下一步:
        1. 我目前知道了什么？
        2. 我还缺少什么信息？
        3. 我应该采取什么行动？
        
        思考:
        """
        return self.llm.generate(prompt)
    
    def select_action(self, context: str) -> tuple:
        """选择行动"""
        prompt = f"""
        根据以下信息，选择一个合适的工具:
        
        任务: {context['task']}
        当前状态: {context['observation']}
        可用工具: {self.tools.get_available_tools()}
        
        请返回:
        - 工具名称
        - 工具参数
        
        格式:
        Thought: 你的思考
        Action: 工具名称
        Action Input: 工具参数
        """
        
        response = self.llm.generate(prompt)
        # 解析响应
        return self.parse_action(response)
    
    def execute_action(self, action: str, action_input: dict) -> str:
        """执行行动"""
        try:
            result = self.tools.execute(action, **action_input)
            return f"Observation: {result}"
        except Exception as e:
            return f"Observation: Error - {str(e)}"
```

### 2.3 ReAct 优化技巧

```python
# 优化 1: 上下文窗口管理
def manage_context_window(self, context: str, max_tokens: int = 4000) -> str:
    """管理上下文窗口"""
    tokens = self.count_tokens(context)
    
    if tokens > max_tokens:
        # 摘要关键信息
        summary = self.llm.summarize(context, max_tokens=max_tokens // 2)
        # 保留最近步骤
        recent_steps = context[-max_tokens // 2:]
        return f"{summary}\nRecent Steps:\n{recent_steps}"
    
    return context

# 优化 2: 并行工具调用
def parallel_execute(self, actions: list) -> dict:
    """并行执行多个工具"""
    import asyncio
    
    async def execute_single(action):
        return await self.tools.execute_async(**action)
    
    tasks = [execute_single(action) for action in actions]
    return dict(zip([a["name"] for a in actions], 
                   asyncio.run(asyncio.gather(*tasks))))
```

---

## 三、RAG 系统 — 生产级架构

### 3.1 RAG 核心流程

```
用户问题 → 查询理解 → 向量检索 → 结果重排 → 上下文组装 → LLM 生成 → 答案
```

### 3.2 完整实现

```python
class ProductionRAG:
    def __init__(self):
        self.embedder = EmbeddingModel()
        self.vector_db = VectorDB()
        self.reranker = RerankerModel()
        self.llm = LLM()
        
    def retrieve(self, query: str, k: int = 10) -> list:
        """检索相关文档"""
        # 1. 查询理解
        expanded_query = self.expand_query(query)
        
        # 2. 向量检索
        embeddings = self.embedder.encode(expanded_query)
        docs = self.vector_db.search(embeddings, k=k*2)  # 召回更多用于重排
        
        # 3. 结果重排
        reranked = self.reranker.rerank(query, docs, top_k=k)
        
        return reranked
    
    def generate(self, query: str, context: list) -> str:
        """生成答案"""
        # 上下文组装
        context_text = self.format_context(context)
        
        prompt = f"""
        基于以下上下文信息回答问题:
        
        上下文:
        {context_text}
        
        问题: {query}
        
        请提供准确、详细的回答。如果上下文中没有相关信息，请说明。
        """
        
        return self.llm.generate(prompt, temperature=0.3)
    
    def expand_query(self, query: str) -> list:
        """查询扩展"""
        # 同义词扩展
        synonyms = self.get_synonyms(query)
        # 相关问题生成
        related = self.llm.generate_related_questions(query)
        
        return [query] + synonyms + related

# 向量数据库配置
class VectorDB:
    def __init__(self, provider="faiss"):
        if provider == "faiss":
            self.index = faiss.IndexFlatL2(1536)  # Ada-002 维度
        elif provider =...[truncated]