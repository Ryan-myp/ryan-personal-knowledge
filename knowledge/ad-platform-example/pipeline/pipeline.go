package pipeline

import (
	"context"
	"fmt"
	"time"
)

// Event 事件基类
type Event struct {
	Type      string    `json:"type"`
	Timestamp time.Time `json:"timestamp"`
	Payload   []byte    `json:"payload"`
}

// ImpressionEvent 曝光事件
type ImpressionEvent struct {
	EventID   string    `json:"event_id"`
	UserID    string    `json:"user_id"`
	AdID      string    `json:"ad_id"`
	CampaignID string   `json:"campaign_id"`
	Timestamp time.Time `json:"timestamp"`
}

// ClickEvent 点击事件
type ClickEvent struct {
	EventID   string    `json:"event_id"`
	UserID    string    `json:"user_id"`
	AdID      string    `json:"ad_id"`
	CampaignID string   `json:"campaign_id"`
	Timestamp time.Time `json:"timestamp"`
}

// ConversionEvent 转化事件
type ConversionEvent struct {
	EventID      string    `json:"event_id"`
	UserID       string    `json:"user_id"`
	AdID         string    `json:"ad_id"`
	CampaignID   string    `json:"campaign_id"`
	Value        float64   `json:"value"`
	Timestamp    time.Time `json:"timestamp"`
}

// KafkaProducer Kafka 生产者
type KafkaProducer struct {
	brokers []string
	topic   string
}

func NewKafkaProducer(brokers []string, topic string) *KafkaProducer {
	return &KafkaProducer{brokers: brokers, topic: topic}
}

func (p *KafkaProducer) Produce(ctx context.Context, event Event) error {
	fmt.Printf("[Kafka] Publishing event to topic %s: %s\n", p.topic, event.Type)
	// 实际实现会调用 Kafka API
	return nil
}

// FlinkProcessor Flink 实时处理器
type FlinkProcessor struct {
	windowSize time.Duration
}

func NewFlinkProcessor(window time.Duration) *FlinkProcessor {
	return &FlinkProcessor{windowSize: window}
}

func (p *FlinkProcessor) ProcessImpressions(ctx context.Context, events []ImpressionEvent) map[string]int {
	counts := make(map[string]int)
	for _, event := range events {
		counts[event.CampaignID]++
	}
	fmt.Printf("[Flink] Processed %d impressions in window %v\n", len(events), p.windowSize)
	return counts
}

func (p *FlinkProcessor) ProcessClicks(ctx context.Context, events []ClickEvent) (map[string]int, map[string]int) {
	clickCounts := make(map[string]int)
	ctrByCampaign := make(map[string]int)
	for _, event := range events {
		clickCounts[event.CampaignID]++
		ctrByCampaign[event.CampaignID]++
	}
	fmt.Printf("[Flink] Processed %d clicks\n", len(events))
	return clickCounts, ctrByCampaign
}

// ClickHouseSink ClickHouse 写入器
type ClickHouseSink struct {
	host     string
	port     int
	database string
	table    string
}

func NewClickHouseSink(host string, port int, database, table string) *ClickHouseSink {
	return &ClickHouseSink{host: host, port: port, database: database, table: table}
}

func (s *ClickHouseSink) InsertImpressions(ctx context.Context, events []ImpressionEvent) error {
	fmt.Printf("[ClickHouse] Inserting %d impressions to %s.%s\n", len(events), s.database, s.table)
	return nil
}

func (s *ClickHouseSink) InsertClicks(ctx context.Context, events []ClickEvent) error {
	fmt.Printf("[ClickHouse] Inserting %d clicks to %s.%s\n", len(events), s.database, s.table)
	return nil
}

func (s *ClickHouseSink) InsertConversions(ctx context.Context, events []ConversionEvent) error {
	fmt.Printf("[ClickHouse] Inserting %d conversions to %s.%s\n", len(events), s.database, s.table)
	return nil
}

// Pipeline 数据管道
type Pipeline struct {
	producer   *KafkaProducer
	flink      *FlinkProcessor
	clickhouse *ClickHouseSink
}

func NewPipeline() *Pipeline {
	return &Pipeline{
		producer:   NewKafkaProducer([]string{"localhost:9092"}, "ad-events"),
		flink:      NewFlinkProcessor(5 * time.Minute),
		clickhouse: NewClickHouseSink("localhost", 9000, "ads", "events"),
	}
}

func (p *Pipeline) Run(ctx context.Context) error {
	fmt.Println("[Pipeline] Starting data pipeline...")
	
	// 模拟数据流
	impressions := []ImpressionEvent{
		{EventID: "imp_1", UserID: "user_123", AdID: "ad_1", CampaignID: "camp_1", Timestamp: time.Now()},
		{EventID: "imp_2", UserID: "user_456", AdID: "ad_2", CampaignID: "camp_1", Timestamp: time.Now()},
	}
	
	clicks := []ClickEvent{
		{EventID: "clk_1", UserID: "user_123", AdID: "ad_1", CampaignID: "camp_1", Timestamp: time.Now()},
	}
	
	conversions := []ConversionEvent{
		{EventID: "conv_1", UserID: "user_123", AdID: "ad_1", CampaignID: "camp_1", Value: 99.98, Timestamp: time.Now()},
	}
	
	// 1. 发送到 Kafka
	for _, imp := range impressions {
		event := Event{Type: "impression", Payload: []byte(fmt.Sprintf("%v", imp))}
		p.producer.Produce(ctx, event)
	}
	
	// 2. Flink 实时计算
	p.flink.ProcessImpressions(ctx, impressions)
	p.flink.ProcessClicks(ctx, clicks)
	
	// 3. 写入 ClickHouse
	p.clickhouse.InsertImpressions(ctx, impressions)
	p.clickhouse.InsertClicks(ctx, clicks)
	p.clickhouse.InsertConversions(ctx, conversions)
	
	fmt.Println("[Pipeline] Pipeline executed successfully")
	return nil
}
