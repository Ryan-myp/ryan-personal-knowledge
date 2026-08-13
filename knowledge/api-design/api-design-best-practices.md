# API 设计最佳实践

> RESTful、GraphQL、gRPC 设计原则与实战。

---

## 1. RESTful 设计原则

```
GET    /api/v1/campaigns       # 获取列表
GET    /api/v1/campaigns/{id}  # 获取详情
POST   /api/v1/campaigns       # 创建
PUT    /api/v1/campaigns/{id}  # 全量更新
PATCH  /api/v1/campaigns/{id}  # 部分更新
DELETE /api/v1/campaigns/{id}  # 删除
```

---

## 2. 响应格式

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "campaigns": [...],
    "total": 100,
    "page": 1,
    "page_size": 20
  },
  "request_id": "abc123"
}
```

---

## 3. 错误码规范

| HTTP 状态码 | 含义 | 使用场景 |
|------------|------|----------|
| 200 | 成功 | 正常响应 |
| 400 | 请求错误 | 参数校验失败 |
| 401 | 未授权 | Token 无效/过期 |
| 403 | 禁止访问 | 权限不足 |
| 404 | 资源不存在 | ID 错误 |
| 429 | 请求过多 | 限流 |
| 500 | 服务器错误 | 内部异常 |

---

## 4. 版本控制

```
# URL 路径
/api/v1/campaigns
/api/v2/campaigns

# 请求头
Accept: application/vnd.ads.v1+json

# 查询参数
/api/campaigns?version=1
```

---

## 5. 性能优化

| 优化 | 说明 |
|------|------|
| 分页 | 避免返回全量数据 |
| 缓存 | ETag/Last-Modified |
| 压缩 | Gzip/Brotli |
| 批量 | 减少请求次数 |

---

**参考**: REST API 设计指南、Google API 设计规范
