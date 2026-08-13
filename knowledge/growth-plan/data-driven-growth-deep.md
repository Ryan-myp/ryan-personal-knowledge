# 数据驱动增长深度实现 - 资深专家深度实现

## 一、数据驱动框架

```
┌─────────────────────────────────────────────────────────────────────────┐
│                   数据驱动增长闭环                                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   数据收集 → 数据分析 → 洞察发现 → 策略制定 → 实验验证 → 效果评估       │
│      ↑                                                        ↓          │
│      └──────────────────── 持续优化 ────────────────────────┘          │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、数据管道

```python
import pandas as pd
from datetime import datetime
import json

class DataPipeline:
    def __init__(self, source: str = 'clickhouse'):
        self.source = source
        self.data = None
    
    def collect_events(self, start_date: str, end_date: str) -> pd.DataFrame:
        """收集用户事件数据"""
        # 简化版实现
        return pd.DataFrame({
            'user_id': ['u1', 'u2', 'u3'],
            'event_type': ['signup', 'purchase', 'retention'],
            'timestamp': [datetime.now(), datetime.now(), datetime.now()],
            'properties': [{}, {}, {}]
        })
    
    def transform(self, raw_data: pd.DataFrame) -> pd.DataFrame:
        """数据清洗和转换"""
        # 处理缺失值
        raw_data = raw_data.dropna(subset=['user_id', 'event_type'])
        
        # 特征工程
        raw_data['hour_of_day'] = raw_data['timestamp'].dt.hour
        raw_data['day_of_week'] = raw_data['timestamp'].dt.dayofweek
        raw_data['is_weekend'] = raw_data['day_of_week'].isin([5, 6])
        
        return raw_data
    
    def load(self, data: pd.DataFrame, destination: str):
        """数据存储"""
        # 简化版
        pass
    
    def get_metrics(self, metric_name: str) -> dict:
        """获取指标数据"""
        metrics = {
            'daU': self.calculate_dau(),
            'maU': self.calculate_mau(),
            'retention': self.calculate_retention(),
            'lTV': self.calculate_ltv()
        }
        return metrics.get(metric_name, {})
    
    def calculate_dau(self) -> int:
        """计算DAU"""
        today = datetime.now().date()
        return len(self.data[self.data['timestamp'].dt.date == today]['user_id'].unique())
    
    def calculate_mau(self) -> int:
        """计算MAU"""
        thirty_days_ago = datetime.now() - pd.Timedelta(days=30)
        return len(self.data[self.data['timestamp'] > thirty_days_ago]['user_id'].unique())
```

## 三、分析看板

```python
class AnalyticsDashboard:
    def __init__(self):
        self.metrics = {}
    
    def update_metrics(self, metrics: dict):
        """更新指标"""
        self.metrics.update(metrics)
    
    def get_kpis(self) -> dict:
        """获取关键指标"""
        return {
            'DAU': self.metrics.get('dau', 0),
            'MAU': self.metrics.get('mau', 0),
            'DAU_MAU_ratio': self.metrics.get('dau', 0) / max(self.metrics.get('mau', 1), 1),
            'Retention_1d': self.metrics.get('retention_1d', 0),
            'Retention_7d': self.metrics.get('retention_7d', 0),
            'LTV': self.metrics.get('ltv', 0),
            'CAC': self.metrics.get('cac', 0),
            'LTV_CAC_ratio': self.metrics.get('ltv', 0) / max(self.metrics.get('cac', 1), 1)
        }
    
    def calculate_health_score(self) -> float:
        """计算产品健康度"""
        kpis = self.get_kpis()
        
        scores = {
            'engagement': min(kpis['DAU_MAU_ratio'] / 0.2, 1.0) * 100,  # 健康值>20%
            'retention': kpis['Retention_7d'] * 100,
            'monetization': min(kpis['LTV_CAC_ratio'] / 3.0, 1.0) * 100,  # 健康值>3
            'growth': min(kpis['DAU'] / 10000, 1.0) * 100  # 假设目标1万DAU
        }
        
        weighted_score = (
            scores['engagement'] * 0.25 +
            scores['retention'] * 0.3 +
            scores['monetization'] * 0.25 +
            scores['growth'] * 0.2
        )
        
        return weighted_score
    
    def generate_report(self) -> dict:
        """生成分析报告"""
        return {
            'timestamp': datetime.now().isoformat(),
            'kpis': self.get_kpis(),
            'health_score': self.calculate_health_score(),
            'trends': self.calculate_trends(),
            'recommendations': self.generate_recommendations()
        }
    
    def calculate_trends(self, period: int = 7) -> dict:
        """计算趋势"""
        return {
            'dau_trend': 'up' if self.metrics.get('dau', 0) > 0 else 'stable',
            'retention_trend': 'up' if self.metrics.get('retention_7d', 0) > 0.3 else 'down'
        }
    
    def generate_recommendations(self) -> list:
        """生成建议"""
        recommendations = []
        kpis = self.get_kpis()
        
        if kpis['DAU_MAU_ratio'] < 0.2:
            recommendations.append('提升用户活跃度，建议增加推送频次')
        if kpis['LTV_CAC_ratio'] < 3:
            recommendations.append('优化获客成本，建议调整投放策略')
        if kpis['Retention_7d'] < 0.3:
            recommendations.append('改善新用户留存，建议优化Onboarding流程')
        
        return recommendations
```

## 四、数据可视化

```python
class DataVisualization:
    def __init__(self, data: pd.DataFrame):
        self.data = data
    
    def create_chart(self, chart_type: str, config: dict) -> dict:
        """创建图表"""
        charts = {
            'line': self.create_line_chart(config),
            'bar': self.create_bar_chart(config),
            'funnel': self.create_funnel_chart(config),
            'cohort': self.create_cohort_chart(config)
        }
        return charts.get(chart_type, {})
    
    def create_line_chart(self, config: dict) -> dict:
        """折线图"""
        return {
            'type': 'line',
            'title': config.get('title', '趋势图'),
            'data': config.get('data', []),
            'x_axis': config.get('x_axis', '日期'),
            'y_axis': config.get('y_axis', '数值')
        }
    
    def create_funnel_chart(self, config: dict) -> dict:
        """漏斗图"""
        steps = config.get('steps', [])
        return {
            'type': 'funnel',
            'title': '转化漏斗',
            'steps': [
                {'name': s['name'], 'value': s['value'], 'rate': s.get('rate', 0)}
                for s in steps
            ]
        }
    
    def create_cohort_chart(self, config: dict) -> dict:
        """Cohort图表"""
        cohort_data = config.get('cohort_data', {})
        return {
            'type': 'cohort',
            'title': '留存分析',
            'data': cohort_data
        }
```

## 五、面试高频题

### Q1: 数据驱动增长的核心是什么？

```
1. 数据收集全面性
2. 分析准确性
3. 决策及时性
4. 验证闭环
```

### Q2: 如何构建数据看板？

```
1. 明确指标体系
2. 设计数据管道
3. 可视化呈现
4. 持续迭代
```

## 六、自测题

1. 解释数据驱动闭环
2. 如何评估指标健康度？
3. 看板设计原则？

---

## 参考文档

- [Data-Driven Growth](https://blog.hubspot.com/marketing/data-driven-growth)
- [Analytics Dashboard](https://www.tableau.com/learn/articles/data-dashboard)
