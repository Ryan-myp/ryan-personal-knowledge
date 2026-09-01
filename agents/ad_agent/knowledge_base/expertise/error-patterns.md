---
schema_version: "1"
id: ad-error-patterns
title: 常见错误模式与解决方案
layer: experience
knowledge_type: error_pattern
platform: all
source: 错误日志 + 社区经验
source_ref: expertise/error-patterns.md
version: "1.0.0"
confidence: 0.8
updated_at: "2026-08-26"
tags: [error, troubleshooting, api]
status: published
---

# 常见错误模式与解决方案

> **来源**: 错误日志 + 社区经验
> **更新时间**: 2026-08-26

## Google Ads API 错误

### RESOURCE_EXHAUSTED (限流)
```
Error: 8 - The resource quota for the customer has been exceeded.
解决方案:
1. 实现指数退避重试
2. 降低请求频率
3. 使用批量操作
```

### DUPLICATE_ELEMENT
```
Error: 37 - The resource already exists.
解决方案:
1. 先检查是否存在
2. 使用 update 而不是 create
3. 添加唯一键校验
```

### VALIDATION_ERROR
```
Error: 102 - Some of the request fields are not valid.
解决方案:
1. 检查必填字段
2. 验证参数格式
3. 参考官方文档
```

## Meta API 错误

### (#80006) 用户限制
```
Error: User rate limit reached.
解决方案:
1. 降低请求频率
2. 使用异步批量操作
3. 等待 60 秒后重试
```

### (#200) 权限不足
```
Error: (#200) Permissions error.
解决方案:
1. 检查 app 权限范围
2. 确认 access token 有效
3. 重新授权获取新 token
```

## TikTok API 错误

### INVALID_ACCESS_TOKEN
```
Error: Invalid access token.
解决方案:
1. 刷新 access token
2. 检查 token 有效期
3. 重新授权
```

### INVALID_PARAMETER
```
Error: Invalid parameter.
解决方案:
1. 检查参数格式
2. 参考 API 文档
3. 使用校验工具
```

## DV360 API 错误

### PARTNER_ID_INVALID
```
Error: The value "0" is not valid for field "partnerId".
解决方案:
1. 确认 partner_id 正确
2. 使用正确的 customer_id
3. 检查认证配置
```

### RESOURCE_NOT_FOUND
```
Error: Resource not found.
解决方案:
1. 检查资源 ID 是否正确
2. 确认资源存在
3. 检查权限范围
```

## 参考

- [Google Ads API 错误码](https://developers.google.com/google-ads/api/docs/errors/error-codes)
- [Meta API 错误参考](https://developers.facebook.com/docs/graph-api/using-graph-api/errorhandling/)
- [TikTok Ads API 错误](https://business-api.tiktok.com/portal/docs?id=1720270248251411)
