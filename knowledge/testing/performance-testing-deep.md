# 性能测试深度实现 - JMeter/Gatling/K6 对比

> **版本**: v2.0  
> **日期**: 2026-08-13  
> **作者**: Ryan  
> **分类**: 测试/性能  
> **代码密度**: 28%

---

## 一、测试类型

```
┌─────────────────────────────────────────────────────────────────────┐
│                    性能测试类型                                      │
│                                                                     │
│  Load Test (负载测试)    → 正常负载下的表现                           │
│  Stress Test (压力测试)  → 极限负载直到崩溃                           │
│  Spike Test (峰值测试)   → 突增流量的恢复能力                         │
│  Endurance Test ( endurance) → 长时间稳定运行                         │
│  Volume Test (容量测试)   → 大数据量下的性能                          │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 二、Gatling 实现 (Scala)

```scala
//gatling/BiddingSimulation.scala
import io.gatling.core.Predef._
import io.gatling.http.Predef._
import scala.concurrent.duration._

class BiddingSimulation extends Simulation {
  
  val httpProtocol = http
    .baseUrl("http://bidding-api.example.com")
    .header("Authorization", "Bearer ${TOKEN}")
    .inferHtmlResources()
  
  val scn = scenario("BiddingSimulation")
    .exec(http("login")
      .post("/api/v1/auth/login")
      .body(StringBody("""{"username":"test","password":"test"}"""))
      .asJSON
      .check(jsonPath("$.token").saveAs("token"))
    )
    .exec(http("bid")
      .post("/api/v1/bid")
      .header("Authorization", "Bearer ${token}")
      .body(StringBody("""{"ad_unit_id":"123","price":1.5}"""))
      .asJSON
      .check(status.is(200))
    )
    .pause(1)
  
  setUp(
    scn.inject(
      rampUsers(100) during (30 seconds),  // 30秒内从0到100并发
      constantUsersPerSec(100) during (1 minute),  // 保持100并发1分钟
      rampUsers(200) during (30 seconds),  // 30秒内到200并发
      constantUsersPerSec(200) during (2 minutes)  // 保持200并发2分钟
    ).protocols(httpProtocol)
  ).assertions(
    global.responseTime.percentile3.lte(100),  // P3 < 100ms
    global.responseTime.percentile95.lte(500),  // P95 < 500ms
    global.failureRate.lt(0.01)  // 错误率 < 1%
  )
}
```

---

## 三、k6 实现 (JavaScript)

```javascript
// k6/bidding_test.js
import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate } from 'k6/metrics';

const errorRate = new Rate('error_rate');

export const options = {
  stages: [
    { duration: '30s', target: 100 },   // 爬升到100 VUs
    { duration: '1m', target: 100 },    // 保持100 VUs
    { duration: '30s', target: 300 },   // 爬升到300 VUs
    { duration: '2m', target: 300 },    // 保持300 VUs
    { duration: '30s', target: 0 },     // 回到0
  ],
  thresholds: {
    http_req_duration: ['p(95)<500', 'p(99)<1000'],
    http_req_failed: ['rate<0.01'],
    error_rate: ['rate<0.05'],
  },
};

export default function() {
  const loginRes = http.post('http://localhost:8080/api/v1/auth/login',
    JSON.stringify({ username: 'test', password: 'test' }),
    { headers: { 'Content-Type': 'application/json' } }
  );
  
  const token = loginRes.json('token');
  
  const bidRes = http.post('http://localhost:8080/api/v1/bid',
    JSON.stringify({ ad_unit_id: '123', price: 1.5 }),
    { headers: { 'Authorization': `Bearer ${token}` } }
  );
  
  const success = check(bidRes, {
    'status is 200': (r) => r.status === 200,
    'response time < 500ms': (r) => r.timings.duration < 500,
  });
  
  errorRate.add(!success);
  sleep(1);
}
```

---

## 四、JMeter 实现

```xml
<!-- bidding_test.jmx -->
<?xml version="1.0" encoding="UTF-8"?>
<jmeterTestPlan>
  <hashTree>
    <ThreadGroup>
      <stringProp name="ThreadGroup.num_threads">100</stringProp>
      <stringProp name="ThreadGroup.ramp_time">30</stringProp>
      <LoopController>
        <intProp name="LoopController.loops">-1</intProp>
      </LoopController>
      <hashTree>
        <HTTPSamplerProxy>
          <stringProp name="HTTPSampler.path">/api/v1/bid</stringProp>
          <stringProp name="HTTPSampler.method">POST</stringProp>
          <elementProp name="HTTPsampler.Arguments">
            <collectionProp name="Arguments.arguments">
              <elementProp>
                <stringProp name="Argument.name">ad_unit_id</stringProp>
                <stringProp name="Argument.value">123</stringProp>
              </elementProp>
            </collectionProp>
          </elementProp>
        </HTTPSamplerProxy>
        <hashTree/>
      </hashTree>
    </ThreadGroup>
  </hashTree>
</jmeterTestPlan>
```

---

## 五、性能指标监控

```yaml
# monitoring/performance.yaml
metrics:
  - name: http_requests_total
    type: counter
    labels: [method, path, status]
    
  - name: http_request_duration_seconds
    type: histogram
    buckets: [0.01, 0.05, 0.1, 0.25, 0.5, 1.0]
    labels: [method, path]
    
  - name: active_connections
    type: gauge
    labels: [pool]
    
  - name: goroutines
    type: gauge
    
alerts:
  - name: HighLatency
    expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 0.5
    severity: warning
    
  - name: HighErrorRate
    expr: rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m]) > 0.01
    severity: critical
```

---

## 六、自测题

1. **Gatling vs k6 vs JMeter 如何选择？**
   - Gatling (Scala,高性能), k6 (JS,云原生), JMeter (GUI,功能丰富)

2. **P95 和 P99 的区别？**
   - P95: 95%请求在此时间内完成; P99: 更严格的标准

3. **如何进行压力测试？**
   - 逐步增加并发直到系统崩溃，找到瓶颈

