# 广告归因生产实践深度实现 - 多触点归因与实验设计

> **版本**: v2.1  
> **日期**: 2026-08-13  
> **作者**: Ryan  
> **分类**: 广告/归因  
> **代码密度**: 32%

---

## 一、多触点归因模型

```
┌─────────────────────────────────────────────────────────────────────┐
│                    触点归因模型对比                                  │
│                                                                     │
│  ┌──────────────────┬──────────┬──────────┬──────────────────────┐ │
│  │      模型         │ 最后触点  │ 首次触点  │        适用场景       │ │
│  ├──────────────────┼──────────┼──────────┼──────────────────────┤ │
│  │ 线性归因          │ 20%      │ 20%      │ 对称渠道             │ │
│  │ 时间衰减          │ 40%      │ 10%      │ 重视转化前触点        │ │
│  │ 位置归因          │ 25%      │ 25%      │ 首末触点重要          │ │
│  │ U型归因           │ 25%      │ 25%      │ 首次+转化触点         │ │
│  │ 自定义权重        │ 可调     │ 可调     │ 有业务经验            │ │
│  │ Markov链          │ 自动学习  │ 自动学习  │ 复杂渠道网络          │ │
│  │ Shapley值         │ 公平分配  │ 公平分配  │ 渠道间强交互          │ │
│  └──────────────────┴──────────┴──────────┴──────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 二、Markov Chain 归因

```python
# attribution/markov.py
import numpy as np
from scipy import linalg

class MarkovAttribution:
    """马尔可夫链归因模型"""
    
    def __init__(self, transition_matrix):
        """
        transition_matrix: 触点转移概率矩阵
        行: 当前触点, 列: 下一触点
        """
        self.P = np.array(transition_matrix)
        self.channels = list(range(len(transition_matrix)))
    
    def compute_vitality(self):
        """计算通道活力值"""
        n = len(self.channels)
        
        # 移除每个通道后的新矩阵
        vitality = {}
        for i in self.channels:
            # 移除第i行第i列
            reduced_matrix = np.delete(np.delete(self.P, i, axis=0), i, axis=1)
            
            # 计算吸收概率
            if reduced_matrix.size > 0:
                try:
                    # 单位矩阵减转移矩阵
                    I_reduced = np.eye(len(reduced_matrix))
                    fundamental = linalg.inv(I_reduced - reduced_matrix)
                    vitality[self.channels[i]] = 1 - np.sum(fundamental[0])
                except:
                    vitality[self.channels[i]] = 0
            else:
                vitality[self.channels[i]] = 0
        
        # 归一化
        total = sum(vitality.values())
        if total > 0:
            for k in vitality:
                vitality[k] /= total
        
        return vitality
    
    def attribute(self, touchpoint_sequence):
        """对单个转化序列归因"""
        contribution = {}
        for t in touchpoint_sequence:
            contribution[t] = contribution.get(t, 0) + 1
        
        total = sum(contribution.values())
        if total == 0:
            return contribution
        
        # 乘以活力值
        vitality = self.compute_vitality()
        for ch in contribution:
            contribution[ch] *= vitality.get(ch, 0)
        
        # 归一化
        total = sum(contribution.values())
        if total > 0:
            for ch in contribution:
                contribution[ch] /= total
        
        return contribution

# 示例: 3个通道的转移矩阵
#        FB   Google  Search
# FB    [0.0, 0.6, 0.4]
# Google [0.3, 0.0, 0.7]
# Search [0.5, 0.5, 0.0]
P = [[0.0, 0.6, 0.4],
     [0.3, 0.0, 0.7],
     [0.5, 0.5, 0.0]]

markov = MarkovAttribution(P)
vitality = markov.compute_vitality()
print(f"通道活力值: {vitality}")
# 结果用于调整各通道贡献度
```

---

## 三、增量测试 (Lift Test)

```go
// attribution/lift_test.go
package attribution

import (
    "context"
    "math"
    "time"
)

// LiftTest 增量测试
type LiftTest struct {
    controlGroup []User    // 对照组(不曝光)
    testGroup    []User    // 实验组(曝光)
    conversions  map[string]int
}

// RunLiftTest 执行增量测试
func (t *LiftTest) RunLiftTest(ctx context.Context, duration time.Duration) (*LiftResult, error) {
    // 1. 随机分组
    allUsers := t.randomSplit(0.5)
    control := allUsers[:len(allUsers)/2]
    test := allUsers[len(allUsers)/2:]
    
    // 2. 对照组不曝光，实验组曝光
    go t.runControl(control, duration)
    go t.runTest(test, duration)
    
    // 3. 等待实验完成
    <-ctx.Done()
    
    // 4. 计算增量
    controlRate := float64(t.conversions["control"]) / float64(len(control))
    testRate := float64(t.conversions["test"]) / float64(len(test))
    
    lift := (testRate - controlRate) / controlRate
    
    return &LiftResult{
        ControlRate: controlRate,
        TestRate:    testRate,
        Lift:        lift,
        SampleSize:  len(allUsers),
    }, nil
}

// CalculateSignificance 计算统计显著性
func (t *LiftTest) CalculateSignificance(controlRate, testRate float64, n int) float64 {
    // Z检验
    pooledRate := (controlRate + testRate) / 2
    se := math.Sqrt(pooledRate * (1 - pooledRate) * 2 / float64(n))
    z := (testRate - controlRate) / se
    
    // p值 (双尾)
    pValue := 2 * normalCDF(-math.Abs(z))
    return pValue
}

type LiftResult struct {
    ControlRate float64
    TestRate    float64
    Lift        float64    // 提升百分比
    SampleSize  int
    PValue      float64
}
```

---

## 四、跨设备归因

```
跨设备归因技术方案:
┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │
│  设备1 (Mobile)         设备2 (Tablet)      设备3 (Desktop)         │
│    IMEI: abc123           MAC: xyz789          Email: user@email.com │
│    IDFA: AAAA-BBBB        IDFA: CCCC-DDDD     User ID: 12345       │
│                                                                     │
│  链接方式:                                                         │
│  1. Hash-based: SHA256(IMEI) → 匿名化标识                           │
│  2. Probabilistic: WiFi MAC + 地理位置 + 时间窗口匹配               │
│  3. Deterministic: 登录状态共享 (同一账号)                          │
│  4. Fingerprinting: 浏览器指纹 + 行为特征                           │
│                                                                     │
│  实现流程:                                                         │
│  点击(Mobile) → 生成匿名ID → 存储device_graph                       │
│       ↓                                                            │
│  转化(Desktop) → 查找device_graph → 关联转化                        │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 五、自测题

1. **Markov归因相比规则归因的优势？**
   - 自动学习通道间的转移概率，考虑所有可能的路径组合

2. **增量测试的核心价值？**
   - 排除自然转化，准确测量广告的真实增量效果

3. **跨设备归因的挑战？**
   - 隐私法规限制、设备识别率低、归因窗口长

