# Kafka架构深度 - 资深专家深度实现

## 一、Kafka核心架构

### 1.1 集群架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      Kafka集群架构                                       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│                         ┌─────────────┐                                 │
│                         │   ZooKeeper │ 元数据管理                      │
│                         │   Cluster   │                                 │
│                         └──────┬──────┘                                 │
│                                │                                       │
│              ┌─────────────────┼─────────────────┐                      │
│              │                 │                 │                      │
│        ┌─────▼─────┐    ┌─────▼─────┐    ┌─────▼─────┐                 │
│        │  Broker 0 │    │  Broker 1 │    │  Broker 2 │                 │
│        │  Controller│   │           │    │           │                 │
│        └─────┬─────┘    └─────┬─────┘    └─────┬─────┘                 │
│              │                │                │                       │
│     ┌────────┼────────┐  ┌────┼────┐    ┌─────┼─────┐                  │
│     │        │        │  │    │    │    │     │     │                  │
│  ┌──▼──┐ ┌──▼──┐ ┌───▼──┐┌─▼──┐┌─▼──┐┌─▼──┐┌─▼──┐┌─▼──┐             │
│  │Part │ │Part │ │Part  ││Part││Part││Part││Part││Part│                │
│  │  0  │ │  1  │ │  2   ││  0 ││  1 ││  2 ││  0 ││  1 │                │
│  └─────┘ └─────┘ └──────┘└────┘└────┘└────┘└────┘└────┘               │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

### 1.2 核心数据结构

```go
// Topic结构
type Topic struct {
    Name      string
    Partitions map[int32]*Partition
    Config    TopicConfig
}

// Partition结构
type Partition struct {
    Topic       string
    PartitionID int32
    Leader      int32
    Replicas    []int32
    ISR         []int32          // In-Sync Replicas
    Log         *Log             // 日志对象
}

// Log结构（核心）
type Log struct {
    baseOffset   int64          // 起始offset
    maxOffset    int64          // 最大offset
    segments     []*Segment     // 段文件
    index        *Index         // 偏移量索引
    dirty        bool           // 是否脏数据
}

// Segment结构
type Segment struct {
    baseOffset int64
    index      *TimeIndex     // 时间索引
    indexFile  *IndexFile     // 索引文件
    logFile    *LogFile       // 日志文件
}
```

## 二、生产者实现

### 2.1 生产者架构

```go
type Producer struct {
    brokers     []*Broker
    cluster     *ClusterMetadata
    sender      *Sender
    recorder    *Recorder
    sampler     *Sampler
    
    // 分区器
    partitioner Partitioner
    
    // 拦截器
    interceptors []ProducerInterceptor
}

// 发送消息
func (p *Producer) Send(topic string, key []byte, value []byte) (*RecordMetadata, error) {
    // 1. 序列化
    serializedKey, _ := p.serializer.Serialize(key)
    serializedValue, _ := p.serializer.Serialize(value)
    
    // 2. 选择分区
    partition := p.partition(partitionKey, topic)
    
    // 3. 构建记录
    record := &ProducerRecord{
        Topic:     topic,
        Partition: partition,
        Key:       serializedKey,
        Value:     serializedValue,
    }
    
    // 4. 拦截器处理
    for _, interceptor := range p.interceptors {
        record = interceptor.OnSend(record)
    }
    
    // 5. 发送到缓冲区
    p.sender.send(record)
    
    return record.Metadata, nil
}
```

### 2.2 批量发送优化

```go
type BatchBuilder struct {
    records     []*ProducerRecord
    batchSize   int
    maxBytes    int
    lingerMs    int64
    lastFlush   time.Time
}

func (b *BatchBuilder) add(record *ProducerRecord) error {
    // 检查批次大小
    if b.size+record.Size > b.maxBytes {
        b.flush()
    }
    
    b.records = append(b.records, record)
    b.size += record.Size
    
    // 检查滞留时间
    if time.Since(b.lastFlush) > time.Duration(b.lingerMs)*time.Millisecond {
        b.flush()
    }
    
    return nil
}

func (b *BatchBuilder) flush() {
    if len(b.records) == 0 {
        return
    }
    
    // 批量发送
    batch := NewBatch(b.records)
    b.sender.send(batch)
    
    b.records = b.records[:0]
    b.size = 0
    b.lastFlush = time.Now()
}
```

## 三、消费者实现

### 3.1 消费者组架构

```go
type ConsumerGroup struct {
    groupID    string
    brokers    []*Broker
    coordinator *GroupCoordinator
    members    map[string]*ConsumerMember
    
    //  rebalance策略
    rebalanceProtocol RebalanceProtocol
}

// 消费者成员
type ConsumerMember struct {
    memberID  string
    clientID  string
    host      string
    assignment *ConsumerAssignment
}

// 重新平衡协议
type RebalanceProtocol interface {
    OnJoin(group *ConsumerGroup, member *ConsumerMember) error
    OnLeave(group *ConsumerGroup, member *ConsumerMember) error
    OnSync(group *ConsumerGroup, member *ConsumerMember) ([]*TopicPartition, error)
}
```

### 3.2 Offset管理

```go
type OffsetManager struct {
    broker    *Broker
    topic     string
    partition int32
    offsets   map[int64]int64  // timestamp -> offset
}

// 提交Offset
func (om *OffsetManager) Commit(offset int64, metadata string) error {
    record := &OffsetCommitRequest{
        Group:     om.groupID,
        Topic:     om.topic,
        Partition: om.partition,
        Offset:    offset,
        Metadata:  []byte(metadata),
    }
    
    response, err := om.broker.OffsetCommit(record)
    if err != nil {
        return err
    }
    
    if response.ErrorCode != ErrCodeNone {
        return errors.New(response.ErrorMessage)
    }
    
    return nil
}

// 拉取消息
func (om *OffsetManager) Poll(maxMessages int) ([]*ConsumerRecord, error) {
    fetchReq := &FetchRequest{
        Group:     om.groupID,
        Topic:     om.topic,
        Partition: om.partition,
        Offset:    om.currentOffset,
        MaxBytes:  1024 * 1024,
    }
    
    response, err := om.broker.Fetch(fetchReq)
    if err != nil {
        return nil, err
    }
    
    // 处理消息
    records := make([]*ConsumerRecord, 0, len(response.Records))
    for _, record := range response.Records {
        records = append(records, &ConsumerRecord{
            Topic:     om.topic,
            Partition: om.partition,
            Offset:    record.Offset,
            Key:       record.Key,
            Value:     record.Value,
        })
    }
    
    return records, nil
}
```

## 四、Broker核心实现

### 4.1 日志写入

```go
type LogAppender struct {
    log      *Log
    batch    []*ProducerRecord
    maxBytes int64
}

func (a *LogAppender) append(records []*ProducerRecord) (*LogAppendResult, error) {
    // 1. 验证批次
    if !a.isValid(records) {
        return nil, ErrInvalidRecord
    }
    
    // 2. 追加到当前segment
    result := &LogAppendResult{}
    for _, record := range records {
        offset, err := a.log.append(record)
        if err != nil {
            return nil, err
        }
        result.Offset = offset
        result.Size += int64(len(record.Value))
    }
    
    // 3. 更新高水位
    a.log.updateHighWatermark()
    
    return result, nil
}
```

### 4.2 消息存储

```go
type MessageSet struct {
    magic      byte
    attributes byte
    timestamp  int64
    key        []byte
    value      []byte
    headers    map[string][]byte
}

// 压缩方式
const (
    NoCompression byte = 0
    GzipCompression byte = 1
    SnappyCompression byte = 2
    LZ4Compression byte = 3
    ZstdCompression byte = 4
)

// 写入消息集
func (s *Log) append(messages []*MessageSet) (int64, error) {
    if len(messages) == 0 {
        return s.lastOffset(), nil
    }
    
    // 获取或创建segment
    segment := s.getOrCreateSegment(messages[0].Timestamp)
    
    // 追加消息
    baseOffset := segment.append(messages)
    
    // 刷盘策略
    if s.config.FlushMessages > 0 && segment.messagesCount >= s.config.FlushMessages {
        segment.flush()
    }
    
    return baseOffset, nil
}
```

## 五、ISR机制

### 5.1 ISR维护

```go
type ISRManager struct {
    broker     *Broker
    replicas   map[int32]*Replica
    config     ISRConfig
}

type ISRConfig struct {
    MinInSyncReplicas    int
    ReplicaLagTimeMaxMs  int64
    ReplicaFetchMaxBytes int
}

// 维护ISR
func (m *ISRManager) updateISR(topic string, partition int32) {
    leader := m.getLeader(topic, partition)
    followers := m.getFollowers(topic, partition)
    
    // 计算每个follower的延迟
    isr := []int32{leader.brokerID}
    for _, follower := range followers {
        lag := follower.lastCaughtUpTime - time.Now().UnixNano()
        if lag < m.config.ReplicaLagTimeMaxMs * 1e6 {
            isr = append(isr, follower.brokerID)
        }
    }
    
    // 更新ISR
    m.setISR(topic, partition, isr)
}
```

### 5.2 副本同步

```go
type Fetcher struct {
    broker     *Broker
    target     *Broker
    fetchState *FetchState
}

func (f *Fetcher) fetch() (*FetchResponse, error) {
    // 构建拉取请求
    req := &FetchRequest{
        ReplicaID:     f.broker.brokerID,
        MaxWaitMs:     500,
        MinBytes:      1,
        MaxBytes:      10485760,
        FallBehind:    false,
    }
    
    // 添加topic-partition
    for _, tp := range f.fetchState.assignedPartitions {
        req.addPartition(tp.Topic, tp.Partition, f.fetchState.offset(tp))
    }
    
    // 发送请求
    resp, err := f.target.Fetch(req)
    if err != nil {
        return nil, err
    }
    
    // 处理响应
    f.processResponse(resp)
    
    return resp, nil
}
```

## 六、面试高频题

### Q1: Kafka为什么快？

```
A:
1. 顺序写磁盘
2. Zero-Copy技术
3. 分页机制
4. 批量发送
5. 分区并行
```

### Q2: 如何保证消息不丢失？

```
A:
1. 生产者：acks=all
2. Broker：replication-factor≥3
3. ISR：min.insync.replicas≥2
4. 消费者：手动提交offset
```

### Q3: 如何保证消息不重复？

```
A:
1. 幂等生产者：enable.idempotence=true
2. 事务生产者：producer.transactional.id
3. 消费者：去重表/唯一索引
```

## 七、自测题

1. 解释Kafka的分区机制
2. ISR是如何维护的？
3. 如何实现Exactly-Once语义？

---

## 参考文档

- [Kafka官方文档](https://kafka.apache.org/documentation/)
- [Kafka源码](https://github.com/apache/kafka)
