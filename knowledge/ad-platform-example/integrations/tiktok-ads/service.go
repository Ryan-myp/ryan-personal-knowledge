package tiktokads

import (
	"context"
	"fmt"
	"time"
)

// Campaign 广告系列
type Campaign struct {
	ID            string    `json:"id"`
	Name          string    `json:"name"`
	Status        string    `json:"status"`
	Objective     string    `json:"objective"` // SALES, APP_PROMOTION
	Budget        float64   `json:"budget"`
	BidStrategy   string    `json:"bid_strategy"`
	StartTime     time.Time `json:"start_time"`
	EndTime       time.Time `json:"end_time"`
}

// AdGroup 广告组
type AdGroup struct {
	ID          string    `json:"id"`
	Name        string    `json:"name"`
	CampaignID  string    `json:"campaign_id"`
	Status      string    `json:"status"`
	Budget      float64   `json:"budget"`
	BidStrategy string    `json:"bid_strategy"`
	Targeting   Targeting `json:"targeting"`
}

type Targeting struct {
	Interests []Interest `json:"interests"`
	Behaviors []string   `json:"behaviors"`
	Locations []string   `json:"locations"`
}

type Interest struct {
	ID   string `json:"id"`
	Name string `json:"name"`
}

// Ad 广告
type Ad struct {
	ID          string   `json:"id"`
	AdGroupID   string   `json:"ad_group_id"`
	Name        string   `json:"name"`
	Status      string   `json:"status"`
	PrimaryText string   `json:"primary_text"`
	Title       string   `json:"title"`
	Description string   `json:"description"`
	CTA         string   `json:"cta"`
	ImageURL    string   `json:"image_url"`
	VideoURL    string   `json:"video_url"`
}

// Service TikTok Ads 服务
type Service struct {
	accessToken  string
	advertiserID string
}

func NewService(accessToken, advertiserID string) *Service {
	return &Service{accessToken: accessToken, advertiserID: advertiserID}
}

func (s *Service) CreateCampaign(ctx context.Context, campaign *Campaign) error {
	fmt.Printf("[TikTok Ads] Creating campaign: %s (Objective: %s)\n", campaign.Name, campaign.Objective)
	return nil
}

func (s *Service) CreateAdGroup(ctx context.Context, adGroup *AdGroup) error {
	fmt.Printf("[TikTok Ads] Creating ad group: %s\n", adGroup.Name)
	return nil
}

func (s *Service) CreateAd(ctx context.Context, ad *Ad) error {
	fmt.Printf("[TikTok Ads] Creating ad: %s\n", ad.Name)
	return nil
}

func (s *Service) GetCampaignMetrics(ctx context.Context, campaignID string) (map[string]interface{}, error) {
	return map[string]interface{}{
		"impressions": 8000,
		"clicks":      320,
		"ctr":         0.04,
		"cpc":         0.75,
		"conversions": 16,
		"roas":        3.2,
	}, nil
}
