# Agent 面试八股与参考答案

> 基于 Datawhale hello-agents 社区贡献整理，覆盖 LLM/VLM/RLHF/Agent/RAG/评估全链路

---

## 第一部分：入门引导（5 分钟速览）

### 面试核心考点概览

| 类别 | 高频考点 | 面试深度 |
|------|---------|---------|
| **LLM** | Transformer/注意力/位置编码/GQA/MoE | ⭐⭐⭐⭐⭐ |
| **VLM** | CLIP/LLaVA架构/视觉对齐/幻觉 | ⭐⭐⭐⭐ |
| **RLHF** | PPO/DPO/GRPO奖励模型/信用分配 | ⭐⭐⭐⭐⭐ |
| **Agent** | ReAct/规划/Memory/Tool Use/Multi-Agent | ⭐⭐⭐⭐⭐ |
| **RAG** | 检索策略/Reranking/Chunking/混合检索 | ⭐⭐⭐⭐ |
| **评估** | AgentBench/IFEval/LLM-as-Judge/监控 | ⭐⭐⭐⭐ |

### 面试准备策略

1. **LLM 基础**：Transformer 自注意力机制、位置编码、GQA/MoE、Scaling Laws、解码策略
2. **Agent 核心**：ReAct 范式、规划能力、Memory 设计、Tool Use、Multi-Agent 协作
3. **训练对齐**：RLHF 三阶段、DPO vs PPO、GRPO 核心思想、信用分配
4. **RAG 优化**：查询改写、Reranking、混合检索、评估指标
5. **面试实战**：先独立思考 → 再看参考答案 → 用自己的话复述 → 结合项目经历

---

## 第二部分：源码级深度

### 2.1 自注意力机制 — Go 实现

```go
package transformer

import (
	"math"
	"matrix" // 假设的矩阵库
)

// SelfAttention 实现 Transformer 的核心注意力机制
type SelfAttention struct {
	HeadCount    int
	HeadDim      int
	QueryWeight  matrix.Matrix // [d_model, d_k * head_count]
	KeyWeight    matrix.Matrix
	ValueWeight  matrix.Matrix
	OutputWeight matrix.Matrix // [d_k * head_count, d_model]
}

func (sa *SelfAttention) Forward(x matrix.Matrix) matrix.Matrix {
	n, d := x.Shape() // n = sequence length, d = d_model
	
	// Step 1: 生成 Q, K, V
	q := matrix.MatMul(x, sa.QueryWeight)   // [n, d_k * head_count]
	k := matrix.MatMul(x, sa.KeyWeight)     // [n, d_k * head_count]
	v := matrix.MatMul(x, sa.ValueWeight)   // [n, d_v * head_count]
	
	q = sa.ReshapeForHeads(q, n) // [head_count, n, d_k]
	k = sa.ReshapeForHeads(k, n)
	v = sa.ReshapeForHeads(v, n)
	
	// Step 2: 计算注意力分数 = QK^T / sqrt(d_k)
	scale := 1.0 / math.Sqrt(float64(sa.HeadDim))
	attnScores := matrix.MatMul(q, k.Transpose()) // [head_count, n, n]
	attnScores = matrix.Scale(attnScores, scale)
	
	// Step 3: Softmax 归一化
	attnWeights := matrix.Softmax(attnScores, -1) // 在最后一个维度 softmax
	
	// Step 4: 加权求和
	output := matrix.MatMul(attnWeights, v) // [head_count, n, d_v]
	output = matrix.ConcatHeads(output) // [n, d_v * head_count]
	
	// Step 5: 输出投影
	return matrix.MatMul(output, sa.OutputWeight) // [n, d_model]
}

// MultiQueryAttention (MQA) 变体：所有 Head 共享同一组 K, V
func (sa *SelfAttention) MultiQueryForward(x matrix.Matrix) matrix.Matrix {
	n, d := x.Shape()
	
	// Q 仍然多头，K, V 全局共享
	q := matrix.MatMul(x, sa.QueryWeight)
	q = sa.ReshapeForHeads(q, n) // [head_count, n, d_k]
	
	// K, V 不需要多头重塑，直接生成
	k := matrix.MatMul(x, sa.KeyWeight) // [n, d_k]
	v := matrix.MatMul(x, sa.ValueWeight) // [n, d_v]
	
	// 注意力分数计算：[head_count, n, 1] × [1, n, d_k] → [head_count, n, n]
	scale := 1.0 / math.Sqrt(float64(sa.HeadDim))
	attnScores := matrix.Scale(
		matrix.MatMul(q, k.Transpose()), 
		scale,
	)
	
	attnWeights := matrix.Softmax(attnScores, -1)
	output := matrix.MatMul(attnWeights, v) // [head_count, n, d_v]
	output = matrix.ConcatHeads(output)
	
	return matrix.MatMul(output, sa.OutputWeight)
}

// GatedQueryAttention (GQA) 变体：group_count 组共享 K, V
// 平衡了 MHA 的质量和高推理速度的 MoE
func (sa *SelfAttention) GQAForward(x matrix.Matrix, groupCount int) matrix.Matrix {
	n, d := x.Shape()
	headCount := sa.HeadCount
	groupSize := headCount / groupCount // 每组共享 K, V 的头数
	dK := sa.HeadDim
	
	q := matrix.MatMul(x, sa.QueryWeight)
	q = sa.ReshapeForGroups(q, n, headCount, groupSize) // [group_count, group_size, n, d_k]
	
	// 每个 group 共享一组 K, V
	kGroup := matrix.MatMul(x, sa.KeyWeight)   // [n, d_k * group_count]
	vGroup := matrix.MatMul(x, sa.ValueWeight) // [n, d_v * group_count]
	kGroup = sa.ReshapeForGroups(kGroup, n, groupCount, groupSize)
	vGroup = sa.ReshapeForGroups(vGroup, n, groupCount, groupSize)
	
	var outputs []matrix.Matrix
	for g := 0; g < groupCount; g++ {
		qG := q[g]          // [group_size, n, d_k]
		kG := kGroup[g]     // [1, n, d_k]
		vG := vGroup[g]     // [1, n, d_v]
		
		scores := matrix.Scale(matrix.MatMul(qG, kG.Transpose()), 1.0/math.Sqrt(float64(dK)))
		weights := matrix.Softmax(scores, -1)
		out := matrix.MatMul(weights, vG) // [group_size, n, d_v]
		outputs = append(outputs, out)
	}
	
	output := matrix.Concat(outputs) // [head_count, n, d_v]
	output = matrix.ConcatHeads(output)
	return matrix.MatMul(output, sa.OutputWeight)
}
```

### 2.2 RLHF PPO 核心逻辑 — Go 实现

```go
package rlhf

import (
	"math"
	"matrix"
)

// PPOTrainer 实现 RLHF 的 PPO 训练循环
type PPOTrainer struct {
	PolicyModel     *PolicyModel // 策略模型（要训练的 LLM）
	ReferenceModel  *PolicyModel // 参考模型（冻结，KL 惩罚基线）
	RewardModel     *RewardModel // 奖励模型
	ActorOptimizer  *Optimizer   // Actor 优化器
	CriticOptimizer *Optimizer   // Critic 优化器
	
	// PPO 超参数
	Gamma     float64 // 折扣因子
	Lambda    float64 // GAE 参数
	Epsilon   float64 // PPO clip 范围
	KLCoef    float64 // KL 惩罚系数
	ClipRange float64 // clip 范围
}

// PPOStep 执行一步 PPO 训练
func (t *PPOTrainer) PPOStep(prompts []string, responses []string) error {
	// Step 1: 用参考模型生成基线 log probs（KL 惩罚）
	refLogProbs, _ := t.ReferenceModel.LogProbs(prompts, responses)
	
	// Step 2: 用当前策略模型生成 responses 的 log probs
	policyLogProbs, _ := t.PolicyModel.LogProbs(prompts, responses)
	
	// Step 3: 用奖励模型打分
	rewards := t.RewardModel.Predict(prompts, responses)
	
	// Step 4: 计算 advantages 和 returns（GAE）
	values := t.CriticModel.Predict(prompts, responses)
	gae := t.ComputeGAE(values, rewards, refLogProbs, policyLogProbs)
	
	// Step 5: PPO 损失
	loss := t.PPOLoss(policyLogProbs, refLogProbs, gae)
	
	// Step 6: 反向传播
	t.ActorOptimizer.Step(loss)
	
	return nil
}

// PPOLoss 计算 PPO 损失，包含 clip 和 KL 惩罚
func (t *PPOTrainer) PPOLoss(
	logProbs, refLogProbs, advantages matrix.Matrix,
) matrix.Matrix {
	// 计算概率比
	ratio := matrix.Exp(logProbs - refLogProbs)
	
	// PPO clip 损失
	surrogate1 := matrix.Mul(ratio, advantages)
	surrogate2 := matrix.Mul(
		matrix.Clip(ratio, 1-t.ClipRange, 1+t.ClipRange),
		advantages,
	)
	surrogateLoss := -matrix.Min(surrogate1, surrogate2)
	
	// KL 惩罚项
	kl := matrix.Sub(logProbs, refLogProbs)
	klLoss := matrix.Mean(matrix.Mul(kl, logProbs)) // KL(p||q) 近似
	
	return matrix.Add(surrogateLoss, matrix.Scale(klLoss, t.KLCoef))
}

// GRPO (Group Relative Policy Optimization) — DeepSeek 提出的简化 PPO 方案
// 核心思想：用同一 prompt 的多个 sampled responses 计算组内相对 advantage，
// 不需要独立的 Value/Critic 模型，大幅降低训练复杂度
type GRPOTrainer struct {
	PolicyModel *PolicyModel
	// 不需要独立的 RewardModel + CriticModel
	Gamma       float64
	Normalization bool
}

// GRPOStep 执行一步 GRPO 训练
func (t *GRPOTrainer) GRPOStep(
	prompts []string,
	groupSize int,
) error {
	// Step 1: 对每个 prompt，采样 groupSize 个 responses
	var allPrompts []string
	var allResponses [][]string
	for _, prompt := range prompts {
		responses := t.PolicyModel.Sample(prompt, groupSize)
		allResponses = append(allResponses, responses)
		for i := 0; i < groupSize; i++ {
			allPrompts = append(allPrompts, prompt)
		}
	}
	
	// Step 2: 对每组 responses 计算奖励（标准化）
	var allRewards []float64
	for _, responses := range allResponses {
		rawRewards := make([]float64, len(responses))
		for i, r := range responses {
			rawRewards[i] = t.ComputeReward(allPrompts, r)
		}
		
		// 组内标准化（减均值除标准差）
		mean, std := t.MeanStd(rawRewards)
		for _, rw := range rawRewards {
			if std > 0 {
				allRewards = append(allRewards, (rw-mean)/std)
			} else {
				allRewards = append(allRewards, 0)
			}
		}
	}
	
	// Step 3: GRPO 损失（组内相对 advantage）
	// 不需要独立的价值模型，直接用组内标准化后的奖励作为 advantage
	advantages := allRewards
	
	// Step 4: 更新策略模型（简化版 PPO，无 Critic）
	return t.UpdatePolicy(prompts, allResponses, advantages)
}

// GRPO 优势：
// 1. 不需要训练独立的 Critic/Value 模型，节省 50%+ 显存
// 2. 训练更稳定，没有 PPO 的 KL 调参负担
// 3. 计算效率更高，每组采样一次即可估计 advantage
// 劣势：
// 1. 组大小限制 advantage 估计的方差
// 2. 需要更多采样来计算稳定的组内统计量

func (t *GRPOTrainer) MeanStd(values []float64) (float64, float64) {
	var sum float64
	for _, v := range values {
		sum += v
	}
	mean := sum / float64(len(values))
	
	var varSum float64
	for _, v := range values {
		varSum += (v - mean) * (v - mean)
	}
	std := math.Sqrt(varSum / float64(len(values)))
	
	return mean, std
}
```

### 2.3 ReAct 范式 — Go 实现

```go
package react

import (
	"context"
	"fmt"
	"strings"
)

// ReActAgent 实现 ReAct (Reason + Act) 循环
// Thought → Action → Observation → Thought → ... → Final Answer
type ReActAgent struct {
	// 核心组件
	PromptBuilder *PromptBuilder  // 构建 ReAct 提示
	ToolRegistry  *ToolRegistry   // 工具注册表
	Callback      Callback        // 回调（日志/监控）
	
	// 配置
	MaxSteps     int    // 最大推理步数
	Temperature  float64 // LLM 温度参数
}

type Step struct {
	StepNum     int
	Thought     string      // 推理思考
	Action      string      // 执行的动作（工具名+参数）
	ActionInput string      // 动作参数
	Observation string      // 工具返回结果
}

func (a *ReActAgent) Run(ctx context.Context, query string) (string, error) {
	var steps []Step
	history := []string{fmt.Sprintf("User: %s", query)}
	
	for step := 1; step <= a.MaxSteps; step++ {
		// Step 1: 构建 ReAct prompt
		prompt := a.PromptBuilder.Build(history, steps)
		
		// Step 2: LLM 输出 Thought → Action → Observation
		response, err := a.CallLLM(ctx, prompt)
		if err != nil {
			return "", fmt.Errorf("LLM call failed at step %d: %w", step, err)
		}
		
		// Step 3: 解析 LLM 输出
		thought, action, actionInput := a.ParseReActOutput(response)
		
		// 检查是否是最终答案
		if strings.HasPrefix(action, "FinalAnswer") {
			return actionInput, nil
		}
		
		// Step 4: 执行工具
		observation, err := a.ExecuteTool(ctx, action, actionInput)
		if err != nil {
			observation = fmt.Sprintf("Tool error: %v", err)
		}
		
		// Step 5: 记录步骤
		steps = append(steps, Step{
			StepNum:     step,
			Thought:     thought,
			Action:      action,
			ActionInput: actionInput,
			Observation: observation,
		})
		
		// 更新 history
		history = append(history, fmt.Sprintf(
			"Thought %d: %s\nAction: %s(%s)\nObservation: %s",
			step, thought, action, actionInput, observation,
		))
	}
	
	return "", fmt.Errorf("max steps (%d) exceeded", a.MaxSteps)
}

// PlanAndSolveAgent 实现 Plan-and-Solve 范式
// 先生成完整计划，再逐步执行
type PlanAndSolveAgent struct {
	PromptBuilder *PromptBuilder
	ToolRegistry  *ToolRegistry
}

func (a *PlanAndSolveAgent) Run(ctx context.Context, query string) (string, error) {
	// Step 1: 先生成计划
	plan, err := a.GeneratePlan(ctx, query)
	if err != nil {
		return "", err
	}
	
	// Step 2: 逐步执行计划
	return a.ExecutePlan(ctx, query, plan)
}

func (a *PlanAndSolveAgent) GeneratePlan(ctx context.Context, query string) ([]PlanStep, error) {
	prompt := fmt.Sprintf(`
请为以下问题制定一个详细的执行计划：

问题: %s

请用以下格式输出计划:
1. [第一步描述]
2. [第二步描述]
3. ...
`, query)
	
	response, _ := a.CallLLM(ctx, prompt)
	// 解析 response 为 PlanStep 列表
	return a.ParsePlan(response), nil
}

// ReflectionAgent 实现 Reflection 范式
// 生成答案 → 反思批评 → 改进答案
type ReflectionAgent struct {
	Generator    *Generator
	Reflection   *Reflector
}

func (a *ReflectionAgent) Run(ctx context.Context, query string) (string, error) {
	// 第一轮：生成答案
	generated, err := a.Generator.Generate(ctx, query)
	if err != nil {
		return "", err
	}
	
	// 反射循环：反思 → 改进
	for i := 0; i < 3; i++ { // 最多 3 轮反思
		// 反思阶段：找出问题
		feedback, err := a.Reflection.Reflect(ctx, query, generated)
		if err != nil {
			break
		}
		
		// 改进阶段：根据反馈重写
		generated, err = a.Generator.Improve(ctx, query, generated, feedback)
		if err != nil {
			break
		}
	}
	
	return generated, nil
}
```

### 2.4 多智能体系统 — Go 实现

```go
package multiagent

import (
	"context"
	"sync"
)

// Agent 表示单个智能体
type Agent struct {
	ID         string
	Name       string
	Prompt     string
	Tools      []Tool
	Response   chan string
	Error      chan error
}

// Coordinator 协调多智能体协作
type Coordinator struct {
	Agents       []*Agent
	MessageBus   *MessageBus
	Logger       Logger
}

// MessageBus 智能体间通信
type MessageBus struct {
	mu         sync.RWMutex
	messages   map[string][]Message
	Subscribers map[string][]chan Message
}

type Message struct {
	From    string
	To      string
	Content string
	Timestamp int64
}

// SimpleCoordinator 简单协调器：按顺序执行
func (c *Coordinator) SimpleExecute(ctx context.Context, query string) (string, error) {
	var result string
	for _, agent := range c.Agents {
		msg := fmt.Sprintf("[%s]: %s", agent.Name, result)
		resp, err := agent.Process(ctx, msg)
		if err != nil {
			return result, err
		}
		result = resp
	}
	return result, nil
}

// HierarchicalCoordinator 分层协调器：Manager 分配任务给 Workers
func (c *Coordinator) HierarchicalExecute(
	ctx context.Context, 
	query string, 
	managerAgent *Agent,
	workerAgents []*Agent,
) (string, error) {
	// Step 1: Manager 分析任务并分配子任务
	subTasks, err := managerAgent.AnalyzeAndDistribute(ctx, query)
	if err != nil {
		return "", err
	}
	
	// Step 2: 并行执行子任务
	var wg sync.WaitGroup
	results := make(map[string]string, len(subTasks))
	
	for i, task := range subTasks {
		agent := workerAgents[i%len(workerAgents)]
		wg.Add(1)
		go func(task string, agent *Agent, idx int) {
			defer wg.Done()
			resp, err := agent.Process(ctx, task)
			if err != nil {
				agent.Error <- err
				return
			}
			results[task] = resp
		}(task, agent, i)
	}
	
	wg.Wait()
	
	// Step 3: Manager 汇总结果
	return managerAgent.Synthesize(ctx, query, results)
}

// GraphCoordinator 基于图的协调器（LangGraph 风格）
// 支持分支、回溯、人工介入
type GraphCoordinator struct {
	Graph    *ExecutionGraph
	State    *AgentState
}

type AgentState struct {
	Query        string
	CurrentStep  string
	Results      map[string]interface{}
	Conversation []ConversationTurn
}

// 执行图节点定义
type GraphNode struct {
	ID       string
	Agent    *Agent
	Edges    []GraphEdge
	Condition func(*AgentState) bool // 条件分支
}

type GraphEdge struct {
	From      string
	To        string
	Condition func(*AgentState) bool
}

// 执行图遍历
func (c *GraphCoordinator) Execute(ctx context.Context) (string, error) {
	currentNode := c.Graph.StartNode
	
	for currentNode != nil {
		// 执行当前节点
		resp, err := currentNode.Agent.Process(ctx, currentNode.ID, c.State)
		if err != nil {
			return "", err
		}
		
		// 记录状态
		c.State.Results[currentNode.ID] = resp
		c.State.CurrentStep = currentNode.ID
		
		// 查找下一个节点
		var nextNode *GraphNode
		for _, edge := range currentNode.Edges {
			if edge.Condition == nil || edge.Condition(c.State) {
				nextNode = c.Graph.FindNode(edge.To)
				break
			}
		}
		currentNode = nextNode
	}
	
	return c.State.Results[c.Graph.EndNode.ID].(string), nil
}
```

---

## 第三部分：面试问题清单

### LLM 八股（高频）

1. 请详细解释 Transformer 自注意力机制，为什么比 RNN 更适合长序列？
2. 位置编码为什么是必需的？至少两种实现方式？
3. MHA / MQA / GQA 的区别？
4. MoE 如何在不增加推理成本的情况下扩大参数规模？
5. Scaling Laws 揭示了什么关系？
6. 解码策略：Greedy / Beam / Top-K / Top-P 的原理和优缺点？
7. BPE 和 WordPiece 子词切分算法比较？

### RLHF 八股

1. RLHF 三个核心阶段是什么？每个阶段的输入输出和目标？
2. PPO 为什么选择它而不是 REINFORCE？
3. DPO 和传统 RLHF (PPO) 的区别？
4. GRPO 和 PPO 的区别？优劣？
5. 什么是 Reward Hacking？如何缓解？

### Agent 八股

1. 如何定义基于 LLM 的 Agent？核心组件？
2. ReAct 框架如何将思维链和行动结合？
3. 赋予 LLM 规划能力的主流方法？
4. Agent 短期记忆和长期记忆系统设计？
5. Tool Use / Function Calling 的原理？
6. 多智能体系统相比单 Agent 的优势和复杂性？

### RAG 八股

1. RAG 系统的核心挑战是什么？
2. 查询改写 (Query Rewriting) 为什么必要？
3. Reranking 为什么比单纯增加 topK 更好？
4. 混合检索 (BM25 + 向量) 的优势？
5. 评估 RAG 系统的指标？

---

## 第四部分：自测题

### 问题 1
Go 的 GMP 模型中，M 和 P 的关系是什么？

<details>
<summary>查看答案</summary>

1. **M (Machine)**: 真正的操作系统线程，执行 Go 代码
2. **P (Processor)**: 逻辑处理器，维护 G 队列，控制调度
3. **G (Goroutine)**: 轻量级线程，P 的队列中排队等待执行
4. **关系**: M 执行 P 的 G 队列，P 数量默认等于 CPU 核心数
5. **Work-Stealing**: P 本地队列为空时，从其他 P 偷取 G 执行
6. **Go 实现**: 每个 P 用 sync.Mutex 保护 G 队列，避免锁竞争

</details>

### 问题 2
Go 中如何实现一个线程安全的 ReAct Agent？

<details>
<summary>查看答案</summary>

1. **状态保护**: Agent 状态用 sync.RWMutex 保护
2. **工具并发**: 多个工具调用用 goroutine + WaitGroup 并行执行
3. **LLM 调用**: 用 channel 限制并发 LLM 调用数（信号量模式）
4. **日志同步**: 用 sync.Mutex 保护共享日志缓冲区
5. **错误处理**: 用 context 实现超时和取消
6. **最佳实践**: 工具注册表用 map + RWMutex，支持并发读写

</details>

### 问题 3
RLHF 中为什么用 PPO 而不是 REINFORCE？

<details>
<summary>查看答案</summary>

1. **方差降低**: PPO 用 Critic 模型估计 baseline，降低梯度方差
2. **稳定性**: PPO 的 clip 机制防止单次更新步长过大
3. **样本效率**: PPO 可以复用多轮采样数据，REINFORCE 每轮丢弃
4. **KL 约束**: PPO 内置 KL 惩罚，防止策略偏离参考模型太远
5. **实际效果**: PPO 在 LLM 对齐任务上比 REINFORCE 更稳定、效果更好
6. **GRPO 替代**: DeepSeek 的 GRPO 用组内相对 advantage，不需要独立 Critic，更轻量

</details>

### 问题 4
为什么 Agent 需要 Memory 系统？短期和长期记忆有什么区别？

<details>
<summary>查看答案</summary>

1. **短期记忆**: 当前对话的上下文，受限于 context window，token 成本高
2. **长期记忆**: 跨会话持久化，用向量数据库/RAG 存储，按需检索
3. **记忆类型**: 
   - 显式记忆：用户明确提供的信息（姓名、偏好）
   - 隐式记忆：从交互中自动提取的模式和事实
   - 程序性记忆：知道怎么做某事（工具使用经验）
4. **记忆检索**: 向量检索（语义相似度）+ 关键词检索（精确匹配）+ 时间衰减（近期记忆权重更高）
5. **记忆更新**: 需要去重、冲突解决、过期清理机制
6. **Go 实现**: 用 sync.Map 存储短期记忆，用 SQLite+FTS5 做长期记忆检索

</details>

---

*本文档基于 Datawhale hello-agents 社区贡献整理，内容经过精简和 Go 化改造。*
*面试准备：先独立思考 → 再看答案 → 用自己的话复述 → 结合项目经历。*
