# Agentic-RL 训练实战：从 SFT 到 GRPO

> 基于 Datawhale hello-agents 第 11 章 + Extra12 整理

---

## 第一部分：入门引导（5 分钟速览）

### 什么是 Agentic-RL？

Agentic-RL 是将**强化学习**应用于 Agent 训练的方法。核心思想：让 Agent 通过与环境交互，学习最优的策略。

### 训练流程总览

```
SFT (监督微调) → DPO (偏好优化) → GRPO (组相对策略优化)
```

### 核心概念

| 概念 | 说明 |
|------|------|
| **SFT** | 用高质量数据微调模型，让它学会基本能力 |
| **DPO** | 用偏好对训练，让模型学会"更喜欢哪种回答" |
| **GRPO** | 简化版 PPO，不需要独立的 Critic 模型 |
| **Reward Model** | 给 Agent 的输出打分，提供训练信号 |

### 为什么需要 Agentic-RL？

1. **通用模型不够专业**: 基础 LLM 在特定领域表现不佳
2. **对齐需求**: 需要模型输出符合人类偏好
3. **持续改进**: 通过反馈循环不断提升 Agent 能力

---

## 第二部分：源码级深度

### 2.1 SFT 训练 — Go 实现

```go
package agenticrl

import (
	"context"
	"fmt"
	"math"
	"matrix" // 假设的矩阵运算库
)

// SFTTrainer 监督微调训练器
type SFTTrainer struct {
	Model     *LLMModel
	Optimizer *Optimizer
	LossFn    LossFunction
}

// SFTData 监督微调数据
type SFTData struct {
	Prompt   string
	Response string
	Labels   []int // 输出 token 的标签
}

// TrainSFT 执行 SFT 训练
func (t *SFTTrainer) TrainSFT(ctx context.Context, data []SFTData) error {
	for _, sample := range data {
		// 1. 前向传播
		logits, _ := t.Model.Forward(sample.Prompt)
		
		// 2. 计算损失
		loss := t.LossFn.CrossEntropy(logits, sample.Labels)
		
		// 3. 反向传播
		t.Optimizer.Step(loss)
	}
	
	return nil
}

// CrossEntropy 交叉熵损失
func (t *SFTTrainer) CrossEntropy(predictions, targets []float64) float64 {
	var loss float64
	for i, pred := range predictions {
		target := targets[i]
		// 防止 log(0)
		pred = math.Max(math.Min(pred, 1.0-epsilon), epsilon)
		loss -= target * math.Log(pred)
	}
	return loss / float64(len(predictions))
}
```

### 2.2 DPO 训练 — Go 实现

```go
package agenticrl

// DPOTrainer 直接偏好优化训练器
type DPOTrainer struct {
	PolicyModel     *LLMModel // 策略模型（要训练的）
	ReferenceModel  *LLMModel // 参考模型（冻结的）
	Optimizer       *Optimizer
	Beta            float64 // KL 惩罚系数
}

// DPOResponse 偏好数据
type DPOResponse struct {
	Prompt      string
	Chosen      string // 人类偏好的回答
	Rejected    string // 人类不偏好的回答
}

// TrainDPO 执行 DPO 训练
func (t *DPOTrainer) TrainDPO(ctx context.Context, data []DPOResponse) error {
	for _, sample := range data {
		// 1. 计算 chosen 和 rejected 的 log probabilities
		chosenLogProb, _ := t.PolicyModel.LogProbs(sample.Prompt, sample.Chosen)
		rejectedLogProb, _ := t.PolicyModel.LogProbs(sample.Prompt, sample.Rejected)
		
		// 2. 计算 reference log probs（用于 KL 惩罚）
		chosenRefLogProb, _ := t.ReferenceModel.LogProbs(sample.Prompt, sample.Chosen)
		rejectedRefLogProb, _ := t.ReferenceModel.LogProbs(sample.Prompt, sample.Rejected)
		
		// 3. DPO 损失
		diff := (chosenLogProb - rejectedLogProb) - (chosenRefLogProb - rejectedRefLogProb)
		loss := -math.Log(sigmoid(t.Beta * diff))
		
		// 4. 反向传播
		t.Optimizer.Step(loss)
	}
	
	return nil
}

// sigmoid Sigmoid 函数
func sigmoid(x float64) float64 {
	return 1.0 / (1.0 + math.Exp(-x))
}
```

### 2.3 GRPO 训练 — Go 实现

```go
package agenticrl

// GRPOTrainer Group Relative Policy Optimization
// DeepSeek 提出的简化 PPO 方案
type GRPOTrainer struct {
	PolicyModel *LLMModel
	Optimizer   *Optimizer
	Gamma       float64 // 折扣因子
}

// GRPOData GRPO 训练数据
type GRPOData struct {
	Prompt      string
	GroupResponses []string // 同一 prompt 的多个 response
	Rewards    []float64 // 每个 response 的奖励
}

// TrainGRPO 执行 GRPO 训练
func (t *GRPOTrainer) TrainGRPO(ctx context.Context, data []GRPOData) error {
	for _, sample := range data {
		// 1. 计算每个 response 的 log prob
		logProbs := make([]float64, len(sample.GroupResponses))
		for i, resp := range sample.GroupResponses {
			lp, _ := t.PolicyModel.LogProbs(sample.Prompt, resp)
			logProbs[i] = lp
		}
		
		// 2. 组内标准化奖励
		mean, std := t.MeanStd(sample.Rewards)
		normalizedRewards := make([]float64, len(sample.Rewards))
		for i, r := range sample.Rewards {
			if std > 0 {
				normalizedRewards[i] = (r - mean) / std
			} else {
				normalizedRewards[i] = 0
			}
		}
		
		// 3. GRPO 损失（组内相对 advantage）
		advantage := normalizedRewards
		loss := t.ComputeGRPOLoss(logProbs, advantage)
		
		// 4. 反向传播
		t.Optimizer.Step(loss)
	}
	
	return nil
}

// ComputeGRPOLoss 计算 GRPO 损失
func (t *GRPOTrainer) ComputeGRPOLoss(logProbs []float64, advantages []float64) float64 {
	// GRPO 不使用 clip，直接用 advantage 加权 log prob
	var loss float64
	for i, lp := range logProbs {
		loss += lp * advantages[i]
	}
	return -loss / float64(len(logProbs))
}

// MeanStd 计算均值和标准差
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

### 2.4 后训练实战流程 — Go 实现

```go
package agenticrl

// PostTrainingPipeline 后训练流水线
type PostTrainingPipeline struct {
	Protocol   *ProtocolFixer    // 产品协议修复
	PromptTune *PromptTuner      // Prompt 调试
	SFT        *SFTTrainer       // SFT 训练
	DPO        *DPOTrainer       // DPO 训练
	GRPO       *GRPOTrainer      // GRPO 训练
	Evaluator  *Evaluator        // 评估器
}

// Train 执行完整训练流程
func (p *PostTrainingPipeline) Train(ctx context.Context, data []TrainingData) error {
	// Step 1: 先改产品协议（固定业务事实）
	if err := p.Protocol.FixProtocol(data); err != nil {
		return err
	}
	
	// Step 2: 冻结评测集
	evalSet := p.Evaluator.FreezeEvalSet(data)
	
	// Step 3: Prompt 调试（找边界）
	p.PromptTune.Tune(data)
	
	// Step 4: SFT 训练（学会结构）
	if err := p.SFT.TrainSFT(ctx, data.SFTData); err != nil {
		return err
	}
	
	// Step 5: DPO 训练（学偏好）
	if err := p.DPO.TrainDPO(ctx, data.DPOData); err != nil {
		return err
	}
	
	// Step 6: GRPO 训练（可选，简化版 PPO）
	if err := p.GRPO.TrainGRPO(ctx, data.GRPodata); err != nil {
		return err
	}
	
	// Step 7: 评估
	score := p.Evaluator.Evaluate(evalSet)
	fmt.Printf("Training complete. Score: %.4f\n", score)
	
	return nil
}
```

---

## 第三部分：实战注意事项

### 为什么不能一上来就训练？

1. **业务事实未固定**: 如果业务逻辑不明确，训练只会把混乱学得更稳定
2. **Prompt 未调优**: Prompt 调试是在找边界，找到 LLM 能稳定工作的范围
3. **评测集未冻结**: 训练数据不能包含评测集，否则过拟合

### 训练策略

1. **SFT**: 让模型学会输出结构（JSON、格式等）
2. **DPO**: 让模型学会偏好（哪些回答更好）
3. **GRPO**: 简化版 PPO，不需要独立 Critic 模型

### 评估指标

| 指标 | 说明 | 目标 |
|------|------|------|
| **HardPass** | 格式、结构是否正确 | > 95% |
| **PlannerSoft** | 逻辑是否合理 | > 85% |
| **BudgetAccuracy** | 预算计算准确性 | > 90% |
| **UserSatisfaction** | 用户满意度 | > 4.0/5.0 |

---

## 第四部分：自测题

### 问题 1
为什么 SFT → DPO → GRPO 的训练顺序不能颠倒？

<details>
<summary>查看答案</summary>

1. **SFT 是基础**: 先让模型学会基本结构和能力
2. **DPO 是偏好**: 在 SFT 基础上，让模型学会"哪种回答更好"
3. **GRPO 是优化**: 最后用 GRPO 进一步微调，不需要独立 Critic
4. **颠倒后果**: 
   - 先 DPO 后 SFT：模型还没学会基本能力就开始学偏好，效果差
   - 先 GRPO 后 SFT：GRPO 需要 SFT 提供的基础能力
5. **类比**: 先学走路（SFT），再学跑步姿势（DPO），最后优化效率（GRPO）

</details>

### 问题 2
GRPO 相比 PPO 的主要优势是什么？

<details>
<summary>查看答案</summary>

1. **不需要 Critic 模型**: PPO 需要独立的 Value/Critic 模型，GRPO 用组内相对 advantage 代替
2. **显存节省**: 不需要训练 Critic，节省 50%+ 显存
3. **训练稳定**: 没有 KL 调参负担，PPO 的 KL 系数很难调
4. **计算效率**: 每组采样一次即可估计 advantage，不需要额外价值模型
5. **劣势**: 组大小限制 advantage 估计的方差，需要更多采样

</details>

### 问题 3
为什么产品协议要先于训练固定？

<details>
<summary>查看答案</summary>

1. **业务事实**: 如果业务逻辑不明确（如"预算 3000"是整趟还是人均），训练会学混乱
2. **规则可替代**: 能结构化的交给工程，能规则化的做成评测
3. **训练专注**: 训练只学模型该学的能力，其他交给规则
4. **迭代成本**: 协议改了要重新训练，成本很高
5. **正确流程**: 协议 → Prompt → SFT → DPO → GRPO → 评估

</details>

---

*本文档基于 Datawhale hello-agents 第 11 章 + Extra12 整理，内容经过精简和 Go 化改造。*
*核心教训：先改协议，再训练。能结构化的交给工程，能规则化的做成评测。*
