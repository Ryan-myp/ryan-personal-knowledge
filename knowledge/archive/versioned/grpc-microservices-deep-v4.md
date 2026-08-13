# gRPC微服务通信深度解析

> 深入gRPC：Protobuf、流式通信、拦截器、性能优化。
> 源码级分析，包含生产环境最佳实践。
> 适用对象：后端工程师、微服务工程师

---

## 1. Protobuf定义

### 1.1 消息格式

```
Protobuf消息定义：

┌─────────────────────────────────────────────────────────────┐
│  syntax = "proto3";                                         │
│                                                             │
│  message User {                                              │
│    string id = 1;                                            │
│    string name = 2;                                          │
│    int32 age = 3;                                            │
│    repeated string tags = 4;  // 重复字段                     │
│    map<string, string> metadata = 5;  // 键值对               │
│  }                                                           │
│                                                             │
│  enum Status {                                               │
│    UNKNOWN = 0;                                              │
│    ACTIVE = 1;                                               │
│    INACTIVE = 2;                                             │
│  }                                                           │
│                                                             │
│  字段编号：1-15占用1字节，16-2047占用2字节                    │
│  建议：频繁使用的字段用小编号                                   │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. gRPC服务定义

### 2.1 服务类型

```
gRPC四种服务类型：

┌─────────────────────────────────────────────────────────────┐
│  1. 简单RPC                                                  │
│     rpc GetUser(GetUserRequest) returns (User) {}           │
│                                                             │
│  2. 服务端流式                                               │
│     rpc ListUsers(ListUsersRequest) returns (stream User) {}│
│                                                             │
│  3. 客户端流式                                               │
│     rpc UploadFiles(stream File) returns (UploadResponse) {}│
│                                                             │
│  4. 双向流式                                                 │
│     rpc Chat(stream Message) returns (stream Message) {}    │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. 自测题

### 3.1 单选题

1. gRPC默认使用的序列化格式是：
   A. JSON  B. XML  C. Protobuf  D. Thrift
   答案：C

---

> 本文档适用对象：后端工程师、微服务工程师
> 难度：资深专家级
