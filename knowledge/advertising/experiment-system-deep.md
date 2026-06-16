# 广告实验系统深度：分流/正交/统计/在线实验

> 从 0 到 1 设计一个广告实验系统，覆盖分流/正交/统计/在线实验

---

## 第一部分：实验系统为什么重要？

### 类比理解实验系统

```
实验系统 = 医院的临床试验

新药上市前：
→ 对照组：吃安慰剂
→ 实验组：吃新药
→ 对比两组效果
→ 统计显著性
→ 决定新药是否上市

广告实验：
→ 对照组：老出价策略
→ 实验组：新出价策略
→ 对比两组 eCPM/CTR/CVR
→ 统计显著性
→ 决定新策略是否全量
```

### 实验系统的核心挑战

```
1. 分流一致性：
   → 同一个用户必须始终在同一组
   → 同一个广告必须始终在同一组

2. 正交性：
   → 实验 A 和实验 B 不能互相干扰
   → 用户不能同时出现在两个冲突的实验中

3. 样本均匀：
   → 每组样本分布要一致
   → 不能实验组都是高价值用户

4. 实时统计：
   → 实验结果要实时可见
   → 不能等实验结束后才能看数据

5. 快速迭代：
   → 实验可以秒级开启/关闭
   → 实验参数可以动态调整
```

---

## 第二部分：分流设计

### 2.1 分流方案选择

| 方案 | 优点 | 缺点 | 适用场景 |
|------|------|------|---------|
| **Hash 分流** | 一致性高，实现简单 | 扩容困难 | **推荐** |
| **配置分流** | 灵活，可随时调整 | 一致性难保证 | 小流量实验 |
| **数据库分流** | 持久化，可查询 | 性能差 | 低频实验 |

**推荐方案：Hash 分流 + 配置管理**

```
核心思路：
1. 用户 ID 做 Hash，映射到 [0, 1000) 区间
2. 根据实验配置，确定用户落在哪个组
3. 实验配置存储在 Redis/MySQL，支持动态调整
4. 本地缓存实验配置，减少远程查询
```

### 2.2 Hash 分流实现

```go
package experiment

import (
    "fmt"
    "hash/fnv"
    "sync"
)

// Bucket 分流桶
type Bucket struct {
    ID     string  // 分流桶 ID
    Weight float64 // 权重（0-1000）
    Name   string  // 组名（control/experiment_a/experiment_b）
}

// Experiment 实验配置
type Experiment struct {
    ID        string    `json:"id"`
    Name      string    `json:"name"`
    Enabled   bool      `json:"enabled"`
    Buckets   []Bucket  `json:"buckets"`
    StartTime string    `json:"start_time"`
    EndTime   string    `json:"end_time"`
}

// Allocator 分流分配器
type Allocator struct {
    experiments map[string]*Experiment
    mu          sync.RWMutex
}

// NewAllocator 创建分流分配器
func NewAllocator() *Allocator {
    return &Allocator{
        experiments: make(map[string]*Experiment),
    }
}

// RegisterExperiment 注册实验
func (a *Allocator) RegisterExperiment(exp *Experiment) {
    a.mu.Lock()
    defer a.mu.Unlock()
    
    a.experiments[exp.ID] = exp
}

// Assign 分配用户到实验组
func (a *Allocator) Assign(userID string, experimentID string) (string, error) {
    a.mu.RLock()
    exp, ok := a.experiments[experimentID]
    a.mu.RUnlock()
    
    if !ok {
        return "", fmt.Errorf("experiment %s not found", experimentID)
    }
    
    if !exp.Enabled {
        return "control", nil
    }
    
    // 1. 计算用户 ID 的 Hash 值
    bucket := a.hashUserID(userID, len(exp.Buckets))
    
    // 2. 根据权重分配
    cumulativeWeight := 0.0
    for _, b := range exp.Buckets {
        cumulativeWeight += b.Weight
        if float64(bucket) < cumulativeWeight*10 { // bucket 范围 [0, 1000)
            return b.Name, nil
        }
    }
    
    // 默认返回对照组
    return "control", nil
}

// hashUserID 对用户 ID 做 Hash，返回 [0, numBuckets) 范围内的值
func (a *Allocator) hashUserID(userID string, numBuckets int) int {
    h := fnv.New32a()
    h.Write([]byte(userID))
    hash := h.Sum32()
    
    // 映射到 [0, numBuckets)
    return int(hash % uint32(numBuckets))
}

// GetExperiment 获取实验配置
func (a *Allocator) GetExperiment(id string) (*Experiment, error) {
    a.mu.RLock()
    defer a.mu.RUnlock()
    
    exp, ok := a.experiments[id]
    if !ok {
        return nil, fmt.Errorf("experiment %s not found", id)
    }
    
    return exp, nil
}
```

### 2.3 流量比例配置

```go
// 示例：A/B 测试，50% 实验组
experimentA := &Experiment{
    ID:      "bidding_strategy_v2",
    Name:    "oCPM v2 vs v1",
    Enabled: true,
    Buckets: []Bucket{
        {ID: "control", Weight: 500, Name: "control"},     // 50%
        {ID: "experiment", Weight: 500, Name: "experiment"}, // 50%
    },
    StartTime: "2024-01-01T00:00:00Z",
    EndTime:   "2024-02-01T00:00:00Z",
}

// 示例：梯度实验，10%/20%/30%/40%
gradientExp := &Experiment{
    ID:      "bid_increase_ratio",
    Name:    "出价增幅梯度实验",
    Enabled: true,
    Buckets: []Bucket{
        {ID: "control", Weight: 400, Name: "0%"},      // 40%
        {ID: "bucket_1", Weight: 200, Name: "10%"},    // 20%
        {ID: "bucket_2", Weight: 200, Name: "20%"},    // 20%
        {ID: "bucket_3", Weight: 100, Name: "30%"},    // 10%
        {ID: "bucket_4", Weight: 100, Name: "40%"},    // 10%
    },
    StartTime: "2024-01-01T00:00:00Z",
    EndTime:   "2024-02-01T00:00:00Z",
}
```

---

## 第三部分：正交设计

### 3.1 什么是正交？

```
正交 = 实验之间互不干扰

例子：
实验 A：出价策略（50% 实验组）
实验 B：排序模型（50% 实验组）

非正交（有问题）：
→ 用户 123 在实验 A 的实验组
→ 用户 123 也在实验 B 的实验组
→ 两组实验同时生效，无法区分是哪个实验的效果

正交（正确）：
→ 用户 123 在实验 A 的实验组（50%）
→ 用户 123 在实验 B 的对照组（50%）
→ 实验 A 和实验 B 的样本分布独立
```

### 3.2 正交分流实现

```go
// OrthogonalAllocator 正交分流分配器
type OrthogonalAllocator struct {
    // 每个实验使用不同的 Hash Salt
    saltMap map[string]string // experimentID -> salt
    allocator *Allocator
}

// AssignOrthogonal 正交分配
func (oa *OrthogonalAllocator) Assign(userID string, experimentID string) (string, error) {
    // 1. 获取该实验的 Salt
    salt, ok := oa.saltMap[experimentID]
    if !ok {
        return "", fmt.Errorf("salt not found for experiment %s", experimentID)
    }
    
    // 2. 使用 Salt + UserID 做 Hash
    key := salt + ":" + userID
    
    // 3. 分配实验组
    return oa.allocator.Assign(key, experimentID)
}

// SetupOrthogonal 设置正交实验
func (oa *OrthogonalAllocator) SetupOrthogonal(experiments []string) {
    // 为每个实验生成唯一的 Salt
    for _, expID := range experiments {
        // 使用 UUID 作为 Salt，保证唯一性
        salt := generateUUID()
        oa.saltMap[expID] = salt
    }
}

// generateUUID 生成 UUID 作为 Salt
func generateUUID() string {
    // 简化实现，实际使用 uuid.New().String()
    return fmt.Sprintf("%d", time.Now().UnixNano())
}
```

### 3.3 正交性验证

```go
// OrthogonalityChecker 正交性检查器
type OrthogonalityChecker struct {
    allocator *OrthogonalAllocator
}

// Check 检查正交性
func (c *OrthogonalChecker) Check(userID string, experimentIDs []string) map[string]string {
    assignments := make(map[string]string)
    
    for _, expID := range experimentIDs {
        group, _ := c.allocator.Assign(userID, expID)
        assignments[expID] = group
    }
    
    // 检查是否有冲突
    // （实际项目中需要更复杂的检查逻辑）
    
    return assignments
}

// 示例输出：
// 用户 123 的实验分配：
// bidding_strategy_v2: experiment
// ranking_model_v2: control
// ad_placement_test: experiment
// 
// 三个实验互不干扰，正交性良好
```

---

## 第四部分：指标统计

### 4.1 核心指标

```
广告实验的核心指标：
1. eCPM：每千次展示收入
2. CTR：点击率
3. CVR：转化率
4. CPA：单次转化成本
5. ROI：投资回报率
6. 填充率：广告填充比例
7. 用户体验：跳出率/停留时长
```

### 4.2 指标统计实现

```go
package experiment

import (
    "sync/atomic"
    "time"
)

// MetricCollector 指标收集器
type MetricCollector struct {
    // 按实验 ID + 组名 统计
    metrics map[string]*GroupMetrics
    mu      sync.RWMutex
}

type GroupMetrics struct {
    Impressions  atomic.Int64 // 展示数
    Clicks       atomic.Int64 // 点击数
    Conversions  atomic.Int64 // 转化数
    Revenue      atomic.Float64 // 收入
    StartTime    time.Time
}

// RecordImpression 记录展示
func (mc *MetricCollector) RecordImpression(experimentID, groupName, userID string) {
    key := experimentID + ":" + groupName
    
    mc.mu.Lock()
    if _, ok := mc.metrics[key]; !ok {
        mc.metrics[key] = &GroupMetrics{
            StartTime: time.Now(),
        }
    }
    mc.mu.Unlock()
    
    mc.metrics[key].Impressions.Add(1)
}

// RecordClick 记录点击
func (mc *MetricCollector) RecordClick(experimentID, groupName string) {
    key := experimentID + ":" + groupName
    
    mc.mu.Lock()
    if _, ok := mc.metrics[key]; !ok {
        mc.metrics[key] = &GroupMetrics{
            StartTime: time.Now(),
        }
    }
    mc.mu.Unlock()
    
    mc.metrics[key].Clicks.Add(1)
}

// RecordConversion 记录转化
func (mc *MetricCollector) RecordConversion(experimentID, groupName string, revenue float64) {
    key := experimentID + ":" + groupName
    
    mc.mu.Lock()
    if _, ok := mc.metrics[key]; !ok {
        mc.metrics[key] = &GroupMetrics{
            StartTime: time.Now(),
        }
    }
    mc.mu.Unlock()
    
    mc.metrics[key].Conversions.Add(1)
    mc.metrics[key].Revenue.Add(revenue)
}

// GetMetrics 获取实验指标
func (mc *MetricCollector) GetMetrics(experimentID string) map[string]*GroupMetrics {
    mc.mu.RLock()
    defer mc.mu.RUnlock()
    
    result := make(map[string]*GroupMetrics)
    for key, metrics := range mc.metrics {
        if len(key) >= len(experimentID) && key[:len(experimentID)] == experimentID {
            result[key] = metrics
        }
    }
    
    return result
}

// CalculateCTR 计算 CTR
func (m *GroupMetrics) CalculateCTR() float64 {
    impressions := m.Impressions.Load()
    clicks := m.Clicks.Load()
    
    if impressions == 0 {
        return 0
    }
    
    return float64(clicks) / float64(impressions)
}

// CalculateCVR 计算 CVR
func (m *GroupMetrics) CalculateCVR() float64 {
    clicks := m.Clicks.Load()
    conversions := m.Conversions.Load()
    
    if clicks == 0 {
        return 0
    }
    
    return float64(conversions) / float64(clicks)
}

// CalculateeCPM 计算 eCPM
func (m *GroupMetrics) CalculateeCPM() float64 {
    impressions := m.Impressions.Load()
    revenue := m.Revenue.Load()
    
    if impressions == 0 {
        return 0
    }
    
    return revenue / float64(impressions) * 1000
}
```

### 4.3 统计显著性检验

```go
package experiment

import (
    "math"
)

// StatisticalTest 统计显著性检验
type StatisticalTest struct{}

// ZTest Z 检验，比较两组的 CTR
func (st *StatisticalTest) ZTest(controlCTR, experimentCTR, controlSamples, experimentSamples float64) (float64, bool) {
    // 计算合并比例
    pooledProportion := (controlCTR*controlSamples + experimentCTR*experimentSamples) / (controlSamples + experimentSamples)
    
    // 计算标准误
    se := math.Sqrt(pooledProportion * (1 - pooledProportion) * (1/controlSamples + 1/experimentSamples))
    
    if se == 0 {
        return 0, false
    }
    
    // 计算 Z 值
    z := (experimentCTR - controlCTR) / se
    
    // 判断显著性（双尾检验，α=0.05）
    significant := math.Abs(z) > 1.96
    
    return z, significant
}

// 示例：
// 对照组：CTR = 1.0%，样本 = 100 万
// 实验组：CTR = 1.2%，样本 = 100 万
// Z = (1.2% - 1.0%) / SE = 2.24
// 显著性：2.24 > 1.96 → 显著！
// 结论：新策略 CTR 提升 20%，统计显著
```

---

## 第五部分：在线实验流程

### 5.1 完整流程

```
1. 创建实验
   → 设置分流比例
   → 设置实验参数
   → 注册到实验系统

2. 分配用户
   → 用户请求到达
   → 查询实验配置
   → Hash 分流到实验组
   → 记录分配结果

3. 执行实验
   → 对照组：使用老策略
   → 实验组：使用新策略
   → 记录指标

4. 统计分析
   → 实时计算指标
   → 显著性检验
   → 生成实验报告

5. 决策
   → 实验组显著优于对照组 → 全量
   → 实验组显著差于对照组 → 回滚
   → 无显著差异 → 继续观察
```

### 5.2 Go 实现

```go
// OnlineExperiment 在线实验处理器
type OnlineExperiment struct {
    allocator  *OrthogonalAllocator
    collector  *MetricCollector
    bidders    map[string]Bidder // 不同实验组的竞价器
    predictor  *Predictor
}

// ProcessBid 处理竞价请求
func (oe *OnlineExperiment) ProcessBid(req *BidRequest) (*BidResult, error) {
    // 1. 获取用户在本实验中的分组
    experimentID := "bidding_strategy_v2"
    group, err := oe.allocator.Assign(req.UserID, experimentID)
    if err != nil {
        // 默认使用对照组
        group = "control"
    }
    
    // 2. 记录分流结果
    oe.recordAssignment(req.UserID, experimentID, group)
    
    // 3. 记录展示
    oe.collector.RecordImpression(experimentID, group, req.UserID)
    
    // 4. 使用对应实验组的竞价器
    bidder, ok := oe.bidders[group]
    if !ok {
        bidder = oe.bidders["control"] // 默认对照组
    }
    
    // 5. 执行竞价
    result, err := bidder.Bid(req)
    if err != nil {
        return nil, err
    }
    
    // 6. 记录点击（如果用户点击了广告）
    if result.Clicked {
        oe.collector.RecordClick(experimentID, group)
    }
    
    // 7. 记录转化（如果用户转化了）
    if result.Converted {
        oe.collector.RecordConversion(experimentID, group, result.Revenue)
    }
    
    return result, nil
}

// recordAssignment 记录分流结果
func (oe *OnlineExperiment) recordAssignment(userID, experimentID, group string) {
    // 记录到 Redis/MySQL，用于后续分析
    // ...
}
```

---

## 第六部分：实验配置管理

### 6.1 配置存储

```go
// ExperimentStore 实验配置存储
type ExperimentStore struct {
    redis *RedisClient
    db    *Database
}

// SaveExperiment 保存实验配置
func (es *ExperimentStore) SaveExperiment(exp *Experiment) error {
    // 1. 保存到 Redis（快速读取）
    data, _ := json.Marshal(exp)
    es.redis.Set(context.Background(), "experiment:"+exp.ID, data, 0)
    
    // 2. 保存到 MySQL（持久化）
    // ...
    
    return nil
}

// LoadExperiment 加载实验配置
func (es *ExperimentStore) LoadExperiment(id string) (*Experiment, error) {
    // 1. 先查 Redis
    data, err := es.redis.Get(context.Background(), "experiment:"+id)
    if err == nil && data != "" {
        var exp Experiment
        json.Unmarshal(data, &exp)
        return &exp, nil
    }
    
    // 2. 查 MySQL
    exp, err := es.db.GetExperiment(id)
    if err != nil {
        return nil, err
    }
    
    // 3. 回填 Redis
    data, _ = json.Marshal(exp)
    es.redis.Set(context.Background(), "experiment:"+id, data, 0)
    
    return exp, nil
}
```

### 6.2 动态调整

```go
// 实验进行中调整流量比例
func (es *ExperimentStore) AdjustTraffic(experimentID string, newWeights []float64) error {
    exp, err := es.LoadExperiment(experimentID)
    if err != nil {
        return err
    }
    
    // 更新权重
    for i, weight := range newWeights {
        if i < len(exp.Buckets) {
            exp.Buckets[i].Weight = weight
        }
    }
    
    // 保存配置
    return es.SaveExperiment(exp)
}

// 示例：从 50:50 调整为 70:30
adjustTraffic("bidding_strategy_v2", []float64{700, 300})
```

---

## 第七部分：生产排障案例

### 7.1 分流不一致

```
现象：同一个用户在两次请求中被分到不同组

排查：
1. 检查 Hash 函数是否一致
2. 检查 Salt 是否一致
3. 检查实验配置是否被修改

根因：
→ 实验配置被修改，Salt 变了
→ 导致同一个用户 Hash 值不同

解决方案：
1. Salt 一旦生成，不可更改
2. 实验配置修改时，只改权重，不改 Salt
3. 记录配置变更日志
```

### 7.2 样本偏差

```
现象：实验组用户价值明显高于对照组

排查：
1. 检查分流算法
2. 检查样本分布
3. 检查实验时间

根因：
→ 实验组和对照组的用户分布不一致
→ 实验组都是高价值用户

解决方案：
1. 使用更大的样本量
2. 确保分流是随机的
3. 检查实验时间是否一致
```

---

## 第八部分：自测题

### 问题 1
为什么实验系统需要 Hash 分流？

<details>
<summary>查看答案</summary>

1. **一致性**：同一个用户始终在同一组
2. **均匀分布**：Hash 值均匀分布在 [0, 1000)
3. **可重现**：相同输入产生相同输出
4. **高性能**：O(1) 计算
5. **支持动态调整**：通过修改权重调整流量比例
</details>

### 问题 2
什么是正交实验？为什么需要正交？

<details>
<summary>查看答案</summary>

1. **正交**：实验之间互不干扰
2. **原因**：无法区分是哪个实验的效果
3. **实现**：不同实验使用不同 Salt
4. **验证**：检查用户在不同实验中的分组是否独立
5. **好处**：可以同时运行多个实验，加速迭代
</details>

### 问题 3
如何判断实验结果是否显著？

<details>
<summary>查看答案</summary>

1. **Z 检验**：比较两组的 CTR/CVR
2. **显著性水平**：α=0.05，Z > 1.96 为显著
3. **样本量**：样本量越大，越容易检测到差异
4. **置信区间**：95% 置信区间不包含 0 为显著
5. **多重检验校正**：Bonferroni 校正
</details>

---

*本文档基于广告实验系统生产实战整理。*