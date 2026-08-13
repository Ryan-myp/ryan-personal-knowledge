# Go并发模式实战 - 资深专家深度实现

## 一、Worker Pool模式

```go
func worker(id int, jobs <-chan int, results chan<- int) {
    for j := range jobs {
        fmt.Printf("worker %d processing job %d\n", id, j)
        time.Sleep(time.Second)
        results <- j * 2
    }
}

func main() {
    jobs := make(chan int, 100)
    results := make(chan int, 100)
    
    // 启动3个worker
    for w := 1; w <= 3; w++ {
        go worker(w, jobs, results)
    }
    
    // 发送任务
    go func() {
        for j := 1; j <= 9; j++ {
            jobs <- j
        }
        close(jobs)
    }()
    
    // 收集结果
    for a := 1; a <= 9; a++ {
        <-results
    }
}
```

## 二、Pipeline模式

```go
func generator(nums ...int) <-chan int {
    out := make(chan int)
    go func() {
        for _, n := range nums {
            out <- n
        }
        close(out)
    }()
    return out
}

func squarer(in <-chan int) <-chan int {
    out := make(chan int)
    go func() {
        for n := range in {
            out <- n * n
        }
        close(out)
    }()
    return out
}

func main() {
    // 创建pipeline
    nums := generator(1, 2, 3, 4)
    sq := squarer(nums)
    
    for v := range sq {
        fmt.Println(v) // 输出: 1, 4, 9, 16
    }
}
```

## 三、面试高频题

### Q1: Worker Pool适合什么场景？

```
A:
1. 批量任务处理
2. 限制并发数
3. 资源隔离
```

### Q2: Pipeline如何实现？

```
A:
1. 管道串联
2. 无阻塞传递
3. 优雅关闭
```

## 四、自测题

1. 解释Worker Pool
2. 如何实现Pipeline？
3. 如何处理错误传播？

---

## 参考文档

- [Go Concurrency Patterns](https://go.dev/talks/2012/concurrency.slide)
- [Go Blog: Concurrent Programming](https://go.dev/blog/pipelines)
