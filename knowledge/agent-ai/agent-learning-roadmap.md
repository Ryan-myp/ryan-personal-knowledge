---
*基于微信读书《Agent设计模式》《智能体一本通》《大模型RAG实战》《AI Agent开发》整理*

---

## 自测题

### 问题 1
为什么 Agent 学习路线要分基础→进阶→专家→实战四个阶段而不是三个阶段？

<details>
<summary>查看答案</summary>

**基础**阶段是通用 AI/ML 知识（不需要 Agent 专业知识），**进阶**阶段学 Agent 核心模式，**专家**阶段深入源码和优化，**实战**阶段是完整系统落地。每个阶段有明确的交付物和质量门槛，保证不会跳过关键环节。

</details>

### 问题 2
Go 的 `Tool` 接口为什么同时包含 `Name()` 和 `Execute()` 两个方法？

<details>
<summary>查看答案</summary>

`Name()` 供注册表和调度器使用，`Execute()` 供实际执行。分离后可以：1）通过名字查找工具 2）注册表可以列出所有可用工具 3）工具可以热插拔。

</details>

---

### Agent 学习路线的 Go 实现

```go
package roadmap

import (
	"fmt"
	"sync"
)

type Stage string
const (
	StageBasic    Stage = "BASIC"
	StageAdvanced Stage = "ADVANCED"
	StageExpert   Stage = "EXPERT"
	StagePractical Stage = "PRACTICAL"
)

type Milestone struct {
	Name    string
	Stage   Stage
	Done    bool
}

type LearningRoadmap struct {
	milestones []*Milestone
	mu         sync.Mutex
}

func NewRoadmap() *LearningRoadmap {
	return &LearningRoadmap{
		milestones: []*Milestone{
			{Name: "Learn Go basics", Stage: StageBasic, Done: false},
			{Name: "Implement Tool interface", Stage: StageBasic, Done: false},
			{Name: "Build ReAct agent", Stage: StageAdvanced, Done: false},
			{Name: "Add RAG pipeline", Stage: StageAdvanced, Done: false},
			{Name: "Multi-agent coordination", Stage: StageExpert, Done: false},
			{Name: "Production deployment", Stage: StagePractical, Done: false},
		},
	}
}

func (r *LearningRoadmap) Complete(name string) bool {
	r.mu.Lock()
	defer r.mu.Unlock()
	for _, m := range r.milestones {
		if m.Name == name && !m.Done {
			m.Done = true
			return true
		}
	}
	return false
}

func (r *LearningRoadmap) Progress() (int, int) {
	r.mu.Lock()
	defer r.mu.Unlock()
	done := 0
	for _, m := range r.milestones {
		if m.Done { done++ }
	}
	return done, len(r.milestones)
}

func main() {
	roadmap := NewRoadmap()
	roadmap.Complete("Learn Go basics")
	roadmap.Complete("Implement Tool interface")
	roadmap.Complete("Build ReAct agent")
	done, total := roadmap.Progress()
	fmt.Printf("Progress: %d/%d milestones done\n", done, total)
}
```