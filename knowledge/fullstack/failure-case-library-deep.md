# 故障排查案例库 - 资深专家深度实现

## 一、案例1: Redis内存溢出

### 问题现象
```
10:30:00 ERROR: OOM command not allowed when used memory > 'maxmemory'
10:30:01 ERROR: Client connection dropped
```

### 排查过程
```bash
# 1. 检查内存使用
redis-cli info memory

# 2. 查找大Key
redis-cli --bigkeys

# 3. 检查淘汰策略
redis-cli config get maxmemory-policy
```

### 解决方案
```yaml
# redis.conf
maxmemory 2gb
maxmemory-policy allkeys-lru

# 淘汰大Key
redis-cli KEYS "large:*" | xargs redis-cli DEL
```

## 二、案例2: MySQL慢查询

### 问题现象
```
Slow queries: 1200/min
Average response time: 2.5s
```

### 排查过程
```sql
-- 1. 开启慢查询日志
SET GLOBAL slow_query_log = 'ON';
SET GLOBAL long_query_time = 1;

-- 2. 分析慢查询
SELECT * FROM mysql.slow_log 
WHERE start_time > DATE_SUB(NOW(), INTERVAL 1 HOUR)
ORDER BY query_time DESC;

-- 3. 检查执行计划
EXPLAIN SELECT * FROM orders WHERE user_id = 123;
```

### 解决方案
```sql
-- 添加索引
ALTER TABLE orders ADD INDEX idx_user_id (user_id);

-- 优化查询
SELECT id, name FROM orders WHERE user_id = 123 LIMIT 10;
```

## 三、案例3: K8s Pod频繁重启

### 问题现象
```
Pod frontend-abc123 restart count: 15/hour
Events: BackOff restarting failed container
```

### 排查过程
```bash
# 1. 查看Pod状态
kubectl describe pod frontend-abc123

# 2. 查看容器日志
kubectl logs frontend-abc123 --previous

# 3. 检查资源限制
kubectl top pod frontend-abc123
```

### 解决方案
```yaml
# 调整资源限制
spec:
  containers:
  - name: frontend
    image: nginx
    resources:
      requests:
        memory: "128Mi"
        cpu: "100m"
      limits:
        memory: "256Mi"
        cpu: "500m"
```

## 四、面试高频题

### Q1: 如何进行故障排查？

```
A:
1. 观察现象
2. 收集日志
3. 定位根因
4. 实施修复
5. 验证结果
```

### Q2: 如何预防故障？

```
A:
1. 监控告警
2. 容量规划
3. 混沌工程
4. 演练预案
```

## 五、自测题

1. 解释故障排查流程
2. 如何快速定位问题？
3. 如何制定应急预案？

---

## 参考文档

- [故障排查最佳实践](https://landing.google.com/sre/books/)
- [K8s排障指南](https://kubernetes.io/docs/tasks/debug/)
