# 混沌工程深度 — 从理论到生产实践的故障注入与容错设计

> 标签: `#混沌工程` `#ChaosEngineering` `#故障注入` `#容错设计` `#弹性` `#源码级`
> 创建日期: 2026-06-10 | 作者: Ryan
> 定位: 资深专家级 — 混沌工程方法论 + 工具链 + 生产实战

---

## 第一部分：入门引导（5 分钟速览）

### 1.1 什么是混沌工程？

混沌工程（Chaos Engineering）是在**生产系统上主动引入故障**，验证系统在故障情况下的**弹性（Resilience）**和**容错能力（Fault Tolerance）**。

```
┌────────────────────────────────────────────────────────────┐
│                   混沌工程的核心思想                         │
│                                                            │
│  "不要等到故障发生才发现问题，要主动寻找系统脆弱点"           │
│                                                            │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              混沌工程闭环                              │  │
│  │                                                      │  │
│  │  1. 建立稳态假设          2. 设计实验                 │  │
│  │     系统正常时的行为          引入可控故障               │  │
│  │         ↓                       ↓                    │  │
│  │  3. 执行实验              4. 验证假设                 │  │
│  │     观察系统行为              对比稳态                  │  │
│  │         ↓                       ↓                    │  │
│  │  5. 修复漏洞              6. 改进设计                 │  │
│  │     修复发现的问题            提升系统弹性              │  │
│  └──────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────┘
```

### 1.2 为什么要做混沌工程？

| 原因 | 说明 |
|------|------|
| **分布式系统的复杂性** | 微服务架构下，故障不再是例外，而是常态 |
| **预防胜于治疗** | 主动发现比被动修复成本低 100 倍 |
| **测试覆盖的局限** | 单元测试/集成测试无法覆盖生产环境的真实故障 |
| **团队信心** | 通过定期实验建立对系统的信心 |
| **合规要求** | 金融/电商行业对高可用性的要求 |

### 1.3 核心原则（Netflix 方法论）

```
1. 建立稳态 (Build a Steady State Hypothesis)
   定义什么是"正常"，量化指标 (错误率 < 0.1%, P99 < 200ms)

2. 引入真实故障 (Vary Real Events)
   不要模拟理想故障，要模拟真实世界的故障 (网络延迟, 磁盘损坏, 机房断电)

3. 在生产中运行 (Run Experiments in Production)
   只有生产环境才能发现真实问题 (但要有安全护栏)

4. 自动化 (Automate Everything)
   实验应该自动化、可重复、可持续

5. 最小爆炸半径 (Minimize Blast Radius)
   故障影响范围可控 (Namespace/Region 隔离)
```

### 1.4 核心工具链

| 工具 | 类型 | 特点 |
|------|------|------|
| **Chaos Mesh** | K8s 原生 | 功能最全，CNCF 毕业项目 ⭐ |
| **ChaosBlade** | 阿里云 | 支持物理机/容器/K8s |
| **Litmus** | K8s 原生 | 简单易用，云原生 |
| **Pumba** | Docker | 轻量，基于容器 |
| **Toxiproxy** | 中间件 | 网络故障注入 (延迟/丢包/限制带宽) |
| **Hystrix/Sentinel** | 熔断器 | 应用层容错 (非混沌工程，但相关) |

---

## 第二部分：故障注入类型 — 源码级

### 2.1 Chaos Mesh 实验类型

```go
// chaos_types.go — Chaos Mesh CRD 定义
package chaos

// 1. Pod Chaos — Pod 级别故障
type PodChaos struct {
    Spec PodChaosSpec
    Status PodChaosStatus
}

type PodChaosSpec struct {
    Action PodAction              // action: partition | failure | clock
    Selector SelectorSpec         // 选择哪些 Pod
    Duration *string              // 持续时间
    GracePeriod int32            // 清理等待时间
}

type PodAction string

const (
    PodFailureAction     PodAction = "pod-failure"   // Pod 失败
    PodKillAction        PodAction = "pod-kill"       // Pod 杀死
    PodExecutionTimeAction PodAction = "pod-execution-time" // 执行耗时
    PodClockChaosAction  PodAction = "clock"           // 时钟篡改
    PodPartitionAction   PodAction = "partition"       // 网络分区
)

// 2. Network Chaos — 网络故障
type NetworkChaos struct {
    Spec NetworkChaosSpec
    Status NetworkChaosStatus
}

type NetworkAction string

const (
    NetworkDelayAction      NetworkAction = "delay"        // 网络延迟
    NetworkDuplicateAction  NetworkAction = "duplicate"     // 网络包重复
    NetworkCorruptAction    NetworkAction = "corrupt"       // 网络包损坏
    NetworkLossAction       NetworkAction = "loss"          // 网络包丢失
    NetworkDNSAction        NetworkAction = "dns"           // DNS 故障
    NetworkPartitionAction  NetworkAction = "partition"     // 网络分区
    NetworkBandwidthAction  NetworkAction = "bandwidth"     // 带宽限制
)

type NetworkDelaySpec struct {
    Delay     string  `json:"delay"`     // "200ms"
    Jitter    string  `json:"jitter"`    // "50ms"
    Correlation string `json:"correlation"` // "25" (关联度 0-100)
    Duplicate string  `json:"duplicate"`   // "1%"
    Corrupt   string  `json:"corrupt"`     // "1%"
    Direction Direction  `json:"direction"`   // to/from/both
    EtherCode uint16  `json:"ether_code"`
    IPProtocol string `json:"ip_protocol"`
    TCPReset   bool    `json:"tcp_reset"`
}

// 3. IO Chaos — 文件系统故障 (Linux only)
type IOChaos struct {
    Spec IOChaosSpec
}

type IOAction string

const (
    IOAttrAction      IOAction = "attr"        // 文件属性篡改
    IOAttributeChangeAction IOAction = "attribute"
    IOReadSlowAction  IOAction = "readslow"    // 读取变慢
    IOWriteSlowAction IOAction = "writeslow"   // 写入变慢
    IOFillAction      IOAction = "fill"        // 磁盘空间填充
    IOErrorAction     IOAction = "error"       // 读/写错误
    IODropAction      IOAction = "drop"        // 丢弃 IO
    IOLatencyAction   IOAction = "latency"     // IO 延迟
)

// 4. Stress Chaos — 资源压力
type StressChaos struct {
    Spec StressChaosSpec
}

type StressKind string

const (
    StressCPU    StressKind = "cpu"     // CPU 压力
    StressMemory StressKind = "memory"  // 内存压力
)

type StressChaosSpec struct {
    Stressors *Stressors
    Selector SelectorSpec
}

type Stressors struct {
    CPU *CPUStressor   // CPU 压力
    Mem *MemStressor   // 内存压力
}

type CPUStressor struct {
    Workers int     `json:"workers"`     // 压力线程数
    Load    int     `json:"load"`        // 加载百分比
    PerCore bool    `json:"per_core"`    // 是否每核
}

type MemStressor struct {
    Size        string `json:"size"`        // 内存大小 "512Mi"
    SwapRatio   int    `json:"swap_ratio"`  // 交换空间比例
    Workers     int    `json:"workers"`     // 压力线程数
    Filesystem  string `json:"filesystem"`  // 文件系统路径
}

// 5. Cloud Chaos — 云平台故障
type CloudChaos struct {
    Spec CloudChaosSpec
}

type CloudAction string

const (
    CloudCPUAction     CloudAction = "cpu"         // AWS/Aliyun CPU 压力
    CloudDiskAction    CloudAction = "disk"         // 磁盘 I/O 压力
    CloudJVMAction     CloudAction = "jvm"          // JVM 异常 (OOM/FullGC)
    CloudNetworkAction CloudAction = "network"       // 云网络故障
    CloudStateAction   CloudAction = "state"         // 云状态 (停机/删除)
    CloudTimeAction    CloudAction = "time"          // 系统时间篡改
    CloudKernelAction  CloudAction = "kernel"        // 内核 panic (Linux only)
)

// 6. DNS Chaos — DNS 故障
// 7. Time Chaos — 时钟故障
// 8. Kernel Panic — 内核级故障
```

### 2.2 网络故障注入详解

```go
// network.go — 网络故障注入核心逻辑

// 网络延迟 (Network Delay) — 最常用
// 原理: 通过 tc (traffic control) + netem 实现
//
// 注入命令 (Chaos Mesh 底层):
// tc qdisc add dev eth0 root netem delay 200ms 50ms 25%
//
// 参数说明:
// - delay 200ms: 基础延迟 200 毫秒
// - jitter 50ms: 抖动 (随机波动) 50 毫秒
// - correlation 25%: 关联度 (连续包的延迟相关性)
//
// 延迟分布:
// 正常:  ────────────────────────── [0ms]
// 延迟:  ───────[200ms]──────────────── [200ms ± 50ms]
// 抖动:  ──[180ms]──[210ms]──[190ms]──[220ms]──[195ms]──
//         (每个包的实际延迟不同)
//
// 应用场景:
// 1. 跨机房延迟: 通常 50-200ms
// 2. CDN 延迟: 通常 10-50ms
// 3. 网络拥塞: 延迟波动大

// 网络包丢失 (Network Loss)
// 原理: tc qdisc add dev eth0 root netem loss 5%
//
// 丢包类型:
// - Random: 随机丢包 (最常见)
// - Repeatable: 基于 seed 的可重复丢包
// - Correlated: 成簇丢包 (连续丢包，模拟网络拥塞)
//
// tc qdisc add dev eth0 root netem loss 5% correlate 50
//
// 应用场景:
// 1. 网络拥塞: 丢包率 1-5%
// 2. WiFi 信号弱: 丢包率 5-10%
// 3. 跨运营商: 丢包率 1-3%

// 网络包重复 (Network Duplicate)
// 原理: tc qdisc add dev eth0 root netem duplicate 1%
//
// 应用场景:
// 1. 驱动程序 bug 导致的重复包
// 2. 网络设备故障
// 3. 罕见的协议实现 bug

// 网络包损坏 (Network Corrupt)
// 原理: tc qdisc add dev eth0 root netem corrupt 0.5%
//
// 应用场景:
// 1. 硬件故障 (网卡/RAM)
// 2. 电磁干扰 (无线环境)
// 3. 协议栈 bug

// 网络分区 (Network Partition) — 最危险
// 原理: iptables DROP + RETURN
//
// 注入命令:
// iptables -A OUTPUT -d <target-ip> -j DROP
// iptables -A INPUT -s <target-ip> -j DROP
//
// 应用场景:
// 1. 机房网络故障
// 2. 防火墙配置错误
// 3. 云 VPC 路由故障
//
// ⚠️ 风险: 可能导致服务完全不可用！
// → 必须有 kill switch (自动恢复机制)

// 带宽限制 (Bandwidth Limit)
// 原理: tc qdisc add dev eth0 root tbf rate 1mbit burst 32kbit latency 500ms
//
// 应用场景:
// 1. 移动端弱网
// 2. 跨国带宽限制
// 3. CDN 带宽瓶颈
```

### 2.3 资源压力注入

```go
// stress.go — 资源压力注入

// CPU 压力
// 原理: 启动多个 goroutine 进行 CPU 密集型计算
//
// 注入命令 (Chaos Mesh 使用 stress-ng):
// stress-ng --cpu 4 --cpu-load 80 --timeout 60s
//
// 参数说明:
// - cpu 4: 4 个工作线程
// - cpu-load 80: 每个线程 80% CPU 使用率
// - timeout 60s: 持续 60 秒
//
// 应用场景:
// 1. 验证 HPA 是否自动扩容
// 2. 验证 Pod 的 CPU Limit 是否生效
// 3. 验证 CPU 节流 (CFS Throttling) 时的表现

// 内存压力
// 原理: 申请并填充内存 (mmap/fork)
//
// 注入命令:
// stress-ng --vm 2 --vm-bytes 512M --timeout 60s
//
// 参数说明:
// - vm 2: 2 个内存压力线程
// - vm-bytes 512M: 每个线程申请 512MB
//
// ⚠️ 风险: 可能触发 OOM Killer！
// → 设置合理的 memory limit, 确保节点还有余量

// 磁盘空间填充
// 原理: 持续写入文件直到磁盘满
//
// 应用场景:
// 1. 验证日志轮转是否生效
// 2. 验证磁盘空间不足时的行为
// 3. 验证 PVC 扩容是否及时
```

---

## 第三部分：混沌实验设计 — 源码级

### 3.1 实验设计模板

```yaml
# chaos-experiment.yaml — 实验设计模板
apiVersion: chaos.mesh/v1alpha1
kind: NetworkChaos
metadata:
  name: network-delay-experiment
  namespace: default
spec:
  # 1. 实验动作
  action: delay
  mode: all                    # all/fixed/pod-name/random
  selector:
    namespaces:
      - default
    labelSelectors:
      app: api-server          # 目标: 所有 api-server Pod
  delay:
    # 网络延迟: 200ms ± 50ms, 关联度 25%
    latency: "200ms"
    jitter: "50ms"
    correlation: "25"
    direction: to              # to: 出方向 / from: 入方向 / both: 双向

  # 2. 持续时间
  duration: 5m                 # 5 分钟后自动恢复

  # 3. 安全护栏
  scheduler:
    cron: "@every 10m"         # 定时实验
    startStage:
      before:
        - command: >
            kubectl get pods -l app=api-server
            | grep -c Running
          expectedResult: "3"
      after:
        - command: >
            kubectl get pods -l app=api-server
            | grep -c Running
          expectedResult: "3"
          timeout: 300s

  # 4. 爆炸半径控制
  affectedPods: 3              # 最多影响 3 个 Pod
```

### 3.2 稳态假设 — 如何定义"正常"

```go
// steadystate.go — 稳态假设验证
package chaos

// SteadyState 稳态假设
type SteadyState struct {
    // 错误指标
    ErrorRateThreshold float64 `json:"error_rate_threshold"`  // 错误率 < 0.1%
    SuccessRateThreshold float64 `json:"success_rate_threshold"` // 成功率 > 99.9%
    LatencyP99Threshold float64 `json:"latency_p99_threshold"`   // P99 < 500ms
    LatencyP95Threshold float64 `json:"latency_p95_threshold"`   // P95 < 200ms
    LatencyP50Threshold float64 `json:"latency_p50_threshold"`   // P50 < 50ms
    
    // 资源指标
    CPUThreshold float64 `json:"cpu_threshold"`        // CPU < 80%
    MemoryThreshold float64 `json:"memory_threshold"`     // Memory < 85%
    DiskThreshold float64 `json:"disk_threshold"`       // Disk < 90%
    
    // 业务指标
    QPSThreshold float64 `json:"qps_threshold"`         // QPS > 1000
    TransactionRate float64 `json:"transaction_rate"`   // 交易成功率 > 99.9%
    
    // 基础设施指标
    NodeReady bool `json:"node_ready"`             // 节点 Ready
    PodRunning bool `json:"pod_running"`           // Pod Running
    ServiceEndpoints []string `json:"service_endpoints"` // 服务端点列表
}

// 稳态验证函数
func (s *SteadyState) Validate(metrics PrometheusMetrics) bool {
    // 错误率检查
    errorRate := metrics.GetMetric("http_requests_total", 
        map[string]string{"status": "5xx"}) / 
        metrics.GetMetric("http_requests_total", nil)
    if errorRate > s.ErrorRateThreshold {
        return false
    }
    
    // 延迟检查
    p99Latency := metrics.GetHistogramQuantile(
        "http_request_duration_seconds", 0.99)
    if p99Latency > s.LatencyP99Threshold {
        return false
    }
    
    // 资源检查
    if metrics.GetResourceUsage("cpu") > s.CPUThreshold {
        return false
    }
    
    return true
}
```

### 3.3 安全护栏设计

```go
// safety.go — 混沌实验安全护栏

type SafetyBail struct {
    // 1. Kill Switch — 一键停止实验
    KillSwitch *KillSwitch
    
    // 2. 自动恢复 — 实验超时自动恢复
    AutoRecovery *AutoRecovery
    
    // 3. 监控告警 — 指标异常自动停止
    MonitorAlert *MonitorAlert
    
    // 4. 人工审批 — 高危实验需审批
    ManualApproval *ManualApproval
    
    // 5. 爆炸半径限制
    BlastRadius *BlastRadius
}

type KillSwitch struct {
    APIEndpoint string          // kill switch API
    Timeout     time.Duration   // 超时自动恢复
    MaxExpTime  time.Duration   // 最长实验时间
}

type AutoRecovery struct {
    Enable bool             // 是否启用自动恢复
    Timeout time.Duration    // 超时恢复时间
    Condition RecoveryCondition // 恢复条件
}

type RecoveryCondition struct {
    ErrorRateMax float64   // 错误率 > 阈值时恢复
    LatencyP99Max float64  // P99 > 阈值时恢复
    CRITICALAlerts int      // 关键告警数 > N 时恢复
}

type BlastRadius struct {
    MaxPods int              // 最大影响 Pod 数
    MaxNamespace string      // 限制命名空间
    MaxRegion string          // 限制 Region
}

// 实验审批流程:
// 1. 低风险实验 (Pod Kill, CPU Stress) → 自动执行
// 2. 中风险实验 (Network Delay, Network Loss) → 自动执行 + 监控告警
// 3. 高风险实验 (Network Partition, Pod Death) → 人工审批
// 4. 超高风险实验 (DNS Chaos, Kernel Panic) → 必须人工审批 + 变更评审
```

---

## 第四部分：生产实战 — 实验案例

### 4.1 经典实验案例

```
┌──────────────────────────────────────────────────────────────┐
│                 混沌实验案例库                                  │
│                                                              │
│  案例 1: 网络延迟实验                                         │
│  ├─ 实验: 模拟跨机房延迟 200ms ± 50ms                         │
│  ├─ 目标: API Gateway → User Service                       │
│  ├─ 预期结果:                                                │
│  │  - 连接池超时 → 触发重试                                  │
│  │  - 服务降级 → 返回缓存数据                                 │
│  │  - 熔断器 → 断开下游连接                                  │
│  ├─ 发现:                                                   │
│  │  - 重试风暴 → 下游服务被压垮                              │
│  │  - 没有超时设置 → 连接等待超时                             │
│  ├─ 修复:                                                   │
│  │  - 添加连接超时 (3s)                                     │
│  │  - 重试加退避 (1s→2s→4s)                                 │
│  │  - 设置最大重试次数 (3次)                                 │
│  └─ 改进:                                                   │
│     - 添加 Circuit Breaker (Hystrix/Sentinel)              │
│                                                              │
│  案例 2: Pod 杀死实验                                       │
│  ├─ 实验: 随机杀死 2 个 API Server Pod                      │
│  ├─ 目标: api-server (3 副本, HPA)                         │
│  ├─ 预期结果:                                                │
│  │  - K8s 自动创建新 Pod                                   │
│  │  - Service Endpoint 自动更新                             │
│  │  - 请求平滑迁移到剩余 Pod                                │
│  ├─ 发现:                                                   │
│  │  - L7 连接未关闭 → 新 Pod 收到旧连接                     │
│  │  - 启动慢 → 服务中断 30s                                │
│  ├─ 修复:                                                   │
│  │  - 添加 PreStop Hook (等待连接关闭)                       │
│  │  - 优化启动 (连接池预建)                                  │
│  │  - 添加 Readiness Probe                                 │
│  └─ 改进:                                                   │
│     - 使用 Pod Disruption Budget (PDB)                     │
│                                                              │
│  案例 3: 磁盘空间不足实验                                    │
│  ├─ 实验: 填充磁盘到 95%                                    │
│  ├─ 目标: logging-service (挂载 PVC)                        │
│  ├─ 预期结果:                                                │
│  │  - 日志轮转生效                                          │
│  │  - 磁盘清理脚本执行                                      │
│  ├─ 发现:                                                   │
│  │  - 日志轮转配置缺失 → 磁盘满                              │
│  │  - 应用无法写入日志 → 崩溃                               │
│  ├─ 修复:                                                   │
│  │  - 配置日志轮转 (logrotate)                              │
│  │  - 添加磁盘告警 (85%/90%/95%)                           │
│  │  - 设置 PVC 自动扩容                                     │
│  └─ 改进:                                                   │
│     - 日志异步写入 (kafka)                                  │
│                                                              │
│  案例 4: 数据库主库宕机实验                                  │
│  ├─ 实验: 杀死 MySQL 主库                                   │
│  ├─ 目标: MySQL 主从集群                                    │
│  ├─ 预期结果:                                                │
│  │  - 从库选举为主库                                        │
│  │  - 应用自动切换到新主库                                   │
│  ├─ 发现:                                                   │
│  │  - 切换耗时 30s → 期间所有写请求失败                      │
│  │  - 应用没有重试机制 → 返回错误                            │
│  ├─ 修复:                                                   │
│  │  - 缩短切换时间 (优化选举)                                │
│  │  - 应用层添加写重试 (最多 3 次)                           │
│  │  - 读写分离 → 读走从库, 写走主库                         │
│  └─ 改进:                                                   │
│     - 使用 ProxySQL 自动故障转移                            │
└──────────────────────────────────────────────────────────────┘
```

### 4.2 实验执行流程

```
┌─────────────────────────────────────────────────────────────┐
│                    混沌实验执行流程                            │
│                                                             │
│  1. 实验前 (Pre-Experiment)                                  │
│  ├── 确认稳态 (Prometheus 指标正常)                          │
│  ├── 确认备份 (数据库备份, 快照)                             │
│  ├── 确认监控 (Grafana Dashboard 打开)                       │
│  ├── 确认通知 (Slack/钉钉/邮件渠道可用)                       │
│  └── 确认回滚 (Rollback 计划就绪)                            │
│                                                             │
│  2. 实验中 (During Experiment)                               │
│  ├── 注入故障 (Chaos Mesh / ChaosBlade)                    │
│  ├── 持续监控 (Prometheus + Grafana)                        │
│  ├── 记录异常 (日志, 指标, 快照)                             │
│  └── 触发 Kill Switch (异常超出阈值)                         │
│                                                             │
│  3. 实验后 (Post-Experiment)                                 │
│  ├── 恢复系统 (自动/手动)                                   │
│  ├── 验证恢复 (指标恢复正常)                                 │
│  ├── 总结报告 (实验结果, 发现的漏洞, 修复建议)                 │
│  └── 更新文档 (Wiki, Runbook)                               │
└─────────────────────────────────────────────────────────────┘
```

---

## 第五部分：实战排障与调优

### 5.1 常见问题速查

| 症状 | 可能原因 | 排查命令 | 解决方案 |
|------|----------|----------|----------|
| **实验不生效** | Selector 错误/权限不足 | `kubectl get podchaos` | 检查 Selector 配置, 检查 RBAC |
| **恢复失败** | Kill Switch 未配置/超时 | Chaos Dashboard | 手动删除实验 CRD |
| **指标突增** | 正常实验行为 | Grafana 时间线 | 设置实验期告警抑制 |
| **Pod 频繁重启** | OOM/CPU Limit | `kubectl describe pod` | 调整资源限制, 添加 HPA |
| **数据不一致** | 并发写入冲突 | 应用日志 | 添加重试/补偿机制 |
| **网络分区无法恢复** | iptables 规则残留 | `iptables -L` | 手动清理, 改进实验设计 |

### 5.2 实验执行 Checklist

```markdown
## 实验前 Check
- [ ] 稳态基线已记录 (Prometheus 截图)
- [ ] 数据备份完成 (DB snapshot, PVC backup)
- [ ] 监控面板已打开 (Grafana Dashboard)
- [ ] 通知渠道已确认 (Slack/钉钉/DingTalk)
- [ ] Kill Switch 已就绪 (API/脚本)
- [ ] 回滚方案已准备 (Rollback 命令)
- [ ] 团队已通知 (Slack 频道消息)
- [ ] 实验时间段确认 (避开高峰期)

## 实验中 Monitor
- [ ] 错误率正常 (< 0.1%)
- [ ] P99 延迟正常 (< 500ms)
- [ ] Pod 无频繁重启
- [ ] 无数据不一致
- [ ] Kill Switch 可用

## 实验后 Verify
- [ ] 所有 Pod 正常运行
- [ ] 所有指标恢复正常
- [ ] 无数据丢失
- [ ] 实验报告已编写
- [ ] 发现的问题已创建 Jira/Ticket
```

---

## 第六部分：自测

### Q1：为什么混沌工程强调要在生产环境中运行，而不是在测试环境？

<details>
<summary>点击查看参考答案</summary>

**核心原因**: 测试环境永远无法完全复现生产环境的复杂性。

**测试环境的局限**:
1. **流量模式不同**: 测试流量少且规律，生产流量大且随机
2. **基础设施不同**: 测试通常是单机/小规模，生产是大规模分布式
3. **依赖关系不同**: 测试环境往往 mock 外部依赖，生产是真实依赖
4. **配置不同**: 生产环境通常有更严格的资源限制和策略

**Netflix 的发现**:
> "我们在测试环境中做了 300+ 次混沌实验，99% 都通过了。
> 但在生产环境中，我们发现了 15 个在测试环境中无法复现的问题。"

**建议**: 
- 初期: 先在预发环境/Staging 运行低风险实验
- 中期: 在非高峰生产时段运行低风险实验
- 成熟: 在生产环境持续运行自动化混沌实验

**安全过渡策略**:
1. 先做"被动式"实验 (只观察，不注入)
2. 再做"主动式"低风险实验 (Pod Kill, CPU Stress)
3. 最后做"主动式"高风险实验 (Network Partition, Disk Full)
</details>

### Q2：网络分区实验（Network Partition）的风险有哪些？如何控制爆炸半径？

<details>
<summary>点击查看参考答案</summary>

**风险**:
1. **服务完全不可用**: 分区导致服务无法通信
2. **脑裂**: 分布式系统分裂成多个"脑"，导致数据不一致
3. **数据丢失**: 分区期间写入丢失
4. **雪崩**: 分区 + 重试风暴 → 全部服务不可用

**爆炸半径控制**:
```yaml
# 1. 限制影响的 Pod 数量
mode: random
randomMax: 2  # 最多影响 2 个 Pod

# 2. 限制影响的 Namespace
selector:
  namespaces: [default]  # 只在 default namespace

# 3. 限制影响的 Region/AZ
selector:
  nodes:
    - node-1
    - node-2  # 只影响特定节点

# 4. 设置 Kill Switch
schedule:
  cron: "@every 5m"
  startStage:
    before:
      - command: "kubectl get pods | grep -c Running"
        expectedResult: "5"  # 如果 Running 的 Pod 数 < 5, 不执行
    after:
      - command: "kubectl get pods | grep -c Running"
        expectedResult: "5"
        timeout: 300s  # 300 秒内未恢复, 自动停止

# 5. 实验时长限制
duration: 1m  # 最长 1 分钟

# 6. 告警抑制
# 实验期间抑制非实验相关的告警, 避免告警风暴
```
</details>

### Q3：如何设计一个完整的混沌实验？

<details>
<summary>点击查看参考答案</summary>

**实验设计五步法**:

1. **定义稳态假设**: "API Server 错误率 < 0.1%, P99 < 500ms"
2. **选择故障**: "模拟 Pod 网络延迟 200ms"
3. **选择目标**: "api-server Pod (3 副本, 命名空间: default)"
4. **设计护栏**: "错误率 > 1% 时自动停止, 最长实验 5 分钟"
5. **定义成功标准**: "实验后 P99 < 500ms, 错误率 < 0.1%, 无数据丢失"

**实验模板**:
```yaml
apiVersion: chaos.mesh/v1alpha1
kind: NetworkChaos
metadata:
  name: api-server-network-delay
  namespace: default
spec:
  action: delay
  mode: random
  selector:
    namespaces: [default]
    labelSelectors:
      app: api-server
  delay:
    latency: "200ms"
    jitter: "50ms"
    correlation: "25"
    direction: both
  duration: 3m
  scheduler:
    cron: "@every 2h"  # 每 2 小时执行一次
```
</details>

### Q4：Chaos Mesh 和 ChaosBlade 有什么区别？怎么选？

<details>
<summary>点击查看参考答案</summary>

| 特性 | Chaos Mesh (CNCF) | ChaosBlade (阿里云) |
|------|-------------------|-------------------|
| **支持平台** | K8s 为主 | K8s/Docker/物理机/虚拟机 |
| **实验类型** | Pod/Network/IO/Stress/DNS/Cloud | 全面 (CPU/内存/网络/磁盘/JVM/Docker) |
| **实现方式** | Operator + CRD | CLI + Agent |
| **社区** | CNCF 毕业, 活跃 | 阿里开源, 国内活跃 |
| **适合场景** | K8s 原生场景 | 混合架构 (容器 + 物理机) |
| **学习成本** | 中等 (CRD 概念) | 低 (CLI 简单) |
| **生产成熟度** | 高 | 高 |

**选择建议**:
- 纯 K8s 环境 → Chaos Mesh (CNCF 标准)
- 混合架构 → ChaosBlade (支持物理机)
- 团队习惯 CLI → ChaosBlade
- 团队习惯 Yaml/CRD → Chaos Mesh
</details>

---

## 第七部分：动手验证

### 7.1 本地搭建 Chaos Mesh

```bash
# 1. 安装 Chaos Mesh
brew install chaos-mesh/chaos-mesh/chaosctl
chaosctl install --cluster-mode standalone

# 2. 验证安装
kubectl get ns chaos-testing
kubectl get pods -n chaos-testing

# 3. 创建一个简单的实验
cat > pod-kill.yaml << 'EOF'
apiVersion: chaos.mesh/v1alpha1
kind: PodChaos
metadata:
  name: pod-kill-experiment
  namespace: default
spec:
  action: pod-kill
  mode: one
  selector:
    namespaces:
      - default
    labelSelectors:
      app: nginx-test
  duration: 30s
EOF

kubectl apply -f pod-kill.yaml

# 4. 观察实验效果
kubectl get pods -w  # 观察 Pod 被杀死后自动重建

# 5. 清理实验
kubectl delete -f pod-kill.yaml
```

### 7.2 设计你的第一个混沌实验

```yaml
# 实验: 模拟 API 服务网络延迟
# 目标: 验证超时和重试配置

apiVersion: chaos.mesh/v1alpha1
kind: NetworkChaos
metadata:
  name: api-network-delay
  namespace: production
spec:
  action: delay
  mode: all
  selector:
    namespaces:
      - production
    labelSelectors:
      app: api-gateway
  delay:
    latency: "100ms"
    jitter: "20ms"
    correlation: "10"
    direction: to
  
  # 持续 2 分钟
  duration: 2m
  
  # 安全护栏
  scheduler:
    cron: "@every 6h"
    startStage:
      before:
        - command: "curl -s http://api-gateway/healthz"
          expectedResult: "200"
```

### 7.3 实验结果记录模板

```markdown
## 混沌实验记录

**实验 ID**: EXP-2026-001
**日期**: 2026-06-10
**实验人**: Ryan

### 1. 稳态基线
- 错误率: 0.02%
- P99 延迟: 120ms
- QPS: 5000
- Pod 副本: 3 (全部 Running)

### 2. 实验内容
- 类型: NetworkDelay
- 参数: 200ms ± 50ms
- 目标: api-server (3 Pods)
- 持续时间: 3m

### 3. 实验结果
- 错误率峰值: 2.5% (实验期间)
- P99 延迟峰值: 450ms
- 重试触发: 120 次
- 无数据丢失: ✅

### 4. 发现的问题
1. 重试风暴 → 下游服务被打满
2. 没有熔断器 → 长时间高延迟
3. PreStop Hook 缺失 → 新 Pod 未准备好就收到流量

### 5. 修复计划
1. [ ] 添加连接超时 (3s) + 重试退避 (P0)
2. [ ] 集成 Sentinel 熔断器 (P0)
3. [ ] 添加 Readiness Probe + PreStop Hook (P1)

### 6. 验证结果
- 修复后重跑实验: 错误率峰值 < 0.5% ✅
```

---

*本文档基于 Chaos Mesh v2.6+ 和 Netflix Chaos Monkey 方法论整理。混沌工程是一个持续改进的过程，建议从低风险实验开始，逐步建立团队信心。*
