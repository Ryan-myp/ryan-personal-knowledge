---

## 自测题

### 问题 1
biz-delivery 框架中为什么用 knowledge-search 而不是直接查数据库？

<details>
<summary>查看答案</summary>

1. **语义搜索**：knowledge-search 支持自然语言查询，数据库只支持精确匹配
2. **混合检索**：BM25 + 向量检索，比单一检索效果好
3. **跨代码库**：knowledge-search 可以搜索代码、文档、数据库
4. **性能**：knowledge-search 做了缓存和预计算，查询更快

</details>

### 问题 2
Go 在 biz-delivery 框架中相比 Python 的优势是什么？

<details>
<summary>查看答案</summary>

1. **性能**：Go 编译型语言，查询性能比 Python 高 10 倍+
2. **并发**：goroutine 天然适合高并发查询场景
3. **部署**：单二进制文件，无依赖，容器化简单
4. **团队**：团队技术栈是 Go，统一语言降低维护成本

</details>

### 问题 2
Go 的 interface{} 在 biz-delivery 框架中如何替代？

<details>
<summary>查看答案</summary>

1. **泛型替代**：Go 1.18+ 使用泛型实现类型安全的接口
2. **Go 实现**：
```go
type SkillInput[T any] interface {
    Execute(ctx context.Context, input T) (interface{}, error)
}

type SkillOutput[T any] interface {
    Serialize() (T, error)
    Deserialize(data T) error
}
```
3. **优势**：编译期类型检查，无需运行时断言

</details>

### 问题 3
biz-delivery 框架中如何测试 Skill 的执行？

<details>
<summary>查看答案</summary>

1. **Mock 依赖**：使用 gomock 模拟 LLM 和 KnowledgeBase
2. **单元测试**：
```go
func TestSkillExecution(t *testing.T) {
    engine := &DeliveryEngine{
        knowledgeBase: mockKnowledgeBase,
        skills: map[string]Skill{
            "ad-analysis": &AdAnalysisSkill{},
        },
    }
    
    result, err := engine.Deliver("ad-analysis", map[string]interface{}{
        "campaignId": "12345",
    })
    
    assert.NoError(t, err)
    assert.NotNil(t, result)
}
```
3. **集成测试**：连接真实 LLM 和知识库

</details>

---

*本文档基于 biz-delivery 框架整理。*

---

## Go 代码示例

### biz-delivery 框架核心

```go
package bizdelivery

import (
    "context"
    "fmt"
)

type DeliveryEngine struct {
    knowledgeBase *KnowledgeBase
    skills        map[string]Skill
}

type Skill interface {
    Name() string
    Execute(ctx context.Context, params map[string]interface{}) (interface{}, error)
}

func (e *DeliveryEngine) Deliver(skillName string, params map[string]interface{}) (interface{}, error) {
    skill, ok := e.skills[skillName]
    if !ok {
        return nil, fmt.Errorf("skill not found: %s", skillName)
    }
    
    return skill.Execute(context.Background(), params)
}
```

---

*本文档基于 biz-delivery 框架整理。*