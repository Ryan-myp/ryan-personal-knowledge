"""Read-only cross-channel budget analysis over caller-supplied report history."""

from __future__ import annotations

import math
from datetime import date, timedelta
from typing import Any, Mapping
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from agents.agent_harness import StaticToolSource, ToolBinding
from agents.agent_harness.core.interfaces import (
    ReplayPolicy,
    RiskLevel,
    ToolContext,
    ToolDefinition,
    ToolEffect,
    ToolResult,
    ToolSchema,
)


MINIMUM_WEEKLY_OBSERVATIONS = 8
_MINIMUM_REPORTING_LAG_DAYS = 7
_MAX_PLATFORMS = 8
_MAX_WEEKLY_BUDGET = 1_000_000_000_000
_CURRENCY_MINOR_UNITS = {
    "BIF": 0, "CLP": 0, "DJF": 0, "GNF": 0, "ISK": 0, "JPY": 0,
    "KMF": 0, "KRW": 0, "PYG": 0, "RWF": 0, "UGX": 0, "UYI": 0,
    "VND": 0, "VUV": 0, "XAF": 0, "XOF": 0, "XPF": 0,
    "BHD": 3, "IQD": 3, "JOD": 3, "KWD": 3, "LYD": 3, "OMR": 3,
    "TND": 3, "CLF": 4, "UYW": 4,
}
_REPORT_TO_PLATFORM = {
    "google_get_campaign_report": "google-ads",
    "meta_get_campaign_report": "meta",
    "tiktok_get_campaign_report": "tiktok",
    "tiktok_get_report": "tiktok",
    "dv360_get_line_item_report": "dv360",
}
_PLATFORM_ALIASES = {
    "google": "google-ads",
    "google ads": "google-ads",
    "google-ads": "google-ads",
    "meta": "meta",
    "facebook": "meta",
    "tiktok": "tiktok",
    "dv360": "dv360",
}


class _BudgetAnalysisExecutor:
    def execute(self, _ctx: ToolContext, input_data: dict[str, Any]) -> ToolResult:
        try:
            result = self._analyze(input_data)
        except (TypeError, ValueError, OverflowError) as error:
            return ToolResult.ok({
                "status": "blocked",
                "reason": str(error),
                "automatic_write": False,
            })
        return ToolResult.ok(result)

    @classmethod
    def _analyze(cls, data: Mapping[str, Any]) -> dict[str, Any]:
        currency = str(data.get("currency") or "").strip().upper()
        if len(currency) != 3 or not currency.isascii() or not currency.isalpha():
            raise ValueError("必须提供三位币种代码")
        precision = _CURRENCY_MINOR_UNITS.get(currency, 2)
        total_budget = cls._budget_number(
            data.get("total_weekly_budget"), "总周预算", precision
        )
        if total_budget <= 0:
            raise ValueError("总周预算必须大于 0")
        objective = str(data.get("objective") or "").strip().lower()
        if objective not in {"revenue", "conversions"}:
            raise ValueError("目标必须是 revenue 或 conversions")

        window_start = cls._date(data.get("window_start"), "历史窗口开始日期")
        window_end = cls._date(data.get("window_end"), "历史窗口结束日期")
        data_as_of = cls._date(data.get("data_as_of"), "数据截至日期")
        if window_end < window_start:
            raise ValueError("历史窗口结束日期不能早于开始日期")
        if window_start.weekday() != 0:
            raise ValueError("历史窗口必须从周一开始，以保证周粒度一致")
        window_days = (window_end - window_start).days + 1
        if window_days % 7:
            raise ValueError("历史窗口必须由完整、连续的自然周组成")

        attribution_model = str(data.get("attribution_model") or "").strip()
        attribution_window_days = cls._integer(
            data.get("attribution_window_days"), "归因窗口天数"
        )
        if not attribution_model or attribution_window_days <= 0:
            raise ValueError("必须提供一致且有效的归因模型和归因窗口")
        mature_after = window_end + timedelta(
            days=attribution_window_days + _MINIMUM_REPORTING_LAG_DAYS
        )
        if data_as_of < mature_after:
            raise ValueError(
                "历史数据尚未成熟；数据截至日期需晚于窗口结束日、归因窗口和 7 天报告延迟"
            )

        timezone = str(data.get("timezone") or "").strip()
        if not timezone:
            raise ValueError("必须提供账户报告时区")
        try:
            ZoneInfo(timezone)
        except (ZoneInfoNotFoundError, ValueError) as error:
            raise ValueError("账户报告时区必须是有效的 IANA 时区") from error

        outcome_definition = str(data.get("outcome_definition") or "").strip()
        if not outcome_definition:
            raise ValueError("必须提供统一的业务结果定义")
        platforms = data.get("platforms")
        if not isinstance(platforms, list) or not 2 <= len(platforms) <= _MAX_PLATFORMS:
            raise ValueError("必须提供 2 到 8 个渠道的历史数据")
        expected_weeks = window_days // 7
        if expected_weeks < MINIMUM_WEEKLY_OBSERVATIONS:
            raise ValueError(
                f"至少需要 {MINIMUM_WEEKLY_OBSERVATIONS} 个连续成熟周的历史数据"
            )

        rows = []
        names: set[str] = set()
        expected_starts = [
            (window_start + timedelta(days=7 * index)).isoformat()
            for index in range(expected_weeks)
        ]
        for raw_platform in platforms:
            if not isinstance(raw_platform, Mapping):
                raise ValueError("每个渠道都必须是结构化对象")
            row = cls._normalize_platform(
                raw_platform,
                objective=objective,
                currency=currency,
                timezone=timezone,
                attribution_model=attribution_model,
                attribution_window_days=attribution_window_days,
                outcome_definition=outcome_definition,
                currency_precision=precision,
                expected_starts=expected_starts,
            )
            if row["platform"] in names:
                raise ValueError("渠道不能重复")
            names.add(row["platform"])
            rows.append(row)

        minimum_sum = math.fsum(row["minimum"] for row in rows)
        maximum_sum = math.fsum(row["maximum"] for row in rows)
        if minimum_sum > total_budget:
            raise ValueError("渠道预算下限总和超过总周预算")
        if maximum_sum < total_budget:
            raise ValueError("渠道预算上限总和不足以覆盖总周预算")

        current_total = math.fsum(row["current"] for row in rows)
        if current_total <= 0:
            raise ValueError("当前渠道周预算总和必须大于 0")
        baseline_raw = {
            row["platform"]: total_budget * row["current"] / current_total
            for row in rows
        }
        baseline = cls._round_to_total(
            total_budget, baseline_raw, rows, precision, respect_bounds=False
        )
        allocations = cls._allocate(total_budget, rows, precision)
        recommendations = [
            {
                "platform": row["platform"],
                "currency": currency,
                "current_weekly_budget": round(row["current"], precision),
                "current_proportional_baseline": baseline[row["platform"]],
                "recommended_weekly_budget": allocations[row["platform"]],
                "historical_efficiency": round(row["efficiency"], 6),
                "observed_weeks": expected_weeks,
            }
            for row in sorted(rows, key=lambda item: item["platform"])
        ]
        return {
            "status": "available",
            "objective": objective,
            "currency": currency,
            "timezone": timezone,
            "window_start": window_start.isoformat(),
            "window_end": window_end.isoformat(),
            "data_as_of": data_as_of.isoformat(),
            "attribution_model": attribution_model,
            "attribution_window_days": attribution_window_days,
            "outcome_definition": outcome_definition,
            "model_type": "historical_efficiency_heuristic",
            "total_weekly_budget": round(total_budget, 2),
            "current_proportional_baseline": baseline,
            "recommendations": recommendations,
            "automatic_write": False,
            "evidence_validation": (
                "caller_asserted_provider_reports_not_independently_verified"
            ),
            "marginal_return_forecast": False,
            "limitations": (
                "这是基于历史平均效率的启发式预算建议，不是边际回报预测、"
                "marginal return forecast、因果结论或 MMM；渠道间口径虽已按输入声明对齐，"
                "来源数据仍需人工核实，建议小步调整并观察边际表现。"
            ),
        }

    @classmethod
    def _normalize_platform(
        cls,
        value: Mapping[str, Any],
        *,
        objective: str,
        currency: str,
        timezone: str,
        attribution_model: str,
        attribution_window_days: int,
        outcome_definition: str,
        currency_precision: int,
        expected_starts: list[str],
    ) -> dict[str, Any]:
        platform_value = str(value.get("platform") or "").strip().casefold()
        platform = _PLATFORM_ALIASES.get(platform_value)
        if not platform:
            raise ValueError(f"不支持的渠道: {platform_value or 'unknown'}")
        source_tool = str(value.get("source_tool") or "").strip()
        if _REPORT_TO_PLATFORM.get(source_tool) != platform:
            raise ValueError(f"{platform} 必须引用该渠道已注册的报表 Tool")
        if str(value.get("data_status") or "").strip().lower() != "live":
            raise ValueError(
                f"{platform} 的历史来源不是 live，禁止用于预算建议"
            )
        if str(value.get("timezone") or "").strip() != timezone:
            raise ValueError("各渠道账户时区必须一致")
        if str(value.get("attribution_model") or "").strip() != attribution_model:
            raise ValueError("各渠道归因模型必须一致")
        if cls._integer(
            value.get("attribution_window_days"),
            f"{platform} 归因窗口天数",
        ) != attribution_window_days:
            raise ValueError("各渠道归因窗口必须一致")
        if str(value.get("outcome_definition") or "").strip() != outcome_definition:
            raise ValueError("各渠道业务结果定义必须一致")
        platform_currency = str(value.get("currency") or "").strip().upper()
        if platform_currency != currency:
            raise ValueError("各渠道币种必须一致，不能直接换算或合并")
        current = cls._budget_number(
            value.get("current_weekly_budget"),
            f"{platform} 当前周预算",
            currency_precision,
        )
        minimum = cls._budget_number(
            value.get("minimum_weekly_budget"),
            f"{platform} 周预算下限",
            currency_precision,
        )
        maximum = cls._budget_number(
            value.get("maximum_weekly_budget"),
            f"{platform} 周预算上限",
            currency_precision,
        )
        if minimum < 0 or maximum < minimum or not minimum <= current <= maximum:
            raise ValueError(f"{platform} 的当前预算或预算上下限不合法")

        observations = value.get("observations")
        if not isinstance(observations, list) or len(observations) != len(expected_starts):
            raise ValueError(
                f"{platform} 必须覆盖窗口内全部连续周，至少 {MINIMUM_WEEKLY_OBSERVATIONS} 周"
            )
        by_week: dict[str, Mapping[str, Any]] = {}
        for observation in observations:
            if not isinstance(observation, Mapping):
                raise ValueError(f"{platform} 的周报数据必须是结构化对象")
            week_start = cls._date(
                observation.get("week_start"), f"{platform} 周起始日期"
            ).isoformat()
            if week_start in by_week:
                raise ValueError(f"{platform} 的周报日期不能重复")
            by_week[week_start] = observation
        if list(sorted(by_week)) != expected_starts:
            raise ValueError(f"{platform} 的历史周数据必须连续且与分析窗口对齐")

        spend = 0.0
        outcome = 0.0
        for week_start in expected_starts:
            observation = by_week[week_start]
            week_spend = cls._number(
                observation.get("spend"), f"{platform} 周花费"
            )
            conversions = cls._number(
                observation.get("conversions"), f"{platform} 周转化"
            )
            revenue = cls._number(
                observation.get("revenue"), f"{platform} 周收入"
            )
            if min(week_spend, conversions, revenue) < 0:
                raise ValueError(f"{platform} 的周报指标不能为负数")
            try:
                spend = math.fsum((spend, week_spend))
                outcome = math.fsum(
                    (outcome, revenue if objective == "revenue" else conversions)
                )
            except OverflowError as error:
                raise ValueError(
                    f"{platform} 的历史报表指标合计超出可计算范围"
                ) from error
        if spend <= 0 or outcome <= 0:
            raise ValueError(
                f"{platform} 没有有效的花费和目标结果信号，不能生成预算建议"
            )
        efficiency = outcome / spend
        if not math.isfinite(efficiency) or efficiency <= 0:
            raise ValueError(f"{platform} 的历史效率超出可计算范围")
        return {
            "platform": platform,
            "current": current,
            "minimum": minimum,
            "maximum": maximum,
            "efficiency": efficiency,
        }

    @classmethod
    def _allocate(
        cls,
        total: float,
        rows: list[dict[str, Any]],
        precision: int,
    ) -> dict[str, float]:
        """Allocate by historical efficiency while honoring declared bounds."""
        ordered = sorted(rows, key=lambda item: item["platform"])
        scales = [
            row["maximum"] / row["efficiency"]
            for row in ordered
            if row["efficiency"] > 0
        ]
        if not scales or not all(math.isfinite(scale) for scale in scales):
            raise ValueError("历史效率无法稳定计算预算分配")
        low, high = 0.0, max(scales)
        for _ in range(80):
            scale = (low + high) / 2
            allocated = math.fsum(
                min(row["maximum"], max(row["minimum"], row["efficiency"] * scale))
                for row in ordered
            )
            if allocated < total:
                low = scale
            else:
                high = scale
        raw = {
            row["platform"]: min(
                row["maximum"],
                max(row["minimum"], row["efficiency"] * high),
            )
            for row in ordered
        }
        return cls._round_to_total(
            total, raw, ordered, precision, respect_bounds=True
        )

    @staticmethod
    def _round_to_total(
        total: float,
        raw: Mapping[str, float],
        rows: list[dict[str, Any]],
        precision: int,
        *,
        respect_bounds: bool,
    ) -> dict[str, float]:
        """Round allocations and distribute the small residual in bounded work."""
        unit = 10 ** -precision
        ordered_rows = sorted(rows, key=lambda row: row["platform"])
        rounded = {key: round(value, precision) for key, value in raw.items()}
        if respect_bounds:
            rounded = {
                row["platform"]: min(
                    row["maximum"],
                    max(row["minimum"], rounded[row["platform"]]),
                )
                for row in ordered_rows
            }
        remaining_units = round(
            (total - math.fsum(rounded.values())) / unit
        )
        if abs(remaining_units) > len(ordered_rows):
            raise ValueError("预算分配数值误差超出可校正范围")
        if remaining_units:
            direction = 1 if remaining_units > 0 else -1
            ranked_rows = sorted(
                ordered_rows,
                key=lambda row: (
                    raw[row["platform"]] - rounded[row["platform"]]
                ),
                reverse=direction > 0,
            )
            for row in ranked_rows:
                if not remaining_units:
                    break
                platform = row["platform"]
                candidate = round(
                    rounded[platform] + direction * unit, precision
                )
                if respect_bounds and not (
                    row["minimum"] <= candidate <= row["maximum"]
                ):
                    continue
                rounded[platform] = candidate
                remaining_units -= direction
        if remaining_units:
            raise ValueError("预算上下限导致无法精确分配总周预算")
        return rounded

    @staticmethod
    def _number(value: Any, label: str) -> float:
        if isinstance(value, bool):
            raise ValueError(f"{label}必须是有限数字")
        try:
            number = float(value)
        except (TypeError, ValueError, OverflowError) as error:
            raise ValueError(f"{label}必须是有限数字") from error
        if not math.isfinite(number):
            raise ValueError(f"{label}必须是有限数字")
        return number

    @classmethod
    def _budget_number(cls, value: Any, label: str, precision: int) -> float:
        number = cls._number(value, label)
        if number > _MAX_WEEKLY_BUDGET:
            raise ValueError(f"{label}不能超过 {_MAX_WEEKLY_BUDGET}")
        unit = 10 ** -precision
        if not math.isclose(
            number / unit,
            round(number / unit),
            rel_tol=0,
            abs_tol=1e-6,
        ):
            raise ValueError(f"{label}的小数位数不符合币种最小单位")
        return round(number, precision)

    @classmethod
    def _integer(cls, value: Any, label: str) -> int:
        number = cls._number(value, label)
        if not number.is_integer():
            raise ValueError(f"{label}必须是整数")
        return int(number)

    @staticmethod
    def _date(value: Any, label: str) -> date:
        try:
            parsed = date.fromisoformat(str(value or ""))
        except (TypeError, ValueError) as error:
            raise ValueError(f"{label}必须使用 YYYY-MM-DD 格式") from error
        if parsed.isoformat() != str(value):
            raise ValueError(f"{label}必须使用 YYYY-MM-DD 格式")
        return parsed


def cross_channel_budget_analysis_tool_source() -> StaticToolSource:
    """Publish a read-only, advisory budget-analysis Tool."""
    definition = ToolDefinition(
        name="advertising_cross_channel_budget_analysis",
        skill="cross-channel",
        namespace="advertising",
        description=(
            "基于多个渠道已查询的成熟、同口径周报计算只读预算建议；"
            "不读取或修改平台资源，不能把历史平均效率解释为边际回报。"
        ),
        input_schema=ToolSchema(
            required=[
                "total_weekly_budget", "objective", "window_start", "window_end",
                "data_as_of", "currency", "timezone", "attribution_model",
                "outcome_definition",
                "attribution_window_days", "platforms",
            ],
            properties={
                "total_weekly_budget": {
                    "type": "number", "exclusiveMinimum": 0,
                    "maximum": _MAX_WEEKLY_BUDGET,
                },
                "objective": {"type": "string", "enum": ["revenue", "conversions"]},
                "window_start": {"type": "string", "format": "date"},
                "window_end": {"type": "string", "format": "date"},
                "data_as_of": {"type": "string", "format": "date"},
                "currency": {"type": "string", "minLength": 3, "maxLength": 3},
                "timezone": {"type": "string", "minLength": 1},
                "attribution_model": {"type": "string", "minLength": 1},
                "outcome_definition": {"type": "string", "minLength": 1},
                "attribution_window_days": {
                    "type": "integer", "minimum": 1, "maximum": 90,
                },
                "platforms": {
                    "type": "array",
                    "minItems": 2,
                    "maxItems": _MAX_PLATFORMS,
                    "items": {
                        "type": "object",
                        "additional_properties": False,
                        "required": [
                            "platform", "source_tool", "data_status",
                            "currency", "current_weekly_budget",
                            "minimum_weekly_budget", "maximum_weekly_budget",
                            "timezone", "attribution_model",
                            "attribution_window_days", "outcome_definition",
                            "observations",
                        ],
                        "properties": {
                            "platform": {"type": "string"},
                            "source_tool": {"type": "string"},
                            "data_status": {"type": "string"},
                            "currency": {"type": "string"},
                            "timezone": {"type": "string"},
                            "attribution_model": {"type": "string"},
                            "attribution_window_days": {
                                "type": "integer", "minimum": 1, "maximum": 90,
                            },
                            "outcome_definition": {"type": "string"},
                            "current_weekly_budget": {
                                "type": "number", "minimum": 0,
                                "maximum": _MAX_WEEKLY_BUDGET,
                            },
                            "minimum_weekly_budget": {
                                "type": "number", "minimum": 0,
                                "maximum": _MAX_WEEKLY_BUDGET,
                            },
                            "maximum_weekly_budget": {
                                "type": "number", "minimum": 0,
                                "maximum": _MAX_WEEKLY_BUDGET,
                            },
                            "observations": {
                                "type": "array",
                                "minItems": MINIMUM_WEEKLY_OBSERVATIONS,
                                "items": {
                                    "type": "object",
                                    "additional_properties": False,
                                    "required": [
                                        "week_start", "spend", "conversions", "revenue",
                                    ],
                                    "properties": {
                                        "week_start": {
                                            "type": "string", "format": "date",
                                        },
                                        "spend": {"type": "number", "minimum": 0},
                                        "conversions": {
                                            "type": "number", "minimum": 0,
                                        },
                                        "revenue": {"type": "number", "minimum": 0},
                                    },
                                },
                            },
                        },
                    },
                },
            },
        ),
        action="analyze",
        resource_type="budget_allocation",
        intent_types=["cross_channel_optimize_budget"],
        intent_aliases=[
            "跨渠道预算优化建议",
            "按历史表现重新分配渠道预算",
            "比较渠道历史效率并规划周预算",
        ],
        risk_level=RiskLevel.LOW,
        effect_class=ToolEffect.READ,
        replay_policy=ReplayPolicy.SAFE,
        traits=["read", "analysis", "cross_channel", "budget"],
        scope_required=False,
        required_permissions=["ads.read"],
        live_support=False,
        timeout_seconds=20,
        max_output_bytes=100_000,
    )
    return StaticToolSource(
        "advertising:shared-budget-analysis",
        [ToolBinding(definition, _BudgetAnalysisExecutor())],
    )


__all__ = [
    "MINIMUM_WEEKLY_OBSERVATIONS",
    "cross_channel_budget_analysis_tool_source",
]
