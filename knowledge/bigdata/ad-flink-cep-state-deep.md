# 广告实时计算深度：Flink CEP/状态后端/Checkpoint 源码级

> 从 Flink 状态管理到 CEP 复杂事件处理，逐行解析广告实时计算

---

## 第一部分：Flink 状态后端源码深度

### 状态后端架构

```
Flink 状态后端：
┌─────────────────────────────────────────────────────────────────────┐
│ State Backend                                                      │
│ ├── MemoryStateBackend: 内存状态（开发测试）                         │
│ ├── FsStateBackend: 文件系统状态（生产推荐）                          │
│ └── RocksDBStateBackend: 嵌入式 RocksDB（超大状态）                  │
│                                                                     │
│ 状态类型：                                                           │
│ • ValueState: 单个值                                                 │
│ • ListState: 列表                                                   │
│ • MapState: 键值对                                                  │
│ • ReducingState: 聚合状态                                            │
│ • AggregatingState: 累加状态                                         │
│                                                                     │
│ 状态恢复：                                                           │
│ 1. Checkpoint 快照 → HDFS/S3                                       │
│ 2. Savepoint → 手动触发                                             │
│ 3. Restart Policy → 自动重启                                        │
└─────────────────────────────────────────────────────────────────────┘
```

### RocksDBStateBackend 源码逐行解析

```java
// Flink 源码：RocksDBStateBackend.java
public class RocksDBStateBackend extends AbstractStateBackend {
    
    private final String dbPath;
    private final boolean enableIncrementalCheckpoints;
    private final CheckpointStorage checkpointStorage;
    
    @Override
    public <K, NV> ValueStateDescriptor<NV> createValueState(
            String stateName, TypeInformation<NV> typeInfo) {
        
        // 1. 创建状态描述符
        ValueStateDescriptor<NV> descriptor = new ValueStateDescriptor<>(
            stateName, typeInfo);
        
        // 2. 注册到 RocksDB
        try (ColumnFamilyHandle cfHandle = rocksDb.openColumnFamily(
                stateName)) {
            
            // 3. 序列化器
            Serializer<NV> serializer = 
                typeInfo.createSerializer(executionConfig);
            
            // 4. 创建状态句柄
            return new RocksDBKeyValueState<>(
                descriptor,
                serializer,
                cfHandle,
                this.keyGroupsRange
            );
        } catch (RocksDBException e) {
            throw new IllegalStateException(
                "Failed to open RocksDB state", e);
        }
    }
    
    @Override
    public void snapshotState(
            long checkpointId,
            long timestamp,
            CheckpointOutputStream out,
            CheckpointOptions checkpointOptions) 
            throws Exception {
        
        // 1. 开始增量 Checkpoint
        if (enableIncrementalCheckpoints) {
            // 1.1 快照当前 SST 文件
            List<SSTFile> sstFiles = 
                rocksDb.getCurrentSSTFiles();
            
            // 1.2 复制增量文件
            for (SSTFile sst : sstFiles) {
                checkpointStorage.storeIncrementally(
                    checkpointId, sst);
            }
        } else {
            // 2. 全量快照
            checkpointStorage.storeFull(
                checkpointId, rocksDb.getAllData());
        }
    }
}
```

---

## 第二部分：CEP 复杂事件处理

### CEP 架构

```
广告 CEP 场景：
1. 欺诈检测：同一设备 10 分钟内点击 > 50 次 → 标记为欺诈
2. 预算预警：单日花费 > 预算 80% → 告警
3. 转化漏斗：曝光 → 点击 → 注册 → 付费，转化率 < 1% → 优化建议
4. 竞对监控：竞品广告出现频率突增 → 通知
```

### CEP 源码逐行解析

```java
// Flink CEP 源码：ComplexEventProcessing.java
public class AdFraudDetector extends CEPProcessFunction {
    
    @Override
    public void open(Configuration parameters) {
        // 1. 定义模式
        Pattern<AdEvent, ?> fraudPattern = Pattern
            .<AdEvent>begin("click")
            .times(50)
            .within(Time.minutes(10))  // 10 分钟内
            .where(new FilterFunction<AdEvent>() {
                @Override
                public boolean filter(AdEvent event) {
                    // 同一设备
                    return event.deviceId != null;
                }
            });
        
        // 2. 选择函数
        PatternSelectFunction<AdEvent, FraudAlert> selectFn = 
            new PatternSelectFunction<AdEvent, FraudAlert>() {
                @Override
                public FraudAlert select(
                    Map<String, List<AdEvent>> pattern) {
                    
                    List<AdEvent> clicks = pattern.get("click");
                    
                    return new FraudAlert(
                        clicks.get(0).deviceId,
                        clicks.size(),
                        clicks.get(0).timestamp
                    );
                }
            };
        
        // 3. 编译模式
        CompiledPattern<AdEvent, ?> compiled = 
            PatternCompiler.compile(fraudPattern, selectFn);
    }
}
```

---

## 第三部分：自测题

### Q1: 为什么广告实时计算用 Flink 而不是 Storm？

**A**: Flink 有 Exactly-Once 语义、状态管理、CEP、Table API 等更完整的功能。

### Q2: RocksDB 状态后端适合什么场景？

**A**: 状态超过内存时（> 100GB），如用户行为序列、实时特征。

### Q3: Checkpoint 和 Savepoint 的区别？

**A**: Checkpoint 自动触发用于恢复，Savepoint 手动触发用于版本迁移。

---

## 第四部分：生产实践

### 1. 状态管理

```
状态管理要点：
1. 合理选择状态后端
2. 定期 Checkpoint
3. 监控状态大小
4. 设置超时策略
```

### 2. CEP 优化

```
CEP 优化要点：
1. 模式简化
2. 窗口大小控制
3. 索引优化
4. 并行度调整
```

### 3. 性能调优

```
性能调优要点：
1. 背压监控
2. 内存配置
3. 并行度设置
4. 序列化优化
```
