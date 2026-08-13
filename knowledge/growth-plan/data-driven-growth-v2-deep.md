# 数据驱动增长深度实现 - 资深专家深度实现

## 一、数据驱动框架

```
┌─────────────────────────────────────────────────────────────────────────┐
│                   数据驱动增长流程                                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   数据收集 → 数据清洗 → 数据分析 → 洞察提取 → 策略制定 → 实验验证          │
│      ↓         ↓         ↓         ↓         ↓         ↓               │
│  埋点事件   去重/补全   可视化/统计  Aha时刻   增长策略   A/B测试         │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、数据采集实现

```python
import json
from datetime import datetime

class DataCollector:
    def __init__(self):
        self.events = []
        self.schemas = {}
    
    def define_schema(self, event_name: str, properties: list):
        """定义事件Schema"""
        self.schemas[event_name] = {
            'properties': properties,
            'required': ['user_id', 'timestamp'],
            'optional': properties
        }
    
    def track_event(self, event_name: str, user_id: str, 
                    properties: dict = None) -> bool:
        """记录事件"""
        if event_name not in self.schemas:
            return False
        
        event = {
            'event_name': event_name,
            'user_id': user_id,
            'timestamp': datetime.now().isoformat(),
            'properties': properties or {}
        }
        
        # 验证必要字段
        for prop in self.schemas[event_name]['required']:
            if prop not in event and prop not in event['properties']:
                return False
        
        self.events.append(event)
        return True
    
    def batch_track(self, events: list) -> dict:
        """批量记录"""
        success = 0
        failed = 0
        
        for event in events:
            if self.track_event(**event):
                success += 1
            else:
                failed += 1
        
        return {'success': success, 'failed': failed}
```

## 三、数据分析实现

```python
class GrowthAnalyzer:
    def __init__(self, events: list):
        self.events = events
        self.pandas_df = None
    
    def analyze_retention(self) -> dict:
        """留存分析"""
        # 按日期分组
        # 计算每日新增用户的次留/7留/30留
        pass
    
    def analyze_funnel(self, steps: list) -> dict:
        """漏斗分析"""
        funnel_results = {}
        prev_users = None
        
        for step in steps:
            users = self.get_users_for_step(step)
            if prev_users:
                conversion = len(users) / len(prev_users)
                funnel_results[step] = conversion
            prev_users = users
        
        return funnel_results
    
    def get_users_for_step(self, step: str) -> set:
        """获取某步骤用户"""
        # 根据事件类型筛选
        return set()
    
    def cohort_analysis(self, cohort_col: str, period: str = 'week') -> dict:
        """队列分析"""
        # 按时间分群，追踪留存曲线
        pass
    
    def calculate_growth_metrics(self) -> dict:
        """计算增长指标"""
        return {
            'dau_mau_ratio': self.calculate_dau_mau(),
            'viral_coefficient': self.calculate_k_factor(),
            'activation_rate': self.calculate_activation_rate(),
            'retention_1d': self.calculate_retention(1),
            'retention_7d': self.calculate_retention(7),
            'retention_30d': self.calculate_retention(30)
        }
    
    def calculate_dau_mau(self) -> float:
        """DAU/MAU"""
        dau = len(self.events[self.events['date'] == self.events['date'].max()])
        mau = self.events['user_id'].nunique()
        return dau / mau if mau > 0 else 0
    
    def calculate_k_factor(self) -> float:
        """K因子"""
        invites = len([e for e in self.events if e['event'] == 'invite_sent'])
        conversions = len([e for e in self.events if e['event'] == 'invite_converted'])
        return conversions / invites if invites > 0 else 0
```

## 四、面试高频题

### Q1: 如何搭建数据指标体系？

```
1. 北极星指标
2. 核心过程指标
3. 辅助指标
```

### Q2: 如何做A/B测试？

```
1. 明确假设
2. 计算样本量
3. 随机分组
4. 统计分析
```

## 五、自测题

1. 数据驱动流程？
2. 核心增长指标？
3. A/B测试步骤？

---

## 参考文档

- [Data-Driven Growth](https://www.growthhackers.com/growth-hacking/data-driven-growth)
- [Metrics Framework](https://www.pivotable.com/blog/growth-metrics-framework)
