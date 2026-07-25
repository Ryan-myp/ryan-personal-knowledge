# 广告系统设计面试深度：从 0 到 1 设计一个 DSP

> 面试常见问题 + 设计思路 + Trade-off 分析 + 生产实践

---

## 第一部分：面试常见问题

### 问题 1：如何设计一个广告竞价系统？

**回答框架：**

```
1. 需求分析
   → QPS：1000+
   → 延迟：50ms
   → 准确性：预算/频次不能超
   → 可用性：99.99%

2. 架构设计
   → API Gateway → Bid Service → Memory Index + Predictor
   → 异步：频次/预算/统计
   → 缓存：L1/L2/L3
   → 降级：画像/模型/Redis 故障

3. 核心流程
   → 多路召回 → 粗排 → 精排 → 竞价决策

4. 关键组件
   → 内存索引（广告筛选）
   → 预测模型（CTR/CVR）
   → 竞价引擎（oCPM）
   → 频次/预算控制

5. Trade-off 分析
   → 内存 vs Redis：内存快但数据易丢失
   → 同步 vs 异步：同步快但有风险
   → 粗排 vs 精排：粗排快但精度低
```

### 问题 2：如何优化广告竞价系统的延迟？

**回答框架：**

```
1. 多路召回并行化
   → 6 路召回并行，总耗时 = max(各路耗时)

2. 批量查询
   → Pipeline 批量查询频次/预算

3. 缓存优化
   → 三级缓存，95% 命中率

4. 模型优化
   → 粗排轻量模型，精排复杂模型

5. 数据结构优化
   → 内存索引 O(1) 查找
```

### 问题 3：如何保证预算不超扣？

**回答框架：**

```
1. 预检查（同步）
   → 竞价前检查预算是否充足

2. 原子扣减（异步）
   → Lua 脚本保证原子性

3. 对账（定时）
   → 每小时对账一次

4. 降级
   → Redis 故障时降级到 MySQL
```

---

## 第二部分：Trade-off 分析

### 2.1 内存 vs Redis

| 维度 | 内存 | Redis |
|------|------|-------|
| 延迟 | 0.01ms | 1ms |
| 并发 | 10 万 QPS | 10 万 QPS |
| 持久化 | ❌ | ✅ |
| 一致性 | 难 | 易 |
| 运维 | 简单 | 复杂 |
| 适用场景 | 实时查询 | 持久化存储 |

### 2.2 同步 vs 异步

| 维度 | 同步 | 异步 |
|------|------|------|
| 延迟 | 高 | 低 |
| 一致性 | 强 | 最终 |
| 复杂度 | 低 | 高 |
| 适用场景 | 预算检查 | 频次记录 |

### 2.3 粗排 vs 精排

| 维度 | 粗排 | 精排 |
|------|------|------|
| 模型 | 轻量级 | 复杂 |
| 候选集 | 800 → 200 | 200 → 10 |
| 延迟 | 5ms | 10ms |
| 精度 | 低 | 高 |

---

## 第三部分：生产实践

### 3.1 线上优化案例

```
案例 1：P99 延迟优化
→ 优化前：50ms
→ 优化后：18ms
→ 方法：多路召回并行化 + Pipeline 批量查询

案例 2：预算超扣修复
→ 问题：并发下预算超扣
→ 修复：Lua 脚本原子扣减

案例 3：缓存穿透修复
→ 问题：恶意请求打到 MySQL
→ 修复：布隆过滤器
```

---

## 第四部分：自测题

### 问题 1
如何设计一个广告竞价系统？

<details>
<summary>查看答案</summary>

1. 需求分析：QPS/延迟/准确性/可用性
2. 架构设计：API Gateway → Bid Service → Memory Index
3. 核心流程：多路召回 → 粗排 → 精排 → 竞价
4. 关键组件：内存索引/预测模型/竞价引擎
5. Trade-off：内存 vs Redis/同步 vs 异步
</details>

### 问题 2
如何优化广告竞价系统的延迟？

<details>
<summary>查看答案</summary>

1. 多路召回并行化
2. 批量查询（Pipeline）
3. 三级缓存
4. 模型优化（粗排/精排）
5. 数据结构优化（内存索引）
</details>

---

*本文档基于广告系统设计面试实战整理。*
---

## Go 代码实战：广告系统面试核心模块

### 1. 分布式预算控制（Redis + Lua）

```go
package budget

import (
	"context"
	"fmt"
	"time"

	"github.com/redis/go-redis/v9"
)

// DistributedBudgetManager 分布式预算管理器
type DistributedBudgetManager struct {
	rdb *redis.Client
}

// ConsumeBudget 消耗预算（原子操作，Lua脚本保证一致性）
func (bm *DistributedBudgetManager) ConsumeBudget(
	ctx context.Context,
	campaignID string,
	amount float64,
	dailyLimit, totalLimit float64,
) error {
	// Lua 脚本：原子检查+扣减
	luaScript := redis.NewScript(`
		local key = KEYS[1]
		local daily_key = KEYS[2]
		local amount = tonumber(ARGV[1])
		local daily_limit = tonumber(ARGV[2])
		local total_limit = tonumber(ARGV[3])
		
		-- 检查日预算
		local daily_spent = tonumber(redis.call('GET', daily_key) or '0')
		if daily_spent + amount > daily_limit then
			return -1  -- 日预算耗尽
		end
		
		-- 检查总预算
		local total_spent = tonumber(redis.call('GET', key) or '0')
		if total_spent + amount > total_limit then
			return -2  -- 总预算耗尽
		end
		
		-- 原子扣减
		redis.call('INCRBYFLOAT', key, amount)
		redis.call('INCRBYFLOAT', daily_key, amount)
		
		-- 设置过期时间（日预算次日凌晨重置）
		redis.call('EXPIRE', daily_key, 86400)
		
		return 0  -- 成功
	`)
	
	result, err := luaScript.Run(ctx, bm.rdb, []string{
		fmt.Sprintf("campaign:%s:total", campaignID),
		fmt.Sprintf("campaign:%s:daily:%s", campaignID, time.Now().Format("20060102")),
	}, amount, dailyLimit, totalLimit).Int64()
	
	if err != nil {
		return fmt.Errorf("budget consume failed: %w", err)
	}
	
	switch result {
	case -1:
		return fmt.Errorf("daily budget exhausted for campaign %s", campaignID)
	case -2:
		return fmt.Errorf("total budget exhausted for campaign %s", campaignID)
	case 0:
		return nil
	default:
		return fmt.Errorf("unknown budget error: %d", result)
	}
}
```

### 2. 多路召回 + 排序流水线

```go
package ranking

import (
	"context"
	"sort"
	"time"
)

// RecallPipeline 多路召回流水线
type RecallPipeline struct {
	userRecall   *UserBasedRecall
	itemRecall   *ItemBasedRecall
	geoRecall    *GeoBasedRecall
	trendRecall  *TrendBasedRecall
	businessRecall *BusinessRuleRecall
	ranker       *RankingEngine
}

// RecallResponse 召回结果
type RecallResponse struct {
	Candidates []*Candidate
	Metrics    RecallMetrics
}

type RecallMetrics struct {
	TotalLatency    time.Duration
	PerRecallLatency map[string]time.Duration
	CandidateCount  int
	DedupRatio      float64
}

func (rp *RecallPipeline) Execute(ctx context.Context, query *Query) (*RecallResponse, error) {
	start := time.Now()
	type recallResult struct {
		name  string
		items []*Candidate
		latency time.Duration
	}
	
	resultCh := make(chan recallResult, 5)
	var wg sync.WaitGroup
	
	// 并行召回5路
	wg.Add(5)
	go func() { defer wg.Done(); rp.doRecall(ctx, "user", query, resultCh) }()
	go func() { defer wg.Done(); rp.doRecall(ctx, "item", query, resultCh) }()
	go func() { defer wg.Done(); rp.doRecall(ctx, "geo", query, resultCh) }()
	go func() { defer wg.Done(); rp.doRecall(ctx, "trend", query, resultCh) }()
	go func() { defer wg.Done(); rp.doRecall(ctx, "business", query, resultCh) }()
	
	go func() {
		wg.Wait()
		close(resultCh)
	}()
	
	var allCandidates []*Candidate
	perLatency := make(map[string]time.Duration)
	
	for r := range resultCh {
		allCandidates = append(allCandidates, r.items...)
		perLatency[r.name] = r.latency
	}
	
	// 去重 + 截断到精排候选集
	dedupStart := time.Now()
	allCandidates = rp.dedup(allCandidates)
	
	metrics := RecallMetrics{
		TotalLatency:     time.Since(start),
		PerRecallLatency: perLatency,
		CandidateCount:   len(allCandidates),
		DedupRatio:       1.0 - float64(len(allCandidates))/float64(max(1, rp.undupCount)),
	}
	
	return &RecallResponse{Candidates: allCandidates[:min(rp.CandidateCount, len(allCandidates))], Metrics: metrics}, nil
}

func (rp *RecallPipeline) dedup(candidates []*Candidate) []*Candidate {
	seen := make(map[string]bool, len(candidates))
	result := make([]*Candidate, 0, len(candidates))
	for _, c := range candidates {
		if !seen[c.ID] {
			seen[c.ID] = true
			result = append(result, c)
		}
	}
	return result
}
```

### 自测题

<details>
<summary>Q1: 为什么预算扣减必须用 Lua 脚本而不是 Go 代码里先 GET 再 INCR？</summary>

**答案**：

**非原子操作的竞态条件**：
```
时刻 T1: 线程A GET campaign_budget → 返回 999
时刻 T2: 线程B GET campaign_budget → 返回 999
时刻 T3: 线程A INCRBY 100 → 设为 1099 ✅
时刻 T4: 线程B INCRBY 100 → 设为 1099 ❌ 应该 1199！
```

**Lua 脚本保证原子性**：Redis 单线程执行 Lua 脚本，中间不会被其他命令打断。这是分布式预算控制的基石——没有它，预算超投是必然的。

</details>

<details>
<summary>Q2: 多路召回并行化时，如果某一路超时（如 trendRecall > 50ms），如何处理？</summary>

**答案**：

```go
// 方案: context 超时 + 部分召回
ctx, cancel := context.WithTimeout(ctx, 50*time.Millisecond)
defer cancel()

// 每路独立 goroutine，各自监听 ctx.Done()
go func() {
    select {
    case <-ctx.Done():
        // 超时了，返回空结果
        resultCh <- recallResult{name: "trend", items: nil, latency: time.Since(start)}
    case <-done:
        resultCh <- recallResult{name: "trend", items: items, latency: time.Since(start)}
    }
}()
```

**Trade-off**：
| 策略 | 延迟影响 | 召回质量 | 适用场景 |
|------|---------|---------|---------|
| 等全部完成 | P99 由最慢路决定 | 最优 | 低QPS |
| 超时丢弃 | P99 可控 | 略降 | **生产标准** |
| 保底数量 | 先返回N路，凑够再返回 | 动态 | 高QPS + 严格SLA |

</details>

<details>
<summary>Q3: Redis INCRBYFLOAT 的精度问题如何处理？（浮点数累加误差）</summary>

**答案**：

**问题**：`INCRBYFLOAT` 使用双精度浮点数，多次累加后会有舍入误差。例如连续消耗 0.1 元 1000 次，结果可能变成 99.99999999999999 而非 100.0。

**解决方案**：
```go
// 方案1: 使用整数（分/厘为单位）
// 所有金额转为整数操作，INCRBY 替代 INCRBYFLOAT
// 缺点：需要改数据结构

// 方案2: 定期校准
// 每天凌晨对账：Redis vs DB，差额补回
// 广告系统天然支持 T+1 对账

// 方案3: 使用 Redis 6.x DECIMAL 扩展
// 或外部精确计算服务

// 实际生产：方案2 + 方案1 组合
// 高频扣减用 INCRBYFLOAT（允许微小误差），每日对账校准
```

广告预算允许 ±0.01 元的误差（用户不关心），但对账必须精确到分。

</details>
