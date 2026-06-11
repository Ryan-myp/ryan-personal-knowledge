# pCTR 模型深度：从逻辑回归到 DeepFM / MMoE

> 创建日期: 2026-06-10
> 作者: Ryan
> 定位: 资深专家级 — pCTR 模型核心

---

## 第一部分：pCTR 问题本质

### 1.1 为什么 pCTR 是广告系统核心

```
┌──────────────────────────────────────────────────────────────┐
│              pCTR 的核心地位                                    │
│                                                              │
│  广告竞价中:                                                  │
│  ├── pCTR × pCVR × Target CPA = Optimal Bid                │
│  ├── pCTR 是 Bid 计算的第一环                                 │
│  ├── pCTR 误差会直接传递给 Bid                               │
│  └─ pCTR 的 AUC 提升 0.1% → ROI 提升 0.5-1%                  │
│                                                              │
│  pCTR = P(click | impression, features)                     │
│  ├── click: 用户是否点击广告                                  │
│  ├── impression: 广告被展示的上下文                             │
│  └─ features: 用户/广告/上下文特征                             │
│                                                              │
│  pCTR vs CTR (对比):                                        │
│  ├── CTR: 历史统计值 (某广告/某关键词的过去 CTR)               │
│  └─ pCTR: 模型预测值 (基于实时特征，预测本次点击概率)            │
│                                                              │
│  挑战:                                                       │
│  ├── 数据量极大: 每天数十亿次展示                              │
│  ├── 特征空间极大: 用户×广告×上下文组合爆炸                     │
│  ├── 稀疏性: 99.9% 的 (用户, 广告) 组合无历史数据              │
│  └─ 实时性: 竞价时 < 10ms 完成推理                            │
└──────────────────────────────────────────────────────────────┘
```

### 1.2 pCTR 模型发展史

```
pCTR 模型演进:

Stage 1: 逻辑回归 (LR) — 2007 之前
─────────────────────────────────────
├─ 模型: P(click) = σ(w·x + b)
│   └─ 线性模型，只捕获线性关系
├─ 优点: 简单、快速、可解释性强
│   └─ 可以在线训练 (FTRL-Proximal)
├─ 缺点: 无法捕获非线性/特征交叉
│   └─ AUC 上限 ~0.65
└─ 代表: Google Ads (早期), AdSense

Stage 2: GBDT/LR 两阶段 — 2007-2014
─────────────────────────────────────
├─ 模型: GBDT (特征工程) + LR (分类)
│   ├── GBDT: 自动提取非线性特征
│   └─ LR: 在 GBDT 特征上分类
├─ 优点: 比纯 LR 提升显著
│   └─ AUC 提升 0.05-0.10
├─ 缺点: 需要手动设计 GBDT 树结构
│   └─ 端到端优化困难
└─ 代表: Facebook (早期), AdSense

Stage 3: Deep Crossing — 2016
─────────────────────────────────────
├─ 模型: Wide & Deep (Google)
│   ├── Wide: 人工特征交叉 (捕获稀疏强信号)
│   ├── Deep: DNN 自动特征学习 (捕获密集弱信号)
│   └─ 联合训练: L = L_wide + λ × L_deep
├─ 优点: 兼顾记忆力和泛化力
│   └─ AUC 提升 0.02-0.05 over LR
└─ 代表: Google Ads (2016+), YouTube

Stage 4: DeepFM / DCN — 2017
─────────────────────────────────────
├─ 模型: DeepFM (Google)
│   ├── FM: 自动一阶/二阶特征交叉
│   ├── Deep: DNN 高阶特征交叉
│   └─ 共享底表示，联合训练
├─ 优点: 自动特征工程，无需手动交叉
│   └─ AUC 提升 0.01-0.03 over Deep
├─ 模型: DCN (Google)
│   ├── 交叉网络: 自动捕获高阶交互
│   └─ 替代 Deep 部分，更适合推荐
└─ 代表: Google Ads, AdSense (2017+)

Stage 5: MMOE / PLE — 2018
─────────────────────────────────────
├─ 模型: MMOE (Multi-gate Mixture-of-Experts)
│   ├── 多任务: 同时优化 CTR + CVR
│   ├── 多门控: 学习不同任务的专家组合
│   └─ 解决任务间冲突 (negative transfer)
├─ 模型: PLE (Progressive Layered Extraction)
│   ├── 专用专家: 每个任务有自己的专家
│   ├── 共享专家: 所有任务共享专家
│   └─ 比 MMOE 更好控制知识共享
└─ 代表: Google (所有推荐/搜索)

Stage 6: Transformer — 2019+
─────────────────────────────────────
├─ 模型: DIN (Deep Interest Network) — 阿里
│   ├── Attention: 基于 query 的用户兴趣
│   └─ 自适应捕获用户兴趣与广告相关性
├─ 模型: DIEN (Deep Interest Evolution Network)
│   ├── GRU: 建模兴趣演化
│   └─ Attention: 时序兴趣到广告
├─ 模型: Bert4Rec — 序列建模
│   └─ Transformer Encoder: 捕获长序列依赖
└─ 代表: Alibaba, JD.com, TikTok

Stage 7: 大规模分布式训练 — 2020+
─────────────────────────────────────
├─ 模型: TensorFlow / PyTorch 分布式
│   ├── Parameter Server: 全局模型参数
│   ├── Worker: 本地梯度计算
│   └─ Async/Sync SGD
├─ 模型: Flink/Spark 实时特征
│   └─ 实时用户行为 → 实时特征
└─ 代表: Google, Meta, TikTok, 字节

当前 SOTA:
├── 搜索广告: DeepFM / MMOE + Attention
├── 推荐广告: DIN / DIEN + 序列建模
└─ 生成式广告: LLM-based CTR 预测 (探索中)
```

---

## 第二部分：Wide & Deep 模型

### 2.1 模型架构

```
┌──────────────────────────────────────────────────────────────┐
│              Wide & Deep 架构                                   │
│                                                              │
│  Wide 部分 (线性模型 + 人工交叉):                              │
│  ┌─────────────────────────────────────────┐                │
│  │  Input: features (500 dim)              │                │
│  │  ├─ Cross Features (人工):              │                │
│  │  │   ├── user_age × ad_category        │                │
│  │  │   ├── search_query × ad_title       │                │
│  │  │   └─ ad_cpc × user_income           │                │
│  │  └─ Wide Layer (LR):                    │                │
│  │      └─ y_wide = w·x + b               │                │
│  └─────────────────────────────────────────┘                │
│                                                              │
│  Deep 部分 (DNN):                                            │
│  ┌─────────────────────────────────────────┐                │
│  │  Input: features (500 dim)              │                │
│  │  ├─ Embedding Layer:                   │                │
│  │  │   ├── user_emb (32 dim)             │                │
│  │  │   ├── ad_emb (32 dim)               │                │
│  │  │   └─ query_emb (32 dim)             │                │
│  │  ├─ Hidden Layer 1 (256 units):        │                │
│  │  │   └─ h1 = ReLU(W1·[emb] + b1)      │                │
│  │  ├─ Hidden Layer 2 (128 units):        │                │
│  │  │   └─ h2 = ReLU(W2·h1 + b2)         │                │
│  │  └─ Hidden Layer 3 (64 units):         │                │
│  │      └─ h3 = ReLU(W3·h2 + b3)         │                │
│  └─────────────────────────────────────────┘                │
│                                                              │
│  合并:                                                       │
│  ┌─────────────────────────────────────────┐                │
│  │  y_concat = Concat(y_wide, h3)          │                │
│  │  y_out = σ(W_out · y_concat + b_out)  │                │
│  └─────────────────────────────────────────┘                │
│                                                              │
│  损失:                                                       │
│  └─ L = -Σ[y·log(y_out) + (1-y)·log(1-y_out)] (BCE)       │
│                                                              │
│  超参数:                                                     │
│  ├── λ (Wide/Deep 权重平衡): 0.1-1.0                        │
│  ├── learning_rate: 0.001-0.01                              │
│  └─ dropout: 0.1-0.3 (防止过拟合)                           │
└──────────────────────────────────────────────────────────────┘
```

### 2.2 Wide & Deep 代码实现

```python
"""
Wide & Deep 模型 — PyTorch 实现
"""

import torch
import torch.nn as nn
import torch.nn.functional as F


class WideDeepModel(nn.Module):
    """
    Wide & Deep 模型
    
    Wide: 线性层 + 人工特征交叉
    Deep: DNN
    合并: Concat + Sigmoid
    """
    
    def __init__(
        self,
        num_dense_features: int = 100,  # 数值特征数量
        num_sparse_features: int = 500,  # 稀疏特征数量 (category/user/ad)
        embed_dim: int = 32,  # embedding 维度
        wide_hidden_dim: int = 256,  # Wide 隐藏层
        deep_hidden_dims: list = [256, 128, 64],  # Deep 隐藏层维度
        cross_pairs: list = None,  # 人工特征交叉对
    ):
        super().__init__()
        
        # Wide 部分
        self.dense_to_wide = nn.Linear(num_dense_features, wide_hidden_dim)
        self.dropout_wide = nn.Dropout(0.1)
        
        # 人工特征交叉 (如果提供)
        self.cross_pairs = cross_pairs or []
        
        # Deep 部分
        self.embedding = nn.Embedding(num_sparse_features, embed_dim)
        embed_size = num_sparse_features * embed_dim  # 展开
        
        deep_layers = []
        in_dim = num_dense_features + embed_size  # Dense + Embedding
        for hidden_dim in deep_hidden_dims:
            deep_layers.extend([
                nn.Linear(in_dim, hidden_dim),
                nn.BatchNorm1d(hidden_dim),
                nn.ReLU(),
                nn.Dropout(0.1),
            ])
            in_dim = hidden_dim
        self.deep_net = nn.Sequential(*deep_layers)
        
        # 合并层
        self.merge = nn.Linear(wide_hidden_dim + deep_hidden_dims[-1], 1)
        
    def forward(self, x_dense, x_sparse):
        """
        Forward pass
        
        Args:
            x_dense: (batch, num_dense_features) — 数值特征
            x_sparse: (batch, num_sparse_features) — 稀疏特征 (ID)
        
        Returns:
            p_ctr: (batch, 1) — 点击概率
        """
        # Wide: 线性变换 + 特征交叉
        wide_out = self.dense_to_wide(x_dense)
        wide_out = self.dropout_wide(F.relu(wide_out))
        
        # 人工特征交叉 (如果有)
        if self.cross_pairs:
            cross_features = []
            for i, j in self.cross_pairs:
                cross_features.append(x_dense[:, i] * x_dense[:, j])
            if cross_features:
                cross_tensor = torch.stack(cross_features, dim=1)
                wide_out = torch.cat([wide_out, cross_tensor], dim=1)
        
        # Deep: Embedding + DNN
        emb = self.embedding(x_sparse)  # (batch, num_sparse, embed_dim)
        emb_flat = emb.view(emb.size(0), -1)  # (batch, num_sparse * embed_dim)
        deep_in = torch.cat([x_dense, emb_flat], dim=1)
        deep_out = self.deep_net(deep_in)
        
        # 合并
        concat = torch.cat([wide_out, deep_out], dim=1)
        logits = self.merge(concat)
        p_ctr = torch.sigmoid(logits)
        
        return p_ctr.squeeze(-1)


def train_wide_deep(
    model: WideDeepModel,
    x_dense: torch.Tensor,
    x_sparse: torch.Tensor,
    y: torch.Tensor,
    optimizer: torch.optim.Optimizer,
) -> dict:
    """训练一步"""
    model.train()
    optimizer.zero_grad()
    
    p_ctr = model(x_dense, x_sparse)
    loss = F.binary_cross_entropy(p_ctr, y)
    
    loss.backward()
    optimizer.step()
    
    return {
        'loss': loss.item(),
        'auc': compute_auc(p_ctr.detach(), y),
    }


def compute_auc(preds: torch.Tensor, targets: torch.Tensor) -> float:
    """简化 AUC 计算"""
    # 排序: 预测值高的排在前面
    sorted_indices = torch.argsort(preds, descending=True)
    sorted_targets = targets[sorted_indices]
    
    # 计算 TP/FP
    tp = torch.cumsum(sorted_targets, dim=0)
    fp = torch.cumsum(1 - sorted_targets, dim=0)
    
    # AUC = Σ(TP_i - TP_{i-1}) × FP_i / (TP_total × FP_total)
    total_pos = targets.sum().item()
    total_neg = (1 - targets).sum().item()
    
    if total_pos == 0 or total_neg == 0:
        return 0.5
    
    auc = torch.sum((tp - torch.cat([torch.tensor([0]), tp[:-1]])) * fp) / (total_pos * total_neg)
    return auc.item()
```

### 3.2 Go 实现 — FTRL 在线学习器

```go
// ftrl.go — FTRL-Proximal 在线 CTR 学习器（Go 版）
package ctr

import (
	"fmt"
	"math"
	"sync"
)

// FeatureBucket 特征桶
type FeatureBucket struct {
	Hash    int64  // 特征哈希值
	Feature string // 原始特征名（可选）
}

// FTRLProximal 在线学习参数
type FTRLParams struct {
	Alpha float64 // 学习率 (默认 0.05)
	Beta  float64 // 平滑参数 (默认 1.0)
	L1    float64 // L1 正则化 (默认 0.0)
	L2    float64 // L2 正则化 (默认 0.1)
}

// FTRLState FTRL 状态 (per-bucket)
type FTRLState struct {
	w float64 // 权重
	z float64 // 累积梯度
	n float64 // 梯度平方和
}

// FTRLProximal 在线学习器
type FTRLProximal struct {
	params  FTRLParams
	state   map[int64]*FTRLState
	mu      sync.RWMutex
	features []FeatureBucket
}

// NewFTRLProximal 创建在线学习器
func NewFTRLProximal(params FTRLParams) *FTRLProximal {
	return &FTRLProximal{
		params:  params,
		state:   make(map[int64]*FTRLState),
		features: make([]FeatureBucket, 0, 10000),
	}
}

// HashFeature 哈希特征名
func HashFeature(name string) int64 {
	// 简单哈希 (生产环境用 murmur3)
	hash := int64(0)
	for _, c := range name {
		hash = hash*31 + int64(c)
	}
	return hash
}

// Sigmoid 数值稳定的 sigmoid
func Sigmoid(x float64) float64 {
	if x >= 0 {
		return 1.0 / (1.0 + math.Exp(-x))
	}
	expX := math.Exp(x)
	return expX / (1.0 + expX)
}

// Predict 预测点击概率
func (f *FTRLProximal) Predict(features []FeatureBucket) float64 {
	f.mu.RLock()
	defer f.mu.RUnlock()

	var score float64
	for _, feat := range features {
		if state, ok := f.state[feat.Hash]; ok {
			score += state.w
		}
	}
	return Sigmoid(score)
}

// Update 在线更新 (在线学习核心)
func (f *FTRLProximal) Update(features []FeatureBucket, label float64) {
	f.mu.Lock()
	defer f.mu.Unlock()

	// 1. 预测
	p := f.predictLocked(features)

	// 2. 计算梯度: l = p - y
	grad := p - label

	// 3. 更新每个特征
	for _, feat := range features {
		h := feat.Hash
		state := f.getOrInitState(h)

		// FTRL 更新公式:
		// σ_i = (√(n_i + σ²) - √n_i) / α
		// w_i = -1/L2 * (L1 * sign(z_i) - z_i) / (α/σ_i + L2)
		σ := math.Sqrt(float64(state.n+1)) - math.Sqrt(float64(state.n))
		σ += f.params.Beta // 防止除以零

		// 累积 z 和 n
		state.z += grad - (state.z - grad*math.Sqrt(float64(state.n+1)-math.Sqrt(float64(state.n))))
		state.n += grad * grad

		// 稀疏 L1 正则化 (产生稀疏解的关键!)
		w := -f.params.L1 * math.Signum(state.z)
		if state.z > 0 {
			w = math.Max(0, state.z-f.params.L1) / (f.params.Alpha*σ/f.params.Beta + f.params.L2)
		} else {
			w = -math.Max(0, -state.z-f.params.L1) / (f.params.Alpha*σ/f.params.Beta + f.params.L2)
		}

		// 如果 L1 正则化使权重归零 → 删除状态 (稀疏化)
		if math.Abs(w) < 1e-10 {
			delete(f.state, h)
		} else {
			state.w = w
		}
	}
}

func (f *FTRLProximal) predictLocked(features []FeatureBucket) float64 {
	var score float64
	for _, feat := range features {
		if state, ok := f.state[feat.Hash]; ok {
			score += state.w
		}
	}
	return Sigmoid(score)
}
```

### 3.3 Wide & Deep 架构 — Go 实现

```go
// wide_deep.go — Wide & Deep 模型实现
package ctr

import (
	"math"
)

// WideDeepModel Wide & Deep 模型
type WideDeepModel struct {
	// Wide: 线性 + 特征交叉
	WideWeights []float64  // 线性权重
	WideCrosses []CrossFeat // 交叉特征

	// Deep: DNN
	HiddenDims []int      // 隐藏层维度 [256, 128, 64]
	Weights    [][]float64 // 权重矩阵 [layer][input_dim × output_dim]
	Biases     []float64    // 偏置向量

	Embeddings map[string][]float64 // 共享 embedding
}

// CrossFeat 交叉特征
type CrossFeat struct {
	FieldA string
	FieldB string
	Weight float64
}

// Forward 前向传播
func (m *WideDeepModel) Forward(features map[string]string, embeddingLookup func(string) []float64) float64 {
	// Wide 部分
	wideScore := m.widePart(features, embeddingLookup)

	// Deep 部分 (DNN)
	deepEmbed := m.deepPart(features, embeddingLookup)

	// 合并输出: σ(α * wide + β * deep)
	combined := 0.5 * wideScore + 0.5 * deepScore
	return Sigmoid(combined)
}

// widePart Wide 部分 (线性 + 人工交叉)
func (m *WideDeepModel) widePart(features map[string]string, lookup func(string) []float64) float64 {
	var score float64

	// 线性部分
	for i, w := range m.WideWeights {
		featVal := 1.0 // one-hot 激活
		score += w * featVal
	}

	// 交叉部分: 人工设计的特征交叉
	for _, cross := range m.WideCrosses {
		valA := features[cross.FieldA]
		valB := features[cross.FieldB]
		if valA != "" && valB != "" {
			score += m.crossEmbed(valA, valB) * cross.Weight
		}
	}

	return score
}

// deepPart Deep 部分 (DNN + Embedding)
func (m *WideDeepModel) deepPart(features map[string]string, lookup func(string) []float64) float64 {
	// 1. 获取 embedding
	var embedding []float64
	for field, val := range features {
		if vec := lookup(val); vec != nil {
			embedding = append(embedding, vec...)
		}
	}

	// 2. DNN 前向传播
	output := embedding
	for layerIdx := range m.HiddenDims {
		layer := m.Weights[layerIdx]
		bias := m.Biases[layerIdx]
		output = m.matmulReLU(output, layer, bias)
	}

	return output
}

// matmulReLU 矩阵乘法 + ReLU
func (m *WideDeepModel) matmulReLU(input []float64, weights [][]float64, bias []float64) []float64 {
	output := make([]float64, len(bias))
	for i, b := range bias {
		sum := b
		for j, x := range input {
			sum += x * weights[i][j]
		}
		output[i] = math.Max(0, sum) // ReLU
	}
	return output
}
```

---

## 第三部分：DeepFM 模型

### 3.1 模型架构

```
┌──────────────────────────────────────────────────────────────┐
│              DeepFM 架构                                       │
│                                                              │
│  输入: 稀疏特征 (类别) + 稠密特征 (数值)                       │
│                                                              │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  Shared Embedding Layer                                  │ │
│  │  ┌───────────────────────────────────────────────┐      │ │
│  │  │  user_id → [32 dim embedding]                  │      │ │
│  │  │  ad_id → [32 dim embedding]                    │      │ │
│  │  │  query → [32 dim embedding]                    │      │ │
│  │  │  ad_category → [32 dim embedding]              │      │ │
│  │  │  user_age_bucket → [32 dim embedding]          │      │ │
│  │  └───────────────────────────────────────────────┘      │ │
│  │  所有 embedding 拼接 → (batch, num_sparse × 32)          │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                              │
│  ├── FM 部分 (Field-aware FM):                                │
│  │  ┌───────────────────────────────────────────────┐      │ │
│  │  │  y_FM = w0 + Σ(w_i · x_i) +                    │      │ │
│  │  │          ½ × Σ_k Σ_i Σ_j <v_i^k, v_j^k>       │      │ │
│  │  │               × x_i · x_j                       │      │ │
│  │  │                                                │      │ │
│  │  │  简化:                                         │      │ │
│  │  │  一阶: w0 + Σ w_i · x_i                        │      │ │
│  │  │  二阶: Σ_i<j <v_i, v_j> · x_i · x_j           │      │ │
│  │  └───────────────────────────────────────────────┘      │ │
│  │  捕获一阶/二阶特征交叉                                    │ │
│  │  自动学习，无需人工设计                                    │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                              │
│  ├── Deep 部分 (DNN):                                        │
│  │  ┌───────────────────────────────────────────────┐      │ │
│  │  │  Input: [emb_concat]                           │      │ │
│  │  │  Hidden 1: 256 ReLU + BN + Dropout             │      │ │
│  │  │  Hidden 2: 128 ReLU + BN + Dropout             │      │ │
│  │  │  Hidden 3: 64 ReLU + BN + Dropout              │      │ │
│  │  │  Output: 1 (Sigmoid)                           │      │ │
│  │  └───────────────────────────────────────────────┘      │ │
│  │  捕获高阶特征交叉 (三阶及以上)                              │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                              │
│  └── 合并:                                                    │
│     ┌───────────────────────────────────────────────┐      │ │
│     │  y = σ(α × y_FM + β × y_Deep + γ)            │      │ │
│     │  α, β, γ: 可学习权重                           │      │ │
│     └───────────────────────────────────────────────┘      │ │
│                                                              │
│  优势:                                                       │
│  ├── FM 自动捕获一/二阶交叉 → 替代 Wide 部分                 │
│  ├── Deep 捕获高阶交叉 → 更灵活                               │
│  ├── 共享 Embedding → 参数高效                               │
│  └─ 端到端训练 → 优化全局                                   │
└──────────────────────────────────────────────────────────────┘
```

### 3.2 DeepFM 代码实现

```python
"""
DeepFM 模型 — PyTorch 实现
"""

import torch
import torch.nn as nn
import torch.nn.functional as F


class FieldAwareFM(nn.Module):
    """
    Field-aware Factorization Machine
    
    y_FM = w0 + Σ w_i·x_i + Σ_i<j <v_i, v_j>·x_i·x_j
    """
    
    def __init__(self, num_fields: int, embed_dim: int = 8):
        super().__init__()
        self.num_fields = num_fields
        self.embed_dim = embed_dim
        
        # 一阶权重
        self.bias = nn.Parameter(torch.zeros(1))
        self.linears = nn.Parameter(torch.zeros(num_fields))
        
        # 二阶 embedding (每个 field 有 embed_dim 维向量)
        self.field_emb = nn.Parameter(
            torch.randn(num_fields, embed_dim) * 0.01
        )
    
    def forward(self, x_sparse):
        """
        Args:
            x_sparse: (batch, num_fields) — one-hot encoded sparse features
        
        Returns:
            y_fm: (batch, 1)
        """
        batch_size = x_sparse.size(0)
        
        # 一阶: Σ w_i · x_i
        linear_part = self.bias + (
            self.linears @ x_sparse.T  # (1, num_fields) @ (num_fields, batch)
        )  # (1, batch)
        
        # 二阶: ½ Σ_k Σ_i Σ_j <v_i^k, v_j^k> · x_i · x_j
        # 简化: 使用 FM 的平方和技巧
        # Σ_i Σ_j <v_i, v_j> · x_i · x_j = 
        #   (Σ_i x_i · v_i)² - Σ_i (x_i · v_i)²
        
        # v: (num_fields, embed_dim)
        v = self.field_emb  # (num_fields, embed_dim)
        
        # x_sparse: (batch, num_fields)
        # 只取激活的 field
        x_sum = torch.sum(x_sparse.unsqueeze(2) * v.unsqueeze(0), dim=1)  # (batch, embed_dim)
        x_sq_sum = torch.sum(
            x_sparse.unsqueeze(2) * (v.unsqueeze(0) ** 2), dim=1
        )  # (batch, embed_dim)
        
        fm_part = 0.5 * torch.sum(
            x_sum ** 2 - x_sq_sum, dim=1
        )  # (batch,)
        
        y_fm = linear_part.squeeze(0) + fm_part
        return y_fm


class DeepFM(nn.Module):
    """
    DeepFM: FM + Deep 联合模型
    
    y = σ(α · y_FM + β · y_Deep + γ)
    """
    
    def __init__(
        self,
        num_fields: int = 500,  # sparse feature fields
        embed_dim: int = 8,  # FM embedding dim
        deep_hidden_dims: list = [256, 128, 64],  # DNN hidden dims
    ):
        super().__init__()
        
        # FM 部分
        self.fm = FieldAwareFM(num_fields, embed_dim)
        
        # Deep 部分 (共享 FM embedding)
        deep_layers = []
        in_dim = num_fields * embed_dim
        for hidden_dim in deep_hidden_dims:
            deep_layers.extend([
                nn.Linear(in_dim, hidden_dim),
                nn.BatchNorm1d(hidden_dim),
                nn.ReLU(),
                nn.Dropout(0.2),
            ])
            in_dim = hidden_dim
        self.deep_net = nn.Sequential(*deep_layers, nn.Linear(in_dim, 1))
        
        # 融合权重 (可学习)
        self.alpha = nn.Parameter(torch.tensor(0.5))
        self.beta = nn.Parameter(torch.tensor(0.5))
        self.gamma = nn.Parameter(torch.tensor(0.0))
    
    def forward(self, x_sparse):
        """
        Args:
            x_sparse: (batch, num_fields) — one-hot or indices
        
        Returns:
            p_ctr: (batch,) — click probability
        """
        # FM part
        y_fm = self.fm(x_sparse)  # (batch,)
        
        # Deep part
        # 获取 embedding (假设 x_sparse 是 indices)
        # 如果是 one-hot，先投影到 embedding
        # 这里简化: 假设 x_sparse 已经是 indices
        emb = self.fm.field_emb[x_sparse]  # (batch, num_fields, embed_dim)
        emb_flat = emb.view(emb.size(0), -1)  # (batch, num_fields * embed_dim)
        y_deep = self.deep_net(emb_flat).squeeze(-1)  # (batch,)
        
        # 融合
        logits = self.alpha * y_fm + self.beta * y_deep + self.gamma
        p_ctr = torch.sigmoid(logits)
        
        return p_ctr


class DeepFMTrainer:
    """DeepFM 训练器"""
    
    def __init__(
        self,
        model: DeepFM,
        learning_rate: float = 1e-3,
        weight_decay: float = 1e-4,
    ):
        self.model = model
        self.optimizer = torch.optim.Adam(
            model.parameters(),
            lr=learning_rate,
            weight_decay=weight_decay,
        )
        self.scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
            self.optimizer, T_max=50
        )
    
    def train_epoch(
        self,
        loader: torch.utils.data.DataLoader,
        epoch: int,
    ) -> dict:
        """训练一个 epoch"""
        self.model.train()
        total_loss = 0.0
        total_samples = 0
        
        for x_sparse, y in loader:
            self.optimizer.zero_grad()
            
            p_ctr = self.model(x_sparse)
            loss = F.binary_cross_entropy(p_ctr, y)
            
            loss.backward()
            self.optimizer.step()
            
            total_loss += loss.item() * y.size(0)
            total_samples += y.size(0)
        
        avg_loss = total_loss / total_samples
        self.scheduler.step()
        
        return {
            'train_loss': avg_loss,
            'learning_rate': self.optimizer.param_groups[0]['lr'],
            'alpha': self.model.alpha.item(),
            'beta': self.model.beta.item(),
        }
    
    def evaluate(self, loader: torch.utils.data.DataLoader) -> dict:
        """评估"""
        self.model.eval()
        preds = []
        targets = []
        
        with torch.no_grad():
            for x_sparse, y in loader:
                p_ctr = self.model(x_sparse)
                preds.append(p_ctr.detach())
                targets.append(y)
        
        preds = torch.cat(preds)
        targets = torch.cat(targets)
        
        auc = compute_auc(preds, targets)
        logloss = F.binary_cross_entropy(preds, targets).item()
        
        return {
            'val_auc': auc,
            'val_logloss': logloss,
        }
```

---

## 第四部分：MMoE / PLE 多任务学习

### 4.1 MMOE (Multi-gate Mixture-of-Experts)

```
MMoE: 多任务学习，同时优化 CTR + CVR + 其他目标

设定:
├─ K 个任务: T = {T_1, T_2, ..., T_K} (如: CTR, CVR)
├─ M 个专家: E = {e_1, e_2, ..., e_M} (如: M=8 个 Expert)
├─ K 个门控: G = {g_1, g_2, ..., g_K} (每个任务一个门控)
└─ 每个门控学习: 哪些专家对哪个任务重要

架构:
┌──────────────────────────────────────────────────────────────┐
│              MMoE 架构                                        │
│                                                              │
│  Input: features → Shared Embedding                          │
│  │                                                          │
│  ├── Expert Layer:                                           │
│  │  ┌───────────────────────────────────────────────┐       │
│  │  │  Expert 1: f_1(x) = σ(W_1 · x + b_1)        │       │
│  │  │  Expert 2: f_2(x) = σ(W_2 · x + b_2)        │       │
│  │  │  ...                                       │       │
│  │  │  Expert M: f_M(x) = σ(W_M · x + b_M)        │       │
│  │  └───────────────────────────────────────────────┘       │
│  │  每个 Expert 独立学习数据的不同子空间                       │
│  │                                                          │
│  ├── Gate Layer (per task):                                 │
│  │  ┌───────────────────────────────────────────────┐       │
│  │  │  Gate 1 (Task 1: CTR):                         │       │
│  │  │    g_1 = softmax(W_g1 · x)                     │       │
│  │  │    h_1 = Σ g_1,m · f_m(x)  (加权平均)          │       │
│  │  │                                                │       │
│  │  │  Gate 2 (Task 2: CVR):                         │       │
│  │  │    g_2 = softmax(W_g2 · x)                     │       │
│  │  │    h_2 = Σ g_2,m · f_m(x)  (加权平均)          │       │
│  │  └───────────────────────────────────────────────┘       │
│  │  每个任务独立学习专家组合权重                               │
│  │                                                          │
│  └─ Tower Layer:                                              │
│     ┌───────────────────────────────────────────────┐       │
│     │  Tower 1 (CTR): y_1 = σ(W_t1 · h_1 + b_t1)   │       │
│     │  Tower 2 (CVR): y_2 = σ(W_t2 · h_2 + b_t2)   │       │
│     └───────────────────────────────────────────────┘       │
│                                                              │
│  损失函数:                                                    │
│  └─ L = L_CTR + α × L_CVR (或 weighted sum)                │
│                                                              │
│  优势:                                                       │
│  ├── 自动学习任务间知识共享                                    │
│  ├── 缓解任务间冲突 (negative transfer)                      │
│  └─ 灵活: 任务增减只需添加/移除对应门控                         │
└──────────────────────────────────────────────────────────────┘
```

### 4.2 MMoE 代码实现

```python
"""
MMoE (Multi-gate Mixture-of-Experts) — PyTorch 实现
"""

import torch
import torch.nn as nn
import torch.nn.functional as F


class Expert(nn.Module):
    """单个 Expert 网络"""
    
    def __init__(self, input_dim: int, hidden_dim: int = 64, output_dim: int = 32):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, output_dim),
        )
    
    def forward(self, x):
        return self.net(x)


class Gate(nn.Module):
    """门控: 学习专家权重"""
    
    def __init__(self, input_dim: int, num_experts: int):
        super().__init__()
        self.gate = nn.Linear(input_dim, num_experts)
    
    def forward(self, x):
        # softmax 得到权重
        return F.softmax(self.gate(x), dim=1)


class MMoE(nn.Module):
    """
    Multi-gate Mixture-of-Experts
    
    多任务 CTR + CVR 联合优化
    """
    
    def __init__(
        self,
        input_dim: int = 500,
        num_experts: int = 8,  # 专家数量
        expert_hidden: int = 128,
        expert_output: int = 32,
        task_towers: list = [
            {'name': 'ctr', 'hidden': [64, 32]},
            {'name': 'cvr', 'hidden': [64, 32]},
        ],
    ):
        super().__init__()
        
        self.num_experts = num_experts
        self.task_names = [t['name'] for t in task_towers]
        
        # Experts
        self.experts = nn.ModuleList([
            Expert(input_dim, expert_hidden, expert_output)
            for _ in range(num_experts)
        ])
        
        # Gates (one per task)
        self.gates = nn.ModuleList([
            Gate(input_dim, num_experts) for _ in range(len(task_towers))
        ])
        
        # Task Towers
        self.towers = nn.ModuleDict()
        for task in task_towers:
            layers = []
            in_dim = expert_output
            for hidden in task['hidden']:
                layers.extend([
                    nn.Linear(in_dim, hidden),
                    nn.ReLU(),
                    nn.Dropout(0.1),
                ])
                in_dim = hidden
            layers.append(nn.Linear(in_dim, 1))
            self.towers[task['name']] = nn.Sequential(*layers)
    
    def forward(self, x):
        """
        Forward pass
        
        Args:
            x: (batch, input_dim)
        
        Returns:
            outputs: dict {'ctr': (batch,), 'cvr': (batch,)}
        """
        # Expert 输出: (batch, num_experts, expert_output)
        expert_outputs = torch.stack(
            [expert(x) for expert in self.experts], dim=1
        )
        
        outputs = {}
        
        # 每个任务的门控 + 聚合
        for i, task_name in enumerate(self.task_names):
            # Gate: 学习专家权重
            gate_weights = self.gates[i](x)  # (batch, num_experts)
            
            # 加权聚合专家输出
            # expert_outputs: (batch, num_experts, expert_output)
            # gate_weights: (batch, num_experts)
            aggregated = torch.bmm(
                gate_weights.unsqueeze(1),  # (batch, 1, num_experts)
                expert_outputs  # (batch, num_experts, expert_output)
            ).squeeze(1)  # (batch, expert_output)
            
            # Task Tower
            tower_out = self.towers[task_name](aggregated).squeeze(-1)
            outputs[task_name] = torch.sigmoid(tower_out)
        
        return outputs


class MMoETrainer:
    """MMoE 训练器"""
    
    def __init__(
        self,
        model: MMoE,
        task_weights: dict = {'ctr': 1.0, 'cvr': 0.5},
        learning_rate: float = 1e-3,
    ):
        self.model = model
        self.task_weights = task_weights
        self.optimizer = torch.optim.Adam(
            model.parameters(),
            lr=learning_rate,
            weight_decay=1e-4,
        )
    
    def train_step(
        self,
        x: torch.Tensor,
        y_ctr: torch.Tensor,
        y_cvr: torch.Tensor,
    ) -> dict:
        """训练一步"""
        self.model.train()
        self.optimizer.zero_grad()
        
        outputs = self.model(x)
        
        # 计算各任务损失
        l_ctr = F.binary_cross_entropy(outputs['ctr'], y_ctr)
        l_cvr = F.binary_cross_entropy(outputs['cvr'], y_cvr)
        
        # 加权总损失
        total_loss = (
            self.task_weights['ctr'] * l_ctr +
            self.task_weights['cvr'] * l_cvr
        )
        
        total_loss.backward()
        self.optimizer.step()
        
        return {
            'total_loss': total_loss.item(),
            'l_ctr': l_ctr.item(),
            'l_cvr': l_cvr.item(),
            'p_ctr': outputs['ctr'].mean().item(),
            'p_cvr': outputs['cvr'].mean().item(),
        }
```

---

### 5.3 Go 实现：FTRL-Proximal 在线学习

```go
// FTRLProximal implements the Follow-The-Regularized-Leader
// with Proximal point estimator, used by Google for online CTR estimation.
// Reference: "Ad Click Prediction: a View from the Trenches" (McMahan et al., 2013)
package pctr

import (
	"fmt"
	"math"
	"sync"
)

// FeatureHash hashes a feature string to a bucket index.
// Used to reduce memory for sparse features (feature hashing / hashing trick).
func FeatureHash(feature string, numBuckets int) int {
	h := uint64(len(feature))
	for i := 0; i < len(feature); i++ {
		h = h*31 + uint64(feature[i])
	}
	return int(h%uint64(numBuckets))
}

// FTRLState tracks per-feature FTRL state.
type FTRLState struct {
	w     float64 // current weight
	z     float64 // sum of gradients
	n     float64 // sum of squared gradients
}

// FTRLProximal implements online learning for pCTR with L1/L2 regularization.
type FTRLProximal struct {
	numBuckets int
	alpha      float64 // learning rate scaling
	beta       float64 // learning rate smoothing
	l1         float64 // L1 regularization strength
	l2         float64 // L2 regularization strength

	mu    float64 // learning rate shift
	state map[int]*FTRLState
	mu    *sync.Mutex
}

// NewFTRLProximal creates a configured FTRL model.
// numBuckets: feature hashing bucket count (e.g., 2^20)
func NewFTRLProximal(numBuckets int, alpha, beta, l1, l2 float64) *FTRLProximal {
	return &FTRLProximal{
		numBuckets: numBuckets,
		alpha:      alpha,
		beta:       beta,
		l1:         l1,
		l2:         l2,
		mu:         0,
		state:      make(map[int]*FTRLState),
		mu: &sync.Mutex{},
	}
}

// sigmoid computes 1 / (1 + exp(-x)) with numerical stability.
func sigmoid(x float64) float64 {
	if x >= 0 {
		e := math.Exp(-x)
		return 1.0 / (1.0 + e)
	}
	e := math.Exp(x)
	return e / (1.0 + e)
}

// Predict returns the pCTR prediction for given feature buckets.
func (f *FTRLProximal) Predict(features []int) float64 {
	f.mu.Lock()
	defer f.mu.Unlock()

	p := 0.0
	for _, bucket := range features {
		s := f.getOrInitState(bucket)
		p += s.w
	}
	return sigmoid(p)
}

// Train updates model weights with one (features, label) sample.
func (f *FTRLProximal) Train(features []int, label float64) {
	f.mu.Lock()
	defer f.mu.Unlock()

	// Compute prediction before update
	pred := f.Predict(features)
	pred = math.Max(pred, 1e-15)
	pred = math.Min(pred, 1-1e-15)
	predLabel := math.Log(pred / (1.0 - pred)) // logit

	// Compute gradient (BCE loss)
	gradient := pred - label // d(BCE)/d(linear)

	// Update each feature
	for _, bucket := range features {
		s := f.getOrInitState(bucket)

		// FTRL update rule
		// a_i = (sqrt(n_i + g_i^2) + beta) / alpha - sqrt(n_i) / beta
		// w_i = -l1 * sign(z_i) / (l2 + a_i)  if |z_i| <= l1
		// w_i = -(z_i + l1 * sign(z_i)) / (2 * l2 + a_i)  otherwise

		a_i := (math.Sqrt(s.n+gradient*gradient) + f.beta) / f.alpha -
			math.Sqrt(s.n) / f.beta

		oldW := s.w
		zNew := s.z + gradient
		nNew := s.n + gradient*gradient

		// Apply proximal operator
		if math.Abs(zNew) <= f.l1 {
			s.w = 0
		} else {
			sign := math.Copysign(1, zNew)
			s.w = -((zNew + f.l1*sign) / (2*f.l2 + a_i))
		}

		s.z = zNew
		s.n = nNew

		// Store delta for efficient loss notification
		_ = oldW
	}
}

// getOrInitState retrieves or initializes FTRL state for a bucket.
func (f *FTRLProximal) getOrInitState(bucket int) *FTRLState {
	if s, ok := f.state[bucket]; ok {
		return s
	}
	s := &FTRLState{w: 0, z: 0, n: 0}
	f.state[bucket] = s
	return s
}

// Serialize exports current weights for model serving.
func (f *FTRLProximal) Serialize() map[int]float64 {
	f.mu.Lock()
	defer f.mu.Unlock()

	out := make(map[int]float64, len(f.state))
	for bucket, s := range f.state {
		out[bucket] = s.w
	}
	return out
}
```

---

## 第五部分：pCTR 训练与优化

### 5.1 训练策略

```
pCTR 训练关键策略:

1. 特征工程:
├── 离散特征: 稀疏 Embedding (每类独立 embedding)               │
├── 连续特征: 标准化 + 分桶 (Bucketization)                     │
├── 交叉特征: 自动 (DNN/FM) 或人工 (Wide)                      │
└─ 序列特征: RNN/Transformer (用户行为序列)                     │

2. 采样策略:
├── 负采样: 10:1 (正:负) 或 100:1 (极端不平衡)                  │
├── 难负采样: 采样与正样本相似但不转化的                          │
└─ 分层采样: 按用户/广告/时间分层保证分布一致                     │

3. 损失函数:
├── BCE: 标准二元交叉熵                                          │
├── Focal Loss: 处理类别不平衡                                  │
│   └─ FL = -α(1-p)^γ · log(p)                                │
└── Class-Balanced Loss: 有效样本数归一化                        │

4. 优化器:
├── Adam: 自适应学习率，收敛快                                   │
├── LAMB: 大规模分布式训练 (Layer-wise adaptive)                │
└─ FTRL-Proximal: Google 在线学习 (Sparse, Online)             │

5. 正则化:
├── Dropout: 0.1-0.3 (DNN)                                    │
├── Weight Decay: 1e-4-1e-5                                   │
├── Label Smoothing: 0.01-0.1                                  │
└─ Early Stopping: 验证集 AUC 不提升则停止                       │

6. 评估:
├── AUC-ROC: 主要指标                                          │
├── LogLoss: 概率质量                                         │
└─ 线上 A/B 测试: ROI, CTR, Revenue                            │
```

### 5.2 pCTR 线上服务

```
pCTR 线上服务架构:

┌──────────────────────────────────────────────────────────────┐
│              pCTR 服务架构                                     │
│                                                              │
│  服务层:                                                     │
│  ├── gRPC 服务: 接收 Bid Request，返回 pCTR                  │
│  ├── API 延迟: < 5ms (P99)                                  │
│  ├── 吞吐量: 100K+ QPS (每个实例)                            │
│  └─ 水平扩展: 自动扩缩容 (K8s HPA)                           │
│                                                              │
│  模型服务:                                                   │
│  ├── TensorFlow Serving / TorchServe / Triton               │
│  ├── 模型热更新: 无需重启服务                                  │
│  └─ 多版本并行: A/B 测试不同模型                              │
│                                                              │
│  缓存层:                                                     │
│  ├── 用户画像缓存 (Redis, SSD)                                │
│  ├── 广告特征缓存 (内存)                                      │
│  └─ pCTR 缓存: 相同特征组合直接返回                           │
│                                                              │
│  监控:                                                       │
│  ├── 延迟: P50/P95/P99                                       │
│  ├── 吞吐: QPS                                               │
│  ├── 预测分布: pCTR 均值/方差                                 │
│  └─ 模型性能: AUC, LogLoss (离线) + 线上 CTR (在线)          │
│                                                              │
│  灰度发布:                                                   │
│  ├── 1% 流量 → 新模型                                        │
│  ├── 观察 1h → 指标正常                                      │
│  ├── 10% → 100% 逐步放量                                     │
│  └─ 自动回滚: 指标异常则回滚到旧模型                           │
└──────────────────────────────────────────────────────────────┘
```

---

## 第六部分：自测题

### 问题 1（基础）
Wide & Deep 的 Wide 和 Deep 部分分别解决什么问题？

<details>
<summary>查看答案</summary>

Wide: 记忆能力，捕获稀疏强信号（人工特征交叉）
Deep: 泛化能力，自动学习密集弱信号（DNN 自动特征）
联合训练兼顾记忆力和泛化力
</details>

### 问题 2（基础）
DeepFM 的 FM 部分如何工作？

<details>
<summary>查看答案</summary>

FM 自动捕获一阶/二阶特征交叉:
一阶: Σ w_i · x_i
二阶: ½ Σ_k (Σ_i x_i · v_i^k)² - Σ_i (x_i · v_i^k)²
无需人工设计，自动学习
</details>

### 问题 3（进阶）
MMoE 如何缓解任务间冲突？

<details>
<summary>查看答案</summary>

每个任务有独立的 Gate，学习不同专家的权重组合:
- 任务 A 可能偏好 Expert 1,3,5
- 任务 B 可能偏好 Expert 2,4,6
- 自动分配专家到合适任务，避免负迁移
</details>

### 问题 4（进阶）
FTRL-Proximal 相比 Adam 在在线 CTR 学习中有什么优势？

<details>
<summary>查看答案</summary>

FTRL-Proximal 优势:
1. 稀疏特征天然友好：只对激活的特征做更新，内存 O(特征数)
2. 支持 L1 正则化：自动产生稀疏解，适合百万级特征
3. 在线学习：每来一个样本就更新，无需等待 batch
4. 收敛理论保证：在凸损失函数下有 regret bound
5. 不需要 GPU：纯 CPU 计算，适合低延迟场景

Adam 劣势:
1. 需要全量梯度更新，不适合超大规模稀疏特征
2. 内存占用大：需要维护每个参数的 momentum 和 variance
3. 不适合在线场景：需要 batch 数据
</details>

### 问题 5（实战）
pCTR 模型线上服务如何实现 <5ms P99 延迟？

<details>
<summary>查看答案</summary>

1. 特征缓存：用户画像/广告特征全部走 Redis Cluster，P99 < 1ms
2. 特征哈希：用 feature hashing 替代 embedding lookup，消除内存查询
3. 模型量化：FP32 → INT8，减少内存带宽
4. 批量推理：同一 batch 的请求合并为一个 tensor 推理
5. gRPC + 零拷贝序列化：Protocol Buffers 替代 JSON
6. 预测缓存：相同特征组合直接命中缓存（key = hash(features)）
7. 模型裁剪：移除低贡献层，减少 FLOPs
8. 部署：模型服务与竞价服务同机部署，避免网络跳转
</details>

### 问题 6（实战）
Go 中 FTRLProximal 的 sigmoid 函数为什么做了数值稳定处理？

<details>
<summary>查看答案</summary>

直接计算 1/(1+exp(-x)) 在 x 很大或很小时会溢出:
- x > 709: exp(-x) ≈ 0, 1/(1+0) = 1 ✓ 没问题
- x < -709: exp(-x) 溢出为 Inf, 1/(1+Inf) = 0 ✓ 也没问题
- 但 x 接近 ±709 时 exp 会接近 float64 极限

数值稳定的写法:
- x >= 0: return 1/(1+exp(-x))   — exp(-x) 很小，安全
- x < 0:  return exp(x)/(1+exp(x))  — exp(x) 很小，安全

这样避免了 exp 溢出到 Inf/NaN，确保预测值始终在 (0, 1) 范围内。
</details>

---

*今天花 90 分钟：深入掌握 pCTR 模型技术*
*答不出自测题？回去重读对应章节。*
