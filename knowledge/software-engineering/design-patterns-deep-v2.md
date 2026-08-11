# 设计模式深度解析

> 深入设计模式：创建型、结构型、行为型模式详解。
> 源码级分析，包含Go/Python实现。
> 适用对象：后端工程师、架构师

---

## 1. 创建型模式

### 1.1 单例模式

```
Go 单例模式实现：

┌─────────────────────────────────────────────────────────────┐
│  // 懒汉式（线程安全）                                       │
│  type Singleton struct {}                                    │
│  var instance *Singleton                                     │
│  var once sync.Once                                          │
│                                                              │
│  func GetInstance() *Singleton {                            │
│      once.Do(func() {                                        │
│          instance = &Singleton{}                             │
│      })                                                      │
│      return instance                                         │
│  }                                                           │
│                                                              │
│  // 饿汉式                                                   │
│  var instance = &Singleton{}                                 │
│                                                              │
│  // 双重检查锁定（Double-Check Locking）                      │
│  func GetInstance() *Singleton {                            │
│      if instance == nil {                                    │
│          sync.Once.Do(&once, func() {                       │
│              if instance == nil {                            │
│                  instance = &Singleton{}                     │
│              }                                               │
│          })                                                  │
│      }                                                       │
│      return instance                                         │
│  }                                                           │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. 结构型模式

### 2.1 代理模式

```
Go 代理模式实现：

┌─────────────────────────────────────────────────────────────┐
│  type Subject interface {                                    │
│      Request() string                                        │
│  }                                                           │
│                                                              │
│  type RealSubject struct {}                                  │
│  func (r *RealSubject) Request() string {                   │
│      return "RealSubject response"                           │
│  }                                                           │
│                                                              │
│  type Proxy struct {                                         │
│      subject Subject                                         │
│  }                                                           │
│  func (p *Proxy) Request() string {                         │
│      // 前置处理                                              │
│      result := p.subject.Request()                          │
│      // 后置处理                                              │
│      return result                                           │
│  }                                                           │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. 自测题

### 3.1 单选题

1. Go中，sync.Once主要用于实现：
   A. 工厂模式  B. 单例模式  C. 观察者模式  D. 策略模式
   答案：B

---

> 本文档适用对象：后端工程师、架构师
> 难度：资深专家级
