# 广告系统排查手册：常见问题快速定位与解决

> 生产环境常见问题 + 排查步骤 + 解决方案 + 预防建议

---

## 第一部分：排查方法论

### 1.1 排查思路

```
问题 → 收集信息 → 假设 → 验证 → 定位 → 解决 → 复盘

1. 收集信息：
   → 问题发生的时间
   → 影响的范围（单个广告/所有广告/单个用户/所有用户）
   → 最近的变更（代码/配置/数据）

2. 假设：
   → 根据经验列出可能的原因
   → 按可能性排序

3. 验证：
   → 逐一验证假设
   → 用日志/监控/诊断工具确认

4. 解决：
   → 临时解决：快速恢复业务
   → 根本解决：修复根因

5. 复盘：
   → 为什么会发生？
   → 如何预防再次发生？
   → 更新排查手册
```

### 1.2 排查工具箱

```
1. 诊断引擎：一键诊断（ad-diagnosis-engine-deep.md）
2. 日志查询：ELK 搜索（ad-observability-deep.md）
3. 监控面板：Grafana 实时查看
4. 数据库：直接查询 MySQL/ClickHouse
5. 缓存：Redis CLI 查看
6. 链路追踪：Jaeger 查看 Trace
```

---

## 第二部分：常见问题排查

### 2.1 问题：广告 0 展示

```
症状：
→ 广告组状态：运行中
→ 预算充足
→ 审核通过
→ 但 0 展示

排查步骤：
1. 查竞价日志：
   SELECT * FROM bid_logs 
   WHERE ad_id = 'xxx' AND date = '2024-01-01'
   ORDER BY timestamp DESC LIMIT 100;
   
   → 如果有请求但没有 win：说明竞价失败
   → 如果没有请求：说明没有流量

2. 查出价竞争力：
   SELECT AVG(bid_price) FROM bid_logs 
   WHERE slot_id = 'xxx' AND date = '2024-01-01';
   
   → 如果我们的出价 < 行业均价：提高出价

3. 查 CTR 预测：
   SELECT predicted_ctr FROM ad_predictions 
   WHERE ad_id = 'xxx';
   
   → 如果 CTR < 0.001：优化创意

4. 查定向条件：
   SELECT targeting FROM campaigns WHERE id = 'xxx';
   
   → 如果地域/年龄/兴趣限制太窄：放宽定向

5. 查广告位流量：
   SELECT request_count FROM slot_metrics 
   WHERE slot_id = 'xxx' AND date = '2024-01-01';
   
   → 如果 request_count = 0：广告位无流量
```

### 2.2 问题：eCPM 突然下降

```
症状：
→ 昨天 eCPM ¥50，今天 ¥30

排查步骤：
1. 拆分解 eCPM：
   eCPM = CTR × CVR × targetCPA × 1000
   
   → CTR 下降？→ 创意疲劳
   → CVR 下降？→ 落地页问题
   → targetCPA 下降？→ 出价策略变更

2. 查 CTR 趋势：
   SELECT DATE(timestamp), AVG(ctr) 
   FROM ad_metrics 
   WHERE ad_id = 'xxx' 
   GROUP BY DATE(timestamp) 
   ORDER BY DATE(timestamp) DESC 
   LIMIT 7;
   
   → 如果 CTR 持续下降：创意疲劳，需要新素材

3. 查流量质量：
   SELECT DATE(timestamp), AVG(user_quality_score) 
   FROM user_metrics 
   WHERE slot_id = 'xxx' 
   GROUP BY DATE(timestamp);
   
   → 如果新用户占比上升：流量质量下降

4. 查竞争环境：
   SELECT DATE(timestamp), AVG(industry_ecpm) 
   FROM market_metrics 
   GROUP BY DATE(timestamp);
   
   → 如果行业 eCPM 下降：竞争加剧

5. 查近期变更：
   → 最近是否调整了出价策略？
   → 最近是否更换了创意？
   → 最近是否扩大了定向范围？
```

### 2.3 问题：用户投诉看不到广告

```
症状：
→ 用户反馈 App 里没有广告

排查步骤：
1. 查用户画像：
   SELECT age, gender, interests FROM user_profiles 
   WHERE user_id = 'xxx';
   
   → 如果用户画像不完整：补充画像

2. 查频次限制：
   SELECT freq_count FROM user_frequency 
   WHERE user_id = 'xxx' AND date = CURDATE();
   
   → 如果 freq_count >= max_freq：用户被频次限制

3. 查反作弊：
   SELECT fraud_score FROM user_fraud 
   WHERE user_id = 'xxx';
   
   → 如果 fraud_score > 0.8：用户被标记为可疑

4. 查广告位填充率：
   SELECT fill_rate FROM slot_metrics 
   WHERE slot_id = 'xxx' AND date = CURDATE();
   
   → 如果 fill_rate < 50%：填充率低

5. 查地域限制：
   → 用户所在城市是否在投放地域内？
```

### 2.4 问题：预算扣减异常

```
症状：
→ 广告主说预算被超额扣减

排查步骤：
1. 查扣费日志：
   SELECT * FROM billing_logs 
   WHERE account_id = 'xxx' AND date = '2024-01-01'
   ORDER BY timestamp;
   
   → 检查是否有重复扣费

2. 查预算状态：
   SELECT budget, spent, remaining FROM campaigns 
   WHERE id = 'xxx';
   
   → 检查 spent 是否 > budget

3. 查并发扣费：
   → 同一广告同时有多个请求时，是否并发扣费？
   → 检查 Redis 的 DECR 操作是否有竞态条件

4. 查对账差异：
   → MySQL 预算记录 vs Redis 预算记录是否一致？
   → 如果不一致，以哪个为准？
```

---

## 第三部分：预防建议

### 3.1 预防措施

```
1. 监控告警：
   → eCPM 下降 > 20%：告警
   → 填充率 < 90%：告警
   → 错误率 > 5%：告警

2. 定期巡检：
   → 每周检查广告主账户状态
   → 每月检查预算扣费准确性
   → 每季度检查创意质量

3. 容量规划：
   → 提前扩容（QPS 增长 50% 时）
   → 提前储备（大促前）

4. 灰度发布：
   → 新出价策略先灰度 1%
   → 新创意模板先灰度 5%
```

### 3.2 应急方案

```
1. 广告投不出去：
   → 临时：降低底价，放宽定向
   → 根本：优化竞价策略

2. eCPM 下降：
   → 临时：提高出价
   → 根本：优化创意

3. 预算扣费异常：
   → 临时：暂停广告组
   → 根本：修复扣费逻辑

4. 系统宕机：
   → 临时：降级到缓存
   → 根本：修复系统
```

---

## 第四部分：自测题

### 问题 1
广告 0 展示的排查步骤？

<details>
<summary>查看答案</summary>

1. 查竞价日志：是否有 win
2. 查出价竞争力：是否 < 行业均价
3. 查 CTR 预测：是否过低
4. 查定向条件：是否太窄
5. 查广告位流量：是否有请求
</details>

### 问题 2
eCPM 下降如何排查？

<details>
<summary>查看答案</summary>

1. 拆解 eCPM = CTR × CVR × targetCPA
2. 查 CTR 趋势：创意疲劳？
3. 查流量质量：新用户占比？
4. 查竞争环境：行业 eCPM？
5. 查近期变更：出价/创意/定向？

### 问题 3
零展示问题的排查步骤是什么？

<details>
<summary>查看答案</summary>

1. **检查 Campaign 状态**：确认处于 active 而非 paused/draft/expired 状态
2. **Budget 检查**：daily budget 是否已 spend 完，remaining_budget > 0？
3. **Targeting 验证**：geo/location/age/demographics 设置是否过于窄，导致无匹配人群
4. **审核状态**：creative 是否通过审核（approved）还是 pending/rejected
5. **竞争环境**：同时段同目标的竞价对手是否过多，eCPM 不够高未胜出
6. **技术链路**：追踪 ID 是否存在，bid request 是否正确发送到 exchange，bid response 是否到达

</details>

</details>

---

*本文档基于广告系统排查生产实战整理。*

## Go 实现：自动诊断引擎

```go
package diagnosis

import (
	"context"
	"fmt"
	"strings"
	"time"
)

// DiagnosticEngine 自动诊断引擎 - 5大模块并行检查
type DiagnosticEngine struct {
	logger *Logger
	metrics *MetricsCollector
}

// Issue 诊断发现的问题
type Issue struct {
	Module    string    `json:"module"`
	Severity  string    `json:"severity"` // "critical", "warning", "info"
	Message   string    `json:"message"`
	Evidence  string    `json:"evidence"`
	Suggestion string   `json:"suggestion"`
}

// DiagnosisReport 诊断报告
type DiagnosisReport struct {
	Timestamp time.Time `json:"timestamp"`
	Issues    []Issue   `json:"issues"`
	RootCause string    `json:"root_cause"`
	Score     float64   `json:"score"` // 健康度 0-100
}

// DiagnoseCampaign 诊断广告组问题
func (d *DiagnosticEngine) DiagnoseCampaign(ctx context.Context, campaignID string) (*DiagnosisReport, error) {
	report := &DiagnosisReport{Timestamp: time.Now()}

	// 5大模块并行检查
	type result struct {
		issues []Issue
		err    error
	}
	ch := make(chan result, 5)

	go d.checkImpressions(ctx, campaignID, ch)
	go d.checkBidCompetitiveness(ctx, campaignID, ch)
	go d.checkCTR(ctx, campaignID, ch)
	go d.checkTargeting(ctx, campaignID, ch)
	go d.checkBudget(ctx, campaignID, ch)

	for i := 0; i < 5; i++ {
		select {
		case r := <-ch:
			if r.err != nil {
				d.logger.Warn("diagnostic check failed", "module", campaignID, "err", r.err)
				continue
			}
			report.Issues = append(report.Issues, r.issues...)
		case <-time.After(5 * time.Second):
			d.logger.Warn("diagnostic timeout", "campaign", campaignID)
		}
	}

	// 根因分析
	report.RootCause = d.analyzeRootCause(report.Issues)
	report.Score = d.calculateHealthScore(report.Issues)

	return report, nil
}

// checkImpressions 检查展示量异常
func (d *DiagnosticEngine) checkImpressions(ctx context.Context, campID string, ch chan<- result) {
	// 查竞价日志：是否有 win / 出价 / 曝光
	impressions, err := d.metrics.GetImpressions(ctx, campID, time.Now().Add(-24*time.Hour))
	if err != nil {
		ch <- result{err: fmt.Errorf("get impressions: %w", err)}
		return
	}

	var issues []Issue
	if impressions == 0 {
		issues = append(issues, Issue{
			Module:   "impressions",
			Severity: "critical",
			Message:  "广告 0 展示",
			Evidence: fmt.Sprintf("24h impressions = %d", impressions),
			Suggestion: "1. 检查竞价日志是否有 win\n2. 检查出价是否低于底价\n3. 检查定向条件是否过窄",
		})
	}
	ch <- result{issues: issues}
}

// checkBidCompetitiveness 检查出价竞争力
func (d *DiagnosticEngine) checkBidCompetitiveness(ctx context.Context, campID string, ch chan<- result) {
	bid, avgBid, err := d.metrics.GetBidCompetitiveness(ctx, campID)
	if err != nil {
		ch <- result{err: err}
		return
	}

	var issues []Issue
	if bid < avgBid*0.8 {
		issues = append(issues, Issue{
			Module:   "bid",
			Severity: "warning",
			Message:  fmt.Sprintf("出价 %.2f 低于行业均价 %.2f", bid, avgBid),
			Evidence: fmt.Sprintf("bid=%.2f, avg=%.2f, ratio=%.2f", bid, avgBid, bid/avgBid),
			Suggestion: "提高出价或优化创意质量分以提升竞争力",
		})
	}
	ch <- result{issues: issues}
}

// checkCTR 检查 CTR 异常
func (d *DiagnosticEngine) checkCTR(ctx context.Context, campID string, ch chan<- result) {
	ctr, prevCtr, err := d.metrics.GetCTR(ctx, campID)
	if err != nil {
		ch <- result{err: err}
		return
	}

	var issues []Issue
	if ctr < prevCtr*0.5 {
		issues = append(issues, Issue{
			Module:   "ctr",
			Severity: "warning",
			Message:  fmt.Sprintf("CTR 下降: %.4f → %.4f", prevCtr, ctr),
			Evidence: fmt.Sprintf("current_ctr=%.4f, previous_ctr=%.4f, drop=%.1f%%", ctr, prevCtr, (prevCtr-ctr)/prevCtr*100),
			Suggestion: "1. 检查创意是否疲劳（同一创意展示 > N 次）\n2. 检查流量质量变化\n3. 检查近期是否更换了创意",
		})
	}
	ch <- result{issues: issues}
}

// checkTargeting 检查定向条件
func (d *DiagnosticEngine) checkTargeting(ctx context.Context, campID string, ch chan<- result) {
	targeting, err := d.metrics.GetTargeting(ctx, campID)
	if err != nil {
		ch <- result{err: err}
		return
	}

	var issues []Issue
	// 检查定向条件是否过窄
	narrowCount := 0
	if strings.Contains(targeting.AgeRange, "-") && len(strings.Split(targeting.AgeRange, "-")[0]) > 0 {
		narrowCount++
	}
	if len(targeting.Geo) > 3 {
		narrowCount++
	}
	if narrowCount >= 2 {
		issues = append(issues, Issue{
			Module:   "targeting",
			Severity: "info",
			Message:  "定向条件可能过窄",
			Evidence: fmt.Sprintf("narrow_factors=%d", narrowCount),
			Suggestion: "放宽定向条件以扩大可投放人群",
		})
	}
	ch <- result{issues: issues}
}

// checkBudget 检查预算
func (d *DiagnosticEngine) checkBudget(ctx context.Context, campID string, ch chan<- result) {
	spent, budget, err := d.metrics.GetBudget(ctx, campID)
	if err != nil {
		ch <- result{err: err}
		return
	}

	var issues []Issue
	if spent >= budget {
		issues = append(issues, Issue{
			Module:   "budget",
			Severity: "critical",
			Message:  "预算已耗尽",
			Evidence: fmt.Sprintf("spent=%.0f, budget=%.0f", spent, budget),
			Suggestion: "增加预算或延长投放周期",
		})
	} else if float64(spent)/budget > 0.95 {
		issues = append(issues, Issue{
			Module:   "budget",
			Severity: "warning",
			Message:  "预算即将耗尽 (>95%)",
			Evidence: fmt.Sprintf("spent=%.0f, budget=%.0f, usage=%.0f%%", spent, budget, float64(spent)/budget*100),
			Suggestion: "提前准备预算补充方案",
		})
	}
	ch <- result{issues: issues}
}

// analyzeRootCause 根因分析
func (d *DiagnosticEngine) analyzeRootCause(issues []Issue) string {
	// 按严重程度排序，取最严重的问题
	criticalCount := 0
	for _, issue := range issues {
		if issue.Severity == "critical" {
			criticalCount++
		}
	}
	if criticalCount > 0 {
		return fmt.Sprintf("发现 %d 个严重问题，需立即处理", criticalCount)
	}
	warningCount := 0
	for _, issue := range issues {
		if issue.Severity == "warning" {
			warningCount++
		}
	}
	if warningCount > 0 {
		return fmt.Sprintf("发现 %d 个警告问题，建议优化", warningCount)
	}
	return "系统运行正常"
}

// calculateHealthScore 计算健康度分数
func (d *DiagnosticEngine) calculateHealthScore(issues []Issue) float64 {
	score := 100.0
	for _, issue := range issues {
		switch issue.Severity {
		case "critical":
			score -= 30
		case "warning":
			score -= 10
		case "info":
			score -= 5
		}
	}
	if score < 0 {
		score = 0
	}
	return score
}
```

### 生产排障：eCPM 突然下降 50% 的案例

**场景**: 某电商 Campaign eCPM 从 15 元骤降到 7.5 元

**排查步骤**:
1. **确认时间范围**: Grafana 查看 eCPM 曲线，确认下降时间点
2. **拆解公式**: eCPM = CTR × CVR × targetCPA × 1000
3. **逐项检查**:
   - CTR: 从 2% → 1%（下降 50%）✓ 根因
   - CVR: 稳定在 5%
   - targetCPA: 未变更
4. **定位 CTR 下降原因**:
   - 对比创意数据：主图创意展示占比 80%，CTR 从 2.5% → 1.2%
   - 结论：创意疲劳
5. **解决方案**: 上传新创意 → CTR 恢复至 2.1% → eCPM 恢复至 14 元

**Go 验证代码**:
```go
// 快速验证 CTR 下降是否由特定创意引起
func diagnoseCreativeFatigue(ctx context.Context, campID string) {
	creatives := getCreatives(ctx, campID)
	for _, c := range creatives {
		ctr := c.impressions > 0 ? float64(c.clicks)/float64(c.impressions) : 0
		if c.impressions > 10000 && ctr < 0.01 {
			fmt.Printf("[FATIGUE] creative=%s impressions=%d ctr=%.4f\n",
				c.id, c.impressions, ctr)
		}
	}
}
```