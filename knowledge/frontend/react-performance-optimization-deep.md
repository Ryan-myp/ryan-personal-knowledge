# React 性能优化深度实现 - 源码级解析

> **版本**: v2.0  
> **日期**: 2026-08-13  
> **作者**: Ryan  
> **分类**: 前端/React  
> **代码密度**: 35%

---

## 一、React 渲染机制

### 1.1 Fiber 架构

```typescript
// fiber 节点结构
interface FiberNode {
  tag: WorkTag;           // 节点类型
  key: null | string;
  elementType: any;       // 组件类型
  pendingProps: any;      // 新 props
  memoizedProps: any;     // 旧 props
  memoizedState: any;     // 旧 state
  dependencies: DependencyList | null;
  
  // 链接
  child: FiberNode | null;
  sibling: FiberNode | null;
  return: FiberNode | null;
  
  // 效果
  effectTag: SideEffect;
  nextEffect: FiberNode | null;
  
  // 时间
  baseDuration: number;
  lastUpdateTime: number;
  nextRenderTime: number;
}
```

### 1.2 调度优先级

```typescript
// Scheduler 优先级常量
const ImmediatePriority    = 0;  // 紧急 (input)
const UserBlockingPriority = 1;  // 用户阻塞 (click)
const NormalPriority       = 2;  // 普通 (render)
const LowPriority          = 3;  // 低 (animation)
const IdlePriority         = 4;  // 空闲 (预加载)

// useTransition 实现原理
function useTransition() {
  const [isPending, startTransition] = useState(false);
  
  const transition = useCallback((callback) => {
    startTransition(true);
    requestTransition(() => {
      callback();
      startTransition(false);
    });
  }, []);
  
  return [isPending, transition] as const;
}

// requestTransition 使用 scheduler
function requestTransition(callback: () => void) {
  scheduler.scheduleCallback(
    NormalPriority,
    callback
  );
}
```

---

## 二、性能优化技术

### 2.1 React.memo + useMemo + useCallback

```typescript
// 性能对比
// ❌ 不优化：每次渲染都重新创建
function ExpensiveComponent({ data }) {
  const processed = data.map(item => expensiveTransform(item)); // 每次都重新计算
  return <div>{processed}</div>;
}

// ✅ 优化：useMemo 缓存计算结果
function OptimizedComponent({ data }) {
  const processed = useMemo(
    () => data.map(item => expensiveTransform(item)),
    [data]  // 依赖项变化时才重新计算
  );
  return <div>{processed}</div>;
}

// ❌ 不优化：每次创建新函数，导致子组件重渲染
function Parent() {
  const handleClick = () => { console.log('clicked'); };
  return <Child onClick={handleClick} />; // 新引用
}

// ✅ 优化：useCallback 稳定引用
function ParentOptimized() {
  const handleClick = useCallback(() => {
    console.log('clicked');
  }, []); // 空依赖，引用稳定
  return <Child onClick={handleClick} />;
}

// ✅ 组合优化：React.memo + useCallback
const Child = React.memo(function Child({ onClick }) {
  return <button onClick={onClick}>Click</button>;
});
```

### 2.2 虚拟列表

```typescript
// VirtualList 实现
interface VirtualListProps {
  items: any[];
  itemHeight: number;
  containerHeight: number;
  renderItem: (item: any, index: number) => React.ReactNode;
}

function VirtualList({ items, itemHeight, containerHeight, renderItem }: VirtualListProps) {
  const [scrollTop, setScrollTop] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);
  
  // 计算可见范围
  const startIndex = Math.max(0, Math.floor(scrollTop / itemHeight) - 10);
  const endIndex = Math.min(
    items.length,
    Math.ceil((scrollTop + containerHeight) / itemHeight) + 10
  );
  
  const visibleItems = items.slice(startIndex, endIndex);
  const offsetTop = startIndex * itemHeight;
  
  const handleScroll = (e: React.UIEvent<HTMLDivElement>) => {
    setScrollTop(e.currentTarget.scrollTop);
  };
  
  return (
    <div 
      ref={containerRef}
      style={{ height: containerHeight, overflow: 'auto' }}
      onScroll={handleScroll}
    >
      <div style={{ height: items.length * itemHeight, position: 'relative' }}>
        {visibleItems.map((item, i) => (
          <div
            key={startIndex + i}
            style={{
              position: 'absolute',
              top: i * itemHeight,
              height: itemHeight,
              width: '100%',
            }}
          >
            {renderItem(item, startIndex + i)}
          </div>
        ))}
      </div>
    </div>
  );
}
```

### 2.3 Code Splitting

```typescript
// 路由级分割
import { lazy, Suspense } from 'react';

const Dashboard = lazy(() => import('./pages/Dashboard'));
const Settings = lazy(() => import('./pages/Settings'));
const Profile = lazy(() => import('./pages/Profile'));

function App() {
  return (
    <Suspense fallback={<LoadingSpinner />}>
      <Routes>
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="/profile" element={<Profile />} />
      </Routes>
    </Suspense>
  );
}

// 组件级分割
const HeavyChart = lazy(() => import('./components/HeavyChart'));

function ReportPage() {
  const [showChart, setShowChart] = useState(false);
  
  return (
    <div>
      <button onClick={() => setShowChart(true)}>Show Chart</button>
      {showChart && (
        <Suspense fallback={<ChartSkeleton />}>
          <HeavyChart data={chartData} />
        </Suspense>
      )}
    </div>
  );
}
```

---

## 三、性能监控

### 3.1 React DevTools Profiler

```typescript
// 手动标记性能边界
import { unstable_startTransition } from 'react';

function ExpensiveUpdate({ data }) {
  // 使用 startTransition 标记非紧急更新
  unstable_startTransition(() => {
    setExpensiveData(processData(data));
  });
  
  return <div>...</div>;
}

// Performance API 监控
function usePerformanceMetrics() {
  useEffect(() => {
    const observer = new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        console.log(`${entry.name}: ${entry.duration}ms`);
      }
    });
    
    observer.observe({ entryTypes: ['measure', 'longtask'] });
    return () => observer.disconnect();
  }, []);
}
```

### 3.2 自定义 Hook 性能追踪

```typescript
function usePerformanceHook(name: string) {
  const startRef = useRef.performance.now();
  
  return {
    mark: () => {
      const end = performance.now();
      console.log(`${name}: ${end - startRef.current}ms`);
    }
  };
}

// 使用
function MyComponent() {
  const perf = usePerformanceHook('MyComponent');
  
  useEffect(() => {
    perf.mark();
  }, []);
  
  return <div>...</div>;
}
```

---

## 四、总结

| 优化技术 | 适用场景 | 效果 |
|---------|---------|------|
| React.memo | 纯展示组件 | 避免不必要的重渲染 |
| useMemo | 昂贵计算 | 缓存计算结果 |
| useCallback | 回调函数传递 | 稳定引用 |
| 虚拟列表 | 大量列表数据 | 只渲染可见区域 |
| Code Splitting | 大型应用 | 减少初始包体积 |
| Suspense | 异步数据 | 优雅加载中状态 |

---

## 五、自测题

1. **React.memo 为什么不保证性能提升？**
   - 仅 shallow compare props，深层变化仍会触发更新

2. **useMemo 和 useCallback 的区别？**
   - useMemo 缓存值，useCallback 缓存函数引用

3. **虚拟列表如何实现跳过渲染？**
   - 通过绝对定位 + 只渲染可见区间

