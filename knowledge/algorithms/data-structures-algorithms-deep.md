# 数据结构与算法深度解析

> 深入数据结构与算法：链表、树、图、排序、动态规划。
> 源码级分析，包含 LeetCode 经典题目。
> 适用对象：后端工程师、算法工程师、面试准备者

---

## 1. 链表

### 1.1 单向链表

```
单向链表结构：

Node -> Node -> Node -> Node -> nil
  |       |       |       |
  val     val     val     val
  next    next    next    nil
```

### 1.2 Go 实现

```go
// linked_list.go

package datastructure

type ListNode struct {
    Val  int
    Next *ListNode
}

func ReverseList(head *ListNode) *ListNode {
    var prev *ListNode
    curr := head
    for curr != nil {
        next := curr.Next
        curr.Next = prev
        prev = curr
        curr = next
    }
    return prev
}

func MergeTwoLists(l1, l2 *ListNode) *ListNode {
    dummy := &ListNode{}
    tail := dummy
    
    for l1 != nil && l2 != nil {
        if l1.Val < l2.Val {
            tail.Next = l1
            l1 = l1.Next
        } else {
            tail.Next = l2
            l2 = l2.Next
        }
        tail = tail.Next
    }
    
    if l1 != nil {
        tail.Next = l1
    } else {
        tail.Next = l2
    }
    
    return dummy.Next
}
```

---

## 2. 树

### 2.1 二叉搜索树

```
二叉搜索树性质：
├── 左子树所有节点 < 根节点
├── 右子树所有节点 > 根节点
└── 左右子树也是 BST
```

### 2.2 Go 实现

```go
// binary_search_tree.go

package datastructure

type TreeNode struct {
    Val   int
    Left  *TreeNode
    Right *TreeNode
}

func Insert(root *TreeNode, val int) *TreeNode {
    if root == nil {
        return &TreeNode{Val: val}
    }
    if val < root.Val {
        root.Left = Insert(root.Left, val)
    } else {
        root.Right = Insert(root.Right, val)
    }
    return root
}

func Search(root *TreeNode, val int) bool {
    if root == nil {
        return false
    }
    if val == root.Val {
        return true
    } else if val < root.Val {
        return Search(root.Left, val)
    }
    return Search(root.Right, val)
}

func InorderTraversal(root *TreeNode) []int {
    result := []int{}
    var inorder func(*TreeNode)
    inorder = func(node *TreeNode) {
        if node == nil {
            return
        }
        inorder(node.Left)
        result = append(result, node.Val)
        inorder(node.Right)
    }
    inorder(root)
    return result
}
```

### 2.3 AVL 树

```
AVL 树旋转操作：

左旋 (Left Rotate):
    y                               x
   / \                             / \
  x   T3     左旋               y     T3
 / \      ─────────────────►   / \
T1   T2                       T1  T2

右旋 (Right Rotate):
  x                                y
 / \                              / \
T1   y        右旋            x     T3
    / \      ─────────────────► / \
   T2   T3                     T1  T2
```

---

## 3. 图

### 3.1 图的表示

```
图的表示方式：

1. 邻接矩阵
   ├── 空间复杂度 O(V²)
   └── 适合稠密图

2. 邻接表
   ├── 空间复杂度 O(V+E)
   └── 适合稀疏图
```

### 3.2 Go 实现

```go
// graph.go

package datastructure

type Graph struct {
    AdjList map[int][]int
    Vertices int
}

func NewGraph(v int) *Graph {
    return &Graph{
        AdjList: make(map[int][]int),
        Vertices: v,
    }
}

func (g *Graph) AddEdge(u, v int) {
    g.AdjList[u] = append(g.AdjList[u], v)
    g.AdjList[v] = append(g.AdjList[v], u)
}

func (g *Graph) BFS(start int) []int {
    visited := make(map[int]bool)
    queue := []int{start}
    visited[start] = true
    result := []int{}
    
    for len(queue) > 0 {
        node := queue[0]
        queue = queue[1:]
        result = append(result, node)
        
        for _, neighbor := range g.AdjList[node] {
            if !visited[neighbor] {
                visited[neighbor] = true
                queue = append(queue, neighbor)
            }
        }
    }
    
    return result
}

func (g *Graph) DFS(start int) []int {
    visited := make(map[int]bool)
    result := []int{}
    
    var dfs func(int)
    dfs = func(node int) {
        visited[node] = true
        result = append(result, node)
        for _, neighbor := range g.AdjList[node] {
            if !visited[neighbor] {
                dfs(neighbor)
            }
        }
    }
    
    dfs(start)
    return result
}
```

---

## 4. 排序算法

### 4.1 快速排序

```
快速排序流程：

1. 选择基准 (pivot)
2. 分区 (partition)
   ├── 小于基准的放左边
   └── 大于基准的放右边
3. 递归排序左右子数组
```

### 4.2 Go 实现

```go
// quicksort.go

package datastructure

func QuickSort(arr []int) {
    quickSortHelper(arr, 0, len(arr)-1)
}

func quickSortHelper(arr []int, low, high int) {
    if low < high {
        pi := partition(arr, low, high)
        quickSortHelper(arr, low, pi-1)
        quickSortHelper(arr, pi+1, high)
    }
}

func partition(arr []int, low, high int) int {
    pivot := arr[high]
    i := low - 1
    
    for j := low; j < high; j++ {
        if arr[j] <= pivot {
            i++
            arr[i], arr[j] = arr[j], arr[i]
        }
    }
    
    arr[i+1], arr[high] = arr[high], arr[i+1]
    return i + 1
}
```

---

## 5. 动态规划

### 5.1 背包问题

```
0/1 背包问题：

状态定义：dp[i][w] 表示前 i 个物品，容量为 w 时的最大价值

状态转移：
dp[i][w] = max(dp[i-1][w], dp[i-1][w-weight[i]] + value[i])

初始化：
dp[0][w] = 0 (0个物品价值为0)
dp[i][0] = 0 (容量为0价值为0)
```

### 5.2 Go 实现

```go
// knapsack.go

package datastructure

func Knapsack(weights, values []int, capacity int) int {
    n := len(weights)
    dp := make([][]int, n+1)
    for i := range dp {
        dp[i] = make([]int, capacity+1)
    }
    
    for i := 1; i <= n; i++ {
        for w := 0; w <= capacity; w++ {
            // 不选第 i 个物品
            dp[i][w] = dp[i-1][w]
            // 选第 i 个物品（如果容量允许）
            if w >= weights[i-1] {
                val := dp[i-1][w-weights[i-1]] + values[i-1]
                if val > dp[i][w] {
                    dp[i][w] = val
                }
            }
        }
    }
    
    return dp[n][capacity]
}
```

---

## 6. 哈希表

### 6.1 冲突解决

```
哈希冲突解决方法：

1. 链地址法 (Separate Chaining)
   └── 每个桶维护一个链表

2. 开放寻址法 (Open Addressing)
   ├── 线性探测 (Linear Probing)
   ├── 二次探测 (Quadratic Probing)
   └── 双重哈希 (Double Hashing)
```

### 6.2 Go 实现

```go
// hashmap.go

package datastructure

type entry struct {
    key   string
    value interface{}
    next  *entry
}

type HashMap struct {
    buckets []*entry
    size    int
    capacity int
}

func NewHashMap(capacity int) *HashMap {
    return &HashMap{
        buckets: make([]*entry, capacity),
        capacity: capacity,
    }
}

func (hm *HashMap) Hash(key string) int {
    hash := 0
    for i := 0; i < len(key); i++ {
        hash = hash*31 + int(key[i])
    }
    return hash % hm.capacity
}

func (hm *HashMap) Put(key string, value interface{}) {
    index := hm.Hash(key)
    e := hm.buckets[index]
    
    // 查找是否已存在
    for e != nil {
        if e.key == key {
            e.value = value
            return
        }
        if e.next == nil {
            break
        }
        e = e.next
    }
    
    // 插入
    if e == nil {
        hm.buckets[index] = &entry{key: key, value: value}
    } else {
        e.next = &entry{key: key, value: value}
    }
    hm.size++
}

func (hm *HashMap) Get(key string) (interface{}, bool) {
    index := hm.Hash(key)
    e := hm.buckets[index]
    
    for e != nil {
        if e.key == key {
            return e.value, true
        }
        e = e.next
    }
    return nil, false
}
```

---

## 7. 总结

### 7.1 算法复杂度

| 算法 | 最好 | 平均 | 最坏 | 空间 |
|------|------|------|------|------|
| 快速排序 | O(nlogn) | O(nlogn) | O(n²) | O(logn) |
| 归并排序 | O(nlogn) | O(nlogn) | O(nlogn) | O(n) |
| 堆排序 | O(nlogn) | O(nlogn) | O(nlogn) | O(1) |
| 二叉搜索树 | O(logn) | O(logn) | O(n) | O(n) |
| 哈希表 | O(1) | O(1) | O(n) | O(n) |

### 7.2 最佳实践

- [ ] 选择合适的排序算法
- [ ] 理解动态规划状态转移
- [ ] 掌握图的基本遍历
- [ ] 注意哈希冲突处理
- [ ] 进行复杂度分析

---

*最后更新：2026-08-11*
*作者：Ryan*
