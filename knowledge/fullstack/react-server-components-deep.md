# React Server Components 深度实现

> **文档级别**: Level 5 - 专家级  
> **创建日期**: 2026-08-13  
> **状态**: ✅ 已补齐

---

## 一、RSC 架构原理

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     React Server Components 架构                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌─────────────────┐           ┌─────────────────┐                       │
│   │   Client        │           │   Server        │                       │
│   │   Components    │◄─────────►│   Components    │                       │
│   │   (客户端)      │  流式传输  │   (服务端)      │                       │
│   └────────┬────────┘           └────────┬────────┘                       │
│            │                             │                                │
│   ┌────────▼────────┐           ┌────────▼────────┐                       │
│   │   Interactive   │           │   Data Fetching │                       │
│   │   (交互组件)    │           │   (数据获取)    │                       │
│   └────────┬────────┘           └────────┬────────┘                       │
│            │                             │                                │
│   ┌────────▼────────┐           ┌────────▼────────┐                       │
│   │   State/Effects │           │   DB/Cache      │                       │
│   │   (状态/副作用) │           │   (数据库/缓存) │                       │
│   └─────────────────┘           └─────────────────┘                       │
│                                                                             │
│  核心优势:                                                                   │
│  • 零 JavaScript 打包开销                                                  │
│  • 直接访问后端资源                                                          │
│  • 自动代码分割                                                              │
│  • 流式渲染支持                                                              │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 二、Server Component 实现

```tsx
// 文件: components/ServerAdCard.tsx

// ─── Server Component (默认) ───
async function AdCard({ adId }: { adId: string }) {
  // 直接访问数据库
  const ad = await fetch(`/api/ads/${adId}`);
  
  // 不需要 client-side bundle
  return (
    <div className="ad-card">
      <img src={ad.imageUrl} alt={ad.title} />
      <h3>{ad.title}</h3>
      <p>CTR: {ad.ctr.toFixed(2)}%</p>
    </div>
  );
}

// ─── 父组件 ───
async function AdFeed({ campaignId }: { campaignId: string }) {
  const ads = await fetch(`/api/campaigns/${campaignId}/ads`);
  
  return (
    <div className="ad-feed">
      {ads.map((ad: Ad) => (
        <AdCard key={ad.id} adId={ad.id} />
      ))}
    </div>
  );
}
```

---

## 三、Client Component 与交互

```tsx
// 文件: components/ClientBidControl.tsx

'use client';  // 明确标记为客户端组件

import { useState, useEffect } from 'react';

export function BidControl({ initialBid }: { initialBid: number }) {
  const [bid, setBid] = useState(initialBid);
  const [isAdjusting, setIsAdjusting] = useState(false);
  
  // 客户端交互逻辑
  const adjustBid = async (delta: number) => {
    setIsAdjusting(true);
    const newBid = bid + delta;
    
    await fetch('/api/bids/update', {
      method: 'POST',
      body: JSON.stringify({ bid: newBid }),
    });
    
    setBid(newBid);
    setIsAdjusting(false);
  };
  
  return (
    <div className="bid-control">
      <span className="current-bid">${bid.toFixed(2)}</span>
      <button 
        onClick={() => adjustBid(-0.1)}
        disabled={isAdjusting}
      >
        -0.1
      </button>
      <button 
        onClick={() => adjustBid(0.1)}
        disabled={isAdjusting}
      >
        +0.1
      </button>
    </div>
  );
}

// ─── 在 Server Component 中使用 ───
async function CampaignDashboard({ campaignId }) {
  const campaign = await fetchCampaign(campaignId);
  
  return (
    <div>
      <h1>{campaign.name}</h1>
      {/* Client Component 可以访问 Server Component 的数据 */}
      <BidControl initialBid={campaign.currentBid} />
    </div>
  );
}
```

---

## 四、数据获取模式

```tsx
// 文件: data/fetchPatterns.tsx

// ─── 模式 1: Direct DB Access ───
async function getAdDetails(adId: string) {
  // 直接在 Server Component 中查询
  const db = await getDB();
  return db.ads.find(a => a.id === adId);
}

// ─── 模式 2: Parallel Fetching ───
async function CampaignPage({ campaignId }) {
  // 并行获取多个数据
  const [campaign, stats, recentAds] = await Promise.all([
    fetchCampaign(campaignId),
    fetchStats(campaignId),
    fetchRecentAds(campaignId, 10),
  ]);
  
  return (
    <>
      <CampaignInfo campaign={campaign} />
      <StatsPanel stats={stats} />
      <AdList ads={recentAds} />
    </>
  );
}

// ─── 模式 3: Streaming with Suspense ───
import { Suspense } from 'react';

function StreamingPage() {
  return (
    <Suspense fallback={<LoadingSpinner />}>
      <HeavyComponent />
    </Suspense>
  );
}

async function HeavyComponent() {
  // 耗时操作
  const data = await fetchData();
  return <HeavyContent data={data} />;
}
```

---

## 五、参考资料

```
官方文档:
├── React RSC Docs: https://react.dev/reference/rsc
├── Next.js App Router: https://nextjs.org/docs/app
└── React Server Components: https://github.com/reactwg/server-components

最佳实践:
├── "React Server Components in Action"
└── Vercel RSC Handbook
```

---

*文档版本: v1.0*  
*最后更新: 2026-08-13*  
*作者: Ryan*
