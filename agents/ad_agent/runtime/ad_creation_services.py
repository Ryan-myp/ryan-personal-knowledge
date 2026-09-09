"""Advertising creation and parameter-contract application services.

This application-layer mixin owns blueprint/UI policy only; it is not part of
the generic Runtime Kernel and has no Provider client access.
"""

from __future__ import annotations

import copy
import json
import logging
import re
import uuid
from datetime import datetime
from typing import Any, Iterable, Mapping, Optional

from ..domain.ad.auth import normalize_account_id
from ..domain.ad.blueprint import _schema_at_path
from ..core.execution_plan import ExecutionPlan
from ..core.execution_trace import ExecutionTrace
from ..core.interfaces import ExecutionMode, ParsedIntent, ToolResult
from ..domain.ad.contracts import AdFormatCoverage
from ..core.intent import SimpleIntentRouter
from ..core.tool_registry import validate_tool_input
from .account_context import AccountResolver

logger = logging.getLogger(__name__)


class AdCreationServicesMixin:
    def get_schedule_draft(self, session_id: str) -> Optional[dict[str, Any]]:
        """Return the pending schedule draft restored for this session."""
        session = self._sessions.get(str(session_id or ""))
        if not session:
            return None
        draft = session.ctx.metadata.get("schedule_draft")
        return copy.deepcopy(draft) if isinstance(draft, dict) else None

    def set_schedule_draft(
        self, session_id: str, draft: Optional[Mapping[str, Any]],
    ) -> None:
        """Keep a bounded, redacted schedule draft in durable session metadata."""
        session = self._sessions.get(str(session_id or ""))
        if not session:
            return
        if draft is None:
            session.ctx.metadata.pop("schedule_draft", None)
            return
        safe = self._redact_for_persistence(dict(draft))
        serialized = json.dumps(safe, ensure_ascii=False, default=str)
        if len(serialized.encode("utf-8")) > 32_000:
            raise ValueError("scheduled task draft exceeds persistence limit")
        session.ctx.metadata["schedule_draft"] = safe

    def get_creation_draft(self, session_id: str) -> Optional[dict[str, Any]]:
        """Return the durable, provider-neutral creation draft for a session."""
        session = self._sessions.get(str(session_id or ""))
        if not session:
            return None
        draft = session.ctx.metadata.get("creation_draft")
        return copy.deepcopy(draft) if isinstance(draft, dict) else None

    def set_creation_draft(
        self, session_id: str, draft: Optional[Mapping[str, Any]],
    ) -> None:
        """Persist only bounded, redacted creation context between turns."""
        session = self._sessions.get(str(session_id or ""))
        if not session:
            return
        if draft is None:
            session.ctx.metadata.pop("creation_draft", None)
            return
        safe = self._redact_for_persistence(dict(draft))
        serialized = json.dumps(safe, ensure_ascii=False, default=str)
        if len(serialized.encode("utf-8")) > 48_000:
            raise ValueError("creation draft exceeds persistence limit")
        session.ctx.metadata["creation_draft"] = safe

    def get_action_draft(self, session_id: str) -> Optional[dict[str, Any]]:
        """Return a pending non-creation action clarification draft."""
        session = self._sessions.get(str(session_id or ""))
        if not session:
            return None
        draft = session.ctx.metadata.get("action_draft")
        return copy.deepcopy(draft) if isinstance(draft, dict) else None

    def set_action_draft(
        self, session_id: str, draft: Optional[Mapping[str, Any]],
    ) -> None:
        """Persist bounded context needed to continue an incomplete action."""
        session = self._sessions.get(str(session_id or ""))
        if not session:
            return
        if draft is None:
            session.ctx.metadata.pop("action_draft", None)
            return
        safe = self._redact_for_persistence(dict(draft))
        serialized = json.dumps(safe, ensure_ascii=False, default=str)
        if len(serialized.encode("utf-8")) > 32_000:
            raise ValueError("action clarification draft exceeds persistence limit")
        session.ctx.metadata["action_draft"] = safe

    @staticmethod
    def _creation_intent_from_draft(draft: Optional[Mapping[str, Any]]) -> Optional[ParsedIntent]:
        if not isinstance(draft, Mapping):
            return None
        raw = draft.get("intent") if isinstance(draft.get("intent"), Mapping) else draft
        if not isinstance(raw, Mapping):
            return None
        fields = getattr(ParsedIntent, "__dataclass_fields__", {})
        values = {key: copy.deepcopy(value) for key, value in raw.items() if key in fields}
        if "attributes" not in values:
            values["attributes"] = {
                str(key): copy.deepcopy(value)
                for key, value in raw.items()
                if key not in fields and key not in {"scoped_parameters"}
            }
        if "scoped_parameters" not in values:
            values["scoped_parameters"] = copy.deepcopy(
                raw.get("scoped_parameters") or {}
            )
        # ParsedIntent.to_dict() intentionally omits raw_input from the public
        # contract. A durable draft still needs a safe seed for deterministic
        # Blueprint resolution, so restore it from the draft envelope when
        # available and otherwise use an empty string.
        values.setdefault("raw_input", str(raw.get("raw_input") or draft.get("raw_input") or ""))
        try:
            return ParsedIntent(**values)
        except (TypeError, ValueError):
            return None

    def _adopt_creation_draft(
        self, session_id: str, intent: ParsedIntent, follow_up_text: str,
    ) -> ParsedIntent:
        """Adopt a short answer into the pending creation conversation."""
        draft = self.get_creation_draft(session_id)
        pending = self._creation_intent_from_draft(draft)
        if pending is None:
            return intent
        try:
            adopted = self.creation_card_builder.merge_pending_intent(
                pending, intent, follow_up_text,
            )
        except Exception:
            logger.debug("failed to merge pending creation draft", exc_info=True)
            return intent
        if adopted is None:
            return intent
        return adopted

    def _adopt_action_draft(
        self, session_id: str, intent: ParsedIntent, follow_up_text: str,
    ) -> ParsedIntent:
        """Merge a concise answer into the last incomplete action.

        A reply such as ``campaign_id=123`` often has no platform or action
        words. Reusing the durable intent keeps that answer attached to the
        original request after a restart, while a new non-chat intent is left
        untouched so a pending clarification cannot hijack a new request.
        """
        draft = self.get_action_draft(session_id)
        pending = self._creation_intent_from_draft(draft)
        if pending is None or self.creation_card_builder.is_creation_intent(pending):
            return intent
        current_type = str(getattr(intent, "intent_type", "") or "")
        current_platforms = list(getattr(intent, "namespaces", []) or [])
        pending_platforms = list(getattr(pending, "namespaces", []) or [])
        if current_type not in {"", "chat"} and current_type != pending.intent_type:
            return intent
        if current_platforms and set(current_platforms) != set(pending_platforms):
            return intent

        merged = pending.to_dict()
        merged["raw_input"] = str(getattr(pending, "raw_input", "") or "")
        merged_params = copy.deepcopy(getattr(pending, "scoped_parameters", {}) or {})
        current_params = getattr(intent, "scoped_parameters", {}) or {}
        if isinstance(current_params, Mapping):
            for platform, values in current_params.items():
                if not isinstance(values, Mapping):
                    continue
                destination = dict(merged_params.get(platform, {}) or {})
                destination.update(copy.deepcopy(dict(values)))
                merged_params[platform] = destination
        if pending_platforms:
            try:
                extracted = self.intent_parser.extract_parameters(
                    follow_up_text, pending_platforms
                )
            except Exception:
                extracted = {}
            if isinstance(extracted, Mapping):
                for platform, values in extracted.items():
                    if not isinstance(values, Mapping):
                        continue
                    destination = dict(merged_params.get(platform, {}) or {})
                    destination.update(copy.deepcopy(dict(values)))
                    merged_params[platform] = destination
        attributes = dict(merged.get("attributes") or {})
        attributes.update(copy.deepcopy(getattr(intent, "attributes", {}) or {}))
        merged["attributes"] = attributes
        merged["scoped_parameters"] = merged_params
        merged["intent_type"] = pending.intent_type
        merged["namespaces"] = pending_platforms
        try:
            return ParsedIntent(**{
                key: value for key, value in merged.items()
                if key in ParsedIntent.__dataclass_fields__
            })
        except (TypeError, ValueError):
            return intent

    def _action_clarification_response(
        self,
        *,
        session: "SessionContext",
        session_id: str,
        run_id: str,
        turn_id: str,
        user_input: str,
        reply: str,
        intent: ParsedIntent,
        ui: Mapping[str, Any],
        trace: ExecutionTrace,
        recalled_memories: list[dict[str, Any]],
        memory_updates: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Stop before plan/workflow creation while collecting action inputs."""
        clarification = ui.get("clarification") if isinstance(ui, Mapping) else {}
        confirmation_payload = None
        clarification_fields = (
            clarification.get("fields", [])
            if isinstance(clarification, Mapping) else []
        )
        account_fields = [
            item for item in clarification_fields
            if isinstance(item, Mapping)
            and str(item.get("path") or "") in set(AccountResolver.ACCOUNT_FIELDS)
        ]
        non_account_fields = [item for item in clarification_fields if item not in account_fields]
        # Keep the established account-selection interaction for the simple
        # account-only case. A request with both an account and other missing
        # data stays an inline clarification so users do not receive a
        # fragmented sequence of popups.
        if account_fields and not non_account_fields:
            platform = str(account_fields[0].get("platform") or "目标平台")
            confirmation_payload = {
                "type": "ask_account",
                "platform": platform,
                "question": f"请提供要操作的 {platform} 广告账户 ID。",
            }
            reply = confirmation_payload["question"]
        trace.stage_status(
            "action_clarification",
            "补充执行信息",
            "awaiting_confirmation",
            subtitle="等待用户明确资源范围和必填参数",
            safe_metadata={"reason": "required_parameters"},
            safe_output={
                "field_count": len(clarification.get("fields", []) or {})
                if isinstance(clarification, Mapping) else 0,
            },
        )
        self.set_action_draft(session_id, {
            "intent": intent.to_dict(),
            "clarification": clarification,
        })
        trace.reply()
        trace.done("awaiting_confirmation", safe_metadata={
            "reason": "action_clarification", "tool_count": 0,
        })
        self.persist_conversation_turn(
            session, turn_id, user_input, reply, execution_trace=trace, ui=ui,
        )
        updater = getattr(self._session_manager, "update_execution_run", None)
        if callable(updater):
            try:
                updater(str(run_id), status="awaiting_confirmation")
            except Exception:
                logger.debug("failed to finalize action clarification run", exc_info=True)
        response_results = []
        if confirmation_payload:
            response_results.append({
                "tool": str(account_fields[0].get("tool") or "account_scope"),
                "platform": str(account_fields[0].get("platform") or ""),
                "success": False,
                "data": {},
                "error": "缺少账户ID",
                "needs_confirmation": True,
                "confirmation_payload": confirmation_payload,
            })
        return {
            "session_id": session_id,
            "run_id": run_id,
            "turn_id": turn_id,
            "timestamp": datetime.now().isoformat(),
            "intent": intent.to_dict(),
            "tool_plan": {},
            "execution_plan": {},
            "tool_selection": None,
            "memory": recalled_memories,
            "memory_updates": memory_updates,
            "results": response_results,
            "response_source": "action_clarification",
            "reply": reply,
            "needs_confirmation": bool(confirmation_payload),
            "needs_input": True,
            "confirmation_payload": confirmation_payload,
            "workflow_id": None,
            "ui": dict(ui),
        }
    def list_ad_formats(
        self, platform: Optional[str] = None, coverage: Optional[str] = None
    ) -> list[dict[str, Any]]:
        """Return JSON-safe format coverage metadata for UI/planners."""
        if coverage is not None:
            coverage = str(coverage).strip().lower()
            if coverage not in {item.value for item in AdFormatCoverage}:
                raise ValueError(f"unsupported ad format coverage: {coverage}")
        platforms = [self._canonical_platform(platform)] if platform else sorted(
            self.ad_format_catalogs
        )
        result: list[dict[str, Any]] = []
        for current in platforms:
            for entry in self.ad_format_catalogs.get(current, []):
                if coverage and entry.get("coverage") != coverage:
                    continue
                result.append({"platform": current, **dict(entry)})
        return result

    def list_parameter_options(
        self, platform: Optional[str] = None, field: Optional[str] = None,
        tool_name: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Return JSON-safe static or dynamic provider parameter metadata."""
        return [
            catalog.to_dict()
            for catalog in self.parameter_catalogs.list(
                platform=platform, field=field, tool_name=tool_name
            )
        ]

    def list_creation_blueprints(
        self, provider: Optional[str] = None, ad_format: Optional[str] = None,
        selector_dimension: Optional[str] = None, selector_value: Any = None,
    ) -> list[dict[str, Any]]:
        """Return provider-owned creation metadata without making network calls."""
        result = []
        for blueprint in self.creation_blueprints.list(
            provider, ad_format, selector_dimension, selector_value
        ):
            expanded = self.creation_card_builder.expand_blueprint(blueprint)
            document = expanded.to_dict()
            document["support"] = self._creation_blueprint_support(expanded)
            result.append(document)
        return result

    @staticmethod
    def _creation_format_tokens(value: Any) -> set[str]:
        return {
            token for token in re.split(r"[^a-z0-9]+", str(value or "").casefold())
            if token
        }

    def _creation_blueprint_support(self, blueprint: Any) -> dict[str, Any]:
        """Attach catalog evidence without inventing provider mappings."""
        suffix = str(getattr(blueprint, "blueprint_id", "")).rsplit(".", 1)[-1]
        blueprint_tokens = (
            self._creation_format_tokens(suffix)
            | self._creation_format_tokens(getattr(blueprint, "ad_format", ""))
        )
        candidates: list[tuple[int, Mapping[str, Any]]] = []
        for entry in self.ad_format_catalogs.get(str(getattr(blueprint, "provider", "")), []) or []:
            if not isinstance(entry, Mapping):
                continue
            format_id = str(entry.get("format_id") or "")
            category = str(entry.get("category") or "")
            format_key = format_id.casefold()
            suffix_key = suffix.casefold()
            score = 0
            if format_key == suffix_key:
                score = 100
            elif format_key == str(getattr(blueprint, "ad_format", "")).casefold():
                score = 100
            elif category and category.casefold() == suffix_key:
                score = 80
            elif blueprint_tokens & (
                self._creation_format_tokens(format_id)
                | self._creation_format_tokens(category)
            ):
                score = 60
            if score:
                candidates.append((score, entry))
        if not candidates:
            return {
                "level": "contract_only",
                "label": "已接入字段合同",
                "catalog_match": False,
                "gaps": ["尚未关联渠道广告类型目录"],
            }
        _score, entry = sorted(candidates, key=lambda item: (-item[0], str(item[1].get("format_id"))))[0]
        coverage = str(entry.get("coverage") or "contract_only")
        labels = {
            "supported_dry_run": "支持草稿校验",
            "partial_dry_run": "部分支持草稿",
            "declared_only": "暂不支持向导创建",
            "contract_only": "已接入字段合同",
        }
        return {
            "level": coverage,
            "label": labels.get(coverage, coverage),
            "catalog_match": True,
            "catalog_format": entry.get("format_id"),
            "dependencies": list(entry.get("dependencies") or [])[:8],
            "gaps": list(entry.get("gaps") or [])[:8],
        }

    def resolve_creation_blueprint(
        self,
        provider: str,
        *,
        selector_values: Optional[Mapping[str, Any]] = None,
        values: Optional[Mapping[str, Any]] = None,
        version: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        """Resolve provider-owned creation metadata from declarative selectors."""
        blueprint = self.creation_blueprints.resolve(
            provider,
            selector_values=selector_values,
            values=values,
            version=version,
        )
        return (
            self.creation_card_builder.expand_blueprint(blueprint).to_dict()
            if blueprint is not None else None
        )

    def evaluate_creation_blueprint(
        self,
        blueprint_id: str,
        values: Mapping[str, Any],
        *,
        version: Optional[str] = None,
        previous_values: Optional[Mapping[str, Any]] = None,
        changed_fields: Optional[Iterable[str]] = None,
    ) -> dict[str, Any]:
        """Evaluate cascade state for a registered Blueprint deterministically."""
        blueprint = self.creation_blueprints.get(blueprint_id, version)
        if blueprint is None:
            raise KeyError(f"creation blueprint not found: {blueprint_id}@{version or 'latest'}")
        blueprint = self.creation_card_builder.expand_blueprint(blueprint)
        # The cascade engine stays provider-neutral. Runtime only supplies the
        # enum portion of the already-registered Tool schema so a Blueprint can
        # use ``option_rules`` even when its base options are inherited from a
        # Tool rather than duplicated in JSON.
        option_sources: dict[str, list[Any]] = {}
        for field in blueprint.fields:
            tool_name, schema_path = str(field["tool_ref"]).split(".", 1)
            try:
                definition, _handler = self._get_registered_tool(tool_name)
            except (KeyError, LookupError, ValueError):
                continue
            properties = getattr(getattr(definition, "input_schema", None), "properties", {}) or {}
            schema = _schema_at_path(properties, schema_path) or {}
            enum = schema.get("enum") if isinstance(schema, Mapping) else None
            if not isinstance(enum, list) and isinstance(schema, Mapping) and isinstance(schema.get("items"), Mapping):
                enum = schema["items"].get("enum")
            if isinstance(enum, list):
                option_sources[str(field["path"])] = list(enum)
        return self.blueprint_cascade.evaluate(
            blueprint,
            values,
            previous_values=previous_values,
            changed_fields=changed_fields,
            option_sources=option_sources,
        )

    def build_creation_ui(
        self,
        intent: ParsedIntent,
        tool_plan: Optional[Mapping[str, Any]] = None,
    ) -> dict[str, Any]:
        """Build safe conversational creation cards without executing Tools."""
        try:
            cards = self.creation_card_builder.build(intent, tool_plan=tool_plan)
        except Exception:
            logger.exception("构建广告创建参数卡失败")
            cards = []
        if not cards:
            return {}
        return self._redact_for_persistence({
            "cards": cards,
            "schema_version": "1.0",
            "needs_input": any(
                bool(card.get("missing_fields") or card.get("invalid_fields"))
                for card in cards
            ),
        })

    @staticmethod
    def _is_campaign_only_plan(
        tool_plan: Optional[Mapping[str, Any]],
        intent: Optional[Any] = None,
    ) -> bool:
        """Return whether a provider-declared plan contains only Campaign.

        Campaign-only smoke tests are an explicit Tool contract, not a
        Runtime intent-name special case.  The provider Capability marks the
        selected Tool with ``campaign_only``; ordinary creation routes keep
        their complete Blueprint and descendant validation.
        """
        tools = [
            tool
            for routed in (tool_plan or {}).values()
            for tool in (routed or ())
        ]
        intent_type = str(getattr(intent, "intent_type", "") or "").strip()
        # A Tool may advertise a broad primary intent plus a narrower
        # lifecycle intent.  Only the latter is an explicit opt-in to this
        # scope; a generic creation request that happens to route to one
        # Campaign (because its format is incomplete) must still open the
        # full Blueprint and collect descendants.
        explicit_scope = any(
            intent_type in {
                str(item).strip()
                for item in (getattr(tool, "intent_types", []) or [])[1:]
            }
            for tool in tools
        )
        return bool(tools) and explicit_scope and all(
            str(getattr(tool, "action", "") or "").strip().lower() == "create"
            and str(getattr(tool, "resource_type", "") or "").strip().lower()
            == "campaign"
            and "campaign_only" in {
                str(item).strip().lower()
                for item in (getattr(tool, "traits", []) or [])
            }
            for tool in tools
        )

    def _creation_blueprint_tool_plan(
        self,
        blueprint_id: Optional[str],
        blueprint_version: Optional[str],
        intent: ParsedIntent,
    ) -> tuple[Optional[dict[str, list[Any]]], Optional[str]]:
        """Resolve a submitted Blueprint into its declared Tool composition.

        A form submission is a structured continuation of an earlier turn.
        Re-parsing its short UI label can select one leaf Tool (for example an
        ad) instead of the Blueprint's complete parent-to-child chain. The
        Blueprint remains the source of composition; this method only reads
        its already-validated Tool references and never contains provider
        names or business field branches.
        """
        if not blueprint_id:
            return None, None
        blueprint = self.creation_blueprints.get(blueprint_id, blueprint_version)
        if blueprint is None:
            return None, f"广告创建蓝图不存在：{blueprint_id}@{blueprint_version or 'latest'}"
        requested_platforms = {
            self._canonical_platform(platform)
            for platform in (getattr(intent, "namespaces", []) or [])
        }
        blueprint_platform = self._canonical_platform(blueprint.provider)
        if requested_platforms and requested_platforms != {blueprint_platform}:
            return None, "广告创建蓝图与当前请求的平台不一致，请重新打开对应向导。"
        definitions = []
        missing_tools = []
        for tool_name in blueprint.tools:
            try:
                definition, _handler = self.registry.get(tool_name)
            except (KeyError, LookupError):
                missing_tools.append(str(tool_name))
                continue
            if self._canonical_platform(definition.namespace) != blueprint_platform:
                missing_tools.append(str(tool_name))
                continue
            definitions.append(definition)
        if missing_tools:
            return None, "广告创建蓝图依赖的能力暂不可用：" + ", ".join(missing_tools[:8])
        if not definitions:
            return None, "广告创建蓝图没有可用的创建能力。"
        ordered = SimpleIntentRouter._order_by_resource_dependencies(definitions)
        return {blueprint_platform: ordered}, None

    @staticmethod
    def creation_ui_reply(ui: Mapping[str, Any], user_input: str = "") -> str:
        """Explain an incomplete creation draft in operator-friendly language.

        The card remains the rich interaction surface, but this reply is a
        complete text fallback.  It describes legal enum choices, lookup
        selection, manual-ID boundaries and cascade dependencies so an
        operator can continue without opening the card.
        """
        is_english = bool(user_input) and not re.search(r"[\u3400-\u9fff]", user_input)
        cards = ui.get("cards") if isinstance(ui, Mapping) else []
        titles = [
            str(card.get("title") or "广告创建")
            for card in cards or []
            if isinstance(card, Mapping)
        ]
        selector_cards = [
            card for card in cards or []
            if isinstance(card, Mapping) and card.get("type") == "ad_creation_selector"
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
            missing_account = bool(selector_cards[0].get("account_required") and not selector_cards[0].get("account_id"))
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
                account_text = "Provide the advertiser/account ID (it is never guessed). " if missing_account else ""
                options_text = f"Available choices: {choice_text} " if choice_text else ""
                return (
                    f"I identified a {provider} ad creation request. {account_text}"
                    f"{options_text}Choose a campaign goal or ad format, then I will show only the parameters"
                    " allowed for that combination. You can also continue in plain language."
                    " Once the details are complete, I will show a final preview and wait for your confirmation before submitting."
                )
            choice_text = "；".join(choices)
            account_text = "请提供要操作的广告账户 ID（请人工填写，系统不会猜测账户）。" if missing_account else ""
            options_text = f"当前可选：{choice_text}。" if choice_text else ""
            return (
                f"我识别到你要在 {provider} 创建广告。{account_text}{options_text}"
                "你可以直接用文字继续补充目标、类型和参数；选定后我只展示该组合允许的字段。"
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
                card.get("account_required") and not str(card.get("account_id") or "").strip()
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

        # Keep account scope visible even when the Blueprint has no other
        # missing fields. It is a user decision, not an inferred default.
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
                    rendered.append(str(shown) if str(shown) == str(value) else f"{shown} ({value})")
                suffix = " or more" if len(options) > 6 else ""
                return f"{label}: " + ", ".join(rendered) + suffix
            lookup = field.get("lookup")
            if isinstance(lookup, Mapping) or str(field.get("source") or "").lower() == "lookup":
                tool = str((lookup or {}).get("tool") or "resource list") if isinstance(lookup, Mapping) else "resource list"
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
                return f"{label}: choose {dep_text} first" if english else f"{label}：请先完成 {dep_text}"
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
            if invalid_labels:
                action = "Please correct"
            elif pending_labels:
                action = "Please provide"
            else:
                action = "You can review the preview"
            details = "; ".join(field_help(field, True) for field in focus_fields)
            if account_missing:
                details = "Account/advertiser ID (enter it manually; it will not be guessed)" + ("; " + details if details else "")
            if not details:
                details = ", ".join(visible_labels)
            return (
                f"I identified {subject}. {action}: {details}. "
                "You may reply in plain language, for example: “Use account [ID], choose Android, "
                "optimize for app installs, and set a daily budget of 100.” "
                "I will validate the combination, show a final preview, and submit only after your confirmation."
            )
        if invalid_labels:
            action = "请先修改"
        elif pending_labels:
            action = "还需要补充"
        else:
            action = "你可以先查看下方预览"
        details = "；".join(field_help(field) for field in focus_fields)
        if account_missing:
            details = "请提供要操作的广告账户 ID（请人工填写，系统不会猜测）" + ("；" + details if details else "")
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

    def _creation_contract_preflight(
        self,
        intent: ParsedIntent,
        tool_plan: Mapping[str, Iterable[Any]],
        session: "SessionContext",
        account_id: str,
    ) -> list[dict[str, Any]]:
        """Validate the complete creation chain before any Tool is executed.

        Parent IDs are generated by the preceding create step at execution
        time, so they receive a bounded planning placeholder here. All user
        and provider-contract fields are still validated against the actual
        Tool schema, including minItems and conditional requirements. This
        keeps an invalid child creative from partially creating its parents.
        """
        issues: list[dict[str, Any]] = []
        original_account = session.ctx.account_id
        session.ctx.account_id = account_id
        try:
            for platform, tools in tool_plan.items():
                actual_platform = self._canonical_platform(platform)
                for tool_def in tools:
                    if not tool_def.is_write_tool or not tool_def.input_schema:
                        continue
                    tool_input = self.input_builder.build(
                        tool_def, intent, platform, session.ctx
                    )
                    unknown = tool_input.pop("_unknown_params", []) or []
                    selection_errors = tool_input.pop("_selection_errors", []) or []
                    missing = list(tool_input.pop("_missing_params", []) or [])

                    parent_field = self._parent_resource_id_field_for_tool(tool_def)
                    if parent_field in missing:
                        # The parent create Tool will supply this ID. It is
                        # intentionally never exposed as a user-fillable ID.
                        tool_input[parent_field] = f"__planned_{parent_field}__"
                        missing.remove(parent_field)
                    for field_name in missing:
                        issues.append({
                            "tool": tool_def.name,
                            "platform": actual_platform,
                            "field": str(field_name),
                            "message": f"Missing required field: {field_name}",
                        })
                    for field_name in unknown:
                        issues.append({
                            "tool": tool_def.name,
                            "platform": actual_platform,
                            "field": str(field_name),
                            "message": f"Field '{field_name}' is not allowed",
                        })
                    for message in selection_errors:
                        issues.append({
                            "tool": tool_def.name,
                            "platform": actual_platform,
                            "field": "selection",
                            "message": str(message),
                        })
                    schema_errors = validate_tool_input(
                        tool_def.input_schema,
                        tool_input,
                        include_capability_contract=True,
                    )
                    for message in schema_errors:
                        field_match = re.search(r"Field '([^']+)'", str(message))
                        if field_match is None:
                            field_match = re.search(
                                r"Provider contract requires field:\s*([A-Za-z0-9_.-]+)",
                                str(message),
                            )
                        issues.append({
                            "tool": tool_def.name,
                            "platform": actual_platform,
                            "field": field_match.group(1) if field_match else "",
                            "message": str(message),
                        })
        finally:
            session.ctx.account_id = original_account
        return issues

    @staticmethod
    def _creation_contract_reply(
        ui: Mapping[str, Any], issues: Iterable[Mapping[str, Any]]
    ) -> str:
        """Turn schema errors into concise operator-facing corrections."""
        label_by_key: dict[tuple[str, str], str] = {}
        for card in ui.get("cards", []) if isinstance(ui, Mapping) else []:
            if not isinstance(card, Mapping):
                continue
            for field in card.get("fields", []) or []:
                if not isinstance(field, Mapping):
                    continue
                label = str(field.get("label") or field.get("path") or "参数")
                tool = str(field.get("tool") or "")
                provider_field = str(field.get("provider_field") or "")
                path = str(field.get("path") or "")
                for key in ((tool, provider_field), (tool, path), ("", provider_field), ("", path)):
                    if key[1]:
                        label_by_key.setdefault(key, label)

        details: list[str] = []
        issue_list = [item for item in issues if isinstance(item, Mapping)]
        exact_fields = {
            str(item.get("field") or "")
            for item in issue_list
        }
        for issue in issue_list:
            tool = str(issue.get("tool") or "")
            field = str(issue.get("field") or "")
            message = str(issue.get("message") or "")
            # A short item-type error (for example headlines[0] must be an
            # object) is secondary when the same field already reports its
            # actionable minimum count. Keep the operator message focused.
            if "[" in field and field.split("[", 1)[0] in exact_fields:
                continue
            label = label_by_key.get((tool, field)) or label_by_key.get(("", field))
            count_match = re.search(r"at least (\d+) items?/characters", message)
            if count_match and label:
                detail = f"{label}至少需要 {count_match.group(1)} 项"
            elif message.startswith("Missing required field:") and label:
                detail = f"请补充{label}"
            elif "Provider contract requires field:" in message and label:
                detail = f"请补充{label}"
            elif label:
                detail = f"{label}需要调整"
            else:
                detail = "有一项创建参数不符合平台要求"
            if detail not in details:
                details.append(detail)
        details = details[:8]
        return (
            "提交前检查发现以下内容还不符合当前广告类型的要求："
            + "；".join(details)
            + "。本次没有创建任何广告资源，请返回卡片补充或调整后再提交。"
        )

    def resolve_parameter_options(
        self,
        platform: str,
        field: str,
        tool_name: str,
        account_id: Optional[str] = None,
        *,
        session_id: Optional[str] = None,
        user_id: str = "parameter-options",
        tenant_id: str = "default",
        account_scope: Optional[Mapping[str, set[str]]] = None,
        granted_permissions: Optional[set[str] | frozenset[str]] = None,
        lookup_context: Optional[Mapping[str, Any]] = None,
        query: Optional[str] = None,
    ) -> dict[str, Any]:
        """Resolve one dynamic catalog through a registered read Tool.

        The metadata endpoint intentionally does not make network calls. This
        explicit resolver is the provider-backed counterpart for a form/UI:
        it reuses the normal account, permission, timeout and read-data
        boundaries, then returns short-lived selection tokens that are bound
        to this user/session/account/tool/field context.
        """
        actual_platform = self._canonical_platform(platform)
        catalog = self.parameter_catalogs.get(actual_platform, field, tool_name)
        if catalog is None:
            raise KeyError(
                f"parameter catalog not found for {actual_platform}.{field} ({tool_name})"
            )
        if catalog.source != "lookup":
            return catalog.to_dict()
        source_tool = str(catalog.lookup_tool or "")
        definition, _handler = self._get_registered_tool(source_tool)
        if not definition.is_read_tool:
            raise PermissionError("parameter lookup source must be read-only")
        if self._canonical_platform(definition.namespace) != actual_platform:
            raise ValueError("parameter lookup source belongs to a different platform")
        account_value = str(account_id or "").strip()
        source_properties = getattr(definition.input_schema, "properties", {}) or {}
        source_required = set(getattr(definition.input_schema, "required", []) or [])
        account_fields = {"account_id", "advertiser_id", "customer_id"}
        # A provider may explicitly declare that a reference catalog is
        # global (for example TikTok Apps or locations), even when a shared
        # source schema contains an optional account-shaped field.  The
        # provider contract wins over Runtime inference; absent an explicit
        # declaration we conservatively require the account when the source
        # Tool does.
        account_required = (
            bool(catalog.account_required)
            if catalog.account_required is not None
            else bool(source_required.intersection(account_fields))
        )
        if account_required and not account_value:
            raise ValueError("该查询需要先提供广告账户 ID，才能加载可用选项")
        if account_value:
            allowed, account_error = self._validate_account_with_principal(
                actual_platform, account_value, False, account_scope
            )
            if not allowed:
                raise PermissionError(account_error)
        permissions = self._granted_permissions if granted_permissions is None else frozenset(granted_permissions)
        permission_error = self._check_tool_permissions(definition, permissions)
        if permission_error:
            raise PermissionError(permission_error)

        session = self._ensure_session(
            session_id or str(uuid.uuid4()), user_id, account_value,
            None, tenant_id=tenant_id,
        )
        session.ctx.account_id = account_value
        input_data: dict[str, Any] = {}
        properties = source_properties
        for account_field in ("account_id", "advertiser_id", "customer_id"):
            if account_field in properties and account_value:
                input_data[account_field] = account_value
                break
        for field_name, default_value in (catalog.lookup_defaults or {}).items():
            if field_name in properties and field_name not in input_data:
                input_data[str(field_name)] = copy.deepcopy(default_value)
        context_values = dict(lookup_context or {})
        dependencies = list(catalog.dependencies or ())
        for dependency in dependencies:
            if not isinstance(dependency, Mapping):
                raise ValueError("lookup dependency metadata must be an object")
            input_field = str(
                dependency.get("input_field") or dependency.get("field") or ""
            ).strip()
            value_path = str(
                dependency.get("value_path") or dependency.get("source_field")
                or input_field
            ).strip()
            if not input_field or input_field not in properties:
                raise ValueError(
                    f"lookup dependency points to undeclared source field: {input_field or value_path}"
                )
            value = context_values.get(value_path)
            if value is None and "." in value_path:
                value = self.input_builder._value_at_path(context_values, value_path)
            if value in (None, "", [], {}):
                if dependency.get("required", True):
                    label = str(dependency.get("label") or value_path)
                    raise ValueError(f"请先选择或填写{label}，再加载当前字段的可用选项")
                continue
            input_data[input_field] = value
        query_field = catalog.query_field
        if query and query_field:
            if query_field not in properties:
                raise ValueError(f"lookup query field is not declared by source Tool: {query_field}")
            input_data[query_field] = str(query).strip()
        missing_source = sorted(
            field_name for field_name in source_required
            if field_name not in input_data
            and not (
                field_name in account_fields
                and catalog.account_required is False
            )
        )
        if missing_source:
            raise ValueError(
                "当前查询还缺少必要的上级条件：" + "、".join(missing_source)
            )
        result = self.tool_executor.execute(session.ctx, source_tool, input_data)
        result = self.input_builder.decorate_lookup_result(
            definition, result, session.ctx, actual_platform,
            target_tool_name=tool_name,
            target_field=field,
        )
        result = self.security.enforce_result_limit(result, definition)
        if not result.success:
            raise RuntimeError(result.error or "parameter lookup failed")
        for selection in result.data.get("parameter_selections", []):
            if (
                selection.get("tool_name") == tool_name
                and selection.get("field") == field
            ):
                return selection
        raise RuntimeError(
            f"provider lookup {source_tool} returned no options for {tool_name}.{field}"
        )

    def _validate_parameter_lookup_contract(self) -> None:
        """Ensure dynamic fields point to executable same-provider read tools.

        A lookup descriptor is part of the Skill contract, not a free-form
        hint. Failing at registration keeps a typo or a write-tool reference
        from reaching the UI as a selectable option that Runtime cannot
        safely attest later.
        """
        definitions = {tool.name: tool for tool in self.registry.list_all()}
        errors: list[str] = []
        for tool in definitions.values():
            properties = getattr(tool.input_schema, "properties", {}) or {}
            for field_name, field_schema in self.input_builder._iter_schema_fields(properties):
                lookup_tool = self.input_builder.lookup_tool_for_schema_field(
                    field_schema
                )
                if not lookup_tool:
                    continue
                source = definitions.get(lookup_tool)
                if source is None:
                    errors.append(
                        f"{tool.name}.{field_name} references unknown lookup tool {lookup_tool}"
                    )
                    continue
                tool_platform = self._canonical_platform(tool.namespace)
                source_platform = self._canonical_platform(source.namespace)
                if tool_platform != source_platform:
                    errors.append(
                        f"{tool.name}.{field_name} lookup tool {lookup_tool} "
                        f"belongs to {source_platform}, not {tool_platform}"
                    )
                if not source.is_read_tool:
                    errors.append(
                        f"{tool.name}.{field_name} lookup tool {lookup_tool} must be read-only"
                    )
        if errors:
            raise ValueError("Invalid parameter lookup contract: " + "; ".join(errors[:20]))

    def _creation_input_response(
        self,
        *,
        session: "SessionContext",
        session_id: str,
        run_id: str,
        turn_id: str,
        user_input: str,
        reply: str,
        intent: ParsedIntent,
        ui: Mapping[str, Any],
        trace: ExecutionTrace,
        recalled_memories: list[dict[str, Any]],
        memory_updates: list[dict[str, Any]],
        reason: str,
    ) -> dict[str, Any]:
        """Finish a clarification turn without materializing Tool nodes."""
        trace.stage_status(
            "creation_clarification",
            "创建需求澄清" if reason == "creation_selector_required" else "创建参数收集",
            "awaiting_confirmation",
            subtitle="等待补充明确的广告类型和必填参数",
            safe_metadata={"reason": reason},
            safe_output={
                "provider": (ui.get("clarification") or {}).get("provider")
                if isinstance(ui, Mapping) else None,
                "card_count": len(ui.get("cards", []) or []) if isinstance(ui, Mapping) else 0,
            },
        )
        self.set_creation_draft(session_id, {"intent": intent.to_dict(), "reason": reason})
        trace.reply()
        trace.done("awaiting_confirmation", safe_metadata={"reason": reason, "tool_count": 0})
        self.persist_conversation_turn(
            session, turn_id, user_input, reply, execution_trace=trace, ui=ui,
        )
        updater = getattr(self._session_manager, "update_execution_run", None)
        if callable(updater):
            try:
                updater(str(run_id), status="awaiting_confirmation")
            except Exception:
                logger.debug("failed to finalize clarification execution run", exc_info=True)
        return {
            "session_id": session_id,
            "run_id": run_id,
            "turn_id": turn_id,
            "timestamp": datetime.now().isoformat(),
            "intent": intent.to_dict(),
            "tool_plan": {},
            "execution_plan": {},
            "tool_selection": None,
            "memory": recalled_memories,
            "memory_updates": memory_updates,
            "results": [],
            "response_source": (
                "creation_clarification"
                if reason == "creation_selector_required" else "creation_card"
            ),
            "reply": reply,
            "needs_confirmation": False,
            "needs_input": True,
            "confirmation_payload": None,
            "workflow_id": None,
            "ui": dict(ui),
        }

    def _creation_policy_response(
        self,
        *,
        session: "SessionContext",
        session_id: str,
        run_id: str,
        turn_id: str,
        user_input: str,
        intent: ParsedIntent,
        trace: ExecutionTrace,
        error: str,
    ) -> dict[str, Any]:
        """Reject an out-of-scope explicit account before clarification."""
        trace.error(reason="account_scope_denied")
        trace.done("failed", safe_metadata={"reason": "account_scope_denied"})
        reply = "❌ " + str(error)
        self.persist_conversation_turn(
            session, turn_id, user_input, reply, execution_trace=trace,
        )
        updater = getattr(self._session_manager, "update_execution_run", None)
        if callable(updater):
            try:
                updater(str(run_id), status="failed")
            except Exception:
                logger.debug("failed to finalize creation policy run", exc_info=True)
        return {
            "session_id": session_id,
            "run_id": run_id,
            "turn_id": turn_id,
            "timestamp": datetime.now().isoformat(),
            "intent": intent.to_dict(),
            "tool_plan": {},
            "execution_plan": {},
            "tool_selection": None,
            "results": [],
            "reply": reply,
            "needs_confirmation": False,
            "needs_input": False,
            "confirmation_payload": None,
            "policy_errors": [str(error)],
            "workflow_id": None,
            "ui": {},
        }

    def preflight_scheduled_prompt(
        self, prompt: str, *, session_id: str,
        platforms: Optional[list[str]] = None,
        account_id: Optional[str] = None,
        platform_params: Optional[dict[str, Any]] = None,
        permissions: Optional[set[str] | frozenset[str]] = None,
        account_scope: Optional[Mapping[str, Any]] = None,
    ) -> dict[str, Any]:
        """Check a scheduled instruction against the live Tool Registry.

        This is metadata-only: it parses and routes a normal Agent request but
        never calls a Tool or Provider. The scheduled turn still repeats this
        check at execution time because Skills, schemas and permissions may
        change between creation and the next occurrence.
        """
        text = str(prompt or "").strip()
        if not text:
            return {"status": "needs_input", "missing": ["instruction"], "reason": "请补充到期后要执行的具体指令。"}
        session = self._sessions.get(str(session_id or ""))
        if session is None:
            return {"status": "needs_input", "missing": ["session"], "reason": "当前会话上下文尚未准备好，无法完成能力预检。"}
        try:
            candidate = self.intent_parser.parse(text, session.ctx)
        except Exception as exc:
            logger.info("scheduled prompt preflight parse failed", exc_info=True)
            return {
                "status": "unsupported", "missing": [],
                "reason": "无法识别定时任务到期后的具体业务动作，请说明查询、分析、创建或其他动作。",
                "parse_error": type(exc).__name__,
            }
        supplied_platforms = [
            str(item).strip() for item in (platforms or []) if str(item).strip()
        ]
        if supplied_platforms:
            candidate.namespaces = list(dict.fromkeys(supplied_platforms))
        if platform_params:
            merged_params = dict(getattr(candidate, "scoped_parameters", {}) or {})
            for platform, values in platform_params.items():
                if isinstance(values, dict):
                    merged = dict(merged_params.get(platform, {}) or {})
                    merged.update(values)
                    merged_params[str(platform)] = merged
            candidate.platform_params = merged_params
        is_control_intent = any(
            bool(getattr(feature, "is_control_intent", lambda _intent: False)(candidate))
            for feature in self.features
        )
        if str(getattr(candidate, "intent_type", "") or "") == "chat" or is_control_intent:
            return {
                "status": "needs_input", "missing": ["action"],
                "reason": "请明确到期后要执行的业务动作，例如查询资源 performance 或创建资源。",
            }
        if not candidate.namespaces:
            return {
                "status": "needs_input", "missing": ["platform"],
                "reason": "请明确一个当前已注册的执行渠道，或说明需要跨渠道处理。",
                "intent_type": candidate.intent_type,
            }
        plan = self.intent_router.route(candidate, self.registry)
        if not plan:
            return {
                "status": "unsupported", "missing": [],
                "reason": "当前已注册的 Tool/Capability 没有匹配该动作和渠道的执行能力。",
                "intent_type": candidate.intent_type,
                "platforms": list(candidate.namespaces),
            }
        account_values = []
        if account_id not in (None, ""):
            account_values.append(str(account_id))
        for values in (getattr(candidate, "scoped_parameters", {}) or {}).values():
            if not isinstance(values, dict):
                continue
            for field_name in ("account_id", "advertiser_id", "customer_id"):
                if values.get(field_name) not in (None, ""):
                    account_values.append(str(values[field_name]))
        account_values = list(dict.fromkeys(account_values))
        if len(account_values) > 1:
            return {
                "status": "needs_input", "missing": ["account"],
                "reason": "请求中出现多个不同广告账户，请明确每个渠道使用的账户。",
                "intent_type": candidate.intent_type,
                "platforms": list(plan),
                "account_candidates": account_values[:10],
            }
        if not account_values:
            return {
                "status": "needs_input", "missing": ["account"],
                "reason": "请明确要使用的广告账户，并确保当前身份有该账户权限。",
                "intent_type": candidate.intent_type,
                "platforms": list(plan),
            }
        matched_tools = [
            definition for definitions in plan.values() for definition in definitions
        ]
        permission_errors = []
        for definition in matched_tools:
            error = self._check_tool_permissions(definition, permissions)
            if error and error not in permission_errors:
                permission_errors.append(error)
        if permission_errors:
            return {
                "status": "unsupported", "missing": [],
                "reason": "；".join(permission_errors),
                "intent_type": candidate.intent_type,
                "platforms": list(plan),
            }
        write_tools = [definition for definition in matched_tools if definition.is_write_tool]
        account_errors = []
        if account_scope is not None or self.enforce_account_scope:
            for platform in plan:
                platform_account = account_values[0]
                allowed, account_error = self._validate_account_with_principal(
                    platform, platform_account, bool(write_tools), account_scope,
                )
                if not allowed and account_error not in account_errors:
                    account_errors.append(account_error)
        if account_errors:
            return {
                "status": "unsupported", "missing": [],
                "reason": "；".join(account_errors),
                "intent_type": candidate.intent_type,
                "platforms": list(plan),
            }
        # A matched intent is not enough to declare a future run executable:
        # the selected Tool contract may still require resource IDs or other
        # structured fields. Check only the declarative required contract here;
        # no lookup or Provider call is allowed during schedule creation.
        platform_params_by_canonical: dict[str, dict[str, Any]] = {}
        for platform_name, values in (getattr(candidate, "scoped_parameters", {}) or {}).items():
            if not isinstance(values, dict):
                continue
            canonical = self._canonical_platform(str(platform_name))
            current = platform_params_by_canonical.setdefault(canonical, {})
            current.update(values)
        missing_parameters: dict[str, list[str]] = {}
        ready_tools: list[Any] = []
        for platform, definitions in plan.items():
            canonical = self._canonical_platform(str(platform))
            supplied = dict(platform_params_by_canonical.get(canonical, {}))
            candidates_ready = False
            platform_missing: set[str] = set()
            for definition in definitions:
                schema = getattr(definition, "input_schema", None)
                properties = getattr(schema, "properties", {}) if schema else {}
                properties = properties if isinstance(properties, Mapping) else {}
                candidate_input = {
                    key: value for key, value in supplied.items() if key in properties
                }
                for field_name in ("account_id", "advertiser_id", "customer_id"):
                    if field_name in properties and account_values:
                        candidate_input.setdefault(field_name, account_values[0])
                required = [
                    str(field_name) for field_name in (getattr(schema, "required", []) or [])
                ]
                required.extend(
                    str(field_name)
                    for field_name in (getattr(schema, "capability_required", []) or [])
                    if str(field_name) not in required
                )
                missing = {
                    field_name for field_name in required
                    if candidate_input.get(field_name) in (None, "", {}, [])
                }
                for alternatives in (
                    (getattr(schema, "capability_any_of", []) or [])
                    if schema else ()
                ):
                    if not any(candidate_input.get(str(field_name)) not in (None, "", {}, []) for field_name in alternatives):
                        missing.add("one_of:" + "|".join(str(field_name) for field_name in alternatives))
                if not missing:
                    candidates_ready = True
                    ready_tools.append(definition)
                else:
                    platform_missing.update(missing)
            if not candidates_ready and platform_missing:
                missing_parameters[canonical] = sorted(platform_missing)
        if missing_parameters:
            formatted = [
                f"{platform}: {', '.join(fields)}"
                for platform, fields in sorted(missing_parameters.items())
            ]
            return {
                "status": "needs_input", "missing": [
                    "parameter:" + field
                    for fields in missing_parameters.values()
                    for field in fields
                ],
                "reason": "匹配的 Tool 还缺少必填参数：" + "；".join(formatted),
                "intent_type": candidate.intent_type,
                "platforms": list(plan),
                "missing_parameters": missing_parameters,
            }
        if ready_tools:
            matched_tools = ready_tools
            write_tools = [definition for definition in matched_tools if definition.is_write_tool]
        return {
            "status": "ready",
            "intent_type": candidate.intent_type,
            "platforms": list(plan),
            "tool_names": [str(definition.name) for definition in matched_tools],
            "effects": ["write" if write_tools else "read"],
            "write_tools": [str(definition.name) for definition in write_tools],
            "account_id": account_values[0],
            "execution_mode": "dry_run",
            "reason": "已匹配当前 Registry 的 Tool/Capability；到期执行仍会重新校验。",
        }
