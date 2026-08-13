# 性能测试实战指南

> k6, JMeter, Gatling 对比与实战。

---

## 1. k6 使用

```javascript
import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  stages: [
    { duration: '30s', target: 100 },
    { duration: '1m', target: 100 },
    { duration: '30s', target: 0 },
  ],
};

export default function () {
  const res = http.get('http://test.k6.io/');
  check(res, {
    'status is 200': (r) => r.status === 200,
  });
  sleep(1);
}
```

---

## 2. JMeter 脚本

```xml
<TestPlan guiclass="TestPlanGui" testclass="TestPlan">
  <hashTree>
    <ThreadGroup guiclass="ThreadGroupGui">
      <stringProp name="ThreadGroup.num_threads">100</stringProp>
      <stringProp name="ThreadGroup.ramp_up">10</stringProp>
    </ThreadGroup>
  </hashTree>
</TestPlan>
```

---

## 3. 指标监控

```bash
# Prometheus metrics
curl http://localhost:9090/metrics | grep http_request_duration

# Grafana 看板
# 导入 k6 dashboard JSON
```

---

**参考**: k6 官方文档、JMeter 用户指南
