# Google Ads App 广告完整指南：UA、App Events、Install Attribution、ASO

> **领域**: 广告投放 / GOOGLE_ADS
> **深度**: ⭐⭐⭐⭐⭐ 实战级指南
> **标签**: GOOGLE_ADS, 广告投放
> **更新时间**: 2026-08-14
> **类型**: 深度知识文档

---

# 文档定位与阅读导览

本文件是 Ryan 个人知识库中针对 **Google Ads App 广告（App Campaigns / UAC）** 的全方位实战指南。

它覆盖从 **用户获取（UA）**、**App 事件追踪（App Events）**、**安装归因（Install Attribution）**、
**SKAdNetwork 一致性** 到 **ASO（应用商店优化）** 的完整链路。

全文档围绕三个可以回答的核心问题展开：

1. 如何用 App Campaigns 稳定、可扩展地买量（UA）？
2. 如何正确地设置转化事件、选择数据源、校准归因，让智能出价真正“看得见”价值？
3. 当投放量级已经上来后，如何通过诊断、频控、ASO 联动去守住 ROAS 并持续放大？

写作对象是**有投放后台操作经验、但需要系统化理解 App 广告机械原理的增长团队与代理商优化师**。

文档中出现的 API 示例均基于 `scripts/google_ads_api.py` 中真实可调用的方法。

```text
google_ads_api.py 核心方法清单（本文代码均使用这些方法）
--------------------------------------------------------------------
search(customer_id, query)                  GAQL 查询
list_campaigns / get_campaign               读取广告系列
create_campaign / update_campaign           创建 / 更新广告系列
pause_campaign / resume_campaign            暂停 / 恢复
delete_campaign                             删除
list_ad_groups / create_ad_group            广告组
update_ad_group / pause_ad_group            暂停恢复广告组
create_keywords / list_keywords             关键词（App 广告诉求较弱，仅参考）
list_ads / create_ad / update_ad            广告与更新
list_conversion_actions / create_conversion_action  转化行为
list_bid_strategies / get_bid_suggestion    出价策略与建议
generate_report(customer_id, date_range)    报表数据
get_campaign_type_options / get_bid_strategy_options / get_asset_type_options  选项元数据
端点: https://googleads.googleapis.com/v24
认证头: Authorization Bearer + developer-token + login-customer-id
--------------------------------------------------------------------
```

> **与既有文档的边界**
> 本文与 `google-ads-display-video-shopping-app-deep.md` 中的 App 泛型章节互补。
> 那篇讲 App 广告的“是什么”与基础创建流程，本文只深入 App 领域特有机制：
> App Events、Install Attribution、SKAdNetwork、ASO 联动、事件漏斗出价。
> 泛决策不重复展开，可互为交叉引用。

---

## 一、核心概念与架构

### 1.1 什么是 App 广告系列（UAC / App Campaigns）

App 广告系列（App Campaigns）是 Google 面向移动应用推广的**全自动广告产品**。

它把过去分散在搜索、展示、YouTube、Discover、Google Play 商店（标注为“推荐”）的
流量位统一交给机器去分配，优化师只需要：

- 选择**终极目标**（安装 / 应用内事件 / 预注册）；
- 上传**文字、图片、视频、HTML5** 等素材；
- 设定**目标出价与预算**。

系统会根据这些输入自动生成海量广告组合，并在全流量位实时竞价。

这是典型的 **“素材进、结果出”** 的黑盒式机器学习产品。

理解它的第一性认知是：**优化师不再控制关键词、受众、版位，而是控制“目标和信号”**。

```text
传统搜索广告 vs App 广告系列的职责边界
--------------------------------------------------------------------
传统 AdWords / PMax(网站)          App Campaigns (UAC)
优化师: 关键词/受众/出价/文案        优化师: 目标/素材/出价/预算/事件
关键词定向                 ⇢        Play 商店 + 应用信号定向
受众列表                   ⇢        Auto Audience（自动受众）
手动 CPC                  ⇢        tCPA / tROAS 自动出价
落地页                     ⇢        应用安装/ Deep Link
逐次点击归因               ⇢        install attribution + DDA
--------------------------------------------------------------------
```

UAC 看似“黑盒”，但黑盒不等于“不可控”。

你可以通过**事件选择、出价策略、预算结构、素材质量、数据源选择**这五个旋钮，
把机器的优化方向引导到你想要的商业结果上。

这也是本指南的核心方法论：**不直接拧螺丝（定向），而是设计好信号与约束来“喂”机器**。

### 1.2 三种终极目标：安装 / 应用内事件 / 预注册

Google Ads 为 App 广告系列定义了三种**目标（Objective）**。

目标直接决定系统优化什么、用什么信号做机器学习、以及展示的版位形态。

下面是三种目标的核心表（本文件多处会引用此表）。

| 目标类型 | 英文 | 适用产品 | 出价方式 | 主要信号 |
| -------- | ---- | -------- | -------- | -------- |
| 应用安装推广 | App installs | 一切想快速拿量的产品 | tCPI / tCPA | 安装事件 |
| 应用互动推广 | App engagement | 已起量、需回访/留存的产品 | tCPA（事件） | 指定应用内事件 |
| 应用预订推广 | App pre-registration | 尚未上架的预约游戏/应用 | tCPI | 预约人数 |

三种目标并不互斥，产品生命周期不同阶段会切换主用目标。

例如一款新游戏上线首月用 `App installs` 抢量，跑稳后切到 `App engagement` 去优化首日留存
与内购事件，上架预约期则可能先用 `pre-registration` 提前蓄水。

#### 1.2.1 应用安装推广（App installs）

最经典、最基础的 UAC 目标。

系统优化的是“安装”这一动作，出价通常表达为目标每次安装费用（tCPI）。

适合：

- 新产品冷启动，尚未有足够转化数据；
- 买量偏“量”而非“质”，先建立用户基数；
- 付费安装（CPI Campaign）对冲自然量、抢榜、冲热玩榜。

需要注意：**只优化安装，往往带来的是低质、低留存的用户**。

因为安装是最浅层的转化信号，机器会倾向于用最低成本拉最大量，而入量质量未必高。

#### 1.2.2 应用互动推广（App engagement）

这是**大部分成熟产品的默认首选**。

系统不再只看安装，而是优化你指定的**应用内事件（如 Purchase、Level Complete、Tutorial Done）**。

出价表达为目标每次转化费用（tCPA），ROI 由事件价值决定。

适合：

- 已积累足够安装/事件数据的产品；
- IAP / 电商 / 工具类产品，关注付费或核心行为；
- 需要把 ROAS 或 LT 价值做到可衡量的阶段。

**这是本指南推荐的“跑量主模式”**，因为它让机器直接对着商业价值优化。

#### 1.2.3 应用预订推广（App pre-registration）

针对尚未在应用商店上架（或着准备上架）的产品。

用户在 Google Play 上“预约”，上架后自动安装。

适合：

- 知名 IP 续作、大厂新游的蓄水；
- 提前锁定核心用户，降低正式上线后的获客压力；
- 在 Play 商店创造“预约人数”的榜单效应。

需要注意预约的用户量有限，且预约完成后系统会优化“完成预约”这个动作，
无法保证上架后这些用户一定会成为活跃/付费用户。

### 1.3 App Campaigns 与 PMax 的关系（重要概念）

很多优化师会困惑：PMax（Performance Max）和 UAC 是什么关系？

答案：PMax 是“更泛的自动化广告产品”，UAC 是 App 场景的专属形态。

在 API 层面，两者都以 **asset_group** 为单位组织素材，都以机器自动化为核心。

具体到广告系列子类型（advertising_channel_sub_type），App 广告系列有一套专属枚举，
与网站型 PMax 明显不同。

```text
advertising_channel_sub_type 枚举对照（GAQL 中 campaign 维度字段）
--------------------------------------------------------------------
PERFORMANCE_MAX_FOR_GOALS               PMax（通用目标）
PERFORMANCE_MAX_FOR_TRAVEL_GOALS        PMax（旅游）
SHOPPING_GOALS                          PMax（购物）
PERFORMANCE_MAX_FOR_ANDROID_APPS        PMax（安卓 App 场景）
APP_CAMPAIGN                            App 广告系列（传统 UAC）
--------------------------------------------------------------------
```

从产品演化看：

- 传统 **UAC（APP_CAMPAIGN）** 已经运行多年，稳定可靠；
- Google 正在把 **App 场景逐步收敛进 PMax（PERFORMANCE_MAX_FOR_ANDROID_APPS）**，
  让 iOS 与 Android 一起在更统一的产品形态里跑。

对优化师的实际影响：

- 创建新 App 系列时，某些账户会看到“App campaigns for Android apps”被重命名为 PMax 形态；
- 本质不变：都是素材 + 目标 + 出价 + 预算的自动化优化器；
- 本文讨论的原理与操作对两者都成立。

### 1.4 系统总体架构图

下面用 ASCII 架构图展示 App 广告系列从输入到输出、再到归因回传的完整链路。

这是理解全文件（尤其归因与事件回传部分）的地图。

```text
                    ┌───────────────────────────────────────────────────┐
                    │           广告主 / 优化师                          │
                    │  目标(安装/事件/预注册) + 素材 + 出价 + 预算        │
                    └───────────────┬───────────────────────────────────┘
                                    │  (API create_campaign / 素材上传)
                                    ▼
        ┌───────────────────────────────────────────────┐
        │            Google Ads 机器学习出价引擎           │
        │   (tCPA / tROAS / MAXIMIZE_CONVERSIONS ...)    │
        └───────┬───────────────────────┬───────────────┘
                │                       │
   ┌────────────▼───────────┐   ┌───────▼──────────────────────┐
   │   流量位 / Inventory     │   │  归因与数据源                  │
   │  Search │ Display       │   │  Google Play / App Store     │
   │  YouTube│ Discover      │   │  GAFB(Firebase) / GA4       │
   │  Gmail  │ Play Store    │   │  MMP(AppsFlyer/Adjust/Sing) │
   └────────────┬───────────┘   │  SKAdNetwork(SKAN) 4.x       │
                │               └───────┬──────────────────────┘
                ▼                       │
        ┌───────────────────────────────▼───────────────────────┐
        │            用户设备 / App 内                            │
        │  安装 → 启动 → 注册 → 完成教程 → 付费 / 留存              │
        └───────────────────────┬───────────────────────────────┘
                                │  事件回传 (Conversion / MMP postback)
                                ▼
        ┌───────────────────────────────────────────────┐
        │  转化行为 conversion_action + 事件价值回传       │
        │  → 机器学习持续学习 → 优化出价 → 循环 (DDA)       │
        └───────────────────────────────────────────────┘
```

把这张图记住，后面所有章节都围绕其中的一条或多条链路展开：

- **出价链路**：目标 + 预算 + 事件 → 机器学习 → 出价；
- **归因链路**：数据源（GAFB/GA4/MMP/SKAN）→ 安装归因 → 转化回传；
- **素材链路**：素材上传 → 资产自动组合 → 展示 → A/B。

### 1.5 关键术语速查

进入深度章节前，先建立统一的术语表。

| 术语 | 全称 / 解释 | 备注 |
| ---- | ----------- | ---- |
| UA | User Acquisition，用户获取 | 买量获客的统称 |
| UAC | Universal App Campaigns，App 广告系列 | 本文主角 |
| tCPI | target Cost Per Install，目标每次安装成本 | 安装目标的出价 |
| tCPA | target Cost Per Action，目标每次转化成本 | 事件目标出价 |
| tROAS | target Return On Ad Spend，目标广告支出回报率 | 价值型出价 |
| CPI | Cost Per Install，每次安装成本 | 安装买量口径 |
| CPA | Cost Per Action，每次转化成本 | 事件买量口径 |
| ROAS | Return On Ad Spend，广告支出回报 | 收入/花费 |
| LTV / LT | Lifetime Value，用户生命周期价值 | 评估用户质量 |
| D7 / D30 | 7日 / 30日留存 | 常用留存口径 |
| GAFB | Google Analytics for Firebase | Google 归因方案之一 |
| GA4 | Google Analytics 4 | 含 Firebase 事件 |
| MMP | Mobile Measurement Partner，移动归因方 | AppsFlyer/Adjust/Singular |
| SKAN | SKAdNetwork，苹果私密归因 | iOS 归因 |
| DDA | Data-Driven Attribution，数据驱动归因 | 模型化归因 |
| ASO | App Store Optimization，应用商店优化 | 元数据/评分优化 |
| Asset Group | 资产组 | App 广告的素材组织单位 |
| IAP | In-App Purchase，应用内购买 | 变现来源 |
| eCPI | effective CPI，有效安装成本 | 事件归因到安装 |
| DPI | Deep Link / URI scheme | 跳转深度链接 |

后面章节出现这些词不再重复解释。

---

## 二、深度原理解析

本章是全文最“硬核”的部分，讲清楚 App 广告背后的三种关键机制：

1. **App 事件（App Events）** 与转化上报；
2. **安装归因（Install Attribution）** 与数据源；
3. **SKAdNetwork 一致性与数据中心化**。

理解这些机制，是正确设置 UAC、并能解释“为什么转化忽高忽低”的基础。

### 2.1 App 事件（App Events）：转化信号的来源

#### 2.1.1 什么是 App 事件

App 事件是指在 App 内发生、且被 SDK 上报到某个归因/分析平台的“用户动作”。

典型事件包括：

- `first_open`（首次启动，通常等同安装信号）
- `session_start`
- `tutorial_complete`（完成新手教程）
- `registration`（完成注册）
- `add_to_cart`（加入购物车）
- `purchase`（完成购买，需带金额）
- `level_complete`（游戏过关）
- `spend_virtual_currency`（消耗虚拟货币）

这些事件本身是“数字信号”，但谷歌要用它们做优化，必须满足两个前提：

1. 事件能稳定、低延迟地上报到 Google（conversion tracking）；
2. 事件在归因窗内与一次广告点击/曝光建立关联。

只有当事件回传成功，机器学习才能把它当作转化信号来学习。

#### 2.1.2 事件有两类：可出价事件 vs 计数/参考事件

这一点对优化师极其重要，因为很多人在后台找不到“为什么某事件不能设成转化”。

Google 把事件大致分为两类：

| 事件类别 | 说明 | 能否直接做出价目标 |
| -------- | ---- | ---------------- |
| 可出价转化事件 | 被配置为 conversion_action 的事件 | 是 |
| 计数 / 参考事件 | 只统计、不参与出价 | 否（除非提升为转化） |

例如 `purchase`、`registration` 这类核心动作被设为转化后，系统直接优化它们。

而 `level_start`、`tutorial_view` 这类频次高但商业价值低的事件，通常只做数据参考，
不直接进入出价优化集合。

> **实操建议**
> 不要把所有事件都设成转化。转化标签越多、越杂，机器学习信号越不纯净。
> 一般建议核心业务事件保持在 1-3 个，其余用参考事件观测漏斗。

#### 2.1.3 事件如何在 Google Ads 中成为转化

事件要变成“转化”并被 tCPA 优化，需要一条链路。

在 API 层，对应的方法是 `create_conversion_action` 与 `list_conversion_actions`。

一个转化行为（conversion_action）有几个关键属性，直接影响归因与优化：

| 属性 | 含义 | 对 UAC 的影响 |
| ---- | ---- | ------------ |
| type | 转化类型（APP_INSTALL / IN_STORE / ...） | 决定归类 |
| attribution_model | 归因模型（LAST_CLICK / DDA 等） | 影响口径 |
| category | 类别（PURCHASE / SIGNUP / ...） | 报表归类 |
| value | 是否带价值（value_setting） | tROAS 需要 |
| status | ENABLED / PAUSED | 是否参与优化 |

下面用 `list_conversion_actions` 读取当前账户已配置的转化行为。

```python
# -*- coding: utf-8 -*-
"""
读取账户已配置的转化行为（App 事件 → conversion_action）。
对应 scripts/google_ads_api.py 的 list_conversion_actions。
"""
from google_ads_api import GoogleAdsClient

def load_credentials():
    # 从你的凭证存储读取 google_ads 配置
    return {
        'google_ads': {
            'developer_token': 'DEVELOPER_TOKEN',
            'login_customer_id': '1234567890',
            'access_token': 'ACCESS_TOKEN',
        }
    }

client = GoogleAdsClient(load_credentials())
customer_id = '1234567890'

resp = client.list_conversion_actions(customer_id)
if not resp.success:
    print('读取失败:', resp.error)
    raise SystemExit(1)

print('账户内转化行为:')
for row in resp.data.get('results', []):
    ca = row.get('conversion_action', {})
    print(
        f"  id={ca.get('id')} "
        f"name={ca.get('name')} "
        f"type={ca.get('type')} "
        f"status={ca.get('status')}"
    )
```

这段代码解决的真实问题：

- 在调整 UAC 出价前，先确认目标转化事件是否**已启用**；
- 确认事件是否**带价值**（value），因为 tROAS 依赖价值；
- 排查“为什么某事件优化不了”——往往是因为根本没有配置成转化。

#### 2.1.4 事件漏斗与“优化集合”设计

UAC 的优化本质是**事件漏斗优化**。

一次用户旅程大致是：

```text
展示 → 点击 → 安装 → 首次启动 → 注册/教程 → 深度行为(付费/留存)
 |      |       |        |           |            |
曝光率   点击率   安装率    启动率       转化率        价值
 CTR     CVR      DVCR     ...
```

系统在一个转化窗（默认多为 7 天点击 / 1 天浏览）内，把所有信号串联起来。

你**选哪个事件作为终极目标**，决定了机器为“哪个漏斗终点”服务。

设计原则：

- **单一主目标**：选一个最能代表商业价值的动作（如 Purchase 或付费留存）；
- **辅以观测事件**：把漏斗中间环节（注册、教程完成）作为参考，看转化卡点；
- **分漏斗实验**：如果你有两个强事件（如内购 + 广告变现），可以考虑分层建系列。

### 2.2 数据源：GAFB(Firebase) / GA4 与第三方 MMP

#### 2.2.1 为什么“选择数据源”会如此影响结果

App 广告与网站广告最大的差异之一是：**安装发生在外部的应用商店，归因依赖 SDK 与商店回执**。

这带来一个根本性的选择：**用 Google 自己的数据（GAFB / GA4），还是用第三方 MMP**。

这个选择直接决定：

- 转化事件以谁的回传为准；
- 同一批安装/事件在报表里计数是否一致；
- 智能出价读到的是哪一路“变现价值”。

所以本文把“数据源选择”列为与“出价与预算”并列的核心旋钮。

#### 2.2.2 各大数据源特点

| 数据源 | 归属 | 事件来源 | 优势 | 注意点 |
| ------ | ---- | ---- | ---- | ---- |
| Google Analytics for Firebase (GAFB) | Google | Firebase SDK 事件 | 与 Google Ads 原生打通、实时性好 | 需接入 Firebase |
| GA4 | Google | GA4 + Firebase 事件 | 统一分析 + 广告归因 | 与 Google Ads 联通 |
| AppsFlyer | 第三方 MMP | AppsFlyer SDK 事件 | 多平台统一、可仲裁 | 需回传配置 |
| Adjust | 第三方 MMP | Adjust SDK 事件 | 多平台统一 | 需回传配置 |
| Singular | 第三方 MMP | Singular SDK 事件 | 服务重客 | 需回传配置 |

从“归因仲裁”看，Google 通常建议 **Google 自己的数据源（GAFB/GA4）** 作为 Ads 内转化来源，
因为它最原生、延迟最低、与出价引擎衔接最顺。

但很多有独立 BI 的增长团队用 MMP 做统一口径。此时要在两者间做**校准**。

#### 2.2.3 用代码查看转化行为的来源/团长

在 Google Ads 中，一个转化行为对应一个“团长（conversion source / event_group）”。

它是数据源维度。读取时可以从 `conversion_action` 之外再拉取外部归因字段。
下面用 `search` 拉取转化行为与其来源信息。

```python
# -*- coding: utf-8 -*-
"""
查看转化行为的来源类型与归因数据源。
GAQL 示例来自 google_ads_api.py 的 search 方法。
"""
from google_ads_api import GoogleAdsClient

client = GoogleAdsClient({...})
customer_id = '1234567890'

query = """
SELECT
  conversion_action.id,
  conversion_action.name,
  conversion_action.type,
  conversion_action.category,
  conversion_action.attribution_model_settings.attribution_model,
  conversion_action.status
FROM conversion_action
WHERE conversion_action.status = 'ENABLED'
"""

resp = client.search(customer_id, query)
for row in resp.data.get('results', []):
    ca = row.get('conversion_action', {})
    print({
        'id': ca.get('id'),
        'name': ca.get('name'),
        'type': ca.get('type'),
        'category': ca.get('category'),
        'attribution_model': ca.get(
            'attribution_model_settings', {}).get('attribution_model'),
        'status': ca.get('status'),
    })
```

#### 2.2.4 数据中心化：让 Google 出价看到正确的价值

很多优化的第一个坎是“价值错位”：

- Ads 报表里 ROAS 很好看，但业务财务 ROAS 很差；
- 原因是归因口径与变现价值没有对齐到 Google 出价引擎。

要做到对齐，关键动作是**把每次安装/事件的价值回传成 Google 能用的“转化价值”**。

例如电商 App，应把 `purchase` 事件带上 `value`（客单价）与 `currency`。

这样 tROAS / MAXIMIZE_CONVERSION_VALUE 才有正确的优化依据。

下面展示如何拉取“带价值的转化”指标来核对价值是否回传。

```python
# -*- coding: utf-8 -*-
"""
核对转化价值回传是否正常。
用到 generate_report 的同类 GAQL（此处给出更完整版本）。
"""
from google_ads_api import GoogleAdsClient

client = GoogleAdsClient({...})
customer_id = '1234567890'
date_range = {'start': '2026-08-01', 'end': '2026-08-07'}

query = f"""
SELECT
  campaign.name,
  metrics.cost_micros,
  metrics.conversions,
  metrics.conversions_value,
  metrics.all_conversions,
  metrics.all_conversions_value,
  metrics.cost_per_conversion
FROM campaign
WHERE segments.date BETWEEN '{date_range['start']}' AND '{date_range['end']}'
  AND campaign.advertising_channel_type = 'MULTI_CHANNEL'
ORDER BY metrics.cost_micros DESC
"""

resp = client.search(customer_id, query)
print(f"{'campaign':<28}{'cost_$':>10}{'conv':>8}{'value_$':>12}{'CPA_$':>10}")
for row in resp.data.get('results', []):
    c = row.get('campaign', {})
    m = row.get('metrics', {})
    name = c.get('name', '')[ :26]
    cost = m.get('cost_micros', 0) / 1_000_000
    conv = m.get('conversions', 0)
    val = m.get('conversions_value', 0) / 1_000_000
    cpa = m.get('cost_per_conversion', 0) / 1_000_000
    print(f"{name:<28}{cost:>10.2f}{conv:>8.1f}{val:>12.2f}{cpa:>10.2f}")
```

当 `all_conversions_value` 远大于 `conversions_value` 时，通常说明：

- 某些价值只计入“全部转化”，未进入“出价转化”；
- 或存在 cross-device / 未登录归因的误差。

需要回到转化行为设置，检查 value 与 attribution 口径。

### 2.3 安装归因（Install Attribution）深度

#### 2.3.1 一次“安装”是如何归因到广告的

一次安装的过程，在广告侧大致是这样：

```text
用户看到广告 (impression) ──► 点击 (click) ──► 跳转应用商店
      │                                 │
      │  曝光归因(浏览, 1天窗)           │  点击归因(多为 7 天窗)
      ▼                                 ▼
   归因窗口判定                  归因窗口判定
              │
              ▼
  记录一次安装 install attributed to ad
              │
              ▼
  install → first_open 事件回传 Google / MMP
```

归因的本质是：**在设定好的时间窗内，把这个“安装的功劳”记到某一次广告互动上**。

#### 2.3.2 归因窗口与模型

| 归因维度 | 默认值 | 说明 |
| -------- | ------ | ---- |
| 点击归因窗 | 通常 7 天 | 点击后 7 天内安装计入 |
| 浏览归因窗 | 通常 1 天 | 曝光后 1 天内安装计入 |
| 归因模型 | LAST_CLICK / FIRST_CLICK / DDA | 功劳分配方式 |
| 数据驱动归因 DDA | 模型化分配 | 更适合多触点 |

**难点在于归因窗影响“计数质量”**：

- 窗口太长 → 计入过多“自然/来迟”的安装，稀释广告真实效果；
- 窗口太短 → 漏掉真实转化，低估广告价值。

不同行业有不同合理窗，例如游戏重付费用户可能用更长留存窗，
工具类轻产品用较短转化窗，避免长期记账影响节奏判断。

#### 2.3.3 GA4 / GAFB 与 MMP 的归因差异

这是增长团队最常见的一个争论点。下表给出它们的一致性差异。

| 维度 | Google (GAFB/GA4) | 第三方 MMP | 差异原因 |
| ---- | ----------------- | ---------- | -------- |
| 安装数 | 以 Google 归因引擎 | 以 MMP 归因引擎 | 数据源不同 |
| 点击归因窗 | 可配置 | 可配置 | 配置不完全一致 |
| 浏览归因窗 | 可配置 | 可配置 | 同上 |
| 去重逻辑 | Google 内部去重 | MMP 跨渠道去重 | 去重口径不同 |
| 未安装归因 | 支持 | 依赖 SDK | 采集方式不同 |
| SKAN 处理 | Google 转发 SKAN | MMP 直接收 SKAN | 链路不同 |

**一致性差的根源**：

- 归因引擎判定的“最后一次点击”可能不同；
- 浏览归因与去重的优先级不同；
- SKAN 缺失时各自的估算方法不同。

#### 2.3.4 如何让两套数据基本对齐

要让 Google 与 MMP 数字大致一致，建议：

1. 统一归因窗口径（都设 7 天点击 / 1 天浏览）；
2. 统一去重策略；
3. 以一套为“计帐口径”、另一套为“观测口径”，不要混用；
4. 关注趋势而非绝对值：短周期波动看相对变化，跨周看累计校准。

> **经验法则**
> 不要试图让 Google 内部转化数与 MMP 完全相等。它们逻辑不同。
> 关键是**趋势一致 + 长期累计差距稳定**。若长期差距持续扩大或方向相反，才需要排查。

### 2.4 SKAdNetwork（SKAN）一致性

#### 2.4.1 为什么 iOS 归因如此特殊

Apple 的隐私政策（ATT / IDFA 受限）使 iOS 上无法稳定获得设备级 IDFA 归因。

Google 与 MMP 都必须依赖 **Apple 的 SKAdNetwork（SKAN）** 作为主归因通道。

SKAN 的本质是**私密、汇总、延迟、有噪声**的归因协议：

- 归因由 Apple 在设备端匿名计算；
- 结果以 **观察（postback）** 形式由 SKAdNetwork 派发给广告网络与 MMP；
- 曝光先到、转化后到，具有**随机延迟（通常 24-48 小时）**；
- 数值带**隐私噪声（privacy threshold）**，单次数据不准。

```text
SKAN 4.x 归因流程
--------------------------------------------------------------------
广告展示 (source app → ad network)   ← 早期通知
用户点击跳转 App Store → 安装 → 漏斗内行为
App 在 0-24h 随机窗口 (≥5s 触发) 发送 postback
postback 带: 转化值(6bit/分层) + 来源ID + 金额分层
Apple/SKAdNetwork 汇总 → 分发给 Google / MMP
--------------------------------------------------------------------
```

#### 2.4.2 SKAN 与数据中心化的落地

因为 SKAN 是主归因通道，所以 **Google 与 MMP 都会用 SKAN 数据校准**。

但 SKAN 有随机延迟 + 噪声，直接导致：

- iOS 报表比 Android 更晚、更“锯齿状”；
- 单日数据不可靠，必须累计到 3-7 天以上再看；
- tCPA/tROAS 在 iOS 上的学习节奏更慢。

**实操对策**：

- iOS 与 Android **分开建系列**，避免噪声相互污染；
- iOS 系列用更长观察窗（7 日以上）与更稳健的出价；
- 用 MMP 的 SKAN 面板与 Google 的 SKAN 数据交叉核对安装量级与转化分布。

#### 2.4.3 SKAN 差异排查要点

当 Google 内与 MMP 的 iOS 安装数明显不一致时，按以下顺序排查：

1. 是否都用 SKAN 无 IDFA/IDFA 混合模式；
2. 时间窗是否一致（postback 延迟导致错位）；
3. privacy threshold 是否导致小事件被丢弃；
4. source app / ad network 过滤是否一致。

> **黄金经验**
> SKAN 场景下，与其纠结“差几个安装”，不如盯住**转化分布（conversion value *distribution*）**。
> 分布形状稳定，说明漏斗健康；分布漂移，说明转化结构在变化。

### 2.5 DDA 与机器学习信号的可信度

#### 2.5.1 数据驱动归因（DDA）在 App 场景的作用

Google Ads 的智能出价并不只看“最后一次点击”，而是用**数据驱动归因（DDA）**，
在多个触点间按模型分配功劳。

对 App 广告这种多触点、多版位的场景，DDA 比单一 last-click 更接近真实贡献。

```text
       触点A(展示)    触点B(点击)    触点C(点击)     安装
          │            │            │               │
          │    DDA 模型根据行为/上下文分配功劳        │
          ▼            ▼            ▼               ▼
        0.2          0.5          0.3            (合计 1.0)
```

DDA 的好处是让出价引擎“看得见”每个触点的边际贡献，
坏处是模型可能随流量变化而漂移，需要持续观测。

#### 2.5.2 信号是优化的一切

App 广告的机器学习本质上是对“信号 → 出价”的学习。

信号可信度决定了优化的天花板。

```text
信号可信度金字塔
--------------------------------------------------------------------
        高可信
          │   带价值的核心事件 (purchase with value)
          │   付费留存 / 深度行为
          │   注册/教程完成 (中量)
          │   安装 / 启动 (量最大但质浅)
        低可信
--------------------------------------------------------------------
```

- **信号越偏商业价值** → 优化质量越高，但量可能受限于事件频率；
- **信号越浅（安装）** → 量越大，但用户质量越不稳。

这就是为什么“跑安装目标”容易起量却难保证 ROAS，
而“跑付费事件”ROAS 更稳但起量更慢。

优化师要在“学习速度”与“信号质量”之间做平衡，通常用**多层级系列的预算结构**来解决。

今明两章会把这些设计原则落成可执行的生产配置。
