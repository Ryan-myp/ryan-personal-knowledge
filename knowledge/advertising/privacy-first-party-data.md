# 隐私计算与第一方数据深度 — Cookie 时代的广告技术转型

> 标签: `#隐私计算` `#第一方数据` `#GDPR` `#CCPA` `#Cookie替代` `#身份解析` `#源码级`
> 创建日期: 2026-06-10 | 作者: Ryan
> 定位: 资深专家级 — 隐私法规、第一方数据策略、隐私计算技术、广告适配

---

## 第一部分：入门引导（5 分钟速览）

### 1.1 广告追踪的技术演进

```
┌─────────────────────────────────────────────────────────────┐
│              广告追踪技术三代演进                              │
│                                                             │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  第一代: 第三方 Cookie (2000-2022)                      │ │
│  │                                                        │ │
│  │  • 跨域追踪: Site A → 第三方 Tracker → Site B          │ │
│  │  • 用户画像: 基于跨站行为构建                           │ │
│  │  • 广告归因: 跨站点击归因                               │ │
│  │  • 优势: 数据丰富, 覆盖面广                             │ │
│  │  • 问题: 隐私泄露, 用户不知情                            │ │
│  │                                                        │ │
│  │  架构:                                                   │ │
│  │  User → Site A → Third-Party Pixel → 第三方服务器       │ │
│  │                      ↑ Cookie 存储用户 ID                │ │
│  │                  跨站追踪用户行为                         │ │
│  └────────────────────────────────────────────────────────┘ │
│                           ↓ 衰减                            │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  第二代: 第一方数据 + Server-Side (2020-至今)           │ │
│  │                                                        │ │
│  │  • 服务端采集: CAPI/GTM Server-Side                    │ │
│  │  • 用户授权: 基于同意的数据收集                          │ │
│  │  • 身份解析: Hash Email/Phone + Lookalike               │ │
│  │  • 优势: 合规, 数据质量高                               │ │
│  │  • 问题: 覆盖范围受限, 需要用户授权                      │ │
│  │                                                        │ │
│  │  架构:                                                   │ │
│  │  User → Site → Server-Side GTM → Meta CAPI/Google       │ │
│  │                      ↑ 服务端直接上报                     │ │
│  │                  不依赖浏览器 Cookie                      │ │
│  └────────────────────────────────────────────────────────┘ │
│                           ↓ 演进                            │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  第三代: 隐私沙箱 + 身份图谱 (未来)                      │ │
│  │                                                        │ │
│  │  • Google Privacy Sandbox: Topics, FLEDGE, Attestation  │ │
│  │  • Apple Private Click Measurement                      │ │
│  │  • 联邦学习 + 差分隐私                                  │ │
│  │  • 身份图谱: 基于同意的跨设备身份                        │ │
│  │  • 优势: 隐私保护 + 广告效果平衡                         │ │
│  │  • 问题: 标准化未完成, 生态未成熟                        │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 核心法规速查

| 法规 | 适用范围 | 核心要求 | 罚款上限 |
|------|----------|----------|----------|
| **GDPR** (EU) | 欧盟公民数据 | 明示同意 + 数据最小化 + 可撤回 | 2000万€ 或 4% 全球营收 |
| **CCPA/CPRA** (California) | 加州居民 | 选择退出权 + 数据访问权 | $7500/故意违规 |
| **PIPL** (中国) | 中国公民数据 | 单独同意 + 数据本地化 | 5000万¥ 或 5% 营收 |
| **LGPD** (Brazil) | 巴西公民数据 | 类似 GDPR | 2% 营收 (上限 5000万BRL) |
| **TCPA** (US) | 电话/短信 | 事前同意 (Opt-in) | $500-$1500/次违规 |

---

## 第二部分：第一方数据策略 — 源码级

### 2.1 第一方数据收集架构

```go
// first_party_data.go — 第一方数据收集与处理
package privacy

import (
	"context"
	"crypto/sha256"
	"encoding/json"
	"fmt"
	"strings"
	"sync"
	"time"
)

// UserConsent 用户同意状态
type UserConsent struct {
	ConsentGiven bool   `json:"consent_given"`        // 用户是否同意
	ConsentTime  string `json:"consent_time"`         // 同意时间 (RFC3339)
	PurposeIDs   []int  `json:"purpose_ids"`          // 同意的目的 ID
	VendorIDs    []int  `json:"vendor_ids"`           // 同意的供应商 ID
	StringConsent string `json:"string_consent"`      // IAB TCF 同意字符串
}

// 检查用户是否同意
func (c *UserConsent) IsConsented(purpose int) bool {
	if !c.ConsentGiven {
		return false
	}
	for _, pid := range c.PurposeIDs {
		if pid == purpose {
			return true
		}
	}
	return false
}

// IdentityToken 身份令牌 (第一方)
type IdentityToken struct {
	UserID       string    `json:"user_id"`       // 系统内部用户 ID
	Token        string    `json:"token"`         // 第一方身份令牌
	CreatedAt    time.Time `json:"created_at"`
	ExpiresAt    time.Time `json:"expires_at"`
	Consent      UserConsent `json:"consent"`
}

// FirstPartyData 第一方数据结构
type FirstPartyData struct {
	Identity  IdentityToken `json:"identity"`   // 身份信息
	Behavior  []Event       `json:"behavior"`   // 用户行为事件
	Profile   UserProfile   `json:"profile"`    // 用户画像 (基于同意)
	Transaction []Transaction `json:"transaction"` // 交易记录
}

// UserProfile 用户画像 (基于第一方数据)
type UserProfile struct {
	UserID       string    `json:"user_id"`
	RegistrationDate time.Time `json:"registration_date"`
	PurchaseCount int      `json:"purchase_count"`
	LifetimeValue   float64  `json:"lifetime_value"`
	PreferredCategory []string `json:"preferred_category"` // 偏好品类
	AvgOrderValue   float64  `json:"avg_order_value"`
	LastPurchaseDate time.Time `json:"last_purchase_date"`
	Country         string   `json:"country"`
	DeviceType      string   `json:"device_type"`
	// 注意: 不包含 email/phone 等 PII, 除非用户明确授权
}

// Transaction 交易记录
type Transaction struct {
	TransactionID string    `json:"transaction_id"`
	UserID        string    `json:"user_id"`
	Amount        float64   `json:"amount"`
	Currency      string    `json:"currency"`
	Timestamp     time.Time `json:"timestamp"`
	Items         []Item    `json:"items"`
	// 注意: 不包含 payment info, 只存交易摘要
}

// Item 交易商品
type Item struct {
	ItemID     string  `json:"item_id"`
	Name       string  `json:"name"`
	Category   string  `json:"category"`
	Price      float64 `json:"price"`
	Quantity   int     `json:"quantity"`
}
```

### 2.2 第一方数据 → 广告平台对接

```go
// ad_platform.go — 第一方数据对接广告平台
package privacy

import (
	"crypto/sha256"
	"fmt"
)

// HashPII 哈希 PII 数据 (用于广告平台匹配)
func HashPII(value string) string {
	// 数据清洗
	value = strings.TrimSpace(strings.ToLower(value))
	// SHA-256
	hash := sha256.Sum256([]byte(value))
	return fmt.Sprintf("%x", hash)
}

// 第一方数据 → Meta CAPI 转换
func ToMetaCAPIEvent(data *FirstPartyData, eventName string) map[string]interface{} {
	// 只发送用户已同意的数据
	event := map[string]interface{}{
		"event_name": eventName,
		"event_id":   data.Identity.UserID + "_" + eventName + "_" + data.Identity.CreatedAt.Format("20060102"),
		"event_time": data.Identity.CreatedAt.Unix(),
		"user_data": map[string]interface{}{
			// 只发送 Hash 后的 email/phone
			"em": []string{HashPII(data.Profile.UserID)}, // 内部 ID Hash
			// 注意: email/phone 需要额外存储和 Hash
		},
		"custom_data": map[string]interface{}{
			"value":         0,
			"currency":      "USD",
			"num_items":     len(data.Transaction),
			"contents":      toMetaContent(data.Transaction),
		},
	}
	
	// 添加用户画像特征 (不直接传输 PII)
	if len(data.Profile.PreferredCategory) > 0 {
		event["custom_data"].(map[string]interface{})["preferred_categories"] = data.Profile.PreferredCategory
	}
	
	return event
}

// 第一方数据 → Google Ads (Offline Conversions)
func ToGoogleOfflineConversion(data *FirstPartyData, conversionName string) map[string]interface{} {
	// Google Offline Conversions API
	// 需要 Hash 的用户数据
	return map[string]interface{}{
		"conversionAction": fmt.Sprintf("customers/%s/conversionActions/%s", 
			data.Identity.UserID, conversionName),
		"click": map[string]interface{}{
			"clickDateTime": data.Identity.CreatedAt.Format(time.RFC3339),
		},
		"userIdentifiers": []map[string]interface{}{
			{
				"hashedEmailAddress": []string{HashPII(data.Profile.UserID)},
			},
		},
		"conversionValue": data.Transaction[0].Amount,
		"currencyCode":    data.Transaction[0].Currency,
		"conversionDateTime": data.Transaction[0].Timestamp.Format(time.RFC3339),
	}
}

// 第一方数据 → Google DV360 (SDF - Supply-Domain Feed)
// SDF 是 Google 的广告数据回流格式
func ToGoogleSDF(data *FirstPartyData) string {
	// SDF 格式 (CSV)
	// Header: order_id,line_item_id,creative_id,impression_type,ad_unit_id,site_domain,geo_country,geo_region,geo_city,geo_dma,advertiser_id,campaign_id,insertion_order_id,deal_id,impression_id,impression_start_time,impression_end_time,impression_type,advertiser_name,advertiser_id,line_item_id,order_id,campaign_id,creative_id,creative_size,placement_id,placement_name
	// ...
	
	// 简化实现 (实际需完整 SDF 格式)
	type SDFRow struct {
		OrderID       string `json:"order_id"`
		LineItemID    string `json:"line_item_id"`
		ImpressionID  string `json:"impression_id"`
		Timestamp     string `json:"timestamp"`
		UserHash      string `json:"user_hash"` // Hash 的用户标识
		Country       string `json:"geo_country"`
		DeviceType    string `json:"device_type"`
	}
	
	return fmt.Sprintf("%v", SDFRow{
		OrderID:      data.Identity.UserID,
		ImpressionID: data.Identity.UserID + "_impression",
		Timestamp:    data.Identity.CreatedAt.Format(time.RFC3339),
		UserHash:     HashPII(data.Profile.UserID),
		Country:      data.Profile.Country,
		DeviceType:   data.Profile.DeviceType,
	})
}
```

### 2.3 隐私合规 — 同意管理

```go
// consent.go — 同意管理 (GDPR/CCPA 合规)
package privacy

import (
	"context"
	"encoding/base64"
	"strings"
)

// IABTCFConsentString IAB TCF v2.0 同意字符串解析
// TCF (Transparency and Consent Framework) 是 IAB 的同意框架标准
// 字符串格式: 1~1~...~(Purpose 1 consent: 1=Yes, 0=No)~(Vendor 1 consent: 1=Yes, 0=No)~...
type IABTCFConsentString struct {
	Version            int               // TCF 版本 (2)
	PurposeConsents    map[int]bool      // Purpose ID → Consent (1=Yes, 0=No)
	VendorConsents     map[int]bool      // Vendor ID → Consent
	SpecialFeaturesOpt map[int]bool      // 特殊功能 (Opt-in)
	VendorLegitimateInterests map[int]bool // Vendor 合法利益
	Timestamp          int64             // 同意时间 (Unix 毫秒)
}

// ParseConsentString 解析 TCF 同意字符串
func ParseConsentString(tcfString string) (*IABTCFConsentString, error) {
	parts := strings.Split(tcfString, "~")
	if len(parts) < 2 || parts[0] != "1" {
		return nil, fmt.Errorf("invalid TCF string")
	}
	
	result := &IABTCFConsentString{
		Version: 1,
		PurposeConsents:    make(map[int]bool),
		VendorConsents:     make(map[int]bool),
		SpecialFeaturesOpt: make(map[int]bool),
		VendorLegitimateInterests: make(map[int]bool),
	}
	
	// 解析 Purpose 同意 (bits 1-15)
	for i := 0; i < 15; i++ {
		if i < len(parts) {
			result.PurposeConsents[i] = parts[i] == "1"
		}
	}
	
	// 解析 Vendor 同意
	for i := 0; i < len(parts)-1; i++ {
		result.VendorConsents[i] = parts[len(parts)-2-i] == "1"
	}
	
	// 解析 Timestamp
	if len(parts) > 1 {
		result.Timestamp = int64(parts[1])
	}
	
	return result, nil
}

// 关键 Purpose ID (GDPR):
// Purpose 1: 存储/访问设备信息 (Cookie/Device Fingerprint) — 必需用户同意
// Purpose 2: 选择/匹配广告 — 必需用户同意
// Purpose 3: 测量广告效果 — 必需用户同意
// Purpose 4: 选择/匹配个性化广告 — 必需用户同意
// Purpose 5: 测量个性化广告效果 — 必需用户同意
// Purpose 6: 提供个性化广告 — 必需用户同意
// Purpose 7: 选择/匹配非个性化广告 — 合法利益 (无需同意)
// Purpose 8: 测量非个性化广告效果 — 合法利益 (无需同意)
// Purpose 9: 提供非个性化广告 — 合法利益 (无需同意)
// Purpose 10: 公共利益/合法研究 — 合法利益 (无需同意)

// 关键 Vendor ID:
// 每个广告技术供应商 (Pixel, CAPI, DSP, SSP) 都有 Vendor ID
// 用户可以选择同意哪些 Vendor

// CCPA "Do Not Sell" 实现
type CCPADisableSell struct {
	OptOut bool `json:"opt_out"`
}

// 设置 "Do Not Sell" Cookie
func SetDoNotSellCookie(w http.ResponseWriter, doNotSell bool) {
	cookie := &http.Cookie{
		Name:     "_ddns",          // Do Not Sell (CCPA)
		Value:    fmt.Sprintf("%v", doNotSell),
		Path:     "/",
		HttpOnly: false,           // Cookie 需要可读 (浏览器检查)
		SameSite: http.SameSiteNone,
		Secure:   true,            // 仅 HTTPS
	}
	http.SetCookie(w, cookie)
}

// 读取 "Do Not Sell" 信号
func GetDoNotSellFromBrowser() bool {
	// 检查 _ddns Cookie
	// 检查 DNT (Do Not Track) Header
	// 检查 Privacy Preferences Protocol (P3P)
	// ...
	return false
}

// GDPR 用户权利实现
type UserRightsHandler struct {
	db *Database
}

// 用户数据导出 (Right of Access)
func (h *UserRightsHandler) ExportUserData(userID string) ([]byte, error) {
	// 获取用户所有数据 (按 GDPR Art. 15)
	data, err := h.db.GetUserAllData(userID)
	if err != nil {
		return nil, err
	}
	
	// 生成可读格式 (JSON)
	export, err := json.MarshalIndent(data, "", "  ")
	if err != nil {
		return nil, err
	}
	
	return export, nil
}

// 用户数据删除 (Right to be Forgotten)
func (h *UserRightsHandler) DeleteUserData(userID string) error {
	// 删除所有个人数据 (按 GDPR Art. 17)
	err := h.db.DeleteUserData(userID)
	if err != nil {
		return err
	}
	
	// 清除相关 Cookie/LocalStorage
	// 清除广告 ID (如 GA Client ID)
	
	return nil
}

// 数据更正 (Right to Rectification)
func (h *UserRightsHandler) UpdateUserData(userID string, updates map[string]interface{}) error {
	return h.db.UpdateUserData(userID, updates)
}

// 数据处理限制 (Right to Restrict Processing)
func (h *UserRightsHandler) RestrictProcessing(userID string, restricted bool) error {
	// 标记用户数据为 "restricted"
	// 暂停广告优化, 但保留数据
	return h.db.SetRestriction(userID, restricted)
}
```

---

## 第三部分：身份解析 — 第一方数据 vs 第三方身份

### 3.1 身份图谱架构

```
┌──────────────────────────────────────────────────────────────┐
│                   身份图谱 (Identity Graph)                    │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  身份匹配层 (Identity Resolution)                        │  │
│  │                                                        │  │
│  │  输入:                                                   │  │
│  │  • Hash Email (SHA-256)                                │  │
│  │  • Hash Phone (E.164 格式)                              │  │
│  │  • Cookie ID (第三方)                                  │  │
│  │  • Device ID (IDFA/AAID)                               │  │
│  │  • IP + User Agent (弱匹配)                             │  │
│  │                                                        │  │
│  │  匹配算法:                                              │  │
│  │  • Email/Phone: 强匹配 (精确)                           │  │
│  │  • Cookie: 中匹配 (同浏览器)                            │  │
│  │  • Device: 中匹配 (同设备)                              │  │
│  │  • IP+UA: 弱匹配 (概率)                                │  │
│  │                                                        │  │
│  │  输出:                                                   │  │
│  │  • Unified User ID (匿名, 不可逆)                       │  │
│  │  • Match Score (匹配置信度)                             │  │
│  │  • Identity Source (身份来源: First/Third Party)        │  │
│  └────────────────────────────────────────────────────────┘  │
│                           │                                  │
│                   ┌───────▼───────┐                          │
│                   │  Identity Map  │                         │
│                   │  (ID → Profiles)│                        │
│                   └───────┬───────┘                          │
│                           │                                  │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  应用层 (Applications)                                  │  │
│  │  • 广告定向 (Targeting)                                │  │
│  │  • 受众构建 (Audience Building)                         │  │
│  │  • 频次控制 (Frequency Capping)                         │  │
│  │  • 跨渠道归因 (Cross-Channel Attribution)               │  │
│  │  • 个性化推荐 (Personalization)                         │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘

// Go 身份图谱示例
type IdentityMap struct {
	// 存储: Hash → 匿名 ID
	// 不存储明文 PII (数据最小化原则)
	emailToID    map[string]string  // Hash(email) → AnonymousUserID
	phoneToID    map[string]string  // Hash(phone) → AnonymousUserID
	cookieToID   map[string]string  // CookieID → AnonymousUserID
	deviceToID   map[string]string  // DeviceID → AnonymousUserID
	
	// 匿名 ID → 画像
	idToProfile  map[string]*UserProfile
}

func (im *IdentityMap) Resolve(email string) *UserProfile {
	hashedEmail := HashPII(email)
	
	// 查已有匹配
	if uid, exists := im.emailToID[hashedEmail]; exists {
		return im.idToProfile[uid]
	}
	
	// 新身份 → 生成匿名 ID
	anonymousID := generateAnonymousID()
	im.emailToID[hashedEmail] = anonymousID
	im.idToProfile[anonymousID] = &UserProfile{UserID: anonymousID}
	
	return im.idToProfile[anonymousID]
}
```

### 3.2 第一方数据策略

```
┌──────────────────────────────────────────────────────────────┐
│                   第一方数据收集策略                           │
│                                                              │
│  强信号 (High-Value First-Party Data):                       │
│  ───────────────────────────────────                         │
│  1. 注册/登录邮箱                                             │
│     → Hash → 用于 CAPI/Google Ads 用户匹配                   │
│     → 匹配分数: > 0.8                                       │
│                                                              │
│  2. 手机号 (结账/订阅)                                        │
│     → Hash → 用于 CAPI/Google Ads 用户匹配                   │
│     → 匹配分数: > 0.7                                       │
│                                                              │
│  3. 购买记录 (交易数据)                                       │
│     → Order ID + Items + Amount                             │
│     → 用于 Lookalike Audience / 转化优化                     │
│                                                              │
│  4. 浏览行为 (站内)                                           │
│     → Page Views, Product Views, Cart Additions              │
│     → 用于再营销/频次控制                                     │
│                                                              │
│  5. 搜索记录 (站内)                                           │
│     → Search Queries, Filters Applied                       │
│     → 用于兴趣定向/推荐                                       │
│                                                              │
│  弱信号 (Low-Value First-Party Data):                        │
│  ───────────────────────────────────                         │
│  1. IP 地址 (需 Hash)                                        │
│     → 弱匹配, 匹配分数: ~0.3                                  │
│                                                              │
│  2. User Agent (浏览器/设备)                                  │
│     → 弱匹配, 用于设备定向                                     │
│                                                              │
│  3. 页面 Referrer                                             │
│     → 来源分析, 不可用于用户匹配                               │
│                                                              │
│  第一方数据 vs 第三方数据:                                   │
│  ──────────────────────────                                  │
│  | 维度         | 第一方数据               | 第三方数据             |
│  |--------------|------------------------|----------------------|
│  | 数据质量     | 高 (直接获取)          | 低 (推断)            |
│  | 合规性       | 高 (可控制)            | 低 (法规风险)         |
│  | 覆盖范围     | 有限 (仅自有站)        | 广 (跨站追踪)         |
│  | 长期可持续性 | 高 (不受 Cookie 限制)  | 低 (Cookie 衰减)      |
│  | 建议策略     | 核心数据源              | 逐步淘汰              |
└──────────────────────────────────────────────────────────────┘
```

---

## 第四部分：隐私计算技术

### 4.1 差分隐私 (Differential Privacy)

```
差分隐私 — 在统计中加入噪声, 保护个体数据:

┌──────────────────────────────────────────────────────────────┐
│                                                              │
│  核心思想:                                                   │
│  ───────────                                                   │
│  "统计结果不依赖于任何单个用户的数据"                           │
│                                                              │
│  ε (Epsilon) 隐私预算:                                       │
│  ─────────────────────                                       │
│  • ε 越小 → 噪声越大 → 隐私保护越强 → 数据质量越低            │
│  • ε 越大 → 噪声越小 → 隐私保护越弱 → 数据质量越高            │
│  • 典型值: ε = 0.1 (强隐私) / ε = 1.0 (平衡) / ε = 10 (弱)   │
│                                                              │
│  Laplace 机制:                                               │
│  ──────────────────                                            │
│  真实值 + Noise(Laplace(Δf/ε))                                │
│  其中: Δf = 查询敏感度 (最大变化量)                            │
│         ε = 隐私参数                                          │
│                                                              │
│  广告场景应用:                                               │
│  • 用户数量统计 (不去重):                                    │
│    真实访问数 + Laplace 噪声                                  │
│  • 转化率统计:                                              │
│    转化率 + 噪声                                              │
│  • 受众规模估算:                                            │
│    受众人数 + 噪声                                            │
│                                                              │
│  Go 实现:                                                    │
│  ────────────                                                │
│  func ApplyLaplaceNoise(value float64, epsilon float64) float64 {
│      sensitivity := 1.0  // 查询敏感度
│      scale := sensitivity / epsilon
│      noise := laplace.Rand(scale)  // 从 Laplace 分布采样
│      return value + noise
│  }
└──────────────────────────────────────────────────────────────┘
```

### 4.2 联邦学习 (Federated Learning)

```
联邦学习 — 数据不出域, 只共享模型参数:

┌──────────────────────────────────────────────────────────────┐
│                                                              │
│  架构:                                                       │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐       │
│  │  用户 A      │    │  用户 B      │    │  用户 C      │       │
│  │  (本地)      │    │  (本地)      │    │  (本地)      │       │
│  │  本地训练模型 │    │  本地训练模型 │    │  本地训练模型 │       │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘       │
│         │                  │                  │                │
│         ▼                  ▼                  ▼                │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │  中央服务器 (仅聚合模型参数, 不接收原始数据)               │ │
│  │  Parameter_aggregated = Σ(Weight_i × Model_i) / Σ(Weight_i)│ │
│  └──────────────────────────────────────────────────────────┘ │
│         │                                                    │
│         ▼                                                    │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐       │
│  │  全局模型下发│←── │  全局模型下发│←── │  全局模型下发│       │
│  │  用户 A      │    │  用户 B      │    │  用户 C      │       │
│  └─────────────┘    └─────────────┘    └─────────────┘       │
│                                                              │
│  广告场景应用:                                               │
│  • 跨平台用户画像构建 (不共享用户数据)                        │
│  • 联邦学习 CTR 模型 (各平台本地训练, 共享梯度)               │
│  • 联合 Lookalike 建模                                       │
│                                                              │
│  优势:                                                       │
│  • 数据不出域 (合规)                                         │
│  • 保护用户隐私                                              │
│  • 利用多平台数据提升模型效果                                 │
│                                                              │
│  挑战:                                                       │
│  • 通信开销 (模型参数上传)                                   │
│  • 数据异构 (不同平台特征不一致)                              │
│  • 联邦学习聚合算法复杂                                      │
└──────────────────────────────────────────────────────────────┘
```

### 4.3 加密技术

```
隐私保护下的广告匹配:

1. 同态加密 (Homomorphic Encryption):
   • 密文上直接计算, 不解密
   • 用于: 加密的受众匹配
   • 性能: 较慢, 适合低频计算

2. 安全多方计算 (MPC):
   • 多方在不泄露数据的情况下计算联合结果
   • 用于: 跨平台用户交集计算
   • 性能: 中等

3. 零知识证明 (ZKP):
   • 证明某事为真, 而不泄露任何信息
   • 用于: 验证用户同意, 不泄露用户身份
   • 性能: 快速, 适合验证场景

4. 安全哈希 (Hash-based):
   • 数据 Hash 后匹配, 不暴露明文
   • 用于: CAPI 用户匹配
   • 性能: 最快, 实际部署最广泛
```

---

## 第五部分：GDPR 合规实施

### 5.1 同意管理技术栈

```
┌──────────────────────────────────────────────────────────────┐
│              同意管理 (CMP) 技术架构                           │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  用户界面 (CMP Banner)                                    │  │
│  │  • 首次访问时显示同意选择                                 │  │
│  │  • Cookie 类别: 必要/偏好/统计/营销                      │  │
│  │  • 供应商列表 (IAB TCF)                                  │  │
│  │  • "拒绝全部" 按钮 (GDPR 要求)                           │  │
│  └────────────────────┬───────────────────────────────────┘  │
│                       │                                      │
│  ┌────────────────────▼───────────────────────────────────┐  │
│  │  同意存储 (Consent Storage)                              │  │
│  │  • Cookie: IAB TCF 同意字符串                            │  │
│  │  • LocalStorage: 同意状态                               │  │
│  │  • Server: 用户同意记录 (GDPR Art. 7)                    │  │
│  └────────────────────┬───────────────────────────────────┘  │
│                       │                                      │
│  ┌────────────────────▼───────────────────────────────────┐  │
│  │  标签管理 (Tag Manager)                                   │  │
│  │  • GTM 集成: 检查同意状态                                │  │
│  │  • 按需加载: Pixel/CAPI/Analytics 脚本                   │  │
│  │  • 拒绝时: 不触发任何第三方标签                           │  │
│  └────────────────────┬───────────────────────────────────┘  │
│                       │                                      │
│  ┌────────────────────▼───────────────────────────────────┐  │
│  │  数据流控制                                              │  │
│  │  • 用户拒绝: 不收集/不发送任何数据                       │  │
│  │  • 用户同意: 正常收集/发送数据                           │  │
│  │  • 撤回同意: 立即停止收集/通知合作伙伴                    │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘

// Go 同意检查中间件
func ConsentMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// 1. 读取用户同意 Cookie
		cookie, err := r.Cookie("_tcfv2")
		consentString := ""
		if err == nil {
			consentString = cookie.Value
		}
		
		// 2. 解析同意字符串
		parsed, err := ParseConsentString(consentString)
		if err != nil {
			parsed = &IABTCFConsentString{PurposeConsents: map[int]bool{}}
		}
		
		// 3. 检查 Purpose 1 同意 (Cookie)
		if !parsed.IsConsented(1) {
			// 不加载跟踪脚本
			w.Header().Set("X-Consent-Denied", "true")
		}
		
		// 4. 检查 Purpose 2 同意 (广告选择)
		if !parsed.IsConsented(2) {
			// 不加载广告相关脚本
			w.Header().Set("X-Ad-Consent-Denied", "true")
		}
		
		// 5. 继续处理请求
		next.ServeHTTP(w, r)
	})
}
```

### 5.2 GDPR 核心要求 Checklist

```
GDPR 广告合规 Checklist:

数据最小化 (Data Minimization):
[ ] 只收集实现目的所需的最小数据
[ ] 不收集不必要的 PII (如 IP, User Agent 需 Hash)
[ ] 匿名化/假名化处理数据

合法基础 (Lawful Basis):
[ ] 明确说明数据处理的目的
[ ] 基于: 用户同意 (Consent) / 合同需要 / 合法利益
[ ] 营销: 必须用户同意 (Opt-in)
[ ] 分析: 合法利益或同意 (依数据类型)

用户权利 (User Rights):
[ ] 访问权 (Art. 15): 可导出用户所有数据
[ ] 删除权 (Art. 17): 可删除用户所有数据
[ ] 更正权 (Art. 16): 可更正错误数据
[ ] 限制处理权 (Art. 18): 可暂停数据处理
[ ] 数据可携带权 (Art. 20): 可导出机器可读格式
[ ] 反对权 (Art. 21): 可反对数据处理

数据保留 (Data Retention):
[ ] 明确数据保留期限
[ ] 到期自动删除/匿名化
[ ] Cookie 过期时间合理 (通常 ≤ 13 个月)

数据处理者协议 (DPA):
[ ] 与数据处理者 (Pixel/CAPI/Analytics) 签署 DPA
[ ] 明确数据处理范围和目的

跨境传输:
[ ] 数据传输到 EU 以外: 需 SCC (Standard Contractual Clauses)
[ ] 或: 数据保留在 EU

透明度:
[ ] 隐私政策清晰易懂
[ ] 说明收集什么数据, 为什么, 与谁共享
[ ] 提供退出机制

审计:
[ ] 定期审计数据处理活动
[ ] 记录数据处理活动 (RoPA)
[ ] DPIA (数据保护影响评估) 对高风险处理
```

---

## 第六部分：实战排障与调优

### 6.1 常见问题速查

| 症状 | 可能原因 | 排查方法 | 解决方案 |
|------|----------|----------|----------|
| **Pixel 数据骤降** | Cookie 限制/ATS | 检查浏览器版本, 对比历史 | 启用 CAPI, 第一方数据优先 |
| **CAPI 匹配分数低** | 数据缺失/未 Hash | 检查用户数据完整性 | 增加 email/phone 收集 |
| **GDPR 投诉** | 同意管理缺失 | 检查 CMP 配置 | 实现 CMP, 确保 Opt-in |
| **数据保留问题** | 未设置保留期限 | 检查数据保留策略 | 设置自动删除/匿名化 |
| **跨境传输风险** | 数据传到 EU 外 | 检查数据传输路径 | 使用 SCC, 数据本地化 |
| **CMP 不生效** | 脚本提前加载 | 检查加载顺序 | 使用 GTM 管理标签加载 |

### 6.2 第一方数据增强策略

```
第一方数据增强 Checklist:

1. 注册流程优化:
   [ ] 注册时收集 email (必须)
   [ ] 注册时收集 phone (可选, 但鼓励)
   [ ] 注册时询问兴趣偏好
   [ ] 提供利益点 (折扣/独家内容) 换取授权

2. 结账流程优化:
   [ ] 结账时收集 email (必须, 用于确认)
   [ ] 结账时收集 phone (可选, 用于通知)
   [ ] 结账后页面引导授权邮件/短信营销

3. 站内行为追踪:
   [ ] 登录用户: 浏览/搜索/购买行为
   [ ] 未登录用户: 匿名行为 (需同意)
   [ ] 所有行为数据匿名化存储

4. 邮件营销:
   [ ] 邮件打开/点击追踪 (需同意)
   [ ] 交易确认邮件 (无需营销同意)
   [ ] 个性化推荐邮件 (需营销同意)

5. 短信营销:
   [ ] SMS 营销 (需明确 Opt-in)
   [ ] 交易通知 (无需营销同意)
   [ ] 退订机制 (每封短信必须包含)

6. App 内数据:
   [ ] App 内行为追踪
   [ ] App 推送通知 (需同意)
   [ ] In-App 购买数据
```

---

## 第七部分：自测

### Q1：GDPR 下，Pixel + CAPI 同时发送数据，是否需要分别获取同意？

<details>
<summary>点击查看参考答案</summary>

**不需要分别获取**, 但需要确保:

1. **统一的同意管理**: 通过 CMP (同意管理平台) 统一收集用户同意
2. **同意字符串传播**: TCF v2.0 同意字符串传递给所有供应商 (包括 CAPI)
3. **CAPI 也检查同意**: 服务端发送 CAPI 事件前, 检查用户是否已同意
4. **Pixel 和 CAPI 数据源一致**: 同一事件, 同一同意状态

**关键点**:
- 用户同意是针对"数据处理目的" (Purpose), 不是针对特定工具
- Purpose 1 (Cookie): Pixel 需要, CAPI 不需要 (CAPI 是服务端)
- Purpose 2 (广告选择): Pixel 和 CAPI 都需要
- 如果用户拒绝 Purpose 2: Pixel 和 CAPI 都不应发送营销数据

**最佳实践**: 在服务端 (CAPI 发送端) 统一检查同意状态, 确保 Pixel 和 CAPI 行为一致。
</details>

### Q2：第一方数据和第三方数据在广告效果上有什么差异？

<details>
<summary>点击查看参考答案</summary>

**第一方数据**:
- 匹配分数高 (> 0.7, 特别是 email/phone)
- 数据质量高 (直接获取, 无推断)
- 合规性高 (用户授权)
- 覆盖范围有限 (仅自有站用户)
- 长期可持续 (不受 Cookie 衰减影响)
- 适合: 品牌广告, 再营销, 转化优化

**第三方数据**:
- 匹配分数低 (< 0.3, Cookie 推断)
- 数据质量低 (推断, 不精确)
- 合规性低 (法规风险)
- 覆盖范围广泛 (跨站追踪)
- 不可持续 (Cookie 衰减, 隐私法规)
- 适合: 品牌曝光, 再营销 (未来逐步淘汰)

**趋势**: 第一方数据 ROI 正在超越第三方数据。Meta 报告: 第一方数据驱动的 Campaign 比第三方数据高 20-40% 的 CPA 效率。
</details>

### Q3：Cookie 衰减后，广告效果如何保持？

<details>
<summary>点击查看参考答案</summary>

**核心策略**:

1. **Pixel + CAPI 双引擎**:
   - Pixel 实时捕获, CAPI 补漏
   - 互补而非替代

2. **第一方数据增强**:
   - 注册流程收集 email/phone
   - 结账流程收集交易数据
   - 站内行为追踪

3. **Server-Side 架构**:
   - GTM Server-Side 替代客户端 GTM
   - 减少浏览器依赖

4. **隐私沙箱/身份图谱**:
   - Google Privacy Sandbox (未来)
   - 基于同意的身份图谱

5. **优化现有数据**:
   - 提高匹配分数 (收集高质量数据)
   - 优化 AEM 配置 (iOS 限制下)
   - 精准定向 (第一方数据 + Lookalike)

**预期影响**:
- 短期: 数据丢失 20-40%
- 中期: 第一方数据策略实施后, 可恢复 60-80%
- 长期: 隐私沙箱成熟后, 可恢复 85-95%
</details>

---

## 第八部分：动手验证

### 8.1 测试第一方数据匹配

```bash
# 1. 准备测试数据 (Hash)
python3 -c "
import hashlib
print('Email Hash:', hashlib.sha256('test@example.com'.lower().strip().encode()).hexdigest())
print('Phone Hash:', hashlib.sha256('+8613800138000'.lower().strip().encode()).hexdigest())
"

# 2. 发送测试事件
curl -X POST "https://graph.facebook.com/v18.0/YOUR_PIXEL_ID/events?access_token=YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "data": [{
      "event_name": "Purchase",
      "event_id": "test_purchase_001",
      "event_time": 1686364800,
      "user_data": {
        "em": ["YOUR_EMAIL_HASH"],
        "ph": ["YOUR_PHONE_HASH"]
      },
      "custom_data": {
        "value": 99.99,
        "currency": "USD"
      }
    }]
  }'

# 3. 检查匹配分数
# Events Manager → Diagnostics → 查看匹配分数
```

### 8.2 同意管理测试

```bash
# 1. 测试 CMP 同意检查
# 访问网站, 关闭所有 Cookie 同意, 检查是否加载了 Pixel

# 2. 验证 CAPI 客户端不发送数据
# 调试模式下, 检查网络请求是否被阻止

# 3. 测试用户权利
# 发送 GET /api/user/export 和 DELETE /api/user 测试数据导出/删除
```

---

*本文档基于 GDPR/CCPA 法规、IAB TCF v2.0 标准和实际广告技术实践整理。隐私法规持续更新, 建议定期审查合规状态。*
