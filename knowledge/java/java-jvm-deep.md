# Java JVM 深度解析

> 深入 JVM 内存模型、垃圾回收、性能调优。
> 适用对象：Java 开发者、后端架构师

---

## 1. JVM 内存模型

```
┌─────────────────────────────────────────────────────────────┐
│                      JVM 内存结构                           │
├─────────────────────────────────────────────────────────────┤
│  线程共享 (Thread-Shared)                                   │
│  ├── 堆 (Heap)                                             │
│  │   ├── 年轻代 (Young Generation)                          │
│  │   │   ├── Eden (伊甸园)                                  │
│  │   │   ├── Survivor 0 (S0)                                │
│  │   │   └── Survivor 1 (S1)                                │
│  │   └── 老年代 (Old Generation)                            │
│  └── 方法区 (Method Area)                                   │
│       └── Metaspace (元空间，JDK8+)                          │
│                                                             │
│  线程私有 (Per-Thread)                                      │
│  ├── 程序计数器 (Program Counter Register)                  │
│  ├── Java 虚拟机栈 (JVM Stack)                              │
│  └── 本地方法栈 (Native Method Stack)                        │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. 垃圾回收算法

```
标记-清除 (Mark-Sweep):
  - 优点: 简单
  - 缺点: 内存碎片

标记-复制 (Mark-Copy):
  - 优点: 无碎片
  - 缺点: 内存利用率低

标记-整理 (Mark-Compact):
  - 优点: 无碎片，利用率高
  - 缺点: 移动对象开销大
```

---

## 3. GC 收集器

| 收集器 | 代 | 算法 | 特点 |
|--------|----|------|------|
| Serial | 年轻代 | 标记-复制 | 单线程 |
| ParNew | 年轻代 | 标记-复制 | 多线程 |
| Parallel Scavenge | 年轻代 | 标记-复制 | 吞吐量优先 |
| Serial Old | 老年代 | 标记-整理 | 单线程 |
| Parallel Old | 老年代 | 标记-整理 | 吞吐量优先 |
| CMS | 老年代 | 标记-清除 | 低延迟 |
| G1 | 全部 | 分区 | 平衡型 |
| ZGC | 全部 | 染色指针 | 超低延迟 |

---

## 4. JVM 调优命令

```bash
# 常用启动参数
java -Xms2g -Xmx2g -XX:+UseG1GC -XX:MaxGCPauseMillis=200 \
     -XX:+PrintGCDetails -Xloggc:gc.log -jar app.jar

# GC 分析
jstat -gcutil <pid> 1000

# 堆dump
jmap -dump:format=b,file=heap.hprof <pid>

# 线程分析
jstack <pid>
```

---

## 5. 实践 Checklist
- [ ] 选择合适的 GC 收集器
- [ ] 配置合理的堆大小
- [ ] 监控 GC 频率和时间
- [ ] 分析内存泄漏

**参考**: Java Performance 官方文档、JVM 调优实战
