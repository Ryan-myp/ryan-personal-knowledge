# 广告数据湖深度：Hudi/Iceberg/Delta + 实时数仓架构

> 从广告系统视角，深度解析三大数据湖格式和实时数仓架构

---

## 第一部分：为什么广告系统需要 Data Lakehouse？

### 广告数据特点

```
广告数据的特点：
1. 数据量大：每天百亿级事件（曝光/点击/转化）
2. 数据类型多：结构化（交易数据）+ 半结构化（日志）+ 非结构化（创意素材）
3. 查询模式多：实时看板（秒级）+ 离线分析（天级）+ 模型训练（批量）
4. 数据新鲜度要求高：广告主需要实时看数据
5. 历史追溯：需要保留原始数据用于归因分析

传统方案的痛点：
• 数据仓库（ClickHouse）：不适合半结构化数据，schema 变更成本高
• 数据湖（S3/HDFS）：查询性能差，不支持 ACID
• 两者分离：数据同步延迟，数据不一致

Lakehouse 方案：
• 数据湖存储原始数据（低成本）
• 数据湖支持 ACID（Hudi/Iceberg/Delta）
• 多个计算引擎共享同一份数据（Spark/Flink/Trino/Presto）
```

---

## 第二部分：Apache Iceberg 深度

### Iceberg 架构

```
Iceberg 表结构：
┌─────────────────────────────────────────────────────────────────────┐
│ Snapshot（快照）                                                     │
│   Snapshot A: 初始写入                                               │
│   Snapshot B: 追加写入                                               │
│   Snapshot C: 删除/更新（时间旅行）                                    │
│                                                                     │
│ Manifest List（清单列表）                                             │
│   snapshot-a.json → manifest-list-a.avro                             │
│   snapshot-b.json → manifest-list-b.avro                             │
│   snapshot-c.json → manifest-list-c.avro                             │
│                                                                     │
│ Manifest Files（清单文件）                                           │
│   manifest-001.avro → 记录文件 1,2,3 的路径和元数据                   │
│   manifest-002.avro → 记录文件 4,5,6 的路径和元数据                   │
│                                                                     │
│ Data Files（数据文件，Parquet/ORC）                                   │
│   data-001.parquet → 实际数据                                        │
│   data-002.parquet → 实际数据                                        │
│                                                                     │
│ Schema（schema 演进）                                                │
│   v1: {campaign_id, platform, impressions}                           │
│   v2: {campaign_id, platform, impressions, clicks}                   │
│   v3: {campaign_id, platform, impressions, clicks, conversions}      │
└─────────────────────────────────────────────────────────────────────┘
```

### Iceberg 操作实现

```java
// Spark + Iceberg: 广告事件写入
import org.apache.iceberg.spark.source.SparkTable;
import org.apache.iceberg.catalog.TableIdentifier;

public class AdIcebergWriter {
    
    // 1. 创建表
    public void createTable(SparkSession spark) {
        spark.sql("""
            CREATE TABLE IF NOT EXISTS ad_platform.ad_events (
                event_id LONG,
                campaign_id STRING,
                platform STRING,
                creative_id STRING,
                user_id STRING,
                device_id STRING,
                event_type STRING,
                timestamp TIMESTAMP,
                amount DOUBLE,
                metadata MAP<STRING, STRING>
            )
            PARTITIONED BY (days(timestamp), platform)
            LOCATION 's3://ad-data-lake/ad_events/'
        """);
    }
    
    // 2. 批量写入（Spark Structured Streaming）
    public void batchWrite(SparkSession spark, Dataset<Row> events) {
        events.writeTo("ad_platform.ad_events")
            .option("write-format", "parquet")
            .option("write.parquet.compression-codec", "zstd")
            .append();
    }
    
    // 3. 增量查询（CDC）
    public Dataset<Row> incrementalQuery(SparkSession spark, long fromSnapshot) {
        return spark.read()
            .format("iceberg")
            .option("scan.incremental.snapshot.enabled", "true")
            .load("ad_platform.ad_events");
    }
    
    // 4. 时间旅行（查询历史快照）
    public Dataset<Row> timeTravelQuery(SparkSession spark, long snapshotId) {
        return spark.read()
            .format("iceberg")
            .option("snapshot-id", snapshotId)
            .load("ad_platform.ad_events");
    }
    
    // 5. 删除/更新（MERGE INTO）
    public void mergeData(SparkSession spark) {
        spark.sql("""
            MERGE INTO ad_platform.ad_events e
            USING ad_platform.updates u
            ON e.event_id = u.event_id
            WHEN MATCHED AND u.event_type = 'delete' THEN DELETE
            WHEN MATCHED THEN UPDATE SET
                e.amount = u.amount,
                e.metadata = u.metadata
            WHEN NOT MATCHED THEN INSERT *
        """);
    }
    
    // 6. 压缩小文件（compaction）
    public void compact(SparkSession spark) {
        spark.sql("CALL ad_system.procedure_compact('ad_platform.ad_events')");
    }
}
```

### Iceberg vs Parquet vs Delta vs Hudi

```
┌────────────────┬────────────┬────────────┬────────────┬────────────┐
│     特性        │   Parquet  │  Iceberg   │   Delta    │   Hudi     │
├────────────────┼────────────┼────────────┼────────────┼────────────┤
│ ACID           │    ✗       │    ✓       │    ✓       │    ✓       │
│ 时间旅行        │    ✗       │    ✓       │    ✓       │    ✓       │
│ Schema 演进     │    有限     │    ✓       │    ✓       │    ✓       │
│ Upsert/Delete  │    ✗       │    ✓       │    ✓       │    ✓       │
│ 增量读取        │    ✗       │    ✓       │    ✓       │    ✓       │
│ 引擎支持        │  Spark/Flink/...│ Spark/Flink/Trino│ Spark/Flink/Databricks│ Spark/Flink/Hive│
│ 社区活跃度      │  高        │  高（Apache）│  高（Databricks）│  中高（Apache）│
│ 适合场景        │  只写一次   │  多引擎共享 │  Databricks 生态│  实时 Upsert│
└────────────────┴────────────┴────────────┴────────────┴────────────┘

广告系统推荐：Iceberg
理由：
1. 多引擎共享（Spark/Flink/Trino 都能读）
2. 时间旅行支持归因分析（查询历史状态）
3. Upsert/Delete 支持广告数据修正
4. 社区活跃，AWS/GCP/Azure 都支持
```

---

## 第三部分：实时数仓架构

### 广告实时数仓

```
┌─────────────────────────────────────────────────────────────────────┐
│ 实时数仓架构                                                          │
│                                                                     │
│  数据源层：                                                          │
│  • Kafka: ad.impressions, ad.clicks, ad.conversions                  │
│  • MySQL Binlog: campaigns, budgets, creatives                      │
│  • S3: 历史数据归档                                                   │
│                                                                     │
│  计算层：                                                            │
│  • Flink: 实时聚合（5min 窗口）                                       │
│  • Spark Streaming: 微批处理（1min 窗口）                              │
│  • Trino: 即席查询（跨数据源）                                         │
│                                                                     │
│  存储层：                                                            │
│  • Iceberg (S3): 数据湖，原始数据 + 明细                               │
│  • ClickHouse: 实时看板，预聚合                                       │
│  • Redis: 缓存，热点数据                                              │
│  • Elasticsearch: 日志搜索                                           │
│                                                                     │
│  服务层：                                                            │
│  • BI Dashboard: Grafana/Tableau                                    │
│  • API Service: Go/Python                                           │
│  • ML Training: 特征工程                                             │
└─────────────────────────────────────────────────────────────────────┘
```

### Flink 实时聚合实现

```java
// Flink 实时广告聚合
public class AdRealtimeAggregationJob {
    
    public static void main(String[] args) throws Exception {
        StreamExecutionEnvironment env = StreamExecutionEnvironment.getExecutionEnvironment();
        env.enableCheckpointing(60000); // 1 分钟 checkpoint
        env.getCheckpointConfig().setMinPauseBetweenCheckpoints(30000);
        env.getCheckpointConfig().setCheckpointTimeout(300000);
        
        // 1. 读取 Kafka
        DataStream<AdEvent> events = env.addSource(
            new FlinkKafkaConsumer<>("ad-events", 
                new AdEventDeserializationSchema(), 
                getKafkaProps())
        ).setParallelism(8);
        
        // 2. 水位线（处理乱序）
        DataStream<AdEvent> withWatermark = events
            .assignTimestampsAndWatermarks(
                WatermarkStrategy.<AdEvent>forBoundedOutOfOrderness(Duration.ofSeconds(30))
                    .withTimestampAssigner((event, ts) -> event.getTimestamp().getTime())
            );
        
        // 3. 实时聚合（5 分钟窗口）
        DataStream<AdAggregation> aggregated = withWatermark
            .keyBy(AdEvent::getCampaignId)
            .window(TumblingEventTimeWindows.of(Time.minutes(5)))
            .aggregate(new AdAggregationFunction());
        
        // 4. 写入 ClickHouse
        aggregated.addSink(new ClickHouseSink("jdbc:clickhouse://ch:8123/default"));
        
        // 5. 写入 Redis（实时看板）
        aggregated.addSink(new RedisSink<>("ad:realtime:aggregation"));
        
        // 6. 写入 Iceberg（数据湖）
        aggregated.addSink(new IcebergSink("ad_platform.ad_aggregation"));
        
        env.execute("Ad Realtime Aggregation");
    }
}

// 聚合函数
public class AdAggregationFunction 
    implements AggregateFunction<AdEvent, AdAccumulator, AdAggregation> {
    
    @Override
    public AdAccumulator createAccumulator() {
        return new AdAccumulator(0L, 0L, 0L, 0.0, 0.0, 0.0);
    }
    
    @Override
    public AdAccumulator add(AdEvent event, AdAccumulator acc) {
        switch (event.getType()) {
            case "impression":
                acc.impressions++;
                break;
            case "click":
                acc.clicks++;
                acc.spend += event.getAmount();
                break;
            case "conversion":
                acc.conversions++;
                acc.spend += event.getAmount();
                break;
        }
        return acc;
    }
    
    @Override
    public AdAggregation getResult(AdAccumulator acc) {
        double ctr = acc.impressions > 0 ? (double)acc.clicks / acc.impressions : 0;
        double cpc = acc.clicks > 0 ? acc.spend / acc.clicks : 0;
        double cpa = acc.conversions > 0 ? acc.spend / acc.conversions : 0;
        
        return new AdAggregation(
            acc.impressions, acc.clicks, acc.conversions,
            acc.spend, ctr, cpc, cpa
        );
    }
}
```

---

## 第四部分：数据质量与治理

### 数据质量检查

```python
# Great Expectations 数据质量检查
import great_expectations as gx

context = gx.get_context()

# 定义数据质量规则
suite = context.data_sources["ad_events"].add_checkpoint(
    name="ad_events_quality",
    expectations_suite_name="ad_events_suite"
)

# 质量规则：
# 1. 完整性：event_type, campaign_id, timestamp 不能为空
# 2. 有效性：amount >= 0, impressions >= 0
# 3. 一致性：同一 campaign 的 platform 应该一致
# 4. 时效性：timestamp 不应该超过 1 小时
# 5. 唯一性：event_id 不能重复

# 执行检查
result = suite.run()
if not result["success"]:
    # 发送告警
    send_alert(f"Data quality check failed: {result}")
```

### 数据血缘追踪

```
数据血缘：
Kafka (ad-events) → Flink (实时聚合) → Iceberg (数据湖) → ClickHouse (数仓) → Dashboard

血缘追踪：
1. 字段级：campaign_id 从 Kafka → Flink → Iceberg → ClickHouse → Dashboard
2. 任务级：Flink Job "AdRealtimeAggregation" 读取 ad-events，写入 ad_aggregation
3. 表级：ad_events (Iceberg) 被 ad_aggregation (ClickHouse) 依赖

用途：
• 影响分析：上游表变更会影响哪些下游？
• 故障排查：数据异常时，快速定位源头
• 合规审计：数据使用追溯到源头
```

---

## 第五部分：自测题

### Q1: Iceberg 的 Manifest 文件有什么作用？

**A**: Manifest 文件记录了数据文件的路径和元数据（行数、null 值计数、列的范围）。查询时 Iceberg 先读 Manifest 文件，过滤掉不需要的数据文件，减少扫描量。

### Q2: Flink 水位线为什么重要？

**A**: 水位线处理乱序事件。广告事件可能因为网络延迟乱序到达，水位线允许 Flink 在窗口关闭前等待迟到的事件，保证聚合准确性。

### Q3: 数据湖和数据仓库的区别？

**A**: 数据湖存原始数据（Schema-on-Read），灵活但查询慢；数据仓库存清洗后的数据（Schema-on-Write），查询快但不够灵活。Lakehouse 结合两者优势。

---

## 第六部分：生产实践

### 1. Iceberg 运维

```
Iceberg 运维要点：
• 压缩小文件：定期 compaction，避免太多小文件
• 过期快照清理：DELETE FROM snapshots 清理旧快照
• Schema 演进：谨慎修改 schema，做好版本管理
• 权限控制：IAM/RBAC 控制数据访问
```

### 2. Flink 运维

```
Flink 运维要点：
• Checkpoint：定期 checkpoint 保证故障恢复
• 反压监控：监控 operator 反压，及时调整 parallelism
• State Backend：RocksDB 处理大 state
• 资源管理：YARN/K8s 动态分配资源
```

### 3. 数据质量

```
数据质量要点：
• 实时监控：数据延迟、缺失值、异常值
• 自动告警：质量不达标时立即告警
• 数据修复：发现质量问题时自动修复或标记
• 定期审计：每周/月审计数据质量报告
```
