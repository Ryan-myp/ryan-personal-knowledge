# TCP/IP 协议栈深度实战：从内核到应用

## 一、TCP 协议栈内核实现

### 1.1 Linux TCP 内核架构

```
应用层 (send/recv)
    ↓
传输层 (TCP Socket)
    ├── 拥塞控制 (Cubic/BBR)
    ├── 流量控制 (窗口机制)
    ├── 可靠性 (重传/确认)
    └── 连接管理 (三次握手/四次挥手)
    ↓
网络层 (IP)
    ├── 路由选择
    ├── ICMP
    └── Fragmentation
    ↓
数据链路层 (ETH)
    ├── ARP
    └── MAC 帧
    ↓
物理层 (网卡)
```

**内核数据结构：**

```c
// struct sock - 内核中所有套接字的基类
struct sock {
    struct sk_buff_head sk_receive_queue;  // 接收队列
    struct sk_buff_head sk_write_queue;    // 发送队列
    struct tcp_sock *tp;                   // TCP 专用数据
    struct inet_sock inet;                 // IP 层信息
    wait_queue_head_t sk_wait_bit;         // 等待队列
    atomic_t sk_refcnt;                    // 引用计数
    unsigned long sk_flags;                // 标志位
};

// struct tcp_sock - TCP 专用状态
struct tcp_sock {
    u32 snd_una;           // 最早未确认序列号
    u32 snd_nxt;           // 下一个要发送的序列号
    u32 rcv_nxt;           // 下一个期望接收的序列号
    u32 ssthresh;          // 慢启动阈值
    u32 snd_cwnd;          // 拥塞窗口
    u32 snd_cwnd_cnt;      // 拥塞窗口计数器
    u32 snd_wnd;           // 发送窗口
    u32 rcv_wnd;           // 接收窗口
    u32 rcv_space;         // 接收空间
    struct tcp_congestion_ops *congestion_ops;  // 拥塞控制算法
    int rtt_min;           // 最小 RTT
    int pmtu_disc;         // PMTU 发现
};
```

### 1.2 TCP 三次握手内核实现

```c
// 服务器端 accept 流程
SYN_RECV 状态机转换:
1. 收到 SYN → 发送 SYN+ACK → 进入 SYN_RECV 状态
2. 收到 ACK → 进入 ESTABLISHED 状态 → accept() 返回

// 内核实现伪代码
void tcp_v4_rcv(struct sk_buff *skb) {
    struct tcphdr *th = tcp_hdr(skb);
    struct sock *sk = tcp_v4_lookup(...);
    
    switch (sk->state) {
    case TCP_LISTEN:
        // 新连接，创建 sock
        newsock = inet_csk_accept(sk);
        // 发送 SYN+ACK
        tcp_send_ack(sk);
        break;
    case TCP_SYN_RECV:
        // 收到 ACK，连接建立
        tcp_set_state(sk, TCP_ESTABLISHED);
        wake_up_interruptible(sk->sk_sleep);
        break;
    }
}

// 客户端 connect 流程
1. 发送 SYN → 进入 SYN_SENT 状态
2. 收到 SYN+ACK → 发送 ACK → 进入 ESTABLISHED 状态
3. connect() 返回
```

### 1.3 TCP 四次挥手内核实现

```c
// 主动关闭方
FIN_WAIT_1 → FIN_WAIT_2 → TIME_WAIT → CLOSED
被动关闭方
CLOSE_WAIT → LAST_ACK → CLOSED

// TIME_WAIT 状态
// 内核保持 TIME_WAIT 2MSL (默认 60 秒)
// 目的: 确保最后一个 ACK 到达对方, 防止旧连接报文干扰新连接
struct timer_list tw_timer;  // TIME_WAIT 定时器
```

## 二、Linux 网络栈优化

### 2.1 网络参数调优

**内核参数 (sysctl)：**

```bash
# TCP 连接相关
net.ipv4.tcp_max_syn_backlog = 65535          # SYN 队列长度
net.ipv4.tcp_syncookies = 1                   # SYN Cookie
net.ipv4.tcp_tw_reuse = 1                     # TIME_WAIT 复用
net.ipv4.tcp_fin_timeout = 30                 # FIN_WAIT 超时
net.ipv4.tcp_keepalive_time = 600             # 保活探测间隔
net.ipv4.tcp_keepalive_intvl = 30             # 保活探测频率
net.ipv4.tcp_keepalive_probes = 5             # 保活探测次数

# 缓冲区相关
net.core.rmem_max = 16777216                  # 最大接收缓冲区
net.core.wmem_max = 16777216                  # 最大发送缓冲区
net.ipv4.tcp_rmem = 4096 87380 16777216      # TCP 接收缓冲区
net.ipv4.tcp_wmem = 4096 65536 16777216      # TCP 发送缓冲区

# 连接跟踪
net.netfilter.nf_conntrack_max = 1048576      # 连接跟踪表大小
```

### 2.2 Go 网络编程最佳实践

```go
package network

import (
	"context"
	"net"
	"time"
)

// 优化 TCP 连接配置
func NewOptimizedDialer() *net.Dialer {
	return &net.Dialer{
		Timeout:   5 * time.Second,
		KeepAlive: 30 * time.Second,
		DualStack: true, // IPv4/IPv6 双栈
	}
}

// 连接池实现
type TCPConnPool struct {
	pool      chan *net.Conn
	maxIdle   int
	idleTimeout time.Duration
	dialer    *net.Dialer
}

func NewTCPConnPool(maxIdle int, idleTimeout time.Duration) *TCPConnPool {
	return &TCPConnPool{
		pool:      make(chan *net.Conn, maxIdle),
		maxIdle:   maxIdle,
		idleTimeout: idleTimeout,
		dialer:    NewOptimizedDialer(),
	}
}

func (p *TCPConnPool) Get(ctx context.Context) (*net.Conn, error) {
	select {
	case conn := <-p.pool:
		// 检查连接是否仍然有效
		if time.Since((*conn).(*net.TCPConn).RemoteAddr().(*net.TCPAddr).String()) > p.idleTimeout {
			(*conn).Close()
			return p.dial(ctx)
		}
		return conn, nil
	default:
		return p.dial(ctx)
	}
}

func (p *TCPConnPool) Put(conn *net.Conn) {
	select {
	case p.pool <- conn:
	default:
		conn.Close()
	}
}
```

## 三、UDP 协议与性能优化

### 3.1 UDP 内核实现

```c
// UDP 数据报处理
void udp_rcv(struct sk_buff *skb) {
    struct udphdr *uh = udp_hdr(skb);
    struct sock *sk = udp_get_socket(...);
    
    // 检查校验和
    if (!udp_lib_checksum_complete(skb)) {
        kfree_skb(skb);
        return;
    }
    
    // 投递到应用层
    skb_queue_tail(&sk->sk_receive_queue, skb);
    sk->sk_data_ready(sk);
}
```

### 3.2 Go UDP 高性能编程

```go
func UDPServer(addr string, handler func([]byte)) error {
	// 使用 UDP Conn 而非 PacketConn
	conn, err := net.ListenUDP("udp", &net.UDPAddr{
		IP:   net.ParseIP("0.0.0.0"),
		Port: 8080,
	})
	if err != nil {
		return err
	}
	defer conn.Close()
	
	// 预分配缓冲区
	buf := make([]byte, 65535)
	
	for {
		n, remoteAddr, err := conn.ReadFromUDP(buf)
		if err != nil {
			continue
		}
		
		// 拷贝数据（避免引用外部缓冲区）
		data := make([]byte, n)
		copy(data, buf[:n])
		
		// 异步处理
		go handler(data)
	}
}
```

## 四、自测题

1. TCP 三次握手和四次挥手的内核状态机是怎样的？
2. TIME_WAIT 状态的作用是什么？如何优化？
3. Go 网络编程中如何避免 goroutine 泄漏？

## 五、动手验证

```bash
# 1. 使用 tcpdump 抓包分析三次握手
# 2. 使用 ss 查看连接状态
# 3. 调整 sysctl 参数优化性能
# 4. 使用 Go net 包实现高性能服务器
```
