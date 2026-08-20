# Agent 开发工程师 - 一面面试题（Java/Go 版）

> 版本: v1.0  
> 时长: 45-60 分钟  
> 形式: 技术基础 + 算法编码 + 项目追问

---

## ⏱️ 时间分配

| 环节 | 时长 | 内容 |
|------|------|------|
| 自我介绍 | 3min | 候选人简述背景 |
| Java/Go 基础 | 10min | 2-3 道题 |
| 算法编码 | 20min | 1-2 道 LeetCode 中等题 |
| LLM/Agent 基础 | 10min | 2 道概念题 |
| 项目追问 | 10min | 深挖简历项目 |
| Q&A | 5min | 候选人提问 |

---

## 📋 第一部分：Java/Go 基础（10min）

### Q1: Java/GC 与内存管理（3min）

**问法**: "请解释 Java 的内存模型和 GC 机制"

**期望回答**:
- **内存模型**: 堆（Heap）、栈（Stack）、方法区、程序计数器、本地方法栈
- **GC 算法**: 标记-清除、复制、标记-整理
- **GC 收集器**: Serial、Parallel、CMS、G1、ZGC
- **对象生命周期**: Eden → Survivor → Old Gen

**追问**:
- "G1 GC 和其他收集器的区别？" → 分区管理，可预测停顿时间
- "如何判断对象可以被回收？" → 引用计数 + 可达性分析

---

### Q2: Go Goroutine 与 Channel（5min）

**问法**: "Go 的 Goroutine 和 Channel 是什么？如何实现并发控制？"

**期望回答**:
- **Goroutine**: 轻量级线程，由 Go 运行时调度（M:N 模型）
- **Channel**: 类型安全的消息队列，实现"不要通过共享内存来通信，而要通过通信来共享内存"
- **并发控制**: Mutex、RWMutex、sync.WaitGroup、context

```go
// 示例：带缓冲 Channel
func worker(id int, jobs <-chan int, results chan<- int) {
    for j := range jobs {
        results <- j * 2
    }
}

func main() {
    jobs := make(chan int, 100)
    results := make(chan int, 100)
    
    for w := 1; w <= 3; w++ {
        go worker(w, jobs, results)
    }
    
    close(jobs)
    close(results)
}
```

**加分项**:
- 提到 select 语句处理多 Channel
- 提到 context 超时控制

---

### Q3: 接口与多态（2min）

**问法（Java）**: "Java 的接口和抽象类有什么区别？"

**期望回答**:
| 特性 | 接口 | 抽象类 |
|------|------|--------|
| 方法实现 | Java 8 前不能 | 可以有 |
| 变量 | 只能是常量 | 可以是任意类型 |
| 继承 | 多继承 | 单继承 |
| 构造器 | 无 | 有 |

**问法（Go）**: "Go 的接口是什么？如何实现鸭子类型？"

```go
// Go 接口实现（隐式实现）
type Writer interface {
    Write([]byte) (int, error)
}

// 不需要声明 implements，只要实现了方法就是该接口类型
type MyWriter struct{}

func (m MyWriter) Write(p []byte) (int, error) {
    return len(p), nil
}
```

---

## 🔢 第二部分：算法编码（20min）

### 题目 1：LRU Cache（必考，15min）

**LeetCode 146. LRU Cache**

#### Java 实现

```java
import java.util.HashMap;
import java.util.Map;

class LRUCache {
    private final int capacity;
    private final Map<Integer, Integer> cache;
    private final Deque<Integer> deque;  // 双向链表模拟
    
    public LRUCache(int capacity) {
        this.capacity = capacity;
        this.cache = new HashMap<>();
        this.deque = new LinkedList<>();
    }
    
    public int get(int key) {
        if (!cache.containsKey(key)) {
            return -1;
        }
        // 移到最新使用
        deque.remove((Integer) key);
        deque.addFirst(key);
        return cache.get(key);
    }
    
    public void put(int key, int value) {
        if (cache.containsKey(key)) {
            deque.remove((Integer) key);
        } else if (cache.size() >= capacity) {
            // 删除最久未使用
            int last = deque.removeLast();
            cache.remove(last);
        }
        deque.addFirst(key);
        cache.put(key, value);
    }
}
```

**进阶版（使用 LinkedHashMap）**:
```java
class LRUCache extends LinkedHashMap<Integer, Integer> {
    private final int capacity;
    
    public LRUCache(int capacity) {
        super(capacity, 0.75f, true);
        this.capacity = capacity;
    }
    
    @Override
    protected boolean removeEldestEntry(Map.Entry<Integer, Integer> eldest) {
        return size() > capacity;
    }
}
```

---

#### Go 实现

```go
type Node struct {
    Key   int
    Value int
    Prev  *Node
    Next  *Node
}

type DoublyLinkedList struct {
    Head *Node
    Tail *Node
    Size int
}

func (dll *DoublyLinkedList) AddToFront(node *Node) {
    node.Prev = nil
    node.Next = dll.Head
    if dll.Head != nil {
        dll.Head.Prev = node
    }
    dll.Head = node
    if dll.Tail == nil {
        dll.Tail = node
    }
    dll.Size++
}

func (dll *DoublyLinkedList) Remove(node *Node) {
    if node.Prev != nil {
        node.Prev.Next = node.Next
    } else {
        dll.Head = node.Next
    }
    if node.Next != nil {
        node.Next.Prev = node.Prev
    } else {
        dll.Tail = node.Prev
    }
    node.Prev = nil
    node.Next = nil
    dll.Size--
}

type LRUCache struct {
    capacity int
    cache    map[int]*Node
    list     *DoublyLinkedList
}

func Constructor(capacity int) LRUCache {
    return LRUCache{
        capacity: capacity,
        cache:    make(map[int]*Node),
        list:     &DoublyLinkedList{},
    }
}

func (this *LRUCache) Get(key int) int {
    if node, ok := this.cache[key]; ok {
        this.list.Remove(node)
        this.list.AddToFront(node)
        return node.Value
    }
    return -1
}

func (this *LRUCache) Put(key int, value int) {
    if node, ok := this.cache[key]; ok {
        node.Value = value
        this.list.Remove(node)
        this.list.AddToFront(node)
    } else {
        newNode := &Node{Key: key, Value: value}
        this.cache[key] = newNode
        this.list.AddToFront(newNode)
        if this.list.Size > this.capacity {
            tail := this.list.Tail
            this.list.Remove(tail)
            delete(this.cache, tail.Key)
        }
    }
}
```

---

### 题目 2（备选）：二叉树层序遍历（10min）

#### Java 实现

```java
import java.util.*;

class TreeNode {
    int val;
    TreeNode left;
    TreeNode right;
    TreeNode(int x) { val = x; }
}

public List<List<Integer>> levelOrder(TreeNode root) {
    List<List<Integer>> result = new ArrayList<>();
    if (root == null) return result;
    
    Queue<TreeNode> queue = new LinkedList<>();
    queue.offer(root);
    
    while (!queue.isEmpty()) {
        int levelSize = queue.size();
        List<Integer> currentLevel = new ArrayList<>();
        
        for (int i = 0; i < levelSize; i++) {
            TreeNode node = queue.poll();
            currentLevel.add(node.val);
            if (node.left != null) queue.offer(node.left);
            if (node.right != null) queue.offer(node.right);
        }
        result.add(currentLevel);
    }
    return result;
}
```

#### Go 实现

```go
type TreeNode struct {
    Val   int
    Left  *TreeNode
    Right *TreeNode
}

func levelOrder(root *TreeNode) [][]int {
    var result [][]int
    if root == nil {
        return result
    }
    
    queue := []*TreeNode{root}
    
    for len(queue) > 0 {
        levelSize := len(queue)
        currentLevel := []int{}
        
        for i := 0; i < levelSize; i++ {
            node := queue[0]
            queue = queue[1:]
            currentLevel = append(currentLevel, node.Val)
            
            if node.Left != nil {
                queue = append(queue, node.Left)
            }
            if node.Right != nil {
                queue = append(queue, node.Right)
            }
        }
        result = append(result, currentLevel)
    }
    return result
}
```

---

## 🤖 第三部分：LLM/Agent 基础（10min）

### Q1: Attention 机制（5min）

**问法**: "请用公式或代码解释 Transformer 的 Attention 机制"

**期望回答（伪代码）**:
```java
// Java 伪代码
public float[][] attention(Q, K, V) {
    // Q, K, V: [batch, seq_len, d_k]
    float scores = matmul(Q, transpose(K)) / sqrt(d_k);
    float attn = softmax(scores, dim=-1);
    return matmul(attn, V);
}
```

**核心要点**:
- 公式: `Attention(Q, K, V) = softmax(QK^T / √d_k) V`
- Q: Query（我要查什么）
- K: Key（我有什么）
- V: Value（我能给出什么）
- 除以 √d_k: 防止点积过大导致 softmax 饱和

---

### Q2: RAG 流程（5min）

**问法**: "请描述 RAG 系统的完整流程"

**期望回答**:

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   文档库     │────▶│  索引构建    │────▶│  检索增强    │────▶│   生成回答   │
│  (Documents)│     │ (Embedding) │     │  (Retriever)│     │  (Generator)│
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
```

**四个步骤**:
1. **文档分割** (Chunking): 按段落/句子切分，大小 200-1000 tokens
2. **向量化** (Embedding): 使用 embedding 模型转为向量
3. **检索** (Retrieval): 向量相似度搜索（余弦相似度）
4. **生成** (Generation): LLM 基于检索结果生成答案

**加分项**:
- 提到向量数据库选型（Milvus/FAISS/Pinecone）
- 提到重排序（Rerank）提升精度
- 提到混合检索（关键词 + 向量）

---

## 💼 第四部分：项目追问（10min）

**引导话术**:
> "请简单介绍一下你做过的最复杂的一个项目"

**追问方向**:

| 方向 | 问题 |
|------|------|
| **技术选型** | "为什么选 Java/Go？有没有考虑其他语言？" |
| **并发设计** | "如何处理并发请求？用了什么并发原语？" |
| **性能优化** | "系统瓶颈在哪里？怎么优化的？" |
| **Agent 架构** | "ReAct 循环怎么实现的？工具调用怎么处理？" |
| **生产问题** | "遇到过什么线上问题？怎么排查的？" |

---

## 📝 评分表

| 维度 | 权重 | 得分 (1-5) | 备注 |
|------|------|-----------|------|
| Java/Go 基础 | 20% | | GC、并发、接口 |
| 算法能力 | 35% | | LRU Cache、代码规范 |
| LLM/Agent 知识 | 25% | | Attention、RAG |
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

## 🎯 高频考点速查

### Java 高频考点
| 考点 | 关键词 |
|------|--------|
| JVM | 内存模型、GC 算法、类加载 |
| 并发 | ConcurrentHashMap、线程池、锁 |
| 接口 | 函数式接口、默认方法、静态方法 |
| Stream | 流式处理、并行流 |

### Go 高频考点
| 考点 | 关键词 |
|------|--------|
| 并发 | Goroutine、Channel、Mutex、WaitGroup |
| 接口 | 鸭子类型、空接口、类型断言 |
| 错误处理 | error、panic/recover、自定义 error |
| 内存 | 逃逸分析、GC、arena 分配 |

### 算法高频考点
| 考点 | 题目 |
|------|------|
| LRU/LFU | LeetCode 146/460 |
| 链表 | 反转链表、合并排序链表 |
| 树 | 层序遍历、BST 搜索 |
| 字符串 | 最长无重复子串、回文子串 |
| 滑动窗口 | 最小覆盖子串 |

### LLM/Agent 高频考点
| 考点 | 关键词 |
|------|--------|
| Transformer | Attention、Self-Attention、位置编码 |
| 微调 | Fine-tuning、LoRA、Prompt Tuning |
| RAG | Embedding、向量数据库、重排序 |
| Agent | ReAct、Function Calling、Memory |

---

## 💡 面试官技巧

### 好的提问方式
- ✅ "请解释一下..." → 考察理解深度
- ✅ "如果...你会怎么做？" → 场景题
- ✅ "你觉得这个方案的优缺点是什么？" → 权衡分析

### 避免的提问
- ❌ "请背诵..." → 死记硬背
- ❌ 过于细节的 API → 可查阅资料
- ❌ 超过候选人经验范围的题 → 打击信心

### 鼓励技巧
- 候选人卡住时："你可以先说说思路"
- 部分正确时："这个方向是对的，继续想想"
- 完全不会时："这道题有点难，我们换个问题"

---

**祝面试顺利！** 🎉
