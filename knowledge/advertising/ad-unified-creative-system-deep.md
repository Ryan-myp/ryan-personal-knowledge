# 跨平台创意资产管理与自动化系统深度实战

> **领域**: 广告投放 / 跨平台
> **深度**: ⭐⭐⭐⭐⭐ 实战级指南
> **标签**: cross-platform, creative-management, dco, ai-generation, automation
> **更新时间**: 2026-08-14
> **类型**: system/production

---

## 目录

- [一、核心概念与架构](#一核心概念与架构)
- [二、深度原理解析](#二深度原理解析)
- [三、生产环境实战](#三生产环境实战)
- [四、常见问题与排查](#四常见问题与排查)
- [五、自测题](#五自测题)

---

## 一、核心概念与架构

### 1.1 为什么需要跨平台创意资产管理系统

广告业务发展到多平台投放阶段后，创意（Creative）从"一次性物料"演变为"需要持续生产、管理、迭代的核心资产"。
一个成熟出海电商团队通常同时投放 Google / Meta / TikTok / DV360 四个渠道，
每个渠道又有多个版位规格（Feed、Reels、Stories、In-stream、Display Banner、HTML5、VAST 视频……），
规格组合往往超过 60 种。没有统一管理系统时，创意团队会陷入以下泥潭：

```
┌──────────────────────────────────────────────────────────────┐
│                   没有统一创意中台时的典型混乱                  │
├──────────────────────────────────────────────────────────────┤
│  1. 素材散落在网盘/Slack/邮件/设计师本地磁盘，无法追溯         │
│  2. 同一张主视觉被手工裁剪成 15 份，命名各不相同               │
│  3. 文案版本混乱："final_v2_really_final_v3.mp4" 屡见不鲜      │
│  4. 审核通过的素材与投放中的素材不同步，埋下合规风险           │
│  5. 创意迭代没有数据闭环：不知道哪版素材为什么好               │
│  6. 每次新增一个渠道规格，都要重新走一遍人工出图流程           │
│  7. AI 生成的素材没有版本记录，无法回滚、无法对比               │
└──────────────────────────────────────────────────────────────┘
```

跨平台创意资产管理系统（Unified Creative Management System，UCMS）
解决的核心问题可以浓缩为三句话：

1. **一次生产，多渠道复用**：主视觉/主视频 + 规格元数据 → 自动适配所有平台所有规格；
2. **一个事实源（Single Source of Truth）**：素材、版本、审核、投放状态全部沉淀在统一资产库；
3. **一套数据闭环**：创意级指标回传 → 疲劳诊断 → 自动迭代 → 新一代创意生成。

### 1.2 系统核心能力域

| 能力域 | 英文 | 说明 | 关键产出 |
| --- | --- | --- | --- |
| 创意规格引擎 | Spec Engine | 维护全平台规格矩阵与规格校验规则 | 规格定义 YAML + 校验报告 |
| 资产库 | Asset Repository | 素材、元数据、版本、审核状态统一存储 | 资产 ID、版本树、元数据 Schema |
| 渲染适配层 | Rendering/Adaptive Layer | 裁剪、重排、extend、模板合成 | 平台就绪的最终文件 + 预览 |
| AI 生成流水线 | AI Generation Pipeline | 文案/图片/视频/HTML5 自动化生产 | 生成批次（Batch）+ 变体集 |
| DCO 引擎 | Dynamic Creative Optimization | 组合矩阵、规则引擎、CTR 学习 | 创意组合 + 投放配置 |
| 数据分析层 | Analytics | 创意级指标、疲劳诊断、实验评估 | 看板 + 自动迭代信号 |
| 对接网关 | Platform Gateway | Meta/TikTok/Google/DV360 API 上传与同步 | 投放状态同步 |

### 1.3 总体架构

```
┌──────────────────────────── 使用层 ─────────────────────────────┐
│  Web 工作台      API / SDK       创新工具       投放 / 优化 Agent │
└───────────────┬───────────────────────────────────────────────┘
                ▼
┌──────────────────────── 编排与业务层 ────────────────────────────┐
│  CreativeOrchestrator（规格路由 / 适配编排 / 发布编排）           │
│  ├── 规格解析器(SpecResolver)          ├── 审核工作流(Review)     │
│  ├── 版本控制器(Versioner)             └── 发布管理器(Publisher)  │
└───────┬──────────────────────────────────────────────┬──────────┘
        ▼                                               ▼
┌────────────── 能力层（Capability）────────────────┐ ┌─ 决策层 ──┐
│ 资产索引 / 存储(S3+GCS+OSS 三副本)                 │ │ DCO 引擎  │
│ 渲染适配服务 (FFmpeg / Pillow / headless-chromium) │ │ 规则引擎  │
│ 校验服务 (spec lint / 违禁检测 / 技术校验)          │ │ Bandit/AB │
│ AI 服务 (LLM / 视频生成 / 文图生成 / TTS / 音乐)    │ └────┬──────┘
└───────┬──────────────────────────────────────────────┘     │
        ▼                                                     ▼
┌──────────────────────── 数据与基础设施 ────────────────────────┐
│ PostgreSQL(资产元数据)  Redis(缓存/锁)  Kafka(事件)            │
│ ObjectStorage(原片与产物)  FeatureStore(创意特征)              │
│ 平台连接器: MetaAPI / TikTokAPI / GoogleAds / DV360 / CM360    │
└───────────────────────────────────────────────────────────────┘
```

系统采用"规格驱动（Spec-Driven）+ 资产即事实（Asset-as-Truth）"的双核心设计：

1. **规格驱动**：所有生产动作（渲染、校验、发布）都由平台规格定义驱动，新增规格只改配置不改代码；
2. **资产即事实**：任何创意都先是资产库中的一条记录（Asset Record），所有下游（渲染、测试、投放）都基于资产 ID 工作。

### 1.4 端到端核心流程（主链路时序）

以"上传一条 30s 竖版主视频 → 自动生成 9 个规格变体 → 推送到 3 个平台"为例：

```
上传者 / 业务                    UCMS                         平台
   │                              │                             │
   │  1. POST /v1/assets           │                             │
   │─────────────────────────────>│                             │
   │                              │ 2. 生成 asset_id + 元数据    │
   │                              │ 3. 元数据写 PG + 原始文件 S3 │
   │                              │ 4. 异步校验（规格/合规）      │
   │<─────────────────────────────│ 5. 返回 asset_id + status    │
   │                              │                             │
   │ 6. GET /v1/assets/{id}/renders│                             │
   │─────────────────────────────>│                             │
   │                              │ 7. 请求规格矩阵 spec matrix  │
   │                              │ 8. 渲染农场执行 8 个变体      │
   │<─────────────────────────────│ 9. 返回渲染任务列表 + 状态    │
   │                              │                             │
   │ 10. POST /v1/releases         │                             │
   │─────────────────────────────>│                             │
   │                              │ 11. 审核（人工/机审）         │
   │                              │ 12. 按平台连接器上传         │
   │─────────────────────────────────────────────────────────────>│
   │                              │     13. 上传成功 → 状态 COMPLIANT
   │<─────────────────────────────│ 14. 返回 release_id + 平台 ID  │
```

### 1.5 核心实体与元数据 Schema

资产模型采用"不可变原始素材 + 可变衍生资产"策略：
原始主素材一经上传不可覆盖（写入新版本），衍生资产由渲染/生成任务产出、可重建。

```
Asset (资产)
├── asset_id            UUID 唯一标识（对外不可变）
├── master_id           主素材 ID；衍生资产指向其 master
├── type                image | video | html5 | native | audio | doc
├── content_hash        SHA-256，用于去重与完整性校验
├── spec_origin         master_spec（平台原生规格）
├── status              upload→validating→approved→released→archived
├── versions[]          版本历史（不可变）
├── meta                品牌/产品/语言/地域/投放对象等自定义元数据
├── tags[]              内部标签（如 campaign_id, product_id）
└── audit[]             操作审计（谁、何时、为何修改）

Render (渲染产物)
├── render_id           UUID
├── asset_id            关联资产
├── platform            meta|google|tiktok|dv360
├── spec_key            virta_feed_video | stories_square | ...
├── checksum            MD5 + 文件大小
├── file_url            CDN URL
├── status              queued|rendering|done|failed
└── error               失败原因（代码+消息）

Release (发布)
├── release_id          UUID
├── asset_id / render_id
├── account_id          对端投放账户
├── platform_status      uploaded|in_review|review_failed|publishing|live
└── platform_creative_id 对端平台返回的 creative ID
```

### 1.6 元数据 Schema（JSON）

```json
{
  "asset_id": "a1b2c3d4-0000-4000-8000-000000000001",
  "kind": "video",
  "master": true,
  "content_type": "video/mp4",
  "sha256": "9f86d081884c7d659a2feaa0c55ad015...",
  "size_bytes": 52428800,
  "duration_ms": 15000,
  "resolution": {"width": 1080, "height": 1920},
  "frame_rate": 30.0,
  "codec": "h264",
  "bitrate_kbps": 12000,
  "audio": {"codec": "aac", "sample_rate": 48000, "channels": 2},
  "spec": {"platform": "tiktok", "format": "video", "slot": "feed"},
  "status": "approved",
  "business": {
    "product_id": "SKU-9910",
    "campaign_id": "CAM-2026-0721",
    "locale": ["en-US", "es-MX"],
    "audience_segment": ["retarget", "prospecting"]
  },
  "tags": ["summer", "new-arrival", "ued-bg=ocean"],
  "created_by": "service:pipeline-ai",
  "created_at": "2026-08-14T09:30:00Z",
  "version": 3
}
```

### 1.7 关键术语表

| 术语 | 英文 | 定义 |
| --- | --- | --- |
| 主素材 | Master Asset | 平台无关的原始素材，质量最高、内容完整，是所有适配的源头 |
| 规格 | Spec / Placement | 平台对某一版位的技术约束（尺寸/时长/格式/大小/帧率/码率） |
| 适配 | Adaptation | 将主素材按规格变换为可用素材（裁剪/重排/extend/合成） |
| 变体集合 | Variant Set | 同一条主素材产出的全部规格素材 |
| 动态创意 | DCO | 用组合式素材+规则/模型动态组装广告并实时选优 |
| 疲劳指数 | Creative Fatigue | 基于展示/CTR/发布损耗判定创意衰退的量化指标 |
| Bandit | Multi-Armed Bandit | 在多版创意间按探索-利用策略分配流量并学习最优 |
| Spec Lint | — | 对素材/生成的规格与合规检查，自动拦截问题 |
| Release | — | 一次把渲染产物发布到某个平台账户的单元 |

### 1.8 非功能需求与设计取舍

| 关注点 | 目标 | 设计取舍 |
| --- | --- | --- |
| 一致性 | 资产元数据强一致；渲染产物最终一致 | PostgreSQL 单最新版；渲染事件走 Kafka 记录 |
| 可用性 | 控制面 99.9%，渲染面 99.5% | 无状态服务多副本；渲染队列可补偿重试 |
| 扩展性 | 单规格 10000 QPS 查规格 | 规格配置只读缓存 + Redis 本地缓存 60s |
| 成本 | 渲染成本受控 | 渲染优先 remux/裁剪，避免一切重编码；视频当 GPU 占位复用 |
| 安全 | 素材私有，外部引用带签名 | 签名 URL 有效期 15min；文件下载走审计 |

---

## 二、深度原理解析

### 2.1 各平台创意规格要求矩阵

规格矩阵是整个系统的心脏：所有适配、校验、渲染都以规格图（Spec Graph）驱动。
下面先给出全局规格维度，再分平台给出完整矩阵，最后给出一份可落地的 JSON 规格定义。

#### 2.1.1 规格维度总览

规格本质上是一个 9 元组：

```
Spec = {
  版位(placement), 朝向(orientation), 尺寸 WxH(px),
  时长范围(min_ms, max_ms), 格式集(formats),
  文件大小上限(max_bytes), 帧率(fps 或范围),
  码率约束(bitrate_kbps), 安全区(safe_zone), 特殊约束(字幕/文案限制)
}
```

| 维度 | 字典/取值示例 | 说明 |
| --- | --- | --- |
| placement | feed / reels / stories / search / display / banner / instream / outstream / rewarded | 与平台版位一对多 |
| orientation | landscape / portrait / square / fullscreen / dynamic | 全屏多数与竖屏复用 |
| formats | jpg / png / gif / mp4 / webm / html5(four zip) / native / vast 3.0 / MRAID | HTML5 用四帧 + zip |
| duration | 静态图无；视频 5-60s 等 | 平台常给范围 |
| fps | 24 / 30 / 60 | 高帧率用于游戏、动作类 |
| bitrate | 展示 300-1000kbps；feed 1080p 约 4-12Mbps | 在不超过大小上限前提下 |
| safe_zone | 拉近视频信息/UI 覆盖区，文字广告 ≤ 20% 区域 | 关键合规点 |
| accessibility | 字幕格式、对比度、闪烁频率 ≤ 3Hz | 无障碍与癫痫合规 |

#### 2.1.2 Google/YouTube 规格矩阵

| 版位 | 类型 | 尺寸(px) | 方向 | 时长(s) | 格式 | 文件大小上限 | fps | 其他 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Google Search 文字 | 文本 | — | — | — | text | — | — | 标题 ≤ 30 字符 x3，描述 ≤ 90 字符 |
| Responsive Search Ads (RSA) | 文本/资产 | 200x200, 600x314, 1200x628, 1200x1200 | 多 | — | image | 5MB/张 | — | 15 个标题+4 条描述 |
| Responsive Display (RDA) | image+组合 | 同上 | 横/方 | — | image + 素材组合 | 5MB | 120/300/300/250 等 5 种尺寸 | 4 张 + 5 标题 |
| YouTube Instream (skippable) | video | 横 16:9: 1920x1080 | 横 | 15-60s（建议 6-15s） | mp4/mov | 1GB | 30fps, H.264 | 前 5s 洗感区；无水印 |
| YouTube Instax (non-skippable) | video | 1920x1080 | 横 | 15s | mp4 | 1GB | 30fps | 无跳过，需标注"了解详情" |
| YouTube Shorts | video | 1080x1920 | 竖 | ≤60s | mp4 | 1GB | 30fps | 建议 9:16，内容面积最多 20% |
| YouTube Masthead | video+image | 1920x1080 + 海报 480x640 | 横 | ≤30s | mp4+jpg | — | 30fps | 最高价率位 |
| Discover feed | image | 1200x628 | 横 | — | jpg/png | ≤5MB | — | 建议 1200x628 |
| Google 应用 (InApp) | video | 1920x1080 | 横/竖 | ≤30s | mp4 | 1GB | 30fps | 16:9 + 9:16 都需要 |

注：Google 对图像素材有两篇强制约束——纵横比在 1:1 与 4:1 之间（RSA 所载图可 1.91:1），
且"文本占画面比例"在部分版位不得超过 20%（Google 后来把"文字> 20%"要求从展示广告品牌中取消，但贴文（Carsons 等）仍有指引）。

#### 2.1.3 Meta 规格矩阵（Feed / Reels / Stories）

| 版位 | 类型 | 尺寸(px) | 方向 | 时长 | 格式 | 文件大小上限 | 帧率/码率 | 音频/其他 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Feed（信息流）图片 | image | 1080x1080（推荐）允范围 600-1080px | 方 | — | jpg/png | ≤8MB | — | 文件 ≤2:1，文字 ≤ 20% |
| Feed 视频 16:9 | video | 1280x720 最低，1920x1080 推荐 | 横 | 5s-241m | mp4/m4v | ≤4GB(部分缩小为 1GB) | fps 可变：30-60fps | 推荐 H.264、码率高 |
| Feed 视频 4:5 | video | 1080x1350 | 竖 | 同上 | mp4 | ≤4GB | 30fps | 移动端主流 |
| Reels | video | 1080x1920 (9:16) | 竖屏 | 10-90s（新上限 90s） | mp4/mov | ≤4GB | 30fps（推荐 60） | 字幕安全区：下方 1/5 可被 UI 遮挡 |
| Stories | image/video | 1080x1920 (9:16) | 竖 | 1-60s（loop：可设置连续播放） | jpg/png/mp4 | 图片 ≤30MB，视频 ≤4GB | 30fps | 顶部/底部各约 250px UI 遮挡区 |
| Collections | image | 1200x1200 | 方 | — | jpg/png | ≤8MB | — | 卡片式 |
| Messenger | image/video | 1200x1200 或 9:16 | 方/竖 | — | — | — | — | 字幕区避让 |
| Center Stage（原 Feedback） | video | 1080x1920 | 竖 | 3 帧 | mp4 | — | 30fps | 试用中心舞台 |

Meta 避让区核心规则：

```
Feed/Stories 视频：
├── 建议内容区（safe area）: 中央 2/3（即上下各留 ~1/6）
├── 顶部：约 20% 被头像 + 文本 + 行动按钮遮挡（Stories）
├── 底部：约 20-25% 被 CTA + 进度条遮挡
└── 制作规范：文字、Logo、CTA 勿放入遮挡区；CTA 默认叠加在右下

Reels：
├── 右侧 20% 为 UI：点赞/评论/分享/头像
├── 底部 20%：描述文字/音乐名/CTA
└── 安全区建议 1080x(1008~1900) 之间（上下各 60px）
```

#### 2.1.4 TikTok 规格矩阵（Feed / Stories / Pinnable）

| 版位 | 类型 | 尺寸 | 方向 | 时长 | 格式 | 文件大小 | 帧率/码率 | 备注 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| In-Feed Video | video | 1080x1920 (9:16) | 竖 | 5-60s（最长 10min，推荐 5-15s 或 21-34s） | mp4 / MOV / AVI / WEBM (H.264) | ≤500MB | 30/60fps | 安全区：中间 32px 星级提醒 / 左下 UI |
| TikTok TopView | video | 1080x1920 | 竖 | 5-60s | mp4 | ≤500MB | 30fps | 首屏全屏，注意 UI 遮挡（顶部 18%） |
| Spark Ads | video/image | 1080x1920 / 1200x1200 原图 | 竖/方 | 按原生帖 | 原始格式 | ≤500MB | — | 允许使用创作者视频（需授权） |
| Pinnacle Ads（精品） | video | 1080x1920 | 竖 | 10-60s | mp4 | ≤500MB | 30fps | 支持交互组件 |
| 图片轮播 Feed | image | 1080x1920 | 竖 | — | jpg/png | ≤5MB/张 | — | 最多 35 张轮播 |
| TikTok Stories（新） | video | 1080x1920 | 竖 | ≤15s | mp4 | ≤500MB | 30fps | 24h 消失 |

**TikTok 安全区说明（Safe Zones，单位 px，基于 1080x1920 画布）：**

| 区域 | 相对位置 | 建议预留 |
| --- | --- | --- |
| 底部信息条 | 下方 210px | 描述、CTA、进度条 |
| 右侧头像/关注 | 右侧 180px（中线靠右） | 头像、关注按钮 |
| 顶部状态栏 | 顶部 90px | 时间/电量 |

#### 2.1.5 DV360（Display & Video 360）规格矩阵

| 格式 | 尺寸 | 方向 | 备注 |
| --- | --- | --- | --- |
| 展示 HTML5 / Native | 常用 300x250, 728x90, 160x600, 300x600, 320x50, 970x250, 336x280 | 横幅 | ZIP 包（含 index.html + 资源），4 个入口文件允许 |
| HTML5 富媒体 | 300x250 扩展 1000x250 等 | 日常 | 需包含 CLICK_TAG、clickTag 变量 |
| 视频 In-stream | 1920x1080 (16:9) / 1280x720 | 横屏 | mp4（H.264）建议 30fps ✓ |
| 视频 Companion | 300x60, 320x50, 300x250、APInstream | — | 与 VAST 关联展示 |
| VAST / 媒质接入 | 通过 Video Ad Serving | 任意 | 供 3P 广告服务器使用；本 SKU 需要 |
| Native（原生） | image+title+body | — | 复用响应素材套件而非固定尺寸 |
| Master（末尾） — | 1920x350 等 | 横 | Metro/discover 场景 |

**VAST 视频技术规格（供 DV360 / 外链使用）：**

| 维度 | 建议值 |
| --- | --- |
| 容器 | VAST 3.0 / 4.1（后端我们输出 3.0 兼容） |
| 视频编码 | H.264（主流）、可选 HEVC 提供 VBR 标记 |
| 音频 | AAC 128-192kbps，48kHz，立体声 |
| 平均码率 | 1080p：4000-8000kbps；720p：2000-4000kbps |
| 画面率 | 30fps（需与源码一致） |
| 时长 | 与 VMAP/host 一致，通常 15s/30s |
| 位流 | 保留 44 千字节误差容忍；视频 delimit 用 I 帧对齐 |

**HTML5 创意（DV360 hosted / lifting）要求：**

```
HTML5 创意交付 ZIP 结构：
ad.zip
├── index.html        （入口文件，需 <meta charset="utf-8">）
├── script.js         或内联脚本
├── style.css
├── assets/
│   ├── bg.jpg
│   ├── logo.png
│   └── video.mp4
└── manifest.json     （可选，声明素材清单）

关键技术点：
1. 必须包含点击跳转（clickTag）机制：
   - 在 initClickTag(ad) 中将 clickTag 全局变量传递给广告
   - 元素点击时 window.open(window.clickTag || 'fallback')
2. 需声明 exit：通过 dclk-exit 控件或 exitApi
3. 不能依赖外部网络资源（图片/字体/CDN）——全部内联
4. 单一 HTML 文件不得 >2MB；整个 ZIP ≤ 5MB
5. 动画帧率 ≤ 60fps，避免 3 倍频（癫痫风险）
```

**对应示例 HTML5 骨架（index.html）：**

```html
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>DV360 HTML5 Creative</title>
  <meta name="ad.size" content="width=970,height=250">
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { width: 970px; height: 250px; overflow: hidden;
           font-family: Arial, sans-serif; background: #0f172a; color: #fff; }
    #frame { position: absolute; inset: 0;
             display: flex; align-items: center; justify-content: flex-start; padding: 18px; }
    #product { width: 380px; height: 214px; background: center/cover;
               background-image: url('assets/product.png'); border-radius: 12px; }
    #copy { margin-left: 28px; }
    #copy h1 { font-size: 26px; line-height: 1.2; margin-bottom: 8px; }
    #copy p  { font-size: 14px; color: #cbd5e1; margin-bottom: 18px; }
    #cta     { display: inline-block; padding: 10px 26px; font-size: 14px;
               background: #3b82f6; border-radius: 999px; cursor: pointer; }
  </style>
</head>
<body>
  <div id="frame">
    <img id="product" src="assets/product.png" alt="">
    <div id="copy">
      <h1>夏日清凉一夏</h1>
      <p>限时 7 折，全场直降</p>
      <span id="cta">立即抢购 ›</span>
    </div>
  </div>
  <script>
    (function () {
      var ad = {};
      // DV360 注入的全局方法：Google 广告位脚本
      function initClickTag() {
        if (window.clickTag) return;
        var iframe = document.createElement('iframe'); // 兜底
        document.body.appendChild(iframe);
        window.clickTag = '';
      }
      document.getElementById('cta').addEventListener('click', function () {
        var url = window.clickTag || 'https://example.com/fallback';
        if (window.parent && window.parent !== window) {
          try { window.parent.postMessage({ type: 'dclk.exitt', url: url }, '*'); }
          catch (e) { /* ignore */ }
        }
        window.open(url, '_blank');
      });
    })();
  </script>
</body>
</html>
```

#### 2.1.6 规格矩阵 JSON（可供 SpecResolver 消费）

```json
{
  "specs": [
    {
      "spec_id": "meta_feed_video_landscape",
      "platform": "meta",
      "placement": "feed",
      "direction": "landscape",
      "size": {"width": 1080, "height": 1350},
      "aspect": "4:5",
      "duration": {"min_ms": 5000, "max_ms": 241000},
      "formats": ["mp4", "mov"],
      "fps": {"min": 24, "max": 60},
      "max_bytes": 4294967296,
      "max_bitrate_kbps": 12000,
      "audio": {"need": true},
      "safe_zone": {"top": 0.1, "bottom": 0.15, "left": 0.1, "right": 0.1},
      "text_limit": 0.2
    },
    {
      "spec_id": "meta_reels_video_portrait",
      "platform": "meta",
      "placement": "reels",
      "direction": "portrait",
      "words": {"width": 1080, "height": 1920},
      "aspect": "9:16",
      "duration": {"min_ms": 10000, "max_ms": 90000},
      "formats": ["mp4"],
      "fps": {"min": 29, "max": 60},
      "max_bytes": 4294967296
    },
    {
      "spec_id": "tiktok_feed_video_portrait",
      "platform": "tiktok",
      "placement": "feed",
      "direction": "portrait",
      "size": {"width": 1080, "height": 1920},
      "aspect": "9:16",
      "duration": {"min_ms": 5000, "max_ms": 60000},
      "formats": ["mp4"],
      "fps": {"min": 29, "max": 60},
      "max_bytes": 524288000,
      "safe_area_px": {"top": 90, "right": 288, "bottom": 210}
    },
    {
      "spec_id": "dv360_html5_300x250",
      "platform": "dv360",
      "placement": "display",
      "format": "html5",
      "size": {"width": 300, "height": 250},
      "max_zip_bytes": 5242880,
      "click_behavior": "clickTag"
    }
  ]
}
```

> 真实运营中，请以《Google 广告规范》《Meta 广告素材规格》《TikTok 广告规范》《DV360 帮助中心》最新版本为准；
> 本文数据采集于 2026-08，个别数值可能随平台更新，系统应以规格配置中心为准而非硬编码。### 2.2 单素材多平台适配（Adaptation）

#### 2.2.1 适配的本质：从"一个主素材"到"多规格成品"

适配（Adaptation）不是简单缩放，而是把品牌内容表达的最佳状态迁移到不同画幅与约束下。
一个合格的适配系统应遵守三条铁律：

1. **内容无损优先**：先尝试无需重编码的复用（remux / container 转换），仅当画幅或规格不满足时才做有损变换；
2. **语义安全**：裁剪 / 重排不能切断主体（人脸、产品、文字），要依赖显著图（Saliency / Attention Map）与对象检测；
3. **可回溯**：每种适配都记录"主素材 → 变换步骤 → 成品"的变换图（Transformation Graph），便于审计与重建。

#### 2.2.2 适配策略：裁剪 vs 重排 vs extend

| 策略 | 英文 | 原理 | 适用场景 | 风险 / 权衡 |
| --- | --- | --- | --- | --- |
| 裁剪 | Crop | 按目标画幅从原图中心/显著区域裁取 | 从 16:9 主视频裁成 9:16 / 1:1 | 会丢失左右两侧内容，可能切到主体 |
| 重排 | Reposition/Pan | 在保留全部内容前提下重新布局文字/LOGO/主体位置（模板再合成） | 模板化素材，元素可独立摆放 | 需要结构化素材（分层 PSD / JSON 布局） |
| 延伸 | Extend | 用内容外扩（模糊填充、渐变、镜像、AI 生成背景）填满画幅 | 从方形/横向扩展到竖屏全屏 | AI 填充有幻觉风险，需人工抽检 |
| 模糊填充 | Blur Extend | 背景复制 + 高斯模糊 + 暗化，前景叠加 | 视频竖屏化快速兜底 | 视觉档次偏低，仅用于低优先级 |
| 视频镜像填充 | Mirror Extend | 左右镜像复制边缘像素填充 | 不适合有人脸/文字场景 | 会有明显接缝，谨慎 |
| 显著区裁剪 | Saliency Crop | 用显著性检测驱动裁剪窗口的平移缩放 | 高质量图片/视频裁剪 | 计算成本高，需逐帧处理 |
| 智能重排 | Smart Reframe | 逐帧跟踪主体（对象跟踪）并动态改变裁剪窗口 | 人物说话 / 运动视频竖屏化 | 抖动需平滑，易产生跳变 |

#### 2.2.3 通用适配流程（流水线级）

```
主素材（video/image/html5）
   │
   ▼
┌─[1. 探针 Probe]────────────────────────────┐
│  ffprobe 读宽高/时长/fps/码率/编码/音频       │
│  OpenCV 读帧作显著性/人脸/文字检测           │
└─────────┬──────────────────────────────────┘
          ▼
┌─[2. 规格匹配 Spec Match]───────────────────┐
│  目标规格 (target spec) 的宽高比/时长/格式   │
│  与主素材宽高比 diff → 决定 crop/extend       │
└─────────┬──────────────────────────────────┘
          ▼
┌─[3. 策略路由 Strategy Router]──────────────┐
│  - 画幅不同 → crop / extend / smart-reframe │
│  - 时长超限 → 掐头去尾/加速/循环压缩         │
│  - 格式不符 → 转码 / 合成 HTML5              │
└─────────┬──────────────────────────────────┘
          ▼
┌─[4. 执行渲染 Render Execute]───────────────┐
│  FFmpeg CLI / 分层合成引擎 / headless 截图   │
│  -c:v libx264 -preset slow -crf 18          │
└─────────┬──────────────────────────────────┘
          ▼
┌─[5. 再校验 Re-lint]────────────────────────┐
│  尺寸/时长/大小/码率/安全区/字幕全部重查      │
│  失败则进入人工复核队列                      │
└─────────┬──────────────────────────────────┘
          ▼
        成品（render）写入对象存储 + 元数据登记
```

#### 2.2.4 图片适配：显著图裁剪（Saliency Crop）

核心算法：先算显著性热图（Saliency Map），再让裁剪窗口覆盖最"有料"区域并尽量满足目标画幅。

```python
# -*- coding: utf-8 -*-
"""图片显著图引导的智能裁剪示例（Pillow + OpenCV）"""
import cv2
import numpy as np

def saliency_map(img_bgr):
    """基于 OpenCV 静态显著图的简化实现（可用深度模型替代）"""
    sal = cv2.saliency.StaticSaliencySpectralResidual_create()
    ok, smap = sal.computeSaliency(img_bgr)
    # 归一化到 0-255
    smap = (smap * 255).astype("uint8")
    return smap

def smart_crop(img_bgr, target_aspect, margin=0.05):
    h, w = img_bgr.shape[:2]
    t_h, t_w = \
        (h, int(h * target_aspect)) if (h / w >= target_aspect) else (int(w / target_aspect), w)
    # 裁剪窗口不能超过原图
    t_w = min(t_w, w); t_h = min(t_h, h)

    smap = saliency_map(img_bgr)
    # 集成显著图（目标窗口内显著值之和最大化）
    best_box, best_score = None, -1
    step = max(1, t_w // 8)
    for x in range(0, w - t_w + 1, step):
        for y in range(0, h - t_h + 1, step):
            roi = smap[y:y + t_h, x:x + t_w]
            score = roi.sum()
            if score > best_score:
                best_score, best_box = score, (x, y)
    # 微调中心化：靠近画面中心的显著分加权
    c_x, c_y = best_box[0] + t_w / 2, best_box[1] + t_h / 2
    c = np.array([c_x / w, c_y / h]) - 0.5
    center_bonus = 1.0 - (np.abs(c).sum() * 0.1)   # 越居中惩罚越小
    best_score *= center_bonus
    return best_box, (t_w, t_h)

if __name__ == "__main__":
    img = cv2.imread("master.jpg")
    box, size = smart_crop(img, target_aspect=9 / 16)
    x, y = box
    tw, th = size
    crop = img[y:y + th, x:x + tw]
    cv2.imwrite("feed_9x16.jpg", crop)
    print("crop box:", box, "size:", size)
```

#### 2.2.5 视频适配：Smart Reframe（动态裁剪窗口）

竖屏化最专业的路径是逐帧跟踪主体并平滑移动裁剪窗口。核心难点是**平滑性**：
直接逐帧独立求最优窗口会产生抖动。解决方案是对窗口中心与宽高做低通滤波（如 EMA / 卡尔曼滤波）。

```python
"""
视频智能重排（Smart Reframe）伪代码：
输入  原始视频 + 目标纵横比
输出  平滑裁剪窗口序列 + 渲染视频
"""
def reframe_pipeline(src, target_aspect, out):
    # 1. 抽样解析（每 0.25s 取一帧）
    frames = sample_frames(src, interval=0.25)
    # 2. 逐帧检测主体中心（对象检测 + 显著图）
    centers = [detect_focus(f) for f in frames]
    # 3. 平滑（EMA：alpha=0.3 或使用 oneEuro 滤波器抑制抖动）
    smooth = one_euro_filter(centers, min_cutoff=0.8, beta=0.01)
    # 4. 生成裁剪窗口（宽高 = target_aspect 匹配，中心 = smooth）
    windows = [make_window(c, target_aspect, frame_shape) for c in smooth]
    # 5. 用逐帧裁剪渲染（可用 ffmpeg 逐帧滤镜实现）
    render_crops(src, windows, target_aspect, out)
    return out

# 关键经验：
#  - 双手环动时窗口应保留手部，但手势结束后应回到脸部
#  - 防止窗口跳变：任何两帧窗口中心位移 > 帧宽 20% 时强制平滑
#  - 人物出框兜底：若主体超出窗口，扩大窗口到原始比例
```

#### 2.2.6 视频 Extend（扩展背景）

当主素材是横向而目标须为竖屏、又不希望丢失内容时，用"背景延伸 + 前景居中"方案：

```bash
# 方案：把横屏视频缩小居中，上下用镜像+模糊背景填充，输出 9:16。
# 输入 master_16x9.mp4 (1920x1080) -> 输出 portrait_9x16.mp4 (1080x1920)
ffmpeg -i master_16x9.mp4 \
  -filter_complex "\
    [0:v]scale=1920:1080,split[bg][fg];\
    [bg]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,\
        gblur=sigma=18,eq=brightness=-0.15[bgblur];\
    [fg]scale=1080:-2[fgc];\
    [bgblur][fgc]overlay=(W-w)/2:(H-h)/2[outv]" \
  -map "[outv]" -map 0:a -c:v libx264 -crf 18 -preset slow -c:a aac \
  -movflags +faststart portrait_9x16.mp4
```

要点：
- `force_original_aspect_ratio=increase` + `crop` 保证背景填满且不变形；
- 背景比前景暗 15% 提升前景主体层级；
- 模糊 σ=18 左右视觉平衡；σ 过大会发糊，过小则穿帮。

---

### 2.3 创意资产统一管理与版本控制

#### 2.3.1 为什么创意要"git 化"

创意是一个持续演进的对象：设计师上传主素材 → AI 生成变体 → 投放修改（换 CTA/配色）→ 回滚。
传统文件库无法回答"这一版和上一版差在哪"、"这个素材当前在哪些平台在跑"。
把创意当成代码来管理（资产即代码，Asset as Code）能带来：
1. **可回滚**：任何版本可一键回滚；
2. **可追溯**：每次变更记录提交人、提交原因、影响范围；
3. **可评审**：拉 diff（视觉 + 元数据）即可走审核；
4. **可协同**：多角色（设计/AI/投放/法务）并行操作互不覆盖。

#### 2.3.2 Git 化落地方案：对象存储 + 版本树

实际不会把二进制放进 Git 仓库（太大），而是**用"元数据版本树 + 存储地址引用"**模拟 git：

```
Git 隐喻               UCMS 实现
──────────────────────────────────────────────
commit / 版本           asset version (v1, v2, ...)
分支 branch             变体集 variant set / 实验实验组
main 主干              master 资产（最高优先级）
clone                 render 复制产物
merge / rebase        从最新主素材重建衍生资产
tag                    release 里程碑（审核通过 / 上架）
```

版本树数据模型：

```json
{
  "asset_id": "a1...01",
  "head": "v3",
  "versions": [
    { "version": "v1", "content_hash": "h1...", "message": "首版产品图",
      "author": "designer:wang", "created_at": "2026-08-01T08:00Z",
      "parent": null, "ref": "s3://ucms/masters/a1/h1.jpg" },
    { "version": "v2", "content_hash": "h2...", "message": "AI 生图增强背景",
      "author": "pipeline:ai", "created_at": "2026-08-02T10:00Z",
      "parent": "v1", "ref": "s3://ucms/masters/a1/h2.jpg" },
    { "version": "v3", "content_hash": "h3...", "message": "去掉水印，修复文字被切",
      "author": "designer:li", "created_at": "2026-08-03T09:30Z",
      "parent": "v2", "ref": "s3://ucms/masters/a1/h3.jpg" }
  ],
  "branch": "main"
}
```

#### 2.3.3 命名规范

统一命名规范能极大降低检索与协作成本。推荐**分层命名 `平台_规格_主题_变体_语言_版本`**：

```
文件命名模板：
{platform}_{width}x{height}|{aspect}_{subject}_{variation}_{locale}_{vN}.{ext}

示例：
meta_feed_1080x1350_summer-sale_hook-hero_en_v3.jpg
tiktok_feed_1080x1920_summer-sale_cta-blue_en_v1.mp4
google_discover_1200x628_summer-sale_product-v2_es_v2.png
dv360_html5_300x250_summer-sale_animated_v1.zip
```

| 段 | 允许字符 | 示例 | 约束 |
| --- | --- | --- | --- |
| platform | meta/tiktok/google/dv360/pangle/amazon | tiktok | 小写，枚举 |
| 规格 | {w}x{h} 或 aspect + 版位 | 1080x1920 / feed_9x16 | 与规格矩阵对应 |
| subject | 短横线连接的主题 | summer-sale | 无空格，小写 |
| variation | 变体语义 | hook-hero / cta-blue / free-ship | 简短 |
| locale | ISO 639-1 + 区 | en / en-us / es-mx | 小写 - |
| version | vN | v1 | 从 1 递增 |

#### 2.3.4 素材生命周期状态机

```
            ┌──────────── 生命周期状态机 ────────────┐
            │                                        │
  DRAFT ──► UPLOADED ──► VALIDATING ──► APPROVED ──► RELEASED ──► ARCHIVED
            │              │  (规格/合规/技术校验)      │      ▲
            │              ▼                          │      │
            │          REJECTED ◄─────────────────────│      │
            │              │                          │      pending → live
            ▼              ▼                          ▼      （对端状态）
        DELETED (草稿可删)   │                     PAUSED ◄─► RELEASED（暂停/恢复）
                            └── 所有终态不可逆后进入保留期
```

| 状态 | 含义 | 可执行动作 | 审计要求 |
| --- | --- | --- | --- |
| DRAFT | 工作台草稿，未上传原片 | 编辑元数据、删除 | 记录创建者 |
| UPLOADED | 原片已入存储 | 触发校验、走审核 | 记录上传渠道/大小/hash |
| VALIDATING | 校验中 | 等待规格与合规结果 | 记录探针输出 |
| REJECTED | 规格/合规/技术上不通过 | 修改后重提 / 终止 | 记录拒绝原因 |
| APPROVED | 审核通过，可被投放引用 | 生成渲染、发布 | 记录审核人/时间 |
| RELEASED | 已发布到某平台且 live | 暂停 / 下线 / 归档 | 记录 release_id 与对端状态 |
| PAUSED | 对端暂停 | 恢复 | 记录操作人 |
| ARCHIVED | 不再使用但保留 | 只读 / 永久删除(需权限) | 记录归档人/原因 |

#### 2.3.5 审核工作流

审核是"资产即事实"中最重要的合规闸门。一个典型的两级审核：

```
提交审核 ──► 机审（自动） ──► 通过 ──► 终审（人工）
              │                    │
              ├─ 违禁词/合规/敏感            ├─ 品牌安全/视觉抽检
              ├─ 规格 Lint                  └─ 通过 → APPROVED
              ├─ 技术校验（能打开/解码）
              └─ 拒绝 → 返回修改建议
```

机审规则可以是规则表，也可接入审核模型（如视觉内容安全模型）。
审核结果必须结构化落库，便于追溯与二次利用（模型训练、规则排查）。

```json
{
  "review_id": "rv-20260814-0001",
  "asset_id": "a1...01",
  "checks": [
    {"name": "spec_lint", "pass": true, "detail": "尺寸 1080x1350 合规，时长 12s 合规"},
    {"name": "watermark", "pass": true, "detail": "未检测到第三方水印"},
    {"name": "text_ratio", "pass": true, "detail": "文字占比 11% < 20%"},
    {"name": "prohibited_words", "pass": true, "detail": "无敏感词命中"},
    {"name": "decode", "pass": true, "detail": "ffprobe 可解码，码率正常"}
  ],
  "verdict": "APPROVED",
  "reviewed_by": "policy:v1 + human:shli",
  "reviewed_at": "2026-08-14T09:40Z"
}
```

---

### 2.4 AI 创意生成流水线

#### 2.4.1 全链路自动化总览

跨平台创意生产的现代范式是"从文案到成品"的全链路自动化：
以品牌简报（Brief）为输入，产出多平台、多语言、多变体的成套素材。

```
品牌简报 Brief ──► AI 文案 (LLM) ──► AI 视觉/视频/HTML5 ──► 本地化 ──► Batch 生成 ──► 校验 ──► 入库
   │                   │                    │                 │              │
   │ 产品/卖点/CTA       │ 标题/主体/CTA 变体  │ 文生图/图生视频    │ 多语言 TTS    │ 批量并行
   │ 参考图/风格         │ 5-20 条            │ 模板合成          │ 字幕翻译      │ 规格适配
   └────────────────────┴────────────────────┴─────────────────┴──────────────┘
```

#### 2.4.2 文案生成（LLM Copywriting）

LLM 生成广告文案的核心是**结构化提示词 + 可枚举变体**，而不是一次给一个大 prompt 让模型自由发挥。

##### 结构化提示词（Prompt）模板

```text
你是一个资深 DTC 电商营销文案专家。请基于以下品牌简报生成 {N} 条高转化短文案。

【品牌简报】
- 产品：{product_name}
- 核心卖点：{usps：用逗号分隔}
- 目标人群：{audience}
- 价格/促销：{price}/{promo}
- 语气：{tone：energetic|minimal|premium|playful}
- 平台：{platform}（信息流/Reels/Stories）
- 语言：{locale}

【要求】
1. 输出为 JSON 数组，每项含 {headline, body, cta, hook} 四个字段；
2. headline ≤ 30 字符，body ≤ 90 字符，包含至少一个具体数字或利益点；
3. 使用 {tone} 语气，避免空洞形容词（如"高品质""好用"）；
4. 提供 2 种 hook 风格：问题式 / 断言式；
5. 不要出现违禁词（绝对化用语、医疗功效承诺）。
【输出格式】
[{"headline": "...", "body": "...", "cta": "立即购买", "hook": "..."}]
```

##### 变体枚举策略

为避免文案视觉疲劳，同一条文案应生成多套"头尾搭配"：

| 维度 | 变体数 | 示例 |
| --- | --- | --- |
| hook 开头 | 3 | 问题式 / 断言式 / 数字式 |
| CTA 措辞 | 3 | 立即购买 / 限时抢购 / 现在下单 |
| 强调主体 | 2 | 卖点前置 / 痛点前置 |
| 语气 | 2 | energetic / minimal |

组合数 = 3×3×2×2 = 36 条文案，再经去重与规范校验后入库。

##### 文案生成并结合 AIGC 校验（服务端微调版）

```python
# 调用 LLM 生成文案 + 后端过滤
import json, re

def gen_copies(brief: dict, n: int = 8) -> list[dict]:
    prompt = build_prompt(brief, n)          # 见上文模板
    raw = llm_chat(prompt, temperature=0.9, max_tokens=2000)
    try:
        items = json.loads(extract_json(raw))
    except Exception:
        items = []
    # 后处理过滤
    out = []
    for it in items:
        it["headline"] = it.get("headline", "")[:30]
        it["body"] = it.get("body", "")[:90]
        if not it["headline"] or not it["body"]:
            continue
        if banned(it["headline"] + it["body"]):   # 违禁词检测
            continue
        out.append(it)
    return out[:n]
```

#### 2.4.3 文生图 / 图生图（AI Image）

由文案/产品图生成多种视觉变体。常见的三种模式：

| 模式 | 输入 | 输出 | 用途 |
| --- | --- | --- | --- |
| 文生图 Text2Img | 产品 + 风格 prompt | 全新场景图 | 白底换场景、节日氛围 |
| 图生图 Img2Img | 产品图 + prompt | 保持主体改风格 | 生成多背景/多季节 |
| ControlNet | 产品图 + 姿态/布局条件 | 精确控制构图 | 保证产品形态不崩坏 |

AIGC 生成需注意防幻觉与品牌一致性：
- 产品细节（logo、颜色、SKU 形态）需在 prompt 中强约束，或使用 ControlNet / IP-Adapter 锚定；
- 生成后用"一致性校验"（产品特征比对）过滤不符变体。

```python
STYLE_PROMPT = ("产品照片，", ...)
def gen_product_scene(product_img, scene_prompt, out_path):
    # 使用 SDXL/Flux 类模型 + IP-Adapter 保持产品身份
    image = text_to_image(
        prompt=f"{product_desc}, {scene_prompt}, 高端电商摄影，清晰，超高清",
        negative_prompt="模糊, 变形, 多指, 水印, 文字, logo 错乱",
        num_inference_steps=28,
        guidance_scale=6.5,
        ip_adapter=product_img,          # 锚定产品特征
    )
    image.save(out_path)
```

#### 2.4.4 AI 视频（Text to Video / Image to Video）

AI 视频正成为短视频素材主力。常用两类路径：

| 路径 | 说明 | 典型生成时长 | 产出版本 |
| --- | --- | --- | --- |
| 图生视频 I2V | 给一张主视觉，生成符合运动的短片（3-8s） | 30-60s 生成 3-5s | 做 hero 片段 |
| 文生视频 T2V | 直接描述场景生成 | 60-120s 生成 3-5s | 做氛围/产品演示 |
| 视频到视频 V2V | 风格化 / 动作延续 | 更长 | 量产降本 |

**视频生成的最佳实践：**

```
1. 先定"镜头语言"：单产品特写 / 使用场景 / 前后对比
2. 给出首尾帧（I2V）稳定主体与运动起点终点
3. 输出分辨率：先 720p 试跑，高质量再上 1080p（成本线性）
4. 帧率：生成 24fps，投放时保持 24 或升到 30（避免重编码成本）
5. 时长：贴合平台推荐（TikTok 5-15s / Reels 15-30s）
6. 生成后用 AI 滤镜做 9:16 竖屏输出 + 加字幕 + 加音乐
```

```python
def gen_i2v(first_frame, motion_prompt, duration_s=4, fps=24, out="hero.mp4"):
    clip = image_to_video(
        image=first_frame,
        prompt=motion_prompt,
        duration=duration_s,
        fps=fps,
        resolution=(720, 1280),        # 竖屏优先
    )
    clip.write_videofile(out, codec="libx264", audio_codec="aac")
    return out
```

#### 2.4.5 动态模板（Dynamic Template）

动态模板是"结构化 + 参数化"的 HTML5/图片载体：一套模板 + 数据（文案/图片/CTA）→ 批量实例化。

```
模板类型：video_templates / banner_templates / native_templates
模板 = 布局骨架（Layout）+ 插槽（Slot）+ 变量（Variable） + 样式（Style）

变量示例：
  {{headline}}  主标题
  {{body}}      描述
  {{cta}}       行动号召
  {{image_url}} 主图
  {{bg_color}}  背景色
  {{logo_url}}  Logo
```

**模板实例化示例（简单图片合成 / banner）：**

```python
from PIL import Image, ImageDraw, ImageFont

def render_banner(template, data, out_path):
    bg = Image.open(template["bg"]).convert("RGBA")
    draw = ImageDraw.Draw(bg)
    # 变量填充
    draw.text((80, 40), data["headline"],
              font=ImageFont.truetype(template["font"], 34), fill=data.get("title_color", "#111827"))
    draw.text((80, 96), data["body"],
              font=ImageFont.truetype(template["font"], 20), fill=data.get("body_color", "#4b5563"))
    # CTA 圆角按钮
    draw.rounded_rectangle((80, 160, 280, 205), radius=14, fill=data["cta_color"])
    draw.text((110, 170), data["cta"], font=ImageFont.truetype(template["font"], 20), fill="#fff")
    # 主图叠加（等比缩放）
    product = Image.open(data["image"]).convert("RGBA")
    w_r = (bg.width - 320) / product.width
    product = product.resize((int(product.width * w_r), int(product.height * w_r)))
    bg.paste(product, (70, 220), product)
    bg.convert("RGB").save(out_path)
```

#### 2.4.6 本地化（Localization）

面向出海，本地化是必然环节。本地化不止翻译，还要做文化/合规适配：

| 环节 | 做法 | 工具/示例 |
| --- | --- | --- |
| 文本翻译 | LLM + 术语表（Glossary）约束 | prompt 中注入 brand_glossary |
| 字数适配 | 德语/西语通常比英文长 15-30% | 自动检测文本溢出，触发重新排版 |
| 字幕/配音 | TTS 生成目标语言，字幕烧录 | TTS + 音频对齐 |
| 本地合规 | 各地区广告法（如法国医保、德国性价比声明） | 合规规则按 locale 分流 |
| 货币/价格 | 数字本地化（€、$、¥）与符号位置 | i18n 数字格式化 |
| 右左语言 | RTL（阿拉伯语/希伯来语）排版反转 | 镜像布局 + 文本方向属性 |

```python
def localize(copies: list[dict], locale: str, glossary: dict) -> list[dict]:
    results = []
    for c in copies:
        translated = llm_chat(
            f"把以下广告文案翻译成 {locale}，严格使用术语表：{glossary}\n"
            f"headline: {c['headline']}\nbody: {c['body']}\ncta: {c['cta']}"
        )
        results.append(merge_fields(c, translated))
    return results
```

#### 2.4.7 批量生成（Batch）与流水线编排

批量生成是大规模内容生产的核心机制。用一份 JSON 定义"生成批次"，下游 worker 并行消费。

**流水线编排（Python + 阶段 DAG 简化版）：**

```python
"""
批处理编排：把一批 brief 跑成一批素材。
阶段：copy -> image/video -> localize -> render -> lint -> publish
"""
import concurrent.futures as cf

def run_pipeline(batch: dict):
    tasks = batch["tasks"]                       # 若干 brief
    stage = batch.get("stage", "copy")
    with cf.ThreadPoolExecutor(max_workers=batch.get("parallel", 8)) as pool:
        if stage == "copy":
            return pool.map(gen_copies, tasks)
        if stage == "media":
            return pool.map(gen_media_variant, tasks)
        if stage == "localize":
            return pool.map(lambda t: localize(t["copies"], t["locale"], batch["glossary"]), tasks)
        if stage == "render":
            return pool.map(render_all, tasks)
        if stage == "lint":
            return pool.map(lint_all, tasks)
```

**批次定义 JSON：**

```json
{
  "batch_id": "bat-20260814-003",
  "product_id": "SKU-9910",
  "campaign": "summer-sale",
  "locales": ["en-US", "es-MX", "de-DE", "fr-FR"],
  "platforms": ["meta", "tiktok", "google", "dv360"],
  "copy_variants": 8,
  "media_variants": 6,
  "stages": ["copy", "media", "localize", "render", "lint", "publish"],
  "glossary": {
    "en-US": {"free shipping": "Free Shipping", "limited": "Limited Offer"},
    "es-MX": {"free shipping": "Envío Gratis", "limited": "Oferta Limitada"}
  },
  "parallel": 16,
  "on_fail": "keep_running"
}
```

#### 2.4.8 统一 DCO 前的铺垫：把生成与动态优化衔接

AI 批量生成天然产生"大量组合候选"，这正是 DCO 的燃料。
生成的每套素材（文案 + 图片 + CTA + 背景）都保留**结构化标签**（情感、主体、配色、版式），
这些标签将用于 DCO 的组合矩阵与后续 CTR 学习（见 2.5）。
---

### 2.5 动态创意优化（DCO）

#### 2.5.1 DCO 是什么

DCO（Dynamic Creative Optimization，动态创意优化）指**不在投放前固化素材**，而是把创意拆成可组合的元素，
在（接近）实时的投放过程中，针对每个用户/每次曝光/每个上下文动态组装广告，并不断学习最优组合。
DCO 的价值：以更小数量的素材服务长尾个性化，同时用数据驱动持续收敛到最优创意。

```
传统投放：预制 N 张图 → 人工 / A/B 分配 → 固定
DCO 投放：预制"元素池"（图/文案/CTA/配色/背景）→ 组合引擎实时组 → 每用户不同 → 学习器收敛
```

#### 2.5.2 各平台 DCO 机制对比

| 平台/产品 | 机制 | 元素/资产 | 组合方式 | 学习信号 | 特点 / 局限 |
| --- | --- | --- | --- | --- | --- |
| Meta Dynamic Creative | 动态创意（DC） | 图片/视频/文案/标题/CTA/落地页 | 平台自动组合所有资产 | 转化/点击 | 自动化强，但**黑盒**：无法干预具体组合、无法精细控制 |
| Google RSA (Responsive Search) | 响应式搜索广告 | 15 个标题 + 4 条描述 + 3 链接 | Google 自动排列 | 点击/转化 | 自动化标题描述，可固定（pinned）某些位置 |
| Google RDA (Responsive Display) | 响应式展示 | 图 4 张 + 标题 5 + 描述 | Google 组合 | 转化 | 自动生成，可配自有图 |
| TikTok Dynamic Creative | 动态创意 | 多视频/多文案/多 CTA | 平台自动组合 | 转化 | 自动组合在 TikTok 广告里逐个组合 |
| DV360 Dynamic Creative (LSA/DOOH) | 动态素材（feed-based） | 云端模板 + 数据 feed | 数据字段渲染生成 | 投放数据 | 偏 "Template+Data" 不偏好测组合；广告服务器渲染 |

**对比要点：**
- **平台内建 DC（Meta/TikTok/Google）**：学习在平台内闭环，数据充分，但"黑盒"、无法迁移、无法干预；
- **平台外统一 DCO**（本文重点）：元素组合 + 决策发生在 UCMS，通过上传多个变体 + 外部实验 + Bandit 调度，保证可控与可迁移。

#### 2.5.3 统一 DCO 架构

统一 DCO 的核心是把"平台内建学习"升级为"自建可控学习层"：

```
元素池 Asset Pool
  ├── 图片 variants[]（背景/主体/配色）
  ├── 文案 copies[]（hook/CTA/body）
  ├── 视频 clips[]（hero/demo/testimonial）
  └── HTML5 模板 templates[]
        │
        ▼
  组合矩阵 Combos（笛卡尔积，预先去重/去劣）
  ├── (img_1, copy_2, cta_3)
  ├── (img_2, copy_1, cta_2)
  └── ...（受规则引擎约束）
        │
        ▼
  线上调度器 Scheduler
  ├── Bandit 分配曝光（探索/利用）
  ├── 规则引擎硬约束（品牌/频控/合规/豁免）
  └── CTR/转化学习（多臂老虎机 / 贝叶斯）
```

#### 2.5.4 元素池与标签（结构化）

DCO 的前提是元素可被结构化和批量组合。每个元素带标签向量（用于规则引擎与学习器特征）：

```json
{
  "element_id": "copy_20260814_2",
  "type": "copy",
  "content": "夏日清凉，7 折起步",
  "tags": {
    "tone": "energetic",
    "hook": "assertive",
    "cta": "limited",
    "emoji": true,
    "length": "short"
  },
  "score_window": {"clicks": 120, "views": 4000, "ctr": 0.03}
}
```

#### 2.5.5 组合矩阵（Combination Matrix）

组合矩阵 = 各元素类型做笛卡尔积，但会做约束剪枝。理论组合数可能爆炸，需要**规则剪枝 + 样本量预算**。

**笛卡尔积与剪枝：**

```python
import itertools

def build_combos(images, copies, ctas, templates, rules):
    raw = []
    for img, copy, cta, tpl in itertools.product(images, copies, ctas, templates):
        combo = {"image": img, "copy": copy, "cta": cta, "template": tpl}
        combo["combo_id"] = f"{img.id}|{copy.id}|{cta.id}|{tpl.id}"
        combo["features"] = merge_tags(img, copy, cta, tpl)
        if rules.passes(combo["features"]):      # 规则引擎过滤
            raw.append(combo)
    return raw
```

**组合规模估算示例：**

| 元素池大小 | 组合数（未剪） | 剪枝后 | 结论 |
| --- | --- | --- | --- |
| 3 图 × 4 文案 × 2 CTA × 2 模板 | 48 | 40 | OK |
| 6 图 × 12 文案 × 4 CTA × 4 模板 | 1152 | ~600 | 需 Bandit 预算管理 |
| 10 图 × 30 文案 × 6 CTA × 6 模板 | 10800 | ~3000 | 必须收敛，否则流量不足 |

**经验法则**：单广告组同时测试的组合数量建议 ≤ 10-15 个（样本份额足够）；更大元素池应拆成多轮、多广告组，避免稀释统计功效。

#### 2.5.6 规则引擎（Rule Engine）

规则引擎负责**硬约束**，在任何学习器之前强制生效：

```
规则类型：
1. 合规规则  某些地域禁用某些文案（如"最"字绝对化用语）
2. 品牌规则  指定产品只能与指定背景组合；禁用竞品色
3. 频控规则  与最近打过的广告不重复/低重复
4. 技术规则  某些规格必须用固定模板（如 HTML5 必须用 DV360 模板）
5. 预算规则  低保底组合（如预算小时级 < X 时退化为人工指定）

实现：声明式规则（JSON/YAML）+ 规则求值引擎
```

**规则定义示例（YAML）：**

```yaml
rules:
  - id: "geo-banned-copy"
    type: "compliance"
    condition:
      all:
        - locale: "de-DE"
        - copy.banned: "garantiert"
    action: "block"
    message: "德国禁用语"

  - id: "brand-palette"
    type: "brand"
    condition:
      all:
        - product.category: "sunscreen"
        - image.dominant_color: "competitor_blue"
    action: "block"

  - id: "low-budget-fallback"
    type: "budget"
    condition:
      and:
        - budget_per_hour_usd: { "lt": 100 }
        - combo_count: { "gt": 20 }
    action: "reduce_to_best_k"
    params: { k: 5 }
```

#### 2.5.7 CTR 学习（多臂老虎机 / 贝叶斯）

DCO 的在线优化需要"探索-利用"平衡。经典做法：

| 算法 | 思想 | 场景 |
| --- | --- | --- |
| ε-Greedy | 以 ε 概率随机探索，否则用当前最优 | 冷启动 |
| UCB1 | 综合考虑均值与不确定性（上置信界） | 通用 |
| Thompson Sampling | 用 Beta 分布后验抽样，天然平衡探索利用 | 转化率场景，推荐 |

**Thompson Sampling（Beta-Bernoulli）实现：**

```python
import numpy as np

class ThompsonCreativeBandit:
    """对每个 combo 维护 Beta(a, b)，按后验抽样决定下一曝光"""
    def __init__(self, combos, alpha_prior=1.0, beta_prior=1.0):
        self.alpha = {c: alpha_prior for c in combos}
        self.beta  = {c: beta_prior  for c in combos}

    def select(self):
        # 用后验抽样代替单纯最大值，天然含探索
        scores = {c: np.random.beta(self.alpha[c], self.beta[c]) for c in self.alpha}
        return max(scores, key=scores.get)

    def update(self, combo, reward):
        # reward in {0,1}
        self.alpha[combo] += reward
        self.beta[combo]  += (1 - reward)

# 使用
bandit = ThompsonCreativeBandit(combos)
for impression in range(10_000):
    c = bandit.select()
    outcome = serve_and_observe(c)     # 1=点击/转化
    bandit.update(c, outcome)
```

**收敛与保护：**
- 每个组合设 `min_impression`（如 2000）确保学习下限，低于它强制保底曝光；
- 设定止亏阈值：组合 CTR 显著低于基线时冻结其流量；
- 用贝叶斯后验对比做显著性判断，避免频繁 p 值滥用。

#### 2.5.8 统一 DCO 的落地路径

```

落地四步：
1. 元素入库：把现有 / AI 生成素材全部打标签入库（元素池）
2. 组合生成：按规格 + 规则剪枝生成候选组合（Combos）
3. 线上调度：接入 Bandit 分配曝光，实时记录 CTR/转化
4. 收敛反馈：把最优组合回流到"资产库"固化成稳定 creative

反模式：
- 把 100 个组合一次性全开 → 样本稀释，无法学习（应分批）
- 在没有规则引擎兜底时引入 AI 自由组合 → 合规/品牌事故
- 忽略低频组合的噪声 → 错误地过早淘汰好创意
```

---

### 2.6 创意性能分析与迭代

#### 2.6.1 创意级指标体系

创意性能分析需要"创意级"细粒度指标，而不只是广告组聚合。常用指标分三层：

| 层级 | 指标 | 定义 | 意义 |
| --- | --- | --- | --- |
| 曝光/触达 | impressions / reach / frequency | 展示次数、独立触达、平均频次 | 触达规模与疲劳起点 |
| 覆盖	（engagement）| CTR, VTR, 完播率, 3s 播放率, 互动率 | 点击率 / 视频观看率 / 完播 / 3 秒播放 / 点赞评论分享 | 素材吸引力 |
| 转化 | CVR, CPA, ROAS, 新增付费, LTV:CAC | 转化率 / 获客成本 / 广告支出回报率 / 终身价值 | 商业效果 |

**视频专项指标：**

| 指标 | 计算 | 用途 |
| --- | --- | --- |
| VCR%（Video Completion Rate） | 完播次数 / 播放次数 | 素材叙事完整性 |
| 3s 播放率 | 3s 以上播放 / 曝光 | 前 3 秒吸睛力 |
| 平均观看时长 | 总观看秒 / 播放 | 内容投入度 |
| 前 5s 跳出率 | 5s 内退出 | 开头失败诊断 |
| TaT (Time-to-conversion) | 曝光→转化时间 | 素材与漏斗配合 |

#### 2.6.2 创意疲劳诊断（Creative Fatigue）

创意疲劳指同一创意高频触达同一用户后效果衰减（CTR/转化下降）。诊断通常看两个信号：

**信号 1：CTR / CVR 随 Frequency 衰减曲线**

```
CTR
 │
 │  █
 │  ██
 │  ███
 │   ███
 │    ████
 │      ████        ← 开始明显衰减的转折点（疲劳临界 Frequency）
 │        █████
 │          ████
 └───────────────────────► 平均频次 Frequency
        1  2  3  4  5  6
```

**信号 2：疲劳指数（Fatigue Index）**

用近期表现相对基线衰减比量化：

```python
def fatigue_index(cur_ctr, baseline_ctr, cur_cpa, baseline_cpa,
                  freq, threshold_freq=4.0,
                  w_ctr=0.4, w_cpa=0.4, w_freq=0.2):
    ctr_decay = max(0.0, (baseline_ctr - cur_ctr) / max(baseline_ctr, 1e-9))
    cpa_infl  = max(0.0, (cur_cpa - baseline_cpa) / max(baseline_cpa, 1e-9))
    freq_risk = max(0.0, (freq - threshold_freq) / threshold_freq)
    fi = w_ctr * ctr_decay + w_cpa * cpa_infl + w_freq * freq_risk
    return round(min(fi, 1.0), 3)   # 0-1，越高越疲劳

# 分级
def classify(fi):
    if fi < 0.3:  return "HEALTHY"
    if fi < 0.6:  return "WATCH"      # 观察
    if fi < 0.8:  return "REFRESH"    # 建议换素材/降频
    return "KILL"                     # 强制下线
```

**疲劳应对策略：**

| 等级 | 动作 |
| --- | --- |
| HEALTHY | 正常投放 |
| WATCH | 监测频控，准备替换素材池 |
| REFRESH | 换 CTA/配色/主体变体，降低单创意频次，开启频控 |
| KILL | 暂停该创意，让位给新素材 |

#### 2.6.3 迭代闭环：A/B + 多臂老虎机

创意迭代是"假设-验证-规模化"的连续循环：

```
                    ┌─────────────────────────────┐
                    │       创意迭代闭环           │
                    ▼                             │
  生成新创意 (batch) ──► 小流量 A/B (验证) ──► 统计显著? ──► 是──► 放量 / 固化为稳定创意
                          ▲                          │否
                          └────────── 反で淘汰/调整 ──┘
```

**A/B 测试要点（创意级）：**

| 方面 | 建议 |
| --- | --- |
| 同时测试数 | ≤ 3-5 个创意/广告组，避免统计功效稀释 |
| 样本量 | 依据预估 CTR 与期望提升计算（见下） |
| 时长 | 至少 72h，避开周末/大促扰动 |
| 显著性 | 使用贝叶斯 / 频率方法双保险；防止 p-hacking |
| 迭代周期 | 每周一轮：周一看板 → 周二换素材 → 周中评估 |

**样本量估算：**

```python
import math
from scipy import stats

def min_sample(ctr_ctrl, lift, alpha=0.05, power=0.8):
    """给出所需单组最小样本（点击近似为二项）"""
    z_alpha = stats.norm.ppf(1 - alpha / 2)
    z_beta  = stats.norm.ppf(power)
    p1 = ctr_ctrl
    p2 = ctr_ctrl * (1 + lift)
    pooled_p = (p1 + p2) / 2
    n = (z_alpha * math.sqrt(2 * pooled_p * (1 - pooled_p))
         + z_beta * math.sqrt(p1 * (1 - p1) + p2 * (1 - p2))) ** 2 / (p1 - p2) ** 2
    return int(math.ceil(n))

# 例：当前 CTR 1.5%，期望提升 20%
print(min_sample(0.015, 0.20))   # 单组每指标约需样本（展示/点击）
```

#### 2.6.4 闭环中的数据回流

迭代闭环需要把"表现数据"回流到生成侧，指导下一批创意：

```
表现数据（CTR/CPA/完播/疲劳） ──► 特征池 FeatureStore
      │
      └──► 1. 哪些风格/文案/配色跑得快（learnings）
           2. 失败特征黑名单（避免重复）
           3. 给 AI 生成的反思提示词（self-critique）
           4. 触发新一轮 batch 生成
```

**把学习反馈给 LLM（反思式提示）：**

```text
上一轮创意表现总结：
- 表现最好的 3 个：打法 A / 卖点 B / CTA C（CTR 高于基线 2.1x）
- 表现最差的 3 个：打法 D / 卖点 E（CTR 低于基线 0.5x）

请基于此生成下一轮 {N} 条文案：
1. 复用表现好的结构（{打法 A}），替换具体文案；
2. 避免出现 {打法 D} 的毛病（如开头过慢）；
3. 保持高 CTR 风格（{CTA C} 强度）。
```

