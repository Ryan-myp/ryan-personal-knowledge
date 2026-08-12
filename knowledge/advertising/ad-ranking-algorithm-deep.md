# 广告排序算法深度实现

> **文档级别**: Level 5 - 专家级  
> **创建日期**: 2026-08-13  
> **状态**: ✅ 已补齐

---

## 一、排序算法架构

```
请求 → [召回层] → [粗排层] → [精排层] → [重排层] → 输出
      │         │          │          │           │
  ┌───┴───┐ ┌──┴──┐ ┌──┴──┐ ┌──┴──┐
  │向量召回│ │规则召回│ │BM25 │ │业务规则│
  │关键词召回│ │类目召回│ │语义召回│ │冷启处理│
  └───────┘ └─────┘ └─────┘ └─────┘

精排核心公式: pCTR × bid × weight = final_score
```

---

## 二、核心排序算法

### 2.1 GBDT + LR 双塔模型

```go
// 文件: ranking/gbdt_lr.go
package ranking

import (
    "github.com/datalaboratory/gbdt"
    "github.com/tensorflow/tensorflow/tensorflow/go"
)

type GBDDLRLanker struct {
    gbdtModel  *gbdt.Model
    lrModel    *tf.SavedModel
    featureMap map[string]int
}

// Rank 执行排序
func (r *GBDDLRLanker) Rank(ctx context.Context, req *RankRequest) (*RankResponse, error) {
    // 1. GBDT 叶子节点映射
    leafIDs := r.gbdtModel.PredictLeaves(req.Features)
    
    // 2. 转换为 One-Hot 特征
    oneHotFeatures := r.leafToFeatures(leafIDs)
    
    // 3. LR 模型预测 pCTR
    pCTR := r.lrModel.Predict(oneHotFeatures)
    
    // 4. 计算最终分数
    score := pCTR * req.Bid * r.calculateWeight(req)
    
    return &RankResponse{Score: score, pCTR: pCTR}, nil
}

// leafToFeatures 叶子节点转 One-Hot
func (r *GBDDLRLanker) leafToFeatures(leafIDs [][]int) [][]float32 {
    numLeaves := len(r.gbdtModel.Trees[0].Leaves)
    features := make([][]float32, len(leafIDs))
    
    for i, leaves := range leafIDs {
        feat := make([]float32, len(r.gbdtModel.Trees)*numLeaves)
        for j, leaf := range leaves {
            feat[j*numLeaves+leaf] = 1.0
        }
        features[i] = feat
    }
    return features
}
```

### 2.2 DeepFM 深度模型

```go
// 文件: ranking/deepfm.go
package ranking

import "github.com/tensorflow/tensorflow/tensorflow/go"

// DeepFMLanker DeepFM 排序器
type DeepFMLanker struct {
    model      *tf.SavedModel
    session    *tf.Session
    inputFeats map[string]tf.Output
    outputCTR  tf.Output
}

// Predict 预测 pCTR
func (d *DeepFMLanker) Predict(ctx context.Context, features map[string][]float32) (float32, error) {
    inputs := make(map[string]*tf.Tensor)
    for name, values := range features {
        tensor, _ := tf.NewTensor(values)
        inputs[name] = tensor
    }
    
    results, err := d.session.Run(
        d.inputFeats,
        inputs,
        []tf.Output{d.outputCTR},
    )
    if err != nil {
        return 0, err
    }
    
    var pCTR float32
    if err := results[0].To(&pCTR); err != nil {
        return 0, err
    }
    return pCTR, nil
}

// DeepFM 结构:
// 输入层: 离散特征 → Embedding 层 | 连续特征 → 直接输入
// FM 层: 一阶 W·x + 二阶 ΣΣ<b_i·b_j·x_i·x_j>
// DNN 层: 多层全连接 → ReLU → Dropout
// 输出层: Concat(FM, DNN) → Sigmoid → pCTR
```

---

## 三、特征工程

### 3.1 特征体系设计

```
特征体系:
├── 用户特征
│   ├── 基础属性: 年龄、性别、地域、设备
│   ├── 行为特征: 点击历史、转化历史、浏览时长
│   ├── 兴趣标签: 类目偏好、价格敏感度
│   └── 实时特征: 最近 1h/24h/7d 行为
│
├── 广告特征
│   ├── 基础属性: 出价、预算、定向条件
│   ├── 创意特征: 图片类型、文案长度
│   ├── 效果特征: 历史 CTR、转化率
│   └── 竞争特征: 同赛道广告数量
│
├── 上下文特征
│   ├── 时间特征: 小时、星期、节假日
│   ├── 场景特征: 页面类型、位置
│   └── 网络特征: 网速、信号强度
│
└── 交叉特征
    ├── 用户 × 广告: 兴趣匹配度
    ├── 用户 × 上下文: 时段偏好
    └── 广告 × 上下文: 场景相关性
```

---

## 四、多级漏斗排序

```
Stage 1: 召回 (Recall)
├─ 目标: 从百万级广告召回千级候选
├─ 方法: 向量检索 + 规则过滤
├─ 耗时: <5ms
└─ 输出: 1000 个候选广告

Stage 2: 粗排 (Pre-Ranking)
├─ 目标: 从千级候选筛选百级候选
├─ 方法: 浅层模型 (逻辑回归)
├─ 耗时: <10ms
└─ 输出: 100 个候选广告

Stage 3: 精排 (Ranking)
├─ 目标: 对百级候选精确排序
├─ 方法: 深度学习模型 (DeepFM/DNN)
├─ 耗时: <50ms
└─ 输出: 排序后的 100 个广告

Stage 4: 重排 (Re-Ranking)
├─ 目标: 优化用户体验和多样性
├─ 方法: 规则 + MMR 多样性算法
├─ 耗时: <10ms
└─ 输出: 最终展示的 10 个广告

总耗时: <75ms (满足 <100ms 要求)
```

---

## 五、排序性能优化

```go
// 文件: ranking/model_optimization.go
package ranking

import (
    "github.com/dgraph-io/ristretto"
    "time"
)

// ModelCache 模型结果缓存
type ModelCache struct {
    ctrCache   *ristretto.Cache
    featureCache *ristretto.Cache
}

// GetOrPredict 获取或预测
func (m *ModelCache) GetOrPredict(ctx context.Context, features []float32, predictFn func([]float32) (float32, error)) (float32, error) {
    hash := fmt.Sprintf("%x", murmur3.Sum32(features))
    
    if cached, ok := m.ctrCache.Get(hash); ok {
        return cached.(float32), nil
    }
    
    pCTR, err := predictFn(features)
    if err != nil {
        return 0, err
    }
    
    m.ctrCache.SetWithTTL(hash, pCTR, int64(pCTR*1000), 60*time.Second)
    return pCTR, nil
}
```

---

## 六、性能基准

```
模型类型              QPS      P99延迟    准确率 (AUC)
────────────────────────────────────────────────────────
GBDT+LR             10K      35ms       0.68
DeepFM              3K       85ms       0.72
DeepFM + 量化        8K       40ms       0.71
模型缓存 (命中率 80%) 20K      15ms       0.72

推荐方案:
├─ 小规模 (< 1K QPS): GBDT+LR + 缓存
├─ 中规模 (1K-10K QPS): DeepFM 量化 + 多级缓存
└─ 大规模 (> 10K QPS): DeepFM 量化 + 模型服务分离
```

---

*文档版本: v1.0*  
*最后更新: 2026-08-13*  
*作者: Ryan*
