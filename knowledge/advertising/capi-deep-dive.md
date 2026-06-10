# CAPI 深度 — Meta Conversion API 全链路解析

> 标签: `#CAPI` `#Meta` `#ConversionAPI` `#Server-Side` `#事件匹配` `#源码级`
> 创建日期: 2026-06-10 | 作者: Ryan
> 定位: 资深专家级 — CAPI 架构、数据匹配、优先级、与 Pixel 协同

---

## 第一部分：入门引导（5 分钟速览）

### 1.1 为什么需要 CAPI？

```
┌─────────────────────────────────────────────────────────────┐
│              Cookie 衰减时代的数据追踪困境                    │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  浏览器 Cookie 衰减时间线                               │  │
│  │                                                      │  │
│  │  2018:  Safari ITP (Initial Track Prevention)        │  │
│  │        → 第三方 Cookie 7 天过期                        │  │
│  │                                                      │  │
│  │  2020:  Chrome 计划淘汰第三方 Cookie                   │  │
│  │        → 2024 开始测试, 2025+ 全面实施                 │  │
│  │                                                      │  │
│  │  2021:  Firefox ETP (Enhanced Tracking Protection)   │  │
│  │        → 默认阻止第三方 Cookie                         │  │
│  │                                                      │  │
│  │  2022:  iOS 14.5+ ATT (App Tracking Transparency)    │  │
│  │        → 用户需明确授权追踪                            │  │
│  │        → 授权率仅 ~7% (iOS)                            │  │
│  │                                                      │  │
│  │  2023:  Chrome Privacy Sandbox                         │  │
│  │        → Topics API / Protected Audience API          │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  影响: Pixel/客户端追踪丢失率 ~30-50%                        │
│  解法: CAPI (服务端直接上报, 不受 Cookie 影响)               │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 Pixel vs CAPI — 互补架构

```
┌─────────────────────────────────────────────────────────────┐
│                 Pixel + CAPI 双引擎架构                       │
│                                                             │
│  客户端 (Client-Side):            服务端 (Server-Side):      │
│  ┌─────────────────────┐      ┌─────────────────────┐      │
│  │   Pixel              │      │   Conversion API   │      │
│  │   (JavaScript)       │      │   (HTTP API)       │      │
│  │                      │      │                     │      │
│  │  优势:               │      │  优势:             │      │
│  │  • 实时性高          │      │  • 不受 Cookie 限制  │      │
│  │  • 实现简单          │      │  • 数据更完整       │      │
│  │  • 捕获用户行为      │      │  • 可捕获服务端事件   │      │
│  │  • 成本低            │      │  • 可补充 Pixel 遗漏  │      │
│  │                      │      │                     │      │
│  │  劣势:               │      │  劣势:             │      │
│  │  • Cookie 受限       │      │  • 实现复杂         │      │
│  │  • 容易丢失          │      │  • 延迟高           │      │
│  │  • 无法获取服务端事件  │      │  • 需要后端基础设施   │      │
│  └────────────┬─────────┘      └─────────┬───────────┘      │
│               │                           │                  │
│               └───────────┬───────────────┘                  │
│                           ▼                                  │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              Meta Events Manager                      │   │
│  │                                                      │   │
│  │  • 事件去重 (Client + Server 合并)                     │   │
│  │  • 事件优先级 (CAPI > Pixel, 同优先级 FCT > AFT)      │   │
│  │  • 事件增强 (Hash 用户数据, 匹配用户)                 │   │
│  │  • 事件验证 (Validation & Diagnostics)               │   │
│  └──────────────────────────────────────────────────────┘   │
│                           │                                  │
│                           ▼                                  │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              Meta 广告优化引擎                         │   │
│  │  • 转化归因 (基于事件)                                │   │
│  │  • 出价优化 (基于转化价值)                              │   │
│  │  • 受众构建 (基于用户行为)                              │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### 1.3 核心概念速查

| 概念 | 定义 | 说明 |
|------|------|------|
| **Pixel** | 页面嵌入的 JS 追踪代码 | 客户端事件采集 |
| **CAPI** | Meta 的服务端 API | 服务端事件上报 |
| **Event Match** | 将事件与 Meta 用户匹配 | 通过 Hash 的 email/phone 等 |
| **Custom Conversion** | 自定义转化事件 | 基于 URL/事件的规则匹配 |
| **Standard Event** | 预定义标准事件 | Purchase/Lead/AddToCart 等 |
| **Aggregated Event Measurement (AEM)** | 聚合事件测量 | iOS 数据共享限制下的事件优先级 |
| **Event ID** | 事件唯一 ID | 去重关键, 必须全局唯一 |
| **Action Type** | 事件类型 | view_content, add_to_cart, purchase 等 |
| **Event Source** | 事件来源 | website/app/ios/android |
| **FCT** | First Class Treatment | 高质量匹配数据 (email/phone) |
| **AFT** | Additional Field Treatment | 低质量匹配数据 (country/ip) |
| **Data Processing Options** | 数据共享控制 | DPA/LDU 等限制 |

---

## 第二部分：CAPI 架构深度

### 2.1 CAPI 请求结构

```go
// capi.go — Conversion API 请求结构
package meta

import (
	"crypto/sha256"
	"encoding/json"
	"fmt"
	"net/http"
	"strings"
	"time"
)

// Event CAPI 事件结构
type Event struct {
	EventName    string           `json:"event_name"`    // Purchase, Lead, ViewContent
	EventSource  string           `json:"event_source"`  // website
	EventID      string           `json:"event_id"`      // 全局唯一
	Time         int64            `json:"time"`          // Unix 时间戳 (秒)
	ActionType   string           `json:"action_type,omitempty"` // click, view, submit
	Properties   map[string]interface{} `json:"user_data,omitempty"` // 用户数据
	CustomData   map[string]interface{} `json:"custom_data,omitempty"` // 事件属性
}

// UserData 用户数据 (用于事件匹配)
type UserData struct {
	Email       []string `json:"em,omitempty"`      // 邮箱 (SHA-256 Hash)
	Phone       []string `json:"ph,omitempty"`      // 手机号 (SHA-256 Hash)
	Fname       []string `json:"fn,omitempty"`      // 名字
	Lname       []string `json:"ln,omitempty"`      // 姓氏
	City        []string `json:"ct,omitempty"`      // 城市
	State       []string `json:"st,omitempty"`      // 州/省
	Zip         []string `json:"zp,omitempty"`      // 邮编
	Country     []string `json:"cn,omitempty"`      // 国家
	Bday        []string `json:"bd,omitempty"`      // 生日
	Gender      []string `json:"gb,omitempty"`      // 性别
	// 注意: 所有字段值必须是 SHA-256 哈希的小写 hex 字符串
}

// EventRequest CAPI 批量请求
type EventRequest struct {
	Data       []Event `json:"data"`        // 事件列表
	OptOut     bool    `json:"opt_out,omitempty"`
	SyncSource string  `json:"sync_source,omitempty"`
	TestEventCode string `json:"test_event_code,omitempty"` // 测试事件代码
}

// 发送 CAPI 事件
func (m *MetaClient) SendEvents(userID string, events []Event) error {
	req := EventRequest{
		Data: events,
	}
	
	body, _ := json.Marshal(req)
	
	resp, err := http.Post(
		fmt.Sprintf("https://graph.facebook.com/v18.0/%s/events?access_token=%s",
			m.PixelID, m.AccessToken),
		"application/json",
		strings.NewReader(string(body)),
	)
	if err != nil {
		return fmt.Errorf("send events error: %w", err)
	}
	defer resp.Body.Close()
	
	if resp.StatusCode != 200 {
		return fmt.Errorf("CAPI request failed: %d", resp.StatusCode)
	}
	
	return nil
}

// HashUserData 哈希用户数据 (CAPI 要求)
func HashUserData(value string) string {
	hash := sha256.Sum256([]byte(strings.TrimSpace(strings.ToLower(value))))
	return fmt.Sprintf("%x", hash)
}

// 构建标准 Purchase 事件
func BuildPurchaseEvent(orderID string, userID string, value float64, currency string,
	items []Item, userData *UserData) *Event {
	
	customData := map[string]interface{}{
		"value":    value,
		"currency": currency,
		"content_ids": getItemIDs(items),
		"content_type": "product",
		"num_items": len(items),
		"contents": items,
	}
	
	return &Event{
		EventName:   "Purchase",
		EventSource: "website",
		EventID:     generateEventID(userID, orderID),
		Time:        time.Now().Unix(),
		CustomData:  customData,
		Properties:  userData,
	}
}

// 事件 ID 生成 (全局唯一)
func generateEventID(userID, orderID string) string {
	hash := sha256.Sum256([]byte(userID + orderID + time.Now().Format("20060102")))
	return fmt.Sprintf("%x", hash[:16])
}

// Item 购买商品信息
type Item struct {
	ID         string  `json:"id"`
	Title      string  `json:"title,omitempty"`
	Price      float64 `json:"price,omitempty"`
	Quantity   int     `json:"quantity,omitempty"`
	Category   string  `json:"category,omitempty"`
}

// CAPI 请求限制:
// • 每个请求最多 100 个事件
// • 每秒最多 100 个请求
// • 事件必须在发生后 7 天内上报 (推荐 < 24h)
// • 数据必须通过 HTTPS 传输
// • 用户数据必须 SHA-256 哈希
// • Event ID 必须全局唯一 (用于去重)
```

### 2.2 事件匹配机制 — 源码级

```go
// event_matching.go — Meta 事件匹配算法
package meta

import (
	"crypto/sha256"
	"strings"
)

// MatchResult 匹配结果
type MatchResult struct {
	UserMatched bool    `json:"user_matched"`
	MatchScore  float64 `json:"match_score"` // 匹配分数 [0, 1]
	MatchFields []string `json:"match_fields"` // 匹配的字段
}

// 事件匹配分数计算 (Meta 内部算法, 以下为公开信息推测):
//
// Match Score = Σ (FieldWeight × FieldMatch × FieldAvailability)
//
// 字段权重 (FieldWeight):
// - em (Email): 0.25 (最高权重)
// - ph (Phone): 0.20
// - fn (First Name): 0.10
// - ln (Last Name): 0.10
// - db (Day of Birth): 0.05
// - mb (Month of Birth): 0.05
// - yb (Year of Birth): 0.05
// - ct (City): 0.05
// - st (State): 0.05
// - zp (Zip): 0.05
// - cn (Country): 0.05
// - ge (Gender): 0.05
//
// 匹配分数范围:
// - 1.0: 完美匹配 (email + phone)
// - 0.8+: 高质量匹配 (email 或 phone)
// - 0.5-0.7: 中等匹配 (名字 + 城市)
// - < 0.5: 低质量匹配 (仅国家/邮编)
//
// CAPI 匹配流程:
// 1. 接收 CAPI 事件 + 用户数据 (Hash)
// 2. 对用户数据做 Hash → 生成匹配键
// 3. 在 Meta 用户数据库中找到匹配
// 4. 返回 MatchResult + 匹配分数
// 5. 如果匹配成功 → 事件关联到 Meta 用户
// 6. 事件用于广告优化 (归因/受众/出价)

// 第一方数据优先 (First-Party Data)
// Meta 优先使用第一方数据 (CAPI), 其次才看 Pixel
func FirstPartyPriority(event *Event) float64 {
	matchResult := evaluateMatch(event.Properties)
	return matchResult.MatchScore
}

// 事件匹配优先级 (FCT > AFT)
//
// First Class Treatment (FCT):
// - em, ph, fn, ln, db (生日)
// - 这些字段匹配后, 事件会被优先用于优化
// - 在 AEM (聚合事件测量) 中优先级最高
//
// Additional Field Treatment (AFT):
// - ct, st, zp, cn, ge (城市/州/邮编/国家/性别)
// - 这些字段匹配后, 事件仍然可用但优先级较低
// - 在 AEM 中只能排在 FCT 之后

// 实现数据去重
type EventDedup struct {
	seenEvents map[string]bool // EventID → 已处理
}

func (d *EventDedup) IsDuplicate(eventID string) bool {
	if d.seenEvents == nil {
		d.seenEvents = make(map[string]bool)
	}
	if _, exists := d.seenEvents[eventID]; exists {
		return true
	}
	d.seenEvents[eventID] = true
	return false
}

// 事件 ID 去重策略:
// 1. 同一 EventID 只处理一次
// 2. CAPI 和 Pixel 的相同事件必须用相同 EventID
// 3. 建议 EventID = 业务订单号 (如 order_12345)
// 4. 跨渠道 (CAPI + Pixel) 事件用相同 EventID 去重

// 推荐做法: 在业务系统中统一生成 EventID
// event_id = sha256(user_id + event_name + timestamp)[:16]
// 确保:
// - 全局唯一
// - 可重现 (同一个事件多次发送, ID 相同)
// - 与 Pixel 使用相同的生成逻辑
```

### 2.3 CAPI + Pixel 协同 — 事件优先级

```
┌──────────────────────────────────────────────────────────────┐
│               CAPI vs Pixel 事件优先级                         │
│                                                              │
│  Meta 事件优先级规则 (从高到低):                               │
│                                                              │
│  1. FCT (First Class Treatment) + CAPI                       │
│     → 服务端发送的带 email/phone 的事件                        │
│                                                              │
│  2. FCT (First Class Treatment) + Pixel                      │
│     → 浏览器通过 Pixel 发送的带 email/phone 的事件             │
│                                                              │
│  3. AFT (Additional Field Treatment) + CAPI                  │
│     → 服务端发送的带其他数据的事件                             │
│                                                              │
│  4. AFT (Additional Field Treatment) + Pixel                 │
│     → 浏览器通过 Pixel 发送的带其他数据的事件                  │
│                                                              │
│  5. 无匹配数据的事件                                         │
│     → 仍然可以用于归因, 但效果较差                             │
│                                                              │
│  同优先级去重规则:                                           │
│  ──────────────────────────                                  │
│  • CAPI 事件优先于 Pixel (相同 EventID)                       │
│  • 同一优先级: 先到的优先                                     │
│  • 去重基于: EventID + Action Type + Time Window              │
│    (默认 24 小时窗口内相同 EventID + Action Type 去重)         │
│                                                              │
│  实际效果:                                                   │
│  • CAPI 通常比 Pixel 多捕获 20-40% 的转化                     │
│  • 结合使用: Pixel 实时 + CAPI 补漏                           │
│  • 最佳实践: 同时使用两者, CAPI 为主, Pixel 为补充             │
└──────────────────────────────────────────────────────────────┘
```

### 2.4 Aggregated Event Measurement (AEM)

```
AEM 聚合事件测量 — iOS 数据共享限制后的关键:

┌──────────────────────────────────────────────────────────────┐
│                                                              │
│  背景: iOS 14.5+ ATT 框架                                    │
│  - 用户需明确授权 App 追踪                                  │
│  - 授权率仅 ~7%                                             │
│  - 未授权用户: 只能获取 8 个优化事件/天 (App 级别)            │
│                                                              │
│  AEM 解决方案:                                               │
│  • 开发者配置优先事件 (最多 8 个)                            │
│  • Meta 优先优化已配置的事件                                 │
│  • 未配置的事件: 仍然可以收集用于归因, 但不能用于优化          │
│                                                              │
│  配置方式:                                                   │
│  • 设置 → 品牌安全 → Aggregated Event Measurement            │
│  • 配置优先级 (从高到低最多 8 个)                             │
│                                                              │
│  标准事件 (Standard Events) 列表:                            │
│  - CompleteRegistration                                    │
│  - Contact                                                 │
│  - CustomizeProduct                                        │
│  - Donate                                                │
│  - FindLocation                                            │
│  - InitiateCheckout                                      │
│  - Lead                                                  │
│  - Schedule                                              │
│  - Search                                                │
│  - StartTrial                                            │
│  - SubmitApplication                                     │
│  - SubmitContact                                         │
│  - SubmitLead                                            │
│  - SubmitSearch                                          │
│  - ViewContent                                           │
│  - AddToCart                                             │
│  - AddToWishlist                                         │
│  - AddPaymentInfo                                        │
│  - Purchase                                              │
│  - SpentCreditBalance                                    │
│  - Search                                                │
│  - ViewContent                                           │
│  - Search                                                │
│                                                              │
│  电商推荐优先级 (从高到低):                                  │
│  ┌──────────────────────────────────────────────────────────┐
│  │  1. Purchase        ← 核心转化, 最高优先级               │
│  │  2. InitiateCheckout                         │
│  │  3. AddToCart                           ← 漏斗关键节点     │
│  │  4. ViewContent                         ← 流量来源分析     │
│  │  5. Lead            ← 潜在客户追踪                       │
│  │  6. CompleteRegistration                   ← 用户注册      │
│  │  7. Search          ← 搜索行为分析                       │
│  │  8. AddToWishlist                       ← 意向信号        │
│  └──────────────────────────────────────────────────────────┘
│                                                              │
│  AEM + CAPI 协同:                                           │
│  • Pixel 发送的事件遵守 AEM 配置                             │
│  • CAPI 发送的事件也遵守 AEM 配置                            │
│  • CAPI 可以发送 Pixel 无法发送的事件 (如 Purchase 后的确认)   │
│  • 最佳实践: Pixel + CAPI 同时发送同一事件, 由 Meta 去重      │
└──────────────────────────────────────────────────────────────┘
```

---

## 第三部分：Go 服务端实现 — 完整示例

### 3.1 CAPI 客户端封装

```go
// capi_client.go — 生产级 CAPI 客户端
package meta

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"math/rand"
	"net/http"
	"sync"
	"time"
)

// CAPIConfig CAPI 配置
type CAPIConfig struct {
	PixelID       string
	AccessToken   string
	Endpoint      string // 默认: https://graph.facebook.com/v18.0/{pixel_id}/events
	MaxBatchSize  int    // 默认 100
	MaxRetry      int    // 默认 3
	Timeout       time.Duration // 默认 30s
	FlushInterval time.Duration // 默认 5s
}

// CAPIEndpoint CAPI 端点
type CAPIEndpoint string

const (
	EndpointProduction CAPIEndpoint = "https://graph.facebook.com/v18.0/%s/events"
	EndpointTest       CAPIEndpoint = "https://graph.facebook.com/v18.0/%s/test_event_code/%s/events"
)

// Client CAPI 客户端
type Client struct {
	config   CAPIConfig
	client   *http.Client
	batch    []Event
	mu       sync.Mutex
	flushCh  chan struct{}
	doneCh   chan struct{}
}

// NewCAPI 创建 CAPI 客户端
func NewCAPI(config CAPIConfig) *Client {
	c := &Client{
		config: config,
		client: &http.Client{
			Timeout: config.Timeout,
		},
		batch:   make([]Event, 0, config.MaxBatchSize),
		flushCh: make(chan struct{}, 1),
		doneCh:  make(chan struct{}),
	}
	
	// 启动后台批量发送
	go c.flushLoop()
	
	return c
}

// TrackEvent 追踪事件 (异步, 非阻塞)
func (c *Client) TrackEvent(event Event) {
	c.mu.Lock()
	defer c.mu.Unlock()
	
	c.batch = append(c.batch, event)
	
	// 批次满 → 触发 flush
	if len(c.batch) >= c.config.MaxBatchSize {
		select {
		case c.flushCh <- struct{}{}:
		default:
			// 已有 flush 在队列中, 不再重复
		}
	}
}

// flushLoop 后台批量发送循环
func (c *Client) flushLoop() {
	ticker := time.NewTicker(c.config.FlushInterval)
	defer ticker.Stop()
	
	for {
		select {
		case <-c.flushCh:
			c.flush()
		case <-ticker.C:
			c.flush()
		case <-c.doneCh:
			// 关闭前最后一次 flush
			c.flush()
			return
		}
	}
}

// flush 发送批次
func (c *Client) flush() {
	c.mu.Lock()
	batch := c.batch
	c.batch = make([]Event, 0, c.config.MaxBatchSize)
	c.mu.Unlock()
	
	if len(batch) == 0 {
		return
	}
	
	// 重试逻辑
	var lastErr error
	for attempt := 0; attempt <= c.config.MaxRetry; attempt++ {
		err := c.sendBatch(batch)
		if err == nil {
			return
		}
		lastErr = err
		log.Printf("CAPI send attempt %d failed: %v", attempt+1, err)
		
		// 指数退避
		backoff := time.Duration(1<<uint(attempt)) * time.Second
		time.Sleep(backoff)
	}
	
	log.Printf("CAPI send failed after %d retries: %v", c.config.MaxRetry+1, lastErr)
}

// sendBatch 发送批次到 Meta
func (c *Client) sendBatch(events []Event) error {
	payload := EventRequest{
		Data: events,
	}
	
	body, err := json.Marshal(payload)
	if err != nil {
		return fmt.Errorf("marshal events: %w", err)
	}
	
	url := fmt.Sprintf(string(EndpointProduction), c.config.PixelID)
	req, err := http.NewRequestWithContext(
		context.Background(),
		"POST", url, bytes.NewReader(body),
	)
	if err != nil {
		return fmt.Errorf("create request: %w", err)
	}
	
	req.Header.Set("Content-Type", "application/json")
	
	resp, err := c.client.Do(req)
	if err != nil {
		return fmt.Errorf("http request: %w", err)
	}
	defer resp.Body.Close()
	
	respBody, _ := io.ReadAll(resp.Body)
	
	if resp.StatusCode >= 500 {
		return fmt.Errorf("server error %d: %s", resp.StatusCode, string(respBody))
	}
	
	if resp.StatusCode >= 400 {
		return fmt.Errorf("client error %d: %s", resp.StatusCode, string(respBody))
	}
	
	// 解析响应
	var result struct {
		IsBatch bool        `json:"is_batch"`
		Errors  []APIError  `json:"errors,omitempty"`
	}
	json.Unmarshal(respBody, &result)
	
	if len(result.Errors) > 0 {
		for _, e := range result.Errors {
			log.Printf("CAPI error: %v", e)
		}
	}
	
	return nil
}

// Shutdown 关闭客户端
func (c *Client) Shutdown() {
	close(c.doneCh)
}

// APIError CAPI API 错误
type APIError struct {
	Message   string `json:"message"`
	Type      string `json:"type"`
	Code      int    `json:"code"`
	ErrorSubcode int  `json:"error_subcode"`
	FbTraceID string `json:"fbtrace_id"`
}

// 常见错误码:
// 1349129: Pixel does not exist
// 1349127: Invalid access token
// 1349132: Event name is invalid
// 1349136: Time is out of range (事件超过 7 天)
// 1349138: Duplicate event (相同 EventID 已处理)
// 800000: Rate limit exceeded (超过每秒 100 请求)
```

### 3.2 业务事件集成示例

```go
// 电商 Purchase 事件
func OnOrderPlaced(order *Order, user *User) {
	// 1. 生成事件
	event := meta.BuildPurchaseEvent(
		order.ID,
		user.ID,
		order.TotalAmount,
		order.Currency,
		order.Items,
		&meta.UserData{
			Email: []string{meta.HashUserData(user.Email)},
			Phone: []string{meta.HashUserData(user.Phone)},
			City:  []string{meta.HashUserData(user.City)},
			Country: []string{meta.HashUserData(user.Country)},
		},
	)
	
	// 2. 发送到 CAPI
	apiClient.TrackEvent(*event)
	
	// 3. 同时发送到 Pixel (客户端)
	// 在页面渲染时嵌入 Pixel 事件
}

// Lead 事件 (表单提交)
func OnLeadSubmitted(lead *Lead) {
	event := &meta.Event{
		EventName:   "Lead",
		EventSource: "website",
		EventID:     meta.GenerateEventID(lead.UserID, "lead", time.Now()),
		Time:        time.Now().Unix(),
		Properties: &meta.UserData{
			Email: []string{meta.HashUserData(lead.Email)},
			Phone: []string{meta.HashUserData(lead.Phone)},
		},
		CustomData: map[string]interface{}{
			"lead_source": lead.Source,
			"lead_type":   lead.Type,
		},
	}
	
	apiClient.TrackEvent(*event)
}

// AddToCart 事件
func OnAddToCart(userID string, cart *Cart) {
	event := &meta.Event{
		EventName:   "AddToCart",
		EventSource: "website",
		EventID:     meta.GenerateEventID(userID, "add_to_cart", time.Now()),
		Time:        time.Now().Unix(),
		Properties: &meta.UserData{
			Email: []string{meta.HashUserData(userID)}, // 如果已知 email
		},
		CustomData: map[string]interface{}{
			"value":    cart.Total(),
			"currency": cart.Currency,
			"contents": cart.Items,
		},
	}
	
	apiClient.TrackEvent(*event)
}

// CAPI 集成 Checklist:
// ✅ Event ID 全局唯一且可重现
// ✅ 用户数据 SHA-256 哈希 (小写)
// ✅ 事件在 24 小时内上报 (不超过 7 天)
// ✅ 使用 HTTPS
// ✅ 批量发送 (每批最多 100)
// ✅ 重试机制 (指数退避)
// ✅ 错误日志记录
// ✅ Pixel 和 CAPI 使用相同 Event ID
// ✅ AEM 配置已设置 (iOS 数据限制)
// ✅ 数据共享控制 (DPA/LDU)
```

---

## 第四部分：实战排障与调优

### 4.1 常见问题速查

| 症状 | 可能原因 | 排查方法 | 解决方案 |
|------|----------|----------|----------|
| **Pixel 数据少** | Cookie 限制/ATS 限制 | Events Manager 诊断 | 启用 CAPI, 配合使用 |
| **CAPI 事件不匹配** | 用户数据缺失/未 Hash | 测试事件工具 | 添加 email/phone, 确保 Hash |
| **事件重复** | Event ID 不唯一 | 检查生成逻辑 | 统一使用业务 ID 作为 Event ID |
| **AEM 事件优化受限** | 未配置 AEM / 优先级不够 | Events Manager | 配置 8 个优化事件优先级 |
| **CAPI 报错 1349136** | 事件超过 7 天 | 检查上报时间 | 确保事件在 7 天内上报 |
| **CAPI 报错 800000** | 速率限制 | 检查请求频率 | 控制每秒请求数 < 100 |
| **转化数据不一致** | Pixel + CAPI 未去重 | 检查 Event ID | 确保跨渠道 Event ID 一致 |

### 4.2 CAPI 实施 Checklist

```
CAPI 实施 Checklist:

1. 基础配置
   [ ] 创建 Business Manager 账户
   [ ] 创建 Pixel (如未创建)
   [ ] 创建 CAPI 访问令牌
   [ ] 验证域名所有权 (Domain Verification)

2. 数据发送
   [ ] 实现 CAPI 客户端 (带重试/批量)
   [ ] 生成唯一的 Event ID
   [ ] Hash 用户数据 (SHA-256, 小写)
   [ ] 发送标准事件 (Purchase, Lead, AddToCart, ViewContent)
   [ ] 发送自定义事件 (如 AppInstall, CompleteRegistration)

3. Pixel + CAPI 协同
   [ ] Pixel 和 CAPI 使用相同 Event ID
   [ ] CAPI 作为主要数据源
   [ ] Pixel 作为实时补充
   [ ] 配置 AEM 优先级

4. 验证与监控
   [ ] 使用 Meta 测试事件工具验证
   [ ] 检查匹配分数 (≥ 0.5 为合格)
   [ ] 设置转化监控告警
   [ ] 定期检查诊断报告

5. 合规
   [ ] 设置数据共享控制 (DPA/LDU)
   [ ] GDPR 合规 (用户同意)
   [ ] CCPA 合规 (Do Not Sell)
   [ ] 隐私政策更新
```

### 4.3 匹配分数优化

```
匹配分数优化策略:

1. 收集高质量用户数据:
   - 登录/注册流程中收集 email + phone
   - 结账流程中收集 email + phone
   - 避免只收集国家/城市等低权重字段

2. 数据清洗:
   - 统一 email 格式 (小写, 去空格)
   - 统一 phone 格式 (国际格式 +86xxx)
   - 确保数据准确性

3. Hash 处理:
   - 始终使用 SHA-256 (小写 hex)
   - 发送前 Trim() + Lower()
   - 保持 Pixel 和 CAPI 的 Hash 一致

4. 实时 vs 批量:
   - 关键事件 (Purchase/Lead) 实时发送
   - 非关键事件 (ViewContent) 可批量

5. 数据时效性:
   - 事件发生后 24 小时内发送
   - 避免延迟超过 7 天 (API 会拒绝)
```

---

## 第五部分：自测

### Q1：CAPI 的事件去重机制是什么？为什么需要 EventID？

<details>
<summary>点击查看参考答案</summary>

**去重机制**:
- Meta 使用 EventID + Action Type + 时间窗口 (24h) 进行去重
- 同一 EventID 在同时间窗口内的同类型事件只处理一次
- CAPI 事件优先于 Pixel 事件 (同 EventID)

**为什么需要 EventID**:
1. 全局唯一标识事件
2. 跨渠道去重 (Pixel + CAPI 同一事件)
3. 避免重复计费/归因
4. 便于数据分析和诊断

**最佳实践**:
- 使用业务系统的唯一 ID (如订单号)
- 格式: `order_12345_purchase` 或 `sha256(userID + event + time)[:16]`
- Pixel 和 CAPI 必须使用相同 EventID
</details>

### Q2：AEM 是什么？为什么需要它？

<details>
<summary>点击查看参考答案</summary>

**AEM (Aggregated Event Measurement) 聚合事件测量**:

**背景**: iOS 14.5+ 引入了 ATT (App Tracking Transparency), 用户需明确授权 App 追踪。iOS 用户授权率仅 ~7%, 导致大量数据丢失。

**AEM 作用**:
- 允许开发者配置最多 8 个优化事件的优先级
- Meta 优先优化已配置的事件
- 未配置的事件仍可收集用于归因, 但不能用于优化

**为什么需要**:
1. Cookie 衰减 → Pixel 数据减少
2. ATT 限制 → iOS 数据几乎全丢
3. AEM 让 Meta 能在有限数据下做最优优化

**配置方法**:
- Meta 后台 → 设置 → Aggregated Event Measurement
- 配置 8 个优先级事件 (从高到低)
- 电商推荐: Purchase > InitiateCheckout > AddToCart > ViewContent > Lead > ...
</details>

### Q3：CAPI 和 Pixel 同时发送同一事件时，Meta 如何处理？

<details>
<summary>点击查看参考答案</summary>

**处理逻辑**:

1. 如果 EventID 相同:
   - 只处理一次 (去重)
   - CAPI 优先于 Pixel (如果优先级相同)
   - 结果: 只上报一个事件

2. 如果 EventID 不同:
   - 作为两个独立事件处理
   - 可能导致重复计数 (购买计为 2 次)
   - 结果: 可能重复计费

**最佳实践**:
- **Pixel 和 CAPI 必须使用相同的 EventID**
- CAPI 作为主要数据源 (更可靠)
- Pixel 作为实时补充 (捕获 CAPI 延迟的事件)
- Meta 会自动合并和去重

**验证方法**:
- 使用 Meta 测试事件工具 → 查看同一事件的来源
- 确认 "Event Source" 字段: "website" (Pixel) 或 "Business" (CAPI)
</details>

### Q4：CAPI 用户数据字段中，em 和 ph 是什么？为什么重要？

<details>
<summary>点击查看参考答案</summary>

**em (Email)**:
- 邮箱地址的 SHA-256 哈希
- 权重最高 (0.25)
- 匹配分数贡献最大

**ph (Phone)**:
- 手机号的 SHA-256 哈希
- 权重第二 (0.20)
- 国际格式 (+86xxx, +1xxx 等)

**为什么重要**:
- em + ph 组合可实现 > 0.8 的匹配分数
- 匹配分数越高 → 事件用于优化的权重越高
- 在 AEM 中优先用于 First Class Treatment

**数据格式要求**:
- 必须是 SHA-256 哈希的小写 hex
- 发送前 Trim() 和 Lower()
- 示例: `sha256("user@example.com") → "a1b2c3..."`
</details>

---

## 第六部分：动手验证

### 6.1 CAPI 测试工具

```bash
# 1. 使用 Meta 测试事件工具
# Events Manager → Test Events → 获取 Test Event Code
# → 使用 Test Event Code 发送测试事件

# 2. 发送 CAPI 测试事件
curl -X POST "https://graph.facebook.com/v18.0/YOUR_PIXEL_ID/events?test_event_code=YOUR_CODE" \
  -H "Content-Type: application/json" \
  -d '{
    "data": [{
      "event_name": "ViewContent",
      "event_id": "test_001",
      "event_time": 1686364800,
      "event_source": "website",
      "user_data": {
        "em": ["5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8"],
        "ph": ["5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8"]
      },
      "custom_data": {
        "content_id": "product_123",
        "content_type": "product",
        "value": 99.99,
        "currency": "USD"
      }
    }]
  }'

# 3. 验证事件是否被接收
# Events Manager → Test Events → 查看实时事件流
```

### 6.2 Go 集成验证

```go
// main.go — CAPI 集成验证
package main

import (
	"log"
	"time"
	"yourproject/meta"
)

func main() {
	// 创建 CAPI 客户端
	config := meta.CAPIConfig{
		PixelID:       "YOUR_PIXEL_ID",
		AccessToken:   "YOUR_ACCESS_TOKEN",
		MaxBatchSize:  100,
		MaxRetry:      3,
		Timeout:       30 * time.Second,
		FlushInterval: 5 * time.Second,
	}
	
	client := meta.NewCAPI(config)
	defer client.Shutdown()
	
	// 发送 Purchase 事件
	event := meta.BuildPurchaseEvent(
		"order_12345",
		"user_abc",
		99.99,
		"USD",
		[]meta.Item{{ID: "product_123", Price: 99.99, Quantity: 1}},
		&meta.UserData{
			Email: []string{meta.HashUserData("test@example.com")},
		},
	)
	
	client.TrackEvent(*event)
	
	// 等待发送完成
	time.Sleep(10 * time.Second)
	
	log.Println("CAPI 集成测试完成")
}
```

---

*本文档基于 Meta CAPI v18.0 整理。CAPI 文档: https://developers.facebook.com/docs/marketing-apis/conversion-api*
