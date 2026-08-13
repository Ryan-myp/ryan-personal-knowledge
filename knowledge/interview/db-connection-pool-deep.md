# 数据库连接池 - 资深专家深度实现

## 一、连接池架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     数据库连接池架构                                     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   ┌─────────────┐      ┌─────────────┐      ┌─────────────┐           │
│   │  App Pool   │──────►│  Idle Conns │──────►│  DB Server  │           │
│   │  (本地)     │      │  (空闲)     │      │  (数据库)   │           │
│   └─────────────┘      └─────────────┘      └─────────────┘           │
│          │                       │                                       │
│          │               ┌───────┴───────┐                             │
│          │               │  Active Conns │                             │
│          │               │  (使用中)     │                             │
│          │               └───────────────┘                             │
│          │                       │                                     │
│          └───────────────────────┘                                     │
│                          │                                             │
│                   ┌──────┴──────┐                                      │
│                   │  Connection │                                      │
│                   │  Factory    │                                      │
│                   └─────────────┘                                      │
│                                                                         │
│   关键参数:                                                              │
│   • maxPoolSize: 最大连接数                                              │
│   • minIdle: 最小空闲连接                                                │
│   • maxWait: 最大等待时间                                                │
│   • connectionTimeout: 连接超时                                          │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、HikariCP实现

```java
public class HikariPool extends HikariConfig implements PoolBase {
    private final PriorityQueue<HikariConnectionHolder> pending;
    private final List<HikariConnectionHolder> connections;
    
    @Override
    public Connection getConnection(long timeout) throws SQLException {
        // 1. 尝试从空闲池获取
        HikariConnectionHolder connection = pollConnection(timeout);
        if (connection != null) {
            return connection;
        }
        
        // 2. 创建新连接
        if (poolSize < maximumPoolSize) {
            connection = createPoolConnection();
            return connection;
        }
        
        // 3. 等待其他线程归还连接
        return waitForConnection(timeout);
    }
}
```

## 三、连接泄漏检测

```java
public class ConnectionLeakDetector {
    private static final long LEAK_THRESHOLD_MS = 2000;
    
    public static void trackLeak(Connection conn) {
        StackTraceElement[] stack = Thread.currentThread().getStackTrace();
        long startTime = System.currentTimeMillis();
        
        Timer timer = new Timer();
        timer.schedule(new TimerTask() {
            @Override
            public void run() {
                if (System.currentTimeMillis() - startTime > LEAK_THRESHOLD_MS) {
                    logLeak(stack);
                }
            }
        }, LEAK_THRESHOLD_MS);
    }
}
```

## 四、面试高频题

### Q1: 连接池工作原理？

```
A:
1. 初始化连接池
2. 复用连接
3. 连接回收
4. 健康检查
```

### Q2: 如何选择合适的连接数？

```
A:
1. 根据CPU核心数
2. 根据磁盘IO能力
3. 根据网络带宽
4. 压测验证
```

## 五、自测题

1. 解释连接池工作原理
2. 如何检测连接泄漏？
3. 如何优化连接池性能？

---

## 参考文档

- [HikariCP源码](https://github.com/brettwooldridge/HikariCP)
- [连接池最佳实践](https://github.com/alibaba/druid/wiki)
