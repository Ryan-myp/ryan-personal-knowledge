# 前端性能优化深度实现 - 资深专家

## 一、Code Splitting与懒加载

### 1.1 React.lazy + Suspense

```javascript
import React, { lazy, Suspense } from 'react';

// 定义懒加载组件
const Chart = lazy(() => import('./components/Chart'));
const Dashboard = lazy(() => import('./pages/Dashboard'));
const Analytics = lazy(() => import('./pages/Analytics'));

// 懒加载组件包装器
const LazyComponent = ({ component: Component, ...props }) => (
  <Suspense fallback={<LoadingSpinner />}>
    <Component {...props} />
  </Suspense>
);

// 路由级代码分割
const AppRoutes = () => (
  <Suspense fallback={<div className="skeleton">Loading...</div>}>
    <Routes>
      <Route path="/dashboard" element={<Dashboard />} />
      <Route path="/analytics" element={<Analytics />} />
      <Route path="/chart" element={<LazyComponent component={Chart} />} />
    </Routes>
  </Suspense>
);
```

### 1.2 Webpack Dynamic Import

```javascript
// 动态导入主题
const getTheme = (themeName) => {
  return import(`./themes/${themeName}.css`);
};

// 动态导入模块
const loadModule = async (moduleName) => {
  try {
    const module = await import(`./modules/${moduleName}`);
    return module.default;
  } catch (error) {
    console.error(`Failed to load module ${moduleName}:`, error);
    return null;
  }
};

// 预加载重要模块
const preloadModules = () => {
  // 使用prefetch
  const link = document.createElement('link');
  link.rel = 'prefetch';
  link.href = '/static/js/vendor.chunk.js';
  document.head.appendChild(link);
};
```

### 1.3 Rollup动态导入

```javascript
// rollup.config.js
export default {
  input: 'src/main.js',
  output: {
    dir: 'dist',
    format: 'es',
    chunkFileNames: 'chunks/[name]-[hash].js'
  },
  plugins: [
    // 自动代码分割
    autoSplitChunks({
      chunks: 'all',
      maxAsyncRequests: 30,
      maxInitialRequests: 30,
      cacheGroups: {
        vendors: {
          test: /[\\/]node_modules[\\/]/,
          name: 'vendors',
          chunks: 'all',
          priority: -10
        },
        default: {
          minChunks: 2,
          priority: -20,
          reuseExistingChunk: true
        }
      }
    })
  ]
};
```

## 二、虚拟列表优化

### 2.1 基础实现

```javascript
import React, { useState, useEffect, useRef, useCallback } from 'react';

// 虚拟列表组件
const VirtualList = ({ 
  items, 
  itemHeight = 50, 
  containerHeight = 600,
  overscan = 5,
  renderItem 
}) => {
  const containerRef = useRef(null);
  const [scrollTop, setScrollTop] = useState(0);
  
  // 计算可视范围内的items
  const calculateVisibleItems = useCallback(() => {
    const startIndex = Math.max(0, Math.floor(scrollTop / itemHeight) - overscan);
    const endIndex = Math.min(
      items.length - 1,
      Math.ceil((scrollTop + containerHeight) / itemHeight) + overscan
    );
    
    return {
      startIndex,
      endIndex,
      totalHeight: items.length * itemHeight
    };
  }, [scrollTop, itemHeight, containerHeight, overscan, items.length]);
  
  const { startIndex, endIndex, totalHeight } = calculateVisibleItems();
  
  // 渲染可见items
  const visibleItems = items.slice(startIndex, endIndex + 1);
  
  return (
    <div 
      ref={containerRef}
      style={{ 
        height: containerHeight, 
        overflow: 'auto',
        position: 'relative'
      }}
      onScroll={(e) => setScrollTop(e.currentTarget.scrollTop)}
    >
      <div style={{ height: totalHeight, position: 'relative' }}>
        <div style={{ transform: `translateY(${startIndex * itemHeight}px)` }}>
          {visibleItems.map((item, index) => (
            <div
              key={item.id}
              style={{ height: itemHeight }}
            >
              {renderItem(item, startIndex + index)}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
```

### 2.2 高性能版本（使用requestAnimationFrame）

```javascript
const VirtualListOptimized = ({ items, itemHeight, containerHeight, renderItem }) => {
  const containerRef = useRef(null);
  const [visibleRange, setVisibleRange] = useState({ start: 0, end: 0 });
  const rafId = useRef(null);
  const lastScrollTop = useRef(0);
  
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    
    const handleScroll = () => {
      // 防抖优化：使用requestAnimationFrame
      if (rafId.current) {
        cancelAnimationFrame(rafId.current);
      }
      
      rafId.current = requestAnimationFrame(() => {
        const scrollTop = container.scrollTop;
        
        // 只在scroll位置变化超过itemHeight时更新
        if (Math.abs(scrollTop - lastScrollTop.current) >= itemHeight) {
          const start = Math.floor(scrollTop / itemHeight);
          const end = Math.min(
            items.length - 1,
            Math.ceil((scrollTop + containerHeight) / itemHeight)
          );
          
          setVisibleRange({ start, end });
          lastScrollTop.current = scrollTop;
        }
      });
    };
    
    container.addEventListener('scroll', handleScroll, { passive: true });
    return () => {
      container.removeEventListener('scroll', handleScroll);
      if (rafId.current) {
        cancelAnimationFrame(rafId.current);
      }
    };
  }, [itemHeight, containerHeight, items.length]);
  
  const visibleItems = items.slice(visibleRange.start, visibleRange.end + 1);
  const offsetY = visibleRange.start * itemHeight;
  
  return (
    <div 
      ref={containerRef}
      style={{ height: containerHeight, overflow: 'auto' }}
    >
      <div style={{ height: items.length * itemHeight, position: 'relative' }}>
        <div style={{ transform: `translateY(${offsetY}px)` }}>
          {visibleItems.map((item, index) => (
            <div key={item.id} style={{ height: itemHeight }}>
              {renderItem(item, visibleRange.start + index)}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
```

## 三、Web Worker优化

### 3.1 基础Worker

```javascript
// worker.js
self.onmessage = function(e) {
  const { type, data } = e.data;
  
  switch(type) {
    case 'PROCESS_DATA':
      const result = processData(data);
      self.postMessage({ type: 'RESULT', data: result });
      break;
      
    case 'COMPUTE_HEAVY':
      const computation = heavyComputation(data);
      self.postMessage({ type: 'COMPUTATION_DONE', data: computation });
      break;
      
    default:
      self.postMessage({ type: 'ERROR', message: 'Unknown message type' });
  }
};

function processData(data) {
  // 大量数据处理
  return data.map(item => transformItem(item));
}

function heavyComputation(data) {
  let result = 0;
  for (let i = 0; i < 1000000; i++) {
    result += Math.sqrt(i) * Math.sin(i);
  }
  return result;
}
```

```javascript
// 主线程使用
const worker = new Worker('./worker.js');

worker.postMessage({
  type: 'PROCESS_DATA',
  data: largeDataset
});

worker.onmessage = (e) => {
  const { type, data } = e.data;
  
  if (type === 'RESULT') {
    updateUI(data);
  } else if (type === 'ERROR') {
    handleError(data);
  }
};

worker.terminate(); // 销毁worker
```

### 3.2 Web Worker Pool

```javascript
class WorkerPool {
  constructor(workerPath, size) {
    this.workers = [];
    this.taskQueue = [];
    this.availableWorkers = [];
    
    // 创建worker池
    for (let i = 0; i < size; i++) {
      const worker = new Worker(workerPath);
      this.workers.push(worker);
      this.availableWorkers.push(worker);
      
      worker.onmessage = (e) => {
        this.handleTaskComplete(worker, e.data);
      };
    }
  }
  
  submitTask(task) {
    return new Promise((resolve, reject) => {
      task.resolve = resolve;
      task.reject = reject;
      this.taskQueue.push(task);
      this.processNextTask();
    });
  }
  
  processNextTask() {
    if (this.availableWorkers.length === 0 || this.taskQueue.length === 0) {
      return;
    }
    
    const worker = this.availableWorkers.shift();
    const task = this.taskQueue.shift();
    
    worker.postMessage(task.data);
    
    // 保存task引用到worker
    worker._currentTask = task;
  }
  
  handleTaskComplete(worker, result) {
    const task = worker._currentTask;
    
    task.resolve(result);
    this.availableWorkers.push(worker);
    delete worker._currentTask;
    
    // 处理下一个任务
    this.processNextTask();
  }
  
  destroy() {
    this.workers.forEach(worker => worker.terminate());
    this.workers = [];
    this.availableWorkers = [];
    this.taskQueue = [];
  }
}

// 使用示例
const pool = new WorkerPool('./worker.js', 4);

const promise = pool.submitTask({
  type: 'PROCESS_DATA',
  data: largeDataset
});

promise.then(result => {
  console.log('Result:', result);
});

pool.destroy();
```

## 四、资源优化

### 4.1 图片优化

```javascript
// 响应式图片加载
const OptimizedImage = ({ src, alt, sizes, priority = false }) => {
  return (
    <picture>
      {/* WebP格式 */}
      <source 
        srcSet={`${src}.webp`}
        type="image/webp"
      />
      {/* 传统格式回退 */}
      <source 
        srcSet={`${src}.avif`}
        type="image/avif"
      />
      <img
        src={`${src}.jpg`}
        alt={alt}
        sizes={sizes}
        loading={priority ? 'eager' : 'lazy'}
        decoding="async"
        width={getwidth(sizes)}
        height={getHeight(sizes)}
      />
    </picture>
  );
};

// 图片懒加载
const LazyImage = ({ src, ...props }) => {
  const [isLoaded, setIsLoaded] = useState(false);
  const imgRef = useRef(null);
  
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach(entry => {
          if (entry.isIntersecting) {
            const img = entry.target;
            img.src = img.dataset.src;
            setIsLoaded(true);
            observer.unobserve(img);
          }
        });
      },
      { rootMargin: '50px' }
    );
    
    if (imgRef.current) {
      observer.observe(imgRef.current);
    }
    
    return () => observer.disconnect();
  }, []);
  
  return (
    <div style={{ position: 'relative', paddingTop: '56.25%' }}>
      {!isLoaded && (
        <div className="image-placeholder" style={{ 
          position: 'absolute', 
          top: 0, 
          left: 0, 
          right: 0, 
          bottom: 0,
          backgroundColor: '#f0f0f0'
        }} />
      )}
      <img
        ref={imgRef}
        data-src={src}
        alt={props.alt}
        className={isLoaded ? 'loaded' : 'loading'}
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          width: '100%',
          height: '100%',
          objectFit: 'cover',
          opacity: isLoaded ? 1 : 0,
          transition: 'opacity 0.3s'
        }}
      />
    </div>
  );
};
```

### 4.2 字体优化

```javascript
// 字体预加载
const FontPreloader = ({ fonts }) => {
  useEffect(() => {
    fonts.forEach(font => {
      const link = document.createElement('link');
      link.rel = 'preload';
      link.as = 'font';
      link.type = font.type;
      link.href = font.src;
      link.crossOrigin = 'anonymous';
      document.head.appendChild(link);
    });
  }, [fonts]);
  
  return null;
};

// 使用示例
<FontPreloader 
  fonts={[
    { src: '/fonts/roboto.woff2', type: 'font/woff2' },
    { src: '/fonts/icons.woff2', type: 'font/woff2' }
  ]}
/>
```

## 五、性能监控

### 5.1 Core Web Vitals

```javascript
import { getCLS, getFID, getFCP, getLCP, getTTFB, getTTI } from 'web-vitals';

// 上报性能数据
const reportWebVitals = ({ name, value, id }) => {
  const metric = {
    name,
    value: Math.round(value),
    id,
    timestamp: Date.now()
  };
  
  // 发送到分析平台
  navigator.sendBeacon('/api/performance', JSON.stringify(metric));
};

// 监控指标
getCLS(reportWebVitals);      // Cumulative Layout Shift
getFID(reportWebVitals);      // First Input Delay
getFCP(reportWebVitals);      // First Contentful Paint
getLCP(reportWebVitals);      // Largest Contentful Paint
getTTFB(reportWebVitals);     // Time to First Byte
getTTI(reportWebVitals);      // Time to Interactive
```

### 5.2 自定义性能监控

```javascript
class PerformanceMonitor {
  constructor() {
    this.metrics = {};
    this.startTime = performance.now();
  }
  
  // 标记关键时间点
  mark(name) {
    performance.mark(name);
  }
  
  // 测量两个mark之间的时间
  measure(name, startMark, endMark) {
    performance.measure(name, startMark, endMark);
    const measure = performance.getEntriesByName(name)[0];
    this.metrics[name] = measure.duration;
  }
  
  // 获取Long Tasks
  getLongTasks() {
    return new Promise((resolve) => {
      const observer = new PerformanceObserver((list) => {
        resolve(list.getEntries());
      });
      observer.observe({ entryTypes: ['longtask'] });
    });
  }
  
  // 获取网络性能
  getNetworkPerformance() {
    const entries = performance.getEntriesByType('resource');
    return entries.filter(entry => 
      entry.initiatorType === 'http' || 
      entry.initiatorType === 'navigate'
    );
  }
  
  // 生成性能报告
  generateReport() {
    const navigation = performance.getEntriesByType('navigation')[0];
    
    return {
      domContentLoaded: navigation.domContentLoadedEventEnd - navigation.domContentLoadedEventStart,
      loadComplete: navigation.loadEventEnd - navigation.startTime,
      metrics: this.metrics,
      longTasks: await this.getLongTasks(),
      network: this.getNetworkPerformance()
    };
  }
}
```

## 六、面试高频题

### Q1: Code Splitting的原理是什么？

```
A:
1. 将代码拆分成多个chunk
2. 按需加载，减少首屏体积
3. 利用浏览器并行下载能力
4. 常用方案：React.lazy + dynamic import
```

### Q2: 如何实现虚拟列表？

```
A:
1. 只渲染可视区域的items
2. 使用transform定位
3. 监听scroll事件计算可视范围
4. 优化：requestAnimationFrame + 防抖
```

### Q3: Web Worker适用场景？

```
A:
1. 大量数据处理
2. 复杂计算任务
3. 避免阻塞主线程
4. 实时音视频处理
```

## 七、自测题

1. 解释Core Web Vitals指标
2. 如何实现图片懒加载？
3. Web Worker的最佳实践？
4. 如何监控前端性能？

---

## 参考文档

- [Web Vitals](https://web.dev/vitals/)
- [React.lazy文档](https://react.dev/reference/react/lazy)
- [Web Workers API](https://developer.mozilla.org/en-US/docs/Web/API/Web_Workers_API)
