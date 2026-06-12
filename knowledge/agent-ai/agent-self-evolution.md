# Agent 自进化：四类闭环与代表项目

> 基于 Datawhale hello-agents Extra10 社区贡献整理

---

## 第一部分：入门引导（5 分钟速览）

### 什么是 Agent 自进化？

> 自进化 Agent 是一种能够依据自身交互轨迹、任务反馈、用户纠正、工具执行结果、群体经验等信号，对上下文、记忆、技能、工具、工作流、代码或模型参数进行持续更新，并让这些更新影响未来任务表现的智能体系统。

三个关键点：
1. **经验驱动**：更新来自真实任务、执行反馈、用户纠错
2. **持续生效**：更新会进入记忆、技能库、工作流，持续发挥作用
3. **可评估、可回滚**：越强的自进化越需要评估器和回滚机制

### 四类闭环总览

| 类型 | 代表项目 | 更新对象 | 风险等级 |
|------|---------|---------|---------|
| **内建上下文闭环** | Hermes Agent, Agent Zero | 记忆/会话/技能 | 🟢 低 |
| **技能资产化闭环** | Darwin Skill, JiuwenClaw, EvoSkill | SKILL.md 资产 | 🟡 中 |
| **外部监督/群体智能** | Ultron, OpenSpace, SkillClaw | 共享技能库 | 🟠 中高 |
| **参数/代码自修改** | OpenClaw-RL, Agent Lightning | 模型权重/代码 | 🔴 高 |

---

## 第二部分：源码级深度

### 2.1 内建上下文闭环 — Go 实现

```go
package selfevolution

// 内建上下文闭环：让 Agent 在自己的主循环里学习
// 不直接修改模型参数，而是让 Agent 把经验写入记忆、反思文本、会话索引

type InternalLoop struct {
	Memory    *MemoryEngine    // 持久记忆
	Skills    *SkillEngine     // 技能管理
	Session   *SessionManager  // 会话管理
}

// MemoryEngine 持久记忆引擎
type MemoryEngine struct {
	ShortTerm map[string]string  // 短期记忆（当前会话）
	LongTerm  *VectorDB         // 长期记忆（向量数据库）
	Episodic  []Episode         // 情景记忆（任务轨迹）
}

// Episode 情景记忆：一次完整的任务轨迹
type Episode struct {
	EpisodeID   string
	Timestamp   time.Time
	Query       string
	Steps       []Step
	Outcome     string
	Score       float64
	Feedback    string
}

// Step ReAct 循环中的一步
type Step struct {
	Thought     string
	Action      string
	Observation string
}

// LearnFromFeedback 从用户反馈中学习
func (m *MemoryEngine) LearnFromFeedback(query, feedback string, score float64) {
	// 1. 记录到情景记忆
	episode := Episode{
		Timestamp: time.Now(),
		Query:     query,
		Score:     score,
		Feedback:  feedback,
	}
	
	// 2. 提取关键经验
	insights := m.ExtractInsights(query, feedback, score)
	
	// 3. 更新长期记忆
	for _, insight := range insights {
		m.LongTerm.Add(insight)
	}
	
	// 4. 如果反馈很负面，标记为负面案例
	if score < 0.5 {
		m.NegativeCases = append(m.NegativeCases, episode)
	}
	
	// 5. 如果反馈很好，标记为正面案例
	if score > 0.8 {
		m.PositiveCases = append(m.PositiveCases, episode)
	}
}

// ExtractInsights 从反馈中提取关键经验
func (m *MemoryEngine) ExtractInsights(query, feedback string, score float64) []Insight {
	// 这里可以用 LLM 来分析反馈
	// 简化版：基于关键词提取
	var insights []Insight
	
	if score < 0.5 {
		// 负面反馈，提取问题
		insights = append(insights, Insight{
			Type:      "failure",
			Query:     query,
			Feedback:  feedback,
			Severity:  "high",
		})
	} else if score > 0.8 {
		// 正面反馈，提取成功模式
		insights = append(insights, Insight{
			Type:      "success",
			Query:     query,
			Feedback:  feedback,
			Pattern:   "good_response",
		})
	}
	
	return insights
}

// QueryMemory 查询记忆
func (m *MemoryMemory) QueryMemory(query string) []Memory {
	// 1. 短期记忆（当前会话）
	var results []Memory
	for k, v := range m.ShortTerm {
		results = append(results, Memory{Key: k, Value: v})
	}
	
	// 2. 长期记忆（向量检索）
	vectorResults := m.LongTerm.Search(query, 10)
	
	// 3. 合并结果
	return append(results, vectorResults...)
}
```

### 2.2 技能资产化闭环 — Go 实现

```go
package selfevolution

// 技能资产化闭环：让经验沉淀为可复用 Skill
// Darwin Skill：把 SKILL.md 当作可评测、可回滚的资产

type SkillAsset struct {
	Name        string
	Version     string
	CreatedAt   time.Time
	Content     string
	EvalScore   *float64 // 评估得分
}

type SkillRegistry struct {
	skills map[string][]*SkillAsset
}

// CreateSkill 创建新 Skill
func (r *SkillRegistry) CreateSkill(name, content string) (*SkillAsset, error) {
	version := fmt.Sprintf("v%d", len(r.skills[name])+1)
	skill := &SkillAsset{
		Name:      name,
		Version:   version,
		CreatedAt: time.Now(),
		Content:   content,
	}
	
	r.skills[name] = append(r.skills[name], skill)
	return skill, nil
}

// EvaluateSkill 评估 Skill 质量
func (r *SkillRegistry) EvaluateSkill(name, version string, score float64) error {
	for _, s := range r.skills[name] {
		if s.Version == version {
			s.EvalScore = &score
			return nil
		}
	}
	return fmt.Errorf("skill %s version %s not found", name, version)
}

// BestVersion 获取最佳版本
func (r *SkillRegistry) BestVersion(name string) *SkillAsset {
	var best *SkillAsset
	bestScore := -1.0
	
	for _, s := range r.skills[name] {
		if s.EvalScore != nil && *s.EvalScore > bestScore {
			bestScore = *s.EvalScore
			best = s
		}
	}
	
	return best
}

// Ratchet 机制：只有更好的版本才替换
func (r *SkillRegistry) Ratchet(name, newContent string, threshold float64) error {
	best := r.BestVersion(name)
	if best == nil || best.EvalScore == nil {
		// 没有基准版本，直接创建
		_, err := r.CreateSkill(name, newContent)
		return err
	}
	
	// 评估新版本
	newScore := r.EvaluateNewSkill(name, newContent)
	
	if *best.EvalScore+threshold > newScore {
		// 新版本不够好，回滚
		return fmt.Errorf("new skill version not good enough")
	}
	
	// 新版本更好，保留
	_, err := r.CreateSkill(name, newContent)
	return err
}
```

### 2.3 群体智能闭环 — Go 实现

```go
package selfevolution

// 群体智能闭环：个人经验蒸馏为群体知识
// Ultron: 个人 → 群体
// OpenSpace: 外部演化服务
// SkillClaw: 跨会话、跨设备、跨用户合并

type GroupIntelligence struct {
	SkillRegistry *SkillRegistry
	Distillation  *DistillationEngine
}

// DistillationEngine 蒸馏引擎
type DistillationEngine struct {
	GlobalKnowledge []SkillPattern // 全局知识模式
}

// SkillPattern 技能模式
type SkillPattern struct {
	PatternName string
	Instances   []SkillInstance
	Confidence  float64
}

type SkillInstance struct {
	UserID    string
	SkillName string
	Content   string
	EvalScore float64
}

// Distill 从个人经验蒸馏群体知识
func (d *DistillationEngine) Distill(userSkills map[string][]*SkillAsset) {
	// 1. 聚合所有用户的 Skill
	var allInstances []SkillInstance
	for userID, skills := range userSkills {
		for _, skill := range skills {
			allInstances = append(allInstances, SkillInstance{
				UserID:    userID,
				SkillName: skill.Name,
				Content:   skill.Content,
				EvalScore: *skill.EvalScore,
			})
		}
	}
	
	// 2. 按技能名分组
	groupedBySkill := make(map[string][]SkillInstance)
	for _, instance := range allInstances {
		groupedBySkill[instance.SkillName] = append(
			groupedBySkill[instance.SkillName], instance,
		)
	}
	
	// 3. 对每个技能，聚合最佳模式
	for skillName, instances := range groupedBySkill {
		bestScore := 0.0
		bestContent := ""
		
		for _, instance := range instances {
			if instance.EvalScore > bestScore {
				bestScore = instance.EvalScore
				bestContent = instance.Content
			}
		}
		
		d.GlobalKnowledge = append(d.GlobalKnowledge, SkillPattern{
			PatternName: skillName,
			Confidence:  bestScore,
		})
	}
}

// ApplyGlobalKnowledge 应用全局知识
func (g *GroupIntelligence) ApplyGlobalKnowledge(userID string) {
	// 从全局知识中选择适合当前用户的模式
	for _, pattern := range g.Distillation.GlobalKnowledge {
		// 评估是否适合当前用户
		suitability := g.EvaluateSuitability(userID, pattern)
		
		if suitability > 0.7 {
			// 应用该模式
			g.ApplyPattern(userID, pattern)
		}
	}
}
```

### 2.4 参数自修改闭环 — Go 实现

```go
package selfevolution

// 参数、代码或工作流自修改闭环
// OpenClaw-RL：真实对话反馈 → 异步 RL/OPD 信号
// Agent Lightning：解耦 Agent 执行与 RL 训练

type ParameterUpdate struct {
	AgentID   string
	Step      int
	Observation  []string
	Reward    float64
}

type RLTrainer struct {
	Policy     *PolicyNetwork
	RewardModel *RewardModel
}

// 简化版 RL 训练
func (t *RLTrainer) TrainFromFeedback(
	agentID string,
	observations []string,
	reward float64,
) error {
	// 1. 计算 advantage
	gae := t.ComputeGAE(observations, reward)
	
	// 2. 计算 policy loss
	policyLoss := t.ComputePolicyLoss(observations, gae)
	
	// 3. 更新策略
	t.Policy.Update(policyLoss)
	
	// 4. 更新价值模型
	valueLoss := t.ComputeValueLoss(observations, reward)
	t.RewardModel.Update(valueLoss)
	
	return nil
}
```

---

## 第三部分：代表项目详解

### 内建上下文闭环

| 项目 | 特点 |
|------|------|
| **Hermes Agent** | 记忆、会话检索、技能创建进主循环 |
| **Agent Zero** | Project 隔离、动态工具、子智能体 |

### 技能资产化闭环

| 项目 | 特点 |
|------|------|
| **Darwin Skill** | SKILL.md 可评测、可回滚 |
| **JiuwenClaw** | 运行时根据反馈优化 Skill |
| **EvoSkill** | 从失败轨迹生成、测试、保留技能变体 |

### 群体智能闭环

| 项目 | 特点 |
|------|------|
| **Ultron** | 个人经验 → 群体记忆/技能/Harness |
| **OpenSpace** | 外部演化服务维护技能版本谱系 |
| **SkillClaw** | 跨会话、跨设备、跨用户共享技能 |

### 参数自修改闭环

| 项目 | 特点 |
|------|------|
| **OpenClaw-RL** | 真实对话反馈 → 异步 RL/OPD |
| **Agent Lightning** | 解耦 Agent 执行与 RL 训练 |

---

## 第四部分：自测题

### 问题 1
Agent 自进化的四类闭环中，哪一类最安全？为什么？

<details>
<summary>查看答案</summary>

1. **最安全**: 内建上下文闭环（Hermes Agent, Agent Zero）
2. **原因**: 
   - 不修改模型参数，只更新上下文和记忆
   - 容易审计和回滚
   - 影响范围可控（仅限当前会话/项目）
   - 不需要训练基础设施
3. **风险等级**: 🟢 低
4. **适用场景**: 个人 Agent、团队 Agent、轻量级部署
5. **局限**: 能力上限受限于底层模型

</details>

### 问题 2
Ratchet 机制在技能进化中起到什么作用？

<details>
<summary>查看答案</summary>

1. **定义**: 只有评估更好的版本才替换旧版本
2. **作用**: 确保 Skill 质量不会下降
3. **实现**: 对比新旧版本评估分数，只有提升超过阈值才保留
4. **好处**: 持续改进，防止回退
5. **阈值**: 需要合理设置（如 0.1），太严格会阻碍进化，太宽松会降低质量
6. **Go 实现**: 用 version 管理 + eval 评分 + ratchet 逻辑

</details>

### 问题 3
群体智能闭环相比个人学习有什么优势？

<details>
<summary>查看答案</summary>

1. **知识聚合**: 多个用户的经验合并为共享知识
2. **多样性**: 不同用户的问题和解决方案更丰富
3. **质量筛选**: 通过聚合，自然筛选出高质量技能
4. **冷启动**: 新用户可以直接使用群体知识，无需从零开始
5. **风险**: 隐私问题、知识冲突、权限控制
6. **实现**: 需要 Distillation Engine 和 Global Knowledge Store

</details>

---

*本文档基于 Datawhale hello-agents Extra10 社区贡献整理，内容经过精简和 Go 化改造。*
*自进化的核心：让 Agent 从真实经验中持续学习，而不是静态配置。*
