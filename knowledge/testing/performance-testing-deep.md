# 性能测试深度实现

> **文档级别**: Level 5 - 专家级  
> **创建日期**: 2026-08-13  
> **状态**: ✅ 已补齐

---

## 一、性能测试方法论

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        性能测试方法论                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. 基准测试 (Benchmark)                                                    │
│     • 单次操作的性能指标                                                     │
│     • 吞吐量、延迟、资源消耗                                                │
│                                                                             │
│  2. 负载测试 (Load Testing)                                                 │
│     • 正常负载下的表现                                                       │
│     • 峰值负载测试                                                           │
│                                                                             │
│  3. 压力测试 (Stress Testing)                                               │
│     • 极限负载                                                               │
│     • 系统崩溃点                                                             │
│                                                                             │
│  4. 稳定性测试 (Soak Testing)                                               │
│     • 长时间运行                                                             │
│     • 内存泄漏检测                                                           │
│                                                                             │
│  5. 尖峰测试 (Spike Testing)                                                │
│     • 突然流量变化                                                           │
│     • 系统恢复能力                                                           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 二、Go Benchmark 实战

```go
// 文件: testing/performance/benchmark_test.go

package performance

import "testing"

// ===== 基础 Benchmark =====

func BenchmarkStringConcat(b *testing.B) {
	for i := 0; i < b.N; i++ {
		s := ""
		for j := 0; j < 100; j++ {
			s += string(rune(j))
		}
	}
}

func BenchmarkStringBuilder(b *testing.B) {
	for i := 0; i < b.N; i++ {
		var sb strings.Builder
		for j := 0; j < 100; j++ {
			sb.WriteByte(byte(j))
		}
		_ = sb.String()
	}
}

// ===== 并行 Benchmark =====

func BenchmarkParallel(b *testing.B) {
	b.RunParallel(func(pb *testing.PB) {
		for pb.Next() {
			process()
		}
	})
}

// ===== 内存分析 =====

func BenchmarkMemory(b *testing.B) {
	b.ReportAllocs()
	for i := 0; i < b.N; i++ {
		data := make([]byte, 1024)
		_ = data
	}
}

// ===== 结果解读 =====
// goos: darwin
// goarch: amd64
// pkg: mypackage
// BenchmarkStringConcat-8   	    1000	   1234567 ns/op	  1234 B/op	    10 allocs/op
// BenchmarkStringBuilder-8  	   50000	     23456 ns/op	     0 B/op	     0 allocs/op
// PASS
```

---

## 三、k6 压测脚本

```javascript
// 文件: testing/performance/k6_script.js

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

// 自定义指标
const errorRate = new Rate('error_rate');
const requestDuration = new Trend('request_duration');

export const options = {
  stages: [
    { duration: '30s', target: 100 },  // 升温
    { duration: '1m', target: 100 },   // 稳定负载
    { duration: '30s', target: 200 },  // 加压
    { duration: '30s', target: 0 },    // 冷却
  ],
};

export default function() {
  const res = http.get('http://localhost:8080/api/bid');
  
  check(res, {
    'status is 200': (r) => r.status === 200,
    'response time < 100ms': (r) => r.timings.duration < 100,
  });
  
  errorRate.add(res.status !== 200 ? 1 : 0);
  requestDuration.add(res.timings.duration);
  
  sleep(1);
}
```

---

## 四、参考资料

```
核心工具:
├── Go testing: 内置 benchmark
├── k6: 现代压测工具
└── JMeter: 传统压测工具

指标解读:
├── p50/p95/p99 延迟
├── 吞吐量 (RPS/QPS)
└── 错误率
```

---

*文档版本: v1.0*  
*最后更新: 2026-08-13*  
*作者: Ryan*
