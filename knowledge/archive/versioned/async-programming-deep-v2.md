# 异步编程深度解析

> 深入异步编程：Promise/async-await、协程、Future、回调地狱。
> 源码级分析，包含生产环境最佳实践。
> 适用对象：后端工程师、全栈工程师

---

## 1. Promise机制

### 1.1 状态机

```
Promise状态机：

┌─────────────────────────────────────────────────────────────┐
│  三种状态：                                                  │
│  ├── Pending：初始状态                                       │
│  ├── Fulfilled：成功完成                                      │
│  └── Rejected：失败                                         │
│                                                             │
│  状态转换：                                                  │
│  Pending → Fulfilled（不可逆）                               │
│  Pending → Rejected（不可逆）                                │
│                                                             │
│  then/catch链：                                              │
│  promise.then(onFulfilled, onRejected)                      │
│              .catch(onError)                                 │
│              .finally(onFinally)                             │
│                                                             │
│  微任务：                                                    │
│  ├── Promise回调是微任务                                     │
│  ├── 当前执行栈清空后执行                                     │
│  └── 优先级高于setTimeout                                     │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. async/await

### 2.1 语法糖

```
async/await本质：

┌─────────────────────────────────────────────────────────────┐
│  async函数：                                                 │
│  ├── 返回Promise                                            │
│  ├── 可以await其他async函数                                  │
│  └── 语法糖，不改变异步本质                                    │
│                                                             │
│  await表达式：                                               │
│  ├── 等待Promise resolve                                     │
│  ├── 暂停函数执行                                             │
│  ├── 非阻塞（释放线程）                                      │
│  └── 只能在async函数内使用                                    │
│                                                             │
│  错误处理：                                                  │
│  ├── try/catch                                             │
│  └── 等价于 .catch()                                        │
│                                                             │
│  并发控制：                                                  │
│  ├── Promise.all()：全部成功                                 │
│  ├── Promise.race()：最快结果                                │
│  └── Promise.allSettled()：全部完成                          │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. 自测题

### 3.1 单选题

1. Promise.all()在什么情况下返回：
   A. 任一Promise reject  B. 全部Promise resolve  C. 最先完成的  D. 最后完成的
   答案：B

---

> 本文档适用对象：后端工程师、全栈工程师
> 难度：资深专家级
