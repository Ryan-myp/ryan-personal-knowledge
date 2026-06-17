# 广告反作弊深度：设备指纹/GNN/实时风控

> 从规则引擎到图神经网络，逐层解析广告反作弊系统

---

## 第一部分：广告作弊类型

### 作弊手法全景

```
广告作弊类型：
┌─────────────────────────────────────────────────────────────────────┐
│ 1. 点击欺诈 (Click Fraud)                                           │
│    ├── 机器人点击 (Bot Clicks)                                      │
│    ├── 点击农场 (Click Farms)                                       │
│    ├── 恶意竞争对手点击                                             │
│    └── 激励点击 (Incentivized Clicks)                               │
│                                                                     │
│ 2. 曝光欺诈 (Impression Fraud)                                      │
│    ├── 隐形曝光 (Ad Stacking) - 广告放在不可见区域                   │
│    ├── 像素欺骗 (Pixel Stuffing) - 1x1 像素广告                      │
│    ├── 服务器端伪造 (Server-side Spoofing)                           │
│    └── 模拟点击 (Click Injection) - 安装后伪造点击                    │
│                                                                     │
│ 3. 安装欺诈 (Install Fraud)                                         │
│    ├── 劫持 (Hijacking) - 拦截有机安装                              │
│    ├── 模拟设备 (Device Emulation) - Android 模拟器                  │
│    ├── 虚假安装 (Fake Installs) - 脚本自动安装                      │
│    └── 点击注入 (Click Injection) - 监听剪贴板                       │
│                                                                     │
│ 4. 流量伪造 (Traffic Fraud)                                         │
│    ├── 代理 IP (Proxy IPs)                                          │
│    ├── 数据中心 IP (Datacenter IPs)                                 │
│    ├── VPN/ Tor                                                     │
│    └── 僵尸网络 (Botnets)                                           │
│                                                                     │
│ 5. 归因欺诈 (Attribution Fraud)                                     │
│    ├── 点击劫持 (Click Hijacking)                                   │
│    ├── 安装劫持 (Install Hijacking)                                 │
│    └── 虚假转化 (Fake Conversions)                                  │
└─────────────────────────────────────────────────────────────────────┘
```

### 广告作弊损失

```
行业数据：
- 全球广告作弊损失：~$87B/年 (2024)
- 点击欺诈占比：~30%
- 曝光欺诈占比：~25%
- 安装欺诈占比：~20%
- 流量伪造占比：~15%
- 归因欺诈占比：~10%

影响：
- 广告主 ROI 下降 15-30%
- SSP/DSP 信任度降低
- 合规风险（GDPR/CCPA）
```

---

## 第二部分：设备指纹深度

### 设备指纹采集

```
设备指纹维度：
┌─────────────────────────────────────────────────────────────────────┐
│ 浏览器指纹 (Browser Fingerprint)                                      │
│ ├── User Agent                                                      │
│ ├── Screen Resolution                                                │
│ ├── Color Depth                                                     │
│ ├── Timezone                                                         │
│ ├── Language                                                         │
│ ├── Canvas Fingerprint (HTML5 Canvas)                               │
│ ├── WebGL Fingerprint                                               │
│ ├── AudioContext Fingerprint                                        │
│ ├── Font Detection                                                  │
│ ├── Plugin Detection                                                │
│ ├── Battery API                                                     │
│ ├── Network Information (RTT, Downlink)                             │
│ ├── Touch Support                                                   │
│ ├── Bluetooth (WebBluetooth API)                                    │
│ └── Permissions (Camera, Microphone, etc.)                          │
│                                                                     │
│ 网络指纹 (Network Fingerprint)                                       │
│ ├── IP Address                                                      │
│ ├── ASN (Autonomous System Number)                                  │
│ ├── GeoIP (Country, City, Region)                                   │
│ ├── ISP                                                             │
│ ├── Connection Type (WiFi/4G/5G)                                    │
│ ├── Proxy Detection                                                 │
│ ├── Tor Exit Node Detection                                         │
│ └── Data Center IP Detection                                        │
│                                                                     │
│ 行为指纹 (Behavioral Fingerprint)                                    │
│ ├── Mouse Movement Patterns                                         │
│ ├── Typing Speed                                                     │
│ ├── Scroll Behavior                                                 │
│ ├── Touch Gestures                                                  │
│ ├── App Usage Pattern                                               │
│ ├── Device Orientation                                               │
│ └── Interaction Timing                                               │
│                                                                     │
│ 硬件指纹 (Hardware Fingerprint)                                      │
│ ├── Device Model                                                    │
│ ├── OS Version                                                      │
│ ├── CPU Cores                                                        │
│ ├── Memory Size                                                     │
│ ├── Storage Capacity                                                │
│ ├── GPU Renderer                                                    │
│ └── MAC Address (deprecated in modern browsers)                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 设备指纹生成源码

```go
package fingerprint

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"net"
	"net/http"
	"runtime"
	"strings"
	"time"
)

// Fingerprint 设备指纹结构
type Fingerprint struct {
	DeviceID string
	Score    float64 // 可信度 0-1
	Risk     string  // low/medium/high/critical
	Tags     []string
}

// Collect 收集指纹信息
func Collect(req *http.Request) map[string]string {
	features := make(map[string]string)
	
	// 1. User Agent
	features["ua"] = req.UserAgent()
	
	// 2. IP 地址
	ip := getClientIP(req)
	features["ip"] = ip
	
	// 3. 网络信息
	host := req.Host
	features["host"] = host
	
	// 4. 时间戳（用于检测时区）
	features["tz_offset"] = fmt.Sprintf("%d", time.Now().UnixNano()/1e6)
	
	// 5. Accept headers
	features["accept"] = req.Header.Get("Accept")
	features["accept_lang"] = req.Header.Get("Accept-Language")
	
	// 6. Referer
	features["referer"] = req.Referer()
	
	// 7. 连接类型
	if req.TLS != nil {
		features["proto"] = "https"
	} else {
		features["proto"] = "http"
	}
	
	// 8. 安全头
	features["sec_ch_ua"] = req.Header.Get("Sec-Ch-Ua")
	features["sec_ch_ua_mobile"] = req.Header.Get("Sec-Ch-Ua-Mobile")
	features["sec_ch_ua_platform"] = req.Header.Get("Sec-Ch-Ua-Platform")
	
	// 9. Cookie
	cookie, err := req.Cookie("_fp")
	if err == nil {
		features["prev_fp"] = cookie.Value
	}
	
	return features
}

// Hash 生成指纹哈希
func Hash(features map[string]string) string {
	// 1. 排序 key 保证一致性
	keys := sortKeys(features)
	
	// 2. 拼接值
	var parts []string
	for _, k := range keys {
		parts = append(parts, features[k])
	}
	
	// 3. SHA256 哈希
	h := sha256.Sum256([]byte(strings.Join(parts, "|")))
	return hex.EncodeToString(h[:])
}

// GetClientIP 获取客户端真实 IP
func getClientIP(req *http.Request) string {
	// 1. X-Forwarded-For
	if xff := req.Header.Get("X-Forwarded-For"); xff != "" {
		parts := strings.Split(xff, ",")
		return strings.TrimSpace(parts[0])
	}
	
	// 2. X-Real-IP
	if xri := req.Header.Get("X-Real-IP"); xri != "" {
		return xri
	}
	
	// 3. RemoteAddr
	host, _, err := net.SplitHostPort(req.RemoteAddr)
	if err == nil {
		return host
	}
	
	return req.RemoteAddr
}

// DetectProxy 检测代理
func DetectProxy(ip string) bool {
	// 检查是否是已知代理 IP 段
	proxyRanges := []string{
		"10.0.0.0/8",    // 私有网络
		"172.16.0.0/12", // 私有网络
		"192.168.0.0/16", // 私有网络
		"127.0.0.0/8",   // 回环
	}
	
	for _, cidr := range proxyRanges {
		_, block, _ := net.ParseCIDR(cidr)
		if block.Contains(net.ParseIP(ip)) {
			return true
		}
	}
	
	// TODO: 查询代理 IP 数据库
	return false
}

// DetectDataCenter 检测数据中心 IP
func DetectDataCenter(ip string) bool {
	// TODO: 查询数据中心 IP 数据库
	// 常见数据中心 IP 段：
	// AWS, GCP, Azure, Alibaba Cloud, Tencent Cloud
	return false
}

// Generate 生成完整指纹
func Generate(req *http.Request) *Fingerprint {
	features := Collect(req)
	deviceID := Hash(features)
	
	fp := &Fingerprint{
		DeviceID: deviceID,
		Score:    1.0,
		Tags:     []string{},
	}
	
	// 风险评估
	if DetectProxy(features["ip"]) {
		fp.Tags = append(fp.Tags, "proxy")
		fp.Score -= 0.3
	}
	
	if DetectDataCenter(features["ip"]) {
		fp.Tags = append(fp.Tags, "datacenter")
		fp.Score -= 0.2
	}
	
	if features["sec_ch_ua_mobile"] == "?1" {
		fp.Tags = append(fp.Tags, "mobile")
	}
	
	// 确定风险等级
	if fp.Score < 0.3 {
		fp.Risk = "critical"
	} else if fp.Score < 0.5 {
		fp.Risk = "high"
	} else if fp.Score < 0.8 {
		fp.Risk = "medium"
	} else {
		fp.Risk = "low"
	}
	
	return fp
}
```

---

## 第三部分：实时风控引擎

### 风控规则引擎架构

```
风控规则引擎：
┌─────────────────────────────────────────────────────────────────────┐
│  输入：BidRequest + Device Fingerprint + Historical Data             │
│                                                                        │
│  ┌─────────────────────────────────────────────────────────────┐     │
│  │  Rule Engine (Drools/自研)                                    │     │
│  │                                                             │     │
│  │  ┌─────────────────────────────────────────────────────┐   │     │
│  │  │  规则 1: IP 黑名单                                   │   │     │
│  │  │  IF ip IN blacklist THEN risk = HIGH               │   │     │
│  │  └─────────────────────────────────────────────────────┘   │     │
│  │  ┌─────────────────────────────────────────────────────┐   │     │
│  │  │  规则 2: 点击频率                                   │   │     │
│  │  │  IF clicks_per_minute > 10 THEN risk = MEDIUM      │   │     │
│  │  └─────────────────────────────────────────────────────┘   │     │
│  │  ┌─────────────────────────────────────────────────────┐   │     │
│  │  │  规则 3: 地理位置                                   │   │     │
│  │  │  IF country != target_country THEN risk = HIGH     │   │     │
│  │  └─────────────────────────────────────────────────────┘   │     │
│  │  ┌─────────────────────────────────────────────────────┐   │     │
│  │  │  规则 4: 设备指纹                                   │   │     │
│  │  │  IF device_score < 0.5 THEN risk = CRITICAL        │   │     │
│  │  └─────────────────────────────────────────────────────┘   │     │
│  │  ┌─────────────────────────────────────────────────────┐   │     │
│  │  │  规则 5: 时间模式                                   │   │     │
│  │  │  IF hour IN [0-5] AND clicks > 5 THEN risk = HIGH  │   │     │
│  │  └─────────────────────────────────────────────────────┘   │     │
│  │                                                             │     │
│  │  ┌─────────────────────────────────────────────────────┐   │     │
│  │  │  评分聚合                                             │   │     │
│  │  │  total_risk = SUM(rule_scores) * weights           │   │     │
│  │  └─────────────────────────────────────────────────────┘   │     │
│  └─────────────────────────────────────────────────────────────┘     │
│                                                                        │
│  输出：risk_score + risk_level + blocked_actions                       │
└─────────────────────────────────────────────────────────────────────┘
```

### 风控规则引擎 Go 实现

```go
package fraud

import (
	"context"
	"sync"
	"time"
)

// RiskLevel 风险等级
type RiskLevel string

const (
	RiskLow     RiskLevel = "low"
	RiskMedium  RiskLevel = "medium"
	RiskHigh    RiskLevel = "high"
	RiskCritical RiskLevel = "critical"
)

// FraudRule 风控规则接口
type FraudRule interface {
	Name() string
	Evaluate(ctx context.Context, event *FraudEvent) float64 // 返回 0-1 风险分
}

// FraudEvent 欺诈事件
type FraudEvent struct {
	RequestID    string
	DeviceID     string
	IPAddress    string
	UserAgent    string
	Platform     string
	CampaignID   string
	AdUnitID     string
	Timestamp    time.Time
	Action       string // click/impression/install
	PreviousRisk float64
}

// FraudDetector 欺诈检测器
type FraudDetector struct {
	rules   []FraudRule
	mu      sync.RWMutex
	cache   map[string]*FraudEvent // 最近事件缓存
}

// NewFraudDetector 创建欺诈检测器
func NewFraudDetector() *FraudDetector {
	fd := &FraudDetector{
		cache: make(map[string]*FraudEvent),
	}
	
	// 注册内置规则
	fd.RegisterRule(NewIPBlacklistRule())
	fd.RegisterRule(NewClickFrequencyRule())
	fd.RegisterRule.NewGeolocationRule())
	fd.RegisterRule(NewDeviceFingerprintRule())
	fd.RegisterRule(NewTemporalPatternRule())
	fd.RegisterRule(NewBehavioralRule())
	
	return fd
}

// RegisterRule 注册规则
func (fd *FraudDetector) RegisterRule(rule FraudRule) {
	fd.mu.Lock()
	defer fd.mu.Unlock()
	fd.rules = append(fd.rules, rule)
}

// Detect 检测欺诈
func (fd *FraudDetector) Detect(ctx context.Context, event *FraudEvent) (*FraudResult, error) {
	// 1. 执行所有规则
	var scores []float64
	for _, rule := range fd.rules {
		score := rule.Evaluate(ctx, event)
		scores = append(scores, score)
	}
	
	// 2. 加权平均
	totalScore := weightedAverage(scores)
	
	// 3. 确定风险等级
	riskLevel := determineRiskLevel(totalScore)
	
	// 4. 缓存事件
	fd.cache[event.RequestID] = event
	
	return &FraudResult{
		RequestID: event.RequestID,
		Score:     totalScore,
		RiskLevel: riskLevel,
		Blocked:   riskLevel == RiskCritical || riskLevel == RiskHigh,
	}, nil
}

// FraudResult 检测结果
type FraudResult struct {
	RequestID string
	Score     float64
	RiskLevel RiskLevel
	Blocked   bool
}

// 内置规则实现

// IPBlacklistRule IP 黑名单规则
type IPBlacklistRule struct{}

func (r *IPBlacklistRule) Name() string { return "ip_blacklist" }

func (r *IPBlacklistRule) Evaluate(ctx context.Context, event *FraudEvent) float64 {
	// 查询 Redis 黑名单
	blacklisted, _ := redisClient.SIsMember(ctx, "ip:blacklist", event.IPAddress)
	if blacklisted {
		return 1.0 // 高风险
	}
	return 0.0
}

// ClickFrequencyRule 点击频率规则
type ClickFrequencyRule struct{}

func (r *ClickFrequencyRule) Name() string { return "click_frequency" }

func (r *ClickFrequencyRule) Evaluate(ctx context.Context, event *FraudEvent) float64 {
	// 查询最近 1 分钟的点击次数
	count, _ := redisClient.ZCard(ctx, "clicks:"+event.DeviceID+":1m")
	if count > 60 { // > 1 click/sec
		return 0.8
	}
	if count > 30 { // > 0.5 click/sec
		return 0.5
	}
	if count > 10 { // > 0.17 click/sec
		return 0.2
	}
	return 0.0
}

// GeolocationRule 地理位置规则
type GeolocationRule struct{}

func (r *GeolocationRule) Name() string { return "geolocation" }

func (r *GeolocationRule) Evaluate(ctx context.Context, event *FraudEvent) float64 {
	// 检查用户位置是否与广告目标位置匹配
	userCountry := geolocateIP(event.IPAddress)
	targetCountries := getTargetCountries(event.CampaignID)
	
	if !contains(targetCountries, userCountry) {
		return 0.7 // 不匹配
	}
	return 0.0
}

// DeviceFingerprintRule 设备指纹规则
type DeviceFingerprintRule struct{}

func (r *DeviceFingerprintRule) Name() string { return "device_fingerprint" }

func (r *DeviceFingerprintRule) Evaluate(ctx context.Context, event *FraudEvent) float64 {
	// 检查设备可信度
	score := getDeviceScore(event.DeviceID)
	if score < 0.3 {
		return 0.9 // 不可信
	}
	if score < 0.5 {
		return 0.6
	}
	return 0.0
}

// TemporalPatternRule 时间模式规则
type TemporalPatternRule struct{}

func (r *TemporalPatternRule) Name() string { return "temporal_pattern" }

func (r *TemporalPatternRule) Evaluate(ctx context.Context, event *FraudEvent) float64 {
	hour := event.Timestamp.Hour()
	// 凌晨时段（0-5 点）的异常点击
	if hour >= 0 && hour < 5 {
		return 0.5
	}
	return 0.0
}

// BehavioralRule 行为模式规则
type BehavioralRule struct{}

func (r *BehavioralRule) Name() string { return "behavioral" }

func (r *BehavioralRule) Evaluate(ctx context.Context, event *FraudEvent) float64 {
	// 分析鼠标/触摸行为模式
	// 机器人行为特征：
	// - 直线移动
	// - 匀速移动
	// - 无随机抖动
	// 此处简化为查询行为分数
	behaviorScore := getBehaviorScore(event.DeviceID)
	if behaviorScore < 0.3 {
		return 0.8
	}
	return 0.0
}
```

---

## 第四部分：图神经网络反作弊

### 为什么用 GNN？

```
传统规则引擎的问题：
1. 规则维护成本高（每发现新作弊手法都要加规则）
2. 难以发现协同作弊（多个设备/账号协同）
3. 对新型攻击反应慢

GNN 的优势：
1. 自动学习图结构中的异常模式
2. 发现协同作弊（团伙攻击）
3. 泛化能力强（对新攻击模式有鲁棒性）

应用场景：
- 点击图：用户-设备-IP-广告-点击
- 安装图：用户-设备-应用-安装-转化
- 社交图：用户-好友-互动
```

### 图结构设计

```
作弊检测图：
┌─────────────────────────────────────────────────────────────────────┐
│ 节点类型：                                                          │
│ ├── User (用户)                                                     │
│ ├── Device (设备)                                                   │
│ ├── IP (IP 地址)                                                    │
│ ├── App (应用)                                                      │
│ ├── Ad (广告)                                                       │
│ ├── Campaign (广告系列)                                             │
│ └── Publisher (发布商)                                              │
│                                                                     │
│ 边类型：                                                            │
│ ├── User → Device (拥有)                                            │
│ ├── Device → IP (使用)                                              │
│ ├── User → App (安装)                                               │
│ ├── App → Ad (展示)                                                 │
│ ├── Ad → Campaign (属于)                                            │
│ ├── Publisher → Ad (投放)                                           │
│ ├── Device → Device (相似)                                          │
│ ├── IP → IP (同网段)                                                │
│ └── User → User (好友/互动)                                         │
│                                                                     │
│ 图特征：                                                            │
│ ├── 节点特征：设备指纹、行为模式、地理位置                            │
│ ├── 边特征：时间间隔、频率、距离                                    │
│ └── 图结构特征：度数、聚类系数、社区结构                            │
└─────────────────────────────────────────────────────────────────────┘
```

### GNN 反作弊模型

```python
# PyTorch Geometric 实现
import torch
import torch.nn.functional as F
from torch_geometric.nn import GCNConv, SAGEConv, GATConv
from torch_geometric.data import Data

class FraudGNN(torch.nn.Module):
    def __init__(self, node_dim, hidden_dim, num_classes=2):
        super().__init__()
        # 多层 GNN 提取图结构特征
        self.conv1 = GCNConv(node_dim, hidden_dim)
        self.conv2 = GCNConv(hidden_dim, hidden_dim)
        self.conv3 = GCNConv(hidden_dim, hidden_dim)
        
        # 图池化（全局平均池化）
        self.pool = torch.nn.AdaptiveAvgPool1d(1)
        
        # 分类头
        self.classifier = torch.nn.Sequential(
            torch.nn.Linear(hidden_dim, hidden_dim // 2),
            torch.nn.ReLU(),
            torch.nn.Dropout(0.3),
            torch.nn.Linear(hidden_dim // 2, num_classes),
        )
    
    def forward(self, x, edge_index, batch=None):
        # 1. GCN 层
        x = F.relu(self.conv1(x, edge_index))
        x = F.dropout(x, p=0.3, training=self.training)
        
        x = F.relu(self.conv2(x, edge_index))
        x = F.dropout(x, p=0.3, training=self.training)
        
        x = F.relu(self.conv3(x, edge_index))
        
        # 2. 全局池化
        x = self.pool(x.unsqueeze(-1)).squeeze(-1)
        
        # 3. 分类
        logits = self.classifier(x)
        probs = F.softmax(logits, dim=-1)
        
        return probs, logits

# 训练数据构建
def build_fraud_graph(clicks, devices, ips, users):
    """
    构建作弊检测图
    
    Args:
        clicks: [(user_id, device_id, ip_id, timestamp)]
        devices: [(device_id, fingerprint)]
        ips: [(ip_id, geo_info)]
        users: [(user_id, behavior)]
    
    Returns:
        Data object for PyTorch Geometric
    """
    # 1. 收集所有节点
    nodes = {}
    node_idx = 0
    
    for device_id, _ in devices:
        if device_id not in nodes:
            nodes[device_id] = node_idx
            node_idx += 1
    
    for ip_id, _ in ips:
        if ip_id not in nodes:
            nodes[ip_id] = node_idx
            node_idx += 1
    
    for user_id, _ in users:
        if user_id not in nodes:
            nodes[user_id] = node_idx
            node_idx += 1
    
    # 2. 构建边
    edge_list = []
    
    for user_id, device_id, ip_id, _ in clicks:
        if user_id in nodes and device_id in nodes:
            edge_list.append([nodes[user_id], nodes[device_id]])
        if device_id in nodes and ip_id in nodes:
            edge_list.append([nodes[device_id], nodes[ip_id]])
    
    # 3. 构建节点特征
    x = torch.zeros(len(nodes), node_dim)
    for node_id, idx in nodes.items():
        # 填充节点特征（设备指纹、IP 信息等）
        x[idx] = get_node_features(node_id)
    
    # 4. 构建标签
    y = torch.zeros(len(nodes), dtype=torch.long)
    for node_id, idx in nodes.items():
        if is_known_fraud(node_id):
            y[idx] = 1
    
    # 5. 返回图数据
    edge_index = torch.tensor(edge_list, dtype=torch.long).t()
    
    return Data(x=x, edge_index=edge_index, y=y)
```

### 实时 GNN 推理

```go
// 实时欺诈检测（GNN + 规则引擎）
func RealTimeDetect(event *FraudEvent) *FraudResult {
    // 1. 规则引擎快速过滤（< 1ms）
    ruleResult := ruleEngine.Detect(event)
    if ruleResult.RiskLevel == RiskCritical {
        return ruleResult // 直接拒绝
    }
    
    // 2. 构建子图（最近 1000 个相关事件）
    subgraph := buildSubgraph(event)
    
    // 3. GNN 推理（< 10ms）
    gnnProb, _ := fraudGNN.Predict(subgraph)
    
    // 4. 融合规则引擎和 GNN 结果
    finalScore := ruleResult.Score*0.3 + gnnProb*0.7
    
    riskLevel := determineRiskLevel(finalScore)
    
    return &FraudResult{
        RequestID: event.RequestID,
        Score:     finalScore,
        RiskLevel: riskLevel,
        Blocked:   riskLevel == RiskCritical || riskLevel == RiskHigh,
    }
}
```

---

## 第五部分：自测题

### Q1: 设备指纹和 Cookie 的区别？

**A**:
- **Cookie**: 存储在客户端，可被清除，依赖用户同意
- **设备指纹**: 基于浏览器/设备特征生成，不可清除，不依赖 Cookie
- 趋势：随着 Cookie 淘汰，设备指纹成为主流追踪方案

### Q2: GNN 反作弊相比规则引擎有什么优势？

**A**:
- **协同作弊检测**：GNN 可以发现设备/IP/用户之间的隐藏关联
- **自适应**：模型自动学习新模式，无需人工编写规则
- **泛化能力**：对未见过的攻击模式有一定鲁棒性
- **缺点**：训练成本高、推理延迟较大

### Q3: 实时风控的延迟预算是多少？

**A**:
- 规则引擎：< 1ms
- GNN 推理：< 10ms
- 总预算：< 20ms（不能超过竞价超时）
- 优化：GNN 使用子图 + 缓存 + 异步推理

---

## 第六部分：生产实践

### 1. 反作弊监控面板

```
关键监控指标：
1. 欺诈率：fraud_clicks / total_clicks（目标 < 1%）
2. 误杀率：blocked_legit / total_blocked（目标 < 0.1%）
3. 规则命中率：每条规则的触发次数
4. GNN 置信度分布
5. 设备指纹更新频率
6. IP 黑名单增长趋势
```

### 2. 对抗策略

```
作弊者 vs 反作弊：
- 作弊者：更换设备指纹 → 反作弊：行为分析 + GNN
- 作弊者：使用住宅代理 → 反作弊：IP 信誉库
- 作弊者：模拟人类行为 → 反作弊：时序模式分析
- 作弊者：分布式攻击 → 反作弊：图聚类分析
```
