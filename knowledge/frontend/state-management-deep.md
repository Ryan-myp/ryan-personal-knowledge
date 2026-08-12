# 状态管理架构深度实现

> **文档级别**: Level 5 - 专家级  
> **创建日期**: 2026-08-13  
> **状态**: ✅ 已补齐

---

## 一、状态管理选型

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        状态管理选型决策树                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  应用规模                                                                   │
│  ├── 小型 (局部状态) → useState/useReducer                                  │
│  ├── 中型 (跨组件共享) → Context + useReducer                               │
│  ├── 大型 (全局状态) → Zustand/Jotai                                        │
│  └── 复杂 (企业级) → Redux Toolkit                                          │
│                                                                             │
│  性能需求                                                                   │
│  ├── 高频更新 → Zustand (无渲染屏障)                                        │
│  ├── 精确订阅 → Jotai (原子粒度)                                            │
│  └── 时间旅行 → Redux (DevTools)                                            │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 二、Zustand 实战

```typescript
// 文件: frontend/store/ad-bidding.ts

import { create } from 'zustand';
import { devtools } from 'zustand/middleware';

interface AdState {
  campaigns: Campaign[];
  selectedCampaign: Campaign | null;
  addCampaign: (campaign: Campaign) => void;
  updateBudget: (id: string, budget: number) => void;
}

const useAdStore = create<AdState>()(
  devtools((set) => ({
    campaigns: [],
    selectedCampaign: null,
    
    addCampaign: (campaign) => 
      set((state) => ({ 
        campaigns: [...state.campaigns, campaign] 
      })),
    
    updateBudget: (id, budget) =>
      set((state) => ({
        campaigns: state.campaigns.map((c) =>
          c.id === id ? { ...c, budget } : c
        ),
      })),
  }))
);
```

---

## 三、参考资料

```
核心库:
├── Zustand: https://github.com/pmndrs/zustand
├── Jotai: https://jotai.org/
└── Redux Toolkit: https://redux-toolkit.js.org/
```

---

*文档版本: v1.0*  
*最后更新: 2026-08-13*  
*作者: Ryan*
