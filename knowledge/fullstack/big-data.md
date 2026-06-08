# 大数据系统 — Hadoop/Spark 架构、数据管道、流批一体

> 标签: `#大数据` `#Hadoop` `#Spark` `#数据管道` `#流批一体`
> 创建日期: 20260608
> 作者: Ryan

---

## 1. Hadoop 生态系统

### 1.1 HDFS 分布式文件系统

```
HDFS 架构:
┌─────────────────────────────────────────────────────────────┐
│                        NameNode                              │
│  - 存储文件系统元数据（目录树、文件-块映射）                    │
│  - 维护 In-Metadata（内存中的文件树）                         │
│  - 管理 Block Location（哪个 DataNode 有哪些块）               │
│  - 处理客户端请求                                             │
└──────────────────┬──────────────────────────────────────────┘
                   │
    ┌──────────────┼──────────────┐
    ▼              ▼              ▼
┌────────┐  ┌────────┐  ┌────────┐
│DataNode│  │DataNode│  │DataNode│
│ #1     │  │ #2     │  │ #3     │
│ Block  │  │ Block  │  │ Block  │
│ A,B,C  │  │ B,D,E  │  │ A,C,E  │
│ 128MB  │  │ 128MB  │  │ 128MB  │
└────────┘  └────────┘  └────────┘

Block Size: 默认 128MB（Hadoop 2.x）或 256MB（Hadoop 3.x）
副本数: 默认 3（rack-aware 策略）
  - 第 1 副本: 本地机架的本地节点
  - 第 2 副本: 本地机架的其他节点
  - 第 3 副本: 其他机架的节点

NameNode HA:
  - Active NameNode + Standby NameNode（基于 ZooKeeper Failover）
  - Shared edits log（QJM: Quorum Journal Manager）
  - Standby 定期从 Active 同步 fsimage + edits
```

### 1.2 MapReduce 计算模型

```
MapReduce 执行流程:

Input (HDFS)
  │
  ▼
┌─────────────┐
│  Mapper     │  ← 处理输入分片（InputSplit）
│  map(key,   │
│       value)│
│  → emit     │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Shuffle    │  ← 按 Key 分区、排序、合并
│  (网络传输)  │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Reducer    │  ← 聚合处理
│  reduce(key,│
│         vals)│
│  → emit     │
└──────┬──────┘
       │
       ▼
Output (HDFS)

Map 阶段:
  - 每个 Mapper 处理一个 InputSplit（通常对应一个 HDFS Block）
  - map() 函数处理每条记录
  - 输出 (key, value) 对，写入本地磁盘（溢写）
  - 溢写文件按 key 排序（Combiner 可选预聚合）

Shuffle 阶段:
  - 分区: partition(key) % numReducers
  - 排序: 按 key 排序
  - 合并: 相同 key 的 value 合并为迭代器
  - 网络传输: Mapper 将数据拷贝到 Reducer 所在节点

Reduce 阶段:
  - 接收多个 Mapper 的相同 key 的数据
  - reduce(key, Iterator<Value>)
  - 输出到 HDFS

局限:
  - 中间结果写磁盘 → IO 开销大
  - 不适合迭代计算（如 ML）
  - 不适合 DAG 计算
```

### 1.3 YARN 资源管理

```
YARN 架构:
┌─────────────────────────────────────────────────────────────┐
│                        ResourceManager                         │
│  - 全局资源调度（全局 FIFO/Fair/Capacity 队列）                │
│  - 管理 NodeManager 心跳                                     │
│  - ApplicationMaster 注册                                    │
└──────────────────┬──────────────────────────────────────────┘
                   │
    ┌──────────────┼──────────────┐
    ▼              ▼              ▼
┌────────┐  ┌────────┐  ┌────────┐
│NodeMgr │  │NodeMgr │  │NodeMgr │
│        │  │        │  │        │
││  │
│  ┌─────────────┐
│  │  Container  │
│  │  (Memory)   │
│  └─────────────┘
└────────┘  └────────┘  └────────┘

ApplicationMaster (AM):
  - 每个 Application 一个 AM
  - 向 RM 申请资源（Container）
  - 向 NM 提交任务
  - 监控任务进度，处理失败重试
  - MapReduce: MRAppMaster
  - Spark: SparkDeployAM

Container:
  - YARN 的资源抽象
  - 包含: vCore, Memory, Disk, GPU
  - 生命周期: 创建 → 执行任务 → 释放
```

---

## 2. Spark 核心架构

### 2.1 Spark vs MapReduce

```
MapReduce 问题:
  1. 磁盘 IO 重: 每次 Map → Shuffle → Reduce 都写磁盘
  2. 迭代计算慢: 每次迭代都从磁盘重读
  3. DAG 复杂: 多步骤 Pipeline 需要写多个 MR Job

Spark 优势:
  1. In-Memory: 中间结果存内存（RDD Cache/Persist）
  2. DAG Execution: 有向无环图优化执行计划
  3. 宽窄依赖: 窄依赖 Pipeline 优化，宽依赖 Shuffle
  4. 支持: SQL、Streaming、MLlib、GraphX

性能对比:
  - 内存计算: 比 MR 快 10-100 倍
  - 磁盘计算: 比 MR 快 3-5 倍
  - 迭代计算: 比 MR 快 100 倍
```

### 2.2 Spark 架构

```
Spark 集群架构:
┌─────────────────────────────────────────────────────────────┐
│                     Driver Program                             │
│  - 创建 SparkContext                                        │
│  - 注册 Listener（监控）                                     │
│  - 提交 Application（submit）                                 │
│  - 创建 DAGScheduler（Stage 划分）                           │
│  - 创建 TaskScheduler（Task 分发）                           │
└──────────────┬───────────────────────────────────────────────┘
               │
       ┌───────┼───────┐
       ▼       ▼       ▼
┌────────┐ ┌────────┐ ┌────────┐
│Executor│ │Executor│ │Executor│
│ #1     │ │ #2     │ │ #3     │
││        │
│  │Task  │
│  │Task  │
│  │Task  │
│  └────────┘
└────────┘  └────────┘  └────────┘

部署模式:
  - Local: 本地测试（1 线程或 N 线程）
  - Standalone: Spark 自带资源管理（Master + Workers）
  - YARN: 生产环境主流（Client/Cluster 模式）
  - Kubernetes: 容器化部署
  - Mesos: 早期方案（较少用）

关键组件:
  - SparkContext: 集群连接入口
  - RDD: 弹性分布式数据集（核心抽象）
  - DAGScheduler: Stage 划分（基于宽/窄依赖）
  - TaskScheduler: Task 分发到 Executor
  - BlockManager: 数据缓存/拉取
  - ShuffleManager: 数据 Shuffle（Sort/Shuffle）
```

### 2.3 RDD 编程模型

```
RDD (Resilient Distributed Dataset):
  - 只读、分区的数据集合
  - 通过算子转换（transformation）生成新 RDD
  - 缓存到内存（memory_only/memory_and_disk）
  - 容错: 通过 Lineage（血统）重建丢失分区

RDD 操作:
  Transformation (惰性求值):
    - map, filter, flatMap
    - groupByKey, reduceByKey, sortByKey
    - join, cogroup
    - distinct, sample
    
  Action (触发计算):
    - collect, take, count
    - saveAsTextFile, saveAsObjectFile
    - foreach, foreachPartition
    
  Persistence:
    - cache() = persist(StorageLevel.MEMORY_ONLY)
    - persist(StorageLevel.MEMORY_AND_DISK)
    - unpersist() 释放缓存

宽依赖 vs 窄依赖:
  窄依赖 (Narrow Dependency):
    - 每个父 RDD 分区被 ≤ 1 个子分区使用
    - map, filter, union
    - 可 Pipeline 优化（不需要 Shuffle）
    
  宽依赖 (Wide Dependency):
    - 父 RDD 分区被子 RDD 多个分区使用
    - groupByKey, reduceByKey, join
    - 需要 Shuffle → 划分 Stage

Stage 划分:
  DAGScheduler 根据宽依赖划分 Stage
  Stage 内任务可 Pipeline 优化（窄依赖）
  Stage 间通过 Shuffle 连接
```

### 2.4 Spark SQL & Catalyst

```
Spark SQL 执行流程:
  SQL 语句 → Parser (ANTLR) → Logical Plan
    → Analyzer (Rule) → Analyzed Logical Plan
    → Optimizer (Catalyst) → Optimized Logical Plan
    → Planner (Strategy) → Physical Plan
    → CodeGen (Tungsten) → Bytecode
    → Execution

Catalyst 优化器规则:
  1. 谓词下推 (Predicate Pushdown): WHERE 尽量下推
  2. 列裁剪 (Column Pruning): 只读需要的列
  3. 常量折叠 (Constant Folding): 编译时计算常量
  4. 自适应查询执行 (AQE): 运行时优化
     - 自适应 Shuffle 分区数
     - 自适应 Join 策略
     - 动态过滤

DataFrame API:
  df.filter("age > 25")
    .groupBy("city")
    .agg({"spend": "sum"})
    .orderBy(desc("sum(spend)"))
    .show()
    
  等价 SQL:
  SELECT city, SUM(spend) 
  FROM table 
  WHERE age > 25 
  GROUP BY city 
  ORDER BY SUM(spend) DESC
```

---

## 3. 数据管道架构

### 3.1 Lambda 架构

```
Lambda 架构:
┌─────────────────────────────────────────────────────────────┐
│                        数据源                                │
│  (日志、API、数据库 CDC)                                     │
└──────────────┬──────────────────────────────────────────────┘
               │
       ┌───────┼───────┐
       ▼       ▼       ▼
┌────────┐ ┌────────┐ ┌────────┐
│Speed   │ │Batch   │ │Speed   │
│Layer    │ │Layer   │ │Layer   │
│(实时)   │ │(离线)  │ │Layer   │
│        │ │        │ │(实时)  │
└───┬────┘ └───┬────┘ └───┬────┘
    │          │          │
    ▼          ▼          ▼
┌─────────────────────────────────────────────────────────────┐
│                   Service Layer                              │
│  - 统一服务层，合并 Batch + Speed 层结果                       │
│  - 查询时: Batch View + Speed View = 最终结果                │
└─────────────────────────────────────────────────────────────┘

Batch Layer:
  - 全量数据 + 全量计算
  - 使用 Spark/Hadoop
  - 定期运行（如每小时/每天）
  - 生成 Batch View

Speed Layer (实时代码):
  - 增量数据 + 增量计算
  - 使用 Storm/Spark Streaming/Flink
  - 实时处理（秒级）
  - 生成 Speed View

Service Layer:
  - 合并 Batch View + Speed View
  - Speed View 有延迟，但 Batch View 更准确
  - 最终一致性

问题:
  - 代码重复（Batch + Speed 逻辑一致）
  - 运维复杂（两套系统）
  - 数据一致性困难
```

### 3.2 Kappa 架构

```
Kappa 架构:
┌─────────────────────────────────────────────────────────────┐
│                        数据源                                │
│  (Kafka/PubSub 作为唯一数据源)                               │
└──────────────┬──────────────────────────────────────────────┘
               │
       ┌───────┼───────┐
       ▼       ▼       ▼
┌────────┐ ┌────────┐ ┌────────┐
│Stream  │ │Stream  │ │Stream  │
│Proc    │ │Proc    │ │Proc    │
│(实时)  │ │(实时)  │ │(实时)  │
│        │ │        │ │        │
└───┬────┘ └───┬────┘ └───┬────┘
    │          │          │
    ▼          ▼          ▼
┌─────────────────────────────────────────────────────────────┐
│                   View / Sink                                │
│  - 所有计算都是流式计算                                       │
│  - 需要历史数据 → 从 Kafka 重放（Replay）                     │
└─────────────────────────────────────────────────────────────┘

Kafka 作为消息队列:
  - 保留策略: 7 天/14 天/30 天（配置 retention）
  - 重放数据: 重置 Offset，从历史数据开始消费
  - 单数据源: 所有逻辑在 Stream 层
  
Flink/Spark Streaming:
  - 处理流数据
  - 支持精确一次（Exactly-Once）语义
  - 状态管理: State Backend（RocksDB）
  
优势:
  - 逻辑统一（都是 Stream）
  - 运维简单（一套系统）
  - 支持任意时间窗口
  
劣势:
  - 全量重放成本高
  - 状态管理复杂
```

### 3.3 现代数据管道

```
现代数据管道:
┌─────────────────────────────────────────────────────────────┐
│                    Data Ingestion                            │
│  - 日志: Filebeat/Fluentd → Kafka                            │
│  - 数据库: Debezium (CDC) → Kafka                            │
│  - API: Custom Sink → Kafka                                  │
└──────────────┬──────────────────────────────────────────────┘
               │
       ┌───────┼───────┐
       ▼       ▼       ▼
┌────────┐ ┌────────┐ ┌────────┐
│Batch   │ │Stream  │ │Batch+  │
│Spark   │ │Flink   │ │Stream  │
│        │ │        │ │(统一)  │
└───┬────┘ └───┬────┘ └───┬────┘
    │          │          │
    ▼          ▼          ▼
┌─────────────────────────────────────────────────────────────┐
│                   Data Lake / Warehouse                      │
│  - S3/HDFS: Raw Data (Parquet/ORC)                         │
│  - Hive/Iceberg/Hudi: ACID 表                             │
│  - ClickHouse/Doris: OLAP 查询                              │
│  - Presto/Trino: 跨数据源查询                                 │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. 流批一体

### 4.1 流批一体架构

```
流批一体:
┌─────────────────────────────────────────────────────────────┐
│                      Flink/Spark                             │
│  - 统一 API: DataStream API + DataSet API                   │
│  - 统一运行时: 批是流的特例（有限流）                        │
│  - 统一状态管理: State Backend                              │
│  - 统一语义: Exactly-Once（Chandy-Lamport 算法）            │
└──────────────┬──────────────────────────────────────────────┘
               │
       ┌───────┼───────┐
       ▼       ▼       ▼
┌────────┐ ┌────────┐ ┌────────┐
│Kafka   │ │Kafka   │ │Kafka   │
│Source  │ │Sink    │ │Source  │
└───┬────┘ └───┬────┘ └───┬────┘
    │          │          │
    ▼          ▼          ▼
┌─────────────────────────────────────────────────────────────┐
│                   Storage Layer                              │
│  - Kafka: 消息队列（保留策略）                               │
│  - HDFS/S3: 数据湖                                         │
│  - Hive/Iceberg: ACID 表                                   │
└─────────────────────────────────────────────────────────────┘

Flink 流批一体:
  - DataStream API 处理流
  - DataSet API 处理批（已废弃，统一用 DataStream）
  - Bounded Stream = 批处理
  
Exactly-Once 语义:
  1. Source: 从 checkpoint 恢复 Offset
  2. Processing: 状态更新在 checkpoint 中
  3. Sink: Two-Phase Commit（2PC）或幂等写入
  
Checkpoint 机制:
  - 定期保存状态快照（State Snapshot）
  - 失败时从最近 Checkpoint 恢复
  - 对齐 Checkpoint（Barrier 对齐，保证一致性）
```

### 4.2 Iceberg/Hudi 数据湖格式

```
Iceberg (Apache):
  - 面向大数据的开放表格格式
  - ACID 事务支持（多版本并发控制）
  - Schema Evolution（支持字段增减）
  - Time Travel（查询历史版本）
  - 隐藏分区（Hidden Partitioning）
  
  存储结构:
  ├── metadata/
  │   ├── 00001-abc.metadata.json  ← 元数据
  │   ├── 00002-def.metadata.json
  │   └── 00003-ghi.metadata.json
  ├── data/
  │   ├── partition=1/
  │   │   ├── part-00000.parquet
  │   │   └── part-00001.parquet
  │   └── partition=2/
  │       └── ...
  └── snapshot/
      ├── 00001-abc-SNAP  ← 快照指针
      └── 00002-def-SNAP

Hudi (Apache):
  - 增量数据摄取 +  Upsert + 删除
  - 支持 Copy-On-Write / Merge-On-Read
  - 时间旅行（Time Travel）
  - 小文件管理（Compaction）
  
  Table Types:
  - COW (Copy-On-Write): 查询快，写入慢
  - MOR (Merge-On-Read): 查询慢，写入快（读时合并）
```

---

## 5. 性能调优

### 5.1 Spark 调优

```
并行度:
  - spark.default.parallelism: 默认 200（HDFS Block 数）
  - spark.sql.shuffle.partitions: 200（Shuffle 分区数）
  - 原则: 每个 Task 处理 100MB-1GB 数据
  
内存管理:
  - spark.executor.memory: 每个 Executor 内存
  - spark.executor.memoryOverhead: 堆外内存（默认 10%）
  - spark.driver.memory: Driver 内存
  - 内存分配: Executor Memory = Execution + Storage + Reserved
  
缓存策略:
  - df.cache() = MEMORY_ONLY
  - df.persist(StorageLevel.MEMORY_AND_DISK)
  - 监控: Spark UI → Storage 标签页
  
广播变量:
  - 小表广播到所有 Executor，避免 Shuffle
  - broadcast(df.join(broadcast(small_df), "key"))
  
避免数据倾斜:
  - 现象: 某些 Task 处理大量数据
  - 解决:
    1. 加盐（Salting）: key + random prefix
    2. 双聚合: 先局部聚合，再全局聚合
    3. 调整分区数: 增加 shuffle partitions
```

### 5.2 Flink 调优

```
并行度:
  - flink.parallelism.default: 全局默认并行度
  - stream.map().setParallelism(8): 算子级别设置
  
内存:
  - taskmanager.memory.process.size: 总内存
  - taskmanager.memory.jvm-metaspace.size: Metaspace
  - taskmanager.memory.network.fraction: 网络内存比例
  
Checkpont:
  - execution.checkpointing.interval: 5min
  - execution.checkpointing.timeout: 10min
  - execution.checkpointing.min-pause: 1min（最小间隔）
  - state.backend: rocksdb（大状态）/ hashmap（小状态）
  
反压:
  - 监控: Flink UI → Tasks → Back Pressured
  - 原因: 下游处理慢于上游
  - 解决: 增加并行度、优化算子逻辑
```

### 5.3 存储调优

```
Parquet 文件:
  - 列式格式，高压缩比
  - 页大小: 128KB（默认）
  - 行组大小: 128MB（默认）
  - 压缩: Snappy/LZ4/ZSTD
  
小文件问题:
  - 影响: NameNode 压力、Spark 启动慢
  - 解决:
    1. Spark: repartition/coalesce 合并
    2. Hadoop: MapReduce Merge
    3. Flink: 定期 Compaction
    
数据格式选择:
  - Parquet: 列存，适合分析查询
  - ORC: 列存，适合 Hive
  - Avro: 行存，适合日志
  - JSON/CSV: 通用，但效率低
```

---

## 6. 实战场景

### 6.1 实时数据管道

```sql
-- Kafka → Flink → ClickHouse
-- 实时广告曝光统计

-- Flink SQL:
CREATE TABLE ad_exposures (
    ad_id BIGINT,
    campaign_id BIGINT,
    user_id BIGINT,
    ts TIMESTAMP(3),
    WATERMARK FOR ts AS ts - INTERVAL '5' SECOND
) WITH (
    'connector' = 'kafka',
    'topic' = 'ad-exposures',
    'properties.bootstrap.servers' = 'kafka:9092',
    'group.id' = 'flink-consumer',
    'format' = 'json'
);

CREATE TABLE ad_stats (
    campaign_id BIGINT,
    dt STRING,
    exposure_count BIGINT,
    PRIMARY KEY (campaign_id, dt) NOT ENFORCED
) WITH (
    'connector' = 'clickhouse',
    'url' = 'http://clickhouse:8123',
    'database' = 'ads',
    'table' = 'daily_stats'
);

INSERT INTO ad_stats
SELECT 
    campaign_id,
    DATE_FORMAT(ts, 'yyyy-MM-dd') AS dt,
    COUNT(*) AS exposure_count
FROM ad_exposures
GROUP BY campaign_id, DATE_FORMAT(ts, 'yyyy-MM-dd');
```

### 6.2 离线数据仓库

```sql
-- Spark SQL 数据仓库分层
-- ODS (原始数据层) → DWD (明细层) → DWS (汇总层) → ADS (应用层)

-- DWD 层: 用户行为明细
CREATE TABLE dwd_user_behavior (
    user_id STRING,
    event_type STRING,
    event_time TIMESTAMP,
    device STRING,
    city STRING
) PARTITIONED BY (dt STRING)
STORED AS PARQUET;

-- DWS 层: 用户日汇总
CREATE TABLE dws_user_daily (
    user_id STRING,
    dt STRING,
    page_views INT,
    spend DECIMAL(10,2),
    sessions INT
) STORED AS PARQUET;

INSERT INTO dws_user_daily
SELECT 
    user_id,
    dt,
    COUNT(CASE WHEN event_type = 'page_view' THEN 1 END) AS page_views,
    SUM(CASE WHEN event_type = 'purchase' THEN amount ELSE 0 END) AS spend,
    COUNT(DISTINCT session_id) AS sessions
FROM dwd_user_behavior
WHERE dt = '${yesterday}'
GROUP BY user_id, dt;

-- ADS 层: 业务报表
SELECT 
    city,
    SUM(spend) AS total_spend,
    COUNT(DISTINCT user_id) AS active_users
FROM dws_user_daily
WHERE dt BETWEEN '${start_date}' AND '${end_date}'
GROUP BY city;
```

---

*本文档基于 Spark 3.x + Flink 1.17 整理，覆盖大数据核心架构与流批一体实践*
