package creative

import (
	"context"
	"fmt"
	"sync"
)

// Creative 广告创意
type Creative struct {
	ID          string   `json:"id"`
	Type        string   `json:"type"` // image, video, carousel
	Title       string   `json:"title"`
	Description string   `json:"description"`
	ImageURL    string   `json:"image_url"`
	VideoURL    string   `json:"video_url"`
	CTA         string   `json:"cta"`
	TargetURL   string   `json:"target_url"`
	Labels      []string `json:"labels"`
}

// CreativeService 创意服务
type CreativeService struct {
	creatives map[string][]*Creative
	mu        sync.RWMutex
}

func NewCreativeService() *CreativeService {
	return &CreativeService{
		creatives: make(map[string][]*Creative),
	}
}

func (s *CreativeService) Match(ctx context.Context, userID, interests string) (*Creative, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	
	// 根据用户兴趣匹配创意
	for _, creatives := range s.creatives {
		for _, c := range creatives {
			for _, label := range c.Labels {
				if label == interests {
					return c, nil
				}
			}
		}
	}
	
	return nil, fmt.Errorf("no matching creative found")
}

// 初始化测试数据
func init() {
	service := NewCreativeService()
	service.creatives["electronics"] = []*Creative{
		{
			ID:          "creative_001",
			Type:        "image",
			Title:       "Latest Smartphones",
			Description: "Check out our newest collection",
			ImageURL:    "https://example.com/smartphone.jpg",
			CTA:         "Shop Now",
			TargetURL:   "https://example.com/smartphones",
			Labels:      []string{"electronics", "smartphone"},
		},
		{
			ID:          "creative_002",
			Type:        "carousel",
			Title:       "Summer Sale",
			Description: "Up to 50% off on electronics",
			ImageURL:    "https://example.com/summer-sale.jpg",
			CTA:         "Buy Now",
			TargetURL:   "https://example.com/sale",
			Labels:      []string{"electronics", "sale"},
		},
	}
}
