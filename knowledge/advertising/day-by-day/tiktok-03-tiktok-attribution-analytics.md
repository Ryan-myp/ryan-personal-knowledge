# TikTok Ads — 归因模型与数据分析

> 创建日期: 2026-06-09
> 作者: Ryan

---

## 第一部分：TikTok 归因模型深度解析

### 1.1 TikTok 转化追踪

```
TikTok 使用 Conversion API + Pixel 追踪转化:

┌──────────────────────────────────────────────────────┐
│              TikTok 转化追踪流程                       │
│                                                      │
│  1. 用户点击 TikTok 广告                               │
│       ↓                                              │
│  2. 添加 UTM 参数或 TikTok 点击 ID                     │
│       ↓                                              │
│  3. 用户到达落地页                                     │
│       ↓                                              │
│  4. 落地页加载 TikTok Pixel                             │
│       ↓                                              │
│  5. 触发标准事件 (Purchase/Lead/...)                   │
│       ↓                                              │
│  6. 数据回传到 TikTok                                  │
│       ↓                                              │
│  7. TikTok 使用归因模型分配功劳                         │
└──────────────────────────────────────────────────────┘
```

### 1.2 TikTok 归因窗口

```
┌─────────────────────────────────────────────────────────┐
│                  TikTok 归因窗口                         │
│                                                         │
│  Click-Through Window:                                  │
│  └── 点击后 7 天内发生的转化                              │
│                                                         │
│  View-Through Window:                                   │
│  └── 展示后 1 天内发生的转化                              │
│                                                         │
│  Attribution Model:                                     │
│  └── Last Touch: 默认归因给最后一次点击                   │
└─────────────────────────────────────────────────────────┘
```

### 1.3 TikTok 广告效果分析

```python
# tiktok_ads/analytics/performance.py
# TikTok 广告效果分析

class TikTokPerformanceAnalyzer:
    """
    TikTok 广告效果分析
    
    核心指标:
    ├── CTR (点击率): clicks / impressions
    ├── CVR (转化率): conversions / clicks
    ├── CPA (每次行动费用): spend / conversions
    ├── ROAS (广告支出回报率): revenue / spend
    ├── VTR (视频观看率): video_views / impressions
    └── 3s Play Rate: 3s plays / impressions
    """
    
    def calculate_metrics(self, impressions: int, clicks: int,
                          conversions: int, spend: float,
                          revenue: float, video_views: int = 0,
                          plays_3s: int = 0) -> dict:
        """
        计算核心指标
        
        参数:
        ├── impressions: 展示
        ├── clicks: 点击
        ├── conversions: 转化
        ├── spend: 花费
        ├── revenue: 收入
        ├── video_views: 视频播放 (15s+)
        └── plays_3s: 3s 播放
        
        返回:
        └── 指标字典
        """
        ctr = clicks / max(impressions, 1)
        cvr = conversions / max(clicks, 1)
        cpa = spend / max(conversions, 1)
        roas = revenue / max(spend, 0.01)
        vtr = video_views / max(impressions, 1)
        play_3s_rate = plays_3s / max(impressions, 1)
        
        return {
            'ctr': ctr,
            'cvr': cvr,
            'cpa': cpa,
            'roas': roas,
            'vtr': vtr,
            'play_3s_rate': play_3s_rate,
        }
    
    def benchmark(self, metrics: dict) -> dict:
        """
        行业基准对比
        
        TikTok 行业平均 (2024):
        ├── CTR: 0.5% - 1.5%
        ├── CVR: 1% - 5%
        ├── CPA: $5 - $50
        └── VTR: 30% - 60%
        """
        benchmarks = {
            'ctr': {'low': 0.005, 'avg': 0.01, 'high': 0.015},
            'cvr': {'low': 0.01, 'avg': 0.03, 'high': 0.05},
            'cpa': {'low': 50, 'avg': 20, 'high': 5},
            'vtr': {'low': 0.3, 'avg': 0.45, 'high': 0.6},
        }
        
        assessment = {}
        for metric in ['ctr', 'cvr', 'cpa', 'vtr']:
            if metric not in benchmarks:
                continue
            
            value = metrics.get(metric, 0)
            benchmark = benchmarks[metric]
            
            if value >= benchmark['high']:
                grade = 'A'
            elif value >= benchmark['avg']:
                grade = 'B'
            elif value >= benchmark['low']:
                grade = 'C'
            else:
                grade = 'D'
            
            assessment[metric] = {
                'value': value,
                'grade': grade,
                'benchmark': benchmark,
            }
        
        return assessment
```

### 1.4 A/B 测试框架

```python
# tiktok_ads/experiment/ab_test.py
# TikTok A/B 测试

class TikTokABTest:
    """
    TikTok A/B 测试框架
    
    测试维度:
    ├── 创意 (Creative): 视频 vs 图片
    ├── 文案 (Copy): 不同文案
    ├── 定向 (Targeting): 不同受众
    ├── 出价 (Bidding): 不同出价策略
    └── 落地页 (Landing Page): 不同页面
    """
    
    def setup_test(self, campaign_id: str, test_type: str,
                   variants: list, budget_per_variant: float = 100.0) -> dict:
        """
        设置 A/B 测试
        
        参数:
        ├── campaign_id: 广告系列 ID
        ├── test_type: 测试类型 (creative/copy/targeting/bidding)
        ├── variants: 变体列表
        └── budget_per_variant: 每个变体的预算
        
        返回:
        └── 测试配置
        """
        test_config = {
            'campaign_id': campaign_id,
            'test_type': test_type,
            'variants': variants,
            'budget_per_variant': budget_per_variant,
            'duration_days': 7,  # 至少 7 天
            'sample_size': self._calculate_sample_size(),
        }
        
        return test_config
    
    def analyze_results(self, variant_results: dict) -> dict:
        """
        分析测试结果
        
        使用 statistical significance test
        判断是否有显著差异
        """
        # 计算每个变体的关键指标
        results = {}
        for name, data in variant_results.items():
            impressions = data['impressions']
            clicks = data['clicks']
            conversions = data['conversions']
            
            ctr = clicks / max(impressions, 1)
            cvr = conversions / max(clicks, 1)
            
            results[name] = {
                'ctr': ctr,
                'cvr': cvr,
                'impressions': impressions,
                'clicks': clicks,
                'conversions': conversions,
            }
        
        # 找出最佳变体
        best_variant = max(results.items(), 
                          key=lambda x: x[1]['cvr'])
        
        return {
            'results': results,
            'best_variant': best_variant[0],
            'best_cv': best_variant[1]['cvr'],
        }
```

---

## 第二部分：TikTok 数据分析实战

### 2.1 视频表现分析

```python
# tiktok_ads/analytics/video.py
# 视频表现分析

class VideoPerformanceAnalyzer:
    """
    TikTok 视频表现分析
    
    核心分析维度:
    ├── 播放完成率 (Completion Rate)
    ├── 互动率 (Engagement Rate)
    ├── 分享率 (Share Rate)
    └── 转化率 (Conversion Rate)
    """
    
    def analyze_video(self, video_data: dict) -> dict:
        """
        分析视频表现
        
        参数:
        └── video_data: 视频数据
            ├── impressions: 展示
            ├── plays_3s: 3s 播放
            ├── full_plays: 完整播放
            ├── likes: 点赞
            ├── comments: 评论
            ├── shares: 分享
            ├── clicks: 点击
            └── conversions: 转化
        
        返回:
        └── 分析报告
        """
        impressions = video_data.get('impressions', 0)
        plays_3s = video_data.get('plays_3s', 0)
        full_plays = video_data.get('full_plays', 0)
        likes = video_data.get('likes', 0)
        comments = video_data.get('comments', 0)
        shares = video_data.get('shares', 0)
        clicks = video_data.get('clicks', 0)
        conversions = video_data.get('conversions', 0)
        
        # 计算指标
        metrics = {
            'play_3s_rate': plays_3s / max(impressions, 1),
            'completion_rate': full_plays / max(plays_3s, 1),
            'like_rate': likes / max(impressions, 1),
            'comment_rate': comments / max(impressions, 1),
            'share_rate': shares / max(impressions, 1),
            'click_rate': clicks / max(impressions, 1),
            'conversion_rate': conversions / max(clicks, 1),
        }
        
        # 综合评分
        score = (
            metrics['play_3s_rate'] * 0.2 +
            metrics['completion_rate'] * 0.2 +
            metrics['like_rate'] * 0.15 +
            metrics['share_rate'] * 0.15 +
            metrics['click_rate'] * 0.2 +
            metrics['conversion_rate'] * 0.1
        ) * 10
        
        return {
            'metrics': metrics,
            'score': score,
            'grade': self._get_grade(score),
        }
    
    def _get_grade(self, score: float) -> str:
        """评分等级"""
        if score >= 8:
            return 'S'
        elif score >= 6:
            return 'A'
        elif score >= 4:
            return 'B'
        elif score >= 2:
            return 'C'
        else:
            return 'D'


# 使用示例
analyzer = VideoPerformanceAnalyzer()

video_data = {
    'impressions': 100000,
    'plays_3s': 35000,
    'full_plays': 15000,
    'likes': 5000,
    'comments': 500,
    'shares': 1000,
    'clicks': 3000,
    'conversions': 150,
}

result = analyzer.analyze_video(video_data)
print(f"评分: {result['score']:.2f}")
print(f"等级: {result['grade']}")
for metric, value in result['metrics'].items():
    print(f"  {metric}: {value:.4f}")
```

---

## 第三部分：自测

### 问题 1
TikTok 的默认归因窗口是多少？
<details>
<summary>查看答案</summary>

- Click-Through: 7 天
- View-Through: 1 天
- 默认归因模型: Last Touch
</details>

### 问题 2
TikTok 视频的核心指标有哪些？
<details>
<summary>查看答案</summary>

- CTR (点击率)
- CVR (转化率)
- VTR (视频观看率)
- 3s Play Rate (3s 播放率)
- Completion Rate (播放完成率)
</details>

### 问题 3
TikTok A/B 测试至少需要持续多久？
<details>
<summary>查看答案</summary>

- 至少 7 天
- 确保覆盖完整的用户行为周期
</details>

---

## 第四部分：动手验证

### 4.1 视频表现分析

```python
from tiktok_ads.analytics.video import VideoPerformanceAnalyzer

analyzer = VideoPerformanceAnalyzer()

video_data = {
    'impressions': 100000,
    'plays_3s': 35000,
    'full_plays': 15000,
    'likes': 5000,
    'comments': 500,
    'shares': 1000,
    'clicks': 3000,
    'conversions': 150,
}

result = analyzer.analyze_video(video_data)
print(f"评分: {result['score']:.2f}")
print(f"等级: {result['grade']}")
```

---

*今天花 60-90 分钟：深入理解 TikTok 归因模型，实践数据分析*
*答不出自测题？回去重读对应章节。*

```go
package tiktokattr

import (
	"fmt"
	"sort"
)

type Engine struct {
	model string
}

func (e *Engine) Assign(touchpoints []string, revenue float64) map[string]float64 {
	credits := make(map[string]float64)
	n := float64(len(touchpoints))
	if n > 0 { for _, tp := range touchpoints { credits[tp] += revenue / n } }
	return credits
}

type Result struct {
	Channel string
	Credit  float64
	Grade   string
}

func (e *Engine) Grade(touchpoints []string, revenue float64) []Result {
	credits := e.Assign(touchpoints, revenue)
	results := make([]Result, 0, len(credits))
	for ch, cr := range credits {
		grade := "C"
		if cr*100/revenue > 3 { grade = "A" } else if cr*100/revenue > 1.5 { grade = "B" }
		results = append(results, Result{ch, cr, grade})
	}
	sort.Slice(results, func(i, j int) bool { return results[i].Credit > results[j].Credit })
	return results
}

func main() {
	e := &Engine{}
	for _, r := range e.Grade([]string{"fb", "tiktok", "email"}, 300.0) {
		fmt.Printf("  %s: $%.2f (%s)
", r.Channel, r.Credit, r.Grade)
	}
}

