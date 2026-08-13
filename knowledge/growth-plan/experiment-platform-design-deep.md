# 增长实验平台设计深度实现 - 资深专家深度实现

## 一、平台架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                   增长实验平台架构                                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   实验管理       │ 流量分发       │ 数据采集       │ 分析决策            │
│   ───────────────┼────────────────┼────────────────┼─────────────────│
│   • 创建实验     │ • 分流算法     │ • 埋点系统     │ • A/B测试         │
│   • 版本管理     │ • 一致性保证   │ • 数据同步     │ • 统计检验        │
│   • 人群 targeting│ • 灰度发布    │ • 实时计算     │ • 效果评估        │
│   • 停止/上线    │ • 快速回滚     │ • 数据质量监控 │ • 决策建议        │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、实验管理实现

```python
import hashlib
import random
from datetime import datetime

class ExperimentManager:
    def __init__(self):
        self.experiments = {}
        self.allocations = {}
    
    def create_experiment(self, config: dict) -> str:
        """创建实验"""
        exp_id = hashlib.md5(str(config).encode()).hexdigest()[:12]
        
        self.experiments[exp_id] = {
            'id': exp_id,
            'name': config['name'],
            'variants': config['variants'],
            'allocation': config.get('allocation', {}),
            'status': 'draft',
            'created_at': datetime.now(),
            'metrics': config.get('metrics', [])
        }
        
        return exp_id
    
    def allocate_user(self, user_id: str, experiment_id: str) -> str:
        """分配用户到实验组"""
        experiment = self.experiments.get(experiment_id)
        if not experiment:
            return 'invalid_experiment'
        
        variants = experiment['variants']
        weights = experiment['allocation']
        
        # 确保同一用户始终分配到同一组
        hash_value = int(hashlib.md5(f"{experiment_id}:{user_id}".encode()).hexdigest(), 16)
        
        if weights:
            # 加权分配
            total_weight = sum(weights.values())
            rand_val = hash_value % total_weight
            cumulative = 0
            for variant, weight in weights.items():
                cumulative += weight
                if rand_val < cumulative:
                    return variant
            return list(variants.keys())[-1]
        else:
            # 均匀分配
            variant_index = hash_value % len(variants)
            return list(variants.keys())[variant_index]
    
    def record_conversion(self, user_id: str, experiment_id: str, 
                         variant: str, metric: str, value: float):
        """记录转化"""
        key = f"{experiment_id}:{user_id}"
        if key not in self.allocations:
            self.allocations[key] = self.allocate_user(user_id, experiment_id)
        
        # 记录数据
        pass
```

## 三、统计分析实现

```python
class ExperimentAnalyzer:
    def __init__(self):
        self.results = {}
    
    def analyze_experiment(self, experiment_id: str) -> dict:
        """分析实验结果"""
        data = self.get_experiment_data(experiment_id)
        
        # 计算各variant的指标
        variant_stats = {}
        for variant, conversions in data.items():
            total = len(conversions)
            converted = sum(1 for c in conversions if c['converted'])
            rate = converted / total if total > 0 else 0
            variant_stats[variant] = {
                'sample_size': total,
                'conversion_rate': rate,
                'confidence_interval': self.calculate_ci(rate, total)
            }
        
        # 显著性检验
        comparison = self.significance_test(variant_stats)
        
        return {
            'experiment_id': experiment_id,
            'variant_stats': variant_stats,
            'significant': comparison['significant'],
            'recommendation': comparison['recommendation']
        }
    
    def calculate_ci(self, rate: float, n: int, confidence: float = 0.95) -> tuple:
        """计算置信区间"""
        import math
        z = 1.96 if confidence == 0.95 else 2.576
        se = math.sqrt(rate * (1 - rate) / n) if n > 0 else 0
        return (rate - z * se, rate + z * se)
    
    def significance_test(self, stats: dict) -> dict:
        """显著性检验"""
        variants = list(stats.keys())
        if len(variants) < 2:
            return {'significant': False, 'recommendation': 'need_more_variants'}
        
        # 比较两个variant
        v1, v2 = variants[0], variants[1]
        s1, s2 = stats[v1], stats[v2]
        
        # 简单差异检验
        diff = s2['conversion_rate'] - s1['conversion_rate']
        se_diff = math.sqrt(s1['conversion_rate']*(1-s1['conversion_rate'])/s1['sample_size'] +
                           s2['conversion_rate']*(1-s2['conversion_rate'])/s2['sample_size'])
        z = abs(diff) / se_diff if se_diff > 0 else 0
        
        significant = z > 1.96
        
        return {
            'significant': significant,
            'z_score': z,
            'recommendation': 'launch_v2' if significant and diff > 0 else 'no_change'
        }
```

## 四、面试高频题

### Q1: 实验平台核心组件？

```
1. 实验管理 (创建/配置/监控)
2. 流量分发 (分流/一致性)
3. 数据采集 (埋点/同步)
4. 分析决策 (统计/可视化)
```

### Q2: 如何避免实验污染？

```
1. 同一用户一致性
2. 交叉实验隔离
3. 冷启动保护
```

## 五、自测题

1. 实验分流算法？
2. 显著性检验方法？
3. 如何避免污染？

---

## 参考文档

- [Experiment Platform](https://growthhackers.com/growth-hacking/experimentation)
- [A/B Testing Guide](https://github.com/erikwinter/ab-testing-guide)
