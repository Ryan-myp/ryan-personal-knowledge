# 广告技术人成长路线：从入门到架构师

> 基于广告技术栈的完整学习路径，覆盖竞价/排序/Agent/架构

---

## 第一部分：广告技术能力矩阵

```
广告技术人才四维度：
┌─────────────────────────────────────────────────────────────────────┐
│ 1. 技术深度（Technical Depth）                                       │
│    • Go/Python 语言级                                                │
│    • MySQL/Redis/ClickHouse 源码级                                   │
│    • Linux 内核级                                                    │
│    • 高并发/分布式系统设计                                            │
│                                                                     │
│ 2. 广告领域（Advertising Domain）                                    │
│    • RTB/竞价/排序/归因                                             │
│    • 多平台 API（Meta/Google/TikTok/DV360）                          │
│    • 广告协议（OpenRTB/TCF/Privacy Sandbox）                         │
│    • 反欺诈/合规                                                     │
│                                                                     │
│ 3. AI/Agent（AI & Agent）                                          │
│    • 推荐系统（召回/排序/重排）                                      │
│    • 深度学习（DeepFM/DIN/MMOE）                                     │
│    • Agent 编排（MCP/技能系统/图编排）                               │
│    • NL2AD/对话式广告                                               │
│                                                                     │
│ 4. 架构与领导力（Architecture & Leadership）                        │
│    • 系统架构设计                                                    │
│    • 高可用/高并发/容灾                                              │
│    • 团队管理/技术影响力                                             │
│    • 商业思维                                                        │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 第二部分：学习路线图

### Phase 1: 基础夯实（0-6 个月）

```
目标：掌握广告系统核心技术栈

技术栈：
• Go 语言：并发编程/网络编程
• MySQL：索引优化/事务/锁
• Redis：数据结构/持久化/集群
• Linux：系统调用/性能调优
• HTTP/HTTPS：协议基础

广告基础：
• 广告术语：CPM/CPC/CPA/CTR/CVR/ROAS
• 广告流程：展示→点击→转化→归因
• 广告平台：Meta Ads/Google Ads/TikTok Ads

学习资源：
• 《Go 语言圣经》
• 《MySQL 技术内幕》
• Redis 官方文档
• 广告平台官方文档
```

### Phase 2: 进阶提升（6-18 个月）

```
目标：深入广告核心技术

技术栈：
• Kafka：消息队列/事件流
• ClickHouse：列式数据库/数仓
• Elasticsearch：搜索引擎
• Docker/K8s：容器化/编排

广告进阶：
• RTB 竞价流程
• 多路召回/排序模型
• A/B 测试/实验设计
• 广告归因模型

学习资源：
• 《Kafka 权威指南》
• ClickHouse 官方文档
• 《推荐系统实战》
• 广告平台 API 文档
```

### Phase 3: 专家突破（18-36 个月）

```
目标：成为广告技术专家

技术栈：
• 分布式系统：一致性/分片/容错
• 深度学习：PyTorch/TensorFlow
• 大数据：Spark/Flink
• 可观测性：OTel/Prometheus/Grafana

广告专家：
• 竞价策略优化（RL/Bandit）
• 排序模型（DeepFM/DIN/MMOE）
• 多平台 API 集成
• 反欺诈/GNN

学习资源：
• 《Designing Data-Intensive Applications》
• 《Deep Learning》(Goodfellow)
• Spark 官方文档
• 论文阅读（SIGIR/KDD/WWW）
```

### Phase 4: 架构师（3-5 年）

```
目标：系统架构师/技术负责人

技术栈：
• 云原生：Service Mesh/Istio
• 多活容灾：跨区域部署
• 成本优化：Spot 实例/Reserved
• 安全合规：GDPR/CCPA

架构能力：
• 系统架构设计
• 团队管理
• 技术选型
• 跨部门协作

领导力：
• 技术影响力（演讲/开源/专利）
• 商业思维（ROI/成本/收益）
• 人才培养（mentorship）
```

---

## 第三部分：技能评估

### 自评量表

```
技能等级：
1. 了解（Awareness）：知道是什么，能解释基本概念
2. 会用（Proficient）：能在项目中实际应用
3. 精通（Expert）：能解决复杂问题，优化性能
4. 专家（Authority）：能设计架构，指导他人

示例：Go 网络编程
• Level 1：知道 net/http 的基本用法
• Level 2：能用 net/http 构建 REST API
• Level 3：理解 Netpoller 源码，能优化高并发
• Level 4：能设计新的网络框架
```

### 面试准备

```
高频面试题：
1. Go 相关：
   • GMP 调度器工作原理
   • Netpoller 实现细节
   • GC 机制和调优
   • 内存分配器设计

2. 数据库：
   • MySQL InnoDB 事务隔离级别
   • Redis 持久化机制
   • ClickHouse 查询优化

3. 广告系统：
   • RTB 竞价流程
   • 排序模型选型
   • 高并发设计

4. 系统设计：
   • 设计一个广告系统
   • 如何保证数据一致性
   • 如何做容灾设计
```

---

## 第四部分：自测题

### Q1: 广告技术人应该优先学习什么？

**A**: 先打好 Go/MySQL/Redis 基础，再深入广告领域知识（竞价/排序/归因），最后学习 AI/Agent 和架构设计。

### Q2: 如何衡量学习效果？

**A**: 
1. 能独立完成广告系统模块开发
2. 能通过面试
3. 能在生产中解决复杂问题
4. 能指导他人

### Q3: 广告技术人的核心竞争力是什么？

**A**: 技术深度 + 广告领域知识 + AI/Agent 能力 + 架构设计能力的组合。单纯的技术或单纯的广告知识都不够，需要跨界整合。

---

## 第五部分：生产实践

### 1. 学习计划

```
每周学习建议：
• 20% 时间：阅读源码/论文
• 30% 时间：动手实践（写代码/搭环境）
• 30% 时间：输出（写文档/博客）
• 20% 时间：交流（讨论/分享）
```

### 2. 资源推荐

```
书籍：
• 《Go 语言设计与实现》
• 《MySQL 技术内幕》
• 《Redis 设计与实现》
• 《Designing Data-Intensive Applications》
• 《推荐系统实战》

课程：
• Coursera: Machine Learning (Andrew Ng)
• Udemy: Go 语言实战
• B 站: 广告技术系列

论文：
• DeepFM (SIGIR 2017)
• DIN (KDD 2018)
• MMOE (KDD 2018)
• PLE (KDD 2020)
```

### 3. 成长里程碑

```
里程碑检查：
□ 能独立开发广告系统模块
□ 能优化数据库查询性能
□ 能设计高并发系统
□ 能使用 ClickHouse 做数据分析
□ 能部署和维护 K8s 集群
□ 能设计广告排序模型
□ 能实现 NL2AD 功能
□ 能设计多活容灾架构
□ 能指导团队成员成长
□ 能在技术会议上分享
```

## 六、Go 源码级实现：技术能力评估系统

### 6.1 技能矩阵评估器

```go
package career

import (
	"fmt"
	"sync"
	"time"
)

// SkillLevel 技能等级
type SkillLevel int

const (
	Basic SkillLevel = iota
	Intermediate
	Advanced
	Expert
	ThoughtLeader
)

func (s SkillLevel) String() string {
	names := map[SkillLevel]string{
		Basic: "基础", Intermediate: "进阶", Advanced: "高级",
		Expert: "专家", ThoughtLeader: "思想领袖",
	}
	return names[s]
}

// Competency 能力维度
type Competency struct {
	ID          string
	Name        string
	Description string
	Categories  []SkillCategory
}

// SkillCategory 技能分类
type SkillCategory struct {
	Name      string
	Skills    []Skill
	TargetLevel SkillLevel
}

// Skill 具体技能
type Skill struct {
	Name        string
	CurrentLevel SkillLevel
	TargetLevel  SkillLevel
	Evidence     []Evidence
	LastUpdated  time.Time
}

// Evidence 证据
type Evidence struct {
	Type   string // project, article, talk, patent, code_review
	Title  string
	Date   time.Time
	Link   string
	Impact float64 // 0-100
}

// SkillMatrix 技能矩阵
type SkillMatrix struct {
	mu         sync.RWMutex
	skills     map[string]*Skill
	competencies map[string]*Competency
	userID     string
}

// NewSkillMatrix 创建技能矩阵
func NewSkillMatrix(userID string) *SkillMatrix {
	return &SkillMatrix{
		skills:       make(map[string]*Skill),
		competencies: make(map[string]*Competency),
		userID:       userID,
	}
}

// AddSkill 添加技能
func (sm *SkillMatrix) AddSkill(skill *Skill) error {
	sm.mu.Lock()
	defer sm.mu.Unlock()
	
	if skill.Name == "" {
		return fmt.Errorf("skill name is required")
	}
	
	sm.skills[skill.Name] = skill
	skill.LastUpdated = time.Now()
	
	return nil
}

// AddEvidence 添加工匠证据
func (sm *SkillMatrix) AddEvidence(skillName string, evidence Evidence) error {
	sm.mu.Lock()
	defer sm.mu.Unlock()
	
	skill, ok := sm.skills[skillName]
	if !ok {
		return fmt.Errorf("skill %s not found", skillName)
	}
	
	evidence.Type = "code_review" // 默认类型
	evidence.Date = time.Now()
	skill.Evidence = append(skill.Evidence, evidence)
	skill.LastUpdated = time.Now()
	
	return nil
}

// GetGap 计算技能差距
func (sm *SkillMatrix) GetGap(skillName string) *SkillGap {
	sm.mu.RLock()
	defer sm.mu.RUnlock()
	
	skill, ok := sm.skills[skillName]
	if !ok {
		return &SkillGap{SkillName: skillName, Missing: true}
	}
	
	levelDiff := int(skill.TargetLevel) - int(skill.CurrentLevel)
	progress := float64(skill.CurrentLevel) / float64(skill.TargetLevel)
	
	return &SkillGap{
		SkillName:    skillName,
		CurrentLevel: skill.CurrentLevel,
		TargetLevel:  skill.TargetLevel,
		LevelDiff:    levelDiff,
		Progress:     progress,
		Missing:      false,
	}
}

// SkillGap 技能差距
type SkillGap struct {
	SkillName    string
	CurrentLevel SkillLevel
	TargetLevel  SkillLevel
	LevelDiff    int
	Progress     float64
	Missing      bool
}

// OverallProgress 整体进度
type OverallProgress struct {
	TotalSkills    int
	AchievedSkills int
	OverallScore   float64
	ByCategory     map[string]float64
	WeakPoints     []string
	StrongPoints   []string
}

// CalculateProgress 计算整体进度
func (sm *SkillMatrix) CalculateProgress() *OverallProgress {
	sm.mu.RLock()
	defer sm.mu.RUnlock()
	
	progress := &OverallProgress{
		ByCategory: make(map[string]float64),
	}
	
	var totalScore, categoryScore float64
	var categoryCount, categoryAchieved int
	
	for name, skill := range sm.skills {
		totalScore += float64(skill.CurrentLevel)
		maxScore := float64(skill.TargetLevel)
		if maxScore > 0 {
			categoryScore += float64(skill.CurrentLevel) / maxScore
			categoryCount++
		}
		
		if skill.CurrentLevel >= skill.TargetLevel {
			progress.AchievedSkills++
			progress.StrongPoints = append(progress.StrongPoints, name)
		} else if int(skill.TargetLevel)-int(skill.CurrentLevel) >= 2 {
			progress.WeakPoints = append(progress.WeakPoints, name)
		}
	}
	
	progress.TotalSkills = len(sm.skills)
	if categoryCount > 0 {
		progress.OverallScore = categoryScore / float64(categoryCount) * 100
	}
	
	return progress
}

// LearningPlan 学习计划
type LearningPlan struct {
	UserID      string
	CreatedAt   time.Time
	Tasks       []LearningTask
	Priority    string // high, medium, low
	Duration    time.Duration
}

// LearningTask 学习任务
type LearningTask struct {
	TaskID    string
	Title     string
	SkillName string
	Type      string // read, practice, project, mentor
	Duration  time.Duration
	Resources []string
	DueDate   time.Time
	Completed bool
}

// GeneratePlan 生成学习计划
func (sm *SkillMatrix) GeneratePlan(days int) *LearningPlan {
	plan := &LearningPlan{
		UserID:   sm.userID,
		CreatedAt: time.Now(),
		Duration: time.Duration(days) * 24 * time.Hour,
	}
	
	// 按差距排序
	type gapInfo struct {
		name   string
		diff   int
		skill  *Skill
	}
	
	var gaps []gapInfo
	for name, skill := range sm.skills {
		diff := int(skill.TargetLevel) - int(skill.CurrentLevel)
		if diff > 0 {
			gaps = append(gaps, gapInfo{name, diff, skill})
		}
	}
	
	// 按差距大小排序（优先补最大差距）
	for i := 0; i < len(gaps); i++ {
		for j := i + 1; j < len(gaps); j++ {
			if gaps[j].diff > gaps[i].diff {
				gaps[i], gaps[j] = gaps[j], gaps[i]
			}
		}
	}
	
	// 为每个差距生成学习任务
	for _, g := range gaps {
		task := LearningTask{
			TaskID:    fmt.Sprintf("task_%s", g.name),
			Title:     fmt.Sprintf("提升 %s 到 %s", g.name, g.skill.TargetLevel),
			SkillName: g.name,
			Type:      "read",
			Duration:  time.Duration(g.diff*30) * 24 * time.Hour,
			DueDate:   time.Now().Add(time.Duration(g.diff*30) * 24 * time.Hour),
		}
		plan.Tasks = append(plan.Tasks, task)
	}
	
	return plan
}
```

### 6.2 面试模拟系统

```go
package career

import (
	"math/rand"
	"strings"
	"sync"
	"time"
)

// InterviewQuestion 面试题目
type InterviewQuestion struct {
	ID        string
	Category  string // go, mysql, redis, ads, architecture
	Difficulty int    // 1-5
	Question  string
	Answer    string
	KeyPoints []string
	FollowUp  []string
}

// InterviewSession 面试会话
type InterviewSession struct {
	SessionID  string
	StartTime  time.Time
	Questions  []InterviewQuestion
	Answers    []AnswerRecord
	Scorer     *InterviewScorer
}

// AnswerRecord 回答记录
type AnswerRecord struct {
	QuestionID string
	Answer     string
	Score      float64
	Feedback   string
	Timestamp  time.Time
}

// InterviewScorer 面试评分器
type InterviewScorer struct {
	mu         sync.Mutex
	questions  map[string][]InterviewQuestion
	difficultyWeights map[int]float64
}

// NewInterviewScorer 创建评分器
func NewInterviewScorer() *InterviewScorer {
	return &InterviewScorer{
		questions: make(map[string][]InterviewQuestion),
		difficultyWeights: map[int]float64{
			1: 0.4, 2: 0.6, 3: 0.8, 4: 0.9, 5: 1.0,
		},
	}
}

// AddQuestions 添加题库
func (is *InterviewScorer) AddQuestions(qs []InterviewQuestion) {
	is.mu.Lock()
	defer is.mu.Unlock()
	
	for _, q := range qs {
		is.questions[q.Category] = append(is.questions[q.Category], q)
	}
}

// GenerateInterview 生成面试题目
func (is *InterviewScorer) GenerateInterview(categories []string, count int, difficulty int) []InterviewQuestion {
	is.mu.Lock()
	defer is.mu.Unlock()
	
	var selected []InterviewQuestion
	
	for _, cat := range categories {
		questions := is.questions[cat]
		if len(questions) == 0 {
			continue
		}
		
		// 按难度筛选
		var filtered []InterviewQuestion
		for _, q := range questions {
			if q.Difficulty == difficulty || q.Difficulty == difficulty+1 {
				filtered = append(filtered, q)
			}
		}
		
		if len(filtered) > 0 {
			selected = append(selected, filtered[rand.Intn(len(filtered))])
		}
	}
	
	// 限制数量
	if len(selected) > count {
		selected = selected[:count]
	}
	
	return selected
}

// ScoreAnswer 评分回答
func (is *InterviewScorer) ScoreAnswer(question InterviewQuestion, answer string) *ScoreResult {
	result := &ScoreResult{
		QuestionID: question.ID,
		Keywords:   make(map[string]bool),
	}
	
	answerLower := strings.ToLower(answer)
	keyPointsLower := make([]string, len(question.KeyPoints))
	for i, kp := range question.KeyPoints {
		keyPointsLower[i] = strings.ToLower(kp)
	}
	
	// 关键词匹配
	for _, kp := range keyPointsLower {
		if strings.Contains(answerLower, kp) {
			result.Keywords[kp] = true
			result.ScoredKeywords++
		}
	}
	
	// 长度评分（答案不能太短）
	wordCount := len(strings.Fields(answer))
	if wordCount < 20 {
		result.Score *= 0.5
		result.Feedback = "回答过于简短，需要更详细的解释"
	} else if wordCount > 200 {
		result.Score *= 1.1
	}
	
	// 难度权重
	result.Score *= is.difficultyWeights[question.Difficulty]
	
	// 归一化
	if result.Score > 100 {
		result.Score = 100
	}
	
	return result
}

// ScoreResult 评分结果
type ScoreResult struct {
	QuestionID    string
	Score         float64
	KeyPoints     []string
	ScoredKeywords int
	Keywords      map[string]bool
	Feedback      string
}

// InterviewReport 面试报告
type InterviewReport struct {
	SessionID  string
	StartTime  time.Time
	EndTime    time.Time
	TotalScore float64
	ByCategory map[string]float64
	WeakAreas  []string
	Strengths  []string
	Advice     []string
}

// GenerateReport 生成面试报告
func (is *InterviewScorer) GenerateReport(session *InterviewSession) *InterviewReport {
	report := &InterviewReport{
		SessionID:  session.SessionID,
		StartTime:  session.StartTime,
		EndTime:    time.Now(),
		ByCategory: make(map[string]float64),
	}
	
	var totalScore float64
	var categoryScores map[string][]float64
	
	for _, record := range session.Answers {
		totalScore += record.Score
		
		if categoryScores == nil {
			categoryScores = make(map[string][]float64)
		}
		
		// 简化：从问题中获取类别
		for _, q := range session.Questions {
			categoryScores[q.Category] = append(categoryScores[q.Category], record.Score)
		}
	}
	
	report.TotalScore = totalScore / float64(len(session.Answers))
	
	// 按类别统计
	for cat, scores := range categoryScores {
		sum := 0.0
		for _, s := range scores {
			sum += s
		}
		report.ByCategory[cat] = sum / float64(len(scores))
	}
	
	// 找出薄弱环节
	for cat, score := range report.ByCategory {
		if score < 60 {
			report.WeakAreas = append(report.WeakAreas, cat)
		} else {
			report.Strengths = append(report.Strengths, cat)
		}
	}
	
	// 生成建议
	report.Advice = is.generateAdvice(report)
	
	return report
}

func (is *InterviewScorer) generateAdvice(report *InterviewReport) []string {
	var advice []string
	
	for _, weak := range report.WeakAreas {
		advice = append(advice, fmt.Sprintf("建议加强 %s 方面的学习", weak))
	}
	
	if len(advice) == 0 {
		advice = append(advice, "各项能力均衡，继续保持！")
	}
	
	return advice
}

## 七、自测题

### Q1: 技能矩阵中，如何客观评估一个人的技能等级？证据收集有哪些维度？

<details>
<summary>查看答案</summary>

**答案：**

技能等级评估标准：
| 等级 | 标准 | 典型行为 |
|------|------|----------|
| Basic | 了解概念 | 能阅读代码，理解基本逻辑 |
| Intermediate | 独立使用 | 能独立完成中等复杂度任务 |
| Advanced | 优化改进 | 能优化性能，解决复杂问题 |
| Expert | 设计架构 | 能设计系统架构，指导他人 |
| ThoughtLeader | 行业影响 | 有技术影响力，输出行业观点 |

证据收集维度：
1. **项目贡献**：PR review、代码质量、bug 率
2. **技术文章**：博客、内部分享、专利
3. **技术演讲**：技术大会、团队分享
4. **代码审查**：review 他人代码的质量和深度
5. **mentorship**：指导他人的效果

Go 实现要点：
- 使用 Evidence 结构体记录每种证据
- Impact 字段量化影响力（0-100）
- CalculateProgress 按加权平均计算整体进度

</details>

### Q2: 面试模拟系统中，关键词匹配评分有什么局限性？如何改进？

<details>
<summary>查看答案</summary>

**答案：**

关键词匹配的局限性：
1. **同义词遗漏**：回答用了"哈希表"但期望词是"hash map"
2. **上下文无关**：关键词出现不代表理解正确
3. **过度依赖长度**：长回答不一定好，短回答可能更精准
4. **无法评估深度**：只检查表面关键词，不验证逻辑正确性

改进方案：
1. **语义相似度**：用向量嵌入计算余弦相似度（需要 ML 模型）
2. **结构化评分**：将答案拆解为多个维度分别评分
3. **Rubric 评分**：预先定义每个关键点的评分标准
4. **人工复核**：AI 初筛 + 专家复核

生产实践：Google/Meta 的面试系统都采用结构化评分 rubric，而不是简单的关键词匹配。

</details>

### Q3: 从 TL 到专家工程师的成长路径中，最关键的转变是什么？如何衡量是否完成了这个转变？

<details>
<summary>查看答案</summary>

**答案：**

最关键转变：
1. **个人贡献 → 团队杠杆**：从自己写代码到让团队产出 10x
2. **执行 → 决策**：从"怎么做"到"做什么/为什么做"
3. **技术 → 商业**：从技术最优到商业价值最优
4. **局部 → 全局**：从模块视角到系统/业务视角

衡量标准：
- **技术深度**：能否深入源码级理解（Go runtime、编译器优化）
- **架构设计**：能否独立设计高并发/高可用系统
- **广告 API 精通**：对 DSP/SSP/Ad Exchange 的深刻理解
- **技术领导力**：能否带团队交付复杂项目

成长路线图验证：
- P5→P6：独立负责模块
- P6→P7：独立负责系统
- P7→P8：跨系统架构设计
- P8→P9：技术战略规划

</details>
