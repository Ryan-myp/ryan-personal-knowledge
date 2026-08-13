# gRPC 微服务通信深度解析

> 深入gRPC：协议设计、序列化、流式通信、服务发现。
> 源码级分析，包含生产环境最佳实践。
> 适用对象：微服务工程师、后端工程师

---

## 1. gRPC 协议设计

### 1.1 HTTP/2 传输

```
gRPC 基于 HTTP/2：

├── 多路复用
│   └── 单连接多流

├── 二进制帧
│   └── 高效的帧结构

├── 头部压缩
│   └── HPACK算法

└── 流控
    └── 流量控制
```

### 1.2 Go 实现 gRPC 核心

```go
// grpc_core.go

package grpc

import (
    "context"
    "sync"
)

type Server struct {
    port      int
    services  map[string]*Service
    handlers  map[string]Handler
    mu        sync.Mutex
}

type Service struct {
    Name    string
    Methods map[string]*Method
}

type Method struct {
    Name       string
    RequestType string
    ResponseType string
    StreamType  StreamType
}

type StreamType int

const (
    Unary StreamType = iota
    ServerStreaming
    ClientStreaming
    BidiStreaming
)

type Handler func(context.Context, interface{}) (interface{}, error)

func NewServer(port int) *Server {
    return &Server{
        port:     port,
        services: make(map[string]*Service),
        handlers: make(map[string]Handler),
    }
}

func (s *Server) RegisterService(service *Service, handler Handler) {
    s.mu.Lock()
    defer s.mu.Unlock()
    s.services[service.Name] = service
    for methodName := range service.Methods {
        key := service.Name + "/" + methodName
        s.handlers[key] = handler
    }
}

func (s *Server) Start() error {
    // 监听端口
    // 处理连接
    // 分发请求
    return nil
}
```

---

## 2. Protobuf 序列化

### 2.1 消息格式

```
Protobuf 消息格式：

├── 变长编码
│   ├── Varint: 整数编码
│   ├── Fixed32: 固定32位
│   └── Fixed64: 固定64位
│
├── 字段编号
│   └── 字段编号 +  wire type
│
└── 扩展机制
    └── 向后兼容
```

### 2.2 Go 实现 Protobuf

```go
// protobuf.go

package grpc

import (
    "encoding/binary"
    "bytes"
)

type Message interface {
    Marshal() ([]byte, error)
    Unmarshal(data []byte) error
}

type Field struct {
    Number  int
    Type    Type
    Value   interface{}
}

type Type int

const (
    TypeVarint Type = iota
    TypeFixed64
    TypeLengthDelimited
    TypeFixed32
)

type Serializer struct{}

func (s *Serializer) Encode(fieldNumber int, fieldType Type, value interface{}) []byte {
    var buf bytes.Buffer
    
    // 写入tag
    tag := (fieldNumber << 3) | int(typeToWire[fieldType])
    buf.WriteByte(byte(tag))
    
    // 写入值
    switch fieldType {
    case TypeVarint:
        encodeVarint(&buf, value.(uint64))
    case TypeFixed32:
        buf.WriteByte(byte(value.(uint32)))
        buf.WriteByte(byte(value.(uint32) >> 8))
        buf.WriteByte(byte(value.(uint32) >> 16))
        buf.WriteByte(byte(value.(uint32) >> 24))
    case TypeLengthDelimited:
        data := value.([]byte)
        encodeVarint(&buf, uint64(len(data)))
        buf.Write(data)
    }
    
    return buf.Bytes()
}

func (s *Serializer) Decode(data []byte) ([]Field, error) {
    var fields []Field
    reader := bytes.NewReader(data)
    
    for reader.Len() > 0 {
        tagByte, err := reader.ReadByte()
        if err != nil {
            break
        }
        
        fieldNumber := int(tagByte) >> 3
        wireType := tagByte & 0x7
        
        field := Field{
            Number: fieldNumber,
            Type:   wireToType[wireType],
        }
        
        // 解码值
        field.Value, err = s.decodeValue(reader, wireType)
        if err != nil {
            return nil, err
        }
        
        fields = append(fields, field)
    }
    
    return fields, nil
}
```

---

## 3. 流式通信

### 3.1 四种模式

```
gRPC 流式通信模式：

├── Unary RPC
│   └── 请求 → 响应
│
├── Server Streaming
│   └── 请求 → 多个响应
│
├── Client Streaming
│   └── 多个请求 → 响应
│
└── Bidirectional Streaming
    └── 多个请求 ↔ 多个响应
```

### 3.2 Go 实现流式

```go
// streaming.go

package grpc

import (
    "context"
    "sync"
)

type ServerStream interface {
    Send(m interface{}) error
    Recv() (interface{}, error)
    Context() context.Context
}

type ClientStream interface {
    Send(m interface{}) error
    Recv() (interface{}, error)
    CloseSend() error
    Context() context.Context
}

type streamingServer struct {
    ctx     context.Context
    sendCh  chan interface{}
    recvCh  chan interface{}
    mu      sync.Mutex
}

func (ss *streamingServer) Send(m interface{}) error {
    ss.sendCh <- m
    return nil
}

func (ss *streamingServer) Recv() (interface{}, error) {
    select {
    case m := <-ss.recvCh:
        return m, nil
    case <-ss.ctx.Done():
        return nil, ss.ctx.Err()
    }
}

type streamingClient struct {
    sendCh  chan interface{}
    recvCh  chan interface{}
}

func (sc *streamingClient) Send(m interface{}) error {
    sc.sendCh <- m
    return nil
}

func (sc *streamingClient) Recv() (interface{}, error) {
    return <-sc.recvCh, nil
}
```

---

## 4. 服务发现

### 4.1 服务注册

```
gRPC 服务发现：

├── DNS Service Discovery
│   └── SRV记录
│
├── Consul
│   └── HTTP API
│
├── etcd
│   └── Watch机制
│
└── ZooKeeper
    └── 临时节点
```

### 4.2 Go 实现服务发现

```go
// service_discovery.go

package grpc

import (
    "sync"
    "time"
)

type ServiceInstance struct {
    ID       string
    Address  string
    Port     int
    Tags     map[string]string
    Metadata map[string]string
}

type ServiceDiscovery struct {
    services map[string][]*ServiceInstance
    mu       sync.RWMutex
}

func NewServiceDiscovery() *ServiceDiscovery {
    return &ServiceDiscovery{
        services: make(map[string][]*ServiceInstance),
    }
}

func (sd *ServiceDiscovery) Register(instance *ServiceInstance) {
    sd.mu.Lock()
    defer sd.mu.Unlock()
    
    key := instance.Address + ":" + string(instance.Port)
    sd.services[key] = append(sd.services[key], instance)
}

func (sd *ServiceDiscovery) Deregister(instance *ServiceInstance) {
    sd.mu.Lock()
    defer sd.mu.Unlock()
    
    key := instance.Address + ":" + string(instance.Port)
    instances := sd.services[key]
    for i, inst := range instances {
        if inst.ID == instance.ID {
            sd.services[key] = append(instances[:i], instances[i+1:]...)
            break
        }
    }
}

func (sd *ServiceDiscovery) GetServices(serviceName string) []*ServiceInstance {
    sd.mu.RLock()
    defer sd.mu.RUnlock()
    
    return sd.services[serviceName]
}
```

---

## 5. 总结

### 5.1 核心原理回顾

| 组件 | 作用 |
|------|------|
| HTTP/2 | 传输层 |
| Protobuf | 序列化 |
| 流式通信 | 高效传输 |
| 服务发现 | 动态路由 |

### 5.2 最佳实践

- [ ] 使用Protobuf定义接口
- [ ] 合理设计流式通信
- [ ] 实现服务发现
- [ ] 监控RPC性能

---

*最后更新：2026-08-11*
*作者：Ryan*
