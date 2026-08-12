# 故障排查案例库深度实现

> **文档级别**: Level 5 - 专家级  
> **创建日期**: 2026-08-12  
> **状态**: ✅ 已补齐

---

## 一、竞价系统故障排查

### 1.1 竞价超时故障

```
【故障现象】
- P99 延迟从 20ms 飙升到 500ms+
- 大量请求超时被丢弃
- 竞价成功率下降到 60%

【排查步骤】
1. 检查 Redis 连接池
   → 发现连接池耗尽，活跃连接 1000/1000
   
2. 检查下游服务响应
   → RTA 服务平均响应时间从 5ms 增加到 200ms
   
3. 检查网络链路
   → 发现跨机房网络抖动，延迟增加 150ms

【根因】
- RTA 服务突发流量导致响应变慢
- 超时配置不合理，默认 200ms 不足以应对
- 重试机制触发，进一步加重负载

【解决方案】
1. 调整超时配置
   - 短超时: 5ms (RTA 预检)
   - 中超时: 15ms (模型推理)
   - 长超时: 50ms (综合竞价)
   
2. 增加熔断器
   - 失败率 > 10% 时熔断
   - 熔断 30s 后半开测试
   
3. 优化重试策略
   - 不重试超时请求
   - 只重试 5xx 错误

【代码实现】
```go
type TimeoutConfig struct {
    RTATimeout      time.Duration // 5ms
    ModelTimeout    time.Duration // 15ms
    BiddingTimeout  time.Duration // 50ms
    CircuitBreaker  CircuitConfig
}

func (b *BiddingEngine) Bid(ctx context.Context, req *BidRequest) (*BidResponse, error) {
    // 分层超时控制
    ctx, cancel := context.WithTimeout(ctx, b.config.BiddingTimeout)
    defer cancel()
    
    // RTA 预检 (短超时)
    rtaCtx, rtaCancel := context.WithTimeout(ctx, b.config.RTATimeout)
    defer rtaCancel()
    
    rtaResult, err := b.rtaService.Check(rtaCtx, req)
    if err != nil {
        return nil, fmt.Errorf("RTA check failed: %w", err)
    }
    
    // 熔断器检查
    if !b.circuitBreaker.Allow() {
        return nil, ErrCircuitOpen
    }
    
    // ... 后续逻辑
}
```
```

### 1.2 内存泄漏故障

```
【故障现象】
- 竞价服务内存持续增长
- 每 24 小时增长 2GB
- 最终导致 OOM 被 kill

【排查步骤】
1. 检查 pprof 快照
   → 发现大量 goroutine 未释放
   
2. 分析 goroutine 堆栈
   → 主要在 Kafka 消费者协程
   
3. 定位代码
   → 消息处理回调中引用了外部变量

【根因】
```go
// 问题代码示例
func (c *Consumer) Start() {
    for msg := range c.ch {
        go func() {  // goroutine 捕获外部变量
            c.process(msg)
        }()
    }
}

func (c *Consumer) process(msg *Message) {
    // 使用 c 的引用，导致 c 无法被 GC
    c.stats.Record(msg)
}
```

【解决方案】
```go
// 修复后代码
func (c *Consumer) Start() {
    for msg := range c.ch {
        go func(m *Message) {  // 值传递
            processMessage(m)
        }(msg)
    }
}

func processMessage(msg *Message) {
    // 独立函数，不依赖外部对象
    stats.Record(msg)
}
```
```

---

## 二、DSP 系统故障排查

### 2.1 出价策略异常

```
【故障现象】
- 某广告主预算消耗过快
- 一天内消耗了 30 天预算
- ROI 严重低于预期

【排查步骤】
1. 检查出价策略配置
   → 发现目标 CPA 从 50 元变成 5 元
   
2. 检查代码变更
   → 最近一次发布修改了出价公式
   
3. 定位问题代码
   → 浮点数精度问题导致出价计算错误

【根因】
```go
// 问题代码
bidPrice := basePrice * (1 + confidence)
// confidence 为 0.95，basePrice 为 100
// 理论上 bidPrice = 195，实际计算结果为 1950.000000001

// 浮点数精度问题
confidence := 0.95
result := 100 * (1 + confidence) // 195.00000000000003
```

【解决方案】
```go
// 修复：使用 Decimal 精度计算
import "github.com/shopspring/decimal"

bidPrice := decimal.NewFromFloat(basePrice).
    Mul(decimal.NewFromFloat(1 + confidence)).
    Round(2)  // 保留 2 位小数
```
```

### 2.2 数据一致性问题

```
【故障现象】
- 计费金额与曝光量不一致
- 财务对账发现差异
- 差异率约 0.5%

【排查步骤】
1. 检查数据管道
   → Kafka 消息有重复消费
   
2. 检查幂等性设计
   → 缺少消息 ID 去重机制
   
3. 检查数据库事务
   → 分布式事务未正确提交

【根因】
```go
// 问题代码
func (s *BillingService) RecordExposure(ctx context.Context, req *ExposureRequest) error {
    // 直接写入数据库，无幂等保护
    _, err := s.db.Exec(
        "INSERT INTO exposures (id, ad_id, user_id, cost) VALUES (?, ?, ?, ?)",
        req.ID, req.AdID, req.UserID, req.Cost,
    )
    return err
}
```

【解决方案】
```go
// 修复：添加幂等保护
func (s *BillingService) RecordExposure(ctx context.Context, req *ExposureRequest) error {
    // 使用唯一索引保证幂等
    _, err := s.db.Exec(`
        INSERT INTO exposures (id, ad_id, user_id, cost, created_at)
        VALUES (?, ?, ?, ?, NOW())
        ON DUPLICATE KEY UPDATE cost = cost
    `, req.ID, req.AdID, req.UserID, req.Cost)
    
    return err
}
```
```

---

## 三、SSP 系统故障排查

### 3.1 Header Bidding 超时

```
【故障现象】
- 广告填充率下降到 40%
- 用户反馈广告加载慢
- 竞价成功率低

【排查步骤】
1. 检查竞价日志
   → 大部分供应商响应超时
   
2. 分析超时原因
   → 供应商服务器响应慢
   
3. 检查超时配置
   → 统一 200ms 超时，部分供应商需要 500ms

【解决方案】
```go
// 分级超时策略
type SupplierTimeout struct {
    Name     string
    Timeout  time.Duration
    Priority int
}

var supplierTimeouts = []SupplierTimeout{
    {"AppNexus", 100 * time.Millisecond, 1},
    {"Index Exchange", 150 * time.Millisecond, 2},
    {"Rubicon", 200 * time.Millisecond, 3},
    {"PubMatic", 300 * time.Millisecond, 4},
}
```
```

### 3.2 库存预测不准

```
【故障现象】
- 预卖了 100 万曝光，实际只有 80 万
- 无法履约，客户投诉
- 需要赔偿

【排查步骤】
1. 检查预测模型
   → 预测准确度只有 85%
   
2. 分析误差来源
   → 未考虑节假日效应
   
3. 检查数据质量
   → 历史数据存在缺失

【解决方案】
```go
// 改进预测模型
type InventoryForecaster struct {
    baseModel     *BaseModel
    holidayModel  *HolidayAdjustment
    trendModel    *TrendAnalysis
}

func (f *InventoryForecaster) Forecast(date time.Time) int {
    base := f.baseModel.Predict(date)
    holiday := f.holidayModel.Adjust(date)
    trend := f.trendModel.Adjust(base)
    
    // 安全边际
    safetyMargin := 0.9  // 只卖预测值的 90%
    return int(float64(base*holiday*trend) * safetyMargin)
}
```
```

---

## 四、故障排查方法论

### 4.1 五步排查法

```
┌─────────────────────────────────────────────────────────────────┐
│                     故障排查五步法                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Step 1: 复现问题                                              │
│  ├─ 确认故障现象                                               │
│  ├─ 收集相关日志和指标                                         │
│  └─ 确定影响范围                                               │
│                                                                 │
│  Step 2: 定位根因                                              │
│  ├─ 分析日志查找异常                                           │
│  ├─ 检查关键指标变化                                           │
│  └─ 缩小问题范围                                               │
│                                                                 │
│  Step 3: 验证假设                                              │
│  ├─ 提出可能的原因                                             │
│  ├─ 设计验证方案                                               │
│  └─ 执行验证                                                   │
│                                                                 │
│  Step 4: 实施修复                                              │
│  ├─ 制定修复方案                                               │
│  ├─ 小流量验证                                                 │
│  └─ 全量发布                                                   │
│                                                                 │
│  Step 5: 复盘总结                                              │
│  ├─ 编写故障报告                                               │
│  ├─ 完善监控告警                                               │
│  └─ 制定预防措施                                               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 常用排查工具

```bash
# Go 性能分析
go tool pprof http://localhost:6060/debug/pprof/heap
go tool pprof http://localhost:6060/debug/pprof/goroutine

# 链路追踪
curl -H "X-B3-TraceId: $(uuidgen)" http://api.example.com/bid

# Redis 诊断
redis-cli --latency-history
redis-cli --bigkeys

# Kafka 诊断
kafka-consumer-groups.sh --describe --bootstrap-server localhost:9092
kafka-topics.sh --describe --topic bid-events
```

---

## 五、监控告警配置

```yaml
# Prometheus 告警规则
groups:
  - name: bidding_alerts
    rules:
      - alert: HighBidLatency
        expr: histogram_quantile(0.99, rate(bid_latency_seconds_bucket[5m])) > 0.1
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "竞价 P99 延迟过高"
          
      - alert: LowBidSuccessRate
        expr: rate(bid_success_total[5m]) / rate(bid_request_total[5m]) < 0.8
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "竞价成功率下降"
          
      - alert: HighMemoryUsage
        expr: process_resident_memory_bytes / 1024 / 1024 / 1024 > 8
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "内存使用过高"
```

---

## 六、参考资料

```
排查方法论:
├── Google SRE 手册
├── AWS Well-Architected Framework
└── Azure Incident Response Guide

工具文档:
├── pprof 官方文档
├── Jaeger 追踪指南
└── Prometheus 告警配置

最佳实践:
├── ChatGPT 故障排查指南
├── K8s 故障排查手册
└── 微服务故障排查最佳实践
```

---

*文档版本: v1.0*  
*最后更新: 2026-08-12*  
*作者: Ryan*
