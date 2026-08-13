# 团队管理实战深度实现 - 资深专家深度实现

## 一、TL角色定位

```
┌─────────────────────────────────────────────────────────────────────────┐
│                   技术TL的核心职责                                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   1. 业务目标拆解       → 将公司目标转化为团队可执行的任务                   │
│   2. 人员培养          → 识别潜力，制定成长路径                           │
│   3. 技术决策          → 架构选型，技术风险管理                           │
│   4. 跨团队协作        → 资源协调，冲突解决                               │
│   5. 招聘与团队建设    → 识人用人，打造高绩效团队                          │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、人员管理体系

```python
class TeamManagement:
    def __init__(self):
        self.performance_review_cycle = 90  # 天
    
    def evaluate_performance(self, member: dict) -> dict:
        """评估绩效"""
        metrics = {
            'code_quality': self.evaluate_code_quality(member),
            'delivery_speed': self.evaluate_delivery(member),
            'team_collaboration': self.evaluate_collaboration(member),
            'growth_potential': self.evaluate_growth(member)
        }
        
        score = sum(metrics.values()) / len(metrics)
        rating = self.score_to_rating(score)
        
        return {
            **metrics,
            'overall_score': score,
            'rating': rating,
            'recommendations': self.generate_recommendations(member, rating)
        }
    
    def evaluate_code_quality(self, member: dict) -> float:
        """评估代码质量"""
        return member.get('code_review_score', 0)
    
    def evaluate_delivery(self, member: dict) -> float:
        """评估交付速度"""
        return member.get('on_time_delivery_rate', 0)
    
    def score_to_rating(self, score: float) -> str:
        """分数转等级"""
        if score >= 0.9:
            return 'S'
        elif score >= 0.8:
            return 'A'
        elif score >= 0.7:
            return 'B'
        else:
            return 'C'
```

## 三、成长路径设计

```python
class GrowthPath:
    def __init__(self):
        self.levels = ['初级', '中级', '高级', '资深', '专家']
    
    def design_path(self, current_level: int, target_level: int) -> dict:
        """设计成长路径"""
        path = []
        for level in range(current_level + 1, target_level + 1):
            competencies = self.get_level_requirements(level)
            path.append({
                'level': self.levels[level],
                'requirements': competencies,
                'timeline_months': self.estimate_timeline(level)
            })
        return path
    
    def get_level_requirements(self, level: int) -> list:
        """获取级别要求"""
        requirements = {
            1: ['基础技能', '任务交付'],
            2: ['独立负责', '代码审查'],
            3: ['技术深度', '跨团队协作'],
            4: ['技术影响力', '人才培养'],
            5: ['战略视野', '行业影响']
        }
        return requirements.get(level, [])
    
    def estimate_timeline(self, level: int) -> int:
        """预估时间"""
        return {1: 6, 2: 12, 3: 18, 4: 24, 5: 36}.get(level, 12)
    
    def create_ica(self, member: dict) -> dict:
        """制定ICP (Individual Development Plan)"""
        return {
            'member_name': member['name'],
            'current_level': self.levels[member['level']],
            'target_level': self.levels[min(member['level'] + 1, 4)],
            'strengths': member.get('strengths', []),
            'areas_for_improvement': member.get('improvements', []),
            'actions': [
                '完成XX项目',
                '主导技术分享',
                '指导新人'
            ],
            'review_date': '2026-12-31'
        }
```

## 四、面试高频题

### Q1: 如何评估团队成员？

```
1. 业务产出 (KPI/OKR)
2. 技术能力 (代码质量)
3. 团队协作 (沟通能力)
4. 成长潜力 (学习意愿)
```

### Q2: TL最重要的三个能力？

```
1. 识人用人
2. 目标拆解
3. 技术判断
```

## 五、自测题

1. 如何制定成长路径？
2. ICP是什么？
3. TL的核心职责？

---

## 参考文档

- [Engineering Management](https://edwardtufte.github.io/engineering-management/)
- [TL Handbook](https://github.com/tiangolo/advanced-python)
