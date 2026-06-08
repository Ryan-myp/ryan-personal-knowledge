# 广告系统架构 — 竞价系统、广告排序、流量分配、竞价拍卖深度

> 标签: `#广告系统` `#竞价` `#RTB` `#广告排序` `#流量分配` `#竞价拍卖` `#源码级`
> 创建日期: 20260608
> 作者: Ryan

---

## 1. 广告竞价系统深度

### 1.1 竞价机制源码级分析

```java
// 竞价核心逻辑（Bidding Engine）:
// 
// 核心公式:
// eCPM = pCTR × pCVR × BidAmount × 1000
// 
// pCTR: 点击概率预测
// pCVR: 转化概率预测
// BidAmount: 出价金额
//
// 竞价策略:
// 1. oCPM: 按千次展示出价 = pCTR × pCVR × TargetCPA × 1000
// 2. oCPC: 按点击出价 = pCVR × TargetCPA
// 3. oCPX: 按目标出价 = pCTR × TargetCPA
//
// 代码路径:
// class BidEngine {
//     fun calculateBid(ad: Ad, user: User, context: Context): Bid {
//         // 1. 预测 pCTR
//         val pctr = ctrModel.predict(user.features, ad.features, context.features)
//         
//         // 2. 预测 pCVR
//         val pcvr = cvrModel.predict(user.features, ad.features, context.features)
//         
//         // 3. 计算 eCPM
//         val ecpm = pctr * pcvr * ad.bidAmount * 1000
//         
//         // 4. 预算控制
//         val adjustedBid = budgetPacing.adjust(ad, ecpm)
//         
//         // 5. 竞价策略
//         val finalBid = biddingStrategy.calculate(
//             strategy = ad.strategy,  // oCPM/oCPC/oCPX
//             targetCPA = ad.targetCPA,
//             pctr = pctr,
//             pcvr = pcvr,
//             baseBid = adjustedBid
//         )
//         
//         return Bid(
//             adId = ad.id,
//             bid = finalBid,
//             ecpm = pctr * pcvr * finalBid * 1000,
//             targetCPA = ad.targetCPA,
//             strategy = ad.strategy
//         )
//     }
// }
//
// 竞价拍卖类型:
// 1. 第一价格拍卖（First-Price Auction）:
//    - 最高出价者获胜，支付自己出价
//    - 公式: price = bid_winner
//    - 策略: 出价要保守（避免过高）
//
// 2. 第二价格拍卖（Second-Price Auction / VCG）:
//    - 最高出价者获胜，支付第二高出价
//    - 公式: price = bid_second_highest
//    - 策略: 出价要诚实（真实估值）
//
// 3. 广义第二价格拍卖（GSP - Generalized Second-Price）:
//    - 广告排序按 eCPM，但支付第二高出价
//    - 公式: price_i = max(bid_{i+1} × quality_i+1 / quality_i, min_bid)
//    - 策略: 出价要策略性（考虑质量分）
//
// 竞价流程源码:
// class AuctionEngine {
//     fun runAuction(ads: List<Ad>, slots: List<Slot>): AuctionResult {
//         // 1. 计算每个广告的 eCPM
//         val scoredAds = ads.map { ad ->
//             val ecpm = bidEngine.calculateBid(ad).ecpm
//             AdScored(ad, ecpm)
//         }
//         
//         // 2. 排序（降序）
//         val sortedAds = scoredAds.sortedByDescending { it.ecpm }
//         
//         // 3. 分配广告位（VCG 定价）
//         val result = mutableMapOf<Slot, Ad>()
//         for (i in sortedAds.indices) {
//             if (i < slots.size) {
//                 val slot = slots[i]
//                 val ad = sortedAds[i].ad
//                 val price = if (i + 1 < sortedAds.size) {
//                     // VCG: 支付第二高出价
//                     val nextAd = sortedAds[i + 1]
//                     vcgPrice(ad, nextAd.ecpm)
//                 } else {
//                     minBid
//                 }
//                 
//                 result[slot] = ad
//                 ad.price = price
//             }
//         }
//         
//         return AuctionResult(result)
//     }
//     
//     fun vcgPrice(winner: AdScored, loser: AdScored): Double {
//         // VCG 定价:  winner 需要支付的社会成本
//         // socialCost = 其他广告的总效用（如果 winner 不存在时的总效用 - 当前总效用）
//         return loser.ecpm * (winner.quality / loser.quality)
//     }
// }
```

### 1.2 实时竞价（RTB）架构

```java
// RTB 实时竞价架构:
// 
// 请求流程:
// 1. 媒体（Publisher）请求广告
// 2. SSP（Supply-Side Platform）收集广告位信息
// 3. SSP → Ad Exchange → DSP（Demand-Side Platform）
// 4. DSP 竞价决策:
//    - 用户 ID 匹配（1st party → 3rd party）
//    - 用户画像检索（Ad User Profile）
//    - 出价决策（Bid Engine）
//    - 返回出价（BidResponse）
// 5. Ad Exchange 选择最高出价
// 6. Ad Exchange → Publisher（广告展示）
// 7. Publisher → DSP（Impression/Click 回传）
// 8. DSP 更新模型（反馈学习）
//
// RTB 架构源码（简化）:
// class RTBEngine {
//     fun processBidRequest(request: BidRequest): BidResponse {
//         // 1. 解析请求
//         val adSlot = request.adSlot
//         val userId = request.userId
//         val context = request.context
//         
//         // 2. 用户画像检索
//         val userProfile = userProfileService.getUserProfile(userId)
//         
//         // 3. 广告预筛选
//         val candidateAds = adFilter.filter(userProfile, context)
//         
//         // 4. 广告排序 + 竞价
//         val scoredAds = candidateAds.map { ad ->
//             val ecpm = adSorter.calculateECPM(ad, userProfile, context)
//             AdScored(ad, ecpm)
//         }
//         
//         // 5. 选择最佳广告
//         val bestAd = scoredAds.maxBy { it.ecpm }
//         
//         // 6. 生成竞价响应
//         return BidResponse(
//             bidderId = request.bidderId,
//             adId = bestAd?.ad?.id,
//             bid = bestAd?.calculateBid(),
//             cpm = bestAd?.ecpm,
//             adCreative = bestAd?.ad?.creative
//         )
//     }
// }
//
// RTB 延迟要求:
// - 总延迟 < 100ms（行业标准）
// - 用户画像检索 < 10ms
// - 广告筛选 < 20ms
// - 排序 + 竞价 < 50ms
// - 网络往返 < 20ms
//
// 优化策略:
// 1. 用户画像缓存（Redis）: TTL=5min
// 2. 广告预筛选倒排索引（ES）: 毫秒级检索
// 3. 排序模型蒸馏（Distillation）: 从大模型到小模型
// 4. 异步竞价: 提前预加载热门广告
```

---

## 2. 广告排序深度

### 2.1 排序模型

```java
// 广告排序模型架构:
// 
// 多层排序:
// 1. 预筛选（Pre-filter）:
//    - 规则过滤: 定向条件、频控、黑名单
//    - 倒排索引: 按 user interests → ad categories
//    - 输出: 候选集（Top 1000）
//
// 2. 粗排（Pre-ranking）:
//    - 轻量模型: 线性回归 / 逻辑回归
//    - 特征: user profile + ad features（简单）
//    - 输出: Top 100
//
// 3. 精排（Ranking）:
//    - 深度学习模型: DNN / Wide & Deep / DeepFM
//    - 特征: user profile + ad features + context（全面）
//    - 输出: Top 10
//
// 4. 重排（Re-ranking）:
//    - 业务规则: 广告混合、多样性、频控
//    - 输出: 最终广告序列
//
// 排序模型: Wide & Deep
// 
// class WideDeepRanker {
//     // Wide 部分: 特征交叉
//     val wideModel = WideModel(
//         featurePairs = listOf(
//             "age:30-40:gender:female",
//             "location:Beijing:interest:tech",
//             "device:iOS:time:night"
//         )
//     )
//     
//     // Deep 部分: 特征学习
//     val deepModel = DeepModel(
//         embeddingSize = 64,
//         hiddenLayers = listOf(256, 128, 64)
//     )
//     
//     fun predict(userFeatures: Features, adFeatures: Features, context: Context): Double {
//         // Wide 部分: 特征交叉
//         val wideScore = wideModel.score(userFeatures, adFeatures, context)
//         
//         // Deep 部分: 深度学习
//         val deepScore = deepModel.score(userFeatures.embedding, adFeatures.embedding)
//         
//         // 融合
//         val finalScore = alpha * wideScore + (1 - alpha) * deepScore
//         
//         return sigmoid(finalScore)
//     }
// }
//
// 特征工程:
// 1. User Features:
//    - 基础: age, gender, location, device
//    - 行为: 点击率, 转化率, 最近 7 天行为
//    - 兴趣: 标签, 偏好, 浏览历史
//    - 社交: 关系链, 互动频率
//
// 2. Ad Features:
//    - 基础: category, price, brand
//    - 历史: cTR, cCVR, impressions, clicks
//    - 创意: image, title, description
//    - 质量: 落地页质量分, 品牌安全
//
// 3. Context Features:
//    - 时间: hour, day, weekday
//    - 位置: city, country, timezone
//    - 页面: page type, content category
//    - 设备: platform, browser, network
```

### 2.2 多目标排序

```java
// 多目标排序（Multi-Objective Ranking）:
// 
// 广告平台通常需要优化多个目标:
// 1. pCTR（点击率）
// 2. pCVR（转化率）
// 3. pWatchTime（观看时长）
// 4. pEngagement（互动率）
// 5. revenue（收入）
//
// 多目标融合:
// finalScore = w1 × pCTR + w2 × pCVR + w3 × pWatchTime + w4 × revenue
//
// 实现:
// class MultiObjectiveRanker {
//     fun rank(ads: List<Ad>, user: User): List<Ad> {
//         // 1. 预测每个目标的值
//         val predictions = ads.map { ad ->
//             val pctr = ctrModel.predict(ad, user)
//             val pcvr = cvrModel.predict(ad, user)
//             val pwatchtime = watchtimeModel.predict(ad, user)
//             val revenue = revenueModel.predict(ad, user)
//             
//             // 2. 融合
//             val score = 0.3 * pctr + 0.2 * pcvr + 0.1 * pwatchtime + 0.4 * revenue
//             
//             AdPredicted(ad, pctr, pcvr, pwatchtime, revenue, score)
//         }
//         
//         // 3. 排序
//         return predictions.sortedByDescending { it.score }
//     }
// }
//
// MMOE（Multi-gate Mixture-of-Experts）:
// class MMOEModel {
//     val sharedExperts = ExpertNetwork()  // 共享专家层
//     val taskSpecificGates = listOf<GateNetwork>()  // 任务特定门控
//     
//     fun predict(ad: Ad, user: User): Map<String, Double> {
//         // 1. 共享专家
//         val expertOutputs = sharedExperts.forward(ad, user)
//         
//         // 2. 每个任务有自己的门控
//         val taskOutputs = mutableMapOf<String, Double>()
//         for (task in tasks) {
//             val gate = taskSpecificGates[task]
//             val weightedOutput = gate.forward(expertOutputs)
//             taskOutputs[task] = weightedOutput
//         }
//         
//         return taskOutputs
//     }
// }
```

---

## 3. 流量分配深度

### 3.1 流量分配策略

```java
// 流量分配策略:
// 
// 1. 保量广告（Guaranteed Delivery）:
//    - 先满足保量广告（PDB/PG）
//    - 剩余流量走竞价广告
//    - 保量优先级: PDB > PGL > PO > 竞价
//
// 2. 竞价广告（Auction Delivery）:
//    - 按 eCPM 排序
//    - 最高 eCPM 获胜
//
// 3. 混合分配（Hybrid Delivery）:
//    - 保量广告优先
//    - 保量不足时，竞价广告补充
//    - 保量超额时，竞价广告减少
//
// 预算控制（Budget Pacing）:
// class BudgetPacing {
//     // 目标: 在一天内均匀消耗预算
//     // 避免: 上午花完下午没钱
//     
//     fun calculateAdjustedBid(bid: Bid, budget: Budget): Double {
//         // 1. 计算已花费比例
//         val spentRatio = budget.spent / budget.total
//         val timeRatio = currentTime / totalDayTime
//         
//         // 2. 如果花费过快，降低出价
//         if (spentRatio > timeRatio * 1.2) {
//             val adjustFactor = timeRatio / spentRatio
//             return bid.baseBid * adjustFactor
//         }
//         
//         // 3. 如果花费过慢，提高出价
//         if (spentRatio < timeRatio * 0.8) {
//             val adjustFactor = timeRatio / spentRatio
//             return bid.baseBid * (1 + adjustFactor)
//         }
//         
//         return bid.baseBid
//     }
//     
//     // 平滑算法:
//     // 使用移动平均 + 指数平滑
//     // 避免波动过大
//     fun smoothBudget(timeSeries: List<Double>): List<Double> {
//         val smoothed = mutableListOf<Double>()
//         var prev = timeSeries[0]
//         for (current in timeSeries) {
//             val alpha = 0.3  // 平滑系数
//             val smoothedValue = alpha * current + (1 - alpha) * prev
//             smoothed.add(smoothedValue)
//             prev = smoothedValue
//         }
//         return smoothed
//     }
// }
```

### 3.2 广告混排

```java
// 广告混排（Ad-Mixed Content）:
// 
// 1. 广告与自然内容混合:
//    - 每 N 条内容插入 1 条广告
//    - 广告位置固定（前 3 位、中间、底部）
//    - 避免过多广告影响用户体验
//
// 2. 广告间混排:
//    - 竞价广告和保量广告混合
//    - 避免同一广告连续出现
//    - 保证多样性
//
// class AdMixedPlacer {
//     fun mix(ads: List<Ad>, content: List<Content>, slots: Int): List<AdOrContent> {
//         // 1. 确定广告位置
//         val adPositions = calculateAdPositions(ads, slots)
//         
//         // 2. 插入广告
//         val result = mutableListOf<AdOrContent>()
//         var contentIndex = 0
//         var adIndex = 0
//         
//         for (i in 0 until slots) {
//             if (adPositions.contains(i)) {
//                 result.add(AdOrContent.Ad(ads[adIndex]))
//                 adIndex++
//             } else {
//                 result.add(AdOrContent.Content(content[contentIndex]))
//                 contentIndex++
//             }
//         }
//         
//         // 3. 确保广告不会连续出现
//         removeConsecutiveAds(result)
//         
//         return result
//     }
//     
//     fun calculateAdPositions(ads: List<Ad>, slots: Int): Set<Int> {
//         // 固定位置: 第 1 位、第 4 位、第 7 位
//         return setOf(0, 3, 6)
//     }
// }
```

---

## 4. 竞价拍卖深度

### 4.1 拍卖机制源码级分析

```java
// 竞价拍卖机制:
// 
// 1. First-Price Auction（第一价格）:
// class FirstPriceAuction {
//     fun run(ads: List<Ad>): List<Ad> {
//         val sorted = ads.sortedByDescending { it.ecpm }
//         return sorted.map { it.copy(price = it.bid) }
//     }
// }
//
// 2. Second-Price Auction（第二价格）:
// class SecondPriceAuction {
//     fun run(ads: List<Ad>): List<Ad> {
//         val sorted = ads.sortedByDescending { it.ecpm }
//         return sorted.mapIndexed { index, ad ->
//             val price = if (index + 1 < sorted.size) {
//                 sorted[index + 1].ecpm
//             } else {
//                 minBid
//             }
//             ad.copy(price = price)
//         }
//     }
// }
//
// 3. VCG（Vickrey-Clarke-Groves）:
// class VCGLAuction {
//     fun run(ads: List<Ad>): List<Ad> {
//         return ads.map { ad ->
//             // 计算社会成本（其他广告的总效用变化）
//             val socialCost = calculateSocialCost(ad, ads)
//             ad.copy(price = socialCost)
//         }
//     }
//     
//     fun calculateSocialCost(winner: Ad, allAds: List<Ad>): Double {
//         // 移除 winner 后的总效用
//         val totalWithoutWinner = allAds.filter { it != winner }
//             .sortedByDescending { it.ecpm }
//             .take(1)  // 假设只有 1 个广告位
//             .sumOf { it.ecpm }
//         
//         // 当前总效用（包含 winner）
//         val totalWithWinner = allAds.sortedByDescending { it.ecpm }
//             .take(1)
//             .sumOf { it.ecpm }
//         
//         return totalWithoutWinner - totalWithWinner
//     }
// }
```

### 4.2 竞价反作弊

```java
// 竞价反作弊:
// 
// 1. 点击欺诈（Click Fraud）:
//    - 同一用户/IP 重复点击
//    - 机器人流量
//    - 竞对恶意点击
//
// 2. 转化欺诈（Conversion Fraud）:
//    - 虚假转化
//    - 自动化工具模拟转化
//
// 3. 流量欺诈（Traffic Fraud）:
//    - 僵尸网络
//    - 无效流量（IVT）
//
// class FraudDetection {
//     fun detectFraud(click: Click): Boolean {
//         // 1. 同一用户点击频率
//         val userClickCount = userClickFrequency(click.userId, click.adId)
//         if (userClickCount > threshold) return true
//         
//         // 2. 同一 IP 点击频率
//         val ipClickCount = ipClickFrequency(click.ip, click.adId)
//         if (ipClickCount > threshold) return true
//         
//         // 3. 设备指纹
//         val deviceFingerprint = deviceFingerprint(click.deviceId)
//         if (isSuspicious(deviceFingerprint)) return true
//         
//         // 4. 行为模式
//         if (isBot(click.behavior)) return true
//         
//         return false
//     }
// }
```

---

## 5. 广告平台 API 对比

```
┌──────────┬────────────────┬────────────────┬────────────────┐
│          │  Google Ads    │  Meta Ads      │  TikTok Ads    │
├──────────┼────────────────┼────────────────┼────────────────┤
│ 竞价     │ vCPM/vCPC      │  ABO/CBO       │  oCPX/oCPM     │
│          │  First-Price   │  Second-Price  │  First-Price   │
├──────────┼────────────────┼────────────────┼────────────────┤
│ 排序     │ 质量分 + eCPM  │  pCTR/pCVR     │  eCPM          │
│          │  (Ad Rank)     │  (Rank Score)  │                │
├──────────┼────────────────┼────────────────┼────────────────┤
│ 定向     │  兴趣/行为/    │  兴趣/行为/    │  兴趣/行为/    │
│          │  关键词/地理    │  自定义受众    │  兴趣/行为     │
├──────────┼────────────────┼────────────────┼────────────────┤
│ 转化追踪 │  Google Tag    │  Pixel         │  TikTok Pixel  │
├──────────┼────────────────┼────────────────┼────────────────┤
│ API 限制 │  100 QPS/账号  │  50 QPS/账号   │  20 QPS/账号   │
├──────────┼────────────────┼────────────────┼────────────────┤
│ 优势     │  搜索意图      │  社交推荐      │  短视频内容    │
│          │  强转化意图    │  社交互动      │  内容推荐      │
└──────────┴────────────────┴────────────────┴────────────────┘
```

---

*本文档基于广告竞价系统架构整理，覆盖竞价/排序/流量分配/拍卖/API对比*
