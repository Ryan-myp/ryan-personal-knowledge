# 前端性能优化深度实战

## 一、性能优化全景

### 1.1 核心指标

| 指标 | 说明 | 优秀标准 |
|------|------|----------|
| LCP | 最大内容绘制 | <2.5s |
| FID | 首次输入延迟 | <100ms |
| CLS | 累积布局偏移 | <0.1 |
| TTFB | 首字节时间 | <800ms |
| FCP | 首次内容绘制 | <1.8s |

### 1.2 优化策略分层

```
资源层:
├── 代码分割 (Code Splitting)
├── Tree Shaking
├── 压缩 (Gzip/Brotli)
└── CDN 加速

渲染层:
├── SSR/SSG/ISR
├── 虚拟列表
├── 懒加载
└── 防抖节流

缓存层:
├── Service Worker
├── HTTP Cache
├── LocalStorage
└── IndexedDB
```

## 二、代码分割实战

### 2.1 Webpack 配置

```javascript
module.exports = {
  optimization: {
    splitChunks: {
      chunks: 'all',
      cacheGroups: {
        vendors: {
          test: /[\\/]node_modules[\\/]/,
          name: 'vendors',
          priority: 10,
        },
        common: {
          minChunks: 2,
          name: 'common',
          priority: 5,
          reuseExistingChunk: true,
        },
      },
    },
  },
};
```

### 2.2 React 懒加载

```jsx
import { lazy, Suspense } from 'react';

const Dashboard = lazy(() => import('./Dashboard'));
const Settings = lazy(() => import('./Settings'));

function App() {
  return (
    <Suspense fallback={<Loading />}>
      <Routes>
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/settings" element={<Settings />} />
      </Routes>
    </Suspense>
  );
}
```

## 三、自测题

1. Web Vitals 包含哪些指标？
2. 代码分割有什么好处？

## 四、动手验证

```bash
# 1. 配置代码分割
# 2. 实现懒加载
# 3. 添加 Service Worker
# 4. 使用 Lighthouse 测试
```
