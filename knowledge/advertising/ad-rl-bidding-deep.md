# 强化学习在广告出价中的应用深度

> RL 优化出价 + 多臂老虎机 + 深度 Q 网络 + 生产实战

---

## 第一部分：为什么广告出价适合用强化学习？

### 传统方法 vs RL

```
传统方法：
→ 固定出价策略（CPC/CPM/oCPM）
→ 基于规则的优化（阈值触发调价）
→ 无法适应动态环境

强化学习：
→ 与环境交互学习最优策略
→ 自适应调整出价
→ 最大化长期回报（ROI）
→ 处理探索与利用的权衡
```

### RL 在广告中的优势

```
1. 动态环境：
   → 竞争对手出价不断变化
   → 流量质量波动
   → RL 能实时适应

2. 长期优化：
   → 传统方法只看短期 CPA
   → RL 考虑长期 ROI
   → 避免短期优化损害长期收益

3. 个性化：
   → 每个广告主有不同的目标和约束
   → RL 可以为每个广告主定制策略
```

---

## 第二部分：RL 基础概念

### 2.1 马尔可夫决策过程（MDP）

```
状态 Space (S)：
→ 当前预算剩余
→ 历史 CPA
→ 当前 CTR/CVR
→ 时间特征（时段/工作日）
→ 竞争环境

动作 Space (A)：
→ 提高出价 10%
→ 降低出价 10%
→ 保持当前出价

奖励函数 (R)：
→ 转化：+10
→ 点击：+1
→ 消耗：-cost/targetCPA

策略 (π)：
→ 根据状态选择动作的概率分布
→ π(a|s) = P(动作 a | 状态 s)

价值函数 (V/Q)：
→ V(s): 状态 s 的长期回报
→ Q(s,a): 状态 s 采取动作 a 的长期回报
```

### 2.2 探索与利用

```
ε-greedy 策略：
→ ε=0.1: 10% 概率随机探索，90% 概率利用最优策略
→ 初期 ε 较大（多探索）
→ 后期 ε 较小（多利用）

UCB 策略：
→ Upper Confidence Bound
→ 优先探索不确定性高的动作
→ 自动平衡探索和利用

Thompson Sampling：
→ 贝叶斯方法
→ 根据后验分布采样
→ 自适应探索
```

---

## 第三部分：算法实现

### 3.1 Q-Learning

```python
import numpy as np

class QLearningAgent:
    """Q-Learning 出价代理"""
    
    def __init__(self, state_size, action_size, learning_rate=0.1, 
                 discount_factor=0.95, epsilon=0.1):
        self.state_size = state_size
        self.action_size = action_size
        self.lr = learning_rate
        self.gamma = discount_factor
        self.epsilon = epsilon
        
        # Q 表
        self.q_table = np.zeros((state_size, action_size))
    
    def get_action(self, state):
        """选择动作（ε-greedy）"""
        if np.random.random() < self.epsilon:
            # 探索：随机动作
            return np.random.randint(self.action_size)
        else:
            # 利用：最优动作
            return np.argmax(self.q_table[state])
    
    def update(self, state, action, reward, next_state):
        """更新 Q 值"""
        # Bellman 方程
        current_q = self.q_table[state, action]
        max_next_q = np.max(self.q_table[next_state])
        new_q = current_q + self.lr * (reward + self.gamma * max_next_q - current_q)
        self.q_table[state, action] = new_q
    
    def decay_epsilon(self, decay_rate=0.995):
        """衰减探索率"""
        self.epsilon = max(0.01, self.epsilon * decay_rate)
```

### 3.2 Deep Q-Network (DQN)

```python
import torch
import torch.nn as nn
import torch.optim as optim
from collections import deque
import random

class DQN(nn.Module):
    """深度 Q 网络"""
    
    def __init__(self, state_size, action_size):
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(state_size, 256),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(256, 256),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(256, action_size),
        )
    
    def forward(self, x):
        return self.network(x)


class DQNAgent:
    """DQN 出价代理"""
    
    def __init__(self, state_size, action_size, device='cpu'):
        self.state_size = state_size
        self.action_size = action_size
        self.device = device
        
        # Q 网络
        self.q_network = DQN(state_size, action_size).to(device)
        self.target_network = DQN(state_size, action_size).to(device)
        self.target_network.load_state_dict(self.q_network.state_dict())
        
        # 优化器
        self.optimizer = optim.Adam(self.q_network.parameters(), lr=1e-4)
        self.loss_fn = nn.MSELoss()
        
        # 经验回放缓冲区
        self.memory = deque(maxlen=100000)
        self.batch_size = 64
        
        # 探索参数
        self.epsilon = 1.0
        self.epsilon_min = 0.01
        self.epsilon_decay = 0.995
    
    def remember(self, state, action, reward, next_state, done):
        """存储经验"""
        self.memory.append((state, action, reward, next_state, done))
    
    def act(self, state):
        """选择动作"""
        if random.random() < self.epsilon:
            return random.randint(0, self.action_size - 1)
        
        state_tensor = torch.FloatTensor(state).unsqueeze(0).to(self.device)
        with torch.no_grad():
            q_values = self.q_network(state_tensor)
        return q_values.argmax(dim=1).item()
    
    def replay(self):
        """训练网络"""
        if len(self.memory) < self.batch_size:
            return
        
        # 采样批次
        batch = random.sample(self.memory, self.batch_size)
        states, actions, rewards, next_states, done = zip(*batch)
        
        states = torch.FloatTensor(states).to(self.device)
        actions = torch.LongTensor(actions).to(self.device)
        rewards = torch.FloatTensor(rewards).to(self.device)
        next_states = torch.FloatTensor(next_states).to(self.device)
        done = torch.FloatTensor(done).to(self.device)
        
        # 计算目标 Q 值
        with torch.no_grad():
            current_q = self.q_network(states).gather(1, actions.unsqueeze(1)).squeeze(1)
            next_q = self.target_network(next_states).max(1)[0]
            target_q = rewards + (1 - done) * 0.99 * next_q
        
        # 计算损失并更新
        loss = self.loss_fn(current_q, target_q.detach())
        self.optimizer.zero_grad()
        loss.backward()
        self.optimizer.step()
        
        return loss.item()
    
    def update_target(self):
        """更新目标网络"""
        self.target_network.load_state_dict(self.q_network.state_dict())
    
    def decay_epsilon(self):
        """衰减探索率"""
        self.epsilon = max(self.epsilon_min, self.epsilon * self.epsilon_decay)
```

### 3.3 上下文多臂老虎机（Contextual Bandit）

```python
class ContextualBanditAgent:
    """
    上下文多臂老虎机
    适用于：每次决策独立，无状态转移的场景
    比 DQN 更简单，更适合广告出价
    """
    
    def __init__(self, n_arms, feature_dim):
        self.n_arms = n_arms
        self.feature_dim = feature_dim
        self.W = np.zeros((n_arms, feature_dim))  # 权重矩阵
        self.regularization = 1.0
    
    def predict_reward(self, arm, features):
        """预测奖励"""
        return np.dot(self.W[arm], features)
    
    def select_arm_ucb(self, features, c=1.0):
        """UCB 选择动作"""
        scores = np.zeros(self.n_arms)
        for arm in range(self.n_arms):
            mean_reward = self.predict_reward(arm, features)
            # UCB 不确定性
            uncertainty = c * np.sqrt(np.log(sum(self.counts)) / self.counts[arm])
            scores[arm] = mean_reward + uncertainty
        
        return np.argmax(scores)
    
    def update(self, arm, features, reward):
        """更新权重（线性回归）"""
        # 岭回归更新
        X = np.vstack([features, self.regularization * np.eye(self.feature_dim)])
        y = np.array([reward] + [0] * self.feature_dim)
        
        self.W[arm] = np.linalg.solve(
            X.T @ X + self.regularization * np.eye(self.feature_dim),
            X.T @ y
        )
```

---

## 第四部分：RL 出价策略

### 4.1 策略梯度方法（REINFORCE）

```python
class PolicyGradientAgent:
    """
    策略梯度方法
    直接优化策略，适合连续动作空间
    """
    
    def __init__(self, state_size, action_size):
        self.policy = nn.Sequential(
            nn.Linear(state_size, 128),
            nn.ReLU(),
            nn.Linear(128, action_size),
            nn.Softmax(dim=-1),  # 输出概率分布
        )
        self.optimizer = optim.Adam(self.policy.parameters(), lr=1e-3)
    
    def select_action(self, state):
        state_tensor = torch.FloatTensor(state).unsqueeze(0)
        probs = self.policy(state_tensor)
        distribution = torch.distributions.Categorical(probs)
        action = distribution.sample()
        return action.item(), distribution.log_prob(action)
    
    def update(self, trajectory, gamma=0.99):
        """
        trajectory: [(state, action, reward), ...]
        """
        returns = []
        G = 0
        for r in reversed(trajectory):
            G = r['reward'] + gamma * G
            returns.insert(0, G)
        
        returns = torch.FloatTensor(returns)
        returns = (returns - returns.mean()) / (returns.std() + 1e-8)
        
        policy_loss = []
        for i, step in enumerate(trajectory):
            state = torch.FloatTensor(step['state']).unsqueeze(0)
            action = torch.LongTensor([step['action']])
            log_prob = self.policy(state).log()[0][action]
            policy_loss.append(-log_prob * returns[i])
        
        loss = torch.stack(policy_loss).sum()
        self.optimizer.zero_grad()
        loss.backward()
        self.optimizer.step()
        
        return loss.item()
```

### 4.2 PPO（近端策略优化）

```python
class PPOAgent:
    """
    PPO 算法
    当前 RL 中最流行的算法
    适合广告出价优化
    """
    
    def __init__(self, state_size, action_size, clip_param=0.2):
        self.actor = nn.Sequential(
            nn.Linear(state_size, 128),
            nn.ReLU(),
            nn.Linear(128, action_size),
            nn.Softmax(dim=-1),
        )
        self.critic = nn.Sequential(
            nn.Linear(state_size, 128),
            nn.ReLU(),
            nn.Linear(128, 1),
        )
        self.clip_param = clip_param
        self.optimizer = optim.Adam(
            list(self.actor.parameters()) + list(self.critic.parameters()),
            lr=1e-4
        )
    
    def act(self, state):
        state_tensor = torch.FloatTensor(state).unsqueeze(0)
        probs = self.actor(state_tensor)
        dist = torch.distributions.Categorical(probs)
        action = dist.sample()
        return action.item(), dist.log_prob(action)
    
    def compute_gae(self, rewards, values, dones, gamma=0.99, lam=0.95):
        """广义优势估计"""
        advantages = []
        gae = 0
        for i in reversed(range(len(rewards))):
            delta = rewards[i] + gamma * values[i+1] * (1 - dones[i]) - values[i]
            gae = delta + gamma * lam * (1 - dones[i]) * gae
            advantages.insert(0, gae)
        return advantages
    
    def update(self, states, actions, old_log_probs, advantages, values, epochs=4):
        """PPO 更新"""
        states = torch.FloatTensor(states)
        actions = torch.LongTensor(actions)
        old_log_probs = torch.FloatTensor(old_log_probs)
        advantages = torch.FloatTensor(advantages)
        values = torch.FloatTensor(values)
        
        for _ in range(epochs):
            # Actor 更新
            probs = self.actor(states)
            dist = torch.distributions.Categorical(probs)
            log_probs = dist.log_prob(actions)
            ratio = torch.exp(log_probs - old_log_probs)
            
            surr1 = ratio * advantages
            surr2 = torch.clamp(ratio, 1 - self.clip_param, 1 + self.clip_param) * advantages
            
            actor_loss = -torch.min(surr1, surr2).mean()
            
            # Critic 更新
            new_values = self.critic(states).squeeze()
            critic_loss = F.mse_loss(new_values, values)
            
            # 总损失
            loss = actor_loss + 0.5 * critic_loss
            
            self.optimizer.zero_grad()
            loss.backward()
            self.optimizer.step()
        
        return loss.item()
```

---

## 第五部分：生产部署

### 5.1 在线学习架构

```
┌─────────────────────────────────────────────────────────────┐
│                    RL 出价系统架构                            │
└─────────────────────────────────────────────────────────────┘

                    ┌───────────────────────────────────────┐
                    │         Online Training               │
                    │  - 实时收集数据                         │
                    │  - 增量更新模型                         │
                    │  - A/B 测试新策略                       │
                    └──────────────┬────────────────────────┘
                                   │
                    ┌──────────────▼────────────────────────┐
                    │       Model Registry                  │
                    │  - 模型版本管理                         │
                    │  - 自动回滚                             │
                    │  - 性能监控                             │
                    └──────────────┬────────────────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              │                    │                    │
    ┌─────────▼────────┐ ┌────────▼─────────┐ ┌───────▼────────┐
    │  控制组 (50%)     │ │ 实验组 A (25%)   │ │ 实验组 B (25%) │
    │  传统出价策略     │ │ PPO 策略 v1      │ │ DQN 策略 v2    │
    └──────────────────┘ └──────────────────┘ └────────────────┘
```

### 5.2 安全约束

```python
class SafeRLBidder:
    """
    安全的 RL 出价器
    添加约束防止 RL 探索造成损失
    """
    
    def __init__(self, base_bidder, constraints):
        self.base_bidder = base_bidder
        self.constraints = constraints
    
    def bid(self, state):
        action = self.base_bidder.select_action(state)
        
        # 约束检查
        if not self.check_constraints(action, state):
            action = self.safeguard_action(action, state)
        
        return action
    
    def check_constraints(self, action, state):
        """检查约束"""
        # 1. 出价不能超过上限
        if action.bid > self.constraints.max_bid:
            return False
        
        # 2. 单日消耗不能超过预算
        if state.daily_spend + action.cost > self.constraints.daily_budget:
            return False
        
        # 3. CPA 不能超过目标
        if state.current_cpa > self.constraints.max_cpa * 1.5:
            return False
        
        return True
    
    def safeguard_action(self, action, state):
        """安全保护动作"""
        # 降级到传统出价策略
        return ConservativeBidder().bid(state)
```

---

## 第六部分：自测题

### 问题 1
为什么广告出价适合用强化学习？

<details>
<summary>查看答案</summary>

1. **动态环境**：竞争对手出价不断变化
2. **长期优化**：考虑长期 ROI 而非短期 CPA
3. **个性化**：每个广告主有不同的目标和约束
4. **探索利用**：自动平衡探索新策略和利用已知策略
</details>

### 问题 2
RL 出价系统如何保证安全？

<details>
<summary>查看答案</summary>

1. **出价上限**：防止 RL 出价过高
2. **预算约束**：单日消耗不超过预算
3. **CPA 限制**：CPA 不超过目标的 1.5 倍
4. **安全降级**：触发约束时降级到传统策略
5. **A/B 测试**：小流量测试新策略
</details>

---

*本文档基于广告强化学习生产实战整理。*