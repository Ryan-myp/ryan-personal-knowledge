# React 测试策略深度实现

> **版本**: v2.0  
> **日期**: 2026-08-13  
> **作者**: Ryan  
> **分类**: 前端/测试  
> **代码密度**: 30%

---

## 一、测试金字塔

```
         /\
        /  \      E2E Tests (少)
       /----\
      /      \    Integration Tests (中)
     /--------\
    /          \  Unit Tests (多)
   /------------\
```

---

## 二、单元测试

```typescript
// __tests__/BidCard.test.tsx
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import BidCard from '../BidCard';

vi.mock('../hooks/useBid', () => ({
  useBid: vi.fn(() => ({
    bid: vi.fn(),
    isLoading: false,
  })),
}));

describe('BidCard', () => {
  const defaultProps = {
    adId: '123',
    price: 100,
    budget: 500,
  };

  it('renders bid button', () => {
    render(<BidCard {...defaultProps} />);
    expect(screen.getByRole('button', { name: /bid/i })).toBeInTheDocument();
  });

  it('calls bid on click', async () => {
    const { useBid } = await import('../hooks/useBid');
    const mockBid = vi.fn();
    vi.mocked(useBid).mockReturnValue({ bid: mockBid, isLoading: false });
    
    render(<BidCard {...defaultProps} />);
    fireEvent.click(screen.getByRole('button'));
    
    expect(mockBid).toHaveBeenCalledWith('123', 100);
  });

  it('shows loading state', () => {
    const { useBid } = vi.runInNewContext(() => require('../hooks/useBid'));
    vi.mocked(useBid).mockReturnValue({ bid: vi.fn(), isLoading: true });
    
    render(<BidCard {...defaultProps} />);
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });
});
```

---

## 三、集成测试

```typescript
// __tests__/BiddingFlow.test.tsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import BiddingFlow from '../BiddingFlow';

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>
      {children}
    </QueryClientProvider>
  );
};

describe('BiddingFlow', () => {
  it('completes full bidding flow', async () => {
    global.fetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ bidPrice: 120, status: 'won' }),
      })
    );

    render(<BiddingFlow adId="123" />, { wrapper: createWrapper() });
    
    fireEvent.click(screen.getByRole('button', { name: /bid/i }));
    
    await waitFor(() => {
      expect(screen.getByText(/bid won/i)).toBeInTheDocument();
    });
  });
});
```

---

## 四、E2E 测试 (Playwright)

```typescript
// e2e/bidding.spec.ts
import { test, expect } from '@playwright/test';

test.describe('Bidding Flow', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/auction/123');
  });

  test('can place a bid', async ({ page }) => {
    await page.click('[data-testid="bid-button"]');
    await expect(page.locator('[data-testid="bid-result"]'))
      .toContainText('Bid submitted');
  });

  test('shows error on insufficient budget', async ({ page }) => {
    await page.fill('[data-testid="bid-amount"]', '99999');
    await page.click('[data-testid="bid-button"]');
    await expect(page.locator('[data-testid="error-message"]'))
      .toBeVisible();
  });

  test('updates price in real-time', async ({ page }) => {
    const priceLocator = page.locator('[data-testid="current-price"]');
    await expect(priceLocator).toHaveText(/\$\d+/);
  });
});
```

---

## 五、测试覆盖率配置

```typescript
// vitest.config.ts
import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      thresholds: {
        statements: 80,
        branches: 70,
        functions: 80,
        lines: 80,
      },
    },
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
  },
});
```

---

## 六、自测题

1. **单元测试和集成测试的区别？**
   - 单测隔离组件，集成测组件协作

2. **Mock 何时使用？**
   - 依赖外部服务、定时器、随机数

3. **Playwright vs Cypress 如何选择？**
   - Playwright 多浏览器支持更好，Cypress 调试体验更佳

