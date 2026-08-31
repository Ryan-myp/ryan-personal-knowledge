"""Business Skill policy adapter.

The business Skill remains a standard natural-language package.  This module
only interprets its optional declarative frontmatter for policy enforcement;
it does not register Tools, create clients, or execute provider requests.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml

from ...core.platform import normalize_platform


@dataclass(frozen=True)
class BusinessSkillPolicy:
    """RuntimePolicy implementation owned by one business Skill."""

    name: str
    allowed_platforms: tuple[str, ...] = ()
    denied_platforms: tuple[str, ...] = ()
    allowed_campaign_types: tuple[str, ...] = ()
    rules: dict[str, Any] = field(default_factory=dict)
    focus_metrics: tuple[str, ...] = ()

    @classmethod
    def from_skill_file(
        cls,
        business_name: str,
        skills_root: Optional[str] = None,
    ) -> "BusinessSkillPolicy":
        root = (
            Path(skills_root)
            if skills_root
            else Path(__file__).resolve().parents[1]
        )
        skill_file = root / "businesses" / business_name / "SKILL.md"
        if not skill_file.exists():
            raise FileNotFoundError(f"Business Skill not found: {skill_file}")
        content = skill_file.read_text(encoding="utf-8")
        match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
        metadata = yaml.safe_load(match.group(1)) if match else {}
        business = metadata.get("business", {}) if isinstance(metadata, dict) else {}
        if not isinstance(business, dict):
            raise ValueError(f"Invalid business metadata in {skill_file}")
        rules = business.get("business_rules") or {}
        if not isinstance(rules, dict):
            raise ValueError(f"Invalid business_rules in {skill_file}")
        return cls(
            name=str(business.get("name") or business_name),
            allowed_platforms=tuple(
                str(value) for value in (business.get("allowed_channels") or [])
            ),
            denied_platforms=tuple(
                str(value) for value in (business.get("disallowed_channels") or [])
            ),
            allowed_campaign_types=tuple(
                str(value) for value in (business.get("allowed_campaign_types") or [])
            ),
            rules=dict(rules),
            focus_metrics=tuple(str(value) for value in (rules.get("focus_metrics") or [])),
        )

    @classmethod
    def from_values(
        cls,
        name: str,
        allowed_platforms: tuple[str, ...] = (),
        denied_platforms: tuple[str, ...] = (),
        allowed_campaign_types: tuple[str, ...] = (),
        rules: Optional[dict[str, Any]] = None,
        focus_metrics: tuple[str, ...] = (),
    ) -> "BusinessSkillPolicy":
        return cls(
            name=name,
            allowed_platforms=tuple(allowed_platforms),
            denied_platforms=tuple(denied_platforms),
            allowed_campaign_types=tuple(allowed_campaign_types),
            rules=dict(rules or {}),
            focus_metrics=tuple(focus_metrics),
        )

    def filter_platforms(self, platforms: list[str] | tuple[str, ...]) -> list[str]:
        allowed, denied = self._platform_sets()
        return [
            platform for platform in platforms
            if normalize_platform(platform) not in denied
            and (not allowed or normalize_platform(platform) in allowed)
        ]

    def validate_intent(self, intent: Any) -> list[str]:
        allowed, denied = self._platform_sets()
        errors: list[str] = []
        for platform in getattr(intent, "platforms", []) or []:
            normalized = normalize_platform(platform)
            if normalized in denied or (allowed and normalized not in allowed):
                errors.append(
                    f"业务 {self.name} 不允许使用 {platform} 渠道"
                )

        rules = self.rules or {}
        if (
            getattr(intent, "intent_type", "") == "create_campaign"
            and self.allowed_campaign_types
        ):
            supplied_types: set[str] = set()
            campaign_type = getattr(intent, "campaign_type", None)
            if campaign_type:
                supplied_types.add(str(campaign_type).upper())
            for params in (getattr(intent, "platform_params", {}) or {}).values():
                if not isinstance(params, dict):
                    continue
                for key in ("campaign_type", "type", "campaignType"):
                    value = params.get(key)
                    if value not in (None, ""):
                        supplied_types.add(str(value).upper())
            allowed_types = {
                str(value).upper() for value in self.allowed_campaign_types
            }
            if not supplied_types:
                errors.append(
                    f"业务 {self.name} 创建 Campaign 必须明确 campaign_type；"
                    f"允许值: {', '.join(sorted(allowed_types))}"
                )
            elif not supplied_types.intersection(allowed_types):
                errors.append(
                    f"Campaign 类型 {', '.join(sorted(supplied_types))} "
                    f"不在业务允许范围内：{', '.join(sorted(allowed_types))}"
                )

        budgets: list[tuple[str, Any]] = []
        budget = getattr(intent, "budget", None)
        if budget is not None:
            budgets.append(("common", budget))
        for platform, params in (getattr(intent, "platform_params", {}) or {}).items():
            if not isinstance(params, dict):
                continue
            for key in ("budget", "daily_budget"):
                if params.get(key) not in (None, ""):
                    budgets.append((str(platform), params[key]))
                    break
        should_check_budget = (
            getattr(intent, "intent_type", "")
            in {"create_campaign", "cross_channel_batch_update_budget"}
            or bool(budgets)
        )
        if should_check_budget:
            minimum = rules.get("min_budget")
            maximum = rules.get("max_budget")
            for scope, raw_budget in budgets:
                try:
                    value = float(raw_budget)
                except (TypeError, ValueError):
                    errors.append(f"{scope} 预算必须是数字")
                    continue
                if minimum is not None and value < float(minimum):
                    errors.append(f"{scope} 预算低于业务下限 {minimum}")
                if maximum is not None and value > float(maximum):
                    errors.append(f"{scope} 预算超过业务上限 {maximum}")
        return list(dict.fromkeys(errors))

    def _platform_sets(self) -> tuple[set[str], set[str]]:
        return (
            {normalize_platform(value) for value in self.allowed_platforms},
            {normalize_platform(value) for value in self.denied_platforms},
        )

    def context_metadata(self) -> dict[str, Any]:
        return {
            "policy": {
                "name": self.name,
                "allowed_platforms": list(self.allowed_platforms),
                "denied_platforms": list(self.denied_platforms),
                "allowed_campaign_types": list(self.allowed_campaign_types),
                "rules": dict(self.rules or {}),
                "focus_metrics": list(self.focus_metrics),
            }
        }
