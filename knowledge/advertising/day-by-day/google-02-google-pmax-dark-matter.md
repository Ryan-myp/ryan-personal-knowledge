# Google Ads — PMax 黑盒剖析：信号权重、资产组优化、LLM 驱动

> 创建日期: 2026-06-09
> 作者: Ryan
> 定位: 资深专家级

---

## 第一部分：PMax 的架构本质

### 1.1 PMax 是什么——不是"自动化广告"那么简单

```
PMax (Performance Max) 不是"一键投放"，而是一个跨渠道的
多目标优化系统。

传统广告系列：
┌──────────────────────────────────────┐
│  Campaign: "Search Ads"              │
│  Channel: Search only                │
│  Creative: Fixed (Text ads)          │
│  Targeting: Keywords + Locations     │
│  Optimization: Clicks/Conversions    │
└──────────────────────────────────────┘

PMax 广告系列：
┌────────────────────────────────────────────────────────┐
│  Campaign: "PMax"                                      │
│  Channels: Search + Display + YouTube + Gmail + Maps  │
│  Creative: Asset Group (Images, Videos, Logos, Text)  │
│  Targeting: Signals (NOT Keywords)                    │
│  Optimization: Conversions/Revenue                     │
│  AI Engine: Multi-channel Attribution + Bid + Creative│
└────────────────────────────────────────────────────────┘

核心差异：
├─ 传统: 你控制每一个出价、每一个定向
├─ PMax: 你提供信号和素材，Google 的 AI 引擎决定一切
└─ PMax 是 Google 最复杂的广告产品
```

### 1.2 PMax 的底层架构

```
PMax 的系统架构：

┌──────────────────────────────────────────────────────────────┐
│                    PMax Architecture                         │
│                                                              │
│  User Input Layer                                           │
│  ├── Asset Groups: 素材组（图片、视频、logo、标题、描述）   │
│  ├── Signals: 信号（受众、关键词、位置、网站）               │
│  ├── Budget: 日预算                                          │
│  └── Conversion Goals: 转化目标                              │
│                                                              │
│  AI Engine (Google 黑盒)                                     │
│  ├── 渠道分配 (Channel Allocation)                            │
│  │   └─ 决定每个转化来自哪个渠道                               │
│  ├── 出价优化 (Bid Optimization)                              │
│  │   └─ 跨渠道统一出价                                        │
│  ├── 创意组合 (Creative Combination)                           │
│  │   └─ 动态组合标题+描述+图片+视频                            │
│  └── 归因 (Attribution)                                       │
│      └─ 跨渠道转化归因                                         │
│                                                              │
│  Output Layer                                                │
│  ├── Search Ads: 搜索广告                                     │
│  ├── Display Ads: 展示广告（自动创建）                         │
│  ├── YouTube Ads: 视频广告                                    │
│  ├── Gmail Ads: 邮件广告                                     │
│  ├── Maps Ads: 地图广告                                      │
│  └─ Shopping Ads: 商品广告（如果使用 Product Feed）          │
└──────────────────────────────────────────────────────────────┘
```

---

## 第二部分：Asset Group 的优化机制

### 2.1 Asset Group 的结构

```
PMax 的核心是 Asset Group（资产组）：

Asset Group 包含：
├─ Images (图片): 最多 20 张
│   └─ 建议: 1:1, 16:9, 4:5 比例各备
├─ Logos (Logo): 最多 20 个
│   └─ 建议: 正方形 + 横版
├─ Videos (视频): 最多 50 个（通常 2-5 个）
│   └─ 建议: 6s, 15s, 30s 各备
├─ Headlines (标题): 最多 5 个
│   └─ 每个最多 30 字符
├─ Descriptions (描述): 最多 4 个
│   └─ 每个最多 90 字符
└─ Call-to-action (CTA): 1 个
   └─ "Buy Now", "Learn More" 等

关键点：
├─ Asset Group 数量: 建议 3-10 个（基于产品/受众细分）
├─ 每个 Asset Group 对应一个受众/产品线
└─ Asset Group 之间不共享素材（互斥）
```

### 2.2 创意组合的 A/B 测试机制

```
PMax 如何自动测试创意组合？

动态创意生成 (Dynamic Creative Optimization, DCO)：

假设 Asset Group 有：
├─ 5 个 Headlines: H1-H5
├─ 4 个 Descriptions: D1-D4
├─ 10 个 Images: I1-I10
├─ 3 个 Videos: V1-V3

可能的组合数: 5 × 4 × 10 × 3 = 600 种

PMax 的工作流程：
1. 初始阶段：每个组合随机曝光，收集点击/转化数据
2. 探索阶段: ε-greedy 策略（5% 探索，95% 利用）
3. 利用阶段: 优先展示历史表现最好的组合
4. 更新周期: 每 24 小时更新一次排名

实际组合数远小于理论值：
├─ Google 使用贝叶斯优化减少搜索空间
├─ 只测试历史上表现好的组合的子集
└─ 约 50-100 种组合在同时测试

创意表现分层：
├─ 顶级组合 (Top 10%): 占 60% 展示
├─ 中等组合 (Middle 80%): 占 35% 展示
└─ 底部组合 (Bottom 10%): 占 5% 展示（淘汰风险）
```

### 2.3 Asset Group 表现分析

```python
# PMax Asset Group 表现分析工具

class AssetGroupAnalyzer:
    """
    PMax Asset Group 表现分析器
    
    分析维度:
    ├── Asset Performance: 每个素材的表现
    ├── Combination Performance: 组合表现
    └── Channel Performance: 各渠道贡献
    """
    
    def analyze_asset_performance(self, asset_data: dict) -> dict:
        """
        分析素材表现
        
        参数:
        └── asset_data: 素材表现数据
        
        返回:
        └── 素材分析报告
        """
        # 按素材类型分组
        by_type = {}
        for asset in asset_data['assets']:
            asset_type = asset['type']  # headline, description, image, video
            if asset_type not in by_type:
                by_type[asset_type] = []
            by_type[asset_type].append(asset)
        
        analysis = {}
        for asset_type, assets in by_type.items():
            # 按表现排序
            assets.sort(key=lambda x: x['cvr'], reverse=True)
            
            # 找出 Top 和 Bottom
            top = assets[0]
            bottom = assets[-1]
            
            analysis[asset_type] = {
                'count': len(assets),
                'avg_cvr': sum(a['cvr'] for a in assets) / len(assets),
                'top_performer': {
                    'id': top['id'],
                    'cvr': top['cvr'],
                    'impressions': top['impressions'],
                },
                'bottom_performers': [
                    {'id': a['id'], 'cvr': a['cvr']}
                    for a in assets[:3]  # 最差的前 3 个
                ],
            }
        
        return analysis
    
    def optimize_asset_groups(self, ag_data: list) -> list:
        """
        优化 Asset Group
        
        策略：
        ├── 表现好的 AG: 增加预算
        ├── 表现差的 AG: 减少预算或合并
        └── 新素材: 持续替换
        """
        # 按 ROAS 排序
        sorted_ag = sorted(ag_data, key=lambda x: x['roas'], reverse=True)
        
        optimizations = []
        for ag in sorted_ag:
            if ag['roas'] > 3.0:
                optimizations.append({
                    'action': 'INCREASE_BUDGET',
                    'ag_id': ag['id'],
                    'factor': 1.2,
                    'reason': f"ROAS={ag['roas']:.2f}",
                })
            elif ag['roas'] < 1.0 and ag['conversions'] > 10:
                optimizations.append({
                    'action': 'DECREASE_BUDGET',
                    'ag_id': ag['id'],
                    'factor': 0.8,
                    'reason': f"ROAS={ag['roas']:.2f} 且转化>10",
                })
            else:
                optimizations.append({
                    'action': 'KEEP',
                    'ag_id': ag['id'],
                    'reason': '表现稳定',
                })
        
        return optimizations
```

---

## 第三部分：Signals（信号）的本质

### 3.1 PMax 的定向机制

```
PMax 使用 Signals（信号）替代传统的定向方式：

Signal 类型：
├─ Audience Signals (受众信号)
│   ├── First-party audiences: 自有受众（CRM、网站访客）
│   ├── In-market audiences: 购买意向受众
│   ├── Demographics: 人口统计（年龄、性别、收入）
│   └── Custom segments: 自定义受众
├─ Keyword Signals (关键词信号)
│   └─ 不是精确匹配！而是"相关性信号"
├─ Placement Signals (展示位信号)
│   └─ 指定 YouTube 频道、网站等
├─ Location Signals (地理位置信号)
│   └─ 国家、地区、城市、半径
└─ Website Signals (网站信号)
   └─ 类似 Remarketing 的网页 URL 信号

关键区别：
├─ 传统广告: 关键词 = 精确/短语/广泛匹配（触发条件）
├─ PMax: 关键词信号 = 相关性指示（不触发匹配）
└─ PMax 的 Signal 不会告诉你在哪里投放，只是"偏好"
```

### 3.2 Signal 权重分配

```
PMax 如何分配 Signal 权重？

底层模型：
Signal_Relevance = f(信号类型, 历史表现, 竞争环境)

权重分配逻辑：
1. 第一方受众: 权重最高 (因为转化数据丰富)
2. 购买意向: 权重高（Intent 强）
3. 人口统计: 权重中
4. 关键词信号: 权重低（仅作为相关性信号）

信号权重公式（简化）：
Signal_Weight = Base_Weight × Performance_Factor × Recency_Factor

├─ Base_Weight:
│   ├── First-party: 1.0
│   ├── In-market: 0.8
│   ├── Demographics: 0.5
│   └── Keyword: 0.3
├─ Performance_Factor: 基于历史表现调整 (0.5-1.5)
└─ Recency_Factor: 近期表现权重更高 (指数衰减)

实战意义：
├─ 上传自己的受众列表（第一方）效果最好
├─ 购买意向受众次之
├─ 关键词信号只是"提示"，不要依赖它
└─ 定期更新信号列表（表现好的受众权重更高）
```

### 3.3 跨渠道归因（Cross-Channel Attribution）

```
PMax 的核心优势：跨渠道转化路径分析

典型 PMax 转化路径：
┌──────────────────────────────────────────────────────┐
│  Day 1: 用户在 YouTube 看到视频广告（展示）            │
│       ↓                                              │
│  Day 2: 用户在 Google 搜索品牌词（点击视频广告）      │
│       ↓                                              │
│  Day 3: 用户在 Gmail 看到邮件广告（展示）             │
│       ↓                                              │
│  Day 4: 用户在 Display 看到图片广告（点击）           │
│       ↓                                              │
│  Day 5: 用户直接搜索品牌 → 完成购买                   │
│                                                      │
│  传统归因会说：最后转化来自 "Direct Search"           │
│  PMax 说：转化来自 YouTube 的首次触达！               │
│  → 这才是 PMax 真正的价值                            │
└──────────────────────────────────────────────────────┘

跨渠道归因的数据驱动模型：
├─ 识别每个触点在转化路径中的贡献
├─ 考虑触点的时间衰减
├─ 考虑触点的交互效应（YouTube 展示提升了搜索点击）
└─ 使用机器学习模型估计每个触点的增量价值
```

---

## 第四部分：PMax 的 LLM 驱动创意优化

### 4.1 Google 如何使用 LLM 优化 PMax

```
Google 在 PMax 中使用 LLM 进行创意优化：

1. 创意生成 (Creative Generation)
   ─────────────────────────────
   输入: 产品标题 + 描述 + 图片
   输出: 自动生成的广告文案
   
   流程:
   ├── 提取产品特征（从 Feed 或落地页）
   ├── 生成多种文案变体
   ├── A/B 测试各变体
   └── 根据表现淘汰/保留
   
2. 视频脚本生成 (Video Script Generation)
   ─────────────────────────────
   输入: 产品类别 + 目标受众
   输出: 视频脚本 + 分镜
   
   流程:
   ├── 分析高转化视频的脚本模式
   ├── 生成符合模式的脚本
   ├── 生成视频 storyboard
   └── 建议拍摄方案

3. 标题优化 (Headline Optimization)
   ─────────────────────────────
   输入: 历史表现数据
   输出: 优化建议
   
   流程:
   ├── 分析表现最好的标题的特征
   ├── 提取有效模板（"X% off"、"Free shipping"）
   ├── 生成新的标题组合
   └── 自动测试新组合
```

### 4.2 创意 A/B 测试的自动化

```
PMax 的自动化 A/B 测试：

测试框架:
├─ 多臂老虎机 (Multi-Armed Bandit)
│   └─ 动态分配流量给表现最好的创意
├─ 贝叶斯优化 (Bayesian Optimization)
│   └─ 高效搜索创意空间
└─ Thompson Sampling
   └─ 平衡探索与利用

实施：
1. 初始阶段: 所有创意组合随机展示
2. 学习阶段: 根据表现调整权重
3. 利用阶段: 80% 流量给最佳组合，20% 继续探索
4. 更新周期: 每天更新一次权重

效果:
├─ 相比手动 A/B 测试，自动化测试的 ROI 高 15-30%
├─ 无需人工干预，Google 自动处理
└─ 每天可测试数百种创意组合
```

---

## 第五部分：PMax 生产实战

### 5.1 PMax 的坑与排障

```
PMax 常见问题：

1. 预算分配不合理
   ── 症状: 某些渠道花不完，某些渠道超支
   ── 原因: 信号不够精准，Google 不知道投放到哪里
   ── 解决: 增加第一方受众，减少泛泛的受众信号

2. 品牌词被竞争对手抢
   ── 症状: 品牌搜索被竞争对手广告拦截
   ── 原因: PMax 的 Broad Match + Signal 机制
   ── 解决: 保留独立的 Search 广告系列保护品牌

3. 创意相关性差
   ── 症状: 展示了很多不相关的广告
   ── 原因: 素材组太泛，信号不够具体
   ── 解决: 拆分多个 Asset Group，每个更聚焦

4. 转化量下降
   ── 症状: 转化数突然下降
   ── 原因: 信号过期、创意疲劳、竞争变化
   ── 解决: 更新信号、替换创意、检查竞品

5. 看不到具体匹配关键词
   ── 症状: 不知道哪些搜索词触发了广告
   ── 原因: PMax 不展示搜索词报告
   ── 解决: 查看"搜索词报告"（有限信息）+ 关键词信号分析
```

### 5.2 PMax 最佳实践

```
PMax 最佳实践清单：

1. Asset Group 规划
   ├── 按产品线/受众/地域拆分多个 AG
   ├── 每个 AG 有 3-5 个核心素材
   ├── 标题要包含核心卖点
   └─ 避免 AG 之间素材重叠

2. 信号策略
   ├── 上传 CRM 数据（最高优先级）
   ├── 使用购买意向受众
   ├── 添加关键词信号（作为提示）
   └─ 定期更新信号列表

3. 创意策略
   ├── 视频广告是 PMax 的 killer asset
   ├── 准备多种比例的图片（1:1, 16:9, 4:5）
   ├── 标题要有 CTA
   └─ 每季度更新一次创意

4. 预算策略
   ├── PMax 需要充足预算（≥ 30 × target CPA）
   ├── 不要在短期内频繁调整预算
   ├── 考虑单独设一个 PMax 预算测试
   └─ 监控渠道分布，确保不过度依赖某一渠道

5. 品牌保护
   ├── 保留独立的 Brand Search 广告系列
   ├── 使用品牌否定（在 PMax 中排除品牌词）
   └─ 监控品牌词的 PMax 消耗
```

---

## 第六部分：PMax vs 传统广告系列

### 6.1 PMax 的适用场景

```
什么时候用 PMax？
├─ ✅ 电商网站（有 Product Feed）
├─ ✅ 需要跨渠道曝光
├─ ✅ 预算充足，需要自动化
├─ ✅ 有充足的转化数据
└─ ❌ 品牌保护（保留独立 Search）
└─ ❌ 需要精细控制（保留独立广告系列）

什么时候不用 PMax？
├─ ❌ 预算有限（< $500/月）
├─ ❌ B2B 服务（受众太窄）
├─ ❌ 需要精确控制关键词
└─ ❌ 没有转化数据（学习期太长）
```

### 6.2 PMax 与其他渠道的协同

```
PMax 的渠道协同策略：

Search + PMax:
├─ Brand Search: 独立广告系列（保护品牌）
├─ Non-Brand Search: 交给 PMax
└─ PMax 覆盖搜索 + 展示 + 视频

Display + PMax:
├─ PMax 自动生成 Display 广告
└─ 无需单独 Display 广告系列

YouTube + PMax:
├─ PMax 自动生成 YouTube 广告
└─ 品牌 YouTube 广告可独立设置

Gmail + PMax:
├─ PMax 自动生成 Gmail 广告
└─ 通常表现一般，可关闭
```

---

## 自测题

### 问题 1
PMax 中的 Signal 与 Search 广告的关键词匹配有什么区别？

<details>
<summary>查看答案</summary>

- Search 关键词匹配是触发条件（决定广告是否展示）
- PMax Signal 是相关性信号（影响投放偏好，不触发匹配）
- PMax 不展示搜索词报告，Signal 不会告诉你在哪里投放
</details>

### 问题 2
PMax 的创意组合最多有多少种可能？

<details>
<summary>查看答案</summary>

- 假设 5 个标题 × 4 个描述 × 10 个图片 × 3 个视频 = 600 种
- Google 使用贝叶斯优化缩小搜索空间
- 实际同时测试约 50-100 种
</details>

### 问题 3
为什么 PMax 不适合品牌保护？

<details>
<summary>查看答案</summary>

- PMax 的 Broad Match + Signal 机制会匹配竞品词
- 无法精确控制品牌词的投放
- 品牌搜索可能被竞争对手广告拦截
- 应保持独立 Brand Search 广告系列
</details>

---

## 动手验证

### 5.1 Asset Group 优化

```python
from google_ads.pmax.asset_analyzer import AssetGroupAnalyzer

analyzer = AssetGroupAnalyzer()

asset_data = {
    'assets': [
        {'id': 'h1', 'type': 'headline', 'text': '50% Off', 'cvr': 0.05, 'impressions': 10000},
        {'id': 'h2', 'type': 'headline', 'text': 'Best Price', 'cvr': 0.02, 'impressions': 8000},
        {'id': 'h3', 'type': 'headline', 'text': 'Free Shipping', 'cvr': 0.03, 'impressions': 9000},
    ]
}

result = analyzer.analyze_asset_performance(asset_data)
for asset_type, analysis in result.items():
    print(f"{asset_type}:")
    print(f"  平均 CVR: {analysis['avg_cvr']:.4f}")
    print(f"  最佳: {analysis['top_performer']}")
```

---

### PMax 创意资产优化的 Go 实现

```go
package pmax

import (
	"fmt"
	"math/rand"
	"sort"
	"sync"
	"time"
)

type AssetType string
const (
	AssetHeadline AssetType = "HEADLINE"
	AssetDescription AssetType = "DESCRIPTION"
	AssetImage AssetType = "IMAGE"
	AssetVideo AssetType = "VIDEO"
	AssetLogo AssetType = "LOGO"
	AssetPromoAsset AssetType = "PROMO_ASSET"
)

type Asset struct {
	Type      AssetType `json:"type"`
	Source    string    `json:"source"` // GENERATED, CLIENT_UPLOADED
	Status    string    `json:"status"`
	Value     string    `json:"value"`
	PerfScore float64   `json:"perf_score"`
}

type AssetGroup struct {
	ID      string   `json:"id"`
	Name    string   `json:"name"`
	Assets  []*Asset `json:"assets"`
	Signals []*Signal `json:"signals"`
}

type Signal struct {
	Type          string         `json:"type"`
	Values        []string       `json:"values"`
	Performance[]float64      `json:"performance"`
}

type CreativePerformance struct {
	CreativeID      string  `json:"creative_id"`
	Impressions     int     `json:"impressions"`
	Clicks          int     `json:"clicks"`
	Conversions     int     `json:"conversions"`
	Revenue         float64 `json:"revenue"`
	CTR             float64 `json:"ctr"`
	CVR             float64 `json:"cvr"`
	ROAS            float64 `json:"roas"`
}

type CreativeAnalyzer struct {
	assets     map[AssetType][]*Asset
	perf       []*CreativePerformance
	mu         sync.RWMutex
}

func (a *CreativeAnalyzer) ScoreAsset(asset *Asset, ctype AssetType) float64 {
	a.mu.RLock()
	defer a.mu.RUnlock()
	totalImp, totalConv := 0, 0
	for _, p := range a.perf {
		if p.Conversions > 0 && p.Impressions > 0 {
			totalConv += p.Conversions
			totalImp += p.Impressions
		}
	}
	baseScore := asset.PerfScore
	if baseScore == 0 {
		baseScore = 0.5 // 默认
	}
	// 资产质量分 = 历史表现 × 权重
	switch ctype {
	case AssetHeadline:
		return baseScore * 0.3 + rand.Float64()*0.2
	case AssetImage:
		return baseScore * 0.4 + rand.Float64()*0.15
	case AssetDescription:
		return baseScore * 0.2 + rand.Float64()*0.25
	default:
		return baseScore * 0.3
	}
}

func (a *CreativeAnalyzer) AnalyzeAssets() map[AssetType][]*Asset {
	a.mu.RLock()
	defer a.mu.RUnlock()
	result := make(map[AssetType][]*Asset)
	for _, asset := range a.assets {
		for _, a := range asset {
			key := a.Type
			if _, ok := result[key]; !ok {
				result[key] = make([]*Asset, 0)
			}
			result[key] = append(result[key], a)
		}
	}
	for _, assets := range result {
		sort.Slice(assets, func(i, j int) bool {
			return assets[i].PerfScore > assets[j].PerfScore
		})
	}
	return result
}

func (a *CreativeAnalyzer) RecordPerformance(cp *CreativePerformance) {
	a.mu.Lock()
	defer a.mu.Unlock()
	a.perf = append(a.perf, cp)
}

type PerformanceMaxOptimizer struct {
	targetROAS float64
	budget     float64
	groups     []*AssetGroup
}

func NewPMaxOptimizer(targetROAS, budget float64) *PerformanceMaxOptimizer {
	return &PerformanceMaxOptimizer{targetROAS: targetROAS, budget: budget}
}

func (o *PerformanceMaxOptimizer) AllocateBudget() map[string]float64 {
	weights := make(map[string]float64)
	totalWeight := 0.0
	for _, g := range o.groups {
		w := 0.0
		for _, asset := range g.Assets {
			if asset.PerfScore > 0 {
				w += asset.PerfScore
			}
		}
		weights[g.ID] = w
		totalWeight += w
	}
	budget := make(map[string]float64)
	for id, w := range weights {
		if totalWeight > 0 {
			budget[id] = (w / totalWeight) * o.budget
		} else {
			budget[id] = o.budget / float64(len(o.groups))
		}
	}
	return budget
}

func main() {
	analyzer := &CreativeAnalyzer{assets: make(map[AssetType][]*Asset)}
	asset := &Asset{Type: AssetHeadline, Value: "Summer Sale", PerfScore: 0.85}
	fmt.Printf("Asset score: %.2f\n", analyzer.ScoreAsset(asset, AssetHeadline))

	optimizer := NewPMaxOptimizer(3.0, 1000.0)
	optimizer.groups = []*AssetGroup{
		{ID: "ag1", Assets: []*Asset{{PerfScore: 0.9}, {PerfScore: 0.7}}},
		{ID: "ag2", Assets: []*Asset{{PerfScore: 0.6}, {PerfScore: 0.8}}},
	}
	budget := optimizer.AllocateBudget()
	for id, b := range budget {
		fmt.Printf("Budget %s: $%.2f\n", id, b)
	}
}
```

---

*今天花 90 分钟：深入理解 PMax 的 AI 引擎和创意优化*
*答不出自测题？回去重读对应章节。*
