3. 微服务/实时: NATS JetStream
   - 低延迟，简单部署
   - 适合服务间通信
```

---

### Kafka Broker 的 Go 实现

```go
package kafka

import (
	"fmt"
	"sync"
	"time"
)

type Partition struct {
	ID         int64
	Topic      string
	Log        []*Message
	BaseOffset int64
	mu         sync.Mutex
}

type Message struct {
	Offset    int64
	Key       string
	Value     string
	Timestamp time.Time
}

func (p *Partition) Append(msg *Message) int64 {
	p.mu.Lock()
	defer p.mu.Unlock()
	msg.Offset = p.BaseOffset
	p.Log = append(p.Log, msg)
	p.BaseOffset++
	return msg.Offset
}

func (p *Partition) Fetch(offset int64, maxBytes int) []*Message {
	p.mu.Lock()
	defer p.mu.Unlock()
	var msgs []*Message
	for _, m := range p.Log {
		if m.Offset >= offset {
			msgs = append(msgs, m)
		}
	}
	return msgs
}

type Broker struct {
	ID         int32
	Partitions []*Partition
	mu         sync.Mutex
}

func (b *Broker) GetOrCreatePartition(topic string, id int64) *Partition {
	b.mu.Lock()
	defer b.mu.Unlock()
	for _, p := range b.Partitions {
		if p.ID == id { return p }
	}
	p := &Partition{ID: id, Topic: topic}
	b.Partitions = append(b.Partitions, p)
	return p
}

type ZeroCopySender struct {
	brokers map[int32]*Broker
	sent    int64
	mu      sync.Mutex
}

func (s *ZeroCopySender) Send(topic string, partition int64, msg *Message) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.sent++
}

func main() {
	broker := &Broker{ID: 1}
	p := broker.GetOrCreatePartition("events", 0)
	p.Append(&Message{Key: "user1", Value: "click", Timestamp: time.Now()})
	msgs := p.Fetch(0, 1024)
	fmt.Printf("Fetched: %d messages\n", len(msgs))

	sender := &ZeroCopySender{brokers: make(map[int32]*Broker)}
	sender.Send("events", 0, &Message{Key: "test", Value: "data"})
	fmt.Printf("Sent: %d messages\n", sender.sent)
}
```

---

## 自测题

### 问题 1
Kafka 的零拷贝（Zero Copy）在 Go 中如何实现？

<details>
<summary>查看答案</summary>

1. **内核态优化**：Kafka 用 sendfile() 系统调用，数据不经过用户态
2. **Go 中**：可以用 `syscall.Sendfile()` 实现零拷贝
3. **优势**：减少 CPU 拷贝次数，降低上下文切换
4. **局限**：只对文件到文件有效，网络发送仍需用户态 buffer

</details>

### 问题 2
Go 的 `sync.Mutex` 在 Kafka Broker 的 Partition 中为什么比 `sync.RWMutex` 更合适？

<details>
<summary>查看答案</summary>

1. Append 是高频写操作，Fetch 是低频读操作
2. RWMutex 在写多读少场景下性能不如 Mutex
3. Append 需要独占锁，Fetch 也需要锁保护
4. 实际 Kafka 用分段锁（segment lock）进一步优化

</details>