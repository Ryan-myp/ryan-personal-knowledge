# 广告数据管道深度：从用户行为到实时报表

> 用户行为采集 → Kafka → Flink → ClickHouse → 实时报表

---

## 第一部分：广告数据管道的核心挑战

### 数据流全景

```
用户行为产生 → 采集 → 传输 → 处理 → 存储 → 查询 → 报表

1. 用户行为：
   → 展示（Impression）
   → 点击（Click）
   → 转化（Conversion）
   → 曝光（View）

2. 数据量：
   → 每天 10 亿次展示
   → 每次展示 1KB 数据
   → 每天 1TB 原始数据
   → 每秒 12KB 写入

3. 实时性要求：
   → 广告主希望看到实时消耗
   → 广告平台需要实时反作弊
   → 竞价引擎需要实时 CTR/CVR
```

### 架构选型对比

| 方案 | 优点 | 缺点 | 适用场景 |
|------|------|------|---------|
| **Lambda 架构** | 批处理+流处理，数据准确 | 双链路维护成本高 | 大数据量 |
| **Kappa 架构** | 只维护流处理，简单 | 历史数据重算慢 | 实时性要求高 |
| **湖仓一体** | 统一存储，成本低 | 查询性能一般 | 数据分析 |

**推荐方案：Kappa 架构 + Flink**

---

## 第二部分：数据管道架构

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                    广告数据管道架构                           │
└─────────────────────────────────────────────────────────────┘

                    ┌─────────────────────────────────────┐
                    │         Client (App/Web)            │
                    │  用户行为：展示/点击/转化             │
                    └──────────────┬──────────────────────┘
                                   │ HTTPS
                    ┌──────────────▼──────────────────────┐
                    │       SDK/Agent (采集层)             │
                    │  - 本地缓存（防丢失）                 │
                    │  - 批量发送（减少请求）               │
                    │  - 断点续传                         │
                    └──────────────┬──────────────────────┘
                                   │
                    ┌──────────────▼──────────────────────┐
                    │       API Gateway                   │
                    │  - 限流                              │
                    │  - 鉴权                              │
                    │  - 日志记录                          │
                    └──────────────┬──────────────────────┘
                                   │
                    ┌──────────────▼──────────────────────┐
                    │       Kafka Cluster                 │
                    │  Topic:                               │
                    │    - ad.impression (展示)             │
                    │    - ad.click (点击)                 │
                    │    - ad.conversion (转化)            │
                    │    - ad.view (曝光)                  │
                    └──────────────┬──────────────────────┘
                                   │
                    ┌──────────────▼──────────────────────┐
                    │       Flink Cluster                 │
                    │  - 实时去重                          │
                    │  - 实时聚合                          │
                    │  - 实时反作弊                        │
                    │  - 实时 CTR/CVR 更新                 │
                    └──────┬──────────┬──────────┬────────┘
                           │          │          │
              ┌────────────▼──┐ ┌─────▼────┐ ┌───▼────────┐
              │  ClickHouse   │ │ Redis    │ │ MySQL      │
              │  - 实时报表    │ │ - 实时指标 │ │ - 用户画像  │
              │  - 历史数据分析│ │ - 缓存   │ │ - 配置     │
              └───────────────┘ └──────────┘ └────────────┘
```

### 2.2 数据模型设计

```sql
-- 展示事件表（ClickHouse）
CREATE TABLE ad_impression (
    event_id       String,       -- 事件 ID（去重用）
    user_id        String,       -- 用户 ID
    ad_id          String,       -- 广告 ID
    campaign_id    String,       -- 广告系列 ID
    adset_id       String,       -- 广告组 ID
    account_id     String,       -- 广告主 ID
    creative_id    String,       -- 创意 ID
    slot_id        String,       -- 广告位 ID
    request_id     String,       -- 请求 ID
    bid_price      Float64,      -- 出价
    win_price      Float64,      -- 成交价
    timestamp      DateTime,     -- 事件时间
    event_time     DateTime,     -- 处理时间
    device_os      String,       -- 设备系统
    device_model   String,       -- 设备型号
    network        String,       -- 网络类型
    city           String,       -- 城市
    ip             String,       -- IP
    ua             String,       -- User Agent
    signature      String,       -- 签名（防篡改）
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (account_id, campaign_id, timestamp)
TTL timestamp + 90 DAY;

-- 点击事件表
CREATE TABLE ad_click (
    event_id       String,
    user_id        String,
    ad_id          String,
    campaign_id    String,
    impression_id  String,       -- 关联的展示事件
    timestamp      DateTime,
    click_time     DateTime,     -- 点击时间（距展示的时间）
    device_os      String,
    device_model   String,
    city           String,
    ip             String,
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (campaign_id, timestamp);

-- 转化事件表
CREATE TABLE ad_conversion (
    event_id       String,
    user_id        String,
    ad_id          String,
    campaign_id    String,
    impression_id  String,
    click_id       String,       -- 关联的点击事件
    conversion_type String,      -- 转化类型（注册/下载/购买）
    conversion_value Float64,    -- 转化价值
    timestamp      DateTime,
    device_os      String,
    city           String,
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (campaign_id, timestamp);
```

---

## 第三部分：数据采集层

### 3.1 SDK 设计

```go
package tracker

import (
    "sync"
    "time"
)

// EventCollector 事件采集器
type EventCollector struct {
    buffer     []*Event
    bufferSize int
    flushInterval time.Duration
    mu         sync.Mutex
    stopped    bool
}

type Event struct {
    Type       string    `json:"type"` // impression/click/conversion
    UserID     string    `json:"user_id"`
    AdID       string    `json:"ad_id"`
    CampaignID string    `json:"campaign_id"`
    AdsetID    string    `json:"adset_id"`
    AccountID  string    `json:"account_id"`
    CreativeID string    `json:"creative_id"`
    SlotID     string    `json:"slot_id"`
    RequestID  string    `json:"request_id"`
    BidPrice   float64   `json:"bid_price"`
    WinPrice   float64   `json:"win_price"`
    Timestamp  time.Time `json:"timestamp"`
    DeviceOS   string    `json:"device_os"`
    DeviceModel string   `json:"device_model"`
    Network    string    `json:"network"`
    City       string    `json:"city"`
    IP         string    `json:"ip"`
    UA         string    `json:"ua"`
}

// NewEventCollector 创建事件采集器
func NewEventCollector(bufferSize int, flushInterval time.Duration) *EventCollector {
    ec := &EventCollector{
        buffer:        make([]*Event, 0, bufferSize),
        bufferSize:    bufferSize,
        flushInterval: flushInterval,
    }
    
    // 启动定时 flush
    go ec.startFlush()
    
    return ec
}

// RecordImpression 记录展示
func (ec *EventCollector) RecordImpression(event *Event) {
    ec.mu.Lock()
    defer ec.mu.Unlock()
    
    ec.buffer = append(ec.buffer, event)
    
    // 达到缓冲区大小，立即 flush
    if len(ec.buffer) >= ec.bufferSize {
        ec.flush()
    }
}

// RecordClick 记录点击
func (ec *EventCollector) RecordClick(event *Event) {
    ec.mu.Lock()
    defer ec.mu.Unlock()
    
    ec.buffer = append(ec.buffer, event)
    
    if len(ec.buffer) >= ec.bufferSize {
        ec.flush()
    }
}

// RecordConversion 记录转化
func (ec *EventCollector) RecordConversion(event *Event) {
    ec.mu.Lock()
    defer ec.mu.Unlock()
    
    ec.buffer = append(ec.buffer, event)
    
    if len(ec.buffer) >= ec.bufferSize {
        ec.flush()
    }
}

// flush 批量发送
func (ec *EventCollector) flush() {
    if len(ec.buffer) == 0 {
        return
    }
    
    // 深拷贝
    events := make([]*Event, len(ec.buffer))
    copy(events, ec.buffer)
    ec.buffer = ec.buffer[:0]
    
    // 异步发送
    go ec.sendEvents(events)
}

// sendEvents 发送事件
func (ec *EventCollector) sendEvents(events []*Event) {
    // 发送到 API Gateway
    // ...
}

// startFlush 启动定时 flush
func (ec *EventCollector) startFlush() {
    ticker := time.NewTicker(ec.flushInterval)
    defer ticker.Stop()
    
    for {
        select {
        case <-ticker.C:
            ec.flush()
        }
    }
}
```

### 3.2 采集策略

```
1. 批量发送：
   → 每 100 条或 1 秒发送一次
   → 减少网络请求

2. 本地缓存：
   → 内存中缓存未发送的事件
   → 崩溃后本地缓存丢失（可接受）

3. 优先级：
   → 转化事件：实时发送（高价值）
   → 点击事件：批量发送（中价值）
   → 展示事件：批量发送（低价值）
```

---

## 第四部分：Flink 实时处理

### 4.1 实时去重

```java
// Flink 实时去重
public class ImpressionDeduplication {
    
    public static DataStream<Event> deduplicate(DataStream<Event> stream) {
        return stream
            .keyBy(Event::getEventId)
            .process(new KeyedProcessFunction<String, Event, Event>() {
                
                private ValueState<Boolean> seenState;
                
                @Override
                public void open(Configuration parameters) {
                    seenState = getRuntimeContext()
                        .getState(new ValueStateDescriptor<>("seen", Boolean.class));
                }
                
                @Override
                public void processElement(Event event, Context ctx, Collector<Event> out) throws Exception {
                    Boolean seen = seenState.value();
                    if (seen == null || !seen) {
                        // 首次出现，处理
                        seenState.update(true);
                        out.collect(event);
                        
                        // 30 秒后清除状态（节省内存）
                        ctx.timerService().registerEventTimeTimer(
                            ctx.eventTimestamp() + 30000);
                    }
                    // 重复出现，丢弃
                }
                
                @Override
                public void onTimer(long timestamp, OnTimerContext ctx, Collector<Event> out) throws Exception {
                    seenState.clear();
                }
            });
    }
}
```

### 4.2 实时聚合

```java
// Flink 实时聚合（每分钟）
public class RealtimeAggregation {
    
    public static DataStream<AggregationResult> aggregate(DataStream<Event> stream) {
        return stream
            .keyBy(Event::getAccountID)
            .keyBy(Event::getTimestamp)
            .window(TumblingProcessingTimeWindows.of(Duration.ofMinutes(1)))
            .aggregate(new AccountAggregation());
    }
    
    public static class AccountAggregation implements AggregateFunction<Event, AggregationState, AggregationResult> {
        
        @Override
        public AggregationState createAccumulator() {
            return new AggregationState();
        }
        
        @Override
        public AggregationState add(Event event, AggregationState acc) {
            acc.impressions++;
            acc.clicks += (event.getType().equals("click") ? 1 : 0);
            acc.conversions += (event.getType().equals("conversion") ? 1 : 0);
            acc.revenue += event.getWinPrice();
            return acc;
        }
        
        @Override
        public AggregationResult getResult(AggregationState acc) {
            return new AggregationResult(
                acc.accountID,
                acc.impressions,
                acc.clicks,
                acc.conversions,
                acc.revenue
            );
        }
        
        @Override
        public AggregationState merge(AggregationState acc1, AggregationState acc2) {
            acc1.impressions += acc2.impressions;
            acc1.clicks += acc2.clicks;
            acc1.conversions += acc2.conversions;
            acc1.revenue += acc2.revenue;
            return acc1;
        }
    }
}
```

### 4.3 实时反作弊

```java
// Flink 实时反作弊
public class FraudDetection {
    
    public static DataStream<Event> detectFraud(DataStream<Event> stream) {
        return stream
            .keyBy(Event::getUserID)
            .process(new KeyedProcessFunction<String, Event, Event>() {
                
                private ValueState<Integer> clickCountState;
                private ValueState<Long> lastClickTimeState;
                
                @Override
                public void open(Configuration parameters) {
                    clickCountState = getRuntimeContext()
                        .getState(new ValueStateDescriptor<>("clickCount", Integer.class));
                    lastClickTimeState = getRuntimeContext()
                        .getState(new ValueStateDescriptor<>("lastClickTime", Long.class));
                }
                
                @Override
                public void processElement(Event event, Context ctx, Collector<Event> out) throws Exception {
                    if (event.getType().equals("click")) {
                        Integer clickCount = clickCountState.value();
                        Long lastClickTime = lastClickTimeState.value();
                        
                        if (clickCount == null) {
                            clickCount = 0;
                        }
                        
                        // 检查点击频率
                        if (clickCount >= 10) { // 1 分钟内点击超过 10 次
                            // 标记为可疑，不发送
                            return;
                        }
                        
                        // 检查点击间隔
                        if (lastClickTime != null) {
                            long interval = event.getTimestamp() - lastClickTime;
                            if (interval < 1000) { // 1 秒内点击
                                return; // 丢弃
                            }
                        }
                        
                        // 更新状态
                        clickCountState.update(clickCount + 1);
                        lastClickTimeState.update(event.getTimestamp());
                        
                        // 1 分钟后重置
                        ctx.timerService().registerEventTimeTimer(
                            event.getTimestamp() + 60000);
                    }
                    
                    out.collect(event);
                }
                
                @Override
                public void onTimer(long timestamp, OnTimerContext ctx, Collector<Event> out) throws Exception {
                    clickCountState.clear();
                    lastClickTimeState.clear();
                }
            });
    }
}
```

---

## 第五部分：ClickHouse 存储

### 5.1 ClickHouse 配置优化

```xml
<!-- config.xml -->
<clickhouse>
    <max_concurrent_queries>100</max_concurrent_queries>
    <max_memory_usage>16000000000</max_memory_usage>
    <max_threads>16</max_threads>
    
    <!-- 合并树配置 -->
    <merge_tree>
        <max_suspicious_broken_parts>5</max_suspicious_broken_parts>
        <part_validity_depth>100</part_validity_depth>
    </merge_tree>
</clickhouse>
```

### 5.2 查询优化

```sql
-- 查询今天的广告主消耗
SELECT 
    account_id,
    SUM(win_price) as total_spend,
    COUNT() as impressions,
    SUM(CASE WHEN type = 'click' THEN 1 ELSE 0 END) as clicks,
    SUM(CASE WHEN type = 'conversion' THEN 1 ELSE 0 END) as conversions
FROM ad_events
WHERE date = today()
GROUP BY account_id
ORDER BY total_spend DESC;

-- 查询每个广告的 CTR/CVR
SELECT 
    ad_id,
    SUM(CASE WHEN type = 'impression' THEN 1 ELSE 0 END) as impressions,
    SUM(CASE WHEN type = 'click' THEN 1 ELSE 0 END) as clicks,
    SUM(CASE WHEN type = 'conversion' THEN 1 ELSE 0 END) as conversions,
    if(impressions > 0, clicks / impressions, 0) as ctr,
    if(clicks > 0, conversions / clicks, 0) as cvr
FROM ad_events
WHERE date = today()
GROUP BY ad_id
HAVING impressions > 1000
ORDER BY ctr DESC;

-- 查询每个广告系列的 ROI
SELECT 
    campaign_id,
    SUM(win_price) as spend,
    SUM(CASE WHEN type = 'conversion' THEN conversion_value ELSE 0 END) as revenue,
    revenue / spend as roi
FROM ad_events
WHERE date = today()
GROUP BY campaign_id
ORDER BY roi DESC;
```

---

## 第六部分：实时报表

### 6.1 报表架构

```
┌─────────────────────────────────────────────────────────────┐
│                    实时报表层                               │
└─────────────────────────────────────────────────────────────┘

                    ┌─────────────────────────────────────┐
                    │       Redis Cache                   │
                    │  - 广告主消耗（每分钟更新）          │
                    │  - 广告系列消耗（每分钟更新）        │
                    │  - 实时 CTR/CVR（每分钟更新）        │
                    └──────────────┬──────────────────────┘
                                   │
                    ┌──────────────▼──────────────────────┐
                    │       API Gateway                   │
                    │  - 广告主后台查询                    │
                    │  - 广告平台后台查询                  │
                    └─────────────────────────────────────┘
```

### 6.2 Redis 实时更新

```go
// 每分钟更新 Redis 缓存
func updateRedisCache() {
    // 1. 从 ClickHouse 查询今天的消耗
    rows, _ := db.Query(`
        SELECT account_id, 
               SUM(win_price) as spend,
               COUNT() as impressions,
               SUM(CASE WHEN type = 'click' THEN 1 ELSE 0 END) as clicks,
               SUM(CASE WHEN type = 'conversion' THEN 1 ELSE 0 END) as conversions
        FROM ad_events
        WHERE date = today()
        GROUP BY account_id
    `)
    
    // 2. 写入 Redis
    for rows.Next() {
        var accountID string
        var spend, impressions, clicks, conversions int64
        rows.Scan(&accountID, &spend, &impressions, &clicks, &conversions)
        
        key := fmt.Sprintf("account:stats:%s:%s", accountID, date)
        redis.HMSet(key, map[string]interface{}{
            "spend":       spend,
            "impressions": impressions,
            "clicks":      clicks,
            "conversions": conversions,
        })
    }
}
```

---

## 第七部分：自测题

### 问题 1
广告数据管道为什么用 Kafka + Flink？

<details>
<summary>查看答案</summary>

1. **Kafka**：高吞吐、低延迟、持久化
2. **Flink**：实时处理、状态管理、Exactly-once
3. **ClickHouse**：列式存储、快速聚合
4. **整体架构**：采集 → Kafka → Flink → ClickHouse → 报表
5. **数据量**：每天 1TB，每秒 12KB 写入
</details>

### 问题 2
如何防止数据重复？

<details>
<summary>查看答案</summary>

1. **事件 ID**：每个事件有唯一 ID
2. **Flink 去重**：KeyedProcessFunction + State
3. **TTL 清除**：30 秒后清除状态
4. **幂等性**：接收端幂等处理
5. **端到端**：采集端 + 传输端 + 处理端都保证幂等
</details>

### 问题 3
ClickHouse 查询优化有哪些？

<details>
<summary>查看答案</summary>

1. **分区**：按月份分区
2. **排序键**：按 account_id, campaign_id, timestamp 排序
3. **TTL**：90 天自动清理
4. **物化视图**：预聚合常用查询
5. **采样**：大数据量时使用 SAMPLE
</details>

---

*本文档基于广告数据管道生产实战整理。*