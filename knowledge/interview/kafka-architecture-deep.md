# Kafka架构深度 - 资深专家深度实现

## 一、核心组件

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       Kafka集群架构                                      │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   ┌─────────────┐                                                      │
│   │   Producer  │ ◄── 发布消息                                         │
│   └──────┬──────┘                                                      │
│          │                                                             │
│          ▼                                                             │
│   ┌─────────────┐                                                      │
│   │   Broker    │ ──► Topic: orders                                   │
│   │   (Node 1)  │    Partition: 0,1,2,3                              │
│   └──────┬──────┘    Offset: 0,1,2,3...                              │
│          │                                                             │
│          ▼                                                             │
│   ┌─────────────┐                                                      │
│   │   Consumer  │ ◄── 消费消息                                         │
│   └─────────────┘                                                      │
│                                                                         │
│   特点:                                                                  │
│   • 分布式日志                                                           │
│   • 持久化存储                                                           │
│   • 水平扩展                                                             │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、Partition管理

```java
public class Partition {
    private final String topic;
    private final int partitionId;
    private final File logDir;
    private long highWatermark;
    private long logEndOffset;
    
    // 日志段管理
    private Map<Long, LogSegment> segments;
    
    public void append(Message message) {
        long offset = logEndOffset++;
        segments.get(offset / segmentSize).append(message);
    }
    
    public Message read(long offset) {
        return segments.get(offset / segmentSize).read(offset);
    }
}
```

## 三、Controller选举

```java
public class KRaftController extends Controller {
    private final RaftManager raft;
    private volatile boolean isLeader;
    
    @Override
    public void run() {
        while (!shuttingDown) {
            if (raft.isLeader()) {
                processMetadataChanges();
                updatePartitionLeadership();
            }
            sleep(100);
        }
    }
}
```

## 四、面试高频题

### Q1: Kafka如何保证消息顺序？

```
A:
1. 单Partition内有序
2. 分区键保证
3. 消费端顺序处理
```

### Q2: 如何实现Exactly-Once？

```
A:
1. 事务性Producer
2. 幂等性Producer
3. 两阶段提交
```

## 五、自测题

1. 解释Partition原理
2. 如何实现故障转移？
3. 如何优化吞吐？

---

## 参考文档

- [Kafka源码](https://github.com/apache/kafka)
- [Kafka设计文档](https://kafka.apache.org/design)
