# 设计模式章节

> 简要介绍设计模式的核心概念

---

## 一、设计模式简介

设计模式是**可复用的软件设计解决方案**，分为三类：
- **创建型**：工厂、单例、建造者
- **结构型**：适配器、装饰器、代理
- **行为型**：观察者、策略、命令

---

## 二、Go 中的设计模式

Go 没有继承，通过**接口 + 组合**实现设计模式。

### 2.1 策略模式

```go
type PaymentStrategy interface {
    Pay(amount float64) error
}

type CreditCard struct{}
func (c *CreditCard) Pay(amount float64) error { ... }

type PayPal struct{}
func (p *PayPal) Pay(amount float64) error { ... }
```

### 2.2 观察者模式

```go
type Observer interface {
    Update(message string)
}

type Subject struct {
    observers []Observer
}

func (s *Subject) Notify() {
    for _, o := range s.observers {
        o.Update("hello")
    }
}
```

---

## 三、实战建议

- **先写代码，再识别模式**：模式是事后总结的，不是事前规划的
- **不要为了模式而模式**：简单场景用 if-else 就好
- **Go 的接口比 Java 更灵活**：不需要预先定义所有接口

---

## 四、自测题

### 问题 1
策略模式和条件分支（if-else/Switch）在什么情况下该用策略模式？

<details>
<summary>查看答案</summary>

当以下条件满足 3 个以上时用策略模式：
1. 分支超过 3 个（if-else 超过 3 层可读性差）
2. 策略之间逻辑独立，互不影响
3. 策略需要动态切换（运行时决定用哪个）
4. 策略可能频繁新增/删除（开闭原则）

Go 用 interface 天然支持策略模式，不需要创建额外的 Strategy 接口。

</details>

### 问题 2
Go 的 struct 组合与继承有什么区别？为什么 Go 选择组合而非继承？

<details>
<summary>查看答案</summary>

**组合**是 has-a 关系，**继承**是 is-a 关系。

Go 选择组合的原因：
1. 继承导致类层次爆炸，组合更灵活
2. 继承违反封装，子类依赖父类实现细节
3. 组合支持运行时切换行为，继承是编译期静态绑定
4. Go 的匿名字段语法糖（Embedding）让组合比继承更简洁

</details>