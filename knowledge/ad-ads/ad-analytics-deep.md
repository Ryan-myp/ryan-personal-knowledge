1. Top of Search (TOS) — 搜索结果顶部 (转化率最高)
2. Product Pages (PDP) — 商品页面 (转化率中等)
3. Rest of Search (ROS) — 搜索结果其他位置 (转化率最低)
</details>

---

### 广告分析的 Go 实现

```go
package adanalytics

import (
	"fmt"
	"sync"
)

type AdAccount struct {
	ID     string
	Name   string
	Status string
}

type Campaign struct {
	ID          string
	AccountID   string
	Name        string
	Status      string
	DailyBudget float64
	Objective   string
}

type AdGroup struct {
	ID       string
	Campaign string
	Name     string
	Bid      float64
}

type Ad struct {
	ID        string
	AdGroupID string
	Name      string
	Status    string
	CPA       float64
	CTR       float64
}

type AnalyticsEngine struct {
	accounts  map[string]*AdAccount
	campaigns map[string]*Campaign
	ads       map[string]*Ad
	mu        sync.RWMutex
}

func NewAnalyticsEngine() *AnalyticsEngine {
	return &AnalyticsEngine{
		accounts:  make(map[string]*AdAccount),
		campaigns: make(map[string]*Campaign),
		ads:       make(map[string]*Ad),
	}
}

func (a *AnalyticsEngine) AddAccount(acc *AdAccount) { a.accounts[acc.ID] = acc }
func (a *AnalyticsEngine) AddCampaign(cp *Campaign)   { a.campaigns[cp.ID] = cp }
func (a *AnalyticsEngine) AddAd(ad *Ad)               { a.ads[ad.ID] = ad }

func (a *AnalyticsEngine) GetPerformance(accountID string) (float64, float64, float64) {
	a.mu.RLock()
	defer a.mu.RUnlock()
	
	var impressions, clicks, conversions, spend, revenue float64
	for _, cp := range a.campaigns {
		if cp.AccountID == accountID {
			for _, ad := range a.ads {
				if ad.CPA > 0 { conversions++ }
				if ad.CTR > 0 { clicks += ad.CTR * 100 }
				spend += ad.CPA * conversions
				revenue += conversions * 100
			}
		}
	}
	ctr := 0.0
	if impressions > 0 { ctr = clicks / impressions }
	cpa := 0.0
	if conversions > 0 { cpa = spend / conversions }
	roas := 0.0
	if spend > 0 { roas = revenue / spend }
	return ctr, cpa, roas
}

func main() {
	engine := NewAnalyticsEngine()
	engine.AddAccount(&AdAccount{ID: "acc1", Name: "My Shop"})
	engine.AddCampaign(&Campaign{ID: "cp1", AccountID: "acc1", Name: "Summer Sale", DailyBudget: 100})
	engine.AddAd(&Ad{ID: "ad1", AdGroupID: "ag1", CPA: 5.0, CTR: 0.03})
	ctr, cpa, roas := engine.GetPerformance("acc1")
	fmt.Printf("CTR: %.2f%%, CPA: $%.2f, ROAS: %.2f\n", ctr*100, cpa, roas)
}
```

---

## 自测题

### 问题 1
A/B 测试中，为什么需要至少 95% 的置信度（p-value < 0.05）才算显著？

<details>
<summary>查看答案</summary>

1. **第一类错误（假阳性）**：p-value < 0.05 意味着 5% 的概率误判
2. **业务风险**：广告平台决策涉及大量预算，5% 风险太高
3. **多重比较**：如果同时测试多个变体，需要 Bonferroni 校正
4. **样本量**：置信度固定时，样本量越大检测能力越强

</details>

### 问题 2
Go 的 RWMutex 在 AnalyticsEngine 中为什么比 Mutex 更合适？

<details>
<summary>查看答案</summary>

1. **读多写少**：广告账户配置变动少，性能查询频繁
2. **ReadLock**：多个 goroutine 可以同时读取数据
3. **性能**：读操作不阻塞，写操作独占
4. **安全**：Write 操作时读操作会被阻塞，保证数据一致性

</details>