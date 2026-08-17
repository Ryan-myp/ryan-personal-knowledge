# Agent 开发工程师 - 校招面试题集

> 版本: v1.0  
> 日期: 2026-08-14  
> 适用岗位: 初级/中级 Agent 开发工程师

---

## 目录

1. [Python 基础](#1-python-基础)
2. [数据结构与算法](#2-数据结构与算法)
3. [计算机网络](#3-计算机网络)
4. [操作系统](#4-操作系统)
5. [数据库](#5-数据库)
6. [LLM 与 NLP 基础](#6-llm-与-nlp-基础)
7. [Agent 架构设计](#7-agent-架构设计)
8. [RAG 系统](#8-rag-系统)
9. [系统工程与架构](#9-系统工程与架构)
10. [场景题与开放题](#10-场景题与开放题)
11. [编程题（在线编码）](#11-编程题在线编码)

---

## 1. Python 基础

### 1.1 必答题

**Q1: 请解释 Python 中的 GIL（全局解释器锁），它对多线程有什么影响？**

期望回答要点:
- GIL 是 CPython 解释器的一个互斥锁，保证同一时刻只有一个线程执行 Python 字节码
- 影响：CPU 密集型任务多线程无法真正并行，IO 密集型任务受影响较小
- 解决方案：使用多进程、使用 Cython 释放 GIL、使用 Jython/IronPython

```python
# 示例：多线程在 CPU 密集型任务上的问题
import threading
import time

def cpu_bound(n):
    while n > 0:
        n -= 1

start = time.time()
threads = [threading.Thread(target=cpu_bound, args=(10000000,)) for _ in range(4)]
for t in threads: t.start()
for t in threads: t.join()
print(f"多线程耗时: {time.time() - start:.2f}s")  # 实际可能比单线程更慢
```

---

**Q2: Python 中的装饰器是什么？请写一个计时装饰器。**

期望回答:
- 装饰器是一个函数，接受一个函数作为参数，返回一个新的函数
- 使用 `@decorator` 语法糖
- 常见用途：日志、计时、权限验证、缓存

```python
import functools
import time

def timer(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        end = time.time()
        print(f"{func.__name__} 耗时: {end - start:.4f}s")
        return result
    return wrapper

@timer
def process_data(n):
    time.sleep(0.1)
    return sum(range(n))

process_data(1000000)
```

---

**Q3: 请解释 `*args` 和 `**kwargs` 的用法和区别。**

期望回答:
- `*args`: 接收任意数量的位置参数，打包为 tuple
- `**kwargs`: 接收任意数量的关键字参数，打包为 dict
- 常用在函数定义和函数调用中

```python
def example(*args, **kwargs):
    print(f"args: {args}, type: {type(args)}")  # tuple
    print(f"kwargs: {kwargs}, type: {type(kwargs)}")  # dict

example(1, 2, 3, name="Alice", age=25)
```

---

**Q4: Python 中的 Generator 是什么？与 List 相比有什么优势？**

期望回答:
- Generator 使用 `yield` 关键字，惰性求值
- 优势：节省内存（不一次性加载所有数据）、支持无限序列
- 使用场景：大数据处理、迭代器协议

```python
# Generator 示例
def fibonacci(n):
    a, b = 0, 1
    for _ in range(n):
        yield a
        a, b = b, a + b

# 内存高效：一次只生成一个值
for num in fibonacci(1000000):
    print(num)
```

---

**Q5: 请解释 Python 中的 `__new__` 和 `__init__` 的区别。**

期望回答:
- `__new__`: 静态方法，负责创建实例（内存分配）
- `__init__`: 实例方法，负责初始化实例属性
- `__new__` 先于 `__init__` 执行

```python
class Singleton:
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, value):
        self.value = value
```

---

### 1.2 选答题

**Q6: Python 中的 metaclass 是什么？请举例说明。**

**Q7: 请解释 Python 中的 descriptor 协议。**

**Q8: Python 的 MRO（Method Resolution Order）是如何工作的？**

---

## 2. 数据结构与算法

### 2.1 必答题

**Q1: 请实现 LRU Cache。**

```python
from collections import OrderedDict

class LRUCache:
    def __init__(self, capacity: int):
        self.cache = OrderedDict()
        self.capacity = capacity
    
    def get(self, key: int) -> int:
        if key not in self.cache:
            return -1
        self.cache.move_to_end(key)  # 标记为最新使用
        return self.cache[key]
    
    def put(self, key: int, value: int) -> None:
        if key in self.cache:
            self.cache.move_to_end(key)
        self.cache[key] = value
        if len(self.cache) > self.capacity:
            self.cache.popitem(last=False)  # 删除最久未使用

# 测试
cache = LRUCache(2)
cache.put(1, 1)
cache.put(2, 2)
print(cache.get(1))  # 返回 1
cache.put(3, 3)      # 淘汰 key 2
print(cache.get(2))  # 返回 -1 (not found)
```

**复杂度分析**: O(1) 时间复杂度，O(n) 空间复杂度

---

**Q2: 实现 Trie（前缀树），用于单词查找。**

```python
class TrieNode:
    def __init__(self):
        self.children = {}
        self.is_end = False

class Trie:
    def __init__(self):
        self.root = TrieNode()
    
    def insert(self, word: str) -> None:
        node = self.root
        for char in word:
            if char not in node.children:
                node.children[char] = TrieNode()
            node = node.children[char]
        node.is_end = True
    
    def search(self, word: str) -> bool:
        node = self._find_node(word)
        return node is not None and node.is_end
    
    def starts_with(self, prefix: str) -> bool:
        node = self._find_node(prefix)
        return node is not None
    
    def _find_node(self, prefix: str) -> TrieNode:
        node = self.root
        for char in prefix:
            if char not in node.children:
                return None
            node = node.children[char]
        return node
```

---

**Q3: 给定一个数组，找到最长无重复字符的子串长度。**

```python
def length_of_longest_substring(s: str) -> int:
    char_index = {}  # 字符 -> 最新索引
    max_length = 0
    start = 0
    
    for end, char in enumerate(s):
        if char in char_index and char_index[char] >= start:
            start = char_index[char] + 1
        char_index[char] = end
        max_length = max(max_length, end - start + 1)
    
    return max_length

# 测试
print(length_of_longest_substring("abcabcbb"))  # 3: "abc"
print(length_of_longest_substring("bbbbb"))     # 1: "b"
print(length_of_longest_substring("pwwkew"))    # 3: "wke"
```

**复杂度**: O(n) 时间，O(min(m,n)) 空间（m 为字符集大小）

---

**Q4: 实现二叉树的层序遍历（BFS）。**

```python
from collections import deque

class TreeNode:
    def __init__(self, val=0):
        self.val = val
        self.left = None
        self.right = None

def level_order(root: TreeNode) -> list[list[int]]:
    if not root:
        return []
    
    result = []
    queue = deque([root])
    
    while queue:
        level_size = len(queue)
        current_level = []
        
        for _ in range(level_size):
            node = queue.popleft()
            current_level.append(node.val)
            
            if node.left:
                queue.append(node.left)
            if node.right:
                queue.append(node.right)
        
        result.append(current_level)
    
    return result
```

---

**Q5: 给定两个排序链表，合并它们为一个排序链表。**

```python
class ListNode:
    def __init__(self, val=0):
        self.val = val
        self.next = None

def merge_two_sorted_lists(l1: ListNode, l2: ListNode) -> ListNode:
    dummy = ListNode(0)
    current = dummy
    
    while l1 and l2:
        if l1.val <= l2.val:
            current.next = l1
            l1 = l1.next
        else:
            current.next = l2
            l2 = l2.next
        current = current.next
    
    current.next = l1 or l2
    return dummy.next
```

---

### 2.2 选答题

**Q6: 实现堆排序，并解释为什么堆排序的时间复杂度是 O(n log n)。**

**Q7: 给定一个二维矩阵，找出其中最大的正方形全 1 子矩阵。**

**Q8: 实现带权重的随机选择算法（Weighted Random）。**

```python
import random

class WeightedRandom:
    def __init__(self, weights: list[float]):
        self.weights = weights
        self.prefix_sum = []
        total = 0
        for w in weights:
            total += w
            self.prefix_sum.append(total)
    
    def choose(self) -> int:
        target = random.uniform(0, self.prefix_sum[-1])
        for i, prefix in enumerate(self.prefix_sum):
            if target <= prefix:
                return i
        return len(self.prefix_sum) - 1
```

---

## 3. 计算机网络

### 3.1 必答题

**Q1: 请解释 TCP 三次握手和四次挥手的过程。**

**三次握手:**
```
Client                    Server
  |                         |
  |--- SYN (seq=x) ------->|  第一次握手：客户端发起连接
  |<-- SYN+ACK (seq=y, ack=x+1) --|  第二次握手：服务器确认
  |--- ACK (ack=y+1) ----->|  第三次握手：客户端确认连接建立
  |                         |
  |======= 连接建立 =======|
```

**四次挥手:**
```
Client                    Server
  |                         |
  |--- FIN (seq=u) ------->|  第一次：客户端请求关闭
  |<-- ACK (ack=u+1) -----|  第二次：服务器确认
  |                         |  （此时服务器可能还有数据要发送）
  |<-- FIN+ACK (seq=v) ----|  第三次：服务器请求关闭
  |--- ACK (ack=v+1) ----->|  第四次：客户端确认
  |                         |
  |======= 连接关闭 =======|
```

**Q2: HTTP 和 HTTPS 有什么区别？**

| 特性 | HTTP | HTTPS |
|------|------|-------|
| 端口 | 80 | 443 |
| 加密 | 无 | SSL/TLS 加密 |
| 证书 | 不需要 | 需要 SSL 证书 |
| 性能 | 较快 | 首次握手较慢 |
| SEO | 不利 | 有利 |
| 安全性 | 低（数据明文） | 高（数据加密） |

**Q3: 请解释 DNS 解析过程。**

```
1. 浏览器缓存检查
2. 操作系统缓存检查 (/etc/hosts)
3. 本地 DNS 服务器递归查询
   - 根域名服务器 (.com)
   - 顶级域名服务器 (example.com)
   - 权威域名服务器 (www.example.com)
4. 返回 IP 地址
```

---

### 3.2 选答题

**Q4: HTTP/2 相比 HTTP/1.1 有哪些改进？**

**Q5: 请解释 WebSocket 的工作原理。**

**Q6: 什么是 CDN？它如何工作？**

---

## 4. 操作系统

### 4.1 必答题

**Q1: 请解释进程和线程的区别。**

| 特性 | 进程 | 线程 |
|------|------|------|
| 定义 | 资源分配的基本单位 | CPU 调度的基本单位 |
| 独立性 | 有独立内存空间 | 共享进程内存空间 |
| 开销 | 创建/销毁开销大 | 创建/销毁开销小 |
| 通信 | IPC（管道、消息队列等） | 共享内存 |
| 稳定性 | 一个进程崩溃不影响其他 | 一个线程崩溃可能导致进程崩溃 |

**Q2: 什么是死锁？产生死锁的必要条件是什么？**

**四个必要条件:**
1. 互斥条件：资源不能共享
2. 占有并等待：持有资源同时等待其他资源
3. 不可剥夺：资源不能被强制释放
4. 循环等待：存在等待循环

**解决方法:**
- 破坏必要条件
- 死锁检测与恢复
- 死锁预防（银行家算法）

**Q3: 解释 Linux 中的 fork()、exec()、wait() 系统调用。**

```c
// fork(): 创建子进程
pid_t pid = fork();
if (pid == 0) {
    // 子进程
    execvp("ls", args);  // 替换进程镜像
} else if (pid > 0) {
    // 父进程
    wait(NULL);  // 等待子进程结束
}
```

---

### 4.2 选答题

**Q4: 什么是虚拟内存？它如何工作？**

**Q5: 解释 Linux 中的 epoll 模型，与 select/poll 的区别？**

---

## 5. 数据库

### 5.1 必答题

**Q1: MySQL 索引失效的常见场景有哪些？**

```sql
-- 以下情况索引可能失效:

-- 1. 对索引列进行函数运算
SELECT * FROM users WHERE YEAR(create_time) = 2024;  -- 失效
SELECT * FROM users WHERE create_time >= '2024-01-01';  -- 有效

-- 2. 隐式类型转换
SELECT * FROM users WHERE phone = 13800138000;  -- 失效（字符串列传数字）

-- 3. LIKE 以通配符开头
SELECT * FROM users WHERE name LIKE '%张三';  -- 失效
SELECT * FROM users WHERE name LIKE '张三%';  -- 有效

-- 4. OR 条件不满足联合索引最左前缀
SELECT * FROM users WHERE age = 25 OR phone = '138...';  -- 可能失效

-- 5. 联合索引不使用最左列
-- 索引 (name, age, phone)
SELECT * FROM users WHERE age = 25;  -- 失效
SELECT * FROM users WHERE name = '张三' AND age = 25;  -- 有效
```

**Q2: 请解释 ACID 特性和事务隔离级别。**

**ACID:**
- **A**tomicity（原子性）：事务要么全部成功，要么全部失败回滚
- **C**onsistency（一致性）：事务前后数据保持一致性
- **I**solation（隔离性）：并发事务互不干扰
- **D**urability（持久性）：事务提交后数据永久保存

**隔离级别:**
| 隔离级别 | 脏读 | 不可重复读 | 幻读 |
|---------|------|-----------|------|
| READ UNCOMMITTED | ✓ | ✓ | ✓ |
| READ COMMITTED | ✗ | ✓ | ✓ |
| REPEATABLE READ | ✗ | ✗ | ✓（MySQL InnoDB 解决了） |
| SERIALIZABLE | ✗ | ✗ | ✗ |

**Q3: 什么情况下需要分库分表？**

- 单表数据量超过 1000 万行
- 单库 QPS 超过 1 万
- 存储空间超过单机上限
- 读写分离无法满足需求

**分片策略:**
- 范围分片：按 ID 范围
- 哈希分片：按 hash(id) % N
- 一致性哈希：减少数据迁移

---

### 5.2 选答题

**Q4: Redis 有哪些数据结构？各自的使用场景是什么？**

**Q5: 请解释 Redis 持久化机制（RDB vs AOF）。**

---

## 6. LLM 与 NLP 基础

### 6.1 必答题

**Q1: 请解释 Transformer 的 Attention 机制。**

**核心公式:**
$$\text{Attention}(Q, K, V) = \text{softmax}\left(\frac{QK^T}{\sqrt{d_k}}\right)V$$

**多头注意力（Multi-Head Attention）:**
```python
import torch
import torch.nn as nn
import math

class MultiHeadAttention(nn.Module):
    def __init__(self, d_model, nheads):
        super().__init__()
        self.nheads = nheads
        self.d_k = d_model // nheads
        
        self.W_q = nn.Linear(d_model, d_model)
        self.W_k = nn.Linear(d_model, d_model)
        self.W_v = nn.Linear(d_model, d_model)
        self.W_o = nn.Linear(d_model, d_model)
    
    def forward(self, q, k, v, mask=None):
        batch_size = q.size(0)
        
        # 线性变换
        q = self.W_q(q).view(batch_size, -1, self.nheads, self.d_k).transpose(1, 2)
        k = self.W_k(k).view(batch_size, -1, self.nheads, self.d_k).transpose(1, 2)
        v = self.W_v(v).view(batch_size, -1, self.nheads, self.d_k).transpose(1, 2)
        
        # Attention
        scores = torch.matmul(q, k.transpose(-2, -1)) / math.sqrt(self.d_k)
        if mask is not None:
            scores = scores.masked_fill(mask == 0, -1e9)
        attn = torch.softmax(scores, dim=-1)
        
        # 输出
        out = torch.matmul(attn, v).transpose(1, 2).contiguous()
        out = out.view(batch_size, -1, self.nheads * self.d_k)
        
        return self.W_o(out)
```

---

**Q2: 请解释 LLM 的微调方法：Fine-tuning vs LoRA vs Prompt Tuning。**

| 方法 | 原理 | 参数量 | 训练速度 | 适用场景 |
|------|------|--------|---------|---------|
| Fine-tuning | 更新全部参数 | 100% | 慢 | 数据充足，需要深度定制 |
| LoRA | 低秩分解，冻结原参数 | 0.1-1% | 快 | 数据有限，快速适配 |
| Prompt Tuning | 只训练 prompt 参数 | <0.1% | 最快 | 轻量级任务适配 |

```python
# LoRA 实现示例
from peft import LoraConfig, get_peft_model

config = LoraConfig(
    r=16,              # 低秩维度
    lora_alpha=32,     # 缩放因子
    target_modules=["q_proj", "v_proj"],  # 应用模块
    lora_dropout=0.1,
)

model = get_peft_model(base_model, config)
model.print_trainable_parameters()  # 只显示 LoRA 参数
```

---

**Q3: 什么是 Tokenizer？常见的 Tokenizer 有哪些？**

**工作原理:**
```
原始文本 → 分词 → 词汇映射 → Token IDs

"Hello world!" 
  → ["Hello", " world", "!"] 
  → [1234, 5678, 9012]
```

**常见 Tokenizer:**
- **BPE (Byte-Pair Encoding)**: GPT-2, LLaMA
- **WordPiece**: BERT
- **Unigram**: T5
- **SentencePiece**: 多语言支持

---

### 6.2 选答题

**Q4: 请解释 RLHF（Reinforcement Learning from Human Feedback）的原理。**

**Q5: 什么是思维链（Chain-of-Thought）？如何激活它？**

---

## 7. Agent 架构设计

### 7.1 必答题

**Q1: 请设计一个简单的 Agent 框架，包含 ReAct 循环。**

```python
from typing import List, Dict, Any, Optional
import asyncio

class Agent:
    def __init__(self, llm, tools: List[Dict]):
        self.llm = llm
        self.tools = {t['name']: t for t in tools}
        self.memory = []
    
    async def think(self, thought: str) -> str:
        """使用 LLM 进行思考"""
        messages = [
            {"role": "system", "content": "你是一个智能助手"},
            {"role": "user", "content": thought}
        ]
        return await self.llm.chat(messages)
    
    async def act(self, action: str) -> str:
        """执行动作"""
        tool_name, *args = action.split('(')
        tool = self.tools.get(tool_name.strip())
        if tool:
            return await tool['function'](*args)
        return f"未知工具: {tool_name}"
    
    async def react_loop(self, query: str, max_steps: int = 5) -> str:
        """ReAct 循环：思考 → 行动 → 观察"""
        for step in range(max_steps):
            # 思考
            thought = await self.think(query)
            self.memory.append({"step": step, "type": "thought", "content": thought})
            
            # 判断是否需要行动
            if "最终答案" in thought:
                return thought
            
            # 行动
            action = await self.extract_action(thought)
            if action:
                observation = await self.act(action)
                self.memory.append({"step": step, "type": "action", "content": action})
                self.memory.append({"step": step, "type": "observation", "content": observation})
                query = f"{query}\n观察结果: {observation}"
        
        return "达到最大步数，无法回答"
    
    async def extract_action(self, thought: str) -> Optional[str]:
        """从思考中提取动作"""
        # 简化实现：查找 ToolCall 标记
        if "ToolCall:" in thought:
            return thought.split("ToolCall:")[1].split("<br>")[0].strip()
        return None

# 使用示例
async def main():
    tools = [
        {"name": "search", "function": search_web},
        {"name": "calculator", "function": calculate}
    ]
    
    agent = Agent(llm=model, tools=tools)
    result = await agent.react_loop("今天天气怎么样？")
    print(result)
```

---

**Q2: 请解释 Function Calling 的工作原理。**

```python
# 示例：OpenAI Function Calling
response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "北京今天天气怎么样？"}],
    functions=[
        {
            "name": "get_weather",
            "description": "获取指定城市的天气",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "城市名称"}
                },
                "required": ["city"]
            }
        }
    ],
    function_call="auto"
)

# LLM 返回工具调用
if response.choices[0].message.function_call:
    args = json.loads(response.choices[0].message.function_call.arguments)
    result = get_weather(args["city"])
    
    # 将结果返回给 LLM
    response2 = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "user", "content": "北京今天天气怎么样？"},
            {"role": "assistant", "function_call": response.choices[0].message.function_call},
            {"role": "function", "name": "get_weather", "content": json.dumps(result)}
        ]
    )
```

---

**Q3: 如何设计 Agent 的记忆系统？**

```python
from datetime import datetime
from typing import List, Dict
import hashlib

class MemorySystem:
    def __init__(self):
        self.short_term = []  # 当前会话记忆
        self.long_term = {}   # 长期记忆
        self.working_memory = []  # 工作记忆（最近 n 条）
    
    def add_to_short_term(self, message: Dict):
        """添加短期记忆"""
        self.short_term.append({
            **message,
            "timestamp": datetime.now().isoformat()
        })
        # 限制长度
        if len(self.short_term) > 50:
            self.short_term = self.short_term[-30:]
    
    def save_to_long_term(self, key: str, value: Any):
        """持久化长期记忆"""
        self.long_term[key] = {
            "value": value,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
    
    def recall(self, query: str, top_k: int = 5) -> List[Dict]:
        """检索相关记忆"""
        # 简单实现：关键词匹配
        results = []
        for key, memory in self.long_term.items():
            if query.lower() in str(memory["value"]).lower():
                results.append(memory)
        return results[:top_k]
    
    def get_working_memory(self, limit: int = 10) -> List[Dict]:
        """获取工作记忆"""
        return self.short_term[-limit:]
```

---

### 7.2 选答题

**Q4: 如何设计 Agent 的工具选择策略？**

**Q5: 请解释 Plan-and-Solve 与 ReAct 的区别。**

**Q6: 如何实现 Agent 的自我反思（Self-Reflection）？**

---

## 8. RAG 系统

### 8.1 必答题

**Q1: 请描述 RAG 系统的完整流程。**

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   文档库     │────▶│  索引构建    │────▶│  检索增强    │────▶│   生成回答   │
│  (Documents)│     │ (Embedding) │     │  (Retriever)│     │  (Generator)│
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
                                                       │
                                              ┌────────▼────────┐
                                              │   后处理 & 输出   │
                                              └─────────────────┘
```

**步骤:**
1. **文档分割**: 将长文档切分为小块（Chunking）
2. **向量化**: 使用 Embedding 模型将文本转为向量
3. **索引构建**: 构建向量数据库索引
4. **查询检索**: 将问题转为向量，检索相似文档
5. **上下文拼接**: 将检索结果与问题组合
6. **生成回答**: LLM 基于上下文生成答案

---

**Q2: 如何选择 Chunk Size 和 Chunk Overlap？**

| 场景 | Chunk Size | Overlap | 原因 |
|------|-----------|---------|------|
| 短文本问答 | 200-400 tokens | 20-50 | 保持语义完整 |
| 长文档检索 | 500-1000 tokens | 50-100 | 平衡信息密度与检索精度 |
| 代码检索 | 300-600 tokens | 50-100 | 保持代码逻辑完整 |

```python
def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
    """智能文本分割"""
    chunks = []
    words = text.split()
    
    for i in range(0, len(words), chunk_size - overlap):
        chunk = ' '.join(words[i:i + chunk_size])
        chunks.append(chunk)
    
    return chunks

# 更智能：按段落/句子分割
def chunk_by_sentences(text: str, max_tokens: int = 500) -> List[str]:
    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks, current = [], ""
    
    for sentence in sentences:
        if len(current) + len(sentence) > max_tokens:
            chunks.append(current)
            current = sentence
        else:
            current += " " + sentence if current else sentence
    
    if current:
        chunks.append(current)
    
    return chunks
```

---

**Q3: 如何处理 RAG 的检索不准确问题？**

**解决方案:**

1. **HyDE（Hypothetical Document Embeddings）**:
```python
# 先生成假设性答案，再用假设答案检索
async def hyde_retrieve(query: str, llm, retriever):
    # Step 1: 生成假设性文档
    hypothetical = await llm.chat([
        {"role": "system", "content": "请基于你的知识，生成一个可能回答该问题的文档片段"},
        {"role": "user", "content": query}
    ])
    
    # Step 2: 用假设文档检索真实文档
    relevant_docs = await retriever.search(hypothetical)
    return relevant_docs
```

2. **重排序（Rerank）**:
```python
# 初检 + 重排序
relevant = await retriever.search(query, top_k=50)
reranked = await reranker.rank(query, relevant, top_k=5)
```

3. **Query 改写**:
```python
# 将模糊查询改写为更精确的查询
async def rewrite_query(original_query: str, llm):
    messages = [
        {"role": "system", "content": "请将用户问题改写为更适合检索的形式"},
        {"role": "user", "content": original_query}
    ]
    return await llm.chat(messages)
```

---

### 8.2 选答题

**Q4: 如何选择 Embedding 模型？**

**Q5: 如何实现向量数据库的增量更新？**

---

## 9. 系统工程与架构

### 9.1 必答题

**Q1: 如何设计一个高可用的 LLM 服务架构？**

```
                          ┌─────────────┐
                          │   API Gateway│
                          │  (限流/缓存)  │
                          └──────┬──────┘
                                 │
              ┌──────────────────┼──────────────────┐
              │                  │                  │
      ┌───────▼───────┐  ┌──────▼──────┐   ┌──────▼──────┐
      │  Load Balancer │  │  Cache Layer│   │  Queue      │
      │  (Nginx/Envoy) │  │  (Redis)    │   │  (Celery)   │
      └───────┬───────┘  └─────────────┘   └──────┬──────┘
              │                                     │
    ┌─────────┼─────────┐                 ┌────────┴────────┐
    │         │         │                 │                 │
┌───▼───┐ ┌──▼───┐ ┌──▼───┐         ┌────▼────┐    ┌─────▼─────┐
│GPU 0  │ │GPU 1 │ │GPU 2 │         │ Worker  │    │ Worker    │
│(vLLM) │ │(vLLM)│ │(vLLM)│         │ (batch) │    │ (async)   │
└───────┘ └──────┘ └──────┘         └─────────┘    └───────────┘
```

**关键设计:**
- **负载均衡**: Nginx/Envoy 分发请求
- **缓存层**: Redis 缓存常见查询结果
- **批处理**: 合并小请求为大 batch
- **异步队列**: Celery/RQ 处理耗时操作
- **熔断降级**: 服务故障时返回 fallback 答案

---

**Q2: 如何进行 LLM 服务的性能优化？**

| 优化方法 | 原理 | 效果 |
|---------|------|------|
| **Batching** | 合并多个请求 | 提高 GPU 利用率 |
| **PagedAttention** | vLLM 的显存管理 | 减少显存碎片 |
| **Speculative Decoding** | 用小模型草稿 + 大模型验证 | 加速推理 2-3x |
| **Quantization** | FP16/INT8/INT4 | 减少显存，加速计算 |
| **KV Cache** | 缓存已计算的 Key-Value | 避免重复计算 |

```python
# vLLM 示例
from vllm import LLM, SamplingParams

llm = LLM(model="meta-llama/Llama-2-7b-chat-hf", tensor_parallel_size=2)

sampling_params = SamplingParams(
    temperature=0.7,
    top_p=0.9,
    max_tokens=512
)

prompts = ["Hello, my name is", "The capital of France is"] * 100  # 批量请求
outputs = llm.generate(prompts, sampling_params)

for output in outputs:
    print(output.outputs[0].text)
```

---

**Q3: 如何设计 Agent 的错误恢复机制？**

```python
import asyncio
from typing import Optional, Callable, Any

class RetryWithFallback:
    def __init__(self, max_retries: int = 3, fallback: Optional[Callable] = None):
        self.max_retries = max_retries
        self.fallback = fallback
    
    async def execute(self, func: Callable, *args, **kwargs) -> Any:
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_error = e
                print(f"Attempt {attempt + 1} failed: {e}")
                await asyncio.sleep(2 ** attempt)  # 指数退避
        
        # 重试失败，使用 fallback
        if self.fallback:
            return await self.fallback(*args, **kwargs)
        
        raise last_error

# 使用示例
async def call_llm(query: str) -> str:
    # 主 LLM 调用
    ...

async def fallback_llm(query: str) -> str:
    # 备用 LLM 调用
    ...

executor = RetryWithFallback(
    max_retries=3,
    fallback=fallback_llm
)

result = await executor.execute(call_llm, "用户问题")
```

---

### 9.2 选答题

**Q4: 如何设计 Agent 的权限控制系统？**

**Q5: 如何实现 Agent 的多轮对话状态管理？**

---

## 10. 场景题与开放题

### 10.1 系统设计题

**题目 1: 设计一个智能客服 Agent**

要求:
- 支持多轮对话
- 能够调用外部工具（查询订单、退款等）
- 具备情感识别能力
- 支持人工接管

```
设计方案:

┌─────────────────────────────────────────────────────────────┐
│                    智能客服 Agent                            │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │ Intent   │  │ Dialog   │  │ Tool     │  │ Sentiment│   │
│  │ Classifier│  │ Manager  │  │ Executor │  │ Analyzer │   │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘   │
│       │             │             │             │          │
│       └─────────────┴─────────────┴─────────────┘          │
│                          │                                  │
│                   ┌──────▼──────┐                          │
│                   │  Response   │                          │
│                   │  Generator  │                          │
│                   └──────┬──────┘                          │
│                          │                                  │
│                   ┌──────▼──────┐                          │
│                   │  Human      │                          │
│                   │  Handoff    │                          │
│                   └─────────────┘                          │
└─────────────────────────────────────────────────────────────┘
```

---

**题目 2: 设计一个代码辅助 Agent**

要求:
- 能够理解自然语言需求
- 生成可执行的代码
- 自动运行并验证结果
- 支持迭代改进

---

### 10.2 开放题

**题目 1: 你如何评估一个 Agent 的好坏？**

考察点:
- 指标设计（准确率、F1、Human Eval）
- 自动化评估 vs 人工评估
- 场景化评估

**题目 2: LLM 有哪些局限性？如何在 Agent 中弥补？**

考察点:
- 幻觉问题
- 上下文限制
- 知识时效性
- 推理能力不足

---

## 11. 编程题（在线编码）

### 11.1 简单题

**题目 1: 反转链表**

```python
def reverse_list(head):
    prev = None
    current = head
    while current:
        next_node = current.next
        current.next = prev
        prev = current
        current = next_node
    return prev
```

---

**题目 2: 判断括号是否有效**

```python
def is_valid_parentheses(s: str) -> bool:
    stack = []
    mapping = {')': '(', '}': '{', ']': '['}
    
    for char in s:
        if char in mapping:
            top = stack.pop() if stack else '#'
            if mapping[char] != top:
                return False
        else:
            stack.append(char)
    
    return not stack
```

---

### 11.2 中等题

**题目 3: 实现一个简单的 JSON Path 解析器**

```python
import json

def json_path_query(data: dict, path: str):
    """
    示例: json_path_query({"a": {"b": 1}}, "a.b") -> 1
    """
    keys = path.split('.')
    current = data
    
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        elif isinstance(current, list):
            try:
                index = int(key)
                current = current[index]
            except (ValueError, IndexError):
                return None
        else:
            return None
    
    return current
```

---

**题目 4: 实现 LRU Cache（不使用 OrderedDict）**

```python
class DLinkedList:
    def __init__(self, key=None, val=None):
        self.key = key
        self.val = val
        self.prev = None
        self.next = None

class LRUCache:
    def __init__(self, capacity: int):
        self.capacity = capacity
        self.cache = {}
        self.head = DLinkedList()  # 伪头
        self.tail = DLinkedList()  # 伪尾
        self.head.next = self.tail
        self.tail.prev = self.head
    
    def _add_to_head(self, node):
        node.prev = self.head
        node.next = self.head.next
        self.head.next.prev = node
        self.head.next = node
    
    def _remove_node(self, node):
        node.prev.next = node.next
        node.next.prev = node.prev
    
    def _move_to_head(self, node):
        self._remove_node(node)
        self._add_to_head(node)
    
    def _pop_tail(self):
        node = self.tail.prev
        self._remove_node(node)
        return node
    
    def get(self, key: int) -> int:
        if key in self.cache:
            node = self.cache[key]
            self._move_to_head(node)
            return node.val
        return -1
    
    def put(self, key: int, value: int) -> None:
        if key in self.cache:
            node = self.cache[key]
            node.val = value
            self._move_to_head(node)
        else:
            node = DLinkedList(key, value)
            self.cache[key] = node
            self._add_to_head(node)
            if len(self.cache) > self.capacity:
                tail = self._pop_tail()
                del self.cache[tail.key]
```

---

**题目 5: 实现一个简单的 Rate Limiter**

```python
import time
from collections import defaultdict

class RateLimiter:
    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = defaultdict(list)
    
    def allow_request(self, client_id: str) -> bool:
        now = time.time()
        # 清除过期记录
        self.requests[client_id] = [
            t for t in self.requests[client_id]
            if now - t < self.window_seconds
        ]
        
        if len(self.requests[client_id]) < self.max_requests:
            self.requests[client_id].append(now)
            return True
        return False
```

---

## 评分标准

| 维度 | 权重 | 说明 |
|------|------|------|
| 基础知识 | 30% | Python、数据结构、网络、操作系统 |
| 算法能力 | 25% | 代码实现、复杂度分析 |
| 系统设计 | 25% | 架构设计、权衡分析 |
| LLM/Agent | 20% | Transformer、RAG、Agent 设计 |

---

## 参考答案汇总

> 完整参考答案见：`docs/interview_answers/`

| 题目编号 | 题目名称 | 难度 | 预计时长 |
|---------|---------|------|---------|
| 1.1-Q1 | GIL | ⭐ | 5min |
| 1.1-Q2 | 装饰器 | ⭐⭐ | 10min |
| 2.1-Q1 | LRU Cache | ⭐⭐ | 15min |
| 2.1-Q2 | Trie | ⭐⭐ | 15min |
| 2.1-Q3 | 最长无重复子串 | ⭐⭐ | 10min |
| 6.1-Q1 | Transformer | ⭐⭐⭐ | 15min |
| 6.1-Q2 | 微调方法对比 | ⭐⭐ | 10min |
| 7.1-Q1 | ReAct Agent | ⭐⭐⭐ | 20min |
| 8.1-Q1 | RAG 流程 | ⭐⭐ | 10min |
| 9.1-Q1 | 高可用架构 | ⭐⭐⭐ | 20min |

---

**祝面试顺利！** 🎉
