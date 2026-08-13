# 产品指标体系设计 - 资深专家深度实现

## 一、指标体系框架

```
┌─────────────────────────────────────────────────────────────────────────┐
│                   产品指标体系 (OSM模型)                                   │
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
class MetricSystem:
    def __init__(self, product_type: str):
        self.product_type = product_type
        self.metrics = {}
    
    def define_metrics(self) -> dict:
        """定义产品指标"""
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
            },
            'content': {
                '北极星指标': '内容消费时长',
                '核心指标': ['DAU', '完播率', '评论数', '分享率'],
                '辅助指标': ['订阅数', '点赞数', '收藏数']
            }
        }
        return metrics_by_type.get(self.product_type, metrics_by_type['social'])
    
    def calculate_health_score(self, metrics: dict) -> float:
        """计算产品健康度"""
        weights = {
            'DAU': 0.3,
            '留存率': 0.25,
            '增长率': 0.2,
            ' monetization': 0.15,
            '满意度': 0.1
        }
        
        score = 0
        for metric, weight in weights.items():
            value = metrics.get(metric, 0)
            normalized = min(value / 100, 1.0)  # 假设最大值100
            score += normalized * weight
        
        return score * 100
```

## 三、漏斗分析

```python
class FunnelAnalysis:
    def __init__(self, steps: list):
        self.steps = steps
        self.data = {}
    
    def add_data(self, step: str, users: int):
        """添加漏斗数据"""
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
        """找到瓶颈环节"""
        conversions = self.calculate_conversion()
        bottleneck = max(conversions.items(), key=lambda x: x[1]['dropoff'])
        return bottleneck[0]
    
    def visualize(self) -> str:
        """生成可视化ASCII图"""
        lines = []
        max_width = 50
        
        for step in self.steps:
            data = self.data.get(step, 0)
            width = int(data / max(self.data.values()) * max_width)
            bar = '█' * width
            lines.append(f"{step:15s} |{bar} {data}")
        
        return '\n'.join(lines)
```

## 四、指标异常检测

```python
import numpy as np
from scipy import stats

class AnomalyDetection:
    def __init__(self, threshold: float = 2.0):
        self.threshold = threshold
    
    def z_score_test(self, values: list, current: float) -> dict:
        """Z-Score异常检测"""
        mean = np.mean(values)
        std = np.std(values)
        z_score = (current - mean) / std if std > 0 else 0
        
        return {
            'is_anomaly': abs(z_score) > self.threshold,
            'z_score': z_score,
            'mean': mean,
            'std': std
        }
    
    def moving_average(self, values: list, window: int = 7) -> list:
        """移动平均"""
        return [np.mean(values[max(0, i-window+1):i+1]) for i in range(len(values))]
    
    def detect_seasonality(self, values: list, period: int = 7) -> dict:
        """检测季节性"""
        # 简化版: 使用傅里叶变换
        fft = np.fft.fft(values)
        power = np.abs(fft) ** 2
        
        dominant_frequency = np.argmax(power[1:]) + 1
        return {
            'dominant_period': period,
            'seasonality_strength': power[dominant_frequency] / power[0]
        }
```

## 五、面试高频题

### Q1: 如何确定北极星指标？

```
1. 与业务目标对齐
2. 可量化可追踪
3. 能指导行动
4. 团队共识
```

### Q2: 漏斗分析如何应用？

```
1. 定义关键转化路径
2. 收集各步骤数据
3. 计算转化率
4. 找到瓶颈
5. 优化迭代
```

## 六、自测题

1. 解释OSM模型
2. 如何检测指标异常？
3. 漏斗分析的价值？

---

## 参考文档

- [OSM Model](https://www.pivotable.com/blog/osm-model)
- [Funnel Analysis](https://amplitude.com/help/guides/funnel-analysis)
