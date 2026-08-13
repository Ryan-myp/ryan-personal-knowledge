# 漏斗分析方法深度实现 - 资深专家深度实现

## 一、漏斗模型

```
┌─────────────────────────────────────────────────────────────────────────┐
│                   典型转化漏斗                                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   曝光 (Impression)  ── 100% ──→ 点击 (Click) ── 20% ──→ 注册 (Sign)  │
│                              │                    │                   │
│                              └── 80%流失 ──→       └── 70%流失 ──→    │
│                                                         │             │
│                                              激活 (Activate)         │
│                                                         │             │
│                                                         └── 80%流失 ──→│
│                                                                     │
│                                                              付费     │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、漏斗实现

```python
import pandas as pd
import numpy as np

class FunnelAnalyzer:
    def __init__(self, events: pd.DataFrame):
        self.events = events
        self.steps = []
    
    def add_step(self, name: str, filter_expr: str):
        """添加漏斗步骤"""
        self.steps.append({'name': name, 'filter': filter_expr})
    
    def calculate_funnel(self, users: pd.Series) -> pd.DataFrame:
        """计算漏斗"""
        results = []
        prev_count = len(users)
        
        for step in self.steps:
            # 应用过滤条件
            filtered = self.apply_filter(users, step['filter'])
            count = len(filtered)
            conversion = count / prev_count * 100 if prev_count > 0 else 0
            dropoff = 100 - conversion
            
            results.append({
                'step': step['name'],
                'users': count,
                'conversion_rate': conversion,
                'dropoff_rate': dropoff,
                'cumulative_conversion': count / len(users) * 100
            })
            
            prev_count = count
        
        return pd.DataFrame(results)
    
    def apply_filter(self, users: pd.Series, expr: str) -> pd.Series:
        """应用过滤条件"""
        # 简化实现，实际应根据事件数据过滤
        return users.head(int(len(users) * 0.7))  # 模拟
    
    def find_bottleneck(self, funnel_df: pd.DataFrame) -> str:
        """找到瓶颈"""
        max_dropoff = funnel_df['dropoff_rate'].max()
        bottleneck = funnel_df[funnel_df['dropoff_rate'] == max_dropoff].iloc[0]
        return bottleneck['step']
    
    def cohort_funnel(self, signups: pd.Series, cohort_col: str) -> dict:
        """队列漏斗分析"""
        cohorts = signups.groupby(cohort_col)
        results = {}
        
        for cohort, users in cohorts:
            funnel = self.calculate_funnel(users)
            results[cohort] = {
                'total_users': len(users),
                'funnel': funnel,
                'overall_conversion': funnel.iloc[-1]['cumulative_conversion']
            }
        
        return results
```

## 三、可视化

```python
class FunnelVisualization:
    def __init__(self, funnel_data: pd.DataFrame):
        self.data = funnel_data
    
    def render_ascii(self) -> str:
        """ASCII可视化"""
        max_width = 50
        max_users = self.data['users'].max()
        
        output = "=== 漏斗分析 ===\n\n"
        for _, row in self.data.iterrows():
            width = int(row['users'] / max_users * max_width)
            bar = "█" * width
            output += f"{row['step']:12s} | {bar} {row['users']:6d} ({row['conversion_rate']:5.1f}%)\n"
        
        return output
    
    def generate_chart_config(self) -> dict:
        """生成图表配置"""
        return {
            'type': 'funnel',
            'data': self.data[['step', 'users', 'conversion_rate']].to_dict('records'),
            'options': {
                'title': '转化漏斗分析',
                'xAxis': '用户数',
                'yAxis': '步骤',
                'show_values': True
            }
        }
```

## 四、面试高频题

### Q1: 如何定义漏斗步骤？

```
从用户首次接触到最终转化的完整路径
每个步骤应该是可量化的事件
```

### Q2: 如何找到瓶颈？

```
1. 计算每步转化率
2. 找到转化率最低的步骤
3. 针对性优化
```

## 五、自测题

1. 漏斗分析方法？
2. 瓶颈识别方法？
3. 队列分析应用？

---

## 参考文档

- [Funnel Analysis](https://amplitude.com/help/guides/funnel-analysis)
- [Conversion Funnel](https://hubspot.com/marketing/funnels)
