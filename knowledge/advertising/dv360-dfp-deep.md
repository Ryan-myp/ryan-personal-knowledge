# DV360/DFP 深度 — Google Display & Video 360 全链路解析

> 标签: `#DV360` `#DFP` `#Google_AdManager` `#程序化广告` `#广告服务器` `#源码级`
> 创建日期: 2026-06-10 | 作者: Ryan
> 定位: 资深专家级 — DV360/DFP 架构、API、竞价对接、数据回流

---

## 第一部分：入门引导（5 分钟速览）

### 1.1 DV360 vs DFP — 一个生态的两面

```
┌──────────────────────────────────────────────────────────────┐
│              Google 广告平台体系                               │
│                                                              │
│  ┌─────────────────────┐     ┌─────────────────────┐         │
│  │   DV360             │     │   DFP / Ad Manager  │         │
│  │ Display & Video 360 │     │ (Google Ad Manager) │         │
│  │                     │     │                     │         │
│  │ 买方平台 (Buy-Side)  │     │ 卖方平台 (Sell-Side) │         │
│  │ 广告主/代理用        │     │ 媒体/Publisher 用   │         │
│  │                     │     │                     │         │
│  │ • 投放管理          │     │ • 广告位管理         │         │
│  │ • 竞价策略          │     │ • 优先级/排期        │         │
│  │ • 创意管理          │     │ • 水印/授权          │         │
│  │ • 报告分析          │     │ • 瀑布/头拍         │         │
│  │ • 目标优化          │     │ • 收益最大化         │         │
│  │                     │     │ • 广告请求处理       │         │
│  └─────────────────────┘     └─────────────────────┘         │
│           ↕ 通过 RTB (Real-Time Bidding) 对接                │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              SDC (Supply-Domain Connection)           │   │
│  │              自动对接 RTB + 保证交易                    │   │
│  └──────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
```

### 1.2 DFP → Google Ad Manager 的演变

| 时间 | 版本 | 名称 | 说明 |
|------|------|------|------|
| 2008 | 早期 | DFP (DoubleClick for Publishers) | 广告服务器 |
| 2015 | 2015 | DoubleClick Ad Manager (DG) | 企业版增强 |
| 2018 | 2018 | Google Ad Manager (GAM) | 统一命名 |
| 2020+ | 现在 | Google Ad Manager | 当前名称 |

**⚠️ 重要**: 代码中所有 `dfp` 关键词仍保留，但产品名称是 **Google Ad Manager**。API 端点、命名空间仍使用 `dfp`。

### 1.3 核心概念速查

| 概念 | 定义 | 说明 |
|------|------|------|
| **Line Item (LI)** | 广告投放条目 | 核心交易单位，定义投放规则 |
| **Order** | 订单 | 包含一个或多个 LI 的容器 |
| **Creative** | 创意 | Banner/视频/原生等广告素材 |
| **Ad Unit** | 广告单元 | Publisher 的广告位树形结构 |
| **Targeting** | 定向 | 基于人群/上下文/设备/时间的投放条件 |
| **Ad Server** | 广告服务器 | 决策"展示哪个创意" |
| **SSP** | 供应方平台 | 帮 Publisher 卖广告 |
| **DSP** | 需求方平台 | 帮广告主买广告 |
| **RTB** | 实时竞价 | SSP → Ad Exchange → DSP 竞价 |
| **PMP (Private Marketplace)** | 私人交易市场 | 邀标的 RTB |
| **Guaranteed LI** | 保量 LI | 保证展示量（固定交易） |
| **Native LI** | 原生 LI | 按展示计费（RTB） |
| **Waterfall** | 瀑布流 | 依次请求多个需求方的竞价 |
| **Header Bidding** | 头部竞价 | 并行请求多个 SSP 的竞价 |

---

## 第二部分：架构深度 — DV360 ↔ GAM 对接

### 2.1 DV360 投放流程

```
┌────────────────────────────────────────────────────────────────┐
│                    DV360 投放全流程                              │
│                                                                │
│  1. 广告主创建订单 (Order)                                     │
│     ├── 设置预算: CPM/CPC/OCPM/CPI                            │
│     ├── 设置目标: 地域/人口/兴趣/时段                          │
│     └── 设置创意: Banner/视频/原生                             │
│          │                                                     │
│          ▼                                                     │
│  2. DV360 创建 Line Item                                      │
│     ├── Line Item Type: Standard(保量) | Programmatic(RTB)    │
│     ├── 出价策略: Standard CPM | Optimized CPM                │
│     ├── 优先级: Low | Medium | High | Super | Priority        │
│     ├── 目标: 人群/上下文/设备                                 │
│     └── 创意绑定                                              │
│          │                                                     │
│          ▼                                                     │
│  3. DV360 ↔ GAM 对接 (SDC 或手动)                              │
│     ├── 自动对接: DV360 创建 "SDC 订单" → 自动同步到 GAM      │
│     └── 手动对接: 在 GAM 创建 LI → 绑定 DV360 的 RTB 交易      │
│          │                                                     │
│          ▼                                                     │
│  4. GAM 广告请求处理                                           │
│     ├── 页面加载 → GAM 广告请求                                │
│     ├── 检查 Ad Unit 的 LI 优先级                              │
│     ├── 保量 LI: 优先检查 → 有保量则展示                       │
│     └── RTB LI: 触发竞价                                       │
│          │                                                     │
│          ▼                                                     │
│  5. RTB 竞价流程 (Header Bidding 模式)                         │
│     ├── GAM 并行请求多个 SSP                                   │
│     ├── SSP 转发竞价请求到 Ad Exchange                         │
│     ├── Ad Exchange 通知多个 DSP (包括 DV360)                 │
│     ├── DSP 在 100ms 内返回出价                                │
│     ├── 最高出价获胜 → 返回创意                                 │
│     └── GAM 展示获胜创意                                       │
└────────────────────────────────────────────────────────────────┘
```

### 2.2 保量 vs RTB 竞价逻辑

```java
// GAM 竞价决策流程 (Java 抽象)
//
// 当广告请求到达 GAM 时:
//
// 1. 按 LI 优先级排序 (Priority > Super > High > Medium > Low)
// 2. 对每个优先级:
//    a. 检查保量 LI (Guaranteed Line Items)
//       - 检查流量配额是否足够
//       - 检查定向条件是否匹配 (Targeting)
//       - 检查日期范围
//       → 匹配且配额足够 → 展示保量创意
//    b. 检查 RTB LI (Programmatic Line Items)
//       - 触发 Header Bidding 竞价
//       - 并行请求所有 SSP/Exchange
//       → 有出价 → 最高出价者获胜
//       → 无出价 → 回退到下一个优先级

// 保量 LI 的流量分配逻辑:
//
// ┌──────────────────────────────────────────────────────────┐
// │  LI-1 (Priority=High, Guaranteed=10000 impressions)     │
// │  ├── Day 1: 消耗 1000                                   │
// │  ├── Day 2: 消耗 1200                                   │
// │  ├── ...                                                │
// │  └── Day 10: LI-1 完成 → 流量流向下一个 LI               │
// │                                                        │
// │  LI-2 (Priority=Medium, Programmatic CPM $5)           │
// │  └── 从 Day 1 开始竞价 (但 LI-1 有流量时，LI-2 不竞价)   │
│  └── LI-1 完成后，LI-2 获得更多竞价机会                   │
└──────────────────────────────────────────────────────────┘

// 保量 LI 的 Overdelivery 处理:
// 如果保量 LI 的展示量超过目标 (Overdelivery):
// 1. 正常情况: LI 正常结束，展示量可能略超
// 2. 严重超量: GAM 会暂停该 LI 的竞价资格
// 3. 保量保证: LI 完成后，保证展示量 ≥ 承诺量 (Underdelivery 会补量)
```

### 2.3 SDC (Supply-Domain Connection) — 自动对接

```
SDC 对接流程:
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│  DV360 Side (Buyer)         GAM Side (Publisher)           │
│  ─────────────              ─────────────                   │
│                                                             │
│  1. 创建 SDC 订单                                          │
│     ├── Line Item (保量 100K impressions)                   │
│     ├── Line Item (RTB Native LI)                         │
│     └── Line Item (RTB Video LI)                          │
│            │                                               │
│            ▼                                               │
│  2. SDC 自动创建 GAM Order/LI                              │
│     ├── GAM 中自动生成:                                    │
│     │   ├── Order: [SDC] Campaign X                        │
│     │   ├── LI: [Guaranteed] Campaign X - 100K            │
│     │   ├── LI: [RTB] Campaign X - Native                 │
│     │   └── LI: [RTB] Campaign X - Video                  │
│            │                                               │
│            ▼                                               │
│  3. 双向同步                                               │
│     ├── DV360 变更 LI → 同步到 GAM                         │
│     ├── GAM 变更 LI → 同步到 DV360                         │
│     └── 同步延迟: 通常 < 5 分钟                             │
│            │                                               │
│            ▼                                               │
│  4. 数据回流                                               │
│     ├── GAM 展示/点击 → 上报到 DV360                       │
│     ├── GAM 转化 → 通过 SDF (Supply-Domain Feed) 回传      │
│     └── DV360 使用数据优化竞价                             │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**SDC 的关键配置:**

```
SDC 对接的 GAM 配置要求:
1. 账户必须是 Google Ad Manager 企业版
2. 必须启用 "SDC" 功能
3. 广告单位必须配置正确的 RTB 设置
4. 需要配置 Supply-Domain 域名验证
5. 需要配置 SDF (Supply-Domain Feed) 转化回传

SDC 支持的 LI 类型:
✅ 保量 LI (Guaranteed)
✅ RTB 原生 LI (Programmatic Native)
✅ RTB 视频 LI (Programmatic Video)
❌ DV360 优化 LI (Optimized Line Items) — 需手动对接
```

---

## 第三部分：DV360/DFP API — 源码级深度

### 3.1 API 架构

```
┌─────────────────────────────────────────────────────────────┐
│              Google DV360/DFP API 架构                       │
│                                                             │
│  ┌────────────────────────────────────────────────────────┐ │
│  │                API 入口                                  │ │
│  │  DV360: https://displayvideo.googleapis.com/            │ │
│  │  DFP (GAM): https://dfp.googleapis.com/                 │ │
│  │                                                         │ │
│  │  版本: v1, v1beta (DV360)                               │ │
│  │  版本: v202405 (GAM)                                    │ │
│  └────────────────────────────────────────────────────────┘ │
│                           │                                 │
│                   OAuth 2.0 认证                             │ │
│                   Service Account                            │ │
│                     │                                       │ │
│                     ▼                                       │ │
│  ┌────────────────────────────────────────────────────────┐ │
│  │               REST API                                  │ │
│  │  POST /v1/accounts/{account}/lineItems                  │ │
│  │  GET  /v202405/AdUnitService/getAdUnits                  │ │
│  └────────────────────────────────────────────────────────┘ │
│                           │                                 │
│  ┌────────────────────────────────────────────────────────┐ │
│  │              Batch Operations                           │ │
│  │  - 批量创建 LI (BatchCreateLineItems)                    │ │
│  │  - 批量更新 LI (BatchUpdateLineItems)                    │ │
│  │  - 批量删除创意 (BatchDeleteCreatives)                   │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 DV360 API — Go SDK 实现

```go
// dv360_api.go — DV360 API Go 实现
package dv360

import (
	"context"
	"fmt"
	"log"

	displayvideo "google.golang.org/api/displayvideo/v1"
	"google.golang.org/api/option"
	"golang.org/x/oauth2/google"
)

// DV360Client DV360 API 客户端封装
type DV360Client struct {
	AdvertiserService *displayvideo.AdvertiserService
	LineItemService   *displayvideo.LineItemService
	CreativeService   *displayvideo.CreativeService
	PartnerService    *displayvideo.PartnerService
	ChannelService    *displayvideo.ChannelService
}

// NewDV360Client 创建 DV360 客户端
func NewDV360Client(ctx context.Context) (*DV360Client, error) {
	// 使用 Service Account 认证
	config, err := google.DefaultTokenSource(ctx,
		"https://www.googleapis.com/auth/display-video",
	)
	if err != nil {
		return nil, fmt.Errorf("oauth token error: %w", err)
	}

	svc, err := displayvideo.NewService(ctx, option.WithHTTPClient(
		// 增加超时和重试
		&http.Client{
			Timeout: 60 * time.Second,
			Transport: &retryTransport{
				inner:   http.DefaultTransport,
				maxRetries: 3,
			},
		},
	))
	if err != nil {
		return nil, fmt.Errorf("dv360 client error: %w", err)
	}

	return &DV360Client{
		AdvertiserService: displayvideo.NewAdvertiserService(svc),
		LineItemService:   displayvideo.NewLineItemService(svc),
		CreativeService:   displayvideo.NewCreativeService(svc),
		PartnerService:    displayvideo.NewPartnerService(svc),
		ChannelService:    displayvideo.NewChannelService(svc),
	}, nil
}

// LineItem DV360 Line Item 结构
type LineItem struct {
	// 核心字段
	AdvertiserID    string  // 广告主 ID
	CampaignID      string  // 活动 ID
	DisplayName     string  // 显示名称
	Status          string  // ACTIVE | ARCHIVED | DRAFT | SCHEDULED

	// 竞价相关
	LineItemType    string  // GUARANTEED | PROGRAMMATIC
	BuyType         string  // PREMIUM | RTB | OPTIMIZED | PLANNED
	CostType        string  // CPM | CPC | CPI | CPP

	// 出价
	StandardPrice struct {
		CurrencyCode string  `json:"currencyCode"` // USD
		MicroUnits   int64   `json:"microUnits"`   // 微单位 (1 USD = 1,000,000 microUnits)
	} `json:"standardPrice"`

	// 目标
	Targeting struct {
		VideoTypes     []string `json:"videoTypes"`     // VRA | VRS | VOD | VODR | ...
		Devices        []string `json:"devices"`        // MOBILE | TABLET | DESKTOP | TV
		Genders        []string `json:"genders"`        // ALL | MALE | FEMALE
		AgeRanges      []string `json:"ageRanges"`      // ALL | 18-24 | 25-34 | ...
		Lifestyles     []string `json:"lifestyles"`     // 生活方式标签
		CustomSegments []string `json:"customSegments"` // 自定义受众
	} `json:"targeting"`

	// 排期
	Scheduling struct {
		StartTimestampMs  int64 `json:"startTimestampMs"`  // 毫秒级时间戳
		EndTimestampMs    int64 `json:"endTimestampMs"`    // 毫秒级时间戳
		TimeZoneCode      string `json:"timeZoneCode"`     // UTC / America/New_York / Asia/Shanghai
		CountryIds        []int64 `json:"countryIds"`      // 国家代码 (Google 内部 ID)
	} `json:"scheduling"`

	// 创意绑定
	CreativeIDs []string `json:"creativeIds"` // 绑定的创意 ID
}

// CreateLineItem 创建 Line Item
func (c *DV360Client) CreateLineItem(ctx context.Context, li *LineItem) (string, error) {
	displayVideoLineItem := &displayvideo.LineItem{
		AdvertiserId: li.AdvertiserID,
		CampaignId:   li.CampaignID,
		DisplayName:  li.DisplayName,
		Status:       li.Status,
		LineItemType: li.LineItemType,
		BuyType:      li.BuyType,
		CostType:     li.CostType,
		Scheduling: &displayvideo.Scheduling{
			StartTimestampMs: li.Scheduling.StartTimestampMs,
			EndTimestampMs:   li.Scheduling.EndTimestampMs,
			TimeZoneCode:     li.Scheduling.TimeZoneCode,
		},
	}

	// 保量 LI: 设置 impressions
	if li.LineItemType == "GUARANTEED" {
		displayVideoLineItem.GuaranteedImpressions = &displayvideo.GuaranteedImpressions{
			Count: 100000, // 10 万展示
		}
	}

	// RTB LI: 设置出价
	if li.LineItemType == "PROGRAMMATIC" {
		displayVideoLineItem.StandardPrice = &displayvideo.StandardPrice{
			CurrencyCode: li.StandardPrice.CurrencyCode,
			MicroUnits:   li.StandardPrice.MicroUnits,
		}
	}

	// 调用 API
	response, err := c.LineItemService.Create(displayVideoLineItem).Context(ctx).Do()
	if err != nil {
		return "", fmt.Errorf("create line item failed: %w", err)
	}

	return response.LineItemId, nil
}

// BatchUpdateLineItems 批量更新 Line Items
func (c *DV360Client) BatchUpdateLineItems(ctx context.Context, updates []*displayvideo.LineItem) error {
	batch := &displayvideo.BatchUpdateLineItemsRequest{
		Requests: make([]*displayvideo.UpdateLineItemRequest, len(updates)),
	}
	for i, li := range updates {
		batch.Requests[i] = &displayvideo.UpdateLineItemRequest{
			LineItem: li,
		}
	}

	_, err := c.LineItemService.BatchUpdate(batch).Context(ctx).Do()
	return err
}

// Creative DV360 创意结构
type Creative struct {
	Type         string // BANNER | VIDEO | NATIVE
	Status       string // APPROVED | UNDER_REVIEW | REJECTED
	Height       int    // 高度 (像素)
	Width        int    // 宽度 (像素)
	FileName     string // S3/GCS 文件路径
	MimeType     string // image/jpeg, video/mp4
	// ... 更多创意类型特定字段
}

// GetCreativeReport 获取创意报表
func (c *DV360Client) GetCreativeReport(ctx context.Context, advertiserID string, dateRange *DateRange) ([]CreativeReport, error) {
	// DV360 报表 API
	// 支持: impressions, clicks, ctr, cvr, cpa, roas, cost
	report := &displayvideo.ReportSpec{
		DimensionFilters: &displayvideo.Dimensions{
			CampaignId:  []string{advertiserID},
			LineItemId:  nil,
		},
		Dimensions: []string{
			"DATE",
			"CAMPAIGN_ID",
			"LINE_ITEM_ID",
			"CREATIVE_ID",
			"VIDEO_AD_ID",
		},
		Metrics: []string{
			"IMPRESSIONS",
			"CLICKS",
			"CONVERSIONS",
			"COST",
			"REVENUE",
			"CPC",
			"CPM",
		},
		DateRange: &displayvideo.DateRange{
			StartDate: &Date{Year: dateRange.Start.Year, Month: int(dateRange.Start.Month), Day: dateRange.Start.Day},
			EndDate:   &Date{Year: dateRange.End.Year, Month: int(dateRange.End.Month), Day: dateRange.End.Day},
		},
	}

	// 创建报表
	_, err := c.LineItemService.CreateReport(report).Context(ctx).Do()
	if err != nil {
		return nil, err
	}

	// 获取报表下载链接
	downloadLink := c.LineItemService.GetReportDownloadLink(advertiserID)

	// 下载 CSV
	// ...
	return results, nil
}
```

### 3.3 GAM/DFP API — Java SDK 实现

```java
// gam_api.java — Google Ad Manager (DFP) API Java 实现
package com.yourcompany.gam;

import com.google.api.gax.rpc.ApiException;
import com.google.api.ads.dfp.jaxws.api.v202405.*;
import com.google.api.ads.dfp.lib.client.DfpSession;
import com.google.api.ads.dfp.lib.client.DfpSessionFactory;

// GAM API 核心接口
public class GAMClient {
    
    private DfpSession session;
    private LineItemServiceInterface lineItemService;
    private OrderServiceInterface orderService;
    private CreativeServiceInterface creativeService;
    private AdUnitServiceInterface adUnitService;
    private ReportServiceInterface reportService;
    private ForecastServiceInterface forecastService;
    
    // 创建 GAM 客户端
    public GAMClient(String developerToken, String userAgent) {
        DfpSessionBuilder builder = new DfpSession.Builder()
            .withDeveloperToken(developerToken)
            .withUserAgent(userAgent)
            .withOAuth2Credential(new OAuth2Credential(System.getenv("GAM_CLIENT_ID"), System.getenv("GAM_CLIENT_SECRET")));
        
        this.session = builder.build();
        
        // 初始化所有 Service
        DfpSessionFactory factory = new DfpSessionFactory();
        this.lineItemService = factory.getService(session, LineItemServiceInterface.class);
        this.orderService = factory.getService(session, OrderServiceInterface.class);
        this.creativeService = factory.getService(session, CreativeServiceInterface.class);
        this.adUnitService = factory.getService(session, AdUnitServiceInterface.class);
        this.reportService = factory.getService(session, ReportServiceInterface.class);
        this.forecastService = factory.getService(session, ForecastServiceInterface.class);
    }
    
    // Line Item — 核心创建
    public LineItem createLineItem(LineItem li) throws ApiException {
        // 设置 Line Item 类型
        li.setLineItemType(LineItemType.GUARANTEED);
        
        // 设置优先级
        li.setPriority(Priority.HIGH);
        
        // 设置目标
        Targeting targeting = new Targeting();
        targeting.setTargetingType(TargetingType.GEO_TARGET);
        
        // 设置广告单位
        Set<Long> adUnitIds = new HashSet<>();
        adUnitIds.add(Long.parseLong(li.getAdUnitId()));
        targeting.setIncludedAssetIds(adUnitIds);
        li.setTargeting(targeting);
        
        // 设置排期
        li.setStartTime(new DateTime(li.getStartDate()));
        li.setEndTime(new DateTime(li.getEndDate()));
        li.setTimeZone(TimeZoneCode.UTC);
        
        // 设置出价
        if (li.getLineItemType() == LineType.PROGRAMMATIC) {
            li.setStandardPrice(new StandardPrice());
            li.getStandardPrice().setCurrencyCode("USD");
            li.getStandardPrice().setCpmMicroAmount(li.getCpmMicroAmount());
        } else {
            li.setGuaranteedImpressions(new GuaranteedImpressions());
            li.getGuaranteedImpressions().setCount(li.getImpressionsCount());
        }
        
        // 调用 API
        LineItem[] created = lineItemService.createLineItems(new LineItem[]{li});
        return created[0];
    }
    
    // 获取广告单位树
    public Map<String, AdUnit> getAdUnitTree(Long networkCode) throws ApiException {
        String query = String.format(
            "WHERE id IN (SELECT id FROM ad_unit WHERE networkCode = %d ORDER BY hierarchyPathSegments ASC)",
            networkCode
        );
        
        Page<AdUnit> page = adUnitService.getAdUnitsByStatement(
            new StatementBuilder().where(query).build()
        );
        
        Map<String, AdUnit> tree = new LinkedHashMap<>();
        if (page.getResults() != null) {
            for (AdUnit adUnit : page.getResults()) {
                tree.put(adUnit.getHierarchyPathSegments(), adUnit);
            }
        }
        return tree;
    }
    
    // 竞价预报 (Forecasting)
    public Forecast getBidForecast(ForecastRequest request) throws ApiException {
        // 预测某个 LI 在指定目标下的展示量/点击量/转化量
        Forecast forecast = forecastService.getForecast(request);
        return forecast;
    }
    
    // 批量生成报表
    public void generateReport() throws ApiException {
        // 生成 CSV/Excel 报表
        ReportDefinition reportDef = new ReportDefinition();
        reportDef.setReportName("Daily Line Item Performance");
        reportDef.setStartDate(new DateTime(new java.util.Date()));
        reportDef.setEndDate(new DateTime(new java.util.Date()));
        reportDef.setReportQuery(new ReportQuery());
        reportDef.getReportQuery().setDimensions(new String[] {
            "DATE", "LINE_ITEM_ID", "LINE_ITEM_NAME", "AD_UNIT_ID"
        });
        reportDef.getReportQuery().setColumns(new String[] {
            "IMPRESSIONS", "CLICKS", "CTR", "CONVERSIONS", "COST"
        });
        reportDef.getReportQuery().setDateRangeType(DateRangeType.LAST_30_DAYS);
        
        // 异步生成
        GenerateReportJob job = reportService.generateReport(reportDef);
        System.out.println("Report job created: " + job.getId());
        
        // 轮询完成状态
        while (true) {
            job = reportService.getReportJob(job.getId());
            if (job.getReportJobStatus() == ReportJobStatus.COMPLETED) {
                // 下载报表
                downloadReport(job.getResultFile());
                break;
            }
            Thread.sleep(5000);
        }
    }
}
```

### 3.4 GAM/DFP 竞价决策 API

```java
// GAM Ad Request 处理
//
// GAM 提供三种广告请求方式:
// 1. 网页请求 (AdSense/Ad Manager) — 通过 JavaScript 发起
// 2. SDK 请求 (Mobile App) — 通过 GAM SDK 发起
// 3. Server-to-Server (S2S) — 通过 API 直接请求

// 方式 3: Server-to-Server 广告请求 (Java)
public class GAMSSRRequest {
    
    public AdResponse requestAd(Site site, AdSlot adSlot, Targeting targeting) throws Exception {
        // 构建广告请求
        AdRequest request = new AdRequest();
        request.setNetworkCode(site.getNetworkCode());
        request.setAdUnitCode(adSlot.getAdUnitCode());
        request.setTargeting(targeting);
        
        // 设置 Header Bidding 参数
        request.setHeaderBiddingConfig(new HeaderBiddingConfig());
        request.getHeaderBiddingConfig().setRefreshPercent(10); // 10% 刷新率
        
        // 设置 SSP 竞价 ID (来自 Header Bidding)
        Map<String, String> bidResponses = targeting.getBidResponses();
        if (bidResponses != null) {
            for (Map.Entry<String, String> entry : bidResponses.entrySet()) {
                request.setTargetingValue(entry.getKey(), entry.getValue());
            }
        }
        
        // 调用 GAM API 获取广告
        AdResponse response = adServer.getAd(request);
        return response;
    }
}

// Header Bidding 集成流程:
//
// 1. 网页加载 → JS 库 (Prebid.js / OpenWrap) 收集竞价
//    ├── Prebid.js 并行请求多个 SSP
//    │   ├── AppNexus (Axonix)
//    │   ├── Index Exchange
//    │   ├── PubMatic
//    │   ├── RUBICON
//    │   └── ...
//    │
// 2. SSP 返回竞价 (Bid)
//    └── Bid: {"hb_bidder": "appnexus", "hb_adid": "abc123", "hb_pb": "$2.50"}
//
// 3. GAM 接收竞价 → 设置到 Ad Request
//    └── GAM 比较所有竞价 (保量 LI + Header Bidding 竞价)
//
// 4. GAM 返回获胜广告
//    └── Ad: 创意 HTML + 追踪像素
```

---

## 第四部分：DV360 竞价策略深度

### 4.1 竞价策略详解

```
┌────────────────────────────────────────────────────────────┐
│                 DV360 竞价策略体系                           │
│                                                            │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  出价策略 (Bidding Strategies)                         │  │
│  │                                                      │  │
│  │  1. Standard CPM (sCPM) — 手动出价                    │  │
│  │     广告主手动设置 CPM 价格                            │  │
│  │     适用: 品牌曝光, 保量交易                           │  │
│  │     优势: 控制力强, 成本可控                           │  │
│  │     劣势: 需要大量调优经验                              │  │
│  │                                                      │  │
│  │  2. Optimized CPM (oCPM) — 智能优化                   │  │
│  │     广告主设置目标 CPA, DV360 自动调整 CPM              │  │
│  │     适用: 转化优化, CPA 目标                           │  │
│  │     优势: 自动优化, 效果好                              │  │
│  │     劣势: 控制力较弱, 学习期需要数据                   │  │
│  │                                                      │  │
│  │  3. Target CPA — 目标每次转化费用                       │  │
│  │     设置目标 CPA, DV360 自动出价                       │  │
│  │     适用: 转化目标明确的场景                            │  │
│  │                                                      │  │
│  │  4. Target ROAS — 目标广告支出回报率                    │  │
│  │     设置目标 ROAS (如 400% = 每花 $1 赚 $4)            │  │
│  │     适用: 电商 ROI 导向                               │  │
│  │                                                      │  │
│  │  5. Maximize Conversions — 最大化转化                  │  │
│  │     在预算内最大化转化量                                │  │
│  │     适用: 预算有限, 追求最多转化                        │  │
│  │                                                      │  │
│  │  6. Maximize Clicks — 最大化点击                        │  │
│  │     在预算内最大化点击量                                │  │
│  │     适用: 品牌曝光 + 流量获取                           │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                            │
│  oCPM 竞价公式:                                            │
│  ──────────────                                            │
│  DV360 实际出价 = oCPM = eCPA / pCVR × 1000               │
│  其中:                                                    │
│  - eCPA: 广告主设置的每次转化费用目标                        │
│  - pCVR: DV360 预测的转化概率 (通过模型)                    │
│  - 1000: 每千次展示单位                                     │
│                                                            │
│  示例:                                                    │
│  - 广告主目标 CPA = $20                                   │
│  - DV360 预测 pCVR = 2% (0.02)                           │
│  - DV360 出价 = $20 / 0.02 × 1000 = $1000 CPM           │
│  - 如果 pCVR 更低 (如 1%) → CPM = $2000                  │
│  - 如果 pCVR 更高 (如 5%) → CPM = $400                   │
│                                                            │
│  → DV360 自动根据预估 pCVR 调整出价, 追求 CPA 目标         │
└────────────────────────────────────────────────────────────┘
```

### 4.2 RTB 竞价对接 — GAM ↔ DV360

```
RTB 竞价对接架构:

┌──────────────────────────────────────────────────────────────┐
│                                                              │
│  ┌─────────────────┐    RTB 请求    ┌─────────────────────┐ │
│  │  GAM (Ad Server) │ ────────────→ │  Ad Exchange        │ │
│  │                  │               │  (Google AdX)       │ │
│  │  1. 页面加载      │               │                     │ │
│  │  2. 触发 GAM 广告 │               │  转发竞价请求         │ │
│  │     请求          │               │  到多个 DSP          │ │
│  │  3. 并行请求 SSP  │               │                     │ │
│  │     竞价          │               │                     │ │
│  └─────────────────┘               │                     │ │
│                                     │  ┌───────────────┐  │ │
│                                     │  │  DSP 1        │  │ │
│                                     │  │  (DV360)      │  │ │
│                                     │  └───────┬───────┘  │ │
│                                     │          │          │ │
│                                     │  ┌───────▼───────┐  │ │
│                                     │  │  DSP 2        │  │ │
│                                     │  │  (MediaMath)  │  │ │
│                                     │  └───────┬───────┘  │ │
│                                     │          │          │ │
│                                     │  ┌───────▼───────┐  │ │
│                                     │  │  DSP 3        │  │ │
│                                     │  │  (The Trade    │  │ │
│                                     │  │   Desk)       │  │ │
│                                     │  └───────┬───────┘  │ │
│                                     └──────────┼──────────┘ │
│                                                │            │
│                                         竞价响应 (Bids)      │
│                                                │            │
│                                          ┌─────▼─────┐      │
│                                          │ Ad Exchange│      │
│                                          │ 选最高出价 │      │
│                                          └─────┬─────┘      │
│                                                │             │
│                                        ┌───────▼───────┐     │
│                                        │ 获胜 DSP     │     │
│                                        │ 返回创意 HTML  │     │
│                                        └───────┬───────┘     │
│                                                │             │
│                                        ┌───────▼───────┐     │
│                                        │ GAM 展示广告  │     │
│                                        └───────────────┘     │
└──────────────────────────────────────────────────────────────┘

RTB 竞价时间线 (端到端 < 100ms):
├── 0ms:    GAM 发起竞价请求
├── 5ms:    GAM 转发到 Ad Exchange
├── 10ms:   Ad Exchange 通知所有 DSP
├── 20-80ms: DSP 竞价 (DV360 计算 pCTR/pCVR)
├── 80ms:   Ad Exchange 收到所有出价
├── 85ms:   Ad Exchange 选出最高出价者
├── 90ms:   返回创意 HTML
├── 95ms:   GAM 接收并渲染广告
└── 100ms:  广告展示给用户
```

---

## 第五部分：实战排障与调优

### 5.1 常见问题速查

| 症状 | 可能原因 | 排查方法 | 解决方案 |
|------|----------|----------|----------|
| **SDC 对接失败** | 账户权限/SDF 配置 | GAM SDC 设置页面 | 检查账户权限, 启用 SDC, 验证域名 |
| **DV360 不填充广告** | LI 未同步/目标不匹配 | GAM 订单/LI 列表 | 检查 LI 同步状态, 检查 LI 目标和排期 |
| **RTB 无竞价** | SSP 未配置/出价太低 | GAM RTB 报告 | 检查 SSP 竞价 ID, 提高出价 |
| **创意未审批** | 创意审核不通过 | DV360 创意状态 | 检查拒绝原因, 修改创意规格 |
| **流量不足** | 目标太窄/预算太低 | 报表分析 | 放宽目标, 增加预算, 检查优先级 |
| **oCPM 效果差** | 学习期不足/数据少 | 报表对比 | 等待学习期 (通常 3-7 天), 增加数据量 |
| **Header Bidding 延迟高** | 竞价库过多 | 页面速度报告 | 减少 SSP 数量, 优化 Prebid.js |

### 5.2 DV360 调优建议

```
DV360 优化 Checklist:

1. 竞价策略选择:
   - 品牌曝光 → Standard CPM
   - 转化目标 → Optimized CPM / Target CPA
   - ROI 导向 → Target ROAS
   - 预算有限 → Maximize Conversions

2. 出价调整:
   - oCPM: 根据 CPA 实际表现调整目标 CPA
   - sCPM: 根据实际 CPM 和行业基准调整
   - 定期 (每周) 检查出价效率

3. 定向优化:
   - 使用受众群体 (In-Market, Affinity, Custom Segments)
   - A/B 测试不同定向组合
   - 排除低效受众 (Exclusion)

4. 创意优化:
   - 使用动态创意优化 (DCO)
   - A/B 测试不同创意尺寸和文案
   - 视频广告前 5 秒决定留存

5. 时段优化:
   - 按小时分析投放效果
   - 高峰时段提高出价
   - 低效时段降低出价或暂停

6. 平台优化:
   - 检查各平台 (App/Web/TV) 的 ROI
   - 高 ROI 平台增加预算
   - 低 ROI 平台减少预算
```

---

## 第六部分：自测

### Q1：DV360 的 SDC 对接和手动 LI 绑定有什么区别？

<details>
<summary>点击查看参考答案</summary>

**SDC 对接**:
- 自动化: DV360 创建 LI → 自动同步到 GAM
- 双向同步: GAM 变更也同步回 DV360
- 数据回流: GAM 自动上报展示/点击/转化到 DV360
- 适用: 新投放, 推荐方式
- 限制: 仅支持部分 LI 类型

**手动 LI 绑定**:
- 在 GAM 手动创建 LI → 绑定 DV360 的 RTB 交易
- 更灵活: 支持更多 LI 类型和定制配置
- 手动同步: 需要手动维护 LI 状态
- 适用: 特殊场景, 需要精细控制

**建议**: 优先使用 SDC，特殊情况再手动绑定。
</details>

### Q2：oCPM 的竞价公式中，pCVR 对出价有什么影响？

<details>
<summary>点击查看参考答案</summary>

**竞价公式**: `oCPM = 目标 CPA / pCVR × 1000`

**pCVR 与出价成反比**:
- pCVR 越高 → 出价越低 (因为转化概率高，不需要出高价)
- pCVR 越低 → 出价越高 (因为转化概率低，需要出高价竞争)

**示例**:
```
目标 CPA = $20

pCVR = 5% → oCPM = $20 / 0.05 × 1000 = $400
pCVR = 2% → oCPM = $20 / 0.02 × 1000 = $1000
pCVR = 1% → oCPM = $20 / 0.01 × 1000 = $2000
```

**关键点**:
- DV360 通过模型估算 pCVR (考虑用户历史行为、上下文等)
- pCVR 不准会导致出价过高 (浪费预算) 或过低 (拿不到流量)
- 学习期 (3-7 天) pCVR 模型逐步准确
- 数据越多，pCVR 越准，竞价效果越好
</details>

### Q3：Header Bidding 中，GAM 如何决定最终展示哪个广告？

<details>
<summary>点击查看参考答案</summary>

**GAM 竞价决策流程**:

1. 保量 LI (Guaranteed LI) 优先检查
   - 检查流量配额 + 定向 + 排期
   - 匹配则直接展示保量创意

2. 保量 LI 无法满足时，进入 RTB 竞价
   - GAM 并行请求所有 Header Bidding 的竞价
   - 同时 GAM 也检查自己的 RTB LI (如 DV360 的 RTB LI)

3. 比较所有竞价结果
   - 保量 LI 有固定优先级 (高于任何竞价)
   - RTB LI 之间按出价比较
   - 最高出价者获胜

4. 如果 RTB 无竞价
   - GAM 检查兜底广告 (Fallback Ad)
   - 如果没有兜底 → 留白 (Blank)

**优先级顺序**:
```
保量 LI (按优先级: Priority > Super > High > Medium > Low)
  → RTB 竞价 (Header Bidding)
    → GAM RTB LI (如 DV360 RTB)
      → 兜底广告
```
</details>

### Q4：GAM API 中，如何批量创建 Line Items？

<details>
<summary>点击查看参考答案</summary>

**批量创建方式**:

Java (GAM API):
```java
// 创建多个 Line Items
LineItem[] lineItems = new LineItem[3];
// ... 初始化 lineItems

try {
    LineItem[] results = lineItemService.createLineItems(lineItems);
    for (LineItem li : results) {
        System.out.println("Created: " + li.getName());
    }
} catch (ApiException e) {
    // 批量创建部分失败时，检查 e.getErrors()
    for (ApiError error : e.getErrors()) {
        System.err.println("Error: " + error.getTrigger());
    }
}
```

DV360 API (Go):
```go
// 批量创建
batch := &displayvideo.BatchUpdateLineItemsRequest{
    Requests: []*displayvideo.UpdateLineItemRequest{
        { LineItem: li1 },
        { LineItem: li2 },
        { LineItem: li3 },
    },
}
resp := lineItemService.BatchUpdate(batch).Context(ctx).Do()
```

**注意事项**:
- 批量请求有大小限制 (通常最多 1000 个)
- 部分失败不影响成功的部分
- 使用 Batch API 减少网络开销
- 建议每批 100-500 个
</details>

### Q5：DV360 和 Google Ads (Search) 有什么本质区别？

<details>
<summary>点击查看参考答案</summary>

**DV360 (Display & Video 360)**:
- 面向**展示广告和视频广告**
- 基于 RTB (实时竞价)
- 面向 DSP (Demand-Side Platform)
- 广告主/代理商使用
- 展示为主 (Banner/视频/原生)
- 竞价策略: CPM/oCPM/RPOAS

**Google Ads (Search)**:
- 面向**搜索广告**
- 基于关键词竞价
- 面向 Search Network
- 面向广告主
- 搜索为主 (文字/购物)
- 竞价策略: CPC/CPA/ROAS

**关键区别**:
1. **广告类型**: DV360 = 展示/视频, Google Ads = 搜索/购物
2. **竞价方式**: DV360 = RTB, Google Ads = 关键词竞价
3. **定位**: DV360 = DSP, Google Ads = 搜索平台
4. **账户体系**: 完全独立的账户体系
5. **数据隔离**: DV360 和 Google Ads 数据不互通 (需要整合)

**关联**:
- DV360 和 Google Ads 同属 Google 广告生态
- 数据可通过 Google Marketing Platform (GMP) 整合
- DV360 可以与 Google Ads Campaign 配合投放
</details>

---

## 第七部分：动手验证

### 7.1 DV360 API 快速测试

```bash
# 1. 创建 Google Cloud 项目并启用 DV360 API
gcloud projects create your-dv360-project
gcloud services enable displayvideo.googleapis.com

# 2. 创建 Service Account
gcloud iam service-accounts create dv360-automation \
  --display-name "DV360 Automation"

# 3. 下载 Service Account Key
gcloud iam service-accounts keys create dv360-key.json \
  --iam-account dv360-automation@your-dv360-project.iam.gserviceaccount.com

# 4. 在 GAM 中添加 Service Account 为管理员
# GAM 管理后台 → 广告客户 → 添加用户 → 输入 SA 邮箱

# 5. 运行 Go 脚本测试
go run dv360_test.go
```

### 7.2 GAM API 快速测试

```bash
# 1. 创建 GAM API Service Account
# Google Cloud Console → IAM → 创建 SA

# 2. 在 GAM 中添加该 SA 为广告主管理员

# 3. 测试 Java 代码
mvn test -Dtest=GAMTest
```

### 7.3 验证 SDC 对接

```bash
# 1. 在 GAM 中检查 SDC 状态
# GAM 管理后台 → SDC 设置

# 2. 检查 DV360 中的 SDC 订单
# DV360 → 订单 → 查看 SDC 订单状态

# 3. 验证数据回流
# DV360 → 报表 → 检查 GAM 上报的展示/点击数据
```

---

*本文档基于 Google Ad Manager v202405 和 DV360 v1 API 整理。GAM/DFP API 文档: https://developers.google.com/ad-manager  DV360 API: https://developers.google.com/display-video*
