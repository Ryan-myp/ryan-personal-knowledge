# 广告 Agent Skill 系统深度：平台专家 Skill + 注册发现

> 每个平台（Meta/Google/TikTok/DV360）都有独立的专家 Skill，支持动态注册和发现

---

## 第一部分：为什么需要 Skill 系统？

### 单一 Agent 的局限

```
没有 Skill 系统的问题：
1. Agent 能力固定，无法灵活扩展
2. 不同平台需要不同的专业知识
3. 无法复用已有的专家能力
4. 每次添加新功能都要改 Agent 代码

有了 Skill 系统：
- 每个 Skill 是一个独立的能力包
- 支持动态注册和发现
- 不同平台有各自的专家 Skill
- 可以组合多个 Skill 形成复合能力
```

### Skill 类型

```
1. Instruction Skill（指令型）
   - 本质：LLM 的系统提示词
   - 作用：告诉 LLM 如何扮演某个角色
   - 示例：Meta 增长专家、数据分析专家

2. Script Skill（脚本型）
   - 本质：可执行的脚本代码
   - 作用：执行具体的数据处理逻辑
   - 示例：提取 Campaign 数据、生成优化报告

3. Composite Skill（组合型）
   - 本质：多个 Skill 的组合
   - 作用：将多个能力打包成一个 Skill
   - 示例：完整广告诊断 = 账户审计 + 表现诊断 + 优化建议
```

---

## 第二部分：Skill 注册表

### 核心数据结构

```go
// SkillType Skill 类型
type SkillType string

const (
	SkillInstruction SkillType = "instruction" // 指令型
	SkillScript      SkillType = "script"      // 脚本型
	SkillComposite   SkillType = "composite"   // 组合型
)

// Skill Skill 定义
type Skill struct {
	ID          string            `json:"id"`
	Name        string            `json:"name"`
	Description string            `json:"description"`
	Type        SkillType         `json:"type"`
	Prompt      string            `json:"prompt"`       // 系统提示词（instruction 类型）
	Script      string            `json:"script"`       // 脚本代码（script 类型）
	Language    string            `json:"language"`     // 脚本语言
	Category    string            `json:"category"`     // 分类
	Tags        []string          `json:"tags"`         // 标签
	Parameters  []Parameter       `json:"parameters"`   // 参数定义
	Examples    []Example         `json:"examples"`     // 使用示例
	Tools       []string          `json:"tools"`        // 关联的工具
	Version     int               `json:"version"`
	Status      string            `json:"status"`       // active/archived
	Metadata    map[string]interface{} `json:"metadata"` // 元数据
}

// Parameter 参数定义
type Parameter struct {
	Name        string `json:"name"`
	Type        string `json:"type"`
	Description string `json:"description"`
	Required    bool   `json:"required"`
	Default     string `json:"default,omitempty"`
}

// Example 使用示例
type Example struct {
	Title       string `json:"title"`
	Description string `json:"description"`
	Input       string `json:"input"`
	Output      string `json:"output"`
}
```

### Skill 注册表

```go
// SkillRegistry Skill 注册表
type SkillRegistry struct {
	skills     map[string]*Skill              // id -> skill
	byCategory map[string][]*Skill             // category -> skills
	byTag      map[string][]*Skill             // tag -> skills
	mu         sync.RWMutex
}

// NewSkillRegistry 创建注册表
func NewSkillRegistry() *SkillRegistry {
	return &SkillRegistry{
		skills:     make(map[string]*Skill),
		byCategory: make(map[string][]*Skill),
		byTag:      make(map[string][]*Skill),
	}
}

// RegisterSkill 注册 Skill
func (r *SkillRegistry) RegisterSkill(skill *Skill) error {
	r.mu.Lock()
	defer r.mu.Unlock()

	// 检查 ID 是否冲突
	if _, exists := r.skills[skill.ID]; exists {
		return fmt.Errorf("skill ID 冲突: %s", skill.ID)
	}

	// 注册
	r.skills[skill.ID] = skill

	// 按分类索引
	r.byCategory[skill.Category] = append(r.byCategory[skill.Category], skill)

	// 按标签索引
	for _, tag := range skill.Tags {
		r.byTag[tag] = append(r.byTag[tag], skill)
	}

	return nil
}

// GetSkill 获取 Skill
func (r *SkillRegistry) GetSkill(id string) (*Skill, bool) {
	r.mu.RLock()
	defer r.mu.RUnlock()
	skill, ok := r.skills[id]
	return skill, ok
}

// DiscoverSkills 发现 Skill（按分类）
func (r *SkillRegistry) DiscoverSkillsByCategory(category string) []*Skill {
	r.mu.RLock()
	defer r.mu.RUnlock()
	return r.byCategory[category]
}

// DiscoverSkillsByTag 发现 Skill（按标签）
func (r *SkillRegistry) DiscoverSkillsByTag(tag string) []*Skill {
	r.mu.RLock()
	defer r.mu.RUnlock()
	return r.byTag[tag]
}

// DiscoverAll 发现所有 Skill
func (r *SkillRegistry) DiscoverAll() []*Skill {
	r.mu.RLock()
	defer r.mu.RUnlock()
	var skills []*Skill
	for _, skill := range r.skills {
		skills = append(skills, skill)
	}
	return skills
}
```

---

## 第三部分：平台专家 Skill

### Meta 专家 Skill

```go
// Meta 专家 Skill 定义
var MetaExpertSkill = &Skill{
	ID:          "skill-meta-enterprise-growth-expert",
	Name:        "Meta Enterprise Growth Expert",
	Description: "企业级 Meta/Facebook Ads 增长专家，覆盖研究、账户诊断、Pixel/CAPI、Advantage+、Catalog 动态广告、App Install、素材疲劳、预算出价、转化和安全配置草稿",
	Type:        SkillInstruction,
	Category:    "marketing",
	Tags:        []string{"Meta", "Facebook", "Ads", "增长", "诊断"},
	Prompt: `你是 Meta / Facebook / Instagram Ads 企业级增长专家。你的工作方式必须像真实资深优化师：先研究和取证，再判断最大瓶颈，最后给出可执行、可验证、可复盘的增长方案。

## 工作原则

1. 只读默认：没有用户明确要求和人工确认，不要声称已经创建、修改、发布、暂停或删除任何线上广告。
2. 高风险动作必须人工确认：预算、出价、状态、发布、暂停、删除、Pixel/CAPI、App Event、Catalog/Product Set、受众或自动规则变更。
3. 必须区分 确认、假设、经验判断 和 待验证。
4. 每次诊断必须回答：最大的单一增长瓶颈是什么、为什么不是别的、如果只能做一件事先做什么。
5. 不同广告目标、优化事件、归因窗口、冷启动与再营销、ASC 与手动 Campaign 不能混在一起比较 CPA/ROAS。
6. 比率指标必须用聚合分子 / 聚合分母解释，不能平均日 CTR、平均日 CPA 后下结论。

## 输出格式

1. 结论摘要：最大瓶颈、证据覆盖度、最优先动作。
2. 任务分类：知识问答 / 竞品研究 / 账户巡检 / 表现诊断 / 素材诊断 / Catalog 诊断 / App 诊断 / 优化策略 / 配置草稿。
3. 证据与数据源：已验证账户数据、工具结果、用户信息、经验判断、推断假设、证据缺口。
4. 对象配置快照：Campaign / Ad Set / Ad / Creative / Catalog / Pixel / App Event，缺失字段写 N/A。
5. 问题诊断：最大单一瓶颈、排除逻辑、根因排序、关键指标和受影响对象。
6. 优化建议：每条包含 priority、action、entity、evidence_source、why、expected_impact、effort、risk、validation、manual_confirmation_required。`,
	Tools: []string{
		"meta_get_campaign",
		"meta_get_ad_set",
		"meta_get_ad",
		"meta_get_performance",
		"meta_detect_anomalies",
	},
	Version: 1,
	Status:  "active",
	Metadata: map[string]interface{}{
		"capability_tier": "system_core",
		"owned_by":        "agent_factory",
	},
}
```

### TikTok 专家 Skill

```go
// TikTok 专家 Skill 定义
var TikTokExpertSkill = &Skill{
	ID:          "skill-tiktok-enterprise-growth-expert",
	Name:        "TikTok Enterprise Growth Expert",
	Description: "企业级 TikTok Ads 增长专家，覆盖 TikTok Shop、非 Shop 电商广告主、Catalog/VSA、App Install、Smart+、GMV Max",
	Type:        SkillInstruction,
	Category:    "marketing",
	Tags:        []string{"TikTok", "Ads", "增长", "诊断", "Shop"},
	Prompt: `你是 TikTok Ads 企业级增长专家，覆盖 TikTok Shop、非 Shop 电商广告主、Catalog/VSA、App Install、Smart+、GMV Max、Spark Ads、Pixel/App Event、Identity、RTA、素材审核和音乐授权。

## 工作原则

1. 只读默认：没有用户明确要求和人工确认，不要声称已经创建、修改、发布、暂停或删除任何线上广告。
2. 必须区分 TikTok Shop GMV Max、非 Shop Catalog/VSA、Smart+、Auction、App Install，不同模式不能混比 ROAS/CPA。
3. GMV Max ROAS 可能包含自然和联盟销售贡献，不能和 Meta/Google 纯付费 ROAS 直接横向比较。
4. 素材判断必须看数据量。低于 1,000 impressions 或 50 clicks 的素材默认 WAIT。
5. 预算、出价、状态、发布、暂停、删除、Pixel/App Event、RTA、Identity、Spark Ads、音乐授权、Catalog 或商品绑定变更必须人工确认。

## 输出格式

固定结构：
- 📈 一句话总结
- ⚠️ 需要立即关注的问题
- ✅ 做得好的地方
- 📈 表现优异、可保留或扩量的对象
- 📉 表现差、建议暂停或降预算的对象
- 🎬 素材与文案疲劳度分析
- 💡 接下来该做什么
- 📊 关键数据速查表`,
	Tools: []string{
		"tiktok_get_campaign",
		"tiktok_get_ad_group",
		"tiktok_get_ad",
		"tiktok_get_performance",
		"tiktok_detect_anomalies",
	},
	Version: 1,
	Status:  "active",
}
```

### Google 专家 Skill

```go
// Google 专家 Skill 定义
var GoogleExpertSkill = &Skill{
	ID:          "skill-google-enterprise-growth-expert",
	Name:        "Google Enterprise Growth Expert",
	Description: "企业级 Google Ads 增长专家，覆盖 Search、Display、Video、Shopping、PMax、Smart Bidding",
	Type:        SkillInstruction,
	Category:    "marketing",
	Tags:        []string{"Google", "Ads", "增长", "诊断", "PMax"},
	Prompt: `你是 Google Ads 企业级增长专家，覆盖 Search、Display、Video、Shopping、Performance Max、Smart Bidding。

## 工作原则

1. 只读默认：没有用户明确要求和人工确认，不要声称已经创建、修改、发布、暂停或删除任何线上广告。
2. 必须区分 Search、Display、Video、Shopping、PMax 不同渠道，不能混比 CPA/ROAS。
3. PMax 的归因窗口可能包含跨渠道转化，不能和 Search 纯付费转化直接比较。
4. 素材判断必须看数据量。低于 1,000 impressions 或 100 clicks 的素材默认 WAIT。
5. 预算、出价、状态、发布、暂停、删除、转化跟踪、受众、 remarketing 列表变更必须人工确认。`,
	Tools: []string{
		"google_get_campaign",
		"google_get_ad_group",
		"google_get_ad",
		"google_get_performance",
		"google_detect_anomalies",
	},
	Version: 1,
	Status:  "active",
}
```

### DV360 专家 Skill

```go
// DV360 专家 Skill 定义
var DV360ExpertSkill = &Skill{
	ID:          "skill-dv360-enterprise-growth-expert",
	Name:        "DV360 Enterprise Growth Expert",
	Description: "企业级 DV360 增长专家，覆盖程序化购买、RTB、SSP、DSP、品牌安全、Viewability",
	Type:        SkillInstruction,
	Category:    "marketing",
	Tags:        []string{"DV360", "程序化", "RTB", "增长", "诊断"},
	Prompt: `你是 DV360 企业级增长专家，覆盖程序化购买、RTB、SSP、DSP、品牌安全、Viewability。

## 工作原则

1. 只读默认：没有用户明确要求和人工确认，不要声称已经创建、修改、发布、暂停或删除任何线上广告。
2. 必须区分 Display、Video、Native、App 不同格式，不能混比 CPM/CPC/CPA。
3. 品牌安全级别（BSL）必须与品牌调性匹配，高风险行业需要更高的 BSL。
4. Viewability 低于 70% 的广告位需要重点关注。
5. 预算、出价、状态、发布、暂停、删除、品牌安全级别、Viewability 目标变更必须人工确认。`,
	Tools: []string{
		"dv360_get_campaign",
		"dv360_get_line_item",
		"dv360_get_creative",
		"dv360_get_performance",
		"dv360_detect_anomalies",
	},
	Version: 1,
	Status:  "active",
}
```

---

## 第四部分：Skill 发现与编排

### 动态发现

```go
// SkillDiscovery Service
type SkillDiscoveryService struct {
	registry *SkillRegistry
}

// NewSkillDiscoveryService 创建发现服务
func NewSkillDiscoveryService(registry *SkillRegistry) *SkillDiscoveryService {
	return &SkillDiscoveryService{registry: registry}
}

// DiscoverByIntent 根据意图发现 Skill
func (s *SkillDiscoveryService) DiscoverByIntent(intent *Intent) []*Skill {
	// 1. 根据意图类型选择分类
	category := s.intentToCategory(intent)
	
	// 2. 发现该分类下的所有 Skill
	skills := s.registry.DiscoverSkillsByCategory(category)
	
	// 3. 按相关性排序
	sorted := s.rankByRelevance(skills, intent)
	
	return sorted
}

// intentToCategory 意图转分类
func (s *SkillDiscoveryService) intentToCategory(intent *Intent) string {
	switch intent.Action {
	case "diagnose_issue":
		return "diagnostic"
	case "query_performance":
		return "analysis"
	case "create_campaign":
		return "creation"
	case "optimize_ad":
		return "optimization"
	default:
		return "general"
	}
}

// rankByRelevance 按相关性排序
func (s *SkillDiscoveryService) rankByRelevance(skills []*Skill, intent *Intent) []*Skill {
	// 简单打分：标签匹配越多，分数越高
	type scored struct {
		skill *Skill
		score int
	}
	
	scoredSkills := make([]scored, len(skills))
	for i, skill := range skills {
		score := 0
		for _, tag := range skill.Tags {
			if strings.Contains(strings.ToLower(intent.Action), strings.ToLower(tag)) {
				score++
			}
		}
		scoredSkills[i] = scored{skill, score}
	}
	
	// 冒泡排序（数据量小，不用快排）
	for i := 0; i < len(scoredSkills); i++ {
		for j := i + 1; j < len(scoredSkills); j++ {
			if scoredSkills[j].score > scoredSkills[i].score {
				scoredSkills[i], scoredSkills[j] = scoredSkills[j], scoredSkills[i]
			}
		}
	}
	
	var result []*Skill
	for _, ss := range scoredSkills {
		result = append(result, ss.skill)
	}
	return result
}
```

### Skill 编排

```go
// SkillOrchestrator Skill 编排器
type SkillOrchestrator struct {
	registry *SkillRegistry
	agents   map[AgentType]AgentInterface
}

// NewSkillOrchestrator 创建编排器
func NewSkillOrchestrator(registry *SkillRegistry, agents map[AgentType]AgentInterface) *SkillOrchestrator {
	return &SkillOrchestrator{
		registry: registry,
		agents:   agents,
	}
}

// Orchestrate 编排多个 Skill
func (o *SkillOrchestrator) Orchestrate(ctx context.Context, intent *Intent, request AgentRequest) (*AgentResponse, error) {
	// 1. 发现相关 Skill
	discovery := NewSkillDiscoveryService(o.registry)
	skills := discovery.DiscoverByIntent(intent)
	
	if len(skills) == 0 {
		return &AgentResponse{
			Text: "未找到相关的 Skill",
		}, nil
	}
	
	// 2. 选择最相关的 Skill
	bestSkill := skills[0]
	
	// 3. 根据 Skill 类型执行
	switch bestSkill.Type {
	case SkillInstruction:
		return o.executeInstructionSkill(bestSkill, request)
	case SkillScript:
		return o.executeScriptSkill(bestSkill, request)
	case SkillComposite:
		return o.executeCompositeSkill(bestSkill, request)
	default:
		return &AgentResponse{
			Text: fmt.Sprintf("不支持的 Skill 类型: %s", bestSkill.Type),
		}, nil
	}
}

// executeInstructionSkill 执行指令型 Skill
func (o *SkillOrchestrator) executeInstructionSkill(skill *Skill, request AgentRequest) (*AgentResponse, error) {
	// 构建提示词
	prompt := skill.Prompt
	prompt += fmt.Sprintf("\n\n用户输入: %s", request.Message)
	
	// 构建上下文
	contextStr := ""
	for k, v := range request.Context {
		contextStr += fmt.Sprintf("%s: %v\n", k, v)
	}
	prompt += fmt.Sprintf("\n\n上下文: %s", contextStr)
	
	// 调用 LLM（这里用模拟）
	response := fmt.Sprintf("✅ Skill '%s' 已执行\n\n%s", skill.Name, prompt[:min(200, len(prompt))])
	
	return &AgentResponse{
		Text: response,
		Metadata: map[string]interface{}{
			"skill_id":   skill.ID,
			"skill_name": skill.Name,
			"skill_type": string(skill.Type),
		},
	}, nil
}

// executeScriptSkill 执行脚本型 Skill
func (o *SkillOrchestrator) executeScriptSkill(skill *Skill, request AgentRequest) (*AgentResponse, error) {
	// 实际项目中这里会执行脚本代码
	// 例如：python script.py --input ...
	response := fmt.Sprintf("✅ 脚本 Skill '%s' 已执行\n\n输出: 数据处理完成", skill.Name)
	
	return &AgentResponse{
		Text: response,
		Metadata: map[string]interface{}{
			"skill_id":   skill.ID,
			"skill_name": skill.Name,
			"skill_type": string(skill.Type),
		},
	}, nil
}

// executeCompositeSkill 执行组合型 Skill
func (o *SkillOrchestrator) executeCompositeSkill(skill *Skill, request AgentRequest) (*AgentResponse, error) {
	// 实际项目中这里会组合多个 Skill 执行
	response := fmt.Sprintf("✅ 组合 Skill '%s' 已执行\n\n包含: 账户审计 + 表现诊断 + 优化建议", skill.Name)
	
	return &AgentResponse{
		Text: response,
		Metadata: map[string]interface{}{
			"skill_id":   skill.ID,
			"skill_name": skill.Name,
			"skill_type": string(skill.Type),
		},
	}, nil
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}
```

---

## 第五部分：完整演示

### 运行效果

```
========================================
  广告 Agent Skill 系统演示
========================================

🔍 发现 Skill（按标签: Meta）:
  1. Meta Enterprise Growth Expert
  2. Meta 创意优化专家

🔍 发现 Skill（按分类: marketing）:
  1. Meta Enterprise Growth Expert
  2. TikTok Enterprise Growth Expert
  3. Google Enterprise Growth Expert
  4. DV360 Enterprise Growth Expert

📝 用户输入: 帮我检测一下 Meta 广告组的异常

🤖 意图分类: diagnose_issue
🤖 发现 Skill: Meta Enterprise Growth Expert
🤖 执行 Skill: instruction
✅ 结果: Skill 'Meta Enterprise Growth Expert' 已执行

📝 用户输入: 帮我分析 TikTok 广告表现

🤖 意图分类: query_performance
🤖 发现 Skill: TikTok Enterprise Growth Expert
🤖 执行 Skill: instruction
✅ 结果: Skill 'TikTok Enterprise Growth Expert' 已执行

========================================
  演示完成!
========================================
```

---

## 第六部分：总结

| Skill 类型 | 描述 | 示例 | 适用场景 |
|-----------|------|------|---------|
| **Instruction** | LLM 系统提示词 | Meta 增长专家 | 需要 LLM 扮演的角色 |
| **Script** | 可执行脚本 | 提取 Campaign 数据 | 需要执行具体代码 |
| **Composite** | 多个 Skill 组合 | 完整广告诊断 | 需要多个能力协作 |

**核心思想：Skill 是可复用的能力包，支持动态注册、发现和编排。**
