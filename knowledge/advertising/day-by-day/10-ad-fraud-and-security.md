# 广告反欺诈与安全性深度指南

> 创建日期: 2026-06-10
> 作者: Ryan
> 定位: 资深专家级 — 广告安全与反欺诈

---

## 第一部分：广告欺诈类型

### 1.1 欺诈类型全景

```
┌──────────────────────────────────────────────────────────────┐
│              广告欺诈类型                                      │
│                                                              │
│  展示欺诈 (Impression Fraud):                                │
│  ├── 无效流量 (IVT): 4-8% 的全球广告流量                      │
│  ├── Bot 流量: 自动化程序模拟人类行为                         │
│  ├── Pixel Stuffing: 1x1 像素嵌入广告                         │
│  ├── Ad Stacking: 多个广告叠放在同一广告位                     │
│  ├── Snooping: 人类手动查看广告位                             │
│  └─ Server-to-Server: 伪造展示信号                             │
│                                                              │
│  点击欺诈 (Click Fraud):                                     │
│  ├── 竞争对手点击: 恶意点击竞对广告                            │
│  ├── 点击农场: 人工或自动化点击                               │
│  ├── 点击劫持: 诱导用户误点击                                 │
│  ├── 点击膨胀: 刷高点击次数                                   │
│  └─ Cookie Stuffing: 植入追踪 Cookie 骗取佣金                  │
│                                                              │
│  转化欺诈 (Conversion Fraud):                                │
│  ├── 虚假转化: 伪造转化事件 (安装/购买/注册)                   │
│  ├── 归因劫持: 将有机转化据为己有                              │
│  ├── 自点击: 用户点击自己广告                                  │
│  └─ 设备指纹伪造: 模拟真实设备                                  │
│                                                              │
│  其他欺诈:                                                   │
│  ├── 域欺骗 (Domain Spoofing): 伪装成高价值网站               │
│  ├── 广告劫持 (Ad Hijacking): 劫持广告展示                    │
│  ├── 供应链欺诈: Supply Chain 不透明                         │
│  └─ 暗网交易: 购买虚假流量                                     │
│                                                              │
│  损失规模:                                                   │
│  ├── 全球广告欺诈损失: $83B+ (2024)                           │
│  ├── IVT 率: 4-8% (平均)                                    │
│  ├── 点击欺诈: 2-5%                                          │
│  └─ 转化欺诈: 1-3%                                          │
└──────────────────────────────────────────────────────────────┘
```

### 1.2 Bot 检测核心原理

```
Bot 检测: 区分 Bot 和人类用户

特征维度:
├── 设备指纹:                                                 │
│   ├── Device ID: 重复使用/伪造                                │
│   ├── User-Agent: 已知 Bot UA                                 │
│   ├── 屏幕分辨率: 异常 (如 1x1, 800x600)                     │
│   ├── 操作系统: 非常见版本 (Android 99.0)                     │
│   └─ 浏览器特性: Canvas/Fingerprint/WASM                      │
│                                                              │
├── 行为特征:                                                  │
│   ├── 点击频率: 远高于人类均值                                │
│   ├── 浏览路径: 无规律/随机/循环                              │
│   ├── 鼠标/触摸轨迹: 直线/匀速 (非人类)                       │
│   ├── 页面停留时间: 0ms (瞬间)                                │
│   └─ 滚动行为: 无滚动/固定模式                                │
│                                                              │
├── 网络特征:                                                  │
│   ├── IP 地址: Data Center/VPS/Proxy                         │
│   ├── ASN: 已知托管/云提供商                                  │
│   ├── 地理位置: 与 IP 不匹配 (GPS vs IP)                     │
│   ├── 连接类型: 高带宽低延迟 (数据中心)                        │
│   └─ HTTP 头: 缺少常见头 (Accept-Language, Referer)          │
│                                                              │
├── 时间特征:                                                  │
│   ├── 请求间隔: 固定/匀速 (人类随机)                          │
│   ├── 活跃时间: 非人类活跃时段                                │
│   └─ 会话长度: 异常短/长                                      │
│                                                              │
└── 上下文特征:                                                │
    ├── 页面内容: 无实质内容 (Farm/Blank Page)                  │
    ├── JavaScript: 未执行/跳过                                 │
    └─ 广告可见性: 不在视口 (Pixel Stuffing)                    │
```

---

## 第二部分：反欺诈模型

### 2.1 实时反欺诈决策引擎

```
实时反欺诈决策引擎架构:

┌──────────────────────────────────────────────────────────────┐
│              反欺诈决策流程                                    │
│                                                              │
│  1. 数据采集 (Data Collection):                              │
│  ├── Bid Request 中的每个字段                                  │
│  ├── 设备指纹: 解析 User-Agent + 屏幕 + Canvas                │
│  ├── 网络信息: IP, ASN, Geo, ISP                              │
│  ├── 行为信号: 点击/浏览/交互轨迹                             │
│  └─ 上下文信号: 页面/APP/广告位信息                            │
│                                                              │
│  2. 特征提取 (Feature Engineering):                           │
│  ├── 实时特征 (Redis, < 1ms):                                 │
│  │   ├── 该 IP 过去 1h 点击数                                 │
│  │   ├── 该设备过去 24h 展示数                                │
│  │   ├── 该用户画像信誉分                                     │
│  │   └─ 该广告系列历史欺诈率                                  │
│  ├── 离线特征 (HDFS/S3):                                     │
│  │   ├── 用户行为序列 (过去 30d)                              │
│  │   ├── 设备指纹聚类                                         │
│  │   └─ 图特征 (设备-IP-用户图)                               │
│  └─ 聚合特征:                                                │
│      ├── 滑动窗口统计 (过去 1h/6h/24h/7d)                     │
│      └─ 百分位排名 (对比全局分布)                              │
│                                                              │
│  3. 模型推理 (Model Inference):                               │
│  ├── 模型: Gradient Boosting (XGBoost/LightGBM)               │
│  │   └─ 特征: 200-500 维                                      │
│  │   └─ 输出: fraud_score ∈ [0, 1]                           │
│  ├── 延迟: < 2ms (P99)                                       │
│  └─ 特征: 集成多个模型 (Bot检测/点击欺诈/转化欺诈)              │
│                                                              │
│  4. 决策 (Decision):                                         │
│  ├── fraud_score > 0.9 → 阻断 (Block)                        │
│  ├── 0.5 < score ≤ 0.9 → 放养/慢速 (Slop/Honey Pot)          │
│  │   └─ 慢速响应，消耗 Bot 资源                               │
│  ├── 0.2 < score ≤ 0.5 → 正常竞价但标记                       │
│  └─ score ≤ 0.2 → 正常竞价                                    │
│                                                              │
│  5. 反馈循环 (Feedback Loop):                                │
│  ├── 人工标注: 审计师标记误判                                   │
│  ├── 模式更新: 新 Bot 模式 → 添加规则                         │
│  ├── 模型重训: 每周/每月重训练                                │
│  └─ 黑名单更新: 实时下发                                       │
└──────────────────────────────────────────────────────────────┘
```

### 2.2 反欺诈模型代码实现

```python
"""
反欺诈模型 — 实时检测引擎
"""

import numpy as np
import torch
import torch.nn as nn
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import time


@dataclass
class BidRequestFraudSignals:
    """Bid Request 中的反欺诈信号"""
    ip: str
    asn: int
    geo_country: str
    device_make: str
    device_model: str
    os: str
    os_version: str
    user_agent: str
    screen_width: int
    screen_height: int
    screen_dpi: int
    js_enabled: bool
    canvas_hash: Optional[str]
    ifa: Optional[str]
    cookie: Optional[str]
    page_url: Optional[str]
    placement_type: str
    is_top_rank: bool
    request_rate_last_1h: float  # 该 IP 过去 1h 请求数
    device_impressions_24h: int  # 该设备过去 24h 展示数
    click_count_last_1h: int  # 该设备过去 1h 点击数
    conversion_count_last_24h: int  # 该设备过去 24h 转化数
    time_interval_ms: float  # 与前一次请求的间隔
    scroll_depth: float  # 滚动深度 (0-1)
    page_load_time_ms: float  # 页面加载时间
    ad_view_duration_ms: int  # 广告可见持续时间


class FraudDetectionModel:
    """
    实时反欺诈模型
    
    使用 XGBoost/LightGBM 或 DNN
    """
    
    def __init__(
        self,
        model_type: str = 'lgbm',  # 'lgbm' 或 'dnn'
        fraud_threshold: float = 0.9,  # 阻断阈值
        slop_threshold: float = 0.5,  # 放养阈值
    ):
        self.model_type = model_type
        self.fraud_threshold = fraud_threshold
        self.slop_threshold = slop_threshold
        
        if model_type == 'dnn':
            self.model = nn.Sequential(
                nn.Linear(30, 128),
                nn.ReLU(),
                nn.Dropout(0.3),
                nn.Linear(128, 64),
                nn.ReLU(),
                nn.Dropout(0.2),
                nn.Linear(64, 32),
                nn.ReLU(),
                nn.Linear(32, 1),
                nn.Sigmoid(),
            )
    
    def predict(
        self,
        signals: BidRequestFraudSignals,
    ) -> Tuple[float, str]:
        """
        预测是否欺诈
        
        Returns:
            (score, decision):
            ├── score: [0, 1], 越高越可能是欺诈
            └─ decision: 'block', 'slop', 'flag', 'allow'
        """
        # 特征提取
        features = self._extract_features(signals)
        
        # 模型推理
        start = time.perf_counter()
        if self.model_type == 'dnn':
            with torch.no_grad():
                features_tensor = torch.FloatTensor([features])
                score = self.model(features_tensor).item()
        else:
            # LightGBM / XGBoost
            score = self._lgbm_predict(features)
        latency_ms = (time.perf_counter() - start) * 1000
        
        # 决策
        decision = self._make_decision(score)
        
        return score, decision
    
    def _extract_features(
        self,
        signals: BidRequestFraudSignals,
    ) -> List[float]:
        """
        从信号中提取 30 维特征
        
        特征类别:
        ├── 设备特征 (10 维)
        ├── 网络特征 (5 维)
        ├── 行为特征 (8 维)
        └─ 上下文特征 (7 维)
        """
        features = []
        
        # 设备特征
        features.append(self._is_known_bot_device(signals.device_make, signals.device_model))
        features.append(1.0 if signals.os in ['Android', 'iOS'] else 0.0)
        features.append(signals.screen_width / 1920.0)  # 归一化
        features.append(signals.screen_height / 1080.0)  # 归一化
        features.append(1.0 if signals.screen_dpi < 200 else 0.0)  # 低 DPI 可疑
        features.append(1.0 if signals.js_enabled else 0.0)
        features.append(1.0 if signals.canvas_hash is None else 0.0)  # 无 Canvas 可疑
        features.append(self._ua_fraud_score(signals.user_agent))
        features.append(self._ifa_fraud_score(signals.ifa))
        features.append(self._cookie_fraud_score(signals.cookie))
        
        # 网络特征
        features.append(self._asn_fraud_score(signals.asn))
        features.append(self._ip_reputation_score(signals.ip))
        features.append(1.0 if signals.geo_country not in ['US', 'GB', 'DE', 'FR', 'JP'] else 0.0)
        features.append(signals.request_rate_last_1h / 10000.0)  # 归一化
        features.append(1.0 if signals.request_rate_last_1h > 1000 else 0.0)
        
        # 行为特征
        features.append(signals.device_impressions_24h / 100000.0)
        features.append(signals.click_count_last_1h / 1000.0)
        features.append(signals.conversion_count_last_24h / 100.0)
        features.append(signals.time_interval_ms / 1000.0)  # 归一化
        features.append(1.0 if signals.time_interval_ms < 100 else 0.0)  # 极快
        features.append(signals.scroll_depth)
        features.append(signals.page_load_time_ms / 5000.0)
        features.append(signals.ad_view_duration_ms / 30000.0)
        
        # 上下文特征
        features.append(1.0 if not signals.is_top_rank else 0.0)
        features.append(self._page_fraud_score(signals.page_url))
        features.append(self._placement_fraud_score(signals.placement_type))
        features.append(1.0 if signals.screen_width < 300 or signals.screen_height < 200 else 0.0)
        features.append(1.0 if signals.screen_width > 10000 else 0.0)  # 异常分辨率
        
        return features
    
    def _make_decision(self, score: float) -> str:
        """
        决策:
        ├── score > 0.9 → block (阻断)
        ├── 0.5 < score ≤ 0.9 → slop (放养/蜜罐)
        ├── 0.2 < score ≤ 0.5 → flag (标记)
        └─ score ≤ 0.2 → allow (正常)
        """
        if score > self.fraud_threshold:
            return 'block'
        elif score > self.slop_threshold:
            return 'slop'
        elif score > 0.2:
            return 'flag'
        else:
            return 'allow'
    
    def _is_known_bot_device(
        self,
        device_make: str,
        device_model: str,
    ) -> float:
        """已知 Bot 设备分数"""
        bot_keywords = ['bot', 'crawler', 'spider', 'phantom', 'headless']
        for kw in bot_keywords:
            if kw in device_make.lower() or kw in device_model.lower():
                return 1.0
        return 0.0
    
    def _ua_fraud_score(self, ua: str) -> float:
        """User-Agent 欺诈分数"""
        bot_uas = ['python-requests', 'curl', 'wget', 'scrapy', 'selenium']
        if not ua:
            return 1.0
        for pattern in bot_uas:
            if pattern in ua.lower():
                return 1.0
        # 短 UA 可疑
        if len(ua) < 50:
            return 0.7
        return 0.0
    
    def _lgbm_predict(self, features: List[float]) -> float:
        """LightGBM 预测 (简化)"""
        # 实际: 加载 pre-trained LightGBM 模型
        # 这里用简单加权分数模拟
        weights = [
            0.15, 0.1, 0.05, 0.05, 0.1, 0.1, 0.1, 0.1, 0.05, 0.05,  # 设备
            0.08, 0.08, 0.05, 0.05, 0.05,  # 网络
            0.04, 0.04, 0.02, 0.03, 0.03,  # 行为
            0.02, 0.02, 0.02, 0.02, 0.02,  # 上下文
        ]
        return min(1.0, sum(f * w for f, w in zip(features, weights)))
```

---

## 第三部分：供应链透明性 (Supply Chain)

### 3.1 IAB Source Transaction ID (STID) 与 schain

```
schain (Supply Chain): 追踪广告从发布商到广告主的完整路径

┌──────────────────────────────────────────────────────────────┐
│              schain 结构                                       │
│                                                              │
│  {                                                            │
│    "ver": "1.0",                                           │
│    "complete": 1,  // 是否完整供应链 (1=完整)                    │
│    "nodes": [                                               │
│      {                                                      │
│        "asi": "example.com",  // 站点/应用标识符                 │
│        "sid": "00000000-0000-0000-0000-000000000001",       │
│        "hp": 1,  // 是否是出价方                                 │
│        "dt": 1234567890  // 时间戳                              │
│      },                                                     │
│      {                                                      │
│        "asi": "ssp.example.com",                            │
│        "sid": "00000000-0000-0000-0000-000000000002",       │
│        "hp": 1,                                             │
│        "rid": "bid-request-id",                             │
│        "dt": 1234567891                                     │
│      },                                                     │
│      {                                                      │
│        "asi": "adexchange.google.com",                      │
│        "sid": "google001",                                  │
│        "hp": 1,                                             │
│        "dt": 1234567892                                     │
│      },                                                     │
│      {                                                      │
│        "asi": "dsp.admanager.com",                          │
│        "sid": "dsp001",                                     │
│        "hp": 0,  // 非出价方                                    │
│        "dt": 1234567893                                     │
│      }                                                      │
│    ]                                                        │
│  }                                                           │
│                                                              │
│  每个节点代表供应链中的一个参与者:                               │
│  ├── Publisher (发布商)                                        │
│  ├── SSP (供应方平台)                                          │
│  ├── Ad Exchange (广告交易平台)                                 │
│  ├── DSP (需求方平台)                                          │
│  └─ Advertiser (广告主)                                        │
│                                                              │
│  关键信息:                                                   │
│  ├── asi: 参与者标识 (域名/ID)                                 │
│  ├── sid: 参与者唯一 ID                                       │
│  ├── hp: 是否参与竞价                                         │
│  ├── rid: 关联的 Bid Request ID                               │
│  └─ dt: 处理时间戳                                            │
│                                                              │
│  作用:                                                       │
│  ├── 防止域欺骗 (Domain Spoofing):                            │
│  │   └─ 验证发布商是否在链中                                    │
│  ├── 提高透明度: 广告主知道钱去了哪里                           │
│  ├── 合规: IAB 要求所有程序化交易提供 schain                   │
│  └─ 审计: 追踪每一步的加价                                      │
└──────────────────────────────────────────────────────────────┘
```

---

## 第四部分：自测题

### 问题 1
广告欺诈的四大类型是什么？

<details>
<summary>查看答案</summary>

1. 展示欺诈 (Impression Fraud) — Bot 伪造展示
2. 点击欺诈 (Click Fraud) — 恶意点击
3. 转化欺诈 (Conversion Fraud) — 伪造转化
4. 其他欺诈 — 域欺骗/供应链欺诈
</details>

### 问题 2
反欺诈决策的三个阈值是什么？

<details>
<summary>查看答案</summary>

- score > 0.9 → block (阻断)
- 0.5 < score ≤ 0.9 → slop (放养/蜜罐)
- score ≤ 0.2 → allow (正常)
</details>

### 问题 3
schain 中的 "complete" 字段含义？

<details>
<summary>查看答案</summary>

complete = 1: 供应链完整，从发布商到广告主所有节点都包含
complete = 0: 供应链不完整，有节点缺失 (可能域欺骗)
</details>

---

*今天花 90 分钟：深入掌握广告反欺诈技术*
*答不出自测题？回去重读对应章节。*

```go
package fraud

import (
	"fmt"
	"sync"
)

type Click struct {
	UserID string
	IP     string
	Action string
}

type FraudDetector struct {
	clicks  map[string][]Click
	limits  map[string]int
	mu      sync.Mutex
}

func NewDetector() *FraudDetector {
	return &FraudDetector{clicks: make(map[string][]Click), limits: map[string]int{"user": 10, "ip": 50}}
}

func (f *FraudDetector) Record(c Click) {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.clicks[c.UserID] = append(f.clicks[c.UserID], c)
}

func (f *FraudDetector) DetectFraud() map[string]int {
	f.mu.Lock()
	defer f.mu.Unlock()
	suspicious := make(map[string]int)
	for uid, clicks := range f.clicks {
		if len(clicks) > f.limits["user"] { suspicious[uid] = len(clicks) }
	}
	return suspicious
}

func main() {
	d := NewDetector()
	for i := 0; i < 15; i++ { d.Record(Click{UserID: "bot1", Action: "click"}) }
	fraud := d.DetectFraud()
	for uid, count := range fraud { fmt.Printf("Suspicious %s: %d clicks
", uid, count) }
}

