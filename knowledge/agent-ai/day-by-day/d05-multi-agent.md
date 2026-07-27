---
*今天花 60-90 分钟：前 5 分钟入门，40 分钟源码分析，15 分钟动手验证*
*答不出自测题？回去重读对应章节。*

---

### Multi-Agent 系统的 Go 实现

```go
package multiagent

import (
	"context"
	"fmt"
	"sync"
)

type Agent struct {
	ID     string
	Role   string
	Tools  []string
	mu     sync.Mutex
	memory []string
}

type Message struct {
	From      string
	To        string
	Content   string
	Timestamp int64
}

type Coordinator struct {
	agents map[string]*Agent
	mu     sync.Mutex
	msgLog []Message
}

func NewCoordinator() *Coordinator {
	return &Coordinator{agents: make(map[string]*Agent), msgLog: make([]Message, 0)}
}

func (c *Coordinator) RegisterAgent(agent *Agent) {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.agents[agent.ID] = agent
}

func (c *Coordinator) SendMessage(from, to, content string) {
	c.mu.Lock()
	defer c.mu.Unlock()
	msg := Message{From: from, To: to, Content: content}
	c.msgLog = append(c.msgLog, msg)

	agent, ok := c.agents[to]
	if ok {
		agent.mu.Lock()
		agent.memory = append(agent.memory, content)
		agent.mu.Unlock()
	}
}

func (c *Coordinator) GetAgentMemory(agentID string) []string {
	c.mu.Lock()
	defer c.mu.Unlock()
	if agent, ok := c.agents[agentID]; ok {
		agent.mu.Lock()
		defer agent.mu.Unlock()
		result := make([]string, len(agent.memory))
		copy(result, agent.memory)
		return result
	}
	return nil
}

func main() {
	coord := NewCoordinator()
	coord.RegisterAgent(&Agent{ID: "researcher", Role: "research", Tools: []string{"search"}})
	coord.RegisterAgent(&Agent{ID: "writer", Role: "writer", Tools: []string{"write"}})

	coord.SendMessage("researcher", "writer", "Go is a compiled language")
	coord.SendMessage("writer", "researcher", "Thanks, I'll incorporate this")

	mem := coord.GetAgentMemory("writer")
	fmt.Printf("Writer memory: %v\n", mem)
	fmt.Printf("Total messages: %d\n", len(coord.msgLog))
}
```

---

## 自测题

### 问题 1
Multi-Agent 系统中为什么需要 Coordinator（协调器）而不是让 Agent 直接通信？

<details>
<summary>查看答案</summary>

1. Coordinator 提供全局视图，可以路由和优化任务分配
2. 避免 Agent 之间的循环依赖和死锁
3. 统一的日志和监控入口
4. 支持动态调整 Agent 角色和职责

</details>

### 问题 2
Go 的 channel 在 Multi-Agent 通信中为什么比共享内存更安全？

<details>
<summary>查看答案</summary>

1. Go 的哲学：不要通过共享内存通信，通过通信共享内存
2. channel 天然保证数据一致性，不需要 mutex
3. 死锁更容易检测（goroutine 阻塞在 channel 上）
4. 消息传递天然支持异步和解耦

</details>
### 问题 3
多 Agent 通信中如何保证消息顺序的一致性？

<details>
<summary>查看答案</summary>

1. **单 channel 顺序**：同一个 receiver 使用单一 channel，go 保证 FIFO 交付顺序
2. **带序号的消息**：每条消息携带 sequence number，receiver 按序重组乱序到达的包
3. **sharded channel**：按 message.key hash 分到不同 channel，相同 key 的消息必走同 channel 保序
4. **Barrier 同步**：在关键处理阶段使用 sync.WaitGroup 确保所有 agent 完成上一步再进入下一步
5. **日志重放**：所有消息写入持久化 log，系统重启后可从最后已处理的 sequence 号重放恢复状态
</details>
