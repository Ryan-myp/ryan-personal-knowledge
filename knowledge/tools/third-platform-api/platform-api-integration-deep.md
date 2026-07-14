# 广告平台 API 集成深度实战：Meta/GTikTok/Google Ads

> **来源**：官方 API 文档 + 开源 SDK 源码解析 + 生产实践
> **创建日期**：2026-07-10
> **深度等级**：🟢深（源码级）

---

## 一、为什么广告平台 API 集成是难点？

### 1.1 核心挑战矩阵

| 挑战 | Meta Ads API | TikTok Marketing API | Google Ads API |
|------|-------------|---------------------|----------------|
| **认证方式** | OAuth 2.0 + App Secret | OAuth 2.0 + Access Token | OAuth 2.0 + Developer Token |
| **速率限制** | 20 req/900s per ad account | 50 req/min per app | 1000 req/day per developer token |
| **数据模型** | Campaign/AdSet/Ad 三级 | Campaign/AdGroup/Ad 三级 | Campaign/AdGroup/Ad 三级 |
| **更新模式** | REST + Batch | REST + Webhook | gRPC + REST |
| **字段变更** | 频繁（季度大更） | 中等 | 较少 |

### 1.2 共同痛点

```
1. 认证过期 → 需要 Token 刷新机制
2. 速率限制 → 需要智能限流 + 队列管理
3. 字段不一致 → 需要抽象层屏蔽差异
4. 增量同步 → 需要高效的数据变更检测
5. 错误处理 → 需要重试 + 降级策略
```

---

## 二、统一 API 抽象层设计

### 2.1 架构设计

```
┌─────────────────────────────────────────────────────┐
│                  Application Layer                   │
│                                                      │
│  CampaignManager  BudgetManager  ReportGenerator     │
└──────────────────┬──────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────┐
│              Unified API Interface                   │
│                                                      │
│  interface PlatformAPI {                            │
│      CreateCampaign(ctx, Campaign) error             │
│      UpdateBudget(ctx, CampaignID, Budget) error     │
│      GetPerformance(ctx, Filter) (*Report, error)    │
│      ListCreatives(ctx, Filter) ([]Creative, error)  │
│  }                                                  │
└──────────────────┬──────────────────────────────────┘
                   │
    ┌──────────────┼──────────────┐
    ▼              ▼              ▼
┌────────┐   ┌────────┐   ┌────────┐
│ Meta   │   │TikTok  │   │ Google │
│ Adapter│   │Adapter │   │ Adapter│
└────────┘   └────────┘   └────────┘
    │              │              │
    ▼              ▼              ▼
┌────────┐   ┌────────┐   ┌────────┐
│ Meta   │   │TikTok  │   │ Google │
│ REST   │   │ REST   │   │ gRPC   │
└────────┘   └────────┘   └────────┘
```

### 2.2 Go 实现：统一接口

```go
package platform

import (
	"context"
	"time"
)

// Campaign 统一广告活动模型
type Campaign struct {
	ID          string
	Name        string
	Status      CampaignStatus
	Budget      float64
	Currency    string
	Platform    PlatformType
	CreatedAt   time.Time
	UpdatedAt   time.Time
	Metadata    map[string]interface{}
}

type CampaignStatus string

const (
	CampaignActive   CampaignStatus = "ACTIVE"
	CampaignPaused   CampaignStatus = "PAUSED"
	CampaignDeleted  CampaignStatus = "DELETED"
)

type PlatformType string

const (
	PlatformMeta     PlatformType = "meta"
	PlatformTikTok   PlatformType = "tiktok"
	PlatformGoogle   PlatformType = "google"
)

// PerformanceReport 性能报告
type PerformanceReport struct {
	CampaignID     string
	Date           time.Time
	Impressions    int64
	Clicks         int64
	Spent          float64
	Conversions    int64
	CTR            float64
	CPC            float64
	CPA            float64
}

// PlatformAPI 统一平台 API 接口
type PlatformAPI interface {
	// Campaign CRUD
	CreateCampaign(ctx context.Context, campaign *Campaign) (*Campaign, error)
	UpdateCampaign(ctx context.Context, campaign *Campaign) error
	DeleteCampaign(ctx context.Context, id string) error
	GetCampaign(ctx context.Context, id string) (*Campaign, error)
	ListCampaigns(ctx context.Context, filter *CampaignFilter) ([]*Campaign, error)
	
	// Budget Management
	UpdateBudget(ctx context.Context, campaignID string, budget float64) error
	GetBudget(ctx context.Context, campaignID string) (float64, error)
	
	// Performance
	GetPerformance(ctx context.Context, campaignID string, start, end time.Time) ([]*PerformanceReport, error)
	
	// Creatives
	ListCreatives(ctx context.Context, campaignID string) ([]*Creative, error)
	CreateCreative(ctx context.Context, creative *Creative) (*Creative, error)
	
	// Health
	HealthCheck(ctx context.Context) error
}

// CampaignFilter 广告活动过滤条件
type CampaignFilter struct {
	Platform   PlatformType
	Status     []CampaignStatus
	CreatedAfter time.Time
	CreatedBefore time.Time
	BudgetMin  float64
	BudgetMax  float64
	Tags       []string
}

// Creative 创意素材
type Creative struct {
	ID         string
	CampaignID string
	Type       CreativeType // IMAGE, VIDEO, CAROUSEL
	Title      string
	Description string
	ThumbnailURL string
	AssetURLs  []string
	Status     CreativeStatus
	CreatedAt  time.Time
}

type CreativeType string
type CreativeStatus string
```

### 2.3 元数据适配器模式

```go
package adapter

import (
	"context"
	"fmt"
	"sync"
	"time"
)

// Registry 适配器注册表
type Registry struct {
	adapters map[PlatformType]PlatformAPI
	mu       sync.RWMutex
}

func NewRegistry() *Registry {
	return &Registry{
		adapters: make(map[PlatformType]PlatformAPI),
	}
}

// Register 注册平台适配器
func (r *Registry) Register(platform PlatformType, api PlatformAPI) {
	r.mu.Lock()
	defer r.mu.Unlock()
	r.adapters[platform] = api
}

// Get 获取平台适配器
func (r *Registry) Get(platform PlatformType) (PlatformAPI, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()
	
	api, ok := r.adapters[platform]
	if !ok {
		return nil, fmt.Errorf("platform %s not registered", platform)
	}
	
	return api, nil
}

// MultiPlatformClient 多平台客户端
type MultiPlatformClient struct {
	registry *Registry
	logger   Logger
}

func NewMultiPlatformClient(registry *Registry, logger Logger) *MultiPlatformClient {
	return &MultiPlatformClient{registry: registry, logger: logger}
}

// CreateCampaignAcrossPlatforms 跨平台创建活动
func (c *MultiPlatformClient) CreateCampaignAcrossPlatforms(
	ctx context.Context,
	campaign *Campaign,
) map[PlatformType]error {
	results := make(map[PlatformType]error)
	
	platforms := []PlatformType{PlatformMeta, PlatformTikTok, PlatformGoogle}
	
	for _, platform := range platforms {
		api, err := c.registry.Get(platform)
		if err != nil {
			results[platform] = err
			continue
		}
		
		// 转换平台特定字段
		platformCampaign := c.convertToPlatform(campaign, platform)
		
		start := time.Now()
		_, err = api.CreateCampaign(ctx, platformCampaign)
		duration := time.Since(start)
		
		if err != nil {
			c.logger.Errorf("create campaign on %s failed: %v (%v)", platform, err, duration)
		} else {
			c.logger.Infof("campaign created on %s in %v", platform, duration)
		}
		
		results[platform] = err
	}
	
	return results
}

// convertToPlatform 转换为平台特定格式
func (c *MultiPlatformClient) convertToPlatform(campaign *Campaign, platform PlatformType) *Campaign {
	switch platform {
	case PlatformMeta:
		// Meta 需要额外的 targeting 字段
		campaign.Metadata["ad_account_id"] = campaign.Metadata["meta_ad_account_id"]
	case PlatformTikTok:
		// TikTok 使用不同的预算单位（CNY vs USD）
		if campaign.Currency == "USD" {
			campaign.Budget = campaign.Budget * 7.2 // 汇率
			campaign.Currency = "CNY"
		}
	case PlatformGoogle:
		// Google 需要 campaign ID 前缀
		campaign.Name = "[GCL] " + campaign.Name
	}
	
	return campaign
}
```

---

## 三、Meta Ads API 深度实现

### 3.1 OAuth 2.0 认证流程

```go
package metaadapter

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/url"
	"time"
)

// MetaAuth Meta OAuth 2.0 认证
type MetaAuth struct {
	AppID       string
	AppSecret   string
	AccessToken string
	TokenExpiry time.Time
	RefreshURL  string
}

// ExchangeCode 用授权码换取 Access Token
func (a *MetaAuth) ExchangeCode(ctx context.Context, code string) (*TokenResponse, error) {
	params := url.Values{}
	params.Set("client_id", a.AppID)
	params.Set("client_secret", a.AppSecret)
	params.Set("code", code)
	params.Set("grant_type", "authorization_code")
	params.Set("redirect_uri", a.RedirectURI)
	
	req, err := http.NewRequestWithContext(ctx, "POST", a.TokenURL, strings.NewReader(params.Encode()))
	if err != nil {
		return nil, err
	}
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	
	var tokenResp TokenResponse
	if err := json.NewDecoder(resp.Body).Decode(&tokenResp); err != nil {
		return nil, err
	}
	
	a.AccessToken = tokenResp.AccessToken
	a.TokenExpiry = time.Now().Add(time.Duration(tokenResp.ExpiresIn) * time.Second)
	
	return &tokenResp, nil
}

// RefreshToken 刷新 Access Token
func (a *MetaAuth) RefreshToken(ctx context.Context) (*TokenResponse, error) {
	params := url.Values{}
	params.Set("grant_type", "refresh_token")
	params.Set("refresh_token", a.RefreshToken)
	params.Set("client_id", a.AppID)
	params.Set("client_secret", a.AppSecret)
	
	req, err := http.NewRequestWithContext(ctx, "POST", a.RefreshURL, strings.NewReader(params.Encode()))
	if err != nil {
		return nil, err
	}
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	
	var tokenResp TokenResponse
	if err := json.NewDecoder(resp.Body).Decode(&tokenResp); err != nil {
		return nil, err
	}
	
	a.AccessToken = tokenResp.AccessToken
	a.TokenExpiry = time.Now().Add(time.Duration(tokenResp.ExpiresIn) * time.Second)
	
	return &tokenResp, nil
}

// ValidateToken 验证 Token 有效性
func (a *MetaAuth) ValidateToken(ctx context.Context) error {
	req, err := http.NewRequestWithContext(ctx, "GET", 
		fmt.Sprintf("%s/me?fields=id,name&access_token=%s", a.APIBase, a.AccessToken), nil)
	if err != nil {
		return err
	}
	
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	
	if resp.StatusCode == 401 {
		return fmt.Errorf("token expired or invalid")
	}
	
	return nil
}

// TokenResponse OAuth Token 响应
type TokenResponse struct {
	AccessToken  string `json:"access_token"`
	ExpiresIn    int    `json:"expires_in"`
	RefreshToken string `json:"refresh_token,omitempty"`
	Scope        string `json:"scope"`
}
```

### 3.2 批量请求优化

```go
package metaadapter

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
)

// BatchRequest Meta 批量请求
type BatchRequest struct {
	Method   string                 `json:"method"`
	Path     string                 `json:"path"`
	Body     map[string]interface{} `json:"body,omitempty"`
	Headers  map[string]string      `json:"headers,omitempty"`
}

// BatchResponse 批量响应
type BatchResponse struct {
	Status  int                    `json:"status"`
	Body    map[string]interface{} `json:"body,omitempty"`
	Error   map[string]interface{} `json:"error,omitempty"`
}

// ExecuteBatch 执行批量请求（最多 50 个操作）
func (a *API) ExecuteBatch(ctx context.Context, requests []BatchRequest) ([]*BatchResponse, error) {
	if len(requests) > 50 {
		return nil, fmt.Errorf("batch size exceeds limit of 50")
	}
	
	body := map[string]interface{}{
		"requests": requests,
	}
	
	payload, err := json.Marshal(body)
	if err != nil {
		return nil, err
	}
	
	req, err := http.NewRequestWithContext(ctx, "POST", a.BaseURL+"/v18.0/", bytes.NewReader(payload))
	if err != nil {
		return nil, err
	}
	
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", fmt.Sprintf("Bearer %s", a.AccessToken))
	
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	
	var responses []BatchResponse
	if err := json.NewDecoder(resp.Body).Decode(&responses); err != nil {
		return nil, err
	}
	
	// 检查部分失败
	var firstErr error
	for i, r := range responses {
		if r.Status >= 400 && firstErr == nil {
			firstErr = fmt.Errorf("batch request %d failed: %+v", i, r.Error)
		}
	}
	
	return responses, firstErr
}
```

### 3.3 Webhook 订阅

```go
package metaadapter

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
)

// WebhookHandler Meta Webhook 处理器
type WebhookHandler struct {
	AppSecret string
	Callback  func(event WebhookEvent) error
}

// VerifySignature 验证 Webhook 签名
func (h *WebhookHandler) VerifySignature(payload []byte, signature string) bool {
	mac := hmac.New(sha256.New, []byte(h.AppSecret))
	mac.Write(payload)
	expected := hex.EncodeToString(mac.Sum(nil))
	
	return hmac.Equal([]byte(signature), []byte(expected))
}

// HandleWebhook 处理 Webhook 回调
func (h *WebhookHandler) HandleWebhook(w http.ResponseWriter, r *http.Request) {
	// 1. 验证 Challenge（订阅时）
	challenge, exists := r.URL.Query()["hub.challenge"]
	if exists && len(challenge) > 0 {
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(challenge[0]))
		return
	}
	
	// 2. 读取请求体
	body, err := io.ReadAll(r.Body)
	if err != nil {
		http.Error(w, "read body failed", http.StatusBadRequest)
		return
	}
	
	// 3. 验证签名
	signature := r.Header.Get("X-Hub-Signature-256")
	if !h.VerifySignature(body, signature) {
		http.Error(w, "invalid signature", http.StatusUnauthorized)
		return
	}
	
	// 4. 解析事件
	var event WebhookEvent
	if err := json.Unmarshal(body, &event); err != nil {
		http.Error(w, "parse event failed", http.StatusBadRequest)
		return
	}
	
	// 5. 分发到回调
	if h.Callback != nil {
		if err := h.Callback(event); err != nil {
			h.logError(err)
			http.Error(w, "callback failed", http.StatusInternalServerError)
			return
		}
	}
	
	w.WriteHeader(http.StatusOK)
}

// WebhookEvent Meta Webhook 事件
type WebhookEvent struct {
	Object    string            `json:"object"`
	Entry     []WebhookEntry    `json:"entry"`
}

type WebhookEntry struct {
	ID        string              `json:"id"`
	Time      int64               `json:"time"`
	Changes   []WebhookChange     `json:"changes"`
}

type WebhookChange struct {
	Field     string      `json:"field"`
	Value     interface{} `json:"value"`
	Timestamp int64       `json:"timestamp"`
}
```

---

## 四、TikTok Marketing API 深度实现

### 4.1 认证与 Rate Limiting

```go
package tiktokadapter

import (
	"context"
	"fmt"
	"net/http"
	"strings"
	"sync"
	"time"
)

// TikTokAuth TikTok OAuth 认证
type TikTokAuth struct {
	ClientID     string
	ClientSecret string
	AccessToken  string
	RefreshToken string
	Region       string // US, EU, IN
}

// RateLimiter TikTok API 限流器
type RateLimiter struct {
	mu          sync.Mutex
	requests    []time.Time
	maxRequests int
	window      time.Duration
}

func NewRateLimiter(maxReq int, window time.Duration) *RateLimiter {
	return &RateLimiter{
		maxRequests: maxReq,
		window:      window,
	}
}

// Allow 检查是否允许请求
func (rl *RateLimiter) Allow() bool {
	rl.mu.Lock()
	defer rl.mu.Unlock()
	
	now := time.Now()
	cutoff := now.Add(-rl.window)
	
	// 清理过期记录
	valid := make([]time.Time, 0)
	for _, t := range rl.requests {
		if t.After(cutoff) {
			valid = append(valid, t)
		}
	}
	rl.requests = valid
	
	if len(rl.requests) >= rl.maxRequests {
		return false
	}
	
	rl.requests = append(rl.requests, now)
	return true
}

// WaitUntilAllowed 等待直到允许请求
func (rl *RateLimiter) WaitUntilAllowed(ctx context.Context) error {
	for {
		if rl.Allow() {
			return nil
		}
		
		select {
		case <-ctx.Done():
			return ctx.Err()
		case <-time.After(100 * time.Millisecond):
			// 短暂等待后重试
		}
	}
}

// API TikTok Marketing API 客户端
type API struct {
	auth     *TikTokAuth
	limiter  *RateLimiter
	client   *http.Client
	baseURL  string
}

func NewAPI(auth *TikTokAuth) *API {
	region := auth.Region
	if region == "" {
		region = "US"
	}
	
	baseURL := "https://business-api.tiktok.com/portal"
	if region == "EU" {
		baseURL = "https://business-api.tiktok-eu.com/portal"
	}
	
	return &API{
		auth:    auth,
		limiter: NewRateLimiter(50, time.Minute), // TikTok: 50 req/min
		client:  &http.Client{Timeout: 30 * time.Second},
		baseURL: baseURL,
	}
}

// Do 执行 API 请求（自动限流 + 重试）
func (api *API) Do(ctx context.Context, method, path string, body interface{}) (*http.Response, error) {
	// 1. 等待限流
	if err := api.limiter.WaitUntilAllowed(ctx); err != nil {
		return nil, err
	}
	
	// 2. 构建请求
	payload, err := json.Marshal(body)
	if err != nil {
		return nil, err
	}
	
	req, err := http.NewRequestWithContext(ctx, method, api.baseURL+path, bytes.NewReader(payload))
	if err != nil {
		return nil, err
	}
	
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Access-Token", api.auth.AccessToken)
	
	// 3. 执行请求
	resp, err := api.client.Do(req)
	if err != nil {
		return nil, err
	}
	
	// 4. 处理速率限制响应
	if resp.StatusCode == 429 {
		retryAfter := resp.Header.Get("Retry-After")
		if retryAfter != "" {
			delay, _ := strconv.Atoi(retryAfter)
			time.Sleep(time.Duration(delay) * time.Second)
			return api.Do(ctx, method, path, body) // 递归重试
		}
	}
	
	return resp, nil
}
```

### 4.2 增量同步

```go
package tiktokadapter

import (
	"context"
	"time"
)

// IncrementalSync TikTok 增量同步
type IncrementalSync struct {
	db      *Database
	lastSync map[string]time.Time // platform -> last_sync_time
}

func (s *IncrementalSync) SyncCampaigns(ctx context.Context, platform PlatformType) error {
	lastSync, exists := s.lastSync[platform]
	if !exists {
		lastSync = time.Now().Add(-24 * time.Hour) // 默认同步最近 24 小时
	}
	
	// 查询变更
	campaigns, err := s.db.QueryChangedCampaigns(ctx, platform, lastSync)
	if err != nil {
		return err
	}
	
	// 处理变更
	for _, campaign := range campaigns {
		switch campaign.ChangeType {
		case "created":
			err = s.createCampaign(ctx, platform, campaign)
		case "updated":
			err = s.updateCampaign(ctx, platform, campaign)
		case "deleted":
			err = s.deleteCampaign(ctx, platform, campaign.ID)
		}
		
		if err != nil {
			s.logError(err)
		}
	}
	
	// 更新时间戳
	s.lastSync[platform] = time.Now()
	
	return nil
}

// QueryChangedCampaigns 查询变更的广告活动
func (db *Database) QueryChangedCampaigns(ctx context.Context, platform PlatformType, since time.Time) ([]*CampaignChange, error) {
	query := `
		SELECT id, platform, change_type, data, updated_at
		FROM campaign_changes
		WHERE platform = ? AND updated_at > ?
		ORDER BY updated_at ASC
	`
	
	rows, err := db.QueryContext(ctx, query, string(platform), since)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	
	var changes []*CampaignChange
	for rows.Next() {
		var c CampaignChange
		if err := rows.Scan(&c.ID, &c.Platform, &c.ChangeType, &c.Data, &c.UpdatedAt); err != nil {
			return nil, err
		}
		changes = append(changes, &c)
	}
	
	return changes, nil
}
```

---

## 五、Google Ads API 深度实现

### 5.1 gRPC 客户端

```go
package googleads

import (
	"context"
	"fmt"
	"time"

	pb "google.golang.org/genproto/googleapis/ads/googleads/v16/services"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/oauth"
)

// GoogleAdsClient Google Ads API gRPC 客户端
type GoogleAdsClient struct {
	conn     *grpc.ClientConn
	client   pb.GoogleAdsServiceClient
	projectID string
}

func NewGoogleAdsClient(ctx context.Context, developerToken, clientCustomerID string) (*GoogleAdsClient, error) {
	// 1. 建立 gRPC 连接
	conn, err := grpc.DialContext(ctx, "googleads.googleapis.com:443",
		grpc.WithTransportCredentials(credentials.NewTLS(nil)),
		grpc.WithPerRPCCredentials(oauth.NewOAuthJWTWithToken(
			ctx,
			&jwt.Config{
				Email:      os.Getenv("GOOGLE_SERVICE_ACCOUNT"),
				PrivateKey: []byte(os.Getenv("GOOGLE_PRIVATE_KEY")),
				Scopes:     []string{"https://www.googleapis.com/auth/adwords"},
				TokenURL:   "https://oauth2.googleapis.com/token",
			},
			map[string]interface{}{
				"sub":              clientCustomerID,
				"developer_token":  developerToken,
			},
		)),
	)
	if err != nil {
		return nil, fmt.Errorf("dial: %w", err)
	}
	
	return &GoogleAdsClient{
		conn: conn,
		client: pb.NewGoogleAdsServiceClient(conn),
	}, nil
}

// Search 搜索广告活动
func (c *GoogleAdsClient) Search(ctx context.Context, customerID string, query string) (*pb.SearchGoogleAdsResponse, error) {
	req := &pb.SearchGoogleAdsRequest{
		CustomerId: customerID,
		Query:      query,
		PageSize:   1000,
	}
	
	resp, err := c.client.Search(ctx, req)
	if err != nil {
		return nil, fmt.Errorf("search: %w", err)
	}
	
	return resp, nil
}

// StreamSearch 流式搜索（处理大数据集）
func (c *GoogleAdsClient) StreamSearch(ctx context.Context, customerID string, query string) (<-chan *pb.GoogleAdsRow, error) {
	streamChan := make(chan *pb.GoogleAdsRow, 100)
	
	go func() {
		defer close(streamChan)
		
		req := &pb.SearchStreamRequest{
			CustomerId: customerID,
			Query:      query,
			PageSize:   10000,
		}
		
		stream, err := c.client.SearchStream(ctx, req)
		if err != nil {
			return
		}
		
		for {
			resp, err := stream.Recv()
			if err == io.EOF {
				break
			}
			if err != nil {
				return
			}
			
			for _, row := range resp.Results {
				select {
				case streamChan <- row:
				case <-ctx.Done():
					return
				}
			}
		}
	}()
	
	return streamChan, nil
}
```

### 5.2 错误处理与重试

```go
package googleads

import (
	"context"
	"fmt"
	"time"

	"google.golang.org/api/googleapi"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// RetryConfig 重试配置
type RetryConfig struct {
	MaxRetries    int
	BaseDelay     time.Duration
	MaxDelay      time.Duration
	RetryableCodes []codes.Code
}

var DefaultRetryConfig = RetryConfig{
	MaxRetries: 3,
	BaseDelay:  1 * time.Second,
	MaxDelay:   30 * time.Second,
	RetryableCodes: []codes.Code{
		codes.ResourceExhausted,  // 速率限制
		codes.Unavailable,        // 服务不可用
		codes.DeadlineExceeded,   // 超时
	},
}

// ExecuteWithRetry 带重试的执行
func ExecuteWithRetry(ctx context.Context, config RetryConfig, operation func(context.Context) error) error {
	var lastErr error
	
	for attempt := 0; attempt <= config.MaxRetries; attempt++ {
		err := operation(ctx)
		if err == nil {
			return nil
		}
		
		lastErr = err
		
		// 检查是否可重试
		if !isRetryable(err, config.RetryableCodes) {
			return err
		}
		
		// 指数退避
		delay := config.BaseDelay * time.Duration(math.Pow(2, float64(attempt)))
		if delay > config.MaxDelay {
			delay = config.MaxDelay
		}
		
		select {
		case <-time.After(delay):
			continue
		case <-ctx.Done():
			return ctx.Err()
		}
	}
	
	return fmt.Errorf("retry exhausted after %d attempts: %w", config.MaxRetries+1, lastErr)
}

func isRetryable(err error, codes []codes.Code) bool {
	st, ok := status.FromError(err)
	if !ok {
		return false
	}
	
	for _, code := range codes {
		if st.Code() == code {
			return true
		}
	}
	
	return false
}
```

---

## 六、生产排障案例

### 6.1 Token 刷新风暴

**现象**：多个服务实例同时刷新 Token，导致 OAuth 服务器过载。

**修复方案：**

```go
// TokenRefresher 分布式 Token 刷新器
type TokenRefresher struct {
	mu         sync.Mutex
	token      *TokenResponse
	expiry     time.Time
	refresher  func() (*TokenResponse, error)
}

func (r *TokenRefresher) GetToken(ctx context.Context) (*TokenResponse, error) {
	r.mu.Lock()
	defer r.mu.Unlock()
	
	// 提前 5 分钟刷新
	if time.Until(r.expiry) < 5*time.Minute {
		newToken, err := r.refresher()
		if err != nil {
			return r.token, err // 返回旧 token
		}
		r.token = newToken
		r.expiry = time.Now().Add(time.Duration(newToken.ExpiresIn) * time.Second)
	}
	
	return r.token, nil
}
```

### 6.2 批量请求超时

**现象**：Meta 批量请求经常超时（30s），但单个请求正常。

**根因：** Meta 批量请求会按顺序执行所有子请求，一个慢请求拖累整体。

**修复方案：**

```go
// 拆分为多个小批次
func (api *API) ExecuteBatchOptimized(ctx context.Context, requests []BatchRequest) error {
	const batchSize = 25 // 每批最多 25 个
	
	for i := 0; i < len(requests); i += batchSize {
		end := i + batchSize
		if end > len(requests) {
			end = len(requests)
		}
		
		batch := requests[i:end]
		if err := api.ExecuteBatch(ctx, batch); err != nil {
			return err
		}
		
		// 批次间短暂暂停
		time.Sleep(100 * time.Millisecond)
	}
	
	return nil
}
```

---

## 七、自测题

### Q1：如何设计一个支持多平台、高可用的广告 API 网关？

**参考答案：**

核心设计要点：
1. **统一认证层**：OAuth Token 集中管理 + 自动刷新
2. **智能路由**：根据目标平台路由到对应适配器
3. **熔断降级**：单平台故障不影响其他平台
4. **缓存策略**：读操作缓存（Campaign 列表等）
5. **限流配额**：按平台 + 账户维度限流
6. **监控告警**：延迟/错误率/配额使用率实时监控

### Q2：Meta Ads API 的 Batch 请求有什么限制？如何应对？

**参考答案：**

限制：
- 最多 50 个操作/批
- 总大小不超过 5MB
- 按顺序执行，一个失败整个批可能受影响
- 每个操作有独立的速率限制计数

应对：
- 拆分大批为多个小批（25 个/批）
- 使用异步 Webhook 替代轮询
- 关键操作单独发送，非关键操作批量
- 实施重试逻辑处理部分失败

### Q3：TikTok API 的增量同步如何实现？

**参考答案：**

1. 维护 `last_sync_time` 状态（按平台存储）
2. 调用 `/insight/campaign/report` 时传入 `since` 参数
3. 比较返回数据与本地数据库的差异
4. 使用 `campaign_id` + `updated_at` 作为唯一键
5. 处理删除事件（通过状态标记而非物理删除）

---

## 八、与知识库的对照

### 已有知识
1. **`ad-ads/ad-data-platform-deep.md`** — 广告数据平台架构，缺少 API 集成细节
2. **`advertising/dsp-core-flow-deep.md`** — DSP 核心流程，有外部 API 调用但未深入
3. **`tools/weread-api-reference.md`** — 微信读书 API，方法论可复用

### 本文件补充
1. **三大广告平台 API 完整实现** — Meta/TikTok/Google
2. **统一抽象层设计** — 适配器模式 + 多平台客户端
3. **生产级认证/限流/重试** — Token 刷新风暴/批量超时等案例
4. **增量同步机制** — TikTok 数据变更检测

### 新增 Gap
1. 缺少 Snapchat/Amazon/Pinterest 等其他平台适配
2. 缺少 API 版本管理的最佳实践
3. 缺少 OpenAPI/Swagger 自动生成适配器的工具链
