"""Advertising presentation adapters kept outside the Run facade."""

from __future__ import annotations

import logging
from typing import Any, Mapping, Optional

from .session_context import SessionContext

logger = logging.getLogger(__name__)


class AdvertisingPresentationService:
    """Build advertising labels and grounded model-backed responses."""

    def __init__(self, runtime: Any) -> None:
        self.runtime = runtime

    @staticmethod
    def clarification_field_label(
        path: str,
        spec: Mapping[str, Any],
    ) -> Optional[str]:
        configured = spec.get("label") or spec.get("title")
        if configured:
            return str(configured)
        return {
            "account_id": "广告账户 ID",
            "ad_account_id": "广告账户 ID",
            "advertiser_id": "广告主 ID",
            "customer_id": "客户账户 ID",
            "campaign_id": "Campaign ID",
            "campaign_ids": "Campaign ID 列表",
            "ad_group_id": "Ad Group ID",
            "adgroup_id": "Ad Group ID",
            "ad_id": "Ad ID",
        }.get(str(path or "").rsplit(".", 1)[-1])

    @staticmethod
    def clarification_field_hint(
        path: str,
        _spec: Mapping[str, Any],
    ) -> Optional[str]:
        if str(path or "").rsplit(".", 1)[-1] in {
            "account_id",
            "ad_account_id",
            "advertiser_id",
            "customer_id",
        }:
            return "请填写当前渠道的广告账户 ID，不能用其他渠道账户代替。"
        return None

    def render_response(
        self,
        user_input: str,
        intent: Any,
        results: list[dict[str, Any]],
        needs_confirmation: bool,
        analysis: Optional[dict[str, Any]] = None,
        session: Optional[SessionContext] = None,
        fallback_reply: Optional[str] = None,
    ) -> tuple[str, str]:
        runtime = self.runtime
        fallback = fallback_reply or runtime.response_renderer.render(
            intent,
            results,
            needs_confirmation,
            analysis=analysis,
        )
        synthesizer = runtime.response_synthesizer
        if synthesizer is None or runtime._llm is None:
            return fallback, "renderer"
        skill_context = runtime._build_skill_context_from_metadata(session)
        try:
            answer = synthesizer.synthesize(
                runtime._llm,
                user_input=user_input,
                intent=intent,
                results=runtime._redact_for_persistence(results),
                knowledge=runtime._redact_for_persistence(
                    skill_context.get("knowledge", [])
                ),
                memory=runtime._redact_for_persistence(
                    skill_context.get("memory", [])
                ),
                analysis=runtime._redact_for_persistence(analysis or {}),
                fallback_reply=fallback,
                needs_confirmation=needs_confirmation,
            )
        except Exception as exc:
            logger.debug(
                "LLM 最终回复生成失败，使用 Renderer 兜底: %s",
                exc,
            )
            answer = None
        return (answer, "llm") if answer else (fallback, "renderer")


__all__ = ["AdvertisingPresentationService"]
