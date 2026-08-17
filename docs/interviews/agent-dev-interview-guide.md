# Agent 开发工程师 - 一面面试指南

> 版本: v1.0  
> 时长: 45-60 分钟  
> 形式: 技术基础 + 算法编码 + 项目追问

---

## ⏱️ 时间分配建议

| 环节 | 时长 | 内容 |
|------|------|------|
| 自我介绍 | 3min | 候选人简述背景 |
| Python 基础 | 10min | 2-3 道题 |
| 算法编码 | 20min | 1-2 道 LeetCode 中等题 |
| LLM/Agent 基础 | 10min | 2 道概念题 |
| 项目追问 | 10min | 深挖简历项目 |
| Q&A | 5min | 候选人提问 |

---

## 📋 第一部分：Python 基础（10min）

### Q1: 请解释 GIL（3min）

**问法**: "Python 中的 GIL 是什么？它对多线程有什么影响？"

**期望回答**:
- GIL 是全局解释器锁，同一时刻只允许一个线程执行 Python 字节码
- 影响：CPU 密集型任务多线程无法真正并行
- 解决方案：多进程、C 扩展释放 GIL

**追问**（如果时间够）:
- "那 IO 密集型任务受影响吗？" → 回答：IO 密集型影响较小，因为等待 IO 时会释放 GIL

---

### Q2: 装饰器实现（5min）

**问法**: "请手写一个计时装饰器"

```python
import functools
import time

def timer(func):
    @functools.wraps(func)          # 保留原函数信息
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        end = time.time()
        print(f"{func.__name__} 耗时: {end - start:.4f}s")
        return result
    return wrapper

@timer
def sleep_one():
    time.sleep(1)
```

**评分标准**:
- ✅ 完整实现（加分项）
- ✅ 使用 `*args, **kwargs` 通用传参
- ✅ 使用 `functools.wraps` 保留元信息
- ⚠️ 缺少 `functools.wraps`（扣 1 分）

---

### Q3: Generator 与 List 区别（2min）

**问法**: "Generator 和 List 有什么区别？什么时候用 Generator？"

**期望回答**:
- 惰性求值，节省内存
- 支持无限序列
- 大数据处理、迭代器协议

---

## 🔢 第二部分：算法编码（20min）

### 题目 1：LRU Cache（必考，15min）

**LeetCode 146. LRU Cache**

**题目描述**:
设计并实现一个满足 LRU (最近最少使用) 缓存约束的数据结构。

**要求**:
- `get(key)`: 如果关键字存在于缓存中，则获取关键字的值，否则返回 -1
- `put(key, value)`: 如果关键字已经存在，则变更其数据值；如果关键字不存在，则插入该组「关键字/值」。当缓存容量达到上限时，它应该在写入新数据之前删除最久未使用的数据值

**代码模板**:
```python
from collections import OrderedDict

class LRUCache:
    def __init__(self, capacity: int):
        self.capacity = capacity
        self.cache = OrderedDict()
    
    def get(self, key: int) -> int:
        if key not in self.cache:
            return -1
        self.cache.move_to_end(key)
        return self.cache[key]
    
    def put(self, key: int, value: int) -> None:
        if key in self.cache:
            self.cache.move_to_end(key)
        self.cache[key] = value
        if len(self.cache) > self.capacity:
            self.cache.popitem(last=False)
```

**考察点**:
- 能否想到用 OrderedDict（O(1) 操作）
- 边界条件处理（key 已存在、容量满）
- 复杂度分析（O(1) 时间，O(n) 空间）

**追问**:
- "不用 OrderedDict 如何实现？" → 双向链表 + 哈希表
- "时间复杂度是多少？" → O(1)

---

### 题目 2（备选）：最长无重复子串（10-15min）

**LeetCode 3. Longest Substring Without Repeating Characters**

```python
def length_of_longest_substring(s: str) -> int:
    char_index = {}
    max_length = 0
    start = 0
    
    for end, char in enumerate(s):
        if char in char_index and char_index[char] >= start:
            start = char_index[char] + 1
        char_index[char] = end
        max_length = max(max_length, end - start + 1)
    
    return max_length
```

---

## 🤖 第三部分：LLM/Agent 基础（10min）

### Q1: Attention 机制（5min）

**问法**: "请用公式或文字解释 Transformer 的 Attention 机制"

**期望回答**:
- 公式: `Attention(Q, K, V) = softmax(QK^T / √d_k) V`
- Q: Query（查询），K: Key（键），V: Value（值）
- 核心思想：计算 Query 与所有 Key 的相似度，加权求和 Value

**追问**:
- "为什么要除以 √d_k？" → 防止点积过大导致 softmax 梯度消失
- "多头注意力的作用？" → 捕捉不同子空间的信息

---

### Q2: RAG 流程（5min）

**问法**: "请描述 RAG 系统的完整流程"

**期望回答**（至少 4 个步骤）:
1. 文档分割（Chunking）
2. 向量化（Embedding）
3. 检索（Retrieval）
4. 生成（Generation）

**加分项**:
- 提到 Chunk Size 的选择（200-1000 tokens）
- 提到向量数据库（Milvus/FAISS/Pinecone）
- 提到重排序（Rerank）

---

## 💼 第四部分：项目追问（10min）

**引导话术**:
> "请简单介绍一下你做过的最复杂的一个项目"

**追问方向**（任选 2-3 个）:

1. **技术选型**
   - "为什么选这个技术栈？"
   - "有没有考虑过其他方案？"

2. **难点攻克**
   - "遇到了什么最大挑战？"
   - "怎么解决的？"

3. **性能优化**
   - "系统瓶颈在哪里？"
   - "怎么优化的？"

4. **Agent 相关**
   - "用了什么框架？LangChain/自研？"
   - "怎么处理工具的？"
   - "有没有遇到过幻觉问题？"

---

## 📝 评分表

| 维度 | 权重 | 得分 (1-5) | 备注 |
|------|------|-----------|------|
| Python 基础 | 20% | | GIL、装饰器、Generator |
| 算法能力 | 35% | | LRU Cache、代码规范、复杂度分析 |
| LLM/Agent 知识 | 25% | | Attention、RAG 流程 |
| 项目深度 | 20% | | 技术选型、难点解决 |

**总分**: ___/20

### 录用建议

| 总分 | 建议 |
|------|------|
| 16-20 | ✅ 强烈推荐二面 |
| 12-15 | ✅ 推荐二面 |
| 8-11 | ⚠️ 谨慎考虑 |
| <8 | ❌ 不推荐 |

---

## 🎯 常见问题速查

### Python 高频考点
| 考点 | 关键词 |
|------|--------|
| GIL | 全局解释器锁、多线程、CPU 密集型 |
| 装饰器 | @wrapper、*args、**kwargs、functools.wraps |
| Generator | yield、惰性求值、内存优化 |
| 上下文管理器 | with、__enter__、__exit__ |
| 深浅拷贝 | copy、deepcopy、内存共享 |

### 算法高频考点
| 考点 | 题目 |
|------|------|
| LRU/LFU | LeetCode 146/460 |
| 链表操作 | 反转链表、合并排序链表 |
| 树遍历 | 层序遍历、前中后序 |
| 字符串 | 最长无重复子串、回文子串 |
| 滑动窗口 | 最小覆盖子串 |

### LLM/Agent 高频考点
| 考点 | 关键词 |
|------|--------|
| Transformer | Attention、Self-Attention、多头注意力 |
| 微调方法 | Fine-tuning、LoRA、Prompt Tuning |
| RAG | Embedding、向量数据库、重排序 |
| Agent 架构 | ReAct、Function Calling、Memory |

---

## 💡 面试官技巧

### 好的提问方式
- ✅ "请解释一下..." → 开放性问题
- ✅ "如果...你会怎么做？" → 场景题
- ✅ "你觉得这个方案的优缺点是什么？" → 权衡分析

### 避免的提问
- ❌ "请背诵..." → 死记硬背
- ❌ 过于细节的 API | → 可查阅资料
- ❌ 超过候选人经验范围的题 | → 打击信心

### 鼓励技巧
- 候选人卡住时："你可以先说说思路"
- 部分正确时："这个方向是对的，继续想想"
- 完全不会时："这道题有点难，我们换个问题"

---

**祝面试顺利！** 🎉
