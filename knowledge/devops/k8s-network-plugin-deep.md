# Kubernetes网络插件深度实现 - 资深专家

## 一、网络插件架构

### 1.1 CNI规范

```go
// CNI Plugin接口
type NetworkPlugin interface {
    // 添加网络
    AddNetwork(net *NetworkConfig, conf *RuntimeConf) error
    
    // 删除网络
    DelNetwork(net *NetworkConfig, conf *RuntimeConf) error
    
    // 获取网络状态
    GetNetworkStatus(net *NetworkConfig, conf *RuntimeConf) error
    
    // 版本检查
    Check() (*VersionResult, error)
}

// 网络配置
type NetworkConfig struct {
    CNIVersion string           `json:"cniVersion"`
    Name       string           `json:"name"`
    Type       string           `json:"type"`
    IPAM       *IPAMConfig      `json:"ipam,omitempty"`
    DNS        *DNSConfig       `json:"dns,omitempty"`
    Routes     []*Route         `json:"routes,omitempty"`
}

// IPAM配置
type IPAMConfig struct {
    Type       string   `json:"type"`
    Range      *IPRange `json:"range,omitempty"`
    RangeStart string   `json:"range_start,omitempty"`
    RangeEnd   string   `json:"range_end,omitempty"`
    Routes     []*Route `json:"routes,omitempty"`
    Gateway    string   `json:"gateway,omitempty"`
}
```

### 1.2 主流插件对比

| 插件 | 网络模型 | 性能 | 功能 | 适用场景 |
|------|----------|------|------|----------|
| Calico | BGP路由 | ⭐⭐⭐⭐⭐ | 网络策略 | 大规模集群 |
| Flannel | VXLAN隧道 | ⭐⭐⭐ | 基础网络 | 简单部署 |
| Cilium | eBPF | ⭐⭐⭐⭐⭐ | 可观测性 | 高性能需求 |
| Weave |  Mesh网络 | ⭐⭐⭐ | 跨机房 | 多集群 |
| Contiv | 多租户 | ⭐⭐⭐ | 策略丰富 | 云平台 |

## 二、Calico深度实现

### 2.1 BGP路由架构

```go
// BGP Peering配置
type BGPPeer struct {
    ASNumber    int      `json:"as_number"`
    PeerIP      string   `json:"peer_ip"`
    PeerASN     int      `json:"peer_asn,omitempty"`
    NodeSelector string  `json:"node_selector,omitempty"`
}

// BGP路由器配置
type BGPConfiguration struct {
    ASNumber          int             `json:"as_number"`
    Nodes             []*BGPPeer      `json:"nodes,omitempty"`
    Peerings          []*BGPPeer      `json:"peerings,omitempty"`
    ServiceClusterCIDR string         `json:"service_cluster_cidr,omitempty"`
}

// BGP路由表
type BGPRouteTable struct {
    localRoutes map[string]*Route
    peerRoutes  map[string]*Route
}

// 路由添加
func (rt *BGPRouteTable) AddRoute(prefix, nextHop string) {
    rt.localRoutes[prefix] = &Route{
        Prefix:  prefix,
        NextHop: nextHop,
        Type:    RouteLocal,
    }
}

// 路由同步
func (rt *BGPRouteTable) SyncWithPeer(peer string) {
    for prefix, route := range rt.localRoutes {
        if route.NextHop == "local" {
            rt.sendToPeer(peer, prefix, route.NextHop)
        }
    }
}
```

### 2.2 网络策略实现

```go
// 网络策略
type NetworkPolicy struct {
    Metadata PolicyMetadata   `json:"metadata"`
    Spec     PolicySpec       `json:"spec"`
}

type PolicyMetadata struct {
    Name      string
    Namespace string
}

type PolicySpec struct {
    PodSelector  LabelSelector   `json:"podSelector"`
    Ingress      []Rule          `json:"ingress,omitempty"`
    Egress       []Rule          `json:"egress,omitempty"`
    PolicyTypes  []PolicyType    `json:"policyTypes"`
}

type Rule struct {
    Action   Action       `json:"action"`
    Protocol *Protocol    `json:"protocol,omitempty"`
    Ports    []PortSpec   `json:"ports,omitempty"`
    CIDR     string       `json:"cidr,omitempty"`
}

type Action string

const (
    Allow Action = "Allow"
    Deny  Action = "Deny"
)

// iptables规则生成
func (p *NetworkPolicy) GenerateRules() []iptables.Rule {
    var rules []iptables.Rule
    
    for _, ingress := range p.Spec.Ingress {
        rule := iptables.Rule{
            Chain:   "KUBE-EXTERNAL-SERVICES",
            Table:   "filter",
            Match:   p.buildMatch(ingress),
            Target:  p.buildTarget(ingress),
        }
        rules = append(rules, rule)
    }
    
    return rules
}
```

## 三、Cilium eBPF实现

### 3.1 eBPF程程序结构

```c
// eBPF网络处理程序
#include <vmlinux.h>
#include <bpf/bpf_helpers.h>
#include <bpf/bpf_tracing.h>

// 连接跟踪
struct {
    __uint(type, BPF_MAP_TYPE_HASH);
    __uint(max_entries, 1024 * 1024);
    __type(key, struct bpf_sock_tuple);
    __type(value, struct connection_info);
} conn_track SEC(".maps");

// 网络策略
struct {
    __uint(type, BPF_MAP_TYPE_ARRAY);
    __uint(max_entries, 256);
    __type(key, __u32);
    __type(value, struct policy_entry);
} policy_map SEC(".maps");

// 包处理
SEC("lxc")
int handle_packet(struct __sk_buff *ctx) {
    void *data = (void *)ctx->data;
    void *data_end = (void *)ctx->data_end;
    
    // 解析L2
    struct ethhdr *eth = data;
    if ((void *)(eth + 1) > data_end)
        return TC_ACT_OK;
    
    // 解析L3
    struct iphdr *ip = (void *)(eth + 1);
    if ((void *)(ip + 1) > data_end)
        return TC_ACT_OK;
    
    // 检查策略
    struct bpf_sock_tuple tuple = {};
    tuple.ipv4 = *ip;
    
    if (bpf_map_lookup_elem(&conn_track, &tuple)) {
        return TC_ACT_OK;
    }
    
    // 应用策略
    __u32 key = ip->saddr;
    struct policy_entry *policy = bpf_map_lookup_elem(&policy_map, &key);
    if (policy && policy->action == DENY) {
        return TC_ACT_SHOT;
    }
    
    return TC_ACT_OK;
}
```

### 3.2 eBPF与内核交互

```go
// eBPF程序加载
type BPFProgram struct {
    FD       int
    Type     bpfProgType
    License  string
    Version  uint32
}

// 加载eBPF程序
func LoadBPFProgram(file string) (*BPFProgram, error) {
    // 读取字节码
    bytes, err := os.ReadFile(file)
    if err != nil {
        return nil, err
    }
    
    // 创建内存映射
    spec, err := elf.NewFile(bytes.NewReader(bytes))
    if err != nil {
        return nil, err
    }
    
    // 加载程序
    prog, err := bpf.NewProgram(&bpf.ProgramAttr{
        License: "GPL",
        Version: 0x01,
        Bytes:   bytes,
    })
    if err != nil {
        return nil, err
    }
    
    return &BPFProgram{
        FD:      prog.FD,
        Type:    bpfProgType(prog.Type()),
        License: "GPL",
    }, nil
}

// eBPF map操作
type BPFMap struct {
    FD  int
    Key size_t
    Val size_t
}

func (m *BPFMap) Lookup(key []byte) ([]byte, error) {
    var value []byte
    err := bpfSyscall(BPF_MAP_LOOKUP_ELEM, m.FD, key, &value)
    return value, err
}
```

## 四、生产实践

### 4.1 网络监控

```go
// 网络指标收集
type NetworkMetrics struct {
    PacketsIn  uint64
    PacketsOut uint64
    BytesIn    uint64
    BytesOut   uint64
    ErrorsIn   uint64
    ErrorsOut  uint64
    DropsIn    uint64
    DropsOut   uint64
}

// Prometheus指标
var (
    packetInCounter = prometheus.NewCounterVec(
        prometheus.CounterOpts{
            Name: "cilium_packets_in_total",
            Help: "Number of packets received",
        },
        []string{"node", "pod", "namespace"},
    )
    
    bytesInCounter = prometheus.NewCounterVec(
        prometheus.CounterOpts{
            Name: "cilium_bytes_in_total",
            Help: "Number of bytes received",
        },
        []string{"node", "pod", "namespace"},
    )
)

// 指标注册
func init() {
    prometheus.MustRegister(packetInCounter)
    prometheus.MustRegister(bytesInCounter)
}
```

### 4.2 故障排查

```go
// 网络诊断工具
type NetworkDiagnoser struct {
    kubeClient kubernetes.Clientset
}

// 诊断步骤
func (d *NetworkDiagnoser) Diagnose(podName, namespace string) {
    // 1. 检查Pod状态
    pod, err := d.kubeClient.CoreV1().Pods(namespace).Get(...)
    if err != nil {
        log.Error("pod not found")
        return
    }
    
    // 2. 检查CNI配置
    cniConf := d.checkCNIConfig(pod.Spec.NodeName)
    
    // 3. 检查网络策略
    policies := d.listNetworkPolicies(namespace)
    
    // 4. 检查路由表
    routes := d.checkRoutes(pod.Spec.NodeName)
    
    // 5. 检查DNS
    dnsStatus := d.checkDNS(podName, namespace)
    
    // 输出诊断报告
    d.printReport(pod, cniConf, policies, routes, dnsStatus)
}
```

## 五、面试高频题

### Q1: Calico和Cilium有什么区别？

```
A:
1. 网络模型: Calico用BGP，Cilium用eBPF
2. 性能: Cilium更高(eBPF直接操作)
3. 功能: Calico策略丰富，Cilium可观测性强
4. 复杂度: Calico简单，Cilium复杂
```

### Q2: 如何选择网络插件？

```
A:
1. 规模: 小规模用Flannel，大规模用Calico
2. 性能: 高性能需求用Cilium
3. 安全: 严格网络策略用Calico
4. 可观测: 需要深度监控用Cilium
```

## 六、自测题

1. 解释CNI插件的工作流程
2. Calico BGP路由如何工作？
3. eBPF如何提升网络性能？

---

## 参考文档

- [K8s网络深度](./k8s-network-deep.md)
- [Service Mesh深度](./service-mesh-production-deep.md)
- [Istio架构深度](./istio-mesh-deep.md)
