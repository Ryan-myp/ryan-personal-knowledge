# 大数据系统 — Hadoop/Spark 架构、数据管道、流批一体

> 标签: `#大数据` `#Hadoop` `#Spark` `#Flink` `#数据管道` `#流批一体` `#源码级`
> 创建日期: 20260608
> 作者: Ryan

---

## 1. Hadoop 生态系统 — 源码级

### 1.1 HDFS — 源码级

```java
// HDFS 架构（org.apache.hadoop.hdfs）
// 
// NameNode:
public class NameNode implements FSNamesystem {
    private FSImage fsImage;          // 文件系统镜像（fsimage）
    private EditLog editLog;          // 编辑日志
    private BlockManager blockManager; // 块管理
    private DatanodeManager datanodeManager; // 节点管理
    private JournalManager journalManager;   // 日志管理器（HA）
    
    // FsImage:
    // - inode tree: 文件系统树的根节点
    // - 包含所有文件/目录的元数据
    // - 持久化为 fsimage 文件
    // 
    // EditLog:
    // - 记录所有元数据变更操作
    // - CREATE, DELETE, RENAME, SET_PERMISSION 等
    // - 持久化为 edit_log 文件
    // 
    // 合并流程（Checkpoint）:
    // 1. SecondaryNameNode 定期请求 NameNode 的 edit_log
    // 2. 合并 fsImage + editLog → 新的 fsImage
    // 3. 上传到 NameNode 更新
    // 
    // HA 架构（QJM）:
    // - Multiple JournalNodes (至少 3 个)
    // - Active NameNode 写入 editLog 到所有 JNs
    // - Standby NameNode 从 JNs 读取 editLog
    // - 切换时，Active 提交剩余 editLog，Standby 提升
    
    // 元数据操作:
    public void createDirectory(String path, PermissionStatus perm) {
        // 1. 权限检查
        checkPermission(path, perm);
        
        // 2. 检查父目录是否存在
        INode parent = fsDir.getINode(path.getParent());
        if (parent == null) {
            throw new FileNotFoundException("Parent directory not found");
        }
        
        // 3. 创建 inode
        INode newDir = new INodeDirectory(path, perm, now());
        
        // 4. 添加到父目录
        fsDir.addChild(parent, newDir);
        
        // 5. 记录 editLog
        editLog.logCreate(path, newDir);
        
        // 6. 更新 fsImage（内存）
        fsImage.incModCount();
    }
}

// DataNode:
public class DataNode extends AbstractMapRed implements Configurable {
    private BlockPoolSliceScanner blockScanner;  // 块扫描器
    private BlockReceiver blockReceiver;         // 块接收器
    private BlockSender blockSender;             // 块发送器
    private VolumeManager volumeManager;         // 存储管理
    private ReplicationMonitor replicationMonitor; // 副本监控
    
    // 块接收（写流程）:
    public void writeBlock(DatanodeInfo[] targets, ...) {
        // 1. 创建新块
        Block newBlock = new Block(blockId, generationStamp);
        
        // 2. 创建数据流
        DataOutputStream out = new DataOutputStream(
            new BufferedOutputStream(
                volumeManager.createBlock(newBlock)
            )
        );
        
        // 3. 从上游接收数据
        while (hasMoreData) {
            byte[] buffer = readFromUpstream();
            out.write(buffer);
            checksum.update(buffer);
        }
        
        // 4. 关闭数据流
        out.close();
        
        // 5. 发送 ACK 给上游
        sendACK(targets[0]);
    }
    
    // 块复制（副本管理）:
    public void replicateBlock(Block block, DatanodeInfo source, DatanodeInfo target) {
        // 1. 从 source 读取数据
        BlockSender sender = new BlockSender(source, block);
        
        // 2. 写入本地
        BlockReceiver receiver = new BlockReceiver(target, block);
        
        // 3. 数据流传输
        sender.transferTo(receiver);
        
        // 4. 完成复制
        receiver.close();
        sender.close();
    }
}
```

### 1.2 YARN — 资源调度

```java
// YARN 架构（org.apache.hadoop.yarn）
// 
// ResourceManager:
public class ResourceManager {
    private Scheduler scheduler;           // 资源调度器
    private ApplicationsManager appsManager; // 应用管理器
    private NodeManager nodeManager;       // 节点管理器
    private RecoveryService recoveryService; // 恢复服务
    
    // 调度器类型:
    // 1. FIFOScheduler: 先进先出（默认）
    // 2. CapacityScheduler: 容量调度（多队列，公平）
    // 3. FairScheduler: 公平调度（动态公平）
    
    // CapacityScheduler:
    public class CapacityScheduler implements ResourceScheduler {
        private List<Queue> queues; // 队列列表
        
        public Resource allocate(ResourceRequest request) {
            // 1. 选择队列
            Queue queue = selectQueue(request.getQueue());
            
            // 2. 从队列分配资源
            Container container = queue.allocate(request);
            
            // 3. 更新调度器状态
            updateSchedulerState();
            
            return container.getResource();
        }
        
        // 队列资源分配:
        Container allocate(ResourceRequest request) {
            // 1. 检查队列容量上限
            if (queueUsed > queueCapacity) {
                return null;  // 超出容量
            }
            
            // 2. 查找合适的节点
            Node node = findNodeWithResource(request);
            if (node == null) {
                return null;  // 没有足够资源
            }
            
            // 3. 分配容器
            Container container = createContainer(node, request);
            queue.addContainer(container);
            
            return container;
        }
    }
}

// ApplicationMaster:
public class ApplicationMaster implements ResourceManagerProtocol {
    private ContainerAllocator containerAllocator; // 容器分配器
    private ContainerLauncher containerLauncher;   // 容器启动器
    
    // 资源请求流程:
    public void start() {
        // 1. 注册到 ResourceManager
        RegisterApplicationMasterResponse response = 
            resourceManager.register(this);
        
        // 2. 请求资源
        List<ResourceRequest> requests = createResourceRequests();
        
        // 3. 发送资源请求
        List<Container> allocatedContainers = 
            resourceManager.allocate(requests);
        
        // 4. 启动容器
        for (Container container : allocatedContainers) {
            containerLauncher.launch(container);
        }
    }
    
    // 容器分配:
    private List<ResourceRequest> createResourceRequests() {
        List<ResourceRequest> requests = new ArrayList<>();
        
        // 1. 优先请求本地节点（rack-local）
        ResourceRequest request1 = new ResourceRequest(
            ResourceRequest.ANY,        // 任意节点
            getRequiredMemory(),        // 内存要求
            1,                          // 需要 1 个容器
            getRequiredCores()          // 核心要求
        );
        requests.add(request1);
        
        // 2. 如果本地不够，请求 rack-local
        ResourceRequest request2 = new ResourceRequest(
            getPreferredRack(),         // 首选机架
            getRequiredMemory(),
            2,                          // 需要 2 个容器
            getRequiredCores()
        );
        requests.add(request2);
        
        // 3. 最后请求任意节点
        ResourceRequest request3 = new ResourceRequest(
            ResourceRequest.ANY,
            getRequiredMemory(),
            Integer.MAX_VALUE,          // 任意数量
            getRequiredCores()
        );
        requests.add(request3);
        
        return requests;
    }
}
```

---

## 2. Spark — 源码级

### 2.1 Spark 执行引擎

```java
// Spark 架构（org.apache.spark）
// 
// Driver Program:
public class SparkContext {
    private DAGScheduler dagScheduler;   // DAG 调度器
    private TaskScheduler taskScheduler; // 任务调度器
    private SchedulerBackend backend;    // 调度后端
    private BlockManager blockManager;   // 块管理
    private AccumulatorRegistry accumulatorRegistry; // 累加器
    
    // 任务提交流程:
    public <T> T runJob(RDD<T> rdd, Function<T, T> func) {
        // 1. 生成 DAG
        DAGStage stage = generateDAG(rdd);
        
        // 2. 划分 Stage（基于 shuffle）
        List<Stage> stages = stage.stage(rdd);
        
        // 3. 提交 Stage
        for (Stage stage : stages) {
            // 3.1 生成 TaskSet
            List<Task<?>> tasks = stage.generateTasks();
            
            // 3.2 提交到 TaskScheduler
            taskScheduler.submitTasks(new TaskSet(tasks));
        }
        
        // 4. 等待完成
        waitForCompletion();
        
        // 5. 返回结果
        return rdd.collect();
    }
    
    // DAG 调度:
    private DAGStage generateDAG(RDD<?> rdd) {
        DAGStage stage = new DAGStage();
        
        // 回溯依赖，找到窄依赖的边界
        while (rdd != null) {
            // 1. 找到 RDD 的最后一个宽依赖
            ShuffleDependency<?, ?, ?> shuffleDep = 
                findShuffleDependency(rdd);
            
            if (shuffleDep != null) {
                // 2. 划分 Stage
                stage.addShuffleBoundary(shuffleDep);
                rdd = shuffleDep.rdd();
            } else {
                // 3. 窄依赖，合并到一个 Stage
                stage.addNarrowDependencies(rdd);
                rdd = rdd.dependencies()[0].getDependencies()[0];
            }
        }
        
        return stage;
    }
}

// Task 执行:
public class Task<T> implements Runnable {
    private TaskContext taskContext;    // 任务上下文
    private Iterator<T> iterator;       // 数据迭代器
    
    public void run() {
        // 1. 反序列化任务
        deserialize();
        
        // 2. 执行计算
        T result = iterator.next();
        
        // 3. 汇报进度
        taskContext.markTaskCompleted();
        
        // 4. 返回结果
        return result;
    }
}
```

### 2.2 RDD 核心

```java
// RDD 抽象:
public abstract class RDD<T> implements Serializable {
    protected final SparkContext sc;       // Spark 上下文
    protected final List<Dependency<T>> dependencies; // 依赖
    protected final Partition[] partitions;   // 分区
    protected final StorageLevel storageLevel; // 存储级别
    
    // 核心方法:
    public Iterator<T> partitions(Partition split) {
        // 遍历所有依赖，找到数据
        for (Dependency<T> dep : dependencies) {
            if (dep instanceof NarrowDependency) {
                // 窄依赖: 父分区映射到子分区
                Iterator<T> parent = 
                    ((NarrowDependency<T>) dep).getParent(split).iterator();
                return parent;
            } else if (dep instanceof ShuffleDependency) {
                // 宽依赖: 从 ShuffleRead 读取
                return ShuffleRead.read(split);
            }
        }
        return new EmptyIterator<>();
    }
    
    // 缓存策略:
    public RDD<T> cache() {
        this.storageLevel = StorageLevel.MEMORY_ONLY();
        return this;
    }
    
    public RDD<T> persist(StorageLevel level) {
        this.storageLevel = level;
        return this;
    }
}

// 宽依赖 vs 窄依赖:
// 窄依赖（Narrow Dependency）:
// - OneToOneDependency: 一对一映射（map, filter）
// - RangeDependency: 范围映射（takeOrdered）
// - PruneDependency: 剪枝映射（mapValues）
// 
// 宽依赖（Shuffle Dependency）:
// - ShuffleDependency: shuffle 操作（groupBy, reduceByKey, join）
// 
// 依赖图:
// RDD-A → filter → RDD-B → map → RDD-C → reduceByKey → RDD-D → map → RDD-E
// 
// DAG:
// Stage 1: RDD-A → filter → RDD-B → map → RDD-C
// Shuffle: RDD-C → reduceByKey → RDD-D
// Stage 2: RDD-D → map → RDD-E
```

### 2.3 Spark SQL 优化

```java
// Catalyst Optimizer:
public class CatalystOptimizer {
    public LogicalPlan optimize(LogicalPlan plan) {
        // 优化规则链
        RuleSeq rules = RuleSeq.of(
            PushDownPredicate,      // 谓词下推
            PruneColumns,           // 列裁剪
            ConstantFolding,        // 常量折叠
            ArithmeticOptimization, // 算术优化
            Inference,              // 类型推断
            ReorderJoin,            // 连接重排序
            SkewJoinOptimization    // 倾斜优化
        );
        
        LogicalPlan optimized = plan;
        for (Rule rule : rules) {
            optimized = rule.apply(optimized);
            if (!optimized.changed()) {
                break;  // 无变化，停止
            }
        }
        
        return optimized;
    }
}

// 谓词下推:
// 原始查询:
// SELECT * FROM users WHERE age > 25 JOIN orders ON users.id = orders.user_id
//
// 优化后:
// SELECT * FROM (SELECT * FROM users WHERE age > 25) AS u JOIN orders ON u.id = orders.user_id
//
// 好处: 减少 Join 前的数据量

// 列裁剪:
// 原始查询:
// SELECT name, age FROM users
//
// 优化后: 只读取 name 和 age 列，不读取其他列
// 好处: 减少 IO

// 自适应查询执行（AQE）:
public class AdaptiveQueryExecution {
    public PhysicalPlan execute(PhysicalPlan plan) {
        // 1. 统计运行时信息
        RuntimeStat stats = collectRuntimeStats(plan);
        
        // 2. 动态合并小分区
        plan = mergeSmallPartitions(plan, stats);
        
        // 3. 动态选择 Join 策略
        plan = optimizeJoinStrategy(plan, stats);
        
        // 4. 动态处理数据倾斜
        plan = handleSkew(plan, stats);
        
        return plan;
    }
    
    // 动态 Join 策略选择:
    private PhysicalPlan optimizeJoinStrategy(PhysicalPlan plan, RuntimeStat stats) {
        if (stats.isSmallTable(plan.left)) {
            // 小表广播 → Broadcast Hash Join
            return new BroadcastHashJoin(plan);
        } else if (stats.hasSkew(plan.left, plan.right)) {
            // 数据倾斜 → Sort Merge Join + 倾斜处理
            return new SkewAwareSortMergeJoin(plan);
        } else {
            // 默认 → Sort Merge Join
            return new SortMergeJoin(plan);
        }
    }
}
```

---

## 3. 流处理 — Flink 架构

### 3.1 Flink 执行模型

```java
// Flink 架构（org.apache.flink）
// 
// JobManager（Coordinator）:
public class JobManager {
    private LeaderElectionService leaderElection; // 领导选举
    private SlotPoolManager slotPoolManager;      // 槽位管理
    private JobGraphLoader jobGraphLoader;        // 作业图加载
    private CheckpointCoordinator checkpointCoordinator; // 检查点
    
    // 检查点协调:
    public void triggerCheckpoint(long checkpointId) {
        // 1. 触发开始信号
        for (Operator operator : operators) {
            operator.prepareSnapshot(checkpointId);
        }
        
        // 2. 等待所有算子确认
        waitForConfirmation(checkpointId);
        
        // 3. 持久化到存储
        persistCheckpoint(checkpointId);
    }
}

// TaskManager（Executor）:
public class TaskManager {
    private SlotPool slotPool;            // 槽位池
    private NetworkEnvironment networkEnv; // 网络环境
    private BufferPoolManager bufferPoolManager; // 缓冲区池
    
    // Task 执行:
    public void execute(Task task) {
        try {
            // 1. 初始化
            task.initialize();
            
            // 2. 执行
            while (!task.isCanceled()) {
                Object record = task.next();
                task.process(record);
            }
            
            // 3. 完成
            task.complete();
        } catch (Exception e) {
            task.fail(e);
        }
    }
}

// 数据流:
// Source → map → filter → keyBy → window → reduce → Sink
//
// 算子链（Operator Chaining）:
// map → filter 链在一起，共享同一个 Task（减少网络开销）
//
// 数据分区:
// keyBy: 按 key 哈希分区
// broadcast: 广播到所有下游
// rebalance: 均匀分发到所有下游
// global: 全部发送到同一个下游
```

### 3.2 窗口与状态

```java
// 窗口操作:
public class WindowOperator {
    // 窗口类型:
    // 1. Tumbling Window: 滚动窗口（固定大小，不重叠）
    //    window(TumblingEventTimeWindows.of(Time.minutes(5)))
    //
    // 2. Sliding Window: 滑动窗口（固定大小，有重叠）
    //    window(SlidingEventTimeWindows.of(Time.minutes(10), Time.minutes(5)))
    //
    // 3. Session Window: 会话窗口（无固定大小，基于空闲时间）
    //    window(EventTimeSessionWindows.withGap(Time.minutes(30)))
    //
    // 4. Count Window: 计数窗口（固定数量）
    //    window(EventCountWindow.of(100))
    
    public void processElement(StreamRecord<T> element) {
        // 1. 找到对应的窗口
        Window window = getWindowAssigner().assignWindow(element);
        
        // 2. 添加到窗口
        window.add(element);
        
        // 3. 检查是否需要触发
        if (window.isTriggerable()) {
            trigger(window);
        }
    }
    
    private void trigger(Window window) {
        // 1. 获取窗口内的所有元素
        List<T> elements = window.getElements();
        
        // 2. 应用聚合函数
        T result = aggregate(elements);
        
        // 3. 输出结果
        emit(result);
    }
}

// 状态管理:
public class StateBackend {
    // 状态后端:
    // 1. MemoryStateBackend: 内存存储（适合测试）
    // 2. FsStateBackend: 文件系统存储（生产环境）
    // 3. RocksDBStateBackend: RocksDB 存储（超大状态）
    
    // 算子状态（Operator State）:
    // - 每个算子实例独立管理
    // - 用于 Source、Sink、自定义算子
    // - 支持 ListState、UnionListState
    
    // 键控状态（Keyed State）:
    // - 按 key 分区存储
    // - 用于 Map、Filter、ProcessFunction
    // - ValueState、ListState、MapState、ReducingState
    
    public V getState(String name, TypeDescriptor<V> type) {
        // 1. 检查缓存
        V cached = cache.get(name);
        if (cached != null) {
            return cached;
        }
        
        // 2. 从后端读取
        V state = backend.get(name);
        
        // 3. 缓存
        cache.put(name, state);
        
        return state;
    }
}
```

---

## 4. 数据管道

### 4.1 Lambda 架构 vs Kappa 架构

```
Lambda 架构:
┌──────────┐    ┌──────────┐    ┌──────────┐
│  Speed   │    │ Batch    │    │ Serving  │
│  Layer   │    │ Layer    │    │ Layer    │
├──────────┤    ├──────────┤    ├──────────┤
│Flink/    │    │Spark/    │    │HBase/    │
│Storm     │    │Hadoop    │    │Cassandra │
└──────────┘    └──────────┘    └──────────┘
       │               │               │
       └───────────────┼───────────────┘
                       │
                ┌──────────┐
                │  Data    │
                │  Lake    │
                └──────────┘

Kappa 架构:
┌──────────┐    ┌──────────┐    ┌──────────┐
│  Stream  │    │ Stream   │    │ Serving  │
│  Layer   │    │ Layer    │    │ Layer    │
├──────────┤    ├──────────┤    ├──────────┤
│Kafka     │    │Flink     │    │ES/       │
│           │    │          │    │ClickHouse│
└──────────┘    └──────────┘    └──────────┘
       │               │               │
       └───────────────┼───────────────┘
                       │
                ┌──────────┐
                │  Stream  │
                │  Store   │
                └──────────┘

选择建议:
- Lambda: 需要离线批处理 + 实时流处理
- Kappa: 只需要实时流处理，用 stream replay 替代批处理

Flink 支持的 Kappa:
1. Source 支持 replay（Kafka offset 回溯）
2. State 支持 checkpoint（故障恢复）
3. 可以重新运行历史数据
```

### 4.2 数据管道实现

```java
// 广告数据管道:
public class AdPipeline {
    private StreamExecutionEnvironment env; // Flink 执行环境
    private DataStream<AdEvent> eventStream;
    
    public void setup() {
        // 1. 创建执行环境
        env = StreamExecutionEnvironment.getExecutionEnvironment();
        env.setParallelism(8);
        
        // 2. 从 Kafka 读取
        DataStream<AdEvent> source = env.addSource(
            new FlinkKafkaConsumer<>(
                "ad-events",
                new AdEventDeserializationSchema(),
                kafkaProps
            )
        );
        
        // 3. 数据清洗
        DataStream<AdEvent> cleaned = source
            .filter(event -> event.isValid())
            .map(event -> clean(event));
        
        // 4. 实时聚合
        DataStream<AdMetrics> metrics = cleaned
            .keyBy(AdEvent::getCampaignId)
            .window(TumblingEventTimeWindows.of(Time.minutes(5)))
            .process(new AdMetricsAggregator());
        
        // 5. 写入 ClickHouse（实时报表）
        metrics.addSink(new ClickHouseSink("clickhouse://..."));
        
        // 6. 写入 HDFS（原始数据）
        source.addSink(new HdfsSink("hdfs://..."));
        
        // 7. 启动执行
        env.execute("Ad Pipeline");
    }
}

// 实时聚合:
public class AdMetricsAggregator extends ProcessWindowFunction<
    AdEvent, AdMetrics, String, TimeWindow> {
    
    public void process(String campaignId, Context context, 
                       Iterable<AdEvent> events, Collector<AdMetrics> out) {
        long impressions = 0;
        long clicks = 0;
        long conversions = 0;
        double revenue = 0;
        
        for (AdEvent event : events) {
            if (event.getType() == IMPRESSION) {
                impressions++;
            } else if (event.getType() == CLICK) {
                clicks++;
            } else if (event.getType() == CONVERSION) {
                conversions++;
            }
            revenue += event.getRevenue();
        }
        
        // 计算指标
        double ctr = impressions > 0 ? (double) clicks / impressions : 0;
        double cvr = clicks > 0 ? (double) conversions / clicks : 0;
        
        // 输出
        out.collect(new AdMetrics(
            campaignId,
            impressions, clicks, conversions,
            revenue, ctr, cvr,
            context.window().getStart(),
            context.window().getEnd()
        ));
    }
}
```

---

## 5. 大数据选型对比

```
┌─────────────┬─────────────┬─────────────┬─────────────────┐
│             │   Hadoop    │   Spark     │   Flink         │
├─────────────┼─────────────┼─────────────┼─────────────────┤
│ 计算模型    │ MapReduce   │ RDD/DAG     │ DataFlow        │
│             │             │             │                 │
├─────────────┼─────────────┼─────────────┼─────────────────┤
│ 存储       │ HDFS        │ HDFS/S3     │ HDFS/S3/Kafka   │
│             │             │             │                 │
├─────────────┼─────────────┼─────────────┼─────────────────┤
│ 延迟       │ 分钟级      │ 秒级        │ 毫秒级          │
│             │             │             │                 │
├─────────────┼─────────────┼─────────────┼─────────────────┤
│ 适用场景    │ 离线批处理  │ 混合批处理  │ 实时流处理      │
│             │             │  交互式查询 │  事件处理       │
├─────────────┼─────────────┼─────────────┼─────────────────┤
│ 容错       │ Checkpoint  │ RDD Lineage │ State Backend   │
│             │             │             │                 │
├─────────────┼─────────────┼─────────────┼─────────────────┤
│ 生态       │ HDFS/Hive   │ SparkSQL/   │ FlinkSQL/Kafka  │
│             │ HBase/Pig   │ MLlib/      │ State Backend   │
│             │             │ GraphX      │                 │
└─────────────┴─────────────┴─────────────┴─────────────────┘

选择建议:
- 离线批处理: Hadoop MapReduce / Spark
- 实时流处理: Flink
- 交互式查询: Spark SQL / Presto / Hive
- 事件处理: Flink / Storm
- 混合场景: Spark Structured Streaming / Flink
```

---

*本文档基于大数据系统架构整理，覆盖 Hadoop/Spark/Flink 核心机制*
