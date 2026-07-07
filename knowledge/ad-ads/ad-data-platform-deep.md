# 广告数据平台架构深度实战

## 一、广告数据平台全景

### 1.1 平台定位

广告数据平台是广告系统的核心基础设施，负责收集、处理、存储和分析广告曝光、点击、转化等数据。

**核心价值：**
- 实时数据处理：毫秒级处理千万级广告请求
- 精准用户画像：基于行为数据构建用户画像
- 智能投放优化：基于数据驱动的投放策略优化
- 效果归因分析：多触点归因，量化广告价值

### 1.2 架构分层

```
数据采集层
├── 曝光日志 (Impression Log)
├── 点击日志 (Click Log)
├── 转化日志 (Conversion Log)
└── 用户行为日志 (User Behavior Log)

数据摄入层
├── Kafka (消息队列)
├── Flume (日志收集)
└── Logstash (日志处理)

数据处理层
├── Flink (实时计算)
├── Spark (批处理)
└── Storm (实时计算)

数据存储层
├── ClickHouse (OLAP 分析)
├── Elasticsearch (搜索检索)
├── Redis (缓存)
└── HDFS (数据湖)

数据服务层
├── 用户画像服务
├── 广告推荐服务
├── 效果分析服务
└── 报表服务

应用层
├── 广告投放系统
├── 效果分析平台
├── 用户画像平台
└── BI 报表系统
```

## 二、数据采集与摄入

### 2.1 日志格式设计

```json
{
  "event_id": "evt_1234567890",
  "event_type": "impression",
  "timestamp": 1704067200000,
  "user_id": "user_12345",
  "device_id": "dev_abc123",
  "ad_id": "ad_67890",
  "campaign_id": "camp_11111",
  "ad_group_id": "ag_22222",
  "creative_id": "creative_33333",
  "placement_id": "placement_44444",
  "site_id": "site_55555",
  "ip": "192.168.1.1",
  "os": "iOS",
  "os_version": "17.0",
  "device_model": "iPhone 15",
  "location": {
    "country": "US",
    "region": "California",
    "city": "San Francisco",
    "lat": 37.7749,
    "lng": -122.4194
  },
  "bid_price": 0.50,
  "currency": "USD"
}
```

### 2.2 Kafka Topic 设计

| Topic | 说明 | 分区数 | 保留时间 |
|-------|------|--------|----------|
| ad.impression | 曝光日志 | 100 | 7 天 |
| ad.click | 点击日志 | 100 | 7 天 |
| ad.conversion | 转化日志 | 50 | 30 天 |
| ad.user.behavior | 用户行为 | 200 | 3 天 |
| ad.realtime.stats | 实时统计 | 10 | 1 天 |

## 三、实时计算引擎

### 3.1 Flink 实时统计

```java
public class RealtimeStatsJob {
    public static void main(String[] args) throws Exception {
        StreamExecutionEnvironment env = StreamExecutionEnvironment.getExecutionEnvironment();
        
        // 读取曝光日志
        DataStream<ImpressionEvent> impressions = env
            .addSource(new KafkaSource<>("ad.impression"))
            .keyBy(ImpressionEvent::getUserId);
        
        // 读取点击日志
        DataStream<ClickEvent> clicks = env
            .addSource(new KafkaSource<>("ad.click"))
            .keyBy(ClickEvent::getUserId);
        
        // 实时 CTR 统计
        impressions.connect(clicks)
            .keyBy(e -> e.getUserId())
            .process(new CTRCalculator())
            .addSink(new KafkaSink<>("ad.realtime.stats"));
        
        env.execute("Realtime Stats Job");
    }
}

public class CTRCalculator extends KeyedProcessFunction<String, ImpressionEvent, ClickEvent, String> {
    private ValueState<Long> impressionCount;
    private ValueState<Long> clickCount;
    
    @Override
    public void open(Configuration parameters) {
        impressionCount = getRuntimeContext().getState(
            new ValueStateDescriptor<>("impressionCount", Long.class));
        clickCount = getRuntimeContext().getState(
            new ValueStateDescriptor<>("clickCount", Long.class));
    }
    
    @Override
    public void processElement(ImpressionEvent value, Context ctx, Collector<String> out) 
            throws Exception {
        Long impressions = impressionCount.value() == null ? 0 : impressionCount.value();
        impressionCount.update(impressions + 1);
        
        if (impressions % 1000 == 0) {
            Long clicks = clickCount.value() == null ? 0 : clickCount.value();
            double ctr = impressions > 0 ? (double) clicks / impressions : 0;
            out.collect(String.format("{\"user_id\":\"%s\",\"ctr\":%.4f}", 
                value.getUserId(), ctr));
        }
    }
}
```

## 四、数据存储与查询

### 4.1 ClickHouse 表设计

```sql
-- 曝光明细表
CREATE TABLE ad_impressions (
    event_id String,
    event_time DateTime,
    user_id String,
    device_id String,
    ad_id String,
    campaign_id String,
    ad_group_id String,
    creative_id String,
    placement_id String,
    site_id String,
    country String,
    region String,
    city String,
    os String,
    os_version String,
    device_model String,
    bid_price Decimal(10,4),
    currency String
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(event_time)
ORDER BY (campaign_id, event_time)
TTL event_time + INTERVAL 30 DAY;

-- 实时统计表
CREATE TABLE ad_realtime_stats (
    hour DateTime,
    campaign_id String,
    impressions UInt64,
    clicks UInt64,
    conversions UInt64,
    cost Decimal(10,2),
    ctr Float64,
    cvr Float64,
    cpc Decimal(10,4),
    ecpm Decimal(10,2)
) ENGINE = AggregatingMergeTree()
ORDER BY (hour, campaign_id);
```

### 4.2 查询优化

```sql
-- 查询今日各广告系列表现
SELECT 
    campaign_id,
    sum(impressions) as impressions,
    sum(clicks) as clicks,
    sum(conversions) as conversions,
    sum(cost) as cost,
    sum(impressions) > 0 ? sum(clicks) / sum(impressions) : 0 as ctr,
    sum(clicks) > 0 ? sum(conversions) / sum(clicks) : 0 as cvr,
    sum(clicks) > 0 ? sum(cost) / sum(clicks) : 0 as cpc
FROM ad_realtime_stats
WHERE hour >= today()
GROUP BY campaign_id
ORDER BY cost DESC;
```

## 五、自测题

1. 广告数据平台的架构分层是怎样的？
2. Kafka Topic 如何设计？
3. ClickHouse 表如何优化查询性能？

## 六、动手验证

```bash
# 1. 搭建 Kafka 集群
# 2. 配置 Flink 实时计算
# 3. 部署 ClickHouse
# 4. 编写查询语句
# 5. 验证数据准确性
```
