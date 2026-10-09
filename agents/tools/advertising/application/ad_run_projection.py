"""Project generic Harness Run results into advertising response data."""

from __future__ import annotations

from typing import Any, Mapping, Optional

from agents.agent_harness import redact_for_persistence


class AdvertisingRunProjection:
    """Translate generic Tool results and interactions to the ad UI contract."""

    @staticmethod
    def application_state_from_run(
        runtime: Any,
        payload: Mapping[str, Any],
        session_id: str,
        user_input: str,
    ) -> dict[str, Any]:
        results: list[dict[str, Any]] = []
        planned_tools: list[tuple[str, str]] = []
        tool_types: list[tuple[str, ...]] = []
        interaction_cards: list[dict[str, Any]] = []
        account_selection: Optional[dict[str, Any]] = None
        clarification: Optional[dict[str, Any]] = None
        for item in payload.get("tool_results") or ():
            if not isinstance(item, Mapping):
                continue
            name = str(item.get("name") or "").strip()
            raw = item.get("content")
            result = dict(raw) if isinstance(raw, Mapping) else {
                "success": not bool(item.get("is_error")),
                "error": str(raw or "") if item.get("is_error") else "",
            }
            if name:
                result.setdefault("tool", name)
                try:
                    definition, _handler = runtime.registry.get(name)
                except (KeyError, AttributeError):
                    definition = None
                if definition is not None:
                    namespace = str(getattr(definition, "namespace", "") or "")
                    if namespace:
                        planned_tools.append((name, namespace))
                    result.setdefault("platform", namespace)
                    result.setdefault("action", getattr(definition, "action", ""))
                    result.setdefault(
                        "resource_type", getattr(definition, "resource_type", ""),
                    )
                    tool_types.append(tuple(
                        str(value) for value in (
                            getattr(definition, "intent_types", ()) or ()
                        ) if str(value)
                    ))
            for key in (
                "needs_input", "needs_confirmation", "confirmation_payload",
            ):
                if key in item:
                    result[key] = item[key]
            interaction = item.get("interaction")
            interaction_only = False
            if isinstance(interaction, Mapping):
                result["interaction"] = dict(interaction)
                interaction_only = bool(item.get("needs_input"))
                if interaction.get("type") == "ad_creation_form":
                    card = interaction.get("payload")
                    if isinstance(card, Mapping):
                        interaction_cards.append(dict(card))
                        result["needs_input"] = True
                elif interaction.get("type") == "account_selection":
                    payload_data = interaction.get("payload")
                    if isinstance(payload_data, Mapping):
                        account_selection = dict(payload_data)
                        result["needs_input"] = True
                        interaction_only = True
                elif interaction.get("type") == "action_clarification":
                    payload_data = interaction.get("payload")
                    if isinstance(payload_data, Mapping):
                        clarification = dict(payload_data)
                        result["needs_input"] = True
                        interaction_only = True
            if not interaction_only:
                results.append(result)

        tool_plan: dict[str, list[str]] = {}
        for item in results:
            name = str(item.get("tool") or "")
            namespace = str(item.get("platform") or "")
            if name and namespace:
                tool_plan.setdefault(namespace, []).append(name)
        namespaces = list(dict.fromkeys(
            namespace for _name, namespace in planned_tools if namespace
        ))
        common_intents = set(tool_types[0]) if tool_types else set()
        for values in tool_types[1:]:
            common_intents.intersection_update(values)
        intent_type = next(iter(tool_types[0]), "tool_calls") if tool_types else "chat"
        if common_intents:
            intent_type = next(
                value for value in tool_types[0] if value in common_intents
            )

        session = runtime._sessions.get(str(session_id or ""))
        metadata = getattr(getattr(session, "ctx", None), "metadata", {})
        skill_context = (
            metadata.get("skill_context", {})
            if isinstance(metadata, Mapping) else {}
        )
        skill_context = skill_context if isinstance(skill_context, Mapping) else {}
        confirmation = next((
            item.get("confirmation_payload") for item in results
            if isinstance(item.get("confirmation_payload"), Mapping)
        ), None)
        request_error = str(payload.get("request_validation_error") or "")
        ui = next((
            dict(item["ui"]) for item in results
            if isinstance(item.get("ui"), Mapping)
        ), {})
        if interaction_cards or account_selection or clarification:
            ui = {"schema_version": "1.0"}
            if interaction_cards:
                ui["cards"] = interaction_cards
            if account_selection:
                ui["account_selection"] = account_selection
            if clarification:
                ui["clarification"] = clarification
        return {
            "intent": {
                "intent_type": intent_type,
                "namespaces": namespaces,
                "raw_input": redact_for_persistence(str(user_input or "")),
            },
            "last_results": results,
            "tool_plan": tool_plan,
            "tool_selection": {
                "tools": [name for name, _namespace in planned_tools]
            },
            "memory": list(skill_context.get("memory") or []),
            "memory_updates": list(metadata.get("memory_updates") or [])
            if isinstance(metadata, Mapping) else [],
            "needs_input": bool(
                payload.get("needs_input")
                or interaction_cards
                or account_selection
                or clarification
                or any(
                    item.get("needs_input") or item.get("needs_confirmation")
                    for item in (payload.get("tool_results") or ())
                    if isinstance(item, Mapping)
                )
            ),
            "needs_confirmation": any(
                bool(item.get("needs_confirmation"))
                for item in (payload.get("tool_results") or ())
                if isinstance(item, Mapping)
            ),
            "confirmation_payload": confirmation,
            "ui": ui,
            "clarification": clarification,
            "policy_errors": [request_error] if request_error else [],
            "response_source": "policy" if request_error else "harness",
        }


__all__ = ["AdvertisingRunProjection"]
