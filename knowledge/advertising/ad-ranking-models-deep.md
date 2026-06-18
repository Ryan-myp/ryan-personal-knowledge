# 排序模型深度：DeepFM/DIN/MMOE/PLE 源码级

> 逐行解析推荐/广告排序核心模型，从 DeepFM 到 PLE 多目标学习

---

## 第一部分：排序模型演进

### 模型发展史

```
2010: LR (Logistic Regression)
      ↓ 线性，无法捕捉特征交互
      
2013: Factorization Machine (FM)
      ↓ 二阶特征交互，但仍是线性模型
      
2016: DeepFM
      ↓ 低阶+高阶特征自动学习
      
2018: DIN (Deep Interest Network)
      ↓ 引入注意力机制，捕捉用户兴趣
      
2019: MMOE/PLE (Multi-Objective)
      ↓ 多任务学习，同时优化 CTR+CVR+GMV
      
2020+: Transformer-based (BERT4Rec, TiSASRec)
      ↓ 序列建模，捕捉用户兴趣演化
```

---

## 第二部分：DeepFM 源码级

```go
package ranking

import (
	"math"
)

// DeepFM 深度因子分解机
type DeepFM struct {
	embeddingDim int
	fmLayer      *FMLayer
	dnnLayer     *DNNLayer
	outputLayer  *SigmoidLayer
}

// NewDeepFM 创建 DeepFM
func NewDeepFM(embeddingDim int, dnnHiddenSizes []int) *DeepFM {
	return &DeepFM{
		embeddingDim: embeddingDim,
		fmLayer:      NewFMLayer(embeddingDim),
		dnnLayer:     NewDNNLayer(embeddingDim, dnnHiddenSizes),
		outputLayer:  NewSigmoidLayer(),
	}
}

// Predict 预测点击概率
func (m *DeepFM) Predict(features map[string]float64) float64 {
	// 1. 特征嵌入
	embeddings := m.embedFeatures(features)
	
	// 2. FM 层：一阶 + 二阶特征交互
	fmOutput := m.fmLayer.Forward(embeddings)
	
	// 3. DNN 层：深层特征交互
	dnnOutput := m.dnnLayer.Forward(embeddings)
	
	// 4. 拼接输出
	concat := append(fmOutput, dnnOutput...)
	
	// 5. Sigmoid 输出概率
	return m.outputLayer.Forward(concat)
}

func (m *DeepFM) embedFeatures(features map[string]float64) [][]float64 {
	var embeddings [][]float64
	for _, v := range features {
		// 简化：实际会使用 Embedding 层
		emb := make([]float64, m.embeddingDim)
		for i := range emb {
			emb[i] = v * float64(i+1) * 0.01
		}
		embeddings = append(embeddings, emb)
	}
	return embeddings
}
```

### FM 层实现

```go
package ranking

import "math"

// FMLayer 因子分解机层
type FMLayer struct {
	embeddingDim int
}

func NewFMLayer(dim int) *FMLayer {
	return &FMLayer{embeddingDim: dim}
}

// Forward 前向传播
func (l *FMLayer) Forward(embeddings [][]float64) []float64 {
	n := len(embeddings)
	if n == 0 {
		return []float64{0}
	}
	
	// 一阶：线性部分
	var linearSum float64
	for _, emb := range embeddings {
		for _, v := range emb {
			linearSum += v
		}
	}
	
	// 二阶：交叉部分
	// (Σxi)² - Σ(xi²) 所有除以 2
	var squaredSum float64
	var sumSquared float64
	for _, emb := range embeddings {
		var rowSum float64
		for _, v := range emb {
			rowSum += v
		}
		squaredSum += rowSum * rowSum
		for _, v := range emb {
			sumSquared += v * v
		}
	}
	
	crossTerm := (squaredSum - sumSquared) / 2
	
	return []float64{linearSum, crossTerm}
}
```

### DNN 层实现

```go
package ranking

// DNNLayer 深度神经网络层
type DNNLayer struct {
	layers []Layer
}

type Layer interface {
	Forward(input []float64) []float64
}

// ReLULayer ReLU 激活层
type ReLULayer struct {
	inputDim  int
	outputDim int
	weights   [][]float64
	biases    []float64
}

func NewReLULayer(inputDim, outputDim int) *ReLULayer {
	return &ReLULayer{
		inputDim:  inputDim,
		outputDim: outputDim,
		weights:   initWeights(inputDim, outputDim),
		biases:    make([]float64, outputDim),
	}
}

func (l *ReLULayer) Forward(input []float64) []float64 {
	output := make([]float64, l.outputDim)
	for j := 0; j < l.outputDim; j++ {
		sum := l.biases[j]
		for i := 0; i < l.inputDim; i++ {
			sum += input[i] * l.weights[i][j]
		}
		output[j] = max(0, sum) // ReLU
	}
	return output
}

// SigmoidLayer Sigmoid 激活层
type SigmoidLayer struct{}

func NewSigmoidLayer() *SigmoidLayer {
	return &SigmoidLayer{}
}

func (l *SigmoidLayer) Forward(input []float64) float64 {
	// 取最后一个值作为输出
	val := input[len(input)-1]
	return 1.0 / (1.0 + math.Exp(-val))
}

func initWeights(rows, cols int) [][]float64 {
	weights := make([][]float64, rows)
	for i := range weights {
		weights[i] = make([]float64, cols)
		for j := range weights[i] {
			weights[i][j] = (rand.Float64() - 0.5) * 0.01
		}
	}
	return weights
}
```

---

## 第三部分：DIN（Deep Interest Network）源码

```go
package ranking

// DIN 深度兴趣网络
type DIN struct {
	embeddingDim   int
	attentionLayer *AttentionLayer
	poolingLayer   *WeightedPooling
	dnnLayer       *DNNLayer
	outputLayer    *SigmoidLayer
}

// NewDIN 创建 DIN
func NewDIN(embeddingDim int, hiddenSizes []int) *DIN {
	return &DIN{
		embeddingDim:   embeddingDim,
		attentionLayer: NewAttentionLayer(embeddingDim),
		poolingLayer:   NewWeightedPooling(),
		dnnLayer:       NewDNNLayer(embeddingDim, hiddenSizes),
		outputLayer:    NewSigmoidLayer(),
	}
}

// Predict 预测点击概率
func (m *DIN) Predict(candidateEmbedding []float64, userHistory [][]float64) float64 {
	// 1. 注意力机制：计算候选物品对用户历史的激活度
	weights := m.attentionLayer.QueryAttention(candidateEmbedding, userHistory)
	
	// 2. 加权池化：得到用户兴趣向量
	userInterest := m.poolingLayer.WeightedSum(userHistory, weights)
	
	// 3. 特征交叉
	candidateEmb := candidateEmbedding
	featureConcat := append(candidateEmb, userInterest...)
	
	// 4. DNN 层
	dnnOutput := m.dnnLayer.Forward(featureConcat)
	
	// 5. Sigmoid 输出
	return m.outputLayer.Forward(dnnOutput)
}

// AttentionLayer 注意力层
type AttentionLayer struct {
	hiddenSize int
}

func NewAttentionLayer(size int) *AttentionLayer {
	return &AttentionLayer{hiddenSize: size}
}

// QueryAttention 计算注意力权重
func (l *AttentionLayer) QueryAttention(query []float64, keys [][]float64) []float64 {
	weights := make([]float64, len(keys))
	maxW := -math.MaxFloat64
	
	for i, key := range keys {
		// 简化：余弦相似度
		sim := cosineSimilarity(query, key)
		weights[i] = sim
		if sim > maxW {
			maxW = sim
		}
	}
	
	// Softmax
	for i := range weights {
		weights[i] = math.Exp(weights[i] - maxW)
	}
	sum := 0.0
	for _, w := range weights {
		sum += w
	}
	for i := range weights {
		weights[i] /= sum
	}
	
	return weights
}

func cosineSimilarity(a, b []float64) float64 {
	dot := 0.0
	normA := 0.0
	normB := 0.0
	for i := range a {
		dot += a[i] * b[i]
		normA += a[i] * a[i]
		normB += b[i] * b[i]
	}
	return dot / (math.Sqrt(normA) * math.Sqrt(normB))
}

// WeightedPooling 加权池化
type WeightedPooling struct{}

func NewWeightedPooling() *WeightedPooling {
	return &WeightedPooling{}
}

func (p *WeightedPooling) WeightedSum(values [][]float64, weights []float64) []float64 {
	n := len(values[0])
	result := make([]float64, n)
	
	for i, w := range weights {
		for j := range result {
			result[j] += w * values[i][j]
		}
	}
	
	return result
}
```

---

## 第四部分：MMOE/PLE 多目标学习

```go
package ranking

// MMOE 多门混合专家模型
type MMOE struct {
	experts   []*ExpertLayer
	gates     []*GateLayer
	taskLayers []*TaskLayer
	numTasks  int
}

// ExpertLayer 专家层
type ExpertLayer struct {
	inputDim  int
	outputDim int
	weights   [][]float64
	biases    []float64
}

func NewExpertLayer(inputDim, outputDim int) *ExpertLayer {
	return &ExpertLayer{
		inputDim:  inputDim,
		outputDim: outputDim,
		weights:   initWeights(inputDim, outputDim),
		biases:    make([]float64, outputDim),
	}
}

func (e *ExpertLayer) Forward(input []float64) []float64 {
	output := make([]float64, e.outputDim)
	for j := 0; j < e.outputDim; j++ {
		sum := e.biases[j]
		for i := 0; i < e.inputDim; i++ {
			sum += input[i] * e.weights[i][j]
		}
		output[j] = max(0, sum) // ReLU
	}
	return output
}

// GateLayer 门控层
type GateLayer struct {
	inputDim  int
	outputDim int
	weights   [][]float64
	biases    []float64
	index     int
}

func NewGateLayer(inputDim, outputDim int, idx int) *GateLayer {
	return &GateLayer{
		inputDim:  inputDim,
		outputDim: outputDim,
		weights:   initWeights(inputDim, outputDim),
		biases:    make([]float64, outputDim),
		index:     idx,
	}
}

func (g *GateLayer) Forward(input []float64) []float64 {
	output := make([]float64, g.outputDim)
	for j := 0; j < g.outputDim; j++ {
		sum := g.biases[j]
		for i := 0; i < g.inputDim; i++ {
			sum += input[i] * g.weights[i][j]
		}
		output[j] = sum
	}
	// Softmax
	max := output[0]
	for _, v := range output {
		if v > max { max = v }
	}
	for i := range output {
		output[i] = math.Exp(output[i] - max)
	}
	sum := 0.0
	for _, v := range output { sum += v }
	for i := range output {
		output[i] /= sum
	}
	return output
}

// TaskLayer 任务层
type TaskLayer struct {
	inputDim  int
	outputDim int
	weights   [][]float64
	biases    []float64
}

func NewTaskLayer(inputDim, outputDim int) *TaskLayer {
	return &TaskLayer{
		inputDim:  inputDim,
		outputDim: outputDim,
		weights:   initWeights(inputDim, outputDim),
		biases:    make([]float64, outputDim),
	}
}

func (t *TaskLayer) Forward(input []float64) []float64 {
	output := make([]float64, t.outputDim)
	for j := 0; j < t.outputDim; j++ {
		sum := t.biases[j]
		for i := 0; i < t.inputDim; i++ {
			sum += input[i] * t.weights[i][j]
		}
		output[j] = sum
	}
	return output
}

// NewMMOE 创建 MMOE
func NewMMOE(numExperts, numTasks, expertDim, gateDim, taskDim int) *MMOE {
	mmo := &MMOE{
		numTasks: numTasks,
	}
	
	// 创建 experts
	for i := 0; i < numExperts; i++ {
		mmo.experts = append(mmo.experts, NewExpertLayer(gateDim, expertDim))
	}
	
	// 创建 gates
	for i := 0; i < numTasks; i++ {
		mmo.gates = append(mmo.gates, NewGateLayer(gateDim, numExperts, i))
	}
	
	// 创建 task layers
	for i := 0; i < numTasks; i++ {
		mmo.taskLayers = append(mmo.taskLayers, NewTaskLayer(expertDim, 1))
	}
	
	return mmo
}

// Predict 多任务预测
func (m *MMOE) Predict(input []float64) []float64 {
	var outputs []float64
	
	// 1. 所有 expert 处理输入
	expertOutputs := make([][]float64, len(m.experts))
	for i, expert := range m.experts {
		expertOutputs[i] = expert.Forward(input)
	}
	
	// 2. 每个 task 有独立的 gate，加权组合 experts
	for taskIdx, gate := range m.gates {
		weights := gate.Forward(input)
		
		// 加权求和
		weightedSum := make([]float64, len(expertOutputs[0]))
		for i, w := range weights {
			for j := range weightedSum {
				weightedSum[j] += w * expertOutputs[i][j]
			}
		}
		
		// task 特定输出层
		taskOutput := m.taskLayers[taskIdx].Forward(weightedSum)
		outputs = append(outputs, taskOutput[0])
	}
	
	return outputs
}
```

---

## 第五部分：自测题

### Q1: DeepFM 和 DIN 的区别？

**A**: DeepFM 是静态特征交互，DIN 是动态注意力机制。DIN 能捕捉"用户当前对什么感兴趣"，DeepFM 只能捕捉"用户整体喜欢什么"。

### Q2: MMOE 和 PLE 的区别？

**A**: MMOE 共用一组 experts，PLE 有共享 experts 和专属 experts。PLE 效果更好但更复杂。

### Q3: 多目标学习为什么需要 MMOE/PLE？

**A**: 不同目标（CTR/CVR/GMV）可能有冲突，MMOE/PLE 通过独立的 gate 为每个任务选择不同的 experts，缓解冲突。

---

## 第六部分：生产实践

### 1. 模型部署

```
训练：
1. 离线训练（TensorFlow/PyTorch）
2. 模型评估（AUC/GAUC/NDCG）
3. 模型导出（SavedModel/ONNX）

部署：
1. TensorFlow Serving / Triton
2. gRPC 接口，延迟 < 10ms
3. 灰度发布，A/B 测试
```

### 2. 特征工程

```
特征体系：
- 用户特征：静态（性别/年龄）+ 动态（点击/收藏）
- 物品特征：静态（类目/品牌）+ 动态（近期CTR）
- 上下文特征：时间/地点/设备
- 交叉特征：用户×物品×上下文
```

### 3. A/B 测试

```
实验设计：
1. 对照组：现有模型
2. 实验组：DeepFM/DIN/MMOE
3. 指标：CTR/CVR/GMV/停留时长
4. 显著性检验：p-value < 0.05
```
