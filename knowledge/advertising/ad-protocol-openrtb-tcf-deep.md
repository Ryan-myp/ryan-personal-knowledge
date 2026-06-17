# 广告协议深度：OpenRTB 2.6/Privacy Sandbox/TCF 2.0/Ads.txt

> 逐行解析 OpenRTB 协议结构、Privacy Sandbox 提案、TCF 2.0 合规、Ads.txt 反欺诈

---

## 第一部分：OpenRTB 2.6 协议深度

### 为什么要用 OpenRTB？

```
广告竞价协议演进：
1. 私有协议（2005-2010）：每家的 Exchange 用不同的 API
2. OpenRTB 1.0（2010）：IAB 标准化，统一 BidRequest/BidResponse
3. OpenRTB 2.0+（2011-2023）：持续扩展，2.6 是当前主流

OpenRTB 核心优势：
- 跨平台对接：一次对接，支持所有 Exchange
- 协议标准化：BidRequest/BidResponse 有明确结构
- 生态成熟：所有 DSP/SSP/DSP 都支持
```

### BidRequest 结构源码级解析

```json
{
  "id": "bid-request-12345",
  "tmax": 100,
  "at": 1,
  "imp": [
    {
      "id": "imp-001",
      "banner": {
        "w": 300,
        "h": 250,
        "pos": 2,
        "api": [1, 2, 3],
        "mimes": ["image/jpeg", "image/png"],
        "topframe": 1,
        "api": [1, 2, 3]
      },
      "video": {
        "mimes": ["video/mp4"],
        "protocols": [1, 2, 3, 4, 5, 6, 7, 8],
        "maxduration": 30,
        "startdelay": 0,
        "linearity": 1,
        "skip": 1,
        "skipmin": 5,
        "placement": 2
      },
      "native": {
        "request": "{\"ver\":\"1.2\",\"assets\":[...]}",
        "api": [1, 2, 3]
      },
      "pmp": {
        "private_auctions": [
          {
            "id": "pmp-001",
            "bidders": ["dsp-001", "dsp-002"],
            "deals": [
              {
                "id": "deal-001",
                "bidfloor": 2.5,
                "bidfloorcur": "USD"
              }
            ]
          }
        ]
      },
      "bidfloor": 1.0,
      "bidfloorcur": "USD",
      "secure": 1
    }
  ],
  "site": {
    "id": "site-001",
    "name": "Example News Site",
    "domain": "example.com",
    "cat": ["IAB19", "IAB19-1"],
    "sectioncat": ["IAB19-1", "IAB19-2"],
    "pagecat": ["IAB19-1"],
    "page": "https://example.com/article/123",
    "ref": "https://google.com",
    "search": "advertising platform",
    "mobile": 0,
    "privacypolicy": 1,
    "publisher": {
      "id": "pub-001",
      "name": "Example Publisher",
      "domain": "example.com"
    },
    "content": {
      "id": "content-001",
      "episode": 5,
      "season": 2,
      "series": "Ad Tech Weekly",
      "title": "OpenRTB Deep Dive",
      "category": "Technology",
      "language": "en",
      "len": 120,
      "qagmediarating": 2,
      "videoquality": "MQM"
    }
  },
  "app": {
    "id": "app-001",
    "name": "My App",
    "bundle": "com.example.myapp",
    "storeurl": "https://play.google.com/store/apps/details?id=com.example",
    "domain": "example.com",
    "cat": ["IAB18-1", "IAB18-1-1"],
    "sectioncat": ["IAB18-1-1"],
    "pagecat": ["IAB18-1-1"],
    "web": {
      "id": "web-001",
      "bundle": "com.example.web"
    },
    "publisher": {
      "id": "pub-001",
      "name": "Example Publisher",
      "domain": "example.com"
    },
    "content": {
      "id": "content-001",
      "episode": 1,
      "title": "Episode 1",
      "language": "en"
    },
    "private_taxonomy": 1,
    "keywords": "advertising,dsp,openrtb"
  },
  "device": {
    "ua": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)",
    "ip": "203.0.113.1",
    "ipv6": "2001:db8::1",
    "dnt": 0,
    "lmt": 0,
    "make": "Apple",
    "model": "iPhone 15 Pro",
    "os": "iOS",
    "osv": "17.0",
    "hwv": "15",
    "h": 2340,
    "w": 1080,
    "devicetype": 1,
    "connectiontype": 0,
    "carrier": "Verizon",
    "mccmnc": "310-004",
    "language": "en",
    "country": "US",
    "geo": {
      "lat": 37.7749,
      "lon": -122.4194,
      "latrs": 1000,
      "lonrs": 1000,
      "type": 1,
      "city": "San Francisco",
      "region": "CA",
      "country": "US",
      "metro": "807",
      "zip": "94102"
    }
  },
  "user": {
    "id": "user-001",
    "buyeruid": "dsp-user-001",
    "yob": 1990,
    "gender": "m",
    "keywords": "advertising,tech,news",
    "customdata": "segment=premium",
    "geo": {
      "lat": 37.7749,
      "lon": -122.4194,
      "type": 1,
      "city": "San Francisco",
      "region": "CA",
      "country": "US"
    }
  },
  "regulations": {
    "gdpr": 1,
    "usprivacy": "1YNN",
    "coppa": 0
  },
  "ext": {
    "prebid": {
      "cache": {
        "bids": true,
        "vastxml": true
      },
      "bidder": {
        "appnexus": {"placementId": "12345"},
        "rubicon": {"accountId": 1234, "siteId": 5678}
      }
    },
    "schain": [
      {
        "asi": "example.com",
        "sid": "1234",
        "hp": 1,
        "rid": "transaction-id-001",
        "name": "Example Publisher",
        "domain": "example.com"
      },
      {
        "asi": "bidder.example.com",
        "sid": "5678",
        "hp": 0,
        "rid": "transaction-id-002",
        "name": "Reseller",
        "domain": "reseller.example.com"
      }
    ]
  }
}
```

### OpenRTB 字段详解

```
BidRequest 核心字段：
├── id: 唯一请求 ID（用于追踪和调试）
├── tmax: 竞价超时（毫秒），默认 100ms
├── at: 竞价类型（1=First Price, 2=Second Price）
├── imp: 广告位数组（支持多广告位同时竞价）
├── site: 网站上下文（如果是 Web）
├── app: APP 上下文（如果是 Mobile App）
├── device: 设备信息（UA/IP/Geo/连接类型）
├── user: 用户信息（ID/年龄/性别/兴趣）
└── regulations: 隐私合规（GDPR/US Privacy/COPPA）

imp（广告位）字段：
├── id: 广告位唯一 ID
├── bidfloor: 底价（美元）
├── bidfloorcur: 底价货币（默认 USD）
├── banner: 横幅广告规格
├── video: 视频广告规格
├── native: 原生广告规格
├── pmp: 私有市场（Private Marketplace）
└── secure: 是否仅 HTTPS

banner 字段：
├── w/h: 尺寸（固定）
├── wmin/hmin: 最小尺寸
├── wmax: 最大尺寸
├── pos: 广告位置（0=未知, 1=above fold, 2=below fold, ...）
├── api: 支持的技术（1=VPAID 1.0, 2=VPAID 2.0, 3=MRAID）
├── topframe: 是否在顶层框架
├── mimes: 支持的 MIME 类型
└── battr: 禁止的技术

video 字段：
├── mimes: 支持的格式（video/mp4, video/webm）
├── protocols: 支持的协议（VAST 1-8）
├── maxduration: 最大时长（秒）
├── startdelay: 预滚动延迟（秒）
├── linearity: 行性（1=in-stream, 2=overlay）
├── skip: 是否可跳过（0=不可, 1=可）
├── skipmin: 最小观看时长后跳过（秒）
├── skipafter: 跳过后的延迟（秒）
└── placement: 投放类型

native 字段：
├── request: JSON 序列化（定义需要的资产）
├── ver: 原生广告版本（1.0-1.2）
└── api: 支持的技术
```

### BidResponse 源码级解析

```json
{
  "id": "bid-response-12345",
  "seatbid": [
    {
      "seat": "seat-001",
      "bid": [
        {
          "id": "bid-001",
          "impid": "imp-001",
          "price": 2.5,
          "adm": "<iframe src='...' width='300' height='250'></iframe>",
          "adid": "creative-001",
          "adomain": ["example.com"],
          "iurl": "https://example.com/thumbnail.jpg",
          "cid": "campaign-001",
          "crid": "creative-001",
          "cat": ["IAB19", "IAB19-1"],
          "dest": "https://example.com/landing",
          "lurl": "https://tracker.example.com/impression",
          "durl": "https://tracker.example.com/click",
          "attr": [1, 2, 3],
          "api": [1, 2, 3],
          "mimes": ["image/jpeg"],
          "exp": 0,
          "ext": {
            "prebid": {
              "type": "banner",
              "auction": "2.0",
              "bid": {
                "id": "prebid-bid-001",
                "seatbid": [{"bid": [{"id": "prebid-bid-001"}], "seat": "prebid"}]
              }
            }
          }
        }
      ],
      "group": 0
    }
  ],
  "nurl": "https://bidder.example.com/win-notice?bidid=xxx",
  "bidid": "bid-001",
  "cur": "USD",
  "usprivacy": "1YNN",
  "ext": {}
}
```

### Go 实现 BidRequest/BidResponse

```go
package openrtb

import (
	"encoding/json"
	"fmt"
)

// OpenRTB Types
// 1. Banner
type Banner struct {
	ID       string   `json:"id,omitempty"`
	W        int      `json:"w,omitempty"`
	H        int      `json:"h,omitempty"`
	WMin     int      `json:"wmin,omitempty"`
	HMin     int      `json:"hmin,omitempty"`
	WMax     int      `json:"wmax,omitempty"`
	HMax     int      `json:"hmax,omitempty"`
	Pos      int      `json:"pos,omitempty"`       // 0=Unknown, 1=Above Fold, ...
	BType    []int    `json:"btype,omitempty"`     // 禁止的浏览类型
	BAdv     []string `json:"badv,omitempty"`      // 禁止的广告主
	API      int      `json:"api,omitempty"`       // 1=VPAID 1.0, 2=VPAID 2.0, 3=MRAID
	Mimes    []string `json:"mimes,omitempty"`     // 支持的 MIME 类型
	TopFrame *int     `json:"topframe,omitempty"`  // 是否在顶层框架
	Ext      json.RawMessage `json:"ext,omitempty"` // 扩展字段
}

// 2. Video
type Video struct {
	MIMEs      []string `json:"mimes,omitempty"`
	Protocols  []int    `json:"protocols,omitempty"`  // VAST 1-8
	Protocol   *int     `json:"protocol,omitempty"`   // 协议版本
	W          *int     `json:"w,omitempty"`
	H          *int     `json:"h,omitempty"`
	StartDelay *int     `json:"startdelay,omitempty"`
	Linearity  *int     `json:"linearity,omitempty"`  // 1=in-stream, 2=overlay
	MaxDuration *int    `json:"maxduration,omitempty"`
	Skip       *int     `json:"skip,omitempty"`       // 0=不可跳过, 1=可跳过
	SkipMin    *int     `json:"skipmin,omitempty"`
	SkipAfter  *int     `json:"skipafter,omitempty"`
	Placement  *int     `json:"placement,omitempty"`
	Badv       []string `json:"badv,omitempty"`
	Ext        json.RawMessage `json:"ext,omitempty"`
}

// 3. Impression
type Imp struct {
	ID         string  `json:"id"`
	BidFloor   float64 `json:"bidfloor,omitempty"`
	BidFloorCur string  `json:"bidfloorcur,omitempty"`
	Banner     *Banner `json:"banner,omitempty"`
	Video      *Video  `json:"video,omitempty"`
	// Native, Pmp, Secure, etc.
}

// 4. Device
type Device struct {
	UA           string `json:"ua,omitempty"`
	IP           string `json:"ip,omitempty"`
	IPv6         string `json:"ipv6,omitempty"`
	DNT          *int   `json:"dnt,omitempty"` // 0=Not Do Not Track, 1=Do Not Track
	LMT          *int   `json:"lmt,omitempty"` // 0=Limited Ad Tracking, 1=Ad Tracking Allowed
	Make         string `json:"make,omitempty"`
	Model        string `json:"model,omitempty"`
	OS           string `json:"os,omitempty"`
	OSV          string `json:"osv,omitempty"`
	HWV          string `json:"hwv,omitempty"`
	H            int    `json:"h,omitempty"`
	W            int    `json:"w,omitempty"`
	DevType      int    `json:"devicetype,omitempty"` // 1=Mobile, 2=Desktop, 3=Tablet
	ConnectionType int  `json:"connectiontype,omitempty"` // 0=Unknown, 1=Ethernet, ...
	Carrier      string `json:"carrier,omitempty"`
	MCCMNC       string `json:"mccmnc,omitempty"`
	Language     string `json:"language,omitempty"`
	Country      string `json:"country,omitempty"`
	Geo          *Geo   `json:"geo,omitempty"`
}

// 5. Geo
type Geo struct {
	Lat    float64 `json:"lat,omitempty"`
	Lon    float64 `json:"lon,omitempty"`
	LatRS  *int    `json:"latrs,omitempty"` // Radius
	LonRS  *int    `json:"lonrs,omitempty"`
	Type   int     `json:"type,omitempty"` // 1=GPS, 2=IP, 3=Place
	City   string  `json:"city,omitempty"`
	Region string  `json:"region,omitempty"`
	Country string `json:"country,omitempty"`
	Metro  string  `json:"metro,omitempty"`
	Zip    string  `json:"zip,omitempty"`
}

// 6. BidRequest
type BidRequest struct {
	ID         string   `json:"id"`
	TMax       *int     `json:"tmax,omitempty"`
	AT         *int     `json:"at,omitempty"`         // 1=First Price, 2=Second Price
	Imp        []Imp    `json:"imp"`
	Site       *Site    `json:"site,omitempty"`
	App        *App     `json:"app,omitempty"`
	Device     *Device  `json:"device,omitempty"`
	User       *User    `json:"user,omitempty"`
	Regs       *Regs    `json:"regulations,omitempty"`
	Ext        json.RawMessage `json:"ext,omitempty"`
}

type Regs struct {
	GDPR        *int    `json:"gdpr,omitempty"`         // 0=未设, 1=设有
	USPrivacy   string  `json:"usprivacy,omitempty"`    // IAB US Privacy String (4 chars)
	COPPA       *int    `json:"coppa,omitempty"`        // 0=不设, 1=设
}

// 7. BidResponse
type BidResponse struct {
	ID      string     `json:"id"`
	SeatBid []SeatBid  `json:"seatbid,omitempty"`
	NURL    string     `json:"nurl,omitempty"`     // Win Notice URL
	BidID   string     `json:"bidid,omitempty"`
	Cur     string     `json:"cur,omitempty"`
	Ext     json.RawMessage `json:"ext,omitempty"`
}

type SeatBid struct {
	Bid   []Bid    `json:"bid"`
	Seat  string   `json:"seat,omitempty"`
	Group *int     `json:"group,omitempty"`    // 0=不分组, 1=分组
}

type Bid struct {
	ID        string   `json:"id"`
	ImpID     string   `json:"impid"`
	Price     float64  `json:"price"`
	ADM       string   `json:"adm"`               // 广告内容
	AdID      string   `json:"adid,omitempty"`
	ADomain   []string `json:"adomain,omitempty"`   // 广告主域名
	IURL      string   `json:"iurl,omitempty"`      // 缩略图 URL
	CID       string   `json:"cid,omitempty"`       // 广告系列 ID
	CRID      string   `json:"crid,omitempty"`      // 创意 ID
	CAT       []string `json:"cat,omitempty"`       // 广告分类
	Dest      string   `json:"dest,omitempty"`      // 落地页 URL
	LURL      string   `json:"lurl,omitempty"`      // 曝光追踪 URL
	DURL      string   `json:"durl,omitempty"`      // 点击追踪 URL
	Attr      []int    `json:"attr,omitempty"`      // 广告类型
	API       *int     `json:"api,omitempty"`
	MIMEs     []string `json:"mimes,omitempty"`
	Exp       *int     `json:"exp,omitempty"`       // 过期时间（秒）
	Ext       json.RawMessage `json:"ext,omitempty"`
}

// ParseBidRequest 解析 BidRequest
func ParseBidRequest(data []byte) (*BidRequest, error) {
	var req BidRequest
	if err := json.Unmarshal(data, &req); err != nil {
		return nil, fmt.Errorf("parse bid request: %w", err)
	}
	return &req, nil
}

// BuildBidResponse 构建 BidResponse
func BuildBidResponse(reqID string, impID string, price float64, adm string) (*BidResponse, error) {
	resp := BidResponse{
		ID:     fmt.Sprintf("resp-%s", reqID),
		Cur:    "USD",
		SeatBid: []SeatBid{{
			Bid: []Bid{{
				ID:      fmt.Sprintf("bid-%s", reqID),
				ImpID:   impID,
				Price:   price,
				ADM:     adm,
				ADomain: []string{"example.com"},
				CID:     "campaign-001",
				CRID:    "creative-001",
				Dest:    "https://example.com/landing",
				LURL:    "https://tracker.example.com/impression",
				DURL:    "https://tracker.example.com/click",
			}},
		}},
	}
	return &resp, nil
}
```

---

## 第二部分：TCF 2.0 深度

### TCF 2.0 是什么？

```
TCF 2.0 (Transparency and Consent Framework):
IAB 制定的用户同意管理框架，用于 GDPR 合规

核心组件：
1. CMP (Consent Management Platform): 向用户收集同意
2. TC String: 编码后的同意信号
3. GVL (Global Vendor List): 供应商列表（~150 家 DSP）
4. Purposes: 用户同意的目的（15 个标准目的）
5. Legitimate Interests: 合法利益（9 个标准利益）
6. Special Features: 特殊功能（精确定位/广告偏好等）
7. Special Purposes: 特殊目的（测量/开发等）
```

### TC String 解码

```go
// TCF 2.0 TC String 结构
// 格式：COu0... (Base64 编码)

type TCFConsent struct {
	PolicyVersion      uint8            // 策略版本（当前=2）
	PublisherCC        string           // 国家代码（如 "US", "DE"）
	ConsentScreen      uint8            // 同意屏幕 ID
	PublisherPurposeIDs  []int          // 发布者请求的目的 ID
	ConsentString      string           // TC String 本身
	ISPurposeAllowed   map[int]bool     // 每个目的是否被允许
	ISVendorAllowed    map[int]bool     // 每个供应商是否被允许
	ISPublisherLI      map[int]bool     // 发布者合法利益
	ISPublisherSpecialPurpose map[int]bool // 发布者特殊目的
}

// DecodeTCString 解码 TC String
func DecodeTCString(tcString string) (*TCFConsent, error) {
	// 1. Base64 解码
	decoded, err := base64.RawURLEncoding.DecodeString(tcString)
	if err != nil {
		return nil, err
	}
	
	// 2. 解析 IAB Europe TC String
	// 位图结构：
	// 0-7:   Policy Version
	// 8-16:  (预留)
	// 17-32:  Publisher CC (2 bytes)
	// 33-64:  (预留)
	// 65-96:  Purposes (32 bits)
	// 97-128: Vendors (256 bits = 32 bytes)
	// ...
	
	consent := &TCFConsent{}
	consent.PolicyVersion = decoded[0]
	
	// 解析 Purposes（bit 65-96）
	consent.ISPurposeAllowed = make(map[int]bool)
	for i := 0; i < 15; i++ {
		if decoded[11+i/8]&(1<<(7-i%8)) != 0 {
			consent.ISPurposeAllowed[i+1] = true
		}
	}
	
	// 解析 Vendors（bit 97-128，32 bytes）
	consent.ISVendorAllowed = make(map[int]bool)
	for i := 0; i < 256; i++ {
		if decoded[15+i/8]&(1<<(7-i%8)) != 0 {
			consent.ISVendorAllowed[i+1] = true
		}
	}
	
	return consent, nil
}
```

### 广告竞价中的 TCF 检查

```go
// 在 BidRequest 中检查 TCF 合规
func CheckTCFCompliance(req *BidRequest, tcString string) error {
	consent, err := DecodeTCString(tcString)
	if err != nil {
		// 无法解码 TC String → 拒绝竞价
		return fmt.Errorf("invalid tc string")
	}
	
	// 检查用户是否同意目的 1（数据采集）
	if !consent.ISPurposeAllowed[1] {
		return fmt.Errorf("user did not consent to purpose 1")
	}
	
	// 检查用户是否同意目的 3（广告选择）
	if !consent.ISPurposeAllowed[3] {
		return fmt.Errorf("user did not consent to purpose 3")
	}
	
	// 检查用户是否同意目的 7（广告性能）
	if !consent.ISPurposeAllowed[7] {
		return fmt.Errorf("user did not consent to purpose 7")
	}
	
	// 检查 DSP 是否在允许的供应商列表中
	if !consent.ISVendorAllowed[1234] { // 1234=your DSP ID
		return fmt.Errorf("vendor not allowed by user")
	}
	
	return nil
}
```

---

## 第三部分：Privacy Sandbox

### Google Privacy Sandbox 提案

```
Privacy Sandbox 目标：
用 cookieless 方案替代第三方 Cookie

核心提案：
1. FLEDGE (First Party Local Group Experiment)
   → 基于浏览器的兴趣分组和实时竞价
   → 替代第三方 Cookie + RTB

2. Topics API
   → 浏览器本地兴趣标签
   → 替代第三方 Cookie 的用户画像

3. Attribution Reporting API
   → 跨站转化归因
   → 替代第三方 Cookie 的转化归因

4. Protected Audience API (FLEDGE)
   → 浏览器端实时竞价
   → DSP 在浏览器内出价（而非服务器端）

5. Trust Tokens
   → 反欺诈
   → 替代 fingerprinting
```

### FLEDGE 竞价流程

```
传统 RTB:
1. 用户访问页面
2. SSP 发送 BidRequest → Exchange → DSP 服务器
3. DSP 服务器计算出价 → 返回 BidResponse
4. Exchange 选出最高价 → 展示广告
5. 曝光/点击 → DSP 服务器追踪

FLEDGE 竞价:
1. 用户访问页面，浏览器本地收集兴趣标签
2. 广告主通过 Protected Audience API 创建竞价组
3. 用户再次访问相关页面
4. 浏览器本地运行竞价（不调用 DSP 服务器）
5. 浏览器选择广告 → 展示
6. 曝光/点击 → 通过 Attribution Reporting 上报

关键变化：
- 竞价从 DSP 服务器 → 浏览器本地
- 用户数据不出浏览器（隐私保护）
- DSP 无法追踪单个用户（隐私保护）
```

---

## 第四部分：Ads.txt 深度

### Ads.txt 是什么？

```
Ads.txt (Authorized Digital Sellers):
IAB 制定的广告供应链透明化标准

目的：防止域名伪造和未经授权的销售

格式（每行一个授权）：
domain_name, publisher_id, relationship_type, certification_authority_id

示例：
google.com, pub-1234567890123456, Direct, 12345
amazon.com, pub-0987654321098765, Re_sell, 12345

relationship_type:
- Direct: 发布者直接授权
- Re_sell: 再销售授权（需 certification_authority_id）
```

### Apps.txt (APP 版本)

```
Apps.txt:
适用于移动 APP 的授权销售者清单

格式：
publisher_id, platform_type, platform_publisher_id, relationship_type

示例：
pub-1234567890123456, apple_app_store, com.example.myapp, Direct
pub-0987654321098765, google_play_store, com.example.myapp, Re_sell
```

### Ads.txt 验证实现

```go
package main

import (
	"bufio"
	"fmt"
	"os"
	"strings"
)

// AdsEntry 广告主授权条目
type AdsEntry struct {
	Domain           string
	PublisherID      string
	Relationship     string // "Direct" 或 "Re_sell"
	CertificationID  string // 仅 Re_sell 需要
}

// ParseAdsTxt 解析 ads.txt 文件
func ParseAdsTxt(filepath string) ([]AdsEntry, error) {
	file, err := os.Open(filepath)
	if err != nil {
		return nil, err
	}
	defer file.Close()
	
	var entries []AdsEntry
	scanner := bufio.NewScanner(file)
	lineNum := 0
	
	for scanner.Scan() {
		lineNum++
		line := strings.TrimSpace(scanner.Text())
		
		// 跳过空行和注释
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		
		parts := strings.Split(line, ",")
		if len(parts) < 3 {
			fmt.Printf("Line %d: invalid format\n", lineNum)
			continue
		}
		
		entry := AdsEntry{
			Domain:          strings.TrimSpace(parts[0]),
			PublisherID:     strings.TrimSpace(parts[1]),
			Relationship:    strings.TrimSpace(parts[2]),
			CertificationID: strings.TrimSpace(parts[3]),
		}
		
		entries = append(entries, entry)
	}
	
	return entries, scanner.Err()
}

// VerifyAds 验证广告主是否被授权
func VerifyAds(entries []AdsEntry, domain, publisherID string) bool {
	for _, entry := range entries {
		if entry.Domain == domain && entry.PublisherID == publisherID {
			return true
		}
	}
	return false
}
```

---

## 第五部分：自测题

### Q1: OpenRTB 2.6 中 first price 和 second price 竞价的区别？

**A**:
- **First Price (at=1)**: 出价即实际支付价格
- **Second Price (at=2)**: 支付第二高价
- 趋势：2023 年起越来越多平台转向 first price
- 影响：first price 需要更精确的出价策略（避免过度出价）

### Q2: TCF 2.0 中如果用户拒绝目的 1，DSP 还能竞价吗？

**A**: 不能。目的 1（数据采集）是基本目的，拒绝后 DSP 无法获取用户数据，也无法追踪曝光/点击。DSP 必须在 BidResponse 中标记自己已被拒绝。

### Q3: Privacy Sandbox 的 FLEDGE 相比传统 RTB 有什么优势？

**A**:
- 优势：用户数据不出浏览器，隐私保护更好
- 优势：减少网络延迟（浏览器本地竞价）
- 挑战：DSP 失去用户数据，难以优化模型
- 挑战：浏览器性能影响（内存/CPU）

---

## 第六部分：生产实践

### 1. OpenRTB 兼容性

```
常见兼容性陷阱：
1. BidRequest 字段缺失 → 使用默认值
2. Banner 尺寸协商 → 支持多种尺寸
3. Video 协议版本 → 支持 VAST 1-8
4. Native 资产要求 → 按需请求
5. PMP 私有市场 → 检查 deal 状态
6. GDPR/TCF → 必须检查同意信号
```

### 2. GDPR 合规清单

```
GDPR 合规检查：
1. ✅ CMP 集成（所有欧洲用户展示同意屏幕）
2. ✅ TC String 解码和验证
3. ✅ GVL 同步（定期更新供应商列表）
4. ✅ 用户数据最小化（只请求必要信息）
5. ✅ 数据删除请求处理
6. ✅ 数据跨境传输合规（EU-US 数据保护框架）
```

### 3. Ads.txt 集成

```
ads.txt 最佳实践：
1. 在 exchange 层验证 ads.txt
2. 拒绝未经授权的销售
3. 定期更新 publisher 授权列表
4. 对违规 publisher 暂停竞价
5. 监控异常竞价模式
```
