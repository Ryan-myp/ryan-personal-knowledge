# Amazon Advertising API — 高级用法深度指南

> 创建日期: 2026-06-10
> 作者: Ryan
> 定位: 资深专家级 — API 高级用法

---

## 第一部分: Amazon 认证体系

### 1.1 OAuth2 认证流程

```
Amazon Advertising API 认证采用 OAuth2 + Client Credentials:

┌──────────────────────────────────────────────────────────────┐
│              Amazon 认证流程                                    │
│                                                              │
│  前置条件:                                                   │
│  ├── Amazon Seller/Agency Account                             │
│  ├── Amazon Advertising API Access (申请)                     │
│  ├── SP-API Client ID + Client Secret                         │
│  └─ LWA (Login with Amazon) Refresh Token                    │
│                                                              │
│  认证流程:                                                   │
│  ├── Step 1: 获取 Access Token                                │
│  │   POST https://api.amazon.com/auth/o2/token               │
│  │   body:                                                   │
│  │   {                                                        │
│  │     "grant_type": "refresh_token",                         │
│  │     "client_id": "{client_id}",                            │
│  │     "client_secret": "{client_secret}",                    │
│  │     "refresh_token": "{refresh_token}"                     │
│  │   }                                                       │
│  │                                                           │
│  │   response:                                               │
│  │   {                                                        │
│  │     "access_token": "eyJ...",                              │
│  │     "expires_in": 3600,                                    │
│  │     "refresh_token": "{refresh_token}"                     │
│  │   }                                                       │
│  │                                                           │
│  ├── Step 2: 使用 Token 调用 API                              │
│  │   GET https://advertising-api.amazon.com/v2/spCampaigns   │
│  │   headers:                                                │
│  │   {                                                        │
│  │     "Content-Type": "application/json",                    │
│  │     "Authorization": "Bearer {access_token}",              │
│  │     "Amazon-Access-Token-Expiration": "3600"               │
│  │   }                                                       │
│  └─ Step 3: Token 刷新                                       │
│      ├── Access Token 有效期: 1 小时                           │
│      ├── Refresh Token 有效期: 1 年 (需每年刷新一次)            │
│      └─ Refresh Token 只能刷新一次 (one-time use)             │
│                                                              │
│  区域端点 (Region Endpoints):                                  │
│  ├── US: advertising-api.amazon.com                          │
│  ├── EU: advertising-api-eu.amazon.com                       │
│  ├── FE: advertising-api-fe.amazon.com                       │
│  └─ JP: advertising-api-jp.amazon.com                        │
└──────────────────────────────────────────────────────────────┘
```

### 1.2 SP-API 权限体系

```
Amazon SP-API 权限:

┌──────────────────────────────────────────────────────────────┐
│              SP-API 权限                                       │
│                                                              │
│  权限类型:                                                   │
│  ├── Catalog — 商品数据                                      │
│  ├── Orders — 订单数据                                       │
│  ├── Reports — 报告数据                                       │
│  ├── Finances — 财务数据                                     │
│  ├── Notifications — 通知                                    │
│  └─ Applications — 应用权限                                  │
│                                                              │
│  Advertising API 权限:                                       │
│  ├── campaigns/v2 — 广告系列管理                              │
│  ├── targeting/v2 — 定向管理                                  │
│  ├── keywords/v2 — 关键词管理                                 │
│  ├── products/v2 — 商品管理                                  │
│  ├── headlines/v2 — 标题管理                                  │
│  ├── portfolios/v2 — 投资组合管理                              │
│  └─ reports/v2 — 报告管理                                    │
│                                                              │
│  权限授予流程:                                               │
│  ├── 创建 App → 获取 Client ID/Secret                         │
│  ├── 用户授权 → 获取 Refresh Token                            │
│  ├── 使用 Refresh Token → 获取 Access Token                   │
│  └─ 使用 Access Token → 调用 API                              │
└──────────────────────────────────────────────────────────────┘
```

---

## 第二部分: Campaign API 深度使用

### 2.1 Campaign 管理

```
Campaign CRUD 操作:

1. 创建 Sponsored Products Campaign:

POST /v2/spCampaigns
{
    "campaignName": "Summer Sale SP",
    "campaignType": "SPONSORED_PRODUCTS",
    "state": "paused",  // enabled/paused
    "defaultBid": 1.50,  // USD
    "dailyBudget": 50.00,
    "budgetExpirationDate": "2026-12-31",
    "targetingType": "AUTO",  // AUTO/MANUAL
    "adGroupData": [
        {
            "adGroupName": "Auto Targeting AG",
            "state": "enabled",
            "defaultBid": 1.50,
            "productAdGroups": [
                {
                    "asin": "B08XYZ1234",
                    "targeting": {
                        "type": "AUTO"
                    }
                }
            ]
        }
    ],
    "placementDefaults": [
        {
            "placementType": "REST_OF_SEARCH",
            "bidMultiplier": 0.80  // 80% 基础出价
        },
        {
            "placementType": "PRODUCT_PAGES",
            "bidMultiplier": 1.00  // 100% 基础出价
        },
        {
            "placementType": "SEARCH_TOP_OF_SEARCH",
            "bidMultiplier": 1.50  // 150% 基础出价
        }
    ]
}

2. 创建 Sponsored Brands Campaign:

POST /v2/sbCampaigns
{
    "campaignName": "Brand Awareness SB",
    "campaignType": "SPONSORED_BRANDS",
    "state": "enabled",
    "defaultBid": 0.80,
    "dailyBudget": 30.00,
    "portfolioId": "portfolio_123",
    "targetingType": "MANUAL",
    "products": {
        "targetType": "PRODUCT",
        "ids": ["B08XYZ1234", "B08ABC5678"]
    },
    "customProductTargeting": {
        "asinCount": 50,
        "asinCategory": ["Electronics", "Cell Phones"],
        "targetType": "ASIN_CATEGORY"
    }
}

3. 更新 Campaign:

PATCH /v2/spCampaigns/{campaignId}
{
    "state": "enabled",
    "dailyBudget": 75.00,
    "defaultBid": 2.00
}

4. 获取 Campaign:

GET /v2/spCampaigns?limit=10&sort=metric
{
    "campaigns": [
        {
            "campaignId": "sp_123456",
            "campaignName": "Summer Sale SP",
            "campaignType": "SPONSORED_PRODUCTS",
            "state": "enabled",
            "defaultBid": 1.50,
            "dailyBudget": 50.00,
            "metrics": {
                "impressions": 100000,
                "clicks": 2000,
                "ctr": 0.02,
                "orders": 50,
                "acos": 0.25,
                "roas": 4.0,
                "sales": 2000.00
            }
        }
    ]
}

5. 批量操作 (批量更新):

PATCH /v2/spCampaigns/batch
[
    {
        "op": "replace",
        "path": "/campaigns/{id1}",
        "value": {
            "defaultBid": 2.00,
            "state": "enabled"
        }
    },
    {
        "op": "replace",
        "path": "/campaigns/{id2}",
        "value": {
            "defaultBid": 1.80,
            "state": "paused"
        }
    }
]
```

### 2.2 Keyword API

```
Keyword 管理:

1. 添加关键词 (Manual Targeting):

POST /v2/spCampaigns/{campaignId}/keywords
{
    "keywordDataList": [
        {
            "keywordText": "wireless earbuds",
            "matchType": "EXACT",
            "state": "enabled",
            "bid": 2.50,
            "negate": false
        },
        {
            "keywordText": "bluetooth earbuds",
            "matchType": "PHRASE",
            "state": "enabled",
            "bid": 1.80,
            "negate": false
        },
        {
            "keywordText": "cheap earbuds",
            "matchType": "BROAD",
            "state": "enabled",
            "bid": 1.20,
            "negate": true  // 否定关键词
        }
    ]
}

2. 匹配类型对比:

| 匹配类型 | 匹配规则 | 流量 | 精度 | 出价建议 |
|---------|---------|------|------|---------|
| EXACT  | 完全匹配  | 低   | 高   | 高 (2-5x) |
| PHRASE | 包含短语  | 中   | 中   | 中 (1-2x) |
| BROAD  | 相关搜索  | 高   | 低   | 低 (0.5-1x) |

3. 否定关键词:

NEGATIVE_EXACT — 精确否定
NEGATIVE_PHRAS — 短语否定
NEGATIVE_BROAD — 广泛否定

示例: 否定不相关搜索
{
    "keywordText": "free",
    "matchType": "BROAD",
    "negate": true
}

4. 关键词自动出价调整:

自动规则:
├── 如果 ACOS < 20% → 出价 +10%
├── 如果 ACOS > 40% → 出价 -10%
├── 如果 CVR < 5% → 出价 -20%
├── 如果 CVR > 15% → 出价 +20%
└─ 如果 CTR < 0.3% → 暂停/否定关键词

实现:
├── 通过 Amazon Advertising API 自动调用                          │
├── 或使用 Amazon Ads Console 内置规则                           │
└─ 或自建脚本 (每小时/每天)
```

---

## 第三部分: 报告 API

### 3.1 报告生成

```
Amazon 报告 API:

1. 创建报告:

POST /reports/reports
{
    "reportType": "GET_BROWSE_TREE_REPORT",  // 报告类型
    "dataStartTime": "2026-01-01T00:00:00Z",
    "dataEndTime": "2026-06-10T23:59:59Z",
    "version": 1,
    "reportOptions": {
        "marketplaceIds": ["ATVPDKIKX0DER"]  // US marketplace
    }
}

2. 报告类型:

报告类型:
├── GET_BROWSE_TREE_REPORT — 浏览树报告
├── GET_SEARCH_INTEGRATION_REPORT — 搜索集成报告
├── GET_ADVERTISING_REPORT — 广告报告
├── GET_PERFORMANCE_REPORT — 性能报告
├── GET_SEARCH_PERFORMANCE_REPORT — 搜索性能报告
├── GET_TARGETING_REPORT — 定向报告
├── GET_SP_CAMPAIN_REPORT — SP 广告系列报告
├── GET_SB_CAMPAIN_REPORT — SB 广告系列报告
├── GET_SD_CAMPAIN_REPORT — SD 广告系列报告
└─ GET_PRODUCT_DIAGNOSTICS_REPORT — 商品诊断报告

3. 下载报告:

GET /reports/{reportId}/download
{
    "downloadUrl": "https://s3.amazonaws.com/...",
    "expiresIn": 300  // 5 分钟有效
}

4. 报告状态:

报告状态:
├── CREATE_IN_PROGRESS — 创建中
├── COMPLETE — 已完成
├── FAILED — 失败
└─ INVALID_INPUT — 输入无效

检查报告状态:
GET /reports/{reportId}
```

### 3.2 Search Term Report

```
Search Term Report 深度使用:

搜索词报告字段:
├── campaignName — 广告系列名称
├── adGroupName — 广告组名称
├── keywordText — 匹配关键词
├── matchType — 匹配类型
├── searchTerm — 实际搜索词
├── impressions — 展示次数
├── clicks — 点击次数
├── ctr — 点击率
├── cpc — 平均 CPC
├── orders — 订单数
├── acos — ACOS
├── roas — ROAS
├── sales — 销售额
└─ placement — 展示位置

搜索词分析流程:

1. 低转化高点击 → 添加否定关键词                              │
2. 高转化低流量 → 加量出价                                    │
3. 高点击低展示 → 提高基础出价                                │
4. 零展示 → 检查匹配类型/出价/竞争                              │
5. 高 ACOS → 降低出价或否定                                   │

批量否定关键词:
POST /v2/negativeKeywords
{
    "negateKeywords": [
        {
            "keywordText": "free",
            "matchType": "BROAD"
        },
        {
            "keywordText": "cheap",
            "matchType": "BROAD"
        },
        {
            "keywordText": "broken",
            "matchType": "BROAD"
        }
    ]
}
```

---

## 第四部分: Portfolio 与预算优化

### 4.1 Portfolio 管理

```
Portfolio (投资组合) 管理:

Portfolio 作用:
├── 聚合多个广告系列                                             │
├── 统一管理预算                                                 │
├── 统一报告                                                     │
└─ 自动优化预算分配                                             

创建 Portfolio:

POST /v2/portfolios
{
    "name": "Electronics Portfolio",
    "type": "SHOPPING",  // SHOPPING/SEARCH/DISPLAY
    "budget": {
        "amount": 1000.00,
        "currencyCode": "USD",
        "type": "DAILY"  // DAILY/LIFETIME
    },
    "description": "Electronics category portfolio"
}

Portfolio 预算分配策略:

1. 等分分配:
   └── 每个广告系列获得 1/n 的预算

2. 按表现分配:
   ├── 高 ROAS 广告系列: 预算 +20%
   ├── 低 ROAS 广告系列: 预算 -20%
   └─ 新广告系列: 测试预算 (固定)

3. 按目标分配:
   ├── Sales Goal: 按销售目标分配
   ├── ACOS Goal: 按 ACOS 目标分配
   └─ ROAS Goal: 按 ROAS 目标分配

4. 自动预算分配:
   ├── Amazon DSP 提供自动预算分配                                 │
   ├── 基于历史表现预测最优分配                                    │
   └─ 每日自动调整
```

---

## 第五部分: 错误处理与速率限制

### 5.1 错误码

```
Amazon API 错误码:

┌──────────────────────────────────────────────────────────────┐
│              Amazon API 错误                                   │
│                                                              │
│  HTTP 状态码:                                               │
│  ├── 200: Success                                          │
│  ├── 400: Bad Request — 参数错误                             │
│  ├── 401: Unauthorized — 认证失败                             │
│  ├── 403: Forbidden — 权限不足                               │
│  ├── 404: Not Found — 资源不存在                             │
│  ├── 429: Too Many Requests — 速率限制                       │
│  ├── 500: Internal Server Error — 服务器错误                  │
│  ├── 503: Service Unavailable — 服务不可用                    │
│  └─ 504: Gateway Timeout — 网关超时                          │
│                                                              │
│  业务错误:                                                   │
│  ├── CAMPAIGN_NOT_FOUND — 广告系列不存在                      │
│  ├── AD_GROUP_NOT_FOUND — 广告组不存在                       │
│  ├── INVALID_BID — 出价无效                                   │
│  ├── BUDGET_EXCEEDED — 预算超支                               │
│  ├── DAILY_BUDGET_EXCEEDED — 日预算超支                       │
│  ├── CAMPAIGN_STATE_ERROR — 广告系列状态错误                   │
│  └─ PRODUCT_NOT_FOUND — 商品不存在                            │
│                                                              │
│  认证错误:                                                   │
│  ├── INVALID_TOKEN — 无效令牌                                 │
│  ├── TOKEN_EXPIRED — 令牌过期                                 │
│  ├── INVALID_GRANT — 授权无效                                 │
│  └─ INSUFFICIENT_PERMISSIONS — 权限不足                       │
└──────────────────────────────────────────────────────────────┘
```

### 5.2 速率限制

```
Amazon API 速率限制:

┌──────────────────────────────────────────────────────────────┐
│              速率限制规则                                       │
│                                                              │
│  限制类型:                                                   │
│  ├── Requests per second: 5 次/秒 (Per Campaign)             │
│  ├── Requests per day: 10,000 次/天                          │
│  └─ Report generation: 10 次/天                              │
│                                                              │
│  响应头:                                                   │
│  ├── x-amzn-RequestId — 请求 ID                              │
│  ├── x-amzn-ErrorType — 错误类型                              │
│  └─ Retry-After — 重试延迟 (秒)                              │
│                                                              │
│  处理:                                                       │
│  ├── 监控响应头                                              │
│  ├── 指数退避                                                │
│  └─ 批量操作减少请求                                          │
└──────────────────────────────────────────────────────────────┘
```

### 5.3 错误处理代码

```python
import time
import requests

class AmazonAPIError(Exception):
    """Amazon API 异常"""
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"HTTP {status_code}: {message}")

RATE_LIMIT_STATUS = {429}
RETRYABLE_STATUS = {429, 500, 503, 504}

def safe_amazon_request(url: str, method: str = "GET",
                        data: dict = None, headers: dict = None,
                        max_retries: int = 3,
                        base_delay: float = 1.0) -> dict:
    """
    安全的 Amazon API 请求
    
    参数:
    ├── url: API 端点
    ├── method: HTTP 方法
    ├── data: 请求数据
    ├── headers: 请求头
    ├── max_retries: 最大重试次数
    └── base_delay: 基础延迟 (秒)
    
    返回:
    └── 响应数据
    """
    headers = headers or {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
    }
    
    for attempt in range(max_retries):
        try:
            response = requests.request(
                method, url, json=data, headers=headers,
                timeout=30
            )
            
            # 速率限制
            if response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', base_delay))
                print(f"Rate limited. Retrying after {retry_after}s...")
                time.sleep(retry_after)
                continue
            
            # 可重试错误
            if response.status_code in RETRYABLE_STATUS:
                delay = base_delay * (2 ** attempt)
                print(f"Retryable error ({response.status_code}). Retry in {delay}s...")
                time.sleep(delay)
                continue
            
            # 成功
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                time.sleep(delay)
            else:
                raise
    
    raise Exception(f"Failed after {max_retries} retries")

# 使用示例
campaigns = safe_amazon_request(
    "https://advertising-api.amazon.com/v2/spCampaigns",
    headers={"Authorization": f"Bearer {access_token}"},
)
```

---

## 第六部分: 最佳实践

```
Amazon Advertising API 最佳实践:

1. 认证管理:
   ├── 安全存储 credentials (环境变量)
   ├── 自动刷新 token
   └─ 定期轮换 refresh token

2. 请求优化:
   ├── 使用批量操作
   ├── 使用缓存
   └─ 使用 search stream

3. 错误处理:
   ├── 监控 429/500/503/504
   ├── 指数退避
   └─ 日志所有错误

4. 报告:
   ├── 使用 search term report 优化关键词
   ├── 使用 placement report 优化 bid adjustment
   └─ 使用 campaign report 优化预算

5. 自动化:
   ├── ACOS < 20% → 出价 +10%
   ├── ACOS > 40% → 出价 -10%
   ├── CVR > 15% → 出价 +20%
   └─ 搜索词转化率低 → 否定关键词
```

---

*今天花 90 分钟：深入掌握 Amazon Advertising API 高级用法*
*答不出自测题？回去重读对应章节。*

---

## 自测题

### 问题 1
ACOS 和 TACOS 的区别是什么？

<details>
<summary>查看答案</summary>

ACOS = Ad Spend / Ad Sales (只看广告销售)
TACOS = Total Ad Spend / Total Sales (包含有机销售)
TACOS 更能反映整体广告效率
</details>

### 问题 2
Amazon API 的三种竞价方式分别是什么？

<details>
<summary>查看答案</summary>

1. Dynamic Bids - Down Only (动态降价)
2. Dynamic Bids - Up and Down (动态升降)
3. Fixed Bids (固定出价)
</details>

### 问题 3
Amazon 广告 API 的速率限制是多少？

<details>
<summary>查看答案</summary>

5 次/秒 (Per Campaign), 10,000 次/天, Report generation: 10 次/天
</details>

---

### Amazon Ads API 的 Go 实现

```go
// Amazon Ads API: Go 生产级客户端实现
// 覆盖 OAuth2、SP/MC API、广告系列管理、报告下载
package amazonads

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"
)

// ==================== Amazon 认证 ====================

// AmazonClient Amazon API 客户端
type AmazonClient struct {
	baseURL      string
	clientKey    string
	clientSecret string
	accessToken  string
	expiresIn    int
	expiresAt    time.Time
	httpClient   *http.Client
}

// NewAmazonClient 创建客户端
func NewAmazonClient(clientKey, clientSecret string) *AmazonClient {
	return &AmazonClient{
		baseURL:      "https://advertising.api.amazon.com",
		clientKey:    clientKey,
		clientSecret: clientSecret,
		httpClient:   &http.Client{Timeout: 30 * time.Second},
	}
}

// Authenticate OAuth2 认证
func (c *AmazonClient) Authenticate() error {
	reqBody := map[string]string{
		"grant_type":    "client_credentials",
		"client_id":     c.clientKey,
		"client_secret": c.clientSecret,
	}

	req, _ := json.Marshal(reqBody)
	resp, err := c.httpClient.Post(
		"https://api.amazon.com/auth/o2/token",
		"application/json",
		bytes.NewReader(req),
	)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	var result map[string]interface{}
	json.NewDecoder(resp.Body).Decode(&result)

	c.accessToken, _ = result["access_token"].(string)
	c.expiresIn = int(result["expires_in"].(float64))
	c.expiresAt = time.Now().Add(time.Duration(c.expiresIn) * time.Second)
	return nil
}

func (c *AmazonClient) hasToken() bool {
	return c.accessToken != "" && time.Now().Before(c.expiresAt)
}

// ==================== SP API 接口封装 ====================

// Campaign Amazon 广告系列
type Campaign struct {
	CampaignId          string  `json:"campaignId"`
	CampaignName        string  `json:"campaignName"`
	CampaignType        string  `json:"campaignType"`
	State               string  `json:"state"`
	BudgetAmount        float64 `json:"budgetAmount"`
	BudgetCurrencyCode  string  `json:"budgetCurrencyCode"`
	BudgetPeriod        string  `json:"budgetPeriod"`
	TargetingReturnType string  `json:"targetingReturnType"`
}

// AdGroup 广告组
type AdGroup struct {
	AdGroupId   string  `json:"adGroupId"`
	AdGroupName string  `json:"adGroupName"`
	Bid         float64 `json:"bid"`
	State       string  `json:"state"`
}

// Ad 广告
type Ad struct {
	AdId       string `json:"adId"`
	Name       string `json:"name"`
	AdGroupId  string `json:"adGroupId"`
	CampaignId string `json:"campaignId"`
}

// ==================== 广告系列 CRUD ====================

// CreateCampaign 创建广告系列
func (c *AmazonClient) CreateCampaign(campaign *Campaign) (*Campaign, error) {
	if !c.hasToken() {
		return nil, fmt.Errorf("not authenticated")
	}

	body, _ := json.Marshal(campaign)
	req, _ := http.NewRequest("POST",
		c.baseURL+"/sp/campaigns",
		bytes.NewReader(body),
	)
	req.Header.Set("Authorization", "Bearer "+c.accessToken)
	req.Header.Set("Content-Type", "application/json")

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	var result Campaign
	json.NewDecoder(resp.Body).Decode(&result)
	return &result, nil
}

// GetCampaign 获取广告系列
func (c *AmazonClient) GetCampaign(campaignId string) (*Campaign, error) {
	if !c.hasToken() {
		return nil, fmt.Errorf("not authenticated")
	}

	req, _ := http.NewRequest("GET",
		c.baseURL+"/sp/campaigns/"+campaignId,
		nil,
	)
	req.Header.Set("Authorization", "Bearer "+c.accessToken)

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	var result Campaign
	json.NewDecoder(resp.Body).Decode(&result)
	return &result, nil
}

// ==================== 广告组管理 ====================

// CreateAdGroup 创建广告组
func (c *AmazonClient) CreateAdGroup(campaignId string, adGroup *AdGroup) (*AdGroup, error) {
	if !c.hasToken() {
		return nil, fmt.Errorf("not authenticated")
	}

	body, _ := json.Marshal(adGroup)
	req, _ := http.NewRequest("POST",
		c.baseURL+"/sp/campaigns/"+campaignId+"/adgroups",
		bytes.NewReader(body),
	)
	req.Header.Set("Authorization", "Bearer "+c.accessToken)
	req.Header.Set("Content-Type", "application/json")

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	var result AdGroup
	json.NewDecoder(resp.Body).Decode(&result)
	return &result, nil
}

// UpdateBid 更新出价
func (c *AmazonClient) UpdateBid(adGroupId string, newBid float64) error {
	if !c.hasToken() {
		return fmt.Errorf("not authenticated")
	}

	type bidUpdate struct {
		Bid float64 `json:"bid"`
	}
	body, _ := json.Marshal(bidUpdate{Bid: newBid})

	req, _ := http.NewRequest("PUT",
		c.baseURL+"/sp/adgroups/"+adGroupId+"/bids",
		bytes.NewReader(body),
	)
	req.Header.Set("Authorization", "Bearer "+c.accessToken)
	req.Header.Set("Content-Type", "application/json")

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	return nil
}

// ==================== 报告管理 ====================

// ReportResponse 报告响应
type ReportResponse struct {
	ReportId          string `json:"reportId"`
	ReportType        string `json:"reportType"`
	State             string `json:"state"`
	DownloadURL       string `json:"downloadUrl"`
	ErrorDescription  string `json:"errorDescription"`
}

// GenerateReport 生成广告报告
func (c *AmazonClient) GenerateReport(reportType string, params map[string]string) (string, error) {
	if !c.hasToken() {
		return "", fmt.Errorf("not authenticated")
	}

	reportSpec := map[string]interface{}{
		"reportType":   reportType,
		"dateRange":    params["dateRange"],
		"dimensions":   params["dimensions"],
		"metrics":      params["metrics"],
	}

	body, _ := json.Marshal(reportSpec)
	req, _ := http.NewRequest("POST",
		c.baseURL+"/reports",
		bytes.NewReader(body),
	)
	req.Header.Set("Authorization", "Bearer "+c.accessToken)
	req.Header.Set("Content-Type", "application/json")

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()

	var result ReportResponse
	json.NewDecoder(resp.Body).Decode(&result)
	return result.ReportId, nil
}

// DownloadReport 下载报告
func (c *AmazonClient) DownloadReport(reportId string) ([]byte, error) {
	if !c.hasToken() {
		return nil, fmt.Errorf("not authenticated")
	}

	req, _ := http.NewRequest("GET",
		c.baseURL+"/reports/"+reportId+"/download",
		nil,
	)
	req.Header.Set("Authorization", "Bearer "+c.accessToken)

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	return io.ReadAll(resp.Body)
}

// ==================== 使用示例 ====================

func main() {
	client := NewAmazonClient("your_key", "your_secret")

	// 认证
	// client.Authenticate()

	// 创建广告系列
	// camp := &Campaign{
	// 	CampaignName: "Summer Sale",
	// 	CampaignType: "sponsoredProducts",
	// 	BudgetAmount: 100.0,
	// 	BudgetPeriod: "DAILY",
	// }
	// created, _ := client.CreateCampaign(camp)
	// fmt.Printf("Created campaign: %s\n", created.CampaignId)

	// 更新出价
	// client.UpdateBid("ag_123", 1.50)
}
