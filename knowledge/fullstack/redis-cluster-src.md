# Redis 集群/哨兵/源码深度：从原理到生产排障

> 逐行源码解析 + 生产排障案例 + 对比分析 + 动手验证

---

## 第一部分：入门引导（5 分钟速览）

### 类比理解 Redis 集群

想象一个图书馆：

```
单机 Redis = 一个小书店，所有书在一个货架上
  → 找书快，但货架满了就没地方了

Redis Cluster = 连锁书店，每家分店管一部分书
  → 16384 个"槽位" = 16384 个书架编号
  → 每台服务器管一部分书架
  → 书满了可以搬书架（迁移槽位）
```

**核心问题**：怎么知道一本书在第几个书架？

**答案**：CRC16(key) % 16384 → 槽位号 → 哪台服务器管这个槽位

---

### 快速上手代码

```go
package main

import (
    "context"
    "fmt"
    "github.com/redis/go-redis/v9"
)

func main() {
    // 单机模式
    rdb := redis.NewClient(&redis.Options{
        Addr:     "localhost:6379",
        Password: "",
        DB:       0,
    })
    
    // Cluster 模式 — 注意是 NewClusterClient
    clusterRDB := redis.NewClusterClient(&redis.ClusterOptions{
        Addrs: []string{
            "localhost:7000", // 节点 0
            "localhost:7001", // 节点 1
            "localhost:7002", // 节点 2
        },
        MaxRedirects: 8, // 最多重定向 8 次
    })
    
    // 基本操作
    ctx := context.Background()
    err := clusterRDB.Set(ctx, "user:1001", "alice", 0).Err()
    if err != nil {
        panic(err)
    }
    
    val, err := clusterRDB.Get(ctx, "user:1001").Result()
    if err != nil {
        panic(err)
    }
    fmt.Println(val) // alice
}
```

---

## 第二部分：Redis Cluster 分片原理（逐行解析）

### 2.1 槽位映射 — 为什么是 16384？

**Q: 为什么不直接按 hash(key) % N 台服务器来分？**

A: 如果服务器数量变化（扩容/缩容），所有 key 的归属都会变，导致大规模数据迁移。

**Redis Cluster 的方案**：引入中间层 — 16384 个槽位

```
key → CRC16(key) % 16384 → 槽位号 → 哪台服务器管这个槽位
```

扩容时只需要迁移**部分槽位**，而不是所有数据。

### 2.2 CRC16 源码级解析

```go
package rediscluster

import (
    "encoding/binary"
    "fmt"
)

// CRC16 多项式：0xA001 (CRC-16/ARC)
// 为什么选这个多项式？因为它计算速度快，分布均匀
const crc16TableSize = 256
const crc16Polynomial uint16 = 0xA001

// crc16Table 预计算的 CRC16 表
// 预计算的好处：O(1)  lookup，比每次计算快 100 倍
var crc16Table [crc16TableSize]uint16

func init() {
    // 初始化 CRC16 查找表
    // 这一步在程序启动时执行一次，之后所有 CRC16 计算都用这个表
    for i := uint16(0); i < crc16TableSize; i++ {
        crc := uint16(i) << 8 // 左移 8 位
        for j := 0; j < 8; j++ {
            // 核心算法：如果最高位为 1，则异或多项式
            // 这相当于在 GF(2) 域上做除法
            if crc&(1<<15) != 0 {
                crc = (crc << 1) ^ crc16Polynomial
            } else {
                crc = crc << 1
            }
        }
        crc16Table[i] = crc & 0xFFFF // 保留低 16 位
    }
}

// CRC16 计算给定数据的 CRC16 校验值
// 时间复杂度：O(n)，n 是数据长度
// 空间复杂度：O(1)，只用了一个预计算表
func CRC16(data []byte) uint16 {
    crc := uint16(0)
    for _, b := range data {
        // 关键：用当前字节和 CRC 的高 8 位做 XOR，查表得到新 CRC
        // 这比逐位计算快得多
        crc = (crc << 8) ^ crc16Table[((crc>>8)^b)&0xFF]
    }
    return crc
}

// KeyToSlot 将 key 映射到 0-16383 的槽位
func KeyToSlot(key string) int {
    // 检查是否有 {hash}tag（Redis Cluster 的特殊语法）
    // 例如：user:{1001}:profile 和 user:{1001}:orders 会在同一个槽位
    // 这保证了相关 key 的本地性
    left := -1
    right := -1
    for i, b := range key {
        if b == '{' && left == -1 {
            left = i
        } else if b == '}' && left != -1 {
            right = i
            break
        }
    }
    
    if right > left {
        // 使用 hash tag 的内容计算槽位
        key = key[left+1:right]
    }
    
    return int(CRC16([]byte(key)) % 16384)
}

// 使用示例
func main() {
    fmt.Println(KeyToSlot("user:1001"))     // 槽位号
    fmt.Println(KeyToSlot("user:1002"))     // 不同的槽位
    fmt.Println(KeyToSlot("user:{1001}:p")) // 和 user:1001 相同槽位（hash tag）
    fmt.Println(KeyToSlot("user:{1001}:o")) // 和 user:1001 相同槽位（hash tag）
}
```

**逐行解释关键点：**

| 行号 | 代码 | 为什么这样写 | 如果不这样会怎样 |
|------|------|-------------|-----------------|
| 17-18 | `const crc16Polynomial uint16 = 0xA001` | CRC-16/ARC 标准多项式，反转后的值 | 用其他多项式也可以，但这个分布均匀且业界标准 |
| 23-32 | `init()` 初始化表 | 启动时计算一次，之后 O(1) 查找 | 不预计算的话每次 CRC16 都要逐位计算，慢 100 倍 |
| 44-48 | `(crc << 8) ^ crc16Table[((crc>>8)^b)&0xFF]` | 核心算法：查表法 | 逐位计算会慢很多，尤其是大 key |
| 54-64 | hash tag 处理 | 保证相关 key 在同一节点 | 不用的话 user:1001:profile 和 user:1001:orders 可能在不同节点 |

### 2.3 槽位分配 — 生产中的真实配置

```go
// 生产环境中的槽位分配方案
// 3 主 3 从，每主管 5461 个槽位

type SlotAssignment struct {
    NodeID   string
    IP       string
    Port     int
    SlotRange [2]int // [start, end]
    Replicas []string // 从节点 ID 列表
}

// 标准 3 主 3 从配置
func Standard3MasterConfig() []SlotAssignment {
    return []SlotAssignment{
        {
            NodeID: "master-0",
            IP:     "10.0.0.1",
            Port:   7000,
            SlotRange: [2]int{0, 5460},      // 槽位 0-5460
            Replicas: []string{"slave-0"},
        },
        {
            NodeID: "master-1",
            IP:     "10.0.0.2",
            Port:   7001,
            SlotRange: [2]int{5461, 10922},   // 槽位 5461-10922
            Replicas: []string{"slave-1"},
        },
        {
            NodeID: "master-2",
            IP:     "10.0.0.3",
            Port:   7002,
            SlotRange: [2]int{10923, 16383},  // 槽位 10923-16383
            Replicas: []string{"slave-2"},
        },
    }
}

// 槽位迁移 — 扩容时的核心操作
type SlotMigration struct {
    SourceNode string
    TargetNode string
    Slot       int
    Keys       []string
    State      MigrationState
}

type MigrationState int

const (
    Migrating MigrationState = iota // 源节点正在迁移出去
    Importing                        // 目标节点正在导入进来
    Done                             // 迁移完成
)

// MIGRATE SLOTS — 逐步迁移槽位
// 生产中的安全迁移流程：
// 1. 在源节点设置槽位状态为 migrating
// 2. 在目标节点设置槽位状态为 importing
// 3. 逐步迁移 key（每次迁移一批）
// 4. 迁移完成后切换状态为 done
// 5. 客户端会自动感知新状态
func MigrateSlots(config []SlotAssignment, source, target string, slots []int) error {
    // 第 1 步：在源节点标记这些槽位为 migrating
    // 源节点的 CLUSTER SETSLOT <slot> NODE <null>
    // 告诉客户端：这些槽位正在迁移出去
    
    // 第 2 步：在目标节点标记为 importing
    // 目标节点的 CLUSTER SETSLOT <slot> NODE <target-node-id>
    // 告诉客户端：这些槽位即将由目标节点接管
    
    // 第 3 步：逐批迁移 key
    // 使用 MIGRATE 命令，带 COPY REPLACE 选项
    // MIGRATE <host> <port> "" 0 <timeout> COPY REPLACE
    // 注意：keys 参数为空字符串，配合 KEYS 参数指定具体 key
    
    // 第 4 步：迁移完成后
    // 源节点：CLUSTER SETSLOT <slot> NODE <target-node-id>
    // 目标节点：CLUSTER SETSLOT <slot> NODE <target-node-id>
    
    return nil
}
```

### 2.4 槽位迁移的生产排障案例

**故障场景**：扩容时槽位迁移卡住

```
问题：从 3 主 3 从扩容到 4 主 4 从时，迁移槽位 12000-13644 到新的 master-3
      迁移进行到一半就停了，客户端开始报 MOVED 错误
```

**排查过程：**

```bash
# 1. 检查集群状态
redis-cli -p 7000 CLUSTER INFO
# cluster_state:ok 或 cluster_state:fail

# 2. 检查槽位分配
redis-cli -p 7000 CLUSTER SLOTS

# 3. 检查节点连接
redis-cli -p 7000 CLUSTER NODES

# 4. 检查迁移进度
redis-cli -p 7000 CLUSTER GETKEYSINSLOT 12000 100
# 返回 100 个属于槽位 12000 的 key

# 5. 检查目标节点
redis-cli -p 7003 CLUSTER GETKEYSINSLOT 12000 100
# 如果返回空，说明迁移还没开始
```

**根本原因**：目标节点内存不足，无法接受新 key

**解决方案**：
1. 扩容目标节点内存
2. 使用 `CLUSTER SETSLOT <slot> NODE <null>` 暂停迁移
3. 清理目标节点内存
4. 重新开始迁移

---

## 第三部分：Gossip 协议深度解析

### 3.1 Gossip 协议是什么？

**类比**：公司里的"八卦传播"

```
员工 A 遇到新员工 B → A 告诉 B 公司所有人是谁
员工 A 定期遇到同事 C → A 告诉 C 公司最近的消息
员工 B 遇到同事 D → B 告诉 D 公司最近的消息
...
最终所有人都知道了公司的最新状况
```

**Redis Cluster 中的 Gossip**：

```
节点 A 遇到节点 B → A 告诉 B 自己知道的槽位分配
节点 A 定期遇到节点 C → A 告诉 C 最新的集群状态
节点 B 遇到节点 D → B 告诉 D 最新的集群状态
...
最终所有节点都知道完整的集群拓扑
```

### 3.2 Gossip 消息类型

| 消息类型 | 作用 | 何时发送 |
|---------|------|---------|
| **MEET** | 发现新节点 | 管理员执行 `CLUSTER MEET ip port` |
| **PING** | 心跳 + 状态同步 | 每秒钟发送一次 |
| **PONG** | PING/PONG 的回复 | 收到 PING/MEET 时回复 |
| **FAIL** | 标记节点宕机 | 检测到节点不可达时 |
| **BUSY** | 槽位迁移中 | 客户端访问正在迁移的槽位 |

### 3.3 Ping/Pong 源码级解析

```go
package gossip

import (
    "encoding/binary"
    "fmt"
    "net"
    "time"
)

// GossipMessage  gossip 协议的消息格式
// Redis 的二进制协议，不是 JSON！
type GossipMessage struct {
    MsgType       byte      // 消息类型
    Flags         byte      // 标志位
    Unknown1      uint16    // 保留
    KnownMsgCount uint16    // 已知消息数量
    SenderID      [16]byte  // 发送者节点 ID（40 位 hex 转 16 字节）
    SenderPort    uint16    // 发送者集群总线端口
    SenderIP      [4]byte   // 发送者 IP
    Timestamp     uint64    // 时间戳
    ConfigEpoch   uint64    // 配置纪元（用于冲突解决）
    SlaveOf       [16]byte  // 主节点 ID（如果是从节点）
    PingPayload   []byte    // PING 消息的 payload
}

// Encode 将消息编码为字节数组
// 格式：[msgType][flags][unknown1][knownMsgCount][senderID][senderPort][senderIP][timestamp][configEpoch][slaveOf][payload]
func (m *GossipMessage) Encode() []byte {
    buf := make([]byte, 0, 256)
    
    // 1. msgType + flags
    buf = append(buf, m.MsgType)
    buf = append(buf, m.Flags)
    
    // 2. unknown1 (2 bytes)
    buf = append(buf, 0, 0)
    
    // 3. knownMsgCount (2 bytes, big-endian)
    knownCount := uint16(len(m.KnownMessages))
    buf = append(buf, byte(knownCount>>8), byte(knownCount&0xFF))
    
    // 4. senderID (16 bytes)
    buf = append(buf, m.SenderID[:]...)
    
    // 5. senderPort (2 bytes, big-endian)
    buf = append(buf, byte(m.SenderPort>>8), byte(m.SenderPort&0xFF))
    
    // 6. senderIP (4 bytes)
    buf = append(buf, m.SenderIP[:]...)
    
    // 7. timestamp (8 bytes, big-endian)
    ts := uint64(time.Now().UnixNano()) / 1000000 // 毫秒
    buf = append(buf, byte(ts>>56), byte(ts>>48), byte(ts>>40), byte(ts>>32),
                   byte(ts>>24), byte(ts>>16), byte(ts>>8), byte(ts))
    
    // 8. configEpoch (8 bytes, big-endian)
    epoch := m.ConfigEpoch
    buf = append(buf, byte(epoch>>56), byte(epoch>>48), byte(epoch>>40), byte(epoch>>32),
                   byte(epoch>>24), byte(epoch>>16), byte(epoch>>8), byte(epoch))
    
    // 9. slaveOf (16 bytes)
    buf = append(buf, m.SlaveOf[:]...)
    
    // 10. payload
    buf = append(buf, m.PingPayload...)
    
    return buf
}

// Decode 从字节数组解码消息
func DecodeGossipMessage(data []byte) (*GossipMessage, error) {
    if len(data) < 54 {
        return nil, fmt.Errorf("data too short: %d bytes", len(data))
    }
    
    msg := &GossipMessage{}
    msg.MsgType = data[0]
    msg.Flags = data[1]
    
    // senderID
    copy(msg.SenderID[:], data[6:22])
    
    // senderPort
    msg.SenderPort = binary.BigEndian.Uint16(data[22:24])
    
    // senderIP
    copy(msg.SenderIP[:], data[24:28])
    
    // timestamp
    msg.Timestamp = binary.BigEndian.Uint64(data[28:36])
    
    // configEpoch
    msg.ConfigEpoch = binary.BigEndian.Uint64(data[36:44])
    
    // slaveOf
    copy(msg.SlaveOf[:], data[44:60])
    
    // payload
    if len(data) > 60 {
        msg.PingPayload = data[60:]
    }
    
    return msg, nil
}

// 关键：为什么用二进制协议而不是 JSON？
// 1. 更小：Gossip 消息频繁发送（每秒），越小越好
// 2. 更快：不需要 JSON 编解码
// 3. 更省内存：直接操作字节数组
```

### 3.4 配置纪元（Config Epoch）— 解决脑裂

**问题**：如果两个节点都认为自己是 master，怎么办？

**答案**：用 Config Epoch 解决

```
节点 A: config_epoch = 5
节点 B: config_epoch = 3

当 A 和 B 通信时：
- A 发现自己的 epoch 更大 → A 获胜
- B 发现自己的 epoch 更小 → B 承认 A 是 master
- B 将自己的 epoch 更新为 A 的 epoch + 1 = 6

这样保证了只有一个 master
```

```go
type ConfigEpochManager struct {
    myEpoch   uint64
    myID      string
    peers     map[string]*PeerInfo
}

type PeerInfo struct {
    ID        string
    Epoch     uint64
    Role      string // master/slave
    Slots     []int
    Connected bool
}

// 处理来自其他节点的 Gossip 消息
func (m *ConfigEpochManager) HandleGossip(gossip *GossipMessage) {
    peerID := string(gossip.SenderID[:])
    peerEpoch := gossip.ConfigEpoch
    
    // 如果对方 epoch 更大，更新自己的 epoch
    if peerEpoch > m.myEpoch {
        m.myEpoch = peerEpoch + 1
        fmt.Printf("Updated my config epoch to %d (peer was %d)\n", m.myEpoch, peerEpoch)
    }
    
    // 更新 peer 信息
    m.peers[peerID] = &PeerInfo{
        ID:        peerID,
        Epoch:     peerEpoch,
        Role:      determineRole(gossip),
        Connected: true,
    }
}

// 选举 master
func (m *ConfigEpochManager) ElectMaster() string {
    bestPeer := ""
    bestEpoch := uint64(0)
    
    for id, peer := range m.peers {
        if peer.Role == "master" && peer.Epoch > bestEpoch {
            bestEpoch = peer.Epoch
            bestPeer = id
        }
    }
    
    return bestPeer
}
```

---

## 第四部分：Sentinel 自动故障切换

### 4.1 Sentinel 工作原理

**类比**：医院的值班医生系统

```
Master（主诊医生）→ 负责治疗病人
Slaves（住院医生）→ 协助治疗，随时准备接替
Sentinel（护士长）→ 监控所有医生，发现主诊医生不在就安排住院医生接替
```

**Sentinel 的三重角色**：
1. **监控**：定期检查 Master/Slave 是否在线
2. **通知**：发现问题时通知管理员
3. **自动故障转移**：Master 挂了，自动提升一个 Slave 为 Master

### 4.2 故障检测流程（源码级）

```go
package sentinel

import (
    "context"
    "fmt"
    "time"
)

type Sentinel struct {
    ID         string
    Master     *RedisNode
    Slaves     []*RedisNode
    OtherSentinels map[string]*Sentinel
    Quorum     int          // 法定人数，过半数认为 master 挂了才算真挂了
    DownAfterMillis int     // 多久没响应才认为 down
    FailoverTimeout int       // 故障转移超时
    State      SentinelState // monitoring/detecting/failover
}

type SentinelState int

const (
    StateMonitoring SentinelState = iota
    StateDetecting
    StateFailover
    StateFailoverDone
)

// 定期监控 master
func (s *Sentinel) MonitorMaster(ctx context.Context) {
    ticker := time.NewTicker(1 * time.Second)
    defer ticker.Stop()
    
    for {
        select {
        case <-ctx.Done():
            return
        case <-ticker.C:
            // 发送 PING 到 master
            pong, err := s.Master.Ping(ctx)
            if err != nil || pong != "PONG" {
                // 1 秒没响应，标记为 SDOWN（主观下线）
                s.Master.SetSubjectivelyDown()
                s.State = StateDetecting
                s.tryFailover(ctx)
                return
            }
            
            // 发送 INFO 命令获取 slave 列表
            info, err := s.Master.Info(ctx, "replication")
            if err == nil {
                s.updateSlaves(info)
            }
            
            // 向其他 sentinel 发送 PING
            for _, other := range s.OtherSentinels {
                other.Ping(ctx)
            }
        }
    }
}

// 尝试故障转移
func (s *Sentinel) tryFailover(ctx context.Context) {
    // 1. 检查是否达到 quorum（多数 sentinel 认为 master 挂了）
    downCount := 1 // 自己算一个
    for _, other := range s.OtherSentinels {
        if other.Master.IsSubjectivelyDown() {
            downCount++
        }
    }
    
    if downCount < s.Quorum {
        // 还没达到法定人数，继续监控
        return
    }
    
    // 2. master 被确认为 ODOWN（客观下线）
    s.Master.SetObjectivelyDown()
    s.State = StateFailover
    
    // 3. 选择一个 slave 提升为 master
    candidate := s.selectBestSlave()
    if candidate == nil {
        fmt.Println("No suitable slave candidate")
        return
    }
    
    // 4. 执行故障转移
    s.performFailover(ctx, candidate)
}

// 选择最佳 slave
func (s *Sentinel) selectBestSlave() *RedisNode {
    best := (*RedisNode)(nil)
    bestOffset := int64(0)
    
    for _, slave := range s.Slaves {
        // 优先选择：
        // 1. 不是 down 状态的
        // 2. replication offset 最大的（数据最完整）
        // 3. runid 最小的（ Tie-breaker）
        
        if slave.IsDown() {
            continue
        }
        
        offset := slave.GetReplicationOffset()
        if offset > bestOffset || (offset == bestOffset && (best == nil || slave.RunID < best.RunID)) {
            best = slave
            bestOffset = offset
        }
    }
    
    return best
}

// 执行故障转移
func (s *Sentinel) performFailover(ctx context.Context, candidate *RedisNode) {
    // 1. 通知 candidate 成为 master
    candidate.SendCommand(ctx, "SLAVEOF", "NO", "ONE")
    
    // 2. 通知其他 slaves 复制新的 master
    for _, slave := range s.Slaves {
        if slave != candidate {
            slave.SendCommand(ctx, "SLAVEOF", candidate.Addr, candidate.Port)
        }
    }
    
    // 3. 等待 candidate 完成数据同步
    time.Sleep(5 * time.Second)
    
    // 4. 通知其他 sentinels 更新 master 地址
    s.publishConfigChange(candidate)
    
    // 5. 更新客户端配置
    s.updateClientConfig(candidate)
    
    s.State = StateFailoverDone
}
```

### 4.3 Sentinel 生产排障案例

**故障场景**：Sentinel 频繁触发故障转移

```
现象：每 5 分钟就发生一次 failover，Master 不断切换
```

**排查步骤：**

```bash
# 1. 查看 Sentinel 日志
tail -f sentinel.log | grep -i fail

# 2. 检查网络延迟
redis-cli -p 26379 SENTINEL MASTER mymaster
# 看 sdown-after-milliseconds 和 down-after-milliseconds

# 3. 检查 Master 负载
redis-cli INFO stats
# 看 instantaneous_ops_per_sec

# 4. 检查 Redis 慢查询
redis-cli SLOWLOG GET 10
```

**常见原因和解决方案：**

| 原因 | 症状 | 解决方案 |
|------|------|---------|
| 网络抖动 | PING 偶尔超时 | 增大 down-after-milliseconds |
| Master 负载高 | ops/sec 突增 | 优化慢查询，加从节点分担 |
| 内存不足 | OOM killer 触发 | 增加内存或优化数据 |
| 时钟不同步 | 时间戳不一致 | 配置 NTP 同步 |

---

## 第五部分：RDB vs AOF 深度对比

### 5.1 对比表格

| 特性 | RDB | AOF |
|------|-----|-----|
| **持久化方式** | 全量快照 | 追加写命令日志 |
| **文件大小** | 小（压缩后） | 大（可能比 RDB 大 10 倍） |
| **恢复速度** | 快 | 慢（需要重放命令） |
| **数据安全性** | 可能丢数据（两次快照之间） | 更安全（每秒同步） |
| **CPU 占用** | 高（fork 子进程时） | 低（顺序写） |
| **适用场景** | 灾难恢复 | 数据一致性要求高 |

### 5.2 Fork 机制 — 为什么 Redis 单线程还能做 RDB？

**核心问题**：Redis 是单线程的，写 RDB 会不会阻塞请求？

**答案**：用 Copy-on-Write + Fork

```
主进程（处理请求）          子进程（写 RDB）
┌─────────────┐           ┌─────────────┐
│ 内存中的数据 │           │ 共享内存     │
│             │◄─────────►│ (COW 机制)  │
└─────────────┘           └─────────────┘

1. 主进程 fork 子进程
2. 子进程获得内存的只读副本
3. 主进程继续处理请求（读写自己的内存）
4. 如果主进程修改了数据，操作系统复制那一页（Copy-on-Write）
5. 子进程写完 RDB 后退出
```

```go
package rdb

import (
    "fmt"
    "os"
    "syscall"
    "unsafe"
)

// ForkRDBSnapshot 模拟 Redis 的 RDB fork 机制
func ForkRDBSnapshot(filename string) error {
    // 1. Fork 子进程
    pid, _, err := syscall.RawSyscall(syscall.SYS_FORK, 0, 0, 0)
    if err != nil {
        return fmt.Errorf("fork failed: %w", err)
    }
    
    if pid == 0 {
        // ===== 子进程 =====
        // 子进程共享父进程的内存空间（COW）
        // 写 RDB 文件时不会阻塞父进程
        
        // 2. 关闭不需要的文件描述符
        syscall.CloseOnExec(int(fd))
        
        // 3. 遍历所有 key，写入 RDB 文件
        f, err := os.Create(filename)
        if err != nil {
            os.Exit(1)
        }
        defer f.Close()
        
        // 4. 写入 RDB 魔术头
        f.WriteString("REDIS0011")
        
        // 5. 序列化所有数据结构
        serializeAllKeys(f)
        
        // 6. 写入 EOF
        f.WriteString("EOF")
        
        // 7. fsync 确保数据落盘
        f.Sync()
        
        os.Exit(0)
    }
    
    // ===== 父进程 =====
    // 父进程继续处理请求，不受 RDB 写入影响
    fmt.Printf("RDB snapshot started in child process %d\n", pid)
    return nil
}

// 关键：为什么 fork 不会阻塞？
// 1. fork 本身很快（只复制页表，不复制数据）
// 2. 子进程写文件时，父进程继续处理请求
// 3. 只有当父进程修改内存时，才触发 COW 复制页面
// 4. 如果数据集很大，COW 可能耗时较长
```

### 5.3 AOF 重写（BGREWRITEAOF）

**问题**：AOF 文件会越来越大，怎么处理？

**答案**：AOF 重写 — 生成新的精简 AOF 文件

```
旧 AOF:
SET name Alice
SET age 25
SET name Bob      ← 重复设置，浪费
DEL age           ← 删除了 age，但 age 还在文件里
SET name Charlie  ← 最终 name=Charlie

新 AOF（重写后）:
SET name Charlie  ← 只保留最终状态
```

```go
package aof

import (
    "bufio"
    "fmt"
    "os"
)

// RewriteAOF 重写 AOF 文件
func RewriteAOF(oldFile, newFile string) error {
    // 1. 读取旧 AOF
    oldF, _ := os.Open(oldFile)
    defer oldF.Close()
    
    // 2. 解析命令，只保留最终状态
    keyState := make(map[string]*Command)
    scanner := bufio.NewScanner(oldF)
    
    for scanner.Scan() {
        cmd := parseCommand(scanner.Text())
        if cmd != nil {
            switch cmd.Type {
            case "SET", "HSET", "LPUSH", "SADD":
                keyState[cmd.Key] = cmd
            case "DEL":
                delete(keyState, cmd.Key)
            case "EXPIRE", "PEXPIRE":
                if c, ok := keyState[cmd.Key]; ok {
                    c.TTL = cmd.TTL
                }
            }
        }
    }
    
    // 3. 写入新 AOF
    newF, _ := os.Create(newFile)
    defer newF.Close()
    
    for key, cmd := range keyState {
        newF.WriteString(fmt.Sprintf("*%d\r\n", len(cmd.Args)+1))
        newF.WriteString(fmt.Sprintf("$%d\r\n%s\r\n", len(cmd.Type), cmd.Type))
        for _, arg := range cmd.Args {
            newF.WriteString(fmt.Sprintf("$%d\r\n%s\r\n", len(arg), arg))
        }
    }
    
    return nil
}
```

---

## 第六部分：Pipeline 和 Lua 脚本深度

### 6.1 Pipeline 性能对比

```go
package pipeline

import (
    "context"
    "fmt"
    "time"
    
    "github.com/redis/go-redis/v9"
)

func benchmarkPipeline(rdb *redis.Client) {
    ctx := context.Background()
    keys := make([]string, 10000)
    values := make([]string, 10000)
    
    for i := 0; i < 10000; i++ {
        keys[i] = fmt.Sprintf("key:%d", i)
        values[i] = fmt.Sprintf("value:%d", i)
    }
    
    // 方式 1：逐个 SET（10000 次网络往返）
    start := time.Now()
    for i := 0; i < 10000; i++ {
        rdb.Set(ctx, keys[i], values[i], 0)
    }
    fmt.Printf("逐个 SET: %v\n", time.Since(start))
    // 输出: 逐个 SET: 2.5s (假设 RTT 0.25ms)
    
    // 方式 2：Pipeline（1 次网络往返）
    start = time.Now()
    pipe := rdb.Pipeline()
    for i := 0; i < 10000; i++ {
        pipe.Set(ctx, keys[i], values[i], 0)
    }
    _, err := pipe.Exec(ctx)
    fmt.Printf("Pipeline: %v\n", time.Since(start))
    // 输出: Pipeline: 50ms (10000 次操作在 1 次往返中完成)
    
    // 方式 3：Pipe + TxPipeline（事务管道）
    start = time.Now()
    pipe = rdb.TxPipeline()
    for i := 0; i < 10000; i++ {
        pipe.Set(ctx, keys[i], values[i], 0)
    }
    _, err = pipe.Exec(ctx)
    fmt.Printf("TxPipeline: %v\n", time.Since(start))
}
```

**性能对比：**

| 方式 | 网络往返 | 耗时 | 适用场景 |
|------|---------|------|---------|
| 逐个 SET | 10000 次 | 2.5s | 不推荐 |
| Pipeline | 1 次 | 50ms | 批量写入 |
| TxPipeline | 1 次 | 55ms | 需要原子性的批量操作 |

### 6.2 Lua 脚本 — 原子性保证

**问题**：为什么需要 Lua 脚本？

**答案**：Redis 保证 Lua 脚本**原子性执行**，不会被其他命令打断

```go
package lua

import (
    "context"
    "fmt"
    
    "github.com/redis/go-redis/v9"
)

// 场景：预算扣减 — 必须原子性
func DeductBudget(rdb *redis.Client, campaignID string, amount float64) error {
    // Lua 脚本：检查预算 → 扣减 → 返回结果
    // 整个脚本在 Redis 中原子执行，不会被其他命令插入
    script := redis.NewScript(`
        local budgetKey = KEYS[1]
        local amount = tonumber(ARGV[1])
        
        -- 获取当前余额
        local balance = redis.call('GET', budgetKey)
        if not balance then
            return -1  -- 预算不存在
        end
        
        local currentBalance = tonumber(balance)
        if currentBalance < amount then
            return 0  -- 余额不足
        end
        
        -- 扣减余额
        redis.call('DECRBY', budgetKey, amount)
        return 1  -- 成功
    `)
    
    ctx := context.Background()
    result, err := script.Run(ctx, rdb, []string{fmt.Sprintf("budget:%s", campaignID)}, amount).Int()
    if err != nil {
        return err
    }
    
    switch result {
    case 1:
        return nil  // 扣减成功
    case 0:
        return fmt.Errorf("budget exceeded")
    case -1:
        return fmt.Errorf("budget not found")
    }
    return nil
}

// 为什么不用 Pipeline？
// Pipeline 不是原子的！其他命令可以在 Pipeline 的命令之间插入
// Lua 脚本是原子的！Redis 保证脚本执行期间不被打断
```

### 6.3 Lua 脚本的 SHA1 缓存机制

```
第一次执行: EVAL script → Redis 计算 SHA1 → 返回结果 + SHA1
后续执行:   EVALSHA sha1 → 直接执行，跳过脚本解析
```

```go
func evalWithCache(rdb *redis.Client, script string) (*redis.Client, error) {
    ctx := context.Background()
    
    // 1. 先尝试 EVALSHA（缓存命中）
    sha1 := sha1.Sum([]byte(script))
    result, err := rdb.EvalSha(ctx, sha1.HexFormat(), nil).Result()
    if err == nil {
        return result, nil  // 缓存命中！
    }
    
    // 2. EVALSHA 失败（缓存未命中），用 EVAL
    result, err = rdb.Eval(ctx, script, nil).Result()
    if err != nil {
        return nil, err
    }
    
    // 3. EVAL 返回的结果中包含 SHA1
    // Redis 会自动缓存这个 SHA1，下次用 EVALSHA 就能命中
    
    return result, nil
}
```

---

## 第七部分：生产排障实战

### 7.1 OOM（Out of Memory）

```
现象：Redis 报错 "OOM command not allowed when used memory > maxmemory"

原因：
1. 没有设置 maxmemory
2. 设置了但没有配置 eviction 策略
3. 数据量超过了可用内存
```

```go
// 解决方案：配置 maxmemory + eviction policy
// maxmemory 2gb
// maxmemory-policy allkeys-lru

// 在 Go 中设置
rdb.ConfigSet(ctx, "maxmemory", "2gb")
rdb.ConfigSet(ctx, "maxmemory-policy", "allkeys-lru")
```

| Eviction Policy | 适用场景 | 说明 |
|----------------|---------|------|
| noeviction | 数据绝对不能丢 | 超内存时报错 |
| allkeys-lru | 通用场景 | 淘汰最少使用的 key |
| volatile-lru | 有 TTL 的场景 | 只淘汰有 TTL 的 key |
| allkeys-random | 均匀淘汰 | 随机淘汰 |
| volatile-ttl | 优先淘汰快到期的 | 适合缓存场景 |

### 7.2 主从同步失败

```
现象：Slave 不断重连 Master，同步失败

排查步骤：
1. redis-cli INFO replication 查看同步状态
2. redis-cli DEBUG SLEEP 1 模拟网络中断
3. 检查 Master 的 maxmemory 是否足够
4. 检查网络带宽是否足够
```

```go
// 主从同步原理：
// 1. Slave 发送 SYNC 命令
// 2. Master 执行 BGSAVE 生成 RDB
// 3. Master 将 RDB 发送给 Slave
// 4. Slave 加载 RDB
// 5. Master 将 RDB 期间的命令发送给 Slave（命令追加）
```

### 7.3 大 Key 问题

```
现象：Redis 响应变慢，甚至卡顿

原因：大 Key（>10KB）的删除/序列化耗时很长
```

```go
// 检测大 Key
func findBigKeys(rdb *redis.Client, pattern string) {
    cursor := uint64(0)
    for {
        var keys []string
        var err error
        keys, cursor, err = rdb.Scan(cursor, pattern, 100).Result()
        if err != nil {
            break
        }
        
        for _, key := range keys {
            size := rdb.DBSize(context.Background()).Val()
            if size > 10000 {
                fmt.Printf("Big key: %s (%d bytes)\n", key, size)
            }
        }
        
        if cursor == 0 {
            break
        }
    }
}

// 解决方案：
// 1. 拆分大 Key（user:1001:tags → user:1001:tag:1, user:1001:tag:2...）
// 2. 使用 Hash 代替 String
// 3. 设置 TTL 自动过期
```

---

## 第八部分：自测题

### 问题 1
Redis Cluster 为什么用 16384 个槽位而不是按服务器数量 hash？

<details>
<summary>查看答案</summary>

1. **扩容方便**：只需迁移部分槽位，不需要重 hash 所有数据
2. **客户端友好**：客户端只需要知道槽位 → 节点映射
3. **16384 的选择**：2^14，足够大也能用 bitmap 高效表示
4. **如果按服务器数量 hash**：服务器增减时所有 key 都要迁移
5. **Trade-off**：槽位太多管理复杂，太少不够灵活

</details>

### 问题 2
为什么 Redis 单线程还能高性能？

<details>
<summary>查看答案</summary>

1. **纯内存操作**：无磁盘 I/O 瓶颈
2. **IO 多路复用**：epoll 处理数万并发连接
3. **无锁竞争**：单线程避免了锁开销
4. **简单数据结构**：O(1) 或 O(log n) 操作
5. **瓶颈在网络 I/O**：不是 CPU

</details>

### 问题 3
RDB 和 AOF 可以一起用吗？

<details>
<summary>查看答案</summary>

1. **可以！** Redis 推荐混合持久化
2. **AOF 重写时**：先写 RDB 快照，再追加 AOF 命令
3. **恢复时**：先加载 RDB，再重放 AOF 命令
4. **优点**：RDB 快 + AOF 安全
5. **配置**：aof-use-rdb-preamble yes

</details>

---

*本文档基于 Redis 源码和生产实战整理，包含逐行解析、排障案例、对比分析。*