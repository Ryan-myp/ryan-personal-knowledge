# 服务网格深度解析

> 深入Service Mesh：Istio、Envoy、流量管理、安全通信。
> 源码级分析，包含生产环境实践。
> 适用对象：微服务架构师、SRE

---

## 1. Istio 架构

### 1.1 控制平面

```
Istio 控制平面：

├── Istiod
│   ├── Pilot: 服务发现与路由
│   ├── Citadel: 证书管理
│   ├── Galley: 配置校验
│   └── Ingress/Egress Gateway
│
├── 数据平面
│   └── Envoy Proxy
│
└── 管理平面
    ├── Kiali: 可观测性
    ├── Jaeger: 链路追踪
    └── Prometheus: 指标监控
```

### 1.2 Go 实现 Istio 核心

```go
// istio.go

package mesh

import (
    "sync"
)

type Istiod struct {
    pilot    *Pilot
    citadel  *Citadel
    galley   *Galley
    mu       sync.Mutex
}

type Pilot struct {
    serviceRegistry *ServiceRegistry
    configController *ConfigController
}

type ServiceRegistry struct {
    services map[string]*Service
    endpoints map[string][]*Endpoint
}

type Service struct {
    Name      string
    Namespace string
    Ports     []Port
    Selector  map[string]string
}

type Endpoint struct {
    IP       string
    Port     int
    Weight   int
}

func NewIstiod() *Istiod {
    return &Istiod{
        pilot:    NewPilot(),
        citadel:  NewCitadel(),
        galley:   NewGalley(),
    }
}

func (i *Istiod) RegisterService(service *Service) error {
    i.pilot.serviceRegistry.Register(service)
    return nil
}

func (i *Istiod) GetEndpoints(serviceName string) []*Endpoint {
    return i.pilot.serviceRegistry.GetEndpoints(serviceName)
}
```

---

## 2. Envoy 代理

### 2.1 代理架构

```
Envoy 代理架构：

├── Listener
│   ├── Inbound
│   └── Outbound
│
├── Route
│   ├── Virtual Host
│   └── Route Rule
│
├── Cluster
│   └── 后端服务
│
└── Filter
    ├── Access Log
    ├── Rate Limit
    ├── Auth
    └── CORS
```

### 2.2 Go 实现 Envoy 代理

```go
// envoy.go

package mesh

import (
    "context"
    "net/http"
)

type EnvoyProxy struct {
    listeners  []*Listener
    clusters   map[string]*Cluster
    filters    []Filter
}

type Listener struct {
    Name     string
    Address  string
    Port     int
    Filters  []Filter
}

type Cluster struct {
    Name       string
    Endpoints  []string
    LB         string
    Timeout    int
}

type Filter interface {
    Handle(req *http.Request, resp http.ResponseWriter)
}

func NewEnvoyProxy() *EnvoyProxy {
    return &EnvoyProxy{
        clusters: make(map[string]*Cluster),
    }
}

func (ep *EnvoyProxy) RouteRequest(req *http.Request) (*http.Response, error) {
    // 1. 匹配Listener
    listener := ep.matchListener(req)
    if listener == nil {
        return nil, ErrNoListener
    }
    
    // 2. 匹配Route
    route := ep.matchRoute(req)
    
    // 3. 应用Filters
    for _, filter := range listener.Filters {
        // 过滤处理
    }
    
    // 4. 转发到后端
    return ep.forwardToCluster(req, route.Cluster)
}
```

---

## 3. 流量管理

### 3.1 路由规则

```
流量管理规则：

├── VirtualService
│   ├── 请求路由
│   └── 流量镜像
│
├── DestinationRule
│   ├── 负载均衡
│   └── 连接池
│
└── Gateway
    └── 入口流量
```

### 3.2 Go 实现流量管理

```go
// traffic_management.go

package mesh

type TrafficManager struct {
    virtualServices map[string]*VirtualService
    destinationRules map[string]*DestinationRule
}

type VirtualService struct {
    Name      string
    Namespace string
    Hosts     []string
    HTTP      []HTTPRoute
}

type HTTPRoute struct {
    Match   []RouteMatch
    Route   []RouteDestination
    Timeout string
}

type RouteMatch struct {
    URI    URIMatch
    Headers map[string]string
}

type RouteDestination struct {
    Host    string
    Subset  string
    Weight  int
}

type DestinationRule struct {
    Name      string
    Namespace string
    Host      string
    TrafficPolicy *TrafficPolicy
}

type TrafficPolicy struct {
    LoadBalancer *LoadBalancerPolicy
    ConnectionPool *ConnectionPoolPolicy
    OutlierDetection *OutlierDetectionPolicy
}

func (tm *TrafficManager) Route(host string, req *HTTPRequest) *RouteResult {
    // 匹配VirtualService
    vs := tm.matchVirtualService(host)
    if vs == nil {
        return nil
    }
    
    // 匹配Route
    for _, route := range vs.HTTP {
        if tm.matchRoute(route.Match, req) {
            return tm.selectDestination(route.Route)
        }
    }
    
    return nil
}
```

---

## 4. 安全通信

### 4.1 mTLS

```
mTLS 工作流程：

1. 服务注册
   └── 获取证书

2. 连接建立
   ├── 客户端握手
   └── 服务端握手

3. 数据加密
   └── TLS加密通信
```

### 4.2 Go 实现 mTLS

```go
// mtls.go

package mesh

import (
    "crypto/tls"
    "crypto/x509"
)

type MTLSManager struct {
    caCert     *x509.Certificate
    caKey      []byte
    certStore  map[string]*Certificate
}

type Certificate struct {
    Cert     []byte
    Key      []byte
    CA       []byte
    Expiry   time.Time
}

func NewMTLSManager() *MTLSManager {
    return &MTLSManager{
        certStore: make(map[string]*Certificate),
    }
}

func (m *MTLSManager) GenerateCert(serviceAccount string) (*tls.Certificate, error) {
    // 生成证书
    cert, err := m.generateCert(serviceAccount)
    if err != nil {
        return nil, err
    }
    
    // 存储证书
    m.certStore[serviceAccount] = cert
    
    return cert.ToTLS()
}

func (m *MTLSManager) VerifyClient(cert *tls.Certificate) bool {
    // 验证客户端证书
    return true
}
```

---

## 5. 总结

### 5.1 核心原理回顾

| 组件 | 作用 |
|------|------|
| Istiod | 控制平面 |
| Envoy | 数据平面 |
| Pilot | 服务发现 |
| Citadel | 证书管理 |

### 5.2 最佳实践

- [ ] 合理配置服务网格
- [ ] 启用mTLS加密
- [ ] 监控流量指标
- [ ] 灰度发布流量

---

*最后更新：2026-08-11*
*作者：Ryan*
