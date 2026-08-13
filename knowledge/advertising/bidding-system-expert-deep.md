# 广告竞价系统 - 资深专家深度实现

## 一、系统架构

### 1.1 整体架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           广告竞价系统架构                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐               │
│  │   广告主端    │────▶│   竞价引擎    │────▶│   投放平台    │               │
│  │  (Ad Server) │     │  (Bidding    │     │ (DSP)       │               │
│  │              │     │   Engine)    │     │             │               │
│  └──────────────┘     └──────────────┘     └──────────────┘               │
│                                         │                                  │
│                                         ▼                                  │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐               │
│  │   媒体端     │←────│   RTB市场    │←────│   SSP       │               │
│  │(Publisher)  │     │  (RTB        │     │ (Supply     │               │
│  │              │     │   Exchange)  │     │  Side)      │               │
│  └──────────────┘     └──────────────┘     └──────────────┘               │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 核心组件

| 组件 | 职责 | 技术选型 |
|------|------|----------|
| 竞价引擎 | 实时竞价决策 | Go + Redis |
| 出价计算 | pCTR/pCVR预估 | DeepFM模型 |
| 频控模块 | 频次控制 | Redis ZSet |
| 归因模块 | 转化归因 | 时间衰减模型 |
| 监控模块 | 实时指标 | Prometheus + Grafana |

---

## 二、竞价引擎实现

### 2.1 核心流程

```go
package bidding

import (
    "context"
    "time"
    "github.com/yourcompany/bidding/core"
)

// BidRequest 竞价请求
type BidRequest struct {
    ImpressionID string  `json:"imp_id"`
    UserID       string  `json:"user_id"`
    AdSlotID     string  `json:"ad_slot_id"`
    Budget       float64 `json:"budget"`
    Timestamp    int64   `json:"timestamp"`
}

// BidResponse 竞价响应
type BidResponse struct {
    ImpressionID string  `json:"imp_id"`
    BidPrice     float64 `json:"bid_price"`
    AdID         string  `json:"ad_id"`
    TTL          int     `json:"ttl"`
}

// BiddingEngine 竞价引擎
type BiddingEngine struct {
    ctrModel    *CTRModel
    cvrModel    *CVRModel
    freqCtrl    *FrequencyController
    budgetMgr   *BudgetManager
    redis       *RedisClient
}

// HandleBid 处理竞价请求
func (e *BiddingEngine) HandleBid(ctx context.Context, req *BidRequest) (*BidResponse, error) {
    // 1. 频控检查
    if ok := e.freqCtrl.Check(req.UserID, req.AdSlotID); !ok {
        return &BidResponse{ImpressionID: req.ImpressionID}, nil
    }

    // 2. 预算检查
    if !e.budgetMgr.CheckBudget(req.UserID, req.Budget) {
        return &BidResponse{ImpressionID: req.ImpressionID}, nil
    }

    // 3. 出价计算
    bidPrice, err := e.calculateBid(ctx, req)
    if err != nil {
        return nil, err
    }

    // 4. 选择广告
    adID := e.selectAd(req.AdSlotID, bidPrice)

    return &BidResponse{
        ImpressionID: req.ImpressionID,
        BidPrice:     bidPrice,
        AdID:         adID,
        TTL:          2000, // 2秒TTL
    }, nil
}

// calculateBid 计算出价
func (e *BiddingEngine) calculateBid(ctx context.Context, req *BidRequest) (float64, error) {
    // pCTR预测
    ctr, err := e.ctrModel.Predict(ctx, req.UserID, req.AdSlotID)
    if err != nil {
        return 0, err
    }

    // pCVR预测
    cvr, err := e.cvrModel.Predict(ctx, req.UserID, req.AdSlotID)
    if err != nil {
        return 0, err
    }

    // 出价 = target CPA * pCTR * pCVR
    targetCPA := 50.0
    bidPrice := targetCPA * ctr * cvr

    // 添加竞拍策略因子
    bidPrice *= e.applyBidStrategy(req)

    return bidPrice, nil
}

// applyBidStrategy 应用出价策略
func (e *BiddingEngine) applyBidStrategy(req *BidRequest) float64 {
    // OCPM策略：根据转化率动态调整
    // 转化率高则提高出价，反之降低
    conversionRate := req.Budget / 1000.0
    if conversionRate > 0.05 {
        return 1.2 // 提高20%出价
    }
    return 0.8 // 降低20%出价
}
```

### 2.2 性能优化

```go
// 并行预测优化
func (e *BiddingEngine) calculateBidParallel(ctx context.Context, req *BidRequest) (float64, error) {
    // 使用goroutine并行预测pCTR和pCVR
    var ctr, cvr float64
    var ctrErr, cvrErr error
    
    var wg sync.WaitGroup
    wg.Add(2)
    
    go func() {
        defer wg.Done()
        ctr, ctrErr = e.ctrModel.Predict(ctx, req.UserID, req.AdSlotID)
    }()
    
    go func() {
        defer wg.Done()
        cvr, cvrErr = e.cvrModel.Predict(ctx, req.UserID, req.AdSlotID)
    }()
    
    wg.Wait()
    
    if ctrErr != nil || cvrErr != nil {
        return 0, errors.New("prediction failed")
    }
    
    targetCPA := 50.0
    bidPrice := targetCPA * ctr * cvr
    bidPrice *= e.applyBidStrategy(req)
    
    return bidPrice, nil
}
```

---

## 三、出价策略

### 3.1 OCPM出价

```python
class OCPMBidder:
    """OCPM出价策略"""
    
    def __init__(self, target_cpa: float, beta: float = 0.5):
        self.target_cpa = target_cpa
        self.beta = beta  # 风险偏好系数
    
    def calculate_bid(self, pctr: float, pcvr: float, conversion_rate: float) -> float:
        """
        出价公式：
        bid = target_cpa * pctr * pcvr * (1 + beta * (cvr - target_cvr))
        
        其中：
        - cvr = 历史转化率
        - target_cvr = target_cpa / eCPM
        """
        ecpm = self.target_cpa / (pctr * pcvr)
        target_cvr = self.target_cpa / ecpm
        
        # 偏差修正
        deviation = conversion_rate - target_cvr
        adjustment = 1 + self.beta * deviation
        
        bid = self.target_cpa * pctr * pcvr * adjustment
        return max(0.01, bid)  # 最低出价0.01元
```

### 3.2 强化学习出价

```python
class DQNBidder:
    """DQN强化学习出价"""
    
    def __init__(self, state_dim: int, action_dim: int):
        self.q_network = self._build_q_network(state_dim, action_dim)
        self.target_network = self._build_target_network(state_dim, action_dim)
        self.optimizer = Adam(self.q_network.parameters(), lr=0.001)
        self.memory = ReplayBuffer(capacity=10000)
    
    def select_action(self, state: np.ndarray, epsilon: float = 0.1) -> int:
        """Epsilon-greedy策略选择动作"""
        if random.random() < epsilon:
            return random.randint(0, self.action_dim - 1)
        
        with torch.no_grad():
            q_values = self.q_network(state)
            return torch.argmax(q_values).item()
    
    def train_step(self, batch: tuple):
        """DQN训练步骤"""
        states, actions, rewards, next_states, dones = batch
        
        # 计算目标Q值
        with torch.no_grad():
            target_q = rewards + (1 - dones) * 0.99 * torch.max(
                self.target_network(next_states), dim=1
            ).values
        
        # 计算当前Q值
        current_q = self.q_network(states).gather(1, actions.unsqueeze(1)).squeeze(1)
        
        # 计算损失并更新
        loss = F.mse_loss(current_q, target_q)
        self.optimizer.zero_grad()
        loss.backward()
        self.optimizer.step()
        
        return loss.item()
```

---

## 四、频控系统

### 4.1 固定频控

```go
package frequency

import (
    "github.com/go-redis/redis/v8"
    "time"
)

// FixedFrequencyController 固定频控
type FixedFrequencyController struct {
    redis *redis.Client
    limit int  // 最大展示次数
}

func (c *FixedFrequencyController) Check(userID, adID string) bool {
    key := fmt.Sprintf("freq:%s:%s", userID, adID)
    
    // 使用Redis INCR原子操作
    count := c.redis.Incr(context.Background(), key)
    
    // 设置过期时间
    if count == 1 {
        c.redis.Expire(context.Background(), key, 24*time.Hour)
    }
    
    return count <= int64(c.limit)
}
```

### 4.2 滑动窗口频控

```go
// SlidingWindowFrequencyController 滑动窗口频控
type SlidingWindowFrequencyController struct {
    redis *redis.Client
    window time.Duration  // 时间窗口
    limit  int            // 最大次数
}

func (c *SlidingWindowFrequencyController) Check(userID, adID string) bool {
    key := fmt.Sprintf("sw_freq:%s:%s", userID, adID)
    now := time.Now()
    
    // 移除过期数据
    c.redis.ZRemRangeByScore(context.Background(), key, 0, now.Add(-c.window).Unix())
    
    // 检查当前次数
    count := c.redis.ZCard(context.Background(), key)
    
    if count >= int64(c.limit) {
        return false
    }
    
    // 添加当前时间戳
    c.redis.ZAdd(context.Background(), key, redis.Z{
        Score:  float64(now.Unix()),
        Member: fmt.Sprintf("%d_%s", now.UnixNano(), uuid.New().String()),
    })
    
    // 设置过期时间
    c.redis.Expire(context.Background(), key, c.window)
    
    return true
}
```

---

## 五、归因模型

### 5.1 时间衰减归因

```python
class TimeDecayAttribution:
    """时间衰减归因模型"""
    
    def __init__(self, half_life: float = 1.0):
        self.half_life = half_life  # 半衰期（天）
    
    def calculate_weight(self, hours_since_conversion: int) -> float:
        """计算时间衰减权重"""
        days = hours_since_conversion / 24
        weight = 0.5 ** (days / self.half_life)
        return weight
    
    def assign_credit(self, touchpoints: list, conversion_time: int) -> dict:
        """
        分配转化归因
        
        Args:
            touchpoints: 触点列表 [{'time': timestamp, 'channel': str}, ...]
            conversion_time: 转化时间戳
        
        Returns:
            各渠道归因权重
        """
        weights = {}
        for tp in touchpoints:
            hours = (conversion_time - tp['time']) / 3600
            weight = self.calculate_weight(hours)
            channel = tp['channel']
            weights[channel] = weights.get(channel, 0) + weight
        
        # 归一化
        total = sum(weights.values())
        if total > 0:
            for channel in weights:
                weights[channel] /= total
        
        return weights
```

### 5.2 Shapley值归因

```python
class ShapleyAttribution:
    """Shapley值归因模型"""
    
    def __init__(self, model):
        self.model = model
    
    def calculate_shapley(self, channels: list, conversion_data: dict) -> dict:
        """
        计算Shapley值
        
        Args:
            channels: 渠道列表
            conversion_data: 转化数据
        
        Returns:
            各渠道的Shapley值
        """
        n = len(channels)
        shapley_values = {ch: 0 for ch in channels}
        
        # 遍历所有子集
        for k in range(n):
            for subset in itertools.combinations(channels, k):
                # 计算边际贡献
                marginal = self._marginal_contribution(
                    subset, channels, conversion_data
                )
                
                # Shapley值公式
                weight = math.factorial(k) * math.factorial(n - k - 1) / math.factorial(n)
                for ch in channels:
                    if ch not in subset:
                        shapley_values[ch] += weight * marginal
        
        # 归一化
        total = sum(shapley_values.values())
        if total > 0:
            for ch in shapley_values:
                shapley_values[ch] /= total
        
        return shapley_values
    
    def _marginal_contribution(self, subset: tuple, channels: list, data: dict) -> float:
        """计算边际贡献"""
        subset_set = set(subset)
        remaining = [ch for ch in channels if ch not in subset_set]
        
        # 包含subset的转化率
        conversion_with = self._get_conversion_rate(subset_set, data)
        
        # 不包含subset的转化率
        conversion_without = self._get_conversion_rate(set(), data)
        
        return conversion_with - conversion_without
```

---

## 六、监控体系

### 6.1 核心指标

```go
package metrics

import (
    "github.com/prometheus/client_golang/prometheus"
)

// 竞价相关指标
var (
    bidRequestCount = prometheus.NewCounter(
        prometheus.CounterOpts{
            Name: "bidding_request_total",
            Help: "Total bid requests",
        },
    )
    
    bidLatency = prometheus.NewHistogram(
        prometheus.HistogramOpts{
            Name:    "bidding_latency_ms",
            Help:    "Bid latency in milliseconds",
            Buckets: []float64{1, 5, 10, 20, 50, 100, 200, 500},
        },
    )
    
    bidSuccessRate = prometheus.NewGauge(
        prometheus.GaugeOpts{
            Name: "bidding_success_rate",
            Help: "Bid success rate",
        },
    )
    
    ctrPredictionError = prometheus.NewHistogram(
        prometheus.HistogramOpts{
            Name:    "ctr_prediction_error",
            Help:    "CTR prediction error distribution",
            Buckets: []float64{0.01, 0.05, 0.1, 0.2, 0.5},
        },
    )
)

func init() {
    prometheus.MustRegister(bidRequestCount)
    prometheus.MustRegister(bidLatency)
    prometheus.MustRegister(bidSuccessRate)
    prometheus.MustRegister(ctrPredictionError)
}
```

### 6.2 告警规则

```yaml
# alerting_rules.yml
groups:
  - name: bidding
    rules:
      - alert: HighBidLatency
        expr: bidding_latency_ms_p99 > 100
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "竞价延迟过高"
          description: "P99延迟超过100ms，当前值: {{ $value }}ms"
      
      - alert: LowSuccessRate
        expr: bidding_success_rate < 0.95
        for: 10m
        labels:
          severity: critical
        annotations:
          summary: "竞价成功率过低"
          description: "成功率低于95%，当前值: {{ $value }}"
      
      - alert: CTRPredictionDrift
        expr: abs(ctr_prediction_error_mean) > 0.1
        for: 30m
        labels:
          severity: warning
        annotations:
          summary: "CTR预测偏差过大"
          description: "预测误差均值: {{ $value }}"
```

---

## 七、生产实践

### 7.1 性能调优

```go
// 连接池配置
redisOpts := &redis.Options{
    Addr:         "redis:6379",
    Username:     "your_username",
    Password:     "your_password",
    DB:           0,
    MaxActive:    100,     // 最大连接数
    MaxIdle:      10,      // 最大空闲连接
    IdleTimeout:  240 * time.Second,
    DialTimeout:  100 * time.Millisecond,
    ReadTimeout:  50 * time.Millisecond,
    WriteTimeout: 50 * time.Millisecond,
}

// 请求超时控制
ctx, cancel := context.WithTimeout(context.Background(), 20*time.Millisecond)
defer cancel()

// 熔断器配置
breaker := resilience.NewBreaker(resilience.BreakerConfig{
    Timeout:      10 * time.Second,
    MaxErrors:    5,
    HalfOpenOps:  1,
})
```

### 7.2 故障排查

```go
// 常见故障及解决方案

// 1. Redis连接超时
// 现象：bid_latency_p99突增
// 原因：Redis负载过高或网络抖动
// 解决：增加Redis实例，启用本地缓存

// 2. 出价计算慢
// 现象：bid_latency高，success_rate低
// 原因：模型推理慢
// 解决：启用模型缓存，优化特征工程

// 3. 频控计数错误
// 现象：部分用户被重复曝光
// 原因：Redis集群分裂
// 解决：使用Redis Cluster，增加重试机制
```

---

## 八、自测题

### 8.1 基础题

1. 解释OCPM出价公式中各参数的含义
2. 滑动窗口频控 vs 固定频控，各有什么优缺点？
3. 时间衰减归因模型中，半衰期如何影响归因结果？

### 8.2 进阶题

1. 设计一个支持多渠道归因的系统，要求：
   - 支持时间衰减、位置衰减、Shapley值等多种模型
   - 支持实时归因和批量归因
   - 归因结果可解释、可追溯

2. 竞价系统出现以下问题，如何排查？
   - p99延迟从50ms飙升到200ms
   - 成功率从99%下降到90%
   - 部分广告主反馈曝光量下降50%

3. 设计一个A/B测试框架，用于评估新出价策略的效果：
   - 如何划分实验组和对照组？
   - 需要监控哪些指标？
   - 如何判断实验是否显著？

---

## 参考文档

- [Bidding Engine Implementation](./bidding-engine-production-deep.md)
- [Frequency Control Deep Implementation](./frequency-control-deep.md)
- [Attribution Model Deep Implementation](./attribution-model-deep.md)
