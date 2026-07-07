# 程序化广告深度实战：从RTB到DSP

## 一、程序化广告的前世今生

### 1.1 广告发展历程

```
传统广告时代:
├── 人工谈判
├── 固定价格
└── 低效匹配

程序化广告时代:
├── 自动化购买
├── 实时竞价
└── 精准定向
```

### 1.2 程序化广告定义

**IAB定义：**
程序化广告是通过技术手段自动完成广告位购买、售卖和投放的过程。

**核心要素：**
- 自动化
- 数据驱动
- 实时决策
- 精准定向

## 二、程序化广告基础

### 2.1 IAB接口规范

**关键标准：**
- OpenRTB: 实时竞价协议
- VAST/VPAID: 视频广告标准
- MRAID: 移动富媒体广告

### 2.2 OpenRTB协议详解

```
Bid Request 结构:
{
  "id": "bid-request-id",
  "imp": [{
    "id": "imp-id",
    "banner": {
      "w": 300,
      "h": 250
    },
    "instl": 0
  }],
  "site": {
    "domain": "example.com",
    "page": "https://example.com"
  },
  "device": {
    "ua": "Mozilla/5.0...",
    "ip": "192.168.1.1"
  },
  "user": {
    "id": "user-id",
    "buyeruid": "buyer-user-id"
  }
}
```

**Go 实现 OpenRTB 解析：**

```go
package openrtb

import (
	"encoding/json"
	"fmt"
)

type BidRequest struct {
	ID      string     `json:"id"`
	Imp     []Impression `json:"imp"`
	Site    *Site      `json:"site,omitempty"`
	App     *App       `json:"app,omitempty"`
	Device  *Device    `json:"device"`
	User    *User      `json:"user,omitempty"`
}

type Impression struct {
	ID       string    `json:"id"`
	Banner   *Banner   `json:"banner,omitempty"`
	Video    *Video    `json:"video,omitempty"`
	Instl    int       `json:"instl"`
	TagID    string    `json:"tagid,omitempty"`
	Secure   int       `json:"secure,omitempty"`
	InstlPos int       `json:"instlpos,omitempty"`
}

type Banner struct {
	W      int      `json:"w,omitempty"`
	H      int      `json:"h,omitempty"`
	Format []Format `json:"format,omitempty"`
}

type Video struct {
	W      int      `json:"w,omitempty"`
	H      int      `json:"h,omitempty"`
	Mimes  []string `json:"mimes,omitempty"`
	Protos []int    `json:"protos,omitempty"`
}

type Site struct {
	Domain string `json:"domain,omitempty"`
	Page   string `json:"page,omitempty"`
	Name   string `json:"name,omitempty"`
}

type App struct {
	Domain string `json:"domain,omitempty"`
	Name   string `json:"name,omitempty"`
}

type Device struct {
	UA    string `json:"ua,omitempty"`
	IP    string `json:"ip,omitempty"`
	Make  string `json:"make,omitempty"`
	Model string `json:"model,omitempty"`
}

type User struct {
	ID       string            `json:"id,omitempty"`
	BuyerUID string            `json:"buyeruid,omitempty"`
	Ext      map[string]interface{} `json:"ext,omitempty"`
}

func ParseBidRequest(data []byte) (*BidRequest, error) {
	req := &BidRequest{}
	if err := json.Unmarshal(data, req); err != nil {
		return nil, fmt.Errorf("failed to parse bid request: %w", err)
	}
	return req, nil
}
```

## 三、程序化广告中的大数据基础

### 3.1 人的唯一性标识

**ID类型：**

| 类型 | 说明 | 示例 |
|------|------|------|
| Cookie ID | 浏览器标识 | __cfduid |
| Device ID | 设备标识 | IDFA/OAID |
| User ID | 用户标识 | 登录ID |
| Fingerprint | 设备指纹 | 硬件+软件组合 |

**Go 实现设备指纹：**

```go
package fingerprint

import (
	"crypto/md5"
	"fmt"
	"runtime"
	"time"
)

type Fingerprint struct {
	UserAgent string
	IP        string
	Language  string
	Platform  string
	Timezone  string
	Screen    string
	Fonts     []string
	Canvas    string
	WebGL     string
}

func Generate(fp Fingerprint) string {
	data := fmt.Sprintf("%s|%s|%s|%s|%s|%s|%s|%s|%s",
		fp.UserAgent,
		fp.IP,
		fp.Language,
		fp.Platform,
		fp.Timezone,
		fp.Screen,
		fp.Canvas,
		fp.WebGL,
		fp.Time,
	)
	
	hash := md5.Sum([]byte(data))
	return fmt.Sprintf("%x", hash)
}
```

## 四、监测注意要点

### 4.1 视频广告投放TA浓度KPI注意事项

**关键指标：**

| 指标 | 说明 | 计算公式 |
|------|------|----------|
| TA浓度 | 目标受众覆盖率 | 目标受众曝光数/总曝光数 |
| 有效曝光 | 可见性达标 | 50%像素可见≥1秒 |
| 完播率 | 视频观看完成度 | 完整观看数/总观看数 |

## 五、移动广告的关键知识

### 5.1 移动端特有的一些问题

**挑战：**
- 屏幕尺寸多样
- 网络环境复杂
- 隐私政策限制

**解决方案：**
- 响应式设计
- 自适应布局
- 合规数据采集

## 六、广告交易平台ADX要点

### 6.1 什么是RTB

**实时竞价流程：**

```
1. 用户访问App/网站
2. 请求广告位
3. ADX发送Bid Request
4. DSP接收请求
5. DSP计算出价
6. ADX选择最高出价
7. 返回Winner Ad
8. 广告展示
9. 计费通知
```

**Go 实现简易RTB引擎：**

```go
package rtb

import (
	"context"
	"fmt"
	"sync"
)

type RTBEngine struct {
	dspClients map[string]DSPClient
	mu         sync.RWMutex
}

type DSPClient interface {
	Bid(ctx context.Context, req *BidRequest) (*BidResponse, error)
}

type BidRequest struct {
	AdSlotID string
	UserID   string
	Device   string
}

type BidResponse struct {
	BidPrice float64
	AdID     string
}

func (e *RTBEngine) ProcessBid(ctx context.Context, req *BidRequest) (*BidResponse, error) {
	e.mu.RLock()
	clients := make([]DSPClient, 0, len(e.dspClients))
	for _, client := range e.dspClients {
		clients = append(clients, client)
	}
	e.mu.RUnlock()
	
	// 并发请求
	type result struct {
		response *BidResponse
		err      error
	}
	
	ch := make(chan result, len(clients))
	for _, client := range clients {
		go func(c DSPClient) {
			resp, err := c.Bid(ctx, req)
			ch <- result{resp, err}
		}(client)
	}
	
	// 收集结果
	var winner *BidResponse
	for i := 0; i < len(clients); i++ {
		res := <-ch
		if res.err != nil {
			continue
		}
		if winner == nil || res.response.BidPrice > winner.BidPrice {
			winner = res.response
		}
	}
	
	if winner == nil {
		return nil, fmt.Errorf("no bids received")
	}
	
	return winner, nil
}
```

## 七、程序化买方DSP要点

### 7.1 国内DSP典型模式介绍

**DSP核心功能：**

```
DSP架构:
├── 数据接入层
│   ├── DMP数据
│   ├── 第三方数据
│   └── 自有数据
├── 算法层
│   ├── CTR预估
│   ├── CVR预估
│   └── 出价策略
├── 交易层
│   ├── RTB竞价
│   ├── PMP采购
│   └── 直采
└── 投放层
    ├── 创意管理
    ├── 定向设置
    └── 频次控制
```

## 八、程序化广告高级模式PDB要点

### 8.1 PDB广告处理流程

**PDB (Programmatic Direct Buy)：**

```
PDB流程:
1. 广告主预留库存
2. DSP通过私有市场购买
3. 保证曝光量
4. 固定价格
```

## 九、DMP实战案例

### 9.1 常见DMP盘点

**DMP核心模块：**

```
DMP架构:
├── 数据采集
│   ├── 第一方数据
│   ├── 第二方数据
│   └── 第三方数据
├── 数据处理
│   ├── ID Mapping
│   ├── 标签生成
│   └── 受众分群
└── 数据应用
    ├── 受众定向
    ├── Lookalike
    └── 频次控制
```

## 十、行业发展趋势预测及分析

### 10.1 DSP行业发展及趋势预测

**未来趋势：**

```
技术趋势:
├── AI/ML 驱动
├── 隐私保护
├── 跨屏投放
└── 新兴平台

业务趋势:
├── 从流量到留量
├── 从单次到LTV
├── 从粗放到精细
└── 从人工到AI
```

## 十一、自测题

1. 程序化广告的核心优势是什么？
2. OpenRTB协议的关键字段有哪些？
3. DSP系统的核心模块有哪些？
4. PDB和RTB有什么区别？

## 十二、动手验证

```bash
# 1. 实现OpenRTB解析器
# 2. 实现简易RTB引擎
# 3. 实现设备指纹生成
# 4. 实现DMP基础功能
```
