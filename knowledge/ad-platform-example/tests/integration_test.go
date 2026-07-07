package tests

import (
	"context"
	"testing"
	"time"
	
	"ad-platform-example/services/userprofile"
	"ad-platform-example/services/bidding"
	"ad-platform-example/services/creative"
	"ad-platform-example/services/analytics"
	"ad-platform-example/pipeline"
)

func TestUserProfile(t *testing.T) {
	cache := userprofile.NewCache(30 * time.Minute)
	db := userprofile.NewDatabase()
	service := userprofile.NewService(cache, db)
	
	ctx := context.Background()
	user, err := service.GetUserProfile(ctx, "user_123")
	if err != nil {
		t.Fatalf("Failed to get user profile: %v", err)
	}
	
	if user.UserID != "user_123" {
		t.Errorf("Expected user_123, got %s", user.UserID)
	}
	
	t.Logf("User profile: %+v", user)
}

func TestBidding(t *testing.T) {
	engine := bidding.NewBidEngine(10.0, 4.0)
	
	req := &bidding.BidRequest{
		UserID:    "user_123",
		AdSlotID:  "slot_1",
		Timestamp: time.Now(),
		Device:    "mobile",
		Location:  "US",
	}
	
	resp, err := engine.CalculateBid(context.Background(), req)
	if err != nil {
		t.Fatalf("Failed to calculate bid: %v", err)
	}
	
	t.Logf("Bid response: %+v", resp)
	
	if resp.BidPrice <= 0 {
		t.Error("Bid price should be positive")
	}
}

func TestCreative(t *testing.T) {
	service := creative.NewCreativeService()
	
	creative, err := service.Match(context.Background(), "user_123", "electronics")
	if err != nil {
		t.Fatalf("Failed to match creative: %v", err)
	}
	
	t.Logf("Matched creative: %+v", creative)
}

func TestAnalytics(t *testing.T) {
	service := analytics.NewAnalyticsService()
	
	service.RecordImpression(context.Background(), analytics.Impression{
		EventID:   "imp_1", UserID: "user_123", AdID: "ad_1", CampaignID: "camp_1", Timestamp: time.Now(),
	})
	
	service.RecordClick(context.Background(), analytics.Click{
		EventID:   "clk_1", UserID: "user_123", AdID: "ad_1", CampaignID: "camp_1", Timestamp: time.Now(),
	})
	
	service.RecordConversion(context.Background(), analytics.Conversion{
		EventID: "conv_1", UserID: "user_123", AdID: "ad_1", CampaignID: "camp_1", Value: 99.98, Timestamp: time.Now(),
	})
	
	imp, clk, convVal := service.GetMetrics("ad_1")
	
	if imp != 1 {
		t.Errorf("Expected 1 impression, got %d", imp)
	}
	if clk != 1 {
		t.Errorf("Expected 1 click, got %d", clk)
	}
	if convVal != 99.98 {
		t.Errorf("Expected $99.98, got $%.2f", convVal)
	}
}

func TestPipeline(t *testing.T) {
	pipeline := pipeline.NewPipeline()
	err := pipeline.Run(context.Background())
	if err != nil {
		t.Fatalf("Pipeline failed: %v", err)
	}
	t.Log("Pipeline executed successfully")
}
