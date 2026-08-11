# API 设计深度解析

> 深入 API 设计：RESTful、GraphQL、gRPC、版本控制、安全设计。
> 包含真实生产环境 API 设计实践。
> 适用对象：后端工程师、架构师、产品经理

---

## 1. RESTful API 设计

### 1.1 资源命名规范

```
RESTful 资源命名规则：

1. 使用名词（表示资源）
   ✅ GET /users
   ✅ GET /orders
   ❌ GET /getUsers

2. 使用复数（表示资源集合）
   ✅ GET /users
   ✅ GET /users/123
   ❌ GET /user
   ❌ GET /user/123

3. 使用小写字母和连字符
   ✅ /user-orders
   ✅ /product-details
   ❌ /userOrders
   ❌ /user_orders

4. 嵌套表示从属关系
   ✅ GET /users/123/orders
   ✅ POST /users/123/orders
   ❌ GET /orders?user_id=123
```

### 1.2 HTTP 方法

```
HTTP 方法与语义：

┌──────────┬────────────────┬─────────────────────────────┐
│ 方法     │ 语义           │ 示例                        │
├──────────┼────────────────┼─────────────────────────────┤
│ GET      │ 获取资源       │ GET /users/123              │
│ POST     │ 创建资源       │ POST /users                 │
│ PUT      │ 全量更新       │ PUT /users/123              │
│ PATCH    │ 部分更新       │ PATCH /users/123            │
│ DELETE   │ 删除资源       │ DELETE /users/123           │
└──────────┴────────────────┴─────────────────────────────┘
```

### 1.3 Go 实现

```go
// api_handler.go

package api

import (
    "encoding/json"
    "net/http"
)

type User struct {
    ID    int    `json:"id"`
    Name  string `json:"name"`
    Email string `json:"email"`
}

type Response struct {
    Code    int         `json:"code"`
    Message string      `json:"message"`
    Data    interface{} `json:"data"`
}

func GetUser(w http.ResponseWriter, r *http.Request) {
    id := r.URL.Query().Get("id")
    // 查询用户
    user := &User{ID: 123, Name: "John", Email: "john@example.com"}
    
    json.NewEncoder(w).Encode(Response{
        Code:    200,
        Message: "success",
        Data:    user,
    })
}

func CreateUser(w http.ResponseWriter, r *http.Request) {
    var user User
    json.NewDecoder(r.Body).Decode(&user)
    // 创建用户
    user.ID = 124
    
    w.WriteHeader(http.StatusCreated)
    json.NewEncoder(w).Encode(Response{
        Code:    201,
        Message: "created",
        Data:    user,
    })
}
```

---

## 2. GraphQL API

### 2.1 类型系统

```
GraphQL Schema：

type Query {
    user(id: ID!): User
    users(page: Int, limit: Int): [User!]!
    searchUsers(query: String!): [User!]!
}

type User {
    id: ID!
    name: String!
    email: String!
    orders: [Order!]!
    createdAt: String!
}

type Order {
    id: ID!
    userId: ID!
    amount: Float!
    status: OrderStatus!
    createdAt: String!
}

enum OrderStatus {
    PENDING
    PAID
    SHIPPED
    COMPLETED
    CANCELLED
}
```

### 2.2 Go 实现

```go
// graphql_handler.go

package api

import (
    "github.com/graphql-go/graphql"
)

var userType *graphql.Object
var queryType *graphql.Object
var schema graphql.Schema

func InitGraphQL() error {
    userType = graphql.NewObject(graphql.ObjectConfig{
        Name: "User",
        Fields: graphql.Fields{
            "id":     &graphql.Field{Type: graphql.ID},
            "name":   &graphql.Field{Type: graphql.String},
            "email":  &graphql.Field{Type: graphql.String},
            "orders": &graphql.Field{Type: graphql.NewList(orderType)},
        },
    })
    
    queryType = graphql.NewObject(graphql.ObjectConfig{
        Name: "Query",
        Fields: graphql.Fields{
            "user": &graphql.Field{
                Type: userType,
                Args: graphql.FieldConfigArgument{
                    "id": &graphql.ArgumentConfig{Type: graphql.NewNonNull(graphql.ID)},
                },
                Resolve: func(p graphql.ResolveParams) (interface{}, error) {
                    // 查询用户
                    return nil, nil
                },
            },
        },
    })
    
    var err error
    schema, err = graphql.NewSchema(graphql.SchemaConfig{
        Query: queryType,
    })
    return err
}
```

---

## 3. gRPC API

### 3.1 Protobuf 定义

```protobuf
syntax = "proto3";

package user;

option go_package = "github.com/example/user";

// 服务定义
service UserService {
    // 获取用户
    rpc GetUser(GetUserRequest) returns (GetUserResponse);
    // 创建用户
    rpc CreateUser(CreateUserRequest) returns (CreateUserResponse);
    // 用户流
    rpc WatchUsers(WatchUsersRequest) returns (stream UserEvent);
}

// 消息定义
message GetUserRequest {
    string id = 1;
}

message GetUserResponse {
    User user = 1;
}

message User {
    string id = 1;
    string name = 2;
    string email = 3;
    int64 created_at = 4;
}

message WatchUsersRequest {
    string last_id = 1;
}

message UserEvent {
    string type = 1;  // CREATED/UPDATED/DELETED
    User user = 2;
}
```

### 3.2 Go 实现

```go
// grpc_server.go

package api

import (
    "context"
    "log"
    "net"
    
    "google.golang.org/grpc"
    pb "github.com/example/user/proto"
)

type Server struct {
    pb.UnimplementedUserServiceServer
}

func (s *Server) GetUser(ctx context.Context, req *pb.GetUserRequest) (*pb.GetUserResponse, error) {
    // 查询用户
    user := &pb.User{
        Id: req.GetId(),
        Name: "John",
        Email: "john@example.com",
    }
    return &pb.GetUserResponse{User: user}, nil
}

func (s *Server) WatchUsers(req *pb.WatchUsersRequest, stream pb.UserService_WatchUsersServer) error {
    // 流式返回
    return nil
}

func StartGRPCServer(port int) error {
    lis, err := net.Listen("tcp", fmt.Sprintf(":%d", port))
    if err != nil {
        return err
    }
    
    s := grpc.NewServer()
    pb.RegisterUserServiceServer(s, &Server{})
    
    log.Printf("gRPC server listening on port %d", port)
    return s.Serve(lis)
}
```

---

## 4. API 版本控制

### 4.1 版本策略

```
API 版本控制策略：

1. URL 路径版本
   ├── /v1/users
   ├── /v2/users
   └── 优点：直观；缺点：URL 变化

2. 请求头版本
   ├── Accept: application/vnd.api.v1+json
   └── 优点：URL 稳定；缺点：不够直观

3. 查询参数版本
   ├── /users?version=1
   └── 优点：简单；缺点：污染查询参数

推荐：URL 路径版本（最常用）
```

### 4.2 迁移策略

```
API 迁移最佳实践：

1. 向后兼容
   ├── 新增字段不删除旧字段
   ├── 新增可选参数
   └── 新接口用新路径

2. 灰度发布
   ├── 新接口并行运行
   ├── 逐步迁移流量
   └── 监控错误率

3. 废弃通知
   ├── 提前通知废弃
   ├── 提供迁移指南
   └── 设置废弃日期
```

---

## 5. API 安全设计

### 5.1 认证方案

```
API 认证方案：

1. API Key
   ├── 适合：内部服务、简单场景
   └── 实现：请求头传递

2. JWT (JSON Web Token)
   ├── 适合：无状态认证
   ├── 组成：Header.Payload.Signature
   └── 特点：自包含、可验证

3. OAuth 2.0
   ├── 适合：第三方授权
   ├── 流程：授权码模式
   └── 特点：安全、标准化
```

### 5.2 Go JWT 实现

```go
// jwt_auth.go

package api

import (
    "time"
    "github.com/golang-jwt/jwt/v5"
)

type Claims struct {
    UserID   int    `json:"user_id"`
    Username string `json:"username"`
    jwt.RegisteredClaims
}

func GenerateToken(userID int, username string, secret string, expire time.Duration) (string, error) {
    claims := Claims{
        UserID:   userID,
        Username: username,
        RegisteredClaims: jwt.RegisteredClaims{
            ExpiresAt: jwt.NewNumericDate(time.Now().Add(expire)),
            IssuedAt:  jwt.NewNumericDate(time.Now()),
        },
    }
    
    token := jwt.NewWithClaims(jwt.SigningMethodHS256, claims)
    return token.SignedString([]byte(secret))
}

func VerifyToken(tokenString string, secret string) (*Claims, error) {
    token, err := jwt.ParseWithClaims(tokenString, &Claims{}, func(token *jwt.Token) (interface{}, error) {
        return []byte(secret), nil
    })
    
    if err != nil {
        return nil, err
    }
    
    claims, ok := token.Claims.(*Claims)
    if !ok || !token.Valid {
        return nil, jwt.ErrTokenInvalidClaims
    }
    
    return claims, nil
}
```

---

## 6. API 性能优化

### 6.1 缓存策略

```
API 缓存策略：

1. 客户端缓存
   ├── Cache-Control: max-age=3600
   └── ETag 验证

2. CDN 缓存
   ├── 静态资源缓存
   └── 边缘节点分发

3. 服务端缓存
   ├── Redis 缓存
   ├── 内存缓存
   └── 查询结果缓存
```

### 6.2 Go 缓存实现

```go
// api_cache.go

package api

import (
    "sync"
    "time"
)

type CacheEntry struct {
    Value     interface{}
    ExpiresAt time.Time
}

type APICache struct {
    items sync.Map
    ttl   time.Duration
}

func NewAPICache(ttl time.Duration) *APICache {
    return &APICache{ttl: ttl}
}

func (c *APICache) Get(key string) (interface{}, bool) {
    if v, ok := c.items.Load(key); ok {
        entry := v.(*CacheEntry)
        if time.Now().Before(entry.ExpiresAt) {
            return entry.Value, true
        }
        c.items.Delete(key)
    }
    return nil, false
}

func (c *APICache) Set(key string, value interface{}) {
    c.items.Store(key, &CacheEntry{
        Value:     value,
        ExpiresAt: time.Now().Add(c.ttl),
    })
}
```

---

## 7. 总结

### 7.1 设计原则回顾

| 原则 | 说明 |
|------|------|
| 资源命名 | 使用名词复数，小写连字符 |
| HTTP 语义 | 正确使用 GET/POST/PUT/PATCH/DELETE |
| 错误处理 | 统一错误格式，合理 HTTP 状态码 |
| 版本控制 | 向后兼容，逐步迁移 |
| 安全设计 | JWT/OAuth，防止常见攻击 |

### 7.2 最佳实践

- [ ] 遵循 RESTful 规范
- [ ] 统一错误响应格式
- [ ] 实施版本控制
- [ ] 配置合理的缓存策略
- [ ] 进行安全审计

---

*最后更新：2026-08-11*
*作者：Ryan*
