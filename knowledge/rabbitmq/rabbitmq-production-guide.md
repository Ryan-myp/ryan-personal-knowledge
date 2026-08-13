# RabbitMQ 生产环境实战

> 深入 RabbitMQ 架构、消息模型、运维实践。

---

## 1. 核心架构

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Producer  │────▶│   Exchange  │────▶│    Queue    │
│  (消息生产)  │     │  (交换机)    │     │  (消息队列)  │
└─────────────┘     └─────────────┘     └──────┬──────┘
                                               │
                                         ┌─────▼─────┐
                                         │ Consumer  │
                                         │  (消息消费) │
                                         └───────────┘
```

---

## 2. Exchange 类型

| 类型 | 路由规则 | 适用场景 |
|------|----------|----------|
| Direct | 精确匹配 | 任务队列 |
| Fanout | 广播 | 日志分发 |
| Topic | 模式匹配 | 日志路由 |
| Headers | 头部匹配 | 特殊需求 |

---

## 3. Go 客户端使用

```go
conn, err := amqp.Dial("amqp://guest:guest@localhost:5672/")
ch, err := conn.Channel()

// 声明队列
q, err := ch.QueueDeclare(
    "task_queue", // name
    true,         // durable
    false,        // delete when unused
    false,        // exclusive
    false,        // no-wait
    nil,          // args
)

// 发送消息
msg := amqp.Publishing{
    ContentType: "text/plain",
    Body:        []byte("Hello World"),
}
ch.Publish("", q.Name, false, false, msg)
```

---

## 4. 实践 Checklist
- [ ] 启用消息持久化
- [ ] 配置镜像队列
- [ ] 监控队列深度
- [ ] 设置死信队列

**参考**: RabbitMQ 官方文档、消息队列最佳实践
