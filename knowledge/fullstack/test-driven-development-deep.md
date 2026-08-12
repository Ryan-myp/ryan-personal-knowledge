# 测试驱动开发 (TDD) 深度实现

> **文档级别**: Level 5 - 专家级  
> **创建日期**: 2026-08-13  
> **状态**: ✅ 已补齐

---

## 一、TDD 循环

```
┌─────────────────────────────────────────────────────────────────┐
│                      TDD 红色-绿色-重构循环                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ┌─────────┐    ┌─────────┐    ┌─────────┐                   │
│   │  红色   │ → │  绿色   │ → │  重构   │                   │
│   │ (写测试) │   │ (通过)  │   │ (优化)  │                   │
│   └─────────┘    └─────────┘    └─────────┘                   │
│        ↑                                 │                     │
│        └─────────────────────────────────┘                     │
│                                                                 │
│   规则:                                                          │
│   1. 先写失败的测试 (红色)                                      │
│   2. 写最少代码使测试通过 (绿色)                                │
│   3. 重构代码，保持测试通过                                     │
│   4. 重复                                                        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 二、Go TDD 实战

```go
// 文件: tests/tdd_ad_bidding_test.go
package bidding

import (
	"testing"
	"time"
)

// ─── 阶段 1: 写失败测试 (RED) ───

func TestCalculateBid_InvalidBudget(t *testing.T) {
	// 测试边界条件
	_, err := CalculateBid(-100, 1.5, 0.8)
	if err == nil {
		t.Fatal("expected error for negative budget")
	}
}

func TestCalculateBid_ZeroCTR(t *testing.T) {
	// 测试极端情况
	bid, err := CalculateBid(1000, 0, 0.8)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if bid != 0 {
		t.Errorf("expected 0 bid for 0 CTR, got %f", bid)
	}
}

// ─── 阶段 2: 写通过测试 (GREEN) ───

func TestCalculateBid_NormalCase(t *testing.T) {
	budget := 1000.0
	ctr := 0.02   // 2%
	cvr := 0.1    // 10%
	
	expected := budget * ctr * cvr * 100 // 模拟 eCPM 计算
	bid, err := CalculateBid(budget, ctr, cvr)
	
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if bid < expected*0.9 || bid > expected*1.1 {
		t.Errorf("expected ~%f, got %f", expected, bid)
	}
}

func TestCalculateBid_HighValueUser(t *testing.T) {
	// 高价值用户溢价测试
	budget := 500.0
	ctr := 0.03
	cvr := 0.15
	userValue := 2.0 // 高价值用户系数
	
	bid, err := CalculateBid(budget, ctr, cvr)
	if err != nil {
		t.Fatal(err)
	}
	
	// 验证溢价逻辑
	expected := bid * userValue
	if bid < expected*0.95 {
		t.Errorf("high value user premium not applied correctly")
	}
}

// ─── 测试辅助函数 ───

func BenchmarkCalculateBid(b *testing.B) {
	for i := 0; i < b.N; i++ {
		CalculateBid(1000.0, 0.02, 0.1)
	}
}

func TestCalculateBid_Performance(t *testing.T) {
	start := time.Now()
	for i := 0; i < 10000; i++ {
		CalculateBid(1000.0, 0.02, 0.1)
	}
	elapsed := time.Since(start)
	
	if elapsed > 100*time.Millisecond {
		t.Errorf("too slow: %v for 10000 calls", elapsed)
	}
}
```

---

## 三、测试金字塔

```
                    ┌──────────┐
                   /  E2E测试  \    ← 少量 (10%)
                  /  (集成)    \
                 ─────────────────
                /   服务测试     \   ← 中等 (20%)
               /   (API/网关)    \
              ─────────────────────────
             /      单元测试        \  ← 大量 (70%)
            /     (核心逻辑)        \
           ─────────────────────────────
```

---

## 四、参考资料

```
核心概念:
├── TDD 三定律 (Kent Beck)
├── 测试金字塔
└── 覆盖率标准

工具链:
├── Go: testing + testify
├── JavaScript: Jest + Testing Library
└── Python: pytest + coverage
```

---

*文档版本: v1.0*  
*最后更新: 2026-08-13*  
*作者: Ryan*
