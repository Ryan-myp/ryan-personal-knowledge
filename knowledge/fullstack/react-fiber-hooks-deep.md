# React 前端深度：Fiber 架构 + Hooks 源码

> 逐行分析 React 16+ Fiber 架构、Hooks 链表机制、虚拟 DOM Diff 算法

---

## 第一部分：Fiber 架构源码深度

### 为什么 React 需要 Fiber？

```
React 15 的渲染模型（Stack Reconciler）：
1. 递归遍历组件树 → 构建虚拟 DOM
2. 递归 diff → 找出变更
3. 批量更新真实 DOM
问题：
- 递归调用栈，无法暂停/恢复
- 长时间渲染 → 浏览器主线程阻塞 → UI 卡顿
- 无法优先级调度（高优先级中断不了低优先级）

React 16+ Fiber（Fiber Reconciler）：
1. 将组件树拆分成 Fiber 节点（链表结构）
2. 使用链表替代递归 → 可暂停/恢复
3. 使用 time slicing → 分片渲染，不阻塞主线程
4. 使用优先级调度 → 高优先级可中断低优先级
```

### Fiber 节点结构

```javascript
// Fiber 节点（简化版）
const FiberNode = function(
  tag,           // 节点类型：FunctionComponent/ClassComponent/HostComponent/HostText
  key,           // 唯一标识
  elementType,   // 组件类型（函数/类/原生标签名）
  type,          // 组件渲染结果
  pendingProps,  // 传入的 props
  memoProps,     // 上一次的 props（用于 Diff）
  child,         // 第一个子 Fiber
  sibling,       // 下一个兄弟 Fiber
  return,        // 父 Fiber
  stateNode,     // 真实 DOM 或组件实例
  mode,          // 渲染模式：Sync/Blocking/Strict
  flags,         // 副作用标记：Placement/Update/Deletion
  subtreeFlags,  // 子树副作用标记
  deletions,     // 需要删除的子 Fiber 列表
  nextEffect,    // 下一个有副作用的 Fiber
) {}

// Fiber 树 vs 链表结构：
//          Fiber A
//       /    |    \
//     FiberB FiberC FiberD
//     /   \
//   FiberE FiberF

// 实际存储（链表）：
// A.child = B, A.sibling = C, A.sibling = D
// B.child = E, B.sibling = F
// C.child = null, C.sibling = D
// D.child = null, D.sibling = null
// E.sibling = F
// E.child = null, E.sibling = null
// F.sibling = null
// F.child = null
```

### 源码逐行解析：createWorkInProgress

```javascript
// React 源码：ReactFiber.js - createWorkInProgress
// 复用旧的 Fiber 节点或创建新的

export function createWorkInProgress(
  current: Fiber | null,
  pendingProps: any,
  memoizedProps?: any,
  memoizedState?: any,
): Fiber {
  let workInProgress: Fiber = current?.alternate ?? createFiber(
    currentTag,
    pendingProps,
    key,
    null,
  );
  
  // 1. 复用现有 Fiber（避免 GC）
  workInProgress.type = current?.type;
  workInProgress.key = current?.key;
  
  // 2. 复制 props
  workInProgress.pendingProps = pendingProps;
  workInProgress.memoizedProps = memoizedProps ?? current?.memoizedProps;
  workInProgress.memoizedState = memoizedState ?? current?.memoizedState;
  
  // 3. 复用子节点和副作用
  workInProgress.child = current?.child;
  workInProgress.sibling = current?.sibling;
  workInProgress.flags = current?.flags ?? NoFlags;
  workInProgress.subtreeFlags = NoFlags;
  workInProgress.deletions = null;
  workInProgress.nextEffect = null;
  
  // 4. 复制 stateNode（组件实例或 DOM 引用）
  workInProgress.stateNode = current?.stateNode;
  
  // 5. 复制 Hooks 链表
  if (current?.memorizedState !== null) {
    workInProgress.memorizedState = current?.memorizedState;
  }
  
  return workInProgress;
}

// createFiber — 创建新的 Fiber 节点
function createFiber(
  tag: WorkTag,
  pendingProps: any,
  key: null | string,
  mode: TypeOfMode,
): Fiber {
  // 使用双缓冲：workInProgress 和 current 交替使用
  // 避免了重复创建对象，减少 GC 压力
  return new FiberNode(tag, key, pendingProps, mode);
}
```

**关键点**：
- **Alternate 模式**：每个 Fiber 都有 `alternate` 指针指向自己的副本
- **复用优先**：优先复用旧 Fiber，减少内存分配和 GC
- **双缓冲**：`current`（已提交）和 `workInProgress`（构建中）交替

---

### 协调阶段源码：reconcileChildFibers

```javascript
// React 源码：ReactChildFiber.js - reconcileChildFibers
// 协调子节点（Diff 算法核心）

function reconcileChildFibers(
  returnFiber: Fiber,
  currentFirstChild: Fiber | null,
  newChild: any,
): Fiber | null {
  
  // 1. 处理单一子节点
  if (typeof newChild === 'string' || typeof newChild === 'number') {
    // 文本节点
    return reconcileSingleTextNode(
      returnFiber,
      currentFirstChild,
      newChild,
    );
  }
  
  // 2. 处理 React Element
  if (typeof newChild === 'object' && newChild !== null) {
    switch (newChild.$$typeof) {
      case REACT_ELEMENT_TYPE:
        return reconcileSingleElement(
          returnFiber,
          currentFirstChild,
          newChild,
        );
    }
  }
  
  // 3. 处理数组/迭代器
  if (Array.isArray(newChild) || getIteratorFn(newChild)) {
    return reconcileChildrenArray(
      returnFiber,
      currentFirstChild,
      newChild,
    );
  }
  
  return null;
}

// reconcileSingleElement — 协调单个 Element
function reconcileSingleElement(
  returnFiber: Fiber,
  currentFirstChild: Fiber | null,
  element: ReactElement,
): Fiber {
  const key = element.key;
  
  // 1. 查找是否有相同的 current fiber
  let current = currentFirstChild;
  while (current !== null) {
    if (current.key === key) {
      // 2. 检查类型是否相同
      if (current.elementType === element.type) {
        // 类型相同 → 复用 Fiber（Update 标记）
        const existing = useFiber(current, element.props);
        existing.return = returnFiber;
        return existing;
      } else {
        // 类型不同 → 删除旧的，创建新的
        deleteRemainingChildren(returnFiber, current);
        break;
      }
    }
    current = current.sibling;
  }
  
  // 3. 创建新的 Fiber
  const created = createFiber(
    element.type,
    element.props,
    element.key,
    returnFiber.mode,
  );
  created.return = returnFiber;
  
  return created;
}
```

**关键点**：
- **key 匹配**：通过 key 找到对应的 current fiber
- **类型比较**：类型相同复用 fiber（Update 标记），不同则新建（Placement）
- **删除标记**：类型不同 → `deleteRemainingChildren` 标记删除

---

### 协调阶段：reconcileChildrenArray

```javascript
// 协调子节点数组 — Diff 算法核心

function reconcileChildrenArray(
  returnFiber: Fiber,
  currentFirstChild: Fiber | null,
  newChildren: Array<*>,
): Fiber | null {
  let resultingFirstSibling: Fiber | null = null;
  let previousNewFiber: Fiber | null = null;
  let oldFiber = currentFirstChild;
  let newIdx = 0;
  let lastPlacedIndex = 0;
  
  // 1. 双向遍历（优化常见场景）
  while (oldFiber !== null && newIdx < newChildren.length) {
    const newFiber = updateSlot(
      returnFiber,
      oldFiber,
      newChildren[newIdx],
    );
    
    if (newFiber === null) {
      break; // key 不匹配，停止
    }
    
    // 记录最后一个插入的位置（用于移动操作）
    lastPlacedIndex = placeChild(newFiber, lastPlacedIndex);
    
    if (previousNewFiber === null) {
      resultingFirstSibling = newFiber;
    } else {
      previousNewFiber.sibling = newFiber;
    }
    previousNewFiber = newFiber;
    
    oldFiber = oldFiber.sibling;
    newIdx++;
  }
  
  // 2. 删除多余的 old fiber
  if (newIdx === newChildren.length) {
    deleteRemainingChildren(returnFiber, oldFiber);
    return resultingFirstSibling;
  }
  
  // 3. 处理新增的节点（用 key 查找）
  const existingChildren = mapRemainingChildren(returnFiber, oldFiber);
  
  while (newIdx < newChildren.length) {
    const newFiber = createChild(returnFiber, newChildren[newIdx], existingChildren);
    if (newFiber === null) {
      continue;
    }
    
    lastPlacedIndex = placeChild(newFiber, lastPlacedIndex);
    
    if (previousNewFiber === null) {
      resultingFirstSibling = newFiber;
    } else {
      previousNewFiber.sibling = newFiber;
    }
    previousNewFiber = newFiber;
    
    newIdx++;
  }
  
  return resultingFirstSibling;
}
```

**关键点**：
- **双向遍历**：从左到右比较，减少不必要的 DOM 操作
- **placeChild**：记录插入位置，判断是否需要移动（`layoutEffect`）
- **mapRemainingChildren**：用 key 建立查找表，优化新增节点

---

## 第二部分：Hooks 源码深度

### Hooks 链表结构

```
Hooks 链表：
Fiber StateNode:
┌─────────────────────────────────────────────────┐
│ memorizedState = Hook → Hook → Hook → null      │
├─────────────────────────────────────────────────┤
│ Hook 1: useState (count)                        │
│   .queue = { pending: null }                    │
│   .next = Hook 2                                │
├─────────────────────────────────────────────────┤
│ Hook 2: useEffect (callback)                    │
│   .lastEffect = { create: fn, destroy: fn }     │
│   .next = Hook 3                                │
├─────────────────────────────────────────────────┤
│ Hook 3: useMemo (value)                         │
│   .memoizedState = [value, deps]               │
│   .next = null                                  │
└─────────────────────────────────────────────────┘

Hooks 规则：
1. 只在最顶层调用（不在循环/条件/嵌套函数中）
2. 调用顺序必须一致
3. 依赖链表顺序 → 调用顺序固定
```

### useState 源码逐行解析

```javascript
// React 源码：ReactHooks.js - useState
export function useState<S>(
  initialState: (() => S) | S,
): [S, Dispatch<Action<S>>] {
  // 1. 获取当前 fiber 和 dispatcher
  const current = resolveCurrentlyRenderingFiber();
  const dispatcher = resolveDispatcher();
  
  // 2. 创建 hook
  const hook = mountOrUpdateHook();
  
  // 3. 挂载阶段 vs 更新阶段
  const isMount = current.memoizedState === null;
  
  if (isMount) {
    // 挂载阶段：初始化 state
    let initialState_ = typeof initialState === 'function'
      ? (initialState: Function)()
      : initialState;
    // eslint-disable-next-line no-unsafe-optional-chaining
    hook.memoizedState = hook.baseState = initialState_: S;
    
    // 创建 updater
    const queue = hook.queue = {
      pending: null,
      dispatch: null,
      lastRenderedReducer: basicStateReducer,
      lastRenderedState: initialState_,
    };
    
    // 创建 dispatch
    const dispatch: Dispatch<
      Action<S>,
    > = (queue.dispatch = (dispatchSetState.bind(
      null,
      currentlyRenderingFiber,
      queue,
    ): any));
    
    return [hook.memoizedState, dispatch];
  }
  
  // 更新阶段：处理 pending state
  const queue = current.memoizedState.queue;
  const pending = queue.pending;
  
  if (pending !== null) {
    // 1. 处理 pending 队列
    let newBaseState = current.memoizedState;
    let newBasePriority = current.updateQueue.basePriority;
    
    let updatedQueue = pending.next;
    do {
      const update = updatedQueue;
      const action = update.action;
      
      newBaseState = queue.lastRenderedReducer(
        newBaseState,
        action,
      );
      
      updatedQueue = updatedQueue.next;
    } while (updatedQueue !== pending);
    
    // 2. 更新 state
    current.memoizedState = newBaseState;
    queue.pending = null;
  }
  
  return [current.memoizedState, queue.dispatch];
}

// basicStateReducer — 基础 reducer
function basicStateReducer<S>(
  state: S,
  action: Action<S>,
): S {
  return typeof action === 'function' ? action(state) : action;
}
```

**关键点**：
- **mountOrUpdateHook**：根据当前阶段返回 mountState 或 updateState
- **queue.pending**：state 变更队列（支持批量更新）
- **basicStateReducer**：支持函数式更新 `setState(prev => prev + 1)`

---

### useEffect 源码逐行解析

```javascript
// React 源码：ReactHooks.js - useEffect
export function useEffect(
  create: () => (() => void) | void,
  deps: Array<mixed> | void | null,
): void {
  const current = resolveCurrentlyRenderingFiber();
  
  // 1. 创建 hook
  const hook = mountOrUpdateHook();
  
  // 2. 创建 effect 对象
  const effect: Effect = {
    tag: HookEffect,
    create,
    destroy, // 由 create 返回
    deps,    // 依赖数组
    next: null,
  };
  
  // 3. 挂载阶段：直接挂载 effect
  if (current.memoizedState === null) {
    effect.tag = HookHasEffect; // 标记为需要执行
    currentlyRenderingFiber.flags |= Passive;
    hook.memoizedState = pushEffect(HookHasEffect, create, destroy, deps);
  } else {
    // 更新阶段：比较依赖
    const existing = hook.memoizedState;
    
    if (areHookDepsEqual(deps, existing.deps)) {
      // 依赖没变 → 跳过
      hook.memoizedState = pushEffect(
        HookUpdate,
        create,
        destroy,
        deps,
      );
    } else {
      // 依赖变了 → 标记为需要执行
      hook.memoizedState = pushEffect(
        HookHasEffect,
        create,
        destroy,
        deps,
      );
      currentlyRenderingFiber.flags |= Passive;
    }
  }
}

// areHookDepsEqual — 深度比较依赖
function areHookDepsEqual(
  prevDeps: any[],
  nextDeps: any[],
): boolean {
  if (prevDeps === null) {
    return false;
  }
  
  // 浅比较（React 只做了浅比较）
  for (let i = 0; i < prevDeps.length && i < nextDeps.length; i++) {
    if (Object.is(prevDeps[i], nextDeps[i])) {
      continue;
    }
    return false;
  }
  
  return true;
}
```

**关键点**：
- **Passive 标记**：useEffect 在 commit 阶段后异步执行
- **依赖比较**：Object.is 浅比较
- **cleanup 函数**：上一个 effect 的 destroy 会在下一个 effect 前执行

---

### useMemo 源码逐行解析

```javascript
// React 源码：ReactHooks.js - useMemo
export function useMemo<T>(
  nextCreate: () => T,
  deps: Array<mixed> | void | null,
): T {
  const current = resolveCurrentlyRenderingFiber();
  
  // 1. 创建 hook
  const hook = mountOrUpdateHook();
  
  // 2. 挂载阶段：立即计算
  const isMount = current.memoizedState === null;
  
  if (isMount) {
    const nextValue = nextCreate();
    hook.memoizedState = [nextValue, deps];
    return nextValue;
  }
  
  // 3. 更新阶段：比较依赖
  const prevState = hook.memoizedState;
  if (prevState !== null) {
    if (areHookDepsEqual(deps, prevState[1])) {
      // 依赖没变 → 返回缓存值
      return prevState[0];
    }
  }
  
  // 4. 依赖变了 → 重新计算
  const nextValue = nextCreate();
  hook.memoizedState = [nextValue, deps];
  return nextValue;
}
```

**关键点**：
- **缓存值**：`memoizedState = [value, deps]`
- **依赖比较**：Object.is 浅比较
- **惰性求值**：依赖没变时不重新执行 `nextCreate()`

---

## 第三部分：状态管理深度

### Redux vs Zustand vs Jotai 对比

```
Redux：
┌─────────────────────────────────────────────────┐
│  Action → Reducer → New State → UI 更新          │
│                                                   │
│  优点：                                            │
│  - 状态变更可追踪（Time Travel Debugging）        │
│  - 中间件生态丰富（Thunk/Saga/Logger）            │
│  - 适合大型复杂状态                                │
│  - DevTools 调试体验好                            │
│                                                   │
│  缺点：                                            │
│  - 样板代码多（Action/Reducer/Selector）          │
│  - 过度设计（简单场景没必要）                      │
│  - 更新时整棵树 re-render（需要 memo）            │
└─────────────────────────────────────────────────┘

Zustand：
┌─────────────────────────────────────────────────┐
│  Store（无 Provider）→ Selector → UI 更新        │
│                                                   │
│  优点：                                            │
│  - 极简 API（无 Provider/无样板代码）             │
│  - 细粒度更新（Selector 精确订阅）                │
│  - 支持 Middlewares                              │
│  - TS 友好                                        │
│                                                   │
│  缺点：                                            │
│  - 无 DevTools（需插件）                          │
│  - 适合中小规模状态                                │
└─────────────────────────────────────────────────┘

Jotai：
┌─────────────────────────────────────────────────┐
│  Atom（原子状态）→ Derived Atom → UI 更新        │
│                                                   │
│  优点：                                            │
│  - 原子化状态管理（类似 Signals）                  │
│  - 自动依赖追踪                                    │
│  - 支持异步/副作用                                │
│  - 极简                                             │
│                                                   │
│  缺点：                                            │
│  - 生态较小                                        │
│  - 概念学习成本                                    │
└─────────────────────────────────────────────────┘
```

### Zustand 源码深度

```javascript
// Zustand 核心： createStore.ts - create
function create<TState, StateSlice> (
  initializer: StateCreator<TState>,
  ...args: Middleware[]
): UseBoundStore<TState> {
  
  // 1. 创建内部 state
  let state: TState;
  const setState: SetState<TState> = (partial, replace) => {
    const nextState = typeof partial === 'function'
      ? (partial as Function)(state)
      : partial;
    
    // 2. 合并 state
    const nextStateToChange = replace
      ? nextState as TState
      : Object.assign({}, state, nextState as Partial<TState>);
    
    // 3. 通知订阅者（精确匹配）
    const stateChanged = state !== nextStateToChange;
    if (stateChanged) {
      state = nextStateToChange;
      for (const listener of listeners) {
        listener(state, stateChanged);
      }
    }
  };
  
  // 4. 初始化 state
  state = initializer(setState, (selector) => selector(state), getStore());
  
  // 5. 返回 store
  const api = { getState, setState, subscribe, destroy };
  const store = createHook(api, equalityFn) as UseStore<TState>;
  
  return store;
}

// 订阅机制（精确更新）
function createHook<T> (
  api: StoreApi<T>,
  equalityFn: EqualityFn<T>,
): UseStore<T> {
  let currentSnapshot: T;
  let lastEqualityFn: EqualityFn<T> = defaultEqualityFn;
  
  return function useStore(selector, equalityFn?) {
    // 1. 选择器选择需要的状态切片
    const slice = selector(api.getState());
    
    // 2. 检查是否变化（默认 Object.is）
    const sliceChanged = !equalityFn(slice, currentSnapshot);
    
    // 3. 变化时 re-render，否则跳过
    if (sliceChanged) {
      currentSnapshot = slice;
      rerender(); // 触发 React re-render
    }
    
    return slice;
  };
}
```

**关键点**：
- **精确订阅**：只有选中值变化才触发 re-render
- **无 Provider**：直接在组件中 `useStore(state => state.count)`
- **Middleware 扩展**：devtools、persist、immer 等

---

## 第四部分：SSR/SSG 深度

### Next.js 渲染模式

```
Next.js 渲染策略：
┌─────────────────────────────────────────────────┐
│ 1. SSR（Server-Side Rendering）                  │
│    - 每次请求在服务端渲染 HTML                    │
│    - getServerSideProps                         │
│    - SEO 友好，首屏快                           │
│    - 缺点：每次请求都渲染，延迟较高               │
│                                                 │
│ 2. SSG（Static Site Generation）                 │
│    - 构建时生成静态 HTML                        │
│    - getStaticProps                            │
│    - 最快（CDN 分发）                            │
│    - 缺点：数据不是最新的                       │
│                                                 │
│ 3. ISR（Incremental Static Regeneration）        │
│    - 静态页面 + 后台增量更新                     │
│    - revalidate: 60（60 秒后重新生成）           │
│    - 兼顾速度和新鲜度                           │
│                                                 │
│ 4. CSR（Client-Side Rendering）                  │
│    - 传统 React 单页应用                        │
│    - useEffect 获取数据                         │
│    - 优点：体验流畅                               │
│    - 缺点：SEO 差，首屏慢                       │
└─────────────────────────────────────────────────┘
```

### getServerSideProps 源码深度

```javascript
// Next.js 源码简化版： getServerSideProps
export async function getServerSideProps(context) {
  const { req, res, query, params } = context;
  
  // 1. 在服务端获取数据
  const data = await fetchDataFromAPI(req);
  
  // 2. 将数据注入 props
  return {
    props: {
      campaignData: data.campaigns,
      metrics: data.metrics,
    },
  };
}

// Next.js 内部执行流程：
// 1. 收到请求 → 触发 getServerSideProps
// 2. 服务端执行异步函数 → 获取数据
// 3. 渲染 React 组件 → 生成 HTML
// 4. 发送 HTML 到浏览器 → 客户端 hydration
// 5. 浏览器加载 JS bundle → 绑定事件

// 关键：hydration
// 服务端渲染的 DOM 结构必须与客户端期望的一致
// 否则 React 会重新渲染（浪费性能）
```

### ISR（增量静态再生成）源码

```javascript
// ISR 配置：
export async function getStaticProps() {
  const data = await fetchCampaignData();
  
  return {
    props: { campaigns: data },
    revalidate: 60,  // 60 秒后后台重新生成
  };
}

// ISR 内部机制：
// 1. 首次请求：生成静态 HTML，写入 .next/cache/
// 2. 后续请求：返回缓存的 HTML（零延迟）
// 3. 60 秒后：后台重新调用 getStaticProps
// 4. 新 HTML 生成后，替换旧的缓存
// 5. 下一个请求返回新 HTML
```

---

## 第五部分：性能优化深度

### React.memo + useMemo + useCallback 对比

```javascript
// React.memo：组件级别 memo
const ExpensiveComponent = React.memo(function ExpensiveComponent({ data }) {
  return <div>{compute(data)}</div>;
}, function areEqual(prevProps, nextProps) {
  // 自定义比较函数
  return prevProps.data.id === nextProps.data.id;
});

// useMemo：值级别 memo
const memoizedValue = useMemo(() => {
  return computeExpensiveValue(props.a, props.b);
}, [props.a, props.b]); // 依赖变化时才重新计算

// useCallback：函数级别 memo
const memoizedCallback = useCallback(() => {
  doSomething(props.a, props.b);
}, [props.a, props.b]); // 依赖变化时才重新创建函数

// 三者关系：
// React.memo = useMemo(组件) + areEqual
// useMemo = useCallback(值)
// useCallback = useMemo(() => fn, deps)
```

### 虚拟列表（虚拟滚动）源码

```javascript
// 虚拟列表：只渲染可见区域的 DOM 节点
function VirtualList({
  items,           // 总数据
  itemHeight = 50, // 每项高度
  containerHeight = 600, // 容器高度
  overscan = 5,    // 预渲染额外项数
}) {
  const [scrollTop, setScrollTop] = useState(0);
  const totalItems = items.length;
  const totalHeight = totalItems * itemHeight;
  
  // 1. 计算可见范围
  const startIndex = Math.max(0, Math.floor(scrollTop / itemHeight) - overscan);
  const endIndex = Math.min(
    totalItems,
    Math.ceil((scrollTop + containerHeight) / itemHeight) + overscan
  );
  
  // 2. 渲染可见区域
  const visibleItems = items.slice(startIndex, endIndex);
  const offset = startIndex * itemHeight;
  
  return (
    <div
      style={{ height: totalHeight, position: 'relative' }}
      onScroll={(e) => setScrollTop(e.target.scrollTop)}
    >
      <div style={{ transform: `translateY(${offset}px)` }}>
        {visibleItems.map((item, i) => (
          <div key={item.id} style={{ height: itemHeight }}>
            {item.name}
          </div>
        ))}
      </div>
    </div>
  );
}
```

**关键点**：
- **只渲染可见项**：10000 条数据只渲染 ~20 个 DOM 节点
- **预渲染（overscan）**：滚动时预渲染上下各 5 项，避免白屏
- **transform 定位**：用 translateY 偏移，性能好

---

## 第六部分：自测题

### Q1: Fiber 的 alternate 模式有什么好处？

**A**: 双缓冲模式让 React 可以在构建新树时保留旧树，如果渲染被中断可以恢复。同时避免重复创建对象，减少 GC 压力。

### Q2: useState 的更新是同步还是异步的？

**A**: 
- React 17 及之前：事件处理中是批量更新（异步），原生事件和 setTimeout 中是同步更新
- React 18：全部异步（自动批处理）
- 原因：批量更新减少 re-render 次数，提升性能

### Q3: 为什么不要滥用 useMemo？

**A**:
- useMemo 本身有计算成本（比较依赖、创建闭包）
- 只有在计算成本高或传递给 memo 组件时才值得用
- 简单值直接返回即可，不需要 memo

---

## 第七部分：生产实践

### 1. 性能监控

```javascript
// 性能监控：使用 Performance API
const observer = new PerformanceObserver((list) => {
  for (const entry of list.getEntries()) {
    console.log(`${entry.name}: ${entry.duration}ms`);
    
    // 长任务告警（> 50ms）
    if (entry.duration > 50) {
      alert(`Long Task detected: ${entry.name} took ${entry.duration}ms`);
    }
  }
});

observer.observe({ entryTypes: ['longtask', 'largest-contentful-paint'] });
```

### 2. Code Splitting

```javascript
// React.lazy + Suspense 实现代码分割
const CampaignDashboard = React.lazy(() => import('./CampaignDashboard'));
const AnalyticsPage = React.lazy(() => import('./AnalyticsPage'));

function App() {
  return (
    <Suspense fallback={<LoadingSpinner />}>
      <Routes>
        <Route path="/campaigns" element={<CampaignDashboard />} />
        <Route path="/analytics" element={<AnalyticsPage />} />
      </Routes>
    </Suspense>
  );
}
```

### 3. 状态管理选择

```
选择指南：
- 简单状态（表单、开关）：useState
- 全局小状态（主题、用户信息）：Zustand
- 复杂状态（广告竞价系统）：Redux Toolkit
- 原子化状态（细粒度更新）：Jotai
- 表单状态：React Hook Form
```
