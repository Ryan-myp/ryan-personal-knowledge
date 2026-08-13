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

<details>
<summary>点击查看详细答案</summary>

### 答案一

广告数据平台采用六层架构：

**数据采集层**: 曝光日志/点击日志/转化日志/用户行为日志，通过 SDK 或服务端埋点收集

**数据摄入层**: Kafka/Flume/Logstash，负责日志聚合和缓冲，削峰填谷

**数据处理层**: Flink(实时)/Spark(批处理)，实现 ETL、特征工程、指标计算

**数据存储层**: ClickHouse(OLAP)/Elasticsearch(搜索)/Redis(缓存)/HDFS(湖仓)，分层存储满足不同查询需求

**数据服务层**: 用户画像/广告推荐/效果分析/报表服务，提供 API 接口供上层应用调用

**应用层**: 广告投放/效果分析/用户画像/BBI 报表，最终业务落地

</details>

2. Kafka Topic 分区数如何设计？

<details>
<summary>点击查看详细答案</summary>

### 答案二

Topic 分区数设计原则：

- **吞吐量**: 分区的数量决定了最大并行处理能力。一般公式：，建议预留 20% 余量

- **消费者**: 分区数应大于等于 Consumer Group 中最大并发消费者数

- **Topic 大小**: 大 Topic 需要更多分区以支持快速恢复和处理

- **具体设计**:
  - ad.impression (曝光日志): 100 分区，每秒百万级曝光写入
  - ad.click (点击日志): 100 分区，吞吐量略低于曝光
  - ad.conversion (转化日志): 50 分区，数据量较小但要求强一致性
  - ad.user.behavior (用户行为): 200 分区，高并发写入，用于实时画像更新

</details>

3. ClickHouse 表如何优化查询性能？

<details>
<summary>点击查看详细答案</summary>

### 答案三

ClickHouse 表优化要点：

- **主键索引**: 选择合适的 ORDER BY 和 PRIMARY KEY，通常按时间 + 核心查询字段组合

- **数据分区**: 按月/天分区，实现分区裁剪（Partition Pruning）

- **稀疏索引**: ClickHouse 默认的稀疏索引适合高基数列查询

- **数据类型优化**: 使用更紧凑的类型（如 UInt32 代替 Int64 如果值域合适）

- **预聚合**: 对常用查询创建 MATERIALIZED VIEW 或汇总表

- **查询优化**: 避免 SELECT *，只查询需要的列；合理使用 LIMIT

</details>

4. Go 语言如何实现生产级的广告曝光日志处理流水线？

<details>
<summary>点击查看详细答案</summary>

### 答案四

Go 实现暴露日志处理流水线：

- 使用  实现多阶段流水线处理（解析 -> 过滤 -> 聚合 -> 写入）

- 利用  并发处理多条日志记录，吞吐线性提升

- 使用  内存池复用日志对象，减少 GC 压力

- 二进制编码（Protocol Buffers）替代 JSON 序列化，减少网络传输体积

- 批处理模式减少 I/O 次数，每次批量写入 1000 条记录

完整代码见本节第六部分动手验证。

</details>

## 六、动手验证

```bash
```

### Go 语言生产级实现

```go
package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"os/signal"
	"syscall"
	"time"

	"github.com/google/uuid"
)

// ImpressionEvent 曝光事件结构
type ImpressionEvent struct {
	EventID     string    `json:"event_id"`
	EventType   string    `json:"event_type"`
	Timestamp   int64     `json:"timestamp"`
	UserID      string    `json:"user_id"`
	DeviceID    string    `json:"device_id"`
	AdID        string    `json:"ad_id"`
	CampaignID  string    `json:"campaign_id"`
	AdGroupID   string    `json:"ad_group_id"`
	CreativeID  string    `json:"creative_id"`
	PlacementID string    `json:"placement_id"`
	SiteID      string    `json:"site_id"`
	IP          string    `json:"ip"`
	OS          string    `json:"os"`
	OSVersion   string    `json:"os_version"`
	DeviceModel string    `json:"device_model"`
	BidPrice    float64   `json:"bid_price"`
	Currency    string    `json:"currency"`
}

// EventProcessor 事件处理器
type EventProcessor struct {
	batchSize int
	writeChan chan []byte
}

func NewEventProcessor(batchSize int) *EventProcessor {
	p := &EventProcessor{
		batchSize: batchSize,
		writeChan: make([]byte, batchSize*10),
	}
	return p
}

// Process 处理单个事件
func (p *EventProcessor) Process(ctx context.Context, event ImpressionEvent) error {
	// 生成唯一 ID
	if event.EventID == "" {
		event.EventID = uuid.New().String()
	}

	// 时间戳校验
	now := time.Now().UnixMilli()
	if event.Timestamp < now-86400000 || event.Timestamp > now+3600000 {
		log.Printf("警告: 时间戳异常 event=%d now=%d", event.Timestamp, now)
	}

	// 序列化到 JSON
	data, err := json.Marshal(event)
	if err != nil {
		return fmt.Errorf("marshal error: %w", err)
	}

	// 异步写入 Kafka（伪代码，实际使用 kafka go 库）
	// p.writeToKafka(data)
	
	return nil
}

// BatchProcessor 批量处理 goroutine
func (p *EventProcessor) BatchProcessor(ctx context.Context) {
	batch := make([]ImpressionEvent, 0, p.batchSize)
	ticker := time.NewTicker(100 * time.Millisecond)

	defer func() {
		// 刷新剩余批次
		if len(batch) > 0 {
			log.Printf("刷新 batch: %d events", len(batch))
		}
	}()

	for {
		select {
		case <-ctx.Done():
			log.Printf("批量处理器停止: %v", ctx.Err())
			return
		case <-ticker.C:
			if len(batch) > 0 {
				// 写入存储
				log.Printf("写入批次: %d events", len(batch))
				batch = batch[:0]
			}
		}
	}
}

func main() {
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	// 设置信号处理
	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)

	processor := NewEventProcessor(1000)

	// 启动批量处理器
	go processor.BatchProcessor(ctx)

	// 模拟处理曝光事件
	go func() {
		for i := 0; i < 10000; i++ {
			event := ImpressionEvent{
				EventType: "impression",
				Timestamp: time.Now().UnixMilli(),
				UserID:    fmt.Sprintf("user_%d", i%1000),
				AdID:      fmt.Sprintf("ad_%d", i%500),
				BidPrice:  float64(i)*0.001 + 0.1,
			}
			processor.Process(ctx, event)
			if i%1000 == 0 {
				log.Printf("已处理 %d 个事件", i)
			}
		}
	}()

	// 等待信号退出
	<-sigCh
	log.Println收到终止信号，正在关闭...
	cancel()
	
	// 等待批量处理器优雅退出
	time.Sleep(2 * time.Second)
	log.Println事件处理器关闭完成")
}
```
