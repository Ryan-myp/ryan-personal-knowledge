# 性能测试深度实现

> **文档级别**: Level 5 - 专家级  
> **创建日期**: 2026-08-13  
> **状态**: ✅ 已补齐

---

## 一、测试类型与工具

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       性能测试类型矩阵                                      │
├──────────────────┬──────────────────────┬──────────────────────────────────┤
│     类型         │      工具            │        适用场景                  │
├──────────────────┼──────────────────────┼──────────────────────────────────┤
│ 负载测试         │ k6, JMeter         │ 正常负载下的性能验证            │
│ 压力测试         │ k6, Locust         │ 找到系统瓶颈极限                │
│ 并发测试         │ wrk, ab            │ 高并发场景验证                  │
│ 稳定性测试       │ k6, Grafana      │ 长时间运行下的稳定性            │
│ 峰值测试         │ k6                 │ 突发流量应对能力                │
└──────────────────┴──────────────────────┴──────────────────────────────────┘
```

---

## 二、Go 性能测试实战

```go
// 文件: tests/performance_test.go
package bidding

import (
	"testing"
	"sync"
	"time"
)

// ─── 基准测试 ───

func BenchmarkCalculateBid(b *testing.B) {
	for i := 0; i < b.N; i++ {
		CalculateBid(1000.0, 0.02, 0.1)
	}
}

func BenchmarkCalculateBid_Parallel(b *testing.B) {
	b.RunParallel(func(pb *testing.PB) {
		i := 0
		for pb.Next() {
			CalculateBid(1000.0, float64(i%100)/10000, 0.1)
			i++
		}
	})
}

// ─── 并发测试 ───

func TestBidService_ConcurrentAccess(t *testing.T) {
	service := NewBidService()
	var wg sync.WaitGroup
	
	// 模拟 1000 个并发请求
	for i := 0; i < 1000; i++ {
		wg.Add(1)
		go func(id int) {
			defer wg.Done()
			bid, err := service.CalculateBid(
				1000.0,
				float64(id%100)/10000,
				0.1,
			)
			if err != nil {
				t.Errorf("request %d failed: %v", id, err)
			}
			if bid < 0 {
				t.Errorf("negative bid for request %d", id)
			}
		}(i)
	}
	
	wg.Wait()
}

// ─── 压力测试 ───

func TestBidService_Stress(t *testing.T) {
	service := NewBidService()
	start := time.Now()
	
	const concurrent = 500
	const total = 10000
	
	var wg sync.WaitGroup
	errors := make(chan error, total)
	
	for i := 0; i < total; i++ {
		wg.Add(1)
		go func(id int) {
			defer wg.Done()
			_, err := service.CalculateBid(
				1000.0,
				float64(id%100)/10000,
				0.1,
			)
			if err != nil {
				errors <- err
			}
		}(i)
	}
	
	wg.Wait()
	close(errors)
	
	elapsed := time.Since(start)
	
	// 断言
	if elapsed > 5*time.Second {
		t.Errorf("too slow: %v for %d requests", elapsed, total)
	}
	
	// 检查错误率
	errCount := 0
	for err := range errors {
		t.Logf("error: %v", err)
		errCount++
	}
	
	errorRate := float64(errCount) / float64(total)
	if errorRate > 0.01 {
		t.Errorf("high error rate: %.2f%%", errorRate*100)
	}
	
	t.Logf("avg latency: %v", elapsed/time.Duration(total))
}

// ─── 内存分析 ───

func TestBidService_MemoryProfile(t *testing.T) {
	service := NewBidService()
	
	// 执行大量请求
	for i := 0; i < 100000; i++ {
		service.CalculateBid(1000.0, 0.02, 0.1)
	}
	
	// 触发 GC 并生成内存 profile
	runtime.GC()
	
	// 可使用 pprof 分析
	// go test -memprofile=mem.out
}
```

---

## 三、k6 负载测试脚本

```javascript
// 文件: loadtest/bid_service.js
import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate } from 'k6/metrics';

const errorRate = new Rate('error_rate');

export const options = {
  stages: [
    { duration: '30s', target: 100 },   // 爬坡到 100 QPS
    { duration: '1m', target: 100 },    // 稳定 100 QPS
    { duration: '30s', target: 300 },   // 峰值 300 QPS
    { duration: '1m', target: 300 },    // 稳定峰值
    { duration: '30s', target: 0 },     // 回落
  ],
};

export default function () {
  const payload = JSON.stringify({
    budget: 1000,
    ctr: 0.02,
    cvr: 0.1,
  });
  
  const res = http.post(
    'http://localhost:8080/api/v1/bid/calculate',
    payload,
    { headers: { 'Content-Type': 'application/json' } }
  );
  
  const success = check(res, {
    'status is 200': (r) => r.status === 200,
    'latency < 100ms': (r) => r.timings.duration < 100,
    'response valid': (r) => r.json('bid') > 0,
  });
  
  errorRate.add(!success);
  sleep(0.1);
}
```

---

## 四、参考资料

```
核心工具:
├── Go testing: 内置基准测试
├── k6: 现代负载测试工具
├── JMeter: Java 负载测试
└── Locust: Python 分布式测试

分析工具:
├── pprof: Go 性能分析
├── flamegraph: 火焰图生成
└── benchstat: 基准对比
```

---

*文档版本: v1.0*  
*最后更新: 2026-08-13*  
*作者: Ryan*
