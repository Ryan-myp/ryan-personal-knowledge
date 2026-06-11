# Google Ads — 归因模型与数据分析

> 创建日期: 2026-06-09
> 作者: Ryan

---

## 第一部分：归因模型深度解析

### 1.1 为什么归因很重要？

```
用户旅程:
┌─────────────────────────────────────────────────────┐
│                                                     │
│  用户看到 Google Search 广告 → 点击                  │
│       ↓                                             │
│  用户浏览 Landing Page，没有转化                      │
│       ↓                                             │
│  3 天后用户在 Display 广告看到同一品牌                │
│       ↓                                             │
│  用户再次点击 Display 广告                            │
│       ↓                                             │
│  用户在 Google Search 中直接搜索品牌名                │
│       ↓                                             │
│  用户点击品牌搜索广告 → 完成转化                     │
│                                                     │
│  问题: 这个转化应该归功于哪个广告？                   │
│  - Last Click? (最后一个点击的广告)                  │
│  - First Click? (第一个点击的广告)                   │
│  - Linear? (均匀分配)                               │
│  - Time Decay? (时间衰减)                           │
│  - Data-Driven? (数据驱动)                          │
└─────────────────────────────────────────────────────┘
```

### 1.2 Google Ads 归因模型

```
┌──────────────────────────────────────────────────────────────────────┐
│                    Google Ads 归因模型                                │
│                                                                      │
│  1. Last Click:                                                      │
│     - 100% 功劳给最后一个点击的广告                                   │
│     - 简单但严重偏向转化前触点的广告                                  │
│                                                                      │
│  2. First Click:                                                     │
│     - 100% 功劳给第一个点击的广告                                    │
│     - 偏向拉新渠道 (Search/Display)                                  │
│                                                                      │
│  3. Linear:                                                          │
│     - 所有触点平分功劳                                               │
│     - 假设每个触点贡献相同                                           │
│                                                                      │
│  4. Time Decay:                                                      │
│     - 越接近转化的触点功劳越大                                       │
│     - 衰减函数: credit(t) ∝ e^(-λt)                                 │
│     - λ 可配置 (通常 0.3-0.5)                                       │
│                                                                      │
│  5. Position Based (U-Shaped):                                       │
│     - 首次点击 40%，末次点击 40%，中间均匀分配 20%                   │
│     - 平衡拉新和转化                                                 │
│                                                                      │
│  6. Data-Driven (推荐):                                              │
│     - 基于机器学习，自动分配功劳                                      │
│     - 需要至少 15 次转化/月/广告系列                                 │
│     - 比较转化路径 vs 无转化路径的触点差异                            │
│     - 自适应不同用户旅程                                              │
└──────────────────────────────────────────────────────────────────────┘
```

### 1.3 Data-Driven 归因源码

```python
# google_ads/attribution/dda.py
# Data-Driven Attribution (数据驱动归因) 实现

import numpy as np
from collections import defaultdict

class DataDrivenAttributionModel:
    """
    数据驱动归因模型
    
    核心思想:
    比较"有转化"的转化路径和"无转化"的浏览路径
    统计每个触点在转化路径中的"增量贡献"
    
    使用 Shapley Value 或 Markov Chain 模型
    这里实现简化版 Markov Chain
    """
    
    def __init__(self):
        self.transition_matrix = None
        self.removal_effect = None
    
    def fit(self, conversion_paths: list, 
            browse_paths: list = None,
            max_steps: int = 10):
        """
        训练归因模型
        
        参数:
        ├── conversion_paths: 转化路径列表
        │   - 每个路径是触点序列: ['search', 'display', 'search']
        │   - 最后一个是转化触点
        └── browse_paths: 无转化的浏览路径列表
            - 用于对比分析
        """
        # 构建状态转移矩阵
        state_counts = defaultdict(lambda: defaultdict(int))
        state_totals = defaultdict(int)
        
        for path in conversion_paths + (browse_paths or []):
            for i in range(len(path) - 1):
                current = path[i]
                next_state = path[i + 1]
                state_counts[current][next_state] += 1
                state_totals[current] += 1
        
        # 计算转移概率
        self.transition_matrix = {}
        for state, transitions in state_counts.items():
            total = state_totals[state]
            self.transition_matrix[state] = {
                next_state: count / max(total, 1)
                for next_state, count in transitions.items()
            }
        
        # 计算移除效应 (Removal Effect)
        self.removal_effect = self._calculate_removal_effect(
            conversion_paths
        )
    
    def _calculate_removal_effect(self, paths: list) -> dict:
        """
        计算移除效应
        
        移除某个触点后，转化率下降多少？
        下降越多，该触点的价值越高
        
        公式:
        removal_effect(channel) = 1 - P(convert | without channel) / P(convert)
        """
        # 计算原始转化率
        total_conversions = len(paths)
        
        # 移除每个触点后的转化率
        conversion_rates_without = {}
        for channel in set(c for path in paths for c in path):
            # 过滤掉包含该触点的转化路径
            filtered_paths = [
                path for path in paths
                if channel not in path
            ]
            rate = len(filtered_paths) / max(total_conversions, 1)
            conversion_rates_without[channel] = rate
        
        # 计算移除效应
        removal_effects = {}
        for channel, rate in conversion_rates_without.items():
            original_rate = 1.0  # 假设原始为 1（相对值）
            removal = 1.0 - (rate / max(original_rate, 0.001))
            removal_effects[channel] = max(0, removal)
        
        return removal_effects
    
    def assign_attribution(self, path: list) -> dict:
        """
        为转化路径分配功劳
        
        参数:
        └── path: 触点序列
        
        返回:
        └── {channel: credit} 字典
        """
        if not path:
            return {}
        
        # 使用移除效应加权分配
        total_removal = sum(self.removal_effect.get(ch, 0) for ch in path)
        
        if total_removal == 0:
            # 均匀分配
            return {ch: 1.0 / len(path) for ch in path}
        
        attribution = {}
        for i, channel in enumerate(path):
            # 位置权重 (越靠近转化越高)
            position_weight = (i + 1) / len(path)
            
            # 移除效应权重
            removal_weight = self.removal_effect.get(channel, 0)
            
            # 最终分配
            attribution[channel] = position_weight * removal_weight
        
        # 归一化到 1.0
        total = sum(attribution.values())
        if total > 0:
            attribution = {ch: val / total for ch, val in attribution.items()}
        
        return attribution


# 使用示例
model = DataDrivenAttributionModel()

# 模拟转化路径
conversion_paths = [
    ['search', 'display', 'search'],
    ['search', 'search'],
    ['display', 'search'],
    ['search', 'email', 'search'],
    ['display', 'email', 'search'],
]

# 训练模型
model.fit(conversion_paths)

# 分配功劳
path = ['search', 'display', 'search']
attribution = model.assign_attribution(path)
print(f"路径: {path}")
for channel, credit in attribution.items():
    print(f"  {channel}: {credit:.2%}")
```

### 1.4 转化价值计算

```python
# google_ads/attribution/value.py
# 转化价值计算

class ConversionValueCalculator:
    """
    转化价值计算器
    
    计算每个触点/渠道的:
    ├── 转化次数
    ├── 转化价值
    ├── ROAS (广告支出回报率)
    └── 增量价值
    """
    
    def __init__(self):
        self.channel_data = defaultdict(lambda: {
            'impressions': 0,
            'clicks': 0,
            'conversions': 0,
            'value': 0.0,
            'cost': 0.0,
        })
    
    def add_conversion(self, channel: str, 
                       conversions: int,
                       value: float,
                       cost: float,
                       impressions: int = 0,
                       clicks: int = 0):
        """
        添加转化数据
        
        参数:
        ├── channel: 渠道名称
        ├── conversions: 转化次数
        ├── value: 转化价值
        ├── cost: 广告花费
        ├── impressions: 展示次数
        └── clicks: 点击次数
        """
        data = self.channel_data[channel]
        data['conversions'] += conversions
        data['value'] += value
        data['cost'] += cost
        data['impressions'] += impressions
        data['clicks'] += clicks
    
    def get_roas(self, channel: str) -> float:
        """
        获取渠道 ROAS
        
        ROAS = 转化价值 / 广告花费
        
        参数:
        └── channel: 渠道名称
        
        返回:
        └── ROAS (4.0 = 400%)
        """
        data = self.channel_data[channel]
        return data['value'] / max(data['cost'], 0.01)
    
    def get_incremental_value(self, channel: str, 
                               baseline_roas: float = 1.0) -> float:
        """
        计算增量价值
        
        增量价值 = (渠道 ROAS - 基准 ROAS) × 花费
        
        参数:
        ├── channel: 渠道名称
        └── baseline_roas: 基准 ROAS (无广告时的 ROAS)
        
        返回:
        └── 增量价值 (USD)
        """
        data = self.channel_data[channel]
        channel_roas = self.get_roas(channel)
        incremental = (channel_roas - baseline_roas) * data['cost']
        return max(0, incremental)
```

---

## 第二部分：深度数据分析

### 2.1 漏斗分析

```python
# google_ads/analytics/funnel.py
# 漏斗分析

class FunnelAnalyzer:
    """
    漏斗分析器
    
    分析用户从看到广告到转化的每一步:
    ┌──────────────────────────────────────────────────────┐
    │  Impressions (展示)                                   │
    │       ↓ 100%                                         │
    │  Clicks (点击)         ↓ CTR                         │
    │       ↓                                              │
    │  Landing Page Views (页面浏览)                        │
    │       ↓ 落地页停留率                                  │
    │  Engagements (互动)                                   │
    │       ↓                                              │
    │  Conversions (转化)                                   │
    │       ↓ 转化率                                        │
    │  Revenue (收入)                                       │
    └──────────────────────────────────────────────────────┘
    """
    
    def __init__(self):
        self.funnel_data = {}
    
    def analyze(self, campaign_id: str) -> dict:
        """
        分析广告系列漏斗
        
        参数:
        └── campaign_id: 广告系列 ID
        
        返回:
        └── 漏斗分析报告
        """
        # 获取各层级数据
        data = self._get_funnel_data(campaign_id)
        
        # 计算转化漏斗
        impressions = data['impressions']
        clicks = data['clicks']
        landing_views = data['landing_page_views']
        engagements = data['engagements']
        conversions = data['conversions']
        revenue = data['revenue']
        
        # 计算转化率
        ctr = clicks / max(impressions, 1)
        lp_conversion_rate = landing_views / max(clicks, 1)
        engagement_rate = engagements / max(landing_views, 1)
        conversion_rate = conversions / max(engagements, 1)
        revenue_per_conversion = revenue / max(conversions, 1)
        
        # 找出瓶颈
        bottlenecks = []
        if ctr < 0.02:
            bottlenecks.append({
                'stage': 'CTR',
                'value': ctr,
                'recommendation': '改进广告文案和素材',
            })
        if lp_conversion_rate < 0.3:
            bottlenecks.append({
                'stage': 'Landing Page',
                'value': lp_conversion_rate,
                'recommendation': '优化落地页体验',
            })
        if conversion_rate < 0.05:
            bottlenecks.append({
                'stage': 'Conversion',
                'value': conversion_rate,
                'recommendation': '优化转化路径',
            })
        
        return {
            'funnel': {
                'impressions': impressions,
                'clicks': clicks,
                'landing_page_views': landing_views,
                'engagements': engagements,
                'conversions': conversions,
                'revenue': revenue,
            },
            'rates': {
                'ctr': ctr,
                'landing_page_conversion_rate': lp_conversion_rate,
                'engagement_rate': engagement_rate,
                'conversion_rate': conversion_rate,
                'revenue_per_conversion': revenue_per_conversion,
            },
            'bottlenecks': bottlenecks,
        }
    
    def _get_funnel_data(self, campaign_id: str) -> dict:
        """获取漏斗数据 (模拟)"""
        return {
            'impressions': 100000,
            'clicks': 2000,
            'landing_page_views': 1800,
            'engagements': 500,
            'conversions': 25,
            'revenue': 5000.0,
        }
```

### 2.2 多维数据分析

```python
# google_ads/analytics/multidimensional.py
# 多维数据分析

class MultiDimensionalAnalyzer:
    """
    多维数据分析
    
    分析维度:
    ├── 时间 (小时/天/周/月)
    ├── 设备 (mobile/desktop/tablet)
    ├── 地理位置 (country/region/city)
    ├── 受众 (age/gender/interests)
    ├── 广告位 (placement)
    └── 关键词/创意
    """
    
    def __init__(self):
        self.metrics = defaultdict(lambda: defaultdict(float))
    
    def add_metric(self, dimension: str, metric_name: str, value: float):
        """添加指标数据"""
        self.metrics[dimension][metric_name] += value
    
    def analyze_by_time(self) -> dict:
        """按时间分析"""
        # 找出最佳投放时段
        hourly_data = {}
        for hour in range(24):
            key = f"hour_{hour}"
            impressions = self.metrics[key].get('impressions', 0)
            conversions = self.metrics[key].get('conversions', 0)
            roas = self.metrics[key].get('roas', 0)
            
            hourly_data[hour] = {
                'impressions': impressions,
                'conversions': conversions,
                'roas': roas,
            }
        
        # 找出 ROAS 最高的时段
        best_hour = max(hourly_data.items(), key=lambda x: x[1]['roas'])
        
        return {
            'hourly': hourly_data,
            'best_hour': best_hour[0],
            'best_roas': best_hour[1]['roas'],
        }
    
    def analyze_by_device(self) -> dict:
        """按设备分析"""
        device_metrics = {}
        for device in ['mobile', 'desktop', 'tablet']:
            impressions = self.metrics[device].get('impressions', 0)
            clicks = self.metrics[device].get('clicks', 0)
            conversions = self.metrics[device].get('conversions', 0)
            cost = self.metrics[device].get('cost', 0)
            revenue = self.metrics[device].get('revenue', 0)
            
            device_metrics[device] = {
                'ctr': clicks / max(impressions, 1),
                'conversion_rate': conversions / max(clicks, 1),
                'roas': revenue / max(cost, 0.01),
            }
        
        return device_metrics
```

---

## 第三部分：自测

### 问题 1
Google Ads 有哪些归因模型？
<details>
<summary>查看答案</summary>

- Last Click: 100% 给最后点击的广告
- First Click: 100% 给首次点击的广告
- Linear: 均匀分配
- Time Decay: 越接近转化功劳越大
- Position Based (U-Shaped): 首/末各 40%，中间平分
- Data-Driven: 机器学习自动分配（推荐）
</details>

### 问题 2
Data-Driven 归因的适用条件是什么？
<details>
<summary>查看答案</summary>

- 需要至少 15 次转化/月/广告系列
- 比较转化路径和无转化路径的差异
- 自适应不同用户旅程
</details>

### 问题 3
漏斗分析中，如何判断瓶颈？
<details>
<summary>查看答案</summary>

- CTR < 2%: 广告文案/素材需要优化
- 落地页转化率 < 30%: 落地页需要优化
- 转化率 < 5%: 转化路径需要优化
</details>

---

## 第四部分：动手验证

### 4.1 归因分析

```python
from google_ads.attribution.dda import DataDrivenAttributionModel

model = DataDrivenAttributionModel()

conversion_paths = [
    ['search', 'display', 'search'],
    ['search', 'search'],
    ['display', 'search'],
]

model.fit(conversion_paths)
attribution = model.assign_attribution(['search', 'display', 'search'])

for channel, credit in attribution.items():
    print(f"{channel}: {credit:.2%}")
```

---

### 归因分析引擎的 Go 实现

```go
package analytics

import (
	"fmt"
	"sort"
	"time"
)

type ModelType string
const (
	ModelLinear ModelType = "LINEAR"
	ModelTimeDecay ModelType = "TIME_DECAY"
	ModelDataDriven ModelType = "DATA_DRIVEN"
)

type ConversionPath struct {
	Touchpoints []Touchpoint `json:"touchpoints"`
	Converted   bool         `json:"converted"`
	Revenue     float64      `json:"revenue"`
}

type Touchpoint struct {
	Channel   string    `json:"channel"`
	Type      string    `json:"type"`
	Timestamp time.Time `json:"timestamp"`
	Value     float64   `json:"value"`
}

type AttributionResult struct {
	Channel string
	Credit  float64
	Revenue float64
}

func AssignPath(path *ConversionPath, model ModelType) []AttributionResult {
	results := make(map[string]float64)

	switch model {
	case ModelLinear:
		clicks := 0
		for _, tp := range path.Touchpoints {
			if tp.Type == "click" { clicks++ }
		}
		if clicks > 0 {
			for _, tp := range path.Touchpoints {
				if tp.Type == "click" {
					results[tp.Channel] += path.Revenue / float64(clicks)
				}
			}
		}

	case ModelTimeDecay:
		var weighted []struct{ ch string; w float64 }
		for i, tp := range path.Touchpoints {
			if tp.Type == "click" {
				days := path.Touchpoints[len(path.Touchpoints)-1].Timestamp.Sub(tp.Timestamp).Hours() / 24
				w := 1.0 / (1.0 + days)
				weighted = append(weighted, struct{ ch string; w float64 }{tp.Channel, w})
			}
		}
		total := 0.0
		for _, w := range weighted { total += w.w }
		for _, w := range weighted {
			results[w.ch] += w.w / total * path.Revenue
		}

	case ModelDataDriven:
		for _, tp := range path.Touchpoints {
			if tp.Type == "conversion" {
				results[tp.Channel] += tp.Value
			}
		}
	}

	res := make([]AttributionResult, 0, len(results))
	for ch, cr := range results {
		res = append(res, AttributionResult{Channel: ch, Credit: cr, Revenue: cr})
	}
	sort.Slice(res, func(i, j int) bool { return res[i].Credit > res[j].Credit })
	return res
}

func main() {
	path := &ConversionPath{
		Converted: true, Revenue: 200.0,
		Touchpoints: []Touchpoint{
			{Channel: "search", Type: "click", Timestamp: time.Now().Add(-7*24*time.Hour)},
			{Channel: "display", Type: "impression", Timestamp: time.Now().Add(-5*24*time.Hour)},
			{Channel: "search", Type: "click", Timestamp: time.Now().Add(-3*24*time.Hour)},
			{Channel: "email", Type: "click", Timestamp: time.Now().Add(-1*24*time.Hour)},
		},
	}
	for _, r := range AssignPath(path, ModelTimeDecay) {
		fmt.Printf("  %s: $%.2f\n", r.Channel, r.Credit)
	}
}
