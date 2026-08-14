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

### 2.6 转化回传与控制面：Go 工程落地

增长团队的工程侧往往用 Go 写服务端回传与后台控制面。

这里给出两个真实高频场景的 Go 示例：

1. **服务端事件回传**：把 App 内的 purchase 事件（含价值）实时回传 Google，
   供 conversion tracking 与 tROAS 使用；
2. **GAQL 查询封装**：在 Go 服务里封装对 Google Ads REST 的查询，
   用于周期性拉取 UAC 指标、做 BI 落库。

#### 2.6.1 Go 服务端事件回传示例

很多团队用 Firebase 或 MMP SDK 在端上上报，但**服务端回传**（尤其离线/服务器确认的订单）
更可靠。这里展示一次 POST 到 Google Ads 的 GCLID/转化回传思路。

```go
package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"time"
)

// googleAdsClient 封装对 Google Ads API 的 POST 请求。
type googleAdsClient struct {
	baseURL        string
	developerToken string
	loginCustomer  string
	accessToken    string
	http           *http.Client
}

func newGoogleAdsClient(devToken, loginCustomer, accessToken string) *googleAdsClient {
	return &googleAdsClient{
		baseURL:        "https://googleads.googleapis.com/v24",
		developerToken: devToken,
		loginCustomer:  loginCustomer,
		accessToken:    accessToken,
		http:           &http.Client{Timeout: 30 * time.Second},
	}
}

// post 通用 POST，签名与 Python 侧的 request 对应。
func (c *googleAdsClient) post(ctx context.Context, endpoint string, body any) (map[string]any, error) {
	payload, err := json.Marshal(body)
	if err != nil {
		return nil, err
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost,
		c.baseURL+"/"+endpoint, bytes.NewReader(payload))
	if err != nil {
		return nil, err
	}
	req.Header.Set("Authorization", "Bearer "+c.accessToken)
	req.Header.Set("developer-token", c.developerToken)
	req.Header.Set("login-customer-id", c.loginCustomer)
	req.Header.Set("Content-Type", "application/json")

	resp, err := c.http.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	var out map[string]any
	// 简化：非 200 视为失败（真实代码需读 body 取 error.message）
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("google ads api status %d", resp.StatusCode)
	}
	if err := json.NewDecoder(resp.Body).Decode(&out); err != nil {
		return nil, err
	}
	return out, nil
}

// Search 执行 GAQL 查询（对应 Python search(customer_id, query)）。
func (c *googleAdsClient) Search(ctx context.Context, customerID, query string) (map[string]any, error) {
	return c.post(ctx, "customers/"+customerID+":search", map[string]any{
		"query": query,
	})
}

// ReportCampaign 拉取 App 系列的广告系列级指标。
// 对应 Python generate_report 的 GAQL，但收敛到 App 子类型。
func (c *googleAdsClient) ReportCampaign(ctx context.Context, customerID, start, end string) (map[string]any, error) {
	q := fmt.Sprintf(`
SELECT campaign.name,
       metrics.impressions, metrics.clicks,
       metrics.cost_micros, metrics.conversions, metrics.conversions_value
FROM campaign
WHERE segments.date BETWEEN '%s' AND '%s'
  AND campaign.advertising_channel_sub_type IN
      ('APP_CAMPAIGN', 'PERFORMANCE_MAX_FOR_ANDROID_APPS')`, start, end)
	return c.Search(ctx, customerID, q)
}

func main() {
	ctx := context.Background()
	client := newGoogleAdsClient("DEV", "LOGIN", "TOKEN")

	res, err := client.ReportCampaign(ctx, "1234567890", "2026-08-01", "2026-08-07")
	if err != nil {
		fmt.Println("err:", err)
		return
	}
	// 处理 res（rows 在 res["results"]）
	fmt.Printf("rows: %d\n", len(res["results"].([]any)))
}
```

要点：

- Go 侧签名 `post` / `Search` 与 Python 侧 `request` / `search` 一一对应；
- `login-customer-id`（MCC）要带上，跨子账号查询才有效；
- 组织列为 `campaign.*` + `metrics.*` + `segments.*`，与 GAQL 命名一致。

#### 2.6.2 批量拉数与 BI 落库

增长团队常把 UAC 指标落进数据仓库做长期观察。

这里展示多日期循环拉数（示意，不含落库细节）：

```go
// 多日期聚合，按月循环拉取每日指标
dates := []string{}
for d := time.Date(2026, 8, 1, 0, 0, 0, 0, time.UTC); d.Before(time.Date(2026, 8, 15, 0, 0, 0, 0, time.UTC)); d = d.AddDate(0, 0, 1) {
	dates = append(dates, d.Format("2006-01-02"))
}

for _, day := range dates {
	q := fmt.Sprintf(`
SELECT campaign.name, segments.date, metrics.cost_micros,
       metrics.conversions, metrics.conversions_value
FROM campaign
WHERE segments.date = '%s'
  AND campaign.advertising_channel_sub_type = 'APP_CAMPAIGN'`, day)
	res, err := client.Search(ctx, "1234567890", q)
	if err != nil {
		fmt.Println("day", day, "fail", err)
		continue
	}
	// append res 到落库 buffer
	fmt.Println("fetched", day, len(res["results"].([]any)))
}
```

#### 2.6.3 Go 侧与 Python 侧的分工建议

| 职责 | 建议语言 | 说明 |
| ---- | -------- | ---- |
| 数据回传 / 后台控制面 | Go | 高并发、服务端稳定 |
| 快速脚本 / 报表原型 | Python | 简洁、贴近 `google_ads_api.py` |
| 周期任务 / 批处理 | Go / Python 均可 | 看既有基建 |

两套能力你都要具备：Python 负责策略原型与快速验证，
Go 负责线上稳定的回传与数据管道。

#### 2.6.4 转化回传的健壮性设计

回传是易碎链路，要做幂等与重试：

- 用业务订单粒度做幂等键，避免重复回传导致重复计数；
- 失败回传进入 MQ/重试队列，指数退避重试；
- 监控回传成功率，低于阈值告警；
- SKAN 场景下网络回传失败率高，更要做容错。

```text
回传链路
--------------------------------------------------------------------
App 端事件 ──► SDK(端上) ──► GAFB/GA4 或 MMP ──► Google Ads 转化
服务端确认 ──► 服务端回传 ──► conversion action ──► 出价学习
            └── 幂等键 + 重试队列（健壮性）
--------------------------------------------------------------------
```

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

### 3.9 ASO 深度实战：与 UA 的联动闭环

ASO（App Store Optimization）不是独立部门的事，它是 **UA 预算的放大器**。

UA 花钱把流量导到应用商店页，而商店页的**评分、评价、截图、标题、关键词**
直接决定用户点不点“安装”。商店页转化率差一分，UA 的真实获客成本就涨一分。

本节把 ASO 与 UA 的联动讲透，量化为可操作的口径。

#### 3.10.1 ASO 影响 UA 的量化闭环

一条完整的病理链：

```text
UA 花钱 → 用户点广告 → 到商店页(impression on store)
        → 看评分/截图/标题 → 决定是否安装
        → 安装 → 留存/付费
```

任何一个环节低，都会浪费 UA 预算。用漏斗漏斗看：

| 环节 | 口径 | 健康参考 |
| ---- | ---- | -------- |
| 广告点击→商店页 | CTR | ≥ 1.5% |
| 商店页→安装 | Download conversion rate(DCR) | ≥ 20-30% |
| 安装→首次启动 | first_open rate | 全量(安装即当启动) |
| 启动→付费 | PPI / IAP | 视品类 |

商店页转化率（DCR）是最被低估的杠杆。

很多团队把 DCR 只有 15% 归咎于“广告质量”，其实是商店页（评分/图标/截图）拖后腿。

#### 3.10.2 评分与评价的监控与优化

评分是安装决策的头号因素。要做：**监控 + 引导 + 治理**。

| 动作 | 说明 |
| ---- | ---- |
| 评分监控 | 按版本/地区持续跟踪评分曲线 |
| 差评治理 | 快速响应差评、定位版本回归/支付问题 |
| 好评引导 | 在应用内合适时机引导满意用户打分 |
| 评价回复 | 官方回复提升信任感 |

量化目标：混合商店评分 **≥ 4.4**。

低于 4.0 时，UA 的安装转化率会显著下滑。

下面用 Python 把 UA 指标与商店指标并列做体检（示意，商店数据可来自 ASO 工具/MongoDB）。

```python
# -*- coding: utf-8 -*-
"""
ASO 与 UA 联动体检：并列拉取广告指标与商店假设数据。
"""
from google_ads_api import GoogleAdsClient

client = GoogleAdsClient({...})
customer_id = '1234567890'

# 拉 UA 安装与花费
query = """
SELECT campaign.name,
       metrics.cost_micros,
       metrics.conversions,
       metrics.clicks
FROM campaign
WHERE campaign.advertising_channel_sub_type = 'APP_CAMPAIGN'
  AND segments.date DURING LAST_7_DAYS
"""

resp = client.search(customer_id, query)
total_clicks = 0
total_installs = 0
total_cost = 0.0
for row in resp.data.get('results', []):
    m = row.get('metrics', {})
    total_clicks += m.get('clicks', 0)
    total_installs += m.get('conversions', 0)
    total_cost += m.get('cost_micros', 0) / 1e6

# 假设商店页另有自然流量，用 DCR 折算广告安装的“商店页漏斗”
store_rating = 4.5       # 从商店 API 拉取
dcr_assumed = 0.26       # 从商店分析估算下载转化率
ad_clicks_with_store = total_clicks * dcr_assumed

print(f"7日广告点击: {total_clicks}")
print(f"7日广告安装: {total_installs}")
print(f"7日广告花费: ${total_cost:.2f}")
print(f"估算商店漏斗安装(广告点击*DCR): {ad_clicks_with_store:.0f}")
print(f"当前商店评分: {store_rating}")
```

#### 3.10.3 下载转化率（DCR）优化

DCR 提升带来的直接效果是 UA 的 **eCPI/CPA 下降**。

同一笔广告花费，商店页转化率越高，真实获客成本越低。

DCR 优化清单：

1. **图标 A/B**：图标是第一视觉，直接影响首屏点击；
2. **截图前 3 张**：用户只看前几张，摆核心卖点；
3. **预览视频**：首屏自动播放短视频拉起兴趣；
4. **标题/副标题**：命中目标关键词，同时传达价值；
5. **评分曝光**：评分高则无需隐藏，评分差要治理后再说；
6. **包体大小**：包过大拖慢安装，影响转化与留存。

#### 3.10.4 关键词覆盖与自然量

ASO 的关键词优化能提升**自然安装（organic）**，间接缓解 UA 压力。

| 关键词维度 | 优化动作 |
| ---------- | -------- |
| 标题/副标题 | 放最重要的 1-2 个关键词 |
| 描述/热搜词 | 覆盖长尾搜索意图 |
| 商店分类 | 选对分类提升曝光 |
| 本地化 | 分地区翻译关键词 |

自然量与付费量存在**替代/协同**关系：

- 付费 UA 能帮助提升关键词排名与评分（间接助攻自然量）；
- 自然量增长又能让总 LTV 池更大，给 UA 出价更多空间。

```
ASO ─ UA 协同飞轮
--------------------------------------------------------------------
ASO优化 → 提升商店转化/自然量 → 评分与量能提升
      → UA 预算更高效 → 更多数据喂给模型
      → 自然+付费双增 → 飞轮加速
--------------------------------------------------------------------
```

#### 3.10.5 ASO 复盘节奏

- 每周看评分与差评趋势；
- 每月做一轮截图/图标 A/B；
- 每季度复盘关键词覆盖与本地化；
- 关键版本更新前后重点盯评分曲线（回归风险）。

### 3.10 最佳实践清单（小结）

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


---

## 四、常见问题与排查

第四章承担“落地后救火”的职责。

我们把在真实运营中最高频、最致命的 UAC 问题整理成 **Q&A**，
每个问题都给出：现象、根因、排查动作、修复建议。

至少保证 10 个高质量问答，并用表格/代码辅助排查。

### Q1：广告系列学习期一直不结束，或频繁退出学习期

**现象**：UAC 一直处于“学习中”状态，或刚从学习期出来又退回去，转化数上下跳动。

**根因分析**：

- 转化事件信号太稀疏，达不到学习门槛；
- 事件选择冲突（同时设了安装又与事件目标打架）；
- 预算频繁改动（tCPA/预算每几天改一次）；
- iOS 上 SKAN 延迟导致信号更晚更零散。

**排查动作**：

1. 检查是否为 iOS(SKAN) 数据源，是则放宽观察窗；
2. 检查每周转化量是否达到门槛；
3. 检查近期是否频繁改出价/预算。

**修复**：

- 收敛事件，去掉低频杂事件；
- 保证至少 30 转化/周；
- iOS/Android 分开，避免相互污染；
- 调整后至少等 1 个完整周期（3-7 天）再评判。

用代码检查近期是否频繁触及出价更新（拉取历史出价与建议）：

```python
# -*- coding: utf-8 -*-
"""
排查学习期不收敛：拉最近 30 天转化与估计。
对应 get_bid_suggestion 的思路。
"""
from google_ads_api import GoogleAdsClient

client = GoogleAdsClient({...})
customer_id = '1234567890'
campaign_id = '123456789'

resp = client.get_bid_suggestion(customer_id, campaign_id)
print('bid suggestion / 学习期诊断数据:')
for row in resp.data.get('results', []):
    m = row.get('metrics', {})
    print('  all_conversions=', m.get('all_conversions'),
          ' est_ranked_cpc=', m.get('estimated_ranked_cpc_micros'))
```

### Q2：转化数正常，但 ROAS 明显低于预期

**现象**：报表里转化量可观，但 ROAS 长期在目标以下。

**根因分析**：

- 价值没正确回传（value=0 或货币错）；
- 转化口径把“安装”也算成了高价值转化；
- 归因窗过长把低质自然转化计入；
- 买量偏向低质用户（只跑 install 系列占比过高）。

**排查动作**：

1. 用上文代码核对 `conversions_value` 是否 > 0；
2. 检查转化行为是否带 value、currency 正确；
3. 检查 tROAS 系列是否被 tCPA/install 系列稀释。

**修复**：

- 修正 value 回传，保证带金额；
- 提高 tROAS 系列预算占比，降低 install 系列；
- 收紧归因窗。

### Q3：Google Ads 内安装数与 MMP 明显不一致

**现象**：Ads 报表 iOS 安装 1000，MMP 显示 800 或 1200。

**根因分析**：

- 数据源不同（Google vs MMP 归因引擎）；
- SKAN postback 延迟与随机窗口导致的时点错位；
- privacy threshold 噪声；
- 去重口径差异。

**排查动作**：

1. 确认两套都跑在 SKAN 上；
2. 对齐时间窗（滚动 7 日）再对比；
3. 按转化分布而非单日绝对值对比。

**修复**：

- 用“滚动累计”而非单日对比；
- 以一家为计账口径，另一家为观测；
- 关注长期趋势一致性。

### Q4：视频素材点击率高但安装率很低

**现象**：视频 CTR 不错（≥2%），但点击→安装 CVR 很低。

**根因分析**：

- 视频承诺与商店页实际不符（“货不对板”）；
- Deep Link/商店页落地体验差；
- 目标人群与素材表达错位；
- 评分/评价差影响安装决策。

**排查动作**：

- 检查商店页截图、评分、包大小；
- 检查 Deep Link 是否跳转正确活动页；
- 拆分视频 vs 图片 vs 文字看 CVR。

**修复**：

- 素材表达对齐商店页卖点；
- 优化商店页转化（这其实就进入 ASO 范畴，见下章）；
- 清理高曝光低安装的低效素材。

### Q5：UAC 只烧预算不出量/出量极慢

**现象**：预算与出价都正常，但展示/转化量极少。

**根因分析**：

- tCPA 设得过低，导致竞价失败；
- 学习门槛信号不足；
- 素材强度 Poor，展示受限；
- 覆盖人群过窄（App 小众）。

**排查动作**：

- 检查 asset strength；
- 检查预算是否长期花不完；
- 检查 tCPA 与市场均值差距。

**修复**：

- 适当上调 tCPA（配额学习）；
- 补齐素材种类提升 asset strength；
- 用 `get_bid_suggestion` 看市场建议。

### Q6：为什么我找不到“受众定向”设置

**现象**：UAC 后台没有传统受众列表、没有性别/年龄/兴趣定向选项。

**根因**：这是 **UAC 自动化产品的设计特性**。它不开放传统定向，而是用
**Auto Audience（自动受众）**，由系统基于应用信号与素材自动构建。

**正确理解**：

- 不要硬找受众定向，那是旧手动广告的思维；
- 若要影响人群，通过**素材、出价目标、转化事件**间接引导；
- 可利用 **asset_group_signal**（信号）来提示系统你的目标人群意图。

用 `asset_group_signal` 查看/设置受众信号：

```python
# -*- coding: utf-8 -*-
"""
查看 asset_group_signal（App/PMax 系列的意向信号）。
"""
from google_ads_api import GoogleAdsClient

client = GoogleAdsClient({...})
customer_id = '1234567890'

query = """
SELECT
  asset_group.id,
  asset_group.name,
  asset_group_signal.audience
FROM asset_group_signal
"""

resp = client.search(customer_id, query)
for row in resp.data.get('results', []):
    print(row)
```

### Q7：为什么同一 App 不同系列转化数会“打架/重复计算”

**现象**：多个 UAC 系列加起来转化数大于总转化，或有重复。

**根因分析**：

- 多个系列共享同一转化事件，进行了重复计数；
- 归因去重没覆盖跨系列；
- iOS SKAN 多网络重复 postback。

**排查动作**：

- 检查总报表是否按 campaign 聚合后的去重；
- 检查是否多系列误配相同事件并同时启用。

**修复**：

- 明确系列职责，避免多个系列优化同一终极事件互相抢量；
- 用 `generate_report` 的聚合口径核对全局 vs 分系列。

聚合去重核对的思路：

```python
sum_by_campaign = {}   # 示例
# 从 generate_report 聚合后对比 total 是否等于各系列之和
# 若不等，多半是归因账务/系列重叠问题
```

### Q8：iOS 报表波动非常大，日志上“锯齿状”

**现象**：iOS 转化曲线大起大落，无法用单日做决策。

**根因**：iOS 走 SKAN，postback **随机延迟（24-48h） + privacy threshold 噪声**，
单日数据天然不可靠。

**排查动作**：

1. 确认该系列确实走 SKAN（无 IDFA 或 mixed）；
2. 拉 7 日滚动累计而非单日；
3. 与 MMP 的 SKAN 面板交叉核对转化分布。

**修复**：

- iOS 独立系列 + 更长观察窗；
- 用转化分布曲线而非绝对值；
- 数据齐了再看 ROAS（至少 D7）。

### Q9：为什么转化事件改了，历史数据/出价剧烈变化

**现象**：更换主转化事件（如从 install 切到 purchase）后，成本与 ROAS 剧烈波动。

**根因**：**改变转化目标是改变优化目标本身**，等于给模型换了“北极星”。
历史上以安装为目标的系列，切到 purchase 后模型需要重新学习，波动是正常的。

**排查动作**：

- 确认切换是否有意（是否误改）；
- 评估新事件能否撑起学习门槛。

**修复**：

- 切换时给足学习期（7-14 天）；
- 用 CVR 健康度（如 purchase 事件频率）评估；
- 实在不行分系列并行，用实验法平滑切换。

### Q10：预算从哪里开始，如何评估“预算不足”？

**现象**：预算加不上去，或加预算后 ROAS 反而掉。

**根因分析**：

- 预算低于学习门槛，模型无法饱和；
- 一次性大幅加预算造成学习抖动；
- 高价值库存有限，加量后边际 ROAS 下滑（边际报酬递减）。

**排查动作**：

- 检查日预算是否能支撑 ≥10-15 转化/日；
- 观察加预算后 3 天的 ROAS 走势。

**修复**：

- 阶梯式加预算，每次 +20-50% 观察稳定；
- 若 ROAS 下滑，收缩到盈利区间并引入 tROAS 兜底。

### Q11：SKAdNetwork 一致性反复对不上，怎么办（深入）

**现象**：Google 与 MMP 的 SKAN 安装长期对不上，且无法靠“滚动累计”对齐。

**根因分析**：

- private relay / privacy threshold 导致事件被丢弃；
- 归因分层（source app / ad-network view）不统一；
- Google 与 MMP 对 SKAN 转发的处理策略不同。

**排查动作**：

1. 冻结一天的 SKAN postback 数据集，逐层对比 source_app / ad_network；
2. 对齐归因层（view vs click）；
3. 检查小事件是否低于 privacy threshold 被丢。

**修复**：

- 若为阈值丢弃，接受误差、只比对转化分布；
- 若为转发策略不同，选择一家做“主账本”；
- 建立周级校准，容纳 ±5-10% 常态差。

### Q12：ASO 与 UA 的关系，评分怎么影响投放

**现象**：UA 量推上去了，但安装转化率（点击→装）和留存却不理想。

**根因分析**：商店页（评分/评价/截图/标题/描述）直接决定用户是否安装。
UA 花钱把流量导到商店页，但 **ASO 不佳会浪费投放预算**。

**排查动作**：

- 检查商店评分是否低于 4.0；
- 检查差评是否集中（版本回归/支付失败）；
- 检查商店截图与素材卖点是否一致。

**修复**：

- 提升评分：引导好评、处理差评；
- 优化商店标题/副标题的关键词命中；
- 用 A/B 测试截图与图标，提高下载转化率。

下表展示 ASO 关键指标如何反哺 UA：

| 指标 | 健康值 | 对 UA 的影响 |
| ---- | ------ | ----------- |
| 商店评分 | ≥ 4.3 | 高评分提升安装率 |
| 下载转化率(店铺→装) | ≥ 25% | 越高 UA 越省钱 |
| 图标/截图点击 | 持续 A/B | 直接影响首屏转化 |
| 关键词覆盖 | 持续优化 | 提升自然量 |

### 排查通用流程（汇总）

把上面的经验提炼成一张可复用的决策树：

```text
UAC 排查决策树
--------------------------------------------------------------------
转化与 ROAS 不佳?
 ├─ 先分 iOS / Android
 │    iOS 走 SKAN → 长窗观察, 对分布偏差
 ├─ 量少? → 预算/学习门槛/素材强度
 ├─ 量够但 ROAS 差? → 价值回传 / 事件质量
 ├─ 归因对不上? → 对齐窗口与数据源
 └─ 安装率低? → ASO 商店页优化
--------------------------------------------------------------------
```

### Q13：Deep Link 跳转失败，转化/留存被低估怎么办

**现象**：广告点击后安装正常，但点击应用内活动/深度链接跳转失败，
后续转化（如付费页）大量丢失，UA 报表转化偏低。

**根因分析**：

- Deep Link / URI scheme 配置不完整（iOS Universal Link、Android App Links）；
- 未安装用户的 deferred deep link 处理缺失；
- 商店页跳转参数（如 `referrer`）丢失，归因无法回链到点击。

**排查动作**：

1. 用归因面板测一条完整链路：广告 → 商店页 → 安装 → 首次打开带 deep link；
2. 检查 `first_open` 是否带 `gclid`/`advertising_id`；
3. 用 `list_conversion_actions` 核对事件是否带上正确的 click_id。

**修复**：

- 配置 Universal Link / App Links，保证已安装用户直达内容页；
- 未安装用户走 deferred deep link 恢复；推广素材统一带追踪参数；
- 修复后用 A/B 小流量验证转化回传恢复。

Deep Link 与归因的链路示意：

```text
点击广告(带 deeplink 参数)
   ├─ 已安装 → Universal/App Link 直达页面
   └─ 未安装 → 商店页 → 安装 → 首启时恢复 deep link → 页面
                          └─ 同时把归因 click_id 带进 first_open
```

### Q14：为什么同一个 App 在不同账户跑，成本差异巨大

**现象**：同样素材、同目标，A 账户 CPI $3.0，B 账户 CPI $5.0。

**根因分析**：

- 账户历史/学习基础不同（账户级学习信号）；
- 转化事件配置不一致（B 账户事件更全/更少）；
- 出价与预算结构不同；
- 素材资产组不同步（B 账户 asset strength 更差）；
- SKAN/数据源选择不同。

**排查动作**：

1. 对比两账户的 `conversion_action` 配置；
2. 对比 asset strength 与素材数量；
3. 对比出价设置与学习期状态。

**修复**：

- 统一事件与数据源口径；
- 复制优秀账户的素材/结构到弱账户；
- 弱账户先给足学习预算与时间，不要过早判定失败。

### Q15：周期性掉量（周中掉、周末回）怎么处理

**现象**：UAC 每周稳定出现“周中量下滑、周末反弹”的周期波动。

**根因分析**：

- 目标人群活跃周期（游戏玩家周末更活跃）的自然波动；
- 预算在周中被低价库存消耗，周末竞价上升；
- 出价/预算在周中被动调整放大了波动。

**排查动作**：

- 拉 4-8 周的“按星期几”聚合，确认周期性是否稳定；
- 检查是否每周同一时间触发过出价/预算修改。

**修复**：

- 识别周期性属正常市场波动，避免过度反应；
- 需要平抑时，用 tCPA 小幅上浮覆盖周末竞争；
- 素材按周期轮换，周末用强效创意。

---

## 五、自测题

本章提供 5 道自测题，覆盖本文的核心知识点。

建议先独立作答，再对照 `<details>` 中的答案与解析自查。

答案采用折叠块呈现，点击即可展开。

### 题目 1：目标选择

某款已上线 6 个月、IAP 变现稳定的手游，增长目标由“大量拉新”转为“稳定 ROAS”。

请问在 UAC 中应优先选择哪种目标？为什么？(单选)

- A. App installs
- B. App engagement（指定内购事件）
- C. App pre-registration
- D. 保持默认

<details>
<summary>答案</summary>

**答案：B（App engagement，指定内购事件）。**

**解析**：

- 该游戏已上线 6 个月、IAP 稳定，说明已有充足的安装与事件数据；
- 目标是“稳定 ROAS”，ROAS 依赖价值型事件（Purchase）；
- App installs（A）只优化浅层安装，无法保证 ROAS；
- App pre-registration（C）仅适用于未上架产品；
- 应选择 App engagement，并指定 `purchase`（带价值）作为主转化，配合 tCPA/tROAS；
- 按本文 3.1.2 的分层思路，可用 tCPA(首购) + tROAS(价值) 双层。

</details>

### 题目 2：数据源与归因

为什么同一 App 在 Google Ads 与第三方 MMP 中，iOS 安装数常常不一致？

请列举至少两点根因，并指出最小可执行的校准策略。

<details>
<summary>答案</summary>

**核心不再赘述，两点关键根因**：

1. **归因引擎不同**：Google（GAFB/GA4）与 MMP 各用各的归因引擎，
   去重、点击/浏览窗口、模型（last-click vs DDA）不尽相同；
2. **SKAN 特性**：iOS 走 SKAdNetwork，postback 有 24-48h 随机延迟与 privacy
   threshold 噪声，单日/小量级数据天然不准，逐单对比必然不一致。

**最小可执行校准策略**：

- 统一归因窗口与去重口径（都设 7 天点击 / 1 天浏览）；
- 用滚动累计（≥7 日）而非单日对比；
- 以一家为计账口径、另一家观测；
- 接受 ±5-10% 常态差，关注趋势一致性；
- 若只对 SKAN 对不上，比较转化分布而非绝对值。

</details>

### 题目 3：归因窗口与价值

电商 App 的 UAC 使用 tROAS 优化，但后台 `conversions_value` 长期为 0 或远低于 GMV。

请问最可能的原因是什么？应如何修复？

<details>
<summary>答案</summary>

**最可能原因**：转化事件（如 purchase）的**价值（value）与币种没有正确回传**。

- tROAS 依赖带金额的 conversion value 才能优化；
- 若 purchase 事件 value=0 或 currency 错误，`conversions_value` 就是 0/偏小；
- 也可能把“安装类（无价值）”事件误当成价值转化。

**修复方法**：

1. 在转化行为设置中为 purchase 事件启用价值设置（value + currency，如 USD）；
2. 在 SDK/服务端上报 purchase 时带上订单金额；
3. 用本文 2.2.4 的代码核对 `conversions_value / all_conversions_value`；
4. 确认是“出价转化”而非仅“全部转化”计入价值（检查口径）；
5. 修复后观察 ROAS 是否回归。

补充：若 `all_conversions_value` 远大于 `conversions_value`，
多半是部分价值只计入全部转化、未进入出价转化，需回看转化行为设置。

</details>

### 题目 4：分层系列与预算

月预算 $100K 的游戏 UAC，想把 ROAS 稳定在 120% 以上，同时不放松量级。

请设计一个分层系列结构（预算占比 + 各自目标/出价），并解释理由。

<details>
<summary>答案</summary>

**推荐结构（参考 3.1.2/3.1.4）**：

| 系列 | 目标 | 预算占比 | 月预算 | 出价 |
| ---- | ---- | -------- | ------ | ---- |
| UAC-Installs | App installs | 30% | $30K | tCPI |
| UAC-Engage-Purchase | App engagement | 50% | $50K | tCPA(首购) |
| UAC-ROAS | App engagement(价值) | 20% | $20K | tROAS(120%) |

**理由**：

- 安装层（30%）负责拉新冲量，满足量级与学习数据；
- 首购 tCPA 层（50%）是主力 ROAS 引擎，直接对 purchase 优化，稳定商业回报；
- tROAS 层（20%）守高价值用户，防止量扩张时质量下滑；
- 三层互补：既保量，又保 ROAS ≥120%；
- 若 PPI（付费安装渗透率）偏低，可把更多预算从 install 层移到 tCPA/tROAS 层。

</details>

### 题目 5：UAC 学习期与素材

为什么 UAC 没有传统受众定向？若要影响人群质量，应从哪几个旋钮着手？
并说明 asset strength 的影响。

<details>
<summary>答案</summary>

**为什么无传统受众定向**：

- UAC 是自动化产品，采用 **Auto Audience（自动受众）**；
- 系统基于应用信号 + 素材 + 转化事件自动构建人群，刻意不开放手工定向；
- 这是“素材+目标+出价”驱动范式的核心特性，不是缺失功能。

**可间接影响人群质量的旋钮**：

1. **出价目标与事件**：tROAS 比 install 更能锁定高价值用户；
2. **素材**：素材表达决定匹配人群，视频/文案传达不同人设；
3. **asset_group_signal**：用信号字段给系统人群意图提示；
4. **预算分层**：把预算倾向价值型系列；
5. **转化事件选择**：主事件直接决定优化终点。

**asset strength 的影响**：

- asset strength（Poor/Okay/Good/Excellent）反映素材覆盖与多样性；
- Poor 会限制可展示性、拖慢学习；
- 拉到 Good 以上，补全 TEXT/IMAGE/YOUTUBE_VIDEO/HEADLINE 等类型且保证不重复，
  可显著提升学习速度与量级。

</details>

---

## 附：本文与脚本对照

本文所有代码均基于 `scripts/google_ads_api.py` 的真实方法调用。

常用方法与本排布对照如下，便于读者回到代码库复用：

| 使用场景 | 方法 | 章节 |
| -------- | ---- | ---- |
| 拉取转化行为 | list_conversion_actions / search | 2.1 / 2.2 |
| 创建分层系列 | create_campaign | 3.1 |
| 读取系列 | list_campaigns / get_campaign | 3.1 |
| 更新出价 | update_campaign | 3.1.6 |
| 出价/学习诊断 | get_bid_suggestion | Q1 |
| 报表聚合 | generate_report / search | 3.2 / 3.4 |
| 素材资产组 | search(asset_group) | 3.7 |
| 受众信号 | search(asset_group_signal) | Q6 |
| 暂停/恢复 | pause_campaign / resume_campaign | 参考 |
| 出价选项 | get_bid_strategy_options | 参考 |
| 资产选项 | get_asset_type_options | 3.7 |
| 广告类型选项 | get_campaign_type_options | 参考 |

API 端点：`https://googleads.googleapis.com/v24`
请求头：`Authorization: Bearer <token>` + `developer-token` + `login-customer-id`
GAQL 典型字段：`campaign.id/name/status/advertising_channel_type/advertising_channel_sub_type`、
`campaign.optimization_score`、`asset_group.*`、`asset_group_signal`、
`metrics.impressions/clicks/cost_micros/conversions/conversions_value/all_conversions/ctr/cpv/cpc_micros`、
`segments.date/device`、`campaign_budget.amount_micros`。

---

## 结语

App 广告（UAC）是“素材进、结果出”的自动化买量引擎，
但它的可控点清晰可数：**目标、事件、数据源、出价、预算、素材、ASO**。

本指南的目的不是让你把机器当黑盒听天由命，
而是让你能**设计好信号、约束好预算、校准好归因、迭代好素材**，
从而让 Google 的机器学习朝着你的商业 ROAS 系统性收敛。

把这些章节的知识（尤其归因一致性、SKAN、事件漏斗出价、ASO 联动）吃透，
你就从一个“会建 UAC 的人”成长为“能用 UAC 稳定赚钱的增长专家”。

祝你的每一次点击、每一次安装、每一单付费，都准确地记在正确的地方。

---

*本文档由 Ryan 个人知识库 · Google Ads App 广告专项生成。*
*更新日期：2026-08-14*
