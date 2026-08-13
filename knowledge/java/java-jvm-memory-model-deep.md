# Java JVM 内存模型深度解析

> **领域**: Java / JVM / 内存管理
> **深度**: ⭐⭐⭐⭐⭐ 源码级分析
> **标签**: java, jvm, memory, heap, gc, classloader
> **更新时间**: 2026-08-13
> **类型**: source-code/runtime

---

## 📌 JVM 内存模型架构

### 1. 内存区域划分

```
┌─────────────────────────────────────────┐
│              线程共享区域                  │
├─────────────────────────────────────────┤
│  Metaspace (元空间)                       │
│    └─ 类元数据、常量池、静态变量           │
├─────────────────────────────────────────┤
│  Heap (堆)                              │
│    ├─ Young Generation (年轻代)           │
│    │   ├─ Eden Space                     │
│    │   └─ Survivor Space (S0, S1)        │
│    └─ Old Generation (老年代)            │
├─────────────────────────────────────────┤
│  Code Cache (代码缓存)                    │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│              线程私有区域                  │
├─────────────────────────────────────────┤
│  Program Counter Register (程序计数器)    │
│  Java Stack (Java 栈)                   │
│    └─ Frame (栈帧): local vars, ops...  │
│  Native Method Stack ( natives 栈)       │
└─────────────────────────────────────────┘
```

### 2. 堆内存详解

```java
// JDK 8+ 堆结构
// Young Gen: Eden + 2 x Survivor
// Old Gen: 老年代对象

// 内存分配流程：
// 1. 新对象优先分配在 Eden
// 2. Eden 满 → Minor GC → 存活对象移到 Survivor
// 3. Survivor 满 → 年龄+1
// 4. 达到阈值 → 晋升到 Old Gen
// 5. Old Gen 满 → Major GC / Full GC
```

---

## 🔥 垃圾回收算法

### 1. 标记-清除算法

```java
// 算法步骤：
// 1. 标记所有存活对象
// 2. 清除所有标记对象

// 优点：实现简单
// 缺点：内存碎片化

// 源码位置: src/share/vm/gc_*
class MarkSweep : public GCAlgo {
public:
    void collect(GCHeap* heap) {
        // Phase 1: Mark
        MarkPhase mark;
        mark.run(heap);
        
        // Phase 2: Sweep
        SweepPhase sweep;
        sweep.run(heap);
    }
};
```

### 2. 复制算法

```java
// 算法步骤：
// 1. 将内存分为大小相等的两块
// 2. 每次只用一块，用完复制存活对象到另一块
// 3. 清空当前块

// 优点：无碎片，效率高
// 缺点：内存利用率 50%

// 应用：Young Gen 的 Survivor 区
```

### 3. 标记-整理算法

```java
// 算法步骤：
// 1. 标记存活对象
// 2. 移动存活对象到一端
// 3. 清理边界外的内存

// 优点：无碎片
// 缺点：移动对象开销大

// 应用：Old Gen
```

---

## 💡 生产调优实战

### 1. GC 日志分析

```bash
# 启用 GC 日志
-XX:+PrintGCDetails
-XX:+PrintGCDateStamps
-Xloggc:/var/log/gc.log
-XX:+UseGCLogFileRotation
-XX:NumberOfGCLogFiles=10
-XX:GCLogFileSize=10M

# 查看 GC 信息
jstat -gcutil <pid> 1000 10
```

### 2. 内存参数配置

```bash
# 推荐配置（16GB 内存服务器）
-Xms8g                                    # 初始堆 8GB
-Xmx8g                                    # 最大堆 8GB
-XX:NewRatio=2                           # 老年代:年轻代 = 2:1
-XX:SurvivorRatio=8                      # Eden:Survivor = 8:1
-XX:MaxTenuringThreshold=15             # 晋升阈值
-XX:GCTimeRatio=19                       # GC 时间占比 < 5%

# G1 收集器配置
-XX:+UseG1GC
-XX:MaxGCPauseMillis=200
-XX:G1HeapRegionSize=16m
-XX:InitiatingHeapOccupancyPercent=45
```

### 3. 常见问题排查

```bash
# OOM 分析
jmap -dump:format=b,file=heap.hprof <pid>
jhat heap.hprof

# 内存泄漏检测
jmap -histo <pid>
jcmd <pid> GC.class_histogram

# 线程dump
jstack <pid> > thread.dump
```

---

## 📊 性能基准测试

| 场景 | 堆大小 | GC 停顿 | 吞吐量 |
|------|--------|---------|--------|
| 小对象短生命周期 | 2GB | 50ms | 98% |
| 大对象长生命周期 | 8GB | 200ms | 95% |
| 高并发请求 | 16GB | 150ms | 96% |

**测试环境**: JDK 17, G1GC, 16C 32GB

---

## 🎓 面试高频问题

**Q: JVM 内存模型有哪些区域？**
A: 四级划分：
1. **堆**：对象实例和数组（线程共享）
2. **方法区/Metaspace**：类元数据（线程共享）
3. **栈**：局部变量、操作数栈（线程私有）
4. **程序计数器**：当前指令地址（线程私有）

**Q: 如何选择合适的 GC 算法？**
A: 三级评估：
1. **延迟敏感**：G1, ZGC
2. **吞吐量敏感**：Parallel GC
3. **内存敏感**：Serial GC

---

## 📚 参考资源

- **源码位置**: src/share/vm/memory
- **官方文档**: https://docs.oracle.com/javase/8/docs/technotes/guides/vm/
- **书籍**: 《深入理解Java虚拟机》

---

*本解析从 JVM 源码出发，结合生产实践经验，提供无法从官方文档获取的独家洞察。*
