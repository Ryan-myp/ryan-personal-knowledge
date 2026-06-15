# 中间件补充：RabbitMQ/NATS 深度

> RabbitMQ 交换器/消息持久化/死信队列 / NATS JetStream/服务发现

---

## 第一部分：入门引导（5 分钟速览）

### 为什么需要多种消息队列？

| 场景 | 推荐 MQ | 原因 |
|------|---------|------|
| 高吞吐日志 | Kafka | 顺序写，吞吐量大 |
| 业务消息 | RabbitMQ | 灵活路由，可靠性高 |
| 微服务通信 | NATS | 轻量，延迟低 |
| 事件驱动 | Pulsar | 云原生，多租户 |

---

## 第二部分：RabbitMQ 深度

### 2.1 交换器类型

```go
package rabbitmq

import (
    "github.com/streadway/amqp"
)

type ExchangeType string

const (
    Direct  ExchangeType = "direct"
    Fanout  ExchangeType = "fanout"
    Topic   ExchangeType = "topic"
    Headers ExchangeType = "headers"
)

// 直连交换器：精确匹配 routing key
// 发布/订阅：广播给所有消费者
// 主题交换器：通配符匹配
// 头部交换器：基于消息头匹配
```

### 2.2 消息持久化

```go
func (conn *Connection) Publish(queueName, routingKey string, body []byte) error {
    ch, err := conn.channel.OpenQueue(queueName)
    if err != nil {
        return err
    }
    
    err = ch.Publish(
        "",           // exchange
        routingKey,   // routing key
        true,         // mandatory
        false,        // immediate
        amqp.Publishing{
            ContentType: "application/json",
            Body:        body,
            DeliveryMode: amqp.Persistent, // 持久化
        },
    )
    
    return err
}

// 消费者确认
func (conn *Connection) Consume(queueName string, handler func([]byte) error) error {
    ch, err := conn.channel.OpenQueue(queueName)
    if err != nil {
        return err
    }
    
    msgs, err := ch.Consume(
        queueName,
        "",    // consumer
        false, // auto ack
        false, // exclusive
        false, // no local
        false, // no wait
        nil,   // args
    )
    
    for msg := range msgs {
        err := handler(msg.Body)
        if err != nil {
            msg.Nack(false, true) // 重新入队
        } else {
            msg.Ack(false) // 确认消费
        }
    }
    
    return nil
}
```

### 2.3 死信队列

```go
func SetupDLX(exchangeName string, dlxExchange string) error {
    args := amqp.Table{
        "x-dead-letter-exchange":    dlxExchange,
        "x-dead-letter-routing-key": "dlx.routing.key",
    }
    
    return conn.channel.ExchangeDeclare(
        exchangeName,
        "direct",
        true,  // durable
        false, // auto-deleted
        false, // internal
        false, // no-wait
        args,  // arguments
        nil,   // arguments
    )
}

// 消费者处理死信消息
func HandleDLX(queueName string, handler func([]byte) error) error {
    msgs, err := conn.channel.Consume(queueName, "", false, false, false, false, nil)
    if err != nil {
        return err
    }
    
    for msg := range msgs {
        err := handler(msg.Body)
        if err != nil {
            // 记录错误日志
            log.Printf("DLX message failed: %v", err)
            msg.Ack(false) // 不再重试，直接丢弃
        } else {
            msg.Ack(false)
        }
    }
    
    return nil
}
```

---

## 第三部分：NATS JetStream

### 3.1 JetStream 消息持久化

```go
package nats

import (
    "github.com/nats-io/nats.go"
    "github.com/nats-io/nats.go/jetstream"
)

type JetStreamClient struct {
    nc   *nats.Conn
    js   jetstream.JetStream
}

func NewJetStreamClient(url string) (*JetStreamClient, error) {
    nc, err := nats.Connect(url)
    if err != nil {
        return nil, err
    }
    
    js, err := jetstream.New(nc)
    if err != nil {
        return nil, err
    }
    
    return &JetStreamClient{nc: nc, js: js}, nil
}

// 创建流
func (js *JetStreamClient) CreateStream(name string, subjects []string) error {
    stream, err := js.js.CreateStream(context.Background(), jetstream.StreamConfig{
        Name:      name,
        Subjects:  subjects,
        Storage:   jetstream.FileStorage,
        Retention: jetstream.InterestPolicy,
    })
    
    if err != nil {
        return err
    }
    
    js.stream = stream
    return nil
}

// 发布消息
func (js *JetStreamClient) Publish(subject string, data []byte) error {
    _, err := js.js.Publish(context.Background(), subject, data)
    return err
}

// 订阅消息
func (js *JetStreamClient) Subscribe(subject string, cb jetstream.MsgHandler) error {
    _, err := js.js.Subscribe(context.Background(), subject, cb)
    return err
}
```

### 3.2 发布/订阅模式

```go
// 发布/订阅
pubsub := nats.NewPubSub()

// 发布
err := pubsub.Publish("user.created", []byte(`{"id": 1, "name": "Alice"}`))

// 订阅
err := pubsub.Subscribe("user.created", func(msg *nats.Msg) {
    // 处理消息
})

// 发布/订阅 + 持久化
err := pubsub.SubscribeWithDurable("user.created", "consumer1", func(msg *nats.Msg) {
    // 处理消息
}, jetstream.DurableConfig{
    Name: "consumer1",
})
```

---

## 第四部分：服务发现

### 4.1 NATS 服务发现

```go
type ServiceRegistry struct {
    nc   *nats.Conn
}

func (sr *ServiceRegistry) Register(name, address string) error {
    return sr.nc.Publish(fmt.Sprintf("$SRV.%s.REGISTER", name), []byte(address))
}

func (sr *ServiceRegistry) Unregister(name, address string) error {
    return sr.nc.Publish(fmt.Sprintf("$SRV.%s.UNREGISTER", name), []byte(address))
}

func (sr *ServiceRegistry) Discover(name string) ([]string, error) {
    msgs, err := sr.nc.Request(fmt.Sprintf("$SRV.%s.QUERY", name), nil, 5*time.Second)
    if err != nil {
        return nil, err
    }
    
    return strings.Split(string(msgs.Data), ","), nil
}
```

---

## 第五部分：自测题

### 问题 1
RabbitMQ 交换器类型有哪些？

<details>
<summary>查看答案</summary>

1. **Direct**：精确匹配 routing key
2. **Fanout**：广播给所有消费者
3. **Topic**：通配符匹配（* 和 #）
4. **Headers**：基于消息头匹配
5. **广告场景**：日志用 Fanout，竞价用 Direct

</details>

### 问题 2
JetStream 相比普通 NATS 有什么优势？

<details>
<summary>查看答案</summary>

1. **持久化**：消息持久到磁盘
2. **ACK**：消费者确认机制
3. **流控**：背压控制
4. **多租户**：不同账户隔离
5. **Go 实现**：jetstream.New(nc)

</details>

### 问题 3
如何选择消息队列？

<details>
<summary>查看答案</summary>

1. **吞吐量**：Kafka > RabbitMQ > NATS
2. **延迟**：NATS < RabbitMQ < Kafka
3. **可靠性**：RabbitMQ = Kafka > NATS
4. **运维复杂度**：NATS < RabbitMQ < Kafka
5. **广告场景**：日志用 Kafka，业务用 RabbitMQ，内部通信用 NATS

</details>

---

*本文档基于消息队列原理整理。*