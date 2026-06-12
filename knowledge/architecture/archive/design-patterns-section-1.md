# 设计模式与系统架构 — Go 源码级 23 种模式、DDD、CQRS、Saga、分布式协议

> 标签: `#设计模式` `#DDD` `#CQRS` `#EventSourcing` `#Saga` `#Go` `#源码级`
> 创建日期: 20260608
> 作者: Ryan

---

## 1. 23 种设计模式 — Go 源码级实现

### 1.1 创建型模式（Creational）

#### 单例模式（Singleton）— Go 三种实现

```go
// 方式1: sync.Once（Go 推荐做法）
type Config struct {
    mu   sync.Mutex
    m    map[string]string
}

var (
    once   sync.Once
    config *Config
)

func GetConfig() *Config {
    once.Do(func() {
        config = &Config{
            m: make(map[string]string),
        }
        config.m["timeout"] = "30s"
    })
    return config
}

// 方式2: init() 函数（最简洁，全局唯一）
var defaultLogger = &Logger{level: "info"}

func GetLogger() *Logger { return defaultLogger }

// sync.Once 源码剖析（src/sync/once.go）:
// type Once struct {
//     done uint32 // atomic, 0=未执行, 1=已执行
//     m    Mutex
// }
// func (o *Once) Do(f func()) {
//     if atomic.LoadUint32(&o.done) == 1 { return }
//     o.m.Lock()
//     defer o.m.Unlock()
//     if o.done == 0 { f(); atomic.StoreUint32(&o.done, 1) }
// }
//
// 关键点:
// - atomic.LoadUint32 读 done，未执行时走锁路径
// - 双检：拿到锁后还要再检查 done
// - atomic.StoreUint32 写 done，保证 happens-before 关系
// - Go 的 sync.Once 保证 f() 只执行一次，且 Do() 返回前已完成

</details>

---

*本文档基于设计模式与系统架构整理。*
```

#### 工厂方法 vs 抽象工厂

```go
// 场景: 广告平台的多种计费方式
package billing

type Bidder interface {
    Bid(event AdEvent) (float64, error)
}

type CPMBidder struct{}

func (b *CPMBidder) Bid(event AdEvent) (float64, error) {
    return float64(event.Impressions) * 0.001, nil
}

type CP...[truncated]