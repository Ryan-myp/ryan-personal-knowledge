# 推荐系统深度：排序层（Ranking）— Two-Tower/多塔/DIN/多目标

> 从千级候选中精排出 Top-N，是推荐系统的"核心大脑"

---

## 第一部分：排序的本质

### 排序在推荐漏斗中的位置

```
召回层（1000万 → 1000）→ 粗排层（1000 → 200）→ 精排层（200 → 50）→ 重排层（50 → 10）

排序层的任务：
1. 粗排：快速过滤，模型简单（LR/小树模型），延迟 < 5ms
2. 精排：精准打分，模型复杂（DeepFM/DIN/多塔），延迟 < 50ms
3. 目标：最大化 NDCG/CTR/CVR/GMV

排序 vs 召回的区别：
- 召回：找"可能感兴趣"的物品（广度优先）
- 排序：给"可能感兴趣"的物品打分（精确定位）
```

### 排序的核心指标

| 指标 | 含义 | 优化方向 |
|------|------|---------|
| **AUC** | 模型区分正负样本的能力 | > 0.6（基线）, > 0.7（优秀） |
| **GAUC** | 用户级别的 AUC，消除用户间偏差 | 比 AUC 更可靠 |
| **NDCG@K** | 排序质量，考虑位置衰减 | 越高越好 |
| **CTR 提升** | 线上点击率提升 | 绝对值 +0.5%+ |
| **CVR 提升** | 线上转化率提升 | 绝对值 +0.1%+ |

---

## 第二部分：排序模型演进

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

### 1. DeepFM 模型

```go
// DeepFM: 低阶特征交互（FM）+ 高阶特征交互（Deep）
type DeepFM struct {
    embeddingLayer   *EmbeddingLayer   // 特征嵌入
    fmLayer          *FMLayer          // 一阶 + 二阶特征交互
    dnnLayer         *DNNLayer         // 深层特征交互
    outputLayer      *SigmoidLayer     // 输出概率
}

func (m *DeepFM) Predict(features map[string]float32) float32 {
    // 1. 特征嵌入
    embeddings := m.embeddingLayer.Encode(features)
    
    // 2. FM 层：一阶 + 二阶交互
    fmOutput := m.fmLayer.Forward(embeddings)
    
    // 3. DNN 层：深层非线性交互
    dnnOutput := m.dnnLayer.Forward(embeddings)
    
    // 4. 拼接输出
    concat := append(fmOutput, dnnOutput...)
    
    // 5. Sigmoid 输出概率
    return m.outputLayer.Forward(concat)
}
```

**DeepFM 优势**：
- 自动学习特征交互，无需人工特征工程
- FM 层捕捉低阶交互（如：性别 × 品类）
- DNN 层捕捉高阶交互（如：性别 × 品类 × 价格区间）

### 2. DIN（Deep Interest Network）

```go
// DIN: 引入注意力机制，动态捕捉用户兴趣
type DIN struct {
    embeddingLayer  *EmbeddingLayer
    attentionLayer  *AttentionLayer  // 局部激活单元
    poolingLayer    *WeightedPooling  // 加权池化
    dnnLayer        *DNNLayer
    outputLayer     *SigmoidLayer
}

func (m *DIN) Predict(userID string, candidateItem Item, userHistory []Item) float32 {
    // 1. 候选物品 embedding
    candidateEmb := m.embeddingLayer.Encode(candidateItem)
    
    // 2. 用户历史物品 embedding
    historyEmbs := m.embeddingLayer.EncodeBatch(userHistory)
    
    // 3. 注意力机制：计算候选物品对用户历史的激活度
    // 核心思想：不是所有历史物品都同等重要
    attentionWeights := m.attentionLayer.QueryAttention(
        candidateEmb,  // query: 候选物品
        historyEmbs,   // keys: 用户历史
    )
    
    // 4. 加权池化：得到用户兴趣向量
    userInterest := m.poolingLayer.WeightedSum(historyEmbs, attentionWeights)
    
    // 5. 特征交叉 + DNN
    concat := append(candidateEmb, userInterest...)
    dnnOutput := m.dnnLayer.Forward(concat)
    
    // 6. 输出点击概率
    return m.outputLayer.Forward(dnnOutput)
}
```

**DIN 核心创新**：
- **局部激活单元**：候选物品只激活用户历史中相关的兴趣
- **加权池化**：不同历史行为的权重不同
- **示例**：用户看过"手机"和"口红"，推荐"手机壳"时只激活"手机"兴趣

### 3. Two-Tower 模型

```go
// Two-Tower: 用户塔 + 物品塔，分离训练和推理
type TwoTower struct {
    userTower   *TowerNetwork  // 用户特征 → 用户 embedding
    itemTower   *TowerNetwork  // 物品特征 → 物品 embedding
}

func (m *TwoTower) Train(userFeatures, itemFeatures, labels []float32) {
    // 1. 用户塔编码
    userEmbs := m.userTower.Encode(userFeatures)
    
    // 2. 物品塔编码
    itemEmbs := m.itemTower.Encode(itemFeatures)
    
    // 3. 余弦相似度作为点击概率
    similarities := cosineSimilarity(userEmbs, itemEmbs)
    
    // 4. BCE Loss 训练
    loss := binaryCrossEntropy(similarities, labels)
    loss.Backward()
}

func (m *TwoTower) Recommend(userID string, topK int) []Item {
    // 1. 用户 embedding（离线计算，缓存）
    userEmb := m.userTower.GetCachedEmbedding(userID)
    
    // 2. 向量召回：FAISS 搜索 Top-K 相似物品
    items := m.itemTower.VectorRecall(userEmb, topK)
    
    return items
}
```

**Two-Tower 优势**：
- **解耦**：用户塔和物品塔独立训练
- **高效召回**：物品 embedding 离线计算，在线只需向量搜索
- **实时性**：用户 embedding 可实时更新

---

## 第三部分：多目标排序（MMOE/PLE）

### 为什么需要多目标？

```
单目标优化（CTR）的问题：
- 高 CTR 低转化 → 标题党
- 高 CTR 低时长 → 点完就走
- 高 CTR 低 GMV → 便宜货

多目标优化（CTR + CVR + 时长 + GMV）：
- 综合权衡，找到全局最优
- 避免单目标过拟合
```

### MMOE（Multi-Gate Mixture-of-Experts）

```go
// MMOE: 多个 gate 共享 expert 层
type MMOE struct {
    experts   []*ExpertLayer  // 共享的 expert 网络
    gates     []*GateLayer    // 每个任务的 gate
    taskLayers []*TaskLayer   // 每个任务的输出层
}

func (m *MMOE) Forward(inputs []float32) []float32 {
    var outputs []float32
    
    // 1. 所有 expert 处理输入
    expertOutputs := make([][]float32, len(m.experts))
    for i, expert := range m.experts {
        expertOutputs[i] = expert.Forward(inputs)
    }
    
    // 2. 每个 task 有独立的 gate，加权组合 experts
    for _, gate := range m.gates {
        // gate 输出权重（soft selection）
        weights := gate.Forward(inputs)
        
        // 加权求和
        weightedSum := make([]float32, len(expertOutputs[0]))
        for i, w := range weights {
            for j := range weightedSum {
                weightedSum[j] += w * expertOutputs[i][j]
            }
        }
        
        // task 特定输出层
        taskOutput := m.taskLayers[gate.Index].Forward(weightedSum)
        outputs = append(outputs, taskOutput...)
    }
    
    return outputs
}
```

**MMOE 核心思想**：
- **Experts**：共享的特征提取器（多个）
- **Gates**：每个任务独立选择 experts 的权重
- **解耦**：不同任务关注不同的 expert 子集

### PLE（Progressive Layered Extraction）

```
MMOE vs PLE:

MMOE:
  Input → [Expert1] ─┐
            [Expert2] ├→ Gate1 → Task1
            [Expert3] ─┘
                  ↑
                  └→ Gate2 → Task2

PLE:
  Input → [Expert1] ─┐
            [Expert2] ├→ Shared Gate → Shared Task Output
            [Expert3] ─┘
                  ↑
  Input → [Expert4] ─┐
            [Expert5] ├→ Task1 Gate → Task1 Output
            [Expert6] ─┘
```

**PLE 优势**：
- 显式建模**共享任务**和**专属任务**
- 缓解任务间冲突（如 CTR 和 CVR 可能矛盾）
- 效果更好，但复杂度更高

---

## 第四部分：特征工程

### 特征体系

```
特征类型：
├── 用户特征（User）
│   ├── 静态：性别、年龄、地域、设备
│   └── 动态：最近 7 天点击、收藏、购买
├── 物品特征（Item）
│   ├── 静态：类目、品牌、价格、描述
│   └── 动态：近期点击率、转化率、销量
├── 上下文特征（Context）
│   ├── 时间：小时、星期、节假日
│   ├── 地点：城市、GPS
│   └── 设备：iOS/Android、网络类型
└── 交叉特征（Cross）
    ├── 用户 × 物品：历史点击类目 × 当前类目
    ├── 用户 × 上下文：周末 × 晚间偏好
    └── 物品 × 上下文：新品 × 新用户
```

### 特征交叉示例

```go
// 特征交叉：自动学习高阶交互
type FeatureCross struct {
    embeddingDim int
}

func (fc *FeatureCross) Cross(userFeatures, itemFeatures map[string]float32) []float32 {
    var crossed []float32
    
    // 1. 低阶交叉（手动构造）
    crossed = append(crossed, 
        userFeatures["gender"] * itemFeatures["category"],
        userFeatures["age"] * itemFeatures["price_range"],
    )
    
    // 2. 高阶交叉（通过 embedding 点积）
    userEmb := fc.encodeFeatures(userFeatures)
    itemEmb := fc.encodeFeatures(itemFeatures)
    
    for i := range userEmb {
        for j := range itemEmb {
            crossed = append(crossed, userEmb[i]*itemEmb[j])
        }
    }
    
    return crossed
}
```

---

## 第五部分：自测题

### Q1: DIN 和 DeepFM 有什么区别？

**A**:
- **DeepFM**：静态特征交互，适用于特征固定的场景
- **DIN**：动态注意力机制，适用于用户行为序列场景
- DIN 能捕捉"用户当前对什么感兴趣"，DeepFM 只能捕捉"用户整体喜欢什么"

### Q2: MMOE 和 PLE 怎么选？

**A**:
- **MMOE**：任务间相关性高，共享信息多
- **PLE**：任务间冲突明显，需要隔离
- 广告场景（CTR+CVR+GMV）通常用 PLE，因为 CTR 和 CVR 可能有冲突

### Q3: 如何防止过拟合？

**A**:
- Dropout（0.1-0.3）
- L2 正则化
- Early Stopping
- 特征选择（去掉噪声特征）
- 增大训练数据量

---

## 第六部分：动手验证

### 完整排序模型 Demo

```go
package main

import (
    "fmt"
    "math"
    "sort"
)

// Feature 特征
type Feature map[string]float32

// Item 物品
type Item struct {
    ID   string
    Score float32
}

// DeepFM 简化版
type DeepFM struct {
    weights map[string]float32
}

func NewDeepFM() *DeepFM {
    return &DeepFM{
        weights: map[string]float32{
            "user_age": 0.1,
            "item_price": 0.2,
            "user_item_cross": 0.3,
        },
    }
}

func (m *DeepFM) Predict(features Feature) float32 {
    var score float32
    for feat, weight := range m.weights {
        if val, ok := features[feat]; ok {
            score += val * weight
        }
    }
    // Sigmoid
    return float32(1.0 / (1.0 + math.Exp(-float64(score))))
}

// DIN 简化版
type DIN struct {
    attentionWeights map[string]float32
}

func NewDIN() *DIN {
    return &DIN{
        attentionWeights: map[string]float32{
            "recent_click": 0.6,
            "recent_view":  0.3,
            "long_term":    0.1,
        },
    }
}

func (m *DIN) Predict(candidateFeature Feature, userHistory []Feature) float32 {
    var score float32
    for _, history := range userHistory {
        attWeight := m.attentionWeights["recent_click"]
        if history["is_click"] > 0.5 {
            score += candidateFeature["similarity"] * attWeight
        }
    }
    return float32(1.0 / (1.0 + math.Exp(-float64(score))))
}

func main() {
    // DeepFM 预测
    deepFM := NewDeepFM()
    features := Feature{
        "user_age":            0.8,
        "item_price":          0.6,
        "user_item_cross":     0.9,
    }
    ctr := deepFM.Predict(features)
    fmt.Printf("DeepFM CTR: %.4f\n", ctr)
    
    // DIN 预测
    din := NewDIN()
    history := []Feature{
        {"is_click": 0.9, "similarity": 0.8},
        {"is_click": 0.3, "similarity": 0.5},
    }
    dinCTR := din.Predict(Feature{"similarity": 0.8}, history)
    fmt.Printf("DIN CTR: %.4f\n", dinCTR)
    
    // 排序
    items := []Item{
        {ID: "item_1", Score: 0.65},
        {ID: "item_2", Score: 0.82},
        {ID: "item_3", Score: 0.45},
    }
    sort.Slice(items, func(i, j int) bool {
        return items[i].Score > items[j].Score
    })
    
    fmt.Println("\n排序结果:")
    for i, item := range items {
        fmt.Printf("%d. %s (score: %.2f)\n", i+1, item.ID, item.Score)
    }
}
```

---

## 第七部分：生产实践

### 1. 模型部署

```
训练：
1. 离线训练（TensorFlow/PyTorch）
2. 模型评估（AUC/GAUC/NDCG）
3. 模型导出（SavedModel/ONNX）

部署：
1. TensorFlow Serving / Triton Inference Server
2. gRPC 接口，延迟 < 10ms
3. 灰度发布，A/B 测试
```

### 2. 实时特征

```
实时特征管道：
1. 用户行为 → Kafka
2. Flink 实时聚合 → Redis
3. 排序服务 → 读取 Redis 特征
4. 延迟：< 100ms
```

### 3. A/B 测试

```
实验设计：
1. 对照组：现有模型
2. 实验组：新模型（DIN/MMOE）
3. 指标：CTR、CVR、GMV、停留时长
4. 显著性检验：p-value < 0.05
```
