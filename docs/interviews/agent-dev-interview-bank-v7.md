# Agent 开发工程师 - 校招一面面试题库（高难度版）

> 版本: v7.0  
> 时长: 60 分钟/人  
> 题库规模: 30 道核心题 + 详细答案  
> 适用: 研究生/有研究经验的候选人  
> 特点: 重原理、重底层、重系统设计

---

## ⏱️ 面试流程

| 环节 | 时长 | 内容 |
|------|------|------|
| 破冰 + 项目介绍 | 5min | 了解背景，建立信任 |
| **基础问答题** | 15min | 抽取 3-4 题（高难度） |
| **场景分析题** | 15min | 抽取 2-3 题（复杂场景） |
| **Agent 认知题** | 10min | 抽取 2-3 题（深入理解） |
| **开放设计题** | 10min | 抽取 1 题（系统架构） |
| 反问 | 5min | 了解候选人关注点 |

---

## 一、Java 基础问答题库（12 题）

---

### Q1: 请深入解释 JVM 内存模型，包括对象创建、内存布局、GC 触发条件

**考察点**: JVM 底层原理，适合研究生水平

**参考答案**:

**内存区域详解**:

| 区域 | 作用 | 线程共享 | 回收策略 |
|------|------|---------|---------|
| 堆（Heap） | 存放对象实例和数组，GC 主要区域 | 是 | 分代收集 |
| 栈（Stack） | 局部变量表、操作数栈、方法出口 | 否 | 随方法调用结束 |
| 方法区 | 类信息、常量、静态变量、JIT 编译代码 | 是 | Permanent Gen/Metaspace |
| 程序计数器 | 记录当前线程执行的字节码行号 | 否 | 无回收 |
| 本地方法栈 | Native 方法服务 | 否 | 随线程结束 |

**对象内存布局（64位 JVM，开启压缩指针）**:
```
┌─────────────────────────────────────────┐
│           Object Header (12 bytes)      │
│  ┌─────────────────┬──────────────────┐ │
│  │ Mark Word (64bit)│ Type Pointer    │ │
│  │ · 哈希码 25bit   │ (32bit)         │ │
│  │ · 分代年龄 4bit  │                 │ │
│  │ · 锁标志 1bit    │                 │ │
│  │ · 偏向线程 54bit │                 │ │
│  └─────────────────┴──────────────────┘ │
├─────────────────────────────────────────┤
│           Instance Data (variable)      │
│           (对象真正有效的数据)            │
├─────────────────────────────────────────┤
│           Padding (8 byte alignment)    │
└─────────────────────────────────────────┘
```

**对象创建过程**:
```
1. 类加载检查 → 检查常量池是否有类的符号引用
2. 分配内存 → 指针碰撞（TLAB）或空闲列表
3. 初始化零值 → 清零内存
4. 设置对象头 → Mark Word、Type Pointer
5. init 方法执行 → 执行 <init> 初始化
```

**TLAB（Thread Local Allocation Buffer）**:
- 每个线程在 Eden 区分配一块私有空间
- 避免并发分配时的锁竞争
- 默认启用：`-XX:+UseTLAB`

**GC 触发条件**:
| 触发点 | 说明 |
|--------|------|
| New Object | Eden 区满，触发 Young GC |
| Alloc Fail | 分配失败且 noGC 未禁用 |
| Tenured GC | 老年代不足 |
| Metaspace GC | 元空间满 |
| System.gc() | 显式调用（建议避免） |

**晋升老年代条件**:
1. 大对象直接进老年代（-XX:PretenureSizeThreshold）
2. 长期存活的对象（分代年龄达 15）
3. Dynamic Age 优化（同龄对象总量 > Survivor 50%）
4. 空间分配担保失败

**追问**:
- "如何解决内存溢出？" → MAT/jmap 分析堆转储
- "如何优化 GC？" → 调整堆大小、选择合适 GC、减少大对象

**评分标准**:
- 5 分: 能画出完整布局，说出 TLAB、晋升条件、GC 触发时机
- 4 分: 知道各区域作用，了解对象创建过程
- 3 分: 知道堆/栈区别，但细节不清
- 2 分: 只说"堆存对象，栈存局部变量"
- 1 分: 不清楚

---

### Q2: 深入分析 HashMap 的扩容机制、树化条件、并发安全问题及 ConcurrentHashMap 实现

**考察点**: 数据结构演进、并发编程深度

**参考答案**:

**扩容机制（JDK 8）**:
```java
// 扩容条件
if (++size >= threshold)
    resize();

// 扩容流程
final Node<K,V>[] resize() {
    Node<K,V>[] oldTab = table;
    int oldCap = (oldTab == null) ? 0 : oldTab.length;
    int oldThr = threshold;
    int newCap, newThr = 0;
    
    // 容量翻倍
    if (oldCap > 0) {
        newCap = oldCap << 1;
        newThr = oldThr << 1;
    }
    
    // 重新 hash 分布
    for (int j = 0; j < oldCap; ++j) {
        Node<K,V> e;
        if ((e = oldTab[j]) != null) {
            // 高位为 0：位置不变
            // 高位为 1：新位置 = 原位置 + oldCap
            if ((e.hash & oldCap) == 0) {
                loHead = e;
            } else {
                hiHead = e;
            }
        }
    }
}
```

**树化条件**:
```java
static final int TREEIFY_THRESHOLD = 8;      // 链表 ≥ 8
static final int UNTREEIFY_THRESHOLD = 6;     // 树节点 ≤ 6
static final int MIN_TREEIFY_CAPACITY = 64;   // 数组容量 ≥ 64 才树化

// 为什么需要 MIN_TREEIFY_CAPACITY？
// 容量小时，扩容比树化更高效
```

**并发安全问题**:
| 问题 | 原因 | 解决方案 |
|------|------|---------|
| JDK 7 死循环 | 头插法导致环状链表 | 用 JDK 8 或 ConcurrencyHashMap |
| 数据丢失 | 并发扩容时链表断裂 | 外部同步或使用并发容器 |
| size 不准确 | 多线程修改 size | 使用 ConcurrencyHashMap |

**ConcurrentHashMap 实现（JDK 8）**:
```java
// 核心数据结构
transient volatile Node<K,V>[] table;

// CAS + synchronized 实现线程安全
final V putVal(K key, V value, boolean onlyIfAbsent) {
    Node<K,V>[] tab; Node<K,V> p; int n, i;
    
    // 1. 初始化
    if ((tab = table) == null || (n = tab.length) == 0)
        n = (tab = initTable()).length;
    
    // 2. CAS 计算索引位置
    int index = (n - 1) & hash;
    Node<K,V> f; int fh;
    if ((f = tabAt(tab, index)) == null || 
        (fh = f.hash) == MOVED)
        tab = helpTransfer(tab, f);
    
    // 3. 锁住桶头节点
    synchronized (f) {
        if (tabAt(tab, index) == f) {
            // 链表或树节点插入
            ...
        }
    }
}

// 并发 put 时的帮助扩容
final void helpTransfer(Node<K,V>[] tab, Node<K,V> f) {
    Node<K,V>[] nextTable;
    // 多个线程帮助扩容
    ...
}
```

**CAS 操作（Unsafe）**:
```java
// Unsafe 提供原生 CAS 支持
public final native boolean compareAndSwapObject(Object o, long offset, Object expected, Object x);
public final native boolean compareAndSwapInt(Object o, long offset, int expected, int x);
```

**与 Java 8 之前区别**:
| 特性 | JDK 7 | JDK 8 |
|------|-------|-------|
| 锁粒度 | Segment（分段锁） | Node（桶级锁） |
| 锁实现 | synchronized | synchronized + CAS |
| 并发度 | 16 | 理论上无限 |
| size 计算 | 简单相加 | sumCount() 累加 |

**追问**:
- "为什么 ConcurrentHashMap get 不需要加锁？" → volatile 读保证可见性
- "size() 为什么不精确？" → 并发修改时可能误差

**评分标准**:
- 5 分: 清楚扩容算法、树化条件、CAS 原理、ConcurrentHashMap 实现
- 4 分: 知道主要区别，了解并发问题
- 3 分: 知道线程不安全，但说不清原因
- 2 分: 只说"用 ConcurrentHashMap"
- 1 分: 不清楚

---

### Q3: 线程池的实现原理、任务提交流程、拒绝策略选择及动态线程池设计

**考察点**: 并发编程实战能力

**参考答案**:

**任务提交流程**:
```
submit(task)
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
                      ↓
                线程从队列取任务执行
```

**核心参数详解**:
```java
public class ThreadPoolExecutor {
    // 核心线程数：即使空闲也不会回收
    private final int corePoolSize;
    
    // 最大线程数：队列满后才会创建
    private final int maximumPoolSize;
    
    // 非核心线程存活时间
    private final long keepAliveTime;
    
    // 任务队列
    private final BlockingQueue<Runnable> workQueue;
    
    // 线程工厂（可自定义线程名、优先级）
    private final ThreadFactory threadFactory;
    
    // 拒绝策略
    private final RejectedExecutionHandler handler;
}
```

**工作队列类型**:
| 队列 | 特点 | 适用场景 |
|------|------|---------|
| ArrayBlockingQueue | 有界，公平 | 需要严格控制队列大小 |
| LinkedBlockingQueue | 默认 Integer.MAX_VALUE | 吞吐量大、不担心 OOM |
| SynchronousQueue | 不存储，直接传递 | 极致吞吐，配合 large pool |
| PriorityBlockingQueue | 优先级队列 | 任务有优先级需求 |
| DelayQueue | 延迟队列 | 定时任务 |

**拒绝策略选择**:
| 策略 | 行为 | 适用场景 |
|------|------|---------|
| AbortPolicy | 抛异常 | 默认，强调不丢失任务 |
| CallerRunsPolicy | 调用方执行 | 平滑降级，不丢弃任务 |
| DiscardPolicy | 静默丢弃 | 允许丢失非关键任务 |
| DiscardOldestPolicy | 丢弃最老 | 保证最新任务被执行 |

**线程池大小配置**:
```
CPU 密集型: N + 1（N 为 CPU 核数）
IO 密集型: N / (1 - 阻塞系数) 或 2N
混合密集型: 分解为子任务分别计算
```

**动态线程池设计**:
```java
public class DynamicThreadPool {
    private ThreadPoolExecutor executor;
    
    // 动态调整核心线程数
    public void changeCoreSize(int newCoreSize) {
        executor.setCorePoolSize(newCoreSize);
    }
    
    // 动态调整队列容量
    public void changeQueueCapacity(int newCapacity) {
        if (executor.getQueue() instanceof LinkedBlockingQueue) {
            LinkedBlockingQueue<Runnable> queue = 
                (LinkedBlockingQueue<Runnable>) executor.getQueue();
            queue.clear();
            // 需要替换整个队列（线程池不支持动态改容量）
        }
    }
    
    // 监控指标
    public PoolStatistics getStatistics() {
        return new PoolStatistics(
            executor.getActiveCount(),
            executor.getPoolSize(),
            executor.getCompletedTaskCount(),
            executor.getTaskCount(),
            executor.getQueue().size()
        );
    }
}
```

**线程池监控**:
```java
// 关键指标
activeCount: 当前活跃线程数
poolSize: 当前线程池大小
completedTaskCount: 已完成任务数
taskCount: 总任务数
queueSize: 队列中等待的任务数
```

**常见问题排查**:
| 问题 | 排查方法 | 解决方案 |
|------|---------|---------|
| 任务堆积 | 监控 queueSize | 扩容线程数或队列 |
| 频繁创建线程 | 监控 poolSize | 调整 corePoolSize |
| 任务丢失 | 检查拒绝策略 | 改用 CallerRunsPolicy |
| 线程泄漏 | 检查异常处理 | 完善 try-catch |

**追问**:
- "如何优雅关闭线程池？" → shutdown() + awaitTermination()
- "线程池有哪些坑？" → 不要使用 Executors 工厂方法

**评分标准**:
- 5 分: 清楚任务提交流程，能推导线程数公式，知道动态线程池设计
- 4 分: 知道参数含义，能给出配置建议
- 3 分: 知道核心参数，但说不清流程
- 2 分: 只记得几个参数名
- 1 分: 不了解

---

### Q4: volatile 的内存语义、指令重排、DCL 双重检查锁定详解

**考察点**: 并发基础深度理解

**参考答案**:

**volatile 三大特性**:

| 特性 | 实现机制 | 说明 |
|------|---------|------|
| 可见性 | 写屏障 + 缓存失效 | 写操作刷新到主存，其他 CPU 失效缓存行 |
| 有序性 | 内存屏障 | 禁止指令重排 |
| 原子性 | ❌ 不保证 | read-modify-write 不是原子的 |

**内存屏障（Memory Barrier）**:
```
LoadLoad 屏障: 确保 Load1 数据在所有 Load2 之前加载
StoreStore 屏障: 确保 Store1 数据在所有 Store2 之前刷新  
LoadStore 屏障: 确保 Load1 数据在所有 Store2 之前加载
StoreLoad 屏障: 确保 Store1 数据在所有 Load2 之前刷新（最贵）
```

**Java Memory Model 规则**:
```
1. 程序次序规则: 单线程内按代码顺序
2. 锁定规则: 解锁前同步到主存
3.  volatile 规则: 写前刷盘，读后失效
4.  传递规则: 传递有序性
5.  启动规则: start() 前同步
6.  终止规则: 所有操作先于 join()
7.  中断规则: 中断先于代码检测到
8.  终结规则: 构造函数结束先于 finalize()
```

**DCL（双重检查锁定）详解**:
```java
public class Singleton {
    // volatile 防止指令重排
    private static volatile Singleton instance;
    
    private Singleton() {}
    
    public static Singleton getInstance() {
        // 第一次检查（避免每次加锁）
        if (instance == null) {
            synchronized (Singleton.class) {
                // 第二次检查（避免并发创建）
                if (instance == null) {
                    instance = new Singleton();
                }
            }
        }
        return instance;
    }
}
```

**为什么要 volatile？**
```
new Singleton() 分为三步:
1. allocate() - 分配内存
2. init() - 初始化对象
3. assign() - 赋值给变量

没有 volatile 时，可能发生重排:
1. allocate()
2. assign() - 先赋值（此时对象未初始化）
3. init()

其他线程在步骤 2 后看到 instance != null，
但对象未初始化，导致错误！
```

**volatile vs synchronized**:
| 特性 | volatile | synchronized |
|------|----------|--------------|
| 可见性 | ✅ | ✅ |
| 原子性 | ❌ | ✅ |
| 有序性 | ✅ | ✅ |
| 性能 | 高（无锁） | 较低（有锁） |
| 适用场景 | 状态标志、DCL | 复杂临界区 |

**原子类（基于 CAS）**:
```java
// AtomicInteger 实现
public class AtomicInteger {
    private static final Unsafe unsafe = Unsafe.getUnsafe();
    private static final long valueOffset;
    
    static {
        try {
            valueOffset = unsafe.objectFieldOffset
                (AtomicInteger.class.getDeclaredField("value"));
        } catch (Exception ex) { throw new Error(ex); }
    }
    
    private volatile int value;
    
    public final int getAndIncrement() {
        int current;
        int next;
        do {
            current = this.value;
            next = current + 1;
        } while (!unsafe.compareAndSwapInt(this, valueOffset, current, next));
        return current;
    }
}
```

**追问**:
- "volatile 能替代 CAS 吗？" → 不能，CAS 保证原子性
- "如何理解 happens-before？" → Java 内存模型的核心概念

**评分标准**:
- 5 分: 清楚三大特性，能解释内存屏障和指令重排，给出 DCL 示例
- 4 分: 知道可见性和有序性，但说不清原子性问题
- 3 分: 知道 volatile 保证可见性
- 2 分: 只说"多线程共享变量"
- 1 分: 不清楚

---

### Q5: 深入分析 synchronized 的实现原理、锁升级过程、偏向锁优化

**考察点**: 锁机制底层实现

**参考答案**:

**synchronized 实现原理**:
```
Monitor 结构:
┌─────────────────────────────────────┐
│             Object Header           │
│  ┌─────────────────┬──────────────┐ │
│  │ Mark Word       │ Type Pointer │ │
│  │ · 锁标志 2bit   │              │ │
│  │ · 偏向线程 ID   │              │ │
│  │ · 分代年龄      │              │ │
│  └─────────────────┴──────────────┘ │
├─────────────────────────────────────┤
│          Monitor Structure          │
│  ┌───────────────────────────────┐  │
│  │ Owner (持有者)                 │  │
│  │ EntrySet (等待锁的线程)         │  │
│  │ WaitSet (等待唤醒的线程)        │  │
│  └───────────────────────────────┘  │
└─────────────────────────────────────┘
```

**锁升级过程**:
```
无锁 → 偏向锁 → 轻量级锁（自旋） → 重量级锁（OS Mutex）

1. 无锁状态:
   Mark Word: [01 | hash | age]

2. 偏向锁（首次获取锁）:
   Mark Word: [10 | thread_id | age]
   - 记录持有锁的线程 ID
   - 后续该线程获取锁无需同步

3. 轻量级锁（偏向锁撤销）:
   Mark Word: [00 | lock_record_addr]
   - 线程在栈帧中创建锁记录
   - CAS 替换 Mark Word
   - 自旋等待

4. 重量级锁（自旋失败）:
   Mark Word: [10 | monitor_addr]
   - 指向 Monitor 对象
   - 线程阻塞在 EntrySet
```

**偏向锁优化**:
```java
// 启用偏向锁（JDK 8 默认启用）
-XX:+UseBiasedLocking

// 禁用偏向锁（高竞争场景）
-XX:-UseBiasedLocking
```

**偏向锁撤销流程**:
```
1. 其他线程尝试获取锁
2. JVM 检查偏向线程是否存活
3. 找到锁记录，CAS 替换 Mark Word
4. 唤醒偏向线程，撤销偏向
5. 升级为轻量级锁
```

**锁消除**:
```java
// JIT 编译器进行锁消除
public void add(String s1, String s2) {
    StringBuffer sb = new StringBuffer();
    sb.append(s1);  // sb 是线程私有的，JIT 会消除锁
    sb.append(s2);
    System.out.println(sb.toString());
}
// 等价于：
public void add(String s1, String s2) {
    String result = s1 + s2;
    System.out.println(result);
}
```

**锁粗化**:
```java
// 不推荐：反复加锁解锁
for (int i = 0; i < 1000; i++) {
    synchronized(this) {
        count++;
    }
}

// 推荐：粗化锁范围
synchronized(this) {
    for (int i = 0; i < 1000; i++) {
        count++;
    }
}
```

**追问**:
- "偏向锁有什么缺点？" → 撤销开销大，高竞争场景反而慢
- "如何查看锁状态？" → `-XX:+PrintCommandLineFlags -XX:+UnlockDiagnosticVMOptions -XX:+PrintGC`

**评分标准**:
- 5 分: 清楚锁升级全过程，理解偏向锁优化，知道锁消除/粗化
- 4 分: 知道锁升级过程，了解偏向锁
- 3 分: 知道 synchronized 有锁升级
- 2 分: 只说"有锁竞争"
- 1 分: 不清楚


---

### Q6: ClassLoader 机制、双亲委派模型及其破坏场景

**考察点**: JVM 类加载深度理解

**参考答案**:

**类加载过程**:
```
加载 → 验证 → 准备 → 解析 → 初始化 → 使用 → 卸载
   ↓       ↓       ↓       ↓       ↓
  二进制  格式    静态     符号    clinit
  流     检查    变量     引用    方法
```

**双亲委派模型**:
```
┌─────────────────────────────────┐
│     Application ClassLoader     │  ← 用户类路径
├─────────────────────────────────┤
│    Extension ClassLoader        │  ← 扩展目录
├─────────────────────────────────┤
│   Bootstrap ClassLoader         │  ← 核心类库
└─────────────────────────────────┘
         ↑           ↑           ↑
         └───────────┴───────────┘
              请求向上委派
              
           只有父加载器无法加载时
           才尝试自己加载
```

**双亲委派的作用**:
1. **安全性**: 防止核心 API 被篡改（如 java.lang.String）
2. **唯一性**: 保证类在全局唯一
3. **复用性**: 父加载器已加载的类不会重复加载

**破坏双亲委派的场景**:
| 场景 | 实现方式 | 原因 |
|------|---------|------|
| SPI 机制 | Thread.getContextClassLoader() | 接口在 Bootstrap，实现由 App 提供 |
| Tomcat | 自定义 ClassLoader | 同一类不同 WebApp 隔离 |
| OSGi | Bundle ClassLoader | 模块化管理 |
| 热部署 | URLClassLoader | 动态加载新类 |

**SPI（Service Provider Interface）示例**:
```java
// JDBC 驱动加载
Class.forName("com.mysql.cj.jdbc.Driver");
// 内部使用 Thread.getContextClassLoader().loadClass()
// 而不是系统 ClassLoader
```

**自定义 ClassLoader**:
```java
public class MyClassLoader extends ClassLoader {
    private String classPath;
    
    @Override
    protected Class<?> findClass(String name) throws ClassNotFoundException {
        try {
            byte[] data = loadClassData(name);
            return defineClass(name, data, 0, data.length);
        } catch (IOException e) {
            throw new ClassNotFoundException(name);
        }
    }
    
    private byte[] loadClassData(String className) throws IOException {
        String path = classPath + "/" + 
                      className.replace('.', '/') + ".class";
        try (InputStream is = new FileInputStream(path);
             ByteArrayOutputStream baos = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[4096];
            int len;
            while ((len = is.read(buffer)) != -1) {
                baos.write(buffer, 0, len);
            }
            return baos.toByteArray();
        }
    }
}
```

**追问**:
- "为什么 ThreadLocal 能实现线程隔离？" → 每个 Thread 维护自己的 ThreadLocalMap
- "如何实现类隔离？" → 自定义 ClassLoader，设置不同的 parent

**评分标准**:
- 5 分: 清楚类加载全过程，能解释双亲委派及破坏场景
- 4 分: 知道双亲委派原理，了解 SPI 机制
- 3 分: 知道 ClassLoader 概念
- 2 分: 只说"加载类"
- 1 分: 不清楚

---

### Q7: AQS 原理、ReentrantLock 实现、条件队列详解

**考察点**: Java 并发核心框架

**参考答案**:

**AQS（AbstractQueuedSynchronizer）核心结构**:
```java
public abstract class AbstractQueuedSynchronizer {
    // 同步状态
    private volatile int state;
    
    // 等待队列（双向链表）
    private transient volatile Node head;
    private transient volatile Node tail;
    
    // 内部类 Node
    static final class Node {
        static final Node EXCLUSIVE = null;
        static final int CANCELLED =  1;
        static final int SIGNAL    = -1;
        static final int CONDITION = -2;
        static final int PROPAGATE = -3;
        
        volatile int waitStatus;
        volatile Node prev;    // 前驱
        volatile Node next;    // 后继
        volatile Thread thread;
        Node nextWaiter;       // 条件队列
    }
}
```

**ReentrantLock 实现**:
```java
public class ReentrantLock implements Lock {
    private final Sync sync;
    
    // 公平锁 vs 非公平锁
    abstract static class Sync extends AbstractQueuedSynchronizer {
        abstract void lock();
    }
    
    static final class NonfairSync extends Sync {
        final void lock() {
            // 1. CAS 尝试获取锁
            if (compareAndSetState(0, 1)) {
                setExclusiveOwnerThread(Thread.currentThread());
                return;
            }
            // 2. 获取失败，进入 AQS 队列
            acquire(1);
        }
    }
    
    static final class FairSync extends Sync {
        final void lock() {
            // 公平锁先检查队列是否有等待者
            acquire(1);
        }
    }
}
```

**acquire 流程**:
```
acquire(int arg):
    1. tryAcquire(arg) → 尝试获取锁
       └── 成功：返回
       └── 失败：继续
    2. addWaiter(Node.EXCLUSIVE) → 创建节点加入队列
       └── 快速路径：CAS 入队
       └── 慢速路径：enq() 自旋入队
    3. acquireQueued(node, arg) → 自旋获取锁
       └── 检查前驱是否为 head（头节点后进先出）
       └── 尝试获取锁，失败则 park()
```

**条件队列（Condition）**:
```java
// 一个锁可以有多个条件队列
Lock lock = new ReentrantLock();
Condition notFull  = lock.newCondition();
Condition notEmpty = lock.newCondition();

// 使用示例
notEmpty.await();   // 线程进入 notEmpty 等待队列
notFull.signal();   // 唤醒 notFull 队列中的线程
```

**Condition 实现原理**:
```
普通队列          条件队列
┌─────┐          ┌─────┐
│  T1 │  await() │  T2 │ signal()
└──┬──┘          └──┬──┘
   │ moveToConditionQueue()
   ↓                ↓
┌──────────┐    ┌──────────┐
│ waitQueue │    │condQueue │
└──────────┘    └──────────┘

signal() 时：
1. 从 condQueue 移出一个节点
2. 加入 waitQueue 尾部
3. unpark() 唤醒线程
```

**公平锁 vs 非公平锁**:
| 特性 | 公平锁 | 非公平锁 |
|------|--------|---------|
| 性能 | 较低（排队） | 较高（可能抢占） |
| 饥饿 | 不会出现 | 可能出现 |
| 吞吐量 | 较低 | 较高 |
| 适用场景 | 需要保证顺序 | 追求性能 |

**追问**:
- "为什么非公平锁性能更好？" → 减少上下文切换，可能刚好有线程释放锁
- "如何用 AQS 实现读写锁？" → state 高 16 位读锁，低 16 位写锁

**评分标准**:
- 5 分: 清楚 AQS 队列结构，能画出 acquire 流程，理解条件队列
- 4 分: 知道 ReentrantLock 原理，了解公平/非公平区别
- 3 分: 知道 AQS 是基础框架
- 2 分: 只说"锁的实现"
- 1 分: 不清楚

---

### Q8: Java 异常处理机制、异常链、Try-With-Resources 原理

**考察点**: 异常处理深度理解

**参考答案**:

**异常类层次**:
```
Throwable
├── Error（虚拟机错误，不应捕获）
│   ├── OutOfMemoryError
│   ├── StackOverflowError
│   └── NoClassDefFoundError
└── Exception
    ├── RuntimeException（运行时异常，unchecked）
    │   ├── NullPointerException
    │   ├── ArrayIndexOutOfBoundsException
    │   ├── ClassCastException
    │   └── IllegalArgumentException
    └── IOException（编译时异常，checked）
        ├── FileNotFoundException
        └── SocketException
```

**异常链（Exception Chaining）**:
```java
public class CustomException extends Exception {
    private final String errorCode;
    private final Throwable cause;
    
    public CustomException(String message, String errorCode, Throwable cause) {
        super(message, cause);  // 建立异常链
        this.errorCode = errorCode;
        this.cause = cause;
    }
}

// 使用
try {
    // 业务逻辑
} catch (IOException e) {
    throw new CustomException("业务失败", "E001", e);
}
```

**Try-With-Resources 原理**:
```java
// 语法糖，编译后变为：
try {
    BufferedReader br = new BufferedReader(new FileReader("test.txt"));
    try {
        String line = br.readLine();
    } catch (Exception e) {
        // 编译后会有 suppressed exceptions
    } finally {
        if (br != null) {
            br.close();
        }
    }
} finally {
    // 关闭资源
}
```

**自动关闭接口**:
```java
public interface AutoCloseable {
    void close() throws Exception;
}

// Stream 接口继承
public interface Closeable extends AutoCloseable {
    @Override
    void close() throws IOException;
}
```

**异常性能**:
| 操作 | 开销 |
|------|------|
| 抛出异常 | 高（栈展开） |
| 捕获异常 | 中（异常处理表） |
| 正常返回 | 低 |

**最佳实践**:
```java
// 1. 避免在正常流程中使用异常控制
// ❌ 不推荐
try {
    Integer.parseInt(str);
} catch (NumberFormatException e) {
    return defaultValue;
}

// ✅ 推荐
if (isValidNumber(str)) {
    return Integer.parseInt(str);
}
return defaultValue;

// 2. 使用 Try-With-Resources
try (InputStream is = new FileInputStream("file.txt");
     BufferedReader br = new BufferedReader(new InputStreamReader(is))) {
    // 使用资源
} // 自动关闭

// 3. 记录异常时保留原始堆栈
logger.error("处理失败", e);  // 而不是 e.getMessage()

// 4. 自定义异常继承 RuntimeException（除非需要强制处理）
```

**追问**:
- "为什么 checked exception 有争议？" → 可能污染调用链，实际很少真正处理
- "finally 在 return 前执行吗？" → 是，但 return 的值会先保存

**评分标准**:
- 5 分: 清楚异常层次，理解 try-with-resources 原理，知道异常链
- 4 分: 知道异常分类，了解最佳实践
- 3 分: 知道 try-catch-finally
- 2 分: 只说"处理异常"
- 1 分: 不清楚

---

### Q9: JDK 动态代理 vs CGLIB 代理原理及性能对比

**考察点**: AOP 底层实现

**参考答案**:

**JDK 动态代理**:
```java
// 代理类结构（简化）
public class $Proxy0 extends Proxy implements UserService {
    private Method m3;  // sayHello 方法
    
    public String sayHello(String name) {
        try {
            // 调用 InvocationHandler
            return (String) h.invoke(this, m3, new Object[]{name});
        } catch (...) {}
    }
}

// 创建代理
UserService proxy = (UserService) Proxy.newProxyInstance(
    userService.getClass().getClassLoader(),
    new Class[]{UserService.class},
    new InvocationHandler() {
        public Object invoke(Object proxy, Method method, Object[] args) {
            // 前置增强
            Object result = method.invoke(target, args);
            // 后置增强
            return result;
        }
    }
);
```

**CGLIB 代理**:
```java
// 生成子类字节码
public class UserService$$EnhancerByCGLIB$$xxx extends UserService {
    private MethodInterceptor interceptor;
    
    public String sayHello(String name) {
        // 调用拦截器
        return (String) interceptor.intercept(this, 
            m3, new Object[]{name}, 
            super::sayHello);
    }
}

// 创建代理
UserService proxy = (UserService) new 
    Enhancer().create(UserService.class, interceptor);
```

**两者对比**:
| 特性 | JDK 动态代理 | CGLIB |
|------|-------------|-------|
| 原理 | 反射 + 接口 | 字节码生成 + 继承 |
| 目标类要求 | 必须实现接口 | 无要求（不能是 final） |
| 性能（JDK 8） | 较慢 | 较快 |
| 性能（JDK 9+） | 大幅提升 | 下降 |
| Spring 选择 | 有接口优先使用 | 无接口时使用 |

**JDK 9+ 性能提升原因**:
- 引入 MethodHandle 替代反射
- 动态类生成使用 LambdaMetafactory
- 减少反射开销

**Spring AOP 代理策略**:
```java
@Configuration
@EnableAspectJAutoProxy(proxyTargetClass = false)  // 默认：JDK 代理
// proxyTargetClass = true：强制 CGLIB
```

**追问**:
- "为什么 CGLIB 不能代理 final 类？" → 无法继承
- "Spring Boot 2.x 为什么默认用 CGLIB？" → 简化配置，无需接口

**评分标准**:
- 5 分: 清楚代理原理，能对比性能差异，了解 JDK 9 优化
- 4 分: 知道代理两种实现，了解 Spring 选择策略
- 3 分: 知道动态代理概念
- 2 分: 只说"AOP 实现"
- 1 分: 不清楚

---

### Q10: CompletableFuture 异步编程、组合模式、异常处理

**考察点**: 现代异步编程

**参考答案**:

**基本用法**:
```java
// 异步执行
CompletableFuture<String> future = CompletableFuture
    .supplyAsync(() -> fetchData(), executor);

// 结果处理
future.thenApply(result -> process(result))
      .thenAccept(System.out::println)
      .exceptionally(e -> handleError(e));
```

**组合模式**:
```java
// allOf: 所有任务完成
CompletableFuture.allOf(f1, f2, f3)
    .thenRun(() -> System.out.println("All done"));

// anyOf: 任一任务完成
CompletableFuture.anyOf(f1, f2, f3)
    .thenApply(result -> use(result));

// thenCombine: 组合两个结果
CompletableFuture<String> f1 = CompletableFuture.supplyAsync(() -> "Hello");
CompletableFuture<String> f2 = CompletableFuture.supplyAsync(() -> "World");

f1.thenCombine(f2, (s1, s2) -> s1 + " " + s2)
  .thenAccept(System.out::println);  // "Hello World"

// thenCompose: 嵌套异步（flatMap）
f1.thenCompose(s1 -> f2.thenApply(s2 -> s1 + " " + s2))
  .thenAccept(System.out::println);
```

**异常处理**:
```java
CompletableFuture.supplyAsync(() -> {
    if (Math.random() > 0.5) {
        throw new RuntimeException("Error!");
    }
    return "success";
})
.exceptionally(e -> {
    log.error("Async error", e);
    return "fallback";
})
.orTimeout(5, TimeUnit.SECONDS)
.orElse("timeout");
```

**线程池控制**:
```java
// 自定义线程池
Executor executor = Executors.newFixedThreadPool(10);

CompletableFuture.supplyAsync(() -> task(), executor)
                 .thenApplyAsync(result -> process(result), executor)
                 .exceptionallyAsync(e -> handleError(e), executor);
```

**性能陷阱**:
| 问题 | 表现 | 解决方案 |
|------|------|---------|
| 线程饥饿 | 异步任务阻塞线程池 | 使用专用线程池 |
| 异常丢失 | 静默失败 | 使用 exceptionally |
| 回调地狱 | 代码复杂 | 使用 compose/combine |

**追问**:
- "Future 和 CompletableFuture 的区别？" → Future 只能阻塞获取，Completable 支持链式组合
- "如何取消 CompletableFuture？" → cancel() + isCancelled()

**评分标准**:
- 5 分: 清楚组合模式，能处理异常和超时，知道性能陷阱
- 4 分: 知道基本用法，了解异常处理
- 3 分: 知道异步编程概念
- 2 分: 只说"异步任务"
- 1 分: 不清楚


---

## 二、Go 基础问答题库（8 题）

---

### Q11: Go Scheduler 源码级分析，G/M/P 调度流程

**考察点**: Go 运行时深度理解

**参考答案**:

**GMP 模型详解**:
```go
// runtime/src/runtime/proc.go

// P 结构体
type p struct {
    lock mutex
    
    runqhead uintptr           // 运行队列头
    runqtail uintptr           // 运行队列尾
    runq     [256]guintptr     // 本地队列（256个G）
    sudogcache []*sudog        // 等待队列缓存
    sudogbuf [128]*sudog
    
    palloc persistentAlloc     // 物理内存分配器
    
    deferpool [5]deferfrag     // defer 缓存
    deferpoolbuf [32]*_defer   // defer 池
    
    tracebuf traceBufPtr
    traceSweep int32
    
    m          muintptr        // 绑定的 M
    id         int32           // P ID
    nmidlelocked int32          //  locked 的 M 数量
    status     uint32          // P 状态
    link       puintptr
        
    schedtick    uint32       // 调度计数
    syscalltick  uint32       // 系统调用计数
    sysmonlock   mutex        
    lastpoll   uint64         // 上次 poll 时间
    
    btfsig       uint32
    defersp      unsafe.Pointer
    checkpoints  int32
}

// M 结构体
type m struct {
    g0      *g          // 栈底 G（系统栈）
    curg    *g          // 当前执行的 G
    runningg *g         // 正在运行的 G
    
    p          puintptr    // 绑定的 P（0 表示无绑定）
    nextp      puintptr
    id         int32
    
    sched      sigcontext   // 寄存器保存
    
    preempt      bool       // 抢占标志
    preemptStop  bool       // 停止抢占
    preemptOff   bool       // 关闭抢占
    preemptGen   uint32     // 抢占代数
    
    castalign    *typemap   // 类型映射
}

// G 结构体
type g struct {
    stack       stack      // 栈信息
    stackguard0 uintptr   // 栈保护（防止溢出）
    stackguard1 uintptr   // 栈保护（ARM64）
    
    fp          uintptr   // 帧指针
    lr          uintptr   // 链接寄存器
    pc          uintptr   // 程序计数器
    
    gopc        uintptr   // g 创建者的 PC
    startpc     uintptr   // g 开始执行的 PC
    
    racectx     uintptr
    
    waiting   *whead     // 等待队列
    casinfo   casinfo
    
    lockedint muintptr   // 锁定的 M
    
    m            muintptr  // 当前绑定的 M
    stktopsp     uintptr   // 栈顶虚指针
    
    param        unsafe.Pointer  // 参数传递
    atomicstatus uint32       // 原子状态
    waitreason   waitReason   // 等待原因
    
    gcscavengeuint32    // gc 扫描标记
    gcscanvalid  bool     // gc 扫描有效
}
```

**调度流程（schedtick 计数）**:
```
每 10ms 触发一次调度检查：
1. goexit：G 执行完毕，清理资源
2. yield：主动让出 CPU
3. preempt：抢占调度（Go 1.14+）
4. stop：GOMAXPROCS 变化
```

**workstealing（工作窃取）**:
```
当 P 的本地队列为空时：
1. 从其他 P 的队列窃取一半任务
2. 从全局队列获取任务
3. 阻塞等待（如果所有队列都为空）
```

**Syscall 处理**:
```
G 发起系统调用 → M 放弃 P → 创建新 M 执行 syscall
 syscall 返回 → G 重新入队 → M 被回收或等待
```

**抢占机制（Go 1.14+）**:
```
1. 每个 G 执行约 10ms 后检查抢占标志
2. 如果设置抢占，在安全点（ safepoint ）停止
3. 保存寄存器状态，切换到其他 G
```

**追问题**:
- "GOMAXPROCS 默认值是多少？" → 等于 CPU 核数
- "goroutine 栈大小可变吗？" → 是，初始 2KB，最大 1GB

**评分标准**:
- 5 分: 清楚 GMP 交互，能解释 workstealing 和 syscall 处理
- 4 分: 知道调度流程，了解抢占机制
- 3 分: 知道基本概念
- 2 分: 只说"轻量级线程"
- 1 分: 不清楚

---

### Q12: Go GC 算法详解，三色标记法，写屏障原理

**考察点**: Go 运行时 GC 深度

**参考答案**:

**GC 算法演进**:
| Go 版本 | GC 算法 | STW 时间 |
|---------|---------|---------|
| Go 1.3 | 并发标记清除 | ~100ms |
| Go 1.5 | 并发标记 + 并行清除 | ~10ms |
| Go 1.8 | 混合写屏障 | < 1ms |
| Go 1.12 | Pacer 算法优化 | < 1ms |

**三色标记法**:
```
白色：尚未扫描
灰色：已扫描但子节点未扫描
黑色：已扫描且子节点已扫描

扫描过程:
1. 从根节点出发，标记为灰色
2. 扫描灰色对象的字段，将其标记为灰色，自身转为黑色
3. 重复直到没有灰色对象
4. 白色对象不可达，可回收
```

**写屏障（Write Barrier）**:
```go
// 混合写屏障伪代码
func writeBarrier(old, new *obj) {
    // 1. 如果 old 是白色，记录到白对象集合
    if isWhite(old) {
        whiteObjectSet.add(old)
    }
    // 2. 写入新值
    *old = new
    // 3. 如果 new 是白色，标记为灰色
    if isWhite(new) {
        markAsGray(new)
    }
}
```

**三个不变式**:
| 不变式 | 说明 |
|--------|------|
| I1 | 灰色对象指向的对象要么是灰色，要么是黑色 |
| I2 | 根节点直接指向的对象要么是灰色，要么是黑色 |
| I3 | 扫描过程中不会出现白色对象被黑色对象引用的情况 |

**STW 阶段**:
```
1. 世界静止（World Stop）：暂停所有 G
2. 更新根集合（Root Set）：记录所有根节点
3. 重置标记状态
4. 恢复世界运行（World Run）
5. 并发标记阶段
6. 并发清除阶段
```

**GC 调优参数**:
```bash
# 查看 GC 统计
go tool trace <trace_file>
go tool pprof http://localhost:6060/debug/pprof/heap

# 控制 GC 行为
GOGC=100          # GC 触发阈值（默认 100，即内存增长 100% 时触发）
GOMEMLIMIT=1gb    # 内存限制
GODEBUG=gctrace=1 # 打印 GC 日志
GOGC=off          # 禁用 GC（会导致内存持续增长）
```

**GC 触发条件**:
```go
// gcTriggerTotal 类型
type gcTrigger struct {
    kind gcTriggerKind
    n    int64
}

// 触发类型：
// gcTriggerTime: 时间触发（后台 GC）
// gcTriggerCycle: 周期触发
// gcTriggerHeap: 堆内存触发（默认）
// gcTriggerTest: 测试触发
```

**追问题**:
- "为什么 Go GC 停顿时间短？" → 混合写屏障 + 并发标记
- "GOGC=off 有什么风险？" → 内存持续增长，可能导致 OOM

**评分标准**:
- 5 分: 清楚三色标记和写屏障原理，能解释 STW 阶段
- 4 分: 知道并发标记清除，了解 GC 调优参数
- 3 分: 知道是 GC 回收内存
- 2 分: 只说"自动回收"
- 1 分: 不了解

---

### Q13: Go Interface 底层实现，iface 和 eface 结构

**考察点**: Go 类型系统深度

**参考答案**:

**Interface 数据结构**:
```go
// runtime/src/runtime/type.go

// 带方法的 interface
type iface struct {
    itab *itab    // 接口表
    data unsafe.Pointer  // 数据指针
}

// 不带方法的 interface（interface{}）
type eface struct {
    _type *_type
    data  unsafe.Pointer
}

// 接口表
type itab struct {
    inter *interfacetype  // 接口类型
    _type *_type         // 具体类型
    hash  uint32          // 类型 hash
    _     [4]byte
    fun   [1]uintptr      // 方法指针数组（变长）
}
```

**Interface 赋值过程**:
```go
var w io.Writer = os.Stdout

// 编译后等价于：
var w iface
w.itab = findItab(*type (*io.Writer)(nil), *type (*os.File)(nil))
w.data = unsafe.Pointer(&os.Stdout)

// findItab 查找或创建 itab
```

**动态类型与动态值**:
```go
var i interface{} = 42

// i 的底层结构：
// _type = int 的类型描述符
// data = &42（指向值为 42 的内存地址）

// 类型断言
v, ok := i.(int)  // 检查动态类型是否为 int
```

**空接口优化**:
```go
// Go 1.20+ 的空接口优化
// 小值直接存储在 eface.data 中，避免堆分配

var i interface{} = 42
// 编译后：
var i eface
i._type = typeOf(int)
i.data = &42  // 栈上分配

// 大值仍然需要堆分配
var j interface{} = make([]int, 1000)
// j.data 指向堆上的 slice 头
```

**追问题**:
- "interface{} 和任何类型都有相同的大小吗？" → 是，iface 固定 16 字节（64 位）
- "如何判断 interface 是否为 nil？" → itab 和 data 都为 nil

**评分标准**:
- 5 分: 清楚 iface/eface 结构，理解 itab 查找过程
- 4 分: 知道接口底层结构，了解动态类型
- 3 分: 知道 interface 存储类型和值
- 2 分: 只说"空接口存储任意类型"
- 1 分: 不清楚

---

### Q14: Go 内存分配器 TCMalloc 风格实现，mcache/mcentral/mheap

**考察点**: Go 运行时内存管理

**参考答案**:

**内存分配层级**:
```
┌─────────────────────────────────────────────┐
│                 Mheap                       │  ← 物理内存管理
│  （管理 Span，分配给 MCentral）              │
├─────────────────────────────────────────────┤
│               Mcentral                      │  ← 对象池管理
│  （管理 Class，缓存 Span）                   │
├─────────────────────────────────────────────┤
│                Mcache                       │  ← 线程私有缓存
│  （快速分配，无锁）                          │
├─────────────────────────────────────────────┤
│                 Thread                      │  ← Goroutine
└─────────────────────────────────────────────┘
```

**Span 结构**:
```go
type span struct {
    startsize ptrdiff
    npages    uint32      // 页数
    flags     spanFlags
    gcdata    *byte        // GC 扫描数据
    
    // 对象大小分类
    allocitmap [2]bitmap   // 位图，标记哪些对象已分配
    allocCount uint16      // 已分配对象数
    
    // free list
    freeindex   uintptr     // 空闲对象索引
    nelems      uintptr     // 对象总数
    allocnpages uintptr     // 占用页数
}
```

**Size Class（对象大小分类）**:
```
Size Class 0:  0-8 bytes      (Stack 分配)
Size Class 1:  8-16 bytes
...
Size Class 62: > 32MB        (直接分配，不缓存)

每级跨度约 15%，保证内存利用率 > 85%
```

**分配流程**:
```
1. 线程私有 Mcache 查找对应 Size Class
   └── 有空闲对象 → 直接返回（无锁，极快）
   └── 无空闲对象 → 向 Mcentral 申请
                      └── 有空闲 Span → 返回
                      └── 无空闲 Span → 向 Mheap 申请
                                                   └── 有内存 → 分配新 Span
                                                   └── 无内存 → 向 OS 申请
```

**Mcache 优化**:
```go
// 每个 P 拥有独立的 Mcache
// 避免锁竞争，提升性能

type mcache struct {
    small [numSmallSizeClasses]*mspan  // 小对象缓存
    large [maxLargeSize]**byte         // 大对象缓存
}
```

**追问题**:
- "大对象（>32MB）如何分配？" → 直接通过 Mheap 分配，不经过 Mcache
- "如何实现垃圾回收时的内存整理？" → Sweep 阶段回收 Span

**评分标准**:
- 5 分: 清楚分配层级，能解释 Span 管理和 Size Class
- 4 分: 知道 Mcache/Mcentral/Mheap 三级结构
- 3 分: 知道内存分配基本流程
- 2 分: 只说"自动管理内存"
- 1 分: 不清楚


---

## 三、通用基础问答题库（5 题）

---

### Q15: TCP 拥塞控制算法详解，慢启动、拥塞避免、快重传、快恢复

**考察点**: 网络协议深度理解

**参考答案**:

**拥塞控制四个算法**:
```
cwnd (拥塞窗口) 变化过程:

时间 →
    │ 慢启动阶段
    ├──────────────────────────────────┐
    │  ssthresh = cwnd/2               │
    │  拥塞避免阶段                      │
    ├──────────────────────────────────┤
    │  快重传 + 快恢复                  │
    └──────────────────────────────────┘
    
cwnd: 拥塞窗口
ssthresh: 慢启动阈值
```

**慢启动（Slow Start）**:
```go
// 初始 cwnd = 1 MSS
// 每 RTT 指数增长：1 → 2 → 4 → 8 → ...
func slowStart(cwnd, ssthresh uint32) uint32 {
    if cwnd < ssthresh {
        return cwnd * 2  // 指数增长
    }
    return cwnd
}
```

**拥塞避免（Congestion Avoidance）**:
```go
// 线性增长：每 RTT +1
func congestionAvoidance(cwnd, ssthresh uint32) uint32 {
    if cwnd >= ssthresh {
        return cwnd + 1/cwnd  // 缓慢线性增长
    }
    return slowStart(cwnd, ssthresh)
}
```

**快重传（Fast Retransmit）**:
```
发送端收到 3 个重复 ACK → 立即重传丢失报文段
（无需等待 RTO 超时）

序列号: 1  2  3  4  5
        ↓  ↓  ↓  ↓  ↓
接收:  ACK2 ACK2 ACK2 ACK2 ACK6
                ↑
          3个重复ACK触发快重传
```

**快恢复（Fast Recovery）**:
```go
func fastRecovery(cwnd, ssthresh uint32) uint32 {
    ssthresh = cwnd / 2
    cwnd = ssthresh + 3  // 加3是因为收到3个重复ACK
    // 进入拥塞避免阶段
    return cwnd
}
```

**TCP 版本对比**:
| 算法 | 特点 | 适用场景 |
|------|------|---------|
| Reno | 传统算法 | 一般场景 |
| Cubic | 立方增长函数 | 高带宽延迟产品 |
| BBR | 基于带宽建模 | 现代数据中心 |

**BBR 算法**:
```go
// Google 开发的 BBR 算法
// 核心思想：找到网络的瓶颈带宽和最小 RTT
func bbrProbeBW() {
    // 1. 填充阶段：快速探测带宽
    // 2. 瓶颈带宽估计：测量 delivering_rate
    // 3. 最小 RTT 估计：测量 min_rtt
    // 4. 输出速率控制：cwnd = pacing_rate * min_rtt
}
```

**追问题**:
- "TCP 和 UDP 有什么区别？" → 连接性、可靠性、 ordering
- "QUIC 为什么用 UDP？" → 避免队头阻塞，减少握手延迟

**评分标准**:
- 5 分: 清楚四个算法，能画出 cwnd 变化图，了解 BBR
- 4 分: 知道慢启动和拥塞避免
- 3 分: 只记得"拥塞控制"
- 2 分: 不清楚
- 1 分: 完全不知道

---

### Q16: Raft 一致性算法详解，Leader 选举、日志复制、安全性

**考察点**: 分布式系统核心理论

**参考答案**:

**Raft 三要素**:
```
1. Leader 选举
2. 日志复制
3. 安全性保证
```

**任期（Term）概念**:
```
Term: 逻辑时钟，单调递增
 Election Timeout: 随机超时，触发选举
 Voter: 未投票给任何人
 Candidate: 正在竞选 Leader
 Leader: 已当选的 Leader
 Follower: 普通节点
```

**Leader 选举流程**:
```
1. Follower 超时 → 转为 Candidate
2. 投票给自己，开始选举
3. 向其他节点发送 RequestVote RPC
4. 获得多数票 → 成为 Leader
5. 失败 → 增加 Term，重新开始选举

选举约束：
- 每个 Term 只能投一票
- 候选人必须拥有所有已提交条目的日志
- 日志较新的节点优先当选
```

**日志复制流程**:
```
Client → Leader → Followers → Commit

1. Client 发送请求到 Leader
2. Leader 追加日志条目
3. Leader 广播 AppendEntries RPC
4. Follower 确认成功
5. Leader 收到多数确认后 commit
6. Leader 应用日志到状态机
7. 返回结果给 Client
```

**安全性保证**:
| 属性 | 保证 |
|------|------|
| Election Restriction | 候选人必须包含所有已提交条目 |
| Leader Completeness | Leader 包含所有已提交条目 |
| State Machine Safety | 相同 index 的 entry 具有相同的 command |

**故障转移**:
```
1. Leader 故障：
   - Follower 超时 → 选举新 Leader
   - 新 Leader 补全缺失日志
   
2. Follower 故障：
   - Leader 重试 AppendEntries
   - Follower 恢复后追赶日志
   
3. Network Partition：
   - 多数派形成新 Leader
   - 少数派等待恢复
```

**追问题**:
- "Raft 和 Paxos 的区别？" → Raft 更易理解，分为子问题
- "如何实现线性一致读？" → ReadIndex 机制

**评分标准**:
- 5 分: 清楚选举和日志复制流程，理解安全性保证
- 4 分: 知道 Raft 基本原理
- 3 分: 只听说过分布式一致性
- 2 分: 不清楚
- 1 分: 完全不知道

---

### Q17: 分布式事务实现方案，2PC、3PC、TCC、Saga 对比

**考察点**: 分布式系统事务处理

**参考答案**:

**2PC（两阶段提交）**:
```
Coordinator                    Participant 1    Participant 2
     │                              │                │
     │── 1. Prepare(tx) ──────────►│                │
     │                              │                │
     │◄── 2. Prepared/Abort ────────┤                │
     │                              │                │
     │── 3. Prepare(tx) ───────────────────────────►│
     │                              │                │
     │◄── 4. Prepared/Abort ────────────────────────┤
     │                              │                │
     │  收到多数 Prepared？         │                │
     ├── Yes ── 5. Commit ────────►│                │
     │                            │                │
     │                            │── 5. Commit ───►│
     │                            │                │
     └── No ── 6. Abort ─────────►│                │
                                  │── 6. Abort ────►│
```

**问题**:
- 同步阻塞：参与者执行期间阻塞
- 单点故障：Coordinator 崩溃导致数据不一致
- 脑裂：网络分区导致部分节点 commit，部分 abort

**3PC（三阶段提交）改进**:
```
1. CanCommit：询问是否可以提交
2. PreCommit：预提交，写入日志
3. DoCommit：正式提交
```

**TCC（Try-Confirm-Cancel）**:
```
Try: 预留资源
     - 冻结账户余额
     - 锁定库存
     
Confirm: 确认执行
     - 扣除余额
     - 扣减库存
     
Cancel: 取消操作
     - 解冻余额
     - 恢复库存
```

**Saga 模式**:
```
Long-running 事务分解为多个本地事务
每个本地事务有对应的补偿操作

订单创建 → 库存扣减 → 支付 → 发货

补偿：
支付失败 → 库存回滚 → 订单取消
```

**方案对比**:
| 方案 | 强一致性 | 性能 | 复杂性 | 适用场景 |
|------|---------|------|--------|---------|
| 2PC | ✅ | 差 | 低 | 数据库事务 |
| 3PC | ✅ | 中 | 中 | 较少使用 |
| TCC | ✅ | 好 | 高 | 金融交易 |
| Saga | ⚠️ 最终 | 好 | 中 | 长事务 |

**追问题**:
- "如何保证 Saga 的幂等性？" → 唯一业务 ID + 状态检查
- "TCC 的 NULL 操作是什么？" → Try 未执行时的补偿

**评分标准**:
- 5 分: 清楚各方案原理，能分析优缺点和适用场景
- 4 分: 知道 2PC 和 Saga
- 3 分: 只听说过分布式事务
- 2 分: 不清楚
- 1 分: 完全不知道

---

### Q18: CAP 定理、BASE 理论、分布式一致性模型

**考察点**: 分布式系统理论基础

**参考答案**:

**CAP 定理**:
```
C: Consistency（一致性）
   所有节点同时看到相同数据
   
A: Availability（可用性）
   每个请求都能在合理时间内收到响应
   
P: Partition Tolerance（分区容错性）
   网络分区时系统仍能工作

结论：只能同时满足两个
```

**CP 系统**:
```
MySQL 集群、ZooKeeper、HBase

特点：
- 保证数据强一致
- 网络分区时可能不可用
- 适合金融、交易场景
```

**AP 系统**:
```
Cassandra、Dynamo、Eureka

特点：
- 保证高可用
- 允许最终一致
- 适合社交、内容场景
```

**BASE 理论**:
```
B: Basically Available（基本可用）
   出现故障时保证核心功能可用
   
S: Soft State（软状态）
   允许数据存在中间状态
   
E: Eventually Consistent（最终一致）
   数据最终会达到一致状态
```

**一致性模型**:
| 模型 | 说明 | 示例 |
|------|------|------|
| 强一致 | 所有节点同时可见 | 分布式锁 |
| 因果一致 | 因果关系可见 | 消息队列 |
| 会话一致 | 同一会话内一致 | Session 存储 |
| 单调读 | 读取不会后退 | CDN 缓存 |
| 单调写 | 写入按顺序 | 日志系统 |
| 最终一致 | 无保证，但会收敛 | Dynamo |

**追问题**:
- "PACELC 定理是什么？" → CAP 的扩展，考虑无分区时的延迟和一致性权衡
- "如何实现跨数据中心一致性？" → 多主复制、CRDT

**评分标准**:
- 5 分: 清楚 CAP 定理，能解释 BASE 和一致性模型
- 4 分: 知道 CAP 和 BASE
- 3 分: 只听说过一致性概念
- 2 分: 不清楚
- 1 分: 完全不知道

---

### Q19: MySQL InnoDB 索引结构，聚簇索引、二级索引、覆盖索引

**考察点**: 数据库底层原理

**参考答案**:

**InnoDB 存储引擎结构**:
```
┌─────────────────────────────────────────────┐
│                   Buffer Pool               │  ← 内存缓存
├─────────────────────────────────────────────┤
│                   Log Buffer                │  ←  redo log
├─────────────────────────────────────────────┤
│                 Tablespace                  │  ← 数据文件
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │ Segment  │  │ Extent   │  │ Page     │  │
│  │ (段)     │─▶│ (区)     │─▶│ (页)     │  │
│  └──────────┘  └──────────┘  └──────────┘  │
└─────────────────────────────────────────────┘
```

**B+ 树索引结构**:
```
        ┌─────┐
        │ Root│  ← 非叶子节点（索引页）
        └──┬──┘
       ┌───┴───┐
       ▼       ▼
  ┌────────┐ ┌────────┐
  │Leaf 1  │ │Leaf 2  │  ← 叶子节点（数据页）
  └───┬────┘ └───┬────┘
      ▼          ▼
  [数据]      [数据]
```

**聚簇索引（Clustered Index）**:
```sql
-- InnoDB 默认使用主键作为聚簇索引
CREATE TABLE users (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(50),
    age INT,
    -- 数据存储在叶子节点
    INDEX idx_id (id)  -- 聚簇索引
);
```

**二级索引（Secondary Index）**:
```sql
-- 二级索引的叶子节点存储主键值
CREATE INDEX idx_name ON users(name);

-- 回表查询：二级索引 → 主键 → 聚簇索引
SELECT * FROM users WHERE name = 'Alice';
```

**覆盖索引（Covering Index）**:
```sql
-- 查询只需要访问索引，不需要回表
SELECT id, name FROM users WHERE name = 'Alice';

-- 联合索引优化
CREATE INDEX idx_name_age ON users(name, age);
-- 左前缀原则：idx_name_age 可以优化 name 和 name+age 查询
```

**索引优化建议**:
| 场景 | 方案 |
|------|------|
| 高基数列 | 建立索引 |
| 低基数列 | 不建索引（如性别） |
| 前缀匹配 | 使用最左前缀 |
| 排序优化 | 索引order by |
| 分页优化 | 延迟关联 |

**追问题**:
- "什么情况下索引会失效？" → 函数、类型转换、LIKE '%xx'
- "如何分析查询性能？" → EXPLAIN + performance_schema

**评分标准**:
- 5 分: 清楚 B+ 树结构，理解聚簇/二级索引，知道覆盖索引
- 4 分: 知道索引类型和基本用法
- 3 分: 只说"建立索引加速查询"
- 2 分: 不清楚
- 1 分: 完全不知道

---

### Q20: Elasticsearch 倒排索引原理，分片策略，查询优化

**考察点**: 搜索引擎底层原理

**参考答案**:

**倒排索引结构**:
```
正向索引：文档 → 关键词列表
倒排索引：关键词 → 文档ID列表

文档 1: "the quick brown fox"
文档 2: "the lazy dog"
文档 3: "the quick red fox"

倒排索引：
"the"    → [1, 2, 3]
"quick"  → [1, 3]
"brown"  → [1]
"fox"    → [1, 3]
"lazy"   → [2]
"dog"    → [2]
"red"    → [3]
```

**Lucene 实现**:
```
Term Dictionary（字典）:
┌─────────┬──────────┬──────────┐
│  Term   │ Postings │  Bytes   │
├─────────┼──────────┼──────────┤
│ brown   │     1    │  xxx     │
│ dog     │     2    │  xxx     │
│ fox     │   1,3    │  xxx     │
│ lazy    │     2    │  xxx     │
│ quick   │   1,3    │  xxx     │
│ the     │ 1,2,3    │  xxx     │
└─────────┴──────────┴──────────┘

Postings File（ postings 文件）:
┌─────────┬─────────────────────────┐
│  Term   │ DocumentIDs + Positions │
├─────────┼─────────────────────────┤
│ brown   │ doc[1]: pos[0]          │
│ dog     │ doc[2]: pos[1]          │
│ fox     │ doc[1]:pos[3], doc[3]:pos[4]│
└─────────┴─────────────────────────┘
```

**分片策略**:
```json
{
  "settings": {
    "number_of_shards": 5,
    "number_of_replicas": 1,
    "refresh_interval": "30s"
  },
  "mappings": {
    "properties": {
      "title": {
        "type": "text",
        "analyzer": "ik_smart"
      },
      "status": {
        "type": "keyword"
      }
    }
  }
}
```

**查询优化**:
| 优化点 | 方案 |
|--------|------|
| 避免深分页 | use_search_after |
| 字段类型选择 | keyword vs text |
| 分析器选择 | 根据语言选择 |
| 缓存利用 | request cache, query cache |
| 分片大小 | 单分片 30-50GB |

**追问题**:
- "ES 是如何实现近实时的？" → 默认 1s refresh_interval
- "如何处理海量数据？" → 分片 + 副本 + 冷热分离

**评分标准**:
- 5 分: 清楚倒排索引原理，能设计分片策略，知道优化方法
- 4 分: 知道倒排索引概念
- 3 分: 只说"搜索引擎"
- 2 分: 不清楚
- 1 分: 完全不知道


---

## 四、Redis 深度问答题库（5 题）

---

### Q21: Redis 持久化机制详解，RDB vs AOF 对比及混合持久化

**考察点**: Redis 数据可靠性

**参考答案**:

**RDB（快照）**:
```bash
# 触发方式
1. SAVE：阻塞主进程，生成快照
2. BGSAVE：后台fork子进程生成快照
3. 自动触发：配置save规则

# 触发条件示例
save 900 1      # 900秒内至少1个key变化
save 300 10     # 300秒内至少10个key变化
save 60 10000   # 60秒内至少10000个key变化

# 恢复
cp dump.rdb /var/lib/redis/
redis-server --dir /var/lib/redis
```

**RDB 优缺点**:
| 优点 | 缺点 |
|------|------|
| 文件紧凑，恢复快 | 可能丢失最后一次快照的数据 |
| 适合备份 | fork 子进程消耗内存 |
| 性能影响小 | 不能实时持久化 |

**AOF（追加日志）**:
```bash
# 配置
appendonly yes
appendfsync everysec    # 每秒同步（推荐）
# appendfsync always    # 每次修改同步（最安全，性能差）
# appendfsync no        # OS 控制同步（性能最好，可能丢数据）

# AOF 重写
CONFIG REWRITE          # 手动触发
auto-aof-rewrite-percentage 100  # AOF 增长 100% 时触发
auto-aof-rewrite-min-size 64mb   # AOF 最小 64MB 才触发
```

**AOF 重写流程**:
```
1. 父进程继续处理命令
2. fork 子进程执行重写
3. 子进程遍历内存，生成新 AOF
4. 父进程将新命令写入 aof_buf
5. 子进程完成后，父进程写入 aof_buf
6. 替换旧 AOF 文件
```

**AOF 优缺点**:
| 优点 | 缺点 |
|------|------|
| 数据更安全 | 文件比 RDB 大 |
| 每秒同步，最多丢 1 秒 | 恢复速度比 RDB 慢 |
| 命令格式可读 | 性能开销略大 |

**混合持久化（Redis 4.0+）**:
```bash
aof-use-rdb-preamble yes
```

```
AOF 文件结构:
┌─────────────────┬─────────────────┐
│   RDB 快照部分   │   AOF 增量部分  │
│   （二进制压缩）  │   （命令日志）   │
└─────────────────┴─────────────────┘

优点：
- 恢复速度快（类似 RDB）
- 数据安全高（类似 AOF）
```

**追问题**:
- "如何选择持久化策略？" → 根据业务容忍度
- "Redis 重启后如何恢复？" → 先加载 RDB，再追加 AOF

**评分标准**:
- 5 分: 清楚 RDB/AOF 原理，能分析优缺点，理解混合持久化
- 4 分: 知道两种持久化方式
- 3 分: 只说"有持久化"
- 2 分: 不清楚
- 1 分: 完全不知道

---

### Q22: Redis 集群原理，槽分配、节点选举、数据路由

**考察点**: Redis 分布式架构

**参考答案**:

**Redis Cluster 架构**:
```
┌─────────────────────────────────────────────────────┐
│                    Redis Cluster                     │
├─────────────────────────────────────────────────────┤
│  Node 1 (Master)    Node 2 (Master)    Node 3 (Master)│
│  Slots: 0-5460      Slots: 5461-10922   Slots: 10923-16383 │
│  ┌────────┐         ┌────────┐         ┌────────┐   │
│  │Replica │         │Replica │         │Replica │   │
│  └────────┘         └────────┘         └────────┘   │
└─────────────────────────────────────────────────────┘
```

**槽分配算法**:
```
总槽数：16384
哈希函数：CRC16(key) % 16384

客户端计算：
hash = crc16("mykey") % 16384
slot = hash
if slot < 5461:    → Node 1
elif slot < 10923: → Node 2
else:              → Node 3
```

**节点通信协议**:
```
Gossip 协议：
- ping/pong 消息交换节点信息
- 每个节点维护其他节点的地址和状态
- 节点故障检测：失联超过 cluster-node-timeout

故障转移：
1. Master 故障，Slave 感知
2. Slave 请求其他节点投票
3. 获得多数票后提升为 Master
4. 接管原 Master 的槽
```

**数据路由**:
```go
// 客户端路由
func (c *ClusterClient) getSlot(key string) int {
    // 提取槽号
    hash := crc16.Checksum([]byte(key), crc16.MakeTable(crc16.ECMACDSA))
    return int(hash % 16384)
}

// MOVED 重定向
func handleMOVED(err error) {
    // 解析 MOVED slot new_address
    // 更新客户端缓存
}

// ASK 临时重定向
func handleASK(err error) {
    // 解析 ASK slot address
    // 临时转发请求
}
```

**追问题**:
- "如何扩容集群？" → 新增节点，迁移槽
- "双写一致性如何保证？" → 主从复制 + 故障转移

**评分标准**:
- 5 分: 清楚槽分配和故障转移，理解 Gossip 协议
- 4 分: 知道集群基本概念
- 3 分: 只说"分片存储"
- 2 分: 不清楚
- 1 分: 完全不知道

---

### Q23: Redis 内存淘汰策略，缓存穿透/击穿/雪崩解决方案

**考察点**: Redis 高级应用

**参考答案**:

**内存淘汰策略**:
| 策略 | 说明 | 适用场景 |
|------|------|---------|
| noeviction | 不淘汰，返回错误 | 必须保证数据完整 |
| allkeys-lru | 全键 LRU 淘汰 | 通用缓存 |
| volatile-lru | 有过期时间的键 LRU | 热点数据 |
| allkeys-lfu | 全键 LFU 淘汰 | 访问频率重要的场景 |
| volatile-lfu | 有过期时间的键 LFU | 热点数据 |
| volatile-ttl | 按 TTL 淘汰 | 临时数据 |

**LRU 实现优化**:
```go
// Redis 使用近似 LRU 算法
// 而不是精确 LRU（避免额外开销）

type approxLRU struct {
    poolSize int      // 候选池大小
    sample int       // 采样数量
}

func (a *approxLRU)Evict(keys []string) string {
    // 随机采样 poolSize 个键
    candidates := sampleRandomKeys(keys, a.sample)
    // 从候选中淘汰最近访问时间最长的
    return evictOldest(candidates)
}
```

**缓存穿透**:
```
问题：查询不存在的数据，每次请求都打到数据库
解决方案：
1. 布隆过滤器：查询前判断是否存在
2. 缓存空值：null 也缓存，设置短过期时间
3. 参数校验：拦截非法参数
```

```go
// 布隆过滤器实现
type BloomFilter struct {
    bitSet *bitset.BitSet
    hashCount int
}

func (b *BloomFilter)Add(key string) {
    for i := 0; i < b.hashCount; i++ {
        hash := hash(key, i)
        b.bitSet.Set(hash % b.bitSet.Len())
    }
}

func (b *BloomFilter)MaybeContains(key string) bool {
    for i := 0; i < b.hashCount; i++ {
        hash := hash(key, i)
        if !b.bitSet.Test(hash % b.bitSet.Len()) {
            return false  // 一定不存在
        }
    }
    return true  // 可能存在
}
```

**缓存击穿**:
```
问题：热点 key 过期，并发请求打到数据库
解决方案：
1. 互斥锁：只有一个请求查数据库，其他等待
2. 逻辑过期：不设置 TTL，程序控制过期
3. 永不过期：配合后台异步更新
```

```go
// 互斥锁实现
func GetWithMutex(key string) (*Data, error) {
    // 1. 尝试从缓存获取
    data := cache.Get(key)
    if data != nil {
        return data, nil
    }
    
    // 2. 获取互斥锁
    mutex, ok := getMutex(key)
    if !ok {
        return fallback(), nil
    }
    defer mutex.Unlock()
    
    // 3. 双重检查
    data = cache.Get(key)
    if data != nil {
        return data, nil
    }
    
    // 4. 查询数据库并缓存
    data = queryDB(key)
    cache.Set(key, data, ttl)
    return data, nil
}
```

**缓存雪崩**:
```
问题：大量 key 同时过期，请求打到数据库
解决方案：
1. TTL 加随机值：避免同时过期
2. 多级缓存：本地缓存 + Redis
3. 限流降级：保护后端
4. 高可用：Redis Cluster
```

```go
// TTL 加随机值
func setWithRandomTTL(key string, value interface{}, baseTTL time.Duration) {
    // 随机增加 0-30% 的 TTL
    randomTTL := time.Duration(float64(baseTTL) * (1.0 + rand.Float64() * 0.3))
    cache.Set(key, value, randomTTL)
}
```

**追问题**:
- "如何监控 Redis 性能？" → slowlog + latency command
- "Redis 6.0 多线程是什么？" → 网络 I/O 多线程

**评分标准**:
- 5 分: 清楚淘汰策略，能分析三种问题并给出解决方案
- 4 分: 知道缓存穿透/击穿/雪崩的概念
- 3 分: 只说"加缓存"
- 2 分: 不清楚
- 1 分: 完全不知道

---

### Q24: Redis 哨兵模式原理，主从切换流程，数据一致性保证

**考察点**: Redis 高可用架构

**参考答案**:

**哨兵架构**:
```
┌──────────────────────────────────────────────┐
│                  Sentinels                    │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐     │
│  │Sentinel1│  │Sentinel2│  │Sentinel3│     │
│  └────┬────┘  └────┬────┘  └────┬────┘     │
│       │             │             │          │
│       └─────────────┴─────────────┘          │
│                    │                         │
│              投票选举                          │
│                    │                         │
├────────────────────┼─────────────────────────┤
│                    ▼                         │
│            ┌───────────┐                     │
│            │  Master   │                     │
│            │  (Redis)  │                     │
│            └─────┬─────┘                     │
│                  │ replication               │
│            ┌─────┴─────┐                    │
│            ▼           ▼                    │
│      ┌──────────┐ ┌──────────┐              │
│      │ Replica1 │ │ Replica2 │              │
│      └──────────┘ └──────────┘              │
└──────────────────────────────────────────────┘
```

**哨兵核心功能**:
| 功能 | 说明 |
|------|------|
| 监控 | 定期检查 Master/Replica 是否可达 |
| 通知 | 将结果发送给管理员或其他服务 |
| 自动故障转移 | Master 故障时选举新 Master |
| 配置提供者 | 客户端连接哨兵获取 Master 地址 |

**主观下线（SDOWN）→ 客观下线（ODOWN）**:
```
1. 哨兵 A 发现 Master 不可达 → SDOWN
2. 哨兵 A 询问其他哨兵 → 是否也认为 Master 不可达
3. 达到 quorum（多数派）→ ODOWN
4. 开始故障转移流程
```

**故障转移流程**:
```
1. 选中一个 Sentinel 作为 leader
2. 从 Replica 中选择一个作为新 Master
   - 选择标准：
     a. 复制偏移量最大（数据最新）
     b. run_id 最短（优先级高）
     c. 复制进度最快
3. 发送 SLAVEOF NO ONE 命令
4. 其他 Replica 指向新 Master
5. 更新配置
```

**数据一致性保证**:
```go
// Redis 复制是异步的
// 可能出现数据不一致

// 解决方案：
// 1. min-replicas-to-write：最小从节点数
// 2. min-replicas-max-lag：最大延迟
// 3. write-quorum：写入多数派确认

// 配置示例
min-replicas-to-write 1
min-replicas-max-lag 10
```

**追问题**:
- "哨兵和集群有什么区别？" → 哨兵是高可用方案，集群是分布式方案
- "如何解决脑裂？" → quorum 机制 + fencing token

**评分标准**:
- 5 分: 清楚哨兵原理，能画出故障转移流程
- 4 分: 知道哨兵的作用
- 3 分: 只说"高可用"
- 2 分: 不清楚
- 1 分: 完全不知道

---

### Q25: Redis 分布式锁高级用法，Redlock 算法及争议

**考察点**: Redis 高级应用场景

**参考答案**:

**基本分布式锁**:
```java
// SET key value NX EX seconds
String lockKey = "lock:" + resourceId;
Boolean acquired = redisTemplate.opsForValue()
    .setIfAbsent(lockKey, uuid, 10, TimeUnit.SECONDS);

// 释放锁（Lua 脚本保证原子性）
String script = 
    "if redis.call('get', KEYS[1]) == ARGV[1] then " +
    "return redis.call('del', KEYS[1]) else return 0 end";
redisTemplate.execute(new DefaultRedisScript<>(script, Long.class),
    Collections.singletonList(lockKey), uuid);
```

**看门狗机制（Redisson）**:
```java
// 自动续期，防止业务未执行完锁已过期
RLock lock = redisson.getLock("myLock");
lock.lock();  // 默认 30s 过期，每 10s 续期
try {
    // 业务逻辑
} finally {
    lock.unlock();
}
```

**Redlock 算法（多节点）**:
```java
// 至少 N/2 + 1 个节点成功才算成功
public class Redlock {
    private final List<RedissonClient> clients;
    private final int quorum;
    private final long expireTime;
    
    public boolean lock(String lockName, String value) {
        long start = System.currentTimeMillis();
        int successfullySet = 0;
        
        for (RedissonClient client : clients) {
            RLock lock = client.getLock(lockName);
            if (lock.tryLock(100, expireTime, TimeUnit.MILLISECONDS)) {
                successfullySet++;
            }
        }
        
        long elapsed = System.currentTimeMillis() - start;
        if (successfullySet >= quorum && elapsed < expireTime) {
            // 锁获取成功
            return true;
        }
        
        // 失败则释放所有已获取的锁
        for (RedissonClient client : clients) {
            RLock lock = client.getLock(lockName);
            if (lock.isHeldByCurrentThread()) {
                lock.unlock();
            }
        }
        return false;
    }
}
```

**Redlock 争议**:
| 支持方 | 反对方 |
|--------|--------|
| 提高了可用性 | 时钟回拨可能导致重复执行 |
| 相比单点更安全 | 实现复杂度高 |
| 大多数场景够用 | 需要谨慎使用 |

**替代方案**:
```
1. ZooKeeper 分布式锁（强一致，CP 系统）
2. Etcd 分布式锁（强一致，CP 系统）
3. 业务层幂等设计（最终方案）
```

**追问题**:
- "时钟回拨会导致什么问题？" → 锁提前过期，多个客户端同时持有
- "如何选择分布式锁方案？" → 根据一致性要求选择

**评分标准**:
- 5 分: 清楚 Redlock 原理，了解争议和替代方案
- 4 分: 知道基本分布式锁实现
- 3 分: 只说"用 Redis 做锁"
- 2 分: 不清楚
- 1 分: 完全不知道


---

## 五、Kafka 深度问答题库（5 题）

---

### Q26: Kafka 架构原理，Producer/Consumer/Broker 工作机制

**考察点**: 消息队列底层原理

**参考答案**:

**Kafka 核心概念**:
```
Topic: 消息分类
Partition: Topic 的物理分片
Offset: 消息在 Partition 中的位置
Replica: Partition 的副本
Leader: 处理读写请求的副本
Follower: 同步 Leader 数据的副本
ISR: In-Sync Replicas（与 Leader 同步的副本集合）
ZK: ZooKeeper（协调元数据）
```

**Producer 工作流程**:
```
1. 生产者发送消息到 Topic
2. 计算消息所属 Partition（key 哈希）
3. 批量发送（batch.size + linger.ms）
4. 等待 Broker 确认（acks 配置）
5. 失败重试（retries）

配置示例：
acks=all              # 所有副本确认
retries=Integer.MAX   # 无限重试
batch.size=16384      # 批量大小 16KB
linger.ms=10          # 等待 10ms 凑 batch
```

**Consumer 工作流程**:
```
1. Consumer Group 订阅 Topic
2. Partition 分配到 Consumer
3. 拉取消息（poll）
4. 处理消息
5. 提交偏移量（commit）

消费模式：
- 独占消费：一个 Partition 只能被一个 Consumer 消费
- 广播消费：每个 Consumer 都能收到所有消息（不同 Group）
```

**Broker 工作机制**:
```
┌─────────────────────────────────────┐
│              Broker                 │
├─────────────────────────────────────┤
│  Partition 0    Partition 1         │
│  ┌─────┐        ┌─────┐             │
│  │Leader│        │Leader│            │
│  │ISR   │        │ISR   │            │
│  └─────┘        └─────┘             │
│                                     │
│  Log 分段存储：                      │
│  topic-partition-0.log              │
│  topic-partition-0.index            │
│  topic-partition-1.log              │
│  ...                                │
└─────────────────────────────────────┘
```

**追问题**:
- "如何保证消息不丢失？" → acks=all + 副本机制
- "如何保证消息顺序性？" → 同一 key 路由到同一 Partition

**评分标准**:
- 5 分: 清楚 Producer/Consumer/Broker 全流程
- 4 分: 知道基本概念
- 3 分: 只说"消息队列"
- 2 分: 不清楚
- 1 分: 完全不知道

---

### Q27: Kafka 高吞吐原理，零拷贝、顺序写、Page Cache

**考察点**: Kafka 性能优化原理

**参考答案**:

**零拷贝（Zero Copy）**:
```
传统 I/O:
CPU → 用户缓冲区 → 内核缓冲区 → DMA → 网卡
      (read)       (write)

零拷贝:
DMA → 内核缓冲区 → mmap → 网卡
      (sendfile)

节省：
- 2 次用户态/内核态切换
- 2 次内存拷贝
```

**顺序写磁盘**:
```
随机写：磁盘头来回移动，寻道时间 ~5ms
顺序写：磁盘头连续移动，带宽可达 100MB/s+

Kafka 写入优化：
1. 日志分段追加
2. 页缓存预分配
3. mmap 映射文件
```

**Page Cache 利用**:
```
Linux 内核维护页缓存
Kafka 利用 OS 页缓存作为缓冲区
读取时直接从页缓存返回
写入时异步 flush 到磁盘

优势：
- 避免重复拷贝
- 利用 OS 缓存优化
```

**批量发送优化**:
```java
// Producer 配置
props.put("batch.size", 16384);     // 16KB 批量
props.put("linger.ms", 10);         // 等待 10ms 凑批
props.put("compression.type", "lz4"); // LZ4 压缩
```

**追问题**:
- "Kafka 为什么比 RabbitMQ 吞吐高？" → 顺序写 + 零拷贝
- "如何调优 Kafka 性能？" → batch.size、linger.ms、压缩

**评分标准**:
- 5 分: 清楚零拷贝原理，能解释性能优化机制
- 4 分: 知道顺序写和批量发送
- 3 分: 只说"高效消息队列"
- 2 分: 不清楚
- 1 分: 完全不知道

---

### Q28: Kafka 消息可靠性保证，Exactly-Once 语义实现

**考察点**: 消息可靠性深度理解

**参考答案**:

**消息不丢失保障**:
```
Producer 端：
acks=all + retries=MAX + idempotent=true

Broker 端：
min.insync.replicas=2 + unclean.leader.election=false

Consumer 端：
enable.auto.commit=false + 手动提交
```

**幂等 Producer**:
```java
Properties props = new Properties();
props.put("enable.idempotence", true);  // 启用幂等
props.put("acks", "all");
props.put("max.in.flight.requests.per.connection", 5);
```

**事务 Producer**:
```java
// 开启事务
producer.initTransactions();
producer.beginTransaction();

try {
    // 发送消息
    producer.send(record1);
    producer.send(record2);
    
    // 提交事务
    producer.commitTransaction();
} catch (Exception e) {
    producer.abortTransaction();
}
```

**Exactly-Once 语义**:
```
端到端 Exactly-Once 实现：

1. Source 端：从 Kafka 读取，offset 事务性提交
2. Processing 端：状态更新在事务中
3. Sink 端：写入 Kafka，使用幂等写或事务

关键：幂等写 + 事务提交
```

**Consumer 手动提交**:
```java
// 手动提交确保消息处理完成
while (true) {
    ConsumerRecords<String, String> records = 
        consumer.poll(Duration.ofMillis(100));
    
    for (ConsumerRecord<String, String> record : records) {
        process(record);  // 处理消息
    }
    
    // 提交偏移量（确保已处理的消息不再重消费）
    consumer.commitSync();
}
```

**追问题**:
- "为什么需要手动提交？" → 避免消息丢失或重复
- "事务消息有什么开销？" → 性能下降约 10-20%

**评分标准**:
- 5 分: 清楚端到端可靠性保障，理解 Exactly-Once 实现
- 4 分: 知道 acks=all 和手动提交
- 3 分: 只说"消息会重试"
- 2 分: 不清楚
- 1 分: 完全不知道

---

### Q29: Kafka 分区策略，消息顺序性保证，重平衡机制

**考察点**: Kafka 高级特性

**参考答案**:

**分区策略**:
```java
// 默认分区器
public int partition(String topic, Object key, 
                     byte[] keyBytes, Object value, 
                     byte[] valueBytes, Cluster cluster) {
    List<PartitionInfo> partitions = 
        cluster.partitionsForTopic(topic);
    int numPartitions = partitions.size();
    
    if (keyBytes == null) {
        // 无 key 时轮询
        return stickyCounter.incrementAndGet() % numPartitions;
    }
    
    // 有 key 时哈希取模
    return Utils.toPositive(Utils.murmur2(keyBytes)) 
           % numPartitions;
}
```

**顺序性保证**:
```
问题：消费者多线程消费会导致乱序
解决：单线程消费或维护分区内顺序

方案 1：单 Consumer 线程
consumer.subscribe(topic, 
    new ConsumerRebalanceListener() {
        public void onPartitionsAssigned(...) {
            // 每个分区分配一个单线程消费者
        }
    });

方案 2：分区内排序
producer.send(record, 
    (metadata, exception) -> {
        // 检查分区分配
    });
```

**重平衡（Rebalance）**:
```
触发条件：
1. Consumer 加入/离开 Group
2. Topic Partition 数量变化
3. Consumer 超时（session.timeout.ms）

重平衡过程：
1. Coordinator 协调
2. 重新分配 Partition
3. 提交当前 offset
4. 恢复消费

优化：
- 增大 session.timeout.ms
- 使用 static membership
- 避免频繁扩缩容
```

**Consumer Group 分配策略**:
| 策略 | 说明 | 适用场景 |
|------|------|---------|
| RangeAssignor | 按范围分配 | 分区数少 |
| RoundRobinAssignor | 轮询分配 | 均匀分布 |
| StickyAssignor | 最小化移动 | 生产环境 |

**追问题**:
- "如何避免重平衡？" → 使用 static membership
- "如何保证全局有序？" → 单 Partition

**评分标准**:
- 5 分: 清楚分区策略和重平衡机制
- 4 分: 知道顺序性保证方法
- 3 分: 只说"分区和消费者"
- 2 分: 不清楚
- 1 分: 完全不知道

---

### Q30: Kafka 性能调优，Producer/Consumer/Broker 配置详解

**考察点**: Kafka 生产环境配置

**参考答案**:

**Producer 调优**:
```properties
# 批量发送
batch.size=32768           # 32KB 批量
linger.ms=20               # 等待 20ms 凑批
compression.type=lz4       # LZ4 压缩

# 可靠性
acks=all                   # 所有副本确认
retries=Integer.MAX        # 无限重试
max.in.flight.requests=5   # 允许 5 个未确认请求

# 内存
buffer.memory=67108864     # 64MB 缓冲区
```

**Consumer 调优**:
```properties
# 拉取策略
fetch.min.bytes=1048576    # 至少 1MB 数据再返回
fetch.max.wait.ms=500      # 最多等待 500ms
max.poll.records=500       # 每次最多 500 条

# 会话控制
session.timeout.ms=30000   # 30s 会话超时
heartbeat.interval.ms=10000 # 10s 心跳
```

**Broker 调优**:
```properties
# 网络
num.network.threads=8      # 网络线程数
num.io.threads=16          # IO 线程数
socket.send.buffer.bytes=102400
socket.receive.buffer.bytes=102400

# 磁盘
num.partitions=6           # 默认分区数
log.segment.bytes=1073741824 # 1GB 段大小
log.retention.hours=168    # 7 天保留

# 内存
pagecache.allocation.size=1073741824 # 1GB 页缓存
```

**监控指标**:
| 指标 | 说明 | 阈值 |
|------|------|------|
| Under-replicated | 副本不足 | 0 |
| Offline partitions | 离线分区 | 0 |
| Failed mutations | 写入失败 | 0 |
| Under-min-isr | ISR 不足 | 0 |

**追问题**:
- "如何监控 Kafka 集群？" → JMX + Prometheus + Grafana
- "如何处理消息积压？" → 扩容 Consumer

**评分标准**:
- 5 分: 清楚各组件调优参数，能分析监控指标
- 4 分: 知道基本调优方向
- 3 分: 只说"调整参数"
- 2 分: 不清楚
- 1 分: 完全不知道

---

## 六、Agent 认知深度题库（7 题）

---

### A6: LLM 训练流程详解，预训练、微调、RLHF

**参考答案**:

**预训练（Pre-training）**:
```
数据：海量文本（Common Crawl、Books、Wikipedia）
目标：预测下一个 token（自回归）
模型：Transformer decoder-only
训练：分布式训练，数百个 GPU

损失函数：
L = -Σ log P(token_t | token_1...token_{t-1})
```

**微调（Fine-tuning）**:
```
方法 1: Supervised Fine-tuning (SFT)
- 高质量指令数据
- 让模型学会遵循指令

方法 2: Reinforcement Learning from Human Feedback (RLHF)
- 训练奖励模型（Reward Model）
- PPO 算法优化策略

方法 3: Direct Preference Optimization (DPO)
- 直接优化偏好数据
- 无需显式奖励模型
```

**RLHF 流程**:
```
1. 收集人类偏好数据
   (prompt, response_a, response_b, preference)

2. 训练奖励模型
   R(prompt, response) → 标量分数

3. PPO 强化学习
   Policy: 最大化 R(prompt, response)
   
4. 对齐人类价值观
```

**追问题**:
- "LoRA 是什么？" → Low-Rank Adaptation，低秩适配
- "为什么 RLHF 成本高？" → 需要大量人工标注

**评分标准**:
- 5 分: 清楚训练全流程，理解 RLHF 原理
- 4 分: 知道预训练和微调的区别
- 3 分: 只听说过大模型训练
- 2 分: 不清楚
- 1 分: 完全不知道

---

### A7: Embedding 模型原理，向量检索优化，HNSW 算法

**参考答案**:

**Embedding 模型**:
```
输入：文本
输出：固定维度向量（如 1536 维）

原理：
- 训练目标：相似文本的向量距离近
- 模型架构：BERT、GPT、专用 Embedding 模型

常用模型：
- text-embedding-ada-002 (OpenAI)
- BGE-M3 (阿里)
- mxbai-embed-large
```

**向量检索优化**:
```
暴力搜索：O(n) - 精确但慢
近似搜索：O(log n) - 近似但快

算法：
1. IVF（倒排文件）: 先聚类再搜索
2. HNSW（分层导航小世界）: 图遍历
3. PQ（乘积量化）: 压缩向量
```

**HNSW 算法**:
```
图结构：
- 多层图，顶层稀疏，底层密集
- 搜索时从顶层开始，逐渐细化

构建：
1. 随机选择入口节点
2. 按距离插入节点
3. 保持图的连通性

查询：
1. 从入口节点开始
2. 贪心搜索最近邻
3. 逐步细化到更底层
```

**追问题**:
- "如何选择向量数据库？" → 根据规模和需求
- "HNSW 的参数如何调优？" → M（连接数）、efSearch（搜索深度）

**评分标准**:
- 5 分: 清楚 Embedding 原理和 HNSW 算法
- 4 分: 知道向量检索的基本方法
- 3 分: 只说"相似度搜索"
- 2 分: 不清楚
- 1 分: 完全不知道

---

### A8: Agent 工具调用链设计，错误处理，重试策略

**参考答案**:

**工具调用链**:
```
User Request
    ↓
┌─────────────────┐
│  Intent Router  │  ← 判断是否需要工具调用
└────────┬────────┘
         ↓
┌─────────────────┐
│  Tool Selector  │  ← 选择合适的工具
└────────┬────────┘
         ↓
┌─────────────────┐
│  Tool Executor  │  ← 执行工具调用
└────────┬────────┘
         ↓
┌─────────────────┐
│  Result Parser  │  ← 解析结果
└────────┬────────┘
         ↓
┌─────────────────┐
│  Response Gen   │  ← 生成最终回答
└─────────────────┘
```

**错误处理**:
```python
class ToolCallError(Exception):
    """工具调用错误基类"""
    pass

class ToolRetryPolicy:
    """重试策略"""
    def __init__(self, max_retries=3, backoff=2.0):
        self.max_retries = max_retries
        self.backoff = backoff
    
    def should_retry(self, error: ToolCallError, attempt: int) -> bool:
        if attempt >= self.max_retries:
            return False
        if isinstance(error, TransientError):
            return True
        return False
    
    def get_delay(self, attempt: int) -> float:
        return self.backoff ** attempt
```

**重试策略类型**:
| 策略 | 说明 | 适用场景 |
|------|------|---------|
| 固定间隔 | 每次等待相同时间 | 简单场景 |
| 指数退避 | 等待时间指数增长 | 临时故障 |
| 抖动退避 | 随机化等待时间 | 避免雪崩 |

**追问题**:
- "如何处理工具调用的超时？" → 设置超时 + 降级策略
- "如何保证工具调用的幂等性？" → 唯一请求 ID + 去重

**评分标准**:
- 5 分: 清楚工具调用链设计，能设计错误处理和重试策略
- 4 分: 知道基本的工具调用流程
- 3 分: 只说"调用工具"
- 2 分: 不清楚
- 1 分: 完全不知道

---

### A9: Multi-Agent 系统设计，通信协议，任务分解

**参考答案**:

**通信协议**:
```
1. Message Passing
   Agent A → [Message] → Agent B
   
2. Shared Memory
   Agent A → [Write to DB] → Agent B reads
   
3. Broadcast
   Agent A → [Announce] → All Agents
   
4. Request-Response
   Agent A → [Request] → Agent B → [Response] → Agent A
```

**任务分解策略**:
```
分解方式 1: 按功能模块
┌─────────┐  ┌─────────┐  ┌─────────┐
│ Research│──▶│  Writer │──▶│ Reviewer│
└─────────┘  └─────────┘  └─────────┘

分解方式 2: 按并行任务
         ┌─────────┐
         │ Research│
         └────┬────┘
      ┌────────┼────────┐
      ▼        ▼        ▼
┌─────────┐ ┌─────────┐ ┌─────────┐
│ Writer A│ │Writer B │ │Writer C │
└────┬────┘ └────┬────┘ └────┬────┘
     └───────────┼───────────┘
                 ▼
          ┌─────────┐
          │  Editor │
          └─────────┘
```

**追问题**:
- "如何避免 Agent 间的循环依赖？" → DAG 任务图
- "如何监控多 Agent 系统？" → 分布式追踪

**评分标准**:
- 5 分: 清楚多 Agent 系统设计，能设计通信和任务分解
- 4 分: 知道多 Agent 协作的概念
- 3 分: 只说"多个 Agent"
- 2 分: 不清楚
- 1 分: 完全不知道

---

### A10: Agent 评估体系，RAGAS 框架，自动化测试

**参考答案**:

**RAGAS 评估维度**:
```
1. 上下文召回率（Context Recall）
   检索的文档是否包含答案的所有信息

2. 上下文精准率（Context Precision）
   检索的文档中有多少是相关的

3. 答案忠实度（Answer Faithfulness）
   生成的答案是否基于检索的上下文

4. 答案相关性（Answer Relevance）
   生成的答案是否回答了用户的问题
```

**评估方法**:
```python
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy

# 准备数据集
dataset = Dataset.from_dict({
    "question": [...],
    "answer": [...],
    "contexts": [...],
    "ground_truth": [...]
})

# 评估
result = evaluate(dataset, metrics=[faithfulness, answer_relevancy])
print(result)
```

**自动化测试**:
```
1. 单元测试：每个工具的正确性
2. 集成测试：Agent 端到端流程
3. 回归测试：确保新功能不影响旧功能
4. 性能测试：延迟、吞吐量
```

**追问题**:
- "如何量化 Agent 效果？" → 定义评估指标
- "如何处理 bad case？" → 收集 → 分析 → 改进

**评分标准**:
- 5 分: 清楚评估体系，能设计测试策略
- 4 分: 知道评估的基本概念
- 3 分: 只说"测试效果"
- 2 分: 不清楚
- 1 分: 完全不知道


---

## 七、场景分析深度题库（5 题）

---

### 场景 6: 实时推荐系统设计（详细答案）

**背景**:
> 设计一个电商推荐系统，要求：
> - 实时性：用户行为秒级响应
> - 准确性：推荐精准
> - 可扩展：支持亿级用户

**问题**: 如何设计实时推荐系统？

**参考答案**:

**系统架构**:
```
┌─────────────────────────────────────────────────────────────┐
│                     实时推荐系统                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  用户行为采集                                                │
│  ├── 点击流 → Kafka → Flink → Redis (实时特征)              │
│  ├── 订单数据 → Kafka → Spark (离线特征)                    │
│  └── 用户画像 → HBase / Redis                              │
│                                                             │
│  特征工程                                                    │
│  ├── 实时特征：最近 1 小时行为                              │
│  ├── 离线特征：历史行为统计                                 │
│  └── 物品特征：类目、价格、销量                             │
│                                                             │
│  召回层                                                      │
│  ├── 协同过滤：ItemCF / UserCF                             │
│  ├── 深度学习：DIN / DIEN                                  │
│  ├── 热门召回：Hot Items                                   │
│  └── 地理召回：Nearby Items                                │
│                                                             │
│  排序层                                                      │
│  ├── 粗排：浅层模型快速筛选                                 │
│  ├── 精排：DeepFM / DCN 模型打分                           │
│  └── 重排：MMR / 多样性优化                                │
│                                                             │
│  服务层                                                      │
│  ├── 特征服务：Featurize API                               │
│  ├── 模型服务：TensorFlow Serving                          │
│  └── 缓存层：Redis (推荐结果缓存)                          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**关键技术点**:

| 模块 | 技术选型 | 说明 |
|------|---------|------|
| 实时特征 | Flink + Redis | 窗口聚合，实时更新 |
| 离线特征 | Spark + HBase | 批量计算，历史特征 |
| 召回算法 | Graph Embedding | Node2Vec / DeepWalk |
| 排序模型 | DeepFM / DCN | 特征交叉 |
| 服务部署 | TensorFlow Serving | 高并发推理 |

**召回策略优化**:
```python
# 多路召回融合
def multi_recall(user_id, context):
    recalls = []
    
    # 1. 协同过滤召回
    cf_recall = collaborative_filtering(user_id, k=50)
    recalls.extend(cf_recall)
    
    # 2. 热门召回
    hot_recall = hot_items(time_window='1h')
    recalls.extend(hot_recall)
    
    # 3. 地理召回
    geo_recall = nearby_items(user_location)
    recalls.extend(geo_recall)
    
    # 去重并限制数量
    return deduplicate(recalls)[:100]
```

**追问题**:
- "如何处理冷启动？" → 热门推荐 + 内容特征
- "如何评估推荐效果？" → A/B 测试 + 离线指标

---

### 场景 7: 订单系统分布式事务设计（详细答案）

**背景**:
> 电商平台订单系统，涉及库存扣减、支付、物流多个服务，如何保证数据一致性？

**问题**: 如何设计分布式事务方案？

**参考答案**:

**方案设计对比**:

| 方案 | 一致性 | 性能 | 复杂度 | 适用场景 |
|------|--------|------|--------|---------|
| 2PC | 强一致 | 差 | 低 | 数据库事务 |
| TCC | 强一致 | 好 | 高 | 金融交易 |
| Saga | 最终 | 好 | 中 | 长事务 |
| 本地消息表 | 最终 | 好 | 中 | 通用场景 |

**推荐方案：本地消息表 + Saga**:
```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│ 订单服务  │───▶│ 库存服务  │───▶│ 支付服务  │───▶│ 物流服务  │
└────┬─────┘    └────┬─────┘    └────┬─────┘    └────┬─────┘
     │               │               │               │
     ▼               ▼               ▼               ▼
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│消息表    │    │消息表    │    │消息表    │    │消息表    │
└──────────┘    └──────────┘    └──────────┘    └──────────┘
```

**实现细节**:
```java
// 订单服务
@Transactional
public void createOrder(Order order) {
    // 1. 创建订单
    orderDao.insert(order);
    
    // 2. 发送本地消息
    localMessageDao.insert(new LocalMessage(
        "ORDER_CREATED", 
        order.getId(),
        order.getUserId()
    ));
}

// 消息补偿任务
@Scheduled(fixedDelay = 5000)
public void processPendingMessages() {
    List<LocalMessage> messages = localMessageDao
        .findPendingMessages();
    
    for (LocalMessage msg : messages) {
        try {
            // 发送消息到 MQ
            kafkaTemplate.send("order-events", msg.getPayload());
            // 标记已发送
            localMessageDao.markSent(msg.getId());
        } catch (Exception e) {
            // 记录失败，等待重试
            log.error("Send message failed", e);
        }
    }
}
```

**补偿事务**:
```java
// 支付失败补偿
public void compensatePayment(Long orderId) {
    // 1. 恢复库存
    inventoryService.restore(orderId);
    
    // 2. 取消订单
    orderService.cancel(orderId);
    
    // 3. 发送通知
    notificationService.send(order.getUserId(), 
        "订单已取消，库存已恢复");
}
```

**追问题**:
- "如何保证消息不丢失？" → 本地消息表 + 重试机制
- "如何处理补偿失败？" → 人工介入 + 告警

---

### 场景 8: 大规模日志系统架构设计（详细答案）

**背景**:
> 设计一个日采集 10TB 日志的系统，要求实时查询、历史归档、成本可控。

**参考答案**:

**架构设计**:
```
应用层
  ├── App Server (日志 SDK)
  └── 日志格式统一

采集层
  ├── Filebeat / Fluentd (轻量采集)
  └── Logstash (复杂解析)

传输层
  └── Kafka (消息队列)

存储层
  ├── Elasticsearch (热数据 7 天)
  ├── ClickHouse (分析数据 30 天)
  ├── HDFS / S3 (冷数据归档)
  └── Redis (会话数据)

查询层
  ├── Kibana (日志查看)
  ├── Grafana (监控看板)
  └── API (自定义查询)

告警层
  └── AlertManager (异常告警)
```

**存储策略**:
| 数据类型 | 存储引擎 | 保留周期 | 说明 |
|---------|---------|---------|------|
| 热数据 | Elasticsearch | 7 天 | 实时查询 |
| 温数据 | ClickHouse | 30 天 | 分析查询 |
| 冷数据 | S3/HDFS | 长期 | 归档备份 |

**索引优化**:
```json
{
  "settings": {
    "number_of_shards": 5,
    "number_of_replicas": 1,
    "refresh_interval": "30s"
  },
  "mappings": {
    "properties": {
      "timestamp": { "type": "date" },
      "level": { "type": "keyword" },
      "service": { "type": "keyword" },
      "message": { 
        "type": "text",
        " analyzer": "ik_smart"
      },
      "trace_id": { "type": "keyword" }
    }
  }
}
```

**成本控制**:
| 策略 | 说明 |
|------|------|
| 采样采集 | 非关键日志采样 10% |
| 字段过滤 | 只采集必要字段 |
| 生命周期管理 | 自动删除旧数据 |
| 冷热分离 | 热数据 SSD，冷数据 HDD |

**追问题**:
- "如何保证日志不丢失？" → Kafka 持久化 + 多副本
- "如何处理日志洪峰？" → 流量整形 + 削峰填谷

---

### 场景 9: 金融交易系统高可用设计（详细答案）

**背景**:
> 设计一个股票交易系统，要求 99.999% 可用性，延迟 < 1ms。

**参考答案**:

**架构设计**:
```
┌─────────────────────────────────────────────────────┐
│                   交易系统架构                       │
├─────────────────────────────────────────────────────┤
│                                                     │
│  接入层                                              │
│  ├── 多层负载均衡                                    │
│  ├── 防火墙 + DDoS 防护                              │
│  └── 限流熔断                                        │
│                                                     │
│  计算层                                              │
│  ├── 行情解析（FPGA 加速）                          │
│  ├── 策略计算（内存计算）                            │
│  └── 订单路由                                        │
│                                                     │
│  存储层                                              │
│  ├── 订单撮合（内存撮合引擎）                        │
│  ├── 持仓管理（分布式缓存）                          │
│  └── 交易日志（分布式日志）                          │
│                                                     │
│  外部接口                                            │
│  ├── 交易所连接（专线）                              │
│  └── 银行接口（冗余连接）                            │
│                                                     │
└─────────────────────────────────────────────────────┘
```

**高可用设计**:
| 层级 | 策略 | 说明 |
|------|------|------|
| 网络 | 双线路 + BGP 切换 | 主备线路自动切换 |
| 主机 | 双活数据中心 | 跨机房部署 |
| 数据库 | 主从 + 自动故障转移 | RPO ≈ 0 |
| 缓存 | Redis Cluster | 无单点故障 |
| 消息 | Kafka 多副本 | 消息不丢失 |

**性能优化**:
```
1. 内存计算：避免磁盘 IO
2. 零拷贝：减少数据拷贝
3. 硬件加速：FPGA 行情解析
4. 网络优化：TCP 调优 + 拥塞控制
5. 代码优化：避免锁竞争
```

**监控告警**:
| 指标 | 阈值 | 告警级别 |
|------|------|---------|
| 延迟 P99 | > 1ms | Critical |
| 成功率 | < 99.99% | Critical |
| 队列深度 | > 1000 | Warning |
| 错误率 | > 0.01% | Critical |

**追问题**:
- "如何实现微秒级延迟？" → 内核绕过 + 硬件加速
- "如何处理交易所断连？" → 本地缓存 + 重连机制

---

### 场景 10: AI 训练集群资源调度设计（详细答案）

**背景**:
> 设计一个支持 GPU 训练的集群调度系统，支持数百张 GPU，多租户隔离。

**参考答案**:

**系统架构**:
```
┌─────────────────────────────────────────────────────┐
│                  调度管理层                          │
├─────────────────────────────────────────────────────┤
│                                                     │
│  调度器（Kubernetes + Volcano）                      │
│  ├── 资源申请解析                                    │
│  ├── GPU 拓扑感知调度                                │
│  ├── 队列管理（优先级）                              │
│  └── 抢占式调度                                      │
│                                                     │
│  资源管理层                                          │
│  ├── GPU 池化                                       │
│  ├── NVLink 拓扑感知                                │
│  └── 故障检测                                        │
│                                                     │
│  训练框架                                            │
│  ├── PyTorch Distributed                             │
│  ├── Horovod                                         │
│  └── DeepSpeed                                      │
│                                                     │
│  监控层                                              │
│  ├── GPU 利用率监控                                  │
│  ├── 网络带宽监控                                    │
│  └── 训练进度跟踪                                    │
│                                                     │
└─────────────────────────────────────────────────────┘
```

**关键设计**:
| 模块 | 方案 | 说明 |
|------|------|------|
| GPU 调度 | Volcano | 支持拓扑感知 |
| 任务抢占 | 优先级队列 | 紧急任务优先 |
| 故障恢复 | 检查点 | 自动恢复 |
| 资源隔离 | Kubernetes Namespace | 多租户隔离 |

**调度优化**:
```yaml
# Kubernetes GPU 调度配置
apiVersion: batch.volcano.sh/v1alpha1
kind: Job
metadata:
  name: training-job
spec:
  minAvailable: 8
  plugins:
    svc: []
    ssh: []
  queue: default
  tasks:
    - replicas: 8
      name: trainer
      spec:
        gpus: 1
        resources:
          limits:
            nvidia.com/gpu: 1
        hostname: trainer-{{vertex_index}}
        hostnetwork: true
```

**追问题**:
- "如何处理 GPU 故障？" → 故障检测 + 任务迁移
- "如何优化通信效率？" → NVLink + 拓扑感知

---

## 八、开放设计题（5 题）

---

### D6: 设计一个支持千亿级数据的向量检索系统（详细答案）

**需求**:
> 设计一个支持千亿级向量检索的系统，要求：
> - 延迟 < 100ms
> - 准确率 > 95%
> - 支持在线更新

**架构设计**:
```
┌─────────────────────────────────────────────────────────────┐
│                    向量检索系统                               │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  接入层                                                      │
│  ├── API Gateway（限流、鉴权）                               │
│  ├── 负载均衡                                                 │
│  └── 缓存层（热点查询缓存）                                   │
│                                                             │
│  索引层                                                      │
│  ├── HNSW 索引（近似搜索）                                   │
│  ├── IVF-PQ 索引（高维压缩）                                 │
│  └── 倒排索引（混合检索）                                     │
│                                                             │
│  存储层                                                      │
│  ├── 向量存储（分布式对象存储）                               │
│  ├── 元数据存储（分布式数据库）                               │
│  └── 索引存储（本地 SSD）                                     │
│                                                             │
│  计算层                                                      │
│  ├── 向量计算（GPU 加速）                                    │
│  ├── 重排序（Cross-Encoder）                                │
│  └── 查询优化（Query Rewriting）                            │
│                                                             │
│  管理层                                                      │
│  ├── 索引构建（离线）                                        │
│  ├── 增量更新（在线）                                        │
│  └── 监控告警                                                │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**核心技术**:
| 技术 | 说明 |
|------|------|
| HNSW | 分层导航小世界图，查询 O(log n) |
| IVF-PQ | 倒排文件 + 乘积量化，压缩向量 |
| GPU 加速 | CUDA 并行计算相似度 |
| 增量索引 | 本地索引 + 定期合并 |

**扩展性设计**:
```
分片策略：
- 按向量 ID 哈希分片
- 每个分片独立索引
- 查询时广播到所有分片

复制策略：
- 每个分片 3 副本
- Leader 处理写，Follower 同步
- 读写分离
```

**追问题**:
- "如何处理向量维度爆炸？" → 降维（PCA/UMAP）
- "如何评估检索效果？" → Recall@K + NDCG

---

### D7: 设计一个实时风控系统（详细答案）

**需求**:
> 设计一个实时风控系统，处理每秒 10 万笔交易，要求：
> - 延迟 < 50ms
> - 规则引擎可配置
> - 支持复杂欺诈检测

**架构设计**:
```
┌─────────────────────────────────────────────────────────────┐
│                    实时风控系统                               │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  交易接入                                                    │
│  ├── Kafka 消费（异步接入）                                  │
│  ├── 消息解析                                                │
│  └── 实时特征计算                                            │
│                                                             │
│  特征引擎                                                    │
│  ├── 实时特征：滑动窗口统计                                  │
│  ├── 离线特征：用户画像                                      │
│  └── 图特征：关系网络                                        │
│                                                             │
│  规则引擎                                                    │
│  ├── 规则配置（可视化）                                      │
│  ├── 规则执行（Drools / 自研）                               │
│  └── 规则版本管理                                            │
│                                                             │
│  模型服务                                                    │
│  ├── 机器学习模型（XGBoost / LightGBM）                     │
│  ├── 深度学习模型（TensorFlow / PyTorch）                   │
│  └── 模型版本管理                                            │
│                                                             │
│  决策中心                                                    │
│  ├── 决策编排                                               │
│  ├── 决策结果合并                                           │
│  └── 结果输出                                               │
│                                                             │
│  响应层                                                      │
│  ├── 实时返回（通过/拒绝/人工审核）                          │
│  ├── 告警通知                                                │
│  └── 事后分析                                                │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**性能优化**:
| 优化点 | 方案 |
|--------|------|
| 特征计算 | Flink 实时窗口 |
| 规则执行 | 规则预编译 + JIT |
| 模型推理 | TensorRT 加速 |
| 缓存策略 | Redis 热点特征缓存 |

**追问题**:
- "如何处理特征延迟？" → 特征预计算 + 缓存
- "如何保证规则热更新？" → 规则热加载

---

### D8: 设计一个大规模分布式爬虫系统（详细答案）

**需求**:
> 设计一个日抓取 10 亿页面的分布式爬虫系统，要求：
> - 去重高效
| 优先级 | 策略 |
|--------|------|
| 高 | 立即抓取 |
| 中 | 延迟抓取 |
| 低 | 定期抓取 |

**追问题**:
- "如何处理 JavaScript 渲染？" → Headless Chrome / Puppeteer
- "如何反反爬？" → 代理池 + 请求伪装

---

## 九、面试记录模板

```markdown
## 面试记录

### 候选人信息
- 姓名: 
- 学校: 
- 专业: 
- 研究方向: 
- 面试日期: 

### 基础问答得分
| 题目 | 得分 | 备注 |
|------|------|------|
| Q__: | | |
| Q__: | | |
| Q__: | | |

### 场景分析得分
| 场景 | 得分 | 备注 |
|------|------|------|
| 场景__: | | |
| 场景__: | | |

### Agent 认知得分
| 题目 | 得分 | 备注 |
|------|------|------|
| A__: | | |
| A__: | | |

### 开放设计得分
| 题目 | 得分 | 备注 |
|------|------|------|
| D__: | | |

### 总分: ___/50
### 录用建议: □强烈推荐 □推荐 □谨慎 □不推荐

### 面试官评语
```

---

**祝面试顺利！** 🎉
