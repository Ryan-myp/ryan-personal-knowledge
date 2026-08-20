# Agent 开发工程师 - 校招一面面试题库（含答案）

> 版本: v6.0  
> 时长: 60 分钟/人  
> 题库规模: 15 道核心题 + 详细答案  
> 适用: 研究生/有经验的校招候选人

---

## ⏱️ 面试流程

| 环节 | 时长 | 内容 |
|------|------|------|
| 破冰 + 项目介绍 | 5min | 了解背景，建立信任 |
| **基础问答题** | 15min | 抽取 3-4 题 |
| **场景分析题** | 15min | 抽取 2-3 题 |
| **Agent 认知题** | 10min | 抽取 2-3 题 |
| **开放设计题** | 10min | 抽取 1 题 |
| 反问 | 5min | 了解候选人关注点 |

---

## 一、基础问答题库（10 题）

### Java 方向

---

**Q1: 请详细解释 JVM 内存模型各区域的作用，以及对象在内存中的布局。**

**考察点**: JVM 底层原理，适合研究生水平

**参考答案**:

**内存区域**:
| 区域 | 作用 | 线程共享 |
|------|------|---------|
| 堆（Heap） | 存放对象实例和数组，GC 主要区域 | 是 |
| 栈（Stack） | 存放局部变量表、操作数栈、方法出口 | 否 |
| 方法区（Method Area） | 存放类信息、常量、静态变量、即时编译器编译后的代码 | 是 |
| 程序计数器 | 记录当前线程执行的字节码行号 | 否 |
| 本地方法栈 | Native 方法服务 | 否 |

**对象内存布局（JVM 规范）**:
```
┌─────────────────────────────────────┐
│           Object Header             │
│  ┌─────────────┬──────────────────┐ │
│  │ Mark Word   │ Type Pointer     │ │
│  │ (64bit)     │ (32/64bit)       │ │
│  └─────────────┴──────────────────┘ │
├─────────────────────────────────────┤
│           Instance Data             │
│         (对象真正有效的数据)          │
├─────────────────────────────────────┤
│           Padding                   │
│      (8 字节对齐填充)                │
└─────────────────────────────────────┘
```

**Mark Word 内容**:
- 对象哈希码（25bit）
- 对象分代年龄（4bit）
- 锁状态标志（1bit）
- 线程持有锁的 ID（23bit）
- 偏向线程 ID（54bit，无锁时）

**追问**:
- "大对象会直接分配到老年代吗？" → 不一定，取决于 CMS/G1 策略
- "如何判断对象是否存活？" → 可达性分析（GC Roots）

**评分标准**:
- 5 分: 能画出完整布局，说出 Mark Word 各字段含义
- 4 分: 知道各区域作用，对象布局基本正确
- 3 分: 知道堆/栈区别，但不清楚细节
- 2 分: 只说"堆存对象，栈存局部变量"
- 1 分: 不清楚

---

**Q2: HashMap 在 JDK 7 和 JDK 8 的区别是什么？并发环境下如何使用？**

**考察点**: 数据结构演进、并发安全

**参考答案**:

**JDK 7 vs JDK 8 核心区别**:

| 特性 | JDK 7 | JDK 8 |
|------|-------|-------|
| 数据结构 | 数组 + 链表 | 数组 + 链表 + 红黑树 |
| 哈希冲突 | 头插法 | 尾插法 |
| 扩容 | 一次扩容一个桶 | 按桶位置迁移（rehash） |
| 查找性能 | O(n) | O(log n)（树化后） |

**JDK 8 树化条件**:
```java
// HashMap.java
static final int TREEIFY_THRESHOLD = 8;  // 链表长度 ≥ 8 时考虑树化
static final int UNTREEIFY_THRESHOLD = 6; // 树节点 ≤ 6 时退化链表
static final int MIN_TREEIFY_CAPACITY = 64; // 数组容量 ≥ 64 才树化
```

**并发问题**:
- HashMap 在并发扩容时可能产生**环状链表**（JDK 7 头插法导致）
- JDK 8 尾插法避免了环，但仍有**数据丢失**风险

**并发环境推荐方案**:
```java
// 方案 1: ConcurrentHashMap（推荐）
ConcurrentHashMap<String, Integer> map = new ConcurrentHashMap<>();

// 方案 2: Collections.synchronizedMap
Map<String, Integer> syncMap = Collections.synchronizedMap(new HashMap<>());

// 方案 3: HashMap + 外部同步
synchronized(map) {
    map.put(key, value);
}
```

**ConcurrentHashMap 实现（JDK 8）**:
- 取消 Segment，改用 Node + CAS + synchronized
- 锁粒度更细：只对桶头节点加锁
- get 操作无锁（volatile 读）

**追问**:
- "ConcurrentHashMap 的 size() 方法为什么不能精确？" → 统计时可能有并发修改
- "为什么不用 Hashtable？" → 全局锁，性能差

**评分标准**:
- 5 分: 清楚 JDK 7/8 区别，能解释树化条件，知道 ConcurrentHashMap 实现
- 4 分: 知道主要区别，了解并发问题
- 3 分: 知道 HashMap 线程不安全，但说不清原因
- 2 分: 只知道"用 ConcurrentHashMap"
- 1 分: 不清楚

---

**Q3: 线程池的核心参数有哪些？如何合理配置核心线程数？**

**考察点**: 并发编程实战能力

**参考答案**:

**ThreadPoolExecutor 构造参数**:
```java
public ThreadPoolExecutor(
    int corePoolSize,           // 核心线程数
    int maximumPoolSize,        // 最大线程数
    long keepAliveTime,         // 非核心线程空闲存活时间
    TimeUnit unit,              // 时间单位
    BlockingQueue<Runnable> workQueue,  // 任务队列
    ThreadFactory threadFactory,      // 线程工厂
    RejectedExecutionHandler handler  // 拒绝策略
)
```

**任务提交流程**:
```
提交任务
    ↓
corePoolSize < maximumPoolSize?
    ├── 是 → 创建新线程执行
    └── 否 → 加入 workQueue
              ↓
         workQueue 满?
              ├── 是 → maximumPoolSize 是否已满?
              │         ├── 是 → 执行拒绝策略
              │         └── 否 → 创建非核心线程
              └── 否 → 加入队列等待
```

**核心线程数配置**:
| 场景 | 公式 | 说明 |
|------|------|------|
| CPU 密集型 | N + 1 | N 为 CPU 核数，+1 防止页缺失 |
| IO 密集型 | N × (1 + W/C) | W 等待时间，C 计算时间 |
| 混合密集型 | 分解计算 | 分别估算再合并 |

**实际经验**:
- 监控线程池状态：活跃线程数、队列深度、拒绝次数
- 设置合理的队列容量（避免 OOM）
- 自定义异常处理，不要静默丢弃任务

**拒绝策略**:
| 策略 | 行为 | 适用场景 |
|------|------|---------|
| AbortPolicy | 抛出 RejectedExecutionException | 默认，强调不丢失任务 |
| CallerRunsPolicy | 调用方线程执行 | 平滑降级 |
| DiscardPolicy | 静默丢弃 | 允许丢失非关键任务 |
| DiscardOldestPolicy | 丢弃最老任务 | 保证最新任务 |

**追问**:
- "如何动态调整线程池参数？" → 反射或封装动态线程池
- "线程池溢出怎么排查？" → 监控 + 日志 + 分析任务类型

**评分标准**:
- 5 分: 清楚任务提交流程，能推导线程数公式，知道拒绝策略选择
- 4 分: 知道参数含义，能给出配置建议
- 3 分: 知道核心参数，但说不清流程
- 2 分: 只记得几个参数名
- 1 分: 不了解

---

**Q4: volatile 关键字的作用是什么？它与 synchronized 的区别？**

**考察点**: 并发基础深度理解

**参考答案**:

**volatile 三大特性**:
1. **可见性**: 一个线程修改后，其他线程立即看到
2. **禁止指令重排**: 通过内存屏障实现
3. **不保证原子性**: read-modify-write 不是原子的

**内存屏障（Memory Barrier）**:
```
LoadLoad 屏障：确保 Load1 数据在所有 Load2 之前加载
StoreStore 屏障：确保 Store1 数据在所有 Store2 之前刷新
LoadStore 屏障：确保 Load1 数据在所有 Store2 之前加载
StoreLoad 屏障：确保 Store1 数据在所有 Load2 之前刷新（最贵）
```

**volatile vs synchronized**:
| 特性 | volatile | synchronized |
|------|----------|--------------|
| 可见性 | ✅ | ✅ |
| 原子性 | ❌ | ✅ |
| 有序性 | ✅ | ✅ |
| 性能 | 高（无锁） | 较低（有锁） |
| 适用场景 | 状态标志、双重检查锁定 | 复杂临界区 |

**volatile 经典用法**:
```java
// 1. 状态标志
volatile boolean running = true;
while (running) { /* 工作 */ }

// 2. 双重检查锁定（DCL）
class Singleton {
    private static volatile Singleton instance;
    public static Singleton getInstance() {
        if (instance == null) {
            synchronized (Singleton.class) {
                if (instance == null) {
                    instance = new Singleton();
                }
            }
        }
        return instance;
    }
}

// 3. 发布安全（Publication Safety）
class Publisher {
    private int x = 0;
    private volatile boolean ready = false;
    
    public void publish() {
        x = 42;           // 1. 写数据
        ready = true;     // 2. 发布（volatile 写）
    }
}
```

**追问**:
- "为什么 DCL 需要 volatile？" → 防止指令重排导致其他线程拿到未初始化对象
- "volatile 能替代 CAS 吗？" → 不能，CAS 保证原子性

**评分标准**:
- 5 分: 清楚三大特性，能解释内存屏障，给出经典用法
- 4 分: 知道可见性和有序性，但说不清原子性问题
- 3 分: 知道 volatile 保证可见性
- 2 分: 只说"多线程共享变量"
- 1 分: 不清楚

---

### Go 方向

---

**Q5: 请解释 Go 的 GMP 调度模型，以及它相比 M:N 模型的优势。**

**考察点**: Go 运行时深度理解

**参考答案**:

**GMP 模型组成**:
| 组件 | 含义 | 数量 |
|------|------|------|
| G (Goroutine) | 协程，包含栈、状态、PC | 无限 |
| M (Machine) | OS 线程，执行 G 的代码 | ~CPU 核数 |
| P (Processor) | 逻辑处理器，维护 runnable G 队列 | GOMAXPROCS |

**调度流程**:
```
G → [runnable] → P 的本地队列 → [sched] → M 执行
                    ↑                       ↓
              stolen from others ← [global queue]
```

**关键机制**:
1. **Work Stealing**: P 的空闲时从其他 P 偷一半 G
2. **Syscall**: G 阻塞时，M 放弃 P，创建新 M 执行
3. **Preemption**: 10ms 定时器强制抢占（Go 1.14+）

**相比 M:N 模型的优势**:
| 问题 | M:N 模型 | GMP 模型 |
|------|---------|---------|
| 死锁检测 | 复杂 | 自动避免 |
| 优先级反转 | 可能发生 | 有优先级队列 |
| 星形饥饿 | 可能 | Work Stealing 缓解 |
| Syscall 阻塞 | 所有 G 阻塞 | 仅当前 M 阻塞 |

**追问题**:
- "GOMAXPROCS 默认值是多少？" → Go 1.5+ 默认等于 CPU 核数
- "goroutine 栈大小是多少？" → 初始 2KB，动态伸缩（最大 1GB）

**评分标准**:
- 5 分: 清楚 GMP 交互，能解释 Work Stealing 和 Syscall 处理
- 4 分: 知道基本概念，能画出大致流程
- 3 分: 知道 G/M/P 分别代表什么
- 2 分: 听说过但不清楚
- 1 分: 不知道

---

**Q6: Channel 的实现原理是什么？select 语句的工作机制？**

**考察点**: Go 并发核心机制

**参考答案**:

**Channel 数据结构**:
```go
type hchan struct {
    qcount   uint           // 队列中元素数量
    dataqsiz uint           // 环形队列大小
    buf      unsafe.Pointer // 环形队列缓冲区
    elemsize uint16
    closed   uint32         // 是否关闭
    elemtype *_type         // 元素类型
    sendx    uint           // 发送索引
    recvx    uint           // 接收索引
    recvq    waitq          // 等待接收的 G 队列
    sendq    waitq          // 等待发送的 G 队列
    
    lock mutex              // 互斥锁
}
```

**Channel 操作**:
```
send(c, elem):
    1. 检查 channel 是否关闭
    2. 如果有等待的 recv G，直接发送
    3. 否则将 elem 放入环形队列
    4. 如果队列满，等待 recv

recv(c):
    1. 检查 channel 是否关闭
    2. 如果有等待的 send G，直接接收
    3. 否则从环形队列取出元素
    4. 如果队列为空，等待 send
```

**select 语句原理**:
```go
select {
case msg := <-ch1:   // 等待 ch1 可读
    handle(msg)
case ch2 <- data:    // 等待 ch2 可写
    sendDone()
case <-time.After(1 * time.Second):
    timeout()
default:
    noReady()
}
```

**select 工作机制**:
1. 对每个 case 的 channel 进行随机排序（防饥饿）
2. 按顺序检查每个 case 是否就绪
3. 如果有多个就绪，随机选择一个执行
4. 如果都没有就绪，阻塞等待（有 default 则执行 default）
5. 超时时取消等待

**Channel 类型对比**:
| 类型 | 创建方式 | 特点 |
|------|---------|------|
| 无缓冲 | make(chan T) | 同步，需双方配合 |
| 有缓冲 | make(chan T, n) | 异步，容量 n |
| 单向 | chan<- T / <-chan T | 限制发送/接收方向 |

**追问题**:
- "close 一个已关闭的 channel 会怎样？" → panic
- "从已关闭的 channel 读取会怎样？" → 返回零值和 false

**评分标准**:
- 5 分: 清楚 Channel 内部结构，能解释 select 的随机选择机制
- 4 分: 知道 Channel 是环形队列，select 随机选
- 3 分: 知道有无缓冲的区别
- 2 分: 了解基本用法
- 1 分: 不清楚

---

**Q7: Go 的垃圾回收是如何工作的？与 Java GC 有什么区别？**

**考察点**: 运行时 GC 理解

**参考答案**:

**Go GC 算法**: 混合写屏障 + 三色标记 + 并发

**三色标记法**:
```
白色：尚未扫描
灰色：已扫描但子节点未扫描
黑色：已扫描且子节点已扫描
```

**扫描过程**:
```
1. STW 阶段：更新根集合（Root Set）
2. 并发标记：从根节点出发，标记可达对象
   - 白→灰：写屏障记录
   - 灰→黑：扫描对象字段
3. 并发清除：遍历堆内存，回收白色对象
```

**写屏障（Write Barrier）**:
```go
// 混合写屏障示例
func WriteBarrier(p *byte, newval *byte) {
    // 1. 记录旧值到白对象列表
    WhiteObjectList.Add(p)
    // 2. 写入新值
    *p = *newval
    // 3. 将新值对象标记为灰色
    MarkAsGray(newval)
}
```

**与 Java GC 对比**:
| 特性 | Go GC | Java GC (G1) |
|------|-------|-------------|
| 算法 | 三色标记 + 混合写屏障 | 增量标记 + 并发清理 |
| STW 时间 | < 1ms | 几 ms 到几十 ms |
| 并发度 | 高（标记、清除全并发） | 高（标记、清理并发） |
| 堆外内存 | 不追踪 | 不追踪 |
| 可预测性 | 较好 | 较好 |

**Go GC 调优**:
```bash
# 查看 GC 统计
go tool trace
go tool pprof

# 控制 GC 行为
GOGC=100          # GC 触发阈值（默认 100）
GOMEMSIZE=1gb     # 内存大小估计
GODEBUG=gctrace=1 # 打印 GC 日志
```

**追问题**:
- "为什么 Go 的 GC 停顿时间短？" → 写屏障 + 并发标记
- "GOGC=off 会怎样？" → 禁用 GC，内存持续增长

**评分标准**:
- 5 分: 清楚三色标记和写屏障，能对比 Java GC
- 4 分: 知道并发标记清除，了解 STW 短
- 3 分: 知道是 GC 回收内存，但不清楚算法
- 2 分: 只说"自动回收"
- 1 分: 不了解

---

### 通用基础

---

**Q8: TCP 三次握手为什么不能是两次？TIME_WAIT 状态的作用是什么？**

**考察点**: 网络协议深度理解

**参考答案**:

**三次握手过程**:
```
Client                          Server
  |--- SYN (seq=x, seq=0) ------->|
  |<-- SYN+ACK (seq=y, ack=x+1) --|
  |--- ACK (seq=x+1, ack=y+1) --->|
```

**为什么不能两次**:
1. **防止已失效的连接请求报文段突然传到服务端**
   - 如果只有两次握手，服务端收到 SYN 就认为连接建立
   - 但客户端可能已经超时重传，服务端不知道
2. **确保双方都能收发**
   - 第一次：客户端发送，服务端接收
   - 第二次：服务端发送，客户端接收
   - 第三次：客户端确认，服务端知道客户端收到了

**TIME_WAIT 状态（2MSL）**:
```
                        2MSL 计时
Client                      Server
  |--- FIN ----->|          |
  |<-- FIN+ACK ---|          |
  |--- ACK ----->|          | 关闭
  |              |--------->|
  |  TIME_WAIT  |           |
  |<------------|-----------|
        2MSL
```

**TIME_WAIT 作用**:
1. **确保最后一个 ACK 到达服务端**
   - 如果 ACK 丢失，服务端会重发 FIN
   - TIME_WAIT 让客户端能响应重发
2. **防止老连接的重复报文干扰新连接**
   - MSL（Maximum Segment Lifetime）：报文最大生存时间
   - 2MSL 确保旧连接的报文全部消失

**TIME_WAIT 过多怎么办**:
- 调整内核参数：`net.ipv4.tcp_tw_reuse=1`
- 使用 UDP 替代 TCP（如果业务允许）
- 增加端口数量

**追问题**:
- "CLOSE_WAIT 和 TIME_WAIT 的区别？" → CLOSE_WAIT 是对端主动关闭，本端还没关闭
- "QUIC 为什么用 UDP？" → 避免队头阻塞，减少握手延迟

**评分标准**:
- 5 分: 清楚三次握手必要性，能解释 TIME_WAIT 作用
- 4 分: 知道不能两次的原因，了解 TIME_WAIT
- 3 分: 知道三次握手过程
- 2 分: 只记得"三次握手"
- 1 分: 不清楚

---

**Q9: Redis 如何实现分布式锁？有什么注意事项？**

**考察点**: 分布式锁实战

**参考答案**:

**基本实现（SET NX PX）**:
```java
// Lua 脚本保证原子性
String script = 
    "if redis.call('get', KEYS[1]) == ARGV[1] then " +
    "return redis.call('del', KEYS[1]) else return 0 end";

// 获取锁
Boolean result = redisTemplate.opsForValue()
    .setIfAbsent(lockKey, uuid, 10, TimeUnit.SECONDS);

// 释放锁
Long result = redisTemplate.execute(
    new DefaultRedisScript<>(script, Long.class),
    Collections.singletonList(lockKey), uuid);
```

**关键点**:
| 要点 | 说明 |
|------|------|
| 原子性 | setIfAbsent + Lua 脚本释放 |
| 过期时间 | 防止死锁，但要注意业务执行时间 |
| UUID | 防止误删其他客户端的锁 |
| 看门狗 | Redisson 自动续期 |

**Redlock 算法（多节点）**:
```java
// 至少 N/2 + 1 个节点成功才算成功
long start = System.currentTimeMillis();
int successfullySet = 0;
for (RedisNode node : nodes) {
    if (node.setnx(lockKey, uuid, expireTime)) {
        successfullySet++;
    }
}
long elapsed = System.currentTimeMillis() - start;
if (successfullySet >= nodes.size() / 2 + 1 
    && elapsed < expireTime) {
    // 锁获取成功
}
```

**注意事项**:
1. **锁粒度要小**：只锁关键代码段
2. **业务执行时间 < 锁过期时间**：否则可能重复执行
3. **时钟漂移问题**：NTP 同步，或使用 Redlock
4. **网络分区**：分布式锁本身是 AP 系统

**追问题**:
- "Redis 主从切换会怎样？" → 可能丢失锁，需要 Redlock
- "ZooKeeper 做分布式锁有什么区别？" → CP 系统，强一致

**评分标准**:
- 5 分: 清楚 SET NX PX 原理，能解释 Redlock 和注意事项
- 4 分: 知道基本实现，了解原子性和过期时间
- 3 分: 知道用 Redis 做分布式锁
- 2 分: 只说"用 setnx"
- 1 分: 不了解

---

**Q10: Kafka 如何保证消息不丢失？如何保证消息顺序性？**

**考察点**: 消息队列可靠性

**参考答案**:

**消息不丢失三阶段**:

| 阶段 | 配置 | 说明 |
|------|------|------|
| Producer | acks=all | 所有副本写入才确认 |
| Broker | replicas=3 | 多副本存储 |
| Consumer | enable.auto.commit=false | 手动提交 |

**Producer 配置**:
```java
Properties props = new Properties();
props.put("acks", "all");                    // 全部副本确认
props.put("retries", Integer.MAX_VALUE);     // 无限重试
props.put("max.in.flight.requests.per.connection", 1); // 保证顺序
props.put("enable.idempotence", true);       // 幂等 Producer
```

**Broker 配置**:
```properties
# 副本数
num.replicas=3
# ISR（In-Sync Replicas）机制
min.insync.replicas=2  // 至少 2 个副本存活才接受写入
```

**Consumer 配置**:
```java
props.put("enable.auto.commit", "false");  // 手动提交
props.put("auto.offset.reset", "latest");  // 从最新开始
```

**提交策略**:
| 策略 | 优点 | 缺点 |
|------|------|------|
| 每次消费提交 | 不丢消息 | 可能重复消费 |
| 批量提交 | 性能好 | 可能丢消息 |
| 事务提交 | 精确一次 | 复杂度高 |

**消息顺序性保证**:
```
关键：同一 key → 同一 Partition

Producer:
producer.send(new ProducerRecord<>("topic", 
    String.valueOf(userId),  // key 保证路由到同一 partition
    message));

Partition 分配:
partition = hash(key) % numPartitions
```

**追问题**:
- "Kafka 能精确一次吗？" → 支持事务，但复杂
- "消费 lag 怎么办？" → 扩容 Consumer Group

**评分标准**:
- 5 分: 清楚三阶段配置，能解释 ISR 和幂等 Producer
- 4 分: 知道 acks=all 和手动提交
- 3 分: 了解基本概念
- 2 分: 只说"多发几次"
- 1 分: 不了解

---

## 二、场景分析题库（5 题）

---

**场景 1: 电商大促抗压设计**

**背景**: 618 大促，流量预计增长 10 倍，老板要求系统不崩。

**问题**:
1. 如何评估当前系统瓶颈？
2. 如果数据库成为瓶颈，如何优化？
3. 如何保证下单流程的可靠性？

**参考答案**:

**1. 瓶颈评估**:
```
┌─────────────────────────────────────────────┐
│              监控系统                         │
├─────────────────────────────────────────────┤
│  Prometheus + Grafana                        │
│  ├── CPU/内存/磁盘/网络                        │
│  ├── QPS/RT/错误率                           │
│  └── JVM 指标（GC 频率、线程数）               │
└─────────────────────────────────────────────┘
              ↓
        定位瓶颈（APM: SkyWalking/Jaeger）
```

**2. 数据库优化**:
| 方案 | 适用场景 | 风险 |
|------|---------|------|
| 缓存预热 | 热点商品 | 数据不一致 |
| 读写分离 | 读多写少 | 延迟 |
| 分库分表 | 数据量大 | 复杂度 |
| 本地缓存 | 极低延迟 | 内存占用 |

```java
// 缓存策略
@Cacheable(value = "product", key = "#id")
public Product getProduct(long id) {
    return productDao.selectById(id);
}

// 缓存更新策略：Cache-Aside
Product product = cache.get(id);
if (product == null) {
    product = db.query(id);
    cache.put(id, product);
}
```

**3. 下单可靠性**:
```
订单流程:
用户请求 → 限流 → 库存扣减(Redis) → 创建订单(DB) → 消息队列 → 异步处理

关键设计:
- Redis 预扣库存（Lua 原子操作）
- 本地消息表 + 定时补偿
- 幂等性设计（唯一索引）
- 超时关单（消息队列延迟消息）
```

**加分项**:
- 提到"压测"（Locust/JMeter）
- 提到"灰度发布"
- 提到"熔断降级"（Sentinel/Hystrix）

---

**场景 2: 实时数据同步设计**

**背景**: MySQL → Elasticsearch，要求延迟 < 1 秒。

**问题**: 如何实现数据同步？如何保证一致性？

**参考答案**:

**方案对比**:
| 方案 | 延迟 | 复杂度 | 一致性 |
|------|------|--------|--------|
| 双写 | < 10ms | 低 | 弱 |
| Canal + Kafka | < 1s | 中 | 最终 |
| ES 查询 MySQL | 实时 | 低 | 强 |

**推荐方案：Canal + Kafka**
```
MySQL → Canal 监听 Binlog → Kafka → Consumer → ES
```

**Canal 配置**:
```properties
canal.instance.master.address=127.0.0.1:3306
canal.instance.dbUsername=canal
canal.instance.dbPassword=canal
canal.instance.connectionCharset=UTF-8
canal.instance.tsdb.enable=true
```

**一致性保证**:
1. **最终一致性**: 接受短暂不一致
2. **对账补偿**: 定时任务校验差异
3. **ES 重试机制**: 消费失败重试 + 死信队列

**追问题**:
- "Canal 挂了怎么办？" → 高可用部署 + 断点续传
- "如何避免重复同步？" → ES 幂等写入

---

**场景 3: 分布式 ID 生成**

**背景**: 需要全局唯一、趋势递增的 ID，支持分库分表。

**问题**: 选择哪种方案？如何解决时钟回拨？

**参考答案**:

**方案对比**:
| 方案 | 优点 | 缺点 |
|------|------|------|
| UUID | 简单、全局唯一 | 无序、索引性能差 |
| 数据库自增 | 简单 | 单点、性能瓶颈 |
| Snowflake | 高性能、分布式 | 时钟回拨问题 |
| Leaf（美团） | 号段模式 | 相对复杂 |

**Snowflake 改进版**:
```java
public class SnowflakeIdGenerator {
    private long workerId;
    private long datacenterId;
    private long sequence = 0L;
    private long lastTimestamp = -1L;
    
    private static final long START_TIMESTAMP = 1609459200000L; // 2021-01-01
    
    public synchronized long nextId() {
        long timestamp = timeGen();
        
        // 时钟回拨处理
        if (timestamp < lastTimestamp) {
            long offset = lastTimestamp - timestamp;
            if (offset <= 5) { // 允许小幅度回拨
                try {
                    wait(offset << 1);
                } catch (InterruptedException e) {
                    throw new RuntimeException(e);
                }
                timestamp = timeGen();
            } else {
                throw new RuntimeException("时钟回拨超过允许范围");
            }
        }
        
        if (timestamp == lastTimestamp) {
            sequence = (sequence + 1) & 4095; // 12位序列号
            if (sequence == 0) {
                timestamp = waitNextMillis(lastTimestamp);
            }
        } else {
            sequence = new Random().nextLong() & 4095;
        }
        
        lastTimestamp = timestamp;
        
        // 41位时间戳 + 10位workerId + 5位数据中心 + 12位序列号
        return ((timestamp - START_TIMESTAMP) << 22) 
             | (workerId << 17) 
             | (datacenterId << 12) 
             | sequence;
    }
}
```

**ID 结构**:
```
| 时间戳(41bit) | WorkerId(10bit) | DataCenter(5bit) | Sequence(12bit) |
|    69年       |     1024台      |      32机房      |     4096/毫秒   |
```

**追问题**:
- "Leaf 的双号段机制是什么？" → 号段两端生成，避免并发
- "如何支持分布式部署？" → 分配不同的 workerId

---

**场景 4: 秒杀系统设计**

**背景**: 10 万人同时抢 100 个商品，要求不超卖、不少卖。

**问题**: 如何设计秒杀系统？

**参考答案**:

**架构设计**:
```
                    ┌─────────────┐
                    │   Nginx 限流  │
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
        ┌─────────┐  ┌─────────┐  ┌─────────┐
        │ 缓存层   │  │ 消息队列 │  │ 网关    │
        │ Redis   │  │ Kafka   │  │ 鉴权    │
        └────┬────┘  └────┬────┘  └────┬────┘
             │             │             │
             └─────────────┴─────────────┘
                           │
                     ┌─────▼─────┐
                     │  库存服务   │
                     │  (Lua)    │
                     └─────┬─────┘
                           │
                     ┌─────▼─────┐
                     │  订单服务   │
                     └───────────┘
```

**核心设计**:
1. **库存预扣（Redis + Lua）**:
```lua
-- 原子扣减库存
local stock = redis.call('get', KEYS[1])
if stock and tonumber(stock) >= tonumber(ARGV[1]) then
    redis.call('decrby', KEYS[1], ARGV[1])
    return 1
end
return 0
```

2. **消息队列异步下单**:
```java
// 秒杀成功 → 发送消息 → 异步创建订单
kafkaTemplate.send("seckill-order", JSON.toJSONString(order));
```

3. **防刷设计**:
- 用户维度限流（Redis 计数器）
- IP 维度限流（Nginx limit_req）
- 设备指纹识别

**追问题**:
- "如何防止超卖？" → Redis 预扣 + 数据库最终扣减
- "如何防止少卖？" → 库存对账 + 补偿

---

**场景 5: 日志系统架构**

**背景**: 百万级 QPS 日志采集，要求实时查询、成本低。

**问题**: 如何设计日志系统？

**参考答案**:

**架构**:
```
App → Logback → Filebeat → Kafka → Logstash → Elasticsearch → Kibana
                                      ↓
                                ClickHouse (分析)
```

**选型对比**:
| 组件 | 方案 | 说明 |
|------|------|------|
| 采集 | Filebeat/Fluentd | 轻量、资源消耗低 |
| 缓冲 | Kafka | 削峰、解耦 |
| 处理 | Logstash | 解析、过滤 |
| 存储 | Elasticsearch | 实时查询 |
| 分析 | ClickHouse |  OLAP 分析 |

**降低成本策略**:
1. **索引优化**: 只索引必要字段
2. **数据生命周期**: ES 7 天 → HDFS 30 天 → 归档
3. **冷热分离**: 热数据 ES，冷数据对象存储

**追问题**:
- "如何快速定位线上问题？" → TraceID 贯穿全链路
- "日志量突增怎么处理？" → 采样、丢弃非关键日志

---

## 三、Agent 认知题库（5 题）

---

**A1: 请解释 ReAct 框架的工作原理。**

**参考答案**:

**ReAct = Reasoning + Acting**

**工作流程**:
```
用户问题
    ↓
┌─────────────────────────────────────────┐
│              Thought (推理)               │
│  "用户问的是天气，我需要调用天气 API"     │
└─────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────┐
│              Action (行动)                │
│  {"tool": "weather_api",              │
│   "query": "北京天气"}                 │
└─────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────┐
│              Observation (观察)           │
│  {"temperature": 25, "condition": "晴"} │
└─────────────────────────────────────────┘
    ↓
    ↓ (循环，直到得到答案)
    ↓
最终回答
```

**Prompt 示例**:
```
You are a helpful assistant. Think step by step.

Thought: I need to find the weather in Beijing.
Action: weather_api
Action Input: {"city": "Beijing"}
Observation: {"temperature": 25, "condition": "sunny"}
Thought: I have the information, I can answer now.
Final Answer: The weather in Beijing is sunny with 25°C.
```

**优势**:
- 可解释性强（能看到推理过程）
- 灵活（可以调用任意工具）
- 容错性好（中间结果可修正）

**追问题**:
- "ReAct 和 Plan-and-Execute 有什么区别？" → ReAct 是交替执行，Plan 是先规划再执行

---

**A2: RAG 系统如何解决 LLM 的知识时效性问题？**

**参考答案**:

**问题背景**:
- LLM 训练数据有截止日期
- 知识更新慢
- 无法访问私有数据

**RAG 解决方案**:
```
┌─────────────────────────────────────────────────────┐
│                   RAG 流程                          │
├─────────────────────────────────────────────────────┤
│                                                     │
│  用户问题 → Embedding → 向量检索 → Top-K 文档      │
│                  ↓                                  │
│          ┌──────────────┐                          │
│          │  向量数据库   │ ← 实时更新的知识库        │
│          │  (Milvus/    │                          │
│          │   Pinecone)  │                          │
│          └──────────────┘                          │
│                  ↓                                  │
│          检索结果 + 原问题 → LLM → 生成答案         │
│                                                     │
└─────────────────────────────────────────────────────┘
```

**关键组件**:
| 组件 | 作用 | 技术选型 |
|------|------|---------|
| Embedding | 文本转向量 | text-embedding-ada-002, BGE |
| 向量数据库 | 相似度检索 | Milvus, Pinecone, FAISS |
| 重排序 | 提升精度 | BGE-Reranker, Cohere Rerank |
| 生成 | 回答问题 | GPT-4, Claude, 开源模型 |

**时效性保证**:
1. **增量更新**: 新知识实时入库
2. **版本管理**: 知识库版本控制
3. **热更新**: 不重启服务更新索引

**追问题**:
- "如何解决检索精度问题？" → Query 改写 + 重排序 + 混合检索
- "如何处理长文档？" → 分段 + 元数据 + 摘要

---

**A3: Function Calling 的工作原理是什么？**

**参考答案**:

**工作流程**:
```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   用户问题   │────▶│    LLM      │────▶│  函数调用    │
└─────────────┘     └─────────────┘     └──────┬──────┘
                                               │
                        ┌──────────────────────┼──────────────────────┐
                        ▼                      ▼                      ▼
                 ┌──────────┐          ┌──────────┐          ┌──────────┐
                 │ 天气查询  │          │ 订单查询  │          │ 发起退款  │
                 └────┬─────┘          └────┬─────┘          └────┬─────┘
                      │                      │                      │
                      └──────────────────────┼──────────────────────┘
                                             ▼
                                    ┌──────────────┐
                                    │   工具执行    │
                                    └──────────────┘
                                             │
                                             ▼
                                    ┌──────────────┐
                                    │   结果返回    │
                                    └──────────────┘
                                             │
                                             ▼
                                    ┌──────────────┐
                                    │   LLM 生成    │
                                    │   最终回答    │
                                    └──────────────┘
```

**实现方式**:
```json
// 1. 定义工具
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

// 2. LLM 返回调用请求
{
  "role": "assistant",
  "function_call": {
    "name": "get_weather",
    "arguments": "{\"city\": \"北京\"}"
  }
}

// 3. 执行工具，获取结果
{
  "role": "function",
  "name": "get_weather",
  "content": "{\"temperature\": 25, \"condition\": \"晴\"}"
}

// 4. LLM 基于结果生成回答
{
  "role": "assistant",
  "content": "北京今天晴，气温 25 度。"
}
```

**最佳实践**:
- 工具描述要清晰明确
- 参数类型要严格定义
- 错误处理要完善
- 结果格式化要合理

---

**A4: Agent 的 Memory 机制有哪些？**

**参考答案**:

**三种 Memory 类型**:

| 类型 | 作用 | 实现 |
|------|------|------|
| 短期记忆 | 当前对话上下文 | Context Window |
| 长期记忆 | 历史对话、知识 | 向量数据库 |
| 示例记忆 | Few-shot 学习 | Prompt 中的示例 |

**短期记忆（Context Window）**:
```
Token 限制：
- GPT-4: 128K tokens
- Claude: 200K tokens
- LLaMA: 32K-128K tokens

管理策略:
1. 滑动窗口：保留最近 N 轮对话
2. 摘要压缩：将历史对话总结
3. 选择性保留：只保留关键信息
```

**长期记忆（向量数据库）**:
```python
# 存储
embeddings = get_embeddings([对话内容])
vector_db.add(ids=[...], embeddings=embeddings, documents=[...])

# 检索
query_embedding = get_embeddings([当前问题])
similar = vector_db.query(query_embedding, top_k=5)
```

**示例记忆（Few-shot）**:
```
User: 帮我订一张明天去北京的机票
Assistant: 好的，请问您需要几点出发？

User: 下午 2 点
Assistant: 已为您查询到以下航班：...
```

**追问题**:
- "如何避免上下文过长？" → 摘要、压缩、选择性保留
- "如何实现个性化记忆？" → 用户画像 + 向量存储

---

**A5: 多 Agent 协作是什么？有什么应用场景？**

**参考答案**:

**概念**: 多个专业化 Agent 分工协作完成复杂任务

**协作模式**:
```
┌──────────────────────────────────────────────────────┐
│                    Orchestrator                      │
│                  (任务编排者)                          │
├──────────────────────────────────────────────────────┤
│                                                       │
│    ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐│
│    │ Research│  │  Writer │  │  Coder  │  │ Reviewer││
│    │  Agent  │─▶│  Agent  │─▶│  Agent  │─▶│  Agent  ││
│    └─────────┘  └─────────┘  └─────────┘  └─────────┘│
│                                                       │
└──────────────────────────────────────────────────────┘
```

**经典架构**:
| 架构 | 说明 | 示例 |
|------|------|------|
| Pipeline | 串行处理 | MetaGPT |
| Hierarchical | 层级管理 | AutoGen |
| Swarm | 平等协作 | ChatDev |
| Loop | 迭代优化 | Reflexion |

**应用场景**:
1. **软件开发**: 需求分析 → 设计 → 编码 → 测试
2. **内容创作**: 调研 → 写作 → 编辑 → 发布
3. **数据分析**: 提取 → 清洗 → 分析 → 可视化
4. **客服系统**: 意图识别 → 知识检索 → 话术生成 → 人工接管

**追问题**:
- "多 Agent 比单 Agent 好在哪里？" → 专业化、可并行、易维护
- "如何避免 Agent 间的冲突？" → 明确接口、版本控制、仲裁机制

---

## 四、开放设计题（5 题）

---

**D1: 设计一个智能客服 Agent**

**需求**: 电商客服，支持订单查询、售后处理、人工转接。

**参考答案**:

**系统架构**:
```
┌─────────────────────────────────────────────────────────────┐
│                     智能客服 Agent                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │ Intent   │  │ Dialog   │  │ Tool     │  │ Human    │  │
│  │ Classifier│  │ Manager  │  │ Executor │  │ Handoff  │  │
│  └────┬─────┘  └────┬─────┘  └────┬────┘  └────┬─────┘  │
│       │             │             │            │         │
│       └─────────────┴─────────────┴────────────┘         │
│                          │                                │
│                   ┌──────▼──────┐                        │
│                   │  Response   │                        │
│                   │  Generator  │                        │
│                   └──────┬──────┘                        │
│                          │                                │
│                   ┌──────▼──────┐                        │
│                   │  Memory     │                        │
│                   │  (Redis)   │                        │
│                   └─────────────┘                        │
└─────────────────────────────────────────────────────────────┘
```

**关键模块设计**:

| 模块 | 功能 | 技术 |
|------|------|------|
| 意图识别 | 分类用户问题 | 微调 BERT / Prompt |
| 对话管理 | 维护多轮状态 | Redis Session |
| 工具调用 | 查询订单/退款 | Function Calling |
| 知识检索 | 售后政策/FAQ | RAG + ES |
| 人工接管 | 复杂问题转人工 | 规则 + LLM 判断 |

**意图识别 Prompt**:
```
用户问题: {question}
历史对话: {history}

请将用户意图分类为以下之一:
- ORDER_QUERY: 订单查询
- AFTER_SALES: 售后处理
- PRODUCT_INFO: 商品信息
- COMPLAINT: 投诉建议
- OTHER: 其他

返回 JSON: {"intent": "ORDER_QUERY", "confidence": 0.95}
```

**服务质量保证**:
- 意图识别准确率 > 90%
- 工具调用成功率 > 95%
- 响应时间 < 2s
- 人工接管阈值设计

---

**D2: 设计一个 Text-to-SQL Agent**

**需求**: 通过自然语言查询数据库，自动生成 SQL 并执行。

**参考答案**:

**系统架构**:
```
用户问题
    ↓
┌─────────────────────────────────┐
│  意图理解 & Schema 选择          │
│  - 实体识别                      │
│  - 相关表选择                    │
└───────────────┬─────────────────┘
                ↓
┌─────────────────────────────────┐
│  SQL 生成                       │
│  - 构建 Prompt                  │
│  - LLM 生成 SQL                 │
│  - SQL 语法校验                 │
└───────────────┬─────────────────┘
                ↓
┌─────────────────────────────────┐
│  SQL 执行                       │
│  - 权限检查（只读）              │
│  - 执行查询                     │
│  - 结果格式化                   │
└───────────────┬─────────────────┘
                ↓
┌─────────────────────────────────┐
│  结果展示                       │
│  - 表格/图表                    │
│  - 自然语言解释                 │
└─────────────────────────────────┘
```

**关键设计**:
1. **Schema 选择**: 从数据库元数据中选择相关表
2. **SQL 生成**: 
```python
prompt = f"""
You are a SQL expert. Database schema:
{schema}

User question: {question}

Generate SQL:
"""
sql = llm.generate(prompt)
```
3. **权限控制**: 只允许 SELECT，禁止 DROP/DELETE
4. **结果格式化**: 根据数据类型自动选择展示方式

**安全考虑**:
- SQL 注入防护
- 查询超时控制
- 结果集大小限制
- 敏感数据脱敏

---

**D3: 设计一个代码审查 Agent**

**需求**: 自动审查代码质量，检测 Bug、规范问题、给出优化建议。

**参考答案**:

**系统架构**:
```
Git Push → Webhook → Agent 接收 PR
    ↓
┌─────────────────────────────────┐
│  代码分析模块                    │
│  - AST 解析                      │
│  - 规则匹配                      │
│  - LLM 语义分析                  │
└───────────────┬─────────────────┘
                ↓
┌─────────────────────────────────┐
│  审查报告生成                    │
│  - Bug 等级                      │
│  - 规范问题                      │
│  - 优化建议                      │
│  - 代码示例                      │
└───────────────┬─────────────────┘
                ↓
GitHub Comment / PR Review
```

**分析维度**:
| 维度 | 方法 | 示例 |
|------|------|------|
| Bug 检测 | 静态分析 + LLM | 空指针、资源泄漏 |
| 规范检查 | 规则引擎 | 命名规范、注释规范 |
| 性能优化 | LLM 分析 | 循环优化、缓存使用 |
| 安全漏洞 | 规则 + LLM | SQL 注入、XSS |

**Prompt 示例**:
```
Please review this code change:

{code_diff}

Check for:
1. Bugs (null pointer, resource leak, etc.)
2. Code style issues
3. Performance problems
4. Security vulnerabilities

Return JSON:
{
  "bugs": [...],
  "style_issues": [...],
  "suggestions": [...],
  "severity": "high/medium/low"
}
```

---

**D4: 设计一个日志分析 Agent**

**需求**: 自动分析线上日志，识别异常模式，生成诊断报告。

**参考答案**:

**系统架构**:
```
日志源 → Filebeat → Kafka → Logstash → ES/ClickHouse
                                    ↓
                            ┌─────────────┐
                            │  日志分析    │
                            │     Agent    │
                            └──────┬──────┘
                                   ↓
                            ┌─────────────┐
                            │  异常检测    │
                            │  - 规则匹配  │
                            │  - 机器学习  │
                            └──────┬──────┘
                                   ↓
                            ┌─────────────┐
                            │  关联分析    │
                            │  - TraceID  │
                            │  - 时间窗口  │
                            └──────┬──────┘
                                   ↓
                            ┌─────────────┐
                            │  报告生成    │
                            │  - 根因定位  │
                            │  - 建议措施  │
                            └─────────────┘
```

**异常检测策略**:
| 方法 | 适用场景 | 示例 |
|------|---------|------|
| 规则匹配 | 已知模式 | ERROR 日志突增 |
| 统计分析 | 基线偏离 | QPS 骤降 |
| 机器学习 | 未知模式 | 异常聚类 |

**诊断流程**:
1. 识别异常日志模式
2. 关联同 TraceID 的日志
3. 时间窗口聚合分析
4. 生成根因假设
5. 给出修复建议

---

**D5: 设计一个自动化测试 Agent**

**需求**: 自动分析代码变更，生成测试用例，执行测试，生成报告。

**参考答案**:

**系统架构**:
```
Git Push → Webhook → Agent 分析变更
    ↓
┌─────────────────────────────────┐
│  变更分析                        │
│  - Git Diff 解析                │
│  - 影响范围评估                  │
│  - 关键路径识别                  │
└───────────────┬─────────────────┘
                ↓
┌─────────────────────────────────┐
│  测试用例生成                    │
│  - 边界值分析                    │
│  - 等价类划分                    │
│  - 异常场景                      │
└───────────────┬─────────────────┘
                ↓
┌─────────────────────────────────┐
│  测试执行                        │
│  - 单元测试                      │
│  - 集成测试                      │
│  - 并发测试                      │
└───────────────┬─────────────────┘
                ↓
┌─────────────────────────────────┐
│  报告生成                        │
│  - 覆盖率统计                    │
│  - 失败分析                      │
│  - 改进建议                      │
└─────────────────────────────────┘
```

**测试用例生成策略**:
```python
# 基于变更生成测试用例
def generate_test_cases(diff):
    cases = []
    for changed_line in diff.changed_lines:
        if changed_line.is_boundary:
            cases.append(generate_boundary_test(changed_line))
        if changed_line.is_exception:
            cases.append(generate_exception_test(changed_line))
        if changed_line.is_performance:
            cases.append(generate_perf_test(changed_line))
    return cases
```

---

## 五、评分标准

### 每题评分（1-5 分）

| 得分 | 标准 |
|------|------|
| 5 | 回答完整深入，能说出底层原理和细节 |
| 4 | 回答正确，能说出主要特点和原理 |
| 3 | 回答基本正确，有部分遗漏 |
| 2 | 回答不完整，需要引导 |
| 1 | 基本不会或完全错误 |

### 总分计算

| 维度 | 权重 | 满分 |
|------|------|------|
| 基础问答 | 40% | 20 |
| 场景分析 | 30% | 15 |
| Agent 认知 | 15% | 7.5 |
| 开放设计 | 15% | 7.5 |
| **总计** | 100% | **50** |

### 录用建议

| 总分 | 建议 |
|------|------|
| 40-50 | ✅ 强烈推荐二面 |
| 30-39 | ✅ 推荐二面 |
| 20-29 | ⚠️ 谨慎考虑 |
| <20 | ❌ 不推荐 |

---

## 六、13 人面试安排

| 人 | 基础题 | 场景题 | Agent 题 | 设计题 |
|----|--------|--------|----------|--------|
| 1 | Q1+Q3+Q5 | 场景1+场景4 | A1+A3 | D1 |
| 2 | Q2+Q4+Q6 | 场景2+场景5 | A2+A4 | D2 |
| 3 | Q7+Q8+Q9 | 场景3+场景1 | A1+A5 | D3 |
| 4 | Q10+Q1+Q3 | 场景4+场景2 | A2+A3 | D4 |
| 5 | Q5+Q6+Q8 | 场景5+场景3 | A4+A5 | D5 |
| 6 | Q2+Q7+Q9 | 场景1+场景4 | A1+A2 | D1 |
| 7 | Q4+Q10+Q1 | 场景2+场景5 | A3+A4 | D2 |
| 8 | Q3+Q5+Q7 | 场景3+场景1 | A5+A1 | D3 |
| 9 | Q6+Q8+Q10 | 场景4+场景2 | A2+A3 | D4 |
| 10 | Q9+Q1+Q4 | 场景5+场景3 | A4+A5 | D5 |
| 11 | Q2+Q6+Q7 | 场景1+场景4 | A1+A2 | D1 |
| 12 | Q3+Q8+Q9 | 场景2+场景5 | A3+A4 | D2 |
| 13 | Q5+Q10+Q1 | 场景3+场景1 | A5+A1 | D3 |

---

**祝面试顺利！** 🎉
