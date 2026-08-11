# Go 单元测试深度实战

> 深入 Go 测试：表驱动测试、mock、基准测试、覆盖率。
> 包含真实测试策略和最佳实践。
> 适用对象：Go 工程师、测试工程师

---

## 1. 表驱动测试

### 1.1 基础模式

```go
// table_test.go

package math

import "testing"

func TestAdd(t *testing.T) {
    tests := []struct {
        name     string
        a, b     int
        expected int
    }{
        {"positive", 1, 2, 3},
        {"negative", -1, -2, -3},
        {"zero", 0, 0, 0},
        {"mixed", -1, 1, 0},
    }
    
    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            if got := Add(tt.a, tt.b); got != tt.expected {
                t.Errorf("Add(%d, %d) = %d, want %d", tt.a, tt.b, got, tt.expected)
            }
        })
    }
}
```

### 1.2 进阶模式

```go
// table_test.go - 进阶

func TestAddEdgeCases(t *testing.T) {
    tests := []struct {
        name     string
        a, b     int
        expected int
        wantErr  bool
    }{
        {"max_int", math.MaxInt32, 1, 0, true},
        {"min_int", math.MinInt32, -1, 0, true},
        {"overflow", 1000000000, 1000000000, 0, false},
    }
    
    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            got, err := AddSafely(tt.a, tt.b)
            if (err != nil) != tt.wantErr {
                t.Errorf("AddSafely() error = %v, wantErr %v", err, tt.wantErr)
                return
            }
            if !tt.wantErr && got != tt.expected {
                t.Errorf("AddSafely() = %v, want %v", got, tt.expected)
            }
        })
    }
}
```

---

## 2. Mock 测试

### 2.1 Interface Mock

```go
// mock_test.go

package service

import (
    "testing"
    "github.com/stretchr/testify/mock"
)

// 定义接口
type UserRepository interface {
    FindByID(id int) (*User, error)
    Save(user *User) error
}

// Mock 实现
type MockUserRepository struct {
    mock.Mock
}

func (m *MockUserRepository) FindByID(id int) (*User, error) {
    args := m.Called(id)
    return args.Get(0).(*User), args.Error(1)
}

func (m *MockUserRepository) Save(user *User) error {
    args := m.Called(user)
    return args.Error(0)
}

// 测试
func TestUserService_FindUser(t *testing.T) {
    mockRepo := new(MockUserRepository)
    service := NewUserService(mockRepo)
    
    expectedUser := &User{ID: 1, Name: "Alice"}
    mockRepo.On("FindByID", 1).Return(expectedUser, nil)
    
    user, err := service.FindUser(1)
    if err != nil {
        t.Fatalf("unexpected error: %v", err)
    }
    if user.Name != "Alice" {
        t.Errorf("expected Alice, got %s", user.Name)
    }
    
    mockRepo.AssertExpectations(t)
}
```

### 2.2 替换依赖

```go
// 使用依赖注入
type UserService struct {
    repo UserRepository
}

func NewUserService(repo UserRepository) *UserService {
    return &UserService{repo: repo}
}

// 生产代码使用真实实现
// 测试代码使用 Mock
```

---

## 3. 基准测试

### 3.1 基础基准测试

```go
// benchmark_test.go

package math

import "testing"

func BenchmarkAdd(b *testing.B) {
    for i := 0; i < b.N; i++ {
        Add(1, 2)
    }
}

func BenchmarkAddParallel(b *testing.B) {
    b.RunParallel(func(pb *testing.PB) {
        for pb.Next() {
            Add(1, 2)
        }
    })
}
```

### 3.2 复杂基准测试

```go
func BenchmarkProcessLargeData(b *testing.B) {
    data := generateLargeData(10000)
    
    b.ReportAllocs() // 报告内存分配
    
    for i := 0; i < b.N; i++ {
        ProcessData(data)
    }
}

func generateLargeData(size int) []int {
    data := make([]int, size)
    for i := range data {
        data[i] = i
    }
    return data
}
```

---

## 4. 测试覆盖率

### 4.1 覆盖率分析

```bash
# 生成覆盖率报告
go test -coverprofile=coverage.out ./...

# 查看覆盖率
go tool cover -func=coverage.out

# 生成 HTML 报告
go tool cover -html=coverage.out

# 查看包级别覆盖率
go test -cover ./...
```

### 4.2 提高覆盖率策略

```
提高覆盖率的方法：

1. 分支覆盖
   ├── 覆盖所有 if/else
   ├── 覆盖 switch case
   └── 覆盖错误处理分支

2. 边界覆盖
   ├── 空值测试
   ├── 边界值测试
   └── 异常场景测试

3. 并行测试
   └── t.Parallel() 加速测试
```

---

## 5. 实战案例

### 5.1 接口测试

```go
// http_handler_test.go

func TestHTTPHandler(t *testing.T) {
    // 创建测试 HTTP server
    mux := http.NewServeMux()
    handler := NewHandler(mux)
    
    srv := httptest.NewServer(handler)
    defer srv.Close()
    
    // 发送请求
    resp, err := http.Get(srv.URL + "/api/users/1")
    if err != nil {
        t.Fatal(err)
    }
    defer resp.Body.Close()
    
    // 验证响应
    if resp.StatusCode != http.StatusOK {
        t.Errorf("expected 200, got %d", resp.StatusCode)
    }
}
```

### 5.2 数据库测试

```go
// db_test.go

func TestDatabaseQuery(t *testing.T) {
    // 使用内存数据库或测试数据库
    db, err := sql.Open("sqlite3", ":memory:")
    if err != nil {
        t.Fatal(err)
    }
    defer db.Close()
    
    // 初始化表结构
    _, err = db.Exec(createTableSQL)
    if err != nil {
        t.Fatal(err)
    }
    
    // 执行测试
    // ...
}
```

---

## 6. 测试策略

### 6.1 测试金字塔

```
           /\
          /  \
         /    \      E2E Tests (10%)
        /______\
       /        \
      /    /\    \   Integration Tests (20%)
     /    /  \    \
    /____/____\____\  Unit Tests (70%)
```

### 6.2 测试命名规范

```go
// 好的命名
func TestAdd_PositiveNumbers_ReturnsSum(t *testing.T) {}
func TestAdd_NegativeNumbers_ReturnsSum(t *testing.T) {}
func TestAdd_ZeroNumbers_ReturnsZero(t *testing.T) {}

// 不好的命名
func Test1(t *testing.T) {}
func TestFunc(t *testing.T) {}
```

---

## 7. 总结

### 7.1 核心原理回顾

| 模块 | 核心机制 |
|------|----------|
| 表驱动测试 | 数据驱动，循环测试 |
| Mock | Interface + mock库 |
| 基准测试 | Benchmark + ReportAllocs |
| 覆盖率 | coverprofile + cover |

### 7.2 最佳实践

- [ ] 使用表驱动测试
- [ ] 测试边界情况
- [ ] 使用 Mock 隔离依赖
- [ ] 编写基准测试
- [ ] 保持高覆盖率

---

*最后更新：2026-08-11*
*作者：Ryan*
