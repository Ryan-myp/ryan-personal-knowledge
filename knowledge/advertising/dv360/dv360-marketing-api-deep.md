# DV360 API 官方文档精读与实战

## 一、DV360 官方架构

### 1.1 官方定义与定位

**Google 官方定义：**
> Display & Video 360 (DV360) 是企业级程序化广告平台，支持跨媒体、跨渠道的广告投放和管理。

**核心价值：**
- 跨媒体投放：展示、视频、音频、电视、零售媒体
- 多 DSP 接入：通过 Exchange 连接多个广告交换平台
- 实时竞价：基于 RTB 的程序化购买
- 数据驱动：结合 Google Ads Data Hub 实现跨平台归因
- 企业级管理：支持多层级账户结构和批量操作

### 1.2 账户层级结构

**官方层级：**

```
360 Connector (360 连接器)
├── Advertisers (广告主)
│   ├── Insertion Orders (IO，订单项)
│   │   ├── Line Items (线条项目)
│   │   │   ├── Creatives (创意)
│   │   │   ├── Targeting (定向)
│   │   │   └── Schedule (排期)
│   │   └── Budget (预算)
│   ├── Partners (合作伙伴)
│   └── Users (用户)
├── Campaigns (广告系列)
├── Reports (报告)
└── Tools (工具)
```

### 1.3 交易类型

**官方交易类型：**

| 类型 | 说明 | 适用场景 |
|------|------|----------|
| Programmatic Guaranteed (PG) | 程序化保量采购 | 品牌大额投放 |
| Private Market Place (PMP) | 私有市场交易 | 优质库存采购 |
| Preferred Deal (PD) | 优先交易 | 优先购买权 |
| Open Auction | 公开竞价 | 常规投放 |

### 1.4 创意格式

**官方创意格式：**

| 格式 | 尺寸 | 说明 |
|------|------|------|
| 横幅广告 | 728x90, 300x250 | 标准尺寸 |
| 矩形广告 | 336x280, 300x600 | 大尺寸 |
| 原生广告 | 自适应 | 与内容融合 |
| HTML5 广告 | 自适应 | 富媒体交互 |
| 视频广告 | 多种比例 | 前贴片、中贴片、后贴片 |

## 二、核心 API 端点实战

### 2.1 认证与授权

**OAuth2 Service Account 流程：**

```
1. 创建 Google Cloud 项目
2. 启用 DV360 API
3. 创建 Service Account
4. 下载 JSON 密钥文件
5. 在 DV360 中授权 Service Account
6. 使用 JWT 签名获取 access_token
7. 调用 API
```

### 2.2 广告主管理

**获取广告主列表：**

```
GET /displayvideo/v2/advertisers
```

**创建广告主：**

```
POST /displayvideo/v2/advertisers
{
  "displayName": "My Advertiser"
}
```

### 2.3 订单项 (IO) 管理

**创建 IO：**

```
POST /displayvideo/v2/advertisers/{advertiser_id}/insertionOrders
{
  "displayName": "My IO",
  "flightEndDateMillis": 1735689600000,
  "flightStartDateMillis": 1704153600000,
  "lineItemCount": 5,
  "targetedGeoIds": ["2840"],
  "type": "PROGRAMMATIC_GUARANTEED"
}
```

### 2.4 线条项目 (Line Item) 管理

**创建 Line Item：**

```
POST /displayvideo/v2/advertisers/{advertiser_id}/insertionOrders/{insertion_order_id}/lineItems
{
  "displayName": "My Line Item",
  "advertiserId": "{advertiser_id}",
  "insertionOrderId": "{insertion_order_id}",
  "targetingType": "TARGETING_TYPE_UNSPECIFIED",
  "flightStartDateMillis": 1704153600000,
  "flightEndDateMillis": 1735689600000,
  "budgetId": "{budget_id}",
  "creativeRotation": {
    "type": "EQUAL_FRQUENCY"
  }
}
```

### 2.5 创意管理

**上传创意：**

```
POST /displayvideo/v2/advertisers/{advertiser_id}/lineItems/{line_item_id}/creatives
{
  "displayName": "My Creative",
  "type": "DISPLAY_VIDEO_AD"
}
```

## 三、定向策略

### 3.1 上下文定向

**关键词定向：**

```
POST /displayvideo/v2/advertisers/{advertiser_id}/lineItems/{line_item_id}/targetings
{
  "keywordTargetingDetails": [{
    "keyword": "running shoes"
  }]
}
```

**分类定向：**

```
POST /displayvideo/v2/advertisers/{advertiser_id}/lineItems/{line_item_id}/targetings
{
  "inMarketAudienceTargetingDetail": {
    "segmentId": "{segment_id}"
  }
}
```

### 3.2 受众定向

**第一方受众：**

```
POST /displayvideo/v2/advertisers/{advertiser_id}/lineItems/{line_item_id}/targetings
{
  "customAudienceTargetingDetail": {
    "customAudienceId": "{custom_audience_id}"
  }
}
```

**In-Market Audiences：**

| 类别 | 说明 | 示例 |
|------|------|------|
| 汽车购买者 | 正在购车的人 | 汽车买家 |
| 酒店预订者 | 正在预订酒店的人 | 旅行者 |
| 在线购物者 | 经常网购的人 | 电商用户 |
| 金融服务者 | 寻求金融服务的人 | 贷款申请者 |

**Life Events：**

| 事件 | 说明 | 适用产品 |
|------|------|----------|
| 新婚 | 最近结婚的人 | 家居、蜜月旅行 |
| 搬家 | 最近搬家的人 | 家具、装修 |
| 新工作 | 刚找到工作的人 | 职业装、理财 |
| 新生儿 | 最近有宝宝的人 | 母婴用品 |

## 四、测量与归因

### 4.1 转化追踪

**设置转化目标：**

```
POST /displayvideo/v2/advertisers/{advertiser_id}/lineItems/{line_item_id}/conversions
{
  "displayName": "Purchase Conversion",
  "type": "TYPE_UNSPECIFIED",
  "countingType": "ONE_PER_EVENT"
}
```

### 4.2 第三方测量

**集成第三方测量工具：**

| 工具 | 功能 | 集成方式 |
|------|------|----------|
| Moat | 品牌安全和可见性 | API 集成 |
| DoubleVerify | 品牌安全和可见性 | 标签集成 |
| Integral Ad Science | 广告质量 | API 集成 |
| comScore | 受众测量 | SDK 集成 |

### 4.3 归因模型

**官方归因模型：**

| 模型 | 说明 | 适用场景 |
|------|------|----------|
| Last Click | 最后一次点击 | 简单转化 |
| First Click | 首次点击 | 新客获取 |
| Linear | 均匀分配 | 全链路分析 |
| Time Decay | 时间衰减 | 短期转化 |
| Position Based | 首尾加权 | 品牌 + 转化 |
| Data-Driven | 数据驱动 | 优化投放 |

## 五、自测题

1. DV360 的核心功能是什么？
2. 四种交易类型各有什么特点？
3. 如何配置第三方测量工具？
4. 归因模型有哪些？各自适用什么场景？

## 六、动手验证

```bash
# 1. 配置 OAuth2 认证
# - 创建 Service Account
# - 下载密钥文件
# - 授权 DV360 API

# 2. 创建广告主
# - 设置广告主名称
# - 配置时区和货币

# 3. 创建 IO 和 Line Item
# - 设置预算
# - 设置排期
# - 选择交易类型

# 4. 上传创意
# - 准备创意素材
# - 上传到 DV360
# - 关联到 Line Item

# 5. 设置定向
# - 选择定向方式
# - 配置受众
# - 设置频率控制

# 6. 监控和优化
# - 查看报告
# - 分析表现
# - 调整策略
```

---

## 第七部分：Go 生产级实现

### DV360 Marketing API Client — Go 源码

```go
package main

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"
)

// DV360Client is a production-grade client for DV360 Marketing API.
type DV360Client struct {
	baseURL    string
	client     *http.Client
	authToken  string
	tokenExpiry time.Time
	retryCount int
}

// NewDV360Client creates a new DV360 API client.
func NewDV360Client(clientID, clientSecret string) *DV360Client {
	return &DV360Client{
		baseURL: "https://api.dev.verve.com",
		client: &http.Client{
			Timeout: 30 * time.Second,
		},
		authToken:  "",
		tokenExpiry: time.Time{},
		retryCount: 3,
	}
}

// GetAuthToken retrieves and caches the OAuth2 token.
func (c *DV360Client) GetAuthToken() (string, error) {
	if c.authToken != "" && time.Now().Before(c.tokenExpiry.Add(-5*time.Minute)) {
		return c.authToken, nil
	}

	resp, err := c.client.PostForm(c.baseURL+"/oauth/token", map[string][]string{
		"grant_type":    {"client_credentials"},
		"client_id":     {os.Getenv("DV360_CLIENT_ID")},
		"client_secret": {os.Getenv("DV360_CLIENT_SECRET")},
	})
	if err != nil {
		return "", fmt.Errorf("token request failed: %w", err)
	}
	defer resp.Body.Close()

	var tokenResp struct {
		AccessToken  string `json:"access_token"`
		ExpiresIn    int    `json:"expires_in"`
		TokenType    string `json:"token_type"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&tokenResp); err != nil {
		return "", fmt.Errorf("decode token response: %w", err)
	}

	c.authToken = tokenResp.AccessToken
	c.tokenExpiry = time.Now().Add(time.Duration(tokenResp.ExpiresIn) * time.Second)
	return c.authToken, nil
}

// Campaign represents a DV360 campaign.
type Campaign struct {
	ID          string    `json:"id"`
	Name        string    `json:"name"`
	Status      string    `json:"status"`
	Budget      float64   `json:"budget"`
	CreatedAt   time.Time `json:"created_at"`
	UpdatedAt   time.Time `json:"updated_at"`
}

// ListCampaigns fetches campaigns with pagination support.
func (c *DV360Client) ListCampaigns(pageSize int, pageToken string) ([]Campaign, string, error) {
	url := fmt.Sprintf("%s/v1/campaigns?pageSize=%d", c.baseURL, pageSize)
	if pageToken != "" {
		url += "&pageToken=" + pageToken
	}

	var campaigns []Campaign
	var nextPageToken string

	for attempts := 0; attempts <= c.retryCount; attempts++ {
		token, err := c.GetAuthToken()
		if err != nil {
			return nil, "", err
		}

		req, err := http.NewRequest("GET", url, nil)
		if err != nil {
			return nil, "", err
		}
		req.Header.Set("Authorization", "Bearer "+token)

		resp, err := c.client.Do(req)
		if err != nil {
			if attempts < c.retryCount {
				time.Sleep(time.Duration(attempts+1) * time.Second)
				continue
			}
			return nil, "", err
		}

		var result struct {
			Campaigns     []Campaign `json:"campaigns"`
			NextPageToken string     `json:"next_page_token"`
		}
		if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
			return nil, "", err
		}
		resp.Body.Close()

		campaigns = append(campaigns, result.Campaigns...)
		nextPageToken = result.NextPageToken
		break
	}

	return campaigns, nextPageToken, nil
}

// CreateCampaign creates a new campaign in DV360.
func (c *DV360Client) CreateCampaign(name, status string, budget float64) (*Campaign, error) {
	token, err := c.GetAuthToken()
	if err != nil {
		return nil, err
	}

	payload := map[string]interface{}{
		"name":    name,
		"status":  status,
		"budget":  budget,
	}
	body, _ := json.Marshal(payload)

	req, err := http.NewRequest("POST", c.baseURL+"/v1/campaigns", strings.NewReader(string(body)))
	if err != nil {
		return nil, err
	}
	req.Header.Set("Authorization", "Bearer "+token)
	req.Header.Set("Content-Type", "application/json")

	resp, err := c.client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	var campaign Campaign
	if err := json.NewDecoder(resp.Body).Decode(&campaign); err != nil {
		return nil, err
	}
	return &campaign, nil
}
```

---

## 第八部分：自测题

### 问题 1：DV360 API 客户端中，为什么 token 缓存设置了 5 分钟的提前过期时间（`tokenExpiry.Add(-5*time.Minute)`）？

<details>
<summary>查看答案</summary>

OAuth2 token 的有效期由 `expires_in` 字段决定。提前 5 分钟过期的原因是：
1. **时钟漂移**：客户端和服务器时间可能有几秒到几分钟的差异
2. **网络延迟**：API 请求处理时间可能接近 token 过期边界
3. **并发安全**：多个 goroutine 同时检查 token 时，避免竞态条件导致重复刷新

如果不设置提前过期，在 token 即将过期的瞬间发起的请求可能返回 401 Unauthorized。

</details>

### 问题 2：ListCampaigns 中的重试逻辑为什么用指数退避（`time.Duration(attempts+1) * time.Second`）？

<details>
<summary>查看答案</summary>

指数退避的核心原因：
1. **避免雪崩**：API 故障时大量请求同时重试会加剧服务器压力
2. **给恢复留时间**：第一次失败后等 1 秒，第二次等 2 秒，第三次等 3 秒
3. **幂等性保证**：GET 请求是幂等的，重试不会造成副作用

如果 API 返回 HTTP 429（Too Many Requests），应该优先检查 Retry-After 头而非盲目重试。

</details>

### 问题 3：CreateCampaign 中使用 `map[string]interface{}` 作为 payload 而不是结构体，有什么优缺点？

<details>
<summary>查看答案</summary>

优点：
1. **灵活性**：可以动态添加可选字段（如 targeting、schedule）
2. **快速原型**：API 字段变化时无需修改结构体定义

缺点：
1. **类型不安全**：编译期无法检查字段名拼写错误
2. **缺少文档**：IDE 无法提供自动补全
3. **序列化开销**：需要额外处理零值字段

生产环境建议使用结构体 + JSON tag，可选字段用指针类型：

```go
type CreateCampaignRequest struct {
	Name     string   `json:"name"`
	Status   string   `json:"status"`
	Budget   *float64 `json:"budget,omitempty"` // 可选字段
}
```

</details>
