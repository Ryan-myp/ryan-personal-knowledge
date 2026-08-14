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

---

## 三、生产环境实战

### 3.1 运行环境与目录规范

#### 3.1.1 服务拓扑

生产环境建议如下部署单元：

| 服务 | 语言/运行时 | 说明 | 并发单元 |
| --- | --- | --- | --- |
| API Gateway | Go / Kratos | 对外 API、鉴权、限流 | 多副本无状态 |
| Asset Service | Go | 资产 CRUD、元数据、版本 | 依赖 PG |
| Render Service | Python + FFmpeg | 渲染农场面 | 可横向扩展 worker |
| AI Pipeline Service | Python | LLM / 图像 / 视频生成 | 异步 worker |
| DCO Service | Go | 组合、规则、Bandit | 内存 + Redis |
| Analytics Service | Python / Go | 指标计算、疲劳诊断 | 定时任务 |
| Platform Connector | Go | Meta/TikTok/Google/DV360 API | 各平台 worker |

#### 3.1.2 仓库目录规范（Monorepo 建议）

```
ucms/
├── api/                     # 对外 API 定义（OpenAPI/proto）
│   ├── asset/               # 资产生命周期
│   ├── render/              # 渲染任务
│   ├── release/             # 发布
│   └── analytics/           # 指标
├── spec/                    # 规格配置（YAML/JSON，单一事实源）
│   ├── platforms/
│   │   ├── meta.yaml
│   │   ├── tiktok.yaml
│   │   ├── google.yaml
│   │   └── dv360.yaml
│   └── rules/               # 合规/审核规则
├── renderers/               # 渲染引擎适配器
│   ├── ffmpeg/              # 视频/图片
│   ├── template/            # HTML5/图片模板合成
│   └── saliency/            # 显著图裁剪
├── ai/                      # AI 生成
│   ├── copy/                # 文案
│   ├── vision/              # 文生图/图生图
│   ├── video/               # 视频生成
│   ├── tts/                 # 配音/字幕
│   └── pipeline/            # 批次编排
├── dco/                     # 动态创意
│   ├── combos/
│   ├── rules/
│   └── bandit/
├── connectors/              # 平台对接
│   ├── meta/
│   ├── tiktok/
│   ├── google/
│   └── dv360/
└── internal/pkg/            # 通用库
```

#### 3.1.3 依赖与运行环境版本

| 组件 | 版本建议 | 说明 |
| --- | --- | --- |
| FFmpeg | ≥ 6.0（含 libx264, libx265, aom） | 视频处理主力 |
| Python | 3.11+ | AI 与渲染 |
| Go | 1.22+ | 控制面 |
| PostgreSQL | 14+ | 元数据、审核、发布、DCO 状态 |
| Redis | 6.2+ | 缓存、分布式锁、Bandit 计数 |
| Kafka | 3.x | 事件流（渲染完成、指标回传） |
| Object Storage | S3/GCS/OSS | 原片与产物 |
| Nginx/CDN | — | 素材分发、签名 URL |

### 3.2 规格引擎实现（Spec Engine）

#### 3.2.1 规格定义示例（YAML，以 Meta 为例）

```yaml
platform: meta
version: "2026-08"
placements:
  - name: feed
    category: feed
    media:
      - type: image
        allowed_formats: [jpg, png]
        size_ranges: [{max_w: 2048, max_h: 2048, aspect_ranges: [[1.0, 2.0]]}]
        max_bytes: 8388608
        text_ratio_max: 0.2
      - type: video
        allowed_formats: [mp4, mov]
        size_required: {w: 1280, h: 720}     # 最小
        size_recommended: {w: 1920, h: 1080}
        duration_ms: {min: 5000, max: 241000}
        fps: {min: 24, max: 60}
        max_bytes: 4294967296
        max_bitrate_kbps: 12000
        audio: {required: true}
  - name: reels
    category: short_video
    media:
      - type: video
        allowed_formats: [mp4]
        size_recommended: {w: 1080, h: 1920}
        aspect: "9:16"
        duration_ms: {min: 10000, max: 90000}
        fps: {min: 29, max: 60}
        max_bytes: 4294967296
        safe_area:
          top_fraction: 0.05
          bottom_fraction: 0.18
          right_fraction: 0.20
  - name: stories
    category: stories
    media:
      - type: image
        size_required: {w: 1080, h: 1920}
      - type: video
        size_required: {w: 1080, h: 1920}
        duration_ms: {max: 60000}
```

#### 3.2.2 规格校验器（Spec Linter）

规格校验把"探针探测到的素材实际参数"与"规格要求"比对，产出通过/失败：

```python
def lint_asset(probe: dict, spec: dict) -> dict:
    """probe 由 ffprobe 探测得到，spec 来自规格配置"""
    checks = []

    def check(name, ok, detail):
        checks.append({"name": name, "pass": bool(ok), "detail": detail})

    w, h = probe.get("width"), probe.get("height")
    aspect = w / h if w and h else None

    # 尺寸/比例
    for media_rule in spec["media"]:
        if media_rule["type"] != "video":
            continue
        ar = media_rule.get("aspect")
        if ar and aspect:
            target = float(ar.split(":")[0]) / float(ar.split(":")[1])
            check("aspect", abs(aspect - target) < 0.02,
                  f"aspect {aspect:.3f} vs {ar}")
        dur = probe.get("duration_ms")
        d = media_rule.get("duration_ms", {})
        if dur is not None:
            ok = (dur >= d.get("min", 0)) and (dur <= d.get("max", 1e12))
            check("duration", ok, f"{dur}ms")
        fps = probe.get("fps")
        f = media_rule.get("fps", {})
        if fps is not None:
            ok = (fps >= f.get("min", 0)) and (fps <= f.get("max", 1e5))
            check("fps", ok, f"{fps}fps")

    # 大小 / 码率
    size = probe.get("size_bytes")
    mb = spec.get("max_bytes")
    if size is not None and mb:
        check("size", size <= mb, f"{size} <= {mb}")

    passed = all(c["pass"] for c in checks)
    return {"passed": passed, "checks": checks}
```

#### 3.2.3 规格解析与生效策略

```
SpecResolver 职责：
1. 加载所有平台规格 → 内存缓存（60s 过期）
2. 给定 (platform, placement, format, orientation) → 返回对应 spec
3. 支持"推荐值"与"硬性约束"分离：推荐值只提示，硬约束必检
4. 规格变更走发布通道：改 YAML → CI 校验 → 热更新，不重启
```

```yaml
# 生效策略示例
resolution_policy: "recommended"     # recommended | required
duration_policy: "required"
text_ratio_policy: "required"
```

### 3.3 素材上传与处理流水线（Python）

#### 3.3.1 上传 API 设计

```
POST /v1/assets            # 创建资产记录并接收文件（分片/直传 S3 预签名）
POST /v1/assets/{id}/files # 关联文件
GET  /v1/assets/{id}       # 查询
PATCH /v1/assets/{id}      # 更新元数据
POST /v1/assets/{id}/render# 触发渲染
```

**上传创建（含去重与探针）：**

```python
import hashlib, uuid
from fastapi import FastAPI, UploadFile

app = FastAPI()

@app.post("/v1/assets")
async def create_asset(file: UploadFile, meta: str):
    data = await file.read()
    digest = hashlib.sha256(data).hexdigest()
    # 去重：同 hash 且同规格直接复用
    existing = find_by_hash(digest)
    if existing:
        return {"asset_id": existing["asset_id"], "dedup": True}

    asset_id = str(uuid.uuid4())
    url = upload_to_storage(asset_id, data, file.filename)   # S3 预签名/直传
    probe = probe_media(url)                                  # ffprobe + 采样
    record = insert_asset(
        asset_id=asset_id, sha256=digest, url=url,
        meta=json.loads(meta), probe=probe, status="UPLOADED")
    enqueue_validation(asset_id)                              # 触发异步校验
    return {"asset_id": asset_id, "probe": probe, "status": "UPLOADED"}
```

**探针（Probe）示例：**

```python
import json, subprocess

def probe_media(url) -> dict:
    """ffprobe 提取媒体技术参数"""
    cmd = ["ffprobe", "-v", "quiet", "-print_format", "json",
           "-show_format", "-show_streams", url]
    out = subprocess.check_output(cmd)
    info = json.loads(out)
    video = next((s for s in info["streams"] if s["codec_type"] == "video"), {})
    audio = next((s for s in info["streams"] if s["codec_type"] == "audio"), {})
    return {
        "codec": video.get("codec_name"),
        "width": int(video.get("width", 0)),
        "height": int(video.get("height", 0)),
        "fps": eval_rational(video.get("avg_frame_rate", "0/1")),
        "duration_ms": int(float(info.get("format", {}).get("duration", 0)) * 1000),
        "size_bytes": int(info.get("format", {}).get("size", 0)),
        "bitrate_kbps": int(info.get("format", {}).get("bit_rate", 0)) // 1000,
        "audio_codec": audio.get("codec_name"),
        "audio_sample_rate": int(audio.get("sample_rate", 0) or 0),
    }

def eval_rational(expr):
    try:
        a, b = expr.split("/")
        return round(float(a) / float(b), 3) if float(b) else 0.0
    except Exception:
        return 0.0
```

#### 3.3.2 异步校验队列

上传后发现是异步进行，状态机见 2.3.4。采用 Redis 队列或 Kafka 触发：

```bash
# 简单队列实现（Redis List + 消费者）
redis-cli LPUSH ucms:validate <asset_id>
# worker 弹出处理
redis-cli BRPOP ucms:validate 5
```

```python
def validation_worker():
    while True:
        asset_id = brpop("ucms:validate")
        asset = load_asset(asset_id)
        lint = lint_asset(asset.probe, resolve_spec(asset.spec))
        compliance = run_compliance_checks(asset)   # 违禁词/水印/合规
        approve = lint.passed and compliance.passed
        update_status(asset_id, "APPROVED" if approve else "REJECTED",
                      reason=collect_failures(lint, compliance))
```

### 3.4 渲染适配实现（Render Farm）

#### 3.4.1 渲染任务模型

```json
{
  "render_id": "r-20260814-0001",
  "asset_id": "a1...01",
  "target_spec": "meta_feed_video_landscape",
  "strategy": "crop_center",          // crop | extend | smart_reframe | template
  "status": "queued",
  "retries": 0,
  "worker": "ffmpeg-w2",
  "created_at": "...",
  "output": "s3://ucms/renders/r-20260814-0001.mp4"
}
```

#### 3.4.2 渲染作业编排（Python Worker）

```python
def render_worker(task: dict):
    spec = resolve_spec(task["target_spec"])
    src = get_master_url(task["asset_id"], task.get("version"))
    strategy = task["strategy"]

    if spec["format"] == "html5":
        out = render_html5(task, spec)
    elif strategy == "crop_center":
        out = ffmpeg_crop_center(src, spec, dst_size(task))
    elif strategy == "smart_reframe":
        out = run_smart_reframe(src, spec)
    elif strategy == "extend":
        out = ffmpeg_extend_blur(src, spec)
    else:
        out = ffmpeg_transcode_default(src, spec)

    # 渲染后强制再校验（re-lint）
    ok = lint_after_render(out, spec)
    if not ok:
        task["status"] = "failed"; record_error(task); return
    upload_render(out, task["render_id"], spec)
    mark_render_done(task["render_id"], out)
```

**FFmpeg 裁剪（crop_center）示例：**

```python
def ffmpeg_crop_center(src, spec, size):
    # 以目标纵横比居中裁剪并缩放到目标尺寸
    w, h = size
    inratio = spec_width(src) / spec_height(src)
    target = w / h
    if inratio > target:
        # 原图更宽 → 裁剪左右
        filter = f"crop=ih*{target}:ih,scale={w}:{h}"
    else:
        # 原图更高 → 裁剪上下
        filter = f"crop=iw:iw/{target},scale={w}:{h}"
    cmd = ["ffmpeg", "-i", src, "-vf", filter,
           "-c:v", "libx264", "-crf", "18", "-preset", "slow",
           "-pix_fmt", "yuv420p", "-movflags", "+faststart", out]
    subprocess.run(cmd, check=True)
    return out
```

#### 3.4.3 FFmpeg 生产参数建议

| 用途 | 视频编码 | 建议参数 |
| --- | --- | --- |
| 平台上传（通用） | H.264 | `libx264 -crf 18 -preset slow -pix_fmt yuv420p` |
| 竖屏清晰度优先 | H.264 | `-crf 16 -preset medium -profile:v high -level 4.2 -g 48 -sc_threshold 0` |
| 高压缩比（低流量） | H.264 | `libx264 -b:v 2500k -maxrate 3500k -bufsize 7000k` |
| 高保真归档 | H.265/HEVC | `libx265 -crf 20` (浏览器兼容性注意) |
| 音频 | AAC | `-c:a aac -b:a 192k -ar 48000 -ac 2` |
| 播放兼容 | 阴极 | `-movflags +faststart -profile:v High -pix_fmt yuv420p` |

**关键注意事项：**
- `-pix_fmt yuv420p` 必须，否则部分播放器/系统黑屏；
- `-movflags +faststart` 把 moov 前移，提升播放启动速度；
- GOP 与 I 帧：直播/秒开建议 `-g 48 -sc_threshold 0`；
- 转码必带音频统一 `-ar 48000 -ac 2`，避免声道不兼容。

#### 3.4.4 HTML5 渲染（模板合成）

HTML5 渲染 = 模板 + 变量 → 生成 zip。常用 headless 浏览器截图预览但不影响最终 zip：

```python
import jinja2, zipfile

def render_html5(template_path, variables, out_zip):
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(template_path))
    html = env.get_template("index.html").render(**variables)
    # 收集资源文件
    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("index.html", html)
        for asset in template_assets(template_path):
            z.write(asset, f"assets/{basename(asset)}")
    return out_zip
```

### 3.5 AI 生成流水线实现

#### 3.5.1 编排（Orchestration）完整示例

用 JSON 描述批次 + Python worker 消费，支持断点续跑：

```python
import json, time
from dataclasses import dataclass

@dataclass
class Batch:
    id: str
    stages: list          # 有序阶段
    tasks: list           # 本批次所有 brief 任务
    state: dict           # 各任务进度 {task_id: {stage: status}}

def run_batch(config: dict):
    batch = Batch(**config)
    for stage in batch.stages:
        for task in batch.tasks:
            if batch.state.get(task["id"], {}).get(stage) == "done":
                continue
            try:
                result = STAGE_ROUTER[stage](task)     # 各阶段处理函数
                persist_task_result(batch.id, task, stage, result)
                batch.state.setdefault(task["id"], {})[stage] = "done"
            except Exception as e:
                if config.get("on_fail") == "stop_all":
                    raise
                batch.state.setdefault(task["id"], {})[stage] = f"failed:{e}"
        # 可选：持久化 batch.state，支持断点
        save_batch_progress(batch)
    return summarize(batch)

STAGE_ROUTER = {
    "copy":     gen_copies,
    "media":    gen_media_variant,
    "localize": localize_task,
    "render":   render_all,
    "lint":     lint_all,
    "publish":  publish_all,
}
```

#### 3.5.2 与外部模型服务解耦

生产环境建议把"模型调用"封装成独立接口，方便换供应商/灰度：

```python
class ModelGateway:
    """统一模型网关：LLM / 图像 / 视频 / TTS 均可切换供应商"""
    def __init__(self, config):
        self.llm = provider_from(config["llm"])       # 如 OpenAI/Claude/DeepSeek/自部署
        self.text2img = provider_from(config["text2img"])
        self.i2v = provider_from(config["i2v"])
        self.tts = provider_from(config["tts"])

    def chat(self, prompt, **kw):
        return self.llm.chat(prompt, **kw)

    def generate_image(self, prompt, negative, size, **kw):
        return self.text2img.generate(prompt, negative_prompt=negative, size=size, **kw)

    def image_to_video(self, image, prompt, duration, **kw):
        return self.i2v.generate(image=image, prompt=prompt, duration=duration, **kw)
```

#### 3.5.3 生成质控（QC）

AI 生成必须过质控闸门，防止劣质/违规内容入库：

| 质控项 | 检查方式 | 拦截策略 |
| --- | --- | --- |
| 技术完整 | 文件能否解码、时长是否达标 | 失败重试 1 次后标记 FAILED |
| 视觉相似 | 与输入一致性（product 特征比对） | 相似度 < 0.8 拒绝 |
| 违规内容 | 图片/文本安全模型 | 命中即拒绝并记录 |
| 文本溢出 | 动态模板中文字是否溢出边界 | 自动缩短/换行或拒绝 |
| 品牌一致性 | logo/配色是否符合 brand kit | 不一致降级为人工审核 |

```json
{
  "qc_result": {
    "decode": "ok",
    "similarity": 0.93,
    "safety": "clean",
    "text_overflow": false,
    "brand_match": true,
    "verdict": "PASS"
  }
}
```

### 3.6 DCO 生产实现

#### 3.6.1 组合生成与存储

```sql
-- 组合表（剪枝后写入，带特征 JSON）
CREATE TABLE dco_combos (
  combo_id      UUID PRIMARY KEY,
  batch_id      UUID,
  image_id      UUID,
  copy_id       UUID,
  cta_id        UUID,
  template_id   UUID,
  features      JSONB,          -- 标签并集/特征向量
  status        TEXT,           -- pending|active|frozen|killed
  impressions   BIGINT DEFAULT 0,
  clicks        BIGINT DEFAULT 0,
  conversions   BIGINT DEFAULT 0,
  created_at    TIMESTAMPTZ DEFAULT now()
);

-- 曝光/奖励流水（用于离线重放与学习）
CREATE TABLE dco_events (
  event_id     BIGSERIAL PRIMARY KEY,
  combo_id     UUID,
  ts           TIMESTAMPTZ,
  reward       INT,             -- 0 或 1
  context      JSONB            -- 地域/设备/时段等
);
CREATE INDEX ON dco_events (combo_id, ts);
```

#### 3.6.2 在线服务端决策（Bandit + 规则）

```python
def dco_select(context) -> str:
    """给定上下文，返回本次曝光的 combo_id"""
    # 1. 规则引擎硬性过滤
    eligible = [c for c in active_combos() if rule_engine.allowed(c, context)]
    if not eligible:
        return fallback_combo(context)          # 兜底：人工指定默认
    # 2. 预算/频控兜底
    if budget_hour(context) < min_budget:
        return budget_fallback(eligible)
    # 3. 学习器选择（Thompson / UCB）
    return bandit.select(eligible)
```

```python
# 服务端 + Redis 计数（近似原子）
import redis
r = redis.Redis()
def record_reward(combo_id, reward):
    key = f"dco:{combo_id}"
    r.hincrby(key, "imp", 1)
    if reward:
        r.hincrby(key, "click", 1)
    # 定期把 Redis 计数固化到 PG（离线学习）
```

#### 3.6.3 预计算 vs 实时渲染

DCO 有两种执行形态，需根据延迟与灵活性权衡：

| 形态 | 延迟 | 灵活性 | 适用 |
| --- | --- | --- | --- |
| 预渲染组合（Pre-rendered） | 低（直接出图） | 组合数受限（需先渲染好） | 大量图片/横幅组合 |
| 实时模板渲染（Server-side） | 中（请求时合成） | 高（可实时换文案/价格） | HTML5 / 动态价格落地 |

> 生产建议：高并发小图用"预渲染 + 命中缓存"；需要个性化（实时价格/库存/用户昵称）用"服务端模板渲染"。

### 3.7 数据分析层实现

#### 3.7.1 指标回传与聚合

平台数据（Meta/TikTok/Google）通过各自报告 API 拉取，落地到数仓后按创意维度聚合：

```sql
-- 创意级指标聚合（示例，示意口径）
SELECT
  asset_id,
  platform,
  SUM(impressions)   AS impressions,
  SUM(clicks)        AS clicks,
  SUM(conversions)   AS conversions,
  SUM(clicks) * 1.0 / NULLIF(SUM(impressions),0) AS ctr,
  SUM(conversions) * 1.0 / NULLIF(SUM(clicks),0)  AS cvr,
  -- 疲劳相关：近 7 天 vs 之前 7 天
  SUM(CASE WHEN ts >= now()-interval '7 day' THEN clicks END)
      / NULLIF(SUM(CASE WHEN ts >= now()-interval '7 day' THEN impressions END),0) AS ctr_recent
FROM fact_creative_metrics
WHERE ts >= now() - interval '14 day'
GROUP BY asset_id, platform
```

#### 3.7.2 疲劳诊断任务（定时）

```python
def daily_fatigue_scan():
    rows = query_creative_metrics_last14d()
    for r in rows:
        ctrl_r7  = compute_window(r, 7)     # 近 7 天指标
        ctrl_r14 = compute_window(r, 14-7)  # 之前 7 天
        fi = fatigue_index(ctrl_r7.ctr, ctrl_r14.ctr,
                           ctrl_r7.cpa, ctrl_r14.cpa,
                           f"avg frequency {r['freq_rec']}")
        level = classify(fi)
        if level in ("REFRESH", "KILL"):
            enqueue_creative_action(r["asset_id"], level)
        log_fatigue(r["asset_id"], fi, level)
```

#### 3.7.3 迭代信号输出

分析层产出结构化的"下一轮创意建议"，供 AI 生成侧消费（见 2.6.4）。

```json
{
  "iteration_signal": {
    "batch": "bat-20260814-003",
    "top_themes": ["hook-assertive", "cta-limited"],
    "worst_themes": ["hook-question-long"],
    "recommend_action": "generate_next_batch",
    "params": {"new_copy_variants": 8, "refresh_asset_pool": true}
  }
}
```

### 3.8 平台对接（Platform Connector）

#### 3.8.1 统一连接器接口

各平台 API 差异大，连接器提供一个统一接口，隐藏差异：

```python
class PlatformConnector(ABC):
    @abstractmethod
    def create_creative(self, asset: dict, spec: dict) -> dict:
        """返回对端 creative id"""

    @abstractmethod
    def upload_media(self, file_url, destination) -> str:
        """上传媒体，返回对端 URL/hash"""

    @abstractmethod
    def get_status(self, creative_id) -> str:
        """查询投放/审核状态"""

    @abstractmethod
    def list_reports(self, since, until) -> list[dict]:
        """拉取创意级报表"""
```

#### 3.8.2 Meta 对接要点（Marketing API）

```python
# 上传到 Meta 的摘要逻辑（真实实现依赖 meta-python SDK）
def meta_upload(ad_account_id, creative, access_token):
    # 1. 先上传媒体资产（图片或视频）
    #    图片：POST /{ad_account_id}/adimages（binary）
    #    视频：POST /{ad_account_id}/advideos（binary, file_size, file_name）
    image_hash = post_adimage(ad_account_id, creative["image_bytes"], access_token)
    # 2. 创建 creative 对象
    creative_spec = {
        "name": creative["name"],
        "object_story_spec": {
            "page_id": creative["page_id"],
            "link_data": {
                "image_hash": image_hash,
                "link": creative["landing_url"],
                "message": creative["primary_text"],
                "call_to_action": {"type": creative["cta_type"]},
            }
        },
    }
    creative_id = post_creative(ad_account_id, creative_spec, access_token)
    return creative_id
```

**Meta 注意事项：**
- 每个素材需满足平台规范（图片 ≤8MB，视频 ≤4GB，时长为资产对应版位）；
- 大量上传需走**异步（job）接口**与**轮询**，注意限流（按广告账户分摊、并发 < 平台限额）；
- 动态创意（DC）通过 `dynamic_creativ` 组合元素，需把元素（图片/文案/CTA）分别上传后创建 `dynamicAdCreative`。

#### 3.8.3 TikTok 对接要点

```python
def tiktok_upload(advertiser_id, creative, access_token):
    # 1. 上传媒体到自定义视频源
    video_id = post_video_upload(advertiser_id, creative["video_bytes"],
                                 fname=creative["file_name"], auth=token)
    # 2. 创建 video_creative
    creative_obj = {
        "advertiser_id": advertiser_id,
        "video_id": video_id,
        "creative_name": creative["name"],
        "identity_id": creative["identity_id"],     # 认证品牌
        "landing_page_url": creative["landing_url"],
        "call_to_action": creative["cta"],
        "music_info": creative.get("music"),        # TikTok 可配音乐
    }
    return post_creative(creative_obj, access_token)
```

**TikTok 注意事项：**
- Spark Ads 需授权创作者视频（`identity_id` 属于认证品牌）；
- 视频 9:16 优先，时长 5-60s（最长 10min，但推荐短时长）；
- 上传有配额，需管理频繁/批量上传的批次与重试。

#### 3.8.4 Google 对接要点（RSA / YouTube）

```python
def google_create_responsive_search(account, headline_list, description_list, urls, token):
    ad_group_criterion = {
        "type": "RESPONSIVE_SEARCH_AD",
        "status": "PAUSED",                      # 先建后启用
        "finalUrls": [urls["final_url"]],
        "headlines": [{"text": h} for h in headline_list],        # ≤15
        "descriptions": [{"text": d} for d in description_list],  # ≤4
    }
    return google_ads_mutation(account, ad_group_criterion, token)

def google_upload_youtube(asset, token):
    # 用 YouTube Data API 或 Google Ads MediaFile 上传视频
    video = upload_to_youtube(asset["file_url"], title=asset["name"],
                              token=token)  # 返回 video_id
    return video["id"]
```

**Google 注意事项：**
- RSA 的标题/描述可 `pinned`（固定位置），但固定太多会降低灵活性——建议仅固定品牌词；
- YouTube 视频上传用 Google Ads `MediaFile` 或 YouTube Data API，需规划配额；
- 展示广告素材尺寸多（300x250, 728x90…），建议用 DCA/自动化素材组合。

#### 3.8.5 DV360 对接要点

```python
def dv360_upload_html5(advertiser_id, zip_bytes, click_tag, token):
    # 1. 上传 HTML5 ZIP 作为 CreativeAsset
    asset = upload_creative_asset(advertiser_id, zip_bytes, "ad.zip")
    asset_id = asset["asset_id"]
    # 2. 创建 Creative 并指定 HTML5 上传文件 + 关联站点/广告位
    creative = {
        "creativeId": None,
        "advertiserId": advertiser_id,
        "type": "DISPLAY",
        "size": {"width": 300, "height": 250},
        "backupImageClickThroughUrl": click_tag,
        "name": "HTML5_Banner_300x250",
        "mimeType": "application/octet-stream",
        "creativeAssetJoiners": [
            {"assetId": asset_id, "role": "PRIMARY"}
        ],
    }
    return create_creative(creative, token)
```

**DV360 注意事项：**
- HTML5 ZIP 需含 `index.html` 入口与点击跳转机制；视频用 VAST 或直接 mp4；
- 富媒体 / 扩展创意需在 DV360 后台配置特定容器与交互组件；
- 需注意广告位尺寸与 Creative 尺寸严格匹配，否则可能投放失败。

### 3.9 监控、告警与 CI/CD

#### 3.9.1 关键监控指标

| 指标 | 告警阈值 | 含义 |
| --- | --- | --- |
| 渲染失败率 | > 2% | 渲染农场异常/素材问题 |
| 渲染队列积压 | > 1000 | 消费跟不上 |
| 规格解析错误 | > 0 | 规格配置损坏 |
| 上传校验通过率 | < 85% | 素材质量问题或规格误配 |
| AI 生成失败率 | > 10% | 模型服务故障/欠费 |
| 平台上传失败 | > 1% | 账户/凭证/限流问题 |
| DCO 组合有效率 | 持续下降 | 元素池老化 |

#### 3.9.2 可观测性埋点

```python
# 结构化日志 + 埋点示例
import structlog
log = structlog.get_logger()

def render_done(render_id, spec, duration_ms, ok):
    log.info("render_completed",
             render_id=render_id, spec=spec,
             duration_ms=duration_ms, ok=ok)
    metrics.incr(f"render.{'ok' if ok else 'fail'}")
    metrics.observe("render.duration_ms", duration_ms)
```

#### 3.9.3 CI/CD 流水线（GitHub Actions 片段）

```yaml
name: ucms-spec-and-render

on:
  push:
    paths: ["spec/**", "renderers/**"]

jobs:
  spec-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install -r requirements.txt
      - run: poetry run pytest tests/spec -q
      - run: poetry run python -m ucms.spec.cli validate spec/platforms/*.yaml

  render-smoke:
    runs-on: ubuntu-latest
    needs: spec-test
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
      - run: pip install -r requirements.txt
      - run: pytest tests/render -q
      - run: bash scripts/run_ffmpeg_smoke.sh
```

#### 3.9.4 回滚与灰度

```
发布策略：
1. 新素材/新规格：先小范围灰度（1 个广告组 / 20% 流量）
2. 渲染/规格变更：改代码需 CI + 冒烟，生成容器镜像滚动更新
3. 素材回滚：版本树一键切回历史 version + 重新渲染
4. 平台发布回滚：调用对端 API 暂停/删除 creative

事故预案：
- 平台封禁某素材 → 自动 Pull：标记 REJECTED，替换备用素材
- 渲染农场全挂 → 降级：用"直传原始高规格素材"兜底，暂停策略适配
```

---

## 四、常见问题与排查

### 4.1 问题速查表

| 问题 | 现象 | 可能原因 | 定位思路 |
| --- | --- | --- | --- |
| 上传后校验失败 | asset 卡在 VALIDATING/REJECTED | 尺寸/时长/格式不合规 | 看 lint checks 细节 |
| 渲染产物黑屏 | 视频打开黑屏/无画面 | pix_fmt 非 yuv420p / 编码格式 | 检查编码参数 |
| 竖屏视频被裁 | 内容被切断 | 误用 crop 而非 extend/smart | 看策略路由 |
| 平台上传失败 | connector 报错 | 凭证/限流/账户权限 | 看对端错误码 |
| 疲劳误判 | 低估/高估疲劳 | 基线窗口/频次口径 | 复查疲劳计算窗口 |
| AI 素材质量差 | 商品变形/违规 | prompt 约束不足/无 QC | 看 QC 结果与负例 |
| DCO 不收敛 | 有效组合少 | 组合过多/样本不足 | 校验组合数与预算 |
| HTML5 白屏 | 预览/线上白屏 | 资源外链/点击跳转缺失 | 检查 ZIP 与 clickTag |

### 4.2 问题 1：素材审核不通过

**现象**：素材规格参数都符合，但审核拒绝。
**排查路径**：

```
1. 查 lint checks：逐项是否 pass，定位到具体规则（尺寸/文字比例/时长）
2. 查合规检查：违禁词/敏感图/水印/合规
3. 查地区规则：不同 locale 有不同的合规要求
4. 查规格版本：是否规格配置过期（平台更新了约束）
5. 若为图片：确认文字占比 ("text_ratio") 未超限
6. 若为视频：确认时长与音频合规、无第三方水印
```

**常见隐藏原因：**
- 图片含不可见水印（Alpha 通道）；*检测原图 Alpha 数据*；
- 文案含绝对化用语（"最""第一""无副作用"）；
- 视频首帧为黑屏/过于抖动，被自动审核判定低质。

### 4.3 问题 2：渲染产物与平台拒绝不符

**现象**：系统渲染"成功"，但对端平台拒绝（如文件过大/尺寸不精确）。
**排查步骤**：

```bash
# 1. 复核最终文件真实参数（渲染后必须，不要只信渲染前）
ffprobe -v error -show_entries stream=width,height,r_frame_rate \
        -show_entries format_format,format_size,format_duration \
        -of json final.mp4

# 2. 检查是否漏掉 faststart（部分平台要求）
ffmpeg -v trace -i final.mp4 -f null - 2>&1 | grep -i "moov" | head

# 3. 检查横竖屏/纵横比是否精确（四舍五入误差）
python -c "import sys; w,h=1920,1080; print(f'{w/h:.6f}')"
```

**应对：** 渲染后强制 re-lint（见 3.4.2），把"最终参数"作为发布前置条件。

### 4.4 问题 3：AI 生成一致性差（商品变形）

**现象**：文生图/图生图结果与产品不一致，logo/形态崩坏。
**根因**：
- prompt 仅靠文字描述，未锚定产品特征；
- 生成后 QC 相似度过低未拦截；
- 负向提示词缺失（变形/多指/水印）。
**对策**：

```
1. 用 ControlNet / IP-Adapter / LoRA 锚定产品身份
2. QC 加"产品一致性与比"（特征嵌入余弦相似度）
3. 充分利用负向提示词
4. 对高危类目（服饰/食品/3C）优先人工抽检
```

### 4.5 问题 4：竖屏视频误裁 / 内容丢失

**现象**：转 9:16 后人物/产品被切成两半。
**根因**：无脑 center crop 而非 smart reframe / extend。
**排查**：

```
1. 查看策略路由结果（strategy 字段）
2. 检查显著性/对象检测是否开启（per-frame focus）
3. 若已 extend：检查背景填充是否穿帮（接缝）
4. 检查窗口平滑（EMA/oneEuro）是否造成主体出框
```

**建议**：人物/产品为主的主素材，竖屏化默认走 smart_reframe；简单图可用 saliency crop；纯氛围可 blur extend。

### 4.6 问题 5：DCO 无有效组合 / 不收敛

**现象**：组合全部被规则拦截，或长期无显著优化。
**排查**：

```
1. 规则引擎：是否存在过严规则全挡（临时放开排查）
2. 组合规模：单组是否 >10-15 个（需分批）
3. 样本量：单组合曝光是否达到学习下限（min_impression）
4. 奖励口径：CTR/转化是否准确回传（reward 埋点）
5. 频控/预算兜底：是否强制走了 fallback
```

**关键教训**：DCO 不是"开箱即收敛"。组合太多、规则过死、样本不足都会让学习失效。先小步快跑再放量。

### 4.7 问题 6：HTML5 白屏 / 点击无效

**现象**：DV360 HTML5 创意投放白屏，或点击不跳转。
**排查**：

```
1. 资源是否全部内联（禁外链图片/字体/CDN）
2. index.html 是否含 meta charset / 正确入口
3. clickTag 是否实现（window.clickTag + exit）
4. ZIP 结构是否符合（index.html + assets/）
5. 是否有广告拦截/iframe 跨域问题
```

```html
<!-- 正确点击跳转最低实现 -->
<script>
  document.getElementById('cta').onclick = function () {
    window.open(window.clickTag || 'https://fallback.example.com', '_blank');
  };
</script>
```

### 4.8 问题 7：平台限流 / 大批量上传失败

**现象**：批量上传对端批量 429 / 失败。
**应对框架**：

```
1. 令牌桶 / 账户级并发控制（每账户并发上限）
2. 分批 + 指数退避重试（429 → 退避）
3. 异步 job 接口优先（平台支持时）
4. 上传前本地预处理压缩（减少体积）
5. 失败落队列重放，避免阻塞主流程
```

```python
def throttled_upload(pool):
    # 账户级并发限制 + 指数退避
    sem = threading.Semaphore(max_concurrency_per_account)
    for task in tasks:
        sem.acquire()
        def do():
            try:
                upload(task)
            except RateLimitError as e:
                time.sleep(backoff(e.retry_after))
                upload(task)
            finally:
                sem.release()
        Thread(target=do).start()
```

### 4.9 排查工具集

| 工具 | 用途 |
| --- | --- |
| ffprobe | 探测媒体参数 |
| ffmpeg | 转码/裁剪/合成/extend |
| HTML validation | 校验 HTML5 入口/编码 |
| saliency/mask 工具 | 显著图调试 |
| 平台 API 报错码查询 | 对端错误语义 |
| 版本/diff | 对比素材前后差异 |

```bash
# 体检一个素材的完整技术参数
ffprobe -v error -show_format -print_format json asset.mp4
```

---

## 五、自测题

### 5.1 知识自测

**问题 1**：主流平台竖屏短视频的推荐分辨率与纵横比分别是什么？（Meta Reels 与 TikTok In-Feed）
<details>
<summary>查看答案</summary>

Meta Reels：推荐 1080x1920（9:16），时长 10-90s，30-60fps；
TikTok In-Feed Video：推荐 1080x1920（9:16），时长 5-60s（推荐 5-15s 或 21-34s），30/60fps。
都是竖屏 9:16。注意各自安全区（Reels 右侧 UI、TikTok 底部信息条/右侧头像）。
</details>

**问题 2**：如何判断一个创意是否"疲劳"？给出至少两个信号和一个量化方法。
<details>
<summary>查看答案</summary>

信号 1：CTR/CVR 随频次（Frequency）上升出现明显衰减转折；
信号 2：近 7 天指标相对之前 7 天基线显著下降。
量化：换算疲劳指数 Fatigue Index（CTR 衰减比、CPA 膨胀比、频次风险加权），分 HEALTHY/WATCH/REFRESH/KILL 四级，REFRESH 换素材/降频，KILL 强制下线。
</details>

**问题 3**：单素材多平台适配为什么优先考虑"重排/ extend / smart reframe"而不是"简单 center crop"？
<details>
<summary>查看答案</summary>

无脑 center crop 会丢弃画幅两侧/上下内容，可能切断主体（人脸/产品/文字）造成语义损失与事故。
extend 通过模糊/镜像/AI 填充补足画幅不丢内容；smart reframe 逐帧跟踪主体并动态裁剪窗口。
选择策略：氛围/纯背景可 blur extend；人物/产品主素材默认 smart_reframe；简单图可用 saliency crop。
所有适配都要"内容无损优先 + 语义安全 + 可回溯"。
</details>

**问题 4**：统一 DCO 与平台内建 Dynamic Creative 有什么区别？为什么有时要用自建 DCO？
<details>
<summary>查看答案</summary>

平台内建 DC（Meta/TikTok/Google）：学习在平台闭环、数据充分，但黑盒、无法干预具体组合、无法跨平台迁移。
统一 DCO：元素池 + 组合矩阵 + 规则引擎 + Bandit，决策在自建层，可控、可迁移、可审计。
自建适合：需要合规硬约束、要精确控制组合、要跨平台统一、要沉淀自有点击/转化学习资产，或不信任平台黑盒优化。
</details>

**问题 5**：AI 生成流水线如何保证产出质量与品牌一致性？
<details>
<summary>查看答案</summary>

1. 结构化 prompt + 变体枚举；2. ControlNet/IP-Adapter/LoRA 锚定产品身份；3. QC 闸门（解码、视觉相似度、安全、文字溢出、品牌一致性）；4. 术语表做本地化一致；5. 数据闭环把表现反馈给生成（反思式提示）；6. 高危类目强人工抽检。
</details>

---

## 附录 A：跨平台创意综合演练案例

### A.1 场景

某 DTC 美妆品牌 summer-sale 活动。主素材：
- 1 张 16:9 产品主视觉（1920x1080, JPG）
- 1 条 16:9 产品视频（1920x1080, 30s, H.264, 8Mbps）
需要铺开 Meta / TikTok / Google / DV360 四平台。

### A.2 预期产出矩阵

| 平台 | 版位 | 规格 | 来源策略 |
| --- | --- | --- | --- |
| Meta | Feed | 1080x1350 (4:5) 视频 | 主视频 crop/smart |
| Meta | Reels | 1080x1920 (9:16) 视频 | smart reframe |
| Meta | Stories | 1080x1920 图片/视频 | extend + 模板 |
| TikTok | In-Feed | 1080x1920 视频 | smart reframe + 3s hook |
| Google | RSA | 标题15+描述4 | LLM 文案 |
| Google | YouTube | 1920x1080 视频 | 主视频直接 |
| Google | Discover | 1200x628 图 | crop + 文案 |
| DV360 | HTML5 | 300x250 / 728x90 | 模板合成 |
| DV360 | VAST | 1280x720 视频 | 主视频转码+VAST轴 |

### A.3 运行批次（简化 JSON 触发）

```json
{
  "batch_id": "summer-sale-launch",
  "product_id": "SKU-9910",
  "locales": ["en-US", "es-MX", "de-DE"],
  "platforms": ["meta", "tiktok", "google", "dv360"],
  "stages": ["copy", "media", "localize", "render", "lint", "publish"],
  "parallel": 16,
  "assets": {
    "master_image": "s3://ucms/masters/sku9910-hero-16x9.jpg",
    "master_video": "s3://ucms/masters/sku9910-30s-16x9.mp4"
  }
}
```

### A.4 结果检查清单

```text
[ ] 所有规格产物已生成且 re-lint 通过
[ ] 各平台 creative 均在 SYSTEM 后台可见（review/live）
[ ] 竖屏视频主体未切断（人工抽查关键帧）
[ ] 文案本地化到位、无绝对化用语
[ ] HTML5 clickTag 可跳转
[ ] 指标回传链路打通（能看到创意级 CTR/CPA）
[ ] DCO 组合已就绪，看到种子曝光与学习启动
[ ] 监控无渲染失败 / 上传失败告警
```

### A.5 复盘与指标

| 指标 | 目标 |
| --- | --- |
| 平均 CTR | ≥ 2.0%（竖屏视频） |
| 视频完播率 | ≥ 35% |
| CVR | ≥ 4% |
| ROAS | ≥ 2.5 |
| 一次创意疲劳周期 | ≥ 7 天 |

---

## 附录 B：知识库交叉引用

| 相关主题 | 建议阅读 |
| --- | --- |
| 创意自动化（AI 裁剪/组合/测试） | 创意自动化公开文档 |
| DCO 与创意组合优化 | 动态创意优化文档 |
| 素材审核与合规 | 创意审核流程文档 |
| 多平台投放策略 | 跨平台策略文档 |
| 归因与跨渠道 | 跨平台归因文档 |
| 创意指标与疲劳 | 创意性能分析文档 |

---

> 本文档为《跨平台创意资产管理自动化系统》深度实战指南，覆盖规格矩阵、资产统一管理、AI 生成流水线、
> DCO、性能分析与迭代闭环，以及生产落地与排障。数值以 2026-08 采集为准，请以平台官方最新规范与系统规格配置中心为准。
---

## 附录 C：图像技术参数与视觉规范深度补充

### C.1 DPI / PPI 与分辨率的关系

很多设计稿会遇到"300 DPI"与"1080px"混淆。背景知识：

```
DPI (Dots Per Inch)  物理打印/输出分辨率：描述物理尺寸与像素的映射
PPI (Pixels Per Inch) 屏幕像素密度：描述屏幕物理大小与像素的映射
分辨率 (Resolution)   实际像素数：width x height（决定清晰度上限）
```

**广告素材核心结论**：DTP 是**相对单位**，最终由"目标像素数 + 输出设备物理尺寸"决定。网页/信息流投放按像素交付，无需纠结 72/150/300 DPI，**只关心目标像素数与文件大小**。

| 场景 | 关注点 | 建议 |
| --- | --- | --- |
| 信息流/视频投放 | 目标像素 + 文件大小 + 码率 | 按规格矩阵交付（如 1080x1920） |
| 印刷/线下物料 | DPI（≥150-300） | 需高分辨率源图 |
| 大屏 DOOH | 物理尺寸 + PPI | 用实际面板尺寸换算像素 |

**换算示例（若确需）**：

```
一个 10 英寸 x 14 英寸的竖版海报，要求 300 DPI：
像素宽 = 10 英寸 × 300 = 3000 px
像素高 = 14 英寸 × 300 = 4200 px
分辨率 = 3000 × 4200
```

### C.2 视频码率参考（Bitrate）与质量等级

| 分辨率 | 建议平均码率（H.264） | 帧率 | 优劣 |
| --- | --- | --- | --- |
| 1080p (1920x1080) | 4000-8000 kbps | 30 | 高保真平台主推 |
| 720p (1280x720) | 2000-4000 kbps | 30 | 平衡 |
| 480p | 800-1500 kbps | 30 | 低带宽兜底 |
| 竖屏 1080x1920 | 4000-8000 kbps（高动态可更高） | 30/60 | 移动端主力 |

**参数选择经验**：
- 静态/文案图可用低频（静态内容码率低）；动态/特效内容需高码率；
- `-crf`（质量系数）与码率权衡：CRF 18 ≈ 高质量，20 平衡，23 一般；
- 平台普遍有"文件大小上限"而非"硬性码率"，但超高码率会增加加载压力、影响播放体验与成本。

### C.3 安全区与文字限制实战

各平台对"文字覆盖画面"与"安全区"有明确指导。系统应在渲染后自动校验：

```yaml
# 文字占比校验配置示例
text_ratio_rules:
  meta_feed_image:   0.20   # 文字占画面 ≤ 20%
  meta_reels_video:  0.20
  tiktok_feed:       0.20   # 视版位而定
  google_display:    0.20
  dv360_banner:      0.25   # 部分 banner 更宽松（以官方为准）
```

```python
def detect_text_ratio(img):
    """近似检测文字像素占比（边缘/OCR，示意）"""
    import cv2
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # 文字区域通常高边缘密度，或用 OCR 文本框
    edges = cv2.Canny(gray, 50, 150)
    ratio = edges.astype(bool).mean()
    return round(float(ratio), 4)   # 0-1
```

### C.4 现代前端/游戏广告对创意的要求

跨平台创意后端越来越多涉及插屏、激励视频、可玩（Playable）广告：

| 类型 | 平台 | 关键技术约束 |
| --- | --- | --- |
| 激励视频 Rewarded | 游戏/App | 需"奖励提示"+ 竖屏 9:16 + 音频 |
| 可玩广告 Playable | 游戏 | HTML5/JS 引擎，首屏即玩，包体 ≤ 10MB 级 |
| 插屏 Interstitial | App | 全屏，需适配机型安全区（刘海） |
| 原生 Native | 展示平台 | 标题+正文+图+图标，多组件组合 |

**可玩广告（Playable）要点：**

```
1. 包体需要控制在平台限额内（如 10MB 内），资源需压缩
2. 需支持点击跳转下载/落地页（entry/exit）
3. 首屏 3-5 秒内呈现"可玩"动作，提升参与度
4. 需兼容 iOS/安卓不同屏幕安全区
5. 一般用 Cocos/Unity/Laya 打包为 HTML5 或特定格式
```

```
可玩广告 zip 结构（示意）：
playable.zip
├── index.html          # 入口
├── game.js             # 游戏逻辑（打包后的 JS）
├── assets/             # 纹理/音效/字体（压缩）
└── config.json         # 广告跳转/分析配置
```

### C.5 字幕与无障碍（Accessibility）

| 平台 | 字幕/无障碍要求 | 实现 |
| --- | --- | --- |
| Meta Reels | 建议加字幕（很多人静音观看） | 烧录字幕 burn-in 或 SRV/SRT |
| TikTok | 首 3 秒信息体现在字幕 | 烧录大字幕 |
| YouTube | 鼓励 CC 字幕 | SRT/WebVTT 上传 |
| 通用 | 闪烁频率 ≤ 3Hz、对比度足够 | 避免高反差闪烁 |

**烧录字幕（FFmpeg）：**

```bash
ffmpeg -i video.mp4 -vf "subtitles=sub.srt:force_style='FontName=Arial,FontSize=14,PrimaryColour=&H00FFFFFF&'" \
  -c:v libx264 -crf 18 -preset slow -c:a copy subbed.mp4
```

---

## 附录 D：数据模型扩展与字段字典

### D.1 Asset 表

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| asset_id | UUID | 主键，对外不可变 |
| master_id | UUID | 主素材 ID 引用 |
| kind | enum | image/video/html5/native/audio |
| content_hash | text | SHA-256 |
| spec_origin | jsonb | 主规格引用 |
| status | enum | DRAFT…ARCHIVED |
| head_version | int | 当前 head 版本号 |
| created_by | text | 创建者 |
| created_at / updated_at | timestamptz | 时间戳 |
| meta | jsonb | 自定义业务元数据 |

### D.2 Render 表

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| render_id | UUID | 主键 |
| asset_id | UUID | 关联资产 |
| platform / placement | text | 目标平台/版位 |
| spec_key | text | 规格键 |
| strategy | text | crop/extend/smart/template |
| status | enum | queued/rendering/done/failed |
| checksum / size | text/int | 产物校验与大小 |
| output_url | text | CDN 地址 |
| error | text | 失败原因 |

### D.3 Release 表

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| release_id | UUID | 主键 |
| render_id / asset_id | UUID | 源 |
| account_id | text | 对端账户 |
| platform_status | enum | uploaded/in_review/.../live |
| platform_creative_id | text | 对端 creative id |
| released_by / at | text / ts | 操作者与时间 |

---

## 附录 E：动态创意优化工作台示例（前端/看板）

创意负责人需要在工作台看到一站式状态：

```
┌───────────────────────── DCO 创意工作台 ──────────────────────────┐
│ 顶层卡：当前活动 / 批次 / 组合总数 / 学习状态                      │
│                                                                    │
│ 组合列表                                                        │
│  ┌──────┬─────────┬────────┬──────┬─────────┬─────────┐
│  │combo │ 元素组合 │ 曝光    │ CTR  │ 转化    │ 状态     │
│  ├──────┼─────────┼────────┼──────┼─────────┼─────────┤
│  │ c1   │ img1+c2  │ 124k   │ 3.1% │ 4200    │ active  │
│  │ c2   │ img2+c1  │ 98k    │ 2.4% │ 3050    │ active  │
│  │ c3   │ img3+c3  │ 21k    │ 0.8% │ 180     │ frozen  │
│  │ c4   │ img1+c4  │ 5k     │ 1.2% │ 60      │ explore │
│  └──────┴─────────┴────────┴──────┴─────────┴─────────┘
│  操作：冻结/加大预算/换取新元素/一键生成新一轮批量                  │
└────────────────────────────────────────────────────────────────────┘
```

---

## 附录 F：从零搭建的最小可用闭环（Checklist）

如果从零搭建一个 MVP 跨平台创意系统，建议按以下顺序落地：

```
阶段一（第 1 周）核心链路
  [ ] 规格矩阵配置（YAML）
  [ ] 资产记录 + 探针 + 规格校验
  [ ] 基础渲染（crop / extend / template）
  [ ] 平台对接（至少 1 个平台上传）

阶段二（第 2-3 周）AI 与批量
  [ ] LLM 文案生成（结构化 prompt）
  [ ] 图生图/文生图接入（带 QC）
  [ ] 本地化（术语表 + TTS）
  [ ] 批次编排 + 断点续跑

阶段三（第 4 周）DCO 与闭环
  [ ] 元素池 + 组合矩阵 + 规则引擎
  [ ] Bandit 在线分配 + 指标回传
  [ ] 疲劳诊断定时任务
  [ ] 迭代信号回流生成侧

阶段四（持续）运维与放量
  [ ] 监控告警 / 可观测性
  [ ] CI/CD / 灰度 / 回滚
  [ ] 全平台覆盖与规模化
```

---

**结语**

跨平台创意资产管理与自动化系统，本质上是一座把"创意"从"一次性物料"升级为"可治理、可复用、可学习的数据资产"的中台。
它由规格矩阵（Spec）、资产库（Asset）、渲染适配（Adaptive）、AI 生成（Pipeline）、DCO（动态优化）与
分析迭代（Analytics）六大能力贯通而成。掌握规格驱动的设计哲学、以"资产即事实"为事实源、以数据闭环驱动迭代，
是团队在多平台时代持续产出高效创意的关键。
