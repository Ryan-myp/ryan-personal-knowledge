# Linux IO调度器 - 资深专家深度实现

## 一、调度算法对比

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    Linux IO调度算法                                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   算法           | 原理              | 适用场景          | 优缺点        │
│   ──────────────┼──────────────────┼──────────────────┼──────────────│
│   CFQ           | 完全公平调度       | 通用场景           | 公平但复杂     │
│  Deadline       | 截止时间优先       | 低延迟需求         | 保证延迟       │
│   NOOP          | 先进先出          | SSD/NVMe         | 简单高效       │
│   BFQ           | 预算公平调度       | 交互式场景         | 响应性好       │
│   mq-deadline   | 多队列截止时间     | NVMe/多队列       | 现代首选       │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、IO调度器实现

```c
// 简化版Deadline调度器
struct deadline_data {
    struct request_queue *q;
    struct rb_root sort_list[2];  // ASC/DESC树
    struct list_head fifo[2];     // FIFO队列
    sector_t next_sector;         // 下一个请求的扇区
    unsigned long front_merges;   // 前置合并计数
};

// 请求排序
static void deadline_sort_add(struct request_queue *q, struct request *req)
{
    struct deadline_data *dd = q->elevator->elevator_data;
    int方向 = rq_data_dir(req);
    
    // 按扇区位置插入红黑树
    elv_rb_add(&dd->sort_list[方向], req);
    
    // 加入FIFO队列
    expiry = jiffies + dd->fifo_expire[方向];
    add_timer_per_cpu(&dd->fifo_timer, cpu);
}

// 查找下一个请求
static struct request *deadline_find_request(struct deadline_data *dd, 
                                              int data_dir, int flag)
{
    struct rb_node *node;
    
    // 优先找能合并的请求
    node = rb_next(dd->next_sector_rb[data_dir]);
    if (node)
        return rb_entry(node, struct request, rb_node);
    
    // 否则找FIFO队列头部
    if (!list_empty(&dd->fifo_list[data_dir]))
        return list_entry(dd->fifo_list[data_dir].next, 
                         struct request, fifo);
    
    return NULL;
}
```

## 三、面试高频题

### Q1: 如何选择IO调度器？

```
A:
1. HDD: Deadline 或 CFQ
2. SSD: NOOP 或 mq-deadline
3. NVMe: mq-deadline
```

### Q2: 如何优化IO性能？

```
A:
1. 选择合适的调度器
2. 调整队列深度
3. 使用SSD/NVMe
```

## 四、自测题

1. 解释五种IO调度算法
2. 如何实现Deadline调度？
3. 如何优化IO性能？

---

## 参考文档

- [Linux IO Subsystem](https://www.kernel.org/doc/html/latest/block/)
- [Elevator Algorithm](https://elinux.org/Block_Subsystem/Elevator_Architecture)
