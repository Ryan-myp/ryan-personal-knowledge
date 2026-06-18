# 微信读书精华：用户画像 + 广告数据定量分析 + 设计模式 蒸馏笔记

> 来源：《用户画像：平台构建与业务实践》- 张型龙
>       《广告数据定量分析》- 齐云涧
>       《设计模式的艺术》- 刘伟
> 状态：已读完 ✅
> 蒸馏日期：2026-06-18

---

## 第一部分：用户画像

### 用户画像三层模型

```
用户画像架构：
┌─────────────────────────────────────────────────────────────────────┐
│ 基础属性层（Who）                                                    │
│ •  demographics: 年龄/性别/地域/职业                                 │
│ •  设备信息: 手机型号/操作系统/网络                                   │
│ •  行为标签: 注册时长/活跃度/消费能力                                 │
│                                                                     │
│ 兴趣偏好层（What）                                                   │
│ •  浏览偏好: 类目偏好/品牌偏好/价格区间                               │
│ •  内容偏好: 文章/视频/直播偏好                                      │
│ •  购物偏好: 购买频次/客单价/品类                                    │
│                                                                     │
│ 行为预测层（Will）                                                   │
│ •  购买意愿: 购买概率/品类倾向                                       │
│ •  流失风险: 流失概率/原因                                           │
│ •  生命周期: 新客/活跃/沉默/流失                                     │
│                                                                     │
│ 数据源：                                                            │
│ • 第一方：用户行为日志、交易数据、注册信息                            │
│ • 第二方：合作伙伴数据                                               │
│ • 第三方：公开数据、数据供应商                                       │
└─────────────────────────────────────────────────────────────────────┘
```

### 标签体系

```
标签分类：
┌─────────────────────────────────────────────────────────────────────┐
│ 事实标签（客观数据）                                                 │
│ • 性别、年龄、城市、手机型号                                         │
│ • 注册时间、最后登录时间                                             │
│                                                                     │
│ 统计标签（聚合计算）                                                 │
│ • 近7天登录次数、近30天消费金额                                      │
│ • 平均客单价、购买频次                                               │
│                                                                     │
│ 模型标签（算法预测）                                                 │
│ • 购买概率、流失概率、LTV                                            │
│ • 用户分层（RFM模型）                                                │
│ • 相似人群（Lookalike）                                              │
│                                                                     │
│ 广告场景标签：                                                       │
│ • 广告敏感度：对广告的点击/转化概率                                  │
│ • 出价意愿：愿意支付的 CPM/CPC                                       │
│ • 创意偏好：喜欢的广告样式/风格                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 第二部分：广告数据定量分析

### 核心指标体系

```
广告指标体系：
┌─────────────────────────────────────────────────────────────────────┐
│ 曝光层：                                                             │
│ • Impressions: 展示次数                                              │
│ • Reach: 独立触达人数                                                │
│ • Frequency: 人均展示次数                                            │
│                                                                     │
│ 点击层：                                                             │
│ • Clicks: 点击次数                                                   │
│ • CTR: 点击率 = Clicks / Impressions                                │
│ • CPC: 平均点击成本 = Spend / Clicks                                │
│                                                                     │
│ 转化层：                                                             │
│ • Conversions: 转化次数                                              │
│ • CVR: 转化率 = Conversions / Clicks                                │
│ • CPA: 平均转化成本 = Spend / Conversions                           │
│ • ROAS: 广告支出回报率 = Revenue / Spend                            │
│                                                                     │
│ 效率层：                                                             │
│ • eCPM: 千次展示收益 = (Revenue / Impressions) * 1000               │
│ • Fill Rate: 填充率 = 实际展示 / 请求次数                           │
│ • Win Rate: 中标率 = 中标次数 / 竞价次数                            │
└─────────────────────────────────────────────────────────────────────┘
```

### 归因模型

```
归因模型对比：
┌────────────────┬────────────┬────────────┬────────────┐
│     模型       │  特点      │  优点      │  缺点      │
├────────────────┼────────────┼────────────┼────────────┤
│ Last Click     │ 最后点击   │ 简单       │ 忽略其他   │
│ First Click    │ 首次点击   │ 看重获客   │ 忽略后续   │
│ Linear         │ 均分       │ 公平       │ 不区分价值 │
│ Time Decay     │ 时间衰减   │ 重视近期   │ 参数难调   │
│ Position Based │ 首末加权   │ 综合考量   │ 权重固定   │
│ Data Driven    │ 数据驱动   │ 最准确     │ 需要数据   │
└────────────────┴────────────┴────────────┴────────────┘

推荐：有足够数据用 Data Driven，否则用 Position Based
```

---

## 第三部分：设计模式

### 创建型模式

```
Go 中的设计模式：
┌─────────────────────────────────────────────────────────────────────┐
│ 1. 单例模式（Singleton）                                             │
│    // 全局唯一实例，如配置管理器                                      │
│    var instance *ConfigManager                                       │
│    var once sync.Once                                                │
│    func GetInstance() *ConfigManager {                               │
│        once.Do(func() { instance = &ConfigManager{} })               │
│        return instance                                               │
│    }                                                                 │
│                                                                     │
│ 2. 工厂模式（Factory）                                               │
│    // 创建广告处理器，根据渠道选择不同实现                            │
│    func NewAdHandler(channel string) AdHandler {                    │
│        switch channel {                                              │
│        case "facebook": return &FacebookHandler{}                    │
│        case "google": return &GoogleHandler{}                        │
│        case "tiktok": return &TikTokHandler{}                        │
│        }                                                            │
│    }                                                                 │
│                                                                     │
│ 3. 建造者模式（Builder）                                             │
│    // 构建复杂的广告请求对象                                         │
│    builder := NewAdRequestBuilder().                                 │
│        SetPlatform("facebook").                                      │
│        SetBudget(1000).                                              │
│        SetTargeting(targeting).                                      │
│        Build()                                                       │
└─────────────────────────────────────────────────────────────────────┘
```

### 结构型模式

```
Go 中的结构型模式：
┌─────────────────────────────────────────────────────────────────────┐
│ 1. 适配器模式（Adapter）                                             │
│    // 适配不同广告平台的 API 接口                                    │
│    type AdPlatform interface {                                       │
│        CreateCampaign(req *Campaign) error                           │
│        GetReport(startDate, endDate string) (*Report, error)         │
│    }                                                                 │
│                                                                     │
│ 2. 装饰器模式（Decorator）                                           │
│    // 给广告请求添加日志/缓存/限流                                   │
│    type LoggingHandler struct {                                      │
│        next AdHandler                                                 │
│    }                                                                 │
│    func (h *LoggingHandler) Handle(req *Request) {                  │
│        log.Info("handling request")                                  │
│        h.next.Handle(req)                                            │
│    }                                                                 │
│                                                                     │
│ 3. 代理模式（Proxy）                                                 │
│    // 广告请求的缓存代理                                             │
│    type CachedAdHandler struct {                                     │
│        next   AdHandler                                               │
│        cache  Cache                                                    │
│    }                                                                 │
└─────────────────────────────────────────────────────────────────────┘
```

### 行为型模式

```
Go 中的行为型模式：
┌─────────────────────────────────────────────────────────────────────┐
│ 1. 策略模式（Strategy）                                              │
│    // 不同的竞价策略                                                  │
│    type BidStrategy interface {                                      │
│        CalculateBid(req *BidRequest) float64                         │
│    }                                                                 │
│    type FixedBidStrategy struct {}                                   │
│    type DynamicBidStrategy struct {}                                 │
│                                                                     │
│ 2. 观察者模式（Observer）                                            │
│    // 广告状态变更通知                                               │
│    type Observer interface {                                         │
│        Update(status string)                                         │
│    }                                                                 │
│    type AdCampaign struct {                                         │
│        observers []Observer                                          │
│    }                                                                 │
│                                                                     │
│ 3. 命令模式（Command）                                               │
│    // 广告操作命令                                                   │
│    type Command interface {                                          │
│        Execute() error                                               │
│        Undo() error                                                  │
│    }                                                                 │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 第四部分：自测题

### Q1: 用户画像的三层模型？

**A**: 基础属性（Who）、兴趣偏好（What）、行为预测（Will）。

### Q2: 广告核心指标？

**A**: CTR（点击率）、CVR（转化率）、CPC（点击成本）、CPA（转化成本）、ROAS（回报率）。

### Q3: Go 中最常用的设计模式？

**A**: 工厂模式（创建处理器）、策略模式（竞价策略）、装饰器模式（日志/缓存）。
