# Linux 网络栈深度解析

> 深入Linux网络栈：协议栈、TCP/IP、网卡驱动、性能调优。
> 源码级分析，包含生产环境网络优化。
> 适用对象：网络工程师、系统工程师

---

## 1. 协议栈架构

### 1.1 网络栈层次

```
Linux 网络栈架构：

┌─────────────────────────────────────────────────────────────┐
│                   应用层 (Application)                       │
│  └── HTTP, HTTPS, FTP, SSH...                              │
├─────────────────────────────────────────────────────────────┤
│                   传输层 (Transport)                         │
│  ├── TCP (可靠传输)                                          │
│  ├── UDP (不可靠传输)                                        │
│  └── SCTP                                                    │
├─────────────────────────────────────────────────────────────┤
│                   网络层 (Network)                           │
│  ├── IPv4                                                    │
│  ├── IPv6                                                    │
│  └── ICMP                                                    │
├─────────────────────────────────────────────────────────────┤
│                   链路层 (Link)                              │
│  ├── Ethernet                                                │
│  ├── VLAN                                                    │
│  └── ARP                                                     │
├─────────────────────────────────────────────────────────────┤
│                   内核网络栈                                 │
│  ├── Socket Layer                                            │
│  ├── Protocol Independent                                    │
│  ├── Network Device Driver                                   │
│  └── Hardware                                                │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 Go 实现网络栈核心

```go
// network_stack.go

package linux

import (
    "net"
    "sync"
)

type ProtocolStack struct {
    transport *TransportLayer
    network   *NetworkLayer
    link      *LinkLayer
}

type TransportLayer struct {
    tcp  *TCPHandler
    udp  *UDPHandler
    mu   sync.RWMutex
}

type NetworkLayer struct {
    ipv4 *IPv4Handler
    ipv6 *IPv6Handler
}

type LinkLayer struct {
    ethernet *EthernetHandler
    arp      *ARPHandler
}

func NewProtocolStack() *ProtocolStack {
    return &ProtocolStack{
        transport: &TransportLayer{
            tcp: NewTCPHandler(),
            udp: NewUDPHandler(),
        },
        network: &NetworkLayer{
            ipv4: NewIPv4Handler(),
            ipv6: NewIPv6Handler(),
        },
        link: &LinkLayer{
            ethernet: NewEthernetHandler(),
            arp:      NewARPHandler(),
        },
    }
}

func (ps *ProtocolStack) Send(data []byte, dstIP net.IP, dstPort uint16) error {
    // 传输层处理
    segment := ps.transport.Encapsulate(data, dstPort)
    
    // 网络层处理
    packet := ps.network.Encapsulate(segment, dstIP)
    
    // 链路层处理
    frame := ps.link.Encapsulate(packet)
    
    // 发送到网卡
    return ps.link.Transmit(frame)
}

func (ps *ProtocolStack) Receive(frame []byte) {
    // 链路层解封装
    packet := ps.link.Decapsulate(frame)
    
    // 网络层解封装
    segment := ps.network.Decapsulate(packet)
    
    // 传输层解封装
    data := ps.transport.Decapsulate(segment)
    
    // 交给应用层
    ps.deliverToApp(data)
}
```

---

## 2. TCP 协议实现

### 2.1 状态机

```
TCP 状态机：

                           Initial
                              |
              +---------------+---------------+
              |                               |
           SYN_SENT                        LISTEN
              |                               |
              |                               |
         SYN_RCVD                       SYN_RCVD
              |                               |
              +-------------+-----------------+
                            |
                          ESTABLISHED
                            |
                            |
                          CLOSE_WAIT
                            |
                          LAST_ACK
                            |
                          CLOSING
                            |
                          TIME_WAIT
                            |
                          CLOSED
```

### 2.2 Go 实现 TCP

```go
// tcp.go

package linux

import (
    "sync"
    "time"
)

type TCPState int

const (
    TCP_CLOSED TCPState = iota
    TCP_LISTEN
    TCP_SYN_SENT
    TCP_SYN_RECEIVED
    TCP_ESTABLISHED
    TCP_FIN_WAIT_1
    TCP_FIN_WAIT_2
    TCP_CLOSE_WAIT
    TCP_CLOSING
    TCP_LAST_ACK
    TCP_TIME_WAIT
)

type TCPConnection struct {
    state      TCPState
    seq        uint32
    ack        uint32
    sndWnd     uint16
    rcvWnd     uint16
    peerIP     string
    peerPort   uint16
    localPort  uint16
    mu         sync.Mutex
    retransmit *RetransmissionTimer
}

type RetransmissionTimer struct {
    rto     time.Duration
    count   int
    maxRetries int
}

func NewTCPConnection(localPort uint16, peerIP string, peerPort uint16) *TCPConnection {
    return &TCPConnection{
        state:    TCP_CLOSED,
        localPort: localPort,
        peerIP:   peerIP,
        peerPort: peerPort,
        retransmit: &RetransmissionTimer{
            rto:          1 * time.Second,
            maxRetries:   3,
        },
    }
}

func (tc *TCPConnection) Send(data []byte) error {
    tc.mu.Lock()
    defer tc.mu.Unlock()
    
    if tc.state != TCP_ESTABLISHED {
        return ErrConnectionNotEstablished
    }
    
    segment := tc.buildSegment(data)
    return tc.transmit(segment)
}

func (tc *TCPConnection) Receive(segment *TCPSegment) {
    tc.mu.Lock()
    defer tc.mu.Unlock()
    
    switch segment.Flags {
    case SYN:
        tc.handleSYN(segment)
    case ACK:
        tc.handleACK(segment)
    case FIN:
        tc.handleFIN(segment)
    case RST:
        tc.handleRST(segment)
    default:
        tc.handleData(segment)
    }
}

func (tc *TCPConnection) handleSYN(segment *TCPSegment) {
    tc.state = TCP_SYN_RECEIVED
    tc.ack = segment.seq + 1
    tc.sendACK()
}
```

---

## 3. 网卡驱动

### 3.1 驱动架构

```
网卡驱动架构：

┌─────────────────────────────────────────────────────────────┐
│                    网卡驱动架构                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Network Layer                                               │
│  └── net_device struct                                      │
│                                                             │
│  Driver Layer                                                │
│  ├── NIC Controller                                         │
│  ├── DMA Engine                                             │
│  └── Interrupt Handler                                      │
│                                                             │
│  Hardware Layer                                              │
│  ├── MAC Address                                            │
│  ├── PHY                                                    │
│  └── Transceiver                                            │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 Go 实现网卡驱动

```go
// nic_driver.go

package linux

import (
    "sync"
    "time"
)

type NICDriver struct {
    name       string
    mac        [6]byte
    speed      uint32
    duplex     string
    mtu        int
    txQueue    *RingBuffer
    rxQueue    *RingBuffer
    mu         sync.Mutex
}

type RingBuffer struct {
    entries  []Descriptor
    head     int
    tail     int
    count    int
    mu       sync.Mutex
}

type Descriptor struct {
    addr   uintptr
    len    uint32
    flags  uint16
    status uint16
}

func NewNICDriver(name string, mac [6]byte) *NICDriver {
    return &NICDriver{
        name:  name,
        mac:   mac,
        mtu:   1500,
        txQueue: NewRingBuffer(256),
        rxQueue: NewRingBuffer(256),
    }
}

func (nic *NICDriver) Transmit(data []byte) error {
    nic.mu.Lock()
    defer nic.mu.Unlock()
    
    // 获取描述符
    desc := nic.txQueue.Dequeue()
    if desc == nil {
        return ErrRingBufferFull
    }
    
    // 复制数据
    copy(desc.addr, data)
    desc.len = uint32(len(data))
    desc.flags = DescriptorFlagOwnerHW
    
    // 触发传输
    return nic.triggerTransmit(desc)
}

func (nic *NICDriver) Receive() []byte {
    desc := nic.rxQueue.Dequeue()
    if desc == nil {
        return nil
    }
    
    data := make([]byte, desc.len)
    copy(data, desc.addr)
    return data
}

func (nic *NICDriver) triggerTransmit(desc *Descriptor) error {
    // 写入寄存器触发传输
    // ...
    return nil
}
```

---

## 4. 性能调优

### 4.1 调优参数

```
Linux 网络调优参数：

├── TCP 参数
│   ├── tcp_rmem: 接收缓冲区
│   ├── tcp_wmem: 发送缓冲区
│   ├── tcp_max_syn_backlog: SYN队列
│   ├── tcp_fin_timeout: FIN等待时间
│   └── tcp_tw_reuse: TIME_WAIT重用
│
├── 网卡参数
│   ├── Rx/Tx Ring Size
│   ├── Interrupt Coalescing
│   └── Flow Control
│
└── 内核参数
    ├── net.core.somaxconn
    ├── net.ipv4.tcp_fastopen
    └── net.core.netdev_max_backlog
```

### 4.2 Go 实现调优

```go
// network_tuning.go

package linux

import (
    "os"
    "strconv"
)

type NetworkTuner struct {
    params map[string]int
}

type TuningResult struct {
    Param  string
    Before int
    After  int
    Error  error
}

func NewNetworkTuner() *NetworkTuner {
    return &NetworkTuner{
        params: make(map[string]int),
    }
}

func (nt *NetworkTuner) Optimize(profile string) []TuningResult {
    var results []TuningResult
    
    switch profile {
    case "high_throughput":
        results = nt.applyHighThroughput()
    case "low_latency":
        results = nt.applyLowLatency()
    case "high_concurrency":
        results = nt.applyHighConcurrency()
    }
    
    return results
}

func (nt *NetworkTuner) applyHighThroughput() []TuningResult {
    params := map[string]int{
        "net.core.rmem_max":        16777216,
        "net.core.wmem_max":        16777216,
        "net.ipv4.tcp_rmem":        4096 87380 16777216,
        "net.ipv4.tcp_wmem":        4096 65536 16777216,
        "net.core.netdev_max_backlog": 5000,
    }
    
    return nt.applyParams(params)
}

func (nt *NetworkTuner) applyParams(params map[string]int) []TuningResult {
    var results []TuningResult
    
    for param, value := range params {
        before := nt.readSysctl(param)
        err := nt.writeSysctl(param, value)
        after := nt.readSysctl(param)
        
        results = append(results, TuningResult{
            Param:  param,
            Before: before,
            After:  after,
            Error:  err,
        })
    }
    
    return results
}

func (nt *NetworkTuner) readSysctl(param string) int {
    data, err := os.ReadFile("/proc/sys/" + param)
    if err != nil {
        return 0
    }
    value, _ := strconv.Atoi(string(data))
    return value
}

func (nt *NetworkTuner) writeSysctl(param string, value int) error {
    return os.WriteFile("/proc/sys/"+param, []byte(strconv.Itoa(value)), 0644)
}
```

---

## 5. 总结

### 5.1 核心原理回顾

| 组件 | 作用 |
|------|------|
| 协议栈 | 分层处理网络数据 |
| TCP | 可靠传输控制 |
| 网卡驱动 | 硬件抽象层 |
| 性能调优 | 参数优化 |

### 5.2 最佳实践

- [ ] 根据场景选择合适的调优参数
- [ ] 监控网络性能指标
- [ ] 定期压力测试
- [ ] 建立网络基线

---

*最后更新：2026-08-11*
*作者：Ryan*
