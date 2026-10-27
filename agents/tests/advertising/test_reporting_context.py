from types import SimpleNamespace

from agents.agent_harness.core.interfaces import ToolContext
from agents.tools.advertising.providers.provider_tools import method_tool
from agents.tools.advertising.providers.google.reports import GoogleGetReportHandler
from agents.tools.advertising.providers.meta.reports import MetaGetReportHandler
from agents.tools.advertising.providers.tiktok.reports import TikTokGetReportHandler
from agents.tools.advertising.shared.domain.reporting import build_report_context


def test_report_context_preserves_requested_period_and_exposes_unknowns():
    context = build_report_context(
        provider="google-ads",
        resource_level="ad",
        input_data={
            "start_date": "2026-10-01",
            "end_date": "2026-10-07",
            "limit": 2,
        },
        rows=[{"id": "a1"}, {"id": "a2"}],
        default_period={"start": "LAST_30_DAYS", "end": "TODAY"},
        default_limit=1000,
    )

    assert context == {
        "provider": "google-ads",
        "resource_level": "ad",
        "period": {
            "value": {"start_date": "2026-10-01", "end_date": "2026-10-07"},
            "source": "tool_input",
        },
        "account_timezone": {"value": None, "status": "unknown"},
        "account_currency": {"value": None, "status": "unknown"},
        "attribution": {"value": None, "status": "not_returned_by_tool"},
        "completeness": {
            "returned_rows": 2,
            "row_limit": 2,
            "may_be_truncated": True,
            "status": "possibly_truncated",
        },
    }


def test_report_context_uses_provider_default_and_marks_empty_response():
    context = build_report_context(
        provider="meta",
        resource_level="campaign",
        input_data={},
        rows=[],
        default_period="last_7d",
        default_limit=1000,
    )

    assert context["period"] == {
        "value": "last_7d",
        "source": "provider_default",
    }
    assert context["completeness"] == {
        "returned_rows": 0,
        "row_limit": 1000,
        "may_be_truncated": False,
        "status": "empty",
    }


def test_provider_method_tool_attaches_context_without_rewriting_report_rows():
    report_rows = [{"campaign_id": "c1", "impressions": 20}]
    _, handler = method_tool(
        namespace="test",
        skill="test",
        name="test_get_report",
        description="Read a test report.",
        method_name="get_report",
        result_key="report",
        properties={"date_range": {"type": "string"}},
        argument_builder=lambda _ctx, data: ((), {"date_range": data.get("date_range")}),
        action="report",
        resource_type="campaign",
        result_context_builder=lambda _ctx, data, rows: build_report_context(
            provider="test",
            resource_level="campaign",
            input_data=data,
            rows=rows,
            default_period="LAST_7_DAYS",
            default_limit=100,
        ),
    )
    handler.client = SimpleNamespace(
        get_report=lambda date_range=None: report_rows
    )

    result = handler.execute(
        ToolContext(session_id="s1", user_id="u1"),
        {"date_range": "2026-10-01/2026-10-07"},
    )

    assert result.success is True
    assert result.data["report"] is report_rows
    assert result.data["report_context"]["period"]["source"] == "tool_input"
    assert result.data["report_context"]["completeness"]["returned_rows"] == 1


def test_platform_campaign_report_handlers_attach_context_to_live_results():
    rows = [{"campaign_id": "c1", "impressions": 20}]

    class GoogleClient:
        customer_id = ""

        def get_campaign_report(self, **_kwargs):
            return rows

    class MetaClient:
        def get_campaign_report(self, *_args, **_kwargs):
            return rows

    class TikTokClient:
        def get_campaign_report(self, **_kwargs):
            return rows

    context = ToolContext(
        session_id="s1",
        user_id="u1",
        scope={"account_id": "test-account"},
    )
    cases = (
        (
            GoogleGetReportHandler(GoogleClient()),
            {"date_range": "LAST_7_DAYS"},
            "google-ads",
        ),
        (
            MetaGetReportHandler(MetaClient()),
            {"date_range": {"since": "2026-10-01", "until": "2026-10-07"}},
            "meta",
        ),
        (
            TikTokGetReportHandler(TikTokClient()),
            {"campaign_ids": ["c1"], "date_range": {
                "start_date": "2026-10-01",
                "end_date": "2026-10-07",
            }},
            "tiktok",
        ),
    )

    for handler, inputs, provider in cases:
        result = handler.execute(context, inputs)
        assert result.success is True
        assert result.data["report"] is rows
        assert result.data["report_context"]["provider"] == provider
        assert result.data["report_context"]["completeness"]["returned_rows"] == 1


def test_empty_google_campaign_report_has_no_observed_metric_totals():
    summary = GoogleGetReportHandler()._summarize_report([])
    assert summary["campaign_count"] == 0
    assert summary["total_impressions"] is None
    assert summary["total_clicks"] is None
    assert summary["total_spend"] is None
    assert summary["total_conversions"] is None
