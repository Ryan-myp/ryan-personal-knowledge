# 广告数据分析：ClickHouse 归因/Spark 特征工程/Data Lake

> 从大数据视角，深度解析广告系统的数据分析架构

---

## 第一部分：ClickHouse 在广告系统中的应用

### 为什么广告数仓用 ClickHouse？

```
ClickHouse 的优势：
1. 列式存储：只读取需要的列，查询速度快
2. 向量化执行：CPU 缓存友好，SIMD 指令优化
3. 数据压缩：LZ4/ZSTD 压缩，节省存储
4. 实时写入：支持 INSERT 和 JOIN
5. 聚合优化：Pre-Aggregation + Materialized View

广告场景匹配：
- 百亿级事件表：曝光/点击/转化
- 实时查询：广告主需要实时看数据
- 多维度聚合：按平台/campaign/creative/geo 聚合
```

### ClickHouse 表设计

```sql
-- 曝光事件表
CREATE TABLE ad_impressions (
    event_id UInt64,
    campaign_id String,
    platform String,
    creative_id String,
    user_id String,
    device_id String,
    ip_address String,
    geo_city String,
    geo_country String,
    timestamp DateTime,
    ad_position UInt8,
    placement String,
    PRIMARY KEY (campaign_id, platform, toYYYYMMDD(timestamp))
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (campaign_id, platform, timestamp);

-- 点击事件表
CREATE TABLE ad_clicks (
    event_id UInt64,
    campaign_id String,
    platform String,
    creative_id String,
    user_id String,
    device_id String,
    ip_address String,
    timestamp DateTime,
    landing_page String,
    PRIMARY KEY (campaign_id, platform, toYYYYMMDD(timestamp))
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (campaign_id, platform, timestamp);

-- 转化事件表
CREATE TABLE ad_conversions (
    event_id UInt64,
    campaign_id String,
    platform String,
    user_id String,
    conversion_type String,  // purchase/lead/install
    conversion_value Float64,
    timestamp DateTime,
    PRIMARY KEY (campaign_id, platform, toYYYYMMDD(timestamp))
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (campaign_id, platform, timestamp);

-- 物化视图（预聚合）
CREATE MATERIALIZED VIEW ad_campaign_daily_mv
ENGINE = AggregatingMergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (campaign_id, platform, timestamp)
AS SELECT
    campaign_id,
    platform,
    toStartOfDay(timestamp) as day,
    count() as impressions,
    countIf(event_type = 'click') as clicks,
    countIf(event_type = 'conversion') as conversions,
    sumIf(amount, event_type = 'conversion') as total_spend,
    uniq(user_id) as unique_users
FROM ad_events
GROUP BY campaign_id, platform, day;
```

### 广告归因查询

```sql
-- 归因分析：Last Click 归因
SELECT
    campaign_id,
    platform,
    COUNT() as total_impressions,
    COUNT() as total_clicks,
    COUNT() as total_conversions,
    total_spend / total_clicks as cpc,
    total_spend / total_conversions as cpa,
    total_conversions * avg_conversion_value / total_spend as roas
FROM ad_campaign_daily_mv
WHERE day BETWEEN '2024-01-01' AND '2024-01-31'
GROUP BY campaign_id, platform
ORDER BY roas DESC;

-- 用户路径分析
SELECT
    user_id,
    arraySort(groupArray(distinct platform)) as platforms_used,
    count() as touchpoints,
    min(timestamp) as first_touch,
    max(timestamp) as last_touch
FROM ad_events
WHERE user_id != ''
GROUP BY user_id
HAVING touchpoints > 1;

-- 多触点归因（MTA）
WITH
    -- 每个用户的触点序列
    user_paths AS (
        SELECT
            user_id,
            arraySort(groupArray(
                tuple(platform, timestamp)
            )) as touchpoints
        FROM ad_events
        WHERE user_id != ''
        GROUP BY user_id
    ),
    -- 最后点击的 platform
    last_touch AS (
        SELECT
            user_id,
            elementAt(touchpoints, length(touchpoints)).1 as last_touch_platform
        FROM user_paths
    )
SELECT
    lt.last_touch_platform,
    COUNT() as attributed_conversions,
    COUNT() / (SELECT COUNT() FROM last_touch) as attribution_rate
FROM last_touch lt
GROUP BY lt.last_touch_platform
ORDER BY attributed_conversions DESC;
```

---

## 第二部分：Spark 特征工程

### 广告特征体系

```
广告特征体系：
┌─────────────────────────────────────────────────────────────────────┐
│ 用户特征（User Features）：                                          │
│ • 静态：年龄、性别、地域、设备                                         │
│ • 动态：最近 7 天点击、最近 30 天转化、活跃天数                        │
│ • 兴趣：基于浏览历史的兴趣标签                                         │
│                                                                     │
│ 广告特征（Ad Features）：                                            │
│ • 静态：广告系列 ID、创意 ID、平台、出价类型                            │
│ • 动态：历史 CTR、历史 CPA、投放天数、剩余预算                          │
│ • 统计：同类广告平均 CTR、同类广告平均 CPA                             │
│                                                                     │
│ 上下文特征（Context Features）：                                     │
│ • 时间：小时、星期、节假日                                             │
│ • 地点：城市、GPS                                                      │
│ • 设备：iOS/Android、网络类型                                          │
└─────────────────────────────────────────────────────────────────────┘
```

### Spark 特征工程实现

```python
from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, count, avg, sum as _sum, max as _max,
    to_date, hour, dayofweek, weekofyear
)
from pyspark.ml.feature import (
    VectorAssembler, Normalizer, OneHotEncoder
)

# 初始化 Spark
spark = SparkSession.builder \
    .appName("AdFeatureEngineering") \
    .config("spark.sql.shuffle.partitions", "200") \
    .getOrCreate()

# 1. 加载事件数据
impressions_df = spark.read.parquet("/data/ad/impressions")
clicks_df = spark.read.parquet("/data/ad/clicks")
conversions_df = spark.read.parquet("/data/ad/conversions")

# 2. 用户级特征
user_features = impressions_df.groupby("user_id").agg(
    count("*").alias("total_impressions_30d"),
    count("user_id").alias("unique_days_active_30d"),
    _sum("impressions").alias("total_impressions_30d"),
    _sum("clicks").alias("total_clicks_30d"),
    _sum("conversions").alias("total_conversions_30d"),
    _sum("spend").alias("total_spend_30d"),
    avg("ctr").alias("avg_ctr_30d"),
    avg("cpc").alias("avg_cpc_30d"),
)

# 3. 广告系列级特征
campaign_features = impressions_df.groupby("campaign_id").agg(
    count("*").alias("total_impressions"),
    _sum("clicks").alias("total_clicks"),
    _sum("conversions").alias("total_conversions"),
    _sum("spend").alias("total_spend"),
    avg("ctr").alias("avg_ctr"),
    avg("cpc").alias("avg_cpc"),
    avg("cpa").alias("avg_cpa"),
    _max("day").alias("last_active_day"),
)

# 4. 时间特征
impressions_with_time = impressions_df.withColumn("hour", hour("timestamp")) \
    .withColumn("day_of_week", dayofweek("timestamp")) \
    .withColumn("is_weekend", (dayofweek("timestamp").isin(1, 7)).cast("int")) \
    .withColumn("is_holiday", (weekofyear("timestamp").isin(1, 52)).cast("int"))

# 5. 交叉特征
cross_features = impressions_df.groupby("campaign_id", "hour").agg(
    count("*").alias("impressions_by_hour"),
    _sum("clicks").alias("clicks_by_hour"),
)

# 6. 合并特征
user_features_df = user_features.withColumnRenamed("user_id", "user_id")
campaign_features_df = campaign_features.withColumnRenamed("campaign_id", "campaign_id")

# 7. 向量化
assembler = VectorAssembler(
    inputCols=["total_impressions_30d", "total_clicks_30d", "total_conversions_30d",
               "avg_ctr_30d", "avg_cpc_30d"],
    outputCol="features"
)
final_df = assembler.transform(user_features_df)
normalizer = Normalizer(inputCol="features", outputCol="normalized_features", p=2.0)
final_df = normalizer.transform(final_df)

# 8. 保存特征
final_df.write.parquet("/data/features/user_features.parquet")
```

---

## 第三部分：Data Lake 架构

```
广告数据湖架构：
┌─────────────────────────────────────────────────────────────────────┐
│ 数据分层：                                                          │
│                                                                     │
│ ODS (原始数据层)：                                                   │
│ • Kafka → S3/HDFS                                                   │
│ • 格式：Parquet + 分区（按天）                                       │
│ • 保留：30 天                                                       │
│                                                                     │
│ DWD (明细数据层)：                                                   │
│ • Spark 清洗、转换、标准化                                           │
│ • 格式：Parquet + 分区（按天 + 平台）                                │
│ • 保留：180 天                                                      │
│                                                                     │
│ DWS (汇总数据层)：                                                   │
│ • ClickHouse 物化视图                                                │
│ • 预聚合：日/周/月粒度                                               │
│ • 保留：永久                                                        │
│                                                                     │
│ ADS (应用数据层)：                                                   │
│ • BI Dashboard 查询                                                  │
│ • 模型训练数据                                                       │
│ • API 服务                                                          │
│                                                                     │
│ 数据质量：                                                          │
│ • Great Expectations / Deequ 数据质量检查                             │
│ • 缺失值检测、异常值检测、一致性检查                                  │
│ • 数据血缘追踪                                                       │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 第四部分：自测题

### Q1: ClickHouse 和 MySQL 在广告系统中的分工？

**A**:
- **MySQL**: 元数据存储（广告系列/创意/用户信息）
- **ClickHouse**: 事件数据聚合（曝光/点击/转化）
- MySQL 适合小数据量强一致性场景，ClickHouse 适合大数据量分析场景

### Q2: Spark 特征工程的关键步骤？

**A**:
1. 加载原始事件数据
2. 用户级聚合（30 天窗口）
3. 广告系列级聚合
4. 时间特征提取
5. 交叉特征构建
6. 向量化和归一化
7. 保存特征供模型使用

### Q3: Data Lake 的分层策略？

**A**:
- ODS：原始数据，保留 30 天
- DWD：清洗转换，保留 180 天
- DWS：预聚合，永久保留
- ADS：应用数据，按需保留

---

## 第五部分：生产实践

### 1. ClickHouse 性能优化

```
ClickHouse 优化：
1. 选择合适的 Primary Key：高频查询字段
2. 使用物化视图：预聚合减少查询时间
3. 分区策略：按月分区，平衡分区数量和查询效率
4. 数据压缩：LZ4 快速，ZSTD 高压缩
5. 合并：定期 OPTIMIZE TABLE 减少分区数
```

### 2. Spark 性能优化

```
Spark 优化：
1. shuffle 优化：调整 partition 数量
2. 缓存：cache() 频繁使用的 DataFrame
3. 广播：broadcast() 小表
4. 过滤：尽早 filter 减少数据量
5. 序列化：使用 Kryo 替代 Java
```

### 3. 数据质量保证

```
数据质量检查：
1. 完整性：检查缺失值
2. 一致性：检查数据格式
3. 准确性：检查异常值
4. 及时性：检查数据延迟
5. 唯一性：检查重复记录
```
