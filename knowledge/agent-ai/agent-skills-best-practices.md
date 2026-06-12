# 如何写出好的 Skill — Skill 写作最佳实践

> 基于 Datawhale hello-agents Extra08 社区贡献整理

---

## 第一部分：入门引导（5 分钟速览）

### 什么是 Skill？

Skill 是 Agent 的**能力扩展单元**——告诉 Agent 在特定场景下"怎么做"。
一个 Skill 的本质是一份结构化指令，它让 Agent 从"什么都能做但都做不好"变成"在特定领域深度专精"。

### Skill 的核心设计理念

| 设计原则 | 说明 |
|---------|------|
| **渐进式披露** | 只在对需要时加载，不浪费 token |
| **人指令 vs AI 指令** | 写给 AI 读的指令 ≠ 写给人读的文档 |
| **可评测可回滚** | 每次变更要有评估和版本记录 |
| **最小形态** | 从最简单的可用版本开始，逐步增强 |

### Skill 的完整结构

```markdown
# 技能名称

## 触发条件
什么情况下加载这个 Skill

## 核心步骤
1. 第一步做什么
2. 第二步做什么

## 注意事项
- 坑点 1
- 坑点 2

## 参考
相关文档链接
```

---

## 第二部分：源码级深度

### 2.1 人指令 vs AI 指令 — Go 实现对比

```go
package skill

import (
	"fmt"
	"strings"
	"time"
)

// ❶ 写给人看的指令（❌ 反面教材）
func HumanReadableSkill() string {
	return `
# 如何调试 Redis 连接问题

嗨，当你遇到 Redis 连接问题时，可以尝试以下方法：

1. 首先检查 Redis 是否正常运行
2. 然后看看网络连接是否通畅
3. 再检查一下密码是否正确
4. 如果还不行，看看日志有没有报错
5. 最后可以试试重启 Redis

记得要先备份哦！
`
}

// ❷ 写给 AI 看的指令（✅ 正确写法）
func AILevelSkill() string {
	return `
# Redis 连接排查

## 触发条件
当出现 redis.DialError / timeout / auth failed 时自动加载

## 核心步骤
1. 用 redis-cli ping 检查 Redis 存活
2. 用 nc -zv <host> <port> 检查网络连通
3. 检查配置文件中 password/username 是否匹配
4. 查看 redis.log 最后 100 行
5. 必要时执行 systemctl restart redis

## 注意事项
- 先确认是哪个环境（dev/staging/prod）
- 生产环境操作前必须加 sudo 确认
- 不要在生产环境执行 FLUSHALL/FLUSHDB

## 参考
redis-cli 文档: ...
`
}

// 渐进式 Skill 加载示例
type SkillLoader struct {
	skills map[string]*Skill // 技能注册表
}

type Skill struct {
	Name         string
	TriggerCond  func(context, error) bool // 触发条件
	Prompt       string                    // AI 指令
	MaxTokens    int                       // 最大 token 限制
	LoadPriority int                       // 加载优先级
}

func (l *SkillLoader) LoadSkills(ctx context.Context, event SkillEvent) ([]string, error) {
	var loaded []string
	
	for name, skill := range l.skills {
		if !skill.TriggerCond(ctx, event.Error) {
			continue // 不满足触发条件，跳过
		}
		
		// 检查 token 预算
		tokens := l.EstimateTokens(skill.Prompt)
		if tokens > event.TokenBudget {
			continue // token 预算不够，跳过
		}
		
		// 加载技能
		loaded = append(loaded, skill.Prompt)
		event.TokenBudget -= tokens
	}
	
	return loaded, nil
}
```

### 2.2 技能资产化管理 — Go 实现

```go
package skill

import (
	"encoding/json"
	"os"
	"path/filepath"
	"time"
)

// SkillAsset 可评测可回滚的 Skill 资产
type SkillAsset struct {
	Name        string    `json:"name"`
	Version     string    `json:"version"` // 版本号
	CreatedAt   time.Time `json:"created_at"`
	UpdatedAt   time.Time `json:"updated_at"`
	Content     string    `json:"content"`
	EvalScore   *float64  `json:"eval_score,omitempty"` // 评估得分
	Metadata    map[string]interface{} `json:"metadata"`
}

// SkillRegistry 技能注册表，支持版本管理
type SkillRegistry struct {
	registryPath string
	skills       map[string][]*SkillAsset // name -> versions
}

func NewSkillRegistry(path string) *SkillRegistry {
	return &SkillRegistry{
		registryPath: path,
		skills:       make(map[string][]*SkillAsset),
	}
}

// Create 创建新版本 Skill
func (r *SkillRegistry) Create(name, content string) (*SkillAsset, error) {
	version := fmt.Sprintf("v%d", len(r.skills[name])+1)
	
	skill := &SkillAsset{
		Name:      name,
		Version:   version,
		CreatedAt: time.Now(),
		UpdatedAt: time.Now(),
		Content:   content,
		Metadata:  make(map[string]interface{}),
	}
	
	// 保存到文件
	if err := r.saveVersion(skill); err != nil {
		return nil, err
	}
	
	r.skills[name] = append(r.skills[name], skill)
	return skill, nil
}

// Evaluate 评估 Skill 版本的质量
func (r *SkillRegistry) Evaluate(name string, version string, score float64) error {
	skill := r.findVersion(name, version)
	if skill == nil {
		return fmt.Errorf("skill %s version %s not found", name, version)
	}
	
	skill.EvalScore = &score
	return r.saveVersion(skill)
}

// Rollback 回滚到指定版本
func (r *SkillRegistry) Rollback(name string, targetVersion string) (*SkillAsset, error) {
	skill := r.findVersion(name, targetVersion)
	if skill == nil {
		return nil, fmt.Errorf("version %s not found", targetVersion)
	}
	
	// 获取最新版本并替换
	latest := r.skills[name][len(r.skills[name])-1]
	latest.Content = skill.Content
	latest.UpdatedAt = time.Now()
	latest.EvalScore = skill.EvalScore
	
	return latest, nil
}

// BestVersion 获取评估分数最高的版本
func (r *SkillRegistry) BestVersion(name string) (*SkillAsset, error) {
	versions := r.skills[name]
	if len(versions) == 0 {
		return nil, fmt.Errorf("no versions found for %s", name)
	}
	
	var best *SkillAsset
	bestScore := -1.0
	
	for _, v := range versions {
		if v.EvalScore != nil && *v.EvalScore > bestScore {
			bestScore = *v.EvalScore
			best = v
		}
	}
	
	return best, nil
}

// 辅助方法
func (r *SkillRegistry) findVersion(name, version string) *SkillAsset {
	for _, v := range r.skills[name] {
		if v.Version == version {
			return v
		}
	}
	return nil
}

func (r *SkillRegistry) saveVersion(skill *SkillAsset) error {
	data, _ := json.MarshalIndent(skill, "", "  ")
	path := filepath.Join(r.registryPath, skill.Name, skill.Version+".json")
	return os.MkdirAll(filepath.Dir(path), 0755) && os.WriteFile(path, data, 0644)
}
```

### 2.3 Darwin Skill 进化机制

```go
package skill

// Darwin Skill 核心：把 SKILL.md 当作可评测、可回滚的资产
// 通过评测和 ratchet 机制不断优化 Skill

type DarwinSkillEngine struct {
	Registry    *SkillRegistry
	Evaluator   *Evaluator
	Ratchet     *Ratchet
}

// Ratchet 机制：只有评估更高的版本才保留
type Ratchet struct {
	CurrentBest *SkillAsset
	Threshold   float64 // 最低提升阈值
}

// EvaluateAndRatchet 评估新版本，如果更好就替换
func (d *DarwinSkillEngine) EvaluateAndRatchet(
	name string, 
	newContent string, 
) error {
	// 创建新版本
	skill, err := d.Registry.Create(name, newContent)
	if err != nil {
		return err
	}
	
	// 用评估器测试新版本
	score := d.Evaluator.Evaluate(name, newContent)
	skill.EvalScore = &score
	
	// Ratchet：只有比当前最好版本高 Threshold 才保留
	best, err := d.Registry.BestVersion(name)
	if err != nil || best == nil {
		return nil // 没有基准版本，直接接受
	}
	
	if score < *best.EvalScore+d.Ratchet.Threshold {
		// 新版本不够好，回滚到旧版本
		_, err := d.Registry.Rollback(name, best.Version)
		return err
	}
	
	return nil // 新版本更好，保留
}
```

---

## 第三部分：实战案例

### Code Review Skill — 完整示例

```markdown
# Code Review Skill

## 触发条件
当用户要求 review 代码、提交 PR、或询问代码质量时加载

## 核心步骤
1. 读取文件列表，了解变更范围
2. 检查安全漏洞（SQL 注入、XSS、硬编码密钥）
3. 检查性能问题（N+1 查询、全表扫描、内存泄漏）
4. 检查代码风格（命名、注释、函数长度）
5. 生成 review 报告

## 注意事项
- 优先检查安全和性能问题，其次是代码风格
- Go 代码检查 goroutine 泄漏、channel 关闭、sync.Mutex 使用
- 提供具体的修复建议，不要只说"有问题"
- 引用代码行号，方便开发者定位
```

---

## 第四部分：自测题

### 问题 1
Skill 的"渐进式披露"是什么意思？为什么重要？

<details>
<summary>查看答案</summary>

1. **定义**: 只在需要时加载 Skill，不一次性加载所有 Skill
2. **原因**: Skill 指令本身占用 token，全量加载会浪费大量 token
3. **触发条件**: 根据场景、错误类型、用户意图来匹配对应 Skill
4. **Token 预算**: 每个对话有 token 限制，需要优先加载最重要的 Skill
5. **效果**: 渐进式披露让 Agent 在保持广度的同时获得深度专精
6. **Go 实现**: 用 map + 触发函数 + token 预算控制实现渐进加载

</details>

### 问题 2
为什么 Skill 要设计成"可评测可回滚"？

<details>
<summary>查看答案</summary>

1. **持续改进**: Skill 需要不断优化，每次改进都要有评估
2. **版本管理**: 每个版本有独立记录，方便追溯和比较
3. **安全回滚**: 改坏的 Skill 可以快速回滚到上一个稳定版本
4. **Ratchet 机制**: 只有评估分数提高的版本才保留，确保 Quality 不下降
5. **经验沉淀**: 历史版本记录了改进过程，形成经验库
6. **生产安全**: 大规模部署时，可以 A/B 测试不同版本 Skill

</details>

### 问题 3
如何评估一个 Skill 的质量？

<details>
<summary>查看答案</summary>

1. **准确率**: Agent 按 Skill 指导完成任务的比例
2. **效率**: 完成任务所需的步骤数和 token 消耗
3. **稳定性**: 在不同输入下的一致性表现
4. **可维护性**: Skill 文档是否清晰，是否容易理解和修改
5. **用户反馈**: 用户对 Agent 按照 Skill 执行结果的满意度
6. **Go 实现**: 用自动化测试 + 人工评估 + 用户反馈三维度评分

</details>

---

*本文档基于 Datawhale hello-agents Extra08 社区贡献整理，内容经过精简和 Go 化改造。*
*Skill 写作的核心：写给 AI 读，不是写给人读。*
