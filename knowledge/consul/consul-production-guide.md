# Consul 生产环境实战

> 服务发现、键值存储、多数据中心部署。

---

## 1. 核心架构

```
┌─────────────────────────────────────────────────────────────┐
│                     Consul Cluster                          │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────┐  ┌─────────┐  ┌─────────┐                     │
│  │ Server  │  │ Server  │  │ Server  │  (Raft 共识)        │
│  │   1     │  │   2     │  │   3     │                     │
│  └────┬────┘  └────┬────┘  └────┬────┘                     │
│       │            │            │                          │
│       └────────────┴────────────┘                          │
│                    │                                       │
│           ┌────────▼────────┐                              │
│           │   Clients       │  (Agent/Proxy)               │
│           └─────────────────┘                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. 服务注册

```bash
# 注册服务
consul services register \
  -name=ads-service \
  -port=8080 \
  -tag=production \
  -check=http://localhost:8080/health

# 查询服务
consul services list
consul catalog service ads-service
```

---

## 3. 键值存储

```bash
# 设置值
consul kv put configs/ads/rate_limit 1000

# 获取值
consul kv get configs/ads/rate_limit

# 监听变更
consul kv watch configs/ads/rate_limit
```

---

## 4. 生产实践

| 实践 | 说明 |
|------|------|
| 奇数节点 | Server 节点应为奇数 (3/5/7) |
| 多 DC | 跨数据中心部署提高可用性 |
| 加密 | 启用 TLS 和 gossip 加密 |
| 备份 | 定期备份 KV 存储 |

---

**参考**: Consul 官方文档、分布式系统一致性模式
