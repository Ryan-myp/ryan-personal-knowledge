# Go 后端开发最佳实践

> Go 后端开发最佳实践：代码规范、错误处理、并发模式、性能优化、测试策略。

---

## 1. 项目结构

```
cmd/
  app/
    main.go
internal/
  handler/
  service/
  repository/
  middleware/
pkg/
  cache/
  logger/
  metrics/
web/
  router.go
  middleware.go
config/
  config.yaml
test/
  fixtures/
```

---

## 2. 错误处理

```go
// ❌ 不推荐
func getUser(id string) (User, error) {
    // ...
    if err != nil {
        return User{}, err
    }
    return user, nil
}

// ✅ 推荐
func getUser(id string) (*User, error) {
    user, err := db.QueryRow("SELECT * FROM users WHERE id = ?", id).Scan()
    if err != nil {
        if errors.Is(err, sql.ErrNoRows) {
            return nil, fmt.Errorf("user not found: %w", err)
        }
        return nil, fmt.Errorf("query user: %w", err)
    }
    return user, nil
}
```

---

## 3. 并发模式

```go
// Worker Pool
func workerPool(ctx context.Context, jobs <-chan Job, results chan<- Result, workers int) {
    var wg sync.WaitGroup
    for i := 0; i < workers; i++ {
        wg.Add(1)
        go func() {
            defer wg.Done()
            for job := range jobs {
                results <- process(job)
            }
        }()
    }
    wg.Wait()
    close(results)
}
```

---

## 4. 性能优化

```go
// 使用 sync.Pool 复用对象
var bufferPool = sync.Pool{
    New: func() interface{} {
        return make([]byte, 0, 1024)
    },
}

func processData() {
    buf := bufferPool.Get().([]byte)
    defer bufferPool.Put(buf)
    // ...
}
```

---

## 5. 测试策略

```go
func TestGetUser(t *testing.T) {
    // 表驱动测试
    tests := []struct {
        name string
        id   string
        want bool
    }{
        {"valid_id", "123", true},
        {"invalid_id", "", false},
    }
    
    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            got, err := getUser(tt.id)
            if (err == nil) != tt.want {
                t.Errorf("getUser(%v) error = %v, wantErr %v", tt.id, err, tt.want)
            }
        })
    }
}
```

---

## 6. 实践 Checklist
- [ ] 使用结构化日志
- [ ] 实现优雅关闭
- [ ] 添加健康检查端点
- [ ] 配置合理超时
- [ ] 编写单元测试
- [ ] 添加性能基准测试

**参考**: Effective Go、Go 设计模式、公司编码规范
