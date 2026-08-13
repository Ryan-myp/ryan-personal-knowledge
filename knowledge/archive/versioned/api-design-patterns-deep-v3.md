# API设计模式深度解析

> 深入API设计：RESTful、GraphQL、gRPC、OpenAPI规范。
> 源码级分析，包含生产环境最佳实践。
> 适用对象：后端工程师、API架构师

---

## 1. RESTful API设计

### 1.1 资源设计

```
RESTful API设计原则：

┌─────────────────────────────────────────────────────────────┐
│  资源命名：                                                  │
│  ├── 使用名词（复数）：/users, /orders                      │
│  ├── 层级结构：/users/{id}/orders                           │
│  └── 避免动词：不使用 /getUsers, /createUser                 │
│                                                             │
│  HTTP方法：                                                  │
│  ├── GET：查询资源                                           │
│  ├── POST：创建资源                                          │
│  ├── PUT：全量更新                                           │
│  ├── PATCH：部分更新                                         │
│  └── DELETE：删除资源                                        │
│                                                             │
│  状态码：                                                    │
│  ├── 200：成功                                              │
│  ├── 201：创建成功                                          │
│  ├── 400：请求参数错误                                       │
│  ├── 401：未认证                                            │
│  ├── 403：无权限                                            │
│  └── 404：资源不存在                                        │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. GraphQL设计

### 2.1 Schema定义

```
GraphQL Schema设计：

┌─────────────────────────────────────────────────────────────┐
│  Type定义：                                                  │
│  type User {                                                 │
│    id: ID!                                                   │
│    name: String!                                             │
│    email: String!                                            │
│    orders: [Order!]!                                         │
│  }                                                           │
│                                                             │
│  Query：                                                     │
│  type Query {                                                │
│    user(id: ID!): User                                       │
│    users(limit: Int, offset: Int): [User!]!                  │
│  }                                                           │
│                                                             │
│  Mutation：                                                  │
│  type Mutation {                                             │
│    createUser(input: CreateUserInput!): User!                │
│    updateUser(id: ID!, input: UpdateUserInput!): User!       │
│    deleteUser(id: ID!): Boolean!                             │
│  }                                                           │
│                                                             │
│  优势：                                                      │
│  ├── 精确数据获取，避免过获取                                 │
│  ├── 强类型Schema                                            │
│  └── 单一端点                                               │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. 自测题

### 3.1 单选题

1. RESTful API中，创建资源应该使用：
   A. GET  B. POST  C. PUT  D. DELETE
   答案：B

---

> 本文档适用对象：后端工程师、API架构师
> 难度：资深专家级
