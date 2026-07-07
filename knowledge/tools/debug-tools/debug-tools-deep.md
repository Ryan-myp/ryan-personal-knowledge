# 调试工具链实战指南

## 一、入门引导

调试是开发者最重要的技能之一。好的调试工具链能大幅缩短问题定位时间。

### 1.1 调试工具分类

| 类别 | 工具 | 用途 |
|------|------|------|
| 进程调试 | gdb, lldb, delve | 源码级调试 |
| 性能分析 | pprof, trace, valgrind | CPU/内存分析 |
| 网络调试 | tcpdump, wireshark, ngrep | 抓包分析 |
| 系统调用 | strace, dtrace, eBPF | 系统调用追踪 |
| 日志分析 | grep, awk, jq, goaccess | 日志处理 |

## 二、Go 调试工具

### 2.1 Delve (dlv)

```bash
# 安装
go install github.com/go-delve/delve/cmd/dlv@latest

# 基本调试
dlv debug main.go
dlv exec ./myapp

# 远程调试
dlv debug --headless --listen=:2345 --api-version=2
dlv connect localhost:2345

# 常用命令
(dlv) break main.go:10      # 设置断点
(dlv) continue              # 继续执行
(dlv) next                  # 单步跳过
(dlv) step                  # 单步进入
(dlv) print var             # 打印变量
(dlv) goroutines            # 查看所有 goroutine
(dlv) goroutine 1 bt        # 查看 goroutine 堆栈
(dlv) threads               # 查看所有线程
(dlv) watch var             # 设置变量监视
(dlv) breakpoints           # 查看所有断点
(dlv) clear                 # 清除断点
```

### 2.2 pprof 性能分析

```go
package main

import (
    "net/http"
    _ "net/http/pprof"
)

func main() {
    // 启动 pprof HTTP 端点
    go func() {
        http.ListenAndServe(":6060", nil)
    }()
    
    // 你的应用逻辑
    http.ListenAndServe(":8080", nil)
}
```

```bash
# CPU 分析
go tool pprof -http=:8081 http://localhost:6060/debug/pprof/profile?seconds=30

# 内存分析
go tool pprof -http=:8081 http://localhost:6060/debug/pprof/heap

# Goroutine 分析
go tool pprof -http=:8081 http://localhost:6060/debug/pprof/goroutine

# 阻塞分析
go tool pprof -http=:8081 http://localhost:6060/debug/pprof/block

# 互斥锁分析
go tool pprof -http=:8081 http://localhost:6060/debug/pprof/mutex

# 生成火焰图
go tool pprof -http=:8081 -png http://localhost:6060/debug/pprof/profile?seconds=30 > cpu.png
```

### 2.3 race detector

```bash
# 运行时检测数据竞争
go run -race main.go
go test -race ./...

# 编译时启用
go build -race -o myapp main.go
```

## 三、Linux 系统调试

### 3.1 strace 系统调用追踪

```bash
# 追踪命令执行
strace -f -e trace=network ./myapp
strace -c ./myapp          # 统计模式

# 追踪已有进程
strace -p <pid>
strace -p <pid> -e trace=open,read,write

# 常用选项
strace -f          # 追踪子进程
strace -e trace=file  # 只追踪文件操作
strace -o output.txt  # 输出到文件
strace -c          # 统计模式
```

### 3.2 ltrace 库调用追踪

```bash
# 追踪动态库调用
ltrace ./myapp
ltrace -e malloc,free ./myapp
```

### 3.3 tcpdump 网络抓包

```bash
# 基本抓包
tcpdump -i eth0
tcpdump -i any

# 过滤
tcpdump host 192.168.1.1
tcpdump port 80
tcpdump tcp port 443 and host 10.0.0.1

# 保存/读取
tcpdump -w capture.pcap
tcpdump -r capture.pcap

# 与 Wireshark 配合
tcpdump -i any -w /tmp/capture.pcap
wireshark /tmp/capture.pcap
```

### 3.4 eBPF 高级追踪

```bash
# bpftrace 脚本
sudo bpftrace -e 'tracepoint:syscalls:sys_enter_open { printf("%s %s\n", comm, str(args->filename)); }'

# bcc 工具
sudo execsnoop        # 追踪进程执行
sudo tcplife          # 追踪 TCP 连接生命周期
sudo biolatency       # 磁盘 IO 延迟
sudo funccount        # 函数调用计数
```

## 四、日志分析

### 4.1 jq 处理 JSON 日志

```bash
# 基本查询
cat app.log | jq '. | select(.level == "error")'

# 统计
cat app.log | jq -s '[.[] | select(.level == "error")] | length'

# 聚合
cat app.log | jq -s 'group_by(.endpoint) | map({endpoint: .[0].endpoint, count: length})'

# 格式化输出
cat app.log | jq -r '.[] | "\(.timestamp) [\(.level)] \(.message)"'
```

### 4.2 goaccess 实时日志分析

```bash
# 安装
brew install goaccess

# 分析 Nginx 日志
goaccess access.log -o report.html --log-format=COMBINED

# 实时分析
tail -f access.log | goaccess --log-format=COMBINED -o /dev/stdout
```

## 五、自测题

### 5.1 选择题

1. pprof 中，哪个端点用于分析内存泄漏？
   - A) /debug/pprof/profile
   - B) /debug/pprof/heap
   - C) /debug/pprof/goroutine
   - D) /debug/pprof/block

2. strace 中，-c 选项的作用是什么？
   - A) 只追踪特定系统调用
   - B) 统计模式，显示调用次数和时间
   - C) 追踪子进程
   - D) 输出到文件

### 5.2 编程题

1. 编写一个 Go 程序，集成 pprof，并提供 CPU 和内存分析的 HTTP 端点

2. 使用 jq 分析 Nginx 日志，找出请求最多的 10 个 IP

## 六、动手验证

```bash
# 1. 安装 Delve
go install github.com/go-delve/delve/cmd/dlv@latest

# 2. 创建一个简单的 Go 程序
cat > main.go << 'EOF'
package main

import (
    "fmt"
    "net/http"
    _ "net/http/pprof"
)

func main() {
    // 启动 pprof
    go func() {
        http.ListenAndServe(":6060", nil)
    }()
    
    http.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
        fmt.Fprintf(w, "Hello!")
    })
    
    http.ListenAndServe(":8080", nil)
}
EOF

# 3. 启动程序
go run main.go &

# 4. 使用 pprof 分析
go tool pprof -http=:8081 http://localhost:6060/debug/pprof/profile?seconds=30

# 5. 使用 Delve 调试
dlv debug main.go
(dlv) break main.go:15
(dlv) continue
(dlv) print fmt
```
