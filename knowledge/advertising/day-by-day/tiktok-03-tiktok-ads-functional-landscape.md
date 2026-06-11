# TikTok Ads — 平台功能全景深度梳理

> 创建日期: 2026-06-09
> 作者: Ryan
> 定位: 资深专家级 — 平台功能全覆盖

---

## 第一部分: 广告层级体系

### 1.1 TikTok 广告层级

```
TikTok 广告采用三到四层级结构:

┌──────────────────────────────────────────────────────────────┐
│                  TikTok 广告层级                               │
│                                                              │
│  1. Campaign (广告系列)                                        │
│     ├── 目标 (Objective): 流量/转化/应用互动/品牌认知/视频互动  │
│     ├── 竞价策略: Lowest Cost / Cost Cap / Bid Cap / Target  │
│     ├── 预算: 日预算/总预算                                    │
│     ├── 排期: 开始/结束日期                                    │
│     └─ 广告系列分组                                            │
│                                                              │
│  2. Ad Group (广告组)                                         │
│     ├── 定向: 地域/年龄/性别/语言/兴趣/行为                    │
│     ├── 预算: 日预算 (Ad Group 级别)                          │
│     ├── 竞价: OCPM/OCPA/OPTC/CPM                             │
│     ├── 优化目标: Conversion/Link Click/Lead/App Install等    │
│     ├── 排期: 时段设置                                         │
│     ├── 频次控制: Frequency Cap                               │
│     ├── 定向优化: Advantage+ Optimization                     │
│     └─ 创意优化: Advantage+ Creative Optimization             │
│                                                              │
│  3. Ad (广告)                                                 │
│     ├── 格式: 视频/单图/轮播/合集/Spark                         │
│     ├── 媒体: 上传视频/图片/轮播                                │
│     ├── 文案: 标题/描述/CTA                                   │
│     ├── 落地页: URL/应用深链                                  │
│     ├── 追踪: Pixel/CAPI                                     │
│     └─ Spark Ads: 引用有机视频                                   │
│                                                              │
│  4. Creative (创意)                                           │
│     ├── 媒体管理                                             │
│     ├── 模板库                                               │
│     └─ 动态创意                                               │
└──────────────────────────────────────────────────────────────┘
```

### 1.2 广告系列目标 (Objectives)

```
TikTok 广告系列目标:

┌──────────────────────────────────────────────────────────────┐
│              TikTok Campaign Objectives                       │
│                                                              │
│  Traffic (流量):                                             │
│  └── 优化目标: Link Clicks / Page Views                     │
│      └─ 竞价: OCPM / OPTC / CPM                           │
│      └─ 适用: 网站引流 / 内容推广                            │
│                                                              │
│  Conversions (转化):                                          │
│  └── 优化目标: Purchase / Lead / Install / CompleteRegistration │
│      └─ 竞价: OCPM / OCPA / Cost Cap                     │
│      └─ 适用: 电商销售 / 线索收集                             │
│                                                              │
│  App Engagement (应用互动):                                    │
│  └── 优化目标: App Install / App Event                      │
│      └─ 竞价: OCPM / OCPA / Bid Cap                      │
│      └─ 适用: 移动应用推广                                    │
│                                                              │
│  Video Views (视频观看):                                      │
│  └── 优化目标: Video View / ThruPlay                        │
│      └─ 竞价: OCPM / OPTC / CPM                          │
│      └─ 适用: 品牌视频推广                                    │
│                                                              │
│  Brand Awareness (品牌认知):                                  │
│  └── 优化目标: Brand Lift / Reach                           │
│      └─ 竞价: CPM / OCPM                                 │
│      └─ 适用: 品牌广告                                        │
│                                                              │
│  Store Traffic (到店):                                        │
│  └── 优化目标: Store Visit                                  │
│      └─ 竞价: OCPM / CPM                                 │
│      └─ 适用: 本地零售                                        │
│                                                              │
│  Lead Generation (线索收集):                                  │
│  └── 优化目标: Lead Form                                    │
│      └─ 竞价: OCPM / OCPA                                │
│      └─ 适用: B2B/服务推广                                    │
└──────────────────────────────────────────────────────────────┘
```

---

## 第二部分: 出价策略体系

### 2.1 TikTok 出价类型

```
TikTok 出价策略:

1. OCPM (Optimized CPM):
   ├── 按展示计费, 系统自动优化目标转化
   ├── 适合: 转化目标 / 品牌曝光
   ├── 计费: 每千次展示
   ├── 优化: 系统根据 pAction 调整实际成本
   └─ 推荐: 大多数场景

2. OCPA (Optimized CPC):
   ├── 按点击计费, 系统优化转化
   ├── 适合: 转化目标
   ├── 计费: 每次点击
   └─ 适合: 追求转化效果

3. OPTC (Optimized Target Cost):
   ├── 设定目标成本 (CPC/CPA)
   ├── 系统尽量接近目标成本
   └─ 适合: 控制成本

4. CPM (Cost Per Mille):
   ├── 按千次展示固定计费
   ├── 适合: 品牌曝光
   └─ 适合: 视频品牌广告

5. CPC (Cost Per Click):
   ├── 按点击固定计费
   ├── 适合: 流量导向
   └─ 适合: 网站引流

6. Bid Cap (出价上限):
   ├── 设置最高 CPC/CPM
   ├── 不会超过此出价
   └─ 适合: 预算有限

7. Cost Cap (成本上限):
   ├── 设定平均 CPA 上限
   ├── 允许短期波动
   └─ 适合: 稳定转化
```

### 2.2 出价策略对比

```
┌──────────────────────────────────────────────────────────────┐
│              TikTok 出价策略选择指南                           │
│                                                              │
│  | 场景                | 推荐策略   | 理由                   |
│  |-------------------|--------|----------------------|
│  | 电商转化           | OCPA    | 按转化优化              |
│  | 品牌曝光           | CPM    | 按展示计费              |
│  | 网站引流           | OCPM   | 平衡成本与效果          |
│  | 应用安装           | OCPM   | 系统自动优化            |
│  | 视频观看           | OPTC   | 控制单次观看成本         |
│  | 线索收集           | OCPA   | 按线索优化              |
│  | 预算有限           | Bid Cap| 控制最高出价            |
│  | 追求稳定成本        | Cost Cap| 设定成本上限           |
└──────────────────────────────────────────────────────────────┘
```

---

## 第三部分: 定位系统 (Targeting)

### 3.1 TikTok 定位类型

```
TikTok 定位系统:

1. Location (地理位置):
   ├── 国家/地区/城市/邮编
   ├── 半径定位
   └─ 优势: 比 Meta 更简洁

2. Demographics (人口统计):
   ├── 年龄 (13+)
   ├── 性别
   ├── 语言
   └─ 限制: 比 Meta 少

3. Interests (兴趣):
   ├── 兴趣类别
   ├── 话题标签 (Hashtags)
   ├── 创作者类别
   └─ 优势: TikTok 独有的兴趣体系

4. Behaviors (行为):
   ├── 设备使用
   ├── 应用互动
   └─ 优势: 基于内容消费行为

5. Custom Audience (自定义受众):
   ├── 客户列表 (CRM)
   ├── 网站 Pixel 数据
   ├── 应用数据
   ├── TikTok 互动 (视频观看/主页访问)
   └─ 优势: 直接利用 TikTok 生态数据

6. Lookalike Audience (类似受众):
   ├── 基于种子受众
   ├── 1-10% 相似度
   └─ 适合: 扩量

7. Advantage+ Audience:
   ├── 只提供排除列表
   ├── TikTok 自动优化
   └─ 推荐: 大多数场景
```

---

## 第四部分: 广告格式与创意

### 4.1 TikTok 广告格式

```
TikTok 广告格式:

1. In-Feed Ads (信息流广告):
   ├── 在 For You Feed 中展示
   ├── 15-60 秒视频
   ├── 竖屏 9:16
   ├── 原生感强
   └─ 适用: 大多数场景

2. Spark Ads:
   ├── 引用有机视频
   ├── 原生感最强
   ├── 有机互动 + 付费推广
   └─ 适用: UGC 内容推广

3. Top View (顶视图):
   ├── 用户打开 TikTok 时展示
   ├── 全屏独占
   ├── 最长 60 秒
   └─ 适用: 品牌大事件

4. Brand Takeover (品牌接管):
   ├── 应用启动时展示
   ├── 瞬时曝光
   ├── 6 秒/20 秒
   └─ 适用: 顶级品牌曝光

5. Branded Hashtag Challenge (挑战赛):
   ├── 品牌发起话题挑战
   ├── UGC 参与
   ├── 高互动
   └─ 适用: 品牌活动

6. Branded Effects (品牌特效):
   ├── AR 特效/滤镜
   ├── 用户可使用
   ├── 高互动
   └─ 适用: 品牌互动

7. Branded Stickers (品牌贴纸):
   ├── 用户可在视频中使用
   ├── 轻量级品牌曝光
   └─ 适用: 品牌提示

8. Collection Ads (合集广告):
   ├── 主视频 + 产品网格
   ├── 点击打开落地页
   └─ 适用: 电商

9. Instant Experience (即时体验):
   ├── 全屏沉浸式
   ├── 快速加载
   └─ 适用: 品牌/电商

10. Masthead (头条):
    ├── 首页顶部横幅
    ├── 顶级曝光
    └─ 适用: 顶级品牌活动
```

---

## 第五部分: 转化追踪体系

### 5.1 TikTok 转化追踪

```
TikTok 转化追踪:

1. TikTok Pixel:
   ├── 网页追踪代码
   ├── 标准事件: Purchase/Lead/CompleteRegistration/Subscribe/AddToCart/InitiateCheckout/AddToWishlist/Search/PageView/ViewContent/Contact/Donate/FindLocation/StartTrial/SubmitApplication/Apply/BookTrip/Download/GameStarted/InstallApp/ReachContent/ScheduleEvent/Search/StartTrial/Subscribe/SubmitApplication/Update/ViewContent/Contact
   ├── 自定义事件
   ├── 事件参数: value/currency/content_id/num_items/product
   └─ 安装: 代码/GTM/Partner

2. Conversion API (CAPI):
   ├── 服务器端追踪
   ├── 与 Pixel 互补
   ├── 用户 ID 匹配
   └─ 适合: 电商/高价值转化

3. App Events:
   ├── App SDK 追踪
   ├── 标准应用事件
   └─ 适合: 移动应用

4. Offline Conversions:
   ├── 导入线下转化
   └─ 适合: 零售/服务
```

### 5.2 Pixel 事件

```
TikTok Pixel 标准事件:

┌──────────────────────────────────────────────────────────────┐
│              TikTok Pixel 事件列表                            │
│                                                              │
│  电商:                                                        │
│  ├── view_content — 查看内容                                   │
│  ├── add_to_cart — 加入购物车                                  │
│  ├── add_to_wishlist — 加入愿望单                               │
│  ├── initiate_checkout — 开始结算                              │
│  ├── purchase — 购买                                          │
│  └── search — 搜索                                            │
│                                                              │
│  注册/线索:                                                    │
│  ├── complete_registration — 完成注册                           │
│  ├── subscribe — 订阅                                         │
│  ├── lead — 线索                                             │
│  ├── submit_application — 提交申请                             │
│  └── apply — 申请                                             │
│                                                              │
│  应用:                                                        │
│  ├── install_app — 安装应用                                     │
│  ├── game_started — 开始游戏                                    │
│  └── reach_content — 触达内容                                  │
│                                                              │
│  内容:                                                        │
│  ├── view_content — 查看内容                                   │
│  ├── schedule_event — 预约活动                                  │
│  ├── find_location — 查找地点                                   │
│  └── contact — 联系                                           │
│                                                              │
│  自定义事件:                                                   │
│  └── 用户自定义事件名称                                          │
└──────────────────────────────────────────────────────────────┘
```

---

## 第六部分: 商品 Feed 管理

### 6.1 TikTok Shop / Product Feed

```
TikTok 商品 Feed:

1. Product Feed (商品目录):
   ├── 通过 API/CSV/Partner 同步
   ├── 必需字段: id/title/description/price/image_link/availability
   ├── 可选字段: brand/category/gender/age_group/condition
   └─ 用途: Shopping Ads / Spark Ads / Catalog Ads

2. TikTok Shop:
   ├── TikTok 内电商
   ├── 商品直接在 TikTok 内销售
   ├── 支付/物流/客服一站式
   └─ 适合: 电商卖家

3. Dynamic Product Ads (动态广告):
   ├── 基于 Product Feed
   ├── 自动展示相关产品
   └─ 适用: 电商重定向
```

---

## 第七部分: Spark Ads

### 7.1 Spark Ads 功能

```
Spark Ads 功能:

1. 使用有机视频:
   ├── 选择已有有机视频
   ├── 视频已验证有互动
   └─ 原生感强

2. 推广方式:
   ├── 推广自己的视频
   ├── 推广他人视频 (需要授权)
   └─ 适合: KOL/UGC 内容

3. 优势:
   ├── 无需重新制作视频
   ├── 有机互动证明质量
   ├── 用户信任度高
   └─ 适合: 电商/品牌
```

---

## 第八部分: API 资源映射

```
┌──────────────────────────────────────────────────────────────┐
│              TikTok Marketing API 资源映射                    │
│                                                              │
│  资源              | API 端点                  | 用途       │
│  ├─ Campaign       | /campaigns               | 管理广告系列 │
│  ├─ AdGroup        | /adgroups                | 管理广告组   │
│  ├─ Ad             | /ads                     | 管理广告     │
│  ├─ Creative       | /creatives               | 管理创意     │
│  ├─ Pixel          | /pixels                  | Pixel 管理   │
│  ├─ Event          | /events                  | 发送事件     │
│  ├─ CustomConversion| /customconversions     | 自定义转化   │
│  ├─ ProductFeed    | /productfeeds            | 商品 Feed    │
│  ├─ CustomAudience | /customaudiences         | 自定义受众   │
│  └─ Insights       | /insights                | 获取数据     │
└──────────────────────────────────────────────────────────────┘
```

---

## 第九部分: 账户体系

### 9.1 TikTok 账户结构

```
TikTok 账户体系:

┌──────────────────────────────────────────────────────────────┐
│              TikTok Business Center                           │
│                                                              │
│  Business Center (商务中心)                                     │
│  ├── 广告账户 (Ad Accounts)                                   │
│  │   └─ 可多个 (不同客户/品牌)                                 │
│  ├── Pixel                                                    │
│  ├── Product Catalog (商品目录)                                │
│  ├── 团队成员 (Users)                                         │
│  ├── API Access (API 访问)                                    │
│  ├── TikTok Shop (电商)                                       │
│  └─ 品牌安全设置                                               │
└──────────────────────────────────────────────────────────────┘
```

---

## 自测题

### 问题 1
TikTok 有多少种广告系列目标？

<details>
<summary>查看答案</summary>

6 种: Traffic, Conversions, App Engagement, Video Views, Brand Awareness, Store Traffic, Lead Generation
</details>

### 问题 2
Spark Ads 的核心优势是什么？

<details>
<summary>查看答案</summary>

- 使用已有的有机视频,无需重新制作
- 有机互动证明内容质量
- 原生感强,用户信任度高
- 有机互动 + 付费推广 = 放大效果
</details>

### 问题 3
TikTok Pixel 有哪些标准事件？

<details>
<summary>查看答案</summary>

Purchase, Lead, AddToCart, InitiateCheckout, CompleteRegistration, ViewContent, Search, Subscribe, InstallApp, StartTrial 等
</details>

---

*今天花 90 分钟：系统掌握 TikTok Ads 平台功能体系*
*答不出自测题？回去重读对应章节。*

```go
package tiktokads

import (
	"fmt"
	"sync"
)

type ProductType string
const (
	ProductVideo ProductType = "VIDEO"
	ProductCollection ProductType = "COLLECTION"
	ProductStandard ProductType = "STANDARD"
)

type Campaign struct {
	ID            string
	Name          string
	Objective     string
	PromotionType ProductType
	DailyBudget   float64
	Status        string
}

type Creative struct {
	ID       string
	VideoURL string
	Headline string
	CTA      string
}

type TikTokAdsManager struct {
	mu        sync.Mutex
	campaigns map[string]*Campaign
}

func (m *TikTokAdsManager) CreateCampaign(name, obj string, budget float64) *Campaign {
	m.mu.Lock()
	defer m.mu.Unlock()
	cp := &Campaign{ID: fmt.Sprintf("camp_%d", len(m.campaigns)), Name: name,
		Objective: obj, DailyBudget: budget, Status: "ENABLED"}
	m.campaigns[cp.ID] = cp
	return cp
}

func (m *TikTokAdsManager) GetCampaigns() []*Campaign {
	m.mu.Lock()
	defer m.mu.Unlock()
	result := make([]*Campaign, 0, len(m.campaigns))
	for _, cp := range m.campaigns { result = append(result, cp) }
	return result
}

func main() {
	m := &TikTokAdsManager{campaigns: make(map[string]*Campaign)}
	cp := m.CreateCampaign("Summer Sale", "VIDEO", 100.0)
	fmt.Printf("Created: %s (%s)
", cp.Name, cp.Status)
}

