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

---

## 三、生产环境实战

第三章把前面讲的机制落成**真实业务场景 + 量化指标 + 可运行代码**。

我们用一个贯穿性的案例主线：**一家出海手游公司的 UAC 月预算 $100K 优化事件组合**。

并穿插电商、APP 增长、代理商、品牌、直播带货等场景，
让不同业务的读者都能找到可直接套用的操作模板。

### 3.1 贯穿案例：游戏公司 UAC 月预算 $100K

#### 3.1.1 背景与目标

假设我们是一家做中重度 RPG 出海的手游公司，产品叫《Rift Saga》。

现状要素：

| 维度 | 数值 |
| ---- | ---- |
| UAC 月预算 | $100,000 |
| 目标市场 | 北美 / 欧洲 / 东南亚 |
| 变现模式 | IAP（内购）+ 少量广告变现 |
| 核心事件 | install → tutorial_done → purchase |
| 主出价目标 | 付费留存与 IAP 收入 |
| 当前 CPI | ~$3.2 |
| 目标 tCPA（首购） | ~$28 |
| 目标 30 日 ROAS | ≥ 120% |
| 关键漏斗 | 安装 → 注册 → 教程 → 首购 |

我们的任务是把这 $100K 的月预算，从“只买安装”升级为
“事件漏斗驱动的分层买量”，并让 ROAS 稳定在 120% 以上。

#### 3.1.2 分层预算与系列结构设计

单靠一个 UAC 系列很难同时满足“冲量”与“保 ROAS”。

行业通用做法是**按目标分层建系列**，让不同信号目标各司其职。

下面是一个针对 $100K 月预算的推荐结构：

| 系列 | 目标 | 预算占比 | 月预算 | 主出价 | 作用 |
| ---- | ---- | -------- | ------ | ------ | ---- |
| UAC-Installs（安装冲量） | App installs | 30% | $30K | tCPI | 建立量级与学习 |
| UAC-Engage-Purchase（首购优化） | App engagement | 50% | $50K | tCPA | 主 ROAS 引擎 |
| UAC-Pmax-ROAS（价值优化） | App engagement(价值) | 20% | $20K | tROAS | 守住高价值用户 |

分层逻辑：

- **安装系列**负责在有限预算内快速拉新，喂给上层漏斗；
- **首购 tCPA 系列**是主力，直接对着 `purchase` 事件优化，稳定 ROAS；
- **tROAS 系列**守高价值，防止量级扩张时质量滑坡。

三层配合，既能起量，又能兜底商业价值。

#### 3.1.3 事件组合与出价目标的量化设计

事件组合不是越多越好，而是“主事件 + 辅助观测事件”的组合。

对《Rift Saga》，我们推荐如下事件策略：

| 事件 | 角色 | 出价口径 | 目标值 |
| ---- | ---- | -------- | ------ |
| install | 观测/冲量 | tCPI | $3.2 |
| tutorial_done | 参考事件 | 不参与出价 | 教程完成率 ≥ 55% |
| first_purchase | 主转化 | tCPA | $28 |
| 首日付费 | 主转化（带价值） | tROAS | 120% |

量化诊断口径（PPI = 付费安装渗透率）常被用来判断买量质量：

```text
PPI 渗透率 = 统计期内付费安装数 / 总安装数
示例: 100 安装中 22 个在 D7 内付费 → PPI = 22%
```

如果 PPI < 15%，说明买量质量偏浅，需要把更多预算倾向 tCPA 系列。

#### 3.1.4 用代码创建分层 UAC 系列

下面用 `google_ads_api.py` 的 `create_campaign` 创建三个分层系列。
App 广告系列的创建在 API 侧体现为 `advertising_channel_sub_type = APP_CAMPAIGN`，
并携带目标（advertising_channel_type = MULTI_CHANNEL + app campaign 设置）。

```python
# -*- coding: utf-8 -*-
"""
创建分层 UAC 系列：安装冲量 / 首购 tCPA / tROAS 价值。
对应 scripts/google_ads_api.py 的 create_campaign。
"""
from google_ads_api import GoogleAdsClient

client = GoogleAdsClient({...})
customer_id = '1234567890'

def make_app_install_campaign(name, daily_budget_micros, target_cpi_micros):
    """安装目标 tCPI 系列。"""
    return {
        'name': name,
        'advertising_channel_type': 'MULTI_CHANNEL',
        'advertising_channel_sub_type': 'APP_CAMPAIGN',
        'status': 'PAUSED',   # 先穿建为暂停，配好素材再启用
        'campaign_budget': {'amount_micros': daily_budget_micros},
        'app_campaign_setting': {
            'app_id': 'com.rift.saga',
            'app_vendor': 'GOOGLE_APP_STORE',
            'bidding_strategy_goal_type': 'OPTIMIZE_INSTALLS_TARGET_INSTALL_COST',
        },
        'target_cpa': {'target_cpa_micros': target_cpi_micros},
        'optimization_goal_type': ['OPTIMIZE_INSTALLS'],
    }

def make_app_engagement_campaign(name, daily_budget_micros, target_cpa_micros):
    """应用内事件 tCPA 系列（主 ROAS 引擎）。"""
    return {
        'name': name,
        'advertising_channel_type': 'MULTI_CHANNEL',
        'advertising_channel_sub_type': 'APP_CAMPAIGN',
        'status': 'PAUSED',
        'campaign_budget': {'amount_micros': daily_budget_micros},
        'app_campaign_setting': {
            'app_id': 'com.rift.saga',
            'app_vendor': 'GOOGLE_APP_STORE',
            'bidding_strategy_goal_type': 'OPTIMIZE_IN_APP_CONVERSIONS_TARGET_CPA',
        },
        'target_cpa': {'target_cpa_micros': target_cpa_micros},
    }

def make_app_roas_campaign(name, daily_budget_micros, target_roas_decimal):
    """价值优化 tROAS 系列（守高价值）。"""
    return {
        'name': name,
        'advertising_channel_type': 'MULTI_CHANNEL',
        'advertising_channel_sub_type': 'APP_CAMPAIGN',
        'status': 'PAUSED',
        'campaign_budget': {'amount_micros': daily_budget_micros},
        'app_campaign_setting': {
            'app_id': 'com.rift.saga',
            'app_vendor': 'GOOGLE_APP_STORE',
            'bidding_strategy_goal_type': 'OPTIMIZE_IN_APP_CONVERSIONS_TARGET_ROAS',
        },
        'target_roas': {'target_roas': target_roas_decimal},
    }

# $100K 月预算 → 约 $3,333/天，分三系列
series = [
    make_app_install_campaign('UA-Installs-tCPI', 1_000_000, 3_200_000),      # $30K/月 ≈ $1000/天
    make_app_engagement_campaign('UA-Engage-Purchase-tCPA', 1_666_000, 28_000_000),  # $50K/月
    make_app_roas_campaign('UA-ROAS-tROAS', 666_000, 1.2),                    # $20K/月
]

for c in series:
    resp = client.create_campaign(customer_id, c)
    if resp.success:
        print('created:', c['name'])
    else:
        print('failed:', c['name'], resp.error)
```

> 说明：这里为了演示 `create_campaign`，把 App 专属设置合并进 campaign 载荷。
> 真实 API 中 App 目标/出价会挂在 campaign 的 `app_campaign_setting` 与出价策略对象里，
> 具体字段以你封装的 DTO 为准。核心目的是展示**结构化的分层创建思路**。

#### 3.1.5 校验创建结果与拉取报表

创建后用 `list_campaigns` 确认系列状态与类型，
再用 `generate_report` 拉取 7 日关键指标做基线。

```python
# -*- coding: utf-8 -*-
"""
读取创建好的 App 系列，并拉取 7 日指标。
对应 list_campaigns 与 generate_report。
"""
from google_ads_api import GoogleAdsClient

client = GoogleAdsClient({...})
customer_id = '1234567890'

# 1) 列出 App 系列
campaigns = client.list_campaigns(
    customer_id,
    filter="campaign.advertising_channel_sub_type = 'APP_CAMPAIGN'"
)
for row in campaigns.data.get('results', []):
    c = row.get('campaign', {})
    print('campaign:', c.get('name'), '| status:', c.get('status'),
          '| id:', c.get('id'))

# 2) 7 日报表基线
rep = client.generate_report(
    customer_id,
    {'start': '2026-08-01', 'end': '2026-08-07'}
)
print('\n7日报表:')
for row in rep.data.get('results', []):
    print(row)
```

这就是一个完整的“建系列 → 拉数据 → 评估”闭环。

#### 3.1.6 出价调优循环（tCPA 松紧）

tCPA 不是设了就不动。它有清晰的调优节奏：

| 信号 | 判定 | 动作 |
| ---- | ---- | ---- |
| 预算花不完 | 学习到位但量不够 | 小幅上调 tCPA 5-10% |
| 量达但 ROAS 低于目标 | 事件价值不足 | 下调 tCPA 或转 tROAS |
| 学习期不收敛 | 信号太浅/冲突 | 收敛事件、统一数据源 |
| 波动大 | 频控/SSA 没跟上 | 加频控、检查资产组 |

每次调整幅度建议 ≤ 20%，且间隔 ≥ 1 个完整学习周期（约 3-7 天）再评判，
避免抖动干扰模型。

用代码更新 tCPA（对应 `update_campaign` 的实现思路）：

```python
# -*- coding: utf-8 -*-
"""
迭代调优出价：按 ±10% 步进更新 tCPA。
对应 google_ads_api.py 的 update_campaign。
"""
from google_ads_api import GoogleAdsClient

client = GoogleAdsClient({...})
customer_id = '1234567890'
campaign_id = '123456789'

def adjust_target_cpa(mult: float):
    # 读取当前 tCPA（此处示意：先拉会话外存的当前值）
    current_cpa_micros = 28_000_000
    new_cpa = int(current_cpa_micros * mult)
    resp = client.update_campaign(
        customer_id, campaign_id,
        {'target_cpa': {'target_cpa_micros': new_cpa}}
    )
    print('updated to', new_cpa / 1_000_000, 'USD →', resp.success)

adjust_target_cpa(1.10)   # 上浮 10%
```

### 3.2 电商 App 场景：UA + 事件价值对齐

#### 3.2.1 场景

一家跨境电商 App，主营家居用品，变现依托 GMV。

与游戏不同，电商的核心痛点是**价值回传与 ROAS 精确性**。

电商 UAC 的关键事件链：

```text
install → add_to_cart → purchase(带 value+currency) → re-order
```

#### 3.2.2 价值回传配置

tROAS 依赖“带价值的 purchase”。

关键是把每笔订单金额作为 conversion value 回传。

下表给电商推荐口径：

| 指标 | 数值 |
| ---- | ---- |
| D7 ROAS | ≥ 150% |
| CPA（首单） | ≤ $12 |
| 客单价 | ~$48 |
| 频控 | 同用户广告展示 ≤ 每日10次 |
| 转化窗 | 7 天点击 / 1 天浏览 |

#### 3.2.3 用代码拉取价值型指标

```python
# -*- coding: utf-8 -*-
"""
电商 App：核对 ROAS 与价值指标。
"""
from google_ads_api import GoogleAdsClient

client = GoogleAdsClient({...})
customer_id = '1234567890'
date_range = {'start': '2026-07-01', 'end': '2026-07-31'}

query = f"""
SELECT
  campaign.name,
  metrics.cost_micros,
  metrics.conversions,
  metrics.conversions_value,
  metrics.all_conversions_value,
  metrics.view_through_conversions,
  campaign.optimization_score
FROM campaign
WHERE segments.date BETWEEN '{date_range['start']}' AND '{date_range['end']}'
  AND campaign.advertising_channel_sub_type IN ('APP_CAMPAIGN',
       'PERFORMANCE_MAX_FOR_ANDROID_APPS')
"""

resp = client.search(customer_id, query)
for row in resp.data.get('results', []):
    c = row.get('campaign', {})
    m = row.get('metrics', {})
    cost = m.get('cost_micros', 0) / 1e6
    val = m.get('conversions_value', 0) / 1e6
    roas = (val / cost) if cost else 0
    print(
        f"{c.get('name'):<24} cost=${cost:7.2f} "
        f"roas={roas*100:5.1f}% conv={m.get('conversions'):5.1f} "
        f"opt_score={c.get('optimization_score')}"
    )
```

### 3.3 APP 增长 / 工具类场景：留存与信号深度

#### 3.3.1 场景

一家专注增长的工具类 App（如清理/记步/效率工具），变现以订阅为主。

工具类特点：

- 安装量大但付费周期长；
- 核心事件是 `subscription_start` 与 `active_7d`；
- 需要把“长期留存”转化思想注入 UAC。

#### 3.3.2 长周期转化与订阅优化

工具类更适合用**带价值的长周期事件**，例如按 LTV 估算订阅价值回传。

| 事件 | 角色 | 说明 |
| ---- | ---- | ---- |
| install | 冲量 | 低质但量大 |
| registration | 参考 | 验证注册链路 |
| subscription_start | 主转化 | 试订/订阅 |
| active_7d | 观测留存 | 判断留存健康 |

工具类不要只跑 install，否则留存与订阅质量难保证。

建议在 tCPA（订阅）与 tROAS（LTV 价值）之间按阶段切换。

### 3.4 代理商场景：多客户批量管理与报告

#### 3.4.1 场景

代理商（Agency）同时管理多个广告主账户，需要批量拉数、批量建系列、批量出报告。

这里展示用 `search` + `generate_report` 做多账户聚合的思路，
并强调 **login-customer-id（MCC）** 在跨账户查询中的作用。

```text
代理账号 (MCC / Manager)  login-customer-id
   └── 子账号 A (客户)
   └── 子账号 B (客户)
   └── 子账号 C (客户)
```

用 API 的客户维度可以批量遍历子账号。

#### 3.4.2 批量报告聚合

```python
# -*- coding: utf-8 -*-
"""
代理商批量拉取多个子账号的 UAC 汇总指标。
"""
from google_ads_api import GoogleAdsClient

client = GoogleAdsClient({
    'google_ads': {
        'developer_token': 'DEV',
        'login_customer_id': 'MANAGER_ID',  # MCC id
        'access_token': 'TOKEN',
    }
})

customer_ids = ['111', '222', '333']  # 子账号列表
date_range = {'start': '2026-08-01', 'end': '2026-08-14'}

grand = {'cost': 0.0, 'value': 0.0, 'conv': 0.0}
for cid in customer_ids:
    rep = client.generate_report(cid, date_range)
    for row in rep.data.get('results', []):
        c = row.get('campaign', {})
        m = row.get('metrics', {})
        # 只看 App 系列
        if c.get('advertising_channel_sub_type') not in (
            'APP_CAMPAIGN', 'PERFORMANCE_MAX_FOR_ANDROID_APPS'):
            continue
        cost = m.get('cost_micros', 0) / 1e6
        val = m.get('conversions_value', 0) / 1e6
        conv = m.get('conversions', 0)
        grand['cost'] += cost
        grand['value'] += val
        grand['conv'] += conv
        print(f"account={cid} camp={c.get('name')[:16]} "
              f"cost=${cost:.2f} conv={conv:.1f} roas={val/cost if cost else 0:.2f}")

print('TOTAL:', {k: round(v, 2) for k, v in grand.items()})
```

代理商的额外要点：

- 统一各账号的事件口径与出价策略选项（用 `get_bid_strategy_options` 校准）；
- 用 `list_conversion_actions` 对比各账号转化配置一致性；
- 输出统一的周报模板。

### 3.5 品牌营销场景：预注册与品牌搜索

#### 3.5.1 场景

大品牌新产品上线前，用 **App pre-registration** 蓄水，制造预约热度。

品牌往往还关心品牌词保护与通知用户。

#### 3.5.2 预注册系列

对于尚未上架的 App，创建 `App pre-registration` 目标系列。

它可以：

- 在未上线时锁定核心用户；
- 为 Play 商店预约人数/榜单造势；
- 上架后自动转化。

用 `create_campaign` 创建预注册系列（示意）：

```python
# -*- coding: utf-8 -*-
"""
创建 App pre-registration 系列。
"""
from google_ads_api import GoogleAdsClient

client = GoogleAdsClient({...})
customer_id = '1234567890'

campaign = {
    'name': 'Brand-PreReg',
    'advertising_channel_type': 'MULTI_CHANNEL',
    'advertising_channel_sub_type': 'APP_CAMPAIGN',
    'status': 'PAUSED',
    'campaign_budget': {'amount_micros': 500_000},  # 每天 $50K微? = $500/天
    'app_campaign_setting': {
        'app_id': 'com.brand.app',
        'app_vendor': 'GOOGLE_APP_STORE',
        'bidding_strategy_goal_type': 'OPTIMIZE_PRE_REGISTRATION_CONVERSION_VOLUME',
    },
}

resp = client.create_campaign(customer_id, campaign)
print('pre-reg created:', resp.success)
```

#### 3.5.3 品牌搜索联动

品牌 App 还常用**品牌搜索保护**：把品牌词放在搜索广告里，
承接用户在 Google 搜索品牌/下载 App 的需求，提升下载转化率。

虽然这属于搜索广告，但对 UA 有“收割自然流量”的补充作用。

### 3.6 直播带货/本地场景（信息流形态的 App 营销）

#### 3.6.1 场景

直播带货或本地生活类 App（如本地优惠、团购、点餐）做推广。

这类 App 以**安装 → 首单/预约/到店**为核心事件。

关键区别是转化事件不在 App 内闭环（如到店），需要**回传离线/到店价值**，
或依赖 deep link 与优惠码。

#### 3.6.2 事件与归因示意

| 事件 | 角色 |
| ---- | ---- |
| install | 冲量 |
| app_open / click_deep_link | 链路验证 |
| purchase(本地) / coupon_redeem | 主转化（可能离线） |

对离线转化，要依赖 **离线转化上传（Offline Conversion Import）**，
把线下履约数据回传 Google，让出价能优化到线下价值。

### 3.7 素材与资产组（Asset Group）实战

#### 3.7.1 素材是 UAC 另一大半

很多优化师只盯出价，忽略素材。但 UAC 的“素材进、结果出”决定了
**素材质量直接决定可展示机会与质量分**。

一个完整的 App UAC 需要以下资产（对应 `get_asset_type_options`）：

| 资产类型 | 建议数量 | 作用 |
| -------- | -------- | ---- |
| TEXT | 5 | 大标题/描述 |
| HEADLINE | 5+ | 标题变体供组合 |
| IMAGE | 若干 | 横版/竖版/方形 |
| YOUTUBE_VIDEO | 3+ | 15-30秒核心视频 |
| APP_EXTENSION | 应用链接 | 直接的下载按钮 |
| LEAD_FORM | 可选 | 表单收集（较少用） |

#### 3.7.2 资产组与 Asset Strength

素材以 **asset_group** 为组织单位。

系统会评估资产组的 **asset strength（素材强度）**，从 Poor/Okay/Good/Excellent。

素材强度直接影响可展示性与学习速度。

```text
Asset Strength 分级
--------------------------------------------------------------------
Poor        <65 分    素材种类过少/重复，展示受限
Okay        65-90     基本可用
Good        >90       展示充分
Excellent   上限       覆盖全部资产种类且多样
--------------------------------------------------------------------
```

高素材强度的要点：

- 覆盖全部推荐资产类型；
- 每种资产提供多个不重复的变体；
- 视频至少 3 支、长短剪辑齐备；
- 图片覆盖多尺寸（横/方/竖）。

#### 3.7.3 下拉资产组列表

用 `list_ad_groups` 与 asset 相关查询读取资产（此处以 ad_group 代示 asset_group 层级，
因为 App/PMax 系列中 asset_group 承载素材，ad_group 概念在 PMax 中被 asset_group 替代）。

```python
# -*- coding: utf-8 -*-
"""
读取 App 系列的资产组与素材概览（示意 GAQL）。
"""
from google_ads_api import GoogleAdsClient

client = GoogleAdsClient({...})
customer_id = '1234567890'
campaign_id = '123456789'

# App/PMax 系列以 asset_group 组织素材（该字段来自 asset_group / asset_group_asset）
query = f"""
SELECT
  asset_group.id,
  asset_group.name,
  asset_group.status,
  asset_group.path1
FROM asset_group
WHERE asset_group.campaign = 'customers/{customer_id}/campaigns/{campaign_id}'
"""

resp = client.search(customer_id, query)
for row in resp.data.get('results', []):
    ag = row.get('asset_group', {})
    print('asset_group:', ag.get('name'), '| id:', ag.get('id'),
          '| status:', ag.get('status'))
```

#### 3.7.4 素材 A/B 与迭代节奏

素材不是一次性上传就完事。推荐节奏：

- 每 3-4 周做一轮素材迭代；
- 用 asset strength + 视频时长 + CTR/CVR 作为离屏候选；
- 保留表现好的资产组合，淘汰弱资产；
- 视频是 UAC 主抓手，务必投入最好创意。

常用量化基准：

| 指标 | 健康区间 |
| ---- | -------- |
| 视频 3 秒观看率 | ≥ 45% |
| 视频完成率 | ≥ 15% |
| CTR | ≥ 1.5% |
| CVR(安装率) | ≥ 2% |
| eCPM | 视市场而定 |

### 3.8 预算与频控实战

#### 3.8.1 预算分配与学习门槛

UAC 进入稳定学习需要足够的转化量与预算。

经验学习门槛参考：

| 出价目标 | 每周建议转化 | 日预算参考 |
| -------- | ----------- | ---------- |
| tCPI(安装) | ≥ 30 安装/周 | ≥ 每日 10-15 CPI 转化 |
| tCPA(事件) | ≥ 30 转化/周 | ≥ 每日 10-15 转化 |
| tROAS | 依价值密度 | ≥ 每日 ~10-20 价值事件 |

低于门槛，模型长期“学习不饱和”，出价会抖。

#### 3.8.2 频控与 SSA（Smart Bidding - 频次优化）

UAC 默认有频控能力，但优化师可以进一步约束展示频率，防止同一用户被过度打扰。

在自动化产品里，频控通过 **smart bidding 的频次目标** 或素材组的展示约束实现。

实操要点：

- 高频次用户 CTR/CVR 会衰减，控制频次可提升素材效率；
- 但 UAC 不开放传统频控设置，主要靠出价与素材组合让系统自发优化；
- 若观察到重复展示高但转化低，可收缩素材组合，减少与同一用户多次匹配。

### 3.9 最佳实践清单（小结）

把第三章的关键操作汇成可直接执行的最佳实践清单：

1. **分层建系列**：冲量/主ROAS/价值守层，预算按 30/50/20 起步；
2. **事件少而精**：主转化 1-3 个，其余做观测；
3. **价值必须回传**：tROAS 依赖带金额的 purchase；
4. **数据源统一**：Google 内以 GAFB/GA4 为主，外以 MMP 校准；
5. **iOS/Android 分开**：SKAN 噪声大，分开更稳；
6. **素材持续迭代**：asset strength 拉到 Good 以上，视频做主；
7. **tCPA 小幅调优**：±10% 步进，间隔完整学习期；
8. **长窗观察**：iOS 至少 7 日、Android 3-5 日再看结论；
9. **频控兜底**：控制展示频率防饱和；
10. **留学习门槛**：预算不足时收敛事件而非摊薄预算。

