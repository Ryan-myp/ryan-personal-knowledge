5. 不包含违规词 (cheap/best price 等)
</details>

---

### 广告系统的 Go 实现

```go
package adsystem

import (
	"fmt"
	"sync"
	"time"
)

type AdType string
const (
	AdTypeSearch   AdType = "SEARCH"
	AdTypeDisplay  AdType = "DISPLAY"
	AdTypeVideo    AdType = "VIDEO"
	AdTypeShopping AdType = "SHOPPING"
)

type Ad struct {
	ID       string
	Type     AdType
	Campaign string
	Status   string
	Bid      float64
	Target   string
}

type Targeting struct {
	UserIDs     []string
	Interests   []string
	Geos        []string
	Demographics map[string]string
}

type AdServer struct {
	ads      map[string]*Ad
	targets  map[string]*Targeting
	budgets  map[string]float64
	mu       sync.RWMutex
	serveCnt int
}

func NewAdServer() *AdServer {
	return &AdServer{
		ads:     make(map[string]*Ad),
		targets: make(map[string]*Targeting),
		budgets: make(map[string]float64),
	}
}

func (s *AdServer) AddAd(ad *Ad) { s.ads[ad.ID] = ad }
func (s *AdServer) SetTargeting(adID string, t *Targeting) { s.targets[adID] = t }

func (s *AdServer) ServeAd(adID, userID string) (bool, float64) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	
	ad, ok := s.ads[adID]
	if !ok { return false, 0 }
	if ad.Status != "ACTIVE" { return false, 0 }
	
	cost := ad.Bid * 0.01 // 简化:CPC
	s.serveCnt++
	return true, cost
}

func (s *AdServer) GetStats() int {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.serveCnt
}

func main() {
	server := NewAdServer()
	server.AddAd(&Ad{ID: "ad1", Type: AdTypeSearch, Bid: 1.5, Status: "ACTIVE"})
	server.AddAd(&Ad{ID: "ad2", Type: AdTypeDisplay, Bid: 0.8, Status: "ACTIVE"})
	server.SetTargeting("ad1", &Targeting{Geos: []string{"US"}})
	
	ok, cost := server.ServeAd("ad1", "user123")
	fmt.Printf("Served: %v, Cost: $%.4f\n", ok, cost)
	fmt.Printf("Total served: %d\n", server.GetStats())
}
```

---

## 自测题

### 问题 1
广告系统在什么情况下使用精确匹配 vs 模糊匹配？

<details>
<summary>查看答案</summary>

1. **精确匹配**：转化率要求高、预算有限、品牌词保护
2. **模糊匹配**：品牌曝光、探索新关键词、预算充足
3. **Go 实现**：精确用 map 查找 O(1)，模糊用字符串匹配 O(n)
4. **最佳实践**：初期用模糊匹配扩大覆盖，后期用精确匹配优化 ROI

</details>

### 问题 2
Go 中怎么实现广告系统的防重放和去重？

<details>
<summary>查看答案</summary>

1. **Request ID**：每次请求带唯一 ID，用 map 记录
2. **Bloom Filter**：概率型去重，内存效率高
3. **Redis SET**：分布式去重，适合集群部署
4. **时间窗口**：相同用户+相同广告在限定时间内只展示一次

</details>