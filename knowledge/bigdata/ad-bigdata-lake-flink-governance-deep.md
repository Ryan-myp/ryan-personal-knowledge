# 广告大数据深度：数据湖/实时计算/数据治理

> 广告系统的大数据架构：数据湖、实时计算、数据治理

---

## 第一部分：广告数据湖架构

### 数据湖 vs 数据仓库

```
数据湖（Data Lake）：
• 存储原始数据（结构化/半结构化/非结构化）
• 格式：Parquet/ORC/Avro
• 计算引擎：Spark/Flink/Trino
• 适用场景：机器学习、探索性分析

数据仓库（Data Warehouse）：
• 存储清洗后的数据
• 格式：列式存储
• 查询引擎：ClickHouse/Trino
• 适用场景：BI 报表、运营分析

广告系统推荐：Lakehouse 架构
• 数据湖存储原始数据
• 数据仓库做实时查询
• 两者通过 CDC 同步
```

### 数据湖实现

```sql
-- Hive 表定义
CREATE EXTERNAL TABLE ad_events_raw (
    event_type STRING,
    campaign_id STRING,
    user_id STRING,
    device_id STRING,
    timestamp BIGINT,
    metadata MAP<STRING, STRING>
)
STORED AS PARQUET
LOCATION 's3://ad-data-lake/raw/events/';

-- Iceberg 表（支持 ACID 和 time travel）
CREATE TABLE ad_events_iceberg (
    event_type STRING,
    campaign_id STRING,
    user_id STRING,
    device_id STRING,
    timestamp TIMESTAMP,
    metadata MAP<STRING, STRING>
) USING iceberg
PARTITIONED BY (bucket(16, campaign_id), days(timestamp));

-- Spark 写入
spark.read.parquet("/data/kafka/events/")
    .write.mode("overwrite")
    .partitionBy("date", "platform")
    .save("s3://ad-data-lake/dwd/events/");
```

---

## 第二部分：Flink 实时计算

### 广告实时聚合

```java
// Flink Job: 实时广告聚合
public class AdRealtimeAggregation {
    public static void main(String[] args) throws Exception {
        StreamExecutionEnvironment env = StreamExecutionEnvironment.getExecutionEnvironment();
        env.setParallelism(4);
        
        // 1. 读取 Kafka 事件
        DataStream<AdEvent> events = env.addSource(
            new FlinkKafkaConsumer<>("ad-events", new AdEventDeserializationSchema(), props)
        );
        
        // 2. 窗口聚合（5 分钟滚动窗口）
        DataStream<AdAggregation> aggregated = events
            .keyBy(event -> event.getCampaignId())
            .window(TumblingProcessingTimeWindows.of(Time.minutes(5)))
            .aggregate(new AdAggregationFunction());
        
        // 3. 写入 ClickHouse
        aggregated.addSink(new ClickHouseSink());
        
        // 4. 写入 Redis（实时看板）
        aggregated.addSink(new RedisSink());
        
        env.execute("Ad Realtime Aggregation");
    }
}

// 聚合函数
public class AdAggregationFunction implements AggregateFunction<AdEvent, AdAccumulator, AdAggregation> {
    @Override
    public AdAccumulator createAccumulator() {
        return new AdAccumulator();
    }
    
    @Override
    public AdAccumulator add(AdEvent event, AdAccumulator acc) {
        acc.impressions++;
        acc.clicks += event.getClicks();
        acc.conversions += event.getConversions();
        acc.spend += event.getAmount();
        return acc;
    }
    
    @Override
    public AdAggregation getResult(AdAccumulator acc) {
        return new AdAggregation(
            acc.impressions,
            acc.clicks,
            acc.conversions,
            acc.spend,
            acc.impressions > 0 ? (double)acc.clicks / acc.impressions : 0,
            acc.clicks > 0 ? acc.spend / acc.clicks : 0
        );
    }
}
```

---

## 第三部分：数据治理

### 数据质量检查

```python
# Great Expectations 数据质量检查
import great_expectations as gx

context = gx.get_context()
suite = context.add_datasource("ad_events").add_checkpoint(
    name="ad_events_quality",
    expectations_suite_name="ad_events_suite"
)

# 定义数据质量规则
suite.add_expectation(
    ExpectColumnValuesToNotBeNull(column="campaign_id"),
    ExpectColumnValuesToBeBetween(
        column="amount", min_value=0, max_value=10000
    ),
    ExpectColumnDistinctValuesToBeInSet(
        column="event_type", value_set=["impression", "click", "conversion"]
    ),
    ExpectTableRowCountToBeBetween(min_value=0, max_value=1000000000)
)
```

### 数据血缘追踪

```
数据血缘：
Kafka → Flink → DWD (Parquet) → DWS (ClickHouse) → ADS (Dashboard)

血缘追踪：
1. 字段级血缘：每个字段从哪里来，到哪里去
2. 任务级血缘：每个 ETL 任务的输入输出
3. 表级血缘：每张表的上下游关系

用途：
• 影响分析：上游表变更会影响哪些下游表
• 故障排查：数据异常时快速定位源头
• 合规审计：数据使用追溯
```

---

## 第四部分：自测题

### Q1: 数据湖和数据仓库的区别？

**A**: 数据湖存原始数据，灵活 schema；数据仓库存清洗后的数据，固定 schema。广告系统推荐 Lakehouse 架构。

### Q2: Flink 实时聚合的关键配置？

**A**: parallelism、watermark（处理乱序）、state backend（RocksDB）、checkpoint 间隔。

### Q3: 数据治理的核心要素？

**A**: 数据质量检查、数据血缘追踪、元数据管理、数据安全管理。

---

## 第五部分：生产实践

### 1. 数据湖运维

```
数据湖运维要点：
• 分区策略：按 date/platform/campaign 分区
• 压缩：Parquet + Snappy
• 生命周期：热数据 30 天，温数据 90 天，冷数据归档
```

### 2. Flink 运维

```
Flink 运维要点：
• 监控：checkpoint 延迟、反压、OOM
• 扩容：动态调整 parallelism
• 容错：savepoint + checkpoint
```

### 3. 数据质量

```
数据质量要点：
• 完整性：检查缺失值
• 准确性：检查异常值
• 一致性：检查跨表一致性
• 及时性：检查数据延迟
```
