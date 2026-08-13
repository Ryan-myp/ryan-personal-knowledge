# 增长指标体系深度实现 - 资深专家深度实现

## 一、指标体系框架

```
┌─────────────────────────────────────────────────────────────────────────┐
│                   增长指标体系 (OSM模型)                                   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   Objective (目标) → Measure (度量) → Signal (信号)                     │
│                                                                         │
│   ──────────────────────────────────────────────────────────────────   │
│                                                                         │
│   北极星指标: 唯一关键指标，指引产品方向                                   │
│                                                                         │
│   示例:                                                                   │
│   • 抖音: 人均使用时长                                                   │
│   • 微信: 日发朋友圈数                                                   │
│   • 淘宝: GMV                                                           │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、核心指标实现

```python
class GrowthMetrics:
    def __init__(self, product_type: str):
        self.product_type = product_type
        self.metrics = {}
    
    def define_metrics(self) -> dict:
        """定义指标"""
        metrics_by_type = {
            'ecommerce': {
                '北极星指标': 'GMV',
                '核心指标': ['DAU', '转化率', '客单价', '复购率'],
                '辅助指标': ['加购率', '收藏数', '分享率']
            },
            'social': {
                '北极星指标': '人均使用时长',
                '核心指标': ['DAU', '发帖数', '互动率', '留存率'],
                '辅助指标': ['好友数', '关注数', '消息数']
            }
        }
        return metrics_by_type.get(self.product_type, metrics_by_type['social'])
    
    def calculate_health_score(self, metrics: dict) -> float:
        """计算健康度"""
        weights = {
            'DAU': 0.3,
            '留存率': 0.25,
            '增长率': 0.2,
            '变现': 0.15,
            '满意度': 0.1
        }
        
        score = 0
        for metric, weight in weights.items():
            value = metrics.get(metric, 0)
            normalized = min(value / 100, 1.0)
            score += normalized * weight
        
        return score * 100
```

## 三、漏斗分析

```python
class FunnelMetrics:
    def __init__(self, steps: list):
        self.steps = steps
        self.data = {}
    
    def add_data(self, step: str, users: int):
        """添加数据"""
        self.data[step] = users
    
    def calculate_conversion(self) -> dict:
        """计算转化率"""
        result = {}
        prev_users = None
        
        for step in self.steps:
            users = self.data.get(step, 0)
            if prev_users:
                conversion = users / prev_users * 100
                result[step] = {
                    'users': users,
                    'conversion': conversion,
                    'dropoff': 100 - conversion
                }
            else:
                result[step] = {'users': users, 'conversion': 100}
            prev_users = users
        
        return result
    
    def find_bottleneck(self) -> str:
        """找到瓶颈"""
        conversions = self.calculate_conversion()
        bottleneck = max(conversions.items(), key=lambda x: x[1]['dropoff'])
        return bottleneck[0]
```

## 四、面试高频题

### Q1: 如何确定北极星指标？

```
1. 与业务目标对齐
2. 可量化可追踪
3. 能指导行动
4. 团队共识
```

### Q2: 漏斗分析的应用？

```
1. 定义转化路径
2. 计算各环节转化率
3. 找到瓶颈
4. 制定优化策略
```

## 五、自测题

1. 解释OSM模型
2. 如何计算健康度？
3. 瓶颈分析方法？

---

## 参考文档

- [OSM Model](https://www.pivotable.com/blog/osm-model)
- [Funnel Analysis](https://amplitude.com/help/guides/funnel-analysis)
