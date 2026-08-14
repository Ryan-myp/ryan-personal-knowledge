# TikTok Brand Solutions 深度指南：Takeover、Branded Effects、Hashtag Challenge

> **领域**: 广告投放 / TIKTOK_ADS
> **深度**: ⭐⭐⭐⭐⭐ 实战级指南
> **标签**: TIKTOK_ADS, 广告投放
> **更新时间**: 2026-08-14
> **类型**: 深度知识文档

---

> **本文档定位（与既有文档差异化）**
>
> 知识库中《tiktok-ads-brand-shop-live-deep.md》已从产品形态角度覆盖了
> TopView、Brand Takeover、Branded Effects、Hashtag Challenge 的 1.1-1.4 基础章节。
> 本文件刻意与之错位，深挖品牌广告的**另一条主线**：
>
> 1. 售卖与库存（预售/档期/CPD/CPM/最小预算 min spend）
> 2. 排期与竞价机制（固定价 vs 竞价、库存抢占）
> 3. 定向与人群（频控、排除、画像、区域包预留）
> 4. 品牌度量（Brand Lift Study、品牌记忆度、Reach & Frequency）
> 5. 素材规格（时长/分辨率/码率/横竖版审核）
> 6. 创意设计（Challenge 策划、特效引擎、达人 UGC、Spark 版权矩阵）
> 7. 品牌 + 效果 + 直播协同的预算分配引擎
>
> 主线全部围绕 **"怎么买、怎么排、怎么量、怎么与效果协同"** 展开，
> 深度为既有品牌基础章节的 2.5 倍以上，可直接指导代理商与品牌方的实操投放。

---

## 目录

- [一、核心概念与架构](#一核心概念与架构)
  - [1.1 品牌广告的定义与底层逻辑](#11-品牌广告的定义与底层逻辑)
  - [1.2 品牌产品矩阵总表](#12-品牌产品矩阵总表)
  - [1.3 六大品牌产品逐一拆解](#13-六大品牌产品逐一拆解)
  - [1.4 品牌广告系统架构（ASCII）](#14-品牌广告系统架构ascii)
  - [1.5 售卖-排期-交付-测量全链路](#15-售卖-排期-交付-测量全链路)
  - [1.6 与效果广告的本质差异](#16-与效果广告的本质差异)
- [二、深度原理解析](#二深度原理解析)
  - [2.1 计价模型：CPD 与 CPM 的物理含义](#21-计价模型cpd-与-cpm-的物理含义)
  - [2.2 库存与排期原理：为什么 Takeover 一天只有 1 次](#22-库存与排期原理为什么-takeover-一天只有-1-次)
  - [2.3 定向原理：画像、频控、排除三件套](#23-定向原理画像频控排除三件套)
  - [2.4 度量原理：Brand Lift Study 与测量设计](#24-度量原理brand-lift-study-与测量设计)
  - [2.5 素材规格技术参数](#25-素材规格技术参数)
  - [2.6 Python 实操：品牌素材管理与曝光报告](#26-python-实操品牌素材管理与曝光报告)
  - [2.7 Go 实操：品牌排期调度与预算护栏](#27-go-实操品牌排期调度与预算护栏)
- [三、生产环境实战](#三生产环境实战)
  - [3.1 国货美妆新品上市全案（核心案例）](#31-国货美妆新品上市全案核心案例)
  - [3.2 电商大促：S 级档期抢量打法](#32-电商大促s-级档期抢量打法)
  - [3.3 游戏发测：Hashtag Challenge 拉新](#33-游戏发测hashtag-challenge-拉新)
  - [3.4 APP 增长：品牌声量 + 效果承接](#34-app-增长品牌声量--效果承接)
  - [3.5 代理商多品牌矩阵运营 SOP](#35-代理商多品牌矩阵运营-sop)
  - [3.6 直播带货：品牌流量为直播间蓄水](#36-直播带货品牌流量为直播间蓄水)
  - [3.7 品牌/效果/直播预算分配模型](#37-品牌效果直播预算分配模型)
  - [3.8 全周期最佳实践清单](#38-全周期最佳实践清单)
- [四、常见问题与排查](#四常见问题与排查)
  - [4.1 - 4.12 十二问十二答](#41--412-十二问十二答)
- [五、自测题](#五自测题)

---

## 一、核心概念与架构

### 1.1 品牌广告的定义与底层逻辑

TikTok Brand Solutions（品牌解决方案）是指以**曝光规模、情感资产、话题势能**
为交付目标的一整类广告产品，与以转化为目标的 Performance Ads 形成双轨体系。

它解决的是效果广告无法回答的三个商业问题：

1. **认知问题**：新品上市时，受众还不知道你是谁，何以谈转化。
2. **信任问题**：效果广告的点击后转化，会被"没听过""不敢买"拦截。
3. **势能问题**：复购、溢价、心智份额，来自持续的品牌记忆，而非单次点击。

品牌广告交付的不是"点击"，而是**确定性曝光 + 场景独占 + 互动参与**。
它的 KPI 不是 CPA/ROAS，而是：

- 品牌记忆度（Brand Recall）
- 广告记忆度（Ad Recall）
- 品牌好感度（Favorability）
- 购买意向（Purchase Intent）
- Reach 与 Frequency（触达人数与人均频次）
- 话题总播放（Hashtag Challenge 的生态指标）

> 一句话：效果广告负责"收割"，品牌广告负责"播种"。
> 没有播种的收割，成本会随竞争被抬到不可持续。

**品牌广告的五门硬性支柱**：

| 支柱 | 说明 | 典型交付物 |
|------|------|-----------|
| 独占感（Exclusivity） | Takeover/TopView 独占首屏或开屏，单日单用户仅 1 次 | 日曝光保底 |
| 全景感（Immersive） | 全屏无干扰的无声内容，完播率高 | 9:16 全竖屏 |
| 原生感（Native） | 与普通内容形态无差别，弹幕与推荐流融入 | 原生 Feed 卡 |
| 参与感（Participatory） | 用特效/话题让用户动手拍内容 | UGC 视频数 |
| 测量感（Measurable） | Brand Lift 等实验给到增量归因 | Lift 百分比 |

接下来把 6 个产品放到统一坐标系，理解它们在"漏斗"上的位置。

### 1.2 品牌产品矩阵总表

六个产品的本质差异：**售卖单位是"时间片/量级/互动"还是"CPM"**。

| 产品 | 英文 | 主要位 | 时长 | 计费 | 独占 | 目标形态 | 适用场景 |
|------|------|--------|------|------|------|----------|----------|
| TopView | TopView Ads | 首刷 3 秒/6 秒 | 6-60s | CPM/CPD 包量 | 单用户 1 次/日 | 第一眼冲击 | 新品上市、大促官宣 |
| Brand Takeover | Brand Takeover | 首刷开屏 / 详情页 | 3-5s 静态/视频 | CPD 固定价 | 单用户单日 1 次 | 全量霸屏 | 全国性曝光 |
| Branded Effects | Branded Effects (AR) | 特效相机 + 投稿页 | 不限 | CPD/包天 | 无 | 相机互动 + UGC | 全民玩法 |
| Hashtag Challenge | Branded Hashtag Challenge | 话题页 + TopView + Feed | 6-15s 主视频 | CPD 包天 | 话题独占 6 天+ | UGC 参与 | 转化参与、圈层种草 |
| Branded Mission | Branded Mission | 用户任务中心 | 任务 24-72h | 按参与付费 | 任务制 | 任务激励 | 长期种草/拉新 |
| Spark 品牌版 | Spark Ads（品牌版） | 达人原帖投放 | 原生时长 | CPM/出价 | 无独占 | 达人内容加权 | 日常品牌流量池 |

**一句话记忆**：
- 要"看得见" → TopView / Takeover（曝光独占）
- 要"玩起来" → Branded Effects / Hashtag Challenge（参与共创）
- 要"留得住" → Branded Mission（任务沉淀）
- 要"铺得开" → Spark 品牌版（达人矩阵加权）

### 1.3 六大品牌产品逐一拆解

**1.3.1 TopView Ads（首刷顶视图）**

- 位置：用户打开 App 首条内容（In-Feed 首帧），全屏竖屏。
- 可见时长：前 3 秒强制可见，随后可滑走；最长支持 60s 完整视频。
- 计费：以 CPM 或按天 CPD 售卖，需提前预订档期（通常 3-4 周）。
- 独占规则：同一用户单日内最多看到 1 次，不与其他 Takeover 叠加。
- 适合：新品宣发、大促开门、联名官宣。

实操要点：
- 前 3 秒必须把品牌名 + 核心卖点打完，否则 60%-70% 用户会滑走。
- 结尾 3-5 秒必须承接点击目标（落地页/详情页/直播间）。
- 声音设计同样重要：60% 以上用户在有声环境中消费。

**1.3.2 Brand Takeover（全域霸屏）**

- 位置：开屏（首刷）+ 部分详情页 / Tab 选中态。
- 形态：静态图（3-5s）或视频（5s），落地链接自定。
- 计费：典型按 CPD（Cost Per Day），价格随国家影响指数波动。
- 独占性：**全国同一用户 24 小时仅出现 1 次**，因此这条线可以视作
  "今天的品牌稀缺资源"。
- 限制：素材需提前进审核，TikTok 对违规内容零容忍，违规即丢档。

**1.3.3 Branded Effects（品牌特效/AR）**

- 本质：在 TikTok 相机等入口上线品牌自制 AR 特效（3D 面具、
  妆容滤镜、地标叠加等），用户在拍摄时主动使用并生成内容。
- 附带：效果页自动挂博主标签，用户发视频携带特效 → 免费流量再放大。
- 数据指标：使用量、拍摄量、发布量、平均使用时长、完播。
- 注意点：特效需要专门的 AR 制作（Effect House）或对接创意供应商，
  审核周期 5-10 个工作日，必须避开敏感政治/宗教/裸露关键词。

**1.3.4 Hashtag Challenge（话题挑战）**

- 位置：品牌话题页（Top 页）+ 全流强加 + 位置语句。
- 结构：品牌 6-15s 官方主视频 + 话题页 Collection 聚合所有 TAG 短视频。
- 参与机制：用户点击话题页 → 选择模板/特效 → 发布视频带 #标签。
- 独占成：6 天内用户不可见其他品牌同类 Challenge（排他）。
- 量级交付：官方只承诺曝光量级，参与量与 UGC 量取决于创意质量。

**1.3.5 Branded Mission（品牌任务）**

- 形态：用户完成任务（发视频、集赞、观看）获得平台奖励/品牌奖品。
- 适合：需要"可持续量产 UGC"的品牌（新品体验、探店）。
- 类比：这是"全民任务"模式的品牌版，比 Hashtag 更轻、反馈更快。
- 排期：通常 2-4 周，可与 Spark 品牌版搭配。

**1.3.6 Spark 品牌版（Brand Spark）**

- 形态：把用户/达人发布的原生内容直接作为品牌广告投放（Brand Spark），
  保留创作者账号 IP，展示品牌认证标记。
- 版权：需要创作者在 Spark Ads 中心授权。
- 玩法：TopView/Feed 形式投放达人内容 + 叠加 Lookalike 对达人粉丝的扩量。

### 1.4 系统架构（ASCII）

        ┌─────────────────────────────────────────────────────────┐
        │                   广告主 / 代理商（买方侧）                │
        │  品牌经理 · 创意团队 · 媒介代理 · 分析师                  │
        └──────────────┬──────────────────────────────────────────┘
                       │ Business API (business-api.tiktok.com/open_api/v1.3)
                       │ Header: Access-Token / Content-Type
                       ▼
        ┌─────────────────────────────────────────────────────────┐
        │                   TikTok 广告平台（卖方侧）               │
        │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
        │  │ 品牌售卖模块   │  │ 排期库存模块  │  │ 素材审核模块   │   │
        │  │ CPD/CPM 计价 │  │ 档期/独占/预留│  │ 规格/合规/权限 │   │
        │  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘   │
        │         └────────┬───────┴────────────────┘             │
        │                  ▼                                     │
        │  ┌──────────────────────────────────────────────┐       │
        │  │                竞价与预算投放器                  │       │
        │  │   TopView / Takeover / Effects / Challenge     │       │
        │  └──────────────────────┬───────────────────────┘       │
        │                         ▼                                │
        │  ┌──────────────────────────────────────────────┐       │
        │  │            Delivery / Frequency Capping       │       │
        │  │   1 次/用户/日 · 频控 · 地域排除 · 份额控制      │       │
        │  └──────────────────────┬───────────────────────┘       │
        │                         ▼                                │
        │  ┌──────────────────────────────────────────────┐       │
        │  │       定价结算模块（CPD/CPM 计费闭口）           │       │
        │  └──────────────────────┬───────────────────────┘       │
        │                         ▼                                │
        │  ┌──────────────────────────────────────────────┐       │
        │  │ 测量模块：Brand Lift / Reach / Frequency      │       │
        │  │ 实验组 vs 对照组 · 第三方（Nielsen等）         │       │
        │  └──────────────────────┬───────────────────────┘       │
        └─────────────────────────┼────────────────────────────────┘
                                  ▼
        ┌─────────────────────────────────────────────────────────┐
        │ 广告主侧数据：Pixel 事件 · CAPI · 转化回传 · GMC/商店       │
        └─────────────────────────────────────────────────────────┘

架构解读（四句）：

1. 品牌广告与效果广告**共用一个"投放 + 竞价引擎"**，差异在交付物。
2. 品牌模块核心是三件事：**计价（CPD/CPM）、库存（独占/排期）、审核**。
3. 频控在 Delivery 层全局施，任何产品都不能突破"1 次/用户/日"上限。
4. 测量模块独立于投放链路，由实验设计驱动，产出增量结论。

### 1.5 售卖 - 排期 - 交付 - 测量全链路

一条品牌广告从念头到上线的生命周期，可拆为 7 个阶段：

| 阶段 | 动作 | 责任方 | 关键数据/产物 |
| ---- | ---- | ------ | ----------- |
| 1 售卖 | 确认目标市场 + 档期 + 预算 | 代理商/平台销售 | 排期回执（IO） |
| 2 排期 | 占住独占位（Takeover/TopView） | 平台库存系统 | 档期 Dash 的 CPD 报价 |
| 3 创意 | 文案 + 视频/图片 + 特效落地 | 创意团队 + 审核 | 素材包（15s/30s/60s） |
| 4 预审 | 提交素材预审，避免丢档 | 平台审核 | 审核通过回执 |
| 5 上线 | Campaign 创建 + 排期绑定 | 媒介运营（API） | 上线时间戳 |
| 6 投放 | 独占 + 频控 + 智能优化 | 投放引擎 | 实时曝光/频次 |
| 7 测量 | Brand Lift / RT / Reach | 分析团队 | 实验报告 |

关键时点经验值（不同国家有差异，以下为通用基线）：
- TopView：至少提前 **14-21 天**锁位。
- Takeover：一般提前 **7-14 天**，大促与国家同销热搜期更长。
- Hashtag Challenge：前置 **20-30 天**（需要创意热 + 效果 + 配音乐）。
- 素材审核：广告素材 1-3 个工作日；AR 特效 5-10 个工作日。

### 1.6 与效果广告的本质差异

| 维度 | 品牌广告（Brand） | 效果广告（Performance） |
| ---- | ---------------- | ----------------------- |
| 目标函数 | 曝光 + Reach + Recall | Conversion / CPA / ROAS |
| 计费 | CPD / CPM | oCPM / CPA 出价 |
| 库存 | 独占稀缺资源（需预售） | 实时竞价池 |
| 预算 | 大包（几天几百万美元） | 日常小预算滚动 |
| 定向 | 宽泛 + 频控 + 排除 | 行为/意图/回传人群包 |
| 竞争 | 提前锁库，不实时竞价为主 | 全量竞价 |
| 度量 | Brand Lift / Ad Recall | 归因面板（7 日点击 1 日浏览） |
| 素材 | 高制作成本，讲究震撼 | 素材迭代快，AB 测频繁 |
| 优化 | 效果主要靠换量 + 换素材 | 自动化出价 + 频控调优 |
| 出现位 | 首屏/全屏/官方话题页 | Feed/Search/Reels 等 |

**为什么两者必须组合**（实证角度）：
- 纯效果广告：CTR 0.8-1.5%，CPA 随竞争上涨，深人群一阵子会衰减。
- 纯品牌广告：曝光大、质量高，但缺少转化承接，浪费在"看完就走"。
- 品牌 + 效果：品牌把认知做起来，效果广告在低成本下捡转化，形成
  "声量闸门 → 转化水渠"的漏斗结构，ROAS 稳定提升。

---

## 二、深度原理解析

### 2.1 计价模型：CPD 与 CPM 的物理含义

品牌广告的计价有两个核心概念，必须先吃透：

**CPD（Cost Per Day，按天计价）**

- 针对独占类产品（Takeover、TopView、Hashtag Challenge 的主视频位）。
- 买方支付"一天的独占曝光权"，无论当天实际展示多少次。
- 因为"单用户每天最多看 1 次"，所以一天的曝光上限 ≈ 该国活跃 DAU。
- 触达上限 = 1 × DAU，因此 CPD 报价会随目标市场 DAU 与热度上浮。

**CPM（每千次展示成本）**

- 针对非独占 / 可放量类（Spark 品牌版、部分 Effects）。
- 买方按实际展示量付费，可控性强，适合精细化频控。

| 产品 | 主计价 | 公式示意 | 预算起点参考 |
|------|--------|----------|-------------|
| TopView | CPM 或包天 | 单价 × 千次 / 1000 | 高预算国家 10 万 USD 起 |
| Brand Takeover | CPD | 每日固定价 | 数十国家 5-20 万 USD |
| Branded Effects | CPD / 包期 | 按特效使用排期 | 3-10 万 USD |
| Hashtag Challenge | CPD 包天 | 6 天 + 素材 | 视市场 15-50 万 USD |
| Branded Mission | 按任务/参与 | 任务奖金池 + 曝光 | 5-20 万 USD |
| Spark 品牌版 | CPM / 出价 | 千次成本 | 数百 USD 起可测 |

**min spend（最小预算）的物理意义**

- 品牌独占位有"素材被覆盖的最低量级"要求，预算太低无法保证测试有效。
- 例如某市场 TopView 单日最低 3 万美元，低于此不会把档期卖给你。
- 原因：独占位成本固定（CPD），预算需覆盖素材制作与测量成本。

**排期窗（time window）概念**

- Takeover/TopView 是"今天卖今天的量"。正因独占稀缺，平台采用预售。
- 你需要提前在销售侧递交 **排期申请（IO / Insertion Order）**。
- 一旦锁定，即使后来价格上浮，也用锁定价执行（固定价非竞价）。

### 2.2 库存与排期原理：为什么 Takeover 一天只有 1 次

**稀缺性的根源**

- TikTok 用户每天打开 App 若干次，但**首刷/开屏只有一次**被分配给品牌。
- 平台必须保证这一曝光的质量与独占性，于是按"DAU"来做库存上限。

**库存三层模型**

        品牌独占库存（首屏/开屏）         ← 固定且稀缺 N = 近似 DAU
              │
              ▼
        普通品牌库存（Feed 加权）          ← 可放量，受频控约束
              │
              ▼
        效果竞价库存（实时池）             ← 出价驱动，量最大

**排期算法（简化示意）**

- 每个市场每天有一张"档期表"，每个品牌产品是一个"格子"。
- 系统按先到先得 + 优先级（重点客户标记）分配独占格。
- 一单 Takeover 占满当天该国库存 → 其他品牌当天无法再买同点位。
- 冲突时：平台回退给"Waitlist"，允许补位或平移档期。

**为什么频控是 1 次/用户/日**

- 用 N（日活 ≤ 1 次/人）保证"不打扰"+ "独占稀缺感"，支撑高 CPD 定价。
- 既保护用户体验（不会看到同一条广告 8 遍），也保护品牌调性。

**和市场热度联动**

- 大促（双 11、黑五、超级碗、春节）期间，DAU 与情绪都在峰值，
  CPD 报价会上浮 20%-50%，且提前预售期更长。
- 反向思考：非热点期买 Takeover 相对便宜，适合预算紧张的品牌锁定心智。

### 2.3 定向原理：画像、频控、排除三件套

品牌广告的定向比效果广告"粗"，但依然有三类可用的控制：

**1. 地理定向（Geo Targeting）**

- 国家 / 省 / 州 / 城市 / 商圈（TikTok Shop 可到站点级）。
- 品牌通常取全国投放以最大化 Reach，因为独占位成本与地理无关。

**2. 画像定向（Demographic）**

- 年龄 / 性别 / 兴趣类目 / 设备 / 运营商等。
- 品牌常用"兴趣 + 宽年龄"来避免过度窄化导致的触达浪费。

**3. 频控（Frequency Capping）**

- 品牌侧可按用户设置最高展示频次（如 1-3 次/周）。
- 这是品牌唯一可以"主动控制不会轰炸用户"的旋钮，务必用上。

**4. 排除（Exclusion）**

- 排除特定竞品关键词 / 不适合的归类（如曾对某受众投放失败）。
- 品牌安全（Brand Safety）：自动排除暴力、情色、政治争议等上下文。

**品牌人群三件套（实战口诀）**

1. 第一步全量 + 频控：把可达人群全覆盖 1 遍。
2. 第二步 Lookalike：用高价值用户（购买者）放大到相似人群。
3. 第三步频控回流：控制高价值人群重复触达频次，保持新鲜感。

> 注意：品牌广告的 Touch Point 杀伤力远高于效果广告（大屏 + 全屏），
> 过量反而引发厌烦。频控不是"限制"，是品牌体验的一部分。

### 2.4 度量原理：Brand Lift Study 与测量设计

品牌广告效果不能用归因面板（那是效果广告的事），而要用**实验法**。

**Brand Lift Study（BLS）原理**

- 系统把目标人群随机分成**实验组**（看到广告）与**对照组**（看不到）。
- 对照组用"影子位"控制，保证基线可比。
- 通过后测问卷（在 App 内弹出）询问品牌记忆度、好感度、购买意向。
- 计算增量：两组指标的差值百分比，即为品牌广告带来的**提升**。

**关键指标解读**

| 指标 | 英文 | 含义 | 参考基准（经验） |
|------|------|------|----------------|
| 广告记忆度 | Ad Recall | 记得看过这条广告的人群占比 | 15%-40% |
| 品牌记忆度 | Brand Recall | 记得该品牌的人群占比 | 10%-30% |
| 好感度 | Favorability | 对品牌好感提升 | +5%-15% |
| 购买意向 | Purchase Intent | 愿意购买的比例提升 | +3%-10% |
| 触达 | Reach | 看过广告的独立用户数 | 目标人群覆盖率 |
| 频次 | Frequency | 平均每个用户看到的次数 | 1.0-2.5 为佳 |
| 关注/搜索 | Consideration | 去搜索 / 关注品牌的增量 | 视品类 |

**测量注意事项**

- 独立性：BLS 必须用平台或第三方（Nielsen 等）的实验设计，避免自证。
- 样本量：要得到显著的 Ad Recall 提升，需要足够大的覆盖人群。
- 时间窗：测量在 Campaign 结束后 2-7 天进行，避免记忆衰减。
- 对照：必须包含未投放的市场 / 人群作为 natural baseline。

**Combined Reach（组合触达）概念**

- 品牌前端曝光 + 效果后端触达的人群，有重叠也有增量。
- Combined Reach 报告能告诉你：品牌和效果各自触达了多少增量独立用户。
- 这让"声量与转化协同"有了量化口径：可以减少重复触达，把钱花在
  "品牌没触达的净增量"上。

**第三方测量**

- 使用 Nielsen / GFK 等独立机构验证 BLS 与媒体交付（交付画像、频次）。
- 用于代理商向广告主交付"独立审计"的可靠结论，负责任地签代投合同。

### 2.5 素材规格技术参数

**视频规格（Feed / TopView / Spark）**

| 参数 | 规格 |
|------|------|
| 比例 | 9:16 竖版（必选），16:9 / 1:1 横版可选 |
| 推荐分辨率 | ≥ 1080×1920（竖版），≥ 720p |
| 时长 | 5s / 15s / 30s / 60s（看产品） |
| 码率 | 建议 ≥ 2.5-4 Mbps |
| 编码 | H.264 / H.265（HEVC 更佳，码率省） |
| 帧率 | 24/30/60 fps，建议 30fps 平滑 |
| 体积 | ≤ 500MB 为安全线，越小预审越快 |
| 字幕 | 建议内嵌字幕，因多数用户静音滑动 |

**图片规格（Takeover 静态 / Spark 图片）**

| 参数 | 规格 |
|------|------|
| 比例 | 9:16 优先，1:1 可 |
| 分辨率 | ≥ 1080×1920 |
| 文件 | PNG / JPG，≤ 5MB |
| 文案 | 文字占比 ≤ 20%（减少违规） |

**审核要点（避免丢档）**

- 无政治、宗教、暴力、歧视、敏感新闻人物。
- 医疗/保健类需合规声明确认。
- 未成年保护：避免诱导未成年人消费。
- 落地页必须与素材内容一致，否则拒审或下线。
- AR 特效需遵守 Effect House 的政策，涉及 Logo 使用需授权。

### 2.6 Python 实操：品牌素材管理与曝光报告

用 `scripts/tiktok_api.py` 的封装方法管理品牌系列、上传素材、拉取曝光报告。
先看一个"品牌素材管理与投放"的完整脚本：

```python
from scripts.tiktok_api import TikTokAdsAPI, ApiConfig

# API Base: business-api.tiktok.com/open_api/v1.3
# Header: Access-Token / Content-Type
config = ApiConfig(
    advertiser_id="XXX_ACCOUNT_ID",
    access_token="XXX_ACCESS_TOKEN",
    base_url="https://business-api.tiktok.com/open_api/v1.3",
)

api = TikTokAdsAPI(config)

def upload_brand_creative() -> str:
    """上传品牌主视频素材，返回 media_id 供广告引用。"""
    media = api.upload_image({
        "file_name": "brand_hero_video.mp4",
        "image_file": "/data/creatives/brand_hero_video.mp4",
        # video: 也支持 api.upload_video，把视频放进 media library
    })
    media_id = media.data["media_info"]["media_id"]
    print(f"[OK] media_id = {media_id}")
    return media_id

def list_brand_media(account_id: str):
    """列出媒体库中已上传的品牌素材。"""
    resp = api.get_media_library(account_id)
    for m in resp.data.get("list", []):
        print(m["media_id"], m.get("video_url", m.get("image_url")))

def create_brand_campaign(account_id: str, name: str, budget: float) -> str:
    """
    创建一个品牌系列的 Campaign。
    品牌 TopView 用 VIDEO_VIEWS 目标，独占曝光位。
    """
    campaign = api.create_campaign(account_id, {
        "campaign_name": name,
        "objective_type": "VIDEO_VIEWS",   # 品牌以完播/曝光为目标
        "budget_mode": "BUDGET_MODE_TOTAL", # 总预算（包天）
        "budget": budget,                  # 例如 250000.00 USD
        "operation_status": "ENABLE",
    })
    return campaign.data["campaign_id"]

def create_brand_effect_adgroup(account_id, campaign_id, geo,
                                placement, capping=1):
    """
    创建品牌 Adgroup，做地理 + 频控。
    placement 固定为 TikTok 独占位。
    """
    adgroup = api.create_adgroup(account_id, {
        "campaign_id": campaign_id,
        "adgroup_name": "Brand TopView - FR 频控1",
        "objective_type": "VIDEO_VIEWS",
        "placement_type": [placement],        # PLACEMENT_TYPE_TIKTOK
        "budget_mode": "BUDGET_MODE_TOTAL",
        "budget": 250000.0,
        "bid_type": "BID_TYPE_CPM",           # 品牌按 CPM 出价
        "gender": "NO_LIMIT",
        "age_groups": ["AGE_13_17","AGE_18_24","AGE_25_34",
                       "AGE_35_44","AGE_45_54"],
        "geo_locations": {"regions": [geo]},
        "frequency_capping": {
            "cap": capping,                    # 频控：每人最多 1 次/日
            "duration": "ONE_DAY",
        },
        "brand_safety": {
            "avoid_sensitive_content": True,   # 品牌安全排除
        },
    })
    return adgroup.data["adgroup_id"]

def attach_brand_creative(account_id, adgroup_id, media_id, url):
    """把素材挂到广告，并给落地页跳转。"""
    ad = api.create_ad(account_id, {
        "adgroup_id": adgroup_id,
        "creatives": [
            {
                "video_id": media_id,          # 上传后的视频
                "title": "国货美妆新品上市",
                "display_name": "YourBrand 新品",
                "click_tracking_url": url,     # 点击跳转落地页/直播间
            }
        ],
    })
    return ad.data["ad_id"]

def run_brand_workflow():
    """一条龙的品牌投放流程。"""
    accounts = api.list_accounts("XXX_ACCOUNT_ID")
    account_id = accounts.data["list"][0]["advertiser_id"]

    media_id = upload_brand_creative()
    list_brand_media(account_id)

    # 查询可用的 objective / bid / placement 选项，避免硬编码错误
    objs = api.get_campaign_objective_options()
    bids = api.get_bid_strategy_options()
    place = api.get_placement_options()   # Feed/Search/Post/Marketplace/Series/Live
    print("objectives:", objs)
    print("bid strategies:", bids)
    print("placements:", [p["code"] for p in place])

    campaign_id = create_brand_campaign(account_id, "Brand TopView FR 2.14",
                                        250000.0)
    adgroup_id = create_brand_effect_adgroup(
        account_id, campaign_id, "FR", "PLACEMENT_TYPE_TIKTOK")
    ad_id = attach_brand_creative(account_id, adgroup_id, media_id,
                                  "https://yourbrand.com/new")
    print("campaign_id:", campaign_id)
    print("adgroup_id :", adgroup_id)
    print("ad_id      :", ad_id)

    # 拉取曝光报告：品牌以 impressions / reach / frequency 为主
    report = api.get_report(
        account_id,
        date_start="2026-02-01",
        date_end="2026-02-14",
        level="AD_GROUP",
        insights=[
            "impressions", "reach", "frequency",
            "video_views", "video_views_3s", "cost_per_mille",
            "cpc", "ctr", "video_play_actions",
        ],
    )
    for row in report.data.get("list", []):
        print(row["adgroup_id"],
              f"{row.get('metrics', {}).get('impressions')} impressions, "
              f"CPM {row.get('metrics', {}).get('cost_per_mille')}")

if __name__ == "__main__":
    run_brand_workflow()
```

**品牌效果报告解读**

- impressions：独占位的总展示，应接近"目标市场 DAU × 天数"。
- reach：去重独立用户，验证是否真做到"1 次/人/日"。
- frequency = impressions / reach；理想 1.0-3.0。
- cost_per_mille：用于与 CPD 对比是否超买，防止亏本。
- video_views_3s：3 秒可见完播，衡量首屏冲击质量。

### 2.7 Go 实操：品牌排期调度与预算护栏

生产环境常见需求：多国家、多档期、多品牌广告的**排期与预算护栏**。
用 Go 写一个调度器，保证同一账户下独占位不重叠、预算不超上限：

```go
package brand

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"strings"
	"time"
)

// APIClient 封装 TikTok Marketing API v1.3 的只读/写操作
type APIClient struct {
	BaseURL     string // https://business-api.tiktok.com/open_api/v1.3
	AccessToken string
	HTTP        *http.Client
}

func NewAPIClient(token string) *APIClient {
	return &APIClient{
		BaseURL:     "https://business-api.tiktok.com/open_api/v1.3",
		AccessToken: token,
		HTTP:        &http.Client{Timeout: 15 * time.Second},
	}
}

// Schedule 代表一次品牌排期（独占位格）
type Schedule struct {
	AdvertiserID string `json:"advertiser_id"`
	CampaignID   string `json:"campaign_id"`
	Market       string `json:"market"` // 例如 FR / DE / US
	Date         string `json:"date"`   // YYYY-MM-DD
	Product      string `json:"product"`// TAKE_OVER / TOP_VIEW
	BudgetUSD    float64 `json:"budget_usd"`
}

// 市场与预算护栏常量
var maxBudgetPerMarket = map[string]float64{
	"US": 400000, "FR": 200000, "DE": 200000, "JP": 150000,
}

// EnsureSinglePerDay 校验同一市场同一天不允许两条独占品牌位
func EnsureSinglePerDay(scheds []Schedule) error {
	seen := map[string]string{}
	for _, s := range scheds {
		key := s.Market + "_" + s.Date
		if prev, ok := seen[key]; ok {
			return fmt.Errorf("档期冲突: %s 与 %s 重叠（%s %s 同一天）",
				prev, s.CampaignID, s.Market, s.Date)
		}
		seen[key] = s.CampaignID
	}
	return nil
}

// CheckBudget 校验当日总预算不超过市场护栏
func CheckBudget(scheds []Schedule) error {
	dayBudget := map[string]float64{}
	for _, s := range scheds {
		dayBudget[s.Market] += s.BudgetUSD
	}
	for market, spent := range dayBudget {
		if cap, ok := maxBudgetPerMarket[market]; ok && spent > cap {
			return fmt.Errorf("%s 当日预算 %.0f 超护栏 %.0f USD",
				market, spent, cap)
		}
	}
	return nil
}

// FetchReport 调 get_report 拉取每日曝光，用于回填实际量级
func (c *APIClient) FetchReport(ctx context.Context,
	advertiserID, dateStart, dateEnd, level string) (map[string]float64, error) {

	body := fmt.Sprintf(`{
        "advertiser_id": %q,
        "report_type": "BASIC",
        "dimensions": ["stat_time_day"],
        "data_level": %q,
        "start_date": %q,
        "end_date": %q,
        "metrics": ["impressions", "reach", "frequency"]
    }`, advertiserID, level, dateStart, dateEnd)

	req, err := http.NewRequestWithContext(ctx, http.MethodPost,
		c.BaseURL+"/report/get/", strings.NewReader(body))
	if err != nil {
		return nil, err
	}
	req.Header.Set("Access-Token", c.AccessToken)
	req.Header.Set("Content-Type", "application/json")

	resp, err := c.HTTP.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	var out struct {
		Code int `json:"code"`
		Data struct {
			List []struct {
				Metrics struct {
					Impressions float64 `json:"impressions"`
					Reach       float64 `json:"reach"`
					Frequency   float64 `json:"frequency"`
				} `json:"metrics"`
			} `json:"list"`
		} `json:"data"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&out); err != nil {
		return nil, err
	}

	result := map[string]float64{}
	for _, row := range out.Data.List {
		result["impressions"] += row.Metrics.Impressions
		result["reach"] += row.Metrics.Reach
	}
	if result["reach"] > 0 {
		result["frequency"] = result["impressions"] / result["reach"]
	}
	return result, nil
}

// Orchestrate 生产级编排：冲突校验 -> 预算护栏 -> 拉报告
func Orchestrate(ctx context.Context, client *APIClient,
	scheds []Schedule) error {
	if err := EnsureSinglePerDay(scheds); err != nil {
		return err
	}
	if err := CheckBudget(scheds); err != nil {
		return err
	}
	for _, s := range scheds {
		if _, err := client.FetchReport(ctx, s.AdvertiserID,
			s.Date, s.Date, "AD_GROUP"); err != nil {
			if strings.Contains(err.Error(), "rate limit") {
				return errors.New("触发限流，请重试或分片")
			}
			return err
		}
	}
	return nil
}
```

Go 实现要点：
- EnsureSinglePerDay 是"独占位不重叠"的硬约束，所有代理商脚本都要有。
- CheckBudget 防呆，避免"手滑把 5 万输成 50 万"。
- FetchReport 对 rate limit 做显式判断，因为品牌大报表量大，容易触发限流。

---


### 2.8 Python 实操：品牌受众与关键词管理

品牌广告虽然以宽泛定向为主，但"排除"与"回流"依然依赖受众与关键词 API。
下面演示受众包管理、负面关键词与自定义转化事件的用法：

```python
from scripts.tiktok_api import TikTokAdsAPI, ApiConfig

api = TikTokAdsAPI(ApiConfig(
    advertiser_id="XXX_ACCOUNT_ID",
    access_token="XXX_ACCESS_TOKEN",
    base_url="https://business-api.tiktok.com/open_api/v1.3",
))

def manage_brand_audiences(account_id: str):
    """品牌侧人群：Lookalike + 排除包。"""

    # 1. 查看现有受众
    existing = api.list_audiences(account_id)
    for a in existing.data.get("list", []):
        print("受众:", a["audience_id"], a["name"], a["type"])

    # 2. 用历史购买者创建 Lookalike，供品牌效果回流使用
    lookalike = api.create_audience(account_id, {
        "name": "BL_LA_美妆购买者_1%",
        "type": "LOOKALIKE",
        "lookalike_spec": {
            "source_audience_id": "CUSTOM_PURCHASER_ID",
            "country_code": ["FR"],
            "ratio": 0.01,          # 1% 最接近源人群
        },
    })
    la_id = lookalike.data["audience_id"]
    print("Lookalike:", la_id)

    # 3. 清理不再使用的受众，避免数据混乱
    # api.delete_audience(account_id, "STALE_AUDIENCE_ID")

    return la_id

def block_negative_keywords(account_id: str, adgroup_id: str):
    """为品牌 adgroup 添加负面关键词，避免碰竞品与敏感词。"""

    existing = api.list_keywords(account_id, adgroup_id)
    print("已有关键词:", existing.data.get("list", []))

    added = api.create_keywords(account_id, adgroup_id, [
        {"keyword": "竞品A", "match_type": "PHRASE"},
        {"keyword": "敏感话题B", "match_type": "EXACT"},
        {"keyword": "负面词C", "match_type": "BROAD"},
    ])
    for kw in added.data.get("list", []):
        print("新增关键词:", kw["keyword_id"], kw["keyword"])

    # 需要移除时
    # api.delete_keywords(account_id, ["KW_ID_1", "KW_ID_2"])

def ensure_conversion_event(account_id: str):
    """品牌效果承接需要完整的事件回传。"""

    events = api.list_conversion_events(account_id)
    names = [e.get("event_name") for e in events.data.get("list", [])]
    print("已配置事件:", names)

    if "ViewContent_Beauty" not in names:
        custom = api.create_custom_conversion(account_id, {
            "name": "ViewContent_Beauty",
            "event_type": "WEB_EVENT",
            "filters": [
                {"field": "event_name", "operator": "EQ",
                 "value": "ViewContent", "subfilters": [
                     {"field": "content_type", "operator": "EQ",
                      "value": "beauty"}]},
            ],
        })
        print("自定义转化已建:", custom.data["conversion_id"])

if __name__ == "__main__":
    la = manage_brand_audiences("XXX_ACCOUNT_ID")
    block_negative_keywords("XXX_ACCOUNT_ID", "ADGROUP_ID")
    ensure_conversion_event("XXX_ACCOUNT_ID")
```

**为什么品牌侧也要管关键词？**

1. 排除竞品：避免品牌广告出现在竞品搜索/话题上下文中。
2. 敏感词拦截：规避政治、医疗、宗教争议语境，保护品牌调性。
3. 精准回流：把关键词命中的"高意向人群"喂给效果承接，提高 ROAS。

### 2.9 Python 实操：Brand Lift 对照分析与报告解读

品牌投放后的复盘，需要把曝光/参与数据与 Brand Lift 结果放一起交叉验证。

```python
from scripts.tiktok_api import TikTokAdsAPI, ApiConfig

api = TikTokAdsAPI(ApiConfig(
    advertiser_id="XXX_ACCOUNT_ID",
    access_token="XXX_ACCESS_TOKEN",
    base_url="https://business-api.tiktok.com/open_api/v1.3",
))

def brand_lift_summary(account_id: str, start: str, end: str):
    """汇总品牌投放曝光数据，评估是否满足 BLS 的触达前提。"""

    report = api.get_report(
        account_id,
        date_start=start,
        date_end=end,
        level="AD",
        insights=[
            "impressions", "reach", "frequency",
            "video_views", "video_views_3s",
            "video_watched_6s", "video_watched_full",
            "cost_per_mille", "cpv",
        ],
    )

    rows = report.data.get("list", [])
    if not rows:
        print("无数据，请检查日期与 level 参数")
        return

    total_imp = sum(r["metrics"].get("impressions", 0) for r in rows)
    reach = sum(r["metrics"].get("reach", 0) for r in rows)
    freq = total_imp / reach if reach else 0
    cpm = sum(r["metrics"].get("cost_per_mille", 0) for r in rows) / len(rows)
    ctr = sum(r["metrics"].get("ctr", 0) for r in rows) / len(rows)

    print(f"总曝光      : {total_imp:,}")
    print(f"触达 (reach): {reach:,}")
    print(f"平均频次    : {freq:.2f}")
    print(f"平均 CPM    : {cpm:.2f} USD")
    print(f"平均 CTR    : {ctr:.2%}")

    # 品牌侧判断
    if freq < 1.0:
        print("警告: 频次<1, 说明存在大量未触达人群, 检查定向/库存")
    if ctr > 0.03:
        print("优秀: 首屏内容吸引度高, 适合继续追加品牌预算")
    else:
        print("提示: 素材点击率偏低, 建议优化前3秒钩子")

if __name__ == "__main__":
    brand_lift_summary("XXX_ACCOUNT_ID", "2026-02-01", "2026-02-14")
```

**交叉验证口径**

- BLS 的 Ad Recall 提升，应与曝光量级（impressions）、完播率（3s 可见）
  同向验证：曝光够大 + 完播够高，Recall 才有底气。
- 若 Recall 高但频率 > 3.0，说明是"轰炸出来的记忆"，
  对品牌好感度可能是负贡献，下轮调低频控。

### 2.10 Go 实操：素材审核状态机

品牌素材必须过审才能上线，丢档风险极高。
用 Go 实现一个"提交 -> 轮询审核 -> 自动重试"的状态机：

```go
package brand

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"strings"
	"time"
)

type ReviewStatus int

const (
	ReviewPending ReviewStatus = iota
	ReviewApproved
	ReviewRejected
)

type ReviewResult struct {
	Status ReviewStatus
	Reason string
}

// PollReview 轮询素材审核状态，最多尝试 12 次，间隔 30s
func PollReview(ctx context.Context, client *APIClient,
	accountID, mediaID string) (*ReviewResult, error) {

	endpoint := client.BaseURL + "/media_library/get/"
	for attempt := 1; attempt <= 12; attempt++ {
		select {
		case <-ctx.Done():
			return nil, ctx.Err()
		case <-time.After(30 * time.Second):
		}

		body := fmt.Sprintf(`{
            "advertiser_id": %q,
            "filtering": [{"field": "media_id", "value": %q}]
        }`, accountID, mediaID)

		req, _ := http.NewRequestWithContext(ctx, http.MethodPost,
			endpoint, strings.NewReader(body))
		req.Header.Set("Access-Token", client.AccessToken)
		req.Header.Set("Content-Type", "application/json")

		resp, err := client.HTTP.Do(req)
		if err != nil {
			return nil, err
		}

		var out struct {
			Data struct {
				List []struct {
					MediaID string `json:"media_id"`
					Status  string `json:"status"`
					Detail  string `json:"detail"`
				} `json:"list"`
			} `json:"data"`
		}
		decErr := json.NewDecoder(resp.Body).Decode(&out)
		resp.Body.Close()
		if decErr != nil {
			return nil, decErr
		}

		for _, m := range out.Data.List {
			if m.MediaID != mediaID {
				continue
			}
			switch m.Status {
			case "APPROVED":
				return &ReviewResult{Status: ReviewApproved}, nil
			case "REJECTED":
				return &ReviewResult{Status: ReviewRejected,
					Reason: m.Detail}, nil
			}
		}
		fmt.Printf("[attempt %d] 素材 %s 仍在审核中...\n", attempt, mediaID)
	}
	return &ReviewResult{Status: ReviewPending,
		Reason: "审核超时，需人工介入"}, nil
}
```

**为什么审核必须自动化？**

- 品牌档期是按天锁定的，素材当天不过审 = 当天曝光作废。
- 人工盯审核容易漏，脚本每 30s 轮询 + 上线前自动告警，能救回档期。
- 被拒时立刻给出 Reason，创意团队可以连夜改素材，不丢第二天档期。

---

### 2.11 全球主要市场售卖与计价参考（经验值）

以下为公开行业经验口径，非官方报价，供预算规划与对价参考：

| 市场 | 典型 CPD 区间 (Takeover) | 等效 CPM 粗估 | 预售提前量 | 竞争热度 |
|------|------------------------|--------------|-----------|---------|
| 美国 US | 20-40 万 USD | $3-6 | 3-4 周 | 极高 |
| 日本 JP | 8-15 万 USD | $2-5 | 3-4 周 | 高 |
| 英国 UK | 8-12 万 GBP | $3-6 | 2-3 周 | 高 |
| 法国 FR | 5-10 万 EUR | $2-5 | 2-3 周 | 中高 |
| 德国 DE | 5-10 万 EUR | $2-5 | 2-3 周 | 中高 |
| 东南亚（泰国/越南） | 1-4 万 USD | $1-3 | 1-2 周 | 中 |
| 印尼 ID | 1-3 万 USD | $1-3 | 1-2 周 | 中 |
| 中东（沙特/阿联酋） | 2-5 万 USD | $2-4 | 2 周 | 中高 |
| 巴西 BR | 1-3 万 USD | $1-2.5 | 1-2 周 | 中 |

**使用注意**

- 以上为行业经验区间，实际以销售回执（IO）为准。
- 大促/重大节日 CPD 会上浮 20%-50%，预售窗口也会拉长。
- 多市场打包（Multi-market IO）常有梯度折扣，代理商可谈组合价。

### 2.12 Python 实操：品牌 Campaign 全生命周期管理

投放中经常需要批量暂停、恢复、删除过期 Campaign，用脚本最安全：

```python
from scripts.tiktok_api import TikTokAdsAPI, ApiConfig

api = TikTokAdsAPI(ApiConfig(
    advertiser_id="XXX_ACCOUNT_ID",
    access_token="XXX_ACCESS_TOKEN",
    base_url="https://business-api.tiktok.com/open_api/v1.3",
))

def lifecycle_demo(account_id: str, campaign_id: str):
    """演示品牌 Campaign 的查询/暂停/恢复/删除全流程。"""

    # 1. 查询
    detail = api.get_campaign(account_id, campaign_id)
    print("Campaign:", detail.data["campaign_id"],
          detail.data.get("campaign_name"))

    # 2. 列表 + 过滤
    camp_list = api.list_campaigns(account_id,
        filtering=[{"field": "objective_type",
                    "value": "VIDEO_VIEWS"}])
    for c in camp_list.data.get("list", []):
        print("  -", c["campaign_id"], c["campaign_name"], c["status"])

    # 3. 暂停（例如品牌档期结束）
    api.pause_campaign(account_id, campaign_id)

    # 4. 改预算（例如大促加量）
    api.update_campaign(account_id, campaign_id,
        {"budget": 400000.0, "budget_mode": "BUDGET_MODE_TOTAL"})

    # 5. 恢复
    api.resume_campaign(account_id, campaign_id)

    # 6. 清理（只演示注释，避免误删真实数据）
    # api.delete_campaign(account_id, campaign_id)

def manage_adgroup_lifecycle(account_id: str, adgroup_id: str):
    """广告组维度同理：暂停/恢复/删除。"""

    adgroups = api.list_adgroups(account_id,
        filtering=[{"field": "adgroup_id", "value": adgroup_id}])
    for ag in adgroups.data.get("list", []):
        print("AdGroup:", ag["adgroup_id"], ag["status"])

    api.pause_adgroup(account_id, adgroup_id)
    api.resume_adgroup(account_id, adgroup_id)

    ads = api.list_ads(account_id, adgroup_id)
    for ad in ads.data.get("list", []):
        print("Ad:", ad["ad_id"], ad.get("status"))
        api.pause_ad(account_id, ad["ad_id"])
        api.resume_ad(account_id, ad["ad_id"])
        api.update_ad(account_id, ad["ad_id"],
            {"creatives": [{"video_id": "NEW_MEDIA_ID"}]})

if __name__ == "__main__":
    lifecycle_demo("XXX_ACCOUNT_ID", "CAMPAIGN_ID")
    manage_adgroup_lifecycle("XXX_ACCOUNT_ID", "ADGROUP_ID")
```

**全生命周期管理要点**

- 品牌档期有硬性起止：结束后必须暂停，避免预算空跑。
- 换素材先暂停 → 更新 → 恢复，避免中间态被展示。
- 所有写操作建议加审计日志（谁在什么时间改了预算），
  代理商多账户场景下这是基本的操作纪律。

---

## 三、生产环境实战

### 3.1 国货美妆新品上市全案（核心案例）

**背景**

某国货美妆品牌「花颜堂」推出一款主打养肤的新粉底液 ANTI-06，
目标市场：法国（FR）+ 德国（DE）+ 日本（JP）。
上市预算：整体 90 万 USD，其中品牌广告 60 万、效果承接 30 万。

**目标**

- 上市首月品牌记忆度提升 ≥ 12 个百分点。
- 触达目标人群 ≥ 1800 万（法德日合计）。
- Hashtag Challenge 参与视频 ≥ 8 万条。
- 效果承接 ROAS ≥ 3.2，CPA 落在品类中位数以下。

**策略组合（品牌 + 效果 + Engagement）**

| 层 | 产品 | 动作 | 预算 | 目标 |
|----|------|------|------|------|
| 认知 | TopView FR 首日 | 新品官宣 15s | 12 万 | Ad Recall 25%+ |
| 认知 | Takeover FR/DE/JP 首周 | 全国霸屏 3s | 20 万 | Reach 1 次/人 |
| 参与 | Hashtag Challenge #ANTI06Glow | 6 天 + 特效 | 18 万 | UGC 8 万条 |
| 互动 | Branded Effects「发光肌」AR 妆效 | 全民试用 | 6 万 | 使用 30 万次 |
| 承接 | Spark 品牌版 + 达人矩阵 | 40 位达人原帖投放 | 4 万 | 日常流量池 |
| 转化 | 效果 Campaign（CONVERSIONS） | 落地页/直播间承接 | 30 万 | ROAS ≥ 3.2 |

**投放节奏（时间窗）**

- T-30：定档、排期申请（TopView 提前 21 天锁位）。
- T-21：素材进入预审，规避敏感词，确保不丢档。
- T-14：AR 特效进 Effect House 审核（预留 10 个工作日）。
- T-7：TopView + Takeover 全部创建，用 v1.3 API 绑定排期。
- T-0：上线首日。品牌位爆发，同时 Spark 达人矩阵起量。
- T+1~6：Hashtag Challenge 主推 6 天，TopView 重新聚焦高潜力人群。
- T+7：Brand Lift 测量开始，对照组启用。
- T+14~30：效果承接拉满，配合品牌余热捡转化。

**量化结果（假设案例）**

| 指标 | 目标 | 实际 | 达标 |
|------|------|------|------|
| Ad Recall (FR) | 25% | 31% | ✅ |
| Brand Recall (三市场) | ≥12pt | +15pt | ✅ |
| Reach | 1800 万 | 2150 万 | ✅ |
| Frequency | ≤2.5 | 1.8 | ✅ |
| UGC 视频 | 8 万 | 9.6 万 | ✅ |
| Challenge 播放 | 2 亿 | 3.1 亿 | ✅ |
| 效果 ROAS | 3.2 | 3.7 | ✅ |
| 粉底液首月 GMV | — | 220 万 USD | ✅ |

**复盘经验（可复制）**

1. 品牌 + 效果联动时，效果广告在品牌爆发期后 24-48h 起量最划算，
   因为认知已被品牌位"预热"，点击成本下降了 25%-35%。
2. Hashtag Challenge 的 UGC 量取决于创意"易上手性"：模板与特效越简单，
   参与率越高。ANITI-06 用"一键上脸试妆"特效，把门槛降到 1 键。
3. 频控别贪多：护肤人群对反复打扰敏感，频控 1.0-2.0 最优，
   超过 3.0 后好感度测试反而下滑。
4. AR 特效往往是被低估的免费放大器：一条 UGC 自带传播带来的
   "reach 增量"比花钱买曝光便宜得多。

### 3.2 电商大促：S 级档期抢量打法

**场景**：双 11 / 黑五（美国）/ 春节（越南）等 S 级节点。

**特点**

- 大盘 DAU 与竞品投放同步激增，CPD 上浮 20%-50%。
- 品牌位库存被抢空的速度极快，"先到先得 + 重点客户优先"。
- 用户情绪峰值，转化承接效果好，适合"品牌引爆 + 效果收割"双开。

**抢量 SOP**

1. 提前 45-60 天锁定关键档期（竞品也可能提前锁）。
2. 用"重点客户"身份提交 IO，争取优先级与锁定价。
3. 素材按"节日主题"定制：春节用红金、黑五用库存倒计时。
4. 大促前一天 TopView 引爆，大促当天 Takeover 全量，之后 Spark 承接。
5. 频控放宽到 2-3 次/周，因为节日用户对广告容忍度更高。

**预算分配示例（黑五，美国）**

| 产品 | 天数 | 预算 | 说明 |
|------|------|------|------|
| TopView 首日 | 1 | 12 万 | 黑五开幕官宣 |
| Takeover 黑五当天 | 1 | 15 万 | 全量霸屏 |
| Spark 品牌版 | 7 天 | 8 万 | 达人操练 + 优惠券 |
| 效果承接 | 10 天 | 20 万 | CONVERSIONS 落地优惠券页 |

节奏要点：品牌引爆把"要不要买"变成"去哪买"，效果承接负责"转化"，
避免大促期间即使广告量大但转化率被认知瓶颈拖累。

### 3.3 游戏发测：Hashtag Challenge 拉新

**场景**：某二次元 RPG 游戏新版本公测，需要拉新 + 预约转正式。

**特点**

- 游戏用户的参与欲强，Hashtag Challenge 天然适合"晒角色/晒战绩"。
- 需要配合达人（游戏 KOL）示范玩法，降低上手门槛。

**打法**

1. Challenge 主题：`#一起来当冒险王` 让用户用 AR 特效扮演游戏角色。
2. 主视频 6-15s，突出独特玩法 + 角色立绘，音效炸裂。
3. 招募 50-100 位游戏 KOC 发挑战视频，为话题页提供初始势能。
4. 用 Spark 品牌版放大头部达人内容，直达 LTV 高用户。
5. 落地页直接接下载/预约，配合效果广告（APP_INSTALL）承接一波。

**量化**

| 指标 | 目标 |
|------|------|
| Challenge 播放 | 8000 万 |
| UGC 视频 | 5 万条 |
| 预约/下载 CPA | 比纯效果低 30% |
| 7 日留存 | 由品牌预热带来的新用户留存更高 |

### 3.4 APP 增长：品牌声量 + 效果承接

**场景**：出海社交/工具 APP，需要从"没听过"到"下载"。

**打法**

- 品牌：Takeover + TopView 建立"这款 APP 是什么"的认知。
- 承接：效果 Campaign（APP_INSTALL / APP_PROMOTION）精准拉安装。
- 关键：品牌素材主打"爽点 3 秒"，效果素材主打"功能 + 福利"。
- Spark 品牌版：找真用户发使用实录，用原生内容拉升可信度。

**协同量化**

- 纯效果：安装成本 C1 = $8-15（红海品类更高）。
- 品牌 + 效果：因为认知度提升，效果端 CPA 可下降 20%-40%。
- 若品牌位 ROI 不佳，可退而求其次只投后链路，但要接受天花板。

### 3.5 代理商多品牌矩阵运营 SOP

代理商管理多个品牌（美妆/快消/游戏/电商）时，需统一的品牌运营 SOP。

**SOP 七个步骤**

1. 品牌建档：目标市场、预算、品类、素材库、版权信息。
2. 档期预占：以周为粒度制作排期 Gantt，避免同市场撞单。
3. 素材资产：媒体库统一管理，复用已验证的高 ROAS 素材。
4. 投放自动化：用 tiktok_api.py 批量创建/更新/暂停品牌 Campaign。
5. 监控看板：reach/frequency/CPM 实时监控，异常即告警。
6. 测量：品牌用 BLS，效果用归因，统一口径汇总给客户。
7. 复盘：每次大促后输出"品牌-效果协同效率"复盘报告。

**多账户护栏（Go/脚本级别）**

- EnsureSinglePerDay：避免两个品牌同市场同天打 Takeover 撞车。
- CheckBudget：每个客户有自己的预算护栏，防呆超支。
- 版权白名单：Spark 需要作者授权，建立授权台账，避免侵权下线。

代理商的差异化价值 = 把"品牌广告怎么买"提升到"如何与效果协同",
帮客户把预算花出"1+1>2"的组合效率，而不仅是单纯卖流量。

### 3.6 直播带货：品牌流量为直播间蓄水

**场景**：美妆 / 服饰直播间，需要开播前蓄水、开播中引流。

**打法**

- 开播前 24-72h：TopView / Spark 投放预约卡，预告直播间。
- 开播中：品牌素材直接连直播间（click_tracking_url 指向直播间）。
- 达人与主播联动：主播原帖用 Spark 品牌版放大，承接粉丝进直播间。

**直播承接漏斗**

        品牌预告（心智预热）
              │
              ▼
        直播间预约（预约用户）
              │
              ▼
        开播引流（直播间在线人数）
              │
              ▼
        实时转化（GMV / 客单）

**量化**

| 指标 | 目标 |
|------|------|
| 预约人数 | ≥ 直播开播流量的 30% |
| 直播间在线峰值 | 品牌预热后提升 30-50% |
| GMV | 直播间人均客单提升 15%+ |
| 退货率 | 因预热提升信任，退货率下降 |

### 3.7 品牌 / 效果 / 直播预算分配模型

生产环境最难的决策：三笔预算怎么切？给出一个可落地的分配模型。

**总预算（B）拆三份**

- 品牌包：B × 40%-50%（认知 + 参与）
- 效果包：B × 35%-45%（转化承接）
- 直播/内容包：B × 10%-20%（直播间预热 + 达人矩阵）

**动态调整规则（feedback loop）**

1. 若品牌位 Ad Recall 提升明显（≥ 目标），效果端自然受益，
   可把品牌包余量转投效果，收割增量。
2. 若效果 CPA 劣于品类中位数且品牌曝光充足，说明承接素材差，
   此时应加大 Spark 品牌版提升真实感，而非加效果预算。
3. 若直播间 GMV 稳定，每周把 5%-10% 预算动态加给直播间预热。

**一个决策伪代码**

```
if brand_recall_lift > target:
    shift 10% brand_budget -> performance
elif cpa > category_median and reach_ok:
    shift budget -> spark_brand  # 提升真实感
elif live_gmv_rising:
    shift 5-10% -> live_warmup
else:
    keep ratio  # 稳态
```

### 3.8 全周期最佳实践清单

**上线前**

- [ ] 锁定档期（TopView 提前 21 天，Hashtag 提前 30 天）。
- [ ] 素材预审 + AR 特效审核预留 10 个工作日。
- [ ] 确认落地页/直播间可用，跳转一致。
- [ ] 设定频控（1-2 次/日）与品牌安全排除。

**投放中**

- [ ] 每日监控 reach/frequency/CPM，盯"独占位是否兑现"。
- [ ] 若曝光远低于目标 DAU，联系销售补充量级。
- [ ] Spark 达人内容若侵权风险，随时下线。

**投放后**

- [ ] 运行 Brand Lift Study（2-7 天窗口）。
- [ ] 输出品牌-效果协同复盘（reach 增量 + ROAS）。
- [ ] 沉淀高 ROI 素材到媒体库，供下一轮复用。

---


### 3.9 快消 FMCG：日常品牌流量池（长期玩法）

**场景**：一家稳健的酸奶品牌，不需要大爆，但要"天天被想起"、
维持稳定的货架心智与回购。

**特点**

- 没有新品事件，预算中等，目标是把"复购 + 品牌好感"做成常态化。
- 用可放量、非独占的产品（Spark 品牌版 / Feed 加权）做日常引流。

**打法**

1. Spark 品牌版：长期投放真实用户早餐/通勤场景的原创内容。
2. 频控固定 1-2 次/周，保持"温柔存在感"，不打扰。
3. 效果承接：用 CREATIVE 里高互动素材做浅层（视频观看/点击）投喂。
4. 季度用一次 Takeover 做"记得住"的消费者提醒，带向线下门店/小程序。

**量化**

| 指标 | 目标 |
|------|------|
| 品牌好感度 (Favorability) | 季度 +3%-5% |
| 复购率 | 提升 5%-10% |
| 日常 Reach | 目标人群月覆盖 60%+ |
| CPM | 维持品类基准 |
| 购买意向 | 缓慢累积正增量 |

**记忆点**：快消不做"一波流"，做"细水长流的心理占有"。
品牌广告在快消的价值 = 把"货架上有"升级成"我常选它"。

### 3.10 奢侈品：限量上新 + 稀缺感营造

**场景**：某奢侈腕表品牌发布限量款，需要"高价高格调 + 限量稀缺"。

**特点**

- 高价商品不追求广撒网转化，追求"精准高净值人群 + 格调曝光"。
- 素材要克制、有质感，避免大促销感拉低品牌心智。

**打法**

1. Takeover：全国高净值市场（如美国/日本）+ 频控 1 次。
2. TopView 用高质感 30s 短片讲故事（工艺/传承），3s 打出品牌 Logo。
3. 定向高净值兴趣（腕表、钟表、收藏、商务）+ 排除低价敏感人群。
4. 落地页直连限量预约页，配合"限量倒计时"制造稀缺。
5. Spark 品牌版：找少量高端 KOL 发佩戴视频，放大社交认证。

**量化**

| 指标 | 目标 |
|------|------|
| 品牌记忆度 | ≥ 品类 Top20% |
| 预约量 | 限量款售罄或预约排满 |
| 客单价 | 保持高价（不做价格战） |
| 高净值 Reach | 目标 100 万内精准触达 |

**记忆点**：奢侈品品牌广告的核心不是"量"，是"对的人群 + 对的情绪"，
宁缺毋滥，频控要更紧，素材要更精。

### 3.11 出海本地化：一个素材适配多国

**场景**：出海快消/APP，想用一套品牌素材覆盖多国，降低制作成本。

**难点**

- 各国文化、语言、法规不同，直接复用容易踩雷。
- 素材审核在各市场要求不一，一个版本可能在某国被拒。

**本地化 SOP**

1. 制作"母版"（无字幕、无地域性元素的高质感 60s 视频）。
2. 按市场出"本地版"：本地语言字幕 + 本地演员 + 本地节日元素。
3. 规避：涉及宗教、政治、历史人物、医疗的素材逐国审查。
4. 每个市场单独创建 Campaign，单独设频控与落地页。
5. 用 get_placement_options 确认每个市场的可用点位后绑定排期。

**量化**

| 项 | 目标 |
|----|------|
| 素材制作成本 | 母版 1 + 本地版 N，比 N 套独立制作省 40%+ |
| 本地 Ad Recall | 各国 ≥ 本地品类均值 |
| 拒审率 | ≤ 5%（提前对标国家政策） |
| ROI | 规模经济下单位成本下降 |

**记忆点**：品牌出海不浪费每一帧。母版一次拍，本地语言/文化适配，
用脚本批量生成各市场 Campaign，既省钱又合规。

### 3.12 直播带货：服饰 24 小时闪购直播间

**场景**：服饰品牌做 24 小时极限闪购直播，需要持续给直播间导流。

**打法**

1. 开播前 6 小时：TopView + Spark 预告直播间，发"限时优惠"。
2. 开播全程：Spark 品牌版放大主播风格穿搭视频，拉实时在线。
3. 高峰时段：Takeover 全量霸屏 1 次，营造"大家都在抢"紧迫感。
4. 效果承接：CONVERSIONS 落地直播间专属优惠下单。

**量化**

| 指标 | 目标 |
|------|------|
| 直播间在线峰值 | 2 万+ |
| GMV | 24h 目标 300 万 USD |
| 客单价提升 | 预热后 +15% |
| 退货率 | 因信任度提升而下降 |

**记忆点**：直播的"流量仪表盘" = 品牌预热（预约/认知）+ 效果引流
（下载/直播）+ Spark 达人（信任），三者协同把"围观"变"下单"。

---


## 四、常见问题与排查

### 4.1 - 4.12 十二问十二答

**Q 4.1：顶视图和 Takeover 有什么区别？怎么选？**

- 顶视图（TopView）出现在首刷第一条 In-Feed，可见时长 3 秒强制 + 最长 60s。
- Takeover 出现在开屏 / 首刷，通常 3-5s，是更强的"霸屏"。
- 选顶视图：想要更长的展示时长、更丰富的叙事（新品故事）。
- 选 Takeover：想要极强独占瞬间、低成本全国曝光。
- 实操：新品官宣用 TopView（讲得清故事）；大促快闪用 Takeover。

**Q 4.2：为什么我的 Takeover 曝光远低于预估的 DAU？**

- 先检查是否被频控限制（1 次/人/日）——这是正常约束。
- 再确认是否有竞品同点位冲突，被分走了一部分。
- 调用 get_report 看 reach 与 frequency：若 frequency < 1 且 reach 偏低，
  说明有大量用户未触达，可能是定向过窄或库存不足。
- 处理：联系销售补量，或放宽地理/年龄覆盖。

**Q 4.3：品牌广告账户新建 Campaign 时该用什么 objective？**

- 品牌以曝光/完播为目标，选 VIDEO_VIEWS（视频完播）。
- 若目标是参与（Challenge/特效），可用 ENGAGEMENT。
- 不要用 CONVERSIONS 去跑品牌独占位——那会浪费独占量级。
- 可在 get_campaign_objective_options() 查看候选列表，避免写错枚举。

**Q 4.4：素材被拒，导致我不小心丢掉了档期怎么办？**

- 档期是稀缺资源，素材拒审 = 立体风险。务必先预审。
- 常见拒因：政治敏感、医疗过度承诺、文字占屏过高、落地页不一致。
- 补救：如果档期已锁但素材被拒，立即联系销售看能否平移档期，
  并准备 1-2 套备选素材（短版 + 无文字版）。
- 长期对策：把审核红线写进创意 brief，素材团队先自查。

**Q 4.5：Brand Lift Study 怎么知道结果可不可信？**

- BLS 必须实验设计：随机实验组/对照组，对照组是影子位。
- 看样本量是否足够、提升是否统计显著（p<0.05）。
- 不相信平台自证？用第三方（Nielsen 等）复核。
- 若对照组也被媒体覆盖到（泄漏），结果会失真，需重跑。

**Q 4.6：为什么要买 Spark 品牌版？和达人 post 加量有什么区别？**

- 达人自己 post 是免费自然流量；Spark 品牌版是把它变成可定量投放的广告。
- Spark 优点：保留创作者真实 IP（信任度高）、可精确控频/定向/预算。
- 需要作者在 Spark Ads 中心授权，否则版权不合格不可投放。
- 风险：素材下线时创作者账号动态可能变化，需跟踪授权状态。

**Q 4.7：Hashtag Challenge 做了但没有 UGC，怎么办？**

- UGC 少 = 创意门槛太高或激励不足，不是平台问题。
- 修正手段：
  1. 降低门槛：用一键 AR 特效 / 模板，让用户 10 秒能产出。
  2. 加激励：Branded Mission 给任务奖励。
  3. 达人预热：先找 KOC 发 50-100 条，制造"大家都在玩"的势能。
  4. 加话题热度：主视频用高完播的短节奏 6-15s。

**Q 4.8：品牌广告和效果广告预算怎么切，才不会相互抢量？**

- 它们不冲突：品牌更多是"增量认知"，效果是"转化承接"。
- 用 Combined Reach 看重叠：避免品牌和效果重复触达同一批人。
- 切法：品牌 40-50%、效果 35-45%、直播/内容 10-20%（动态调整）。
- 若效果 CPA 劣化，先看是否品牌曝光不足（认知瓶颈），而非砍效果。

**Q 4.9：Access-Token 调用品牌 API 报 rate limit 怎么办？**

- 品牌大报表（多国家/多天）请求量大，容易触限。
- 对策：分片拉取（按天/按国家）、加退避（exponential backoff）。
- 用 v1.3 的 report/get 分页 + 单次查询维度减少。
- 生产环境请改用 Go/Python 的重试封装（前面 2.7 给了示例）。

**Q 4.10：做直播带货，品牌广告怎么给直播间导流？**

- 素材 click_tracking_url 指向直播间地址。
- 开播前 24-72h 用 Spark / TopView 发预约卡，蓄预约量。
- 开播中用 Spark 品牌版放大主播号召视频，拉实时在线。
- 注意落地页一致性：直播链接需在排期内保持有效，避免失效跳转。

**Q 4.11：同市场同时买 Takeover 和 TopView，会重复计费吗？**

- 两者是不同点位，会各自计费（Takeover 按 CPD、TopView 按 CPM/包天）。
- 是否重复触达同一用户：不一定，频控在全局起作用，但点位不同可叠加。
- 建议用 Combined Reach 看重叠，决定是否值得两个都要。
- 一般只用两者之一做"首爆"，另一个做日常加压，避免曝光浪费。

**Q 4.12：品牌广告为什么按 CPD 卖，而不是像效果那样按转化出价？**

- 品牌独占位的价值是"确定性曝光"，无法用转化归因精准衡量。
- 它的生意逻辑是"买一天的曝光权"，与 CPM 不同——保证量但不保证转化。
- CPD 让品牌方 = 直播间预热能买到可预期的曝光，适合预算大、要量纲的客户。
- 若你要转化，就把它拆成"品牌做认知 + 效果做转化"，单独走成交出价。

---


**Q 4.13：为什么我的 Spark 品牌版内容点击率很低？**

- 达人内容有"真实感"，但如果素材本身没有钩子，CTR 依然上不去。
- 排查步骤：
  1. 看前 3 秒：是否有强视觉冲击或悬念钩子。
  2. 看文案：达人原帖的 caption 是否带 CTA（限时优惠/点击查看）。
  3. 看定向：是不是人群太窄导致展示给了不感兴趣的人。
  4. 看频控：被反复触达的同一批人，CTR 必然衰减。
- 优化：换达人、改 CTA、放宽定向、降频控，小步快跑 AB 测。

**Q 4.14：品牌广告多市场同时投放，排期冲突怎么办？**

- 每个市场有独立库存，一般不会跨市场冲突。
- 冲突主要发生在同市场：同一天买两个独占位（Takeover+Takeover）。
- 对策：
  1. 用 Go/Python 脚本做 EnsureSinglePerDay 校验（见 2.7）。
  2. 错峰：同市场只留一个独占位，另一个换日期。
  3. 与销售提前确认市场库存表，避免临时换档。

**Q 4.15：品牌广告的量级（impressions）比预期少一半，可能是哪里出了问题？**

- 排查顺序（从常见到少见）：
  1. 频控卡住：用户被限制为 1 次/日，这是正常上限。
  2. 定向过窄：年龄/兴趣/地理过滤掉了大量人群。
  3. 落地页/素材审核被限：素材部分市场被拒。
  4. 库存冲突：同点位被竞品占走一部分。
  5. 时段问题：某些时段不投放（如凌晨）。
- 用 get_report 分日/分市场拆解，快速定位是哪一层少了。

**Q 4.16：CPD 和 CPM 换算，怎么判断我买贵了？**

- 公式：CPD ÷ (当日预计 DAU / 1000) ≈ 等效 CPM。
- 例：某市场 DAU 5000 万，Takeover CPD 15 万美元，
  等效 CPM = 150000 ÷ (50000000/1000) = 150000 ÷ 50000 = $3。
- 对比普通 Feed CPM（通常 $2-8），若等效 CPM 明显高于市场均价，
  说明这个市场的独占位溢价高，可考虑用 Spark 品牌版替代部分量级。
- 记住：独占位有"确定性 + 独占稀缺"溢价，不能只看 CPM 数字。

**Q 4.17：如何判断我的品牌 Campaign 是"有效"的？**

- 不能只看曝光量，要看"度量三角"：
  1. 量级：impressions / reach / frequency 是否达标。
  2. 质量：Ad Recall / Brand Recall / Favorability 是否提升。
  3. 协同：效果端 CPA/ROAS 是否因品牌预热而改善。
- 三角全绿才算有效。单看曝光大，可能是"刷存在感但没进脑子"。

**Q 4.18：品牌广告的素材复用率高吗？多久换一次？**

- 独占位（TopView/Takeover）素材复用率低：用户每天见一次，
  3-5 天后就会"视而不见"，通常 3-7 天需要换新。
- 日常位（Spark/Feed）素材可以长线复用，但也要每周监测 CTR 衰减。
- 建议：每个 Campaign 备 3 套素材轮换（A 首屏冲击/B 功能讲清/
  C 达人真实），按 CTR 表现自动切换（素材轮播 + 出价优化）。

---

## 五、自测题

**问题 1：品牌广告与效果广告的本质区别是什么？请从目标函数、
计费、库存、度量四个维度说明，并结合"花颜堂"案例说明为什么必须组合。**

<details><summary>答案</summary>

| 维度 | 品牌广告 | 效果广告 |
|------|---------|---------|
| 目标函数 | 曝光 + Reach + Recalling | Conversion / CPA / ROAS |
| 计费 | CPD / CPM | oCPM / CPA |
| 库存 | 独占稀缺（需预售） | 实时竞价池 |
| 度量 | Brand Lift / Ad Recall | 归因面板 |

为什么必须组合：纯效果只做"收割"，当认知不足时转化被"没听过/不敢买"
拦截，CPA 被抬到不可持续；纯品牌只做"播种"，看完就走没有承接。
花颜堂案例里，品牌位（TopView/Takeover）把认知做起来后，效果端
点击成本下降 25-35%，ROAS 到 3.7。组合 = 声量闸门 + 转化水渠。
</details>

**问题 2：请设计一个国货品牌 TopView + Hashtag Challenge 联投 +
效果承接的投放节奏（时间窗），并给出每个阶段的预算与目标。**

<details><summary>答案</summary>

| 阶段 | 动作 | 预算 | 目标 |
|------|------|------|------|
| T-30 定档 | 锁 TopView 档期 | — | 不丢档 |
| T-21 预审 | 素材审核 + AR 特效 | — | 过审 |
| T-7 建 Campaign | v1.3 创建 + 绑定排期 | 12 万 | 就绪 |
| T-0 引爆 | TopView 爆发 | 12 万 | Ad Recall 25%+ |
| T+1~6 Challenge | 6 天主推 | 18 万 | UGC 8 万条 |
| T+7 测量 | Brand Lift 开始 | — | 记忆度 +15pt |
| T+14~30 承接 | 效果 Campaign | 30 万 | ROAS ≥ 3.2 |

核心：品牌先引爆认知，效果 24-48h 后承接捡转化，
并靠 Spark 品牌版放大达人内容维持流量池。
</details>

**问题 3：为什么 Takeover 一天只有 1 次/用户？如果曝光低于 DAU，
你如何排查？（结合 API 与指标）**

<details><summary>答案</summary>

- 1 次/用户/日来自"独占稀缺"：开屏/首刷每用户单日仅分配一次，
  保护体验 + 支撑高 CPD 定价，库存上限 = 当日 DAU。
- 曝光低于 DAU 排查：
  1. 检查频控与定向是否过窄（放宽 Geo/年龄）。
  2. 检查是否与竞品同点位冲突被分走。
  3. 调 get_report 看 reach / frequency，判断是否没触达全量。
  4. 若 frequency < 1 且 reach 偏低 → 库存/定向问题，联系销售补量。
</details>

**问题 4：什么是 Brand Lift Study？如何保证测量可信？
请列出至少 4 个品牌度量指标及经验参考值。**

<details><summary>答案</summary>

- Brand Lift Study 用实验法：随机把目标人群分为实验组（见广告）与
  对照组（影子位），通过 App 内后测问卷，计算两组在品牌指标上的差值为
  "提升"（Lift），2-7 天窗口内进行。
- 保证可信：真实随机分组、足够样本量、统计显著（p<0.05）、
  可选第三方（Nielsen）复核、防对照组被媒体污染（泄漏）。
- 四指标与参考值：
  - Ad Recall：15%-40%（好广告 25%+）
  - Brand Recall：10%-30%
  - Favorability：+5%-15%
  - Purchase Intent：+3%-10%
  - 辅助：Reach / Frequency（1.0-2.5 为佳）
</details>

**问题 5：写一段伪代码或伪逻辑，说明"品牌/效果/直播"三笔预算
如何在投放中动态调整。**

<details><summary>答案</summary>

```
初始: brand=45%, perf=40%, live=15%

每轮(周)更新:
  lift = measure_brand_recall_lift()
  cpa  = effect_cpa()
  median_cpa = category_median()
  gmv  = live_gmv_trend()

  if lift > target:           # 品牌已建认知 → 转投效果收割
      brand -= 5%;  perf += 5%
  elif cpa > median_cpa and reach_ok:
      perf -= 5%;  spark += 5%   # 真实感不足, 放大达人矩阵
  elif gmv rising:
      perf -= 5-10%; live += 5-10%  # 直播间蓄水
  else:
      hold ratio
```

原则：品牌为效果铺路，效果为品牌变现，
直播用品牌预热 + 达人矩阵承接，保持 1+1>2 的组合效率。
</details>

---

*文档完成。本指南聚焦品牌广告的"售卖/排期、定向、度量、
素材规格、创意设计与协同整合"，与知识库既有品牌基础章节差异化互补。*
