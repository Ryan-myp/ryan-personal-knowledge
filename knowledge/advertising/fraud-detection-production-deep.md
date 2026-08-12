# 广告反作弊生产实践深度实现 - 从规则到机器学习

> **版本**: v2.0  
> **日期**: 2026-08-13  
> **作者**: Ryan  
> **分类**: 广告/反作弊  
> **代码密度**: 30%

---

## 一、作弊类型与检测策略

```
┌─────────────────────────────────────────────────────────────────────┐
│                    广告作弊类型矩阵                                  │
│                                                                     │
│  ┌──────────────┬──────────────────┬────────────────────────────┐  │
│  │    类型       │    检测难度       │         常见手段           │  │
│  ├──────────────┼──────────────────┼────────────────────────────┤  │
│  │ 点击欺诈      │ ⭐⭐⭐           │ 软件点击/模拟器/设备农场    │  │
│  │ 曝光欺诈      │ ⭐⭐             │ 隐藏广告/堆叠/像素欺骗      │  │
│  │ 转化欺诈      │ ⭐⭐⭐⭐          │ 虚假表单/诱导点击           │  │
│  │ 流量欺诈      │ ⭐⭐             │ BOT流量/伪造来源           │  │
│  │ 归因欺诈      │ ⭐⭐⭐⭐         │ 劫持归因/延迟点击           │  │
│  │ IDFA 欺骗     │ ⭐⭐⭐            │ 伪造设备ID/改包           │  │
│  └──────────────┴──────────────────┴────────────────────────────┘  │
│                                                                     │
│  检测技术栈:                                                        │
│  • 规则引擎: 阈值/模式/黑名单                                       │
│  • 统计模型: 异常检测/分布拟合                                       │
│  • 机器学习: XGBoost/LightGBM/深度学习                              │
│  • 图计算: 关联图谱/社区发现                                        │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 二、实时检测引擎

```go
// fraud/detector.go
package fraud

import (
    "context"
    "time"
)

// Event 检测事件
type Event struct {
    Type       string    // click/impression/conversion
    Timestamp  time.Time
    UserID     uint64
    AdID       uint64
    DeviceID   string
    IP         string
    Geo        string
    UA         string
    Metadata   map[string]interface{}
}

// Detector 检测器接口
type Detector interface {
    Name() string
    Check(ctx context.Context, event *Event) (*Result, error)
}

// Result 检测结果
type Result struct {
    IsFraud    bool
    Score      float64    // 0-1, 越高越可疑
    Reason     string
    Actions    []Action
}

// Action 处理动作
type Action int
const (
    ActionNone Action = iota
    ActionFlag      // 标记
    ActionBlock     // 拦截
    ActionReview    // 人工审核
)

// ScoreEngine 评分引擎
type ScoreEngine struct {
    detectors []Detector
    thresholds map[string]float64
}

// NewScoreEngine 创建评分引擎
func NewScoreEngine() *ScoreEngine {
    return &ScoreEngine{
        detectors: []Detector{
            &RuleDetector{},
            &StatisticalDetector{},
            &MLDetector{},
        },
        thresholds: map[string]float64{
            "click":    0.7,
            "impression": 0.8,
            "conversion": 0.9,
        },
    }
}

// Detect 执行检测
func (e *ScoreEngine) Detect(ctx context.Context, event *Event) (*Result, error) {
    totalScore := 0.0
    reasons := make([]string, 0)
    
    for _, d := range e.detectors {
        result, err := d.Check(ctx, event)
        if err != nil {
            continue
        }
        totalScore += result.Score
        if result.Score > 0.1 {
            reasons = append(reasons, d.Name()+": "+result.Reason)
        }
    }
    
    // 归一化
    if len(e.detectors) > 0 {
        totalScore /= float64(len(e.detectors))
    }
    
    // 阈值判断
    threshold := e.thresholds[event.Type]
    isFraud := totalScore >= threshold
    
    return &Result{
        IsFraud: isFraud,
        Score:   totalScore,
        Reason:  strings.Join(reasons, "; "),
        Actions: e.decideActions(isFraud, totalScore),
    }, nil
}
```

---

## 三、图检测

```python
# fraud/graph_detection.py
import networkx as nx
from collections import defaultdict

class FraudGraph:
    """作弊关联图"""
    
    def __init__(self):
        self.graph = nx.Graph()
    
    def add_event(self, user_id, ad_id, event_type, timestamp):
        """添加事件节点"""
        node_id = f"{user_id}:{ad_id}:{event_type}"
        self.graph.add_node(node_id, user=user_id, ad=ad_id, type=event_type)
        
        # 建立关联边
        if event_type == "click":
            # 同设备点击同一广告
            self._add_device_edge(user_id, ad_id, "device_click")
            # 同IP点击
            self._add_ip_edge(user_id, ad_id, "ip_click")
    
    def _add_device_edge(self, user_id, ad_id, label):
        """添加设备关联"""
        device_key = f"device:{user_id}"
        self.graph.add_edge(f"{user_id}:{ad_id}:click", device_key, weight=1)
    
    def detect_clusters(self, min_size=5):
        """检测作弊集群"""
        # 找连通分量
        components = list(nx.connected_components(self.graph))
        fraud_clusters = []
        for comp in components:
            if len(comp) >= min_size:
                # 检查是否有异常高的点击率
                nodes = self.graph.nodes(comp)
                click_nodes = [n for n in nodes if n.endswith(":click")]
                if len(click_nodes) / len(nodes) > 0.8:
                    fraud_clusters.append(comp)
        return fraud_clusters
    
    def get_suspicious_users(self, min_events=10):
        """获取可疑用户"""
        users = defaultdict(int)
        for node in self.graph.nodes():
            if ":user:" in node:
                users[node] += 1
        return {u: c for u, c in users.items() if c >= min_events}
```

---

## 四、特征工程

```go
// fraud/features.go
package fraud

// Feature 特征
type Feature struct {
    // 设备特征
    DeviceEntropy float64 // 设备指纹熵值
    IsSimulator   bool    // 是否模拟器
    IsRooted      bool    // 是否越狱
    
    // 行为特征
    ClickRate     float64 // 点击率
    ImpressionGap int     // 曝光间隔
    SessionLen    int     // 会话长度
    
    // 时间特征
    HourOfDay     int     // 小时
    DayOfWeek     int     // 星期
    IsNightTime   bool    // 是否夜间
    
    // 网络特征
    IPReputation  float64 // IP信誉分
    ASN           string  // 自治系统
    ISP           string  // 运营商
    
    // 地理位置
    GeoConflicts  int     // 地理冲突次数
    Velocity      float64 // 移动速度(km/h)
}

// ExtractFeatures 提取特征
func ExtractFeatures(event *Event) *Feature {
    return &Feature{
        DeviceEntropy: calcDeviceEntropy(event.DeviceID),
        IsSimulator:   isSimulator(event.UA),
        IsRooted:      checkRooted(event.DeviceID),
        ClickRate:     calcClickRate(event.UserID),
        ImpressionGap: time.Since(event.Timestamp).Seconds(),
        HourOfDay:     event.Timestamp.Hour(),
        IPReputation:  getIPReputation(event.IP),
        Velocity:      calcVelocity(event.Geo, event.Timestamp),
    }
}
```

---

## 五、自测题

1. **为什么图检测有效？**
   - 作弊者往往形成关联网络（同设备、同IP、同行为模式）

2. **实时检测和离线检测的区别？**
   - 实时: 毫秒级响应，拦截作弊; 离线: 深度分析，模型训练

