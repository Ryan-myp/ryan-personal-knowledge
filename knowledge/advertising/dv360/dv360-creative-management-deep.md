# DV360 创意管理系统深度解析（富媒体 / HTML5 / 视频创意 / 模板 / A/B 测试）

> **领域**: 广告投放 / 创意管理
> **深度**: ⭐⭐⭐⭐⭐ 实战级指南
> **标签**: dv360, creative, html5, rich-media, video, creative-template, ab-testing
> **更新时间**: 2026-08-14
> **类型**: 深度文档

---

## 一、核心概念与架构

### 1.1 创意在 DV360 层级中的位置

Display & Video 360（简称 DV360）是 Google 的企业级程序化广告购买平台。在它的对象层级中，创意（Creative）处于**最底层、最接近用户**的位置，是所有投放行为的最终载体。要理解创意管理系统，必须先理解整个 DV360 的对象树：

```
Partner（合作伙伴）
└── Advertiser（广告主）
    ├── Campaign（广告系列）
    └── Insertion Order（插入订单，IO）
        └── Line Item（订单项，投放单元）
            ├── Targeting（定向设置）
            ├── Flight（投放航次）
            ├── Budget（预算与出价）
            └── Creative（创意）★ 本主题核心
                ├── 审核状态（APPROVED / DISAPPROVED / PENDING）
                ├── 关联的创意资产（图片/视频/HTML5 zip/URL）
                └── 关联的 Creative Template（模板变量）
```

关键层级概念：

| 层级 | 作用 | 与创意的关系 |
|------|------|--------------|
| Partner | 最高权限单元，管账户与账单 | 持有 Creative 模板库与审核规则 |
| Advertiser | 业务主体，按品牌/事业部划分 | Creative 归属于 Advertiser |
| Campaign | 市场营销目标（如品牌战役） | 逻辑分组，不直接绑创意 |
| Insertion Order | 预算与投放周期的合同层 | 多家以填充为目标的合同聚合 |
| Line Item | 实际竞价与投放的单元 | **Creative 与 Line Item 关联后才能出量** |
| Creative | 用户实际看到的广告 | 必须 APPROVED 且关联 Line Item |

这段层级关系决定了创意管理的两个"硬约束"：

1. **创意不能独立出量**。一个 Creative 哪怕状态为 `APPROVED`，只要没有挂到任何一个正在投放（`ACTIVE`）的 Line Item 上，就不会产生任何展示。
2. **创意属于 Advertiser 而非 Line Item**。这意味同一份创意可以被多个 Line Item 复用，这是批量管理与模板化生产的基础。

### 1.2 创意资产生命周期

一个创意从"素材文件"到"被用户看到"再到"被淘汰优化"，要经历完整的生命周期。这是创意管理系统最关键的心智模型，也是本主题第一条主线：

```
                    ┌─────────────────────────────────────────────┐
                    │           创意资产生命周期                     │
                    └─────────────────────────────────────────────┘

  ① 创意构思/设计 brief
     │
     ▼
  ② 素材制作（图片/视频/HTML5 zip）          ← 制作团队，产出创意资产文件
     │
     ▼
  ③ 上传到 DV360（创建 Creative）            ← dv360_create_creative / create_creative
     │
     ▼
  ④ 系统审核（审核状态机）                   ← APPROVED / DISAPPROVED / PENDING
     │  ├── PENDING → 等待 Google 审核
     │  ├── APPROVED → 通过，可投放
     │  └── DISAPPROVED → 被拒，需修改后重新提交
     │
     ▼
  ⑤ 关联 Line Item（挂接投放单元）           ← 通过 LineItem.creativeIds 或 creatives.attach
     │
     ▼
  ⑥ 实际投放（竞价 + 展示）                 ← 据此产生 Impression / Click / Conversion
     │
     ▼
  ⑦ 数据回传与报表分析（CTR/CVR/完播率）     ← 触发 A/B 测试与创意疲劳判断
     │
     ▼
  ⑧ 优化迭代 / 下线淘汰
     ├── A/B 胜出 → 追加预算、扩量
     ├── 表现差 → 停投或替换素材
     └── 创意疲劳 → 轮换新创意
```

#### 阶段详解

**① 构思与 Brief**
创意 brief 需要明确：目标受众、广告目标（品牌曝光 vs 转化）、投放格式（展示/视频/原生）、强制品牌元素（Logo/免责声明）、以及各尺寸变体清单。一个完整的电商促销 brief 通常要求 300×250、728×90、320×50、160×600 四种标准尺寸 + 移动端自适应版本。

**② 素材制作**
按格式不同产出：
- 静态横幅：JPG/PNG/GIF，多为 IAB 标准尺寸
- HTML5：一个 zip 包，内含 `index.html` + 资源文件（JS/CSS/图片），必须遵循 DV360 HTML5 规范
- 富媒体：可展开/插页式的交互创意，通常也以 HTML5 zip 形式交付
- 视频：MP4/HD 编码、特定分辨率与时长；若走 VAST 则现场托管
- 原生：以文字+图标的 JSON 资产形式，由 DSP 端原生渲染

**③ 上传创建**
通过 API 或 UI 把资产提交到 DV360。对应脚本方法：
- `dv360_create_creative(advertiser_id, name, type=..., media_file=...)`
- `create_creative(advertiser_id, creative)`（dv360_api.py）
- 批量上传通常配合本地文件校验（体积、尺寸、编码）

**④ 系统审核**
Google 会对每个新创意做政策与规格审核。审核结果驱动状态机流转（详见第二章 2.6 节）。

**⑤ 关联 Line Item**
审核通过后通过 `LineItem.creativeIds` 把创意挂到投放单元。一个 Line Item 可挂多个创意；多个 Line Item 可复用同一创意。

**⑥ 实际投放**
创意在真实竞价中获取展示。此时保证创意格式与库存尺寸匹配才有填充（fill rate）可言。

**⑦ 数据回传**
通过 DV360 报表（`dv360_get_report`）拉取每个 creative 维度的指标，进入优化闭环。

**⑧ 优化迭代**
根据数据决定扩量、降权或下线。创意疲劳（Creative Fatigue）判断也发生在此阶段。

---

### 1.3 创意类型与格式清单

DV360 的创意格式体系以 `get_creative_format_options()`（dv360_api.py）返回的官方枚举为骨架。这些枚举在创建 Creative 时会进入 body 的 `type` 字段：

```python
# 来自 scripts/dv360_api.py 的 get_creative_format_options()
CREATIVE_FORMATS = [
    {'code': 'DISPLAY_VIDEO_AD',     'name': '展示视频广告', 'description': '标准视频广告'},
    {'code': 'BANNER_AD',            'name': '横幅广告',     'description': '静态或富媒体横幅'},
    {'code': 'NATIVE_AD',            'name': '原生广告',     'description': '与内容融合的广告'},
    {'code': 'HTML5_AD',             'name': 'HTML5 广告',   'description': '交互式 HTML5 广告'},
    {'code': 'VIDEO_PREROLL_AD',     'name': '前贴片视频',   'description': '视频前广告'},
    {'code': 'VIDEO_MIDROLL_AD',     'name': '中贴片视频',   'description': '视频中广告'},
]
```

#### 创意格式分类矩阵

DV360 的 Creative 在内部实际按更细的 `CreativeType` 分类，这里给出一份实战可用的汇总表：

| 格式枚举 | 内部类型 | 资产交付方式 | 典型尺寸 | 计费/value 单位 | 审核侧重 |
|----------|----------|--------------|----------|----------------|----------|
| BANNER_AD | 静态横幅 | 图片文件（JPG/PNG/GIF） | 300×250 / 728×90 / 320×50 / 160×600 | CPM/CPC | 素材规格、版权 |
| HTML5_AD | HTML5 横幅 | zip 包（含 index.html） | 300×250 / 728×90 / 970×250 / 自适应 | CPM/CPC | HTML5 规范、体积、脚本 |
| DISPLAY_VIDEO_AD | 富媒体/展示视频 | video 文件或 VAST 标签 | 富媒体自适应；视频 16:9 | CPM/CPV | 交互脚本、体验 |
| VIDEO_PREROLL_AD | 前贴片视频 | MP4 文件 + 横幅配套 | 16:9 / 9:16 / 1:1 | CPV/CPM | 分辨率、时长、编码 |
| VIDEO_MIDROLL_AD | 中贴片视频 | MP4 文件 + VAST | 16:9 主流 | CPV | 与内容衔接、时长 |
| NATIVE_AD | 原生广告 | JSON 资产（文案+图标+大图） | 由 DSP 原生渲染，自适应 | CPM/CPC | 文案规范、落地页 |
| AUDIO_AD | 音频广告 | MP3/AAC/WAV | 无视觉尺寸 | CPM | 音频体验 |
| APP_INSTALL_AD | App 安装 | 需配置 App 商店关联 | 各尺寸 | CPI | App 关联有效性 |
| DYNAMIC (DCO) | 动态创意 | 由 Catalog + 模板运行时组合 | 各尺寸 | CPM | 模板与数据源规范 |

#### 创意资产与 Creative 的关系

务必要区分两个概念：
- **Creative（创意对象）**：DV360 中的记录，包含元数据、状态、关联信息。
- **Creative Asset（创意资产）**：实际的媒体文件（图片/视频/zip/json）。

一个 Creative 可以承载多个资产（例如视频 + 配套横幅 + 音频），也可以引用外部 URL（例如 self-hosted VAST、HTML5 远程资源）。上传时 DV360 会做资产级审核，所以同一 Creative 名下若有多个资产，每个资产都需达标。

---

### 1.4 创意的关联模型（Creative ↔ Line Item ↔ Template）

这是创意管理系统的第二个核心心智模型。它决定了"谁在上传、谁在投放、谁在套模板"三者之间的松耦合关系。

```
                  ┌────────────────────────────────────────┐
                  │          Creative 关联模型               │
                  └────────────────────────────────────────┘

   Creative Template（模板库，属于 Advertiser）
        │  define variables（宽度/高度/文案/logo/CTA 槽位）
        │
        ▼
   Creative（创意记录，属于 Advertiser）
        │  ● templateId → 引用模板
        │  ● creativeVariables → 填入变量值
        │  ● asset → 具体媒体文件
        │  ● status → 审核状态
        │
        ├──────────────►（通过 creativeIds）
        ▼
   Line Item（投放单元）
        │  ● creativeIds: [c1, c2, c3]
        │  ● 每个创意按权重轮换出量
        ▼
   Auction（竞价）→ 展示

   关键性质：
   1. Template 属于 Advertiser，可被多个 Creative 复用
   2. Creative 属于 Advertiser，可被多个 Line Item 复用
   3. 一个 Line Item 可挂多个 Creative（轮换/测试）
```

#### 关联的实际用途

- **一对多（1 Creative : N Line Items）**：同一份品牌主视觉创意，可同时挂到品牌 Line Item、再营销 Line Item、新品 Line Item。省素材、省审核。
- **多对一（N Creatives : 1 Line Item）**：一个投放单元挂多个变体，DV360 轮询（Creative Rotation）自动分配流量，天然承载 A/B 测试与素材疲劳应对。
- **Template : Creative = 1 : N**：一个模板参数化后，批量生成几十上百个创意（详见第二章 2.4 节）。

#### DV360 中 Creative 关系在 API 层的体现

DV360 API v4 中，Line Item 对象包含创意关联合约。创建或更新 Line Item 时通过以下字段建立关系：

```json
{
  "lineItem": {
    "insertionOrderId": "102345",
    "displayName": "2026-Summer-Brand-LI",
    "lineItemType": "LINE_ITEM_TYPE_DISPLAY_DEFAULT",
    "creativeIds": ["cr_300250_banner_001", "cr_72890_banner_001"],
    "creativeRotation": "CREATIVE_ROTATION_RANDOM"
  }
}
```

脚本侧对应：
- `dv360_create_creative(advertiser_id, name, type, media_file)` 创建创意并获得 creative ID
- `dv360_list_creatives(advertiser_id, line_item_id)` 按 Line Item 过滤创意
- `dv360_create_line_item(...)` / `dv360_update_line_item(...)` 建立/维护关联

实战中，新建广告空跑的常见根因之一，就是"创意审核通过但未挂进 Line Item 的 creativeIds"。

---

### 1.5 创意模板体系总览

Creative Template 是 DV360 支持"一套模板、批量产出"的核心机制。它把创意拆成"固定外壳 + 可替换变量"，从而让运营团队无需逐条制作素材即可规模化生产创意。

```
                   Creative Template 体系
   ┌─────────────────────────────────────────────────────────────┐
   │  Advertiser 级模板库                                          │
   │  ┌──────────────────────────────────────────────┐            │
   │  │ Template: 夏季促销标准模板                     │            │
   │  │  ├── layout: index.html（含变量占位符）         │            │
   │  │  ├── variables:                                │            │
   │  │  │     ● width     (NUMBER,  默认300)           │            │
   │  │  │     ● height    (NUMBER,  默认250)           │            │
   │  │  │     ● headline  (TEXT,    适配多语言)        │            │
   │  │  │     ● price     (TEXT,    动态价格)          │            │
   │  │  │     ● logo      (ASSET,   Logo 位)          │            │
   │  │  │     ● cta       (TEXT,    按钮文案)          │            │
   │  │  │     ● backg_img (ASSET,   背景图)           │            │
   │  │  └── preview: 可预览渲染结果                     │            │
   │  └──────────────────────────────────────────────┘            │
   │         │  实例化（填入具体值）                                │
   │         ▼                                                    │
   │   Creative A: headline="夏季大促" price="¥199" ...            │
   │   Creative B: headline="新品首发" price="¥299" ...            │
   │   Creative C: ...（一次循环能生成 500 个）                     │
   └─────────────────────────────────────────────────────────────┘
                    │
                    ▼
            关联到 Line Item 并进入审核
```

#### 模板化生产的四种来源

| 方式 | 适用场景 | 规模 | 自动化程度 |
|------|----------|------|------------|
| UI 手填 | 少量高价值创意 | ≤10 | 低 |
| API `dv360_create_creative_from_template` | 批量生产 | 10~1000 | 中 |
| 数据驱动（Catalog + Dynamic） | DCO 全集生成 | 数千~百万 | 高 |
| 脚本循环（本地 for + API） | 全自动化流水线 | 任意 | 高 |

脚本层对应的两个方法：
- `dv360_list_creative_templates(advertiser_id)`：列出 Advertiser 下所有模板（含变量定义）
- `dv360_create_creative_from_template(template_id, ...)`：基于 template_id 实例化一个创意

这两者与本主题的关联极为紧密：模板功能是"审核状态机"与"批量创意"两大主题的接缝。大量实战踩坑都发生在模板变量类型填错、模板本身未过审核、以及模板渲染与库存尺寸不符上。

---

### 1.6 创意管理系统整体架构图

综合上面所有概念，这里给出创意管理系统的完整架构蓝图。它同时也是后文代码实现的分层参照：

```
                          ┌───────────────────────────────────────────────┐
                          │           创意管理系统架构                       │
                          └───────────────────────────────────────────────┘

 ┌──────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
 │  素材生产端    │   │  HTML5 打包   │   │  模板库       │   │  产品目录     │
 │ (设计/视频/文案)│──▶│ (zip 规范)   │──▶│ (变量定义)    │──▶│ (Catalog)    │
 └──────────────┘   └──────────────┘   └──────────────┘   └──────────────┘
        │                  │                 │                  │
        ▼                  ▼                 ▼                  ▼
 ┌─────────────────────────────────────────────────────────────────────┐
 │                         创意资管服务层   (Go/Python 实现)              │
 │  ┌────────────────┐  ┌────────────────┐  ┌──────────────────────┐    │
 │  │ 上传去重引擎     │  │ 审核队列调度器   │  │ 模板渲染/批量生成引擎  │    │
 │  │ (SHA256+pHash) │  │ (状态机驱动)    │  │ (变量注入+zip组装)    │    │
 │  └────────────────┘  └────────────────┘  └──────────────────────┘    │
 │  ┌────────────────┐  ┌────────────────┐  ┌──────────────────────┐    │
 │  │ 规格校验器      │  │ A/B 分流器      │  │ 关联与轮换调度器       │    │
 │  │ (尺寸/体积/编码) │  │ (样本分配)      │  │ (LineItem 挂接)      │    │
 │  └────────────────┘  └────────────────┘  └──────────────────────┘    │
 └───────────────┬─────────────────────────────────────────────────────┘
                 │  dv360_create_creative / create_creative / HTTP
                 ▼
        ┌───────────────────────┐
        │    DV360 Platform     │
        │  ┌─────────────────┐  │
        │  │ 审核状态机        │  │──▶ APPROVED/DISAPPROVED/PENDING
        │  │ 资产存储          │  │
        │  │ 模板引擎          │  │
        │  │ 竞价与投放        │  │──▶ 展示/点击/转化
        │  └─────────────────┘  │
        └───────────────────────┘
                 │
                 ▼
        ┌───────────────────────┐
        │   报表与优化闭环         │
        │  dv360_get_report      │──▶ CTR/CVR/完播率/疲劳判断
        └───────────────────────┘
```

以上五层（素材生产端 → 创意资管服务层 → DV360 Platform → 投放 → 报表优化）构成了创意管理系统的完整闭环。后文第二章会逐层拆开讲原理，第三章给实战流程与踩坑，第四章给 FAQ。

---

## 二、深度原理解析

### 2.1 HTML5 创意 zip 包规范深度解构

HTML5 创意（`HTML5_AD`）是富交互广告的主流形态，也是创意管理系统中最容易踩坑、最需要严格规范的部分。DV360 对 HTML5 创意以 **zip 包** 形式接收，内部结构、体积、审核都有硬性要求。

#### 2.1.1 标准的 zip 包结构

一个合法的 DV360 HTML5 创意 zip 包必须满足：

```
my_creative_300x250.zip
├── index.html                ★ 必需：创意入口，包内必须存在
├── css/
│   └── style.css             （可选）样式
├── js/
│   ├── main.js               （可选）逻辑脚本
│   └── vendor-lib.js         （可选）第三方库（体积会进总量）
├── img/
│   ├── bg.jpg
│   ├── logo.png
│   └── cta_btn.png
└── 其他静态资源（字体/JSON 数据等）
```

**硬性要求**：
1. **必须包含 `index.html`**，且它必须是创意渲染的入口。DV360 会在 iframe 中加载这个文件。
2. zip 内文件路径必须使用**相对路径**，且统一用 `/` 分隔符（Windows 反斜杠 `\` 会导致资源加载失败）。
3. 压缩前总大小有上限（常见实践以 200KB~250KB 为安全线，部分合作伙伴/库存有更严限制）。
4. 不得包含外部脚本引用依赖缺失（如远程加载 jQuery CDN 在无网环境会白屏）。
5. 默认必须手动点击才能展开/交互的面包屑（expanding creative 需提供 collapsible 交互）。

#### 2.1.2 zip 结构校验的 Python 实现

上传前用脚本做本地校验，能拦截绝大部分"审核被拒"和"上线白屏"问题。核心是遍历 zip 内条目并检查结构、路径、体积、尺寸元数据：

```python
import zipfile
import os
import re
from typing import List, Dict, Optional
from pathlib import Path

HTML5_MAX_SIZE = 200 * 1024      # 200KB 安全线
HTML5_HARD_LIMIT = 240 * 1024    # 部分库存的硬上限
ALLOWED_EXT = {'.html', '.htm', '.css', '.js', '.jsx', '.png', '.jpg',
               '.jpeg', '.gif', '.svg', '.webp', '.json', '.ttf',
               '.woff', '.woff2', '.eot', '.otf', '.map', '.txt', '.ico'}

class HTML5ZipValidator:
    """DV360 HTML5 创意 zip 规范校验器"""

    def __init__(self, zip_path: str, max_size: int = HTML5_MAX_SIZE):
        self.zip_path = zip_path
        self.max_size = max_size
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.entries: List[Dict] = []
        self.size = 0

    def validate(self) -> bool:
        """执行全部校验，返回是否通过"""
        if not os.path.exists(self.zip_path):
            self.errors.append(f"zip 文件不存在: {self.zip_path}")
            return False

        self.size = os.path.getsize(self.zip_path)
        if self.size > self.max_size:
            self.errors.append(
                f"压缩后文件体积 {self.size} bytes 超过上限 {self.max_size} bytes"
            )

        with zipfile.ZipFile(self.zip_path) as zf:
            names = zf.namelist()
            self.entries = [{'name': n, 'info': zf.getinfo(n)} for n in names]

            # 1. 必须有 index.html
            if 'index.html' not in names:
                self.errors.append("缺少 index.html 入口文件")

            # 2. 路径合法性：禁止绝对路径、.. 穿越、反斜杠
            for n in names:
                if n.startswith('/') or '\\' in n:
                    self.errors.append(f"非法路径分隔符/绝对路径: {n}")
                if '/..' in n or n.startswith('../'):
                    self.errors.append(f"路径穿越风险: {n}")

            # 3. 逐条目体积统计（含压缩膨胀）
            uncompressed_total = 0
            for n in names:
                try:
                    info = zf.getinfo(n)
                except KeyError:
                    continue
                if info.is_dir():
                    continue
                ext = Path(n).suffix.lower()
                if ext and ext not in ALLOWED_EXT:
                    self.warnings.append(f"非常规扩展名 {ext} 的文件: {n}")
                uncompressed_total += info.file_size

            # 4. 各资源条目体积警告
            for n in names:
                info = zf.getinfo(n)
                if info.file_size > 90 * 1024 and not info.is_dir():
                    self.warnings.append(
                        f"大体积资源 {n} 解压后 {info.file_size} bytes"
                    )

            self._log_uncompressed_total(uncompressed_total)

        return len(self.errors) == 0

    def _log_uncompressed_total(self, total: int):
        if total > self.max_size:
            self.warnings.append(
                f"解压后总体积 {total} bytes 可能触发审核体积限制"
            )

    def summary(self) -> str:
        status = "通过" if not self.errors else "失败"
        lines = [
            f"HTML5 zip 校验结果: {status}",
            f"  压缩后大小: {self.size} bytes",
            f"  条目数: {len(self.entries)}",
            f"  错误: {len(self.errors)}",
            f"  警告: {len(self.warnings)}",
        ]
        for err in self.errors:
            lines.append(f"    [错误] {err}")
        for warn in self.warnings:
            lines.append(f"    [警告] {warn}")
        return "\n".join(lines)


if __name__ == "__main__":
    import sys
    for path in sys.argv[1:]:
        v = HTML5ZipValidator(path)
        ok = v.validate()
        print(v.summary())
```

这段脚本对应生产流水线的"素材进库前置拦截"环节，能在资源浪费（重复审核）和业务损失（上线白屏）之前把问题挡在门外。

#### 2.1.3 HTML5 zip 审核常见拒因

| 拒因 | 说明 | 规避方法 |
|------|------|----------|
| 缺少 index.html | zip 入口缺失无法渲染 | 校验器强制存在 |
| 体积超限 | 压缩后 >200KB | 压缩图片、精简 JS、按需加载 |
| 外部 JS 依赖缺失 | CDN 无网解析失败 | 把所有依赖打进包 |
| 反斜杠路径 | Windows 打包残留 | 统一 `/` 并检测 `\` |
| 自动播放音频 | 富媒体自动发声被拒 | 默认静音，用户触发后再出声 |
| 隐私数据采集 | 脚本收集 PII | 移除或声明合规 |
| 尺寸与声明不符 | zip 内画布 ≠ 上报尺寸 | 校验宽高与 creative 声明一致 |
| 无法关闭 | 展开式无收起按钮 | 强制提供 collapse 交互 |

#### 2.1.4 HTML5 尺寸与体积参考表

| 库存/格式 | 常见尺寸 | 压缩后体积上限 | 备注 |
|-----------|----------|----------------|------|
| 标准展示横幅 | 300×250 / 728×90 / 320×50 | 150~200KB | 最通用 |
| 大尺寸/富媒体 | 970×250 / 300×600 / 970×90 | 200~250KB | 展开式另算 |
| 移动自适应 | 自适应（宽高比可变） | 150~200KB | 需响应式布局 |
| 视频配套 HTML5 | 与视频同尺寸 | 200KB | 作为 Overlay 或被替换 |
| 原生式 HTML5 | 由 DSP 渲染 | 100~150KB | 更严 |

---

### 2.2 富媒体创意（Rich Media）深度解析

富媒体创意（Rich Media）是比静态/普通 HTML5 更高阶的互动形态，分为**展开式（Expanding）**、**插页式（Interstitial/Peel）**、**浮动式（Floating）** 等。它们在 DV360 中多以 `HTML5_AD` 或 `DISPLAY_VIDEO_AD`（内嵌视频交互）承载。

#### 2.2.1 富媒体类型对比

| 类型 | 交互方式 | 典型尺寸 | 可见/音量要求 | 审核风险 |
|------|----------|----------|---------------|----------|
| 展开式 Expanding | 悬停/点击展开覆盖 | 收起 300×250 → 展开 970×250 | 展开需用户触发 | 自动展开被拒 |
| 插页式 Interstitial | 页面切换全屏弹出 | 自适应全屏 | 需关闭按钮 | 遮挡正文被拒 |
| 撕角式 Peel | 点击页面角落撕开 | 角落 120×240 展开 | 需关闭 | 侵入性被审 |
| 浮动式 Floating | 悬浮跟随 | 底部条 | 需关闭 | 遮挡内容被拒 |
| 内嵌视频富媒体 | 创意内含视频 | 300×250 + 视频 | 静音起播 | 自动播放政策 |

#### 2.2.2 展开式富媒体的交互状态机

展开式创意内部是一个小型的交互状态机，实现时需严格遵循"进可开、退可关"原则：

```
                   用户触发（悬停/点击）
  收起态 COLLAPSED ──────────────────────────▶ 展开态 EXPANDED
        ▲                                          │
        │                                          │ 自动/用户
        │                                          ▼
        │                                     展开动画执行中
        │                                          │
  收起动画执行中 ◀───────── 超时/关闭/移开 ◀─────────┘
```

实现要点：
- **收起态必须存在**：展开式不能一上来就是全展开。
- **必须有明确的收起/关闭手段**：关闭按钮、点击创意外部、移动到移除区域。
- **展开通常限制区域**：多数库存限定展开覆盖区域（如仅在视口内、不遮挡正文 ≥X 秒）。
- **时间约束**：自动收起通常在几秒后触发，避免长时间遮挡。

#### 2.2.3 富媒体 vs 普通 HTML5 在审核上的差异

普通 HTML5 与富媒体的审核差异主要体现在"用户体验政策"维度：

| 维度 | 普通 HTML5 | 富媒体（展开/插页式） |
|------|-----------|----------------------|
| 自动展开 | 不适用 | **禁止**，须用户触发 |
| 关闭按钮 | 可选 | **强制**，清晰可见 |
| 遮挡正文 | 极少 | 严格限制时长与区域 |
| 自动发声 | 默认静音 | 默认静音，交互后有声 |
| 视觉惊吓 | 极少 | 禁止闪烁/全屏跳变 |
| 重复弹出 | 不适用 | 限制频率 |

这些政策是实现富媒体创意时必须内化的规范，开发者应在打包阶段就用配置位强制，而不是等审核被拒后再改。

#### 2.2.4 富媒体创意实现要点清单

1. 展开/收起动画使用 CSS transform/opacity，避免大量 JS 主线程阻塞。
2. 关闭逻辑绑定到 iframe 外点击与移动感知。
3. 所有资源必须打进 zip（无网环境可用）。
4. 提供 `collapsed` 与 `expanded` 两套渲染，确保收起态本身也是完整广告。
5. 审核政策越高危的交互，越要在提交前自测（用真实 iframe 沙箱测关闭键可达）。

---

### 2.3 视频创意规范深度解析（时长 / 分辨率 / 码率 / VAST）

视频创意是 DV360 高价值库存的主力，`VIDEO_PREROLL_AD` 与 `VIDEO_MIDROLL_AD` 都有严格的技术规格。视频创意在上传前必须先满足一系列"硬指标"，否则要么审核被拒，要么填充率极低。

#### 2.3.1 视频技术规格对照表

| 规格维度 | Pre-roll 推荐 | 中贴片推荐 | 低端库存下限 | 备注 |
|----------|---------------|------------|--------------|------|
| 时长 | 15~30 秒 | 15~60 秒 | ≤6 秒（Bumper） | 过长会被截断/降权 |
| 分辨率 | 1280×720 (720p) | 1920×1080 (1080p) | 640×480 | 低于 480p 会被拒 |
| 帧率 | 30fps | 30fps | 24fps | 高帧率体积大 |
| 编码 | H.264 (AVC) | H.264 (AVC) | H.264 | **必选 H.264** |
| 容器 | MP4 (.mp4) | MP4 (.mp4) | MP4 | 首选 .mp4 |
| 码率 | 3~5 Mbps | 5~8 Mbps | 1 Mbps | 过高影响加载 |
| 长宽比 | 16:9 | 16:9 / 1:1 / 9:16 | 16:9 | 需与库存匹配 |
| 音轨 | AAC, 128kbps | AAC | - | 无声需静音标志 |
| 文件大小 | ≤500MB（720p） | ≤500MB | - | 大文件走 CDN |

#### 2.3.2 视频文件的 H.264 校验 Python 实现

视频不合规是"审核/投放"高发问题。用 Python 解析 MP4 的 `ftyp` box 与 `moov` 元数据，可在上传前做基础编码校验（完整校验还需 ffprobe，这里给出纯结构检测示例）：

```python
import struct
from dataclasses import dataclass
from typing import Optional, List

@dataclass
class VideoProbe:
    path: str
    size: int
    major_brand: str
    compatible_brands: List[str]
    file_type: str
    error: Optional[str] = None

    @property
    def is_mp4(self) -> bool:
        return self.file_type == 'isom' or 'mp4' in self.compatible_brands

    @property
    def is_h264_friendly(self) -> bool:
        # H.264 通常由 avc1 采样描述承载，纯结构层面先看 container
        return self.is_mp4


def probe_mp4(path: str) -> VideoProbe:
    """读取 MP4 ftyp box 获取品牌信息，做快速容器校验"""
    with open(path, 'rb') as f:
        data = f.read(64)  # 只读头部即可解析 ftyp（通常在文件头）
    size = len(open(path, 'rb').read()) if False else _file_size(path)

    # ftyp box: [size(4B)][type 'ftyp'(4B)][major_brand(4B)][minor(4B)][compat...]
    if len(data) < 12 or data[4:8] != b'ftyp':
        return VideoProbe(path, size, '', [], 'UNKNOWN',
                          error='不是标准 MP4（缺少 ftyp box）')

    box_size = struct.unpack('>I', data[0:4])[0]
    major_brand = data[8:12].decode('latin1')
    compat = []
    minor = struct.unpack('>I', data[12:16])[0] if box_size >= 16 else 0
    pos = 16
    while pos + 4 <= min(box_size, len(data)):
        compat.append(data[pos:pos+4].decode('latin1'))
        pos += 4

    return VideoProbe(path, size, major_brand, compat, 'isom')


def _file_size(path: str) -> int:
    import os
    return os.path.getsize(path)


def check_video_spec(path: str) -> List[str]:
    """返回不满足规范的 error 列表"""
    errs = []
    probe = probe_mp4(path)
    if probe.error:
        errs.append(probe.error)
        return errs
    if not probe.is_mp4:
        errs.append(f"容器不是 MP4: brands={probe.compatible_brands}")
    if probe.size > 500 * 1024 * 1024:
        errs.append(f"文件过大 {probe.size} bytes（>500MB）")
    return errs
```

> 说明：真正可靠的分辨率/码率/时长检测需调用 `ffprobe`。示例展示了如何在 Python 层做"零依赖快速拦截"，生产系统应把两者结合。

#### 2.3.3 VAST（Video Ad Serving Template）解析

VAST（Video Ad Serving Template）是 IAB 制定的视频广告投放协议，DV360 既可直接托管视频文件，也可通过 **self-hosted VAST tag** 引外部视频。理解 VAST 对 `VIDEO_PREROLL_AD` 的中贴片衔接、多资源备选、跟踪事件上报至关重要。

**VAST 文档的关键结构：**

```
VAST 3.0
└── <Ad>
    ├── <InLine>（内联实际广告内容） 或
    ├── <Wrapper>（指向另一个 VAST 地址，用于链式投放）
    └── <Creatives>
        └── <Creative> [type="media"]
            ├── <Linear>（线性视频广告）
            │   ├── <Duration> 时长
            │   ├── <MediaFiles>
            │   │   └── <MediaFile>（多个备选：不同码率/分辨率/格式）
            │   ├── <VideoClicks>
            │   │   └── <ClickThrough>/<ClickTracking>
            │   └── <TrackingEvents>
            │       ├── start / firstQuartile / midpoint
            │       ├── thirdQuartile / complete
            │       └── (跟踪像素上报)
            └── <NonLinearAds>（overlay 伴随横幅）
```

**DV360 中上视频创意的三条路线：**

| 路线 | 适用 | 优点 | 缺点 |
|------|------|------|------|
| 直接上传 MP4 | 简单视频创意 | 无需自建服务器 | 体积/编码受限 |
| Self-hosted VAST tag | 复杂/多码率 | 灵活、多备选 | 需保证 tag 稳定可达 |
| DV360 Hosted + 伴随横幅 | pre-roll 常配 | 一站式 | 伴随横幅另需素材 |

**Self-hosted VAST 常见坑：**
- VAST URL 必须公网可达且响应快，否则严重拉低填充率。
- 必须提供 `MediaFiles` 的**多个码率备选**（低带宽用户可降级）。
- `ClickThrough` 跳转目标需有效且符合政策。
- `TrackingEvents` 用于完播率上报，事件事件名必须符合 VAST 命名空间（`start`/`complete` 等）。
- 长视频（>60s）要确认库存接受，否则截断导致完播率失真。

#### 2.3.4 视频创意审核重点

| 维度 | 审核关注 | 规避 |
|------|----------|------|
| 编码 | 必须 H.264 | 用 ffmpeg 转码 |
| 分辨率 | ≥480p，推荐 720p+ | 拒绝低清 |
| 时长 | pre-roll 15-30s 主流 | 过长做剪裁 |
| 音轨 | 无声需静音标志 | 或用静音文件 |
| 版权 | 音乐/图片授权 | 提供授权或免版权 |
| 落地页 | 跳转目标有效合规 | 校验 landing page |
| 自动播放 | 静音起播 | 默认 muted |

---

### 2.4 Creative Templates API 与从模板创建

Creative Template 机制对应脚本 API：`dv360_list_creative_templates` 与 `dv360_create_creative_from_template`。这是 DV360 规模化生产创意的核心接口，理解它的变量模型是使用模板的关键。

#### 2.4.1 模板的变量模型

模板把创意固化成"外壳 + 变量槽位"。一个典型模板的变量定义（JSON 示意）：

```json
{
  "template": {
    "templateId": "tpl_summer_promo_001",
    "displayName": "夏季促销标准模板",
    "creativeType": "CREATIVE_TYPE_HTML5",
    "variables": [
      {
        "key": "width",
        "type": "NUMBER",
        "defaultValue": "300",
        "description": "广告宽度"
      },
      {
        "key": "height",
        "type": "NUMBER",
        "defaultValue": "250",
        "description": "广告高度"
      },
      {
        "key": "headline",
        "type": "TEXT",
        "defaultValue": "限时特惠",
        "description": "主标题"
      },
      {
        "key": "price",
        "type": "TEXT",
        "defaultValue": "¥299",
        "description": "价格文案"
      },
      {
        "key": "logo",
        "type": "ASSET",
        "defaultValue": "https://cdn.brand.com/logo.png",
        "description": "品牌 logo 位"
      },
      {
        "key": "cta",
        "type": "TEXT",
        "defaultValue": "立即购买",
        "description": "按钮文案"
      },
      {
        "key": "landingUrl",
        "type": "URL",
        "defaultValue": "https://brand.com/landing",
        "description": "跳转链接"
      }
    ]
  }
}
```

变量类型常见的枚举：`NUMBER` / `TEXT` / `ASSET` / `URL` / `COLOR` / `BOOLEAN` / `ENUM`。类型填错是"模板化失败"（第四章 FAQ 有专节）的头号根因。

#### 2.4.2 从模板创建创意的 Python 示例

```python
from typing import Dict, List


def build_creative_variables(template, overrides: Dict) -> Dict:
    """根据模板变量定义合并并校验变量值，返回可提交的 creativeVariables"""
    variables = {}
    errors = []

    for var in template.get('variables', []):
        key = var.get('key')
        vtype = var.get('type')
        raw = overrides.get(key, var.get('defaultValue'))

        # 类型校验
        if vtype == 'NUMBER':
            try:
                variables[key] = str(int(raw))
            except (TypeError, ValueError):
                errors.append(f"变量 {key} 期望 NUMBER，收到 {raw!r}")
        elif vtype == 'URL':
            if not str(raw).startswith(('http://', 'https://')):
                errors.append(f"变量 {key} 期望合法 URL，收到 {raw!r}")
            variables[key] = raw
        elif vtype in ('TEXT', 'ASSET', 'COLOR', 'ENUM', 'BOOLEAN'):
            variables[key] = raw
        else:
            errors.append(f"未知变量类型 {vtype} 用于 {key}")

    if errors:
        raise ValueError("; ".join(errors))
    return variables


def batch_create_from_template(adapter, advertiser_id: str, template,
                               configs: List[Dict],
                               max_concurrency: int = 4) -> List[Dict]:
    """
    基于单个模板批量实例化创意。

    adapter: 封装了 dv360_create_creative_from_template 的方法桩
    configs: 每项含 name + overrides（变量覆盖）
    """
    results = []
    for i, cfg in enumerate(configs):
        variables = build_creative_variables(template, cfg.get('overrides', {}))
        payload = {
            'advertiser_id': advertiser_id,
            'template_id': template.get('templateId'),
            'name': cfg.get('name', f"creative_{i}"),
            'creative_variables': variables,
            # 下面是脚本层的伪调用，实际由 adapter 映射到
            # dv360_create_creative_from_template(template_id, **kwargs)
        }
        res = adapter.dv360_create_creative_from_template(
            template.get('templateId'),
            advertiser_id=advertiser_id,
            name=cfg.get('name'),
            creative_variables=variables,
        )
        results.append({'config': cfg, 'result': res})
    return results


# 示例：一个 300×250 模板批量生成 3 个不同文案的创意
def demo(adapter, advertiser_id, template):
    configs = [
        {'name': 'summer_A', 'overrides': {'headline': '夏季大促', 'price': '¥199', 'cta': '立即抢购'}},
        {'name': 'summer_B', 'overrides': {'headline': '新品首发', 'price': '¥299', 'cta': '了解更多'}},
        {'name': 'summer_C', 'overrides': {'headline': '会员专享', 'price': '¥99',  'cta': '开通会员'}},
    ]
    return batch_create_from_template(adapter, advertiser_id, template, configs)
```

#### 2.4.3 模板化生产的最佳实践

1. **先审模板再批量**：模板本身需经审核，务必先用一个样本创意验证模板能过审再铺量。
2. **变量最小化**：模板越通用，越要收敛变量数量，避免每个创意都踩一个变量坑。
3. **统一命名规范**：`{campaign}_{format}_{size}_{version}`，便于批量排障。
4. **配合规格校验**：模板生成后仍要在本地校验尺寸/体积，模板渲染不等于一定合规。
5. **限流与去重**：批量调用注意 API 配额，且对相同变量值做去重（避免重复创意刷屏）。

---

### 2.5 Dynamic Creative (DCO) 深度解析

动态创意优化（Dynamic Creative Optimization / DCO）让"一个模板 + 一个数据源（Catalog）"在展示时实时组合出个性化创意。它是创意管理系统里自动化程度最高的形式，与固定 Creative 有本质区别。

#### 2.5.1 DCO 与固定创意的架构差异

```
  固定创意（Static）                    动态创意（Dynamic / DCO）

  Creative ──▶ 一个固定素材                Template ──▶ 外壳（布局、变量槽）
                    │                           │
                    ▼                           ├── Catalog（产品数据源）
                固定展示                          │     ├── 商品1 {图,价,名}
                                                 │     ├── 商品2 {图,价,名}
                                                 │     └── 商品N
                                                 ▼
                                          竞价时按用户画像选择商品
                                          并实时渲染个性化创意展示
```

#### 2.5.2 动态属性（DataFeed）工作流

DCO 核心是 feed（数据源）。完整工作流：

```
① 准备 Catalog / feed 数据
   ─ 商品字段: sku, title, image, price, sale_price, url, ...
② 上传/同步 feed 到 DV360（或连接展示目录）
   ─ dv360_list_display_catalogs / dv360_get_display_catalog_items
③ 创建 Dynamic Creative 模板
   ─ 模板内变量绑定 feed 字段
④ 配置归因/选品逻辑
   ─ 基于用户行为（浏览/加购/类目）选择要展示的商品
⑤ 配置落地页与 CTA
⑥ 关联 Line Item 并投放
⑦ 监控动态创意的展示与转化，持续优化选品规则
```

#### 2.5.3 feed 数据字段规范示例

```json
{
  "sku": "SKU-1001",
  "title": "无线降噪耳机 Pro",
  "image_url": "https://cdn.brand.com/imgs/headphone-pro.jpg",
  "price": "899.00",
  "currency": "CNY",
  "sale_price": "599.00",
  "link_url": "https://brand.com/p/SKU-1001",
  "category": "electronics/audio",
  "tags": ["new", "flagship"],
  "availability": "in_stock"
}
```

#### 2.5.4 DCO 实战要点与坑

| 要点 | 说明 |
|------|------|
| feed 必填字段 | 缺失字段会导致该商品无法出创意 |
| 图片 URL 可达性 | 动态图片需公网可访问且格式合规 |
| 价格货币一致性 | 币种/格式不一致会被拒 |
| 模板变量命名 | 必须与 feed 字段一一对应 |
| 动态选品 | 无行为数据时用默认/热门商品兜底 |
| 数据刷新 | feed 过期导致展示旧价/缺货，需定时同步 |
| 审核 | DCO 模板也要过审，feed 内容变动可能触发重审 |

**动态创意"不生效"的排查**（对应第四章 FAQ）：先检查 feed 是否最新、模板变量名是否与字段名严格一致、模板是否过审、以及是否同一个 Line Item 内静态与动态创意冲突导致动态被忽略。

---

### 2.6 创意审核状态机（APPROVED / DISAPPROVED / PENDING）

创意审核是 DV360 管理系统的"政策闸门"，也是几乎所有运营踩坑的高频区。它由一个明确的状态机驱动。

#### 2.6.1 审核状态机

```
                提交/更新
      ┌──────────────────────────┐
      ▼                          │
   PENDING ◀────────────────────┐│
      │  （等待 Google 审核）       ││ 修改后重新提交
      │                          ││
      ├──► APPROVED ◀────────────┘│
      │       （通过，可投放）       │
      │          │                │
      │          │ 素材/字段变更     │
      │          └──► PENDING      │
      ▼                           │
   DISAPPROVED ───────────────────┘
      （被拒，需修改）
```

状态流转规则：

| 当前状态 | 触发事件 | 目标状态 |
|----------|----------|----------|
| (无) | 新建/上传 | PENDING |
| PENDING | 审核通过 | APPROVED |
| PENDING | 审核拒绝 | DISAPPROVED |
| APPROVED | 素材或关键字段变更 | PENDING（重新审核） |
| APPROVED | 被抽查发现违规 | DISAPPROVED |
| DISAPPROVED | 修改后重新提交 | PENDING |

#### 2.6.2 从 API 读审核状态

DV360 通过 `advertisers/{advertiserId}/creatives/{creativeId}` 或列表接口返回审核信息。简化后：

```python
def poll_creative_approval(adapter, advertiser_id: str,
                           creative_id: str, timeout: int = 1800,
                           interval: int = 60):
    """
    轮询创意审核结果，直到 APPROVED/DISAPPROVED 或超时。
    adapter.dv360_get_creative_approval 为脚本层方法桩。
    """
    import time

    deadline = time.time() + timeout
    while time.time() < deadline:
        approval = adapter.dv360_get_creative_approval(
            advertiser_id=advertiser_id,
            creative_id=creative_id,
        )
        status = approval.get('status', 'PENDING')
        if status != 'PENDING':
            return approval
        time.sleep(interval)

    return {'status': 'PENDING', 'timeout': True,
            'error': f"审核超过 {timeout}s 未返回结果"}
```

#### 2.6.3 常见 DISAPPROVED 原因分类

| 类别 | 具体原因 |
|------|----------|
| 规格违规 | 体积超限、分辨率过低、编码不对、缺 index.html |
| 政策违规 | 虚假承诺、误导性文案、未授权版权、敏感类目 |
| 落地页违规 | 跳转 404、落地页与广告内容不符、恶意下载 |
| 用户体验 | 自动展开、无法关闭、自动发声、过度遮挡 |
| 版权/隐私 | 无授权音乐图片、收集个人身份信息 |

#### 2.6.4 审核状态机的 Go 实现

```go
package creative

import (
	"fmt"
	"time"
	"sync"
)

// ApprovalState 审核状态枚举
type ApprovalState int

const (
	StatePending ApprovalState = iota
	StateApproved
	StateDisapproved
)

// ApprovalReason 审核拒绝原因
type ApprovalReason struct {
	Code    string
	Message string
	Field   string
}

// Creative 创意记录
type Creative struct {
	ID             string
	AdvertiserID   string
	Name           string
	Type           string // HTML5_AD / BANNER_AD / ...
	State          ApprovalState
	Reasons        []ApprovalReason
	ReviewedAt     time.Time
	SubmitCount    int
}

// ReviewMachine 审核状态机
type ReviewMachine struct {
	mu         sync.Mutex
	creatives  map[string]*Creative
	// submitFn 模拟提交审核（真实场景回调 DV360 API）
	submitFn   func(c *Creative) (ApprovalState, []ApprovalReason)
}

func NewReviewMachine(submitFn func(*Creative) (ApprovalState, []ApprovalReason)) *ReviewMachine {
	return &ReviewMachine{
		creatives: make(map[string]*Creative),
		submitFn:  submitFn,
	}
}

// Submit 提交创意进入 PENDING 状态
func (m *ReviewMachine) Submit(c *Creative) error {
	m.mu.Lock()
	defer m.mu.Unlock()

	if c == nil {
		return fmt.Errorf("creative is nil")
	}
	c.State = StatePending
	c.SubmitCount++
	m.creatives[c.ID] = c
	return nil
}

// ProcessOnce 执行一次审核轮询，驱动状态流转
func (m *ReviewMachine) ProcessOnce(c *Creative) {
	// 只有 PENDING 才推进
	if c.State != StatePending {
		return
	}
	state, reasons := m.submitFn(c)
	c.State = state
	c.Reasons = reasons
	c.ReviewedAt = time.Now()
}

// IsApproved 判断是否可投放
func (c *Creative) IsApproved() bool {
	return c.State == StateApproved
}

// GetBlockingReasons 返回首个导致 DISAPPROVED 的原因
func (c *Creative) GetBlockingReasons() []ApprovalReason {
	if c.State != StateDisapproved {
		return nil
	}
	return c.Reasons
}
```

这个状态机实现了核心不变量：**只有 APPROVED 且关联 Line Item 的创意才会出量**；任何素材/字段变更都会把它踢回 PENDING 重新审核，这正是运营常遇到的"改了海报导致广告突然停投"的根本原因。

---

### 2.7 创意 A/B 测试机制与分流

创意 A/B 测试（Creative Testing）在 DV360 中通常通过**一个 Line Item 挂多个创意 + 轮换策略 + 报表对比**实现。理解"并行分流"与"显著性判断"是设计测试的关键。

#### 2.7.1 DV360 中的创意轮换与 A/B 测试模型

DV360 的 Line Item 支持 `creativeRotation`，常见策略：

| 轮换策略 | 行为 | 适用 |
|----------|------|------|
| RANDOM（随机） | 各创意按等权重随机出量 | 常规 A/B 测试（无偏分配） |
| WEIGHTED（权重） | 按权重分配流量 | 渐进放量（80/20 试探） |
| OPTIMIZED（优化） | 由系统按历史表现优化比例 | 已收敛的长期测试 |

A/B 测试的本质是"控制变量 + 统计对比"。要在一个 Line Item 里做可靠的创意测试：

```
Line Item: Summer-AB-LI
   ├── creativeRotation = RANDOM
   ├── creativeIds = [A, B, C]
   ├── A → 300x250 静态（对照组）
   ├── B → 300x250 HTML5（试验组1）
   └── C → 300x250 HTML5 + 弹窗CTA（试验组2）
            │
            ▼
        随机分流（等样本），积累样本
            │
            ▼
        报表按 creative 维度对比：CTR / CVR / 完播率
            │
            ▼
        显著性检验（卡方/z 检验）→ 判定胜者
```

**关键前提：测试变量以外的所有条件必须一致**（同一 Line Item、同一预算、同一定向、同时间段），否则对比失真。

#### 2.7.2 A/B 测试的样本量与显著性

在设计测试时，样本量与显著性直接决定测试可信度。关键公式：

**最小样本量（用于比例类指标，如 CTR）**：
$$n = \frac{(z_{\alpha/2} + z_\beta)^2 \cdot (p_1(1-p_1) + p_2(1-p_2))}{(p_1 - p_2)^2}$$

其中：
- $z_{\alpha/2}$：显著性水平对应的 z 值（α=0.05 时 ≈1.96）
- $z_\beta$：检验功效对应的 z 值（power=0.8 时 ≈0.84）
- $p_1, p_2$：两组预期转化（点击）率

**Python 样本量计算器：**

```python
from scipy import stats

def min_sample_size_ratio(p1: float, p2: float, alpha: float = 0.05,
                          power: float = 0.8) -> float:
    """
    计算比例类指标（CTR/CVR）A/B 测试每组最小样本量。
    p1/p2 为期望的比例（如 CTR 0.01 表示 1%）。
    """
    z_alpha = stats.norm.ppf(1 - alpha / 2)   # 双侧
    z_beta = stats.norm.ppf(power)
    var = p1 * (1 - p1) + p2 * (1 - p2)
    n = ((z_alpha + z_beta) ** 2) * var / ((p1 - p2) ** 2)
    return float(n)


def min_sample_size_mean(std: float, mde: float, alpha: float = 0.05,
                         power: float = 0.8) -> float:
    """
    均值类指标（如平均观看时长）最小样本量。
    std 为标准差，mde 为最小可检测差异（效应量）。
    """
    z_alpha = stats.norm.ppf(1 - alpha / 2)
    z_beta = stats.norm.ppf(power)
    return float(((z_alpha + z_beta) ** 2) * 2 * (std ** 2) / (mde ** 2))


def two_proportion_ztest(x1, n1, x2, n2):
    """两组比例的 z 检验，返回 z 值与 p 值"""
    p1 = x1 / n1
    p2 = x2 / n2
    p = (x1 + x2) / (n1 + n2)
    se = (p * (1 - p) * (1 / n1 + 1 / n2)) ** 0.5
    if se == 0:
        return 0.0, 1.0
    z = (p1 - p2) / se
    p_value = 2 * (1 - stats.norm.cdf(abs(z)))
    return z, p_value


if __name__ == "__main__":
    # 示例：CTR 1% vs 1.5%，α=0.05，power=0.8
    n = min_sample_size_ratio(0.01, 0.015)
    print(f"每组需最少展示样本量: {int(n):,}")

    # 假设 A 组 0.01 CTR，B 组 0.014，各有 20 万展示
    z, pv = two_proportion_ztest(2000, 200000, 2800, 200000)
    print(f"z={z:.3f}, p={pv:.5f}，{'显著' if pv < 0.05 else '不显著'}")
```

**样本量与显著性速查表**（CTR 级测试，power=0.8，α=0.05）：

| 预期差异（提升） | 基础 CTR 1% 时每组样本 | 基础 CTR 3% 时每组样本 |
|------------------|------------------------|------------------------|
| +10% | ~350 万 | ~110 万 |
| +20% | ~90 万 | ~30 万 |
| +30% | ~40 万 | ~13 万 |
| +50% | ~15 万 | ~5 万 |

结论：低基数指标的提升检测需要巨大样本，周末两天的量往往不足以判定胜负。这就是"测试天数不足就下结论"的经典陷阱。

#### 2.7.3 A/B 测试 Practical 规程

1. **固定测试窗口**：避免中途加码/改价导致污染。
2. **并行而非串行**：同一周期内多创意并列，避免时间偏差。
3. **预登记指标**：测试前选定主指标（CTR 或 CVR），避免"结果导向"挑数字。
4. **达到样本量再判定**：未达最小样本量不下结论。
5. **考虑多重比较**：3 组以上要校正（如 Bonferroni），否则假阳性上升。
6. **观察期完整**：覆盖周一~周日，避免日间波动偏差。

#### 2.7.4 A/B 分流的 Go 实现

```go
package creative

import (
	"encoding/binary"
	"hash/fnv"
	"math/rand"
)

// ABAllocator 基于权重的创意分流器
type ABAllocator struct {
	creatives []string
	weights   []float64
}

// NewEvenAllocator 等权分配（RANDOM 策略）
func NewEvenAllocator(ids []string) *ABAllocator {
	w := make([]float64, len(ids))
	for i := range w {
		w[i] = 1.0
	}
	return &ABAllocator{creatives: ids, weights: w}
}

// PickRandom 均匀随机选择一个创意（无偏，适合 A/B 初测）
func (a *ABAllocator) PickRandom(rng *rand.Rand) string {
	if len(a.creatives) == 0 {
		return ""
	}
	return a.creatives[rng.Intn(len(a.creatives))]
}

// PickWeighted 按权重选择（适合渐进放量）
func (a *ABAllocator) PickWeighted(rng *rand.Rand) string {
	total := 0.0
	for _, w := range a.weights {
		total += w
	}
	r := rng.Float64() * total
	acc := 0.0
	for i, w := range a.weights {
		acc += w
		if r < acc {
			return a.creatives[i]
		}
	}
	return a.creatives[len(a.creatives)-1]
}

// DeterministicPick 基于用户 ID 哈希的确定性分配（保证同一用户始终同一变体）
func (a *ABAllocator) DeterministicPick(userID string) string {
	h := fnv.New64a()
	h.Write([]byte(userID))
	idx := binary.BigEndian.Uint64(h.Sum(nil)) % uint64(len(a.creatives))
	return a.creatives[idx]
}
```

#### 2.7.5 创意疲劳（Creative Fatigue）机制

当单一创意暴露过度，用户重复看到会流失点击，即创意疲劳。判断与应对：

```
疲劳信号：
├── CTR 连续下降（对比 30 天均值，>20~30%）
├── CPA 上升
├── 频次超过阈值（品牌 3+，再营销 5+）
└── 视频完播率骤降

应对：
├── 轮换新创意（补充新鲜素材）
├── 调整频次上限（frequency cap）
├── 冷启动暂停低效创意
└── 定期用 A/B 测试补充新变体
```

---

### 2.8 Go 实现创意资管系统（上传去重 / 审核队列 / 模板渲染）

综合第二章各节原理，这里给出一个相对完整的 Go 创意资管系统骨架，覆盖三条核心链路：**上传去重引擎**、**审核队列调度器**、**模板渲染/批量生成引擎**。

#### 2.8.1 上传去重引擎

创意重复上传会浪费审核配额、刷屏库存。去重要在"文件层（候选识别）"与"语义层（pHash）"都要做：

```go
package creative

import (
	"crypto/sha256"
	"encoding/hex"
	"sync"
)

// DedupEngine 创意上传去重引擎
type DedupEngine struct {
	mu       sync.RWMutex
	exact    map[string]string // sha256 -> creativeID  （精确去重索引）
	recent   map[string]string // phash -> creativeID  （感知去重索引，简化用 key）
}

func NewDedupEngine() *DedupEngine {
	return &DedupEngine{
		exact:  make(map[string]string),
		recent: make(map[string]string),
	}
}

// RegisterExact 登记精确哈希
func (d *DedupEngine) RegisterExact(sha string, creativeID string) {
	d.mu.Lock()
	defer d.mu.Unlock()
	d.exact[sha] = creativeID
}

// FindExact 精确查重：内容完全一致
func (d *DedupEngine) FindExact(data []byte) (string, bool) {
	sum := sha256.Sum256(data)
	sha := hex.EncodeToString(sum[:])
	d.mu.RLock()
	defer d.mu.RUnlock()
	id, ok := d.exact[sha]
	return id, ok
}

// phash 简化占位：真实实现需图像 DCT/perceptual hash 库
func (d *DedupEngine) FindPerceptual(imgFingerprint string) (string, bool) {
	d.mu.RLock()
	defer d.mu.RUnlock()
	id, ok := d.recent[imgFingerprint]
	return id, ok
}
```

去重判定策略（生产实践）：
- **先精确（SHA256）**：毫秒级、零误判。
- **再感知（pHash）**：捕获压缩质量变化等"几乎相同"素材。
- **两者结合兜底**：策略是"精确命中或用感知相似度 > 阈值"即判重复并返回已有 creativeID，避免重复消耗审核。

#### 2.8.2 审核队列调度器

审核是异步耗时过程，生产系统用队列 + 状态机推进，避免同步阻塞：

```go
package creative

import (
	"sync"
	"time"
)

// ReviewJob 审核任务
type ReviewJob struct {
	CreativeID string
	Priority   int
	Submitted  time.Time
	Tries      int
}

// ReviewScheduler 审核队列调度器
type ReviewScheduler struct {
	mu      sync.Mutex
	queue   []*ReviewJob   // 简单 FIFO + 优先级
	results chan ApprovalResult
}

type ApprovalResult struct {
	CreativeID string
	State      ApprovalState
	Reasons    []ApprovalReason
	ReviewedAt time.Time
}

func NewReviewScheduler(buffer int) *ReviewScheduler {
	return &ReviewScheduler{
		queue:   make([]*ReviewJob, 0),
		results: make(chan ApprovalResult, buffer),
	}
}

// Enqueue 入队并触发轮询
func (s *ReviewScheduler) Enqueue(creativeID string, priority int) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.queue = append(s.queue, &ReviewJob{
		CreativeID: creativeID,
		Priority:   priority,
		Submitted:  time.Now(),
	})
}

// PollOnce 单次轮询队首任务（真实实现调用 DV360 dv360_get_creative_approval）
func (s *ReviewScheduler) PollOnce(pollFn func(id string) ApprovalResult) {
	s.mu.Lock()
	if len(s.queue) == 0 {
		s.mu.Unlock()
		return
	}
	job := s.queue[0]
	s.queue = s.queue[1:]
	s.mu.Unlock()

	res := pollFn(job.CreativeID)
	s.results <- res // 把结果投递给消费方（如状态机/通知）
}

// Results 返回审核结果通道供消费方读取
func (s *ReviewScheduler) Results() <-chan ApprovalResult {
	return s.results
}
```

调度器要点：
- **优先级**：高优先（品牌战役）任务先轮询，避免小任务阻塞大任务。
- **重试**：PENDING 长时间未回调用指数退避重试。
- **解耦**：提交（Enqueue）与消费（Results channel）分离，可并发处理大量创意而不互相阻塞。

#### 2.8.3 模板渲染/批量生成引擎

把"模板 + 变量"实时渲染成具体创意，是批量生产的高频动作：

```go
package creative

import (
	"bytes"
	"fmt"
	"html/template"
	"sort"
	"strings"
)

// CreativeTemplate 模板对象
type CreativeTemplate struct {
	ID        string
	Body      string // index.html 的模板文本，含 {{.xxx}} 占位符
	Variables []string
}

// RenderResult 渲染结果
type RenderResult struct {
	CreativeID string
	HTML       string
	Variables  map[string]string
	SizeBytes  int
}

// Renderer 模板渲染引擎
type Renderer struct {
	templates map[string]*CreativeTemplate
}

func NewRenderer() *Renderer {
	return &Renderer{templates: make(map[string]*CreativeTemplate)}
}

func (r *Renderer) AddTemplate(t *CreativeTemplate) {
	r.templates[t.ID] = t
}

// Render 注入变量并渲染 HTML，校验体积
func (r *Renderer) Render(tplID string, values map[string]string,
	creativeID string, limit int) (*RenderResult, error) {
	t, ok := r.templates[tplID]
	if !ok {
		return nil, fmt.Errorf("template %q not found", tplID)
	}

	// 转成 html/template 可用的数据
	data := make(map[string]any, len(values))
	for k, v := range values {
		data[k] = v
	}

	var buf bytes.Buffer
	tmpl, err := template.New("creative").Parse(t.Body)
	if err != nil {
		return nil, fmt.Errorf("parse template: %w", err)
	}
	if err := tmpl.Execute(&buf, data); err != nil {
		return nil, fmt.Errorf("render template: %w", err)
	}

	if buf.Len() > limit {
		return nil, fmt.Errorf("rendered HTML %d bytes > limit %d", buf.Len(), limit)
	}

	return &RenderResult{
		CreativeID: creativeID,
		HTML:       buf.String(),
		Variables:  values,
		SizeBytes:  buf.Len(),
	}, nil
}

// BatchRender 批量渲染多组变量
func (r *Renderer) BatchRender(tplID string, configs []map[string]string,
	limit int) ([]*RenderResult, error) {
	var out []*RenderResult
	for i, cfg := range configs {
		id := fmt.Sprintf("cr_%s_%d", tplID, i)
		res, err := r.Render(tplID, cfg, id, limit)
		if err != nil {
			return out, err
		}
		out = append(out, res)
	}
	return out, nil
}

// VariableKeys 返回模板变量列表（按名称排序，便于对齐 feed 字段）
func (t *CreativeTemplate) VariableKeys() []string {
	out := append([]string(nil), t.Variables...)
	sort.Strings(out)
	return out
}

// InlineConfig 用字符串模板构造一个简单模板
func InlineConfig(bodyTemplate string, vars []string) *CreativeTemplate {
	return &CreativeTemplate{
		ID:        "inline",
		Body:      bodyTemplate,
		Variables: vars,
	}
}
```

模板渲染引擎要点：
- **体积闸门**：渲染结果超限立即报错，避免把超体积创意提交审核。
- **变量对齐**：用 `VariableKeys()` 与 feed 字段校验一致（DCO 场景关键）。
- **批量循环**：`BatchRender` 一行生成 N 个创意实例，配合 `dv360_create_creative_from_template` 提交。

这三段 Go 代码（去重、审核队列、模板渲染）拼起来，就是一套可运行的创意资管系统基层。把它们接到 DV360 API（`dv360_create_creative` / `dv360_get_creative_approval` / `dv360_create_creative_from_template` / `dv360_list_creative_templates`）即可形成完整闭环。

---

## 三、生产环境实战

### 3.1 批量创意上传案例（千级创意流水线）

#### 3.1.1 场景还原

一家电商品牌要在"双十一"前完成 **1200 个创意** 的批量上传：600 个静态横幅（6 套素材 × 5 尺寸 × 20 个 SKU）+ 600 个模板化创意。手工上传不可行，必须走程序化流水线。

```
本地素材目录
├── banner/
│   ├── theme_1/{300x250,728x90,320x50,...}
│   ├── theme_2/...
│   └── theme_6/...
├── templates/
│   └── promo_html5_300x250.html
├── catalog.csv（1200 行：sku,title,price,image,url）
└── build_config.json（命名规则/映射）
        │
        ▼
  流水线脚本（Python）
   ├── ① 扫描素材 → 本地校验（尺寸/体积/编码）
   ├── ② 构造 Creative 元数据
   ├── ③ 去重（SHA256）→ 跳过重复
   ├── ④ 限速创建（dv360_create_creative）
   ├── ⑤ 轮询审核（dv360_get_creative_approval）
   ├── ⑥ 收集 APPROVED 清单
   └── ⑦ 挂接 Line Item（dv360_update_line_item）
```

#### 3.1.2 流水线 Python 主控

```python
import csv
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed


class CreativePipeline:
    """
    批量创意上传流水线。

    adapter 期望具备（脚本层方法）：
      - dv360_list_creatives(advertiser_id, line_item_id)
      - dv360_create_creative(advertiser_id, name, type=..., media_file=...)
      - dv360_get_creative_approval(advertiser_id, creative_id)
    """

    def __init__(self, adapter, advertiser_id: str,
                 line_item_id: str, dry_run: bool = True):
        self.adapter = adapter
        self.advertiser_id = advertiser_id
        self.line_item_id = line_item_id
        self.dry_run = dry_run

    def load_catalog(self, path: str):
        rows = []
        with open(path, newline='', encoding='utf-8') as f:
            for r in csv.DictReader(f):
                rows.append(r)
        return rows

    def validate_local(self, media_file: str):
        """本地规格校验：体积上限 + 扩展名。生产应并入 HTML5ZipValidator / video probe。"""
        if not os.path.exists(media_file):
            return False, "文件不存在"
        size = os.path.getsize(media_file)
        if size > 240 * 1024 and not media_file.endswith(('.mp4', '.mov')):
            return False, f"体积超限 {size}"
        if media_file.lower().endswith(('.zip', '.html')):
            # 此处接入 2.1 节的 HTML5ZipValidator
            pass
        return True, "ok"

    def create_one(self, row: dict, base_dir: str):
        name = row['name']
        media = os.path.join(base_dir, row['media'])
        ok, msg = self.validate_local(media)
        if not ok:
            return {'name': name, 'status': 'rejected_local', 'msg': msg}

        if self.dry_run:
            return {'name': name, 'status': 'dry_run',
                    'creative_id': None, 'msg': f"would create {media}"}

        try:
            creative = self.adapter.dv360_create_creative(
                advertiser_id=self.advertiser_id,
                name=name,
                type=row.get('type', 'BANNER_AD'),
                media_file=media,
            )
            return {'name': name, 'status': 'created',
                    'creative_id': creative.get('creativeId'),
                    'msg': ''}
        except Exception as e:
            return {'name': name, 'status': 'error',
                    'creative_id': None, 'msg': str(e)}

    def run(self, catalog_path: str, base_dir: str,
            workers: int = 4, rate_limit_per_sec: int = 2):
        """并行 + 限速执行批量创建"""
        rows = self.load_catalog(catalog_path)
        results = []
        throttle = 1.0 / max(rate_limit_per_sec, 1)
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(self.create_one, r, base_dir): r for r in rows}
            for fut in as_completed(futs):
                res = fut.result()
                results.append(res)
                time.sleep(throttle)  # 简易限速，避免触发配额

        summary = {
            'total': len(rows),
            'created': sum(1 for r in results if r['status'] == 'created'),
            'dry_run': sum(1 for r in results if r['status'] == 'dry_run'),
            'local_rejected': sum(1 for r in results if r['status'] == 'rejected_local'),
            'error': sum(1 for r in results if r['status'] == 'error'),
        }
        return summary, results

    def await_approval(self, results, timeout=1800, interval=60):
        """轮询所有已创建创意的审核结果，返回 APPROVED 清单"""
        approved = []
        deadline = time.time() + timeout
        pending = [r for r in results if r.get('creative_id')]
        while pending and time.time() < deadline:
            still = []
            for r in pending:
                ap = self.adapter.dv360_get_creative_approval(
                    advertiser_id=self.advertiser_id,
                    creative_id=r['creative_id'])
                st = ap.get('status')
                if st == 'APPROVED':
                    r['approval'] = 'APPROVED'
                    approved.append(r)
                elif st == 'DISAPPROVED':
                    r['approval'] = 'DISAPPROVED'
                else:
                    still.append(r)  # 仍 PENDING
            pending = still
            time.sleep(interval)
        for r in pending:
            r['approval'] = 'TIMEOUT'
        return approved

    def attach_to_line_item(self, approved_ids):
        """把 APPROVED 创意挂到 Line Item（real 场景调 dv360_update_line_item）"""
        return self.adapter.dv360_update_line_item(
            advertiser_id=self.advertiser_id,
            line_item_id=self.line_item_id,
            creative_ids=approved_ids,
        )

    def execute(self, catalog_path, base_dir, attach=True):
        summary, results = self.run(catalog_path, base_dir)
        print(f"批量上传汇总: {summary}")
        approved = self.await_approval(results)
        print(f"审核通过 {len(approved)} 个")
        if attach and approved:
            ids = [r['creative_id'] for r in approved]
            self.attach_to_line_item(ids)
            print(f"已挂接 {len(ids)} 个创意到 Line Item")
        return summary


if __name__ == "__main__":
    # 这里 adapter 用真实 API 客户端替换占位
    adapter = None  # 请替换为封装了 dv360_* 方法的客户端
    pipeline = CreativePipeline(adapter, advertiser_id="123456",
                                line_item_id="7891011", dry_run=True)
    pipeline.execute("catalog.csv", base_dir="/data/creatives")
```

#### 3.1.3 批量上传的关键经验

1. **先 dry_run 全量跑一遍**：校验 + 预览，确认命名与素材映射无错再真跑。
2. **本地规格校验前置**：把审核会被拒的问题（体积/编码/缺 index.html）在本地拦截，省下大量"上传→被拒→重传"的往返。
3. **限速与重试**：批量调用要控制并发与频率，遇到 `429 Quota exceeded` 退避重试。
4. **分批挂接**：1200 个创意一次挂进一个 Line Item 可能过于庞大，按素材族分批，便于定位与 A/B 分组。
5. **审核异步化**：创建后立即轮询审核是低效的，应把"创建队列"与"审核轮询"异步解耦。

---

### 3.2 Template 批量生产创意实战

#### 3.2.1 典型场景

品牌要做 40 个不同城市的促销创意，差异仅在"城市名 + 门店地址 + 专属落地页"，其余（尺寸、母版、品牌元素）完全一致。这正是模板化的理想场景：**写一个模板，循环 40 次**。

```
模板：city_promo_300x250.html
  ┌─────────────────────────────┐
  │   [LOGO]                    │
  │   {city} 限定促销             │  ← city 变量
  │   到店 {address} 享 {offer}   │  ← address / offer 变量
  │   [立即前往]  → {landing}    │  ← landing 变量
  └─────────────────────────────┘
  宽度/高度/背景图也由变量控制

40 行配置（CSV）:
  city    address        offer      landing
  上海     南京路1号       首单立减    https://sh.brand.com
  北京     中关村2号       满300减50   https://bj.brand.com
  ...（共 40 行）
```

#### 3.2.2 模板批量生产脚本

```python
import csv
from typing import List, Dict


def load_template_configs(path: str) -> List[Dict]:
    rows = []
    with open(path, newline='', encoding='utf-8') as f:
        for r in csv.DictReader(f):
            rows.append(r)
    return rows


def validate_variable_coverage(configs: List[Dict], required: List[str]) -> List[str]:
    """校验每行配置是否覆盖模板所有必填变量，缺失提前报错"""
    missing_rows = []
    for i, row in enumerate(configs):
        miss = [k for k in required if row.get(k) in (None, '')]
        if miss:
            missing_rows.append({'row': i, 'missing': miss})
    return missing_rows


def batch_from_template(adapter, advertiser_id: str, template_id: str,
                        configs: List[Dict],
                        template_vars: List[str]) -> List[Dict]:
    """
    基于单个模板 + 多行配置批量创建创意。
    对应脚本方法 dv360_create_creative_from_template(template_id, ...)
    """
    # 校验必填变量覆盖
    missing = validate_variable_coverage(configs, template_vars)
    if missing:
        raise ValueError(f"以下配置缺少必填模板变量: {missing}")

    results = []
    for cfg in configs:
        name = f"city_{cfg['city']}_300x250"
        # 构建 creativeVariables，只传模板声明的变量
        vars_payload = {k: v for k, v in cfg.items() if k in template_vars}
        resp = adapter.dv360_create_creative_from_template(
            template_id,
            advertiser_id=advertiser_id,
            name=name,
            creative_variables=vars_payload,
        )
        results.append({'name': name, 'vars': vars_payload, 'result': resp})
    return results
```

#### 3.2.3 模板生产的坑与对策

| 坑 | 现象 | 对策 |
|----|------|------|
| 变量名不匹配 | 模板渲染空白 | 用模板声明变量集过滤配置列 |
| 变量类型填错 | 创建报错 | 按 NUMBER/TEXT/URL 强校验 |
| 模板本身被拒 | 所有实例全 PENDING/拒绝 | 先做 1 个样本验证模板过审 |
| 模板尺寸与库存不符 | fill 率低 | 模板宽高匹配主流库存 |
| 定期刷新 | 城市/价格过期 | 定时重建或更新 feed |

---

### 3.3 A/B 测试设计实战（样本量 / 并行 / 显著性）

#### 3.3.1 一个完整 A/B 测试案例

**目标**：验证"HTML5 互动创意"是否优于"静态横幅"，组内 3 个变体。

```
实验设计
├── 对照组 A：静态 300x250（现状）
├── 试验组 B：HTML5 300x250 基础互动
├── 试验组 C：HTML5 300x250 + 滚动吸顶 CTA
├── 同一 Line Item、RANDOM 轮换、等预算
├── 主指标：CTR；次指标：CVR
└── 观察期：14 天（含两个周末）

样本量估算（前文公式）
├── 假设基础 CTR 1.2%，欲检测 +25%
├── n ≈ 每组 ~110 万展示
└── 14 天内若单组展示不足，延长窗口
```

执行步骤：

```
① 用样本量计算器估算所需展示与天数
② 建 Line Item，RANDOM 轮换挂 A/B/C
③ 统一定向与预算（消除外部干扰）
④ 实时监控各创意展示量是否均衡
⑤ 满样本后跑 z 检验 / 卡方
⑥ 判定胜者 → 扩量；败者降权或下线
```

#### 3.3.2 并行与串行

- **并行**（好）：A/B/C 同时在同一 Line Item 内跑，时间窗口完全一致，消除时段/季节偏差。
- **串行**（差）：先跑 A 再跑 B，环境变化（旺季、改价、竞品）会污染对比。

DV360 的 `RANDOM` 轮换天然支持并行无偏测试，应优先采用。

#### 3.3.3 显著性判断的 Python 检验

```python
from scipy import stats

def chi2_test_for_creatives(groups):
    """
    groups: list of (clicks, impressions)，做卡方独立性检验，
    判断各组 CTR 是否显著不同。
    """
    import numpy as np
    table = np.array([[c, i - c] for c, i in groups])
    chi2, p, dof, expected = stats.chi2_contingency(table)
    return chi2, p


# 示例：A/B 两组
groups = [(1200, 100000), (1500, 100000)]  # (点击, 展示)
chi2, p = chi2_test_for_creatives(groups)
print(f"chi2={chi2:.2f}, p={p:.5f}, 显著={p < 0.05}")
```

#### 3.3.4 常见 A/B 测试错误

| 错误 | 后果 | 规避 |
|------|------|------|
| 样本不足就下结论 | 假阳性 | 满样本再判定 |
| 中途改条件 | 数据污染 | 冻结变体与预算 |
| 只看均值不看显著性 | 误导 | 做检验 |
| 多重比较不校正 | 假阳性膨胀 | 3 组+用 Bonferroni |
| 忽略周末偏差 | 周期失真 | 覆盖整周 |
| 观察后选指标 | 事后挑选 | 预登记主指标 |

---

### 3.4 踩坑经验合集（素材审核被拒 / 尺寸不符 / HTML5 zip / 视频规格 / 动态创意）

下面把本主题在生产中最常踩的坑，按"现象→根因→解决"整理成速查表。这些都以真实业务场景浓缩而来。

#### 3.4.1 素材审核被拒

| # | 现象 | 根因 | 解决 |
|---|------|------|------|
| 1 | HTML5 创意审批通过但上线白屏 | zip 内缺失资源 / 反斜杠路径 | 本地 VAT 校验 + 无网自测 |
| 2 | 静态图被拒"尺寸不符" | 上传尺寸 ≠ 声明尺寸 | 上传前读取图片真实尺寸 |
| 3 | 视频被拒"编码不支持" | 用了 HEVC/VP9 | ffmpeg 转 H.264 MP4 |
| 4 | 富媒体被拒"自动展开" | 悬停即全展开 | 改为用户点击触发 |
| 5 | 文案被拒"误导夸大" | 极限词/虚假承诺 | 文案合规审查 |
| 6 | 落地页被拒 | 跳转 404 或与广告无关 | 落地页可达性 + 一致性校验 |

#### 3.4.2 尺寸不符导致 fill 失败

尺寸不匹配是"创意不出量（fill 低）"的最直接原因之一：

```
坑：创意尺寸 = 970x250（大横幅）
库存里该 Ad Slot 主流是 300x250 / 728x90
→ 竞价系统只能投匹配尺寸库存 → fill 率骤降

对策：
├── 提供主流 IAB 尺寸的完整素材族（300x250 / 728x90 / 320x50 / 160x600）
├── 用模板/Rich Media 的"自适应"能力覆盖多尺寸
└── 用报表按尺寸维度观察哪个尺寸填充率高
```

#### 3.4.3 HTML5 zip 体积超限

```
现象：HTML5 创意审核被拒 "Exceeds file size limit"
根因：zip 内嵌了高分辨率背景图、字体、未压缩 JS 库

对策：
├── 图片转 WebP / 压缩（≤100KB/张）
├── 字体子集化（只打包用到的字形）
├── JS/CSS 压缩混淆
├── 移除调试代码与 sourcemap
└── 控制在 200KB 安全线内
```

#### 3.4.4 动态创意不生效

```
现象：DCO 创意始终只展示默认商品，不随用户变化
排查顺序：
① feed 是否最新？（旧价格/缺货）
② 模板变量名是否与 feed 字段名严格一致？
③ 模板本身是否过审？
④ 是否静态创意与动态冲突导致动态被忽略？
⑤ 选品逻辑是否命中（无行为数据时用兜底）？
```

#### 3.4.5 模板化失败

```
现象：dv360_create_creative_from_template 报错或渲染空白
排查：
① 模板变量类型：TEXT/NUMBER/URL 是否匹配配置值
② 必填变量是否缺失
③ 模板是否已过审
④ 变量值长度/枚举是否在模板约束内
```

#### 3.4.6 视频规格不达标

```
现象：视频创意填充率极低或审核被拒
根因：分辨率 <480p / 编码非 H.264 / 时长超限 / 码率与库存不匹配

对策：
├── 强制 ffprobe 校验后再上传
├── 提供多码率/多分辨率备选（配合 VAST MediaFiles）
└── 时长对齐主流库存（pre-roll 15-30s）
```

---

## 四、常见问题与排查

### 4.1 FAQ 总表

| # | 问题 | 一句话结论 | 详见 |
|---|------|-----------|------|
| 1 | 创意审核通过却不出量 | 未关联 ACTIVE 的 Line Item | 4.2 |
| 2 | 创意被 DISAPPROVED | 规格/政策/落地页/体验问题 | 4.3 |
| 3 | HTML5 上线白屏 | zip 结构/路径/依赖问题 | 4.4 |
| 4 | 动态创意不生效 | feed/变量名/模板/选品问题 | 4.5 |
| 5 | 模板化创建失败 | 变量类型/必填/模板未过审 | 4.6 |
| 6 | 视频填充率低 | 分辨率/编码/时长不达标 | 4.7 |
| 7 | 改了素材广告突然停投 | 改动触发重新审核（→PENDING） | 4.8 |
| 8 | A/B 测不显著 | 样本不足/污染/多重比较 | 4.9 |
| 9 | 上传报 429/配额 | 限速/退避重试 | 4.10 |
| 10 | 创意疲劳 CTR 下滑 | 轮换/调频控/补新素材 | 4.11 |

### 4.2 创意审核通过却不出量

| 排查项 | 说明 |
|--------|------|
| Line Item 状态 | 必须为 ACTIVE，否则不竞价 |
| 是否挂接 | 创意 id 必须在 LineItem.creativeIds |
| 库存匹配 | 创意尺寸是否存在于被投库存 |
| 业务量级 | 是否被其他创意"压制"（轮换被挤占） |
| 频次上限 | 若用户已看够频控则不展示 |
| 定向命中 | 目标受众是否与定向条件相交 |

**排查命令（脚本层）**：
```python
# 列出某 Line Item 下的所有创意
creatives = adapter.dv360_list_creatives(advertiser_id, line_item_id)
# 检查每个创意的审核状态与是否被挂接
for c in creatives:
    print(c['creativeId'], c.get('status'), c.get('approvalStatus'))
```

### 4.3 创意被 DISAPPROVED 排查清单

1. 调 `dv360_get_creative_approval` 读拒绝原因（reasons 数组）。
2. 按原因分类到"规格/政策/落地页/体验"。
3. 修复对应项（体积、编码、版权、关闭按钮等）。
4. 重新提交 → 回到 PENDING → 等待再次审核。
5. 多次被拒时，保留每次原因做趋势分析，反哺素材规范库。

### 4.4 HTML5 白屏排查

- 本地用无网环境直接打开解压后的 index.html，检查资源是否都加载。
- 检查 zip 内是否有 `\` 反斜杠路径或绝对路径。
- 确认依赖（jQuery/CDN）已打包进 zip。
- 检查是否用了浏览器禁用 API（如非沙箱 localStorage）。
- 确认 index.html 在 zip 根目录（不要在子目录）。

### 4.5 动态创意不生效排查

按 3.4.4 的顺序走：feed 新鲜度 → 字段名一致性 → 模板过审 → 静态/动态冲突 → 选品兜底。

### 4.6 模板化创建失败排查

- 用 `dv360_list_creative_templates` 拉模板变量定义与类型。
- 校验每个变量值与声明类型匹配。
- 确认必填变量均已提供。
- 确认模板本身状态可用（已审核）。
- 确认变量值长度/枚举在约束内。

### 4.7 视频填充率低排查

- `ffprobe` 看分辨率/时长/编码/码率。
- 低于 480p → 转码 720p+。
- 非 H.264 → 转 H.264。
- 时长过长 → 裁剪或确认库存接受。
- 提供多码率备选（VAST MediaFiles）。

### 4.8 改了素材广告突然停投

任何会影响审核的改动（换图、改尺寸、改落地页、改文案）都会把创意踢回 PENDING 重新审核。规避：
- 重大改动走"新创意"而非原地修改，保留原创意继续投放。
- 若必须原地改，预留审核时间窗。

### 4.9 A/B 测不显著

- 检查是否达到最小样本量。
- 确认测试条件冻结、未被污染。
- 用 z/卡方检验而非眼看均值。
- 多组时做多重比较校正。

### 4.10 上传报 429 / 配额

- 控制并发与每秒请求数。
- 指数退避重试。
- 拆分批量任务、错峰执行。

### 4.11 创意疲劳 CTR 下滑

- 轮换新鲜创意补充。
- 调整频率上限。
- 用 A/B 测试补充新变体。
- 冷启动暂停低效创意。

---

## 五、自测题

### Q1: DV360 中，为什么"创意已 APPROVED 却始终不出量"？请给出至少 3 种系统层面的原因。

<details>
<summary>查看答案</summary>

**答案：**

`APPROVED` 只代表通过审核，不代表能出量。常见原因：
1. **未挂接 Line Item**：创意 id 不在任何 ACTIVE 的 LineItem.creativeIds 里，平台不会为之竞价。
2. **Line Item 自身未 ACTIVE**：即使创意挂接，投放单元暂停/预算为 0 也不会出量。
3. **库存尺寸不匹配**：创意尺寸在该库存中没有对应 Ad Slot（如 970×250 却只有 300×250 库存），导致填充率骤降。
4. **频次上限已满**：目标用户已被频控拦截，看不到该创意。
5. **定向零命中**：创意配套的定向条件与可触达受众无交集。

**排查**：先 `dv360_list_creatives` 确认挂接与审批状态，再检查 Line Item 状态、库存尺寸匹配与频控。

</details>

### Q2: 一个 HTML5 创意 zip 包被 DV360 审核拒因"缺少 index.html"。请说明 DV360 HTML5 规范对 zip 结构的最低要求，并给出一个在 Python 层提前拦截该问题的校验逻辑。

<details>
<summary>查看答案</summary>

**答案：**

DV360 HTML5 zip 最低要求：
1. **必须包含根目录下的 `index.html`**，作为创意渲染入口。
2. 所有资源路径用相对路径、统一 `/` 分隔（拒绝 `\` 与绝对路径）。
3. 压缩后体积有上限（实战安全线约 200~250KB）。
4. 依赖必须打包进 zip，不得依赖外网 CDN。

Python 层提前拦截：
```python
import zipfile
with zipfile.ZipFile(path) as zf:
    names = zf.namelist()
    if 'index.html' not in names:
        raise ValueError("缺少 index.html 入口文件")
    for n in names:
        if '\\' in n or n.startswith('/'):
            raise ValueError(f"非法路径: {n}")
```
把校验放在上传前，可省下"上传→被拒→重传"的往返。

</details>

### Q3: 你要在 DV360 上比较"静态横幅"与"HTML5 互动创意"的 CTR，基础 CTR 约 1%，希望检测 +25% 的提升。请说明应如何设计这个 A/B 测试（样本量、并行性、统计判断）。

<details>
<summary>查看答案</summary>

**答案：**

设计要点：
1. **样本量**：用公式或脚本计算。基础 CTR 1%、提升 25% 时，每组需约 40~50 万展示（具体用 `min_sample_size_ratio` 估算）。样本不足不能下结论。
2. **并行**：两变体放同一 Line Item 用 `RANDOM` 轮换，同一预算/定向/时间窗口并行跑，消除时段偏差。
3. **统计判断**：满样本后用 z 检验或卡方检验计算 p 值，`p < 0.05` 判显著；不要只看均值差。
4. **预登记**：测试前选定 CTR 为主指标，冻结变体与预算，覆盖完整一周。

</details>

### Q4: DCO 动态创意"始终只展示默认商品、不随用户变化"，请按优先级列出排查步骤。

<details>
<summary>查看答案</summary>

**答案：**

按以下顺序排查：
1. **feed 新鲜度**：数据源是否最新、是否有缺失商品/旧价格/缺货。
2. **字段名一致性**：模板变量名是否与 feed 字段名**严格一致**（大小写/空格不过滤）。
3. **模板过审**：DCO 模板本身是否已 APPROVED。
4. **静态/动态冲突**：同一 Line Item 内是否静态创意压制动态创意。
5. **选品兜底**：无用户行为数据时是否命中默认/热门商品兜底规则。
6. **刷新时机**：feed 是否定时同步，避免过期数据。

</details>

### Q5: 一个模板变量在创建创意时报"类型不匹配"。请说明 Creative Template 常见变量类型，以及上传前如何在脚本层校验。

<details>
<summary>查看答案</summary>

**答案：**

模板常见变量类型：`NUMBER` / `TEXT` / `ASSET` / `URL` / `COLOR` / `BOOLEAN` / `ENUM`。

脚本层校验思路：
```python
def coerce_variable(key, vtype, raw):
    if vtype == 'NUMBER':
        return str(int(raw))          # 非数字会抛异常
    if vtype == 'URL':
        if not str(raw).startswith(('http://', 'https://')):
            raise ValueError(f"{key} 期望 URL")
        return raw
    return raw                          # TEXT/ASSET/COLOR/BOOLEAN/ENUM 直接透传
```
在调用 `dv360_create_creative_from_template` 前遍历模板变量定义逐项强校验，不匹配立即报错，避免创建请求失败或渲染空白。

</details>

---

## 附：本主题与既有文档的互补关系

| 维度 | dv360-creative-brand-safety-deep | 本文档 |
|------|----------------------------------|--------|
| 创意格式通用规格 | 有（概览表） | 深度展开（HTML5 zip / 视频 / 富媒体） |
| DCO 原理 | 有（工作流级） | 深度（feed 字段 / 选品 / 排查） |
| A/B 测试 | 有（框架 + 分析） | 深度（样本量公式 / z/卡方检验 / Go 分流） |
| 审核状态机 | 未展开 | 深度（APPROVED/DISAPPROVED/PENDING 流转 + Go 实现） |
| 模板体系 | 未展开 | 深度（变量模型 / API / 批量生产） |
| 批量管理 | 未展开 | 深度（千级流水线 / 去重 / 限速） |

本文档定位为 DV360 创意管理系统中"富媒体 / HTML5 / 视频 / 模板 / 审核 / 批量 / A/B"的**纵深专项**，与既有"品牌安全 + 创意概览"文档形成互补而非重复。
