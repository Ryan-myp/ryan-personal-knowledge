# 广告 CTR/CVR 模型深度：特征工程/模型训练/线上推理

> 从特征到模型到推理的完整链路

---

## 第一部分：为什么 CTR/CVR 模型是广告系统的核心？

### 模型的重要性

```
eCPM = CTR × CVR × targetCPA × 1000

CTR（点击率）：
→ 预测用户点击广告的概率
→ 0.01 = 1% 概率点击

CVR（转化率）：
→ 预测用户点击后转化的概率
→ 0.05 = 5% 概率转化

模型精度提升 1%：
→ eCPM 提升 1%
→ 收入提升 1%
→ 1 亿收入 = 100 万额外收入
```

### 模型演进

```
1. LR（逻辑回归）：
   → 简单，快速
   → 精度一般
   → 工业界baseline

2. GBDT/XGBoost：
   → 能处理非线性
   → 训练快
   → 精度提升

3. DeepFM：
   → 自动特征交叉
   → 精度更高
   → 当前主流

4. Deep & Cross Network：
   → 显式特征交叉
   → 精度更高
   → 计算量大
```

---

## 第二部分：特征工程

### 2.1 特征分类

```
1. 用户特征：
   → 年龄/性别/城市
   → 历史点击率
   → 兴趣标签

2. 广告特征：
   → 广告主 ID
   → 广告类别
   → 历史 CTR/CVR
   → 创意类型

3. 上下文特征：
   → 时间/日期
   → 设备类型
   → 网络类型
   → 广告位

4. 交叉特征：
   → 用户×广告：用户年龄段×广告类别
   → 用户×上下文：用户城市×时间
   → 广告×上下文：广告类别×广告位
```

### 2.2 代码实现

```go
package feature

import (
    "fmt"
)

// FeatureExtractor 特征提取器
type FeatureExtractor struct {
    userFeatureExtractor *UserFeatureExtractor
    adFeatureExtractor   *AdFeatureExtractor
    contextExtractor     *ContextExtractor
}

// Extract 提取特征
func (fe *FeatureExtractor) Extract(userID, adID, slotID string, ctx Context) (*Features, error) {
    // 1. 用户特征
    userFeatures, err := fe.userFeatureExtractor.Extract(userID)
    if err != nil {
        return nil, err
    }
    
    // 2. 广告特征
    adFeatures, err := fe.adFeatureExtractor.Extract(adID)
    if err != nil {
        return nil, err
    }
    
    // 3. 上下文特征
    contextFeatures := fe.contextExtractor.Extract(ctx)
    
    // 4. 交叉特征
    crossFeatures := fe.extractCrossFeatures(userFeatures, adFeatures, contextFeatures)
    
    // 5. 合并所有特征
    features := mergeFeatures(userFeatures, adFeatures, contextFeatures, crossFeatures)
    
    return features, nil
}

// Features 特征向量
type Features struct {
    // 稠密特征
    DenseFeatures []float32
    
    // 稀疏特征（Embedding）
    SparseFeatures map[string][]float32
    
    // 交叉特征
    CrossFeatures []float32
}
```

### 2.3 特征存储

```go
// FeatureStore 特征存储
type FeatureStore struct {
    redis *RedisClient
    db    *Database
}

// GetUserFeatures 获取用户特征
func (fs *FeatureStore) GetUserFeatures(userID string) (*UserFeatures, error) {
    // 1. 查缓存
    key := fmt.Sprintf("user:features:%s", userID)
    cached, err := fs.redis.Get(key)
    if err == nil && cached != "" {
        return parseCachedFeatures(cached), nil
    }
    
    // 2. 查数据库
    userFeatures, err := fs.db.GetUserFeatures(userID)
    if err != nil {
        return nil, err
    }
    
    // 3. 写缓存
    fs.redis.Set(key, marshalFeatures(userFeatures), 3600)
    
    return userFeatures, nil
}

// GetAdFeatures 获取广告特征
func (fs *FeatureStore) GetAdFeatures(adID string) (*AdFeatures, error) {
    key := fmt.Sprintf("ad:features:%s", adID)
    cached, err := fs.redis.Get(key)
    if err == nil && cached != "" {
        return parseCachedFeatures(cached), nil
    }
    
    adFeatures, err := fs.db.GetAdFeatures(adID)
    if err != nil {
        return nil, err
    }
    
    fs.redis.Set(key, marshalFeatures(adFeatures), 3600)
    
    return adFeatures, nil
}
```

---

## 第三部分：模型训练

### 3.1 模型架构

```
DeepFM 模型架构：
┌─────────────────────────────────────────────────────┐
│                  DeepFM Model                        │
│                                                     │
│  Input: 特征向量                                       │
│    ├─ 稠密特征 → 全连接层                              │
│    └─ 稀疏特征 → Embedding 层                         │
│                                                     │
│  FM 层：                                             │
│    ├─ 一阶：单特征权重                                │
│    └─ 二阶：特征交互                                  │
│                                                     │
│  Deep 层：                                           │
│    ├─ 全连接层 1                                     │
│    ├─ ReLU + Dropout                                │
│    ├─ 全连接层 2                                     │
│    └─ ReLU + Dropout                                │
│                                                     │
│  输出层：                                             │
│    ├─ FM 输出 + Deep 输出 → 拼接                      │
│    └─ Sigmoid → 概率输出                              │
│                                                     │
│  Output: CTR/CVR 概率                                │
└─────────────────────────────────────────────────────┘
```

### 3.2 TensorFlow 实现

```python
import tensorflow as tf
from tensorflow.keras import layers

def build_deepfm_model(feature_columns, embedding_dim=8):
    """
    DeepFM 模型
    """
    # 输入层
    dense_inputs = {}
    sparse_inputs = {}
    
    for col in feature_columns:
        if col.dtype == 'dense':
            dense_inputs[col.name] = layers.Input(
                shape=(col.dim,), name=col.name, dtype='float32'
            )
        else:
            sparse_inputs[col.name] = layers.Input(
                shape=(1,), name=col.name, dtype='int32'
            )
    
    # Embedding 层（稀疏特征）
    embeddings = {}
    for name, inp in sparse_inputs.items():
        embeddings[name] = layers.Embedding(
            input_dim=col.vocabulary_size,
            output_dim=embedding_dim,
            name=f'embedding_{name}'
        )(inp)
    
    # FM 层（二阶特征交互）
    fm_input = tf.concat(list(embeddings.values()), axis=-1)
    fm_output = tf.reduce_sum(
        tf.square(tf.reduce_sum(fm_input, axis=1)) - 
        tf.square(tf.reduce_sum(tf.square(fm_input), axis=1)), 
        axis=1, keepdims=True
    ) / 2
    
    # Deep 层
    deep_input = tf.concat(list(embeddings.values()), axis=-1)
    deep_output = layers.Dense(128, activation='relu')(deep_input)
    deep_output = layers.Dropout(0.3)(deep_output)
    deep_output = layers.Dense(64, activation='relu')(deep_output)
    deep_output = layers.Dropout(0.3)(deep_output)
    deep_output = layers.Dense(32, activation='relu')(deep_output)
    
    # 拼接 FM 和 Deep 输出
    concat = layers.Concatenate()([fm_output, deep_output])
    output = layers.Dense(1, activation='sigmoid')(concat)
    
    model = tf.keras.Model(
        inputs=list(dense_inputs.values()) + list(sparse_inputs.values()),
        outputs=output
    )
    
    model.compile(
        optimizer='adam',
        loss='binary_crossentropy',
        metrics=['AUC']
    )
    
    return model
```

### 3.3 训练流程

```python
# 训练流程
def train_ctr_model(train_data, val_data, epochs=10):
    """
    训练 CTR 模型
    """
    # 1. 数据预处理
    feature_columns = extract_feature_columns(train_data)
    
    # 2. 构建模型
    model = build_deepfm_model(feature_columns)
    
    # 3. 训练
    callbacks = [
        tf.keras.callbacks.EarlyStopping(
            monitor='val_auc',
            patience=3,
            restore_best_weights=True
        ),
        tf.keras.callbacks.ReduceLROnPlateau(
            monitor='val_loss',
            factor=0.5,
            patience=2
        )
    ]
    
    history = model.fit(
        train_data,
        validation_data=val_data,
        epochs=epochs,
        batch_size=2048,
        callbacks=callbacks
    )
    
    # 4. 评估
    auc = model.evaluate(val_data)[1]
    print(f"Validation AUC: {auc}")
    
    # 5. 保存模型
    model.save('ctr_model.h5')
    
    return model
```

---

## 第四部分：线上推理

### 4.1 推理服务

```go
package predictor

import (
    "context"
    "time"
)

// Predictor 预测器
type Predictor struct {
    ctrModel   *Model // CTR 模型
    cvrModel   *Model // CVR 模型
    featureStore *FeatureStore
    timeout    time.Duration
}

// Predict 预测 CTR/CVR
func (p *Predictor) Predict(ctx context.Context, userID, adID string) (*Prediction, error) {
    // 1. 提取特征
    features, err := p.featureStore.Extract(userID, adID)
    if err != nil {
        return nil, err
    }
    
    // 2. 并行预测 CTR 和 CVR
    var ctrPred, cvrPred *ModelPrediction
    var ctrErr, cvrErr error
    
    var wg sync.WaitGroup
    wg.Add(2)
    
    go func() {
        defer wg.Done()
        ctrPred, ctrErr = p.ctrModel.Predict(ctx, features)
    }()
    
    go func() {
        defer wg.Done()
        cvrPred, cvrErr = p.cvrModel.Predict(ctx, features)
    }()
    
    wg.Wait()
    
    // 3. 合并结果
    if ctrErr != nil || cvrErr != nil {
        // 降级：使用历史均值
        return &Prediction{
            CTR: 0.01, // 历史平均 CTR
            CVR: 0.05, // 历史平均 CVR
        }, nil
    }
    
    return &Prediction{
        CTR: ctrPred.Probability,
        CVR: cvrPred.Probability,
    }, nil
}
```

### 4.2 模型部署

```
模型部署架构：
┌─────────────────────────────────────────────────────┐
│                  模型部署架构                          │
│                                                     │
│  Model Server (TensorFlow Serving)                  │
│    ├─ CTR Model (端口 8501)                          │
│    └─ CVR Model (端口 8502)                          │
│                                                     │
│  Predictor Service (Go)                             │
│    ├─ 特征提取                                       │
│    ├─ gRPC 调用模型服务器                            │
│    └─ 结果合并                                       │
│                                                     │
│  性能：                                             │
│    ├─ 特征提取：5ms                                 │
│    ├─ 模型推理：10ms                                │
│    └─ 总耗时：15ms                                  │
└─────────────────────────────────────────────────────┘
```

---

## 第五部分：模型评估

### 5.1 评估指标

```
1. AUC：
   → 衡量模型排序能力
   → AUC > 0.6 可用
   → AUC > 0.7 优秀

2. LogLoss：
   → 衡量预测概率准确性
   → LogLoss 越低越好

3. PSI：
   → 衡量特征分布稳定性
   → PSI < 0.1 稳定
   → PSI > 0.2 需要重新训练

4. Lift：
   → 衡量模型提升效果
   → Lift = 模型组转化率 / 对照组转化率
   → Lift > 1 有效
```

### 5.2 代码实现

```go
// ModelEvaluator 模型评估器
type ModelEvaluator struct{}

// Evaluate 评估模型
func (me *ModelEvaluator) Evaluate(predictions, actuals []float64) *Metrics {
    // 1. 计算 AUC
    auc := me.calculateAUC(predictions, actuals)
    
    // 2. 计算 LogLoss
    logLoss := me.calculateLogLoss(predictions, actuals)
    
    // 3. 计算 PSI
    psi := me.calculatePSI(predictions)
    
    return &Metrics{
        AUC:    auc,
        LogLoss: logLoss,
        PSI:    psi,
    }
}

// calculateAUC 计算 AUC
func (me *ModelEvaluator) calculateAUC(predictions, actuals []float64) float64 {
    // 简化实现，实际使用排序算法
    n := len(predictions)
    pairs := 0
    concordant := 0
    
    for i := 0; i < n; i++ {
        for j := i + 1; j < n; j++ {
            if actuals[i] != actuals[j] {
                pairs++
                if (predictions[i] > predictions[j] && actuals[i] > actuals[j]) ||
                   (predictions[i] < predictions[j] && actuals[i] < actuals[j]) {
                    concordant++
                }
            }
        }
    }
    
    if pairs == 0 {
        return 0.5
    }
    
    return float64(concordant) / float64(pairs)
}
```

---

## 第六部分：自测题

### 问题 1
为什么用 DeepFM 而不是 LR？

<details>
<summary>查看答案</summary>

1. **LR**：只能学习线性特征
2. **DeepFM**：自动学习特征交叉
3. **FM 层**：二阶特征交互
4. **Deep 层**：高阶特征交互
5. **精度**：DeepFM AUC 通常比 LR 高 2-5%
</details>

### 问题 2
模型评估用哪些指标？

<details>
<summary>查看答案</summary>

1. **AUC**：排序能力，> 0.7 优秀
2. **LogLoss**：概率准确性，越低越好
3. **PSI**：特征稳定性，< 0.1 稳定
4. **Lift**：提升效果，> 1 有效
5. **线上指标**：eCPM 提升
</details>

---

*本文档基于广告 CTR/CVR 模型生产实战整理。*