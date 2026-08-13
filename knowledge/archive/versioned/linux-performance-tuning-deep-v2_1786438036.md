# Linux性能调优深度解析

> 深入Linux性能调优：CPU、内存、磁盘、网络优化。
> 源码级分析，包含生产环境最佳实践。
> 适用对象：SRE、运维工程师

---

## 1. CPU性能调优

### 1.1 调优参数

```
Linux CPU性能调优：

┌─────────────────────────────────────────────────────────────┐
│  CPU Governor：                                              │
│  ├── performance：性能模式（最高频率）                        │
│  ├── powersave：省电模式（最低频率）                          │
│  ├── Ondemand：按需调节                                       │
│  └── schedutil：调度器驱动                                    │
│                                                             │
│  关键参数：                                                  │
│  ├── kernel.sched_migration_cost：进程迁移成本                 │
│  ├── kernel.sched_latency_ns：调度延迟                       │
│  └── vm.swappiness：交换倾向（0-100，推荐10）                 │
│                                                             │
│  监控工具：                                                  │
│  ├── top/htop：进程CPU使用                                   │
│  ├── mpstat：CPU统计                                         │
│  └── sar：系统活跃度报告                                     │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. 内存性能调优

### 2.1 调优参数

```
Linux内存性能调优：

┌─────────────────────────────────────────────────────────────┐
│  关键参数：                                                  │
│  ├── vm.overcommit_memory：内存提交策略（0/1/2）              │
│  ├── vm.overcommit_ratio：Swap比例                           │
│  ├── vm.dirty_ratio：脏页比例                                │
│  ├── vm.dirty_background_ratio：后台刷盘比例                 │
│  └── vm.min_free_kbytes：最小空闲内存                         │
│                                                             │
│  IO调度器：                                                  │
│  ├── deadline： deadline调度（SSD推荐）                      │
│  ├── cfq： 完全公平调度（HDD推荐）                           │
│  └── noop： 最简单调度（内存优先）                           │
│                                                             │
│  监控工具：                                                  │
│  ├── free：内存使用情况                                       │
│  ├── vmstat：虚拟内存统计                                    │
│  └── iostat：IO统计                                         │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. 自测题

### 3.1 单选题

1. Linux中，设置CPU为performance模式使用的命令是：
   A. cpufreq-set -g performance  B. chmod 777  C. sysctl -w  D. ps aux
   答案：A

---

> 本文档适用对象：SRE、运维工程师
> 难度：资深专家级
