//    active-defrag-threshold-upper 100
//    active-defrag-cycle-min 5
//    active-defrag-cycle-max 25
```

---

### Redis 的 Go 实现

```go
package redis

import (
	"fmt"
	"sync"
	"time"
)

type KVStore struct {
	data    map[string]string
	expires map[string]time.Time
	mu      sync.RWMutex
}

func NewKVStore() *KVStore {
	return &KVStore{data: make(map[string]string)}
}

func (s *KVStore) Set(key, value string) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.data[key] = value
}

func (s *KVStore) Get(key string) (string, bool) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	if exp, ok := s.expires[key]; ok && time.Now().After(exp) {
		delete(s.data, key)
		delete(s.expires, key)
		return "", false
	}
	v, ok := s.data[key]
	return v, ok
}

func (s *KVStore) SetEx(key, value string, ttl time.Duration) {
	s.Set(key, value)
	s.expires[key] = time.Now().Add(ttl)
}

type PubSub struct {
	subscribers map[string][]chan string
	mu          sync.Mutex
}

func NewPubSub() *PubSub { return &PubSub{subscribers: make(map[string][]chan string)} }

func (ps *PubSub) Subscribe(channel string) chan string {
	ch := make(chan string, 100)
	ps.mu.Lock()
	ps.subscribers[channel] = append(ps.subscribers[channel], ch)
	ps.mu.Unlock()
	return ch
}

func (ps *PubSub) Publish(channel, msg string) {
	ps.mu.Lock()
	for _, ch := range ps.subscribers[channel] {
		select {
		case ch <- msg:
		default:
		}
	}
	ps.mu.Unlock()
}

type ClusterNode struct {
	ID       string
	Addr     string
	Role     string
	Slots    []int
	PingTime time.Duration
}

type Cluster struct {
	nodes []*ClusterNode
	mu    sync.RWMutex
}

func (c *Cluster) AddNode(n *ClusterNode) {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.nodes = append(c.nodes, n)
}

func main() {
	store := NewKVStore()
	store.Set("name", "ryan")
	store.SetEx("session", "abc123", 30*time.Minute)
	if v, ok := store.Get("name"); ok { fmt.Printf("name=%s\n", v) }

	ps := NewPubSub()
	ch := ps.Subscribe("news")
	ps.Publish("news", "Hello")
	fmt.Printf("Received: %s\n", <-ch)
}
```