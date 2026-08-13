# 前端性能监控体系深度实现 - 资深专家

## 一、监控指标体系

### 1.1 Core Web Vitals

```javascript
// LCP - Largest Contentful Paint
function trackLCP() {
  return new Promise((resolve) => {
    const observer = new PerformanceObserver((list) => {
      const entries = list.getEntries();
      const lcp = entries[entries.length - 1];
      resolve({
        value: lcp.startTime,
        element: lcp.element?.tagName,
        url: lcp.url,
      });
    });
    
    observer.observe({ type: 'largest-contentful-paint', buffered: true });
    
    // 超时处理
    setTimeout(() => {
      observer.disconnect();
      resolve(null);
    }, 5000);
  });
}

// FID - First Input Delay
function trackFID() {
  return new Promise((resolve) => {
    let fid = 0;
    const entries = performance.getEntriesByType('event');
    
    for (const entry of entries) {
      if (entry.startTime < performance.getEntriesByType('navigation')[0].startTime + 5000) {
        fid = Math.max(fid, entry.processingEnd - entry.processingStart);
      }
    }
    
    resolve(fid);
  });
}

// CLS - Cumulative Layout Shift
function trackCLS() {
  return new Promise((resolve) => {
    let cls = 0;
    const observer = new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        if (!entry.hadRecentInput) {
          cls += entry.value;
        }
      }
    });
    
    observer.observe({ type: 'layout-shift', buffered: true });
    
    setTimeout(() => {
      observer.disconnect();
      resolve(cls);
    }, 3000);
  });
}
```

### 1.2 性能指标采集

```javascript
// 性能指标采集器
class PerformanceMonitor {
  constructor() {
    this.metrics = {
      // 加载指标
      fcp: null,      // First Contentful Paint
      lcp: null,      // Largest Contentful Paint
      fid: null,      // First Input Delay
      cls: null,      // Cumulative Layout Shift
      ttfb: null,     // Time to First Byte
      domReady: null, // DOM Ready
      
      // 资源指标
      resources: [],
      jsErrors: [],
      networkErrors: [],
      
      // 用户行为
      userActions: [],
      pageViews: [],
    };
  }
  
  // 开始采集
  start() {
    this.collectNavigationMetrics();
    this.collectResourceMetrics();
    this.collectUserBehavior();
    this.setupErrorTracking();
  }
  
  // 导航指标
  collectNavigationMetrics() {
    const navigation = performance.getEntriesByType('navigation')[0];
    if (navigation) {
      this.metrics.ttfb = navigation.responseStart - navigation.requestStart;
      this.metrics.domReady = navigation.domContentLoadedEventEnd - navigation.startTime;
    }
  }
  
  // 资源指标
  collectResourceMetrics() {
    const resources = performance.getEntriesByType('resource');
    this.metrics.resources = resources.map(r => ({
      name: r.name,
      duration: r.duration,
      size: r.transferSize,
      type: r.initiatorType,
      status: r.status,
    }));
  }
}
```

## 二、实时监控

### 2.1 WebSocket实时推送

```javascript
// 实时监控客户端
class RealtimeMonitor {
  constructor(wsUrl) {
    this.wsUrl = wsUrl;
    this.ws = null;
    this.queue = [];
    this.batchSize = 10;
    this.flushTimer = null;
  }
  
  // 连接WebSocket
  connect() {
    this.ws = new WebSocket(this.wsUrl);
    
    this.ws.onopen = () => {
      console.log('Realtime monitor connected');
      this.flushQueue();
    };
    
    this.ws.onmessage = (event) => {
      const message = JSON.parse(event.data);
      this.handleServerMessage(message);
    };
    
    this.ws.onclose = () => {
      // 重连逻辑
      setTimeout(() => this.connect(), 5000);
    };
  }
  
  // 上报数据
  report(metric) {
    this.queue.push(metric);
    
    if (this.queue.length >= this.batchSize) {
      this.flushQueue();
    } else {
      this.scheduleFlush();
    }
  }
  
  // 批量上报
  flushQueue() {
    if (this.queue.length === 0 || !this.ws || this.ws.readyState !== WebSocket.OPEN) {
      return;
    }
    
    const data = JSON.stringify({
      timestamp: Date.now(),
      metrics: this.queue.splice(0),
    });
    
    this.ws.send(data);
  }
  
  // 定时刷新
  scheduleFlush() {
    if (this.flushTimer) clearTimeout(this.flushTimer);
    this.flushTimer = setTimeout(() => this.flushQueue(), 1000);
  }
}
```

### 2.2 服务端聚合

```go
// 性能指标聚合服务
type PerformanceAggregator struct {
    db     *sql.DB
    redis  *redis.Client
    buffer chan MetricPoint
}

// 指标点
type MetricPoint struct {
    Timestamp time.Time
    Metric    string
    Value     float64
    Tags      map[string]string
}

// 批量写入
func (a *PerformanceAggregator) BatchWrite(points []MetricPoint) error {
    // 写入Redis
    pipe := a.redis.Pipeline()
    for _, point := range points {
        key := fmt.Sprintf("perf:%s:%s", point.Metric, point.Tags["page"])
        pipe.ZAdd(context.Background(), key, redis.Z{
            Score:  float64(point.Timestamp.Unix()),
            Member: point.Value,
        })
    }
    pipe.Exec(context.Background())
    
    // 异步写入DB
    go a.writeToDB(points)
    
    return nil
}

// 写入DB
func (a *PerformanceAggregator) writeToDB(points []MetricPoint) {
    tx, _ := a.db.Begin()
    for _, point := range points {
        tagsJSON, _ := json.Marshal(point.Tags)
        tx.Exec(`
            INSERT INTO metric_points (metric, value, tags, timestamp)
            VALUES ($1, $2, $3, $4)
        `, point.Metric, point.Value, tagsJSON, point.Timestamp)
    }
    tx.Commit()
}
```

## 三、告警系统

### 3.1 智能告警

```javascript
// 智能告警引擎
class SmartAlertEngine {
  constructor() {
    this.baselines = new Map();
    this.thresholds = {
      fcp: { warning: 1.8, critical: 3.0 },
      lcp: { warning: 2.5, critical: 4.0 },
      fid: { warning: 100, critical: 300 },
      cls: { warning: 0.1, critical: 0.25 },
    };
  }
  
  // 计算基线
  calculateBaseline(metricName, value) {
    const key = `${metricName}:${this.getCurrentPage()}`;
    const history = this.baselines.get(key) || [];
    history.push(value);
    
    // 保留最近100个样本
    if (history.length > 100) {
      history.shift();
    }
    
    this.baselines.set(key, history);
    
    // 计算统计
    return this.computeStatistics(history);
  }
  
  // 计算统计量
  computeStatistics(values) {
    const sorted = [...values].sort((a, b) => a - b);
    const mean = sorted.reduce((a, b) => a + b, 0) / sorted.length;
    const std = Math.sqrt(
      sorted.reduce((sq, n) => sq + Math.pow(n - mean, 2), 0) / sorted.length
    );
    
    return {
      mean,
      std,
      p50: sorted[Math.floor(sorted.length * 0.5)],
      p75: sorted[Math.floor(sorted.length * 0.75)],
      p90: sorted[Math.floor(sorted.length * 0.9)],
      p99: sorted[Math.floor(sorted.length * 0.99)],
    };
  }
  
  // 判断告警
  checkAlert(metricName, value) {
    const stats = this.calculateBaseline(metricName, value);
    const threshold = this.thresholds[metricName];
    
    // 异常检测: 超过3个标准差
    const isAnomaly = Math.abs(value - stats.mean) > 3 * stats.std;
    
    // 阈值告警
    let severity = null;
    if (value > threshold.critical) {
      severity = 'critical';
    } else if (value > threshold.warning) {
      severity = 'warning';
    }
    
    return {
      metric: metricName,
      value,
      baseline: stats,
      anomaly: isAnomaly,
      severity,
      timestamp: Date.now(),
    };
  }
}
```

### 3.2 告警通知

```go
// 告警通知服务
type AlertNotifier struct {
    channels map[string]NotificationChannel
    router   *AlertRouter
}

// 通知渠道
type NotificationChannel interface {
    Send(alert *Alert) error
}

// 多渠道通知
func (n *AlertNotifier) Notify(alert *Alert) error {
    // 1. 去重
    if n.router.IsDuplicate(alert) {
        return nil
    }
    
    // 2. 路由
    targets := n.router.Route(alert)
    
    // 3. 并行发送
    var wg sync.WaitGroup
    errors := make([]error, len(targets))
    
    for i, target := range targets {
        wg.Add(1)
        go func(idx int, t string) {
            defer wg.Done()
            channel := n.channels[t]
            errors[idx] = channel.Send(alert)
        }(i, target)
    }
    
    wg.Wait()
    
    // 4. 汇总结果
    var lastErr error
    for _, err := range errors {
        if err != nil {
            lastErr = err
        }
    }
    
    return lastErr
}
```

## 四、性能优化

### 4.1 Code Splitting

```javascript
// 动态导入
const Dashboard = React.lazy(() => import('./pages/Dashboard'));
const Analytics = React.lazy(() => import('./pages/Analytics'));
const Settings = React.lazy(() => import('./pages/Settings'));

// 路由配置
const routes = [
  {
    path: '/dashboard',
    component: Dashboard,
    lazy: true,
    chunkName: 'dashboard',
  },
  {
    path: '/analytics',
    component: Analytics,
    lazy: true,
    chunkName: 'analytics',
  },
];

// 懒加载组件
function LazyRoute({ component: Component, ...rest }) {
  return (
    <Route
      {...rest}
      element={
        <Suspense fallback={<LoadingSpinner />}>
          <Component />
        </Suspense>
      }
    />
  );
}
```

### 4.2 图片优化

```javascript
// 响应式图片
function ResponsiveImage({ src, alt, sizes }) {
  return (
    <picture>
      <source srcSet={src.webp} type="image/webp" />
      <source srcSet={src.avif} type="image/avif" />
      <img
        src={src.jpg}
        alt={alt}
        sizes={sizes}
        loading="lazy"
        decoding="async"
      />
    </picture>
  );
}

// 图片预加载
function preloadImage(src) {
  const link = document.createElement('link');
  link.rel = 'preload';
  link.as = 'image';
  link.href = src;
  document.head.appendChild(link);
}

// 关键图片预加载
function preloadCriticalImages(images) {
  images.slice(0, 3).forEach(img => preloadImage(img.src));
}
```

## 五、面试高频题

### Q1: 如何优化FCP？

```
A:
1. 减少关键渲染路径
2. 预加载关键资源
3. 内联关键CSS
4. 优化字体加载
```

### Q2: CLS过高的原因？

```
A:
1. 图片没有尺寸
2. 动态内容插入
3. Web字体加载
4. 广告位预留
```

## 六、自测题

1. 解释Core Web Vitals各指标
2. 如何实现实时性能监控？
3. 智能告警如何工作？

---

## 参考文档

- [前端性能优化](./frontend-perf-optimization-deep.md)
- [React性能优化](../agent-ai/react-performance-deep.md)
- [监控体系设计](../devops/monitoring-stack-deep.md)
