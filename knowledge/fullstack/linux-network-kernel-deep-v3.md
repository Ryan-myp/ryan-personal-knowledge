# Linux内核网络栈深度解析

> 深入Linux网络栈：TCP/IP协议、套接字、Netfilter、性能调优。
> 源码级分析，包含生产环境最佳实践。
> 适用对象：网络工程师、SRE

---

## 1. TCP协议栈

### 1.1 核心机制

```
Linux TCP核心机制：

┌─────────────────────────────────────────────────────────────┐
│  拥塞控制算法：                                              │
│  ├── cubic：默认算法，高带宽延迟场景                          │
│  ├── bbr：Google算法，利用带宽+RTT优化                        │
│  ├── westwood：考虑带宽估计                                  │
│  └── reno：经典算法                                          │
│                                                             │
│  关键参数：                                                  │
│  ├── net.ipv4.tcp_congestion_control：拥塞控制算法            │
│  ├── net.ipv4.tcp_cwnd_clamp：窗口上限                       │
│  ├── net.ipv4.tcp_slow_start_after_idle：空闲后慢启动         │
│  └── net.ipv4.tcp_urg_inline：紧急数据内联                   │
│                                                             │
│  连接管理：                                                  │
│  ├── backlog：监听队列长度                                    │
│  ├── max_syn_backlog：SYN队列长度                            │
│  ├── tcp_abort_on_overflow：溢出时发送RST                    │
│  └── tcp_abort_on_cwr：CWR时重置连接                         │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Netfilter框架

### 2.1 数据包流向

```
Linux Netfilter数据包流向：

┌─────────────────────────────────────────────────────────────┐
│  入站方向：                                                  │
│  PREROUTING → Route → INPUT → Local Process                 │
│                                                             │
│  出站方向：                                                  │
│  Local Process → OUTPUT → Route → POSTROUTING               │
│                                                             │
│  钩子函数：                                                  │
│  ├── PREROUTING：路由前（DNAT）                              │
│  ├── INPUT：进入本机                                        │
│  ├── FORWARD：转发                                          │
│  ├── OUTPUT：本机发出                                        │
│  └── POSTROUTING：路由后（SNAT）                             │
│                                                             │
│  iptables链：                                                │
│  ├── filter：过滤（INPUT/FORWARD/OUTPUT）                   │
│  ├── nat：地址转换（PREROUTING/OUTPUT/POSTROUTING）          │
│  └── mangle：修改报文                                        │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. 自测题

### 3.1 单选题

1. Linux TCP默认拥塞控制算法是：
   A. bbr  B. cubic  C. reno  D. westwood
   答案：B

---

> 本文档适用对象：网络工程师、SRE
> 难度：资深专家级
