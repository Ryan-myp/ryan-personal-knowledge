# 高并发架构深度：Netpoller/连接池/限流熔断 源码级

> 从 Go Netpoller 到连接池再到限流熔断，逐行解析高并发系统核心

---

## 第一部分：Netpoller 源码深度

### Netpoller 架构

```
Go 网络模型：
Goroutine → syscall → Netpoller(epoll/kqueue) → Goroutine ready

1. 用户 goroutine 发起网络请求
2. 阻塞时调用 gopark() 休眠
3. Netpoller(epoll) 监听 fd 事件
4. 事件就绪时调用 goready() 唤醒 goroutine
5. goroutine 从 runq 获取 CPU 执行

关键：无阻塞时 goroutine 休眠，不占 CPU
```

### 源码逐行解析

```go
package netpoll

import (
	"syscall"
	"unsafe"
)

// Netpoller 网络轮询器
type Netpoller struct {
	epfd     int          // epoll fd
	events   []epollevent // 就绪事件数组
	breakR   int          // break pipe read fd
	breakW   int          // break pipe write fd
}

// NewNetpoller 创建 Netpoller
func NewNetpoller() (*Netpoller, error) {
	np := &Netpoller{
		events: make([]epollevent, 128),
	}
	
	// 1. epoll_create
	epfd, err := syscall.EpollCreate1(syscall.EPOLL_CLOEXEC)
	if err != nil {
		return nil, err
	}
	np.epfd = epfd
	
	// 2. 创建 break pipe（self-pipe trick）
	var fds [2]int
	if err := syscall.Pipe2(fds[:], syscall.O_NONBLOCK|syscall.O_CLOEXEC); err != nil {
		syscall.Close(epfd)
		return nil, err
	}
	np.breakR = fds[0]
	np.breakW = fds[1]
	
	// 3. 注册 break pipe 到 epoll
	ev := epollevent{
		events: syscall.EPOLLIN,
	}
	*(*uintptr)(unsafe.Pointer(&ev.data)) = uintptr(np.breakR)
	
	if err := syscall.EpollCtl(epfd, syscall.EPOLL_CTL_ADD, fds[0], &ev); err != nil {
		syscall.Close(fds[0])
		syscall.Close(fds[1])
		syscall.Close(epfd)
		return nil, err
	}
	
	return np, nil
}

// Poll 轮询事件
func (np *Netpoller) Poll(timeout int) ([]FdEvent, error) {
	n, err := syscall.EpollWait(np.epfd, np.events, timeout)
	if err != nil {
		return nil, err
	}
	
	var events []FdEvent
	for i := 0; i < n; i++ {
		fd := int(*(*int32)(unsafe.Pointer(&np.events[i].data)))
		
		// 跳过 break pipe
		if fd == np.breakR {
			var buf [16]byte
			syscall.Read(np.breakR, buf[:])
			continue
		}
		
		event := FdEvent{
			Fd:     fd,
			Readable: np.events[i].events&syscall.EPOLLIN != 0,
			Writable: np.events[i].events&syscall.EPOLLOUT != 0,
		}
		events = append(events, event)
	}
	
	return events, nil
}

// Register 注册 fd
func (np *Netpoller) Register(fd int, readable, writable bool) error {
	var events uint32
	if readable {
		events |= syscall.EPOLLIN
	}
	if writable {
		events |= syscall.EPOLLOUT
	}
	
	ev := epollevent{
		events: events,
	}
	*(*uintptr)(unsafe.Pointer(&ev.data)) = uintptr(fd)
	
	return syscall.EpollCtl(np.epfd, syscall.EPOLL_CTL_ADD, fd, &ev)
}

// Modify 修改 fd 事件
func (np *Netpoller) Modify(fd int, readable, writable bool) error {
	var events uint32
	if readable {
		events |= syscall.EPOLLIN
	}
	if writable {
		events |= syscall.EPOLLOUT
	}
	
	ev := epollevent{
		events: events,
	}
	*(*uintptr)(unsafe.Pointer(&ev.data)) = uintptr(fd)
	
	return syscall.EpollCtl(np.epfd, syscall.EPOLL_CTL_MOD, fd, &ev)
}

// Close 关闭
func (np *Netpoller) Close() error {
	syscall.Close(np.epfd)
	syscall.Close(np.breakR)
	syscall.Close(np.breakW)
	return nil
}
```

---

## 第二部分：连接池深度

```go
package pool

import (
	"context"
	"sync"
	"time"
)

// Conn 连接接口
type Conn interface {
	Read(buf []byte) (int, error)
	Write(buf []byte) (int, error)
	Close() error
	IsValid() bool
}

// PoolConfig 连接池配置
type PoolConfig struct {
	InitialCapacity  int           // 初始容量
	MaxCapacity      int           // 最大容量
	IdleTimeout      time.Duration // 空闲超时
	MaxLifetime      time.Duration // 最大生命周期
	HealthCheckInterval time.Duration // 健康检查间隔
}

// Pool 连接池
type Pool struct {
	config       PoolConfig
	conns        []*PooledConn
	mu           sync.Mutex
	cond         *sync.Cond
	created      int
	closed       int
}

type PooledConn struct {
	conn       Conn
	createdAt  time.Time
	lastUsedAt time.Time
	inUse      bool
}

// NewPool 创建连接池
func NewPool(config PoolConfig) *Pool {
	pool := &Pool{
		config: config,
		conns:  make([]*PooledConn, 0, config.InitialCapacity),
	}
	pool.cond = sync.NewCond(&pool.mu)
	
	// 启动健康检查 goroutine
	go pool.healthCheckLoop()
	
	return pool
}

// Get 获取连接
func (p *Pool) Get(ctx context.Context) (Conn, error) {
	p.mu.Lock()
	defer p.mu.Unlock()
	
	// 1. 尝试从池中获取空闲连接
	for _, conn := range p.conns {
		if !conn.inUse && conn.isValid() {
			conn.inUse = true
			conn.lastUsedAt = time.Now()
			return conn.conn, nil
		}
	}
	
	// 2. 池满则等待
	if p.created >= p.config.MaxCapacity {
		// 等待有连接释放
		p.cond.Wait()
		return p.Get(ctx) // 递归重试
	}
	
	// 3. 创建新连接
	conn, err := p.newConn()
	if err != nil {
		return nil, err
	}
	
	p.conns = append(p.conns, &PooledConn{
		conn:      conn,
		createdAt: time.Now(),
		lastUsedAt: time.Now(),
		inUse:     true,
	})
	p.created++
	
	return conn, nil
}

// Put 归还连接
func (p *Pool) Put(conn Conn) {
	p.mu.Lock()
	defer p.mu.Unlock()
	
	for _, pooled := range p.conns {
		if pooled.conn == conn && pooled.inUse {
			pooled.inUse = false
			pooled.lastUsedAt = time.Now()
			p.cond.Signal() // 唤醒一个等待的 goroutine
			return
		}
	}
	
	// 连接不在池中，关闭
	conn.Close()
}

// Close 关闭连接池
func (p *Pool) Close() error {
	p.mu.Lock()
	defer p.mu.Unlock()
	
	for _, pooled := range p.conns {
		pooled.conn.Close()
	}
	p.conns = nil
	
	return nil
}

func (p *Pool) newConn() (Conn, error) {
	// 创建新连接（具体实现由使用者提供）
	return nil, nil
}

func (p *Pool) healthCheckLoop() {
	ticker := time.NewTicker(p.config.HealthCheckInterval)
	defer ticker.Stop()
	
	for range ticker.C {
		p.mu.Lock()
		for i := len(p.conns) - 1; i >= 0; i-- {
			pooled := p.conns[i]
			
			// 检查空闲超时
			if !pooled.inUse && time.Since(pooled.lastUsedAt) > p.config.IdleTimeout {
				pooled.conn.Close()
				p.conns = append(p.conns[:i], p.conns[i+1:]...)
				p.closed++
				continue
			}
			
			// 检查最大生命周期
			if time.Since(pooled.createdAt) > p.config.MaxLifetime {
				pooled.conn.Close()
				p.conns = append(p.conns[:i], p.conns[i+1:]...)
				p.closed++
				continue
			}
		}
		p.mu.Unlock()
	}
}

func (p *Pool) Stats() map[string]int {
	p.mu.Lock()
	defer p.mu.Unlock()
	
	active := 0
	idle := 0
	for _, conn := range p.conns {
		if conn.inUse {
			active++
		} else {
			idle++
		}
	}
	
	return map[string]int{
		"total":  len(p.conns),
		"active": active,
		"idle":   idle,
		"created": p.created,
		"closed": p.closed,
	}
}
```

---

## 第三部分：限流与熔断

```go
package circuit

import (
	"sync"
	"sync/atomic"
	"time"
)

// 限流器
type RateLimiter struct {
	rate       int           // 每秒允许请求数
	burst      int           // 突发容量
	tokens     int64
	maxTokens  int64
	lastRefill time.Time
	mu         sync.Mutex
}

func NewRateLimiter(rate, burst int) *RateLimiter {
	return &RateLimiter{
		rate:       rate,
		burst:      burst,
		maxTokens:  int64(burst),
		lastRefill: time.Now(),
	}
}

func (rl *RateLimiter) Allow() bool {
	rl.mu.Lock()
	defer rl.mu.Unlock()
	
	now := time.Now()
	elapsed := now.Sub(rl.lastRefill).Seconds()
	
	// 补充 token
	rl.tokens += int64(elapsed * float64(rl.rate))
	if rl.tokens > rl.maxTokens {
		rl.tokens = rl.maxTokens
	}
	
	rl.lastRefill = now
	
	// 消耗 token
	if rl.tokens >= 1 {
		rl.tokens--
		return true
	}
	
	return false
}

// 熔断器
type CircuitBreaker struct {
	state          int // 0=closed, 1=open, 2=half-open
	failureCount   int
	successCount   int
	failureThreshold int
	successThreshold int
	timeout        time.Duration
	lastFailure    time.Time
	mu             sync.Mutex
}

const (
	StateClosed   = 0
	StateOpen     = 1
	StateHalfOpen = 2
)

func NewCircuitBreaker(failureThreshold, successThreshold int, timeout time.Duration) *CircuitBreaker {
	return &CircuitBreaker{
		state:            StateClosed,
		failureThreshold: failureThreshold,
		successThreshold: successThreshold,
		timeout:          timeout,
	}
}

func (cb *CircuitBreaker) Allow() bool {
	cb.mu.Lock()
	defer cb.mu.Unlock()
	
	switch cb.state {
	case StateClosed:
		return true
	case StateOpen:
		if time.Since(cb.lastFailure) > cb.timeout {
			cb.state = StateHalfOpen
			cb.successCount = 0
			return true
		}
		return false
	case StateHalfOpen:
		return true
	}
	return false
}

func (cb *CircuitBreaker) RecordSuccess() {
	cb.mu.Lock()
	defer cb.mu.Unlock()
	
	switch cb.state {
	case StateClosed:
		cb.failureCount = 0
	case StateHalfOpen:
		cb.successCount++
		if cb.successCount >= cb.successThreshold {
			cb.state = StateClosed
			cb.failureCount = 0
		}
	}
}

func (cb *CircuitBreaker) RecordFailure() {
	cb.mu.Lock()
	defer cb.mu.Unlock()
	
	cb.failureCount++
	cb.lastFailure = time.Now()
	
	switch cb.state {
	case StateClosed:
		if cb.failureCount >= cb.failureThreshold {
			cb.state = StateOpen
		}
	case StateHalfOpen:
		cb.state = StateOpen
	}
}
```

---

## 第四部分：自测题

### Q1: Netpoller 为什么比每连接一线程高效？

**A**: 无阻塞时 goroutine 休眠不占 CPU，epoll 单线程管理百万 fd，上下文切换少。

### Q2: 连接池的关键参数？

**A**: InitialCapacity/MaxCapacity/IdleTimeout/MaxLifetime/HealthCheckInterval。

### Q3: 熔断器的三种状态？

**A**: Closed（正常）/ Open（熔断）/ Half-Open（试探）。失败达到阈值 → Open，超时后 → Half-Open，成功达到阈值 → Closed。

---

## 第五部分：生产实践

### 1. Netpoller 优化

```
Netpoller 优化：
1. 批量获取事件（128 个）
2. LT 模式（安全）
3. Break pipe 优雅退出
```

### 2. 连接池优化

```
连接池优化：
1. 初始容量根据预估 QPS 设置
2. IdleTimeout 30-90s
3. 健康检查 10-30s
4. 监控连接数/等待时间
```

### 3. 限流熔断

```
限流熔断：
1. 令牌桶限流：平滑限流
2. 滑动窗口限流：精确控制
3. 熔断器：失败阈值 5，超时 30s
4. 监控：QPS/延迟/错误率
```
