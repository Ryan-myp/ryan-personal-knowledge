# K8s Pod生命周期 - 资深专家深度实现

## 一、容器生命周期

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     Pod生命周期流程                                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   Pending ──→ Initializing ──→ Running ──→ Terminating ──→ Deleted    │
│     ↑         ↑                    ↑              ↑                     │
│     │         │                    │              │                     │
│   调度      初始化              健康检查          优雅退出                │
│                                                                         →
│   Init Containers                                                    │
│   ├── 按顺序执行                                                        │
│   ├── 全部成功才进入主容器                                                 │
│   └── 用于前置准备                                                        │
│                                                                         →
│   PreStop Hook                                                         │
│   ├── SIGTERM发送后执行                                                   │
│   ├── 等待业务清理                                                        │
│   └── 超时强制终止                                                        │
│                                                                         →
│   PostStop Hook                                                        │
│   ├── 容器删除前执行                                                      │
│   └── 用于日志保存                                                        │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、优雅退出实现

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: graceful-shutdown
spec:
  terminationGracePeriodSeconds: 30
  containers:
  - name: app
    image: myapp
    lifecycle:
      preStop:
        exec:
          command: ["/bin/sh", "-c", "sleep 10"]
      postStart:
        exec:
          command: ["/bin/sh", "-c", "mkdir -p /data"]
```

```go
package main

import (
    "net/http"
    "os"
    "os/signal"
    "syscall"
    "time"
)

func main() {
    srv := &http.Server{Addr: ":8080"}
    go srv.ListenAndServe()
    
    // 优雅退出
    sigs := make(chan os.Signal, 1)
    signal.Notify(sigs, syscall.SIGTERM, syscall.SIGINT)
    
    <-sigs
    ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
    defer cancel()
    srv.Shutdown(ctx)
}
```

## 三、面试高频题

### Q1: PreStop作用？

```
A:
1. 等待流量清理
2. 业务数据同步
3. 注册中心下线
```

### Q2: 如何设置优雅退出时间？

```
A:
1. terminationGracePeriodSeconds
2. 默认30秒
3. 根据业务调整
```

## 四、自测题

1. 解释Pod生命周期
2. 如何实现优雅退出？
3. 如何处理Init Container失败？

---

## 参考文档

- [K8s Pod生命周期](https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/)
- [优雅退出最佳实践](https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/#container-probes)
