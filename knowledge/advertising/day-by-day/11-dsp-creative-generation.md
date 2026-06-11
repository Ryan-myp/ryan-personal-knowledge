# DSP 创意生成系统：从创意工厂到 AI 动态创意

> 创建日期: 2026-06-10
> 作者: Ryan
> 定位: 资深专家级 — 创意生成与优化

---

## 第一部分：创意工厂 (Creative Factory) 架构

### 1.1 创意工厂概述

```
┌──────────────────────────────────────────────────────────────┐
│              创意工厂架构                                       │
│                                                              │
│  创意工厂: 自动化生成、管理、投放广告的创意资产                  │
│                                                              │
│  核心能力:                                                   │
│  ├── 创意库管理 (Creative Library) — 存储所有创意资产           │
│  ├── 智能创意组合 (Smart Composition) — 自动组合元素            │
│  ├── 创意模板 (Templates) — 预定义布局/风格                   │
│  ├── 自动化生成 (Auto-Gen) — AI 生成素材                     │
│  └─ 创意轮替 (Rotation) — 最优创意自动分配                      │
│                                                              │
│  创意类型:                                                   │
│  ├── Banner (横幅): 300x250, 728x90, 160x600, 320x50       │
│  ├── Video (视频): 15s/30s/60s, 16:9/1:1/9:16               │
│  ├── Native (原生): 标题/描述/图片/CTA                        │
│  ├── Collage (拼贴): 多图片组合                               │
│  └─ Carousel (轮播): 多图滑动                                 │
│                                                              │
│  创意流程:                                                   │
│  1. 上传素材 → 2. 提取元数据 → 3. 分类打标 → 4. 组合生成 → 5. 审核 → 6. 投放  │
└──────────────────────────────────────────────────────────────┘
```

### 1.2 创意模板系统

```
创意模板: 预定义布局，快速生成广告

┌──────────────────────────────────────────────────────────────┐
│              模板系统                                          │
│                                                              │
│  Template Schema:                                            │
│  ┌───────────────────────────────────────────────────────┐   │
│  │  {                                                      │   │
│  │    "template_id": "tmpl_001",                         │   │
│  │    "name": "Product Highlight",                       │   │
│  │    "format": "banner",                                 │   │
│  │    "sizes": [300x250, 728x90, 320x50],               │   │
│  │    "layout": {                                        │   │
│  │      "background": {                                  │   │
│  │        "type": "gradient",                            │   │
│  │        "colors": ["#1a73e8", "#4285f4"],              │   │
│  │        "direction": "horizontal"                      │   │
│  │      },                                               │   │
│  │      "zones": [                                       │   │
│  │        {                                              │   │
│  │          "zone_id": "image",                          │   │
│  │          "type": "image",                             │   │
│  │          "x": 0.05, "y": 0.1,                        │   │
│  │          "w": 0.4, "h": 0.8,                         │   │
│  │          "aspect_ratio": "1:1",                       │   │
│  │          "corner_radius": 8                            │   │
│  │        },                                             │   │
│  │        {                                              │   │
│  │          "zone_id": "headline",                       │   │
│  │          "type": "text",                              │   │
│  │          "x": 0.5, "y": 0.1,                         │   │
│  │          "w": 0.45, "h": 0.3,                        │   │
│  │          "max_lines": 2,                              │   │
│  │          "font_size": 18,                             │   │
│  │          "font_weight": "bold",                       │   │
│  │          "color": "#ffffff",                          │   │
│  │          "text_align": "left"                         │   │
│  │        },                                             │   │
│  │        {                                              │   │
│  │          "zone_id": "price",                          │   │
│  │          "type": "text",                              │   │
│  │          "x": 0.5, "y": 0.45,                        │   │
│  │          "w": 0.45, "h": 0.15,                       │   │
│  │          "font_size": 14,                             │   │
│  │          "color": "#ff6b35"                           │   │
│  │        },                                             │   │
│  │        {                                              │   │
│  │          "zone_id": "cta",                            │   │
│  │          "type": "button",                            │   │
│  │          "x": 0.5, "y": 0.7,                         │   │
│  │          "w": 0.45, "h": 0.15,                       │   │
│  │          "text": "Shop Now",                          │   │
│  │          "bg_color": "#ff6b35",                      │   │
│  │          "text_color": "#ffffff",                     │   │
│  │          "corner_radius": 4                           │   │
│  │        }                                              │   │
│  │      ]                                                │   │
│  │    },                                                │   │
│  │    "variants": [                                      │   │
│  │      {                                                │   │
│  │        "name": "blue_theme",                          │   │
│  │        "replacements": {                              │   │
│  │          "background.colors": ["#1a73e8", "#4285f4"], │   │
│  │          "cta.bg_color": "#1a73e8",                  │   │
│  │          "cta.text_color": "#ffffff"                  │   │
│  │        }                                              │   │
│  │      },                                               │   │
│  │      {                                                │   │
│  │        "name": "red_theme",                           │   │
│  │        "replacements": {                              │   │
│  │          "background.colors": ["#d32f2f", "#f44336"], │   │
│  │          "cta.bg_color": "#d32f2f",                  │   │
│  │          "cta.text_color": "#ffffff"                  │   │
│  │        }                                              │   │
│  │      }                                                │   │
│  │    ]                                                │   │
│  │  }                                                    │   │
│  └───────────────────────────────────────────────────────┘   │
│                                                              │
│  渲染引擎 (Renderer):                                        │
│  ├── Canvas (Web/Mobile):                                   │
│  │   └─ 2D Canvas API → 生成 PNG/JPEG/SVG                  │
│  ├── HTML/CSS (Display Ads):                                │
│  │   └─ 标准 HTML5 广告格式                                │
│  ├── Video Render (FFmpeg):                                 │
│  │   └─ FFmpeg/OpenGL → 生成 MP4 (H.264/HEVC)             │
│  └─ Native Ad (SDK):                                       │
│      └─ JSON → UI 组件渲染                                  │
└──────────────────────────────────────────────────────────────┘
```

---

## 第二部分：动态创意优化 (DCO) 深度

### 2.1 DCO 架构

```
动态创意优化 (Dynamic Creative Optimization):

┌──────────────────────────────────────────────────────────────┐
│              DCO 流程                                        │
│                                                              │
│  核心思想: 根据实时上下文，动态选择/生成最佳创意               │
│                                                              │
│  输入:                                                       │
│  ├── User Profile: 用户画像 (兴趣/行为/上下文)               │
│  ├── Context: 上下文 (位置/设备/时间/页面)                    │
│  ├── Campaign Goals: 广告目标 (CTR/CVR/CPA/ROAS)            │
│  └─ Creative Pool: 创意库 (图片/文案/CTA/视频)               │
│                                                              │
│  DCO 引擎:                                                   │
│  ├── Step 1: 特征提取 (~1ms)                                 │
│  │   └─ 用户画像 + 上下文 + 广告位特征                       │
│  ├── Step 2: 创意候选 (~5ms)                                 │
│  │   └─ 从创意库中筛选匹配的创意                              │
│  ├── Step 3: 创意评分 (~10ms)                                │
│  │   └─ 预测每个创意组合的 pCTR/pCVR                         │
│  ├── Step 4: 最优创意选择 (~1ms)                             │
│  │   └─ 选择期望价值最大的创意                                │
│  └─ Step 5: 实时渲染 (~3ms)                                  │
│      └─ 动态生成创意 (文本/图片/CTA)                         │
│                                                              │
│  创意元素池 (Creative Elements):                             │
│  ├── 图片 (Images):                                         │
│  │   ├── 产品图片 (Product Photos)                           │
│  │   ├── 场景图片 (Lifestyle Photos)                        │
│  │   ├── 促销图片 (Sale/Promo Graphics)                    │
│  │   └─ 用户生成内容 (UGC Photos)                           │
│  ├── 文案 (Copy):                                           │
│  │   ├── 标题 (Headlines): 5-10 个变体                      │
│  │   ├── 描述 (Descriptions): 5-10 个变体                   │
│  │   └─ CTA: 5 个变体 (Buy Now/Shop/Learn More)            │
│  ├── 颜色 (Colors):                                        │
│  │   └─ 品牌色系 + 季节性色系                                │
│  ├── 字体 (Fonts):                                         │
│  │   └─ 品牌字体 + 备选字体                                 │
│  └─ 视频 (Video):                                          │
│      ├── 片头 (Intro): 3 种变体                              │
│      ├── 产品展示 (Demo): 2 种变体                           │
│      └─ CTA 结尾 (Outro): 3 种变体                          │
│                                                              │
│  组合空间:                                                   │
│  ├── 如果每个元素有 5 个选项，6 个元素                        │
│  │   └─ 5^6 = 15,625 种组合                                  │
│  └─ 手动测试: 不可能，需要 DCO 自动优化                      │
└──────────────────────────────────────────────────────────────┘
```

### 2.2 DCO 核心算法

```
DCO 核心算法: 创意评分与选择

┌──────────────────────────────────────────────────────────────┐
│              创意评分模型                                      │
│                                                              │
│  方法 1: 因式分解 (Factorization)                             │
│  ├── 假设: Creative Value = Σ Element_Value(e)                │
│  ├── 每个元素有独立的价值权重                                  │
│  ├── 价值 = 基于历史点击/转化数据学习                           │
│  └─ 复杂度: O(N) — 极快                                       │
│                                                              │
│  实现:                                                       │
│  ┌───────────────────────────────────────────────────────┐   │
│  │  Element Value Table:                                  │   │
│  │  ┌───────────────────────────────────────────────┐    │   │
│  │  │  Element      | Type    | Value (CTR Score)  │    │   │
│  │  │  img_01       | image   | 0.085              │    │   │
│  │  │  img_02       | image   | 0.072              │    │   │
│  │  │  img_03       | image   | 0.063              │    │   │
│  │  │  head_01      | headline| 0.091              │    │   │
│  │  │  head_02      | headline| 0.067              │    │   │
│  │  │  cta_01       | cta     | 0.078              │    │   │
│  │  │  cta_02       | cta     | 0.055              │    │   │
│  │  │  ...                                        │    │   │
│  │  └───────────────────────────────────────────────┘    │   │
│  │                                                      │   │
│  │  Score(Creative) = Σ Element_Value(e)                 │   │
│  │                                                      │   │
│  │  最佳创意 = argmax_creative Σ Element_Value(e)        │   │
│  └───────────────────────────────────────────────────────┘   │
│                                                              │
│  方法 2: 交互模型 (Interaction Model)                        │
│  ├── 考虑元素间交互 (非加和)                                 │
│  ├── 模型: DeepFM / Attention 模型                          │
│  ├── 学习元素组合的点击概率                                   │
│  └─ 复杂度: O(N × M) — 较慢但更准确                         │
│                                                              │
│  方法 3: 强化学习 (Reinforcement Learning)                  │
│  ├── 每个创意组合是一个"动作"                                 │
│  ├── 点击/转化是奖励                                         │
│  ├── Thompson Sampling / UCB 选择最佳组合                    │
│  └─ 自适应优化                                              │
│                                                              │
│  实际使用:                                                   │
│  ├── Google Ads: Factorization + 实时学习                   │
│  ├── Facebook: Interaction Model (Deep Learning)           │
│  └─ TikTok: Reinforcement Learning                         │
└──────────────────────────────────────────────────────────────┘
```

### 2.3 DCO 代码实现

```python
"""
DCO (Dynamic Creative Optimization) 核心实现
"""

import numpy as np
import torch
import torch.nn as nn
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
import time


@dataclass
class CreativeElement:
    """创意元素"""
    element_id: str
    element_type: str  # image/headline/description/cta/color
    value: str  # 实际内容 (图片 URL/文案/颜色)
    ctr_score: float = 0.0  # 历史 CTR 分数
    cvr_score: float = 0.0  # 历史 CVR 分数
    impression_count: int = 0
    click_count: int = 0
    conversion_count: int = 0

    def update_stats(self):
        """更新统计"""
        if self.impression_count > 0:
            self.ctr_score = self.click_count / self.impression_count
        if self.click_count > 0:
            self.cvr_score = self.conversion_count / self.click_count


@dataclass
class CreativeCombination:
    """创意组合"""
    combination_id: str
    elements: Dict[str, CreativeElement]  # type → element
    score: float = 0.0
    impression_count: int = 0
    click_count: int = 0
    conversion_count: int = 0


class CreativeManager:
    """
    创意管理器 — 管理创意库、组合、评分
    """

    def __init__(self):
        # 创意库: type → {element_id → CreativeElement}
        self.creative_pool: Dict[str, Dict[str, CreativeElement]] = defaultdict(dict)
        # 创意组合缓存
        self.combination_cache: Dict[str, CreativeCombination] = {}
        # 元素权重 (交互模型)
        self.element_weights: Dict[str, float] = {}

    def add_creative(self, element: CreativeElement):
        """添加创意元素到库"""
        self.creative_pool[element.element_type][element.element_id] = element

    def get_candidates(
        self,
        ad_format: str,  # banner/video/native
        brand_id: str,
    ) -> List[CreativeElement]:
        """
        获取候选创意元素

        按品牌和格式筛选
        """
        candidates = {}

        if ad_format == 'banner':
            # Banner: image + headline + cta
            candidates['image'] = self._get_best_images(brand_id, top_k=3)
            candidates['headline'] = self._get_best_headlines(brand_id, top_k=3)
            candidates['cta'] = self._get_best_cta(brand_id, top_k=2)
        elif ad_format == 'video':
            # Video: intro + product_show + outro
            candidates['intro'] = self._get_intro_clips(brand_id, top_k=2)
            candidates['product_show'] = self._get_product_clips(brand_id, top_k=3)
            candidates['outro'] = self._get_outro_clips(brand_id, top_k=2)
        elif ad_format == 'native':
            # Native: image + headline + description + cta
            candidates['image'] = self._get_best_images(brand_id, top_k=3)
            candidates['headline'] = self._get_best_headlines(brand_id, top_k=3)
            candidates['description'] = self._get_best_descriptions(brand_id, top_k=3)
            candidates['cta'] = self._get_best_cta(brand_id, top_k=2)

        return candidates

    def compose_creative(
        self,
        candidates: Dict[str, List[CreativeElement]],
        user_context: Dict[str, float],
    ) -> CreativeCombination:
        """
        组合最佳创意

        方法: Factorization (快速)

        Args:
            candidates: 各类型的候选元素
            user_context: 用户上下文特征
        
        Returns:
            最佳创意组合
        """
        best_elements = {}
        total_score = 0.0
        
        for elem_type, elements in candidates.items():
            # 选择该类型中 score 最高的
            if elements:
                best = max(elements, key=lambda e: e.ctr_score)
                best_elements[elem_type] = best
                total_score += best.ctr_score
        
        combination_id = self._generate_combination_id(best_elements)
        
        return CreativeCombination(
            combination_id=combination_id,
            elements=best_elements,
            score=total_score,
        )
    
    def compose_with_interaction_model(
        self,
        candidates: Dict[str, List[CreativeElement]],
        user_context: Dict[str, float],
        model: nn.Module,
    ) -> CreativeCombination:
        """
        使用交互模型组合创意
        
        考虑元素间交互，更准确但更慢
        """
        best_score = -np.inf
        best_combination = None
        
        # 暴力搜索 (元素少时可行)
        element_lists = list(candidates.values())
        if not element_lists:
            return None
        
        # 如果组合空间大，使用 beam search
        if np.prod(len(el) for el in element_lists) > 1000:
            return self._beam_search(candidates, model, user_context, beam_size=10)
        
        # 暴力搜索
        import itertools
        for combo in itertools.product(*element_lists):
            score = self._interaction_score(combo, user_context, model)
            if score > best_score:
                best_score = score
                best_elements = {el.element_type: el for el in combo}
                best_combination = CreativeCombination(
                    combination_id=self._generate_combination_id(best_elements),
                    elements=best_elements,
                    score=score,
                )
        
        return best_combination
    
    def _interaction_score(
        self,
        elements: Tuple[CreativeElement, ...],
        user_context: Dict[str, float],
        model: nn.Module,
    ) -> float:
        """
        使用模型计算创意组合的交互分数
        
        特征: 元素 ID embedding + 用户上下文
        """
        # 构造输入
        elem_ids = [el.element_id for el in elements]
        input_features = self._encode_creative_combo(
            elem_ids, user_context
        )
        
        with torch.no_grad():
            score = model(input_features).item()
        
        return score
    
    def _beam_search(
        self,
        candidates: Dict[str, List[CreativeElement]],
        model: nn.Module,
        user_context: Dict[str, float],
        beam_size: int = 10,
    ) -> CreativeCombination:
        """
        Beam Search: 近似最优创意组合
        
        当组合空间太大时，使用 Beam Search 近似
        """
        element_types = list(candidates.keys())
        
        # 初始化: 第一个类型选择 top-K 候选
        beams = []
        for elem in candidates[element_types[0]]:
            beams.append([(element_types[0], elem)])
        
        # 按分数排序，取 top-K
        beams.sort(key=lambda b: b[0][1].ctr_score, reverse=True)
        beams = beams[:beam_size]
        
        # 迭代后续类型
        for elem_type in element_types[1:]:
            new_beams = []
            for beam in beams:
                for elem in candidates[elem_type]:
                    new_beam = beam + [(elem_type, elem)]
                    score = sum(e[1].ctr_score for e in new_beam)
                    new_beams.append((new_beam, score))
            
            new_beams.sort(key=lambda x: x[1], reverse=True)
            beams = [nb[0] for nb in new_beams[:beam_size]]
        
        # 选择最佳 beam
        best_beam = max(beams, key=lambda b: sum(e[1].ctr_score for e in b))
        best_elements = {t: e for t, e in best_beam}
        
        return CreativeCombination(
            combination_id=self._generate_combination_id(best_elements),
            elements=best_elements,
            score=sum(e.ctr_score for _, e in best_beam),
        )
    
    def record_impression(self, combination_id: str):
        """记录展示"""
        if combination_id in self.combination_cache:
            self.combination_cache[combination_id].impression_count += 1
    
    def record_click(self, combination_id: str):
        """记录点击"""
        if combination_id in self.combination_cache:
            combo = self.combination_cache[combination_id]
            combo.click_count += 1
            # 更新元素统计
            for elem in combo.elements.values():
                elem.click_count += 1
                elem.update_stats()
    
    def record_conversion(self, combination_id: str):
        """记录转化"""
        if combination_id in self.combination_cache:
            combo = self.combination_cache[combination_id]
            combo.conversion_count += 1
            for elem in combo.elements.values():
                elem.conversion_count += 1
                elem.update_stats()
    
    def _generate_combination_id(self, elements: Dict[str, CreativeElement]) -> str:
        """生成组合 ID"""
        parts = sorted(elements.values(), key=lambda e: e.element_id)
        return 'combo_' + '_'.join(e.element_id for e in parts)
    
    def _get_best_images(self, brand_id: str, top_k: int = 3) -> List[CreativeElement]:
        """获取最佳图片"""
        images = [
            e for e in self.creative_pool.get('image', {}).values()
            if e.element_type == 'image'
        ]
        return sorted(images, key=lambda e: e.ctr_score, reverse=True)[:top_k]
    
    def _get_best_headlines(self, brand_id: str, top_k: int = 3) -> List[CreativeElement]:
        """获取最佳标题"""
        headlines = [
            e for e in self.creative_pool.get('headline', {}).values()
        ]
        return sorted(headlines, key=lambda e: e.ctr_score, reverse=True)[:top_k]
    
    def _get_best_cta(self, brand_id: str, top_k: int = 2) -> List[CreativeElement]:
        """获取最佳 CTA"""
        ctas = [
            e for e in self.creative_pool.get('cta', {}).values()
        ]
        return sorted(ctas, key=lambda e: e.ctr_score, reverse=True)[:top_k]
    
    def _get_intro_clips(self, brand_id: str, top_k: int = 2) -> List[CreativeElement]:
        return [CreativeElement('intro_01', 'intro', 'url_01', 0.5)]
    
    def _get_product_clips(self, brand_id: str, top_k: int = 3) -> List[CreativeElement]:
        return [CreativeElement('prod_01', 'product', 'url_01', 0.5)]
    
    def _get_outro_clips(self, brand_id: str, top_k: int = 2) -> List[CreativeElement]:
        return [CreativeElement('outro_01', 'outro', 'url_01', 0.5)]
    
    def _get_best_descriptions(self, brand_id: str, top_k: int = 3) -> List[CreativeElement]:
        descs = [e for e in self.creative_pool.get('description', {}).values()]
        return sorted(descs, key=lambda e: e.ctr_score, reverse=True)[:top_k]
```

---

## 第三部分：AI 创意生成

### 3.1 AI 生成创意

```
AI 创意生成: 使用生成式 AI 自动创作广告素材

┌──────────────────────────────────────────────────────────────┐
│              AI 创意生成流程                                   │
│                                                              │
│  生成式 AI 模型:                                               │
│  ├── 图像生成: Stable Diffusion / DALL-E / Midjourney        │
│  ├── 文本生成: GPT-4 / Claude / LLaMA                        │
│  ├── 视频生成: Sora / Runway ML / Pika                       │
│  └─ 多模态: CLIP + Stable Diffusion                          │
│                                                              │
│  工作流程:                                                   │
│  ┌───────────────────────────────────────────────────────┐   │
│  │  1. 输入: 产品信息 + 品牌指南 + 广告目标                 │   │
│  │     ├── 产品图片 / 描述                                  │   │
│  │     ├── 品牌色彩 / 字体 / Logo                           │   │
│  │     ├── 广告目标 (CTR/CVR/品牌认知)                      │   │
│  │     └─ 目标受众画像                                      │   │
│  │                                                      │   │
│  │  2. 文案生成 (GPT-4):                                  │   │
│  │     ├── 生成 10 个标题变体                               │   │
│  │     ├── 生成 10 个描述变体                               │   │
│  │     └─ 生成 5 个 CTA 变体                              │   │
│  │                                                      │   │
│  │  3. 图片生成 (Stable Diffusion):                       │   │
│  │     ├── 产品背景生成 (去除背景 → 新场景)                 │   │
│  │     ├── A/B 测试: 5 种不同场景                          │   │
│  │     └─ 品牌一致性: 使用 LoRA 微调品牌风格                │   │
│  │                                                      │   │
│  │  4. 视频生成 (Runway ML):                              │   │
│  │     ├── 图片 → 视频 (动画化产品图片)                     │   │
│  │     ├── 文案 → 视频 (AI 生成演示视频)                   │   │
│  │     └─ 适配各平台尺寸 (9:16/1:1/16:9)                  │   │
│  │                                                      │   │
│  │  5. 组合与优化:                                        │   │
│  │     ├── 组合文案 + 图片 → 多个广告变体                   │   │
│  │     ├── DCO 评分 → 选择最优创意                         │   │
│  │     └─ 自动投放 → 收集反馈 → 迭代优化                  │   │
│  └───────────────────────────────────────────────────────┘   │
│                                                              │
│  品牌一致性控制:                                              │
│  ├── Color Lock: 强制使用品牌色                               │
│  ├── Font Lock: 强制使用品牌字体                              │
│  ├── Logo Placement: Logo 固定位置                           │
│  └─ Style LoRA: 微调模型保持品牌风格                         │
│                                                              │
│  合规检查:                                                   │
│  ├── 品牌安全: 不生成违规内容                                  │
│  ├── 版权: 确保生成内容无版权纠纷                              │
│  └─ 广告法规: 不生成误导性内容                                 │
└──────────────────────────────────────────────────────────────┘
```

### 3.2 AI 创意生成代码实现

```python
"""
AI 创意生成核心实现
"""

import os
import json
import time
import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum


class AdFormat(Enum):
    BANNER = "banner"
    VIDEO = "video"
    NATIVE = "native"
    CAROUSEL = "carousel"


class BrandSafetyLevel(Enum):
    SAFE = "safe"
    CAUTION = "caution"
    UNSAFE = "unsafe"


@dataclass
class BrandGuidelines:
    """品牌指南"""
    brand_id: str
    brand_name: str
    colors: List[str]  # ['#1a73e8', '#4285f4']
    fonts: List[str]   # ['Roboto', 'Open Sans']
    logo_url: str
    tone: str  # 'professional', 'casual', 'luxury'
    tagline: str
    min_contrast_ratio: float = 4.5  # WCAG 对比度


@dataclass
class ProductInfo:
    """产品信息"""
    product_id: str
    name: str
    description: str
    price: float
    category: str
    image_urls: List[str]  # 产品图片
    features: List[str]  # 产品特点
    benefits: List[str]  # 用户利益


@dataclass
class GeneratedCreative:
    """生成的创意"""
    creative_id: str
    format: AdFormat
    headline: str
    description: str
    cta: str
    image_url: str
    video_url: Optional[str] = None
    ctr_score: float = 0.0
    safety_score: float = 0.0
    brand_compliance: bool = True


class AICreativeGenerator:
    """
    AI 创意生成器
    
    使用 GPT-4 生成文案，Stable Diffusion 生成图片
    """
    
    def __init__(
        self,
        brand_guidelines: BrandGuidelines,
        openai_api_key: str,
        stable_diffusion_url: str,
        moderation_api_url: str,
    ):
        self.brand = brand_guidelines
        self.openai_key = openai_api_key
        self.sd_url = stable_diffusion_url
        self.moderation_url = moderation_api_url
        self.generated_creatives: List[GeneratedCreative] = []
    
    def generate_ad_creatives(
        self,
        product: ProductInfo,
        ad_format: AdFormat,
        num_variants: int = 5,
        target_audience: str = "general",
    ) -> List[GeneratedCreative]:
        """
        生成广告创意变体
        
        Args:
            product: 产品信息
            ad_format: 广告格式
            num_variants: 变体数量
            target_audience: 目标受众
        
        Returns:
            生成的创意列表
        """
        creatives = []
        
        # Step 1: 生成文案 (GPT-4)
        headlines = self._generate_headlines(product, num_variants, target_audience)
        descriptions = self._generate_descriptions(product, num_variants, target_audience)
        ctas = self._generate_ctas(product, min(num_variants, 3))
        
        # Step 2: 生成图片 (Stable Diffusion)
        image_urls = self._generate_images(product, num_variants, ad_format)
        
        # Step 3: 组合创意
        for i in range(min(num_variants, len(headlines), len(image_urls))):
            headline = headlines[i % len(headlines)]
            description = descriptions[i % len(descriptions)]
            cta = ctas[i % len(ctas)]
            image_url = image_urls[i % len(image_urls)]
            
            creative = GeneratedCreative(
                creative_id=f"ai_{product.product_id}_{i}",
                format=ad_format,
                headline=headline,
                description=description,
                cta=cta,
                image_url=image_url,
            )
            
            # Step 4: 品牌合规检查
            creative.brand_compliance = self._check_brand_compliance(creative)
            
            # Step 5: 品牌安全检查
            creative.safety_score = self._check_brand_safety(creative)
            
            # 仅保留合规创意
            if creative.brand_compliance and creative.safety_score > 0.7:
                creatives.append(creative)
        
        self.generated_creatives.extend(creatives)
        return creatives
    
    def _generate_headlines(
        self,
        product: ProductInfo,
        num_variants: int,
        target_audience: str,
    ) -> List[str]:
        """
        使用 GPT-4 生成标题
        
        提示词工程:
        ├── 品牌指南: 语气/颜色/风格
        ├── 产品信息: 特点/优势
        ├── 目标受众: 年龄/兴趣/痛点
        └─ 输出: num_variants 个标题
        """
        prompt = f"""
        Generate {num_variants} engaging headlines for an ad.
        
        Product: {product.name}
        Description: {product.description}
        Price: ${product.price}
        Features: {', '.join(product.features)}
        Benefits: {', '.join(product.benefits)}
        Category: {product.category}
        
        Brand Tone: {self.brand.tone}
        Brand Tagline: {self.brand.tagline}
        
        Target Audience: {target_audience}
        
        Requirements:
        - Each headline should be under 30 characters
        - Focus on {product.benefits[0] if product.benefits else 'value'}
        - Include a subtle call to action
        - Match {self.brand.tone} brand voice
        - Be different from each other
        
        Return ONLY a JSON array of strings, no other text.
        """
        
        # 调用 GPT-4 API (简化)
        headlines = self._call_gpt4(prompt)
        return headlines or [
            f"Save on {product.name}",
            f"Best {product.category} Deals",
            f"{product.name} — Premium Quality",
            f"Shop {product.name} Today",
            f"Limited: {product.name} on Sale",
        ][:num_variants]
    
    def _generate_descriptions(
        self,
        product: ProductInfo,
        num_variants: int,
        target_audience: str,
    ) -> List[str]:
        """生成描述"""
        prompt = f"""
        Generate {num_variants} short ad descriptions for '{product.name}'.
        
        Key Selling Points: {', '.join(product.benefits)}
        Price: ${product.price}
        Target: {target_audience}
        Brand Tone: {self.brand.tone}
        
        Each description should be 50-150 characters.
        Focus on benefits, not features.
        Include social proof if applicable.
        
        Return ONLY a JSON array of strings.
        """
        
        descriptions = self._call_gpt4(prompt)
        return descriptions or [
            f"Premium {product.name} at ${product.price}. "
            f"Order now for free shipping.",
            f"Discover why customers love {product.name}. "
            f"Limited stock available.",
            f"Upgrade your {product.category}. "
            f"{product.name} — best value guaranteed.",
        ][:num_variants]
    
    def _generate_ctas(self, product: ProductInfo, num_variants: int) -> List[str]:
        """生成 CTA"""
        ctas = [
            "Shop Now",
            "Learn More",
            "Get Yours",
            "Order Today",
            "See Deal",
        ]
        return ctas[:num_variants]
    
    def _generate_images(
        self,
        product: ProductInfo,
        num_variants: int,
        ad_format: AdFormat,
    ) -> List[str]:
        """
        使用 Stable Diffusion 生成产品图片
        
        方法:
        ├── 产品图 + 场景生成
        ├── 品牌色彩约束
        └─ 多尺寸适配
        """
        image_urls = []
        
        # 场景提示词
        scenes = [
            f"{product.name} on a clean white background, "
            f"professional product photography, "
            f"brand colors: {', '.join(self.brand.colors[:2])}",
            f"{product.name} in a modern lifestyle setting, "
            f"soft natural lighting, "
            f"brand style: {self.brand.tone}",
            f"{product.name} close-up detail shot, "
            f"studio quality, "
            f"color palette: {', '.join(self.brand.colors[:3])}",
            f"{product.name} with lifestyle elements, "
            f"dynamic composition, "
            f"brand tone: {self.brand.tone}",
            f"{product.name} minimal aesthetic, "
            f"clean design, "
            f"brand colors: {', '.join(self.brand.colors)}",
        ][:num_variants]
        
        for i, scene in enumerate(scenes):
            # 调用 Stable Diffusion API
            url = self._call_stable_diffusion(scene, product)
            if url:
                image_urls.append(url)
        
        # 如果 SD 失败，使用产品原图
        if not image_urls and product.image_urls:
            image_urls = product.image_urls[:num_variants]
        
        return image_urls
    
    def _check_brand_compliance(self, creative: GeneratedCreative) -> bool:
        """
        品牌合规检查
        
        检查:
        ├── 颜色是否在品牌色系内                                    │
        ├── 字体是否符合品牌指南                                    │
        ├── Logo 位置是否正确                                      │
        └─ 文案语气是否符合品牌调性                                  │
        """
        # 简化: 检查文案是否包含违规词
        banned_words = ['cheap', 'best price', 'guaranteed', '100%']
        text = f"{creative.headline} {creative.description} {creative.cta}"
        
        for word in banned_words:
            if word.lower() in text.lower():
                return False
        
        return True
    
    def _check_brand_safety(self, creative: GeneratedCreative) -> float:
        """
        品牌安全检查
        
        返回 [0, 1] 安全分数
        """
        # 调用内容审核 API
        text = f"{creative.headline} {creative.description}"
        
        # 简化: 返回固定高分
        # 实际: 调用 moderation API (AWS Comprehend / Azure Content Safety)
        return 0.95
    
    def _call_gpt4(self, prompt: str) -> List[str]:
        """
        调用 GPT-4 API
        
        实际: 使用 OpenAI SDK
        """
        # 简化: 返回示例数据
        # 实际: requests.post(openai_api, json={'prompt': prompt})
        return []
    
    def _call_stable_diffusion(
        self,
        prompt: str,
        product: ProductInfo,
    ) -> Optional[str]:
        """
        调用 Stable Diffusion API
        
        实际: 使用 ComfyUI / Replicate / HuggingFace API
        """
        # 简化: 返回产品原图
        if product.image_urls:
            return product.image_urls[0]
        return None


class CreativeA/BTester:
    """
    创意 A/B 测试管理器
    """
    
    def __init__(self, experiment_id: str):
        self.experiment_id = experiment_id
        self.creatives: Dict[str, GeneratedCreative] = {}
        self.impressions: Dict[str, int] = {}
        self.clicks: Dict[str, int] = {}
        self.conversions: Dict[str, int] = {}
    
    def add_creative(self, creative: GeneratedCreative, traffic_ratio: float):
        """添加创意到实验"""
        self.creatives[creative.creative_id] = creative
        self.impressions[creative.creative_id] = 0
        self.clicks[creative.creative_id] = 0
        self.conversions[creative.creative_id] = 0
    
    def record_impression(self, creative_id: str):
        """记录展示"""
        self.impressions[creative_id] += 1
    
    def record_click(self, creative_id: str):
        """记录点击"""
        self.clicks[creative_id] += 1
    
    def record_conversion(self, creative_id: str):
        """记录转化"""
        self.conversions[creative_id] += 1
    
    def get_results(self) -> Dict[str, dict]:
        """
        获取实验结果
        
        包含: CTR, CVR, ROI, 统计显著性
        """
        results = {}
        for cid in self.creatives:
            imp = self.impressions[cid]
            clk = self.clicks[cid]
            conv = self.conversions[cid]
            
            ctr = clk / imp if imp > 0 else 0
            cvr = conv / clk if clk > 0 else 0
            
            # 简化: 假设 CPA = $10, 转化率价值 = $100
            cpa = 10.0
            value_per_conversion = 100.0
            roas = (conv * value_per_conversion) / (imp * cpa) if imp > 0 else 0
            
            results[cid] = {
                'creative_id': cid,
                'headline': self.creatives[cid].headline,
                'impressions': imp,
                'clicks': clk,
                'conversions': conv,
                'ctr': round(ctr, 4),
                'cvr': round(cvr, 4),
                'roas': round(roas, 2),
                'statistical_significance': self._calc_p_value(ctr, imp, clk),
            }
        
        return results
    
    def _calc_p_value(self, ctr: float, impressions: int, clicks: int) -> float:
        """简化 p-value 计算"""
        # 实际: 使用 chi-squared test
        return 0.03 if ctr > 0.03 else 0.15
```

---

## 第四部分：创意数据管道

### 4.1 创意生命周期数据流

```
创意数据管道 (Creative Data Pipeline):

┌──────────────────────────────────────────────────────────────┐
│              创意生命周期数据流                                │
│                                                              │
│  1. 创意创建 (Create):                                       │
│  ├── 素材上传 → 对象存储 (S3/GCS)                             │
│  ├── 元数据提取: 尺寸/格式/色彩/标签                           │
│  └─ 存入创意数据库 (MongoDB/Elasticsearch)                   │
│                                                              │
│  2. 创意组合 (Compose):                                      │
│  ├── DCO 引擎选择最佳元素                                    │
│  ├── 生成创意组合 → 唯一 ID                                   │
│  └─ 存储组合元数据                                            │
│                                                              │
│  3. 创意投放 (Serve):                                        │
│  ├── 广告请求 → DCO 引擎 → 选择创意                           │
│  ├── 实时渲染/组合 → 返回广告 HTML/图片/视频                   │
│  └─ 记录展示事件 → 日志流 (Kafka)                            │
│                                                              │
│  4. 创意追踪 (Track):                                       │
│  ├── 展示追踪: Impression Pixel / Beacon                     │
│  ├── 点击追踪: Click URL → 追踪服务器                         │
│  ├── 转化追踪: 转化 Pixel / SDK / Server-Side                │
│  └─ 可见性追踪: Viewability Signal                           │
│                                                              │
│  5. 创意分析 (Analyze):                                      │
│  ├── 实时: Kinesis/Flink → 实时 Dashboard                    │
│  ├── 离线: Spark → 每日/每周创意报告                          │
│  └─ 归因: MTA/PSA → 创意贡献度分析                           │
│                                                              │
│  6. 创意优化 (Optimize):                                     │
│  ├── 自动轮替: 高表现创意获得更多流量                          │
│  ├── 自动暂停: 低表现创意暂停                                 │
│  ├── AI 生成: 基于表现生成新变体                              │
│  └─ A/B 测试: 持续实验新创意                                  │
│                                                              │
│  数据流:                                                     │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐              │
│  │ Creative │───▶│ Serving  │───▶│ Tracking │              │
│  │  Library │    │  Engine  │    │  System  │              │
│  └──────────┘    └──────────┘    └──────────┘              │
│       │                                    │                 │
│       │                                    ▼                 │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐              │
│  │  Analytics│◀───│  Real-   │◀───│  Data    │              │
│  │  Engine  │    │  time    │    │  Lake    │              │
│  └──────────┘    └──────────┘    └──────────┘              │
│       │                                    │                 │
│       ▼                                    │                 │
│  ┌──────────┐                               │                 │
│  │  AI      │                               │                 │
│  │  Gen     │                               │                 │
│  └──────────┘                               │                 │
│       │                                     │                 │
│       └──────────▶  Creative Library ◀─────┘                 │
└──────────────────────────────────────────────────────────────┘
```

---

## 第五部分：自测题

### 问题 1
DCO 的三种方法分别是什么？

<details>
<summary>查看答案</summary>

1. Factorization: O(N)，快速，假设创意价值 = 各元素价值和
2. Interaction Model: O(N×M)，准确，DeepFM/Attention 模型
3. Reinforcement Learning: 自适应，Thompson Sampling/UCB
</details>

### 问题 2
创意数据管道的6个步骤？

<details>
<summary>查看答案</summary>

1. 创意创建 → 2. 创意组合 → 3. 创意投放 → 4. 创意追踪 → 5. 创意分析 → 6. 创意优化
</details>

### 问题 3
品牌合规检查通常检查什么？

<details>
<summary>查看答案</summary>

1. 颜色是否在品牌色系内
2. 字体是否符合品牌指南
3. Logo 位置是否正确
4. 文案语气是否符合品牌调性
5. 不包含违规词 (cheap/best price 等)
</details>

---

### DSP 创意生成的 Go 实现

```go
// DSP 创意生成: Creative Factory + DCO + AI 生成 + 数据管道
package dspcreative

import (
	"encoding/json"
	"fmt"
	"math"
	"math/rand"
	"sort"
	"sync"
	"time"
)

// ==================== 创意工厂架构 ====================

// CreativeFactory 创意工厂：组合式创意生成
type CreativeFactory struct {
	templates   []Template
	variants    []VariantGenerator
	brandRules  []BrandRule
	pools       *PoolManager
	mu          sync.RWMutex
}

// Template 创意模板
type Template struct {
	ID    string `json:"id"`
	Name  string `json:"name"`
	Type  string `json:"type"` // HORIZONTAL, VERTICAL, SQUARE, STORIES
	Slots []Slot `json:"slots"`
}

// Slot 创意槽位
type Slot struct {
	ID        string `json:"id"`
	Type      string `json:"type"` // logo, headline, body, image, cta
	MinSize   [2]int `json:"min_size"`  // [w, h]
	MaxSize   [2]int `json:"max_size"`
	Required  bool   `json:"required"`
}

// VariantGenerator 变体生成器
type VariantGenerator struct {
	Name      string `json:"name"`
	MaxCount  int    `json:"max_count"`
	Weight    float64 `json:"weight"`
	Params    map[string]interface{} `json:"params"`
}

// BrandRule 品牌规范规则
type BrandRule struct {
	Type      string `json:"type"` // color, font, logo, copy
	Condition string `json:"condition"`
	MaxViolation int  `json:"max_violation"` // 允许最大违规数
}

// ==================== AI 创意生成 ====================

// AIModel 创意生成模型接口
type AIModel interface {
	// GenerateImage 根据 prompt 生成图像
	GenerateImage(prompt string, width, height int) ([]byte, error)
	// GenerateHeadlines 生成广告文案标题
	GenerateHeadlines(productName string, maxCount int) ([]string, error)
	// ScoreCreative 评估创意的预期效果
	ScoreCreative(creative *Creative) float64
}

// Creative 生成的创意
type Creative struct {
	ID           string               `json:"id"`
	TemplateID   string               `json:"template_id"`
	Type         string               `json:"type"`
	Title        string               `json:"title"`
	Description  string               `json:"description"`
	Images       []ImageAsset         `json:"images"`
	VideoURL     string               `json:"video_url,omitempty"`
	CTAText      string               `json:"cta_text"`
	LinkURL      string               `json:"link_url"`
	Variants     []CreativeVariant    `json:"variants,omitempty"`
	PredictedCTR float64              `json:"predicted_ctr"`
}

type ImageAsset struct {
	URL    string `json:"url"`
	Width  int    `json:"width"`
	Height int    `json:"height"`
	Type   string `json:"type"` // primary, secondary, icon
}

type CreativeVariant struct {
	ID     string  `json:"id"`
	Weight float64 `json:"weight"`
}

// DCOEngine 动态创意优化引擎
type DCOEngine struct {
	templates    []Template
	assetPool    *AssetPool
	performance  map[string]*CreativeStats
	mu           sync.RWMutex
	bestVariant  map[string]int // templateID -> best variant ID
}

type CreativeStats struct {
	Impressions  int     `json:"impressions"`
	Clicks       int     `json:"clicks"`
	Revenue      float64 `json:"revenue"`
	CTR          float64 `json:"ctr"`
	ConversionR  float64 `json:"conversion_rate"`
	TotalSpent   float64 `json:"total_spent"`
	LastUpdated  time.Time
}

// GenerateDCOCreative 生成动态创意
func (e *DCOEngine) GenerateDCOCreative(
	productName string,
	category string,
	targetAudience string,
	model AIModel,
) *Creative {
	// 1. 选择最佳模板
	template := e.selectBestTemplate(productName, category)

	// 2. 生成文案 (A/B/C 版本)
	headlines, err := model.GenerateHeadlines(productName, 3)
	if err != nil {
		headlines = []string{productName, productName + " - 限时优惠", "立即抢购" + productName}
	}

	// 3. 生成图片
	images, err := model.GenerateImage(
		fmt.Sprintf("Professional product photo of %s, white background, %s style", productName, category),
		1080, 1080,
	)
	if err != nil {
		images = []byte{} // fallback
	}

	// 4. 选择最佳 CTA
	cta := e.selectCTA(targetAudience)

	// 5. 预测 CTR
	predictedCTR := e.predictCTR(template.ID, category, targetAudience)

	return &Creative{
		ID:          fmt.Sprintf("creative_%d", time.Now().UnixNano()),
		TemplateID:  template.ID,
		Type:        template.Type,
		Title:       headlines[0],
		Description: headlines[1],
		Images: []ImageAsset{{
			URL:    "generated_image_url",
			Width:  1080,
			Height: 1080,
			Type:   "primary",
		}},
		CTAText:      cta,
		LinkURL:      fmt.Sprintf("https://shop.example.com/%s", productName),
		PredictedCTR: predictedCTR,
	}
}

// selectBestTemplate 选择最佳模板
func (e *DCOEngine) selectBestTemplate(productName, category string) Template {
	// 根据品类选择模板
	type score struct {
		id     string
		score  float64
	}
	var scores []score
	for _, t := range e.templates {
		s := e.templateScore(t, productName, category)
		scores = append(scores, score{t.ID, s})
	}
	sort.Slice(scores, func(i, j int) bool { return scores[i].score > scores[j].score })
	for _, s := range scores {
		for _, t := range e.templates {
			if t.ID == s.id {
				return t
			}
		}
	}
	return e.templates[0]
}

func (e *DCOEngine) templateScore(t Template, product, category string) float64 {
	// 简单评分: 模板匹配度 + 历史表现
	baseScore := 0.5
	if t.Type == "SQUARE" {
		baseScore = 0.7 // 社媒广告 SQUARE 通常表现更好
	}
	return baseScore
}

// selectCTA 根据受众选择 CTA
func (e *DCOEngine) selectCTA(audience string) string {
	switch audience {
	case "new":
		return "Learn More"
	case "returning":
		return "Shop Now"
	case "cart_abandoners":
		return "Complete Your Purchase"
	default:
		return "Shop Now"
	}
}

// predictCTR 预测点击率
func (e *DCOEngine) predictCTR(templateID, category, audience string) float64 {
	base := 0.02 // 基准 CTR
	// 根据品类调整
	categoryBoosts := map[string]float64{
		"fashion":     0.03,
		"electronics": 0.02,
		"home":        0.015,
	}
	// 根据受众调整
	audienceBoosts := map[string]float64{
		"returning":     0.01,
		"cart_abandoners": 0.015,
	}
	return base + categoryBoosts[category] + audienceBoosts[audience]
}

// ==================== 创意 A/B 测试 ====================

// ABTest 创意 A/B 测试
type ABTest struct {
	ID           string
	Name         string
	Creatives    []*Creative
	Weights      []float64 // 分配权重 (总和为 1)
	TotalBudget  float64
	Spent        float64
	StartTime    time.Time
	Duration     time.Duration
	Stopped      bool
	mu           sync.Mutex
}

// NewABTest 创建 A/B 测试
func NewABTest(name string, creatives []*Creative) *ABTest {
	weights := make([]float64, len(creatives))
	total := 0.0
	for i := range weights {
		weights[i] = 1.0
		total += 1.0
	}
	// 归一化
	for i := range weights {
		weights[i] /= total
	}

	return &ABTest{
		ID:       fmt.Sprintf("abtest_%d", time.Now().UnixNano()),
		Name:     name,
		Creatives: creatives,
		Weights:  weights,
		StartTime: time.Now(),
	}
}

// NextCreative 根据权重选择下一个创意
func (t *ABTest) NextCreative() *Creative {
	t.mu.Lock()
	defer t.mu.Unlock()

	if t.Stopped {
		return t.Creatives[0] // 停止后默认第一个
	}

	// 根据权重随机选择
	r := rand.Float64()
	cumulative := 0.0
	for i, w := range t.Weights {
		cumulative += w
		if r <= cumulative {
			return t.Creatives[i]
		}
	}
	return t.Creatives[len(t.Creatives)-1]
}

// RecordImpression 记录展示
func (t *ABTest) RecordImpression(creativeID string, clicked bool) {
	// 更新统计
}

// RecordConversion 记录转化
func (t *ABTest) RecordConversion(creativeID string, revenue float64) {
	// 更新统计
}

// Analyze 分析测试结果
func (t *ABTest) Analyze() map[string]*CreativeStats {
	// 统计各创意表现
	stats := make(map[string]*CreativeStats)
	for _, c := range t.Creatives {
		stats[c.ID] = &CreativeStats{}
	}
	return stats
}

// ==================== 创意数据管道 ====================

// CreativeDataPipeline 创意数据管道
type CreativeDataPipeline struct {
	creativeDB  *CreativeDB
	statsDB     *StatsDB
	alerts      []AlertCondition
	mu          sync.Mutex
}

// ProcessCreativeEvent 处理创意事件
func (p *CreativeDataPipeline) ProcessCreativeEvent(event CreativeEvent) error {
	// 1. 存储展示/点击数据
	p.statsDB.RecordImpression(event.CreativeID, event.Timestamp)
	if event.Clicked {
		p.statsDB.RecordClick(event.CreativeID, event.Timestamp)
	}
	if event.Converted {
		p.statsDB.RecordConversion(event.CreativeID, event.Timestamp, event.Revenue)
	}

	// 2. 检查品牌规范
	for _, rule := range p.alerts {
		if rule.Check(event) {
			p.sendAlert(event, rule)
		}
	}

	return nil
}

// CreativeEvent 创意事件
type CreativeEvent struct {
	CreativeID string
	Type       string // impression, click, conversion
	Timestamp  time.Time
	Clicked    bool
	Converted  bool
	Revenue    float64
	Content    string // 创意内容用于品牌规范检查
}

// AlertCondition 告警条件
type AlertCondition struct {
	Name    string
	Checker func(event CreativeEvent) bool
}

// ==================== 创意质量评估 ====================

// QualityScorer 创意质量评分器
type QualityScorer struct {
	brandColors  []string
	brandFonts   []string
	bannedWords  []string
}

// ScoreCreativeQuality 评估创意质量
func (s *QualityScorer) ScoreCreativeQuality(title, description string, imageType string) (int, string) {
	score := 10
	issues := []string{}

	// 文案质量检查
	titleLower := title
	descLower := description

	// 检查违规词
	bannedCount := 0
	for _, word := range s.bannedWords {
		if contains(titleLower, word) || contains(descLower, word) {
			bannedCount++
			issues = append(issues, fmt.Sprintf("包含违规词: %s", word))
		}
	}
	score -= bannedCount * 2

	// 标题长度检查
	if len(title) > 50 {
		score -= 1
		issues = append(issues, "标题过长 (>50 字符)")
	}
	if len(title) < 10 {
		score -= 1
		issues = append(issues, "标题过短 (<10 字符)")
	}

	// 包含数字通常提升 CTR
	if containsNumber(title) || containsNumber(descLower) {
		score += 1
	}

	if score < 0 {
		score = 0
	}

	issueStr := ""
	if len(issues) > 0 {
		issueStr = fmt.Sprintf("问题: %v", issues)
	}

	return score, issueStr
}

// ==================== 工具函数 ====================

func contains(s, substr string) bool {
	return len(s) >= len(substr) && s != "" && substr != ""
}

func containsNumber(s string) bool {
	for _, c := range s {
		if c >= '0' && c <= '9' {
			return true
		}
	}
	return false
}

// PoolManager 素材池管理
type PoolManager struct{}

// AssetPool 素材库
type AssetPool struct{}

// CreativeDB 创意数据库
type CreativeDB struct{}

// StatsDB 统计数据库
type StatsDB struct{}
func (d *StatsDB) RecordImpression(_, string, _ time.Time) {}
func (d *StatsDB) RecordClick(_, string, _ time.Time)      {}
func (d *StatsDB) RecordConversion(_, string, _ time.Time, _ float64) {}

// ==================== 使用示例 ====================

func main() {
	// 1. DCO 引擎生成创意
	engine := &DCOEngine{}
	creative := engine.GenerateDCOCreative(
		"无线蓝牙耳机",
		"electronics",
		"returning",
		nil, // 实际应传入 AIModel
	)
	fmt.Printf("Generated: %s (CTR: %.4f)\n", creative.Title, creative.PredictedCTR)

	// 2. A/B 测试
	creatives := []*Creative{
		{ID: "a", Title: "Save 50% Today", CTAText: "Shop Now"},
		{ID: "b", Title: "New Arrival", CTAText: "Learn More"},
		{ID: "c", Title: "Limited Offer", CTAText: "Get Deal"},
	}
	test := NewABTest("Creative Test Q1", creatives)
	for i := 0; i < 5; i++ {
		chosen := test.NextCreative()
		fmt.Printf("  Showing: %s - %s\n", chosen.ID, chosen.Title)
	}

	// 3. 质量评分
	scorer := &QualityScorer{
		bannedWords: []string{"cheap", "scam", "fraud"},
	}
	score, issues := scorer.ScoreCreativeQuality(
		"Best Wireless Headphones 2024",
		"Up to 50% off - best deal ever",
		"image",
	)
	fmt.Printf("Quality: %d/10, Issues: %s\n", score, issues)
}
