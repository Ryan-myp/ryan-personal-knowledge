# Kafka架构深度 - 资深专家深度实现

## 一、Broker架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Kafka Broker架构                                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │                      Kafka Broker                               │   │
│   │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │   │
│   │  │  Log     │  │  Log     │  │  Log     │  │  Log     │       │   │
│   │  │  Segment │  │  Segment │  │  Segment │  │  Segment │       │   │
│   │  │   0      │  │   1      │  │   2      │  │   ...    │       │   │
│   │  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘       │   │
│   │       │              │              │              │            │   │
│   │  ┌────▼──────────────▼──────────────▼──────────────▼─────┐      │   │
│   │  │                物理存储 (磁盘)                          │      │   │
│   │  │  topic-partition-0.log / index / timeindex            │      │   │
│   │  └───────────────────────────────────────────────────────┘      │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                                                                           │
│   • Partition: 消息分区，并行处理                                          │
│   • Replica: 副本，保证高可用                                              │
│   • Leader: 主副本，处理读写                                               │
│   • Follower: 从副本，同步数据                                             │
│                                                                           │
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、生产者实现

```java
public class KafkaProducerExample {
    
    private final KafkaProducer<String, String> producer;
    
    public KafkaProducerExample() {
        Properties props = new Properties();
        props.put("bootstrap.servers", "broker1:9092,broker2:9092");
        props.put("key.serializer", "org.apache.kafka.common.serialization.StringSerializer");
        props.put("value.serializer", "org.apache.kafka.common.serialization.StringSerializer");
        props.put("acks", "all");  // 所有副本确认
        props.put("retries", 3);
        
        this.producer = new KafkaProducer<>(props);
    }
    
    public void sendMessage(String topic, String key, String value) {
        ProducerRecord<String, String> record = new ProducerRecord<>(topic, key, value);
        
        producer.send(record, new Callback() {
            @Override
            public void onCompletion(RecordMetadata metadata, Exception exception) {
                if (exception != null) {
                    exception.printStackTrace();
                } else {
                    System.out.println("Sent to partition " + metadata.partition());
                }
            }
        });
    }
}
```

## 三、消费者实现

```java
public class KafkaConsumerExample {
    
    private final KafkaConsumer<String, String> consumer;
    
    public KafkaConsumerExample() {
        Properties props = new Properties();
        props.put("bootstrap.servers", "broker1:9092,broker2:9092");
        props.put("group.id", "test-group");
        props.put("key.deserializer", "org.apache.kafka.common.serialization.StringDeserializer");
        props.put("value.deserializer", "org.apache.kafka.common.serialization.StringDeserializer");
        props.put("auto.offset.reset", "earliest");
        props.put("enable.auto.commit", "false");
        
        this.consumer = new KafkaConsumer<>(props);
        consumer.subscribe(Collections.singletonList("test-topic"));
    }
    
    public void pollMessages() {
        while (true) {
            ConsumerRecords<String, String> records = consumer.poll(Duration.ofMillis(100));
            
            for (ConsumerRecord<String, String> record : records) {
                System.out.printf("offset = %d, key = %s, value = %s%n", 
                    record.offset(), record.key(), record.value());
            }
            
            consumer.commitSync();
        }
    }
}
```

## 四、面试高频题

### Q1: Kafka如何保证消息不丢失？

```
A:
1. 生产者: acks=all
2. Broker: replicas=3
3. 消费者: 手动提交offset
```

### Q2: 什么是Consumer Group？

```
A:
• 消费者组实现负载均衡
• 同一消息只被组内一个消费者处理
• 组内消费者数不超过分区数
```

## 五、自测题

1. 解释Kafka分区策略
2. 如何实现Exactly-Once？
3. 如何处理消息积压？

---

## 参考文档

- [Kafka官方文档](https://kafka.apache.org/documentation/)
- [Kafka源码](https://github.com/apache/kafka)
