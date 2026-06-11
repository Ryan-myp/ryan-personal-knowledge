## 第六部分：自测题

### 问题 1
设计模式中的"开闭原则"在 Go 的 interface 中如何体现？

<details>
<summary>查看答案</summary>

1. **对扩展开放**：新增实现只需实现接口，无需修改已有代码
2. **对修改关闭**：接口定义不变，调用方无需修改
3. Go 的 interface 是隐式实现，天然支持开闭原则
4. 对比 Java 的显式 implements，Go 的鸭子类型更灵活

</details>

### 问题 2
Go 的 interface 空接口 interface{} 作为函数参数有什么代价？

<details>
<summary>查看答案</summary>

1. **类型擦除**：编译期无法检查类型正确性
2. **运行时断言**：需要 type switch 或 type assertion 还原
3. **性能开销**：interface{} 包含 type pointer + data pointer
4. **优化方案**：Go 1.18+ 的泛型可以替代 interface{} 的使用

</details>

### 问题 3
"组合优于继承"在 Go 的 struct embedding 中如何体现？

<details>
<summary>查看答案</summary>

1. **组合是 has-a**：Embedding 让结构体"拥有"另一个结构体的方法
2. **继承是 is-a**：Go 没有继承概念，避免类层次爆炸
3. **嵌入的局限性**：不能重写父结构体的方法，只能 override
4. **推荐做法**：用组合 + 接口实现多态，而不是嵌入实现继承

</details>