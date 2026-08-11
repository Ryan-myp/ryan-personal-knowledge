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
│  // 懒汉式（线程安全）                                        │
│  type Singleton struct{}                                     │
│                                                             │
│  var (                                                       │
│      instance *Singleton                                     │
│      once sync.Once                                          │
│  )                                                           │
│                                                             │
│  func GetInstance() *Singleton {                            │
│      once.Do(func() {                                        │
│          instance = &Singleton{}                             │
│      })                                                      │
│      return instance                                         │
│  }                                                           │
│                                                             │
│  // 饿汉式（已加载即创建）                                    │
│  var instance = &Singleton{}                                 │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 工厂模式

```
工厂模式对比：

┌─────────────────────────────────────────────────────────────┐
│  简单工厂：                                                  │
│  ├── 一个工厂类根据参数创建不同对象                            │
│  └── 缺点：违反开闭原则                                       │
│                                                             │
│  工厂方法：                                                  │
│  ├── 定义创建对象的接口，子类决定实例化哪个类                  │
│  └── 符合开闭原则                                            │
│                                                             │
│  抽象工厂：                                                  │
│  ├── 创建相关或依赖对象家族，无需指定具体类                    │
│  └── 适用于多系列产品                                        │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. 结构型模式

### 2.1 适配器模式

```
适配器模式示例：

┌─────────────────────────────────────────────────────────────┐
│  场景：旧系统接口与新系统不兼容                               │
│                                                             │
│  Target接口（新系统期望）：                                   │
│  type PaymentProcessor interface {                          │
│      Pay(amount float64) error                              │
│  }                                                           │
│                                                             │
│  Adaptee（旧系统）：                                         │
│  type OldPayment struct {}                                   │
│  func (o *OldPayment) ProcessPayment(amount int) error      │
│                                                             │
│  Adapter（适配器）：                                         │
│  type PaymentAdapter struct {                                │
│      oldPayment *OldPayment                                  │
│  }                                                           │
│  func (a *PaymentAdapter) Pay(amount float64) error {       │
│      return a.oldPayment.ProcessPayment(int(amount))         │
│  }                                                           │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. 行为型模式

### 3.1 观察者模式

```
Go 观察者模式实现：

┌─────────────────────────────────────────────────────────────┐
│  type Observer interface {                                   │
│      Update(message string)                                 │
│  }                                                           │
│                                                             │
│  type Subject struct {                                      │
│      observers []Observer                                    │
│  }                                                           │
│                                                             │
│  func (s *Subject) Attach(o Observer) {                     │
│      s.observers = append(s.observers, o)                   │
│  }                                                           │
│                                                             │
│  func (s *Subject) Notify(msg string) {                     │
│      for _, o := range s.observers {                        │
│          o.Update(msg)                                      │
│      }                                                       │
│  }                                                           │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. 自测题

### 4.1 单选题

1. 单例模式使用sync.Once的目的是：
   A. 提高性能  B. 保证线程安全  C. 减少内存  D. 简化代码
   答案：B

---

> 本文档适用对象：后端工程师、架构师
> 难度：资深专家级
