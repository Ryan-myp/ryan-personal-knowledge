# A/B测试框架深度实现 - 资深专家深度实现

## 一、实验设计

```
┌─────────────────────────────────────────────────────────────────────────┐
│                   A/B测试实验设计流程                                       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   1. 明确目标 → 2. 假设提出 → 3. 样本计算 → 4. 随机分组                 │
│         ↓           ↓           ↓           ↓                          │
│   5. 运行实验 → 6. 数据收集 → 7. 统计分析 → 8. 决策上线                 │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、样本量计算

```python
import numpy as np
from statsmodels.stats.power import NormalIndPower

class SampleSizeCalculator:
    def __init__(self, alpha: float = 0.05, power: float = 0.8):
        self.alpha = alpha
        self.power = power
        self.analysis = NormalIndPower()
    
    def calculate(self, effect_size: float) -> int:
        """计算每组所需样本量"""
        n = self.analysis.solve_power(
            effect_size=effect_size,
            alpha=self.alpha,
            power=self.power,
            ratio=1.0
        )
        return int(np.ceil(n))
    
    def calculate_from_min_detect(self, base_rate: float, min_lift: float) -> int:
        """从最小可检测提升计算"""
        # 效应量 = (新率 - 基线率) / 标准差
        effect_size = min_lift / base_rate
        return self.calculate(effect_size)
    
    def example(self):
        """计算示例"""
        base_cvr = 0.05  # 基准转化率5%
        min_lift = 0.01  # 最小检测提升1%
        
        n = self.calculate_from_min_detect(base_cvr, min_lift)
        total = n * 2  # 两组
        
        return {
            'per_group': n,
            'total': total,
            'duration_days': total / 10000 if total > 0 else 0  # 假设日流量1万
        }
```

## 三、实验分析

```python
class ABTestAnalyzer:
    def __init__(self, variant_a: dict, variant_b: dict):
        self.a = variant_a
        self.b = variant_b
    
    def convert_rate_test(self) -> dict:
        """转化率检验 (Z检验)"""
        n_a, x_a = self.a['samples'], self.a['conversions']
        n_b, x_b = self.b['samples'], self.b['conversions']
        
        p_a = x_a / n_a
        p_b = x_b / n_b
        
        # 合并比例
        p_pool = (x_a + x_b) / (n_a + n_b)
        
        # 标准误差
        se = np.sqrt(p_pool * (1 - p_pool) * (1/n_a + 1/n_b))
        
        # Z统计量
        z = (p_b - p_a) / se if se > 0 else 0
        
        # P值
        from scipy.stats import norm
        p_value = 2 * (1 - norm.cdf(abs(z)))
        
        return {
            'p_a': p_a,
            'p_b': p_b,
            'lift': (p_b - p_a) / p_a * 100,
            'z_score': z,
            'p_value': p_value,
            'significant': p_value < 0.05
        }
    
    def mean_test(self) -> dict:
        """均值检验 (T检验)"""
        from scipy import stats
        t_stat, p_value = stats.ttest_ind(self.b['values'], self.a['values'])
        
        return {
            'mean_a': np.mean(self.a['values']),
            'mean_b': np.mean(self.b['values']),
            't_stat': t_stat,
            'p_value': p_value,
            'significant': p_value < 0.05
        }
    
    def bayesian_analysis(self) -> dict:
        """贝叶斯分析"""
        import scipy.stats as st
        
        # Beta分布参数
        alpha_a = self.a['conversions'] + 1
        beta_a = self.a['samples'] - self.a['conversions'] + 1
        alpha_b = self.b['conversions'] + 1
        beta_b = self.b['samples'] - self.b['conversions'] + 1
        
        # P(B > A)
        n_sim = 100000
        sample_a = st.beta.rvs(alpha_a, beta_a, size=n_sim)
        sample_b = st.beta.rvs(alpha_b, beta_b, size=n_sim)
        
        prob_b_wins = np.mean(sample_b > sample_a)
        
        return {
            'prob_b_wins': prob_b_wins,
            'expected_lift': np.mean(sample_b - sample_a) / np.mean(sample_a) * 100,
            'credible_interval': self.credible_interval(sample_b - sample_a)
        }
```

## 四、多重检验校正

```python
class MultipleTestingCorrection:
    def bonferroni(self, p_values: list, alpha: float = 0.05) -> list:
        """Bonferroni校正"""
        return [min(p * len(p_values), 1.0) for p in p_values]
    
    def benjamini_hochberg(self, p_values: list, alpha: float = 0.05) -> list:
        """BH校正 (控制FDR)"""
        n = len(p_values)
        sorted_indices = np.argsort(p_values)
        adjusted_p = np.zeros(n)
        
        for i, idx in enumerate(sorted_indices):
            adjusted_p[idx] = min(1.0, p_values[idx] * n / (i + 1))
        
        # 确保单调性
        for i in range(n-2, -1, -1):
            adjusted_p[i] = min(adjusted_p[i], adjusted_p[i+1])
        
        return adjusted_p.tolist()
```

## 五、面试高频题

### Q1: 样本量如何计算？

```
n = 2 * (Zα/2 + Zβ)² * σ² / Δ²
其中:
Zα/2 = 1.96 (α=0.05)
Zβ = 0.84 (β=0.2)
σ = 标准差
Δ = 最小可检测效应
```

### Q2: 什么是辛普森悖论？

```
在分组比较中都占优势的团伙，在总评中有时反而是劣势的。
原因: 各组样本量分布不均
```

## 六、自测题

1. 样本量不足会导致什么问题？
2. 何时使用贝叶斯分析？
3. 如何避免P值操纵？

---

## 参考文档

- [A/B Testing Guide](https://github.com/erikwinter/ab-testing-guide)
- [Sample Size Calculation](https://www.samplsize.info/)
