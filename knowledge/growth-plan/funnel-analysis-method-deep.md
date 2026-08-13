# 漏斗分析方法深度实现 - 资深专家深度实现

## 一、漏斗模型

```
┌─────────────────────────────────────────────────────────────────────────┐
│                   典型转化漏斗                                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   曝光       →      点击       →      注册      →      激活      →    付费   │
│   Impression    Click         Sign Up      Activation      Purchase    │
│   ───────────  ───────────   ──────────   ───────────   ──────────   │
│   100%          15%            5%           3%             1%           │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、漏斗分析实现

```python
import pandas as pd
import numpy as np

class FunnelAnalyzer:
    def __init__(self, events: pd.DataFrame):
        self.events = events
        self.steps = ['impression', 'click', 'signup', 'activation', 'purchase']
    
    def build_funnel(self) -> pd.DataFrame:
        """构建漏斗"""
        funnel_data = []
        
        for step in self.steps:
            count = len(self.events[self.events['event_type'] == step])
            funnel_data.append({
                'step': step,
                'users': count,
                'conversion_rate': self.calculate_conversion(step),
                'dropoff_rate': 1 - self.calculate_conversion(step)
            })
        
        return pd.DataFrame(funnel_data)
    
    def calculate_conversion(self, step: str) -> float:
        """计算转化率"""
        step_idx = self.steps.index(step)
        if step_idx == 0:
            return 1.0
        
        prev_step = self.steps[step_idx - 1]
        prev_count = len(self.events[self.events['event_type'] == prev_step])
        curr_count = len(self.events[self.events['event_type'] == step])
        
        return curr_count / prev_count if prev_count > 0 else 0
    
    def analyze_by_channel(self, channel_col: str) -> dict:
        """按渠道分析漏斗"""
        channels = self.events[channel_col].unique()
        results = {}
        
        for channel in channels:
            channel_events = self.events[self.events[channel_col] == channel]
            analyzer = FunnelAnalyzer(channel_events)
            funnel = analyzer.build_funnel()
            results[channel] = funnel.to_dict('records')
        
        return results
    
    def find_bottleneck(self) -> dict:
        """找到瓶颈环节"""
        funnel = self.build_funnel()
        bottleneck = funnel.loc[funnel['conversion_rate'].idxmin()]
        
        return {
            'step': bottleneck['step'],
            'conversion_rate': bottleneck['conversion_rate'],
            'dropoff_rate': bottleneck['dropoff_rate'],
            'users_lost': int(bottleneck['users'] * bottleneck['dropoff_rate'])
        }
```

## 三、路径分析

```python
class PathAnalyzer:
    def __init__(self, user_paths: pd.DataFrame):
        self.paths = user_paths
    
    def analyze_paths(self) -> dict:
        """分析用户路径"""
        path_counts = {}
        
        for _, row in self.paths.iterrows():
            path = '->'.join(row['path'])
            path_counts[path] = path_counts.get(path, 0) + 1
        
        # 排序取Top路径
        sorted_paths = sorted(path_counts.items(), key=lambda x: x[1], reverse=True)
        
        return {
            'top_paths': sorted_paths[:10],
            'total_paths': len(path_counts),
            'avg_path_length': np.mean([len(p.split('->')) for p in path_counts.keys()])
        }
    
    def compute_transition_matrix(self) -> pd.DataFrame:
        """计算转移矩阵"""
        transitions = {}
        
        for _, row in self.paths.iterrows():
            path = row['path']
            for i in range(len(path) - 1):
                current = path[i]
                next_step = path[i + 1]
                
                if current not in transitions:
                    transitions[current] = {}
                transitions[current][next_step] = transitions[current].get(next_step, 0) + 1
        
        # 转换为DataFrame
        steps = list(set().union(*transitions.keys()))
        matrix = pd.DataFrame(0, index=steps, columns=steps)
        
        for src, dests in transitions.items():
            for dest, count in dests.items():
                matrix.loc[src, dest] = count
        
        # 归一化
        matrix = matrix.div(matrix.sum(axis=1), axis=0)
        
        return matrix
    
    def simulate_user_journey(self, start_step: str, steps: int = 10) -> list:
        """模拟用户旅程"""
        matrix = self.compute_transition_matrix()
        current = start_step
        journey = [current]
        
        for _ in range(steps):
            if current in matrix.index:
                next_probs = matrix.loc[current].dropna()
                if len(next_probs) > 0:
                    current = next_probs.sample(weights=next_probs).index[0]
                    journey.append(current)
        
        return journey
```

## 四、漏斗优化

```python
class FunnelOptimizer:
    def __init__(self, funnel_data: pd.DataFrame):
        self.funnel = funnel_data
    
    def calculate_opportunity(self) -> dict:
        """计算优化机会"""
        opportunities = {}
        
        for _, row in self.funnel.iterrows():
            step = row['step']
            dropoff = row['dropoff_rate']
            users_lost = int(row['users'] * dropoff)
            
            opportunities[step] = {
                'current_conversion': row['conversion_rate'],
                'dropoff_rate': dropoff,
                'users_lost': users_lost,
                'potential_gain': self.estimate_potential_gain(step, dropoff)
            }
        
        return opportunities
    
    def estimate_potential_gain(self, step: str, current_dropoff: float) -> int:
        """估算潜在收益"""
        # 假设优化后dropoff降低20%
        improved_dropoff = current_dropoff * 0.8
        return int(self.funnel[self.funnel['step'] == step]['users'].values[0] * 
                  (current_dropoff - improved_dropoff))
    
    def prioritize_improvements(self) -> list:
        """优先级排序"""
        opportunities = self.calculate_opportunity()
        
        priorities = []
        for step, data in opportunities.items():
            priority_score = data['users_lost'] * data['potential_gain']
            priorities.append({
                'step': step,
                'priority_score': priority_score,
                'estimated_impact': data['potential_gain']
            })
        
        return sorted(priorities, key=lambda x: x['priority_score'], reverse=True)
```

## 五、面试高频题

### Q1: 如何找到漏斗瓶颈？

```
1. 计算每步转化率
2. 找出最低转化环节
3. 分析用户流失原因
4. 制定优化策略
```

### Q2: 路径分析的价值？

```
1. 发现非预期路径
2. 识别流失节点
3. 优化用户体验
```

## 六、自测题

1. 如何计算转化率？
2. 路径分析如何使用？
3. 如何确定优化优先级？

---

## 参考文档

- [Funnel Analysis](https://mixpanel.com/help/questions/articles/what-is-a-funnel)
- [Path Analysis](https://help.mixpanel.com/hc/en-us/articles/360034907511-Path-Analysis)
