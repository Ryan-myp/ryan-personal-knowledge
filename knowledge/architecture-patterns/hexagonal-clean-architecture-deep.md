# 六边形架构与整洁架构深度实战

## 一、架构演进史：为什么需要六边形？

### 1.1 从分层架构到六边形

传统分层架构（Controller → Service → Repository）在小型项目中表现良好，但当项目复杂度上升时，会出现以下问题：

```
传统分层架构的问题：
┌─────────────────────────────────────┐
│           Presentation Layer        │  ← 用户界面
├─────────────────────────────────────┤
│           Application Layer         │  ← 业务逻辑
├─────────────────────────────────────┤
│           Domain Layer              │  ← 领域模型
├─────────────────────────────────────┤
│           Infrastructure Layer      │  ← 数据库/API
└─────────────────────────────────────┘
          ↓ 依赖方向 ↑
```

**核心问题**：基础设施层（数据库、消息队列、外部API）实际上"污染"了领域层的纯净性。Repository接口定义在Domain层，但实现却在Infrastructure层——这违反了依赖倒置原则（DIP）。

### 1.2 六边形架构（Ports & Adapters）

Alistair Cockburn 于2005年提出六边形架构，核心理念：

> **应用程序的核心（Domain）应该独立于任何外部框架或基础设施。**

```
                    ┌──────────────────┐
                    │   External APIs  │
                    │  (REST/gRPC/etc) │
                    └────────┬─────────┘
                             │
                      ┌──────▼──────┐
                      │  Adapter    │
                      └──────┬──────┘
                             │
       ┌─────────────────────┼─────────────────────┐
       │                     │                     │
       │     ┌───────────────┴───────────────┐     │
       │     │                               │     │
       │     │     ┌───────────────┐         │     │
       │     │     │   Domain      │         │     │
       │     │     │   Core        │         │     │
       │     │     │               │         │     │
       │     │     │  Business     │         │     │
       │     │     │  Logic        │         │     │
       │     │     │               │         │     │
       │     │     └───────────────┘         │     │
       │     │                               │     │
       │     └───────────────────────────────┘     │
       │                                           │
       │  ┌────────────┐    ┌──────────────────┐  │
       │  │   Port     │◄──►│   Port           │  │
       │  │  (Interface)│    │  (Interface)     │  │
       │  └────────────┘    └──────────────────┘  │
       │                                           │
       │     ┌───────────────┐         ┌────────┐  │
       │     │  Database     │         │MQ/Cache│  │
       │     │  Adapter      │         │Adapter │  │
       │     └───────────────┘         └────────┘  │
       └───────────────────────────────────────────┘
```

**关键概念**：
- **Domain Core（域核心）**：纯业务逻辑，不依赖任何框架
- **Port（端口）**：接口定义，描述"谁需要服务"或"服务需要什么"
- **Adapter（适配器）**：实现，将外部世界适配到端口

### 1.3 整洁架构（Clean Architecture）

Robert C. Martin 在六边形基础上进一步提炼，提出"依赖规则"：

```
                ┌─────────────────────┐
                │     Frameworks      │  ← 最外层：DB、Web框架、UI
                │  (Details & Drivers)│
                └──────────┬──────────┘
                           │
                ┌──────────▼──────────┐
                │    Interfaces       │  ← 适配器层：Repository接口、HTTP Handler
                │   (Adapters)        │
                └──────────┬──────────┘
                           │
                ┌──────────▼──────────┐
                │     Use Cases       │  ← 业务规则：Application Services
                │  (Application       │
                │   Business Rules)   │
                └──────────┬──────────┘
                           │
                ┌──────────▼──────────┐
                │     Entities        │  ← 企业级业务规则：Domain Models
                │  (Enterprise        │
                │   Business Rules)   │
                └─────────────────────┘
```

**依赖规则（Dependency Rule）**：
> 源代码中的函数依赖关系只能指向内层。外层不能依赖内层。

```
Entities → Use Cases → Interfaces → Frameworks
    ↑            ↑            ↑            ↑
  最内层 ←──── 依赖方向 ←──── 最外层
```

## 二、Go 语言中的实现

### 2.1 基础项目结构

```
cmd/
├── server/
│   └── main.go              # HTTP Server 入口
└── worker/
    └── main.go              # 后台 Worker 入口
internal/
├── domain/                  # 领域层（最内层）
│   ├── entity/
│   │   ├── order.go         # Order 实体
│   │   └── product.go       # Product 实体
│   ├── repository/
│   │   ├── order_repo.go    # 端口定义（接口）
│   │   └── product_repo.go  # 端口定义（接口）
│   └── service/
│       └── order_service.go # 应用层用例
├── adapter/                 # 适配层
│   ├── http/
│   │   ├── handler/
│   │   │   └── order_handler.go  # 适配器：HTTP → 端口
│   │   └── middleware/
│   └── persistence/
│       └── order_repo_impl.go  # 适配器：Repository 实现
└── config/                  # 配置层
    └── config.go
```

### 2.2 领域层：纯业务逻辑

```go
// internal/domain/entity/order.go
package entity

import (
	"errors"
	"fmt"
	"time"
)

// OrderStatus 订单状态枚举
type OrderStatus string

const (
	StatusPending    OrderStatus = "pending"
	StatusPaid       OrderStatus = "paid"
	StatusShipped    OrderStatus = "shipped"
	StatusDelivered  OrderStatus = "delivered"
	StatusCancelled  OrderStatus = "cancelled"
)

// Order 订单实体 — 只包含业务规则，不依赖任何框架
type Order struct {
	ID        string
	UserID    string
	Items     []OrderItem
	Status    OrderStatus
	CreatedAt time.Time
	UpdatedAt time.Time
}

// OrderItem 订单项
type OrderItem struct {
	ProductID string
	Name      string
	Quantity  int
	Price     float64
}

// NewOrder 构造函数 — 强制业务规则验证
func NewOrder(userID string, items []OrderItem) (*Order, error) {
	if userID == "" {
		return nil, errors.New("user ID cannot be empty")
	}
	if len(items) == 0 {
		return nil, errors.New("order must have at least one item")
	}

	total := 0.0
	for i, item := range items {
		if item.Quantity <= 0 {
			return nil, fmt.Errorf("item %d quantity must be positive", i+1)
		}
		if item.Price < 0 {
			return nil, fmt.Errorf("item %d price cannot be negative", i+1)
		}
		total += item.Price * float64(item.Quantity)
	}

	now := time.Now()
	return &Order{
		ID:        generateOrderID(),
		UserID:    userID,
		Items:     items,
		Status:    StatusPending,
		CreatedAt: now,
		UpdatedAt: now,
	}, nil
}

// Pay 支付方法 — 纯业务逻辑
func (o *Order) Pay() error {
	if o.Status != StatusPending {
		return fmt.Errorf("order %s is not in pending status, current: %s", o.ID, o.Status)
	}
	o.Status = StatusPaid
	o.UpdatedAt = time.Now()
	return nil
}

// Ship 发货方法 — 纯业务逻辑
func (o *Order) Ship() error {
	if o.Status != StatusPaid {
		return fmt.Errorf("order %s must be paid before shipping, current: %s", o.ID, o.Status)
	}
	o.Status = StatusShipped
	o.UpdatedAt = time.Now()
	return nil
}

// Cancel 取消方法 — 含业务规则
func (o *Order) Cancel() error {
	if o.Status == StatusDelivered {
		return errors.New("cannot cancel a delivered order")
	}
	if o.Status == StatusCancelled {
		return errors.New("order is already cancelled")
	}
	o.Status = StatusCancelled
	o.UpdatedAt = time.Now()
	return nil
}

// TotalAmount 计算总金额 — 纯函数，无副作用
func (o *Order) TotalAmount() float64 {
	var total float64
	for _, item := range o.Items {
		total += item.Price * float64(item.Quantity)
	}
	return total
}

func generateOrderID() string {
	return fmt.Sprintf("ORD-%d", time.Now().UnixNano())
}
```

**关键点**：
- `Order` 结构体不包含 `gorm.Model` 标签、不包含 `json` 标签（这些属于序列化层）
- 所有业务规则封装在方法中（`Pay()`、`Ship()`、`Cancel()`）
- `TotalAmount()` 是纯函数，可测试、可复用

### 2.3 端口定义：接口隔离

```go
// internal/domain/repository/order_repo.go
package repository

import "ryan-personal-knowledge/knowledge/architecture-patterns/internal/domain/entity"

// OrderRepository 订单仓库端口 — 只定义契约，不关心实现
type OrderRepository interface {
	// Create 创建订单
	Create(order *entity.Order) error
	// GetByID 按ID查询
	GetByID(id string) (*entity.Order, error)
	// Update 更新订单
	Update(order *entity.Order) error
	// Delete 删除订单
	Delete(id string) error
	// ListByUser 查询用户订单列表
	ListByUser(userID string, page, pageSize int) ([]*entity.Order, int, error)
	// UpdateStatus 批量更新状态（用于支付回调等场景）
	UpdateStatus(id string, status entity.OrderStatus) error
}

// ProductRepository 商品仓库端口
type ProductRepository interface {
	GetByID(id string) (*entity.Product, error)
	ListAvailable() ([]*entity.Product, error)
	UpdateStock(id string, delta int) error // delta > 0 增加，< 0 减少
}
```

**为什么用接口？**
1. **测试友好**：可以注入 mock 实现进行单元测试
2. **实现无关**：可以切换 MySQL/PostgreSQL/MongoDB，不影响上层
3. **依赖倒置**：Use Case 依赖的是抽象（接口），而非具体实现

### 2.4 应用层：用例编排

```go
// internal/domain/service/order_service.go
package service

import (
	"errors"
	"fmt"
	"sync"

	"ryan-personal-knowledge/knowledge/architecture-patterns/internal/domain/entity"
	"ryan-personal-knowledge/knowledge/architecture-patterns/internal/domain/repository"
)

// OrderService 订单服务 — 编排用例，不含具体业务规则
type OrderService struct {
	orderRepo   repository.OrderRepository
	productRepo repository.ProductRepository
	mu          sync.Mutex // 并发控制：防止超卖
}

// NewOrderService 构造函数
func NewOrderService(
	orderRepo repository.OrderRepository,
	productRepo repository.ProductRepository,
) *OrderService {
	return &OrderService{
		orderRepo:   orderRepo,
		productRepo: productRepo,
	}
}

// CreateOrder 创建订单 — 完整业务流程
func (s *OrderService) CreateOrder(userID string, itemRequests []CreateOrderItemRequest) (*entity.Order, error) {
	s.mu.Lock()
	defer s.mu.Unlock()

	// 1. 验证并构建订单项
	var items []entity.OrderItem
	for _, req := range itemRequests {
		product, err := s.productRepo.GetByID(req.ProductID)
		if err != nil {
			return nil, fmt.Errorf("product %s not found: %w", req.ProductID, err)
		}
		if product.Stock < req.Quantity {
			return nil, fmt.Errorf("insufficient stock for product %s: available=%d, requested=%d",
				product.ID, product.Stock, req.Quantity)
		}
		items = append(items, entity.OrderItem{
			ProductID: product.ID,
			Name:      product.Name,
			Quantity:  req.Quantity,
			Price:     product.Price,
		})
	}

	// 2. 创建订单实体（内含业务规则验证）
	order, err := entity.NewOrder(userID, items)
	if err != nil {
		return nil, fmt.Errorf("invalid order: %w", err)
	}

	// 3. 持久化
	if err := s.orderRepo.Create(order); err != nil {
		return nil, fmt.Errorf("failed to persist order: %w", err)
	}

	return order, nil
}

// PayOrder 支付订单 — 含库存扣减的业务流程
func (s *OrderService) PayOrder(orderID string, paymentInfo PaymentInfo) error {
	s.mu.Lock()
	defer s.mu.Unlock()

	// 1. 查询订单
	order, err := s.orderRepo.GetByID(orderID)
	if err != nil {
		return fmt.Errorf("order not found: %w", err)
	}

	// 2. 执行支付业务规则
	if err := order.Pay(); err != nil {
		return err
	}

	// 3. 扣减库存
	for _, item := range order.Items {
		if err := s.productRepo.UpdateStock(item.ProductID, -item.Quantity); err != nil {
			// 库存扣减失败 → 回滚订单状态
			order.Cancel()
			s.orderRepo.Update(order)
			return fmt.Errorf("stock deduction failed, order rolled back: %w", err)
		}
	}

	// 4. 持久化
	return s.orderRepo.Update(order)
}

// CreateOrderItemRequest 创建订单请求
type CreateOrderItemRequest struct {
	ProductID string
	Quantity  int
}

// PaymentInfo 支付信息
type PaymentInfo struct {
	Method    string
	TransactionID string
}
```

**关键设计决策**：
- `sync.Mutex` 放在 Service 层而非 Entity 层 — 因为锁是并发控制 concern，不是业务规则
- `PayOrder` 方法中，库存扣减失败会回滚订单状态 — 这是业务一致性要求
- Service 不直接操作 HTTP 请求/响应 — 它只接受结构化参数

### 2.5 适配器层：HTTP 适配器

```go
// internal/adapter/http/handler/order_handler.go
package handler

import (
	"encoding/json"
	"net/http"
	"strconv"

	"ryan-personal-knowledge/knowledge/architecture-patterns/internal/domain/entity"
	"ryan-personal-knowledge/knowledge/architecture-patterns/internal/domain/service"
)

// OrderHandler 订单 HTTP 处理器 — 纯粹的适配器
type OrderHandler struct {
	orderService *service.OrderService
}

// NewOrderHandler 构造函数
func NewOrderHandler(orderService *service.OrderService) *OrderHandler {
	return &OrderHandler{orderService: orderService}
}

// RegisterRoutes 注册路由
func (h *OrderHandler) RegisterRoutes(mux *http.ServeMux) {
	mux.HandleFunc("POST /api/orders", h.CreateOrder)
	mux.HandleFunc("POST /api/orders/{id}/pay", h.PayOrder)
	mux.HandleFunc("GET /api/orders/{id}", h.GetOrder)
	mux.HandleFunc("GET /api/orders", h.ListOrders)
}

// CreateOrderRequest 创建订单的请求 DTO
type CreateOrderRequest struct {
	Items []struct {
		ProductID string `json:"product_id"`
		Quantity  int    `json:"quantity"`
	} `json:"items"`
}

// CreateOrder 创建订单
func (h *OrderHandler) CreateOrder(w http.ResponseWriter, r *http.Request) {
	var req CreateOrderRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		h.writeError(w, http.StatusBadRequest, "invalid request body")
		return
	}

	userID := r.Header.Get("X-User-ID")
	if userID == "" {
		h.writeError(w, http.StatusUnauthorized, "missing user ID")
		return
	}

	var itemRequests []service.CreateOrderItemRequest
	for _, item := range req.Items {
		itemRequests = append(itemRequests, service.CreateOrderItemRequest{
			ProductID: item.ProductID,
			Quantity:  item.Quantity,
		})
	}

	order, err := h.orderService.CreateOrder(userID, itemRequests)
	if err != nil {
		if err.Error() == "insufficient stock" {
			h.writeError(w, http.StatusConflict, err.Error())
			return
		}
		h.writeError(w, http.StatusInternalServerError, err.Error())
		return
	}

	h.writeJSON(w, http.StatusCreated, order)
}

// PayOrder 支付订单
func (h *OrderHandler) PayOrder(w http.ResponseWriter, r *http.Request) {
	orderID := r.PathValue("id")

	var paymentInfo struct {
		Method          string `json:"method"`
		TransactionID string `json:"transaction_id"`
	}
	if err := json.NewDecoder(r.Body).Decode(&paymentInfo); err != nil {
		h.writeError(w, http.StatusBadRequest, "invalid request body")
		return
	}

	err := h.orderService.PayOrder(orderID, service.PaymentInfo{
		Method:          paymentInfo.Method,
		TransactionID: paymentInfo.TransactionID,
	})
	if err != nil {
		h.writeError(w, http.StatusBadRequest, err.Error())
		return
	}

	h.writeJSON(w, http.StatusOK, map[string]string{"status": "paid"})
}

// GetOrder 获取订单详情
func (h *OrderHandler) GetOrder(w http.ResponseWriter, r *http.Request) {
	orderID := r.PathValue("id")

	order, err := h.orderService.GetOrder(orderID)
	if err != nil {
		h.writeError(w, http.StatusNotFound, "order not found")
		return
	}

	h.writeJSON(w, http.StatusOK, order)
}

// ListOrders 查询订单列表
func (h *OrderHandler) ListOrders(w http.ResponseWriter, r *http.Request) {
	userID := r.Header.Get("X-User-ID")
	page, _ := strconv.Atoi(r.URL.Query().Get("page"))
	pageSize, _ := strconv.Atoi(r.URL.Query().Get("page_size"))

	if page < 1 {
		page = 1
	}
	if pageSize < 1 || pageSize > 100 {
		pageSize = 20
	}

	orders, total, err := h.orderService.ListOrders(userID, page, pageSize)
	if err != nil {
		h.writeError(w, http.StatusInternalServerError, err.Error())
		return
	}

	h.writeJSON(w, http.StatusOK, map[string]interface{}{
		"data":     orders,
		"total":    total,
		"page":     page,
		"page_size": pageSize,
	})
}

// 辅助方法
func (h *OrderHandler) writeJSON(w http.ResponseWriter, status int, data interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(data)
}

func (h *OrderHandler) writeError(w http.ResponseWriter, status int, message string) {
	h.writeJSON(w, status, map[string]string{"error": message})
}
```

**适配器职责**：
1. **解包请求**：从 HTTP Request 中提取参数，转换为 Service 层的结构化输入
2. **打包响应**：将 Service 返回值序列化为 HTTP Response
3. **HTTP 语义映射**：将业务错误映射为合适的 HTTP 状态码
4. **不包含业务逻辑**：所有业务规则都在 Service 层

### 2.6 适配器层：持久化适配器

```go
// internal/adapter/persistence/order_repo_impl.go
package persistence

import (
	"context"
	"fmt"

	"ryan-personal-knowledge/knowledge/architecture-patterns/internal/domain/entity"
	"ryan-personal-knowledge/knowledge/architecture-patterns/internal/domain/repository"
)

// MySQLOrderRepository MySQL 实现的订单仓库
type MySQLOrderRepository struct {
	db *DBPool // 自定义连接池，不依赖具体 ORM
}

// NewMySQLOrderRepository 构造函数
func NewMySQLOrderRepository(db *DBPool) *MySQLOrderRepository {
	return &MySQLOrderRepository{db: db}
}

// Ensure it implements the interface
var _ repository.OrderRepository = (*MySQLOrderRepository)(nil)

// Create 创建订单
func (r *MySQLOrderRepository) Create(order *entity.Order) error {
	query := `INSERT INTO orders (id, user_id, status, created_at, updated_at)
	          VALUES ($1, $2, $3, $4, $5)`

	_, err := r.db.Exec(context.Background(), query,
		order.ID, order.UserID, order.Status, order.CreatedAt, order.UpdatedAt,
	)
	if err != nil {
		return fmt.Errorf("create order: %w", err)
	}

	// 插入订单项
	for _, item := range order.Items {
		itemQuery := `INSERT INTO order_items (order_id, product_id, name, quantity, price)
		              VALUES ($1, $2, $3, $4, $5)`
		_, err := r.db.Exec(context.Background(), itemQuery,
			order.ID, item.ProductID, item.Name, item.Quantity, item.Price,
		)
		if err != nil {
			return fmt.Errorf("create order item: %w", err)
		}
	}

	return nil
}

// GetByID 按ID查询
func (r *MySQLOrderRepository) GetByID(id string) (*entity.Order, error) {
	ctx := context.Background()

	// 查询订单主表
	var order entity.Order
	var userID, status string
	var createdAt, updatedAt string

	query := `SELECT id, user_id, status, created_at, updated_at FROM orders WHERE id = $1`
	row := r.db.QueryRow(ctx, query, id)
	if err := row.Scan(&order.ID, &userID, &status, &createdAt, &updatedAt); err != nil {
		return nil, fmt.Errorf("get order: %w", err)
	}
	order.UserID = userID
	order.Status = entity.OrderStatus(status)
	order.CreatedAt, _ = parseTime(createdAt)
	order.UpdatedAt, _ = parseTime(updatedAt)

	// 查询订单项
	itemsQuery := `SELECT product_id, name, quantity, price FROM order_items WHERE order_id = $1`
	rows, err := r.db.Query(ctx, itemsQuery, id)
	if err != nil {
		return nil, fmt.Errorf("get order items: %w", err)
	}
	defer rows.Close()

	for rows.Next() {
		var item entity.OrderItem
		var price float64
		if err := rows.Scan(&item.ProductID, &item.Name, &item.Quantity, &price); err != nil {
			return nil, fmt.Errorf("scan order item: %w", err)
		}
		item.Price = price
		order.Items = append(order.Items, item)
	}

	return &order, nil
}

// Update 更新订单
func (r *MySQLOrderRepository) Update(order *entity.Order) error {
	query := `UPDATE orders SET status = $1, updated_at = $2 WHERE id = $3`
	_, err := r.db.Exec(context.Background(), query,
		order.Status, order.UpdatedAt, order.ID,
	)
	return err
}

// Delete 删除订单
func (r *MySQLOrderRepository) Delete(id string) error {
	_, err := r.db.Exec(context.Background(), "DELETE FROM orders WHERE id = $1", id)
	return err
}

// ListByUser 分页查询
func (r *MySQLOrderRepository) ListByUser(userID string, page, pageSize int) ([]*entity.Order, int, error) {
	offset := (page - 1) * pageSize

	// 先查总数
	var total int
	err := r.db.QueryRow(context.Background(),
		"SELECT COUNT(*) FROM orders WHERE user_id = $1", userID).Scan(&total)
	if err != nil {
		return nil, 0, err
	}

	// 再查数据
	query := `SELECT id, user_id, status, created_at, updated_at FROM orders
	          WHERE user_id = $1 ORDER BY created_at DESC LIMIT $2 OFFSET $3`
	rows, err := r.db.Query(context.Background(), query, userID, pageSize, offset)
	if err != nil {
		return nil, 0, err
	}
	defer rows.Close()

	var orders []*entity.Order
	for rows.Next() {
		var o entity.Order
		var status, createdAt, updatedAt string
		if err := rows.Scan(&o.ID, &o.UserID, &status, &createdAt, &updatedAt); err != nil {
			return nil, 0, err
		}
		o.Status = entity.OrderStatus(status)
		o.CreatedAt, _ = parseTime(createdAt)
		o.UpdatedAt, _ = parseTime(updatedAt)
		orders = append(orders, &o)
	}

	return orders, total, nil
}

// UpdateStatus 更新订单状态
func (r *MySQLOrderRepository) UpdateStatus(id string, status entity.OrderStatus) error {
	_, err := r.db.Exec(context.Background(),
		"UPDATE orders SET status = $1, updated_at = NOW() WHERE id = $2",
		status, id)
	return err
}
```

**持久化适配器特点**：
- 使用 `database/sql` 原生操作，不依赖 GORM/Ent 等 ORM
- SQL 查询直接写在适配器层，不泄露到领域层
- 通过 `var _ repository.OrderRepository = (*MySQLOrderRepository)(nil)` 确保接口实现

## 三、六边形 vs 整洁架构对比

### 3.1 核心差异

| 维度 | 六边形架构 | 整洁架构 |
|------|-----------|---------|
| 提出者 | Alistair Cockburn (2005) | Robert C. Martin (2012) |
| 核心隐喻 | 六边形（多边形） | 洋葱（同心圆） |
| 关注点 | Ports & Adapters 模式 | 依赖方向规则 |
| 层级划分 | 核心 + 端口 + 适配器 | 实体 + 用例 + 接口 + 框架 |
| 适用场景 | 强调外部系统交互 | 强调业务规则独立性 |

### 3.2 实际选择建议

```
项目类型              推荐架构        理由
─────────────────────────────────────────────────────
微服务/核心业务       六边形          端口清晰，便于替换外部依赖
CLI/工具              整洁架构        简单明了，依赖规则清晰
Web API               两者皆可        看团队偏好，六边形更适合大型项目
嵌入式/IoT            六边形          硬件驱动作为适配器，核心不变
数据密集型            整洁架构        实体层承载复杂业务规则
```

## 四、生产排障案例

### 4.1 案例：适配器泄漏到领域层

**症状**：单元测试越来越慢，Mock 实现越来越复杂

**根因**：某个开发者在 `Order` 实体中加入了 `gorm.Model` 标签：

```go
// ❌ 错误示范
type Order struct {
	gorm.Model       // ← 泄漏了 ORM 依赖！
	ID        string
	UserID    string
	// ...
}
```

**修复**：移除所有框架依赖，保持实体纯净：

```go
// ✅ 正确做法
type Order struct {
	ID        string    // 业务ID
	UserID    string
	CreatedAt time.Time // 时间戳，不用 gorm.Time
	// ...
}
```

### 4.2 案例：循环依赖

**症状**：编译报错 `import cycle not allowed`

**根因**：Use Case 调用了 Entity 的方法，Entity 又调用了 Repository 接口

```go
// ❌ 循环依赖
// entity/order.go
func (o *Order) Validate() error {
	return o.repo.CheckDuplicate(o.UserID, o.Items) // ← Entity 依赖 Repository
}

// service/order_service.go
func (s *OrderService) CreateOrder(...) {
	order.Validate() // ← Service 调用 Entity
}
```

**修复**：将验证逻辑提升到 Service 层：

```go
// ✅ 正确做法
// entity/order.go — 只做基础验证
func (o *Order) ValidateBasic() error {
	if o.UserID == "" {
		return errors.New("user ID required")
	}
	return nil
}

// service/order_service.go — 复杂验证放这里
func (s *OrderService) CreateOrder(userID string, items ...) (*entity.Order, error) {
	// 1. 先创建订单
	order, err := entity.NewOrder(userID, items)
	if err != nil {
		return nil, err
	}

	// 2. 复杂验证（需要访问其他 Repository）
	if err := s.validateBusinessRules(order); err != nil {
		return nil, err
	}

	// 3. 持久化
	return order, s.orderRepo.Create(order)
}
```

## 五、自测题

### 5.1 题目一：依赖方向判断

以下代码中，哪些违反了整洁架构的依赖规则？

```go
// package domain/entity
type Order struct {
	ID string
}

func (o *Order) Save() error {
	db := database.Connect() // 依赖了 infrastructure
	return db.Save(o)
}

// package domain/service
type OrderService struct {
	repo repository.OrderRepository
}

func (s *OrderService) Create(order *entity.Order) error {
	return s.repo.Create(order)
}

// package adapter/http
type Handler struct {
	service *service.OrderService
}

func (h *Handler) Handle(r *http.Request) {
	order := entity.NewOrder(...)
	h.service.Create(order)
}
```

<details>
<summary>点击查看答案</summary>

**违反项**：`Order.Save()` 方法
- Entity 直接依赖了 `database.Connect()`（infrastructure 层）
- 修复：移除 `Save()` 方法，持久化由 Repository 负责

**正确项**：Service 和 Handler
- Service 依赖 Repository 接口（符合依赖倒置）
- Handler 依赖 Service（外层依赖内层，正确）
</details>

### 5.2 题目二：接口设计

设计一个 `PaymentPort` 接口，支持微信支付和支付宝，且后续可扩展 Apple Pay。

<details>
<summary>点击查看参考实现</summary>

```go
type PaymentResult struct {
	TransactionID string
	Status        PaymentStatus
	Amount        float64
	Currency      string
}

type PaymentStatus string

const (
	PaymentSuccess PaymentStatus = "success"
	PaymentFailed  PaymentStatus = "failed"
	PaymentPending PaymentStatus = "pending"
)

// PaymentPort 支付端口
type PaymentPort interface {
	// Pay 发起支付
	Pay(ctx context.Context, request PaymentRequest) (*PaymentResult, error)
	// Refund 退款
	Refund(ctx context.Context, transactionID string, amount float64) (*PaymentResult, error)
	// Query 查询支付状态
	Query(ctx context.Context, transactionID string) (*PaymentResult, error)
}

// PaymentRequest 支付请求
type PaymentRequest struct {
	OrderID    string
	Amount     float64
	Currency   string
	Channel    string // "wechat", "alipay", "apple"
	CallbackURL string
}
```

**设计要点**：
- 接口只定义行为契约，不暴露具体渠道实现
- `Channel` 字段让适配器自行处理路由
- 统一 `PaymentResult` 结构，屏蔽各渠道返回差异
</details>

### 5.3 题目三：测试策略

如何为六边形架构的项目编写单元测试？请给出具体示例。

<details>
<summary>点击查看参考实现</summary>

```go
// 1. 领域层测试 — 无需 Mock，纯业务逻辑
func TestOrderPay(t *testing.T) {
	order := createTestOrder()
	
	err := order.Pay()
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	
	if order.Status != entity.StatusPaid {
		t.Errorf("expected status paid, got %s", order.Status)
	}
}

// 2. Service 层测试 — Mock Repository
func TestOrderService_CreateOrder(t *testing.T) {
	mockRepo := &mockOrderRepository{}
	mockProductRepo := &mockProductRepository{
		products: map[string]*entity.Product{
			"p1": {ID: "p1", Name: "Test", Price: 100, Stock: 10},
		},
	}
	
	service := service.NewOrderService(mockRepo, mockProductRepo)
	
	order, err := service.CreateOrder("u1", []service.CreateOrderItemRequest{
		{ProductID: "p1", Quantity: 2},
	})
	
	assert.NoError(t, err)
	assert.Equal(t, "u1", order.UserID)
	assert.Len(t, order.Items, 1)
}

// 3. 适配器层测试 — 集成测试（可选）
func TestMySQLOrderRepository_CreateAndGet(t *testing.T) {
	db := setupTestDB(t)
	repo := persistence.NewMySQLOrderRepository(db)
	
	order := createTestOrder()
	err := repo.Create(order)
	assert.NoError(t, err)
	
	retrieved, err := repo.GetByID(order.ID)
	assert.NoError(t, err)
	assert.Equal(t, order.ID, retrieved.ID)
}
```

**测试金字塔**：
```
        /\
       /  \      少量集成测试（适配器层）
      /----\
     /      \    中等数量 Service 测试（Mock 依赖）
    /--------\
   /          \  大量领域层测试（纯逻辑，零依赖）
  /------------\
```
</details>

## 六、动手验证

### 6.1 最小可运行项目

创建一个完整的六边形架构 Go 项目：

```bash
mkdir -p weread-hexagon-demo && cd weread-hexagon-demo
go mod init weread-hexagon-demo

# 创建目录结构
mkdir -p cmd/server internal/{domain/{entity,repository,service},adapter/{http/handler,persistence}}
```

**main.go 入口**：

```go
package main

import (
	"log"
	"net/http"
	"os"

	"weread-hexagon-demo/internal/adapter/http/handler"
	"weread-hexagon-demo/internal/adapter/persistence"
	"weread-hexagon-demo/internal/domain/service"
)

func main() {
	// 1. 初始化基础设施
	db, err := connectDB(os.Getenv("DATABASE_URL"))
	if err != nil {
		log.Fatal(err)
	}
	defer db.Close()

	// 2. 注册适配器
	orderRepo := persistence.NewMySQLOrderRepository(db)
	productRepo := persistence.NewMySQLProductRepository(db)

	// 3. 注册 Service（依赖注入）
	orderService := service.NewOrderService(orderRepo, productRepo)

	// 4. 注册 Handler
	mux := http.NewServeMux()
	orderHandler := handler.NewOrderHandler(orderService)
	orderHandler.RegisterRoutes(mux)

	// 5. 启动
	addr := ":8080"
	log.Printf("Server starting on %s", addr)
	log.Fatal(http.ListenAndServe(addr, mux))
}
```

## 七、与知识库的对照

### 已有内容
- `architecture/microservices-ddd-cqrs-saga-deep.md` — 已覆盖 DDD 和 CQRS 部分
- `architecture-patterns/cqrs-event-sourcing-deep.md` — 已有 CQRS 深度文档
- `architecture-patterns/event-driven-deep.md` — 已有 EDA 深度文档

### 本文件补充
1. **六边形架构** — 此前知识库缺少完整的六边形架构实现，本文提供了 Go 语言完整实现
2. **整洁架构** — 补充了与六边形的对比和选择建议
3. **依赖倒置实践** — 通过 Repository 接口 + Mock 测试展示了 DIP 的实际用法
4. **生产排障** — 两个真实案例（适配器泄漏、循环依赖）是此前文档未覆盖的

### 缺失内容（建议后续补充）
- **Circuit Breaker 模式** — 微服务间调用的容错机制（可在 `microservice/resilience-patterns-deep.md` 扩展）
- **Saga 编排 vs 编排** — 分布式事务的两种 Saga 实现方式
- **事件溯源的完整实现** — 包括快照、投影、事件存储
