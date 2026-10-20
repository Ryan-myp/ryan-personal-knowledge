from __future__ import annotations

from copy import deepcopy
from datetime import date, timedelta

from agents.agent_harness.core.interfaces import ToolContext, ToolEffect
from agents.agent_harness.core.tool_registry import validate_tool_input
from agents.applications.advertising.composition.ad_application import AdvertisingComposition
from agents.applications.advertising.persistence.store import AdAgentStore
from agents.tools.advertising.shared.budget_analysis import (
    MINIMUM_WEEKLY_OBSERVATIONS,
    cross_channel_budget_analysis_tool_source,
)
from agents.tools.advertising.providers.google import create_google_tool_source
from agents.tools.advertising.providers.google.reports import GoogleGetReportHandler
from agents.tools.advertising.providers.dv360 import create_dv360_tool_source
from agents.tools.advertising.providers.meta import create_meta_tool_source
from agents.tools.advertising.providers.meta.reports import MetaGetReportHandler
from agents.tools.advertising.providers.tiktok import create_tiktok_tool_source
from agents.tools.advertising.providers.tiktok.reports import TikTokGetReportHandler


def _platform(
    name: str,
    *,
    source_tool: str,
    current_budget: float,
    outcome_scale: float,
    currency: str = "USD",
    data_status: str = "live",
    count: int = MINIMUM_WEEKLY_OBSERVATIONS,
    timezone: str = "America/Los_Angeles",
    attribution_model: str = "last_click",
    attribution_window_days: int = 28,
    outcome_definition: str = "purchase_value",
) -> dict:
    start = date(2025, 1, 6)
    observations = []
    for week in range(count):
        spend = 1000.0 + week * 25.0 + (week % 3) * 100.0
        observations.append({
            "week_start": (start + timedelta(days=7 * week)).isoformat(),
            "spend": spend,
            "conversions": outcome_scale * (20.0 + week),
            "revenue": outcome_scale * (500.0 + 30.0 * week),
        })
    return {
        "platform": name,
        "source_tool": source_tool,
        "data_status": data_status,
        "currency": currency,
        "timezone": timezone,
        "attribution_model": attribution_model,
        "attribution_window_days": attribution_window_days,
        "outcome_definition": outcome_definition,
        "current_weekly_budget": current_budget,
        "minimum_weekly_budget": 0,
        "maximum_weekly_budget": 1000,
        "observations": observations,
    }


def _valid_input() -> dict:
    start = date(2025, 1, 6)
    end = start + timedelta(days=7 * MINIMUM_WEEKLY_OBSERVATIONS - 1)
    return {
        "total_weekly_budget": 1000,
        "objective": "revenue",
        "window_start": start.isoformat(),
        "window_end": end.isoformat(),
        "data_as_of": (end + timedelta(days=35)).isoformat(),
        "currency": "USD",
        "timezone": "America/Los_Angeles",
        "attribution_model": "last_click",
        "attribution_window_days": 28,
        "outcome_definition": "purchase_value",
        "platforms": [
            _platform(
                "meta",
                source_tool="meta_get_campaign_report",
                current_budget=600,
                outcome_scale=1,
            ),
            _platform(
                "google-ads",
                source_tool="google_get_campaign_report",
                current_budget=400,
                outcome_scale=2,
            ),
        ],
    }


def _execute(data: dict):
    binding = cross_channel_budget_analysis_tool_source().list_bindings()[0]
    return binding.executor.execute(
        ToolContext(session_id="budget-test", user_id="operator"),
        data,
    )


def test_budget_analysis_is_a_registered_read_only_tool_with_owned_intent():
    binding = cross_channel_budget_analysis_tool_source().list_bindings()[0]
    definition = binding.definition

    assert definition.name == "advertising_cross_channel_budget_analysis"
    assert definition.intent_types == ["cross_channel_optimize_budget"]
    assert definition.effect_class == ToolEffect.READ
    assert definition.replay_policy.value == "safe"
    assert definition.required_permissions == ["ads.read"]
    assert definition.scope_required is False
    assert "outcome_definition" in definition.input_schema.required


def test_budget_tool_schema_rejects_missing_outcome_definition():
    definition = cross_channel_budget_analysis_tool_source().list_bindings()[0].definition
    payload = _valid_input()
    payload.pop("outcome_definition")

    errors = validate_tool_input(definition.input_schema, payload)

    assert any("outcome_definition" in error for error in errors)


def test_budget_tool_returns_advisory_only_and_uses_comparable_mature_history():
    result = _execute(_valid_input())

    assert result.success is True
    assert result.data["status"] == "available"
    assert result.data["model_type"] == "historical_efficiency_heuristic"
    assert result.data["automatic_write"] is False
    assert result.data["evidence_validation"] == (
        "caller_asserted_provider_reports_not_independently_verified"
    )
    recommendations = {
        row["platform"]: row for row in result.data["recommendations"]
    }
    assert recommendations["google-ads"]["recommended_weekly_budget"] > (
        recommendations["meta"]["recommended_weekly_budget"]
    )
    assert sum(
        row["recommended_weekly_budget"]
        for row in recommendations.values()
    ) == 1000
    assert result.data["current_proportional_baseline"]["google-ads"] == 400
    assert "marginal" in result.data["limitations"].lower()


def test_budget_tool_blocks_currency_and_attribution_mismatches():
    payload = _valid_input()
    payload["platforms"][1]["currency"] = "EUR"
    currency_result = _execute(payload)
    assert currency_result.data["status"] == "blocked"
    assert "币种" in currency_result.data["reason"]

    payload = _valid_input()
    payload["attribution_model"] = ""
    attribution_result = _execute(payload)
    assert attribution_result.data["status"] == "blocked"
    assert "归因" in attribution_result.data["reason"]

    payload = _valid_input()
    payload["platforms"][1]["attribution_window_days"] = 7
    window_result = _execute(payload)
    assert window_result.data["status"] == "blocked"
    assert "归因窗口" in window_result.data["reason"]


def test_budget_tool_blocks_stale_or_insufficient_history():
    payload = _valid_input()
    payload["data_as_of"] = payload["window_end"]
    stale_result = _execute(payload)
    assert stale_result.data["status"] == "blocked"
    assert "成熟" in stale_result.data["reason"]

    payload = _valid_input()
    payload["platforms"][0] = _platform(
        "meta",
        source_tool="meta_get_campaign_report",
        current_budget=600,
        outcome_scale=1,
        count=MINIMUM_WEEKLY_OBSERVATIONS - 1,
    )
    short_result = _execute(payload)
    assert short_result.data["status"] == "blocked"
    assert "周" in short_result.data["reason"]


def test_budget_tool_blocks_non_live_and_zero_signal_instead_of_equal_fallback():
    payload = _valid_input()
    payload["platforms"][0]["data_status"] = "offline_mock"
    offline_result = _execute(payload)
    assert offline_result.data["status"] == "blocked"
    assert "live" in offline_result.data["reason"]

    payload = _valid_input()
    for platform in payload["platforms"]:
        for observation in platform["observations"]:
            observation["revenue"] = 0
    zero_result = _execute(payload)
    assert zero_result.data["status"] == "blocked"
    assert "有效" in zero_result.data["reason"]


def test_budget_tool_accepts_account_level_tiktok_report_as_evidence_source():
    payload = _valid_input()
    payload["platforms"][0] = _platform(
        "tiktok",
        source_tool="tiktok_get_report",
        current_budget=600,
        outcome_scale=1,
    )

    result = _execute(payload)

    assert result.data["status"] == "available"


def test_budget_tool_validates_periods_and_bounds_without_mutating_input():
    payload = _valid_input()
    original = deepcopy(payload)
    payload["platforms"][0]["observations"][5]["week_start"] = "2025-02-20"
    gaps_result = _execute(payload)
    assert gaps_result.data["status"] == "blocked"
    assert "连续" in gaps_result.data["reason"]

    payload = deepcopy(original)
    payload["total_weekly_budget"] = 2500
    bounds_result = _execute(payload)
    assert bounds_result.data["status"] == "blocked"
    assert "上限" in bounds_result.data["reason"]
    assert original["total_weekly_budget"] == 1000


def test_budget_tool_preserves_total_at_currency_precision_and_rejects_subunit():
    payload = _valid_input()
    payload["total_weekly_budget"] = 1000.03
    result = _execute(payload)

    assert result.data["status"] == "available"
    assert sum(
        row["recommended_weekly_budget"]
        for row in result.data["recommendations"]
    ) == 1000.03

    payload = _valid_input()
    payload["total_weekly_budget"] = 1000.001
    result = _execute(payload)
    assert result.data["status"] == "blocked"
    assert "最小单位" in result.data["reason"]


def test_budget_tool_uses_zero_decimal_currency_precision_and_bounds_amounts():
    payload = _valid_input()
    payload["currency"] = "JPY"
    payload["total_weekly_budget"] = 1000
    for platform in payload["platforms"]:
        platform["currency"] = "JPY"
        platform["minimum_weekly_budget"] = 0
        platform["maximum_weekly_budget"] = 1000
    result = _execute(payload)

    assert result.data["status"] == "available"
    assert sum(
        row["recommended_weekly_budget"]
        for row in result.data["recommendations"]
    ) == 1000

    payload["total_weekly_budget"] = 1_000_000_000_001
    result = _execute(payload)
    assert result.data["status"] == "blocked"
    assert "不能超过" in result.data["reason"]


def test_budget_tool_blocks_report_metric_overflow():
    payload = _valid_input()
    for platform in payload["platforms"]:
        for observation in platform["observations"]:
            observation["spend"] = 1e308
            observation["revenue"] = 1e308

    result = _execute(payload)

    assert result.data["status"] == "blocked"
    assert "超出可计算范围" in result.data["reason"]


def test_budget_tool_is_registered_by_the_advertising_composition():
    runtime = AdvertisingComposition(
        require_llm=False,
        offline_mode=True,
        persistence_store=AdAgentStore(":memory:"),
    )
    try:
        definition, _handler = runtime._get_registered_tool(
            "advertising_cross_channel_budget_analysis"
        )
        assert definition.intent_types == ["cross_channel_optimize_budget"]
        assert definition.effect_class == ToolEffect.READ
    finally:
        runtime.close(wait=True)


def test_campaign_list_tools_do_not_claim_budget_optimization_intent():
    for source_factory in (
        create_google_tool_source,
        create_meta_tool_source,
        create_tiktok_tool_source,
        create_dv360_tool_source,
    ):
        source = source_factory()
        campaign_list = next(
            binding.definition
            for binding in source.list_bindings()
            if binding.definition.action == "list"
            and binding.definition.resource_type == "campaign"
        )
        assert "cross_channel_optimize_budget" not in campaign_list.intent_types


def test_meta_report_tool_exposes_weekly_historical_query_contract():
    source = create_meta_tool_source()
    definition = next(
        binding.definition
        for binding in source.list_bindings()
        if binding.definition.name == "meta_get_campaign_report"
    )

    assert "time_increment" in definition.input_schema.properties
    assert "date_range" in definition.input_schema.properties


def test_meta_report_handler_forwards_explicit_weekly_window():
    class Client:
        def __init__(self):
            self.args = None

        def get_campaign_report(self, *args, **kwargs):
            self.args = (args, kwargs)
            return []

    client = Client()
    result = MetaGetReportHandler(client).execute(
        ToolContext(
            session_id="budget-meta-report",
            user_id="operator",
            scope={"account_id": "meta-test-account"},
        ),
        {
            "campaign_ids": ["campaign-1"],
            "date_range": {
                "since": "2025-01-06",
                "until": "2025-03-30",
            },
            "time_increment": 7,
        },
    )

    assert result.success is True
    assert client.args[1]["time_range"] == {
        "since": "2025-01-06",
        "until": "2025-03-30",
    }
    assert client.args[1]["time_increment"] == 7


def test_google_report_contract_accepts_explicit_historical_dates():
    source = create_google_tool_source()
    definition = next(
        binding.definition
        for binding in source.list_bindings()
        if binding.definition.name == "google_get_campaign_report"
    )

    assert "start_date" in definition.input_schema.properties
    assert "end_date" in definition.input_schema.properties


def test_google_report_handler_forwards_explicit_historical_dates():
    class Client:
        def __init__(self):
            self.args = None

        def get_campaign_report(self, **kwargs):
            self.args = kwargs
            return []

    client = Client()
    result = GoogleGetReportHandler(client).execute(
        ToolContext(
            session_id="budget-google-report",
            user_id="operator",
            account_id="google-test-account",
        ),
        {
            "campaign_ids": ["campaign-1"],
            "start_date": "2025-01-06",
            "end_date": "2025-03-30",
        },
    )

    assert result.success is True
    assert client.args["date_from"] == "2025-01-06"
    assert client.args["date_to"] == "2025-03-30"


def test_tiktok_campaign_report_contract_supports_daily_historical_metrics():
    source = create_tiktok_tool_source()
    definition = next(
        binding.definition
        for binding in source.list_bindings()
        if binding.definition.name == "tiktok_get_campaign_report"
    )

    assert definition.input_schema.properties["date_range"]["type"] == [
        "string", "object",
    ]
    assert "metrics" in definition.input_schema.properties
    assert "dimensions" in definition.input_schema.properties
    valid_input = {
        "account_id": "tiktok-test-account",
        "campaign_ids": ["campaign-1"],
        "date_range": {
            "start_date": "2025-01-06",
            "end_date": "2025-01-12",
        },
        "metrics": ["spend", "conversion"],
        "dimensions": ["campaign_id", "stat_time_day"],
    }
    assert validate_tool_input(definition.input_schema, valid_input) == []
    valid_input["dimensions"] = ["unreviewed_dimension"]
    assert validate_tool_input(definition.input_schema, valid_input)

    valid_input["dimensions"] = ["campaign_id", "stat_time_day"]
    valid_input["date_range"] = {"start_date": "2025-01-06"}
    assert any(
        "end_date" in error
        for error in validate_tool_input(definition.input_schema, valid_input)
    )


def test_tiktok_campaign_report_handler_forwards_date_metrics_and_dimensions():
    class Client:
        def __init__(self):
            self.args = None

        def get_campaign_report(self, **kwargs):
            self.args = kwargs
            return []

    client = Client()
    result = TikTokGetReportHandler(client).execute(
        ToolContext(
            session_id="budget-tiktok-report",
            user_id="operator",
            account_id="tiktok-test-account",
        ),
        {
            "campaign_ids": ["campaign-1"],
            "date_range": {
                "start_date": "2025-01-06",
                "end_date": "2025-01-12",
            },
            "metrics": ["spend", "conversion"],
            "dimensions": ["campaign_id", "stat_time_day"],
        },
    )

    assert result.success is True
    assert client.args == {
        "advertiser_id": "tiktok-test-account",
        "campaign_ids": ["campaign-1"],
        "time_range": {
            "start_date": "2025-01-06",
            "end_date": "2025-01-12",
        },
        "metrics": ["spend", "conversion"],
        "dimensions": ["campaign_id", "stat_time_day"],
    }
