# 广告技术人成长路线：面试题库/团队管理/商业思维

> 广告技术人的完整成长路径：从面试准备到团队管理到商业思维

---

## 第一部分：广告技术面试题库

### Go 语言

```
Q: Go 的 GMP 调度器是如何工作的？
A: G（goroutine）/ M（machine/thread）/ P（processor）。每个 P 维护一个 local runq，M 从 P 的 local runq 或 global runq 获取 G 执行。Work stealing：M 的 local runq 为空时，从其他 P 偷一半 G。

Q: Netpoller 的工作原理？
A: epoll/kqueue 监听 fd 事件。goroutine 阻塞时调用 gopark() 休眠，epoll 返回就绪事件时调用 goready() 唤醒。NetpollBreak pipe 用于强制唤醒 netpoll 循环。

Q: GC 是如何工作的？
A: 三色标记清除 + 写屏障。白色（未访问）→ 灰色（待扫描）→ 黑色（已扫描）。STW 阶段：标记开始 + 标记结束。并发阶段：后台扫描器。

Q: sync.Map 的使用场景？
A: 读多写少的场景。内部使用 readOnly + dirty + expunged 优化读取性能。
```

### 数据库

```
Q: MySQL 事务隔离级别有哪些？
A: Read Uncommitted / Read Committed / Repeatable Read（默认）/ Serializable。RR 通过 MVCC + Next-Key Lock 解决幻读。

Q: Redis 持久化机制？
A: RDB（快照，定期）+ AOF（日志，每秒/每次）。推荐 AOF everysec。

Q: Redis Cluster 如何分片？
A: CRC16(key) % 16384 确定槽位，16384 个槽位分布在多个 master。Gossip 协议同步拓扑。

Q: ClickHouse 为什么快？
A: 列式存储（只读需要的列）、向量化执行（SIMD）、数据压缩（LZ4/ZSTD）、物化视图（预聚合）。
```

### 广告系统

```
Q: RTB 竞价流程是怎样的？
A: 用户访问页面 → SSP 发送 BidRequest → Exchange 广播 → DSP 计算出价 → 返回 BidResponse → Exchange 选出最高价 → 展示广告。

Q: 什么是 Second Price Auction？
A: 最高出价者赢得竞价，但支付第二高出价。激励 DSP 按真实估值出价。

Q: 如何防止广告作弊？
A: 设备指纹 + 行为分析 + 图神经网络 + 实时风控引擎。

Q: 归因模型有哪些？
A: Last Click / First Click / Linear / Time Decay / Position Based / MTA / Shapley Value / 马尔可夫链。
```

---

## 第二部分：团队管理

### 技术团队管理框架

```
TL 带 9 人团队的管理框架：
┌─────────────────────────────────────────────────────────────────────┐
│ 管理维度：                                                          │
│                                                                     │
│ 1. 目标管理（OKR）                                                  │
│    • O: 提升广告系统性能 30%                                        │
│    • KR1: P99 延迟从 100ms 降到 70ms                                │
│    • KR2: QPS 从 50K 提升到 80K                                     │
│    • KR3: 故障率降低 50%                                            │
│                                                                     │
│ 2. 人员管理                                                         │
│    • 技能矩阵：评估每个成员的技能水平                                 │
│    • 成长计划：为每人制定 6-12 个月成长计划                           │
│    • 1:1 沟通：每周 30 分钟一对一                                    │
│                                                                     │
│ 3. 项目管理                                                         │
│    • Sprint 规划：2 周一个 sprint                                   │
│    • 每日站会：15 分钟同步进度                                       │
│    • Sprint Review：演示成果，收集反馈                               │
│    • Retrospective：复盘改进                                         │
│                                                                     │
│ 4. 技术管理                                                         │
│    • 技术选型：评估新技术的利弊                                       │
│    • Code Review：保证代码质量                                       │
│    • 技术债务：定期清理                                               │
│    • 知识分享：每周技术分享                                          │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 第三部分：商业思维

### ROI 分析框架

```
广告系统 ROI 分析：
┌─────────────────────────────────────────────────────────────────────┐
│ 收入侧：                                                            │
│ • 广告收入 = 展示量 × CPM / 1000                                    │
│ • 点击收入 = 点击量 × CPC                                           │
│ • 转化收入 = 转化量 × CPA                                           │
│                                                                     │
│ 成本侧：                                                            │
│ • 基础设施成本：服务器/带宽/存储                                      │
│ • 技术成本：人力/工具/云服务                                         │
│ • 获客成本：CAC                                                     │
│                                                                     │
│ ROI = (收入 - 成本) / 成本 × 100%                                   │
│                                                                     │
│ 优化方向：                                                          │
│ 1. 提升填充率 → 增加收入                                            │
│ 2. 提升 CTR → 增加点击收入                                          │
│ 3. 降低基础设施成本 → 降低成本                                       │
│ 4. 优化获客渠道 → 降低 CAC                                          │
└─────────────────────────────────────────────────────────────────────┘
```

### LTV/CAC 分析

```
LTV（用户终身价值）= ARPU × 毛利率 / 流失率
CAC（获客成本）= 营销费用 / 新增用户数

LTV/CAC > 3: 健康
LTV/CAC < 1: 危险

广告平台 LTV 计算：
LTV = Σ (每月 ARPU × 折扣因子^月数) 直到用户流失
ARPU = 广告收入 / DAU
```

---

## 第四部分：自测题

### Q1: 如何评估一个技术团队成员的水平？

**A**: 从四个维度：技术深度（能否解决复杂问题）、工程能力（代码质量/效率）、沟通能力（表达/协作）、影响力（分享/指导他人）。

### Q2: OKR 和 KPI 的区别？

**A**: OKR 关注目标和关键结果（定性+定量），鼓励挑战；KPI 关注关键绩效指标（定量），侧重考核。OKR 更适合创新项目。

### Q3: 如何计算广告平台的 ROI？

**A**: ROI = (广告收入 - 运营成本) / 运营成本。优化方向：提升填充率/CTR、降低基础设施成本、优化获客渠道。

---

## 第五部分：成长建议

### 1. 技术成长

```
每周学习建议：
• 阅读源码/论文：20%
• 动手实践：30%
• 输出文档/博客：30%
• 交流分享：20%
```

### 2. 管理能力

```
TL 成长路径：
• IC → TL（带 3-5 人）→ Senior TL（带 9-15 人）→ 总监
• 关键能力：目标管理、人员培养、技术决策、跨部门协作
```

### 3. 商业思维

```
商业思维培养：
• 理解商业模式：广告平台怎么赚钱
• 数据分析：用数据驱动决策
• 成本意识：关注 ROI
• 市场洞察：关注行业趋势
```

---

## Go 代码实战：技术团队管理工具

### 1. OKR 追踪系统

```go
package okrsystem

import (
	"context"
	"fmt"
	"sync"
	"time"
)

// Objective 目标
type Objective struct {
	ID          string
	Title       string
	Description string
	OwnerID     string
	KeyResults  []KeyResult
	DueDate     time.Time
	Status      string // not_started, in_progress, on_track, at_risk, completed
}

// KeyResult 关键结果
type KeyResult struct {
	ID         string
	Title      string
	CurrentValue float64
	TargetValue  float64
	Unit       string
	Progress   float64 // 0-1
}

// TeamOKR 团队 OKR 追踪器
type TeamOKR struct {
	objectives map[string]*Objective
	mu         sync.RWMutex
}

func NewTeamOKR() *TeamOKR {
	return &TeamOKR{objectives: make(map[string]*Objective)}
}

func (t *TeamOKR) AddObjective(obj *Objective) {
	t.mu.Lock()
	defer t.mu.Unlock()
	
	for i := range obj.KeyResults {
		if obj.KeyResults[i].TargetValue > 0 {
			obj.KeyResults[i].Progress = obj.KeyResults[i].CurrentValue / obj.KeyResults[i].TargetValue
		}
	}
	
	t.objectives[obj.ID] = obj
}

func (t *TeamOKR) GetTeamProgress(ctx context.Context) map[string]float64 {
	t.mu.RLock()
	defer t.mu.RUnlock()
	
	progress := make(map[string]float64)
	
	for _, obj := range t.objectives {
		if len(obj.KeyResults) == 0 {
			continue
		}
		
		totalProgress := 0.0
		for _, kr := range obj.KeyResults {
			totalProgress += kr.Progress
		}
		progress[obj.ID] = totalProgress / float64(len(obj.KeyResults))
	}
	
	return progress
}

func (t *TeamOKR) GetAtRiskObjectives() []*Objective {
	t.mu.RLock()
	defer t.mu.RUnlock()
	
	var atRisk []*Objective
	for _, obj := range t.objectives {
		if obj.Status == "in_progress" {
			progress := t.getObjectiveProgress(obj)
			if progress < 0.5 && time.Since(obj.DueDate) > 0 {
				atRisk = append(atRisk, obj)
			}
		}
	}
	return atRisk
}

func (t *TeamOKR) getObjectiveProgress(obj *Objective) float64 {
	if len(obj.KeyResults) == 0 {
		return 0
	}
	sum := 0.0
	for _, kr := range obj.KeyResults {
		sum += kr.Progress
	}
	return sum / float64(len(obj.KeyResults))
}
```

### 2. Code Review 评分系统

```go
package codereview

import (
	"strings"
)

// ReviewCriteria 评审标准
type ReviewCriteria struct {
	Name        string
	Weight      float64
	CheckFunc   func(*ReviewContext) float64
}

type ReviewContext struct {
	Code        string
	PRTitle     string
	PRDesc      string
	Files       []string
	Comments    int
	Approvals   int
	RequestChng int
}

// Scorer 评分器
type Scorer struct {
	criteria []ReviewCriteria
}

func NewScorer() *Scorer {
	return &Scorer{
		criteria: []ReviewCriteria{
			{Name: "correctness", Weight: 0.3, CheckFunc: checkCorrectness},
			{Name: "performance", Weight: 0.2, CheckFunc: checkPerformance},
			{Name: "readability", Weight: 0.2, CheckFunc: checkReadability},
			{Name: "testing", Weight: 0.15, CheckFunc: checkTesting},
			{Name: "security", Weight: 0.15, CheckFunc: checkSecurity},
		},
	}
}

func (s *Scorer) Score(ctx *ReviewContext) (float64, map[string]float64) {
	breakdown := make(map[string]float64)
	total := 0.0
	
	for _, c := range s.criteria {
		score := c.CheckFunc(ctx)
		breakdown[c.Name] = score
		total += score * c.Weight
	}
	
	return total, breakdown
}

func checkCorrectness(ctx *ReviewContext) float64 {
	score := 1.0
	if ctx.RequestChng > 5 {
		score -= 0.3
	}
	if strings.Contains(strings.ToLower(ctx.PRDesc), "fix bug") {
		score -= 0.1
	}
	return max(score, 0)
}

func checkPerformance(ctx *ReviewContext) float64 {
	score := 1.0
	if strings.Contains(ctx.Code, "for range") && strings.Contains(ctx.Code, "append") {
		score -= 0.2 // 可能 O(n²)
	}
	return max(score, 0)
}

func checkReadability(ctx *ReviewContext) float64 {
	score := 1.0
	lines := strings.Split(ctx.Code, "\n")
	if len(lines) > 300 {
		score -= 0.3 // 文件太大
	}
	return max(score, 0)
}

func checkTesting(ctx *ReviewContext) float64 {
	score := 0.0
	if ctx.RequestChng == 0 && ctx.Approvals >= 1 {
		score = 1.0
	} else if ctx.RequestChng > 0 {
		score = 0.5
	}
	return score
}

func checkSecurity(ctx *ReviewContext) float64 {
	score := 1.0
	badPatterns := []string{"exec.Command", "eval(", "innerHTML"}
	for _, pattern := range badPatterns {
		if strings.Contains(ctx.Code, pattern) {
			score -= 0.3
		}
	}
	return max(score, 0)
}
```

### 自测题

<details>
<summary>Q1: OKR 系统中为什么用 Progress = Current/Target 而不是手动更新？</summary>

**答案**：

**自动化优势**：
1. 减少人为偏差（主观打分）
2. 实时反映真实进度
3. 数据驱动决策

但有些 KR 无法量化（如"提升团队士气"），需要结合主观评估。生产环境用 **定量 + 定性** 混合模式。

</details>

<details>
<summary>Q2: Code Review 评分中为什么 correctness 权重最高（0.3）？</summary>

**答案**：

**Bug 的成本曲线**：
```
发现阶段    修复成本
设计阶段     $1
编码阶段     $10
测试阶段     $100
生产环境     $1000+
```

正确性错误一旦流入生产，修复成本是其他问题的10-100倍。所以 correctness 权重必须最高。

</details>

<details>
<summary>Q3: Scorer 的 CheckFunc 为什么返回 0-1 而不是百分制？</summary>

**答案**：

**归一化好处**：
1. 加权求和时不需要额外换算
2. 不同维度的分数可以直接比较
3. 输出总分也是 0-1，直观理解

生产环境可以映射到百分制：`score * 100`。

</details>
