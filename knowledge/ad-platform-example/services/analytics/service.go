package analytics

import (
	"context"
	"sync"
	"time"
)

// Impression 曝光事件
type Impression struct {
	EventID   string    `json:"event_id"`
	UserID    string    `json:"user_id"`
	AdID      string    `json:"ad_id"`
	CampaignID string   `json:"campaign_id"`
	Timestamp time.Time `json:"timestamp"`
}

// Click 点击事件
type Click struct {
	EventID   string    `json:"event_id"`
	UserID    string    `json:"user_id"`
	AdID      string    `json:"ad_id"`
	CampaignID string   `json:"campaign_id"`
	Timestamp time.Time `json:"timestamp"`
}

// Conversion 转化事件
type Conversion struct {
	EventID      string    `json:"event_id"`
	UserID       string    `json:"user_id"`
	AdID         string    `json:"ad_id"`
	CampaignID   string    `json:"campaign_id"`
	Value        float64   `json:"value"`
	Timestamp    time.Time `json:"timestamp"`
}

// AnalyticsService 分析服务
type AnalyticsService struct {
	impressions map[string]int
	clicks      map[string]int
	conversions map[string]float64
	mu          sync.RWMutex
}

func NewAnalyticsService() *AnalyticsService {
	return &AnalyticsService{
		impressions: make(map[string]int),
		clicks:      make(map[string]int),
		conversions: make(map[string]float64),
	}
}

func (s *AnalyticsService) RecordImpression(ctx context.Context, imp Impression) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.impressions[imp.AdID]++
}

func (s *AnalyticsService) RecordClick(ctx context.Context, click Click) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.clicks[click.AdID]++
}

func (s *AnalyticsService) RecordConversion(ctx context.Context, conv Conversion) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.conversions[conv.AdID] += conv.Value
}

func (s *AnalyticsService) GetMetrics(adID string) (impressions, clicks int, conversionValue float64) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.impressions[adID], s.clicks[adID], s.conversions[adID]
}
