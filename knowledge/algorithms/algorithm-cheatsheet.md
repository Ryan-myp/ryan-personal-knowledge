# 算法速查手册

> 常用算法实现与复杂度分析。

---

## 1. 排序算法

| 算法 | 最好 | 平均 | 最坏 | 空间 | 稳定 |
|------|------|------|------|------|------|
| 快速排序 | O(n log n) | O(n log n) | O(n²) | O(log n) | ❌ |
| 归并排序 | O(n log n) | O(n log n) | O(n log n) | O(n) | ✅ |
| 堆排序 | O(n log n) | O(n log n) | O(n log n) | O(1) | ❌ |
| 冒泡排序 | O(n) | O(n²) | O(n²) | O(1) | ✅ |

---

## 2. 二分查找

```go
func BinarySearch(arr []int, target int) int {
    left, right := 0, len(arr)-1
    for left <= right {
        mid := left + (right-left)/2
        if arr[mid] == target {
            return mid
        } else if arr[mid] < target {
            left = mid + 1
        } else {
            right = mid - 1
        }
    }
    return -1
}
```

---

## 3. 动态规划

```go
// 0/1 背包问题
func knapsack(weights, values []int, capacity int) int {
    n := len(weights)
    dp := make([][]int, n+1)
    for i := range dp {
        dp[i] = make([]int, capacity+1)
    }
    for i := 1; i <= n; i++ {
        for w := 0; w <= capacity; w++ {
            dp[i][w] = dp[i-1][w]
            if w >= weights[i-1] {
                dp[i][w] = max(dp[i][w], dp[i-1][w-weights[i-1]]+values[i-1])
            }
        }
    }
    return dp[n][capacity]
}
```

---

**参考**: CLRS《算法导论》、LeetCode 精选
