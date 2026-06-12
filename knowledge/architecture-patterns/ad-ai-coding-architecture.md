---

## 自测题

### 问题 1
广告平台 AI 编码架构中，为什么需要知识图谱而不是简单的文档检索？

<details>
<summary>查看答案</summary>

1. **语义关联**：知识图谱能表达实体间的多跳关系
2. **结构化**：文档是自由的，知识图谱是结构化的
3. **推理能力**：可以根据关系推导出新信息
4. **多平台**：Google/Meta/TikTok 的 API 关系可以用图谱统一表达

</details>

### 问题 2
在知识图谱中如何实现多跳查询（Multi-hop Query）？

<details>
<summary>查看答案</summary>

1. **BFS 遍历**：从起点开始广度优先搜索
2. **限制深度**：避免遍历整个图
3. **Go 实现**：
```go
func (kg *KnowledgeGraph) MultiHopQuery(start, targetLabel string, depth int) []*Node {
    visited := make(map[string]bool)
    queue := []string{start}
    results := []*Node{}
    
    for d := 0; d < depth && len(queue) > 0; d++ {
        nextQueue := []string{}
        for _, current := range queue {
            if visited[current] {
                continue
            }
            visited[current] = true
            
            if node := kg.nodes[current]; node != nil && node.Label == targetLabel {
                results = append(results, node)
            }
            
            for _, edge := range kg.edges[current] {
                nextQueue = append(nextQueue, edge.To)
            }
        }
        queue = nextQueue
    }
    
    return results
}
```
4. **广告平台场景**：广告主 → 广告计划 → 广告组 → 创意

</details>

### 问题 3
Go 的泛型在知识图谱节点管理中有什么优势？

<details>
<summary>查看答案</summary>

1. **类型安全**：编译期检查，避免 runtime panic
2. **性能**：泛型消除类型断言开销
3. **Go 实现**：
```go
type Node[T any] struct {
    ID    string
    Props map[string]T
}

type Graph[K comparable, V any] struct {
    nodes map[K]*Node[V]
}

func (g *Graph[K, V]) Add(key K, node *Node[V]) {
    g.nodes[key] = node
}
```
4. **适用场景**：不同类型的节点（用户、广告、创意）用不同泛型参数

</details>

---

*本文档基于广告平台 AI 编码架构整理。*

### 问题 2
Go 的 interface{} 在 biz-delivery 的知识图谱查询中为什么不太合适？

<details>
<summary>查看答案</summary>

1. **类型安全**：知识图谱节点/边有明确结构，interface{} 丢失类型信息
2. **性能**：类型断言有运行时开销
3. **泛型替代**：Go 1.18+ 的泛型更适合类型安全的图谱操作
4. **维护性**：强类型代码更容易维护和理解

</details>

---

## Go 代码示例

### 广告平台知识图谱查询

```go
package knowledgegraph

import (
    "context"
    "fmt"
)

type Node struct {
    ID    string
    Label string
    Props map[string]interface{}
}

type Edge struct {
    From    string
    To      string
    Label   string
    Weight  float64
}

type KnowledgeGraph struct {
    nodes map[string]*Node
    edges map[string][]*Edge
}

func NewKnowledgeGraph() *KnowledgeGraph {
    return &KnowledgeGraph{
        nodes: make(map[string]*Node),
        edges: make(map[string][]*Edge),
    }
}

func (kg *KnowledgeGraph) AddNode(node *Node) {
    kg.nodes[node.ID] = node
}

func (kg *KnowledgeGraph) AddEdge(edge *Edge) {
    kg.edges[edge.From] = append(kg.edges[edge.From], edge)
}

func (kg *KnowledgeGraph) Query(ctx context.Context, label string) []*Node {
    var results []*Node
    for _, node := range kg.nodes {
        if node.Label == label {
            results = append(results, node)
        }
    }
    return results
}

func (kg *KnowledgeGraph) FindRelated(ctx context.Context, nodeID string, depth int) []*Node {
    if depth <= 0 {
        return nil
    }
    
    visited := make(map[string]bool)
    var results []*Node
    queue := []string{nodeID}
    
    for len(queue) > 0 {
        current := queue[0]
        queue = queue[1:]
        
        if visited[current] {
            continue
        }
        visited[current] = true
        
        for _, edge := range kg.edges[current] {
            if !visited[edge.To] {
                node := kg.nodes[edge.To]
                if node != nil {
                    results = append(results, node)
                    queue = append(queue, edge.To)
                }
            }
        }
    }
    
    return results
}
```

---

*本文档基于广告平台 AI 编码架构整理。*