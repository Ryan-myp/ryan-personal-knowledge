# 前端性能监控 - 资深专家深度实现

## 一、核心指标

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      Core Web Vitals                                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   LCP (Largest Contentful Paint)                                       │
│   ├── 目标: ≤ 2.5s                                                      │
│   ├── 测量: 最大内容元素加载时间                                            │
│   └── 优化: 资源预加载/懒加载                                              │
│                                                                         →
│   INP (Interaction to Next Paint)                                      │
│   ├── 目标: ≤ 200ms                                                     │
│   ├── 测量: 用户交互到页面响应时间                                           │
│   └── 优化: 代码分割/Web Worker                                            │
│                                                                         →
│   CLS (Cumulative Layout Shift)                                        │
│   ├── 目标: ≤ 0.1                                                       │
│   ├── 测量: 页面布局偏移累积                                               │
│   └── 优化: 尺寸预留/字体优化                                              │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、Real User Monitoring

```javascript
// 上报函数
function reportMetric(metric) {
  const payload = JSON.stringify({
    name: metric.name,
    value: metric.value,
    rating: metric.rating,
    delta: metric.delta,
    id: metric.id
  });
  
  // 使用sendBeacon确保数据送达
  navigator.sendBeacon('/api/metric', payload);
}

// 监听FCP
new PerformanceObserver((list) => {
  for (const entry of list.getEntries()) {
    if (entry.name === 'first-contentful-paint') {
      reportMetric(entry);
    }
  }
}).observe({ type: 'paint', buffered: true });

// 监听LCP
new PerformanceObserver((list) => {
  reportMetric(list.getEntries().pop());
}).observe({ type: 'largest-contentful-paint', buffered: true });
```

## 三、面试高频题

### Q1: 如何优化LCP？

```
A:
1. 预加载关键资源
2. 图片懒加载
3. CDN加速
```

### Q2: INP与FID区别？

```
A:
1. FID是首次输入延迟
2. INP是整体交互延迟
3. INP更准确
```

## 四、自测题

1. 解释Core Web Vitals
2. 如何实现RUM？
3. 如何优化CLS？

---

## 参考文档

- [Web Vitals官方文档](https://web.dev/vitals/)
- [Performance API](https://developer.mozilla.org/en-US/docs/Web/API/Performance_API)
