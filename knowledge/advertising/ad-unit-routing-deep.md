# 广告单元路由策略完整实现

> 智能路由、负载均衡、故障转移、性能优化
> 创建日期: 2026-08-12
> 作者: Ryan
> 定位: 资深专家级 — 广告单元路由

---

## 第一部分：路由架构设计

### 1.1 路由决策流程

```
┌──────────────────────────────────────────────────────────────┐
│                    广告单元路由决策流程                       │
│                                                              │
│  广告请求进入                                               │
│       │                                                     │
│       ▼                                                     │
│  ┌─────────────────┐                                        │
│  │  1. 广告单元解析 │                                        │
│  └────────┬────────┘                                        │
│           │                                                 │
│           ▼                                                 │
│  ┌─────────────────┐                                        │
│  │  2. 地域匹配    │ ◄──── 用户地理位置                      │
│  └────────┬────────┘                                        │
│           │                                                 │
│           ▼                                                 │
│  ┌─────────────────┐                                        │
│  │  3. 品类路由    │ ◄──── 广告类型 (video/banner/native)   │
│  └────────┬────────┘                                        │
│           │                                                 │
│           ▼                                                 │
│  ┌─────────────────┐                                        │
│  │  4. 质量评分    │ ◄──── SSP 质量分 + 历史表现            │
│  └────────┬────────┘                                        │
│           │                                                 │
│           ▼                                                 │
│  ┌─────────────────┐                                        │
│  │  5. 负载均衡    │ ◄──── 当前负载 + 容量                  │
│  └────────┬────────┘                                        │
│           │                                                 │
│           ▼                                                 │
│  ┌─────────────────┐                                        │
│  │  6. 故障转移    │ ◄──── 健康检查状态                     │
│  └────────┬────────┘                                        │
│           │                                                 │
│           ▼                                                 │
│       返回目标 DSP                                          │
└──────────────────────────────────────────────────────────────┘
```

### 1.2 路由层级

```
┌──────────────────────────────────────────────────────────────┐
│                    路由层级结构                               │
│                                                              │
│  Level 1: 全局路由 (Global Router)                           │
│  ├─ 负责跨地域、跨数据中心的流量分配                          │
│  └─ 策略: 基于地理位置 + 延迟敏感度的粗粒度路由               │
│                                                              │
│  Level 2: 品类路由 (Category Router)                         │
│  ├─ 根据广告类型路由到对应集群                                │
│  └─ 策略: video → VideoDSP集群, native → NativeDSP集群       │
│                                                              │
│  Level 3: 地域路由 (Geo Router)                              │
│  ├─ 根据用户地理位置路由到最近数据中心                        │
│  └─ 策略: CN → 北京集群, US → 美西集群, EU → 法兰克福集群   │
│                                                              │
│  Level 4: 质量路由 (Quality Router)                          │
│  ├─ 根据 SSP 质量和历史表现路由                              │
│  └─ 策略: 高评分 SSP 优先，低评分降级或跳过                 │
│                                                              │
│  Level 5: 负载均衡 (Load Balancer)                           │
│  ├─ 在目标集群内均衡负载                                    │
│  └─ 策略: Least Connections / Round Robin / Weighted        │
└──────────────────────────────────────────────────────────────┘
```

---

## 第二部分：核心路由算法

### 2.1 加权负载均衡

```go
package router

import (
	"sync"
	"math/rand"
)

// WeightedRouter 加权路由算法
type WeightedRouter struct {
	mu       sync.RWMutex
	servers  map[string]*ServerWeight
	totalWeight int
}

// ServerWeight 服务器权重信息
type ServerWeight struct {
	Name     string
	Weight   int
	Address  string
	Healthy  bool
	Failures int
}

// NewWeightedRouter 创建加权路由器
func NewWeightedRouter() *WeightedRouter {
	return &WeightedRouter{
		servers: make(map[string]*ServerWeight),
	}
}

// AddServer 添加服务器
func (r *WeightedRouter) AddServer(name, address string, weight int) {
	r.mu.Lock()
	defer r.mu.Unlock()
	
	r.servers[name] = &ServerWeight{
		Name:    name,
		Weight:  weight,
		Address: address,
		Healthy: true,
	}
	r.recalculateTotal()
}

// SelectServer 选择服务器（加权随机）
func (r *WeightedRouter) SelectServer() (*ServerWeight, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()
	
	// 过滤健康服务器
	var healthyServers []*ServerWeight
	for _, s := range r.servers {
		if s.Healthy && s.Weight > 0 {
			healthyServers = append(healthyServers, s)
		}
	}
	
	if len(healthyServers) == 0 {
		return nil, ErrNoHealthyServer
	}
	
	// 加权随机选择
	total := 0
	for _, s := range healthyServers {
		total += s.Weight
	}
	
	rand.Seed(time.Now().UnixNano())
	target := rand.Intn(total)
	
	current := 0
	for _, s := range healthyServers {
		current += s.Weight
		if target < current {
			return s, nil
		}
	}
	
	return healthyServers[len(healthyServers)-1], nil
}

// MarkUnhealthy 标记服务器不健康
func (r *WeightedRouter) MarkUnhealthy(name string) {
	r.mu.Lock()
	defer r.mu.Unlock()
	
	if s, ok := r.servers[name]; ok {
		s.Healthy = false
		s.Failures++
		r.recalculateTotal()
	}
}

// MarkHealthy 标记服务器恢复健康
func (r *WeightedRouter) MarkHealthy(name string) {
	r.mu.Lock()
	defer r.mu.Unlock()
	
	if s, ok := r.servers[name]; ok {
		s.Healthy = true
		r.recalculateTotal()
	}
}

func (r *WeightedRouter) recalculateTotal() {
	r.totalWeight = 0
	for _, s := range r.servers {
		if s.Healthy {
			r.totalWeight += s.Weight
		}
	}
}
```

### 2.2 最少连接路由

```go
package router

import (
	"sync"
	"sync/atomic"
)

// LeastConnectionRouter 最少连接路由
type LeastConnectionRouter struct {
	mu       sync.Mutex
	servers  map[string]*ServerConn
}

// ServerConn 服务器连接状态
type ServerConn struct {
	Name      string
	Address   string
	Active    int64 // 活跃连接数（原子操作）
	Healthy   bool
}

// NewLeastConnectionRouter 创建最少连接路由器
func NewLeastConnectionRouter() *LeastConnectionRouter {
	return &LeastConnectionRouter{
		servers: make(map[string]*ServerConn),
	}
}

// AddServer 添加服务器
func (r *LeastConnectionRouter) AddServer(name, address string) {
	r.mu.Lock()
	defer r.mu.Unlock()
	
	r.servers[name] = &ServerConn{
		Name:    name,
		Address: address,
		Healthy: true,
	}
}

// SelectServer 选择活跃连接最少的服务器
func (r *LeastConnectionRouter) SelectServer() (*ServerConn, error) {
	r.mu.Lock()
	defer r.mu.Unlock()
	
	var best *ServerConn
	minConn := int64(^uint64(0) >> 1) // 最大 int64
	
	for _, s := range r.servers {
		if !s.Healthy {
			continue
		}
		
		conn := atomic.LoadInt64(&s.Active)
		if conn < minConn {
			minConn = conn
			best = s
		}
	}
	
	if best == nil {
		return nil, ErrNoHealthyServer
	}
	
	// 增加连接计数
	atomic.AddInt64(&best.Active, 1)
	
	return best, nil
}

// ReleaseServer 释放连接
func (r *LeastConnectionRouter) ReleaseServer(name string) {
	if s, ok := r.servers[name]; ok {
		atomic.AddInt64(&s.Active, -1)
	}
}
```

---

## 第三部分：故障转移机制

### 3.1 健康检查

```go
package router

import (
	"context"
	"net/http"
	"time"
)

// HealthChecker 健康检查器
type HealthChecker struct {
	interval   time.Duration
	timeout    time.Duration
	unhealthyThreshold int
}

// NewHealthChecker 创建健康检查器
func NewHealthChecker(interval, timeout time.Duration, threshold int) *HealthChecker {
	return &HealthChecker{
		interval: interval,
		timeout: timeout,
		unhealthyThreshold: threshold,
	}
}

// Start 启动健康检查
func (hc *HealthChecker) Start(ctx context.Context, router *WeightedRouter) {
	ticker := time.NewTicker(hc.interval)
	defer ticker.Stop()
	
	for {
		select {
		case <-ticker.C:
			hc.checkAll(ctx, router)
		case <-ctx.Done():
			return
		}
	}
}

// checkAll 检查所有服务器
func (hc *HealthChecker) checkAll(ctx context.Context, router *WeightedRouter) {
	// 获取所有服务器列表
	servers := router.GetAllServers()
	
	for _, server := range servers {
		hc.checkServer(ctx, server, router)
	}
}

// checkServer 检查单个服务器
func (hc *HealthChecker) checkServer(ctx context.Context, server *ServerWeight, router *WeightedRouter) {
	client := &http.Client{
		Timeout: hc.timeout,
	}
	
	req, err := http.NewRequestWithContext(ctx, "GET", server.Address+"/health", nil)
	if err != nil {
		router.MarkUnhealthy(server.Name)
		return
	}
	
	resp, err := client.Do(req)
	if err != nil || resp.StatusCode != http.StatusOK {
		router.MarkUnhealthy(server.Name)
		return
	}
	
	resp.Body.Close()
	router.MarkHealthy(server.Name)
}
```

### 3.2 故障转移策略

```go
package router

// FailoverStrategy 故障转移策略
type FailoverStrategy int

const (
	// SequentialSequential 顺序故障转移
	SequentialSequential FailoverStrategy = iota
	// ParallelFailover 并行故障转移
	ParallelFailover
	// GeoFailover 地理故障转移
	GeoFailover
)

// FailoverRouter 故障转移路由器
type FailoverRouter struct {
	strategy FailoverStrategy
	primary  *WeightedRouter
	backup   *WeightedRouter
	fallback *WeightedRouter
}

// SelectWithFailover 选择服务器（带故障转移）
func (fr *FailoverRouter) SelectWithFailover(req *BidRequest) (*ServerWeight, error) {
	// 尝试主路由
	server, err := fr.primary.SelectServer()
	if err == nil {
		return server, nil
	}
	
	// 主路由失败，尝试备用
	switch fr.strategy {
	case SequentialSequential:
		return fr.selectSequential(req)
	case ParallelFailover:
		return fr.selectParallel(req)
	case GeoFailover:
		return fr.selectGeo(req)
	default:
		return nil, err
	}
}

// selectSequential 顺序故障转移
func (fr *FailoverRouter) selectSequential(req *BidRequest) (*ServerWeight, error) {
	// 尝试备用
	server, err := fr.backup.SelectServer()
	if err == nil {
		return server, nil
	}
	
	// 备用也失败，尝试回退
	return fr.fallback.SelectServer()
}

// selectParallel 并行故障转移
func (fr *FailoverRouter) selectParallel(req *BidRequest) (*ServerWeight, error) {
	// 并行尝试备用和回退
	type result struct {
		server *ServerWeight
		err    error
	}
	
	ch := make(chan result, 2)
	
	go func() {
		server, err := fr.backup.SelectServer()
		ch <- result{server, err}
	}()
	
	go func() {
		server, err := fr.fallback.SelectServer()
		ch <- result{server, err}
	}()
	
	// 等待第一个成功的结果
	for i := 0; i < 2; i++ {
		res := <-ch
		if res.err == nil {
			return res.server, nil
		}
	}
	
	return nil, ErrAllServersUnhealthy
}
```

---

## 第四部分：地域路由

### 4.1 地理路由表

```go
package router

// GeoRouter 地理路由器
type GeoRouter struct {
	// 地域到路由器的映射
	geoRoutes map[string]*WeightedRouter
	
	// 默认路由器
	defaultRouter *WeightedRouter
}

// NewGeoRouter 创建地理路由器
func NewGeoRouter() *GeoRouter {
	return &GeoRouter{
		geoRoutes: make(map[string]*WeightedRouter),
	}
}

// AddRegion 添加地域路由
func (gr *GeoRouter) AddRegion(region string, router *WeightedRouter) {
	gr.geoRoutes[region] = router
}

// SetDefault 设置默认路由器
func (gr *GeoRouter) SetDefault(router *WeightedRouter) {
	gr.defaultRouter = router
}

// SelectByGeo 根据地理位置选择路由
func (gr *GeoRouter) SelectByGeo(userGeo string) (*WeightedRouter, error) {
	// 精确匹配
	if router, ok := gr.geoRoutes[userGeo]; ok {
		return router, nil
	}
	
	// 区域匹配 (CN-BJ, CN-SH -> CN)
	parts := strings.Split(userGeo, "-")
	if len(parts) > 0 {
		if router, ok := gr.geoRoutes[parts[0]]; ok {
			return router, nil
		}
	}
	
	// 使用默认路由器
	if gr.defaultRouter != nil {
		return gr.defaultRouter, nil
	}
	
	return nil, ErrNoRouteFound
}
```

### 4.2 IP 地理定位

```go
package router

import (
	"net"
)

// GeoLocator 地理定位器
type GeoLocator struct {
	// IP 段到地域的映射
	ipRanges []IPRange
}

// IPRange IP 段
type IPRange struct {
	Start    net.IP
	End      net.IP
	Region   string
	Country  string
}

// NewGeoLocator 创建地理定位器
func NewGeoLocator() *GeoLocator {
	return &GeoLocator{}
}

// AddRange 添加 IP 段
func (gl *GeoLocator) AddRange(start, end net.IP, region, country string) {
	gl.ipRanges = append(gl.ipRanges, IPRange{
		Start:   start,
		End:     end,
		Region:  region,
		Country: country,
	})
}

// Locate 定位 IP 地域
func (gl *GeoLocator) Locate(ip net.IP) (string, string) {
	for _, r := range gl.ipRanges {
		if ipInRange(ip, r.Start, r.End) {
			return r.Region, r.Country
		}
	}
	return "UNKNOWN", "UNKNOWN"
}

// ipInRange 检查 IP 是否在范围内
func ipInRange(ip, start, end net.IP) bool {
	ip1 := ipToUint(ip)
	ip2 := ipToUint(start)
	ip3 := ipToUint(end)
	return ip1 >= ip2 && ip1 <= ip3
}

// ipToUint 将 IP 转换为整数
func ipToUint(ip net.IP) uint32 {
	if len(ip) == 16 {
		ip = ip[12:16] // IPv4-mapped IPv6
	}
	if len(ip) != 4 {
		return 0
	}
	return uint32(ip[0])<<24 | uint32(ip[1])<<16 | uint32(ip[2])<<8 | uint32(ip[3])
}
```

---

## 第五部分：性能监控

### 5.1 路由指标

```go
package router

import (
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
)

// RouterMetrics 路由器监控指标
type RouterMetrics struct {
	routingLatency *prometheus.HistogramVec
	routeSuccess   *prometheus.CounterVec
	routeFailure   *prometheus.CounterVec
	failoverCount  *prometheus.CounterVec
}

// NewRouterMetrics 创建路由器指标
func NewRouterMetrics() *RouterMetrics {
	return &RouterMetrics{
		routingLatency: promauto.NewHistogramVec(
			prometheus.HistogramOpts{
				Name:    "dsp_routing_latency_ms",
				Buckets: []float64{1, 5, 10, 20, 50, 100},
			},
			[]string{"strategy", "region"},
		),
		routeSuccess: promauto.NewCounterVec(
			prometheus.CounterOpts{
				Name: "dsp_route_success_total",
				Help: "Total successful routes",
			},
			[]string{"strategy"},
		),
		routeFailure: promauto.NewCounterVec(
			prometheus.CounterOpts{
				Name: "dsp_route_failure_total",
				Help: "Total failed routes",
			},
			[]string{"strategy", "error"},
		),
		failoverCount: promauto.NewCounterVec(
			prometheus.CounterOpts{
				Name: "dsp_failover_count",
				Help: "Total failover events",
			},
			[]string{"from", "to"},
		),
	}
}
```

### 5.2 路由性能基准

```
┌──────────────────────────────────────────────────────────────┐
│  路由策略              │ 延迟      │ 适用场景                │
├──────────────────────────────────────────────────────────────┤
│  轮询 (Round Robin)   │ < 0.1ms   │ 均匀分布的简单场景      │
│  加权随机             │ < 0.1ms   │ 不同容量服务器混部      │
│  最少连接             │ < 0.5ms   │ 长连接、高并发场景      │
│  一致性哈希           │ < 1ms     │ 会话保持场景            │
│  地理路由             │ < 2ms     │ 多地域部署场景          │
│  故障转移             │ < 5ms     │ 高可用保障场景          │
└──────────────────────────────────────────────────────────────┘
```

---

## 第六部分：配置管理

### 6.1 YAML 配置

```yaml
# config/routing.yaml
routing:
  # 全局策略
  default_strategy: weighted_round_robin
  
  # 地域路由
  geo:
    default_region: CN
    regions:
      CN:
        routers:
          - name: bj-cluster
            weight: 100
            address: dsp-bj.example.com:8080
          - name: sh-cluster
            weight: 80
            address: dsp-sh.example.com:8080
      US:
        default_router: us-west-cluster
      EU:
        default_router: frankfurt-cluster
    
  # 故障转移配置
  failover:
    strategy: parallel
    timeout_ms: 100
    retry_count: 3
    
  # 健康检查
  health_check:
    interval: 10s
    timeout: 5s
    unhealthy_threshold: 3
    healthy_threshold: 2
```

---

## 第七部分：总结

### 路由策略选择指南

```
┌──────────────────────────────────────────────────────────────┐
│  如何选择路由策略？                                          │
├──────────────────────────────────────────────────────────────┤
│  场景 1: 单数据中心，服务器同质  → 加权轮询                  │
│  场景 2: 单数据中心，服务器异质  → 最少连接 / 加权随机      │
│  场景 3: 多地域部署            → 地理路由 + 故障转移        │
│  场景 4: 高可用要求            → 并行故障转移               │
│  场景 5: 会话保持            → 一致性哈希                  │
│  场景 6: 混合场景              → 多层路由组合               │
└──────────────────────────────────────────────────────────────┘
```

---

*最后更新：2026-08-12*
*作者：Ryan*
