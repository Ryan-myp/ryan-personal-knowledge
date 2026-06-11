---

## 自测题

### 问题 1
微信读书 API 的 Skill Version 为什么不能省略？

<details>
<summary>查看答案</summary>

1. **版本控制**：API 会迭代，version 确保向后兼容
2. **调试**：version 帮助定位请求格式问题
3. **渐进升级**：新旧版本可以共存，平滑过渡
4. **最佳实践**：所有第三方 API 都应带 version

</details>

### 问题 2
为什么 weread API 要求参数必须平铺在 JSON body 顶层？

<details>
<summary>查看答案</summary>

1. **设计选择**：微信读书 API 没有用嵌套 JSON 结构
2. **调试困难**：参数位置不对返回通用错误，难排查
3. **对比 REST**：REST API 通常用嵌套结构， weread 比较特殊
4. **经验教训**：调用前先用 curl 测试，看返回结构

</details>