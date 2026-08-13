# 前端性能优化 - 资深专家深度实现

## 一、Code Splitting

```javascript
// React.lazy + Suspense
const Chart = React.lazy(() => import('./components/Chart'));
const Dashboard = () => (
  <Suspense fallback={<div>Loading...</div>}>
    <Chart />
  </Suspense>
);

// Webpack dynamic import
const getTheme = () => import(`./themes/${theme}.css`);

// 路由懒加载
const routes = [
  {
    path: '/dashboard',
    component: lazy(() => import('./pages/Dashboard')),
  },
  {
    path: '/analytics', 
    component: lazy(() => import('./pages/Analytics')),
  }
];
```

## 二、虚拟列表

```javascript
import { FixedSizeList as List } from 'react-window';

const Row = ({ index, style }) => (
  <div style={style}>Row {index}</div>
);

const VirtualList = ({ items }) => (
  <List
    height={600}
    itemCount={items.length}
    itemSize={35}
    width={window.innerWidth}
  >
    {Row}
  </List>
);
```

## 三、面试高频题

### Q1: Code Splitting原理？

```
A:
1. 按需加载
2. 减少首屏体积
3. 提升加载速度
```

### Q2: 如何实现虚拟列表？

```
A:
1. 只渲染可视区域
2. 滚动时动态替换
3. 计算偏移量
```

## 四、自测题

1. 解释Code Splitting
2. 如何实现虚拟列表？
3. 如何优化首屏？

---

## 参考文档

- [React代码分割](https://react.dev/reference/react/lazy)
- [react-window文档](https://github.com/bvaughn/react-window)
