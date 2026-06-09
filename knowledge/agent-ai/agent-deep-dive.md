# Agent 技术深度指南 — 源码级原理与生产级架构

> 创建日期: 2026-06-08
> 作者: Ryan

---

## 一、Agent 架构源码级原理

### 1.1 Agent 执行引擎 — 源码级分析

```python
# LangChain AgentExecutor 核心源码分析（langchain/agents/executor.py）
# 这是生产级 Agent 的参考实现

class AgentExecutor(BaseAgentExecutor):
    """
    Agent 执行引擎核心实现
    
    源码结构分析:
    - input_variables: 输入变量（如 question, history）
    - output_parser: 输出解析器
    - agent: 智能体（定义 how to think）
    - tools: 可用工具列表
    - max_iterations: 最大迭代次数（防止死循环）
    - max_execution_time: 最大执行时间
    - early_stopping_method: 早停策略（"force_return" 或 "generate"）
    """
    
    def _call(self, inputs: dict) -> dict:
        """
        核心执行逻辑源码
        
        执行流程:
        1. 初始化空 action_seq（动作序列）
        2. 进入 while 循环，直到满足退出条件
        3. 调用 agent.plan() 生成下一步行动
        4. 执行行动并获取观察结果
        5. 将结果追加到 action_seq
        6. 检查是否达到 max_iterations
        7. 调用 output_parser 解析最终输出
        """
        stop = False
        action_seq: List[AgentAction] = []
        
        # 初始化输入
        new_inputs = self.agent_format_instructions(inputs)
        
        while not stop:
            # Step 1: Agent 规划（核心推理过程）
            agent_output = self.agent.plan(new_inputs, action_seq)
            
            # Step 2: 检查是否应该停止
            if self.early_stopping_method == "force_return":
                # 强制返回模式：达到最大迭代次数时强制返回
                if len(action_seq) >= self.max_iterations:
                    stop = True
                    break
            elif self.early_stopping_method == "generate":
                # 生成模式：让 LLM 决定是否停止
                if isinstance(agent_output, AgentFinish):
                    stop = True
                    break
            
            # Step 3: 执行行动
            if isinstance(agent_output, AgentFinish):
                # 直接返回结果
                return self.output_parser.parse(agent_output.return_values)
            elif isinstance(agent_output, AgentAction):
                # 执行工具调用
                observation = self._take_next_step(
                    name_to_tool_map,
                    self.color_map,
                    agent_output,
                    new_inputs
                )
                # 将观察结果追加到序列
                action_seq.append(agent_output)
            else:
                raise ValueError("Invalid AgentOutput type")
        
        # Step 4: 格式化输出
        final_outputs = self.agent.return_stopped_response(
            self.early_stopping_method,
            self.max_iterations,
            action_seq,
            inputs
        )
        return final_outputs
```

**源码级关键点**:

| 组件 | 作用 | 源码位置 | 性能影响 |
|------|------|----------|----------|
| `agent.plan()` | 核心推理引擎 | `langchain/agents/agent.py` | 决定调用 LLM 次数，每次调用 ~1-3s |
| `action_seq` | 动作历史 | 内存列表 | 随迭代次数线性增长，需管理 token 限制 |
| `max_iterations` | 防死循环 | 构造函数参数 | 默认 10-15 次，过多会导致 token 超限 |
| `output_parser` | 输出解析 | 自定义解析器 | 影响最终结果的结构化程度 |

### 1.2 ReAct 模式 — 状态机源码分析

```python
# ReAct 状态机实现（基于 langchain/agents/mrkl/state.py）
# MRKL = Modular Reasoning, Knowledge, and Language

from enum import Enum

class AgentState(Enum):
    """Agent 执行状态机"""
    INITIALIZING = "initializing"      # 初始化
    PLANNING = "planning"             # 规划阶段
    ACTING = "acting"                 # 执行阶段
    OBSERVING = "observing"           # 观察阶段
    FINISHING = "finishing"           # 收尾阶段
    FAILED = "failed"                 # 失败

class ReActStateTracker:
    """
    ReAct 模式的状态追踪器
    
    状态转换图:
    INITIALIZING → PLANNING → ACTING → OBSERVING → PLANNING → ... → FINISHING
                                        ↓ (失败)
                                     FAILED
    
    核心设计:
    - 维护当前状态
    - 记录历史动作和观察
    - 管理 token 预算
    - 处理异常和重试
    """
    
    def __init__(self, max_tokens: int = 4000):
        self.state = AgentState.INITIALIZING
        self.action_history: List[Dict] = []
        self.observation_history: List[Dict] = []
        self.token_budget = max_tokens
        self.tokens_used = 0
        
    def transition(self, new_state: AgentState) -> bool:
        """
        状态转换
        
        返回值:
        - True: 转换成功
        - False: 转换失败（如 token 预算不足）
        """
        # 检查 token 预算
        if self.tokens_used > self.token_budget:
            self.state = AgentState.FAILED
            return False
        
        # 执行状态转换
        old_state = self.state
        self.state = new_state
        
        # 记录状态转换日志
        self._log_state_transition(old_state, new_state)
        
        return True
    
    def record_action(self, action: str, thought: str):
        """记录动作"""
        self.action_history.append({
            "thought": thought,
            "action": action,
            "tokens": self._count_tokens(f"Thought: {thought}\nAction: {action}")
        })
        self.tokens_used += self.action_history[-1]["tokens"]
        
    def record_observation(self, observation: str):
        """记录观察"""
        self.observation_history.append({
            "observation": observation,
            "tokens": self._count_tokens(f"Observation: {observation}")
        })
        self.tokens_used += self.observation_history[-1]["tokens"]
```

**ReAct 核心源码逻辑**:

```python
# ReAct 循环的伪源码实现
def react_loop(agent, task, tools, state_tracker):
    """
    ReAct 核心循环
    
    源码分析要点:
    1. Prompt 构建：将历史动作和观察组装成上下文
    2. LLM 调用：发送 prompt 获取下一步行动
    3. Action 解析：从 LLM 响应中提取动作和参数
    4. 工具执行：调用相应工具获取观察结果
    5. 状态更新：更新状态追踪器
    6. 循环判断：检查是否应该继续或停止
    """
    state_tracker.transition(AgentState.PLANNING)
    
    while True:
        # 构建 prompt
        prompt = build_react_prompt(
            task=task,
            action_history=state_tracker.action_history,
            observation_history=state_tracker.observation_history,
            available_tools=tools
        )
        
        # LLM 推理（核心：这里是 Agent 的"思考"过程）
        llm_output = agent.llm.generate(prompt)
        
        # 解析输出
        action_output = parse_react_output(llm_output)
        
        if action_output.is_finish():
            state_tracker.transition(AgentState.FINISHING)
            return action_output.final_answer
        
        # 执行动作
        state_tracker.transition(AgentState.ACTING)
        observation = execute_action(
            action_output.action,
            action_output.input
        )
        
        # 记录观察
        state_tracker.transition(AgentState.OBSERVING)
        state_tracker.record_observation(observation)
        
        # 回到规划状态
        state_tracker.transition(AgentState.PLANNING)
```

---

## 二、RAG 系统 — 生产级架构源码分析

### 2.1 RAG 完整流水线源码

```python
# 生产级 RAG 系统架构（基于 LangChain + 向量数据库）
# 源码级分析每个组件的实现细节

from typing import List, Dict, Optional
import asyncio

class ProductionRAGSystem:
    """
    生产级 RAG 系统
    
    架构组件:
    1. Query Expander: 查询扩展（同义词、相关查询生成）
    2. Embedding Model: 向量化模型
    3. Vector Store: 向量数据库（FAISS/Redis/pgvector）
    4. Reranker: 重排序模型
    5. Context Compressor: 上下文压缩
    6. LLM Generator: 最终答案生成
    
    性能优化点:
    - 异步并发调用
    - 缓存层
    - 批量处理
    - 流式输出
    """
    
    def __init__(self):
        # 查询扩展器
        self.query_expander = QueryExpander()
        
        # 嵌入模型
        self.embedder = EmbeddingModel(model="text-embedding-ada-002")
        
        # 向量数据库
        self.vector_store = VectorStore(
            provider="redis",
            host="localhost",
            port=6379,
            db=0
        )
        
        # 重排序器
        self.reranker = CrossEncoderReranker()
        
        # LLM
        self.llm = LLMProvider(model="gpt-4", temperature=0.3)
        
        # 缓存层
        self.cache = LRUCache(max_size=1000)
        
    async def query(self, question: str, top_k: int = 5) -> str:
        """
        查询执行流程（异步）
        
        源码执行路径:
        1. 检查缓存
        2. 查询扩展
        3. 向量化
        4. 向量检索
        5. 重排序
        6. 上下文压缩
        7. LLM 生成
        8. 缓存结果
        """
        # 1. 缓存检查
        cache_key = hash(question)
        if cached_result := self.cache.get(cache_key):
            return cached_result
        
        # 2. 查询扩展（并行）
        expanded_queries = await asyncio.gather(
            self.query_expander.expand_synonyms(question),
            self.query_expander.generate_related(question),
            self.query_expander.rewrite(question)
        )
        
        # 3. 向量化（批量）
        all_queries = [question] + expanded_queries[0] + expanded_queries[1] + expanded_queries[2]
        embeddings = await self.embedder.encode_batch(all_queries)
        
        # 4. 向量检索（并行）
        search_tasks = [
            self.vector_store.search(embedding, k=top_k * 2)
            for embedding in embeddings
        ]
        search_results = await asyncio.gather(*search_tasks)
        
        # 5. 去重和重排序
        deduplicated_docs = self._deduplicate(search_results)
        reranked_docs = await self.reranker.rerank(question, deduplicated_docs, top_k=top_k)
        
        # 6. 上下文压缩
        compressed_context = self._compress_context(reranked_docs)
        
        # 7. LLM 生成
        prompt = self._build_rag_prompt(question, compressed_context)
        answer = await self.llm.generate(prompt)
        
        # 8. 缓存
        self.cache.set(cache_key, answer)
        
        return answer
    
    def _build_rag_prompt(self, question: str, context: str) -> str:
        """
        构建 RAG prompt
        
        Prompt 工程最佳实践:
        - 明确指示基于上下文回答
        - 允许"不知道"的回复
        - 要求引用来源
        """
        return f"""
        你是一位专业的问答助手。请基于以下上下文回答问题。
        
        上下文:
        {context}
        
        问题: {question}
        
        要求:
        1. 只基于提供的上下文回答问题
        2. 如果上下文中没有相关信息，请说明"抱歉，我无法从提供的上下文中找到答案"
        3. 回答要准确、详细
        4. 引用相关来源
        """
```

### 2.2 向量数据库 — 源码级实现

```python
# Redis 向量存储实现（基于 redis-vectors 库）
# 分析 Redis 如何实现向量相似度搜索

import redis
import numpy as np
from typing import List, Dict, Tuple

class RedisVectorStore:
    """
    Redis 向量存储实现
    
    Redis 向量存储架构:
    - 使用 RedisJSON 模块存储向量元数据
    - 使用 RedisVector 模块（或自实现）进行向量相似度搜索
    - 利用 Redis 的内存特性实现高速检索
    
    核心参数:
    - DIM: 向量维度（Ada-002 为 1536）
    - METRIC: 相似度度量（COSINE/L2/IP）
    - INDEX_NAME: 索引名称
    """
    
    def __init__(self, host: str = "localhost", port: int = 6379, 
                 db: int = 0, dim: int = 1536, metric: str = "COSINE"):
        self.redis_client = redis.Redis(host=host, port=port, db=db)
        self.dim = dim
        self.metric = metric
        self.index_name = "vector_index"
        
        # 创建向量索引（首次初始化）
        self._create_index()
        
    def _create_index(self):
        """
        创建 Redis 向量索引
        
        FT.CREATE 命令分析:
        - ON JSON: 基于 JSON 数据创建索引
        - PREFIX: 索引前缀
        - SCHEMA: 字段定义
          - vector: VECTOR 类型，HNSW 算法
            - DIM: 向量维度
            - TYPE: FLOAT32
            - DISTANCE_METRIC: COSINE
        """
        index_exists = self.redis_client.exists(f"idx:{self.index_name}")
        if not index_exists:
            command = [
                "FT.CREATE", f"idx:{self.index_name}",
                "ON", "JSON",
                "PREFIX", "1", "doc:",
                "SCHEMA",
                "vector", "VECTOR", "HNSW", "16",  # 16 parameters
                "TYPE", "FLOAT32",
                "DIM", str(self.dim),
                "DISTANCE_METRIC", self.metric
            ]
            self.redis_client.execute_command(*command)
    
    async def add_documents(self, documents: List[Dict], embeddings: List[List[float]]):
        """
        批量添加文档和向量
        
        源码优化:
        - 使用 Pipeline 批量操作
        - 事务保证一致性
        - 批量写入提升性能
        """
        pipe = self.redis_client.pipeline(transaction=True)
        
        for doc, embedding in zip(documents, embeddings):
            doc_id = f"doc:{doc['id']}"
            doc_data = {
                "id": doc["id"],
                "content": doc["content"],
                "metadata": doc.get("metadata", {}),
                "vector": np.array(embedding, dtype=np.float32).tobytes()
            }
            pipe.json().set(doc_id, "$", doc_data)
        
        await pipe.execute()
    
    async def search(self, query_embedding: List[float], k: int = 10) -> List[Dict]:
        """
        向量相似度搜索
        
        源码分析 - HNSW 算法:
        - HNSW (Hierarchical Navigable Small World)
        - 构建多层图结构
        - 从顶层开始搜索，逐层逼近
        - 时间复杂度: O(log N)
        
        搜索参数:
        - K: 返回最近邻数量
        - EF: 搜索广度（越大越准确但越慢）
        """
        query_vector = np.array(query_embedding, dtype=np.float32).tobytes()
        
        # 构建搜索查询
        query = [
            "FT.SEARCH", f"idx:{self.index_name}",
            f"@vector:[$vector BINNS  {k}]",
            "PARAMS", "2", "vector", query_vector,
            "DIALECT", "2",
            "SORTBY", "__vector_score",
            "ASC",
            "LIMIT", "0", str(k)
        ]
        
        result = self.redis_client.execute_command(*query)
        
        # 解析结果
        return self._parse_search_result(result)
    
    def _parse_search_result(self, result: list) -> List[Dict]:
        """解析搜索结果"""
        documents = []
        if result and len(result) > 1:
            # result[0] 是结果数量
            # result[1:] 是文档列表
            for doc_data in result[1:]:
                if len(doc_data) >= 2:
                    doc_id = doc_data[0]
                    doc_json = doc_data[1]
                    documents.append({
                        "id": doc_id,
                        "content": doc_json.get("content", ""),
                        "metadata": doc_json.get("metadata", {}),
                        "score": doc_json.get("__vector_score", 0)
                    })
        return documents
```

**Redis 向量存储性能参数**:

| 参数 | 推荐值 | 说明 |
|------|--------|------|
| DIM | 1536 | Ada-002 向量维度 |
| METRIC | COSINE | 余弦相似度 |
| HNSW M | 16 | 每层节点连接数 |
| HNSW EF_CONSTRUCTION | 200 | 构建时搜索广度 |
| HNSW EF_SEARCH | 100 | 搜索时搜索广度 |

---

## 三、多 Agent 编排 — 源码级架构

### 3.1 多 Agent 协作模式源码

```python
# 多 Agent 协作系统（基于 AutoGen 风格实现）
# 分析多 Agent 通信和协调机制

from typing import Dict, List, Optional, Callable
import asyncio
from dataclasses import dataclass, field
from enum import Enum

class AgentRole(Enum):
    """Agent 角色定义"""
    RESEARCHER = "researcher"      # 研究专家
    CODER = "coder"                # 编码专家
    REVIEWER = "reviewer"          # 审查专家
    MANAGER = "manager"            # 任务管理器
    ORCHESTRATOR = "orchestrator"  # 编排器

@dataclass
class Message:
    """Agent 间通信消息"""
    sender: str
    receiver: str
    content: str
    timestamp: float = field(default_factory=lambda: asyncio.get_event_loop().time())
    metadata: Dict = field(default_factory=dict)

class AgentCommunicationBus:
    """
    Agent 间通信总线
    
    源码分析:
    - 异步消息队列
    - 消息路由
    - 消息过滤
    - 消息持久化
    """
    
    def __init__(self):
        self.message_queues: Dict[str, asyncio.Queue] = {}
        self.subscribers: Dict[str, List[str]] = {}  # topic -> agents
        
    async def send(self, message: Message):
        """发送消息"""
        queue = self.message_queues.get(message.receiver)
        if queue:
            await queue.put(message)
    
    async def subscribe(self, agent_id: str, topics: List[str]):
        """订阅主题"""
        self.subscribers[agent_id] = topics
    
    async def receive(self, agent_id: str, timeout: float = 1.0) -> Optional[Message]:
        """接收消息"""
        queue = self.message_queues.get(agent_id)
        if queue:
            try:
                return await asyncio.wait_for(queue.get(), timeout=timeout)
            except asyncio.TimeoutError:
                return None
        return None

class MultiAgentOrchestrator:
    """
    多 Agent 编排器
    
    编排模式:
    1. 任务分解（Manager）
    2. 并行执行（Researcher, Coder）
    3. 结果整合（Orchestrator）
    4. 质量审查（Reviewer）
    """
    
    def __init__(self, agents: Dict[AgentRole, "BaseAgent"]):
        self.agents = agents
        self.comm_bus = AgentCommunicationBus()
        self.task_queue: asyncio.Queue = asyncio.Queue()
        self.result_store: Dict[str, any] = {}
        
    async def execute_task(self, task: str) -> str:
        """
        执行复杂任务
        
        源码执行流程:
        1. 任务分解
        2. 分配子任务
        3. 并行执行
        4. 结果整合
        5. 质量审查
        """
        # 1. 任务分解
        manager = self.agents[AgentRole.MANAGER]
        subtasks = await manager.decompose(task)
        
        # 2. 并行执行子任务
        async def execute_subtask(subtask: str) -> str:
            agent_role = self._assign_agent(subtask)
            agent = self.agents[agent_role]
            return await agent.execute(subtask)
        
        # 并行执行所有子任务
        results = await asyncio.gather(*[
            execute_subtask(st) for st in subtasks
        ])
        
        # 3. 结果整合
        orchestrator = self.agents[AgentRole.ORCHESTRATOR]
        integrated_result = await orchestrator.integrate(results)
        
        # 4. 质量审查
        reviewer = self.agents[AgentRole.REVIEWER]
        final_result = await reviewer.review(integrated_result)
        
        return final_result
    
    def _assign_agent(self, subtask: str) -> AgentRole:
        """根据子任务类型分配 Agent"""
        if "code" in subtask.lower():
            return AgentRole.CODER
        elif "research" in subtask.lower():
            return AgentRole.RESEARCHER
        elif "review" in subtask.lower():
            return AgentRole.REVIEWER
        else:
            return AgentRole.ORCHESTRATOR
```

### 3.2 Agent 通信协议源码分析

```python
# Agent 间通信协议（基于 JSON-RPC 风格）
# 分析 Agent 如何高效通信

import json
import asyncio
from typing import Any, Dict, Optional
from dataclasses import dataclass

@dataclass
class RPCRequest:
    """RPC 请求"""
    id: str
    method: str
    params: Dict[str, Any]
    timestamp: float

@dataclass
class RPCResponse:
    """RPC 响应"""
    id: str
    result: Any
    error: Optional[str]
    timestamp: float

class AgentRPCClient:
    """
    Agent RPC 客户端
    
    源码分析:
    - 异步 RPC 调用
    - 超时处理
    - 重试机制
    - 负载均衡
    """
    
    def __init__(self, agent_id: str, timeout: float = 30.0):
        self.agent_id = agent_id
        self.timeout = timeout
        self.server_url = f"http://agent-server:{agent_id}/rpc"
        
    async def call(self, method: str, params: Dict) -> Any:
        """
        远程调用
        
        源码执行路径:
        1. 构建 RPC 请求
        2. 发送 HTTP 请求
        3. 等待响应
        4. 解析响应
        5. 处理错误
        """
        request = RPCRequest(
            id=generate_uuid(),
            method=method,
            params=params,
            timestamp=asyncio.get_event_loop().time()
        )
        
        try:
            # 发送请求
            response = await self._send_request(request)
            
            # 检查错误
            if response.error:
                raise Exception(f"RPC Error: {response.error}")
            
            return response.result
            
        except asyncio.TimeoutError:
            # 超时重试
            return await self._retry_call(method, params)
    
    async def _send_request(self, request: RPCRequest) -> RPCResponse:
        """发送 RPC 请求"""
        payload = {
            "jsonrpc": "2.0",
            "method": request.method,
            "params": request.params,
            "id": request.id
        }
        
        # 使用 aiohttp 发送异步 HTTP 请求
        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.server_url,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            ) as response:
                result = await response.json()
                return RPCResponse(
                    id=result.get("id"),
                    result=result.get("result"),
                    error=result.get("error"),
                    timestamp=asyncio.get_event_loop().time()
                )
```

---

## 四、生产级 Agent 系统 — 深度架构

### 4.1 安全性源码实现

```python
# 生产级 Agent 安全机制
# 源码级实现输入验证、输出审核、权限控制

class ProductionAgentSecurity:
    """
    生产级 Agent 安全系统
    
    安全层:
    1. 输入验证（Input Validation）
    2. 输出审核（Output Audit）
    3. 权限控制（Access Control）
    4. 速率限制（Rate Limiting）
    5. 审计日志（Audit Logging）
    """
    
    def __init__(self):
        self.input_validator = InputValidator()
        self.output_auditor = OutputAuditor()
        self.access_controller = AccessController()
        self.rate_limiter = RateLimiter()
        self.audit_logger = AuditLogger()
        
    def secure_execute(self, agent, user_id: str, task: str) -> str:
        """
        安全执行 Agent 任务
        
        源码执行流程:
        1. 速率限制检查
        2. 权限验证
        3. 输入验证
        4. 执行任务
        5. 输出审核
        6. 记录审计日志
        """
        # 1. 速率限制
        if not self.rate_limiter.allow_request(user_id):
            raise RateLimitExceededError("请求频率过高")
        
        # 2. 权限验证
        if not self.access_controller.has_permission(user_id, "agent.execute"):
            raise PermissionError("无权执行 Agent 任务")
        
        # 3. 输入验证
        if not self.input_validator.validate(task):
            raise ValueError("输入包含非法内容")
        
        # 4. 执行任务
        try:
            result = agent.execute(task)
        except Exception as e:
            self.audit_logger.log_error(user_id, task, str(e))
            raise
        
        # 5. 输出审核
        if not self.output_auditor.audit(result):
            self.audit_logger.log_audit_failure(user_id, task, result)
            return "输出包含不适当内容"
        
        # 6. 记录审计日志
        self.audit_logger.log_success(user_id, task, result)
        
        return result
```

### 4.2 性能优化源码分析

```python
# 性能优化策略源码实现

class PerformanceOptimizer:
    """
    性能优化器
    
    优化策略:
    1. 缓存层（Cache Layer）
    2. 批量处理（Batch Processing）
    3. 流式输出（Streaming）
    4. 连接池（Connection Pooling）
    5. 异步处理（Async Processing）
    """
    
    def __init__(self):
        self.cache = LRUCache(max_size=10000)
        self.batch_processor = BatchProcessor(batch_size=10)
        self.connection_pool = ConnectionPool(max_connections=100)
        
    def optimized_query(self, query: str) -> str:
        """
        优化的查询执行
        
        源码执行路径:
        1. 缓存命中检查
        2. 批量处理
        3. 使用连接池
        4. 异步执行
        5. 结果缓存
        """
        # 1. 缓存检查
        cache_key = hash(query)
        if cached := self.cache.get(cache_key):
            return cached
        
        # 2. 批量处理
        results = self.batch_processor.process([query])
        
        # 3. 使用连接池执行
        with self.connection_pool.get_connection() as conn:
            result = conn.execute(results[0])
        
        # 4. 缓存结果
        self.cache.set(cache_key, result)
        
        return result
```

---

*本文档基于 LangChain、AutoGen、Redis 等开源项目源码分析整理，包含生产级实现和性能优化*
