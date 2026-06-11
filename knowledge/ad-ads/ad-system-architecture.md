---

## 第二部分：广告系统概览

### 2.1 系统架构

```
┌─────────────────────────────────────────────────────┐
│                   广告系统架构                        │
│                                                     │
│  用户请求 → 广告服务器 → 竞价引擎 → 广告返回         │
│                                                     │
│  核心组件:                                          │
│  ├── 广告服务器: 接收请求，返回广告                 │
│  ├── 竞价引擎: 决定哪个广告展示                     │
│  ├── 定向系统: 用户画像 + 上下文                    │
│  └── 计费系统: 扣费 + 报表                         │
└─────────────────────────────────────────────────────┘
```

---

### 2.2 Go 实现

```go
package ads

import (
	"fmt"
	"sync"
	"time"
)

type Ad struct {
	ID     string
	Type   string
	CPM    float64
	Target string
}

type RequestContext struct {
	UserID string
	IP     string
	Page   string
	Time   time.Time
}

type AdServer struct {
	ads     map[string]*Ad
	budgets map[string]float64
	mu      sync.Mutex
	count   int
}

func NewAdServer() *AdServer {
	return &AdServer{
		ads:     make(map[string]*Ad),
		budgets: make(map[string]float64),
	}
}

func (s *AdServer) AddAd(ad *Ad) { s.ads[ad.ID] = ad }

func (s *AdServer) Serve(ctx RequestContext) *Ad {
	s.mu.Lock()
	defer s.mu.Unlock()
	
	// 简单逻辑: 返回第一个广告
	if len(s.ads) == 0 { return nil }
	for _, ad := range s.ads {
		s.count++
		return ad
	}
	return nil
}

func main() {
	server := NewAdServer()
	server.AddAd(&Ad{ID: "ad1", Type: "banner", CPM: 5.0, Target: "US"})
	server.AddAd(&Ad{ID: "ad2", Type: "native", CPM: 3.0, Target: "CN"})
	
	ctx := RequestContext{UserID: "u1", IP: "1.2.3.4", Page: "/home"}
	if ad := server.Serve(ctx); ad != nil {
		fmt.Printf("Served: %s (CPM: $%.1f)\n", ad.ID, ad.CPM)
	}
}
```

---

## 自测题

### 问题 1
广告系统的高可用设计要点是什么？

<details>
<summary>查看答案</summary>

1. **多机房部署**：跨地域容灾，单机房故障不影响全局
2. **缓存降级**：竞价失败时返回预缓存广告
3. **限流熔断**：高峰期自动降载，保护核心链路
4. **健康检查**：定时探测各组件状态，自动切换

</details>

### 问题 2
为什么广告系统用 Go 而不是 Java？

<details>
<summary>查看答案</summary>

1. **低延迟**：Go GC 停顿短（<1ms），广告请求要求毫秒级
2. **高并发**：goroutine 轻量（2KB 栈），适合海量并发
3. **部署简单**：单个二进制文件，无 JVM 依赖
4. **网络库**：net/http 标准库性能优异

</details>