---
*这份路线图由浅入深，每天有明确的学习目标和自测标准。*  
*完成 7 天后，你对 Agent 技术的理解将达到源码级深度。*

---

## 自测题

### 问题 1
为什么学习路线把 RAG 放在 Agent 核心模式之前而不是之后？

<details>
<summary>查看答案</summary>

RAG 是**数据层**，Agent 是**控制层**。理解 RAG 先掌握：
1. 向量检索和 Embedding —— 这是 Agent 的知识来源
2. Prompt Engineering —— Agent 的沟通方式
3. LLM API 调用 —— Agent 的执行引擎

掌握了 RAG 后再学 Agent 模式（Planner、ReAct、Multi-Agent），就能专注于控制流和架构设计，不用同时纠结数据层问题。

</details>

### 问题 2
"答不出自测题就回去重读"这条规则的核心目的是什么？

<details>
<summary>查看答案</summary>

**费曼技巧的逆向应用**：
- 能写出好题目 = 理解了核心概念
- 能答出问题 = 验证了自己真的懂了
- 答不出 = 以为自己懂了但实际没懂（达克效应）

这条规则强制你在"感觉懂了"之后再做一轮客观验证，避免虚假自信。

</details>

---

### 学习路线的 Go 实现

```go
package learnroadmap

import (
	"fmt"
	"sync"
	"time"
)

type Module struct {
	Name      string
	Topic     string
	Completed bool
}

type ModuleTracker struct {
	modules   []*Module
	mu        sync.Mutex
	startTime time.Time
}

func NewModuleTracker() *ModuleTracker {
	return &ModuleTracker{
		modules: []*Module{
			{Name: "Day 1", Topic: "Agent Basics"},
			{Name: "Day 2", Topic: "ReAct Pattern"},
			{Name: "Day 3", Topic: "RAG Pipeline"},
			{Name: "Day 4", Topic: "RAG Optimization"},
			{Name: "Day 5", Topic: "Multi-Agent"},
			{Name: "Day 6", Topic: "Production"},
			{Name: "Day 7", Topic: "Observability"},
		},
		startTime: time.Now(),
	}
}

func (t *ModuleTracker) Complete(idx int) {
	t.mu.Lock()
	defer t.mu.Unlock()
	if idx >= 0 && idx < len(t.modules) {
		t.modules[idx].Completed = true
	}
}

func (t *ModuleTracker) Status() string {
	t.mu.Lock()
	defer t.mu.Unlock()
	done := 0
	var remaining []string
	for _, m := range t.modules {
		if m.Completed { done++ } else { remaining = append(remaining, m.Topic) }
	}
	days := time.Since(t.startTime).Hours() / 24
	return fmt.Sprintf("%d/7 done (%.1f days), remaining: %v", done, days, remaining)
}

func main() {
	tracker := NewModuleTracker()
	tracker.Complete(0)
	tracker.Complete(1)
	fmt.Printf("Status: %s\n", tracker.Status())
}
```