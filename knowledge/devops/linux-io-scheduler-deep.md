# Linux IO调度器 - 资深专家深度实现

## 一、IO调度算法

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      Linux IO调度算法                                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   CFQ (Completely Fair Queuing)                                          │
│   • 按进程公平分配IO带宽                                                   │
│   • 适合机械硬盘                                                          │
│                                                                         │
│   deadline                                                                  │
│   • 保证IO不饿死                                                            │
│   • 适合数据库                                                              │
│                                                                         │
│   NOOP (No Operation)                                                    │
│   • 最简单，FIFO                                                          │
│   • 适合SSD                                                                  │
│                                                                         │
│   mq-deadline (多队列deadline)                                             │
│   • 支持NVMe设备                                                           │
│   • 默认调度器                                                              │
│                                                                         │
│   bfq (Budget Fair Queuing)                                              │
│   • 最公平                                                                  │
│   • 适合桌面环境                                                            │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、调优配置

```bash
# 查看当前调度器
cat /sys/block/sda/queue/scheduler

# 切换为deadline
echo deadline > /sys/block/sda/queue/scheduler

# 设置参数
echo 500 > /sys/block/sda/queue/read_expire
echo 1000 > /sys/block/sda/queue/write_expire
echo 8 > /sys/block/sda/queue/nr_requests
```

## 三、面试高频题

### Q1: 如何选择IO调度器？

```
A:
1. SSD用NOOP/mq-deadline
2. HDD用CFQ/bfq
3. 数据库用deadline
```

### Q2: nr_requests含义？

```
A: 每个队列最大请求数
```

## 四、自测题

1. 解释CFQ原理
2. 如何优化数据库IO？
3. 如何处理IO饥饿？

---

## 参考文档

- [Linux IO调度器](https://www.kernel.org/doc/Documentation/block/cfq-iosched.txt)
- [blk-mq架构](https://lwn.net/Articles/629372/)
