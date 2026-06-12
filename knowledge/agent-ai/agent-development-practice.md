# Agent 应用开发实践踩坑与经验分享

> 基于 Datawhale hello-agents Extra09 社区贡献整理

---

## 第一部分：入门引导（5 分钟速览）

### 为什么 Agent 开发容易踩坑？

Agent 应用开发和其他软件开发最大的不同：
- **不确定性**: LLM 输出不可控，同样的输入可能得到完全不同的结果
- **组合爆炸**: 工具调用、记忆检索、规划决策相互影响，错误会放大
- **调试困难**: 传统 debug 方法（断点、日志）对 LLM 推理过程帮助有限
- **渐进式恶化**: 小问题在多次迭代后累积成大问题

### 踩坑地图

| 类别 | 高频坑点 | 严重程度 |
|------|---------|---------|
| **Prompt** | 指令模糊、上下文窗口溢出、幻觉放大 | ⭐⭐⭐⭐⭐ |
| **管道** | 中间结果错误累积、错误传递放大 | ⭐⭐⭐⭐ |
| **工具** | 调用失败、参数格式错误、超时 | ⭐⭐⭐ |
| **记忆** | 记忆污染、检索不准确、冲突解决 | ⭐⭐⭐⭐ |
| **评估** | 指标与真实体验不符、缺少回归测试 | ⭐⭐⭐⭐⭐ |

### 调试策略

1. **逐步验证**: 每一步都检查输出质量，不要等到最后才发现错误
2. **简化复现**: 把复杂问题简化成最小复现案例
3. **隔离变量**: 一次只改一个变量，观察影响
4. **日志追踪**: 记录完整的推理链，方便回溯

---

## 第二部分：源码级深度

### 2.1 管道命令事故 — Go 实现

```go
package agentpipeline

import (
	"context"
	"fmt"
	"sync"
	"time"
)

// PipelineStep 管道中的一步
type PipelineStep struct {
	Name       string
	Func       func(context.Context, StepInput) (StepOutput, error)
	Timeout    time.Duration
	RetryCount int
}

// StepInput/Output 是管道各步骤之间的数据传递
type StepInput struct {
	Query       string
	Context     map[string]interface{}
	PreviousOutput map[string]interface{}
	Errors      []error
}

type StepOutput struct {
	Result      interface{}
	Metadata    map[string]interface{}
	IsSuccess   bool
}

// AgentPipeline 执行管道
type AgentPipeline struct {
	steps    []PipelineStep
	errorLog []string
	mu       sync.Mutex
}

// 管道事故现场：第一次看见"不可诊断"有多致命
// 问题：当管道中某一步失败时，错误信息不够详细，
// 导致无法定位问题根源

func (p *AgentPipeline) Run(ctx context.Context, input StepInput) (StepOutput, error) {
	currentInput := input
	
	for i, step := range p.steps {
		// ❌ 问题 1: 超时设置太短，没有合理默认值
		stepCtx, cancel := context.WithTimeout(ctx, step.Timeout)
		defer cancel()
		
		// ❌ 问题 2: 错误信息不够详细
		output, err := step.Func(stepCtx, currentInput)
		if err != nil {
			p.mu.Lock()
			p.errorLog = append(p.errorLog, fmt.Sprintf(
				"Step %d failed: %v", i, err,
			))
			p.mu.Unlock()
			
			// 直接返回，不继续执行
			return StepOutput{}, fmt.Errorf("step %d failed: %w", i, err)
		}
		
		currentInput.PreviousOutput[step.Name] = output
		currentInput.Errors = nil // 清除之前的错误
	}
	
	return currentInput.PreviousOutput, nil
}
```

### 2.2 问题修复 — Go 实现

```go
// 修复后的管道
type RobustPipeline struct {
	steps    []PipelineStep
	metrics  *MetricsCollector
	mu       sync.Mutex
}

type MetricsCollector struct {
	stepDuration map[string]time.Duration
	stepErrors   map[string]int
	stepRetries  map[string]int
	mu           sync.Mutex
}

// 修复 1: 详细的错误信息
func (p *RobustPipeline) runStep(
	ctx context.Context,
	step PipelineStep,
	input StepInput,
) (StepOutput, error) {
	// 记录开始
	start := time.Now()
	defer func() {
		p.metrics.recordDuration(step.Name, time.Since(start))
	}()
	
	// 增加重试机制
	var lastErr error
	for attempt := 0; attempt <= step.RetryCount; attempt++ {
		output, err := step.Func(ctx, input)
		if err == nil {
			return output, nil
		}
		
		lastErr = err
		p.metrics.recordError(step.Name, attempt)
		
		// 记录详细错误信息
		fmt.Printf("[Step: %s][Attempt: %d] Error: %v\n", 
			step.Name, attempt, err)
		
		// 指数退避重试
		if attempt < step.RetryCount {
			backoff := time.Duration(1<<uint(attempt)) * time.Second
			time.Sleep(backoff)
		}
	}
	
	return StepOutput{}, fmt.Errorf(
		"step %s failed after %d attempts: %w",
		step.Name, step.RetryCount+1, lastErr,
	)
}

// 修复 2: 管道中间结果验证
func (p *RobustPipeline) validateStepOutput(
	stepName string,
	output StepOutput,
	input StepInput,
) error {
	// 检查输出格式
	if output.Result == nil {
		return fmt.Errorf("step %s returned nil result", stepName)
	}
	
	// 检查输出长度
	resultStr := fmt.Sprintf("%v", output.Result)
	if len(resultStr) > 10000 {
		return fmt.Errorf("step %s output too long: %d chars", 
			stepName, len(resultStr))
	}
	
	// 检查关键信息是否包含
	if stepName == "retrieval" {
		// 检索步骤必须返回至少一个结果
		if len(resultStr) < 10 {
			return fmt.Errorf("retrieval returned insufficient results")
		}
	}
	
	return nil
}

// 修复 3: 可观测性 — 完整的 tracing
type Trace struct {
	TraceID   string
	StepName  string
	Input     StepInput
	Output    StepOutput
	StartTime time.Time
	EndTime   time.Time
	Error     error
	Tags      map[string]string
}

func (p *RobustPipeline) recordTrace(trace Trace) {
	p.mu.Lock()
	defer p.mu.Unlock()
	
	// 记录到追踪系统
	p.metrics.recordTrace(trace)
	
	// 慢步骤告警
	duration := trace.EndTime.Sub(trace.StartTime)
	if duration > 5*time.Second {
		fmt.Printf("[SLOW STEP] %s took %v\n", trace.StepName, duration)
	}
	
	// 错误告警
	if trace.Error != nil {
		fmt.Printf("[STEP ERROR] %s: %v\n", trace.StepName, trace.Error)
	}
}
```

### 2.3 Prompt 调试边界问题 — Go 实现

```go
package prompt

// Prompt 调试不是在"调参数"，而是在"找边界"
// 找到 LLM 能稳定工作的输入范围

type PromptDebugger struct {
	BasePrompt string
	TestCase   []TestCase
}

type TestCase struct {
	Input    string
	Expected string
	MaxTokens int
}

// 找边界：逐步测试 Prompt 的极限
func (d *PromptDebugger) FindBoundaries() []BoundaryResult {
	var results []BoundaryResult
	
	// 测试 1: 不同输入长度
	for _, tc := range d.TestCase {
		for tokens := 100; tokens <= tc.MaxTokens; tokens += 100 {
			result := d.testWithTokenLimit(tc, tokens)
			results = append(results, result)
			
			if !result.Passed {
				// 找到边界了
				break
			}
		}
	}
	
	// 测试 2: 不同复杂度
	for _, complexity := range []string{"simple", "medium", "complex"} {
		result := d.testWithComplexity(complexity)
		results = append(results, result)
	}
	
	return results
}

// 边界结果
type BoundaryResult struct {
	TestCase  TestCase
	Tokens    int
	Complexity string
	Passed    bool
	Error     error
	Confidence float64 // 信心分数
}

// 核心思想：
// 1. Prompt 调试不是"调参"，而是找边界
// 2. 找到 LLM 稳定工作的输入范围
// 3. 超出范围的行为是不可预测的
// 4. 生产系统需要在边界内运行
```

---

## 第三部分：实战经验总结

### 3.1 天崩开局 — 经验教训

**场景**: 一开始就想用复杂的 Multi-Agent 架构

**问题**: 复杂度失控，debug 困难，效果反而不如简单方案

**教训**: 
1. 从简单方案开始（单 Agent + 好 Prompt）
2. 验证效果后再增加复杂度
3. 每一步复杂度增加都要有明确的收益评估

### 3.2 推倒重来 — 经验教训

**场景**: 发现基础架构有问题，需要重构

**问题**: 重构成本高昂，进度延误

**教训**:
1. 架构设计阶段多做验证
2. 保持接口稳定，实现可变
3. 模块化设计，方便局部重构

---

## 第四部分：自测题

### 问题 1
为什么 Agent 管道中的一步失败会导致"不可诊断"的问题？

<details>
<summary>查看答案</summary>

1. **错误信息不足**: 默认错误消息缺少上下文，无法定位问题
2. **错误累积**: 前面的错误在后续步骤中被放大
3. **重试机制缺失**: 没有重试，一次失败就整个管道崩溃
4. **日志不完整**: 缺少 trace ID，无法关联多次调用
5. **修复方案**: 
   - 详细的错误信息（包含步骤名、输入、输出）
   - 重试机制（指数退避）
   - 完整的 tracing 系统
   - 中间结果验证

</details>

### 问题 2
Prompt 调试中"找边界"是什么意思？

<details>
<summary>查看答案</summary>

1. **定义**: 找到 LLM 能稳定工作的输入范围
2. **测试方法**: 
   - 不同输入长度（100 tokens → max tokens）
   - 不同复杂度（simple → medium → complex）
   - 不同领域（通用 → 专业领域）
3. **边界发现**: 
   - 超过一定长度，LLM 开始忽略前面指令
   - 复杂度高时，LLM 输出质量明显下降
   - 专业领域词汇超出训练数据范围时，幻觉增加
4. **生产应用**: 只在测试通过的范围内运行
5. **监控**: 实时监控输入长度和复杂度，超出边界时告警

</details>

### 问题 3
为什么 Multi-Agent 系统比单 Agent 系统更难调试？

<details>
<summary>查看答案</summary>

1. **错误传播**: 一个 Agent 的错误会传递到其他 Agent
2. **状态管理**: 多个 Agent 的状态同步困难
3. **并发问题**: 多个 Agent 同时运行时，竞态条件更难复现
4. **调试粒度**: 需要同时跟踪多个 Agent 的推理链
5. **修复方案**:
   - 每个 Agent 独立测试，保证单个 Agent 正确
   - 定义清晰的 Agent 间接口
   - 完整的 tracing 和日志
   - 从简单到复杂逐步增加 Agent 数量

</details>

---

*本文档基于 Datawhale hello-agents Extra09 社区贡献整理，内容经过精简和 Go 化改造。*
*核心教训：从简单开始，逐步增加复杂度，每一步都要验证。*
