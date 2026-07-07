# WebSocket 深度实战：实时竞价流/监控/广告平台

> 从 WebSocket 协议原理到 Go 生产实现，覆盖 RTB bidstream、实时监控、广告管理平台
> 对比 SSE、gRPC-streaming、MQTT，给出广告平台选型决策树

---

## 一、WebSocket 协议深度解析

### 1.1 为什么需要 WebSocket？

**传统 HTTP 的实时性问题：**

```
轮询 (Polling):
客户端 → 每隔 1s → 服务端: "有新数据吗？"
服务端 → "没有" (浪费带宽)
服务端 → "有！" (延迟最多 1s)

长轮询 (Long Polling):
客户端 → 请求 → 服务端挂起
服务端 → 有新数据 → 立即返回
客户端 → 收到 → 立即发起新请求
(延迟 < 1s，但每个数据都需要一次完整 HTTP 往返)

WebSocket:
客户端 ←--- 全双工通道 ---→ 服务端
(建立一次握手，之后自由收发，延迟 < 10ms)
```

**广告平台实时场景需求：**

| 场景 | 延迟要求 | 双向通信 | 数据量 | 推荐方案 |
|------|----------|----------|--------|----------|
| RTB Bidstream | < 100ms | ✅ 服务端→客户端 | 高 (10K+ msg/s) | WebSocket |
| 广告实时监控 | < 1s | ❌ 单向为主 | 中 | WebSocket 或 SSE |
| 预算告警推送 | < 5s | ❌ 单向 | 低 | SSE 或 MQTT |
| 竞价响应 (RTB) | < 50ms | ✅ 双向 | 极高 | gRPC-streaming |
| IoT 设备上报 | < 1s | ✅ 双向 | 低 | MQTT |

### 1.2 WebSocket 握手协议

```
客户端 → 服务端 (Upgrade 请求):
GET /ws/ad-monitor HTTP/1.1
Host: weread.qq.com
Upgrade: websocket
Connection: Upgrade
Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==
Sec-WebSocket-Version: 13
Sec-WebSocket-Protocol: ad-bidstream-v2

服务端 → 客户端 (101 Switching Protocols):
HTTP/1.1 101 Switching Protocols
Upgrade: websocket
Connection: Upgrade
Sec-WebSocket-Accept: s3pPLMBiTxaQ9kYGzzhZRbK+xOo=
Sec-WebSocket-Protocol: ad-bidstream-v2
```

**Sec-WebSocket-Accept 计算：**

```go
// RFC 6455 规定的 Accept 计算
package websocket

import (
	"crypto/sha1"
	"encoding/base64"
)

const websocketGUID = "258EAFA5-E914-47DA-95CA-5AB5DC10660B"

func computeAccept(key string) string {
	h := sha1.New()
	h.Write([]byte(key + websocketGUID))
	return base64.StdEncoding.EncodeToString(h.Sum(nil))
}

// 验证: Sec-WebSocket-Key = "dGhlIHNhbXBsZSBub25jZQ=="
// Accept = SHA1("dGhlIHNhbXBsZSBub25jZQ==258EAFA5-E914-47DA-95CA-5AB5DC10660B")
//        = base64(s3pPLMBiTxaQ9kYGzzhZRbK+xOo=)
```

### 1.3 WebSocket 帧格式（RFC 6455）

```
0                   1                   2                   3
0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
+-+-+-+-+-------+-+-------------+-------------------------------+
|F|R|R|R| opcode|M| Payload len |    Extended payload length    |
|I|S|S|S|  (4)  |A|     (7)     |             (16/64)           |
|N|V|V|V|       |S|             |   (if payload len==126/127)   |
| |1|2|3|       |K|             |                               |
+-+-+-+-+-------+-+-------------+ - - - - - - - - - - - - - - - +
|     Extended payload length continued, if payload len == 127  |
+ - - - - - - - - - - - - - - - +-------------------------------+
|                               |Masking-key, if MASK set to 1  |
+-------------------------------+-------------------------------+
| Masking-key (continued)       |          Payload Data         |
+-------------------------------- - - - - - - - - - - - - - - - +
:                     Payload Data continued ...                :
+ - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - +
|                     Payload Data continued |
+---------------------------------------------------------------+
```

**关键字段解析：**

| 字段 | 长度 | 说明 |
|------|------|------|
| FIN | 1 bit | 是否为最后帧（分帧消息） |
| RSV1-3 | 各 1 bit | 扩展协商，通常为 0 |
| Opcode | 4 bits | 0x0=数据, 0x1=文本, 0x2=二进制, 0x8=关闭, 0x9=Ping, 0xA=Pong |
| MASK | 1 bit | 客户端帧必须掩码 |
| Payload Len | 7/15/63 bits | 载荷长度，≥126 用扩展长度 |
| Masking-Key | 32 bits | 掩码密钥 |
| Payload Data | 变长 | 实际数据 |

**客户端掩码算法（XOR）：**

```go
// RFC 6455 Section 5.3: 客户端发送的帧必须掩码
func maskFrame(payload []byte, maskKey [4]byte) []byte {
	result := make([]byte, len(payload))
	for i := range payload {
		result[i] = payload[i] ^ maskKey[i%4]
	}
	return result
}

// 服务端收到后解掩码
func unmaskFrame(payload []byte, maskKey [4]byte) {
	for i := range payload {
		payload[i] ^= maskKey[i%4]
	}
}
```

### 1.4 分帧与合并

```
大消息分帧 (Fragmentation):
┌─────────┐     ┌─────────┐     ┌─────────┐
| FIN=0   |     | FIN=0   |     | FIN=1   |
| Opcode  |     | Opcode  |     | Opcode  |
| Payload |     | Payload |     | Payload |
└─────────┘     └─────────┘     └─────────┘
   第一帧          中间帧           最后一帧
   (continuation)  (continuation)   (complete)

广告平台典型用例:
- BidRequest JSON > 128KB → 分帧发送
- 实时监控大屏数据 > 64KB → 二进制分帧
- 心跳 Ping/Pong → 控制帧（无 payload）
```

---

## 二、Go WebSocket 生产实现

### 2.1 技术选型：gorilla/websocket vs nhooyr.io/websocket

| 特性 | gorilla/websocket | nhooyr.io/websocket | net/http 内置 |
|------|-------------------|--------------------|---------------|
| 成熟度 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| 性能 | 中等 | 高 | 最高 |
| API 简洁度 | 中等 | 好 | 最好 |
| 社区支持 | 广泛 | 良好 | 官方 |
| Go 版本要求 | 1.12+ | 1.18+ | 1.22+ |
| 广告平台推荐 | 老项目/稳定 | 新项目/高性能 | Go 1.22+ 首选 |

**Go 1.22+ 内置 ws 包（推荐新项目）：**

```go
// Go 1.22+ net/http 内置 WebSocket 支持
package main

import (
	"log"
	"net/http"
)

func main() {
	http.HandleFunc("/ws", func(w http.ResponseWriter, r *http.Request) {
		upgrader := http.NewWSUpgrader() // Go 1.22+
		conn, err := upgrader.Upgrade(w, r, nil)
		if err != nil {
			log.Printf("upgrade: %v", err)
			return
		}
		defer conn.Close()
		
		for {
			mt, message, err := conn.ReadMessage()
			if err != nil {
				break
			}
			// 处理消息
			_ = mt
			_ = message
		}
	})
	
	log.Fatal(http.ListenAndServe(":8080", nil))
}
```

### 2.2 生产级 WebSocket 服务器（gorilla）

```go
package websocket

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"sync"
	"time"

	"github.com/gorilla/websocket"
)

// ==================== 消息协议定义 ====================

// AdEvent 广告事件（WebSocket 传输的统一消息格式）
type AdEvent struct {
	Type      string                 `json:"type"`       // impression, click, conversion, budget_alert
	Timestamp time.Time              `json:"timestamp"`
	Data      map[string]interface{} `json:"data"`
	SessionID string                 `json:"session_id,omitempty"`
}

// BidStream 竞价流消息
type BidStream struct {
	BidID     string   `json:"bid_id"`
	Request   BidRequest `json:"request"`
	Responses []BidResponse `json:"responses,omitempty"`
	Status    string   `json:"status"` // pending, won, lost, timeout
}

type BidRequest struct {
	ImpressionID string   `json:"imp_id"`
	AdSpaceID    string   `json:"ad_space"`
	UserID       string   `json:"user_id"`
	Device       DeviceInfo `json:"device"`
	Geo          GeoInfo    `json:"geo"`
	Budget       float64   `json:"budget"`
	MaxBid       float64   `json:"max_bid"`
	TTL          int       `json:"ttl_ms"` // 竞价超时毫秒
}

type DeviceInfo struct {
	Make    string `json:"make"`
	Model   string `json:"model"`
	OS      string `json:"os"`
	Browser string `json:"browser"`
}

type GeoInfo struct {
	Country string  `json:"country"`
	Region  string  `json:"region"`
	City    string  `json:"city"`
	Lat     float64 `json:"lat"`
	Lon     float64 `json:"lon"`
}

type BidResponse struct {
	CreatorID string  `json:"creator_id"`
	BidPrice  float64 `json:"bid_price"`
	CreativeID string `json:"creative_id"`
	Targeting map[string]string `json:"targeting,omitempty"`
}

// ==================== Hub 连接管理 ====================

// Hub 管理所有 WebSocket 连接
type Hub struct {
	clients    map[string]*Client   // clientID -> Client
	register   chan *Client
	unregister chan *Client
	broadcast  chan *BroadcastMessage
	mu         sync.RWMutex
}

type BroadcastMessage struct {
	EventType string
	Payload   []byte
	Targets   map[string]bool // 订阅该事件类型的客户端
}

// Client 代表一个 WebSocket 客户端
type Client struct {
	hub      *Hub
	conn     *websocket.Conn
	send     chan []byte       // 发送缓冲区
	clientID string
	tags     map[string]bool   // 订阅标签: "impression", "click"
	mu       sync.RWMutex
}

// NewHub 创建 Hub
func NewHub() *Hub {
	return &Hub{
		clients:    make(map[string]*Client),
		register:   make(chan *Client),
		unregister: make(chan *Client),
		broadcast:  make(chan *BroadcastMessage, 1000),
	}
}

// Run 运行 Hub（在 goroutine 中启动）
func (h *Hub) Run(ctx context.Context) {
	for {
		select {
		case <-ctx.Done():
			return
		case client := <-h.register:
			h.mu.Lock()
			h.clients[client.clientID] = client
			h.mu.Unlock()
			log.Printf("Client registered: %s (total: %d)", client.clientID, len(h.clients))
			
		case client := <-h.unregister:
			h.mu.Lock()
			if _, ok := h.clients[client.clientID]; ok {
				close(client.send)
				delete(h.clients, client.clientID)
			}
			h.mu.Unlock()
			log.Printf("Client unregistered: %s (total: %d)", client.clientID, len(h.clients))
			
		case msg := <-h.broadcast:
			h.mu.RLock()
			for id, client := range h.clients {
				client.mu.RLock()
				if client.tags[msg.EventType] {
					select {
					case client.send <- msg.Payload:
					default:
						// 发送缓冲区满，跳过
						log.Printf("Client %s send buffer full, dropping message", id)
					}
				}
				client.mu.RUnlock()
			}
			h.mu.RUnlock()
		}
	}
}

// ==================== 客户端读写循环 ====================

const (
	writeWait      = 10 * time.Second
	pongWait       = 60 * time.Second
	pingPeriod     = (pongWait * 9) / 10
	maxMessageSize = 65536 // 64KB
)

func (c *Client) readLoop() {
	defer func() {
		c.hub.unregister <- c
		c.conn.Close()
	}()
	
	c.conn.SetReadLimit(maxMessageSize)
	c.conn.SetReadDeadline(time.Now().Add(pongWait))
	c.conn.PongHandler(func(string) error {
		c.conn.SetReadDeadline(time.Now().Add(pongWait))
		return nil
	})
	
	for {
		_, message, err := c.conn.ReadMessage()
		if err != nil {
			if websocket.IsUnexpectedCloseError(err,
				websocket.CloseGoingAway, websocket.CloseAbnormalClosure) {
				log.Printf("Client %s error: %v", c.clientID, err)
			}
			break
		}
		
		// 解析客户端消息
		var event AdEvent
		if err := json.Unmarshal(message, &event); err != nil {
			log.Printf("Client %s invalid message: %v", c.clientID, err)
			continue
		}
		
		// 处理订阅变更
		if event.Type == "subscribe" {
			c.mu.Lock()
			c.tags[event.Data["event_type"].(string)] = true
			c.mu.Unlock()
			log.Printf("Client %s subscribed to %s", c.clientID, event.Data["event_type"])
		}
	}
}

func (c *Client) writeLoop() {
	ticker := time.NewTicker(pingPeriod)
	defer func() {
		ticker.Stop()
		c.conn.Close()
	}()
	
	for {
		select {
		case message, ok := <-c.send:
			c.conn.SetWriteDeadline(time.Now().Add(writeWait))
			if !ok {
				c.conn.WriteMessage(websocket.CloseMessage, []byte{})
				return
			}
			
			w, err := c.conn.NextWriter(websocket.TextMessage)
			if err != nil {
				return
			}
			w.Write(message)
			
			// 批量发送 queued messages
			n := len(c.send)
			for i := 0; i < n; i++ {
				w.Write([]byte{'\n'})
				w.Write(<-c.send)
			}
			
			if err := w.Close(); err != nil {
				return
			}
			
		case <-ticker.C:
			c.conn.SetWriteDeadline(time.Now().Add(writeWait))
			if err := c.conn.WriteMessage(websocket.PingMessage, nil); err != nil {
				return
			}
		}
	}
}

// ==================== HTTP Handler ====================

var upgrader = websocket.Upgrader{
	ReadBufferSize:  4096,
	WriteBufferSize: 4096,
	CheckOrigin: func(r *http.Request) bool {
		// 生产环境应严格校验 Origin
		origin := r.Header.Get("Origin")
		return origin == "https://ads.example.com" || origin == "https://admin.example.com"
	},
}

// WSHandler WebSocket 端点
func (h *Hub) WSHandler(w http.ResponseWriter, r *http.Request) {
	// 1. 鉴权：从 query param 或 header 获取 token
	token := r.URL.Query().Get("token")
	if token == "" {
		token = r.Header.Get("Authorization")
	}
	if token == "" {
		http.Error(w, "Missing token", http.StatusUnauthorized)
		return
	}
	
	claims, err := validateJWT(token) // 实际项目中调用认证服务
	if err != nil {
		http.Error(w, "Invalid token", http.StatusUnauthorized)
		return
	}
	
	// 2. 升级 WebSocket
	conn, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		log.Printf("WebSocket upgrade error: %v", err)
		return
	}
	
	// 3. 创建 Client
	client := &Client{
		hub:      h,
		conn:     conn,
		send:     make(chan []byte, 256),
		clientID: claims.UserID,
		tags:     make(map[string]bool),
	}
	
	// 4. 注册到 Hub
	h.register <- client
	
	// 5. 启动读写协程
	go client.writeLoop()
	go client.readLoop()
}

func validateJWT(token string) (*JWTClaims, error) {
	// 简化实现：实际项目用 golang-jwt
	return &JWTClaims{UserID: "user_123"}, nil
}

type JWTClaims struct {
	UserID string
	Roles  []string
}

// ==================== 广播服务 ====================

// Broadcaster 从 Kafka/Redis 消费事件并广播到 WebSocket 客户端
type Broadcaster struct {
	hub     *Hub
	ctx     context.Context
	cancel  context.CancelFunc
}

func NewBroadcaster(hub *Hub) *Broadcaster {
	ctx, cancel := context.WithCancel(context.Background())
	return &Broadcaster{hub: hub, ctx: ctx, cancel: cancel}
}

// Start 启动广播（从消息队列消费事件）
func (b *Broadcaster) Start(eventChan <-chan AdEvent) {
	go func() {
		for {
			select {
			case <-b.ctx.Done():
				return
			case event, ok := <-eventChan:
				if !ok {
					return
				}
				b.broadcastEvent(event)
			}
		}
	}()
}

func (b *Broadcaster) broadcastEvent(event AdEvent) {
	payload, _ := json.Marshal(event)
	
	msg := &BroadcastMessage{
		EventType: event.Type,
		Payload:   payload,
		Targets:   nil, // nil = 广播给所有订阅者
	}
	
	select {
	case b.hub.broadcast <- msg:
	default:
		log.Printf("Broadcaster: broadcast channel full, dropping event %s", event.Type)
	}
}

func (b *Broadcaster) Stop() {
	b.cancel()
}

// ==================== 实战：RTB Bidstream 推送 ====================

// BidstreamService 竞价流服务
type BidstreamService struct {
	hub      *Hub
	broadcaster *Broadcaster
}

// PushBidRequest 推送竞价请求到客户端
func (s *BidstreamService) PushBidRequest(req BidRequest) error {
	stream := &BidStream{
		BidID:   fmt.Sprintf("bid_%d", time.Now().UnixNano()),
		Request: req,
		Status:  "pending",
	}
	
	payload, err := json.Marshal(stream)
	if err != nil {
		return fmt.Errorf("marshal bid stream: %w", err)
	}
	
	event := AdEvent{
		Type:      "bid_request",
		Timestamp: time.Now(),
		Data:      map[string]interface{}{"stream": stream},
	}
	
	// 通过 Hub 广播
	msg := &BroadcastMessage{
		EventType: "bid_request",
		Payload:   payload,
	}
	
	select {
	case s.hub.broadcast <- msg:
		return nil
	default:
		return fmt.Errorf("broadcast channel full")
	}
}

// PushBidResponse 推送竞价响应
func (s *BidstreamService) PushBidResponse(resp BidResponse) error {
	stream := &BidStream{
		BidID:     resp.Targeting["bid_id"],
		Responses: []BidResponse{resp},
		Status:    "response_received",
	}
	
	payload, _ := json.Marshal(stream)
	
	select {
	case s.hub.broadcast <- &BroadcastMessage{
		EventType: "bid_response",
		Payload:   payload,
	}:
		return nil
	default:
		return fmt.Errorf("broadcast channel full")
	}
}

// ==================== 实战：实时监控面板 ====================

// MonitorService 实时监控服务
type MonitorService struct {
	hub *Hub
}

// PushMetric 推送指标数据到监控面板
func (s *MonitorService) PushMetric(metricType string, data map[string]interface{}) {
	payload, _ := json.Marshal(AdEvent{
		Type:      metricType,
		Timestamp: time.Now(),
		Data:      data,
	})
	
	s.hub.broadcast <- &BroadcastMessage{
		EventType: "metric",
		Payload:   payload,
	}
}

// PushAlert 推送告警
func (s *MonitorService) PushAlert(alert Alert) {
	payload, _ := json.Marshal(AdEvent{
		Type:      "alert",
		Timestamp: time.Now(),
		Data: map[string]interface{}{
			"level":    alert.Level,
			"campaign": alert.CampaignID,
			"message":  alert.Message,
		},
	})
	
	s.hub.broadcast <- &BroadcastMessage{
		EventType: "alert",
		Payload:   payload,
	}
}

type Alert struct {
	Level      string // info, warning, critical
	CampaignID string
	Message    string
}

// ==================== 第三部分：WebSocket 安全与运维 ====================

// 3.1 安全最佳实践

// SecurityConfig 安全配置
type SecurityConfig struct {
	MaxConnectionsPerIP   int           // 单 IP 最大连接数
	ConnectionTimeout     time.Duration // 连接超时
	MessageSizeLimit      int           // 单消息大小限制（字节）
	AllowedOrigins        []string      // 允许的 Origin
	EnableCompression     bool          // 是否启用扩展：permessage-deflate
	AuthHandler           func(token string) (*Claims, error) // 自定义鉴权
}

// RateLimiter 连接速率限制
type RateLimiter struct {
	mu       sync.Mutex
	clients  map[string]*ClientCounter
	interval time.Duration
	limit    int
}

type ClientCounter struct {
	count    int
	resetAt  time.Time
}

func NewRateLimiter(interval time.Duration, limit int) *RateLimiter {
	return &RateLimiter{
		clients:  make(map[string]*ClientCounter),
		interval: interval,
		limit:    limit,
	}
}

func (rl *RateLimiter) Allow(ip string) bool {
	rl.mu.Lock()
	defer rl.mu.Unlock()
	
	now := time.Now()
	counter, exists := rl.clients[ip]
	if !exists || now.After(counter.resetAt) {
		rl.clients[ip] = &ClientCounter{count: 1, resetAt: now.Add(rl.interval)}
		return true
	}
	
	counter.count++
	return counter.count <= rl.limit
}

// 3.2 生产部署架构

/*
WebSocket 生产部署拓扑:

                    ┌──────────────┐
                    │   Nginx LB   │
                    │ (sticky sess)│
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
        ┌──────────┐ ┌──────────┐ ┌──────────┐
        │ WS Node 1│ │ WS Node 2│ │ WS Node 3│
        │ :8080/ws │ │ :8080/ws │ │ :8080/ws │
        └────┬─────┘ └────┬─────┘ └────┬─────┘
             │            │            │
             └────────────┼────────────┘
                          ▼
                   ┌─────────────┐
                   │   Redis Pub  │
                   │  (跨节点广播) │
                   └─────────────┘
                          ▲
                          │
                   ┌─────────────┐
                   │   Kafka      │
                   │ (事件源)      │
                   └─────────────┘
*/

// RedisBridge Redis 跨节点消息桥接
type RedisBridge struct {
	pubsub *redis.PubSub
	chans  map[string]chan []byte
	mu     sync.RWMutex
}

func NewRedisBridge(client *redis.Client) *RedisBridge {
	return &RedisBridge{
		chans: make(map[string]chan []byte),
	}
}

func (rb *RedisBridge) Subscribe(channel string) <-chan []byte {
	rb.mu.Lock()
	defer rb.mu.Unlock()
	
	if ch, exists := rb.chans[channel]; exists {
		return ch
	}
	
	ch := make(chan []byte, 1000)
	rb.chans[channel] = ch
	
	// 启动 Redis 订阅协程
	go func() {
		pubsub := client.Subscribe(context.Background(), channel)
		pubsub.Receive(context.Background()) // 确认订阅成功
		
		for msg := range pubsub.Channel() {
			select {
			case ch <- []byte(msg.Payload):
			default:
				log.Printf("Redis bridge channel full for %s", channel)
			}
		}
	}()
	
	return ch
}

// 3.3 性能调优

/*
WebSocket 性能调优 checklist:

1. 连接数限制
   - 单机 Gorilla: ~10K 连接 (取决于内存)
   - 单机 nhooyr: ~50K+ 连接 (更少的 goroutine)
   - 使用 epoll/epoll-on 减少系统调用

2. 消息大小限制
   - 设置 ReadLimit 防止 OOM
   - 二进制消息 > 文本消息（节省序列化开销）

3. 心跳间隔
   - Ping/Pong 间隔 ≤ 30s
   - 检测死连接，及时清理

4. 批量发送
   - NextWriter 合并多条消息
   - 减少 syscall 次数

5. 内存优化
   - 使用 sync.Pool 复用 []byte
   - 避免频繁 GC
*/

// ==================== 第四部分：WebSocket vs SSE vs gRPC-streaming ====================

/*
方案对比:

┌────────────────┬──────────────┬──────────────┬─────────────────┐
│     特性       │  WebSocket   │    SSE       │ gRPC-streaming  │
├────────────────┼──────────────┼──────────────┼─────────────────┤
│ 通信方向       │ 全双工       │ 服务端→客户端│ 全双工/单向     │
│ 协议           │ WS over TCP  │ HTTP/1.1     │ HTTP/2          │
│ 浏览器支持      │ ✅           │ ✅           │ ❌ (需 grpc-web)│
│ 消息格式       │ 任意         │ JSON/text    │ Protobuf        │
│ 自动重连       │ ❌ (需实现)   │ ✅           │ ✅              │
│ 延迟           │ < 10ms       │ < 50ms       │ < 5ms           │
│ 吞吐量         │ 中           │ 低           │ 高              │
│ 防火墙友好     │ ❌ (需 80/443)│ ✅           │ ✅ (HTTP/2)     │
│ 适用场景       │ 实时交互     │ 数据推送     │ 内部服务通信    │
└────────────────┴──────────────┴──────────────┴─────────────────┘

广告平台选型决策树:

需要双向通信?
├── 是 → 需要浏览器客户端?
│   ├── 是 → WebSocket (bidstream, 实时竞价)
│   └── 否 → gRPC-streaming (内部服务通信)
└── 否 → 只需要服务端推送?
    ├── 需要自动重连 → SSE (预算告警, 指标推送)
    └── 高吞吐 → WebSocket binary (大规模指标)
*/

// ==================== 第五部分：自测题 ====================

/*
自测题 1: WebSocket 连接管理

问题：在一个广告实时监控系统中，有 10K 个 WebSocket 连接，
每秒产生 50K 条事件。如何设计才能保证所有客户端都能及时收到消息？

答案要点：
1. Hub 广播使用 channel，缓冲区 ≥ 10K
2. 客户端分片：按 campaignID hash 到不同 Hub 实例
3. 消息压缩：使用 permessage-deflate 扩展
4. 批量发送：NextWriter 合并多条消息
5. 背压处理：客户端 send channel 满时，丢弃旧消息或断开

Go 实现思路：
- 使用 sharded Hub（16 个分片）
- 每个分片管理 ~625 个连接
- Redis Pub/Sub 跨分片广播
- 客户端连接数超过阈值时，拒绝新连接

---

自测题 2: WebSocket 安全

问题：如何防止 WebSocket 连接被滥用（DDoS、连接泄漏、未授权访问）？

答案要点：
1. 鉴权：连接前验证 JWT token
2. 限流：单 IP 最大连接数限制
3. 超时：空闲连接定时清理
4. 消息大小限制：防止 OOM 攻击
5. Origin 校验：防止 CSRF
6. 速率限制：单连接每秒最大消息数

---

自测题 3: 性能优化

问题：WebSocket 服务器出现高 CPU 使用率，如何排查和优化？

答案要点：
1. pprof 分析：go tool pprof http://host/debug/pprof/profile
2. 检查 goroutine 泄漏：go tool pprof http://host/debug/pprof/goroutine
3. GC 压力：检查 alloc_objects/space 指标
4. 优化方向：
   - 减少 JSON 序列化开销 → 使用 protobuf
   - 批量发送消息 → 合并多次 Write
   - 连接池复用 → 避免频繁创建/销毁
   - 使用 sync.Pool 复用 []byte
   - 考虑切换到 nhooyr.io/websocket（更少 goroutine）
*/

// ==================== 第六部分：动手验证 ====================

/*
验证步骤:

1. 本地启动 WebSocket 服务器
   go run main.go

2. 使用 wscat 测试连接
   wscat -c ws://localhost:8080/ws?token=<jwt>

3. 模拟 1000 并发连接
   wrk -t4 -c1000 -d30s http://localhost:8080/ws

4. 监控 goroutine 数量
   go tool pprof http://localhost:6060/debug/pprof/goroutine

5. 检查内存使用
   go tool pprof http://localhost:6060/debug/pprof/heap

6. 压测消息吞吐
   - 发送端: 10K msg/s
   - 接收端: 验证所有消息到达
   - 测量延迟分布 (p50/p95/p99)
*/
