# API设计深度解析

> 深入API设计：RESTful、GraphQL、gRPC、OpenAPI。
> 源码级分析，包含生产环境最佳实践。
> 适用对象：后端工程师、API架构师

---

## 1. RESTful API设计

### 1.1 资源设计

```
RESTful API设计原则：

┌─────────────────────────────────────────────────────────────┐
│  1. 资源命名                                                │
│     ├── 使用名词，不用动词                                    │
│     ├── 复数形式：/users, /orders                            │
│     └── 层级结构：/users/{id}/orders                        │
│                                                             │
│  2. HTTP方法语义                                             │
│     ├── GET：获取资源（幂等）                                 │
│     ├── POST：创建资源                                       │
│     ├── PUT：全量更新（幂等）                                 │
│     ├── PATCH：部分更新                                       │
│     └── DELETE：删除资源（幂等）                             │
│                                                             │
│  3. 状态码规范                                               │
│     ├── 200：成功                                           │
│     ├── 201：创建成功                                       │
│     ├── 400：请求参数错误                                    │
│     ├── 401：未认证                                         │
│     ├── 403：无权限                                         │
│     ├── 404：资源不存在                                     │
│     ├── 429：请求过于频繁                                    │
│     └── 500：服务器内部错误                                 │
│                                                             │
│  4. 版本控制                                                 │
│     ├── URL路径：/api/v1/users                              │
│     ├── Header：Accept: application/vnd.api.v1+json         │
│     └── 查询参数：/users?version=1                          │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. GraphQL

### 2.1 Schema设计

```
GraphQL Schema示例：

┌─────────────────────────────────────────────────────────────┐
│  type Query {                                                │
│    user(id: ID!): User                                       │
│    users(limit: Int, offset: Int): [User]                    │
│    search(query: String!): [SearchResult]                    │
│  }                                                           │
│                                                             │
│  type Mutation {                                             │
│    createUser(input: CreateUserInput!): User                 │
│    updateUser(id: ID!, input: UpdateUserInput!): User        │
│    deleteUser(id: ID!): Boolean                              │
│  }                                                           │
│                                                             │
│  type User {                                                 │
│    id: ID!                                                   │
│    name: String!                                             │
│    email: String!                                            │
│    orders(limit: Int): [Order]                               │
│  }                                                           │
│                                                             │
│  input CreateUserInput {                                     │
│    name: String!                                             │
│    email: String!                                            │
│  }                                                           │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. 自测题

### 3.1 单选题

1. RESTful API中，幂等操作不包括：
   A. GET  B. POST  C. PUT  D. DELETE
   答案：B

---

> 本文档适用对象：后端工程师、API架构师
> 难度：资深专家级
