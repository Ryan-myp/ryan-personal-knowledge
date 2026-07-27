│  • Rebalance 是控制平面协议，不涉及数据面传输              │
│  • 零拷贝 (sendfile/sendFile) 只在 FetchRequest/          │
│    ReadRequest 数据面传输                                │
└──────────────────────────────────────────────────────────┘
```

---

### Kafka Rebalance 的 Go 实现

```go
package kafka

import (
	"fmt"
	"sort"
	"sync"
)

type Consumer struct {
	ID         string
	Topic      string
	Partitions []int
}

type StickyAssignor struct {
	consumers  []*Consumer
	consumerSet map[string]*Consumer
	mu         sync.Mutex
}

func NewStickyAssignor() *StickyAssignor {
	return &StickyAssignor{consumerSet: make(map[string]*Consumer)}
}

func (a *StickyAssignor) AddConsumer(c *Consumer) {
	a.mu.Lock()
	defer a.mu.Unlock()
	a.consumers = append(a.consumers, c)
	a.consumerSet[c.ID] = c
}

func (a *StickyAssignor) Rebalance(topics []string, totalParts map[string]int) map[string][]int {
	a.mu.Lock()
	defer a.mu.Unlock()

	assigned := make(map[string][]int)
	for _, c := range a.consumers {
		assigned[c.ID] = []int{}
	}

	for _, topic := range topics {
		parts := totalParts[topic]
		count := len(a.consumers)
		if count == 0 { continue }
		for i := 0; i < parts; i++ {
			assignee := a.consumers[i%count]
			assigned[assignee.ID] = append(assigned[assignee.ID], i)
		}
	}
	return assigned
}

type GroupCoordinator struct {
	groups map[string][]*Consumer
	mu     sync.Mutex
}

func NewGroupCoordinator() *GroupCoordinator {
	return &GroupCoordinator{groups: make(map[string][]*Consumer)}
}

func (gc *GroupCoordinator) JoinGroup(groupID, consumerID string) {
	gc.mu.Lock()
	defer gc.mu.Unlock()
	c := &Consumer{ID: consumerID}
	gc.groups[groupID] = append(gc.groups[groupID], c)
}

func main() {
	assignor := NewStickyAssignor()
	assignor.AddConsumer(&Consumer{ID: "c1", Topic: "events"})
	assignor.AddConsumer(&Consumer{ID: "c2", Topic: "events"})
	assignor.AddConsumer(&Consumer{ID: "c3", Topic: "events"})
	result := assignor.Rebalance([]string{"events"}, map[string]int{"events": 6})
	for cid, parts := range result {
		fmt.Printf("  %s: partitions %v\n", cid, parts)
	}
}
```

---

## 自测题

### 问题 1
StickyAssignor 相比 RoundRobinAssignor 的优缺点是什么？

<details>
<summary>查看答案</summary>

1. **StickyAssignor**：最小化重平衡时的分区迁移
2. **RoundRobin**：每次重平衡都重新均匀分配
3. StickyAssignor 适合分区多、消费者少的场景，减少网络传输
4. RoundRobin 实现简单，适合分区少、消费者多的场景

</details>

### 问题 2
Kafka 的 Rebalance 过程中，为什么消费者会短暂不可用？

<details>
<summary>查看答案</summary>

1. Rebalance 是控制平面操作，需要协调所有消费者
2. 旧分区分配在 Rebalance 完成后才失效
3. 在 Rebalance 期间，消费者不能发送或接收消息
4. 解决方案：使用 StickyAssignor + 减少重平衡频率

</details>
### 问题 3
StickyAssignor 如何实现分区分配的状态保持？

<details>
<summary>查看答案</summary>

```go
type StickyAssignor struct {
    assignments map[string]map[int]string // partition → consumer
}

func (sa *StickyAssignor) Assign(
    consumers []string, 
    partitions int,
) map[int]string {
    // 1. 排序消费者和分区
    sort.Strings(consumers)
    sort.Ints(sa.partitions)
    
    n := len(consumers) * partitions / len(consumers)
    
    // 2. 生成基础轮询分配
    assignment := make(map[int]string)
    for i := 0; i < partitions; i++ {
        assignment[i] = consumers[i%n]
    }
    
    // 3. 如果现有分配差异大，才触发新的重新平衡
    if sa.isAssignmentDiffers(assignment) {
        // 最小化变更：只移动必要的分区
        sa.optimizeForMinimalMigration(consumers, assignment)
    }
    
    return assignment
}

func (sa *StickyAssignor) isAssignmentDiffers(
    newAssign map[int]string,
) bool {
    // 比较新旧分配的差异，只有在差异超过阈值时触发 rebalance
    changes := 0
    for p, c := range newAssign {
        if old, exists := sa.assignments[p]; !exists || old != c {
            changes++
        }
    }
    return changes > len(partitions)/4 // 允许最多25%的变化
}
```

核心要点：
1. **状态保持**：Assignor维护已分配状态，对比新旧差异
2. **最小迁移**：只有当差异超过阈值（25%）时才重新分配
3. **消费者存活检测**：通过心跳判断消费者是否存活
4. **分区亲和性**：尽量将同一消费者的分区留在同一Broker附近
5. **避免震荡**：减少不必要的Rebalance，提高集群稳定性

</details>
