# RTB 底层实现：从 Bid Request 到 Bid Response 的全链路

> 创建日期: 2026-06-10
> 作者: Ryan
> 定位: 资深专家级 — RTB 底层实现

---

## 第一部分：RTB 时序精确分析

### 1.1 RTB 100ms 时间线精确分解

```
┌──────────────────────────────────────────────────────────────────────┐
│                   RTB 精确时序 (100ms 预算)                            │
│                                                                      │
│  时间线 (ms)         事件                           延迟    │
│  ────────────────── ───────────────────────────── ─────   │
│  0.0               用户请求页面 (HTTP GET)            │
│  0.5-1.0           HTML 解析，检测广告容器            1ms     │
│  1.0-1.5           发现 Ad Slot，调用 ad loader       0.5ms  │
│  1.5-3.0           SSP SDK 初始化                    1.5ms  │
│  3.0-5.0           Header Bidding 预请求              2ms    │
│                  ┌─────────────────────────────────┐        │
│                  │ Prebid.js 同时请求:              │        │
│                  │ • Google AdX                     │        │
│                  │ • Amazon DSP                     │        │
│                  │ • The Trade Desk                 │        │
│                  │ • Xandr                          │        │
│                  │ • Magnite                        │        │
│                  └─────────────────────────────────┘        │
│  5.0-10.0          DSP 预竞价 (Pre-bid)                     5ms  │
│                  ┌─────────────────────────────────┐        │
│                  │ DSP 预竞价流程:                    │        │
│                  │ 1. 解析 Bid Request               │        │
│                  │ 2. 本地缓存查询 (SSD)             │        │
│                  │ 3. 快速 pCTR 估算 (<1ms)          │        │
│                  │ 4. 返回预竞价出价                  │        │
│                  └─────────────────────────────────┘        │
│  10.0-15.0         Header Bidding 完成                      5ms  │
│                  ┌─────────────────────────────────┐        │
│                  │ 确定底价 (Highest Pre-bid):       │        │
│                  │ Floor = max(prebid_1, ..., prebid_N)│      │
│                  │ 将 Floor 注入 GAM                 │        │
│                  └─────────────────────────────────┘        │
│  15.0-18.0         GAM 处理 Bid Request                    3ms  │
│                  ┌─────────────────────────────────┐        │
│                  │ GAM 处理:                          │        │
│                  │ 1. 设置 Floor (从 Header Bid)      │        │
│                  │ 2. 查询 AdSense/AdX               │        │
│                  │ 3. 准备 Bid Request               │        │
│                  └─────────────────────────────────┘        │
│  18.0-20.0         Bid Request → Ad Exchange            2ms  │
│                  ┌─────────────────────────────────┐        │
│                  │ HTTP POST /open-auction          │        │
│                  │ Content-Type: application/json    │        │
│                  │ {                                │        │
│                  │   "id":"abc123",                 │        │
│                  │   "imp":[...],                   │        │
│                  │   "site":{...},                  │        │
│                  │   "device":{...},                │        │
│                  │   "at":1,                        │        │
│                  │   "tmax":80,                     │        │
│                  │   "source":{                     │        │
│                  │     "tid":"...",                 │        │
│                  │     "fd":1                       │        │
│                  │   },                             │        │
│                  │   "ext":{                        │        │
│                  │     "prebid":{...}               │        │
│                  │   }                              │        │
│                  │ }                                │        │
│                  └─────────────────────────────────┘        │
│  20.0-25.0         Ad Exchange 路由                       5ms  │
│                  ┌─────────────────────────────────┐        │
│                  │ Ad Exchange 处理:                  │        │
│                  │ 1. 验证 Bid Request               │        │
│                  │ 2. 查找注册的 DSP                 │        │
│                  │ 3. 广播给所有 DSP                 │        │
│                  │ 4. 设置超时定时器 (80ms)          │        │
│                  └─────────────────────────────────┘        │
│  25.0-75.0         DSP 竞价计算 (50ms 预算)               50ms │
│                  ┌─────────────────────────────────┐        │
│                  │ DSP 核心竞价循环:                   │        │
│                  │                                     │        │
│                  │ T+0ms:   接收 Bid Request           │        │
│                  │ T+2ms:   提取 user.id/ifa           │        │
│                  │ T+5ms:   查询用户画像缓存 (Redis)   │        │
│                  │ T+8ms:   提取广告位信息 (imp)       │        │
│                  │ T+10ms:  查询创意库 (SSD)           │        │
│                  │ T+12ms:  计算 pCTR 模型推理         │        │
│                  │ T+18ms:  计算 pCVR 模型推理         │        │
│                  │ T+22ms:  计算 Optimal Bid           │        │
│                  │ T+25ms:  检查预算                    │        │
│                  │ T+27ms:  检查频次                    │        │
│                  │ T+28ms:  构建 Bid Response          │        │
│                  │ T+30ms:  发送 Bid Response          │        │
│                  └─────────────────────────────────┘        │
│  75.0-80.0         Ad Exchange 收集结果                    5ms  │
│                  ┌─────────────────────────────────┐        │
│                  │ Ad Exchange 竞价决策:              │        │
│                  │ 1. 收集所有 Bid Response          │        │
│                  │ 2. 按出价排序                      │        │
│                  │ 3. 确定中标者                       │        │
│                  │ 4. 计算支付价格                    │        │
│                  │    First Price: winner_bid        │        │
│                  │    Second Price: 2nd_bid + tick   │        │
│                  │ 5. 返回中标广告                     │        │
│                  └─────────────────────────────────┘        │
│  80.0-85.0         Ad Exchange → SSP                   5ms  │
│  85.0-90.0         SSP → Publisher                    5ms  │
│  90.0-95.0         广告 HTML/CSS/JS 注入页面           5ms  │
│  95.0-100.0        广告渲染完成                         5ms  │
│  100.0+           追踪回调 (不阻塞页面)                async  │
│                  ┌─────────────────────────────────┐        │
│                  │ 追踪回调:                          │        │
│                  │ • Impression URL (展示)           │        │
│                  │ • Click URL (点击)                │        │
│                  │ • Viewability URL (可见性)         │        │
│                  └─────────────────────────────────┘        │
│                                                                      │
│  总延迟: ~100ms                                                      │
│  预算分配:                                                           │
│  ├── Publisher/SSP: ~15ms (15%)                                     │
│  ├── Ad Exchange: ~8ms (8%)                                          │
│  ├── DSP 计算: ~50ms (50%) ← 核心瓶颈                                │
│  └─ 传输: ~27ms (27%)                                                 │
└──────────────────────────────────────────────────────────────────────┘
```

### 1.2 Bid Request 完整结构 (OpenRTB 2.6)

```
OpenRTB 2.6 Bid Request — 完整字段:

{
  "id": "req_123456789012345678901234567890ab",  // UUID v4
  "tmax": 80,  // 最大响应时间 (ms)
  "at": 1,  // 竞价类型: 1=FirstPrice, 2=SecondPrice
  
  "imp": [  // 广告位列表 (可能多个)
    {
      "id": "imp_001",
      "secure": 1,  // 要求 HTTPS
      "banner": {
        "w": 300,
        "h": 250,
        "wmax": 300,  // 最大宽
        "hmax": 250,  // 最大高
        "wmin": 200,  // 最小宽
        "hmin": 100,  // 最小高
        "btype": ["banner"],  // 广告类型
        "bmode": ["graphic"],  // 广告模式
        "pos": 1,  // 广告位置: AboveFold=1, BelowFold=2
        "topframe": 1,  // 是否在顶层
        "instl": 0,  // 是否插屏
        "api": [1, 2, 3],  // API框架: VPAID=2
        "mimes": ["image/jpeg", "image/png", "text/html"],
        "battr": [1, 2, 3, 4],  // 禁止的创意属性
        "expdir": [1, 2, 3, 4],  // 允许的扩展方向
        "quartile": 1  // 广告位置：1=左上, 2=右上, 3=左下, 4=右下
      },
      "instl": 0,  // 插屏: 0=否, 1=是
      "tagid": "banner_300x250_top",
      "bidfloor": 1.50,  // 底价 (从 Header Bidding 注入)
      "bidfloorcur": "USD",
      "video": {  // 视频广告位
        "w": 640,
        "h": 360,
        "mimes": ["video/mp4", "video/webm"],
        "protocols": [2, 3, 5, 6, 7, 8],
        "startdelay": 1,  // 开始延迟
        "maxduration": 30,
        "linearity": 1,
        "skipmin": 5,  // 可跳过前的秒数
        "skipafter": 5,
        "playbackend": 1,  // 播放后端
        "placement": 1  // placement 类型
      },
      "audio": {  // 音频广告位
        "mimes": ["audio/mp3"],
        "maxduration": 30
      },
      "native": {  // 原生广告
        "request": "{\"assets\":[...]}",
        "api": [1, 2]
      },
      "pmp": {  // Private Marketplace
        "private_auction": 1,
        "deals": [
          {
            "id": "deal_001",
            "bidfloor": 2.00,
            "bidfloorcur": "USD",
            "wadspartner": 1,
            "at": 2
          }
        ]
      }
    }
  ],
  
  "site": {  // 网站 (APP 用 app 字段)
    "id": "site_12345",
    "name": "Example News Site",
    "domain": "example.com",
    "page": "https://example.com/article/12345",
    "ref": "https://www.google.com",
    "search": "best wireless headphones",  // 搜索词
    "cat": ["IAB19", "IAB19-1"],
    "sectioncat": ["IAB19-1"],
    "pagecat": ["IAB19"],
    "privacypolicy": 1,
    "publisher": {
      "id": "pub_12345",
      "name": "Example Publisher",
      "domain": "example.com"
    },
    "content": {
      "id": "content_123",
      "title": "Article Title",
      "language": "en",
      "category": "Technology",
      "rating": "G",
      "prodrank": "Medium"
    },
    "ext": {
      "data": {
        "segments": ["A12", "B34", "C56"]
      }
    }
  },
  
  "app": {  // APP (与 site 互斥)
    "id": "com.example.app",
    "name": "Example App",
    "bundle": "com.example.app",
    "domain": "example.com",
    "cat": ["IAB18"],
    "sections": ["social", "messaging"],
    "storeurl": "https://play.google.com/store/apps/details?id=...",
    "webview": 1,  // WebView
    "paid": 0,
    "publisher": {
      "id": "app_pub_123",
      "name": "App Publisher"
    },
    "content": {
      "episode": 1,
      "season": 1,
      "series": "My Show"
    },
    "ext": {
      "data": {
        "segments": ["A12", "B34"]
      }
    }
  },
  
  "device": {
    "ua": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15...",
    "ip": "192.0.2.1",
    "ifa": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",  // IDFV/AAID
    "make": "Apple",
    "model": "iPhone 15 Pro",
    "os": "iOS",
    "osv": "17.0",
    "h": 844,  // 屏幕高度
    "w": 390,  // 屏幕宽度
    "dpi": 460,
    "pxratio": 3.0,  // 像素比率
    "fls": 120,  // 刷新率 (Hz)
    "connectiontype": 1,  // 0=Unknown, 1=Ethernet, 2=WIFI, 3=Cellular4G, 4=Cellular5G
    "carrier": "Verizon",
    "language": "en",
    "country": "US",
    "dnt": 0,  // Do Not Track
    "lmt": 0,  // Limit Ad Tracking
    "js": 1,  // JavaScript enabled
    "devicetype": 1,  // 1=Mobile, 2=Desktop, 3=Tablet
    "geofetch": 2  // Geofetch method: 1=None, 2=IP, 3=GPS
  },
  
  "user": {
    "id": "user_12345678",  // 一方用户 ID
    "buyeruid": "dsp_user_12345",  // DSP 内部用户 ID
    "yob": 1990,  // 出生年份
    "gender": "m",  // m/f/n
    "ext": {
      "segments": ["A12", "B34", "C56"],  // 来自 DMP 的标签
      "consent": {
        "gdpr": 1,  // GDPR 适用
        "consent": "CO_xxxxxxxxxxxxxx"  // TCF Consent String
      }
    }
  },
  
  "regs": {  // 法规控制
    "ext": {
      "gdpr": 1,  // 1=GDPR 适用
      "us_privacy": "1YNN"  // CCPA US Privacy String
    }
  },
  
  "source": {  // 请求来源
    "tid": "trace_id_123456789012345678901234567890ab",  // 追踪 ID
    "fd": 1,  // 是否从外部源
    "ext": {
      "riid": "request_id_12345"  // 请求 ID
    }
  },
  
  "ext": {  // 扩展
    "prebid": {
      "bidders": ["appnexus", "rubicon", "indexexchange", "sovrn"],
      "cache": {
        "vastxml": true,
        "bids": true
      },
      "targeting": {
        "includewinners": true,
        "includebidderkeys": true
      }
    },
    "schain": {  // Supply Chain
      "ver": "1.0",
      "complete": 1,
      "nodes": [
        {
          "asi": "example.com",
          "sid": "00000000-0000-0000-0000-000000000001",
          "hp": 1
        },
        {
          "asi": "ssp.example.com",
          "sid": "00000000-0000-0000-0000-000000000002",
          "hp": 1,
          "rid": "bid-request-id",
          "dt": 1234567890
        }
      ]
    },
    "auction_delay": 0,
    "deal_priority": true
  }
}
```

---

## 第二部分：Bid Response 完整结构

### 2.1 Bid Response 格式

```
OpenRTB Bid Response — 完整结构:

{
  "id": "req_123456789012345678901234567890ab",  // 匹配 Bid Request ID
  "seatbid": [  // 出价列表
    {
      "seat": "dsp_001",  // DSP 标识
      "bid": [
        {
          "id": "bid_123456789012345678901234567890ab",  // 出价 ID
          "impid": "imp_001",  // 对应广告位
          "price": 2.50,  // 出价 (CPM/CPC)
          "nurl": "https://dsp.com/win_notice?bid_id=...",  // 中标通知 (未赢时)
          "lurl": "https://dsp.com/loss_notice?bid_id=...",  // 未中标通知
          "burl": "https://dsp.com/click?bid_id=...",  // 点击通知
          "durl": "https://dsp.com/impression?bid_id=...",  // 展示通知
          "adm": "<html>...</html>",  // 广告 HTML/JS
          "adid": "ad_123456",  // 广告 ID
          "adomain": ["example.com", "example2.com"],  // 广告主域名
          "iurl": "https://dsp.com/click_tracking",  // 点击追踪
          "cid": "campaign_001",  // 广告系列 ID
          "crid": "creative_001",  // 创意 ID
          "cat": ["IAB19"],  // 分类
          "attr": [1, 2, 3],  // 广告属性: 1=RichMedia, 2=Video, ...
          "api": 2,  // API框架: 2=VPAID
          "mimes": ["text/html"],
          "w": 300,  // 宽
          "h": 250,  // 高
          "rid": "bid_123",  // 重复出价 ID
          "exp": 50,  // 广告过期时间 (秒)
          "dealid": "deal_001",  // 如果有 Deal
          "qag_mediarating": 5,  // 媒体评级
          "qag_verification": "https://verification.com",  // 验证 URL
          "wr": 0.8,  // 权重 (用于排序)
          "bundle": "com.example.app",
          "language": "en",
          "languagev2": "en-US",
          "ext": {
            "prebid": {
              "type": "html",
              "cache": {
                "keys": "key1=key1&key2=key2"
              }
            },
            "bidder": {
              "duration": 30,
              "network_id": 12345
            }
          }
        }
      ],
      "group": 0  // 0=正常, 1=互斥 (至少一个)
    }
  ],
  "cur": "USD",
  "nurl": "https://dsp.com/nurl",  // 未中标通知
  "bidid": "bid_id_12345",  // 出价 ID (用于追踪)
  "adid": "ad_123456",  // 广告 ID
  "ext": {
    "prebid": {
      "auctiontimestamp": 1234567890000,
      "generatesbid": true
    }
  }
}
```

---

## 第三部分：RTA (Real-Time API) 深度解析

### 3.1 RTA vs RTB 对比

```
RTA (Real-Time API) 是替代 RTB 的新范式:

┌──────────────────────────────────────────────────────────────┐
│              RTB vs RTA 对比                                   │
│                                                              │
│  RTB (Real-Time Bidding):                                    │
│  ├── 流程: SSP → Ad Exchange → DSP → 出价 → 中标 → 返回广告  │
│  ├── 问题:                                                   │
│  │   ├── DSP 在竞价时才决定，无法访问用户数据 (隐私)          │
│  │   ├── 竞价时没有上下文，pCVR 不准                          │
│  │   ├── 无法控制展示 (一旦中标必须展示)                       │
│  │   └─ 数据泄露: Bid Request 暴露用户 ID/IP                 │
│  └─ 隐私问题严重 (Cookie/IFA 泄露)                            │
│                                                              │
│  RTA (Real-Time API) / RTA:                                 │
│  ├── 流程: SSP → Ad Exchange → RTA API → DSP 决策 → 白名单  │
│  ├── 优势:                                                   │
│  │   ├── DSP 先决策，再决定是否参与竞价                       │
│  │   ├── 可以访问一方用户数据 (一方 ID 不在 Bid Request 中)   │
│  │   ├── 更精准的准入控制 (Filter-in, 而非 Filter-out)       │
│  │   └─ 减少 Bid Request 暴露的隐私数据                        │
│  └─ 核心: "先筛选，再竞价"                                    │
│                                                              │
│  RTA 流程:                                                   │
│  1. SSP 有 Bid Request                                       │
│  2. SSP 调用 RTA API: POST /rta/decide                       │
│     body: {                                                  │
│       "user_ids": ["user_123", "cookie_456"],                 │
│       "imp_ids": ["imp_001"],                                │
│       "ad_formats": ["banner", "video"]                      │
│     }                                                       │
│  3. DSP 决策: 白名单/黑名单                                   │
│     response: {                                              │
│       "user_ids": ["user_123", "cookie_456"],                │
│       "decisions": [                                        │
│         {"user_id": "user_123", "decision": "pass"},  // 参与竞价
│         {"user_id": "cookie_456", "decision": "block"}  // 不参与
│       ]                                                      │
│     }                                                       │
│  4. 根据决策，SSP 决定是否继续竞价流程                        │
│  5. 如果 pass → 正常 RTB 流程                                │
│  6. 如果 block → 跳过该用户/广告位                            │
└──────────────────────────────────────────────────────────────┘
```

### 3.2 RTA 系统设计

```
RTA 系统设计:

架构:
┌──────────────────────────────────────────────────────────────┐
│                  RTA 架构                                      │
│                                                              │
│  SSP (发布商侧)                                               │
│  ├── 1. 收到 Bid Request                                      │
│  ├── 2. 提取用户 ID (Cookie/IFA/Email)                       │
│  ├── 3. 并行调用 RTA API (多个 DSP)                          │
│  │   ├── POST /dsp1/rta/decide                               │
│  │   ├── POST /dsp2/rta/decide                               │
│  │   └─ POST /dsp3/rta/decide                               │
│  ├── 4. 收集 RTA 响应 (超时: 20ms)                           │
│  ├── 5. 根据 RTA 决策过滤                                     │
│  │   ├── block → 不参与竞价                                   │
│  │   └─ pass → 正常竞价                                       │
│  └─ 6. 继续 RTB 流程                                          │
│                                                              │
│  RTA API (DSP 侧)                                             │
│  ├── POST /rta/decide                                         │
│  │   body: {                                                  │
│  │     "user_ids": ["u1", "u2", "u3"],                       │
│  │     "imp_ids": ["i1", "i2"],                              │
│  │     "ad_formats": ["banner"],                              │
│  │     "site": {...},                                         │
│  │     "app": {...}                                           │
│  │   }                                                       │
│  │                                                           │
│  │   response: {                                              │
│  │     "user_ids": ["u1", "u2", "u3"],                       │
│  │     "decisions": [                                        │
│  │       {"user_id": "u1", "decision": "pass"},              │
│  │       {"user_id": "u2", "decision": "block"},             │
│  │       {"user_id": "u3", "decision": "pass"}               │
│  │     ]                                                      │
│  │   }                                                       │
│  └─ POST /rta/register (注册 RTA 端点)                       │
│                                                              │
│  超时处理:                                                   │
│  ├── RTA API 超时 (20ms): 视为 pass (参与竞价)                 │
│  ├── 超时保护: 熔断 (Circuit Breaker)                         │
│  └─ 降级: 不使用 RTA，回到传统 RTB                             │
│                                                              │
│  性能要求:                                                   │
│  ├── P99 延迟: < 20ms                                       │
│  ├── 可用性: 99.99%                                         │
│  ├── 吞吐量: 100K+ QPS (每个 DSP)                            │
│  └─ 缓存: LRU Cache (用户 ID → 决策)                         │
└──────────────────────────────────────────────────────────────┘
```

---

## 第四部分：DSP 竞价引擎核心

### 4.1 竞价引擎代码实现

```python
"""
DSP 竞价引擎核心实现
实时处理 Bid Request，返回 Bid Response
"""

import time
import numpy as np
import torch
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

@dataclass
class BidRequest:
    """Bid Request 数据"""
    request_id: str
    imp_id: str
    user_id: Optional[str]
    ifa: Optional[str]
    cookie: Optional[str]
    ip: str
    ua: str
    device_make: str
    device_model: str
    os: str
    os_version: str
    ad_format: str  # banner/video/native
    ad_width: int
    ad_height: int
    page_url: Optional[str]
    page_category: List[str]
    search_query: Optional[str]
    geo_country: str
    geo_city: str
    placement_type: str  # toprank/midrank/restofsearch
    floor_price: float
    currency: str
    is_privacy_sensitive: bool  # GDPR/CCPA

@dataclass
class BidResponse:
    """Bid Response 数据"""
    bid_id: str
    imp_id: str
    price: float  # CPM
    ad_id: str
    ad_html: str
    adomain: List[str]
    cid: str
    crid: str
    w: int
    h: int
    click_url: str
    impression_url: str

class BidEngine:
    """
    DSP 竞价引擎 — 核心竞价逻辑
    """
    
    def __init__(
        self,
        pctr_model: torch.nn.Module,  # pCTR 模型
        pcvr_model: torch.nn.Module,  # pCVR 模型
        bid_optimizer: 'BidOptimizer',  # 出价优化器
        user_cache: 'UserCache',  # 用户缓存
        creative_cache: 'CreativeCache',  # 创意缓存
        budget_manager: 'BudgetManager',  # 预算管理
        frequency_capper: 'FrequencyCapper',  # 频次控制
        latency_budget_ms: float = 50.0,  # 延迟预算 (ms)
    ):
        self.pctr_model = pctr_model
        self.pcvr_model = pcvr_model
        self.bid_optimizer = bid_optimizer
        self.user_cache = user_cache
        self.creative_cache = creative_cache
        self.budget_manager = budget_manager
        self.frequency_capper = frequency_capper
        self.latency_budget_ms = latency_budget_ms
        
        # 性能监控
        self.stats = {
            'total_requests': 0,
            'total_wins': 0,
            'total_spent': 0.0,
            'avg_latency_ms': 0.0,
            'p99_latency_ms': 0.0,
        }
    
    def bid(
        self,
        bid_request: BidRequest,
        campaign: 'Campaign',  # 广告系列配置
    ) -> Optional[BidResponse]:
        """
        主竞价函数 — 接收 Bid Request，返回 Bid Response (或 None)
        
        核心流程:
        1. 解析 Bid Request (~2ms)
        2. 查询用户画像 (~3ms)
        3. 获取候选创意 (~2ms)
        4. 计算 pCTR (~6ms)
        5. 计算 pCVR (~6ms)
        6. 计算最优出价 (~2ms)
        7. 预算检查 (~1ms)
        8. 频次检查 (~1ms)
        9. 构建 Bid Response (~1ms)
        
        总延迟: ~24ms (在 50ms 预算内)
        """
        start_time = time.perf_counter()
        self.stats['total_requests'] += 1
        
        # Step 1: 解析 Bid Request (~2ms)
        features = self._extract_features(bid_request, campaign)
        
        # Step 2: 查询用户画像 (~3ms)
        user_features = self._query_user_features(bid_request, features)
        
        # Step 3: 获取候选创意 (~2ms)
        candidate_creatives = self._get_candidate_creatives(
            bid_request, features, user_features
        )
        
        if not candidate_creatives:
            return None  # 无合适创意
        
        # Step 4: 计算 pCTR (~6ms)
        pctr = self._compute_pctr(features, user_features, candidate_creatives)
        
        # Step 5: 计算 pCVR (~6ms)
        pcvr = self._compute_pcvr(features, user_features, candidate_creatives)
        
        # Step 6: 计算最优出价 (~2ms)
        optimal_bid = self._compute_optimal_bid(
            pctr, pcvr, bid_request.floor_price, campaign
        )
        
        if optimal_bid < bid_request.floor_price:
            return None  # 出价低于底价
        
        # Step 7: 预算检查 (~1ms)
        if not self.budget_manager.has_budget(campaign.id, optimal_bid):
            return None
        
        # Step 8: 频次检查 (~1ms)
        if self.frequency_capper.is_exceeded(bid_request.user_id, campaign.id):
            return None
        
        # Step 9: 构建 Bid Response (~1ms)
        creative = candidate_creatives[0]  # 选择最佳创意
        bid_response = self._build_bid_response(
            bid_request, creative, optimal_bid, campaign
        )
        
        # 更新统计
        end_time = time.perf_counter()
        latency_ms = (end_time - start_time) * 1000
        self._update_stats(latency_ms, optimal_bid)
        
        return bid_response
    
    def _extract_features(
        self,
        bid_request: BidRequest,
        campaign: 'Campaign',
    ) -> Dict[str, float]:
        """
        从 Bid Request 提取特征
        数值化 + 嵌入
        
        特征维度: ~500 维
        """
        features = {}
        
        # 用户特征
        features['user_age_bucket'] = self._age_bucket(bid_request.os_version)
        features['user_gender'] = 0.5  # 默认
        
        # 设备特征
        features['is_mobile'] = 1.0 if bid_request.device_make == 'Apple' else 0.0
        features['os_version_float'] = float(bid_request.os_version.split('.')[0])
        features['ad_width'] = bid_request.ad_width
        features['ad_height'] = bid_request.ad_height
        features['is_privacy_sensitive'] = 1.0 if bid_request.is_privacy_sensitive else 0.0
        
        # 上下文特征
        features['page_has_search'] = 1.0 if bid_request.search_query else 0.0
        features['is_toprack'] = 1.0 if bid_request.placement_type == 'toprank' else 0.0
        features['is_midrank'] = 1.0 if bid_request.placement_type == 'midrank' else 0.0
        features['is_restofsearch'] = 1.0 if bid_request.placement_type == 'restofsearch' else 0.0
        
        # 类别嵌入 (Category Embedding)
        features['category_embed'] = self._encode_category(bid_request.page_category)
        
        # 搜索词嵌入
        if bid_request.search_query:
            features['search_query_embed'] = self._encode_query(bid_request.search_query)
        
        return features
    
    def _compute_pctr(
        self,
        features: Dict[str, float],
        user_features: Dict[str, float],
        creative: 'Creative',
    ) -> float:
        """
        pCTR 模型推理
        
        模型架构:
        ┌─────────────────────────────────────────┐
        │  Input: 500-dim features                 │
        │  ├─ Embedding Layers (user/category/query)│
        │  ├─ Feature Cross (FM/DNN)              │
        │  ├─ Deep Network (3 layers)              │
        │  └─ Sigmoid Output                      │
        │                                          │
        │  PCTR = sigmoid(W2 · ReLU(W1 · x + b1) + c1)
        │                                          │
        │  推理延迟: ~6ms (GPU/CPU)                │
        └─────────────────────────────────────────┘
        """
        # 合并特征
        inputs = self._merge_features(features, user_features, creative)
        
        # 模型推理 (GPU for <5ms, CPU for <10ms)
        with torch.no_grad():
            inputs_tensor = torch.FloatTensor(inputs).unsqueeze(0)
            logits = self.pctr_model(inputs_tensor)
            pctr = torch.sigmoid(logits).item()
        
        # 平滑: 避免极端值
        pctr = np.clip(pctr, 0.0001, 0.9999)
        
        return float(pctr)
    
    def _compute_pcvr(
        self,
        features: Dict[str, float],
        user_features: Dict[str, float],
        creative: 'Creative',
    ) -> float:
        """
        pCVR 模型推理
        
        模型架构:
        ┌─────────────────────────────────────────┐
        │  Input: 500-dim features                 │
        │  ├─ Embedding Layers                    │
        │  ├─ DeepFM (FM for low-count features) │
        │  ├─ DNN (3 hidden layers)               │
        │  └─ Sigmoid Output                      │
        │                                          │
        │  PCVR = sigmoid(W3 · ReLU(W2 · ReLU(W1 · x) + b2) + c2)│
        │                                          │
        │  注意: CVR 稀疏 → 使用 ESMM 框架           │
        │  P(CTR×CVR) = P(CTR) × P(CVR|CTR)       │
        └─────────────────────────────────────────┘
        
        推理延迟: ~6ms
        """
        inputs = self._merge_features(features, user_features, creative)
        
        with torch.no_grad():
            inputs_tensor = torch.FloatTensor(inputs).unsqueeze(0)
            # 使用 ESMM: P(CVR) = P(CTCVR) / P(CTR)
            pctr_pred = self.pcvr_model.ctcvr_layer(inputs_tensor)
            # CTCVR 直接输出 CVR
            pcvr = torch.sigmoid(pcvr_pred).item()
        
        pcvr = np.clip(pcvr, 0.0001, 0.9999)
        return float(pcvr)
    
    def _compute_optimal_bid(
        self,
        pctr: float,
        pcvr: float,
        floor_price: float,
        campaign: 'Campaign',
    ) -> float:
        """
        计算最优出价
        
        公式:
        ─────────────────────────────────────────────
        Optimal Bid = pCTR × pCVR × Target CPA × β × pacing_factor
        
        或 (对于 CPM):
        Optimal CPM = pCTR × pCVR × 1000 × β × pacing_factor
        
        其中:
        ├── pCTR: 预估点击率
        ├── pCVR: 预估转化率
        ├── Target CPA: 目标每次转化成本 (来自 campaign)
        ├── β: Bid Shading 因子 (学习得到)
        └─ pacing_factor: 预算消耗速率控制 (0.5-1.5)
        ─────────────────────────────────────────────
        """
        target_cpa = campaign.target_cpa
        bid_shading = campaign.bid_shading or 0.85
        pacing_factor = self.budget_manager.get_pacing_factor(
            campaign.id, time.time()
        )
        
        # 计算期望转化成本: pCTR × pCVR × Target CPA
        expected_cpa = pctr * pcvr * target_cpa
        bid = expected_cpa * bid_shading * pacing_factor
        
        # 确保不低于底价
        bid = max(bid, floor_price)
        
        return float(bid)
    
    def _build_bid_response(
        self,
        bid_request: BidRequest,
        creative: 'Creative',
        bid_price: float,
        campaign: 'Campaign',
    ) -> BidResponse:
        """构建 Bid Response"""
        return BidResponse(
            bid_id=f"bid_{bid_request.request_id}_{creative.id}",
            imp_id=bid_request.imp_id,
            price=bid_price,
            ad_id=creative.id,
            ad_html=creative.html,
            adomain=[creative.adomain],
            cid=campaign.id,
            crid=creative.id,
            w=creative.width,
            h=creative.height,
            click_url=f"https://track.dsp.com/c/{creative.id}?click_id={bid_request.request_id}",
            impression_url=f"https://track.dsp.com/i/{creative.id}?bid_id={bid_request.request_id}",
        )
    
    def _update_stats(self, latency_ms: float, bid: float):
        """更新性能统计"""
        if bid > 0:  # 假设中标
            self.stats['total_wins'] += 1
            self.stats['total_spent'] += bid * 0.3  # 估算花费
        # 更新延迟统计 (指数加权平均)
        alpha = 0.1
        self.stats['avg_latency_ms'] = (
            (1 - alpha) * self.stats['avg_latency_ms'] + alpha * latency_ms
        )
```

### 4.2 Go 实现：RTB Bid Request/Response 解析器

```go
// BidRequest represents an OpenRTB 2.5 Bid Request.
// Structured for zero-allocation parsing in hot path.
package rtb

import (
	"encoding/json"
	"fmt"
	"time"
)

// Impression defines a single ad impression in a bid request.
type Impression struct {
	ID            string   `json:"id"`
	Width         int      `json:"w"`
	Height        int      `json:"h"`
	AdPos         string   `json:"pos,omitempty"` // 0=below-fold, 1=above-fold
	BatMin        int      `json:"bat_min"`       // battery
	DevID         string   `json:"devicetype"`
	Make          string   `json:"make"`
	Model         string   `json:"model"`
	OS            string   `json:"os"`
	OSVer         string   `json:"osv"`
	DeviceIP      string   `json:"ip,omitempty"`
	UserAgent     string   `json:"ua"`
	IFAVendor     string   `json:"ifa_vendor,omitempty"`
	IFAValue      string   `json:"ifa,omitempty"`
	Cookie        string   `json:"coppa,omitempty"`
	Page          string   `json:"page,omitempty"`
	Categories    []string `json:"cat,omitempty"`
	TopFrame      int      `json:"tfu,omitempty"` // top frame
	Secure        int      `json:"secure"`        // 1=HTTPS
	MIMEs         []string `json:"mimes"`
	Formats       []struct{ W int `json:"w"` H int `json:"h"` } `json:"format,omitempty"`
}

// Device carries device-level context.
type Device struct {
	IP      string `json:"ip,omitempty"`
	UA      string `json:"ua,omitempty"`
	Make    string `json:"make,omitempty"`
	Model   string `json:"model,omitempty"`
	OS      string `json:"os,omitempty"`
	OSVer   string `json:"osv,omitempty"`
	DevType int    `json:"dtype,omitempty"` // 0=unknown,1=mobile,2=desktop,3=tablet
	ConnectionType string `json:"connectiontype,omitempty"` // 0=unknown,1=eth,2=wifi,3=cellular
}

// User carries user-level signals.
type User struct {
	ID   string   `json:"id,omitempty"`
	BuyerUID string `json:"buyeruid,omitempty"`
	Gender string   `json:"gender,omitempty"`
	YearBr int     `json:"yob,omitempty"`
	KW     []string `json:"kw,omitempty"`
}

// BidRequest wraps the top-level OpenRTB envelope.
type BidRequest struct {
	ID             string     `json:"id"`
	Imp            []Impression `json:"imp"`
	Device         *Device    `json:"device,omitempty"`
	User           *User      `json:"user,omitempty"`
	Site           *Site      `json:"site,omitempty"`
	App            *App       `json:"app,omitempty"`
	Sregs          Registry   `json:"sregs,omitempty"` // seller params
	Uregs          Registry   `json:"uregs,omitempty"` // user params
	at             int        `json:"at"`              // auction type: 1=first, 2=second
	bidfloor       float64    `json:"bidfloor"`
	bidfloorcur    string     `json:"bidfloorcur"` // ISO 4217
	Test           int        `json:"test"`
	TMax           int        `json:"tmax"`      // time budget in ms
	SupplyChain    *SupplyChain `json:"supplychain,omitempty"`
}

// Registry stores seller/user regulatory signals.
type Registry map[string]string

// SupplyChain follows IAB Tech Lab spec.
type SupplyChain struct {
	Version    string   `json:"ver"`
	Complete   int      `json:"complete"`
	Nodes      []SCNode `json:"nodes"`
}

// SCNode is one hop in the supply chain.
type SCNode struct {
	ASI   string `json:"asi"`
	SID   string `json:"sid"`
	HPID  string `json:"hp"`
	T     int64  `json:"t"`
}

// ParseBidRequest deserializes raw JSON into BidRequest with validation.
func ParseBidRequest(raw []byte) (*BidRequest, error) {
	var req BidRequest
	if err := json.Unmarshal(raw, &req); err != nil {
		return nil, fmt.Errorf("parse bid request: %w", err)
	}
	if req.ID == "" {
		return nil, fmt.Errorf("missing bid request id")
	}
	if len(req.Imp) == 0 {
		return nil, fmt.Errorf("no impressions in request")
	}
	for i := range req.Imp {
		if req.Imp[i].ID == "" {
			return nil, fmt.Errorf("impression %d missing id", i)
		}
	}
	return &req, nil
}

// BidResponse is the DSP's reply per OpenRTB spec.
type BidResponse struct {
	ID      string    `json:"id"`
	BidID   string    `json:"bidid,omitempty"`
	BID     []Bid     `json:"bid"`
	AP      int       `json:"ap,omitempty"` // auction type override
	SeatBid []SeatBid `json:"seatbid,omitempty"`
}

// SeatBid groups bids for a single seat (DSP).
type SeatBid struct {
	Bid     []Bid   `json:"bid"`
	Seat    string  `json:"seat"`
	Group   int     `json:"group,omitempty"` // 0=not grouped
}

// Bid represents a single bid line item.
type Bid struct {
	ID         string  `json:"id"`
	ImpID      string  `json:"impid"`
	Price      float64 `json:"price"`
	AdID       string  `json:"adid,omitempty"`
	Crust      string  `json:"crid,omitempty"`
	NURL       string  `json:"nurl,omitempty"` // win notice URL
	BURL       string  `json:"burl,omitempty"` // loss notification URL
	LURL       string  `json:"lurl,omitempty"` // loss callback URL
	Adomain    []string `json:"adomain,omitempty"`
	MIME       string  `json:"mime,omitempty"`
	Cat        []string `json:"cat,omitempty"`
	Attr       []int   `json:"attr,omitempty"`
	QA         []string `json:"qa,omitempty"`
	Deals      []string `json:"deals,omitempty"`
	Ext        json.RawMessage `json:"ext,omitempty"`
}

// BuildBidResponse constructs a valid OpenRTB bid response.
func BuildBidResponse(reqID, bidID, impID string, price float64, adID string) BidResponse {
	return BidResponse{
		ID:    reqID,
		BidID: bidID,
		BID: []Bid{{
			ID:      bidID,
			ImpID:   impID,
			Price:   price,
			AdID:    adID,
			NURL:    fmt.Sprintf("https://track.dsp.com/win/%s", bidID),
			BURL:    fmt.Sprintf("https://track.dsp.com/loss/%s", bidID),
		}},
	}
}
```

#### Go 实现：竞价引擎核心

```go
// BidEngine is the core decision loop for a DSP.
// Every incoming BidRequest flows through BidEngine.Bid()
// with a hard latency budget (typically 50ms).
package rtb

import (
	"context"
	"fmt"
	"sync"
	"time"
)

// FeatureVector holds the flattened feature representation used by models.
type FeatureVector map[string]float64

// CandidateCreative is a winning creative from the creative cache.
type CandidateCreative struct {
	AdID      string
	HTML      string
	ClickURL  string
	Width     int
	Height    int
	MIME      string
	Adomain   []string
	CTRScore  float64
	CVRScore  float64
}

// BudgetManager tracks per-campaign daily budgets and pacing.
type BudgetManager interface {
	HasBudget(campaignID string, amount float64) bool
	GetPacingFactor(campaignID string, now time.Time) float64
	Reserve(campaignID string, amount float64) error
}

// FrequencyCapper limits ad exposure per user per window.
type FrequencyCapper interface {
	IsExceeded(userID, campaignID string, window time.Duration) bool
	Record(userID, campaignID string)
}

// PCTRModel predicts click probability.
type PCTRModel interface {
	Predict(ctx context.Context, features FeatureVector) (float64, error)
}

// PCVRModel predicts conversion probability given a click.
type PCVRModel interface {
	Predict(ctx context.Context, features FeatureVector) (float64, error)
}

// CampaignConfig holds advertiser-side bidding parameters.
type CampaignConfig struct {
	ID          string
	Name        string
	TargetCPA   float64 // target cost-per-acquisition
	BidShading  float64 // learned shading factor, e.g. 0.85
	DailyBudget float64
	Status      string // active/paused/ended
}

// BidEngine orchestrates the full bid decision pipeline.
type BidEngine struct {
	pctrModel     PCTRModel
	pcvrModel     PCVRModel
	budgetMgr     BudgetManager
	freqCapper    FrequencyCapper
	creativeCache *CreativeCache // see below

	latencyBudget time.Duration
	shutdown      chan struct{}
	done          chan struct{}

	// stats
	mu            sync.Mutex
	totalReq      int64
	totalWin      int64
	totalSpent    float64
	latencies     []float64 // ring buffer, max 1024
}

// CreativeCache provides O(1) lookup for approved creatives.
type CreativeCache struct {
	data map[string]*CandidateCreative
}

func NewCreativeCache() *CreativeCache {
	return &CreativeCache{data: make(map[string]*CandidateCreative)}
}

func (c *CreativeCache) Get(adID string) (*CandidateCreative, bool) {
	v, ok := c.data[adID]
	return v, ok
}

func (c *CreativeCache) Put(cr *CandidateCreative) {
	c.data[cr.AdID] = cr
}

// NewBidEngine creates a configured engine.
func NewBidEngine(
	pctr PCTRModel,
	pcvr PCVRModel,
	budgetMgr BudgetManager,
	freqCapper FrequencyCapper,
	cache *CreativeCache,
	latencyBudget time.Duration,
) *BidEngine {
	return &BidEngine{
		pctrModel:     pctr,
		pcvrModel:     pcvr,
		budgetMgr:     budgetMgr,
		freqCapper:    freqCapper,
		creativeCache: cache,
		latencyBudget: latencyBudget,
		shutdown:      make(chan struct{}),
		done:          make(chan struct{}),
		latencies:     make([]float64, 0, 1024),
	}
}

// Bid is the main entry point. Called per incoming bid request.
// Returns nil when the engine decides not to bid.
func (e *BidEngine) Bid(
	ctx context.Context,
	req *BidRequest,
	campaign *CampaignConfig,
) (*BidResponse, error) {
	e.mu.Lock()
	e.totalReq++
	e.mu.Unlock()

	start := time.Now()

	// Hard deadline: abort if approaching latency budget.
	deadline := start.Add(e.latencyBudget)
	ctx, cancel := context.WithDeadline(ctx, deadline)
	defer cancel()

	// Step 1: Extract features (~2ms).
	features := e.extractFeatures(req, campaign)

	// Step 2: Query user features from Redis (~3ms, concurrent).
	userFeatures := e.queryUserFeatures(ctx, req)
	for k, v := range userFeatures {
		features[k] = v
	}

	// Step 3: Get candidate creative (~2ms).
	candidate := e.getCandidateCreative(req, features, campaign)
	if candidate == nil {
		return nil, nil
	}

	// Step 4: pCTR inference (~6ms).
	pctr, err := e.pctrModel.Predict(ctx, features)
	if err != nil || pctr <= 0 {
		return nil, nil
	}

	// Step 5: pCVR inference (~6ms).
	pcvr, err := e.pcvrModel.Predict(ctx, features)
	if err != nil || pcvr <= 0 {
		return nil, nil
	}

	// Step 6: Compute optimal bid (~1ms).
	optimalBid := e.computeOptimalBid(pctr, pcvr, req.bidfloor, campaign)
	if optimalBid < req.bidfloor {
		return nil, nil
	}

	// Step 7: Budget check (~1ms).
	if !e.budgetMgr.HasBudget(campaign.ID, optimalBid) {
		return nil, nil
	}

	// Step 8: Frequency cap (~1ms).
	userID := ""
	if req.User != nil {
		userID = req.User.ID
	}
	if userID == "" && req.User != nil {
		userID = req.User.BuyerUID
	}
	if userID != "" && e.freqCapper.IsExceeded(userID, campaign.ID, 24*time.Hour) {
		return nil, nil
	}

	// Step 9: Reserve budget (~1ms).
	if err := e.budgetMgr.Reserve(campaign.ID, optimalBid); err != nil {
		return nil, nil
	}

	// Step 10: Build response (~1ms).
	bidID := fmt.Sprintf("%s_%s_%d", req.ID, candidate.AdID, time.Now().UnixNano())
	resp := BuildBidResponse(req.ID, bidID, req.Imp[0].ID, optimalBid, candidate.AdID)

	latency := time.Since(start).Seconds() * 1000
	e.recordLatency(latency)

	e.mu.Lock()
	e.totalWin++
	e.totalSpent += optimalBid * 0.3
	e.mu.Unlock()

	return &resp, nil
}

// extractFeatures flattens a BidRequest into a numeric vector.
func (e *BidEngine) extractFeatures(req *BidRequest, camp *CampaignConfig) FeatureVector {
	f := make(FeatureVector, 64)
	if req.Device != nil {
		f["device_is_mobile"] = float64(req.Device.DevType)
		f["device_is_wifi"] = 1.0
	}
	for _, imp := range req.Imp {
		f["imp_width"] += float64(imp.Width)
		f["imp_height"] += float64(imp.Height)
	}
	f["floor_price"] = req.bidfloor
	f["auction_type"] = float64(req.at)
	return f
}

// queryUserFeatures fetches user-level signals from Redis.
func (e *BidEngine) queryUserFeatures(ctx context.Context, req *BidRequest) FeatureVector {
	f := make(FeatureVector, 32)
	// In production: redis.MGET(ctx, "user:profile:"+userID, ...)
	if req.User != nil {
		f["has_user_id"] = 1.0
	}
	return f
}

// getCandidateCreative selects the best creative for this impression.
func (e *BidEngine) getCandidateCreative(
	req *BidRequest,
	features FeatureVector,
	camp *CampaignConfig,
) *CandidateCreative {
	// In production: query creative DB by campaign ID, filter by adformat,
	// sort by historical CTR, pick top-1.
	// Here we simulate a cache lookup.
	// TODO: integrate with real creative retrieval service.
	return nil
}

// computeOptimalBid implements the core bidding formula.
func (e *BidEngine) computeOptimalBid(
	pctr, pcvr, floorPrice float64,
	camp *CampaignConfig,
) float64 {
	// Optimal Bid = pCTR × pCVR × Target CPA × β × pacing
	baseBid := pctr * pcvr * camp.TargetCPA
	shadedBid := baseBid * camp.BidShading
	return shadedBid
}

// recordLatency appends to a lock-free ring buffer.
func (e *BidEngine) recordLatency(ms float64) {
	e.mu.Lock()
	defer e.mu.Unlock()
	e.latencies = append(e.latencies, ms)
	if len(e.latencies) > 1024 {
		copy(e.latencies, e.latencies[1:])
		e.latencies = e.latencies[:1024]
	}
}

// Stats returns current engine metrics.
func (e *BidEngine) Stats() (totalReq, totalWin int64, avgLatency, p99Latency float64) {
	e.mu.Lock()
	defer e.mu.Unlock()
	totalReq = e.totalReq
	totalWin = e.totalWin
	if len(e.latencies) > 0 {
		sum := 0.0
		for _, l := range e.latencies {
			sum += l
		}
		avgLatency = sum / float64(len(e.latencies))
	}
	return
}
```

#### 特征工程详解

```
广告排序特征体系 (500+ 维):

┌──────────────────────────────────────────────────────────────┐
│              特征分类 (500+ 维)                                 │
│                                                              │
│  用户特征 (User Features): ~150 维                            │
│  ├── 人口统计: 年龄/性别/收入/教育 (20 维)                     │
│  ├── 行为: 历史点击/浏览/购买 (50 维, 嵌入后)                  │
│  ├── 兴趣: 兴趣标签 (30 维, embedding)                        │
│  ├── 设备: 品牌/型号/OS/网络 (30 维)                          │
│  └─ 上下文: 时间/位置/天气 (20 维)                            │
│                                                              │
│  查询特征 (Query Features): ~100 维                           │
│  ├── 搜索词: TF-IDF (50 维)                                  │
│  ├── 搜索词嵌入: BERT embedding (128 维 → 降维到 50 维)      │
│  ├── 意图分类: 商业/信息/导航 (3 维)                          │
│  └─ 热度: 搜索量/新鲜度 (5 维)                                │
│                                                              │
│  广告特征 (Ad Features): ~100 维                              │
│  ├── 广告文案: BERT embedding (50 维)                        │
│  ├── 广告类型: Search/Display/Video (3 维)                   │
│  ├── 历史表现: CTR/CVR/CPA (10 维)                           │
│  ├── 广告主: 质量分/历史表现 (10 维)                          │
│  └─ 创意: 尺寸/格式/类型 (10 维)                              │
│                                                              │
│  交叉特征 (Cross Features): ~100 维                           │
│  ├── Query × Ad: 语义相似度 (10 维)                          │
│  ├── Query × User: 用户兴趣匹配 (20 维)                       │
│  ├── Ad × User: 用户历史对该广告主的互动 (10 维)               │
│  ├── User × Context: 用户+上下文 (20 维)                      │
│  └─ Ad × Context: 广告+上下文 (10 维)                         │
│                                                              │
│  上下文特征 (Context Features): ~50 维                        │
│  ├── 页面: URL/内容/类别/广告数量 (20 维)                     │
│  ├── 时间: 小时/星期/季节 (5 维)                              │
│  ├── 位置: 城市/地区/国家 (15 维)                             │
│  └─ 网络: WiFi/4G/5G (5 维)                                  │
│                                                              │
│  特征存储 (Feature Store):                                   │
│  ├── 实时特征: Redis (用户画像/预算/频次)                     │
│  ├── 离线特征: HDFS/S3 (历史行为/统计)                       │
│  └─ 特征服务: Feast / Hopsworks (特征管理)                    │
└──────────────────────────────────────────────────────────────┘
```

---

## 第五部分：自测题

### 问题 1（基础）
RTB 竞价 100ms 中，DSP 计算占了多少时间？

<details>
<summary>查看答案</summary>

~50ms (50%)。这是核心瓶颈。
包含: 用户画像查询(~3ms), pCTR 推理(~6ms), pCVR 推理(~6ms), 出价计算(~2ms)
</details>

### 问题 2（基础）
OpenRTB 协议中 `at` 字段的含义是什么？1 和 2 分别代表什么？

<details>
<summary>查看答案</summary>

`at` = auction type（拍卖类型）
- 1 = First Price（第一价格竞价，胜出者支付自己出价）
- 2 = Second Price（第二价格竞价，胜出者支付第二高出价 + 最小增量）
</details>

### 问题 3（进阶）
在 Go 实现中，BidEngine 如何保证竞价延迟不超过预算？

<details>
<summary>查看答案</summary>

1. 使用 `context.WithDeadline` 设置硬超时，所有子操作共享 deadline
2. 每个步骤标注预期耗时（~2ms, ~3ms 等），总流程 ~24ms
3. latencyBudget 参数控制最大允许时间（通常 50ms）
4. 预算耗尽时直接 return nil，不进入 pCTR/pCVR 推理
5. 使用 `time.Now()` 记录开始时间，最终用 `time.Since()` 精确测量
</details>

### 问题 4（实战）
RTA 和 RTB 的核心区别是什么？

<details>
<summary>查看答案</summary>

RTB: SSP → Ad Exchange → DSP → 出价 → 中标 → 返回广告
RTA: SSP → RTA API → DSP 决策 (白名单/黑名单) → 通过则继续 RTB
RTA 核心: "先筛选，再竞价"，DSP 可以先决策是否参与
RTA 优势: 节省计算资源，只在确认目标用户后才启动竞价
</details>

### 问题 5（实战）
最优出价公式是什么？各参数含义？

<details>
<summary>查看答案</summary>

Optimal Bid = pCTR × pCVR × Target CPA × β × pacing_factor

- pCTR: 预估点击概率（模型预测）
- pCVR: 预估转化概率（模型预测，给定点击条件）
- Target CPA: 广告主目标每次转化成本
- β (Beta): Bid Shading 因子，学习得到（通常 0.7-0.9），用于在第一价格拍卖中降低出价
- pacing_factor: 预算消耗速率控制（0.5-1.5），根据时间进度动态调整
</details>

### 问题 6（进阶）
Go 中 BidEngine 的 FeatureVector 设计为什么使用 `map[string]float64` 而非 `[]float64`？

<details>
<summary>查看答案</summary>

map[string]float64 的优势:
1. 特征维度稀疏：500+ 维中大部分为 0，map 只存储非零特征
2. 可读性强：调试时可以直接看到特征名而非索引
3. 灵活扩展：新增特征无需修改索引映射
4. 在 Go 中配合 sync.Pool 可以复用 map，减少 GC 压力

生产环境中通常使用 []float64（定长向量）以追求极致性能，
但 map 更适合知识学习和原型验证。
</details>

---

*今天花 90 分钟：深入掌握 RTB/RTA 底层实现*
*答不出自测题？回去重读对应章节。*
