# 产品指标体系深度实现 - 资深专家深度实现

## 一、指标体系框架

```
┌─────────────────────────────────────────────────────────────────────────┐
│                   产品指标体系 (HEART)                                     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   H (Happiness)     → 用户满意度: NPS, CSAT, App Store评分               │
│   E (Engagement)    → 用户参与: DAU/MAU, 使用时长, 功能渗透率            │
│   A (Adoption)      → 用户获取: 注册转化率, 激活率, 首单转化率           │
│   R (Retention)     → 用户留存: 次日留存, 7日留存, 30日留存              │
│   T (Task Success)  → 任务完成: 成功率, 完成时间, 错误率                 │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、指标实现

```python
class ProductMetrics:
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
            'DAU_MAU': 0.2,
            'retention_7d': 0.25,
            'conversion': 0.2,
            'revenue_growth': 0.15,
            'nps': 0.2
        }
        
        score = 0
        for metric, weight in weights.items():
            value = metrics.get(metric, 0)
            normalized = min(value / 100, 1.0)
            score += normalized * weight
        
        return score * 100
    
    def generate_dashboard(self) -> dict:
        """生成仪表盘"""
        return {
            'title': f'{self.product_type}产品仪表盘',
            'metrics': self.define_metrics(),
            'health_score': self.calculate_health_score({})
        }
```

## 三、面试高频题

### Q1: 什么是北极星指标？

```
唯一关键指标，指引产品发展方向
应与业务目标强相关
```

### Q2: 如何设计指标体系？

```
1. 明确业务目标
2. 选择北极星指标
3. 拆解过程指标
4. 建立监控机制
```

## 四、自测题

1. HEART模型是什么？
2. 如何计算健康度？
3. 北极星指标选择原则？

---

## 参考文档

- [HEART Framework](https://developers.google.com/analytics/devguides/collection/analyticsjs/user-metrics)
- [Product Metrics](https://www.linkedin.com/pulse/product-metrics-what-are-key-performance-indicators-kpis/)
