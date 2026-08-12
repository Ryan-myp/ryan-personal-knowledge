# 测试驱动开发 (TDD) 深度实现

> **文档级别**: Level 5 - 专家级  
> **创建日期**: 2026-08-13  
> **状态**: ✅ 已补齐

---

## 一、TDD 三重循环

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        TDD 三重循环                                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        Red 阶段                                     │   │
│  │  1. 编写失败的测试用例                                              │   │
│  │  2. 确保测试能够运行                                               │   │
│  │  3. 看到红色 (FAIL)                                                │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                              │                                              │
│                              ▼                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        Green 阶段                                   │   │
│  │  1. 编写最少的代码使测试通过                                       │   │
│  │  2. 不关心代码质量                                                  │   │
│  │  3. 看到绿色 (PASS)                                                 │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                              │                                              │
│                              ▼                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        Refactor 阶段                                │   │
│  │  1. 改进代码结构                                                    │   │
│  │  2. 消除重复                                                      │   │
│  │  3. 提高可读性                                                     │   │
│  │  4. 确保测试仍然通过                                               │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 二、Go TDD 实战

```go
// 文件: testing/tdd/example_test.go

package tdd

import (
	"testing"
	"github.com/stretchr/testify/assert"
)

func TestCalculateDiscount(t *testing.T) {
	result := CalculateDiscount(100, 0.2)
	expected := 80.0
	assert.InDelta(t, expected, result, 0.01)
}

func CalculateDiscount(price float64, discount float64) float64 {
	return price * (1 - discount)
}

func ValidateInputs(price, discount float64) error {
	if price < 0 {
		return fmt.Errorf("price cannot be negative")
	}
	if discount < 0 || discount > 1 {
		return fmt.Errorf("discount must be between 0 and 1")
	}
	return nil
}

func ApplyDiscount(price float64, discount float64) (float64, error) {
	if err := ValidateInputs(price, discount); err != nil {
		return 0, err
	}
	return price * (1 - discount), nil
}
```

---

## 三、测试金字塔

```
                    /\
                   /  \
                  / E2E\      ← 端到端测试 (少)
                 /______\     
                /        \    
               /  集成    \   ← 集成测试 (中)
              /   测试     \   
             /______________\ 
            /                \  
           /    单元测试      \ ← 单元测试 (多)
          /__________________\ 

比例: 单元测试 : 集成测试 : E2E = 70% : 20% : 10%
```

---

*文档版本: v1.0*  
*最后更新: 2026-08-13*  
*作者: Ryan*
