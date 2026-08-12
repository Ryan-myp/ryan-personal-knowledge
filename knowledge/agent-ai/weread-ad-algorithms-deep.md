# 微信读书精华：广告算法与机器学习 蒸馏笔记

> 来源：《广告算法与实践》- 王晓华
> 状态：在读中（基于目录、简介和现有知识蒸馏）
> 蒸馏日期：2026-08-12
> 标签：#广告 #算法 #机器学习 #推荐系统

---

## 第一部分：广告算法核心框架

### 广告算法全景图

```
广告算法体系：

┌─────────────────────────────────────────────────────────────────────┐
│                        广告算法分层                                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  L1: 召回层 (Recall)                                                │
│  ├── 用户画像召回                                                   │
│  ├── 物品召回                                                       │
│  ├── 协同过滤召回                                                   │
│  └── 深度学习召回 (DSSM, DuoRec)                                    │
│                                                                     │
│  L2: 粗排层 (Pre-ranking)                                           │
│  ├── 特征交叉                                                       │
│  ├── 轻量模型排序                                                   │
│  └── 快速过滤                                                       │
│                                                                     │
│  L3: 精排层 (Ranking)                                               │
│  ├── CTR 预估 (pCTR)                                                │
│  ├── CVR 预估 (pCVR)                                                │
│  ├── 多目标融合 (ESMM, MMoE)                                        │
│  └── 深度排序 (DeepFM, DCN, xDeepFM)                               │
│                                                                     │
│  L4: 重排层 (Re-ranking)                                            │
│  ├── 业务规则过滤                                                   │
│  ├── 多样性打散                                                     │
│  ├── 位置偏置校正                                                   │
│  └── 约束优化                                                       │
│                                                                     │
│  L5: 出价层 (Bidding)                                               │
│  ├── 实时竞价 (RTB)                                                 │
│  ├── 智能出价 (tCPA, tROAS)                                         │
│  ├── Bid Shading                                                    │
│  └── 预算约束优化                                                   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 核心公式体系

```
竞价核心公式：
┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │
│  eCPM = bid × pCTR × 1000                                          │
│                                                                     │
│  实际出价 = bid × BidShadingFactor                                 │
│                                                                     │
│  QualityScore = α × CTR + β × 相关度 + γ × 落地页体验              │
│                                                                     │
│  第二价格拍卖：                                                      │
│  中标价 = 第二名出价 × 第二名质量分 / 第一名质量分                   │
│                                                                     │
│  多目标融合：                                                        │
│  Score = w1×pCTR + w2×pCVR×bid + w3×pRetention                     │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 第二部分：CTR/CVR 预估模型

### 模型演进路径

```
CTR 预估模型发展：
┌────────────┬──────────────┬──────────────┬──────────────┐
│   阶段     │    模型      │   核心创新   │   应用场景   │
├────────────┼──────────────┼──────────────┼──────────────┤
│ 1.0 时代   │ LR/GBDT      │ 线性模型     │ 早期工业界   │
│ 2.0 时代   │ DeepCross    │ 特征交叉     │ 推荐系统     │
│ 3.0 时代   │ DeepFM       │ FM+DNN融合   │ 广告排序     │
│ 4.0 时代   │ DCN/xDeepFM  │ 交叉网络     │ 大规模广告   │
│ 5.0 时代   │ Multi-task   │ 多目标学习   │ 多优化目标   │
└────────────┴──────────────┴──────────────┴──────────────┘
```

### DeepFM 核心架构

```python
# DeepFM 模型结构
class DeepFM(nn.Module):
    def __init__(self, feature_dim, embed_dim=8):
        super().__init__()
        # Field-Wise Bi-Interaction Layer
        self.fm = FieldWiseFM(feature_dim, embed_dim)
        # Deep Layer
        self.deep = nn.Sequential(
            nn.Linear(embed_dim * feature_dim, 256),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(256, 128),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(128, 1)
        )
    
    def forward(self, x):
        fm_out = self.fm(x)
        deep_out = self.deep(x)
        return torch.sigmoid(fm_out + deep_out)

# 特征交叉可视化
"""
输入特征：
[性别, 年龄, 城市, 兴趣1, 兴趣2, ...]

FM 层自动学习二阶特征交叉：
y_fm = <v_i, v_j> * x_i * x_j

其中 v_i 是第 i 个特征的隐向量
"""
```

---

## 第三部分：多目标学习

### ESMM 预估模型

```
ESMM (Entire Space Multi-Task Model) 解决 CVR 数据稀疏问题：

传统方案：
┌─────────────────────────────────────────────────────────────────────┐
│   impression → click → convert                                      │
│     ↓          ↓         ↓                                          │
│   全量样本   点击样本   转化样本（极度稀疏）                          │
└─────────────────────────────────────────────────────────────────────┘

ESMM 方案：
┌─────────────────────────────────────────────────────────────────────┐
│  共享底层表示，同时学习：                                            │
│  ├── CTCVR = CVR × CTR（完整空间）                                  │
│  ├── CTR（点击率）                                                   │
│  └── CVR = CTCVR / CTR（间接学习）                                   │
│                                                                     │
│  优势：                                                              │
│  1. 避免样本选择偏差 (SSB)                                          │
│  2. 解决数据稀疏问题 (SD)                                           │
│  3. 利用 CTR 信号辅助 CVR 学习                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### MMoE 多任务架构

```go
// MMoE (Multi-Gate Mixture-of-Experts) 实现
type MMoE struct {
    num_experts int
    num_tasks   int
    expert_dim  int
}

func (m *MMoE) Forward(input Tensor) []Tensor {
    // 共享 expert 层
    expert_outputs := make([]Tensor, m.num_experts)
    for i := 0; i < m.num_experts; i++ {
        expert_outputs[i] = m.experts[i](input)
    }
    
    // 每个 task 的 gate 网络
    task_outputs := make([]Tensor, m.num_tasks)
    for t := 0; t < m.num_tasks; t++ {
        // gate 权重
        gates := m.gates[t](input)
        // 加权聚合 experts
        weighted_sum := zero_tensor
        for e := 0; e < m.num_experts; e++ {
            weighted_sum += gates[e] * expert_outputs[e]
        }
        task_outputs[t] = m.task_networks[t](weighted_sum)
    }
    
    return task_outputs
}
```

---

## 第四部分：广告推荐系统

### 推荐系统 Pipeline

```
广告推荐全流程：

┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │
│  1. 召回 (Retrieval) — 从百万级到千级                                │
│  ├── 规则召回：定向条件过滤                                          │
│  ├── 协同过滤：相似用户/物品                                         │
│  ├── 向量召回：DSSM, DuoRec                                         │
│  └── 热点召回：热门广告                                              │
│                                                                     │
│  2. 粗排 (Pre-ranking) — 从千级到百级                                │
│  ├── 特征交叉预处理                                                  │
│  ├── 轻量模型打分                                                    │
│  └── 快速过滤                                                        │
│                                                                     │
│  3. 精排 (Ranking) — 从百级到十级                                    │
│  ├── DeepFM / DCN 模型                                             │
│  ├── 实时特征提取                                                    │
│  ├── 多目标融合 (CTR+CVR+Retention)                                 │
│  └── 个性化排序                                                      │
│                                                                     │
│  4. 重排 (Re-ranking) — 最终输出                                     │
│  ├── 业务规则：频控、预算、行业分布                                   │
│  ├── 多样性：同一广告主去重                                          │
│  ├── 位置偏置：探索与利用平衡                                        │
│  └── 人工干预：特殊场景处理                                          │
│                                                                     │
│  5. 竞价 (Bidding) — 最终出价                                        │
│  ├── 实时竞价 (RTB)                                                 │
│  ├── 智能出价 (tCPA/tROAS)                                          │
│  ├── Bid Shading                                                   │
│  └── 预算控制                                                        │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 第五部分：冷启动与探索利用

### 冷启动解决方案

```
广告冷启动问题：

场景 1: 新广告主
├─ 问题：无历史数据，无法预估 CTR/CVR
├─ 方案：
│   ├── 基于内容的推荐（素材分析）
│   ├── 相似广告主迁移
│   ├── 主动探索（提高初始出价）
│   └── Bandit 算法平衡探索与利用
└─ 指标：7 日内达到基准 CTR

场景 2: 新流量
├─ 问题：新用户无画像，无法精准投放
├─ 方案：
│   ├── 人口统计学特征
│   ├── 行为序列建模
│   ├── 上下文特征
│   └── 图神经网络（用户-物品关系）
└─ 指标：3 日内完成用户画像构建

场景 3: 新行业
├─ 问题：行业特性不同，模型泛化差
├─ 方案：
│   ├── 迁移学习
│   ├── 元学习 (Meta-Learning)
│   ├── 少样本学习
│   └─ 行业模板
└─ 指标：5 日内达到行业基准
```

### Thompson Sampling 出价策略

```go
// Thompson Sampling 实现
type ThompsonSampling struct {
    alpha map[string]float64 // 成功计数
    beta  map[string]float64 // 失败计数
}

func (t *ThompsonSampling) SelectArm(arm string) float64 {
    alpha := t.alpha[arm]
    beta := t.beta[arm]
    // 从 Beta(alpha, beta) 分布采样
    return betaSample(alpha, beta)
}

func (t *ThompsonSampling) Update(arm string, reward float64) {
    if reward > 0 {
        t.alpha[arm]++
    } else {
        t.beta[arm]++
    }
}

// 应用：广告位出价决策
// 每个广告位是一个 arm，根据历史表现动态调整出价
```

---

## 第六部分：归因与效果评估

### 归因模型对比

```
归因模型对比表：

┌──────────────┬────────────┬────────────┬────────────┐
│    模型      │  核心思想  │   优点     │   缺点     │
├──────────────┼────────────┼────────────┼────────────┤
│ Last Click   │ 最后触点   │ 简单       │ 忽略其他   │
│ First Click  │ 首次触点   │ 看重引流   │ 忽略转化   │
│ Linear       │ 均匀分配   │ 公平       │ 无区分度   │
│ Time Decay   │ 时间衰减   │ 重视近期   │ 参数主观   │
│ Position     │ 位置权重   │ 平衡首尾   │ 固定权重   │
│ U-Shaped     │ 首尾各40%  │ 重视触达   │ 中间忽略   │
│ Data Driven  │ 数据驱动   │ 最准确     │ 需要数据   │
│ Shapley      │ 合作博弈   │ 理论严谨   │ 计算复杂   │
│ Markov       │ 状态转移   │ 考虑序列   │ 实现复杂   │
└──────────────┴────────────┴────────────┴────────────┘
```

---

## 实践应用

### 场景 1: CTR 预估模型选型

1. 评估数据规模（样本量、特征数）
2. 选择模型复杂度（LR → DeepFM → DCN）
3. 实现特征工程（交叉、哈希、Embedding）
4. 在线服务部署（TensorFlow Serving / Triton）
5. 持续 A/B 测试优化

### 场景 2: 多目标优化

1. 确定优化目标（CTR、CVR、ROI）
2. 选择多任务架构（ESMM、MMoE、PLE）
3. 设计损失函数权重
4. 监控各目标指标
5. 动态调整权重

---

## 自测题

<details>
<summary>Q1: 为什么 ESMM 能解决 CVR 数据稀疏问题？</summary>

**答案**：
1. **传统问题**：CVR 样本只有转化用户，数据极度稀疏
2. **ESMM 创新**：
   - 同时在 impression 空间学习 CTR 和 CTCVR
   - CVR = CTCVR / CTR，间接学习
   - CTR 信号帮助 CVR 学习
3. **效果**：避免样本选择偏差 (SSB) 和数据稀疏 (SD)
</details>

<details>
<summary>Q2: DeepFM 相比传统 GBDT+LR 的优势是什么？</summary>

**答案**：
1. **自动特征交叉**：FM 层自动学习二阶交叉，无需人工设计
2. **高阶特征**：Deep 层可学习高阶特征组合
3. **端到端训练**：联合优化，避免级联误差
4. **泛化能力**：Embedding 表示更鲁棒
5. **工业验证**：在 AdTech 领域广泛验证有效
</details>

<details>
<summary>Q3: Bid Shading 的原理是什么？如何实现？</summary>

**答案**：
1. **原理**：通过分析历史中标数据，学习价格分布
2. **目标**：在保持中标率的前提下降低出价
3. **实现**：
   ```go
   func BidShading(originalBid, winRate float64) float64 {
       if winRate > 0.9 {
           return originalBid * 0.95  // 中标率高，降低出价
       }
       if winRate < 0.1 {
           return originalBid * 1.05  // 中标率低，提高出价
       }
       return originalBid
   }
   ```
4. **优化**：结合历史价格分布，动态调整 shading factor
</details>

---

## 后续行动

- [ ] 深入阅读《广告算法与实践》原书
- [ ] 实现 DeepFM 模型代码
- [ ] 搭建 ESMM 多目标训练框架
- [ ] 实践 Bid Shading 出价策略
- [ ] 更新 ad-bidding-expert skill

---

*蒸馏来源：《广告算法与实践》王晓华 | 结合 weread-skills 笔记整理*
