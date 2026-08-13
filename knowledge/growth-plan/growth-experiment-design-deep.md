# 增长实验设计深度实现 - 资深专家深度实现

## 一、实验设计框架

```
┌─────────────────────────────────────────────────────────────────────────┐
│                   增长实验设计流程                                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   1. 明确目标 → 2. 提出假设 → 3. 设计实验 → 4. 确定样本量               │
│         ↓           ↓           ↓           ↓                          │
│   5. 运行实验 → 6. 收集数据 → 7. 分析结果 → 8. 决策上线                 │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、实验设计实现

```python
import numpy as np
from scipy import stats

class ExperimentDesigner:
    def __init__(self):
        self.alpha = 0.05  # 显著性水平
        self.power = 0.8   # 统计功效
    
    def formulate_hypothesis(self, baseline: float, expected_lift: float) -> dict:
        """提出假设"""
        return {
            'null_hypothesis': f'实验组与对照组无差异',
            'alternative_hypothesis': f'实验组转化率提升{expected_lift*100:.1f}%',
            'baseline_conversion': baseline,
            'expected_conversion': baseline * (1 + expected_lift)
        }
    
    def calculate_sample_size(self, baseline: float, min_detect: float) -> int:
        """计算样本量"""
        from statsmodels.stats.power import NormalIndPower
        
        analysis = NormalIndPower()
        
        # 计算效应量
        p1 = baseline
        p2 = baseline * (1 + min_detect)
        effect_size = stats.proportion_effectsize(p1, p2)
        
        # 计算样本量
        n = analysis.solve_power(
            effect_size=effect_size,
            alpha=self.alpha,
            power=self.power,
            ratio=1.0
        )
        
        return int(np.ceil(n))
    
    def design_experiment(self, 
                         baseline_rate: float,
                         min_detect_lift: float,
                         daily_traffic: int) -> dict:
        """设计完整实验"""
        sample_size = self.calculate_sample_size(baseline_rate, min_detect_lift)
        duration_days = (sample_size * 2) / daily_traffic
        
        return {
            'sample_size_per_group': sample_size,
            'total_sample_size': sample_size * 2,
            'duration_days': int(np.ceil(duration_days)),
            'daily_traffic_needed': daily_traffic,
            'confidence_level': (1 - self.alpha) * 100,
            'power': self.power * 100
        }
```

## 三、实验分析

```python
class ExperimentAnalyzer:
    def __init__(self, variant_a: dict, variant_b: dict):
        self.a = variant_a
        self.b = variant_b
    
    def run_z_test(self) -> dict:
        """Z检验"""
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
        p_value = 2 * (1 - stats.norm.cdf(abs(z)))
        
        # 置信区间
        ci = self.calculate_ci(p_a, p_b, n_a, n_b)
        
        return {
            'conversion_a': p_a,
            'conversion_b': p_b,
            'lift': (p_b - p_a) / p_a * 100,
            'z_score': z,
            'p_value': p_value,
            'significant': p_value < 0.05,
            'confidence_interval': ci,
            'recommendation': 'launch' if p_value < 0.05 and p_b > p_a else 'no_change'
        }
    
    def calculate_ci(self, p_a: float, p_b: float, n_a: int, n_b: int) -> tuple:
        """计算置信区间"""
        se_diff = np.sqrt(p_a*(1-p_a)/n_a + p_b*(1-p_b)/n_b)
        margin = 1.96 * se_diff
        return (p_b - p_a - margin, p_b - p_a + margin)
    
    def bayesian_analysis(self) -> dict:
        """贝叶斯分析"""
        import scipy.stats as st
        
        # Beta分布参数
        alpha_a = self.a['conversions'] + 1
        beta_a = self.a['samples'] - self.a['conversions'] + 1
        alpha_b = self.b['conversions'] + 1
        beta_b = self.b['samples'] - self.b['conversions'] + 1
        
        # 模拟
        n_sim = 100000
        sample_a = st.beta.rvs(alpha_a, beta_a, size=n_sim)
        sample_b = st.beta.rvs(alpha_b, beta_b, size=n_sim)
        
        # 计算
        prob_b_wins = np.mean(sample_b > sample_a)
        expected_lift = np.mean((sample_b - sample_a) / sample_a) * 100
        
        # 95%可信区间
        ci_lower, ci_upper = np.percentile(sample_b - sample_a, [2.5, 97.5])
        
        return {
            'prob_b_wins': prob_b_wins,
            'expected_lift': expected_lift,
            'credible_interval': (ci_lower * 100, ci_upper * 100),
            'recommendation': 'launch' if prob_b_wins > 0.95 else 'continue_testing'
        }
```

## 四、实验管理平台

```python
class ExperimentPlatform:
    def __init__(self):
        self.experiments = {}
        self.allocation = {}
    
    def create_experiment(self, config: dict) -> str:
        """创建实验"""
        import hashlib
        experiment_id = hashlib.md5(str(config).encode()).hexdigest()[:12]
        
        self.experiments[experiment_id] = {
            'id': experiment_id,
            'name': config['name'],
            'variants': config['variants'],
            'status': 'active',
            'created_at': datetime.now()
        }
        
        return experiment_id
    
    def allocate_user(self, user_id: str, experiment_id: str) -> str:
        """分配用户到实验组"""
        experiment = self.experiments.get(experiment_id)
        if not experiment:
            return 'invalid_experiment'
        
        variants = experiment['variants']
        hash_value = int(hashlib.md5(f"{experiment_id}:{user_id}".encode()).hexdigest(), 16)
        variant_index = hash_value % len(variants)
        
        return variants[variant_index]
    
    def record_event(self, user_id: str, experiment_id: str, event: str):
        """记录实验事件"""
        key = f"{experiment_id}:{user_id}"
        if key not in self.allocation:
            self.allocation[key] = self.allocate_user(user_id, experiment_id)
        
        # 记录事件
        pass
    
    def get_experiment_results(self, experiment_id: str) -> dict:
        """获取实验结果"""
        # 聚合数据并分析
        pass
```

## 五、面试高频题

### Q1: 样本量如何计算？

```
n = 2 * (Zα/2 + Zβ)² * σ² / Δ²
或用量化工具如 statsmodels
```

### Q2: P值如何解释？

```
P值 < 0.05 表示结果统计显著
不是"假阳性概率"
```

## 六、自测题

1. 解释实验设计流程
2. 如何计算样本量？
3. P值和置信区间的关系？

---

## 参考文档

- [Experiment Design](https://github.com/erikwinter/ab-testing-guide)
- [A/B Testing Best Practices](https://blog.samueljolley.com/ab-testing-best-practices/)
