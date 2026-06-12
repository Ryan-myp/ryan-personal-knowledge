# Redis 集群/哨兵/源码深度

> Redis Cluster 分片/槽位/Gossip / Sentinel 自动故障切换 / RDB/AOF 持久化 / Pipeline / Lua 脚本

---

## 第一部分：入门引导（5 分钟速览）

### Redis 为什么快？

1. **纯内存操作**：数据在内存中，无磁盘 I/O
2. **单线程模型**：避免上下文切换和锁竞争
3. **IO 多路复用**：epoll/kqueue 处理大量连接
4. **高效数据结构**：SDS、跳跃表、压缩列表

### Redis 集群架构

```
客户端 → Redis Cluster（16384 个槽位）
         ├── Node 0: 槽位 0-5460
         ├── Node 1: 槽位 5461-10922
         └── Node 2: 槽位 10923-16383

数据分片：hash(key) % 16384 → 槽位 → Node
```

---

## 第二部分：Redis Cluster 分片原理

### 2.1 槽位分配

Redis Cluster 使用 16384 个哈希槽（hash slot）来分布数据：

```go
package rediscluster

import (
    "fmt"
    "hash/crc32"
)

// SlotMapper 负责将 key 映射到槽位
type SlotMapper struct {
    slots []SlotNode
}

type SlotNode struct {
    Start int
    End   int
    Node  string
}

func NewSlotMapper(slots []SlotNode) *SlotMapper {
    return &SlotMapper{slots: slots}
}

func (sm *SlotMapper) GetSlot(key string) (int, string) {
    // CRC16 计算槽位
    hash := crc32.ChecksumIEEE([]byte(key))
    slot := int(hash % 16384)
    
    // 查找对应的 Node
    for _, s := range sm.slots {
        if slot >= s.Start && slot <= s.End {
            return slot, s.Node
        }
    }
    return 0, ""
}

func (sm *SlotMapper) GetSlots(key string) []int {
    // 批量操作需要获取所有 key 的槽位
    hashes := make([]int, 0)
    for _, k := range key {
        hash := crc32.ChecksumIEEE([]byte(string(k)))
        hashes = append(hashes, int(hash % 16384))
    }
    return hashes
}
```

### 2.2 Gossip 协议

Redis Cluster 使用 Gossip 协议在节点间传播信息：

```go
type GossipMessage struct {
    Type        string    // ping/meet/pong
    Sender      string    // 发送者节点 ID
    Receiver    string    // 接收者节点 ID
    ClusterTime int64     // 时间戳
    Slots       []SlotInfo
    Failures    []string  // 故障节点列表
}

type GossipProtocol struct {
    nodes   map[string]*Node
    channel chan GossipMessage
}

func (gp *GossipProtocol) SendPing(sender, receiver string, slots []SlotInfo) {
    msg := GossipMessage{
        Type:      "ping",
        Sender:    sender,
        Receiver:  receiver,
        ClusterTime: time.Now().UnixNano(),
        Slots:     slots,
    }
    gp.channel <- msg
}

func (gp *GossipProtocol) HandleMessage(msg GossipMessage) {
    switch msg.Type {
    case "ping":
        // 更新槽位信息
        gp.updateSlots(msg.Slots)
    case "meet":
        // 发现新节点
        gp.addNode(msg.Sender)
    case "pong":
        // 心跳响应
        gp.heartbeat(msg.Sender)
    }
}

func (gp *GossipProtocol) updateSlots(slots []SlotInfo) {
    for _, slot := range slots {
        gp.nodes[slot.NodeID] = &Node{
            Slots: slot.SlotRange,
            Status: "online",
        }
    }
}
```

### 2.3 槽位迁移

```go
type SlotMigration struct {
    source      string
    target      string
    slot        int
    state       string // migrating, importing, done
}

func (sm *SlotMigration) MigrateSlot(source, target string, slot int) error {
    // 1. 在源节点标记为 migrating
    err := sm.setSlotState(source, slot, "migrating")
    if err != nil {
        return err
    }
    
    // 2. 在目标节点标记为 importing
    err = sm.setSlotState(target, slot, "importing")
    if err != nil {
        return err
    }
    
    // 3. 迁移数据
    keys := sm.getKeysForSlot(slot)
    for _, key := range keys {
        value, err := sm.getFromSource(source, key)
        if err != nil {
            continue
        }
        err = sm.setToTarget(target, key, value)
        if err != nil {
            return err
        }
    }
    
    // 4. 完成迁移
    err = sm.setSlotState(source, slot, "done")
    if err != nil {
        return err
    }
    err = sm.setSlotState(target, slot, "done")
    if err != nil {
        return err
    }
    
    return nil
}
```

---

## 第三部分：Sentinel 自动故障切换

### 3.1 Sentinel 架构

```
Sentinel 集群
├── Sentinel 0
├── Sentinel 1
└── Sentinel 2

监控：
├── Master (192.168.1.1:6379)
├── Slave 0 (192.168.1.2:6379)
└── Slave 1 (192.168.1.3:6379)
```

### 3.2 故障检测

```go
type Sentinel struct {
    master     *RedisNode
    slaves     []*RedisNode
    quorum     int
    state      string // monitoring, detecting, failover
}

func (s *Sentinel) MonitorMaster(master *RedisNode) {
    s.master = master
    s.state = "monitoring"
    
    // 定期发送 PING 检测健康
    go func() {
        ticker := time.NewTicker(1 * time.Second)
        defer ticker.Stop()
        
        for range ticker.C {
            _, err := master.Ping()
            if err != nil {
                s.detectFailure()
                return
            }
        }
    }()
}

func (s *Sentinel) detectFailure() {
    s.state = "detecting"
    
    // 询问其他 Sentinel 是否也认为 master 挂了
    otherSentinels := s.queryOtherSentinels()
    downCount := 1 // 自己也算一个
    
    for _, sentinel := range otherSentinels {
        isDown, _ := sentinel.IsMasterDown(s.master)
        if isDown {
            downCount++
        }
    }
    
    // 达到 quorum 则认为 master 真的挂了
    if downCount >= s.quorum {
        s.startFailover()
    }
}

func (s *Sentinel) startFailover() {
    s.state = "failover"
    
    // 1. 选择新的 master（优先级最高的 slave）
    newMaster := s.selectBestSlave()
    
    // 2. 提升 slave 为 master
    err := newMaster.SetMaster()
    if err != nil {
        return
    }
    
    // 3. 通知其他 slave 复制新的 master
    for _, slave := range s.slaves {
        if slave != newMaster {
            slave.SetMaster(newMaster)
        }
    }
    
    // 4. 更新客户端配置
    s.publishConfigChange(newMaster)
}
```

---

## 第四部分：RDB/AOF 持久化

### 4.1 RDB 快照

```go
type RDBSnapshot struct {
    filename string
    data     map[string]interface{}
}

func (r *RDBSnapshot) CreateSnapshot() error {
    // 1. 后台 fork 子进程
    pid, err := syscall.Fork()
    if err != nil {
        return err
    }
    
    if pid == 0 {
        // 子进程：创建快照
        r.writeSnapshot()
        os.Exit(0)
    }
    
    // 父进程：继续处理请求
    return nil
}

func (r *RDBSnapshot) writeSnapshot() {
    // 2. 遍历所有 key-value
    f, _ := os.Create(r.filename)
    defer f.Close()
    
    // 3. 写入 RDB 格式
    f.WriteString("REDIS0011") // RDB 版本
    
    for key, value := range r.data {
        // 写入 key 类型
        f.WriteString(fmt.Sprintf("TYPE:%d\n", r.getKeyType(key)))
        // 写入 key
        f.WriteString(fmt.Sprintf("KEY:%s\n", key))
        // 写入 value
        f.WriteString(fmt.Sprintf("VALUE:%v\n", value))
    }
    
    // 4. 写入 EOF 标记
    f.WriteString("EOF")
}
```

### 4.2 AOF 追加日志

```go
type AOFWriter struct {
    file    *os.File
    buffer  []byte
    mu      sync.Mutex
}

func (a *AOFWriter) AppendCommand(cmd string, args ...string) error {
    a.mu.Lock()
    defer a.mu.Unlock()
    
    // 构建命令字符串
    command := fmt.Sprintf("*%d\r\n", len(args)+1)
    command += fmt.Sprintf("$%d\r\n%s\r\n", len(cmd), cmd)
    for _, arg := range args {
        command += fmt.Sprintf("$%d\r\n%s\r\n", len(arg), arg)
    }
    
    // 追加到缓冲区
    a.buffer = append(a.buffer, []byte(command)...)
    
    // 每秒 fsync
    if len(a.buffer) > 1024*1024 { // 1MB
        a.flush()
    }
    
    return nil
}

func (a *AOFWriter) flush() error {
    if len(a.buffer) == 0 {
        return nil
    }
    
    _, err := a.file.Write(a.buffer)
    if err != nil {
        return err
    }
    
    // fsync 确保数据落盘
    err = a.file.Sync()
    if err != nil {
        return err
    }
    
    a.buffer = a.buffer[:0]
    return nil
}
```

### 4.3 AOF 重写

```go
type AOFRewriter struct {
    source      *os.File
    destination *os.File
    keys        map[string]interface{}
}

func (r *AOFRewriter) Rewrite() error {
    // 1. 读取现有 AOF 文件
    scanner := bufio.NewScanner(r.source)
    for scanner.Scan() {
        line := scanner.Text()
        if strings.HasPrefix(line, "*") {
            // 解析命令
            cmd, args := r.parseCommand(line)
            if cmd == "SET" || cmd == "HSET" || cmd == "LPUSH" {
                r.keys[args[0]] = args[1]
            }
        }
    }
    
    // 2. 生成新的 AOF 文件
    for key, value := range r.keys {
        r.destination.WriteString(fmt.Sprintf("*2\r\n$3\r\nSET\r\n$%d\r\n%s\r\n$%d\r\n%v\r\n",
            len(key), key, len(fmt.Sprintf("%v", value)), value))
    }
    
    return nil
}
```

---

## 第五部分：Pipeline 和 Lua 脚本

### 5.1 Pipeline 批量操作

```go
type Pipeline struct {
    conn    net.Conn
    commands [][]byte
}

func (p *Pipeline) Add(cmd string, args ...string) {
    command := fmt.Sprintf("*%d\r\n", len(args)+1)
    command += fmt.Sprintf("$%d\r\n%s\r\n", len(cmd), cmd)
    for _, arg := range args {
        command += fmt.Sprintf("$%d\r\n%s\r\n", len(arg), arg)
    }
    p.commands = append(p.commands, []byte(command))
}

func (p *Pipeline) Execute() ([]interface{}, error) {
    // 1. 批量发送命令
    for _, cmd := range p.commands {
        _, err := p.conn.Write(cmd)
        if err != nil {
            return nil, err
        }
    }
    
    // 2. 批量读取响应
    responses := make([]interface{}, len(p.commands))
    for i := range responses {
        resp, err := p.readResponse()
        if err != nil {
            return nil, err
        }
        responses[i] = resp
    }
    
    return responses, nil
}

func (p *Pipeline) readResponse() (interface{}, error) {
    // 读取 RESP 协议的响应
    header := make([]byte, 1)
    _, err := p.conn.Read(header)
    if err != nil {
        return nil, err
    }
    
    switch header[0] {
    case '+': // 简单字符串
        return p.readLine()
    case '-': // 错误
        return nil, errors.New(p.readLine())
    case ':': // 整数
        return p.parseInt()
    case '$': // bulk string
        return p.readBulkString()
    case '*': // 数组
        return p.readArray()
    default:
        return nil, fmt.Errorf("unknown RESP type: %c", header[0])
    }
}
```

### 5.2 Lua 脚本

```go
type LuaScript struct {
    script   string
    sha1     string
    keys     []string
    args     []string
}

func (l *LuaScript) Eval(conn net.Conn) (interface{}, error) {
    // 1. 如果 SHA1 未知，先 EVALSHA 尝试
    if l.sha1 != "" {
        result, err := l.evalSha(conn)
        if err == nil {
            return result, nil
        }
        // 如果 NOSCRIPT，则 EVAL
    }
    
    // 2. EVAL 执行脚本
    command := fmt.Sprintf("EVAL %s %d %s %s",
        l.script, len(l.keys),
        strings.Join(l.keys, " "),
        strings.Join(l.args, " "))
    
    _, err := conn.Write([]byte(command))
    if err != nil {
        return nil, err
    }
    
    result, err := l.readResponse(conn)
    if err == nil {
        // 缓存 SHA1
        l.sha1 = l.calculateSHA1()
    }
    
    return result, nil
}

func (l *LuaScript) calculateSHA1() string {
    h := sha1.Sum([]byte(l.script))
    return fmt.Sprintf("%x", h)
}
```

---

## 第六部分：自测题

### 问题 1
Redis Cluster 如何处理节点故障？

<details>
<summary>查看答案</summary>

1. **故障检测**：节点间定期发送 PING 消息
2. **主观下线**：超过一定时间未响应，标记为 SFAIL
3. **客观下线**：多数节点确认 SFAIL，标记为 FAIL
4. **故障转移**：
   - 从 slave 中选择一个提升为 master
   - 复制原 master 的数据
   - 更新槽位映射
5. **Go 实现**：使用 Gossip 协议传播故障信息

</details>

### 问题 2
AOF 重写过程中如何保证数据一致性？

<details>
<summary>查看答案</summary>

1. **后台 fork**：父进程继续处理请求
2. **AOF 重写缓冲区**：重写期间的新命令写入缓冲区
3. **重写完成后**：将缓冲区内容追加到新 AOF 文件
4. **原子替换**：使用 rename 原子替换旧 AOF 文件
5. **Go 实现**：
```go
func (rw *AOFRewriter) SafeRewrite() error {
    // 1. fork 子进程
    pid, _ := syscall.Fork()
    if pid == 0 {
        // 子进程：生成新 AOF
        rw.generateNewAOF()
        os.Exit(0)
    }
    
    // 2. 父进程：继续处理，同时写入缓冲区
    rw.startBuffering()
    
    // 3. 等待子进程完成
    syscall.Wait(pid)
    
    // 4. 追加缓冲区内容
    rw.appendToNewAOF()
    
    // 5. 原子替换
    os.Rename("appendonly.aof.tmp", "appendonly.aof")
    
    return nil
}
```

</details>

### 问题 3
Redis Pipeline 相比多次单独请求有什么优势？

<details>
<summary>查看答案</summary>

1. **减少网络往返**：批量发送，一次 RTT
2. **吞吐量提升**：1000 条命令从 1000ms 降到 10ms
3. **适用场景**：批量写入、批量查询、批量删除
4. **注意**：Pipeline 不保证原子性，需要 Lua 脚本保证原子性
5. **Go 实现**：使用 `go-redis` 的 Pipeline API

</details>

---

*本文档基于 Redis 集群原理整理，结合广告平台实战场景。*