# 增长黑客案例库 - 资深专家深度实现

## 一、经典案例

```
┌─────────────────────────────────────────────────────────────────────────┐
│                   增长黑客经典案例                                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   案例              │ 策略                    │ 效果                    │
│   ─────────────────┼───────────────────────┼─────────────────────────│
│   Dropbox           │ 推荐奖励                │ 3900%增长               │
│   (邀请得空间)      │                       │                         │
│   ─────────────────┼───────────────────────┼─────────────────────────│
│   Hotmail           │ 签名-footer            │ 12个月内120万用户       │
│   (邮件签名)        │                       │                         │
│   ─────────────────┼───────────────────────┼─────────────────────────│
│   PayPal            │ 注册奖励               │ 首日12.5万注册          │
│   (送$10)          │                       │                         │
│   ─────────────────┼───────────────────────┼─────────────────────────│
│   Instagram         │ 跨平台同步             │ 24小时1万用户           │
│   (从Burbn转型)     │                       │                         │
│   ─────────────────┼───────────────────────┼─────────────────────────│
│   Airbnb            │  Craigslist抓取        │ 从0到10万房源           │
│   (自动发布)        │                       │                         │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、案例实现

```python
class GrowthCaseStudy:
    def __init__(self, name: str, strategy: str, result: dict):
        self.name = name
        self.strategy = strategy
        self.result = result
    
    def analyze_success_factors(self) -> list:
        """分析成功因素"""
        factors = []
        
        # 1. 低获客成本
        if self.result.get('cac', float('inf')) < 10:
            factors.append('低获客成本')
        
        # 2. 高病毒系数
        if self.result.get('k_factor', 0) > 1:
            factors.append('病毒式传播')
        
        # 3. 产品内增长
        if self.result.get('product_led', False):
            factors.append('产品驱动增长')
        
        # 4. 数据驱动
        if self.result.get('data_driven', False):
            factors.append('数据驱动决策')
        
        return factors
    
    def extract_lessons(self) -> list:
        """提取经验教训"""
        return [
            '找到最小可行实验',
            '快速迭代验证',
            '关注核心指标',
            '利用现有用户网络'
        ]
    
    def create_cheat_sheet(self) -> dict:
        """创建备忘单"""
        return {
            'name': self.name,
            'strategy': self.strategy,
            'key_metrics': {
                'k_factor': self.result.get('k_factor'),
                'cac': self.result.get('cac'),
                'ltv': self.result.get('ltv'),
                'conversion': self.result.get('conversion_rate')
            },
            'tools_used': self.result.get('tools', []),
            'timeline': self.result.get('timeline', {})
        }
```

## 三、实验方法

```python
class GrowthExperiment:
    def __init__(self):
        self.experiments = []
    
    def design_experiment(self, hypothesis: str, metric: str, variant: dict) -> dict:
        """设计实验"""
        experiment = {
            'hypothesis': hypothesis,
            'primary_metric': metric,
            'variants': variant,
            'status': 'draft',
            'sample_size': self.calculate_sample_size(metric),
            'duration_days': 14
        }
        self.experiments.append(experiment)
        return experiment
    
    def calculate_sample_size(self, metric: str) -> int:
        """计算样本量"""
        # 基于效应量的样本量计算
        base_rate = 0.05  # 基准转化率
        min_detect = 0.01  # 最小可检测提升
        
        from statsmodels.stats.power import NormalIndPower
        analysis = NormalIndPower()
        effect_size = min_detect / base_rate
        
        n = analysis.solve_power(effect_size, alpha=0.05, power=0.8)
        return int(n * 2)  # 两组
    
    def run_experiment(self, experiment_id: str) -> dict:
        """运行实验"""
        experiment = next((e for e in self.experiments if e['id'] == experiment_id), None)
        
        if not experiment:
            return {'error': '实验不存在'}
        
        # 模拟实验结果
        return {
            'experiment_id': experiment_id,
            'variant_a': {
                'users': 1000,
                'conversions': 50,
                'rate': 0.05
            },
            'variant_b': {
                'users': 1000,
                'conversions': 65,
                'rate': 0.065
            },
            'p_value': 0.02,
            'significant': True,
            'recommendation': 'launch_variant_b'
        }
```

## 四、面试高频题

### Q1: 如何复制Dropbox的增长策略？

```
1. 设计双向奖励机制
2. 简化分享流程
3. 在关键节点触发邀请
4. 追踪转化漏斗
```

### Q2: 什么是产品驱动增长？

```
通过产品本身的功能带来增长
不需要大量营销投入
```

## 五、自测题

1. 解释三个经典案例
2. 如何设计增长实验？
3. 产品驱动增长的核心？

---

## 参考文档

- [Growth Hacking Cases](https://growthhackers.com/cases)
- [Dropbox Growth](https://www.dropbox.com/company/history)
