# 广告系统竞价算法深度解析

> 深入广告竞价算法：广义第二价格拍卖、VCG机制、在线学习算法。
> 包含真实生产环境竞价算法实现。
> 适用对象：广告算法工程师、拍卖机制研究者

---

## 1. 拍卖机制

### 1.1 常见拍卖类型

```
拍卖机制对比：

┌────────────────┬───────────────────┬──────────────────────┐
│ 拍卖类型       │ 中标价格          │ 特点                 │
├────────────────┼───────────────────┼──────────────────────┤
│ 第一价格拍卖   │ 出价本身          │ 简单但策略复杂       │
│ 第二价格拍卖   │ 第二名出价        │ 激励真实报价         │
│ VCG拍卖        │ 外部效应损失      │ 社会福利最优         │
└────────────────┴───────────────────┴──────────────────────┘
```

### 1.2 Go 实现第二价格拍卖

```go
// auction.go

package ad

import (
    "sort"
)

type Bid struct {
    BidderID string
    Price    float64
    Quality  float64
}

type AuctionResult struct {
    WinnerID  string
    WinPrice  float64
    Score     float64
}

type SecondPriceAuction struct{}

func NewSecondPriceAuction() *SecondPriceAuction {
    return &SecondPriceAuction{}
}

func (spa *SecondPriceAuction) Run(bids []Bid) *AuctionResult {
    // 按质量分×出价排序
    sort.Slice(bids, func(i, j int) bool {
        scoreI := bids[i].Price * bids[i].Quality
        scoreJ := bids[j].Price * bids[j].Quality
        return scoreI > scoreJ
    })
    
    if len(bids) == 0 {
        return nil
    }
    
    winner := bids[0]
    
    // 第二价格：第二名出价×质量分
    winPrice := winner.Price
    if len(bids) > 1 {
        winPrice = bids[1].Price * (winner.Quality / bids[1].Quality)
    }
    
    return &AuctionResult{
        WinnerID: winner.BidderID,
        WinPrice: winPrice,
        Score:    winner.Price * winner.Quality,
    }
}
```

---

## 2. VCG 拍卖

### 2.1 原理

```
VCG (Vickrey-Clarke-Groves) 拍卖：

核心思想：每个中标者支付其对其他参与者造成的外部效应

计算公式：
Payment_i = (Social_Welfare_without_i) - (Social_Welfare_others)
```

### 2.2 Go 实现VCG

```go
// vcg_auction.go

package ad

type VCGAuction struct{}

func NewVCGAuction() *VCGAuction {
    return &VCGAuction{}
}

func (v *VCGAuction) Run(bids []Bid) []*AuctionResult {
    results := make([]*AuctionResult, len(bids))
    
    for i := range bids {
        // 计算不包含当前投标人的社会福利
        others := removeBid(bids, i)
        socialWelfareWithout := calculateSocialWelfare(others)
        
        // 计算其他投标人的最优分配
        othersResult := runOptimalAuction(others)
        othersWelfare := calculateOthersWelfare(othersResult)
        
        // VCG支付
        payment := socialWelfareWithout - othersWelfare
        
        results[i] = &AuctionResult{
            WinnerID: bids[i].BidderID,
            WinPrice: payment,
            Score:    bids[i].Price * bids[i].Quality,
        }
    }
    
    return results
}

func removeBid(bids []Bid, index int) []Bid {
    result := make([]Bid, 0, len(bids)-1)
    for i, bid := range bids {
        if i != index {
            result = append(result, bid)
        }
    }
    return result
}
```

---

## 3. 在线学习算法

### 3.1 上下文多臂老虎机

```
Contextual Bandit 算法：

1. 每一步：
   ├── 观察上下文（用户特征、场景特征）
   ├── 选择动作（出价策略）
   └── 获得奖励（转化/点击）

2. 目标：最大化长期累积奖励
```

### 3.2 Go 实现LinUCB

```go
// linucb.go

package ad

import (
    "math"
    "math/rand"
)

type LinUCB struct {
    arms       []Arm
    d          int
    alpha      float64
    A          [][]float64
    b          []float64
}

type Arm struct {
    ID        string
    Parameters []float64
}

func NewLinUCB(d int, alpha float64) *LinUCB {
    return &LinUCB{
        d:     d,
        alpha: alpha,
        A:     makeIdentityMatrix(d),
        b:     make([]float64, d),
    }
}

func (lb *LinUCB) ChooseArm(context []float64) string {
    bestScore := -math.MaxFloat64
    bestArm := ""
    
    for i := range lb.arms {
        // 计算UCB分数
        theta := multiplyInverse(lb.A, lb.b)
        mean := dotProduct(theta, context)
        uncertainty := lb.alpha * sqrtQuadraticForm(lb.A, context)
        
        score := mean + uncertainty
        if score > bestScore {
            bestScore = score
            bestArm = lb.arms[i].ID
        }
    }
    
    return bestArm
}

func (lb *LinUCB) Update(armID string, context []float64, reward float64) {
    // 更新A和b
    for i := range lb.A {
        lb.A[i][i] += context[i] * context[i]
    }
    for i := range lb.b {
        lb.b[i] += reward * context[i]
    }
}
```

---

## 4. 总结

### 4.1 核心算法对比

| 算法 | 特点 | 适用场景 |
|------|------|----------|
| 第二价格拍卖 | 激励真实报价 | 通用场景 |
| VCG拍卖 | 社会福利最优 | 多物品拍卖 |
| LinUCB | 探索利用平衡 | 动态出价 |

### 4.2 最佳实践

- [ ] 选择合适的拍卖机制
- [ ] 平衡探索与利用
- [ ] 实时监控拍卖效果
- [ ] 持续优化算法参数

---

*最后更新：2026-08-11*
*作者：Ryan*
