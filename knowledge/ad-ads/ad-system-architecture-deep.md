4. 广告轮换
</details>

---

### 广告系统架构的 Go 实现

```go
package adsarchitecture

import (
	"fmt"
	"sync"
	"time"
)

type Service interface {
	Name() string
	Health() bool
	HandleRequest(req Request) Response
}

type Request struct {
	UserID    string
	IP        string
	PageURL   string
	AdSlots   []Slot
	Timestamp time.Time
}

type Response struct {
	Ads    []Ad
	Events []Event
}

type Ad struct {
	ID   string
	Type string
	CPM  float64
}

type Slot struct {
	ID       string
	Width    int
	Height   int
	PageType string
}

type Event struct {
	Type      string
	UserID    string
	AdID      string
	Timestamp time.Time
}

type AdServer struct {
	services map[string]Service
	events   []Event
	mu       sync.Mutex
}

func NewAdServer() *AdServer {
	return &AdServer{
		services: make(map[string]Service),
		events:   make([]Event, 0),
	}
}

func (s *AdServer) Register(name string, svc Service) { s.services[name] = svc }

func (s *AdServer) ServeAd(req Request) Response {
	s.mu.Lock()
	defer s.mu.Unlock()
	
	// 1. 记录曝光事件
	events := make([]Event, 0)
	for _, slot := range req.AdSlots {
		events = append(events, Event{Type: "impression", UserID: req.UserID, AdID: slot.ID, Timestamp: req.Timestamp})
	}
	s.events = append(s.events, events...)
	
	return Response{Ads: []Ad{{ID: "ad_001", Type: "banner", CPM: 5.0}}, Events: events}
}

func (s *AdServer) GetMetrics() map[string]int {
	s.mu.Lock()
	defer s.mu.Unlock()
	return map[string]int{
		"total_impressions": len(s.events),
		"total_requests":    len(s.events),
	}
}

func main() {
	server := NewAdServer()
	req := Request{
		UserID: "user1", PageURL: "/home",
		AdSlots: []Slot{{ID: "slot_1", Width: 728, Height: 90}},
		Timestamp: time.Now(),
	}
	resp := server.ServeAd(req)
	fmt.Printf("Served %d ads\n", len(resp.Ads))
	fmt.Printf("Metrics: %v\n", server.GetMetrics())
}
```

---

## 自测题

### 问题 1
广告系统的 RTB（实时竞价）架构中，DSP/SSP/DSP 各自负责什么？

<details>
<summary>查看答案</summary>

1. **DSP（需求方平台）**：广告主端，控制出价和预算
2. **SSP（供应方平台）**：媒体端，管理广告位和收益
3. **Ad Exchange**：交易平台，撮合买卖双方
4. **Go 实现**：用 channel 做消息传递，各组件解耦

</details>

### 问题 2
Go 的 struct 组合如何体现广告系统的微服务架构？

<details>
<summary>查看答案</summary>

1. **AdServer 组合**了多个 Service（注册表模式）
2. 每个 Service 独立开发、测试、部署
3. Service 接口定义了服务契约，实现可替换
4. 与 Java 的继承相比，组合更灵活、更易于测试

</details>