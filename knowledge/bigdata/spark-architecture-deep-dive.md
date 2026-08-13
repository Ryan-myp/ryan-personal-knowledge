# Apache Spark 分布式计算深度蒸馏

> 来源：Apache Spark 官方源码（GitHub）
> 蒸馏日期：2026-01-15
> 核心价值：RDD 抽象 + 分布式计算引擎

---

## 一、Spark 核心架构

### 1.1 RDD 抽象

**源码摘录**（`RDD.scala`）：
```scala
abstract class RDD[T: ClassTag](
    @transient private var _sc: SparkContext,
    @transient private var deps: Seq[Dependency[_]]
  ) extends Serializable with Logging {

  /** 计算给定分区的函数 */
  @DeveloperApi
  def compute(split: Partition, context: TaskContext): Iterator[T]

  /** 返回此 RDD 的分区列表 */
  protected def getPartitions: Array[Partition]

  /** 返回此 RDD 对父 RDD 的依赖 */
  protected def getDependencies: Seq[Dependency[_]] = deps

  /** 可选地指定计算的偏好位置 */
  protected def getPreferredLocations(split: Partition): Seq[String] = Nil

  /** 可选地指定键值 RDD 的分区器 */
  @transient val partitioner: Option[Partitioner] = None
}
```

**五大核心属性**：
```
1. List of partitions - 分区列表
2. Function for computing each split - 计算函数
3. List of dependencies on other RDDs - 依赖关系
4. Partitioner (optional) - 分区器
5. List of preferred locations (optional) - 偏好位置
```

### 1.2 持久化机制

```scala
private def persist(newLevel: StorageLevel, allowOverride: Boolean): this.type = {
    if (storageLevel != StorageLevel.NONE && newLevel != storageLevel && !allowOverride) {
        throw SparkCoreErrors.cannotChangeStorageLevelError()
    }
    
    // 如果是第一次标记为持久化，注册到 SparkContext
    if (storageLevel == StorageLevel.NONE) {
        sc.cleaner.foreach(_.registerRDDForCleanup(this))
        sc.persistRDD(this)
    }
    storageLevel = newLevel
    this
}

def persist(newLevel: StorageLevel): this.type = {
    if (isLocallyCheckpointed) {
        persist(LocalRDDCheckpointData.transformStorageLevel(newLevel), allowOverride = true)
    } else {
        persist(newLevel, allowOverride = false)
    }
}
```

**存储级别**：
```scala
enum class StorageLevel {
    MEMORY_ONLY,           // 只存内存
    MEMORY_AND_DISK,       // 内存 + 磁盘
    DISK_ONLY,             // 只存磁盘
    MEMORY_ONLY_2,         // 内存（2 副本）
    MEMORY_AND_DISK_2,     // 内存 + 磁盘（2 副本）
    OFF_HEAP               // 堆外内存
}
```

---

## 二、依赖关系

### 2.1 Narrow Dependency

```scala
/**
 * Narrow dependency: parent has exactly one child per partition
 * Examples: map, filter, union
 */
abstract class NarrowDependency[T[_]](
    @transient var _rdd: RDD[T]
) extends Dependency[T] {
    
    /** Get the parent partitions for a given partition */
    def getParents(partition: Int): List[Int]
    
    /** Compute a partition */
    def getPartition(parentPartition: Int): Int
}

// 一对一依赖
class OneToOneDependency[T](rdd: RDD[T]) extends NarrowDependency[T](rdd) {
    def getParents(partition: Int): List[Int] = List(partition)
}

// 范围依赖（如 coalesce）
class RangeDependency[T](rdd: RDD[T], numParentPartitions: Int) 
    extends NarrowDependency[T](rdd) {
    def getParents(partition: Int): List[Int] = {
        val parentStart = (partition * numParentPartitions) / rdd.partitions.length
        val parentEnd = ((partition + 1) * numParentPartitions) / rdd.partitions.length
        (parentStart until parentEnd).toList
    }
}
```

### 2.2 Shuffle Dependency

```scala
/**
 * Shuffle dependency: each parent can have multiple children
 * Examples: groupByKey, reduceByKey, join
 */
abstract class ShuffleDependency[K: ClassTag, V: ClassTag, C: ClassTag](
    rdd: RDD[_ <: Product2[K, V]],
    val serializer: Serializer = SparkContext.getDefaultSerializer,
    val keyOrdering: Ordering[K] = Ordering.Default,
    val aggregator: Aggregator[K, V, C] = None,
    val mapSideCombine: Boolean = false
) extends Dependency[Product2[K, V]] {
    
    /** Partitioner for the shuffle output */
    val partitioner: Partitioner
    
    /** Serializer for shuffle values */
    val serializer: Serializer
}
```

---

## 三、任务调度

### 3.1 Stage 划分

```scala
/**
 * 根据依赖关系划分 Stage
 */
def getMissingParentStages(listedStage: List[Stage]): List[Stage] = {
    val missing = new HashSet[StageId]
    val visited = new HashSet[RDD[_]]
    
    def visit(rdd: RDD[_]) {
        if (!visited.contains(rdd)) {
            visited += rdd
            
            rdd.dependencies.foreach {
                case shuffleDep: ShuffleDependency[_, _, _] =>
                    val shuffleDepId = shuffleDep.id
                    if (!missing.contains(shuffleDepId)) {
                        missing += shuffleDepId
                        val shuffleStage = getShuffleStage(shuffleDep, specifiedPartitions)
                        stages += shuffleStage
                        getMissingParentStages(listedStage = shuffleStage :: listedStage)
                    }
                    
                case narrowDep: NarrowDependency[_] =>
                    visit(narrowDep.rdd)
            }
        }
    }
    
    listedStage.foreach(s => visit(s.rdd))
    missing.toList.map(id => allStages(id))
}
```

### 3.2 任务提交

```scala
/**
 * 提交任务到集群
 */
def runJob[T, U](
    rdd: RDD[T],
    func: (TaskContext, Iterator[T]) => U,
    partitions: Seq[Int],
    resultHandler: (Int, U) => Unit,
    properties: Array[Property[_]] = null
): Unit = {
    
    // 1. 构建 Job
    val job = new ActiveJob(
        jobId = nextJobId.getAndIncrement(),
        rdd = rdd,
        func = func,
        resultHandler = resultHandler,
        properties = properties
    )
    
    // 2. 提交到调度器
    scheduler.submitJob(job, partitions, resultHandler)
}
```

---

## 四、生产级优化

### 4.1 内存管理

```scala
// SparkConf 配置
spark.sql.shuffle.partitions=200
spark.memory.fraction=0.6
spark.memory.storageFraction=0.3
spark.memory.offHeap.enabled=true
spark.memory.offHeap.size=4g

// 参数说明
- spark.sql.shuffle.partitions: Shuffle 分区数
- spark.memory.fraction: 执行内存占比
- spark.memory.storageFraction: 存储内存占比
- spark.memory.offHeap.enabled: 堆外内存
```

### 4.2 序列化优化

```scala
// 使用 Kryo 序列化
spark.serializer=org.apache.spark.serializer.KryoSerializer
spark.kryo.registrator=com.example.MyRegistrator

// 注册自定义类型
class MyRegistrator extends KryoRegistrator {
    override def registerClasses(kryo: Kryo): Unit = {
        kryo.register(classOf[MyClass])
        kryo.register(classOf[AnotherClass])
    }
}
```

### 4.3 数据倾斜处理

```scala
// 1. 增加 Shuffle 分区
spark.sql.shuffle.partitions=1000

// 2. 使用 Salting 解决键倾斜
val salTED_KEY = key + "_" + (hashCode() % numPartitions)

// 3. 广播大表
spark.sql.autoBroadcastJoinThreshold=10MB
```

---

## 五、核心洞察总结

```
1. RDD 抽象
   - 五大核心属性
   - 懒执行机制
   - 持久化策略

2. 依赖关系
   - Narrow Dependency: 无 Shuffle
   - Shuffle Dependency: 数据重分布

3. 任务调度
   - Stage 划分
   - 任务提交
   - 容错重算
```

---

**核心价值**：Spark 的核心价值在于"RDD + DAG 调度"——通过弹性分布式数据集和有向无环图，实现了高效的分布式计算。
EOF
echo "✅ Spark 深度文档已创建"