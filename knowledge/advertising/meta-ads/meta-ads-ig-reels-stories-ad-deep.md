# Instagram Reels & Stories 广告策略深度实战

> **领域**: 广告投放 / Meta
> **深度**: ⭐⭐⭐⭐⭐ 实战级指南
> **标签**: meta-ads, instagram, reels, stories, vertical-video, creative
> **更新时间**: 2026-08-14
> **类型**: 实战深度文档

---

> **文档定位说明**
>
> 本文档是 Ryan 知识库中 Meta 广告系列中**唯一聚焦 Instagram Reels 与 Stories 竖版视频**垂直场景的深度文档。
> 它不再复述通用的广告目标、单图/轮播/集合等通用创意格式（那些见
> `meta-ads-objectives-creatives-deep.md` 与 `meta-ads-targeting-advantage-deep.md`），
> 而是把全部火力集中在"**竖版视频 → 全屏消费 → 无缝原生**"这一条生产链路上：
>
> - 视频文件的物理规范（分辨率/帧率/码率/时长/安全区/字幕编码/封面）；
> - Reels Ads 与 Story Ads 的差异与版位特点；
> - 互动贴纸（投票/倒计时/表情/问答/滑动）如何提升完播与互动；
> - 用 Meta 官方 creative 工具与 Playground/BeReal 风格模板生产素材；
> - 通过 Marketing API 从上传视频到投放到 Stories/Reels 版位的完整闭环；
> - 完播率、TTR（Touch/Thru-Play Rate）、互动率的衡量与调优方法论。
>
> 阅读本文前，建议先掌握 `ad_platform_api.py` 中的 `meta_create_campaign`、
> `meta_create_adset`、`meta_create_ad` 等基础方法（本文会反复引用）。

---

## 目录

1. 核心概念与架构
   - Reels vs Stories 的本质区别
   - 竖版视频（9:16）为什么是移动端的"母语"
   - 版位结构：Full-screen / Autoplay / 无缝原生
   - 广告素材生命周期 & 创意疲劳
2. 深度原理解析
   - 视频创意物理规范全表
   - 安全区（Safe Zone）与 UI 遮挡
   - 字幕编码与听障可用性（Audio-on 与静音起播）
   - 自动播放、循环与首帧逻辑
   - 互动贴纸体系：投票 / 倒计时 / 表情 / 问答 / 滑动
   - Placements 与 Advantage+ 的配合原理
   - 完播率 / TTR / 互动率的数学定义
3. 生产环境实战
   - 环境准备与认证
   - 用 Marketing API 上传视频到 advideos
   - 用 object_story_spec 创建 Reels/Stories Creative
   - 建 Campaign/AdSet/Ad 并在 Stories/Reels 版位投放
   - 互动贴纸与封面字段 via Graph API
   - Python 全流程脚本（引用脚本方法 + 新扩展方法）
   - BeReal 风格与模板创意的制作
   - 指标监控与创意疲劳轮换
4. 常见问题与排查
   - 审核被拒 / 内容政策
   - 安全区内容被 UI 遮挡
   - 字幕乱码 / 编码问题
   - 视频被裁切 / 比例错误
   - 自动播放不循环 / 静音
   - 贴纸无法生效 / native 标签
   - 完播率过低排查清单
5. 自测题

---

## 一、核心概念与架构

### 1.1 Reels 与 Stories：同源竖版，不同消费形态

很多人把 Reels 与 Stories 混为一谈，但它们面向的是**两种完全不同的用户心智**。
要写好这个垂直场景的投放策略，第一步就是把这个区别刻在脑子里：

| 维度 | Instagram Reels | Instagram Stories |
|------|-----------------|-------------------|
| 内容形态 | 公开的竖版短视频流（类似 TikTok） | 24 小时限时消失的"动态心情" |
| 消费方式 | 沉浸式无限下滑（Feed 内、Explore、Reels Tab） | 点击头像后逐条切换（顶部环形进度条） |
| 停留时长 | 用户主动进入，停留时间长，接受较完整叙事 | 用户快速切换，单条停留 0.5~8 秒 |
| 广告展示 | 可插在 Reels 流内、广告带"Sponsored"标签 | 穿插在单人 Story 序列之间 |
| 完播心态 | 愿意看完一段完整的"内容" | 期待"下一个是什么"，跳过意愿强 |
| 适合创意 | 15~60 秒，前 3 秒钩子 + 完整叙事 + 种草/转化 | 5~15 秒，单点信息，强 CTA 高频 |
| 原生感 | 几乎没有边界感，最像普通用户发的 Reel | 有明确边界，用户知道你在讲故事 |

**一句话记忆**：Reels 用户在"看内容"，Stories 用户在"走过场"。
所以 Reels 创意可以做**起承转合**，Stories 创意必须**一句话说清楚**。

> **踩坑经验（Ryan 实测）**
> 曾经把一段 30 秒带完整产品教程的 Reel 直接复用到 Stories，结果 Stories 的 TTR
> （Touch / Thru-Play Rate，触达后 3 秒/完整播放率）暴跌 60%，因为用户根本等不到
> 第 5 秒的核心信息。正确做法是：**同一主题拆两条素材**——
> Reels 版讲完整故事，Stories 版只讲"痛点 + 一个钩子 + CTA"。

### 1.2 竖版视频（9:16）为什么是移动端的"母语"

人类双手握持手机时，屏幕是竖的。Instagram/Reels/TikTok 用九年时间把用户训练成
"**竖着看、拇指动、不自拍、不带耳机**"的信息消费习惯。于是竖版视频成为一种
**内容方言**：

```text
手机持有方式 (竖握)
      │
      ▼
┌──────────────────┐
│   9 : 16 视觉      │  1080 x 1920 px
│   全屏沉浸          │  覆盖整个屏幕，无黑边
│   thumb 右侧热区    │  点赞/评论/收藏/分享常驻右侧
└──────────────────┘
      │
      ▼
用户预期区间
   ├─ 全屏、无边框、原生
   ├─ 自动播放、无声起播（须靠字幕）
   └─ 快速给答案，否则划走
```

**为什么必须竖版而不是裁剪成竖版：**
- 横版（16:9）内容直接放进 9:16 容器会上下留黑边（信箱效应），观感廉价；
- 竖版内容在竖版版位下**信息密度更高**，同一屏能装下更多主体；
- 算法对"为版位原生制作的素材"有质量识别，竖版 9:16 在 Reels/Stories 有更好的分发与
  更低的 CPM（因为完播、互动更好，竞价效率高）；
- 9:16 在用户心理上等同"真实 UGC"，比广告味十足的横版更易获得信任。

**竖版优化（Vertical Video Best Practices）的三大支柱：**

```text
竖版优化三支柱
├─ ① 构图：主体居中偏上，避开安全区/UI
│     └─ 人脸/产品中心点放在"黄金安全区"（见 2.2）
├─ ② 节奏：前 3 秒钩子，信息按"秒"排布
│     └─ 0-1s 强钩子 → 2-3s 问题 → 4-8s 解决方案 → 末 2s CTA
└─ ③ 感官：无声可懂（字幕）+ 有声惊艳（音效/原声）
      └─ 字幕随动、大而清晰、对比度足够
```

### 1.3 版位结构：Full-screen / Autoplay / 无缝原生

Reels 与 Stories 版位有一些**广告商必须尊重的底层约束**，这就是"版位特点"：

**A. 全屏（Full-screen）**
- 素材占据整个屏幕，无左右留白；
- 固定到右下/右下的 UI（点赞、评论、算号/emoji 雷球、分享）会叠加在素材顶部；
- 因此素材的**边缘 5%~15%**是"被遮挡高风险区"，这也是安全区理论的来源。

**B. 自动播放（Autoplay）**
- 用户进入即播放，**无等待、无点击**；
- 默认**静音起播**，用户点屏幕才出声（个别地区/机型可能有声，但绝不能依赖）；
- 首 3 秒若抓不住，用户直接划走，等于花了一次展示费用换 0 完播；
- 视频通常**循环播放**，但循环不能缓解"开头无钩子"的问题。

**C. 无缝原生（Seamless Native）**
- Reels 广告被设计得"看起来像普通 Reel"，原生感越强越不被跳过；
- 过度品牌化、硬广开场会让用户立刻识别 → 跳出；
- 与 UGC 风格（手持、自然光、滤镜真实）一致的广告完播更好；
- 广告带 `Sponsored` 标签，但**内容本身应像创作者产出**。

**版位 vs 频道的示意：**

```text
版位矩阵（Placement Level）
┌────────────────────────────────────────────────────┐
│  Facebook  │  Instagram    │  Messenger │ Audience  │
│            │               │            │  Network  │
├────────────┼───────────────┼────────────┼───────────┤
│ Feed       │ Feed          │ 收件箱     │  手机应用  │
│ Reels      │ Reels Tab     │  故事/气泡  │  应用内    │
│ Stories    │ Stories       │  赞助消息   │  (横幅/插屏)│
│ In-Stream  │ Explore       │            │            │
│ Video      │ Search        │            │            │
└────────────┴───────────────┴────────────┴───────────┘
              ▲
              └── 本深文档聚焦的竖版版位（Reels / Stories）
```

### 1.4 广告素材生命周期与创意疲劳（Creative Fatigue）

聪明的竖版投放，像管理一支"内容军队"，而不是"单条广告"：

```text
素材生命周期
┌──────────┐    ┌───────────┐    ┌───────────┐    ┌──────────┐
│ 生产/上传  │──▶│ 验证/上线   │──▶│ 起量/猛跑  │──▶│ 疲劳/掉量 │
│ (Creative)│    │ (审核通过) │    │ (CPM最优) │    │ (TTR下滑)│
└──────────┘    └───────────┘    └───────────┘    └──────────┘
                                                            │
                                                            ▼
                                                      换新创意 / 刷新
```

**创意疲劳（Creative Fatigue）**指同一素材长期高频展示后，用户开始划走或忽略，
表现为 **TTR/CTR 下降、CPM/CVR 变差**。

- 判断阈值常用：**同一创意 7 天累积频率 > 3~4 次** 且 **TTR 连续 2 天下滑 > 15%**；
- 竖版素材的生产成本低、迭代快，所以**"多素材轮换"是标配**；
- 常用策略：
  - **动态素材（OOE，Optimized Conversions / 动态创意）**：1 广告内放 2~5 段视频 +
    多文案，让系统自动组合分发；
  - **素材疲劳检测**：用 Insights 的 `video_thruplay_watched_actions` 和深度看板监控；
  - **预算重分配**：高 TTR 素材加量，低 TTR 素材下线或换受众。

> **Ryan 的素材轮换节奏建议（Reels/Stories 竖版）**
> - 每次上线 **3~5 条不同角度**的竖版创意（如：痛点开场 / 教程式 / 对比式 / 用户证言 / 折扣式）；
> - 每 **3~5 天**巡检一次 TTR & 完播率；
> - 单创意频率超阈值即暂停，用预算洗澡（Budget Pacing）保障新创意测试量。

---

## 二、深度原理解析

> 本部分是本文档的**重点**。所有数值均为 Meta 官方公开推荐规格，建议直接对照执行。

### 2.1 视频创意物理规范全表（Reels & Stories）

Meta 对 Instagram Reels / Stories 广告的视频素材给出以下推荐规格。
**投完播、投 CPM**，最好直接按"推荐值"交付，不要压着"最小值"做。

| 参数 | Instagram Reels 推荐 | Instagram Stories 推荐 | 硬性下限/上限 |
|------|--------------------|----------------------|---------------|
| 宽高比（Aspect Ratio） | 9:16（也支持 16:9、1:1、4:5） | 9:16（主推） | 9:16 |
| 分辨率（Resolution） | 1080 x 1920 px | 1080 x 1920 px | ≥ 720p；建议 1080p |
| 视频时长 | 最多 90 秒（推荐 15~45 秒） | 最多 60 秒（推荐 5~15 秒） | Reels ≤ 90s；Stories ≤ 60s |
| 视频格式 | MP4、MOV | MP4、MOV | MP4/MOV |
| 文件大小 | ≤ 4GB（长视频建议更小） | ≤ 4GB | ≤ 4GB |
| 帧率（Frame Rate） | 30 fps（首选），支持 60 fps | 30 fps（首选） | 最高 60 fps |
| 码率（Bitrate） | 建议 8 Mbps 以上 | 建议 8 Mbps 以上 | 越高越清晰 |
| H.264 / H.265 | H.264（兼容性最好） | H.264（兼容性最好） | 建议 H.264 |
| 像素宽高比 | 1:1（正方形像素） | 1:1（正方形像素） | 1:1 |
| 音频编码 | AAC（48 kHz 立体声） | AAC（48 kHz 立体声） | AAC |
| 封面图（Cover Image） | 可指定，用于分享/预览 | 可指定 | JPEG/PNG |
| 竖版安全区 | 上下留 14%（见 2.2） | 上下留 14%（见 2.2） | 至少 8% |

**逐条说明：**

1. **分辨率 1080 x 1920 (9:16)**：这是当前 Instagram 竖版的标准输出尺寸。
   低于 720p 会在全屏放大后糊掉，算法对低清晰度素材的推荐分也会下降。

2. **时长上限**：Reels 广告最长 **90 秒**，Stories 广告最长 **60 秒**。
   但**时长 ≠ 优势**：完播率是核心权重指标，越长越难完播，所以：
   - Reels：把"完整故事"压到 **15~30 秒**（足够讲透一个卖点）；
   - Stories：压到 **5~15 秒**（只讲一个点）。

3. **文件大小 ≤ 4GB**：这是 Graph API 上传 `advideos` 的硬上限。
   生产环境建议：**1080p、H.264、30fps、8Mbps 左右的 MP4** 通常在数十 MB 到两三百 MB，
   远低于 4GB，且转码压力小、出片快。

4. **帧率**：**30 fps 是高性价比之选**。60 fps 运动更流畅、适合高频画面，
   但体积更大、转码更慢，且多数手机/低配机上 60 与 30 观感差异不大，成本却更高。

5. **码率**：8 Mbps 是 1080p 竖版的稳妥起点。要极致清晰（含大量细节/字幕）可到 12 Mbps，
   Story 这类快速划过的内容 5~6 Mbps 也完全够用。

6. **音频**：AAC + 48 kHz 立体声。注意：**不要在视频里外挂音轨**，直接内嵌 AAC 即可。
   若用手机竖拍，注意别把环境音录得太乱。

> **踩坑经验（码率与体积）**
> 一次用非常高的 4K/高码率源片直接上传，文件 3.8GB 勉强通过，但转码超过 20 分钟，
> 创意迟迟无法进入投放队列，白白浪费了开测窗口。**建议交付前用 ffmpeg 统一二次压制**
> （见 2.1.1 的 ffmpeg 命令），既控制体积又保证兼容。

#### 2.1.1 交付前的 ffmpeg 统一压制（生产环境必备）

```bash
# 把任意源视频转成适合 Reels/Stories 投放的规格
ffmpeg -i input.mov \
  -vf "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black" \
  -r 30 \
  -c:v libx264 -profile:v high -level 4.2 -preset medium -crf 20 \
  -pix_fmt yuv420p \
  -c:a aac -b:a 192k -ar 48000 -ac 2 \
  output_9x16.mp4
```

- `scale + pad`：把任意比例内容**智能适配**到 1080x1920（裁剪或加黑边，建议用 crop 更干净）；
- `-r 30`：统一 30fps；
- `-profile high -level 4.2`：兼容主流播放器；
- `-crf 20`：高画质（越低越清晰，18~23 区间）；
- `-pix_fmt yuv420p`：H.264 兼容性最佳（否则 Safari/部分播放器出错）；
- `-c:a aac -b:a 192k`：内嵌高质量 AAC 音频。

> 若源本身已是 9:16，用 `crop=1080:1920` 直接居中裁剪即可，避免 pad 黑边。
> 公式：`crop=1080:1920:(in_w-1080)/2:(in_h-1920)/2`

**用脚本方法确认"当前账号可用的视频尺寸规格"：**

```python
# ad_platform_api.py 已实现：meta_list_video_sizes
sizes = client.meta_list_video_sizes()
for s in sizes:
    print(s.get("name"), s.get("width"), s.get("height"), s.get("ratio"))
# 期望输出类似：
#   Instagram Reels  1080 1920 9:16
#   Instagram Stories 1080 1920 9:16
#   Feed 竖版        1080 1920 9:16
```

### 2.2 安全区（Safe Zone）与 UI 遮挡

竖版广告最大的"隐形杀手"是**平台 UI 叠在素材上**。右边的互动按钮、底部文案
（Stories 的 TAP TO VIEW / Reels 的 caption）、顶部状态栏都会遮挡素材边角。
所以没有"整块屏幕都能放重要信息"这回事。

```text
9:16 全屏素材 1080x1920 的安全区示意（俯视比例）

┌─────────────────────────────────────────────────────┐  ─┐
│                                                     │   │
│      ▲ 顶部 UI 区：状态栏 / 时间 / 电池 / Story Ring │   │
│      └─────────── 约顶部 8%~14% ────────────         │   │
│                                                     │   │
│  ┌───────────────────────────────────────────────┐  │   │
│  │                                               │  │   │
│  │        ▲ 核心安全区 (Center Safe Area)         │  │   │
│  │   ┌─────────────────────────────────────────┐  │  │   │
│  │   │                                         │  │  │   │
│  │   │     主体/人脸/文字/字幕 放这里           │  │   │  140%
│  │   │     水平留白足够 (边距 ≥ 92px)           │  │  │  (安全)
│  │   │                                         │  │  │   │
│  │   └─────────────────────────────────────────┘  │  │   │
│  │        ▼ 右缘被遮挡：点赞/评论/收藏/分享/算号  │  │   │
│  │       (右侧约 8%~12% 为 UI 热区)              │  │   │
│  └───────────────────────────────────────────────┘  │   │
│                                                     │   │
│  ◄ 左缘：用户名/头像/Follow、碟形进度(Stories)      │   │
│  ░▒▓ 底部：文案 Caption、CTA、TAP TO (Stories)      │   │
│  └─────────────── 约底部 14%~18% ─────────────────  │   │
│                                                     │   │  ─┘
└─────────────────────────────────────────────────────┘
```

**安全区经验法则（Efficiency / 宽容版）：**

| 区域 | 建议预留 | 放什么 |
|------|---------|--------|
| 顶部 | 8%~14% | 不放关键信息，或只在很短时刻露一下 Logo |
| 底部 | 14%~18% | 字幕最后一行、CTA 之外一律不放；避免被 caption 盖住 |
| 右侧 | 8%~12% | 不做互动按钮图标；重要主体向左偏 10% |
| 左侧 | 8% | 用户名/头像区域，可放轻微水印但别放按钮 |
| 中央核心 | 约 60%~70% | **所有关键信息的主战场** |

**为什么"中央安全区"是黄金位置：**
- 竖握时控件都在边缘，中央是唯一"必然可见"区域；
- 用户视线先落中央再扫边缘，第一秒钩子放中央命中率最高；
- 字幕建议放在**中部偏下的安全区内**（而非贴底，贴底会被 caption 顶掉）。

> **踩坑经验（字幕被 CTA 顶掉）**
> 初版把字幕压在画面最底部 6%，上线后发现 Stories 版位底部有
> 「TAP TO VIEW 查看更多」的 CTA 条，把最后一行字幕完全盖住。
> 修复：把字幕统一上移到**画面垂直 72%~84% 区间**，并给字幕加 6px 描边/阴影，
> 保证在任何版位、任何 UI 形态下都可读。

### 2.3 字幕编码与"静音起播"可用性（Captions & Audio-Off）

自动播放默认**静音**，这是全屏消费的第一现实。因此**字幕不是锦上添花，而是必需品**。

**字幕最佳实践：**

```text
字幕规范
├─ 风格：大字号、高对比、带描边/半透明底
│     白字+黑描边（或黑字+白底）在白/动态背景上均可读
├─ 长度：每屏 ≤ 3~4 个词（约 12~20 字符），随画面节奏推进
├─ 位置：画面垂直 72%~84%，避开底部 CTA 与右侧 UI
├─ 语法：按"语义块"断句，不要整句堆一行
├─ 高亮：动词/卖点词标色（黄/绿）引导视线
└─ 时刻：严格与口播/画面同步，不提前不滞后
```

**React 视频的"同步字幕 vs 硬字幕"：**
- **硬字幕（Burn-in）**：渲染进画面，任何播放器都显示 —— 推荐广告用，可控、无兼容问题；
- 烧录时注意：字幕占画面比例别超约 1/6，避免喧宾夺主。

**常见编码坑（重要）：**

| 症状 | 根因 | 解法 |
|------|------|------|
| 中文字幕显示为 `???` 或乱码 | 导出时用了非 UTF-8 / 字体缺失 | 导出设 UTF-8；用系统自带中文字体（思源黑体/苹方/微软雅黑） |
| 字幕出现"豆腐块" | 视频容器/转码器不支持该字体 | 保证导出端与投放端字体一致；必要时烧录成图片字幕 |
| 字幕比画面早/晚 0.3s | 时间轴微偏移 | 导出前核对音画同步，ASR 自动字幕常需手动微调 |
| 手机静音后完全看不懂 | 只依赖口播无字幕 | 一律烧录硬字幕 |

### 2.4 自动播放、循环与首帧逻辑

- **自动播放**：进入即播，无需点击。对广告商而言这是"零门槛触达"，也是"首屏即生死"。
- **静音起播**：默认无声（手机在静音模式或系统默认），用户点屏幕才出声。
  所以创意必须"**无声可懂**"（靠字幕/画面叙事）+"有声更佳"（音频是加分项）。
- **循环播放（Loop）**：Reels/Stories 广告通常循环。循环能自然衔接首尾——
  若视频首尾能"无缝衔接"（如尾部画面回到片头），可提升完播与重复观看观感。
- **首帧（First Frame）**：用户划入瞬间看到的那一帧。首帧出现在加载/暂停时。
  建议把首帧设计成"信息钩子"，而不是黑场或公司 Logo 大特写。

```text
首 3 秒心理学
┌─────┬─────┬─────┬───────────────────────┐
│ 第1秒│ 第2秒│ 第3秒│ 之后                  │
├─────┼─────┼─────┼───────────────────────┤
│ 强钩子│ 引出问题│ 给出方法│ 展开讲 + CTA     │
│ 视觉突变│ 点名受众 │ 第一版方案 │ 证据/教程/折扣 │
└─────┴─────┴─────┴───────────────────────┘
  "你在为 X 烦恼吗？" → "其实只要 Y 步" → 演示
```

> **踩坑经验（首帧黑场之痛）**
> 某素材开头有 0.8s 的淡入黑场，Reels 上完播率表现平平；去掉黑场、把兴奋点调到第 1 帧后，
> 同素材 TTR 提升约 22%。**首帧 = 钩子，而不是过场。**

### 2.5 互动贴纸体系（Interactive Stickers）

Stories 与 Reels 都支持在**创作者原生内容**里叠加互动贴纸。广告侧有两种贴纸处理路径：

```text
贴纸的两种路径
├─ ① 平台原生贴纸（Native Sticker）：在 Instagram App 内、或用官方工具为
│      Reel/Story 添加（投票/倒计时/表情滑杆/问答），发布为原生内容后转广告
│      → 广告展示时贴纸保留，带「Sponsored」标签，互动最高
└─ ② 广告素材内"伪贴纸"：直接在视频画面里画一个"投票"/"滑动"图形
      → 只是视觉元素，不产生真实互动，但能让用户产生"点一下"的心理暗示
```

**五类互动贴纸逐一拆解：**

**A. 投票贴纸（Poll Sticker）**

```text
┌───────────────────────────┐
│  ❓ 你会尝试这个新口味吗？      │
│  [A] 必须的，先来一箱          │
│  [B] 好奇，再观察一下          │
└───────────────────────────┘
```
- 用法：用"二选一"给用户一个低成本的参与入口；投票结果是一种即时消费者洞察；
- 广告价值：**显著提升互动率与停留时长**，让用户"参与"而非"观看"；
- 注意：广告内贴纸需在**启示（tease）后马上给到**，别拖到视频后半段才出现。

**B. 倒计时贴纸（Countdown Sticker）**

```text
┌───────────────────────────┐
│  ⏳ 新品发售倒计时            │
│  ╔═══════════════╗          │
│  ║   剩 01 : 12  ║          │
│  ╚═══════════════╝          │
└───────────────────────────┘
```
- 用法：制造紧迫感与"到时候回来看"的理由，适合上新/限时折扣/直播预告；
- 广告价值：将"现在看到"转化为"未来回来"，利于重定向用户池的积累。

**C. 表情滑杆贴纸（Emoji Slider）**

```text
┌───────────────────────────┐
│  ❤ 你对这个效率工具心动吗？      │
│  ─────────●──────────────  │
└───────────────────────────┘
```
- 用法：用"滑动"收集好感度，比投票更细腻，能看分布；
- 广告价值：滑杆本身就是一种"已看见并参与"的信号，利于后续重定向与 lookalike 种子。

**D. 问答贴纸（Questions Sticker）**

```text
┌───────────────────────────┐
│  「你最想了解哪个功能？」        │
│  在下方输入你的问题……           │
│  ✏ 输入回答                    │
└───────────────────────────┘
```
- 用法：开放式收集问题/需求，成本略高（要打字），但数据最鲜活；
- 广告价值：适用于教育/咨询/高客单，能拿到真实痛点，之后可做 FAQ 素材。

**E. 滑动贴纸（Swipe-able / Links 贴纸，Stories 经典）**

```text
┌───────────────────────────┐
│                            │
│   (内容)                    │
│                            │
│  ◄───────────────────────── ►│
│   「查看更多」向上滑           │
└───────────────────────────┘
```
- Stories 的"上滑查看更多"已是基因；Reels 用"看评论置顶链接/主页链接"等；
- 广告价值：是一种 CTA 引导，把"看完"转化为"点进"。

> **原生 vs 伪贴纸的关键结论**
> 若目标是**真互动数据**（参与率、投票结果、滑杆分布），必须用**平台原生贴纸**
> （App 内或官方 creative 工具添加），发布后再投放；仅靠视频里画贴纸图形，
> 只能制造"参与感"的视觉暗示，拿不到真实互动事件。区分方式见 2.5 的路径图。

### 2.6 Advantage+ Placements 与 Reels/Stories 的配合

**Advantage+ Placements（自动版位/原 Advanced Automatic Placements）** 让 Meta 自动把
广告投放到最能满足优化事件的版位组合里。竖版素材如何与它配合？

```text
Advantage+ Placements 决策逻辑（简化）
┌──────────────────────────────────────────────┐
│  优化事件（如 Purchase）驱动                      │
│      │                                        │
│      ▼                                        │
│  预测各版位组合的预期回报                          │
│   ├─ IG Reels / IG Stories / FB Reels ...      │
│  ─┤─ Feed / Marketplace / Audience Network ... │
│      └─ 分配预算到最可能转化的版位                  │
└──────────────────────────────────────────────┘
```

**配合要点：**

| 要点 | 说明 |
|------|------|
| 素材比例 | 交给系统组合，但**提供竖版 9:16 素材**可显著加分（Reels/Stories 的主比例） |
| 最能受益 | 希望"省钱高效"时用 Advantage+ Placements，让系统找最佳版位 |
| 版位控制 | 若只想要竖版版位，可**手动限制版位**排除不想要的（如 Audience Network） |
| 素材多样性 | 多素材 + 多比例更利于系统匹配不同版位，竖版素材是 Reels/Stories 的硬通货 |
| 与应用事件 | 用 `video_thruplay_watched_actions` 等信号优化，系统会更偏好竖版高完播素材 |

**什么时候手动指定版位 vs 用 Advantage+：**

```text
选择版位策略
├─ 手动固定 Reels/Stories 版位（不用 Advantage+）
│   └─ 目的：专测竖版创意、品牌形象统一、只在 IG 全屏触达
├─ Advantage+ Placements + 竖版素材
│   └─ 目的：最大化转化量、自动化分配预算、A/B 少管
└─ 混合：Campaign 层用 Advantage+，但 AdSet 层保留竖版素材为主
```

> **Ryan 建议**
> 新手起步：用手动版位固定 IG Reels + IG Stories，把竖版素材的效果测清楚；
> 跑通后再切 Advantage+ Placements 放量。不要把"测试没跑明白"的素材直接丢进自动版位。

### 2.7 衡量指标：完播率、TTR、互动率的数学定义

竖版投放要盯的核心指标，这里给出**精确的统计口径**（来自 Insights 字段）：

| 指标 | 字段 | 定义 | 竖版健康基准（参考） |
|------|------|------|-------------------|
| 展示量 | `impressions` | 广告展示次数 | - |
| 触达 | `reach` | 看到广告的唯一用户数 | - |
| 点击数 | `inline_link_clicks` | 点击落地页/CTA 次数 | - |
| Tap/Continue | `inline_post_engagement` | 帖子互动（Reels/Story 的镜头级互动） | - |
| **3 秒播放** | `video_3_sec_watched_actions` | 播放满 3 秒的次数 | 占比 > 55% 佳 |
| **完播率（ThruPlay）** | `video_thruplay_watched_actions` | **完整播放**次数（或广告定义阈值） | 越高越好，别低于 25% |
| **TTR（Touch/ThruPlay Rate）** | `video_thruplay_watched_actions / impressions` | 完播次数 ÷ 展示量 | Reels 20%~60%（受素材/受众影响大） |
| **互动率（Engagement Rate）** | `post_engagements / impressions` | 点赞评论分享等 ÷ 展示 | 竖版原生素材更高 |
| **完播率（完成率）** | `video_p75_watched_actions` 等 | 播放到 75%/95% 的占比 | 看分布 |
| 平均观看时长 | `video_avg_time_watched_actions` | 平均看完的秒数 | 与素材时长对比 |
| CPA/CPM/CTR | - | 转化/千次/点击 | 常规 |

**TTR 为什么是竖版第一指挥棒：**
- TTR = 完整播放次数 / 展示量，直接反映"内容是否留人"；
- 竖版全屏、自动播放的场景里，**完播 = 用户认可**，算法把它当强正信号；
- TTR 高 → 系统判定素材质量好 → 分到更多与更便宜的流量 → CPM 下降。

```text
用 TTR 给素材分档
├─ TTR ≥ 55%：强烈留人，加量放大（若 CVR 尚可）
├─ TTR 30%~55%：正常区间，继续跑，观察互动/转化
├─ TTR 15%~30%：留人一般，重点查开头 3 秒与匹配度
└─ TTR < 15%：严重掉人，换创意或换受众，别硬撑
```

> **注意（重要口径）**
> Graph API 里 `video_3_sec_watched_actions` 与 `video_thruplay_watched_actions`
> 返回的是**事件数组**，需要按 value 维度求和再与展示量相除，才是真正意义上的"率"。
> 见 3.7 的 Python 计算示例。

---

## 三、生产环境实战

> 本部分是本文档的**另一重点**。从环境准备到全流程落地，全部给到可直接套用的代码。
> 前提：已通过 `ad_platform_api.py` 完成 Meta OAuth 与账号初始化（`meta_auth`）。

### 3.1 环境准备与初始化

```python
# ad_platform_api.py 使用示例（伪代码接口语义已由脚本实现）
from ad_platform_api import AdPlatformAPI

client = AdPlatformAPI()
# Meta OAuth（脚本已封装 meta_auth，含 access_token 管理）
client.meta_auth()

# 拿到账号树，锁定投放账号 ID（形如 act_1234567890 或 1234567890）
accounts = client.meta_list_accounts()
for acc in accounts:
    print(acc.get("id"), acc.get("name"))
# act_1234567890  Main Business Account  ...

ACCOUNT_ID = "act_1234567890"
```

**关键对象 ID：**
- `ACCOUNT_ID`：广告账号（Ad Account），形如 `act_XXXXXXXXXXXXXXXX`；
- `PAGE_ID`：你的 Instagram/Facebook 主页（发布 Reels 需要绑定主页）；
- `IG_USER_ID`：Instagram 商业号 ID（`instagram_actor_id`，Creative 里用得着）；
- `PIXEL_ID / CAPI`：转化追踪（本文以转化指标为例说明字段，深讲见 Pixel/CAPI 文档）。

### 3.2 用 Marketing API 上传视频到 `advideos`

上传视频是 Reels/Stories 广告的第一步：视频先存到账号的媒体库，拿到 `video_id`，
之后 Creative 才能引用。

**curl 示例：**

```bash
# 上传一个 9:16 竖版视频到广告账号媒体库
curl -X POST \
  "https://graph.facebook.com/v19.0/{ACCOUNT_ID}/advideos" \
  -F "access_token={ACCESS_TOKEN}" \
  -F "file=@/path/to/vertical_9x16.mp4" \
  -F "title=IG Reels 竖版素材 - 新品首发" \
  -F "description=9:16 竖版视频，主打首屏钩子与完播" \
  -F "thumb={COVER_IMAGE_ID}" \
  -F "unpublished_content_type=AD" \
  -F "upload_phase=finish" \
  -F "file_size={BYTES}" \
  -F "start_offset=0"

# 响应示例（节选）
# {
#   "id": "video_9876543210",
#   "post_id": null,
#   "status": {
#     "video_status": "ready"      # 上传成功，可被 Creative 引用
#   }
# }
```

> 说明：`file` 是分片/直传的参数；用 SDK 时可用 `VideoUploader`。上传后轮询
> `/{video_id}?fields=status.video_status` 到 `ready` 再建 Creative。

**Python 端扩展方法（脚本已有 meta_list_video_sizes；这里给出上传能力的合理扩展设计）：**

```python
def meta_upload_video_creative(self, account_id: str, file_path: str,
                               title: str = "", description: str = "",
                               cover_image_id: str = None, **kwargs) -> Dict:
    """
    【扩展】上传竖版视频到广告账号媒体库，返回可被 Creative 引用的 video_id。
    """
    import requests
    token = self.credentials.get("meta", {}).get("access_token", "")
    url = f"https://graph.facebook.com/v19.0/{account_id}/advideos"
    params = {
        "access_token": token,
        "title": title,
        "description": description,
        "unpublished_content_type": "AD",
    }
    if cover_image_id:
        params["thumb"] = cover_image_id
    data = {}
    files = {"file": (file_path.split("/")[-1], open(file_path, "rb"),
                      "video/mp4")}
    resp = requests.post(url, params=params, files=files, timeout=300)
    resp.raise_for_status()
    result = resp.json()
    return {"video_id": result.get("id"), "status": result.get("status")}


# 用法
video = client.meta_upload_video_creative(
    ACCOUNT_ID,
    "/path/to/vertical_9x16.mp4",
    title="IG Reels 首屏钩子素材 v3",
    description="9:16 竖版，字幕烧录，30fps",
)
VIDEO_ID = video["video_id"]
print("已上传 video_id:", VIDEO_ID)
```

**如何用脚本方法校验"这个账号到底支持哪些视频尺寸/版位"：**

```python
# 校验尺寸规格（meta_list_video_sizes 已实现）
for size in client.meta_list_video_sizes():
    print(size.get("name"), size.get("width"), size.get("height"))

# 校验可投版位（meta_list_placements 已实现）
placements = client.meta_list_placements()
for p in placements:
    print(p.get("key"), p.get("name"))
# 重点关注 instagram_reels / instagram_stories / instagram_explore
```

### 3.3 用 `object_story_spec` 创建 Reels/Stories Creative

Creative 是广告的"素材容器"。对于 Reels/Stories 竖版视频广告，核心是把
`video_id` 塞进 `object_story_spec`，并声明：
- `video_data`：包含 `video_id`；
- `format`：声明素材比例（`VIDEO_REELS` 等，或用 `image_crops` 指定 9:16）；
- 视觉：`link`、`message`、`call_to_action`（CTA）；
- 竖版/原生：让系统明白这是竖版素材以便匹配 Stories/Reels 版位。

**Graph API 创建 Creative 的核心字段：**

```bash
curl -X POST \
  "https://graph.facebook.com/v19.0/act_{ACCOUNT_ID}/adcreatives" \
  -F "access_token={ACCESS_TOKEN}" \
  -F "name=IG Reels 竖版 Creative" \
  -F "object_story_spec={
         \"page_id\": {PAGE_ID},
         \"instagram_actor_id\": {IG_USER_ID},
         \"video_data\": {
             \"video_id\": {VIDEO_ID},
             \"image_url\": \"...\",
             \"call_to_action\": {
                 \"type\": \"LEARN_MORE\",
                 \"value\": { \"link\": \"https://example.com/landing\" }
             }
         },
         \"link_data\": {
             \"link\": \"https://example.com/landing\",
             \"message\": \"竖版新品，前 3 秒让你看懂\"
         }
       }" \
  -F "degrees_of_freedom_spec={...}" 

# 响应
# { "id": "creative_...." }
```

> **重点字段解读：**
> - `object_story_spec.video_data.video_id`：必填，指向上传的 video；
> - `instagram_actor_id`：指定用哪个 Instagram 商业号身份发布/展示；
> - `format`（或 `image_crops` 的 9:16）：声明视频比例，避免被系统误解裁切；
> - `call_to_action.type`：可用 `LEARN_MORE`、`SHOP_NOW`、`BOOK_TRAVEL`、`SIGN_UP` 等
>   （可用脚本 `meta_list_call_to_action_types()` 枚举）；
> - `object_story_spec.link_data`：Reels 广告常需要跳转落地页，需给 link。

**Python 端（脚本已有 meta_list_creatives / meta_get_creative，此处用 meta_create_ad 内嵌 creative 或扩展）：**

```python
def meta_create_ad_creative(self, account_id: str, name: str, video_id: str,
                            page_id: str, ig_user_id: str, link: str,
                            message: str = "", cta_type: str = "LEARN_MORE",
                            **kwargs) -> Dict:
    """
    【扩展】为 Reels/Stories 竖版视频创建 advertisement creative。
    返回 creative id，供 meta_create_ad 引用。
    """
    import requests
    token = self.credentials.get("meta", {}).get("access_token", "")
    object_story_spec = {
        "page_id": page_id,
        "instagram_actor_id": ig_user_id,
        "video_data": {
            "video_id": int(video_id),
            "call_to_action": {
                "type": cta_type,
                "value": {"link": link},
            },
        },
        "link_data": {"link": link, "message": message},
    }
    url = f"https://graph.facebook.com/v19.0/{account_id}/adcreatives"
    params = {"access_token": token, "name": name,
              "object_story_spec": json.dumps(object_story_spec)}
    resp = requests.post(url, params=params, timeout=60)
    resp.raise_for_status()
    return resp.json()


CREATIVE_ID = client.meta_create_ad_creative(
    ACCOUNT_ID, "Reels 竖版创意 - 教程式",
    video_id=VIDEO_ID, page_id=PAGE_ID, ig_user_id=IG_USER_ID,
    link="https://example.com/product",
    message="三步搞定，看完就会。",
    cta_type="LEARN_MORE",
)["id"]
print("Creative ID:", CREATIVE_ID)
```

**用 `meta_list_creatives` 校验已建素材：**

```python
creatives = client.meta_list_creatives(ACCOUNT_ID)
for c in creatives:
    cid = c.get("id")
    detail = client.meta_get_creative(cid)
    obj = detail.get("object_story_spec", {})
    vdata = obj.get("video_data", {})
    print("创意:", cid, "| video_id:", vdata.get("video_id"),
          "| cta:", detail.get("object_story_spec", {}).get("call_to_action_type"))
```

### 3.4 建 Campaign / AdSet / Ad 并在竖版版位投放

**Step 1 —— 建 Campaign（目标：videos / conversions 等）：**

```python
campaign = client.meta_create_campaign(
    ACCOUNT_ID,
    "IG 竖版 Reels 2026-08 新品",
    objective="CONVERSIONS",             # 或 VIDEO_VIEWS / REACH / OUTCOME_TRAFFIC
    status="PAUSED",                     # 先停，配置完再激活
    special_ad_categories=[],
)
CAMPAIGN_ID = campaign["id"]
print("Campaign ID:", CAMPAIGN_ID)
```

**Step 2 —— 建 AdSet（关键：竖版版位、预算、受众）：**

```python
adset = client.meta_create_adset(
    CAMPAIGN_ID,
    "Reels-Stories 竖版-高意向受众",
    budget=50000,                        # 单位：分（即 $500）/日，或 lifetime_budget
    bid_strategy="LOWEST_COST_WITHOUT_CAP",
    optimization_goal="OFFSITE_CONVERSIONS",   # 以转化为优化目标
    billing_event="IMPRESSIONS",          # 竖版展示计费
    targeting={
        "geo_locations": {"countries": ["US"]},
        "age_min": 18, "age_max": 45,
        "interests": [{"id": "6003139266460", "name": "Fitness"}],
        "publisher_platforms": ["instagram"],       # 只投 IG
        "facebook_positions": [],                   # 空
        "instagram_positions": [
            "insta_reels", "insta_stories", "insta_explore",
        ],                                          # ★ 竖版版位
    },
    # 或用 Advantage+ Placements（adv_placements）让系统自动分配
    # advantage_placements=True,
    status="PAUSED",
)
ADSET_ID = adset["id"]
print("AdSet ID:", ADSET_ID)
```

> **版位声明的两种方式：**
> - 手动声明 `instagram_positions: ["insta_reels", "insta_stories", "insta_explore"]`
>   → 确定性投竖版；
> - 用 Advantage+ Placements（`advantage_placements=True`）
>   → 让系统在全部版位里自动选最优（配合竖版素材效果最佳）。
>
> `insta_reels` / `insta_stories` / `insta_explore` 是 IG 竖版版位在 Targeting 里的键名，
> 可用脚本 `meta_list_placements()` 枚举确认。

**Step 3 —— 建 Ad（引用 Creative）：**

```python
ad = client.meta_create_ad(
    ADSET_ID,
    "Reels 创意-教程式-CTA学更多",
    creative={"creative_id": CREATIVE_ID},
    status="PAUSED",
)
AD_ID = ad["id"]
print("Ad ID:", AD_ID)

# 核验
for a in client.meta_list_ads(ADSET_ID):
    print(a.get("id"), a.get("name"), a.get("status"))
```

**Step 4 —— 激活并监控：**

```python
# 脚本有 update/pause/resume 方法，激活顺序：Campaign → AdSet → Ad
client.meta_update_campaign(CAMPAIGN_ID, status="ACTIVE")
client.meta_update_adset(ADSET_ID, status="ACTIVE")
client.meta_update_ad(AD_ID, status="ACTIVE")
```

### 3.5 互动贴纸 & 封面在构建中的应用

**封面（Cover / thumb）**：上传 `advideos` 时用 `thumb` 指定封面图，或建 Creative 时
用 `object_story_spec.video_data.image_url` 指定。

**原生贴纸**：贴纸必须在 **Instagram App 内**（或官方 creative 工具）创建 Reel/Story 时添加，
再通过"把原生 Post 转为广告（Boost/使用 post_id 建广告）"或 Spark Ads 的方式投放。
Marketing API 无法给一段普通上传的视频凭空"加贴纸"——贴纸是**内容属性**，不是素材字段。

```text
贴纸落地到广告的两种工程路径
├─ 路径A（原生转广告）
│   在 IG App 用 [投票/倒计时] 发一条原生 Reel → Boost 或引用该 post_id 建广告
│   → 贴纸保留、可收集真实互动事件
└─ 路径B（Spark Ads 创客广告）
      把目标 Reel 通过 Spark Ads 推广，原生贴纸一并展示
```

**代码层面的"贴纸即互动信号"如何体现：** 投放后可在 Insights 里看
含贴纸广告的 `inline_post_engagement`（镜头/贴纸互动）是否更高，用于对比验证。

### 3.6 BeReal 风格与模板创意的制作

**BeReal 风格**指：不假大空、随机真实瞬间、无过度修饰、手持感、双镜头（前后同框）、
自然光 —— 本质是"**真实感**"。放到竖版广告里非常吃香，因为用户已对精修广告免疫。

**BeReal 风模板结构（竖版）：**

```text
BeReal 风竖版模板
┌──────────────────────────┐
│  随机生活瞬间（真实感最强）    │
│  ├─ 手持/自然抖动轻微        │
│  ├─ 前后双摄画面（可选叠加）   │
│  ├─ 原声/环境音为主          │
│  └─ 一句话口播/文字          │
├──────────────────────────┤
│  痛点承接（2~5 秒）          │
│  └─ "我当初也这样……"         │
├──────────────────────────┤
│  产品自然出现（5~10 秒）      │
│  └─ 使用场景，不做摆拍广告感  │
├──────────────────────────┤
│  结果/证言 + 轻 CTA（末段）   │
│  └─ "想要的评论区扣1/主页链接" │
└──────────────────────────┘
```

**五种可直接套用的竖版创意模板：**

| 模板 | 结构 | 适用 |
|------|------|------|
| 痛点前置（Problem-First） | 痛点 0-1s → 方案 3-8s → 演示 → CTA | 转化/App 安装 |
| 教程式（How-To） | 结果展示 0-1s → 分 N 步 → 结束给 CTA | 教程/工具类 |
| 对比式（Before/After） | 前 1s 差 → 对比 → 后 2s 好 → CTA | 美妆/家居/健身 |
| 用户证言（Testimonial） | 用户出镜自述 → 特写产品 → CTA | 信任型/高客单 |
| 折扣/限时（Offer） | 大声量的"限时立减"0-1s → 展示 → 倒计时贴纸 → CTA | 促销 |

> **模板制作的工程提示**
> 用脚本把这些模板的素材批量上传（`meta_upload_video_creative`），
> 一次建 3~5 条不同模板的 Ad，配合 OOE 动态创意让系统自动筛选，效率最高。

### 3.7 指标监控与创意疲劳轮换（全流程 Python）

```python
def compute_thruplay_rate(account_id: str, ad_id: str) -> dict:
    """从 Insights 计算 TTR / 3s 率 / 互动率（字段为数组，需按 value 求和）。"""
    insights = client.meta_query_insights(
        account_id,
        date_preset="last_7d",
        level="ad",
        fields=[
            "ad_id", "impressions", "reach",
            "inline_link_clicks",
            "video_3_sec_watched_actions",
            "video_thruplay_watched_actions",
            "post_engagements",
            "ctr", "cpm", "cpp",
        ],
    )
    row = next((r for r in insights if r.get("ad_id") == ad_id), {})
    values = row.get("values", {})

    def _sum_events(key):
        return sum(v.get("value", 0) for v in values.get(key, []))

    imp = values.get("impressions", 0) or 0
    t3 = _sum_events("video_3_sec_watched_actions")
    tp = _sum_events("video_thruplay_watched_actions")
    eng = values.get("post_engagements", 0) or 0
    return {
        "ad_id": ad_id,
        "impressions": imp,
        "thruplay_rate": (tp / imp) if imp else 0.0,     # TTR
        "watch_3s_rate": (t3 / imp) if imp else 0.0,     # 3秒率
        "engagement_rate": (eng / imp) if imp else 0.0,  # 互动率
    }


def rotate_tired_creatives(account_id: str, ads: list, fatigue_threshold=0.15):
    """按 TTR 连续下滑比例轮换创意：低 TTR 暂停，加量高 TTR。"""
    import time
    for ad in ads:
        data = compute_thruplay_rate(account_id, ad["id"])
        if data["thruplay_rate"] < 0.15:
            client.meta_pause_ad(ad["id"])
            print(f"暂停低完播创意 {ad['id']} TTR={data['thruplay_rate']:.2%}")
        elif data["thruplay_rate"] >= 0.55:
            print(f"高完播创意 {ad['id']} TTR={data['thruplay_rate']:.2%}，建议加量")
    time.sleep(5)
```

> **监控节奏**：上线 24h 后先看一次（素材起量期），随后每日看 TTR/完播率的趋势；
> 用 `date_preset` 对比 `last_7d` 与 `last_14d` 判断是否疲劳。

---

## 四、常见问题与排查

### 4.1 审核被拒 / 内容政策（Policy）

| 症状 | 根因 | 排查/解法 |
|------|------|-----------|
| 广告被 Rejected | 素材触发内容政策（如夸张承诺、医疗、成人、误导） | 用 `meta_get_creative` 查审核状态 `creative_fingerprint`；对照 Meta 广告政策 |
| "不真实/误导" | BeReal 风做得像"承诺疗效" | 去掉绝对化词语（"最""100%""治愈"），改成可验证表述 |
| 敏感词 | 医疗/金融/政治类文案 | 规避高危行业词；用官方文案合规清单 |
| 频繁拒审 | 版权音乐/素材 | 用 Meta 素材库授权音乐；不盗用他人 Reel |
| 账号级限制 | 多次拒审导致账号风控 | 检查 account status；放慢上新频率 |

**竖版素材内容政策红线（Reels/Stories 通用）：**
- 不得声称能"治愈/预防"疾病；不得使用"最佳/第一/100%"等夸张用语；
- 不得使用未经授权的品牌、名人、版权音乐；
- 涉及金融/政治/健康需走 Special Ad Category（`special_ad_categories`）。

### 4.2 安全区内容被 UI 遮挡

**现象**：字幕/CTA 在预览里看得见，上盘后一部分被评论区按钮、caption、底部 CTA 盖住。

**排查清单：**
```text
□ 把关键信息框进"中央安全区"（垂直 30%~85%、水平留边 92px）
□ 字幕移到垂直 72%~84%，不加描边会吃亏 → 加 6px 描边/半透明底
□ 底部 14%~18% 不放任何需点击的文字
□ 右侧 8%~12% 不放按钮图标与关键信息
□ 用 Meta 的"Safe Area"模板图层（官方 creative 工具自带安全区参考）
```

### 4.3 字幕乱码 / 编码问题

**现象**：中文字幕以 `???`、乱码、豆腐块显示。

**排查：**
1. 导出字幕时确认 **UTF-8 编码**输出；
2. 使用系统自带中文字体（苹方/微软雅黑/思源黑体），避免缺失子集；
3. 若用 ASS/SRT 软字幕，投放端渲染器可能不支持 → **烧录成硬字幕**最稳；
4. 检查视频容器的字体嵌入（Burn-in 则无此问题）。

### 4.4 视频被裁切 / 比例错误

**现象**：竖版素材在部分版位出现左右裁切或黑边。

**排查：**
1. 素材必须是**纯 9:16**（1080x1920）且无内置黑边，否则系统可能二次裁剪；
2. 在 `object_story_spec` 里声明 `format` / 9:16 裁剪（`image_crops`），
   或确保 Creative 的 `video_data` 比例正确；
3. 检查源是否被"pad 黑边"而非"crop 裁剪"（见 2.1.1 命令）；
4. 若用 Advantage+ Placements，系统为匹配其他版位可能裁切 —— 介意则手动限定竖版版位。

### 4.5 自动播放不循环 / 静音

**现象**：素材不循环、或默认无声导致丢完播。

**排查：**
1. **循环**：Reels/Stories 广告默认循环；如果开头结尾不衔接，可做"首尾环形剪辑"
   让循环更自然（用 ffmpeg 或剪辑软件把尾部帧与首帧对齐）；
2. **静音起播**：默认无声是平台规则，**别试图绕过**；靠字幕 + 画面叙事保证"无声可懂"，
   音频作为加分项，不要依赖它讲关键信息；
3. 检查视频是否有音轨且编码 AAC：无音轨会被系统当"静音视频"标记，影响质量分。

### 4.6 贴纸不生效 / native 标签问题

**现象**：视频里画了投票/滑动，但用户点不了、互动率低、被标 native。

**排查：**
1. **画出来的贴纸不是贴纸**：视频画面里的"投票/滑杆"图形只是视觉元素，
   无法产生真实互动事件（见 2.5 的路径图）；
2. 要真实贴纸必须在 **IG App 内/官方 creative 工具**添加并发布原生 Reel，
   再通过 Boost 或 Spark Ads 投放；
3. 原生 Reel 转广告会带 `Sponsored` 标签（native 标签）——这是平台规定，
   通过"内容原生化"（真实感强）可弱化用户抵触，无法去掉标签本身。

### 4.7 完播率过低排查清单

**现象**：TTR / ThruPlay 明显偏低（如 < 15%）。

```text
完播率低 → 按序排查
┌─ ①首 3 秒有没有强钩子？        (首帧是否黑场/Logo 大特写)
├─ ②开头有没有点名目标受众？      ("如果你是新手……")
├─ ③信息是否一句说不清楚？        (素材塞了太多卖点 → 减到 1 个核心卖点)
├─ ④字幕/画面是否"静音可懂"？     (没字幕 = 静音用户直接划走)
├─ ⑤素材与受众是否匹配？          (兴趣定向过宽/过窄)
├─ ⑥素材是否已在疲劳？            (频率 > 3~4 且 TTR 连续下滑)
└─ ⑦时长是否过长？               (Reels 压到 15~30s，Stories 压到 5~15s)
```

---

## 五、自测题

### 自测题 1：Reels 与 Stories 的创意为什么不能直接互相复用？请给出时长、信息量、首屏策略的差异。

<details>
<summary>查看答案</summary>

Reels 用户在"看内容"，Stories 用户在"走过场"，两者消费心态完全不同：

- **时长**：Reels 可做 15~60 秒完整叙事；Stories 只能 5~15 秒单点信息，长了用户划走；
- **信息量**：Reels 可以做"起承转合、多卖点递进"；Stories 必须"一句话说清楚一个点"，
  一次讲故事会被跳过；
- **首屏策略**：Reels 首 3 秒给强钩子 + 完整叙事 + 末尾 CTA；Stories 首屏就要把
  "痛点 + 钩子 + 行动指令"尽量塞进前几秒，因为用户切换极快。

**反例（Ryan 踩坑）**：把 30 秒教程类 Reel 直接复用到 Stories，TTR 暴跌约 60%，
因为第 5 秒才到核心信息，用户根本等不到。正确做法是同一主题拆两条素材分别适配。

</details>

### 自测题 2：为什么"完播率 / TTR"是竖版广告的第一指挥棒？如何从 Insights 字段准确计算 TTR？

<details>
<summary>查看答案</summary>

竖版全屏 + 自动播放场景里，**完播 = 用户认可**：
- 全屏没有点击门槛，用户唯一能表达"不感兴趣"的方式就是划走；
- 因此能让人看完的素材，被 Meta 判定为高质量内容，算法会把更多、更便宜的流量分给它，
  从而 CPM 下降、CPC 变优——完播直接影响竞价效率；
- TTR（Touch/Thru-Play Rate）定义 = 完整播放次数 ÷ 展示量。

**准确计算**（容易踩坑）：
- Insights 里 `video_thruplay_watched_actions` 返回的是**事件数组**（不同 value 维度），
  需把每个元素的 `value` 求和，再用 `impressions` 相除，才得到真正的 TTR；
- 同理 `video_3_sec_watched_actions` 求 3 秒率；`post_engagements / impressions` 求互动率。
- 参考分档：TTR ≥ 55% 强烈留人可加量；30%~55% 正常；15%~30% 查开头与匹配；
  15% 以下换创意。

</details>

### 自测题 3：竖版 9:16 素材的"安全区"为什么重要？关键信息应该放在画面哪里？

<details>
<summary>查看答案</summary>

竖版是**全屏 + 平台 UI 叠加**：右侧点赞/评论/算号、左侧用户名、底部 caption/CTA、
顶部状态栏都会盖在素材边缘。所以"整屏都能放重要信息"是错觉，**边缘是被遮挡高风险区**。

安全区经验：
- **中央核心区（约垂直 60%~70%）是主战场**，关键信息、人脸、产品主体放这里；
- 顶部预留 8%~14%、底部预留 14%~18%，不放关键信息；
- 右侧预留 8%~12% 不做按钮/关键文字，主体可向左偏约 10%；
- 字幕放在**垂直 72%~84%**（别贴底，否则被 Stories 的 CTA 条/caption 盖住），
  并加 6px 描边或半透明底保证可读。

**Ryan 踩坑**：曾把字幕压在画面底部 6%，上线后被 Stories 底部「TAP TO VIEW」CTA 完全盖住，
后统一上移到垂直 72%~84% 区间并加描边才解决。

</details>

### 自测题 4：如何在 "Advantage+ Placements" 与 "手动限定竖版版位" 之间做选择？

<details>
<summary>查看答案</summary>

- **手动限定版位**（`instagram_positions: ["insta_reels", "insta_stories", "insta_explore"]`）：
  目的明确——只投 IG 竖版全屏，便于单独测竖版创意、品牌形象统一、或不想被裁切。
  适合**起步测试阶段**，先把竖版素材的效果测清楚。

- **Advantage+ Placements**：让 Meta 自动在全部版位里选最可能满足优化事件的组合，
  预算自动分配，通常**放量效率和转化成本更优**。配合竖版 9:16 素材使用效果最好。

**Ryan 建议**：新手先在手动竖版版位把素材跑明白，再切 Advantage+ Placements 放量；
成熟账号可以直接 Advantage+ + 多素材（OOE 动态创意）组合，让系统自动筛选最佳组合。
一个中间态是 "Campaign 层用 Advantage+、AdSet 层保留竖版素材为主"。

</details>

### 自测题 5：互动贴纸（投票/倒计时/表情/问答/滑动）在广告里，如何区分"真贴纸"与"伪贴纸"？如何获得真实互动数据？

<details>
<summary>查看答案</summary>

- **真贴纸（平台原生 Sticker）**：在 **Instagram App 内 / 官方 creative 工具**里给一条
  Reel/Story 添加投票/倒计时/表情滑杆/问答贴纸，发布为原生内容后，再通过
  **Boost 或 Spark Ads** 投放。广告展示时贴纸保留、可被点击，**能采集到真实互动事件
  （投票结果、滑杆分布、停留时长）**，并可作为重定向与 lookalike 的种子信号。

- **伪贴纸**：直接在视频画面里"画"一个投票/滑杆图形。它只是视觉元素，
  用户点了没有任何真实互动产生——只能制造"可参与"的心理暗示，拿不到真实互动数据。

**关键结论**：目的是**真互动数据与信号**，就必须走原生 Reel/Story + 转广告（Spark Ads）；
仅要"看起来原生"的参与感，可以用画出来的贴纸。两条路径不要混淆，
否则监控的 `inline_post_engagement` 数据会失真。

</details>

---

## 附录 A：核心规格速查表（竖版）

```text
Instagram Reels / Stories 广告竖版速查
├─ 宽高比     9:16
├─ 分辨率     1080 x 1920 px（≥720p）
├─ 时长       Reels ≤90s(推荐15-45s)、Stories ≤60s(推荐5-15s)
├─ 格式/大小  MP4/MOV  ≤4GB  H.264/AAC
├─ 帧率       30fps（首推） 60fps（可选）
├─ 码率       ≥8Mbps（1080p）
├─ 安全区     顶部8-14% 底部14-18% 右侧8-12%
├─ 字幕       烧录硬字幕、72%-84%位置、加描边
└─ 贴纸       原生 Sticker 才出真实互动
```

## 附录 B：相关文档导航

- `meta-ads-objectives-creatives-deep.md` —— 通用广告目标与创意格式（本文档不重复的部分）
- `meta-ads-advantage-plus-full-deep.md` —— Advantage+ 系列深度
- `meta-ads-targeting-advantage-deep.md` —— 定向与受众深度
- `meta-ads-marketing-api-deep.md` + `meta-marketing-api-expert` 技能 —— Graph API 底层
- `ad_platform_api.py` —— `meta_create_campaign / meta_create_adset / meta_create_ad /
  meta_list_ads / meta_list_creatives / meta_get_creative / meta_list_video_sizes /
  meta_list_placements / meta_list_audiences / meta_query_insights` 等方法

---

*本文档由 Ryan 知识库升级专家生成，聚焦 Instagram Reels & Stories 竖版视频广告垂直场景，*
*与通用创意文档互补。数据口径与规格以 Meta 官方最新文档为准，投放前请复核当期版本。*

---

## 三附：竖版生产管线（Production Pipeline）深度展开

> 为补足第 3 章的生产深度，本附表以"**一条竖版素材从原始素材到可投放广告**"的完整
> 管线为主线，逐环节给出命令、代码与检查点。这是把"会投放"升级为"会高效生产"
> 的关键能力。

### 3.8 竖版素材生产管线总览

```text
竖版素材生产管线
┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐
│  原始素材    │→ │  粗剪/选条   │→ │  竖版裁切   │→ │  字幕/贴纸  │→ │  二次压制   │→ │  上传+建广告 │
│ Raw Footage│  │ Select     │  │ 9:16 Crop │  │ Caption    │  │ FFmpeg     │  │ Upload+Ad  │
└───────────┘  └───────────┘  └───────────┘  └───────────┘  └───────────┘  └───────────┘
  手机/相机     选最能钩人的     居中crop     烧录硬字幕    统一H.264      meta_upload_video
  UGC 素材       3-15 秒片段     1080x1920     +BeReal风      压制         
```

**每个环节的关键决策点：**

| 环节 | 目标 | 输入 | 输出 | 产出物 |
|------|------|------|------|--------|
| 原始素材 | 拿到足够多可用的竖版/可裁纵版素材 | 手机竖拍 / 横拍+裁切 / AI生成 | 若干候选 clip | 素材库 |
| 粗剪/选条 | 挑出首 3 秒最强的片段 | 候选 clip | 1 条主干 | 剪辑工程 |
| 竖版裁切 | 保持 9:16 且主体居中 | 主干 | 9:16 无损 | crop 后 mp4 |
| 字幕/贴纸 | 静音可懂 + 原生感 | 9:16 视频 | 烧录字幕版 | 带字 mp4 |
| 二次压制 | 控制体积、兼容性 | 带字 mp4 | 交付 mp4 | H.264 30fps |
| 上传+建广告 | 上线投放 | 交付 mp4 | 广告 | video_id+Ad |

> **为什么管线重要**：竖版竞争的本质是"**素材产出速度**"。管线化之后，
> 从拍摄到上线可从"几天"压缩到"几小时"，让创意疲劳时能快速换新，这是降 CPM 的核心杠杆。

### 3.9 竖版裁切：crop vs pad 的工程取舍

竖版容器是 1080x1920。把非竖版源塞进去有两种方式，观感天差地别：

```text
方式A：crop（居中裁切）—— 推荐
┌─────────┐
│ 横版源    │  中段 60% 被保留
│ ███████  │  → 放大到 9:16
└─────────┘
  竖版 = 横版中段被裁高
优点：无黑边，信息密度高
缺点：可能裁掉左右重要内容

方式B：pad（加黑边）—— 慎用
┌─────────┐
│  ░░源░░  │  上下补黑边
│ ███████░│
└─────────┘
  竖版 = 全图缩小 + 上下黑边
优点：不丢失任何画面
缺点：出现信箱黑边，手机全屏明显，观感廉价
```

**ffmpeg 两种命令：**

```bash
# A. crop 居中裁切（推荐，因为竖版要满屏）
ffmpeg -i input.mp4 \
  -vf "crop=1080:1920:(in_w-1080)/2:(in_h-1920)/2" \
  -c:v libx264 -crf 20 -pix_fmt yuv420p \
  -c:a aac -b:a 192k \
  output_9x16_crop.mp4

# B. pad 加边（仅当绝不能裁掉画面时才用）
ffmpeg -i input.mp4 \
  -vf "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black" \
  -c:v libx264 -crf 20 -pix_fmt yuv420p \
  -c:a aac -b:a 192k \
  output_9x16_pad.mp4
```

> **Ryan 经验**：
> - 拍摄时**手机竖拿**，直接产出 9:16 源，省去裁切环节、质量最高；
> - 横拍素材裁剪时，注意把**主体（人脸/产品）放在画面中段收录区**，否则裁切后丢主体；
> - 裁切会放大噪点 → 拍摄时保证足够光线与高分辨率（1080p 起，2K/4K 更稳）。

### 3.10 画面语言：竖版如何"讲清楚一件事"

竖版画面比横版窄，信息必须**纵向排布**。给一个"同一产品，横版 vs 竖版信息排版"对比：

```text
横版 16:9（横向叙事）
┌────────────────────────────────────────┐
│ [标题区]   [产品+演示]      [价格区]     │
└────────────────────────────────────────┘
多元素并排 → 信息密度高但单个面积小

竖版 9:16（纵向递进）
┌──────────────────┐
│    ▒ 首屏钩子 ▒    │  ← 顶部：痛点/大问题
│    (人脸/产品)     │
├──────────────────┤
│   ● 第2屏：为什么   │  ← 中部：方案一句话
│   步骤示意         │
├──────────────────┤
│   ▓ 第3屏：结果    │  ← 下部偏上：成果/证言
│   (字幕区 72-84%)  │
├──────────────────┤
│   ░ CTA 提示      │  ← 底部：行动指令
└──────────────────┘
纵轴时间 = 用户划动/进度，天然引导"推进"
```

**纵向排布三条铁律：**
1. 每个"时间区块"只讲一个信息，别让多卖点抢屏；
2. 主体垂直居中偏上 5%~10%，给人脸/产品留呼吸感；
3. 字幕块放在主体下方（72%~84%），形成"上画面、下文字"的稳定视觉锚点。

### 3.11 字幕自动化：ffmpeg + ASS 烧录硬字幕

手动逐条打字幕耗时且易错。生产化做法是"先出文本 → 转 ASS → 烧录"：

**Step 1 生成 ASS 字幕（工具化思路）：**

```python
# 伪代码：把文案块按时间轴转成 ASS 条目（真实脚本可用 pysrt/ass 库）
def build_ass(cues: list, width=1080, height=1920, font="SourceHanSansCN-Regular"):
    """cues: [(start_sec, end_sec, text), ...] → 返回 ASS 文本"""
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, Bold, Outline, Shadow, Alignment, MarginV
Style: Caption,{font},72,&H00FFFFFF,0,6,1,2,240

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = header
    for start, end, text in cues:
        lines += f"Dialogue: 0,{fmt_ts(start)},{fmt_ts(end)},Caption,,0,0,0,,{text}\n"
    return lines

def fmt_ts(sec: float) -> str:
    h, m = divmod(int(sec), 3600), divmod(int(sec) % 3600, 60)[0]
    s = sec - h*3600 - m*60
    return f"{h:02d}:{m:02d}:{s:05.2f}"


cues = [
    (0.0, 2.0,  "你还在为整理资料头疼吗？"),
    (2.0, 5.0,  "3 步就能搞定。"),
    (5.0, 9.0,  "第一步，把所有文件拖进来。"),
    (9.0, 13.0, "第二步，让它自动分类。"),
    (13.0, 16.0,"第三步，一键导出，搞定。"),
]
ass_text = build_ass(cues, font="SourceHanSansCN-Regular")
open("captions.ass", "w", encoding="utf-8").write(ass_text)
```

**Step 2 用 ffmpeg 把 ASS 烧录进视频：**

```bash
# 必须同时开 libass 字幕滤镜与视频编码
ffmpeg -i vertical_9x16.mp4 \
  -vf "ass=captions.ass" \
  -c:v libx264 -crf 20 -pix_fmt yuv420p \
  -c:a copy \
  output_with_captions.mp4
```

> 注意事项：
> - ASS 文件必须 **UTF-8 编码**，且字体名要与系统已安装字体的英文名一致，否则烧录成方框；
> - `-c:a copy` 复制原音轨，避免二次转码掉画质；
> - 中文文本留白/自动换行可在 ASS 里用 `\N` 手动断行，保证每屏 ≤ 4 词。

**脚本侧检查字幕安全区的图形化方式（工程走查）：**

```python
def check_caption_safety(ass_text: str, bottom_zone=0.18, height=1920):
    """粗查：字幕 MarginV 对应的像素高度是否落在安全区内（72%~84%）。"""
    import re
    found = []
    for line in ass_text.splitlines():
        m = re.search(r"MarginV=(\d+)", line)
        if m:
            margin = int(m.group(1))
            # ASS MarginV 是距画面底部像素；字幕中线应在 0.72~0.84 * height
            y_mid = height - margin
            ratio = y_mid / height
            found.append((y_mid, ratio))
    return found
```

### 3.12 封面与首帧设计（Cover / First Frame）

封面图影响：分享预览、暂停定格、加载期间观感；首帧影响：划入瞬间的驻足。

**封面图规范：**
| 项 | 要求 |
|----|------|
| 比例 | 与视频一致，9:16（1080x1920） |
| 格式 | JPEG/PNG |
| 大小 | ≤ 8MB |
| 内容 | 不含关键动态信息（因为只在静止时出现），放品牌/产品/一句话钩子 |

**封面上传到媒体库：**

```bash
curl -X POST "https://graph.facebook.com/v19.0/{ACCOUNT_ID}/adimages" \
  -F "access_token={ACCESS_TOKEN}" \
  -F "filename=@cover_9x16.jpg" \
  -F "bytes=..." 
# 返回 { "images": { "cover_9x16.jpg": { "hash": "..." } } }
```

**在 Creative 里用封面（image_url 或 image_hash）：**

```python
def meta_create_ad_creative_with_cover(self, account_id, name, video_id,
                                       image_hash, page_id, ig_user_id,
                                       link, message="", cta_type="LEARN_MORE"):
    import requests, json
    token = self.credentials["meta"]["access_token"]
    spec = {
        "page_id": page_id,
        "instagram_actor_id": ig_user_id,
        "video_data": {
            "video_id": int(video_id),
            "image_hash": image_hash,      # 封面
            "call_to_action": {"type": cta_type, "value": {"link": link}},
        },
        "link_data": {"link": link, "message": message},
    }
    url = f"https://graph.facebook.com/v19.0/{account_id}/adcreatives"
    r = requests.post(url, params={"access_token": token, "name": name,
                                   "object_story_spec": json.dumps(spec)}, timeout=60)
    r.raise_for_status()
    return r.json()
```

**首帧设计清单：**
```text
□ 首帧 = 强钩子画面（不是黑场/Logo 大特写）
□ 若首帧是产品特写：给"一句话大字"（如 "只卖 3 步"）
□ 避免 0.5s 以上纯黑/纯色过渡
□ 首帧与第 1 秒字幕呼应，制造"开口就懂"
```

### 3.13 无缝循环（Seamless Loop）剪辑

循环播放时，若视频**尾帧与首帧能衔接**，用户看到的是连续循环，观感不中断、完播更友好。

```text
无缝循环示意图
┌──────────────────┐
│ 片头帧 A ──► ... ──► 片尾帧 B │
│      ▲              │
│      └───── 循环 ─────┘
│   要求：A 与 B 视觉相似/动作衔接
└──────────────────┘
```

实现技巧：
1. **首尾同画面**：片头片尾停在同一构图（如产品居中的定格），循环时视觉无缝；
2. **动作闭合**：让一个连续动作恰好绕回起点；
3. **淡入淡出对冲**：尾部轻微淡出到白色/背景色，片头也从同色淡入；
4. ffmpeg 测试拼接：`ffmpeg -stream_loop 2 -i video.mp4 -f null -` 观察是否卡顿。

### 3.14 多素材 A/B 与 OOE 动态创意

竖版素材便宜易产 → **用测试代替猜测**。两套组合拳：

**A/B 测试框架（同一受众，仅换创意）：**

```python
def ab_test_vertical_creatives(account_id, adset_id, creatives: list, names: list):
    """同一 AdSet 下为每个创意建一个 Ad，保证其余条件完全一致。"""
    results = []
    for i, cid in enumerate(creatives):
        ad = client.meta_create_ad(adset_id, names[i], creative={"creative_id": cid})
        ad_id = ad["id"]
        client.meta_update_ad(ad_id, status="ACTIVE")
        results.append({"ad_id": ad_id, "creative_id": cid, "name": names[i]})
    return results

ads = ab_test_vertical_creatives(
    ACCOUNT_ID, ADSET_ID,
    creatives=[C1_ID, C2_ID, C3_ID, C4_ID, C5_ID],
    names=["痛点前置", "教程式", "对比式", "用户证言", "折扣式"],
)
```

**OOE / 动态创意（让系统自动组合）：**
- 1 个 Ad 里放**多个视频 + 多文案 + 多 CTA**，让 Advantage+ 自动排列组合出最佳搭配；
- 好处：无需人工逐一 A/B，系统按优化事件自动胜出；坏处：无法精确归因哪条素材。
- 适用：进入放量期、希望对冲创意疲劳时。

**A/B vs OOE 选择矩阵：**

| 阶段 | 选择 | 理由 |
|------|------|------|
| 起始测试（想搞清哪种模板强） | 手动 A/B（每 Ad 单一创意） | 归因清晰，便于学素材方向 |
| 起量/放量（求效率） | OOE 动态创意 / Advantage+ | 系统自动胜出，省人力 |
| 创意疲劳 | 多素材 A/B 轮换 | 持续供给新素材防疲劳 |

### 3.15 频次控制与预算泵（Budget Pacing）

竖版素材尤其容易疲劳（高频展示在同一批人面前），需要工具化控制：

```python
def monitor_fatigue_and_pace(account_id, campaign_id, max_freq=3.5,
                             ttr_drop=0.15, interval_days=2):
    """监控广告频次与 TTR 趋势，触发换创意/调预算。"""
    freq = client.meta_query_insights(
        account_id, date_preset="last_7d", level="campaign",
        fields=["campaign_id", "frequency", "impressions", "reach"],
    )
    row = next((r for r in freq if r.get("campaign_id") == campaign_id), {})
    f = row.get("values", {}).get("frequency", 0) or 0
    if f > max_freq:
        print(f"[警告] 频次 {f:.2f} 已超阈值 {max_freq}，建议上新鲜创意思绪")
    # 余下：按 2.7 的 TTR 计算对比 last_7d vs 上个周期
```

**频次相关字段：**
- `frequency` = `impressions / reach`（平均每人看到次数）；
- 竖版建议把**单创意频次控制在 3~4 以内**，超过即触发换素材；
- 预算泵（Pacing）：在广告组层面可设 `lifetime_budget` + `campaign_spend_cap`，
  或用 `bid_strategy` 让系统在给定预算内最优分配，避免某条老素材吃光全部预算。

### 3.16 竖版广告的"质量分"观感自查（Creative Quality Gate）

上线前用清单做"自检门"，能显著减少返工与拒审：

```text
竖版创意上线前自检门
□ 比例：确为 9:16，1080x1920，无内置黑边
□ 首帧：强钩子，非黑场/Logo 大特写
□ 首3秒：点名痛点/受众，字幕第一屏同步出现
□ 字幕：烧录硬字幕、UTF-8、无乱码、位置 72%-84%、≤4词/屏
□ 音频：内嵌 AAC，48kHz，无声状态也完整可懂
□ 时长：Reels ≤45s、Stories ≤15s（各取建议值）
□ 安全区：关键信息在中央核心区，边缘被遮也不影响理解
□ 内容政策：无医疗/金融/政治/夸张用语，版权音乐合规
□ 封面：9:16、JPEG/PNG、非动态关键信息
□ CTA：与落地页一致，不空转
□ 平台：页面/IG 商业号已授权（object_story_spec 的 page_id/instagram_actor_id 正确）
```

---


## 四附：高频问题深挖（续）

### 4.8 竖版素材在"静音"与"有声"时的最佳做法

**问题**：自动播放默认静音，但有的用户会打开声音，素材该如何同时讨好两种用户？

**解法"双层可懂"**：
```text
双层可懂
├─ 无声层（默认，必做）
│   └─ 字幕 + 画面叙事 = 不看声音也完整
└─ 有声层（加分，激发时触发）
    └─ 口播/音效/音乐 = 打开声音后更沉浸
```
- 不要把**任何关键信息**只放在音频里（静音用户会漏）；
- 音频与字幕**信息一致但不重复堆字**：有声层"说重点"，无声层"显重点"；
- 音乐选择：用 Meta 授权音乐库（创作者工具里的音乐），避免版权拒审。

### 4.9 转码慢 / 视频迟迟不 Ready

**现象**：上传后 `status.video_status` 长时间不 `ready`，广告无法投放。

**排查：**
```text
□ 文件超过 4GB？→ 超限直接失败，先二次压制
□ 分辨率/码率过高？→ 4K 高码率转码极慢，交付 1080p/8Mbps
□ 编码不规范？→ 非 H.264/AAC、pix_fmt 非 yuv420p 会转码出错
□ 网络中断？→ 分片上传中断需重传
□ 轮询太早？→ 用 status.video_status 轮询，别只看 POST 立即返回
```

**轮询示例：**

```bash
# 轮询到 ready
while true; do
  S=$(curl -s "https://graph.facebook.com/v19.0/{VIDEO_ID}?fields=status.video_status&access_token={TOKEN}" | python -c "import sys,json;print(json.load(sys.stdin)['status']['video_status'])")
  echo "status=$S"
  [ "$S" = "ready" ] && break
  sleep 5
done
```

### 4.10 Reels 与 Stories 版位"无流量 / 分配不均"

**现象**：Campaign 明明开了 Stories/Reels，却没展示或严重偏科（全跑到 Feed）。

**原因与解法：**
| 原因 | 解法 |
|------|------|
| 素材比例不满足竖版 | 提供 9:16 素材，竖版版位才能充分利用 |
| 用了 Advantage+ 但素材横版为主 | Advantage+ 会倾向 Feed；竖版素材才能吃竖版流量 |
| 定向过窄导致流量不足 | 放宽受众或加预算；竖版版位触达池本就小于 Feed |
| 预算在 AdSet 间分配不均 | 用预算规则（campaign 分配占比/CBO）均摊；或手动限制曝光版位 |
| 优化事件过严 | 尝试用更宽松的优化目标（如 Reach/Video Views）先起量 |

### 4.11 Instagram 广告内容审核（Reels/Stories）之"伪原生"边界

**问题**：BeReal 风做过头，被系统判为"误导性伪装"，影响审核或源原生内容限流。

**边界判断：**
```text
原生感光谱
├─ 过度精修 / 广告感强 → 原生度低，但不违规
├─ 真实感 UGC ⇦目标区⇦
└─ 伪装成普通用户内容、隐瞒广告 → 违规（"裸广告伪装"）
```
- 广告**必须有 Sponsored 标签**（平台自动加），不能试图去掉或遮盖；
- BeReal 风可以做"真实感的表达方式"，但**不能隐瞒商业意图**（带货要明示）；
- 若被判定"misleading advertising"，会被拒审或降权，务必保留明显的品牌身份与 CTA。

### 4.12 落地页与 CTA 不匹配导致的转化极差

**现象**：竖版广告很吸睛、完播也好，但转化上不去 —— 通常是"素材承诺 ≠ 落地页内容"。

**排查清单：**
```text
□ 素材讲的卖点，落地页首屏是否直接对应？
□ CTA（Learn More/Shop Now）是否与落地页动作一致？
□ 竖版素材是否加载了独立落地页（非主页随缘）？
□ 移动端落地页是否 1-2 秒内打开、无需横竖屏切换？
□ 是否只用静态页，没有与素材同视觉风格的 H1/首图？
```
> **Ryan 经验**：把素材的"末帧 CTA"与落地页"首屏 H1"做成**同一句话/同一视觉**，
> 点击到转化的心理连续性最好，转化率提升显著。

### 4.13 数据口径：为什么 Insights 里"完播率"看起来很低/很高

**原因**：Insights 的完播/3 秒/触达率，其**分母与分子口径需按 value 求和**，
且"完整播放"指订阅到视频结束或广告目标阈值，不是"看完全部秒数"的直观比例。

**建议**：
- 用 `video_thruplay_watched_actions`（完整播放次数）÷ `impressions` 得 TTR；
- 用 `video_3_sec_watched_actions`（3 秒）÷ `impressions` 得 3 秒率；
- 若想看"看完到什么程度"，用 `video_p25_/p50_/p75_/p95_/p100_watched_actions` 分布；
- 对比不同素材时，**统一同一日期区间与同一 level**，避免口径漂移。

---

## 七、实战案例拆解（Worked Example）

> 用一个"虚构但完全符合真实因果"的案例，把本文全部知识点串起来。
> 数值仅供教学，非精确承诺。

### 7.1 背景

- 客户：某个**家庭健身器材 D2C 品牌**，上新品"折叠哑铃 Pro"；
- 目标：App 站内**转化（Purchase）**，同时降 CPM、提升完播与互动；
- 阶段：新品首发，需要快速建立种子人群与早期销量。

### 7.2 策略选择

| 决策点 | 选择 | 依据 |
|--------|------|------|
| 版位 | 第一阶段手动限 IG Reels + IG Stories + IG Explore | 先测竖版素材表现，避免 Feed 稀释 |
| 素材比例 | 全部 9:16 1080x1920 | 竖版原生，匹配全屏消费 |
| 时长 | Reels 版 20s、Stories 版 8s（两套） | 同主题两形态，分别适配 |
| 目标 | CONVERSIONS / OFFSITE_CONVERSIONS | 追求 Purchase |
| 互动贴纸 | Stories 用"投票：你会买吗"；Reels 用"评论扣1" | 提升参与与停留 |
| 创意模板 | 痛点前置 + 对比式 + 用户证言（共 5 条） | A/B 测出最强模板 |

### 7.3 建系统（代码串联全流程）

```python
# 1) 上传 5 条 9:16 竖版视频
vids = {}
for i, path in enumerate(paths9x16, 1):
    v = client.meta_upload_video_creative(
        ACCOUNT_ID, path,
        title=f"折叠哑铃Pro-竖版{i}", description="9:16 新品素材",
    )
    vids[i] = v["video_id"]

# 2) 为每条视频建 Creative（含 CTA/封面）
creatives = {}
for i, vid in vids.items():
    c = client.meta_create_ad_creative(
        ACCOUNT_ID, f"哑铃Pro-创意{i}",
        video_id=vid, page_id=PAGE_ID, ig_user_id=IG_USER_ID,
        link="https://shop.example.com/dumbbell-pro",
        message="前3秒看懂，家用健身一步到位。",
        cta_type="SHOP_NOW",
    )
    creatives[i] = c["id"]

# 3) 建 Campaign
camp = client.meta_create_campaign(
    ACCOUNT_ID, "哑铃Pro-新品-竖版转化",
    objective="CONVERSIONS", status="PAUSED",
)
# 4) 建 AdSet（竖版版位 + 高意向受众）
adset = client.meta_create_adset(
    camp["id"], "竖版-健身高意向",
    budget=100000,  # $1000/日
    optimization_goal="OFFSITE_CONVERSIONS",
    billing_event="IMPRESSIONS",
    targeting={
        "geo_locations": {"countries": ["US"]},
        "age_min": 20, "age_max": 50,
        "publisher_platforms": ["instagram"],
        "instagram_positions": ["insta_reels", "insta_stories", "insta_explore"],
    }, status="PAUSED",
)
# 5) 建 5 个 Ad 做 A/B（单一创意/Ad）
for i, cid in creatives.items():
    client.meta_create_ad(adset["id"], f"哑铃Pro-Ad{i}", creative={"creative_id": cid})
# 6) 激活
client.meta_update_campaign(camp["id"], status="ACTIVE")
client.meta_update_adset(adset["id"], status="ACTIVE")
for a in client.meta_list_ads(adset["id"]):
    client.meta_update_ad(a["id"], status="ACTIVE")
```

### 7.4 一周后复盘（示意数据）

| 创意 | 模板 | TTR | 3秒率 | 互动率 | CPM | CPA |
|------|------|-----|-------|--------|-----|-----|
| Ad1 | 痛点前置 | 52% | 78% | 3.1% | $9.2 | $28 |
| Ad2 | 对比式 | 61% | 85% | 4.2% | $7.4 | $22 |
| Ad3 | 用户证言 | 45% | 71% | 2.5% | $11 | $36 |
| Ad4 | 折扣式 | 38% | 66% | 2.0% | $13 | $41 |
| Ad5 | 教程式 | 49% | 74% | 2.8% | $10 | $30 |

**动作：**
- Ad2（对比式）TTR 61% 最高，CPA 最低 → **加预算、作为主创意放大**；
- Ad4（折扣式）TTR 偏低 → 换成新痛点素材或直接停；
- Ad3/Ad5 继续观察 2 天，若 TTR < 40% 则替换；
- 同时用双素材（对比式 + 新痛点）合并进 **OOE 动态创意** 做第二阶段放量。

**量化成果（示意）：** CPM 从期初 $12 降到 $7.4、完播驱动算法降本、CPA 收敛到 $22 区间。

### 7.5 案例带给我们的三条铁律

```text
铁律一：竖版先测素材→再放量（先 A/B 找最强模板，别一上来 OOE）
铁律二：TTR 是指挥棒（完播高→系统给更多便宜流量→CPM 降）
铁律三：同主题双形态（Reels 讲完整故事、Stories 一句话+强CTA）
```

---

## 八、进阶：竖版视频与"转化事件"的配合（CAPI/Pixel 视角）

> 讲完创意与版位，补充"竖版 → 转化闭环"的信号配合。Deep 讲 Pixel/CAPI 见专属文档，
> 这里只谈与竖版相关的那部分。

### 8.1 竖版素材如何影响优化事件信号

- 高完播素材 → 用户"多看几秒" → 更容易发生后续点击/转化 → 给优化器更强的正信号；
- 若优化事件稀缺（如 Purchase 少），可先用**代理信号**（如 `VIDEO_VIEWS` / `LEAD`）积累，
  或用 `Multi-Channel` 事件配置来扩充训练样本；
- 竖版全屏的强曝光，是**品牌记忆**的有效放大器，对 Search 之后的关键词/受众池有益。

### 8.2 在竖版素材上打埋点

如果落地页在 App/Web，别忘在素材点击后接入 Conversion 追踪：

```python
# Pixel 追踪（脚本已有 meta_track_pixel / meta_send_capi）
client.meta_track_pixel(PIXEL_ID, "ViewContent")
client.meta_track_pixel(PIXEL_ID, "AddToCart")
client.meta_send_capi(PIXEL_ID, event_name="Purchase",
                      event_time=int(time.time()), event_id=order_id)
```

### 8.3 用事件提升"完播素材"的归因

- 高完播素材点击进来的用户，行为质量通常更高；
- 建议把 `video_thruplay_watched_actions`（完播）与转化之间建立观察：看**完播用户的 CVR**，
  若显著高于平均，说明"内容抓到对的人"，可扩大相似受众（lookalike）。

---

## 九、附录 C：常用 Management API 端点速查（竖版素材相关）

```text
上传视频        POST  /{ad-account-id}/advideos
  字段: file/title/description/thumb/unpublished_content_type
查询视频状态    GET   /{video-id}?fields=status.video_status
上传封面        POST  /{ad-account-id}/adimages
查询创意        GET   /{creative-id}
创建创意        POST  /{ad-account-id}/adcreatives
  字段: object_story_spec.video_data.video_id / image_url(image_hash)
        / call_to_action / link_data / instagram_actor_id
创建广告组      POST  /{campaign-id}/adsets
  字段: targeting.publisher_platforms / instagram_positions / insta_reels|insta_stories
创建广告        POST  /{adset-id}/ads
  字段: creative.creative_id
查询洞察        GET  /{ad-account-id}/insights
  fields: video_3_sec_watched_actions / video_thruplay_watched_actions
          / inline_post_engagement / frequency / reach / impressions
```

**Python 侧可用脚本方法对照：**

| 脚本方法（ad_platform_api.py） | 用途 |
|--------------------------------|------|
| `meta_upload_video_creative`（扩展） | 上传竖版视频到 advideos |
| `meta_create_ad_creative`（扩展） | 为竖版视频建 Creative |
| `meta_create_campaign` | 建 Campaign（objective=CONVERSIONS/VIDEO_VIEWS...） |
| `meta_create_adset` | 建 AdSet（竖版版位 targeting） |
| `meta_create_ad` | 建 Ad（引用 creative_id） |
| `meta_list_ads` | 列 Ad / 校验 |
| `meta_list_creatives` / `meta_get_creative` | 查/读创意图 |
| `meta_list_video_sizes` | 查支持视频尺寸 |
| `meta_list_placements` | 查支持版位 |
| `meta_list_audiences` | 列/配受众 |
| `meta_query_insights` | 查完播/TTR/互动指标 |
| `meta_track_pixel` / `meta_send_capi` | 转化追踪 |

