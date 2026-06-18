# 广告对话系统深度：意图识别/槽位填充/多轮对话

> 从 NLU 到 Dialog Management，逐行解析广告对话系统核心

---

## 第一部分：意图识别源码

### 意图识别架构

```
意图识别流程：
用户输入 → 文本预处理 → 特征提取 → 分类模型 → 意图置信度

意图分类：
┌─────────────────────────────────────────────────────────────────────┐
│ 1. 创建广告 (create_ad)                                              │
│    - "帮我创建一个 Facebook 广告"                                    │
│    - "我想投一个新的广告系列"                                        │
│                                                                     │
│ 2. 修改广告 (modify_ad)                                              │
│    - "把预算提高到 500 元"                                           │
│    - "暂停这个广告"                                                  │
│                                                                     │
│ 3. 查询数据 (query_data)                                             │
│    - "今天花了多少钱"                                                │
│    - "CTR 是多少"                                                   │
│                                                                     │
│ 4. 优化建议 (optimize_suggestion)                                    │
│    - "帮我优化一下广告"                                              │
│    - "有什么改进建议"                                                │
│                                                                     │
│ 5. 帮助 (help)                                                       │
│    - "怎么用你们平台"                                                │
│    - "帮助"                                                         │
└─────────────────────────────────────────────────────────────────────┘
```

### IntentClassifier 源码逐行解析

```python
# 意图识别器
from transformers import pipeline
import torch

class IntentClassifier:
    def __init__(self, model_name: str = "bert-base-chinese"):
        # 加载预训练模型
        self.classifier = pipeline(
            "text-classification",
            model=model_name,
            tokenizer=model_name,
            return_all_scores=True,
        )
        
        # 意图映射
        self.intent_map = {
            "create_ad": "创建广告",
            "modify_ad": "修改广告",
            "query_data": "查询数据",
            "optimize_suggestion": "优化建议",
            "help": "帮助",
        }
    
    def classify(self, text: str, confidence_threshold: float = 0.7) -> dict:
        """
        识别用户意图
        
        Args:
            text: 用户输入
            confidence_threshold: 置信度阈值
        
        Returns:
            {
                "intent": "create_ad",
                "confidence": 0.95,
                "all_scores": [...],
                "needs_clarification": False
            }
        """
        # 1. 文本预处理
        text = self._preprocess(text)
        
        # 2. 模型预测
        results = self.classifier(text)[0]
        
        # 3. 找出最高置信度的意图
        best_intent = max(results, key=lambda x: x["score"])
        
        # 4. 检查置信度
        if best_intent["score"] < confidence_threshold:
            return {
                "intent": "unknown",
                "confidence": best_intent["score"],
                "needs_clarification": True,
                "top_alternatives": results[:3],
            }
        
        # 5. 检查意图间差距（避免误判）
        sorted_results = sorted(results, key=lambda x: x["score"], reverse=True)
        gap = sorted_results[0]["score"] - sorted_results[1]["score"]
        
        if gap < 0.1:
            # 意图间差距太小，可能需要澄清
            return {
                "intent": best_intent["label"],
                "confidence": best_intent["score"],
                "needs_clarification": True,
                "ambiguity_reason": "意图间差距太小",
            }
        
        return {
            "intent": best_intent["label"],
            "confidence": best_intent["score"],
            "needs_clarification": False,
            "all_scores": results,
        }
    
    def _preprocess(self, text: str) -> str:
        """文本预处理"""
        # 去除多余空格
        text = " ".join(text.split())
        # 去除特殊字符
        text = re.sub(r'[^\w\s\u4e00-\u9fff]', '', text)
        return text
```

---

## 第二部分：槽位填充源码

### 槽位填充架构

```
槽位填充（Slot Filling）：
┌─────────────────────────────────────────────────────────────────────┐
│ 意图: create_ad                                                      │
│                                                                      │
│ 必需槽位:                                                            │
│ ├── platform (平台): Facebook/Google/TikTok                          │
│ ├── budget (预算): 数字 + 货币单位                                   │
│ ├── duration (持续时间): 数字 + 天/月                                 │
│ ├── target_audience (目标人群): 年龄/性别/地区                        │
│ └── creative_type (创意类型): 图片/视频/原生                          │
│                                                                      │
│ 可选槽位:                                                            │
│ ├── ad_name (广告名称)                                               │
│ ├── objective (目标): 品牌认知/转化/流量                              │
│ └── keywords (关键词)                                                │
│                                                                      │
│ 填充策略:                                                            │
│ 1. NER 提取: "我要投 Facebook 广告，预算 1000" → platform=Facebook   │
│ 2. 规则匹配: "投三天" → duration=3                                   │
│ 3. 对话澄清: "请问投哪个平台？"                                       │
│ 4. 上下文继承: 上一轮提到过 Facebook                                  │
└─────────────────────────────────────────────────────────────────────┘
```

### SlotFiller 源码逐行解析

```python
from transformers import AutoTokenizer, AutoModelForTokenClassification
import torch

class SlotFiller:
    def __init__(self):
        # 加载 NER 模型
        self.tokenizer = AutoTokenizer.from_pretrained(
            "bert-base-chinese"
        )
        self.model = AutoModelForTokenClassification.from_pretrained(
            "bert-base-chinese",
            num_labels=10,  # B, I, O 各对应不同槽位
        )
        
        # 槽位标签映射
        self.slot_tags = {
            "B-platform": "平台",
            "I-platform": "平台",
            "B-budget": "预算",
            "I-budget": "预算",
            "B-duration": "持续时间",
            "I-duration": "持续时间",
            "B-target": "目标人群",
            "I-target": "目标人群",
            "B-creative": "创意类型",
            "I-creative": "创意类型",
        }
    
    def fill_slots(self, text: str, intent: str) -> dict:
        """
        填充槽位
        
        Args:
            text: 用户输入
            intent: 识别的意图
        
        Returns:
            {
                "platform": "Facebook",
                "budget": 1000,
                "duration": 7,
                ...
                "missing_slots": ["target_audience", "creative_type"]
            }
        """
        # 1. 文本编码
        inputs = self.tokenizer(
            text,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=512,
        )
        
        # 2. 模型预测
        with torch.no_grad():
            outputs = self.model(**inputs)
        
        # 3. 解码标签
        predictions = torch.argmax(outputs.logits, dim=-1)
        labels = self.tokenizer.convert_ids_to_tokens(inputs["input_ids"][0])
        
        # 4. 提取槽位
        slots = {}
        current_slot = None
        current_value = []
        
        for label, pred in zip(labels, predictions[0]):
            if label == "[PAD]" or label == "[CLS]" or label == "[SEP]":
                continue
            
            pred_label = self._decode_label(pred.item())
            
            if pred_label.startswith("B-"):
                # 开始新槽位
                if current_slot:
                    slots[current_slot] = " ".join(current_value)
                
                slot_type = pred_label[2:]
                current_slot = slot_type
                current_value = []
            elif pred_label.startswith("I-") and current_slot:
                current_value.append(label)
            else:
                # O 标签，结束当前槽位
                if current_slot:
                    slots[current_slot] = " ".join(current_value)
                    current_slot = None
                    current_value = []
        
        # 5. 处理最后一个槽位
        if current_slot:
            slots[current_slot] = " ".join(current_value)
        
        # 6. 转换值类型
        slots = self._convert_values(slots)
        
        # 7. 检查缺失槽位
        required_slots = self._get_required_slots(intent)
        missing = [s for s in required_slots if s not in slots]
        
        return {
            "filled_slots": slots,
            "missing_slots": missing,
            "is_complete": len(missing) == 0,
        }
    
    def _decode_label(self, pred_idx: int) -> str:
        """解码预测标签"""
        id2label = self.model.config.id2label
        return id2label[pred_idx]
    
    def _convert_values(self, slots: dict) -> dict:
        """转换值类型"""
        converted = {}
        for key, value in slots.items():
            if key == "budget":
                try:
                    converted[key] = int(value)
                except ValueError:
                    converted[key] = value
            elif key == "duration":
                try:
                    converted[key] = int(value)
                except ValueError:
                    converted[key] = value
            else:
                converted[key] = value
        return converted
    
    def _get_required_slots(self, intent: str) -> list:
        """获取必需槽位"""
        required = {
            "create_ad": ["platform", "budget", "duration"],
            "modify_ad": ["ad_id", "field", "value"],
            "query_data": ["metric", "time_range"],
            "optimize_suggestion": ["ad_id"],
            "help": [],
        }
        return required.get(intent, [])
```

---

## 第三部分：多轮对话管理源码

### 对话状态追踪

```
对话状态追踪（DST）：
┌─────────────────────────────────────────────────────────────────────┐
│ Turn 1:                                                            │
│ User: "帮我创建一个 Facebook 广告"                                   │
│ Bot: "好的，预算是多少？"                                            │
│ State: {intent: create_ad, platform: Facebook, budget: ???}         │
│                                                                     │
│ Turn 2:                                                            │
│ User: "每天 500 元"                                                 │
│ Bot: "持续多久？"                                                   │
│ State: {intent: create_ad, platform: Facebook, budget: 500}        │
│                                                                     │
│ Turn 3:                                                            │
│ User: "一周"                                                       │
│ Bot: "目标人群是？"                                                 │
│ State: {intent: create_ad, platform: Facebook, budget: 500,        │
│         duration: 7}                                               │
│                                                                     │
│ Turn 4:                                                            │
│ User: "25-35 岁女性"                                                │
│ Bot: "创意类型？"                                                   │
│ State: {intent: create_ad, platform: Facebook, budget: 500,        │
│         duration: 7, target: "25-35岁女性"}                        │
│                                                                     │
│ Turn 5:                                                            │
│ User: "图片"                                                       │
│ Bot: "请提供图片链接或描述"                                         │
│ State: {intent: create_ad, platform: Facebook, budget: 500,        │
│         duration: 7, target: "25-35岁女性", creative: image}       │
└─────────────────────────────────────────────────────────────────────┘
```

### DialogueManager 源码逐行解析

```python
class DialogueManager:
    def __init__(self, intent_classifier: IntentClassifier,
                 slot_filler: SlotFiller):
        self.intent_classifier = intent_classifier
        self.slot_filler = slot_filler
        self.dialogue_history = []
        self.context = {}
    
    def process_turn(self, user_input: str) -> dict:
        """
        处理一轮对话
        
        Args:
            user_input: 用户输入
        
        Returns:
            {
                "response": "Bot 回复",
                "intent": "create_ad",
                "slots": {...},
                "action": "ask_budget",
                "needs_confirmation": False,
            }
        """
        # 1. 识别意图
        intent_result = self.intent_classifier.classify(user_input)
        intent = intent_result["intent"]
        
        # 2. 填充槽位
        slot_result = self.slot_filler.fill_slots(user_input, intent)
        filled_slots = slot_result["filled_slots"]
        missing_slots = slot_result["missing_slots"]
        
        # 3. 更新对话上下文
        self._update_context(intent, filled_slots)
        
        # 4. 决定下一步动作
        action = self._decide_action(intent, missing_slots)
        
        # 5. 生成回复
        response = self._generate_response(action, intent, filled_slots)
        
        # 6. 记录对话历史
        self.dialogue_history.append({
            "user_input": user_input,
            "intent": intent,
            "slots": filled_slots,
            "action": action,
            "response": response,
        })
        
        return {
            "response": response,
            "intent": intent,
            "slots": filled_slots,
            "action": action,
            "needs_confirmation": action == "confirm_and_create",
        }
    
    def _update_context(self, intent: str, slots: dict):
        """更新对话上下文"""
        self.context["intent"] = intent
        self.context["slots"].update(slots)
        
        # 处理指代消解
        self._resolve_coreference(slots)
    
    def _resolve_coreference(self, slots: dict):
        """指代消解"""
        if "this" in slots or "it" in slots:
            # 使用上一次的值
            for key in slots:
                if key in self.context.get("last_slots", {}):
                    slots[key] = self.context["last_slots"][key]
    
    def _decide_action(self, intent: str, missing_slots: list) -> str:
        """决定下一步动作"""
        if not missing_slots:
            return "confirm_and_create"
        elif len(missing_slots) == 1:
            return f"ask_{missing_slots[0]}"
        else:
            return "ask_multiple"
    
    def _generate_response(self, action: str, intent: str,
                           slots: dict) -> str:
        """生成回复"""
        responses = {
            "ask_platform": "请问您想在哪个平台投放广告？（Facebook/Google/TikTok）",
            "ask_budget": "请问您的预算是多少？",
            "ask_duration": "请问广告持续多久？",
            "ask_target": "请问目标人群是谁？",
            "ask_creative": "请问创意类型是什么？（图片/视频/原生）",
            "confirm_and_create": f"确认创建广告：\n"
                                  f"- 平台: {slots.get('platform', 'N/A')}\n"
                                  f"- 预算: {slots.get('budget', 'N/A')}\n"
                                  f"- 持续: {slots.get('duration', 'N/A')}\n\n"
                                  f"请确认是否创建？",
            "created_successfully": "广告创建成功！🎉",
            "unknown_intent": "抱歉，我没理解您的意思。您可以试试：\n"
                              "- '帮我创建一个 Facebook 广告'\n"
                              "- '查看今天的广告数据'",
        }
        
        return responses.get(action, "请再说一遍")
```

---

## 第四部分：自测题

### Q1: 意图识别和槽位填充的关系？

**A**: 先识别意图，再根据意图填充槽位。意图决定需要填充哪些槽位，槽位决定能否执行意图。

### Q2: 多轮对话的状态如何维护？

**A**: 通过 Dialogue State Tracker 维护对话状态，包括当前意图、已填充槽位、缺失槽位。

### Q3: 指代消解怎么处理？

**A**: 当用户说"它"、"这个"时，从对话上下文中找到对应的实体。

---

## 第五部分：生产实践

### 1. 意图识别优化

```
意图识别优化要点：
1. 收集真实用户数据训练
2. 处理长尾意图
3. 设置置信度阈值
4. 定期重新训练
```

### 2. 槽位填充优化

```
槽位填充优化要点：
1. 支持多种表达方式
2. 处理模糊值
3. 上下文继承
4. 错误纠正
```

### 3. 对话管理优化

```
对话管理优化要点：
1. 保持对话连贯性
2. 主动澄清模糊信息
3. 提供快捷方式
4. 记录对话日志
```
