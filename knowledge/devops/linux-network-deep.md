# Linux网络协议栈 - 资深专家深度实现

## 一、协议栈架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                   Linux 网络协议栈分层                                     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   Application Layer (应用层)                                            │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │  HTTP / TCP / UDP / SCTP / Raw IP                             │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                              │                                          │
│   Transport Layer (传输层)                                            │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │  TCP Socket / UDP Socket / netfilter                            │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                              │                                          │
│   Network Layer (网络层)                                              │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │  IP Protocol / Routing / iptables / Netfilter                   │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                              │                                          │
│   Link Layer (链路层)                                                 │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │  Ethernet / Driver / NIC Hardware                               │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、Socket编程

```go
package network

import (
    "net"
    "os"
)

// TCP Server
func StartTCPServer(port string) {
    listener, err := net.Listen("tcp", ":"+port)
    if err != nil {
        os.Fatal(err)
    }
    defer listener.Close()
    
    for {
        conn, err := listener.Accept()
        if err != nil {
            continue
        }
        go handleConnection(conn)
    }
}

// handleConnection 处理连接
func handleConnection(conn net.Conn) {
    defer conn.Close()
    
    buf := make([]byte, 4096)
    for {
        n, err := conn.Read(buf)
        if err != nil {
            return
        }
        conn.Write(buf[:n])
    }
}

// UDP Server
func StartUDPServer(port string) {
    addr, err := net.ResolveUDPAddr("udp", ":"+port)
    if err != nil {
        os.Fatal(err)
    }
    
    conn, err := net.ListenUDP("udp", addr)
    if err != nil {
        os.Fatal(err)
    }
    defer conn.Close()
    
    buf := make([]byte, 4096)
    for {
        n, remoteAddr, err := conn.ReadFromUDP(buf)
        if err != nil {
            continue
        }
        conn.WriteToUDP(buf[:n], remoteAddr)
    }
}
```

## 三、面试高频题

### Q1: TCP三次握手过程？

```
A:
1. SYN: 客户端发送同步序列号
2. SYN+ACK: 服务端确认并发送自己的序列号
3. ACK: 客户端确认服务端的序列号
```

### Q2: 如何优化网络性能？

```
A:
1. 调整TCP窗口大小
2. 启用TCP快速打开
3. 使用DPDK零拷贝
4. 调整net.core.somaxconn
```

## 四、自测题

1. 解释协议栈分层
2. 如何实现TCP Server？
3. 如何优化网络性能？

---

## 参考文档

- [Linux Networking](https://www.kernel.org/doc/html/latest/networking/)
- [TCP/IP Guide](https://www.tcpipguide.com/)
