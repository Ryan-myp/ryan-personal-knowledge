package main

import (
	"context"
	"fmt"
	"strings"
	"sync"
)

// ============================================================
// Skill 系统 - 完整可运行演示
// ============================================================

// SkillType Skill 类型
type SkillType string

const (
	SkillInstruction SkillType = "instruction"
	SkillScript      SkillType = "script"
	SkillComposite   SkillType = "composite"
)

// Skill Skill 定义
type Skill struct {
	ID          string                 `json:"id"`
	Name        string                 `json:"name"`
	Description string                 `json:"description"`
	Type        SkillType              `json:"type"`
	Prompt      string                 `json:"prompt"`
	Script      string                 `json:"script"`
	Language    string                 `json:"language"`
	Category    string                 `json:"category"`
	Tags        []string               `json:"tags"`
	Parameters  []Parameter            `json:"parameters"`
	Examples    []Example              `json:"examples"`
	Tools       []string               `json:"tools"`
	Version     int                    `json:"version"`
	Status      string                 `json:"status"`
	Metadata    map[string]interface{} `json:"metadata"`
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

// SkillRegistry Skill 注册表
type SkillRegistry struct {
	skills     map[string]*Skill
	byCategory map[string][]*Skill
	byTag      map[string][]*Skill
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

	if _, exists := r.skills[skill.ID]; exists {
		return fmt.Errorf("skill ID 冲突: %s", skill.ID)
	}

	r.skills[skill.ID] = skill
	r.byCategory[skill.Category] = append(r.byCategory[skill.Category], skill)

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

// DiscoverSkillsByCategory 按分类发现 Skill
func (r *SkillRegistry) DiscoverSkillsByCategory(category string) []*Skill {
	r.mu.RLock()
	defer r.mu.RUnlock()
	return r.byCategory[category]
}

// DiscoverSkillsByTag 按标签发现 Skill
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

// SkillDiscoveryService 发现服务
type SkillDiscoveryService struct {
	registry *SkillRegistry
}

func NewSkillDiscoveryService(registry *SkillRegistry) *SkillDiscoveryService {
	return &SkillDiscoveryService{registry: registry}
}

// DiscoverByTags 按标签发现 Skill
func (s *SkillDiscoveryService) DiscoverByTags(tags []string) []*Skill {
	var results []*Skill
	seen := make(map[string]bool)

	for _, tag := range tags {
		skills := s.registry.DiscoverSkillsByTag(tag)
		for _, skill := range skills {
			if !seen[skill.ID] {
				seen[skill.ID] = true
				results = append(results, skill)
			}
		}
	}

	return results
}

// SkillOrchestrator 编排器
type SkillOrchestrator struct {
	registry *SkillRegistry
}

func NewSkillOrchestrator(registry *SkillRegistry) *SkillOrchestrator {
	return &SkillOrchestrator{registry: registry}
}

// ExecuteSkill 执行 Skill
func (o *SkillOrchestrator) ExecuteSkill(ctx context.Context, skill *Skill, userInput string) (*AgentResponse, error) {
	switch skill.Type {
	case SkillInstruction:
		return o.executeInstruction(skill, userInput)
	case SkillScript:
		return o.executeScript(skill, userInput)
	case SkillComposite:
		return o.executeComposite(skill, userInput)
	default:
		return nil, fmt.Errorf("不支持的 Skill 类型: %s", skill.Type)
	}
}

// executeInstruction 执行指令型 Skill
func (o *SkillOrchestrator) executeInstruction(skill *Skill, userInput string) (*AgentResponse, error) {
	prompt := skill.Prompt
	prompt += "\n\n用户输入: " + userInput

	return &AgentResponse{
		Text: fmt.Sprintf("✅ Skill '%s' 已执行\n\n提示词长度: %d 字符\n\n前 200 字符:\n%s",
			skill.Name, len(prompt), prompt[:minInt(200, len(prompt))]),
		Metadata: map[string]interface{}{
			"skill_id":   skill.ID,
			"skill_name": skill.Name,
			"skill_type": string(skill.Type),
		},
	}, nil
}

// executeScript 执行脚本型 Skill
func (o *SkillOrchestrator) executeScript(skill *Skill, userInput string) (*AgentResponse, error) {
	return &AgentResponse{
		Text: fmt.Sprintf("✅ 脚本 Skill '%s' 已执行\n\n输出: 数据处理完成", skill.Name),
		Metadata: map[string]interface{}{
			"skill_id":   skill.ID,
			"skill_name": skill.Name,
			"skill_type": string(skill.Type),
		},
	}, nil
}

// executeComposite 执行组合型 Skill
func (o *SkillOrchestrator) executeComposite(skill *Skill, userInput string) (*AgentResponse, error) {
	return &AgentResponse{
		Text: fmt.Sprintf("✅ 组合 Skill '%s' 已执行\n\n包含: 账户审计 + 表现诊断 + 优化建议", skill.Name),
		Metadata: map[string]interface{}{
			"skill_id":   skill.ID,
			"skill_name": skill.Name,
			"skill_type": string(skill.Type),
		},
	}, nil
}

// AgentResponse Agent 响应
type AgentResponse struct {
	Text       string                 `json:"text"`
	Structured map[string]interface{} `json:"structured,omitempty"`
	Metadata   map[string]interface{} `json:"metadata,omitempty"`
}

func minInt(a, b int) int {
	if a < b {
		return a
	}
	return b
}

// ============================================================
// 演示
// ============================================================

func main() {
	fmt.Println("========================================")
	fmt.Println("  广告 Agent Skill 系统完整演示")
	fmt.Println("========================================\n")

	// 1. 创建注册表
	registry := NewSkillRegistry()

	// 2. 注册平台专家 Skill
	metaSkill := &Skill{
		ID:          "skill-meta-enterprise-growth-expert",
		Name:        "Meta Enterprise Growth Expert",
		Description: "企业级 Meta/Facebook Ads 增长专家",
		Type:        SkillInstruction,
		Category:    "marketing",
		Tags:        []string{"Meta", "Facebook", "Ads", "增长", "诊断"},
		Prompt:      "你是 Meta 企业级增长专家...",
		Tools:       []string{"meta_get_campaign", "meta_get_performance"},
		Version:     1,
		Status:      "active",
	}

	tiktokSkill := &Skill{
		ID:          "skill-tiktok-enterprise-growth-expert",
		Name:        "TikTok Enterprise Growth Expert",
		Description: "企业级 TikTok Ads 增长专家",
		Type:        SkillInstruction,
		Category:    "marketing",
		Tags:        []string{"TikTok", "Ads", "增长", "诊断", "Shop"},
		Prompt:      "你是 TikTok 企业级增长专家...",
		Tools:       []string{"tiktok_get_campaign", "tiktok_get_performance"},
		Version:     1,
		Status:      "active",
	}

	googleSkill := &Skill{
		ID:          "skill-google-enterprise-growth-expert",
		Name:        "Google Enterprise Growth Expert",
		Description: "企业级 Google Ads 增长专家",
		Type:        SkillInstruction,
		Category:    "marketing",
		Tags:        []string{"Google", "Ads", "增长", "诊断", "PMax"},
		Prompt:      "你是 Google 企业级增长专家...",
		Tools:       []string{"google_get_campaign", "google_get_performance"},
		Version:     1,
		Status:      "active",
	}

	dv360Skill := &Skill{
		ID:          "skill-dv360-enterprise-growth-expert",
		Name:        "DV360 Enterprise Growth Expert",
		Description: "企业级 DV360 增长专家",
		Type:        SkillInstruction,
		Category:    "marketing",
		Tags:        []string{"DV360", "程序化", "RTB", "增长", "诊断"},
		Prompt:      "你是 DV360 企业级增长专家...",
		Tools:       []string{"dv360_get_campaign", "dv360_get_performance"},
		Version:     1,
		Status:      "active",
	}

	registry.RegisterSkill(metaSkill)
	registry.RegisterSkill(tiktokSkill)
	registry.RegisterSkill(googleSkill)
	registry.RegisterSkill(dv360Skill)

	// 3. 注册数据分析 Skill
	dataAnalysisSkill := &Skill{
		ID:          "skill-data-analysis",
		Name:        "数据分析专家",
		Description: "专业的数据分析 Skill",
		Type:        SkillScript,
		Category:    "analysis",
		Tags:        []string{"数据分析", "趋势", "异常检测"},
		Script:      "def analyze(data): ...",
		Language:    "python",
		Version:     1,
		Status:      "active",
	}
	registry.RegisterSkill(dataAnalysisSkill)

	// 4. 注册完整诊断 Skill（组合型）
	fullDiagnosticSkill := &Skill{
		ID:          "skill-full-diagnostic",
		Name:        "完整广告诊断",
		Description: "组合型 Skill：账户审计 + 表现诊断 + 优化建议",
		Type:        SkillComposite,
		Category:    "diagnostic",
		Tags:        []string{"诊断", "优化", "报告"},
		Tools:       []string{"meta_get_campaign", "meta_get_performance", "meta_detect_anomalies"},
		Version:     1,
		Status:      "active",
	}
	registry.RegisterSkill(fullDiagnosticSkill)

	fmt.Println("📦 已注册 Skill:")
	allSkills := registry.DiscoverAll()
	for _, skill := range allSkills {
		fmt.Printf("  - %s [%s] (%d 标签)\n", skill.Name, skill.Type, len(skill.Tags))
	}
	fmt.Println()

	// 5. 按标签发现
	fmt.Println("🔍 按标签 '诊断' 发现 Skill:")
	diagSkills := registry.DiscoverSkillsByTag("诊断")
	for _, skill := range diagSkills {
		fmt.Printf("  - %s (%s)\n", skill.Name, skill.Type)
	}
	fmt.Println()

	// 6. 按分类发现
	fmt.Println("🔍 按分类 'marketing' 发现 Skill:")
	marketingSkills := registry.DiscoverSkillsByCategory("marketing")
	for _, skill := range marketingSkills {
		fmt.Printf("  - %s (%d 工具)\n", skill.Name, len(skill.Tools))
	}
	fmt.Println()

	// 7. 执行 Skill
	fmt.Println("🚀 执行 Skill:")

	orchestrator := NewSkillOrchestrator(registry)
	ctx := context.Background()

	testCases := []struct {
		skillID string
		input   string
	}{
		{"skill-meta-enterprise-growth-expert", "帮我检测 Meta 广告组的异常"},
		{"skill-tiktok-enterprise-growth-expert", "帮我分析 TikTok 广告表现"},
		{"skill-full-diagnostic", "帮我做完整的广告诊断"},
	}

	for _, tc := range testCases {
		skill, ok := registry.GetSkill(tc.skillID)
		if !ok {
			fmt.Printf("  ❌ Skill %s 不存在\n", tc.skillID)
			continue
		}

		response, err := orchestrator.ExecuteSkill(ctx, skill, tc.input)
		if err != nil {
			fmt.Printf("  ❌ 执行失败: %v\n", err)
			continue
		}

		fmt.Printf("  ✅ Skill '%s'\n", skill.Name)
		fmt.Printf("     输入: %s\n", tc.input)
		fmt.Printf("     结果: %s\n\n", strings.Split(response.Text, "\n")[0])
	}

	fmt.Println("========================================")
	fmt.Println("  演示完成!")
	fmt.Println("========================================")
}
