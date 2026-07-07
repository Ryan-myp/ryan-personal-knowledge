# 互联网广告系统深度实战：架构、算法与智能化

## 一、互联网广告生态

### 1.1 互联网广告生态的参与者

```
广告生态核心参与者:
├── 广告主 (Advertiser)
│   └── 投放广告的企业/个人
├── 需求方平台 (DSP)
│   └── 帮助广告主购买广告库存
├── 广告交换平台 (Ad Exchange)
│   └── 连接DSP和SSP的交易场所
├── 供应方平台 (SSP)
│   └── 帮助媒体出售广告库存
├── 数据管理平台 (DMP)
│   └── 收集和整合用户数据
├── 广告服务器 (Ad Server)
│   └── 管理广告创意和投放
└── 第三方监测平台
    └── 验证广告效果和防作弊
```

### 1.2 在线广告产品形态

| 形态 | 说明 | 典型场景 |
|------|------|----------|
| Banner广告 | 横幅广告 | 网站顶部/侧边 |
| 搜索广告 | 关键词竞价 | Google/Bing搜索 |
| 信息流广告 | 原生内容 | 朋友圈/抖音 |
| 视频广告 | 前贴片/中插 | YouTube/爱奇艺 |
| 激励视频 | 观看获奖励 | 游戏/APP |
| 开屏广告 | 启动页全屏 | 移动APP |
| 原生广告 | 融入内容 | 知乎/头条 |

## 二、广告投放系统

### 2.1 广告层级结构

```
广告账户层级:
├── Campaign (广告系列)
│   ├── 目标: 品牌认知/转化/流量
│   ├── 预算: 日预算/总预算
│   ├── 出价策略: CPC/CPM/oCPM
│   └── 排期: 开始/结束时间
│   ├── Ad Group (广告组)
│   │   ├── 定向: 受众/地域/设备
│   │   ├── 预算分配
│   │   └── 出价设置
│   │   └── Ad (广告创意)
│   │       ├── 素材: 图片/视频/文案
│   │       ├── 落地页
│   │       └── CTA按钮
```

### 2.2 API的基本设计原则

**RESTful API设计：**

```
GET    /v1/campaigns          # 获取广告系列列表
GET    /v1/campaigns/{id}     # 获取单个广告系列
POST   /v1/campaigns          # 创建广告系列
PUT    /v1/campaigns/{id}     # 更新广告系列
DELETE /v1/campaigns/{id}     # 删除广告系列
GET    /v1/campaigns/{id}/insights  # 获取数据洞察
```

**Go 实现示例：**

```go
package api

import (
	"net/http"
	"github.com/gin-gonic/gin"
)

type CampaignService interface {
	ListCampaigns(ctx context.Context, req *ListCampaignsRequest) ([]*Campaign, error)
	GetCampaign(ctx context.Context, id string) (*Campaign, error)
	CreateCampaign(ctx context.Context, req *CreateCampaignRequest) (*Campaign, error)
	UpdateCampaign(ctx context.Context, id string, req *UpdateCampaignRequest) error
	DeleteCampaign(ctx context.Context, id string) error
}

type CampaignController struct {
	service CampaignService
}

func (c *CampaignController) RegisterRoutes(router *gin.Engine) {
	group := router.Group("/v1/campaigns")
	{
		group.GET("", c.listCampaigns)
		group.GET("/:id", c.getCampaign)
		group.POST("", c.createCampaign)
		group.PUT("/:id", c.updateCampaign)
		group.DELETE("/:id", c.deleteCampaign)
	}
}

func (c *CampaignController) listCampaigns(ctx *gin.Context) {
	req := &ListCampaignsRequest{}
	if err := ctx.ShouldBindQuery(req); err != nil {
		ctx.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	
	campaigns, err := c.service.ListCampaigns(ctx.Request.Context(), req)
	if err != nil {
		ctx.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	
	ctx.JSON(http.StatusOK, campaigns)
}
```

## 三、大规模网络系统架构设计

### 3.1 分布式集群管理系统

**核心组件：**

```
集群管理:
├── 资源调度 (Resource Scheduler)
│   ├── 负载均衡
│   ├── 故障转移
│   └── 弹性伸缩
├── 服务发现 (Service Discovery)
│   ├── 注册中心
│   ├── 健康检查
│   └── 配置管理
└── 监控告警 (Monitoring)
    ├── 指标收集
    ├── 日志聚合
    └── 告警通知
```

**Go 实现服务发现：**

```go
package discovery

import (
	"context"
	"sync"
	"time"
)

type ServiceInstance struct {
	ID        string
	Name      string
	Address   string
	Port      int
	Healthy   bool
	Tags      map[string]string
	LastSeen  time.Time
}

type ServiceRegistry struct {
	services map[string][]*ServiceInstance
	mu       sync.RWMutex
	ttl      time.Duration
}

func NewServiceRegistry(ttl time.Duration) *ServiceRegistry {
	return &ServiceRegistry{
		services: make(map[string][]*ServiceInstance),
		ttl:      ttl,
	}
}

func (r *ServiceRegistry) Register(instance *ServiceInstance) error {
	r.mu.Lock()
	defer r.mu.Unlock()
	
	// 检查是否已存在
	for _, existing := range r.services[instance.Name] {
		if existing.ID == instance.ID {
			existing.Address = instance.Address
			existing.Port = instance.Port
			existing.Tags = instance.Tags
			existing.LastSeen = time.Now()
			existing.Healthy = true
			return nil
		}
	}
	
	r.services[instance.Name] = append(r.services[instance.Name], instance)
	return nil
}

func (r *ServiceRegistry) GetInstances(name string) ([]*ServiceInstance, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()
	
	instances := r.services[name]
	if len(instances) == 0 {
		return nil, fmt.Errorf("no instances found for service: %s", name)
	}
	
	// 过滤健康实例
	healthy := make([]*ServiceInstance, 0)
	for _, inst := range instances {
		if inst.Healthy && time.Since(inst.LastSeen) < r.ttl {
			healthy = append(healthy, inst)
		}
	}
	
	if len(healthy) == 0 {
		return nil, fmt.Errorf("no healthy instances for service: %s", name)
	}
	
	return healthy, nil
}
```

### 3.2 分布式存储

**广告系统数据存储：**

```
存储分层:
├── 热数据 (Hot Data)
│   ├── Redis (缓存)
│   └── Memcached
├── 温数据 (Warm Data)
│   ├── MySQL (关系型)
│   └── PostgreSQL
└── 冷数据 (Cold Data)
    ├── ClickHouse (OLAP)
    ├── Elasticsearch (搜索)
    └── HDFS (数据湖)
```

## 四、广告播放系统架构设计

### 4.1 广告播放系统架构

```
广告播放流程:
1. 用户访问页面/App
2. 触发广告请求
3. 广告服务器匹配广告
4. 返回广告创意
5. 前端渲染广告
6. 记录曝光/点击
7. 数据上报
8. 实时计算指标
```

**Go 实现广告匹配引擎：**

```go
package bidding

import (
	"context"
	"fmt"
	"sync"
	"time"
)

type AdRequest struct {
	UserID    string
	Device    string
	Location  string
	PageURL   string
	Categories []string
}

type Ad struct {
	ID          string
	CampaignID  string
	CreativeID  string
	BidPrice    float64
	Targeting   Targeting
	Creative    Creative
	Status      string
}

type Targeting struct {
	GeoIDs      []string
	InterestIDs []string
	Demographics map[string]interface{}
}

type Creative struct {
	Type     string // image, video, html
	URL      string
	Width    int
	Height   int
	CTA      string
}

type MatchEngine struct {
	ads         []*Ad
	indices     map[string][]int // category -> ad indices
	mu          sync.RWMutex
}

func NewMatchEngine() *MatchEngine {
	return &MatchEngine{
		ads:     make([]*Ad, 0),
		indices: make(map[string][]int),
	}
}

func (e *MatchEngine) AddAd(ad *Ad) {
	e.mu.Lock()
	defer e.mu.Unlock()
	
	idx := len(e.ads)
	e.ads = append(e.ads, ad)
	
	// 建立索引
	for _, cat := range ad.Targeting.InterestIDs {
		e.indices[cat] = append(e.indices[cat], idx)
	}
}

func (e *MatchEngine) Match(ctx context.Context, req *AdRequest) ([]*Ad, error) {
	e.mu.RLock()
	defer e.mu.RUnlock()
	
	// 匹配广告
	matched := make(map[int]bool)
	for _, cat := range req.Categories {
		if indices, ok := e.indices[cat]; ok {
			for _, idx := range indices {
				matched[idx] = true
			}
		}
	}
	
	// 过滤结果
	result := make([]*Ad, 0)
	for idx := range matched {
		if idx < len(e.ads) {
			result = append(result, e.ads[idx])
		}
	}
	
	return result, nil
}
```

## 五、广告系统数据架构设计

### 5.1 广告系统数据类型

```
数据分类:
├── 用户数据 (User Data)
│   ├── 人口统计
│   ├── 兴趣标签
│   └── 行为序列
├── 广告数据 (Ad Data)
│   ├── 创意素材
│   ├── 定向设置
│   └── 出价策略
├── 曝光数据 (Impression Data)
│   ├── 时间戳
│   ├── 位置
│   └── 设备信息
└── 转化数据 (Conversion Data)
    ├── 点击
    ├── 下载
    └── 购买
```

### 5.2 数据管理平台

**DMP核心功能：**

```
数据管理:
├── 数据采集 (Collection)
│   ├── SDK埋点
│   ├── API上报
│   └── 第三方数据接入
├── 数据清洗 (Cleaning)
│   ├── 去重
│   ├── 格式化
│   └── 异常检测
├── 数据整合 (Integration)
│   ├── ID Mapping
│   ├── 标签体系
│   └── 用户分群
└── 数据应用 (Application)
    ├── 受众定向
    ├── Lookalike
    └── 频次控制
```

**Go 实现 ID Mapping：**

```go
package dmp

import (
	"sync"
)

type IDMapping struct {
	mappings map[string]map[string]string // platform -> {old_id: new_id}
	mu       sync.RWMutex
}

func NewIDMapping() *IDMapping {
	return &IDMapping{
		mappings: make(map[string]map[string]string),
	}
}

func (m *IDMapping) Map(platform, oldID, newID string) {
	m.mu.Lock()
	defer m.mu.Unlock()
	
	if _, ok := m.mappings[platform]; !ok {
		m.mappings[platform] = make(map[string]string)
	}
	m.mappings[platform][oldID] = newID
}

func (m *IDMapping) Resolve(platform, id string) (string, bool) {
	m.mu.RLock()
	defer m.mu.RUnlock()
	
	platformMap, ok := m.mappings[platform]
	if !ok {
		return "", false
	}
	
	newID, ok := platformMap[id]
	return newID, ok
}
```

## 六、A/B测试与互联网广告

### 6.1 A/B测试介绍

**实验设计流程：**

```
1. 提出假设 (Hypothesis)
   ├── 原假设 H0: 新版本无效果
   └── 备择假设 H1: 新版本有效果

2. 确定指标 (Metrics)
   ├── 主要指标: CTR, CVR, ROAS
   └── 次要指标: CPC, CPA, 留存率

3. 样本量计算 (Sample Size)
   ├── 基础费率 (Baseline Rate)
   ├── 最小可检测效应 (MDE)
   └── 统计功效 (Power)

4. 随机分组 (Randomization)
   ├── 实验组 (Treatment)
   └── 对照组 (Control)

5. 运行实验 (Run)
   ├── 流量分配
   └── 数据收集

6. 分析结果 (Analysis)
   ├── 显著性检验
   └── 效应量计算

7. 决策 (Decision)
   ├── 接受/拒绝 H0
   └── 全量/回滚
```

### 6.2 实验数据分析

**Go 实现 A/B 测试分析：**

```go
package abtest

import (
	"math"
)

type ExperimentResult struct {
	GroupA []UserMetric
	GroupB []UserMetric
}

type UserMetric struct {
	UserID    string
	Converted bool
	Value     float64
}

func (r *ExperimentResult) Analyze() (float64, bool) {
	// 计算转化率
	convertedA := countConverted(r.GroupA)
	totalA := len(r.GroupA)
	convertedB := countConverted(r.GroupB)
	totalB := len(r.GroupB)
	
	ctrA := float64(convertedA) / float64(totalA)
	ctrB := float64(convertedB) / float64(totalB)
	
	// Z-test
	zScore := calculateZScore(convertedA, totalA, convertedB, totalB)
	pValue := 2 * (1 - normalCDF(math.Abs(zScore)))
	
	significant := pValue < 0.05
	return pValue, significant
}

func countConverted(metrics []UserMetric) int {
	count := 0
	for _, m := range metrics {
		if m.Converted {
			count++
		}
	}
	return count
}

func calculateZScore(convA, totalA, convB, totalB int) float64 {
	p1 := float64(convA) / float64(totalA)
	p2 := float64(convB) / float64(totalB)
	p := float64(convA + convB) / float64(totalA + totalB)
	
	se := math.Sqrt(p * (1 - p) * (1.0/float64(totalA) + 1.0/float64(totalB)))
	if se == 0 {
		return 0
	}
	return (p1 - p2) / se
}

func normalCDF(x float64) float64 {
	return 0.5 * (1.0 + erf(x/math.Sqrt(2)))
}

func erf(x float64) float64 {
	a1 := 0.254829592
	a2 := -0.284496736
	a3 := 1.421413741
	a4 := -1.453152027
	a5 := 1.061405429
	p := 0.3275911
	
	sign := 1.0
	if x < 0 {
		sign = -1
	}
	x = math.Abs(x)
	
	t := 1.0 / (1.0 + p*x)
	y := 1.0 - (((((a5*t+a4)*t)+a3)*t+a2)*t+a1)*t*math.Exp(-x*x)
	
	return sign * y
}
```

## 七、广告系统策略

### 7.1 广告竞价

**竞价策略：**

```
竞价类型:
├── 第一价格拍卖 (First-Price)
│   └── 出价即支付
├── 第二价格拍卖 (Second-Price)
│   └── 次高出价者价格
└── 广义第二价格 (GSP)
    └── Google/Facebook使用

出价策略:
├── 手动出价 (Manual Bidding)
│   ├── CPC (按点击)
│   ├── CPM (按展示)
│   └── CPA (按转化)
└── 智能出价 (Smart Bidding)
    ├── Target CPA
    ├── Target ROAS
    └── Maximize Conversions
```

**Go 实现竞价引擎：**

```go
package bidding

import (
	"context"
	"math/rand"
	"time"
)

type BidRequest struct {
	AdSlotID string
	UserID   string
	Budget   float64
	MaxBid   float64
}

type BidResponse struct {
	BidPrice float64
	AdID     string
	Winner   bool
}

type BidEngine struct {
	strategies map[string]BiddingStrategy
}

type BiddingStrategy interface {
	CalculateBid(ctx context.Context, req *BidRequest) (float64, error)
}

type TargetCPA struct {
	targetCPA float64
	ctrModel  *CTRModel
	cvrModel  *CVRModel
}

func (s *TargetCPA) CalculateBid(ctx context.Context, req *BidRequest) (float64, error) {
	ctr := s.ctrModel.Predict(req.UserID)
	cvr := s.cvrModel.Predict(req.UserID)
	
	// eCPM = CTR * CVR * Target CPA
	ecpm := ctr * cvr * s.targetCPA
	
	// 加入随机扰动
	ecpm *= (1.0 + (rand.Float64()-0.5)*0.1)
	
	if ecpm > req.MaxBid {
		ecpm = req.MaxBid
	}
	
	return ecpm, nil
}

type CTRModel struct {
	weights map[string]float64
}

func (m *CTRModel) Predict(userID string) float64 {
	// 简化实现
	baseCTR := 0.02
	if userID == "user_123" {
		baseCTR *= 1.5
	}
	return baseCTR
}

type CVRModel struct {
	weights map[string]float64
}

func (m *CVRModel) Predict(userID string) float64 {
	baseCVR := 0.05
	if userID == "user_123" {
		baseCVR *= 1.3
	}
	return baseCVR
}
```

## 八、预估算法

### 8.1 训练数据准备

**特征工程：**

```
特征类型:
├── 用户特征 (User Features)
│   ├── 人口统计: 年龄、性别、地域
│   ├── 兴趣标签: 偏好分类
│   └── 行为序列: 历史点击/转化
├── 广告特征 (Ad Features)
│   ├── 创意特征: 类型、尺寸
│   ├── 广告主特征: 行业、品牌
│   └── 历史表现: CTR、CVR
└── 上下文特征 (Context Features)
    ├── 时间: 小时、星期
    ├── 设备: 类型、操作系统
    └── 场景: 页面、位置
```

### 8.2 常用预估模型

**模型演进：**

```
LR (逻辑回归) → FM (因子分解机) → DeepFM → DIN → MMOE
```

| 模型 | 特点 | 适用场景 |
|------|------|----------|
| LR | 简单高效，可解释性强 | 基线模型 |
| FM | 特征交叉，处理稀疏数据 | 推荐系统 |
| DeepFM | 深度+因子分解 | 点击率预估 |
| DIN | 注意力机制 | 用户行为序列 |
| MMOE | 多任务学习 | 多目标优化 |

**Go 实现 DeepFM 简化版：**

```go
package model

import (
	"math"
)

type DeepFM struct {
	linearWeights  []float64
	embeddings     map[string][]float64
	hiddenLayers   [][]float64
	learningRate   float64
}

func NewDeepFM(featureDim int, embedDim int) *DeepFM {
	return &DeepFM{
		linearWeights:  make([]float64, featureDim),
		embeddings:     make(map[string][]float64),
		hiddenLayers:   [][]float64{},
		learningRate:   0.01,
	}
}

func (m *DeepFM) Predict(features map[string]interface{}) float64 {
	// 线性部分
	linearOutput := m.linearPart(features)
	
	// 嵌入部分
	embedOutput := m.embeddingPart(features)
	
	// 深度学习部分
	deepOutput := m.deepPart(embedOutput)
	
	// 合并输出
	output := linearOutput + deepOutput
	
	// Sigmoid 激活
	return 1.0 / (1.0 + math.Exp(-output))
}

func (m *DeepFM) linearPart(features map[string]interface{}) float64 {
	sum := 0.0
	for feat, val := range features {
		if idx, ok := m.featureIndex(feat); ok {
			sum += m.linearWeights[idx] * val.(float64)
		}
	}
	return sum
}

func (m *DeepFM) embeddingPart(features map[string]interface{}) []float64 {
	embeddings := make([]float64, 0)
	for feat, val := range features {
		if embed, ok := m.embeddings[feat]; ok {
			// 简化：直接使用嵌入值
			embeddings = append(embeddings, val.(float64)*embed[0])
		}
	}
	return embeddings
}

func (m *DeepFM) deepPart(embeddings []float64) float64 {
	// 简化：直接求和
	sum := 0.0
	for _, e := range embeddings {
		sum += e
	}
	return sum
}

func (m *DeepFM) featureIndex(feat string) (int, bool) {
	// 简化实现
	return 0, true
}
```

## 九、自测题

1. 互联网广告生态的核心参与者有哪些？
2. 广告竞价策略有哪些类型？各有什么优缺点？
3. CTR预估模型经历了哪些演进？
4. 如何进行有效的A/B测试？

## 十、动手验证

```bash
# 1. 实现广告匹配引擎
# 2. 实现竞价策略
# 3. 实现CTR预估模型
# 4. 实现A/B测试分析
```
