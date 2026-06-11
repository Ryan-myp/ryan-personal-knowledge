# Meta Ads — 归因模型与数据分析

> 创建日期: 2026-06-09
> 作者: Ryan

---

## 第一部分：Meta 归因模型深度解析

### 1.1 Meta 归因窗口

```
Meta 使用多种归因窗口来追踪转化:

┌──────────────────────────────────────────────────────────┐
│              Meta 归因窗口                                │
│                                                          │
│  Click-Through Window:                                   │
│  └── 点击后 7 天内发生的转化                              │
│                                                          │
│  View-Through Window:                                    │
│  └── 展示后 1 天内发生的转化（用户没点击）                 │
│                                                          │
│  Attribution Rules:                                      │
│  ├── One Ad Per Click/View: 每个点击/展示只算一次转化     │
│  ├── One Conversion Per Ad Per Day: 每天每个广告最多算一次│
│  └── One Conversion Per Ad Set Per Day: 每天每个广告组   │
└──────────────────────────────────────────────────────────┘
```

### 1.2 Meta 归因模型

```
┌─────────────────────────────────────────────────────────┐
│                  Meta 归因模型                            │
│                                                         │
│  1. Last Interaction (默认):                             │
│     - 归因给最后一次互动 (点击或展示)                     │
│     - 偏向转化前触点                                      │
│                                                         │
│  2. First Interaction:                                  │
│     - 归因给首次互动                                     │
│     - 偏向拉新触点                                        │
│                                                         │
│  3. Most Recent:                                        │
│     - 归因给最近一次互动                                  │
│                                                         │
│  4. Linear:                                             │
│     - 所有触点平分                                       │
│                                                         │
│  5. Time Decay:                                         │
│     - 越接近转化功劳越大                                  │
│                                                         │
│  6. Custom Combinations:                                │
│     - 自定义点击/展示归因规则                              │
│     - 例如: 点击优先 (Click + 1d View)                  │
└─────────────────────────────────────────────────────────┘
```

### 1.3 增量测量 (Incrementality)

```python
# meta_ads/attribution/incrementality.py
# Meta 增量测量

class IncrementalityTester:
    """
    Meta 增量测量
    
    核心问题: "如果没有投放广告，这些用户还会转化吗？"
    
    方法:
    ├── 实验设计 (A/B Test)
    ├── 受众分组 (Treatment vs Control)
    └── 统计显著性检验
    """
    
    def design_experiment(self, target_audience_size: int,
                          holdback_percentage: float = 0.2) -> dict:
        """
        设计增量测试
        
        流程:
        1. 从目标受众中抽取 holdback group (对照组)
        2. 不对对照组投放广告
        3. 对比 treatment group 和 control group 的转化率
        
        参数:
        ├── target_audience_size: 目标受众规模
        └── holdback_percentage: 对照组比例 (通常 20%)
        
        返回:
        └── 实验设计
        """
        holdback_size = int(target_audience_size * holdback_percentage)
        treatment_size = target_audience_size - holdback_size
        
        return {
            'treatment_group': {
                'size': treatment_size,
                'description': '正常投放广告',
            },
            'holdback_group': {
                'size': holdback_size,
                'description': '不投放广告（对照组）',
            },
        }
    
    def calculate_incrementality(self, treatment_data: dict,
                                  control_data: dict) -> dict:
        """
        计算增量效果
        
        参数:
        ├── treatment_data: 实验组数据
        │   ├── conversions: 转化数
        │   ├── spend: 花费
        │   └── revenue: 收入
        └── control_data: 对照组数据
            ├── conversions: 转化数 (自然转化)
            └── spend: 0 (不投放)
        
        返回:
        └── 增量分析报告
        """
        treatment_conversions = treatment_data['conversions']
        control_conversions = control_data['conversions']
        
        # 调整样本大小
        treatment_size = treatment_data.get('audience_size', 10000)
        control_size = control_data.get('audience_size', 10000)
        
        treatment_rate = treatment_conversions / max(treatment_size, 1)
        control_rate = control_conversions / max(control_size, 1)
        
        # 增量转化
        incremental_conversions = treatment_conversions - int(
            control_rate * treatment_size
        )
        
        # 增量 ROAS
        treatment_spend = treatment_data['spend']
        treatment_revenue = treatment_data['revenue']
        control_revenue = control_data.get('revenue', 0)
        
        incremental_revenue = treatment_revenue - control_revenue
        incremental_roas = incremental_revenue / max(treatment_spend, 0.01)
        
        # 自然转化 (如果没有广告会发生的转化)
        natural_conversions = int(control_rate * treatment_size)
        
        return {
            'incremental_conversions': max(0, incremental_conversions),
            'natural_conversions': natural_conversions,
            'incremental_roas': incremental_roas,
            'treatment_conversion_rate': treatment_rate,
            'control_conversion_rate': control_rate,
        }


# 使用示例
tester = IncrementalityTester()

# 实验组数据
treatment = {
    'conversions': 500,
    'spend': 10000,
    'revenue': 50000,
    'audience_size': 50000,
}

# 对照组数据
control = {
    'conversions': 50,
    'spend': 0,
    'revenue': 5000,
    'audience_size': 10000,
}

result = tester.calculate_incrementality(treatment, control)
print(f"增量转化: {result['incremental_conversions']}")
print(f"自然转化: {result['natural_conversions']}")
print(f"增量 ROAS: {result['incremental_roas']:.2f}")
```

### 1.4 Pixel 事件追踪

```python
# meta_ads/tracking/pixel.py
# Meta Pixel 事件追踪

class PixelTracker:
    """
    Meta Pixel 事件追踪
    
    标准事件:
    ├── ViewContent: 查看内容
    ├── AddToCart: 加入购物车
    ├── InitiateCheckout: 开始结算
    ├── Purchase: 购买
    ├── Lead: 销售线索
    ├── CompleteRegistration: 完成注册
    ├── Contact: 联系
    ├── CustomizeProduct: 自定义产品
    └── Donate: 捐赠
    
    自定义事件:
    ├── 用户定义的事件名称
    └── 可传递自定义参数
    """
    
    def track_event(self, event_name: str, 
                    event_id: str = None,
                    value: float = 0.0,
                    currency: str = 'USD',
                    custom_params: dict = None) -> bool:
        """
        追踪 Pixel 事件
        
        参数:
        ├── event_name: 事件名称
        ├── event_id: 事件 ID (唯一标识)
        ├── value: 事件价值
        ├── currency: 货币代码
        └── custom_params: 自定义参数
        
        返回:
        └── 是否成功
        """
        # 发送事件到 Meta Pixel
        payload = {
            'event': event_name,
            'event_id': event_id or self._generate_event_id(),
            'event_time': int(time.time()),
            'user_data': self._get_user_data(),
            'custom_data': {
                'value': value,
                'currency': currency,
                **(custom_params or {}),
            },
        }
        
        # 发送到 Meta 服务器
        response = requests.post(
            'https://pixel-data.facebook.com/events',
            json=payload,
            timeout=5,
        )
        
        return response.status_code == 200
    
    def track_purchase(self, transaction_id: str,
                       value: float,
                       currency: str = 'USD',
                       items: list = None) -> bool:
        """
        追踪购买事件
        
        参数:
        ├── transaction_id: 交易 ID
        ├── value: 交易金额
        ├── currency: 货币
        └── items: 购买的商品列表
        
        返回:
        └── 是否成功
        """
        items_data = []
        if items:
            for item in items:
                items_data.append({
                    'id': item.get('product_id', ''),
                    'quantity': item.get('quantity', 1),
                    'item_price': item.get('price', 0),
                    'title': item.get('title', ''),
                    'category': item.get('category', ''),
                })
        
        return self.track_event(
            event_name='Purchase',
            event_id=transaction_id,
            value=value,
            currency=currency,
            custom_params={
                'content_ids': [item['id'] for item in items_data],
                'contents': items_data,
            }
        )
```

---

## 第二部分：深度数据分析

### 2.1 转化路径分析

```python
# meta_ads/analytics/conversion_path.py
# 转化路径分析

class ConversionPathAnalyzer:
    """
    转化路径分析
    
    分析用户在转化前的触点序列:
    ┌─────────────────────────────────────────────────────┐
    │  Touchpoint Timeline:                                │
    │                                                     │
    │  Day 1: 看到 Instagram Story 广告                    │
    │  Day 2: 搜索品牌词                                    │
    │  Day 3: 看到 Facebook Feed 广告                      │
    │  Day 4: 点击 Ad → 浏览网站                           │
    │  Day 5: 再次点击 → 完成购买                           │
    │                                                     │
    │  触点类型:                                            │
    │  ├── ad_impression: 广告展示                         │
    │  ├── ad_click: 广告点击                              │
    │  ├── organic_search: 自然搜索                         │
    │  └── direct: 直接访问                                │
    └─────────────────────────────────────────────────────┘
    """
    
    def analyze_paths(self, user_paths: list) -> dict:
        """
        分析转化路径
        
        参数:
        └── user_paths: 用户路径列表
        
        返回:
        └── 路径分析报告
        """
        path_counts = defaultdict(int)
        path_to_conversions = defaultdict(int)
        
        for path in user_paths:
            path_key = ' → '.join(path['touchpoints'])
            path_counts[path_key] += 1
            if path.get('converted', False):
                path_to_conversions[path_key] += 1
        
        # 计算每个路径的转化率
        path_stats = {}
        for path_key, count in path_counts.items():
            conversions = path_to_conversions.get(path_key, 0)
            path_stats[path_key] = {
                'count': count,
                'conversions': conversions,
                'conversion_rate': conversions / max(count, 1),
            }
        
        # 找出最高转化路径
        best_path = max(path_stats.items(), 
                       key=lambda x: x[1]['conversion_rate'])
        
        return {
            'path_stats': path_stats,
            'best_path': best_path[0],
            'best_conversion_rate': best_path[1]['conversion_rate'],
        }
```

### 2.2 ROAS 分析

```python
# meta_ads/analytics/roas.py
# ROAS 分析

class ROASAnalyzer:
    """
    ROAS (Return On Ad Spend) 分析
    
    ROAS = 收入 / 广告花费
    
    多维度 ROAS:
    ├── 按广告系列: 哪个系列 ROI 最高
    ├── 按广告组: 哪个广告组 ROI 最高
    ├── 按广告: 哪个广告 ROI 最高
    ├── 按受众: 哪个受众 ROI 最高
    └── 按创意: 哪个创意 ROI 最高
    """
    
    def analyze_roas(self, campaign_data: list) -> dict:
        """
        分析 ROAS
        
        参数:
        └── campaign_data: 广告系列数据列表
        
        返回:
        └── ROAS 分析报告
        """
        results = []
        
        for campaign in campaign_data:
            spend = campaign.get('spend', 0)
            revenue = campaign.get('revenue', 0)
            roas = revenue / max(spend, 0.01)
            
            results.append({
                'name': campaign['name'],
                'spend': spend,
                'revenue': revenue,
                'roas': roas,
                'profit': revenue - spend,
            })
        
        # 排序
        results.sort(key=lambda x: x['roas'], reverse=True)
        
        return {
            'campaigns': results,
            'total_spend': sum(r['spend'] for r in results),
            'total_revenue': sum(r['revenue'] for r in results),
            'overall_roas': sum(r['revenue'] for r in results) / 
                           max(sum(r['spend'] for r in results), 0.01),
        }
```

---

## 第三部分：自测

### 问题 1
Meta 默认的归因窗口是多少？
<details>
<summary>查看答案</summary>

- Click-Through: 7 天
- View-Through: 1 天
</details>

### 问题 2
增量测试中，Holdback Group 的作用是什么？
<details>
<summary>查看答案</summary>

- 作为对照组，不投放广告
- 测量自然转化率
- 计算真正的增量转化 = 实验组转化 - 自然转化
</details>

### 问题 3
Meta Pixel 标准事件有哪些？
<details>
<summary>查看答案</summary>

- ViewContent, AddToCart, InitiateCheckout, Purchase
- Lead, CompleteRegistration, Contact
- CustomizeProduct, Donate
</details>

---

## 第四部分：动手验证

### 4.1 ROAS 分析

```python
from meta_ads.analytics.roas import ROASAnalyzer

analyzer = ROASAnalyzer()

campaign_data = [
    {'name': 'Campaign A', 'spend': 1000, 'revenue': 5000},
    {'name': 'Campaign B', 'spend': 2000, 'revenue': 6000},
    {'name': 'Campaign C', 'spend': 500, 'revenue': 4000},
]

result = analyzer.analyze_roas(campaign_data)
for campaign in result['campaigns']:
    print(f"{campaign['name']}: ROAS={campaign['roas']:.2f}, Profit=${campaign['profit']}")

print(f"整体 ROAS: {result['overall_roas']:.2f}")
```

---

*今天花 60-90 分钟：深入理解 Meta 归因模型，实践数据分析*
*答不出自测题？回去重读对应章节。*

```go
package metaanalytics

import (
	"fmt"
	"sort"
	"time"
)

type AttributionModel string
const (
	ModelLastClick AttributionModel = "LAST_CLICK"
	ModelLinear AttributionModel = "LINEAR"
	ModelTimeDecay AttributionModel = "TIME_DECAY"
)

type ConversionPath struct {
	Touchpoints []Touchpoint
	Revenue     float64
}

type Touchpoint struct {
	Channel   string
	Timestamp time.Time
}

type AttributionResult struct {
	Channel string
	Credit  float64
}

func AssignPath(path *ConversionPath, model AttributionModel) []AttributionResult {
	credits := make(map[string]float64)
	switch model {
	case ModelLastClick:
		if len(path.Touchpoints) > 0 { credits[path.Touchpoints[len(path.Touchpoints)-1].Channel] = path.Revenue }
	case ModelLinear:
		n := float64(len(path.Touchpoints))
		if n > 0 { for _, tp := range path.Touchpoints { credits[tp.Channel] += path.Revenue / n } }
	}
	res := make([]AttributionResult, 0, len(credits))
	for ch, cr := range credits { res = append(res, AttributionResult{ch, cr}) }
	sort.Slice(res, func(i, j int) bool { return res[i].Credit > res[j].Credit })
	return res
}

