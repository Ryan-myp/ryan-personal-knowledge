package userprofile

import (
	"context"
	"fmt"
	"sync"
	"time"
)

// UserProfile 用户画像
type UserProfile struct {
	UserID    string            `json:"user_id"`
	Interests []string          `json:"interests"`
	Demographics map[string]string `json:"demographics"`
	Behavior  map[string]int    `json:"behavior"`
	Tags      []string          `json:"tags"`
	UpdatedAt time.Time         `json:"updated_at"`
}

// Cache 用户画像缓存
type Cache struct {
	data  map[string]*UserProfile
	mu    sync.RWMutex
	ttl   time.Duration
}

func NewCache(ttl time.Duration) *Cache {
	return &Cache{
		data: make(map[string]*UserProfile),
		ttl:  ttl,
	}
}

func (c *Cache) Get(userID string) (*UserProfile, error) {
	c.mu.RLock()
	defer c.mu.RUnlock()
	
	user, exists := c.data[userID]
	if !exists {
		return nil, fmt.Errorf("user not found: %s", userID)
	}
	
	if time.Since(user.UpdatedAt) > c.ttl {
		return nil, fmt.Errorf("cache expired for user: %s", userID)
	}
	
	return user, nil
}

func (c *Cache) Set(user *UserProfile) {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.data[user.UserID] = user
}

func (c *Cache) Delete(userID string) {
	c.mu.Lock()
	defer c.mu.Unlock()
	delete(c.data, userID)
}

// Service 用户画像服务
type Service struct {
	cache *Cache
	db    *Database
}

func NewService(cache *Cache, db *Database) *Service {
	return &Service{cache: cache, db: db}
}

func (s *Service) GetUserProfile(ctx context.Context, userID string) (*UserProfile, error) {
	// 1. 检查缓存
	user, err := s.cache.Get(userID)
	if err == nil {
		return user, nil
	}
	
	// 2. 查询数据库
	user, err = s.db.GetUserProfile(ctx, userID)
	if err != nil {
		return nil, fmt.Errorf("failed to get user profile: %w", err)
	}
	
	// 3. 写入缓存
	s.cache.Set(user)
	
	return user, nil
}

func (s *Service) TrackBehavior(ctx context.Context, userID, eventType string) error {
	return s.db.TrackBehavior(ctx, userID, eventType)
}

// Database 数据库接口
type Database struct {
	data map[string]*UserProfile
	mu   sync.RWMutex
}

func NewDatabase() *Database {
	return &Database{data: make(map[string]*UserProfile)}
}

func (db *Database) GetUserProfile(ctx context.Context, userID string) (*UserProfile, error) {
	db.mu.RLock()
	defer db.mu.RUnlock()
	
	user, exists := db.data[userID]
	if !exists {
		return nil, fmt.Errorf("user not found: %s", userID)
	}
	
	return user, nil
}

func (db *Database) TrackBehavior(ctx context.Context, userID, eventType string) error {
	db.mu.Lock()
	defer db.mu.Unlock()
	
	user, exists := db.data[userID]
	if !exists {
		user = &UserProfile{UserID: userID, UpdatedAt: time.Now()}
		db.data[userID] = user
	}
	
	if user.Behavior == nil {
		user.Behavior = make(map[string]int)
	}
	user.Behavior[eventType]++
	user.UpdatedAt = time.Now()
	
	return nil
}

// 初始化测试数据
func init() {
	db := NewDatabase()
	db.data["user_123"] = &UserProfile{
		UserID:   "user_123",
		Interests: []string{"electronics", "fashion", "travel"},
		Demographics: map[string]string{
			"age":    "25-34",
			"gender": "male",
			"city":   "San Francisco",
		},
		Behavior: map[string]int{
			"page_view":  150,
			"add_to_cart": 20,
			"purchase":   5,
		},
		Tags:      []string{"high_value", "tech_enthusiast"},
		UpdatedAt: time.Now(),
	}
}
