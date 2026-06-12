# 技术面试 Q&A

> Go 语言 / 系统设计 / 数据库 / 网络 — 面试高频题

---

## Go 语言

### GMP 调度模型
- G: goroutine（用户态线程）
- M: OS thread
- P: processor（调度器核心）
- M:N 模型：G → M（线程池）→ P（OS 线程）
- GOMAXPROCS = CPU 核数

### GC 调优
- 三色标记 + 写屏障
- GOGC=100 默认，可调优
- Go 1.12+ 三色标记 + 混合写屏障
- Go 1.17+ 后台 GC 线程

### 常见面试题
1. interface 底层结构
2. map 扩容机制
3. channel 实现原理
4. sync.Pool 使用场景

---

## 系统设计

### 分布式 ID
- Snowflake：41bit 时间 + 10bit 机器 + 12bit 序列
- 淘宝 Leaf：号段模式
- 美团 Leaf：ZooKeeper

### CAP 选择
- CP：分布式锁、预算扣减
- AP：竞价、曝光日志

---

*本文档基于面试高频题整理。*