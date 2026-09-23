"""Text and structured UI fallbacks for advertising creation."""

from __future__ import annotations

import re
from typing import Any, Mapping


class AdCreationUIServicesMixin:
    @staticmethod
    def creation_ui_reply(ui: Mapping[str, Any], user_input: str = "") -> str:
        """Explain an incomplete creation draft in operator-friendly language."""
        is_english = bool(user_input) and not re.search(r"[\u3400-\u9fff]", user_input)
        cards = ui.get("cards") if isinstance(ui, Mapping) else []
        titles = [
            str(card.get("title") or "广告创建")
            for card in cards or []
            if isinstance(card, Mapping)
        ]
        selector_cards = [
            card
            for card in cards or []
            if isinstance(card, Mapping)
            and card.get("type") == "ad_creation_selector"
        ]
        clarification = ui.get("clarification") if isinstance(ui, Mapping) else None
        if isinstance(clarification, Mapping):
            provider = str(clarification.get("provider") or "目标平台")
            option_labels = [
                str(option.get("label") or option.get("value"))
                for option in (clarification.get("options") or [])[:12]
                if isinstance(option, Mapping)
            ]
            options_text = "、".join(dict.fromkeys(option_labels))
            if is_english:
                return (
                    f"I identified a {provider} ad creation request, but the campaign goal/type is not clear yet. "
                    f"Supported choices: {options_text}. Please choose one; I will then show the complete form "
                    "for that Blueprint and will not submit anything without a final confirmation."
                )
            return (
                f"我识别到你要在 {provider} 创建广告，但目前还不能确定具体的推广目标或广告类型。"
                f"当前能力支持：{options_text}。请先选择一种；确定后我再展示该蓝图对应的完整 Campaign、Ad Group 和 Ad 参数，"
                "不会根据模糊描述猜测，也不会提前提交。"
            )
        if selector_cards:
            provider = str(selector_cards[0].get("provider") or "目标平台")
            selector = selector_cards[0]
            missing_account = bool(
                selector_cards[0].get("account_required")
                and not selector_cards[0].get("account_id")
            )
            choices: list[str] = []
            for field in selector.get("fields") or []:
                if not isinstance(field, Mapping):
                    continue
                options = field.get("options") or []
                labels = []
                for option in options[:8]:
                    if isinstance(option, Mapping):
                        labels.append(str(option.get("label") or option.get("value")))
                    else:
                        labels.append(str(option))
                if labels:
                    choices.append(f"{field.get('label') or '广告类型'}：" + "、".join(labels))
            if is_english:
                choice_text = " ".join(f"{item}." for item in choices)
                account_text = (
                    "Choose an authorized advertiser/account first; it is never guessed. "
                    if missing_account else ""
                )
                options_text = f"Available choices: {choice_text} " if choice_text else ""
                template_count = len(selector.get("template_options") or [])
                template_text = (
                    f"{template_count} account templates are available; "
                    "you may use one or continue without a template. "
                    if template_count else
                    "No matching template is available; you can continue without a template. "
                )
                return (
                    f"I identified a {provider} ad creation request. {account_text}"
                    f"{template_text}{options_text}Choose a campaign goal or ad format, then I will show only the parameters"
                    " allowed for that combination. You can also continue in plain language."
                    " Once the details are complete, I will show a final preview and wait for your confirmation before submitting."
                )
            choice_text = "；".join(choices)
            account_text = (
                "请先从当前身份可用的广告账户中选择一个，系统不会猜测账户。"
                if missing_account else ""
            )
            options_text = f"当前可选：{choice_text}。" if choice_text else ""
            template_count = len(selector.get("template_options") or [])
            template_text = (
                f"当前账户有 {template_count} 个可用模板，你可以直接使用模板，也可以跳过模板选择。"
                if template_count else
                "当前账户没有匹配模板，可以直接跳过模板选择。"
            )
            return (
                f"我识别到你要在 {provider} 创建广告。{account_text}{template_text}{options_text}"
                "选定账户后，可以直接使用模板，或选择广告类型进入标准参数向导。"
                "信息完整后，我会先给你看最终方案，等你确认后才提交创建。"
            )
        subject = titles[0] if len(titles) == 1 else "广告创建参数"
        pending_labels: list[str] = []
        invalid_labels: list[str] = []
        pending_fields: list[Mapping[str, Any]] = []
        invalid_fields: list[Mapping[str, Any]] = []
        account_missing = False
        for card in cards or []:
            if not isinstance(card, Mapping):
                continue
            account_missing = account_missing or bool(
                card.get("account_required")
                and not str(card.get("account_id") or "").strip()
            )
            invalid_paths = {str(path) for path in (card.get("invalid_fields") or [])}
            for field in card.get("fields") or []:
                if not isinstance(field, Mapping) or field.get("visible") is False:
                    continue
                path = str(field.get("path") or "")
                label = str(field.get("label") or path or "参数")
                value = field.get("value")
                is_empty = value in (None, "", [], {})
                if path in invalid_paths or field.get("state") == "invalid":
                    if label not in invalid_labels:
                        invalid_labels.append(label)
                        invalid_fields.append(field)
                elif field.get("required") and is_empty and label not in pending_labels:
                    pending_labels.append(label)
                    pending_fields.append(field)
        if account_missing:
            pending_labels.insert(0, "广告账户 ID")
        pending_labels = list(dict.fromkeys(pending_labels))
        invalid_labels = list(dict.fromkeys(invalid_labels))
        visible_labels = (pending_labels + invalid_labels)[:8]
        remaining = len(pending_labels) + len(invalid_labels) - len(visible_labels)
        detail = "、".join(visible_labels)
        if remaining > 0:
            detail += f"等另外 {remaining} 项"

        def field_help(field: Mapping[str, Any], english: bool = False) -> str:
            label = str(field.get("label") or field.get("path") or "parameter")
            options = field.get("options") or []
            if options:
                rendered = []
                option_labels = field.get("option_labels") or {}
                for option in options[:6]:
                    if isinstance(option, Mapping):
                        value = option.get("value")
                        shown = option.get("label") or option_labels.get(str(value)) or value
                    else:
                        value = option
                        shown = option_labels.get(str(value), value)
                    rendered.append(
                        str(shown) if str(shown) == str(value)
                        else f"{shown} ({value})"
                    )
                suffix = " or more" if len(options) > 6 else ""
                return f"{label}: " + ", ".join(rendered) + suffix
            lookup = field.get("lookup")
            if isinstance(lookup, Mapping) or str(field.get("source") or "").lower() == "lookup":
                if english:
                    return f"{label}: choose from the current account list (search is available; do not type an unknown ID)."
                return f"{label}：可从当前账户的列表中搜索选择，系统不会猜测 ID。"
            manual = field.get("manual_entry")
            if isinstance(manual, Mapping):
                instructions = str(manual.get("instructions") or "请提供已在平台中配置的值")
                return f"{label}: {instructions}" if english else f"{label}：{instructions}"
            dependencies = field.get("missing_option_dependencies") or []
            if dependencies:
                dep_text = ", ".join(str(item) for item in dependencies)
                return (
                    f"{label}: choose {dep_text} first"
                    if english else f"{label}：请先完成 {dep_text}"
                )
            constraints = field.get("constraints") or {}
            if constraints:
                hints = []
                if constraints.get("minimum") is not None:
                    hints.append(f">= {constraints['minimum']}" if english else f"至少 {constraints['minimum']}")
                if constraints.get("maximum") is not None:
                    hints.append(f"<= {constraints['maximum']}" if english else f"最多 {constraints['maximum']}")
                if hints:
                    return f"{label} ({', '.join(hints)})"
            return label

        focus_fields = invalid_fields[:4] if invalid_fields else pending_fields[:6]
        if is_english:
            action = "Please correct" if invalid_labels else (
                "Please provide" if pending_labels else "You can review the preview"
            )
            details = "; ".join(field_help(field, True) for field in focus_fields)
            if account_missing:
                details = (
                    "Account/advertiser ID (enter it manually; it will not be guessed)"
                    + ("; " + details if details else "")
                )
            if not details:
                details = ", ".join(visible_labels)
            return (
                f"I identified {subject}. {action}: {details}. "
                "You may reply in plain language, for example: “Use account [ID], choose Android, "
                "optimize for app installs, and set a daily budget of 100.” "
                "I will validate the combination, show a final preview, and submit only after your confirmation."
            )
        action = "请先修改" if invalid_labels else (
            "还需要补充" if pending_labels else "你可以先查看下方预览"
        )
        details = "；".join(field_help(field) for field in focus_fields)
        if account_missing:
            details = (
                "请提供要操作的广告账户 ID（请人工填写，系统不会猜测）"
                + ("；" + details if details else "")
            )
        if not details:
            details = detail
        return (
            f"我识别到你要创建{subject}。{action}：{details}。"
            "你也可以直接用文字继续，例如“账户 ID 是 [账户ID]，选择 Android，优化安装量，日预算 100”。"
            "我会先校验参数组合并展示最终方案，只有你明确确认后才会提交创建。"
        )

    @staticmethod
    def action_clarification_reply(
        ui: Mapping[str, Any], user_input: str = "",
    ) -> str:
        """Render schema-driven missing inputs as a business question."""
        clarification = ui.get("clarification") if isinstance(ui, Mapping) else {}
        if not isinstance(clarification, Mapping):
            return "请补充本次操作所需的信息。"
        question = str(clarification.get("question") or "请补充本次操作所需的信息。")
        fields = clarification.get("fields") or []
        parts: list[str] = []
        for field in fields[:8]:
            if not isinstance(field, Mapping):
                continue
            label = str(field.get("label") or field.get("path") or "参数")
            source = str(field.get("source") or "text")
            if source == "lookup":
                detail = "请从当前账户的资源列表中选择，系统不会猜测 ID"
            elif source == "enum" and field.get("options"):
                options = "、".join(str(item) for item in field["options"][:8])
                detail = f"可选：{options}"
            else:
                detail = str(field.get("hint") or "请直接提供")
            parts.append(f"{label}（{detail}）")
        suffix = "；".join(parts)
        hint = str(clarification.get("hint") or "")
        if suffix:
            question += "\n" + suffix + "。"
        if hint and hint not in question:
            question += "\n" + hint
        return question


__all__ = ["AdCreationUIServicesMixin"]
