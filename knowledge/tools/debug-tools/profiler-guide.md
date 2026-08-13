# Go 性能分析器使用指南

> pprof, trace, ebpf 全栈分析。

---

## 1. pprof 基本使用

```bash
# 启动时启用
go run -race main.go

# 或者代码中启用
import _ "net/http/pprof"
http.ListenAndServe("localhost:6060", nil)

# 收集数据
go tool pprof http://localhost:6060/debug/pprof/heap
go tool pprof http://localhost:6060/debug/pprof/profile
go tool pprof http://localhost:6060/debug/pprof/goroutine
```

---

## 2. Trace 分析

```bash
# 采集 trace
go tool trace trace.out

# 代码中触发
import "runtime/trace"
ctx, err := trace.New(context.Background())
trace.Start(ctx, f)
defer trace.Stop()
```

---

## 3. ebpf 高级分析

```bash
# bpftrace 示例
bpftrace -e 'tracepoint:syscalls:sys_enter_write { @[kstack] = count(); }'

# perf 工具
perf record -g ./myprogram
perf report
```

---

**参考**: Go pprof 官方文档、Linux perf 手册
