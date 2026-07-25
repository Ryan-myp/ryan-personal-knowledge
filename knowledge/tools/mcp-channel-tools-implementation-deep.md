# MCP 工具技能：多渠道广告平台 MCP 工具实现

> 来源：ad_smart_delivery_platform 项目
> 状态：基于代码实现蒸馏
> 蒸馏日期：2026-06-18

---

## 第一部分：MCP 工具注册中心

### 工具注册与管理

```
MCP 工具注册中心：
┌─────────────────────────────────────────────────────────────────────┐
│ 1. 工具注册                                                          │
│    ├── 工具名称：唯一标识符                                         │
│    ├── 工具描述：功能说明                                           │
│    ├── 输入参数：JSON Schema 定义                                   │
│    └── 返回值：结构化响应                                           │
│                                                                     │
│ 2. 工具版本控制                                                      │
│    ├── 版本号：语义化版本控制                                       │
│    ├── 兼容性：向后兼容保证                                         │
│    └── 废弃：废弃标记与迁移指南                                     │
│                                                                     │
│ 3. 工具依赖管理                                                      │
│    ├── 依赖注入：工具间依赖关系                                     │
│    ├── 初始化：工具初始化顺序                                       │
│    └── 销毁：工具清理顺序                                           │
└─────────────────────────────────────────────────────────────────────┘
```

### 工具元数据

```
工具元数据：
┌─────────────────────────────────────────────────────────────────────┐
│ 1. 基本信息                                                          │
│    ├── 名称：工具唯一标识                                           │
│    ├── 版本：语义化版本号                                           │
│    ├── 描述：功能描述                                               │
│    └── 标签：分类标签                                               │
│                                                                     │
│ 2. 参数定义                                                          │
│    ├── 必需参数：必填字段                                           │
│    ├── 可选参数：选填字段                                           │
│    └── 默认值：参数默认值                                           │
│                                                                     │
│ 3. 权限定义                                                          │
│    ├── 认证要求：认证方式                                           │
│    ├── 权限范围：所需权限                                           │
│    └── 角色限制：角色限制                                           │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 第二部分：营销 API 工具

### 账户管理工具

```
账户管理工具：
┌─────────────────────────────────────────────────────────────────────┐
│ 1. 获取账户列表                                                      │
│    ├── 工具名：list_accounts                                        │
│    ├── 参数：{channel, status, page, limit}                         │
│    └── 返回：[{id, name, channel, status, ...}]                     │
│                                                                     │
│ 2. 创建账户                                                          │
│    ├── 工具名：create_account                                       │
│    ├── 参数：{channel, name, config, permissions}                   │
│    └── 返回：{id, name, channel, status, ...}                       │
│                                                                     │
│ 3. 更新账户                                                          │
│    ├── 工具名：update_account                                       │
│    ├── 参数：{id, name, config, status}                             │
│    └── 返回：{id, name, channel, status, ...}                       │
│                                                                     │
│ 4. 删除账户                                                          │
│    ├── 工具名：delete_account                                       │
│    ├── 参数：{id}                                                   │
│    └── 返回：{success, message}                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 广告系列管理工具

```
广告系列管理工具：
┌─────────────────────────────────────────────────────────────────────┐
│ 1. 获取广告系列列表                                                  │
│    ├── 工具名：list_campaigns                                       │
│    ├── 参数：{account_id, channel, status, page, limit}             │
│    └── 返回：[{id, name, status, budget, ...}]                      │
│                                                                     │
│ 2. 创建广告系列                                                      │
│    ├── 工具名：create_campaign                                      │
│    ├── 参数：{account_id, name, status, budget, schedule}           │
│    └── 返回：{id, name, status, budget, ...}                        │
│                                                                     │
│ 3. 更新广告系列                                                      │
│    ├── 工具名：update_campaign                                      │
│    ├── 参数：{id, name, status, budget, schedule}                   │
│    └── 返回：{id, name, status, budget, ...}                        │
│                                                                     │
│ 4. 删除广告系列                                                      │
│    ├── 工具名：delete_campaign                                      │
│    ├── 参数：{id}                                                   │
│    └── 返回：{success, message}                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 广告组管理工具

```
广告组管理工具：
┌─────────────────────────────────────────────────────────────────────┐
│ 1. 获取广告组列表                                                    │
│    ├── 工具名：list_ad_groups                                       │
│    ├── 参数：{campaign_id, channel, status, page, limit}            │
│    └── 返回：[{id, name, status, bid, ...}]                         │
│                                                                     │
│ 2. 创建广告组                                                        │
│    ├── 工具名：create_ad_group                                      │
│    ├── 参数：{campaign_id, name, status, bid, targeting}            │
│    └── 返回：{id, name, status, bid, ...}                           │
│                                                                     │
│ 3. 更新广告组                                                        │
│    ├── 工具名：update_ad_group                                      │
│    ├── 参数：{id, name, status, bid, targeting}                     │
│    └── 返回：{id, name, status, bid, ...}                           │
│                                                                     │
│ 4. 删除广告组                                                        │
│    ├── 工具名：delete_ad_group                                      │
│    ├── 参数：{id}                                                   │
│    └── 返回：{success, message}                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 创意管理工具

```
创意管理工具：
┌─────────────────────────────────────────────────────────────────────┐
│ 1. 获取创意列表                                                      │
│    ├── 工具名：list_creatives                                       │
│    ├── 参数：{ad_group_id, channel, status, page, limit}            │
│    └── 返回：[{id, name, type, url, ...}]                           │
│                                                                     │
│ 2. 创建创意                                                          │
│    ├── 工具名：create_creative                                      │
│    ├── 参数：{ad_group_id, name, type, url, dimensions}             │
│    └── 返回：{id, name, type, url, ...}                             │
│                                                                     │
│ 3. 更新创意                                                          │
│    ├── 工具名：update_creative                                      │
│    ├── 参数：{id, name, type, url, dimensions}                      │
│    └── 返回：{id, name, type, url, ...}                             │
│                                                                     │
│ 4. 删除创意                                                          │
│    ├── 工具名：delete_creative                                      │
│    ├── 参数：{id}                                                   │
│    └── 返回：{success, message}                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 第三部分：平台适配器工具

### Google Ads 适配器工具

```
Google Ads 适配器工具：
┌─────────────────────────────────────────────────────────────────────┐
│ 1. 认证管理                                                          │
│    ├── 工具名：google_auth                                          │
│    ├── 参数：{client_id, client_secret, redirect_uri}               │
│    └── 返回：{access_token, refresh_token, expires_in}              │
│                                                                     │
│ 2. 广告系列操作                                                      │
│    ├── 工具名：google_campaigns                                     │
│    ├── 参数：{action, campaign_data}                                │
│    └── 返回：{result, message}                                      │
│                                                                     │
│ 3. 广告组操作                                                        │
│    ├── 工具名：google_ad_groups                                     │
│    ├── 参数：{action, ad_group_data}                                │
│    └── 返回：{result, message}                                      │
│                                                                     │
│ 4. 创意操作                                                          │
│    ├── 工具名：google_creatives                                     │
│    ├── 参数：{action, creative_data}                                │
│    └── 返回：{result, message}                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Facebook Ads 适配器工具

```
Facebook Ads 适配器工具：
┌─────────────────────────────────────────────────────────────────────┐
│ 1. 认证管理                                                          │
│    ├── 工具名：facebook_auth                                        │
│    ├── 参数：{app_id, app_secret, redirect_uri}                     │
│    └── 返回：{access_token, refresh_token, expires_in}              │
│                                                                     │
│ 2. 广告账户操作                                                      │
│    ├── 工具名：facebook_ad_accounts                                 │
│    ├── 参数：{action, account_data}                                 │
│    └── 返回：{result, message}                                      │
│                                                                     │
│ 3. 广告系列操作                                                      │
│    ├── 工具名：facebook_campaigns                                   │
│    ├── 参数：{action, campaign_data}                                │
│    └── 返回：{result, message}                                      │
│                                                                     │
│ 4. 广告组操作                                                        │
│    ├── 工具名：facebook_ad_sets                                     │
│    ├── 参数：{action, ad_set_data}                                  │
│    └── 返回：{result, message}                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### TikTok Ads 适配器工具

```
TikTok Ads 适配器工具：
┌─────────────────────────────────────────────────────────────────────┐
│ 1. 认证管理                                                          │
│    ├── 工具名：tiktok_auth                                          │
│    ├── 参数：{client_key, client_secret, redirect_uri}              │
│    └── 返回：{access_token, refresh_token, expires_in}              │
│                                                                     │
│ 2. 广告账户操作                                                      │
│    ├── 工具名：tiktok_advertisers                                   │
│    ├── 参数：{action, advertiser_data}                              │
│    └── 返回：{result, message}                                      │
│                                                                     │
│ 3. 广告系列操作                                                      │
│    ├── 工具名：tiktok_campaigns                                     │
│    ├── 参数：{action, campaign_data}                                │
│    └── 返回：{result, message}                                      │
│                                                                     │
│ 4. 广告组操作                                                        │
│    ├── 工具名：tiktok_ad_groups                                     │
│    ├── 参数：{action, ad_group_data}                                │
│    └── 返回：{result, message}                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### DV360 适配器工具

```
DV360 适配器工具：
┌─────────────────────────────────────────────────────────────────────┐
│ 1. 认证管理                                                          │
│    ├── 工具名：dv360_auth                                           │
│    ├── 参数：{client_id, client_secret, developer_token}            │
│    └── 返回：{access_token, refresh_token, expires_in}              │
│                                                                     │
│ 2. 广告账户操作                                                      │
│    ├── 工具名：dv360_advertisers                                    │
│    ├── 参数：{action, advertiser_data}                              │
│    └── 返回：{result, message}                                      │
│                                                                     │
│ 3. 广告系列操作                                                      │
│    ├── 工具名：dv360_campaigns                                      │
│    ├── 参数：{action, campaign_data}                                │
│    └── 返回：{result, message}                                      │
│                                                                     │
│ 4. 广告组操作                                                        │
│    ├── 工具名：dv360_ad_groups                                      │
│    ├── 参数：{action, ad_group_data}                                │
│    └── 返回：{result, message}                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 第四部分：二次确认机制

### 危险操作拦截

```
二次确认机制：
┌─────────────────────────────────────────────────────────────────────┐
│ 1. 操作分类                                                          │
│    ├── 只读操作：无需确认                                           │
│    ├── 普通操作：需要确认                                           │
│    └── 危险操作：需要二次确认                                       │
│                                                                     │
│ 2. 确认方式                                                          │
│    ├── 文本确认：用户输入确认文本                                   │
│    ├── 数字确认：用户输入确认数字                                   │
│    └── 签名确认：用户数字签名                                       │
│                                                                     │
│ 3. 确认流程                                                          │
│    ├── 操作预览：显示即将执行的操作                                 │
│    ├── 风险提醒：提示潜在风险                                       │
│    └── 确认执行：用户确认后执行                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 危险操作清单

```
危险操作清单：
┌─────────────────────────────────────────────────────────────────────┐
│ 1. 删除操作                                                          │
│    ├── 删除广告系列                                                 │
│    ├── 删除广告组                                                   │
│    ├── 删除创意                                                     │
│    └── 删除账户                                                     │
│                                                                     │
│ 2. 修改操作                                                          │
│    ├── 修改预算                                                       │
│    ├── 修改出价                                                       │
│    ├── 修改定向                                                       │
│    └── 修改状态                                                       │
│                                                                     │
│ 3. 批量操作                                                          │
│    ├── 批量暂停                                                       │
│    ├── 批量启用                                                       │
│    ├── 批量修改                                                       │
│    └── 批量删除                                                       │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 第五部分：自测题

### Q1: MCP 工具注册的三大要素？

**A**: 工具名称（唯一标识）、工具描述（功能说明）、输入参数（JSON Schema 定义）。

### Q2: 四大平台适配器的共同认证方式？

**A**: 都使用 OAuth2 认证、都有访问令牌刷新机制、都有权限范围控制。

### Q3: 二次确认机制的三个层面？

**A**: 操作分类（只读/普通/危险）、确认方式（文本/数字/签名）、确认流程（预览/提醒/执行）。

---

## Go 代码实战：MCP 工具实现深度

### 1. MCP SSE 传输层（HTTP 长连接）

```go
package mcp

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"sync"
)

// SSETransport SSE 传输层（适合 HTTP 场景）
type SSETransport struct {
	mu         sync.Mutex
	writers    map[http.ResponseWriter]struct{}
	eventCh    chan *Message
	stopCh     chan struct{}
}

func NewSSETransport() *SSETransport {
	return &SSETransport{
		writers: make(map[http.ResponseWriter]struct{}),
		eventCh: make(chan *Message, 100),
		stopCh:  make(chan struct{}),
	}
}

func (t *SSETransport) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	switch r.Method {
	case "GET":
		t.handleSSE(w, r) // 接收事件
	case "POST":
		t.handleJSONRPC(w, r) // 发送消息
	default:
		http.Error(w, "Method not allowed", 405)
	}
}

func (t *SSETransport) handleSSE(w http.ResponseWriter, r *http.Request) {
	flusher, ok := w.(http.Flusher)
	if !ok {
		http.Error(w, "Streaming unsupported", 500)
		return
	}
	
	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("Connection", "keep-alive")
	
	flusher.Flush()
	
	t.mu.Lock()
	t.writers[w] = struct{}{}
	t.mu.Unlock()
	
	defer func() {
		t.mu.Lock()
		delete(t.writers, w)
		t.mu.Unlock()
	}()
	
	ctx := r.Context()
	for {
		select {
		case msg := <-t.eventCh:
			data, _ := json.Marshal(msg)
			fmt.Fprintf(w, "data: %s\n\n", data)
			flusher.Flush()
			
		case <-ctx.Done():
			return
		}
	}
}

func (t *SSETransport) handleJSONRPC(w http.ResponseWriter, r *http.Request) {
	var msg Message
	if err := json.NewDecoder(r.Body).Decode(&msg); err != nil {
		http.Error(w, err.Error(), 400)
		return
	}
	
	// 处理消息...
	_ = msg
	w.WriteHeader(200)
}

func (t *SSETransport) Send(msg *Message) error {
	t.mu.Lock()
	defer t.mu.Unlock()
	
	for writer := range t.writers {
		select {
		case t.eventCh <- msg:
		default:
			// channel 满了，丢弃
		}
	}
	return nil
}
```

### 2. MCP 资源订阅系统

```go
package mcp

import (
	"context"
	"encoding/json"
	"sync"
	"time"
)

// ResourceSubscription 资源订阅
type ResourceSubscription struct {
	URI        string
	Callback   func(context.Context, []byte) error
	LastUpdate time.Time
}

// ResourceServer 资源服务器
type ResourceServer struct {
	mu           sync.RWMutex
	resources    map[string]ResourceData
	subscriptions map[string][]*ResourceSubscription
	pollInterval time.Duration
}

type ResourceData struct {
	URI         string
	Name        string
	MIMEType    string
	Content     []byte
	Version     int64
}

func NewResourceServer(pollInterval time.Duration) *ResourceServer {
	return &ResourceServer{
		resources:     make(map[string]ResourceData),
		subscriptions: make(map[string][]*ResourceSubscription),
		pollInterval:  pollInterval,
	}
}

func (rs *ResourceServer) Register(resource ResourceData) {
	rs.mu.Lock()
	defer rs.mu.Unlock()
	rs.resources[resource.URI] = resource
}

func (rs *ResourceServer) Subscribe(uri string, callback func(context.Context, []byte) error) error {
	rs.mu.Lock()
	defer rs.mu.Unlock()
	
	sub := &ResourceSubscription{
		URI:      uri,
		Callback: callback,
	}
	
	rs.subscriptions[uri] = append(rs.subscriptions[uri], sub)
	return nil
}

func (rs *ResourceServer) StartPolling(ctx context.Context) error {
	ticker := time.NewTicker(rs.pollInterval)
	defer ticker.Close()
	
	for {
		select {
		case <-ticker.C:
			rs.checkUpdates(ctx)
		case <-ctx.Done():
			return ctx.Err()
		}
	}
}

func (rs *ResourceServer) checkUpdates(ctx context.Context) {
	rs.mu.RLock()
	defer rs.mu.RUnlock()
	
	for uri, subs := range rs.subscriptions {
		resource, ok := rs.resources[uri]
		if !ok {
			continue
		}
		
		for _, sub := range subs {
			if sub.LastUpdate.IsZero() || resource.Version > sub.LastUpdate.Unix() {
				go func(s *ResourceSubscription, data []byte) {
					_ = s.Callback(ctx, data)
					s.LastUpdate = time.Now()
				}(sub, resource.Content)
			}
		}
	}
}
```

### 自测题

<details>
<summary>Q1: SSE 传输相比 WebSocket 有什么优劣？MCP 为什么两种都支持？</summary>

**答案**：

| 特性 | SSE | WebSocket |
|------|-----|-----------|
| 方向 | 服务端→客户端（单向） | 双向 |
| 可靠性 | 自动重连 | 需手动处理 |
| 复杂度 | 低（HTTP 标准） | 高（需要协议处理） |
| 适用场景 | 事件推送、日志流 | 实时交互、聊天 |

MCP 支持两种：stdio 用于 CLI，SSE 用于 Web UI 推送，WebSocket 用于实时 Agent 对话。

</details>

<details>
<summary>Q2: ResourceServer 的 checkUpdates 为什么用 goroutine 执行 Callback？</summary>

**答案**：

**原因**：Callback 可能耗时较长（如写文件、调 API），阻塞 update 检查循环会导致轮询间隔变长。

**Trade-off**：
- 并发执行：快速响应，但可能重复触发同一资源的更新
- 串行执行：保证顺序，但延迟高

生产环境用带限流的 goroutine pool 执行 callback。

</details>

<details>
<summary>Q3: MCP 的 Resource 和 Tool 有什么区别？什么场景用哪个？</summary>

**答案**：

| 特性 | Resource | Tool |
|------|---------|------|
| 性质 | **数据**（只读） | **操作**（可写） |
| 调用方式 | Agent 主动读取 | Agent 主动调用 |
| 示例 | 用户画像、广告配置 | 创建 Campaign、暂停广告 |
| 更新通知 | ✅ 支持订阅 | ❌ 不支持 |

广告平台：用户画像用 Resource（Agent 读取），Campaign 管理用 Tool（Agent 操作）。

</details>
