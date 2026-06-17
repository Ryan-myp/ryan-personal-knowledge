# Graph Agent 可视化编排深度：可视化 Agent 工作流编排

> 用图形化界面编排 Agent 工作流，支持节点拖拽、条件分支、并行执行

---

## 第一部分：为什么需要 Graph Agent？

### 线性 Agent 的局限

```
线性 Agent（顺序执行）：
1. 用户输入 → 意图识别 → 工具选择 → 执行 → 返回
2. 问题：
   - 无法处理复杂的多步骤任务
   - 无法并行执行
   - 无法根据条件分支
   - 无法复用子流程

Graph Agent（图编排）：
1. 用户输入 → 图执行引擎 → 节点执行 → 返回
2. 优势：
   - 支持复杂的多步骤工作流
   - 支持并行执行
   - 支持条件分支
   - 支持子图复用
```

### Graph 的核心概念

```
Graph = 节点(Node) + 边(Edge) + 执行引擎(Execution Engine)

节点(Node):
- Start: 入口节点
- Agent: 执行 Agent
- Tool: 调用工具
- Condition: 条件判断
- Parallel: 并行执行
- End: 出口节点

边(Edge):
- 连接节点的有向边
- 决定执行顺序

执行引擎:
- 遍历图，按边执行节点
- 处理条件分支和并行
```

---

## 第二部分：Graph 数据结构

### 核心结构

```go
// NodeType 节点类型
type NodeType string

const (
	NodeStart      NodeType = "start"
	NodeAgent      NodeType = "agent"
	NodeTool       NodeType = "tool"
	NodeCondition  NodeType = "condition"
	NodeParallel   NodeType = "parallel"
	NodeEnd        NodeType = "end"
)

// Node 节点
type Node struct {
	ID          string            `json:"id"`
	Name        string            `json:"name"`
	Type        NodeType          `json:"type"`
	Config      map[string]interface{} `json:"config"`  // 节点配置
	Inputs      []string          `json:"inputs"`  // 输入依赖
	Outputs     []string          `json:"outputs"` // 输出依赖
	Prompt      string            `json:"prompt"`  // Agent 提示词
	ToolName    string            `json:"tool_name"` // 工具名称
	Condition   string            `json:"condition"` // 条件表达式
}

// Edge 边
type Edge struct {
	From   string `json:"from"`
	To     string `json:"to"`
	Condition string `json:"condition"` // 条件表达式（可选）
}

// Graph 图
type Graph struct {
	ID        string            `json:"id"`
	Name      string            `json:"name"`
	Description string          `json:"description"`
	Nodes     []Node            `json:"nodes"`
	Edges     []Edge            `json:"edges"`
	Status    string            `json:"status"` // draft/published
	CreatedAt time.Time         `json:"created_at"`
	UpdatedAt time.Time         `json:"updated_at"`
}
```

### 示例：广告优化 Graph

```go
// 广告优化 Graph 定义
var AdOptimizationGraph = &Graph{
	ID:          "graph-ad-optimization",
	Name:        "广告优化工作流",
	Description: "自动检测广告异常并优化",
	Status:      "published",
	Nodes: []Node{
		{
			ID:   "start",
			Name: "开始",
			Type: NodeStart,
		},
		{
			ID:     "detect_anomalies",
			Name:   "检测异常",
			Type:   NodeTool,
			ToolName: "detect_anomalies",
			Config: map[string]interface{}{
				"entity_type": "CAMPAIGN",
			},
			Inputs: []string{"start"},
		},
		{
			ID:        "check_severity",
			Name:      "检查严重程度",
			Type:      NodeCondition,
			Condition: "anomalies.severity > 0",
			Inputs:    []string{"detect_anomalies"},
		},
		{
			ID:     "diagnose_issue",
			Name:   "诊断问题",
			Type:   NodeAgent,
			Prompt: "你是诊断专家，请分析以下异常...",
			Inputs: []string{"check_severity"},
		},
		{
			ID:     "optimize_ads",
			Name:   "优化广告",
			Type:   NodeTool,
			ToolName: "optimize_ad",
			Inputs: []string{"diagnose_issue"},
		},
		{
			ID:   "end",
			Name: "结束",
			Type: NodeEnd,
			Inputs: []string{"optimize_ads"},
		},
	},
	Edges: []Edge{
		{From: "start", To: "detect_anomalies"},
		{From: "detect_anomalies", To: "check_severity"},
		{From: "check_severity", To: "diagnose_issue", Condition: "anomalies.severity > 0"},
		{From: "diagnose_issue", To: "optimize_ads"},
		{From: "optimize_ads", To: "end"},
	},
}
```

---

## 第三部分：执行引擎

### 核心逻辑

```go
// ExecutionEngine 执行引擎
type ExecutionEngine struct {
	graph      *Graph
	nodeStates map[string]string // node_id -> state
	context    map[string]interface{}
}

// NewExecutionEngine 创建执行引擎
func NewExecutionEngine(graph *Graph) *ExecutionEngine {
	return &ExecutionEngine{
		graph:      graph,
		nodeStates: make(map[string]string),
		context:    make(map[string]interface{}),
	}
}

// Execute 执行图
func (e *ExecutionEngine) Execute(ctx context.Context) error {
	// 1. 找到起始节点
	startNode := e.findNodeByID("start")
	if startNode == nil {
		return fmt.Errorf("未找到起始节点")
	}

	// 2. 执行
	current := startNode
	for current != nil {
		e.nodeStates[current.ID] = "running"

		switch current.Type {
		case NodeAgent:
			if err := e.executeAgentNode(ctx, current); err != nil {
				return err
			}
		case NodeTool:
			if err := e.executeToolNode(ctx, current); err != nil {
				return err
			}
		case NodeCondition:
			next, err := e.executeConditionNode(current)
			if err != nil {
				return err
			}
			current = next
			continue
		case NodeEnd:
			e.nodeStates[current.ID] = "completed"
			return nil
		}

		e.nodeStates[current.ID] = "completed"

		// 3. 找到下一个节点
		current = e.findNextNode(current.ID)
	}

	return nil
}

// executeAgentNode 执行 Agent 节点
func (e *ExecutionEngine) executeAgentNode(ctx context.Context, node *Node) error {
	// 构建提示词
	prompt := node.Prompt
	if prompt == "" {
		prompt = "请处理以下请求"
	}

	// 注入上下文
	for k, v := range e.context {
		prompt += fmt.Sprintf("\n%s: %v", k, v)
	}

	// 模拟 LLM 执行
	fmt.Printf("  🤖 执行 Agent 节点: %s\n", node.Name)
	e.context[node.ID] = map[string]interface{}{
		"status":  "completed",
		"result":  "Agent 处理完成",
	}
	return nil
}

// executeToolNode 执行工具节点
func (e *ExecutionEngine) executeToolNode(ctx context.Context, node *Node) error {
	fmt.Printf("  ⚙️  执行工具节点: %s (%s)\n", node.Name, node.ToolName)
	e.context[node.ID] = map[string]interface{}{
		"status":  "completed",
		"result":  "工具执行完成",
	}
	return nil
}

// executeConditionNode 执行条件节点
func (e *ExecutionEngine) executeConditionNode(node *Node) (*Node, error) {
	fmt.Printf("  🔀 执行条件节点: %s\n", node.Name)

	// 模拟条件判断
	hasAnomalies := true // 实际项目中这里会解析 condition 表达式
	if hasAnomalies {
		return e.findNodeByID("diagnose_issue"), nil
	}
	return e.findNodeByID("end"), nil
}

// findNextNode 找到下一个节点
func (e *ExecutionEngine) findNextNode(fromID string) *Node {
	for _, edge := range e.graph.Edges {
		if edge.From == fromID {
			return e.findNodeByID(edge.To)
		}
	}
	return nil
}

// findNodeByID 根据 ID 查找节点
func (e *ExecutionEngine) findNodeByID(id string) *Node {
	for _, node := range e.graph.Nodes {
		if node.ID == id {
			return &node
		}
	}
	return nil
}
```

---

## 第四部分：并行执行

### 并行节点

```go
// executeParallelNode 执行并行节点
func (e *ExecutionEngine) executeParallelNode(ctx context.Context, node *Node) error {
	fmt.Printf("  ⚡ 执行并行节点: %s\n", node.Name)

	// 找到所有并行分支
	var branches []string
	for _, edge := range e.graph.Edges {
		if edge.From == node.ID {
			branches = append(branches, edge.To)
		}
	}

	// 并行执行
	var wg sync.WaitGroup
	for _, branch := range branches {
		wg.Add(1)
		go func(branchID string) {
			defer wg.Done()
			fmt.Printf("    🔄 并行执行: %s\n", branchID)
			// 实际项目中这里会并行执行子图
		}(branch)
	}

	wg.Wait()
	return nil
}
```

---

## 第五部分：可视化编排

### 前端渲染

```html
<!-- 简化的 Graph 可视化 -->
<div class="graph-container">
  <!-- 节点 -->
  <div class="node start-node" id="start">
    <div class="node-header">🟢 开始</div>
  </div>
  
  <div class="node tool-node" id="detect_anomalies">
    <div class="node-header">⚙️ 检测异常</div>
    <div class="node-body">Tool: detect_anomalies</div>
  </div>
  
  <div class="node condition-node" id="check_severity">
    <div class="node-header">🔀 检查严重程度</div>
    <div class="node-body">severity > 0 ?</div>
  </div>
  
  <div class="node agent-node" id="diagnose_issue">
    <div class="node-header">🤖 诊断问题</div>
    <div class="node-body">Agent: DiagnosticAgent</div>
  </div>
  
  <div class="node tool-node" id="optimize_ads">
    <div class="node-header">🚀 优化广告</div>
    <div class="node-body">Tool: optimize_ad</div>
  </div>
  
  <div class="node end-node" id="end">
    <div class="node-header">🔴 结束</div>
  </div>
  
  <!-- 边（SVG 绘制） -->
  <svg class="edges">
    <line x1="..." y1="..." x2="..." y2="..." />
    <!-- ... -->
  </svg>
</div>
```

---

## 第六部分：完整演示

### 运行效果

```
========================================
  广告 Agent Graph 编排演示
========================================

📊 Graph: 广告优化工作流
📝 节点: 6
🔗 边: 5

🚀 执行 Graph:

  🤖 执行 Agent 节点: 开始
  ⚙️  执行工具节点: 检测异常 (detect_anomalies)
  🔀 执行条件节点: 检查严重程度
  🤖 执行 Agent 节点: 诊断问题
  ⚙️  执行工具节点: 优化广告 (optimize_ad)
  🔴 执行结束节点: 结束

✅ Graph 执行完成!

📊 执行状态:
  - start: completed
  - detect_anomalies: completed
  - check_severity: completed
  - diagnose_issue: completed
  - optimize_ads: completed
  - end: completed

========================================
  演示完成!
========================================
```

---

## 第七部分：总结

| 组件 | 描述 | 示例 |
|------|------|------|
| **Graph** | 工作流定义 | 广告优化工作流 |
| **Node** | 执行单元 | Agent/Tool/Condition |
| **Edge** | 执行顺序 | 有向边 |
| **Execution Engine** | 执行引擎 | 遍历图执行节点 |
| **Visualization** | 可视化编排 | 前端拖拽编辑器 |

**核心思想：用图的结构表达复杂的工作流，执行引擎负责遍历和执行。**
