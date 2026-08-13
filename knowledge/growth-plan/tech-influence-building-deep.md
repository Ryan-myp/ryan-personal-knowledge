# 技术影响力建设深度实现 - 资深专家深度实现

## 一、影响力维度

```
┌─────────────────────────────────────────────────────────────────────────┐
│                   技术影响力模型                                           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   内部影响力                                                          │
│   ├── 技术分享 (团队内)                                               │
│   ├── 代码贡献 (PR/Review)                                            │
│   └── 知识沉淀 (文档/Wiki)                                            │
│                                                                         │
│   外部影响力                                                          │
│   ├── 开源贡献 (GitHub)                                               │
│   ├── 技术写作 (博客/公众号)                                          │
│   ├── 社区活动 (演讲/Meetup)                                          │
│   └── 行业认可 (认证/奖项)                                            │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、影响力建设

```python
class TechnicalInfluence:
    def __init__(self):
        self.influence_metrics = {}
    
    def build_internal_influence(self, activities: list) -> dict:
        """建设内部影响力"""
        return {
            'tech_shares': {
                'count': len([a for a in activities if a['type'] == 'share']),
                'topics': [a['topic'] for a in activities if a['type'] == 'share']
            },
            'code_contribution': {
                'prs': len([a for a in activities if a['type'] == 'pr']),
                'reviews': len([a for a in activities if a['type'] == 'review'])
            },
            'knowledge_base': {
                'docs': len([a for a in activities if a['type'] == 'doc']),
                'tutorials': len([a for a in activities if a['type'] == 'tutorial'])
            }
        }
    
    def build_external_influence(self, activities: list) -> dict:
        """建设外部影响力"""
        return {
            'open_source': {
                'repos': len([a for a in activities if a['type'] == 'oss']),
                'stars': sum(a.get('stars', 0) for a in activities if a['type'] == 'oss'),
                'contributions': len([a for a in activities if a['type'] == 'oss_contrib'])
            },
            'technical_writing': {
                'articles': len([a for a in activities if a['type'] == 'article']),
                'total_views': sum(a.get('views', 0) for a in activities if a['type'] == 'article')
            },
            'speaking': {
                'talks': len([a for a in activities if a['type'] == 'talk']),
                'events': list(set(a['event'] for a in activities if a['type'] == 'talk'))
            }
        }
    
    def calculate_influence_score(self) -> float:
        """计算影响力评分"""
        weights = {
            'internal': 0.4,
            'external': 0.6
        }
        
        internal_score = self.calculate_internal_score()
        external_score = self.calculate_external_score()
        
        return internal_score * weights['internal'] + external_score * weights['external']
```

## 三、面试高频题

### Q1: 如何提升技术影响力？

```
1. 内部: 技术分享、代码贡献、知识沉淀
2. 外部: 开源、写作、演讲
```

### Q2: 影响力建设的关键？

```
1. 持续输出
2. 解决实际问题
3. 建立个人品牌
```

## 四、自测题

1. 影响力维度有哪些？
2. 如何量化影响力？
3. 内部 vs 外部影响力？

---

## 参考文档

- [Technical Leadership](https://www.paulgraham.com/leadership.html)
- [Influence Building](https://www.yegor256.com/2018/05/16/how-to-become-senior-engineer.html)
