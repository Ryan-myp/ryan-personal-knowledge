from __future__ import annotations

import json
from typing import Any

from agents.tools.marketing_analytics.google_analytics import (
    google_analytics_tool_source,
)
from agents.tools.marketing_analytics.search_console import (
    search_console_tool_source,
)


class FakeResponse:
    def __init__(self, payload: Any, *, status_code: int = 200) -> None:
        self.status_code = status_code
        self.headers = {"Content-Type": "application/json"}
        self._body = json.dumps(payload).encode("utf-8")
        self.closed = False

    def iter_content(self, chunk_size: int = 16_384):
        for offset in range(0, len(self._body), chunk_size):
            yield self._body[offset:offset + chunk_size]

    def close(self) -> None:
        self.closed = True


def _binding(source, name: str):
    return next(binding for binding in source.list_bindings()
                if binding.definition.name == name)


def _oauth_credentials() -> dict[str, str]:
    return {
        "client_id": "client-id",
        "client_secret": "client-secret",
        "refresh_token": "refresh-token",
    }


def test_analytics_tools_publish_bounded_read_only_contracts():
    sources = (
        google_analytics_tool_source(configuration_provider=_oauth_credentials),
        search_console_tool_source(configuration_provider=_oauth_credentials),
    )

    for source in sources:
        assert source.source_id.startswith("marketing:")
        for binding in source.list_bindings():
            definition = binding.definition
            assert definition.effect_class.value == "read"
            assert definition.risk_level.value == "low"
            assert definition.replay_policy.value == "safe"
            assert definition.required_permissions == ["analytics.read"]
            assert definition.timeout_seconds <= 30
            assert definition.max_output_bytes <= 24_000
            assert definition.integration_api_version
            assert definition.input_schema.additional_properties is False


def test_ga4_tools_use_scoped_oauth_and_map_property_and_report_rows():
    requests_seen: list[tuple[str, dict[str, Any]]] = []

    def post(url, **kwargs):
        requests_seen.append((url, kwargs))
        if url == "https://oauth2.googleapis.com/token":
            return FakeResponse({"access_token": "access-token", "expires_in": 3600})
        return FakeResponse({
            "dimensionHeaders": [{"name": "sessionSourceMedium"}],
            "metricHeaders": [{"name": "sessions", "type": "TYPE_INTEGER"}],
            "rows": [{
                "dimensionValues": [{"value": "google / cpc"}],
                "metricValues": [{"value": "42"}],
            }],
            "rowCount": 1,
        })

    def get(url, **kwargs):
        requests_seen.append((url, kwargs))
        return FakeResponse({
            "accountSummaries": [{
                "account": "accounts/123",
                "displayName": "Marketing",
                "propertySummaries": [{
                    "property": "properties/456",
                    "displayName": "Website",
                }],
            }],
        })

    source = google_analytics_tool_source(
        configuration_provider=_oauth_credentials,
        request_get=get,
        request_post=post,
    )
    properties = _binding(source, "ga4_list_properties").executor.execute(
        None, {},
    )
    report = _binding(source, "ga4_run_report").executor.execute(None, {
        "property_id": "456",
        "start_date": "2026-10-01",
        "end_date": "2026-10-07",
        "dimensions": ["sessionSourceMedium"],
        "metrics": ["sessions"],
        "limit": 100,
    })

    assert properties.success is True
    assert properties.data["properties"] == [{
        "account": "accounts/123",
        "account_name": "Marketing",
        "property_id": "456",
        "property_name": "Website",
    }]
    assert report.success is True
    assert report.data["rows"] == [{
        "sessionSourceMedium": "google / cpc",
        "sessions": 42,
    }]
    assert report.data["data_status"] == "live_external"
    token_requests = [item for item in requests_seen
                      if item[0] == "https://oauth2.googleapis.com/token"]
    assert len(token_requests) == 1
    token_form = token_requests[0][1]["data"]
    assert token_form["refresh_token"] == "refresh-token"
    assert token_form["scope"] == "https://www.googleapis.com/auth/analytics.readonly"


def test_ga4_metadata_returns_property_specific_dimensions_and_metrics():
    def post(url, **_kwargs):
        return FakeResponse({"access_token": "access-token", "expires_in": 3600})

    def get(url, **_kwargs):
        if url.endswith("/metadata"):
            return FakeResponse({
                "dimensions": [{"apiName": "sessionCampaignName", "uiName": "Session campaign"}],
                "metrics": [{"apiName": "sessions", "uiName": "Sessions"}],
            })
        return FakeResponse({"accountSummaries": []})

    source = google_analytics_tool_source(
        configuration_provider=_oauth_credentials,
        request_get=get,
        request_post=post,
    )
    result = _binding(source, "ga4_get_metadata").executor.execute(
        None, {"property_id": "456"},
    )

    assert result.success is True
    assert result.data["dimensions"] == [{
        "name": "sessionCampaignName",
        "label": "Session campaign",
    }]
    assert result.data["metrics"] == [{"name": "sessions", "label": "Sessions"}]


def test_ga4_rejects_invalid_property_and_dates_without_network_calls():
    calls: list[str] = []
    source = google_analytics_tool_source(
        configuration_provider=_oauth_credentials,
        request_get=lambda url, **_kwargs: calls.append(url),
        request_post=lambda url, **_kwargs: calls.append(url),
    )
    result = _binding(source, "ga4_run_report").executor.execute(None, {
        "property_id": "properties/456",
        "start_date": "2026-10-08",
        "end_date": "2026-10-01",
        "metrics": ["sessions"],
    })

    assert result.success is False
    assert calls == []

    invalid_currency = _binding(source, "ga4_run_report").executor.execute(None, {
        "property_id": "456",
        "start_date": "2026-10-01",
        "end_date": "2026-10-07",
        "metrics": ["sessions"],
        "currency_code": "ＡＢＣ",
    })
    assert invalid_currency.success is False
    assert calls == []


def test_ga4_missing_credentials_fail_closed():
    calls: list[str] = []
    source = google_analytics_tool_source(
        configuration_provider=dict,
        request_get=lambda url, **_kwargs: calls.append(url),
        request_post=lambda url, **_kwargs: calls.append(url),
    )
    result = _binding(source, "ga4_list_properties").executor.execute(None, {})

    assert result.success is False
    assert "OAuth" in result.error or "配置" in result.error
    assert calls == []


def test_gsc_tools_list_sites_and_query_search_analytics_rows():
    requests_seen: list[tuple[str, dict[str, Any]]] = []

    def post(url, **kwargs):
        requests_seen.append((url, kwargs))
        if url == "https://oauth2.googleapis.com/token":
            return FakeResponse({"access_token": "access-token", "expires_in": 3600})
        return FakeResponse({
            "rows": [{
                "keys": ["growth ads", "https://example.com/guide"],
                "clicks": 12,
                "impressions": 300,
                "ctr": 0.04,
                "position": 5.5,
            }],
        })

    def get(url, **kwargs):
        requests_seen.append((url, kwargs))
        return FakeResponse({"siteEntry": [{
            "siteUrl": "sc-domain:example.com",
            "permissionLevel": "siteOwner",
        }]})

    source = search_console_tool_source(
        configuration_provider=_oauth_credentials,
        request_get=get,
        request_post=post,
    )
    sites = _binding(source, "gsc_list_sites").executor.execute(None, {})
    report = _binding(source, "gsc_search_analytics").executor.execute(None, {
        "site_url": "sc-domain:example.com",
        "start_date": "2026-10-01",
        "end_date": "2026-10-07",
        "dimensions": ["query", "page"],
        "search_type": "web",
        "row_limit": 250,
    })

    assert sites.success is True
    assert sites.data["sites"] == [{
        "site_url": "sc-domain:example.com",
        "permission_level": "siteOwner",
    }]
    assert report.success is True
    assert report.data["rows"] == [{
        "query": "growth ads",
        "page": "https://example.com/guide",
        "clicks": 12,
        "impressions": 300,
        "ctr": 0.04,
        "position": 5.5,
    }]
    query_request = next(
        item for item in requests_seen
        if item[0].endswith("/searchAnalytics/query")
    )
    assert query_request[1]["json"]["dimensions"] == ["query", "page"]
    token_form = next(
        item[1]["data"] for item in requests_seen
        if item[0] == "https://oauth2.googleapis.com/token"
    )
    assert token_form["scope"] == "https://www.googleapis.com/auth/webmasters.readonly"


def test_gsc_rejects_untrusted_site_url_and_invalid_date_range():
    calls: list[str] = []
    source = search_console_tool_source(
        configuration_provider=_oauth_credentials,
        request_get=lambda url, **_kwargs: calls.append(url),
        request_post=lambda url, **_kwargs: calls.append(url),
    )
    result = _binding(source, "gsc_search_analytics").executor.execute(None, {
        "site_url": "https://user:pass@example.com/path?token=secret",
        "start_date": "2026-10-08",
        "end_date": "2026-10-01",
    })

    assert result.success is False
    assert calls == []


def test_google_api_errors_do_not_echo_oauth_secrets():
    secret = "private-refresh-token"

    def post(url, **_kwargs):
        if url == "https://oauth2.googleapis.com/token":
            return FakeResponse({"error": secret}, status_code=400)
        raise AssertionError("report call should not be reached")

    source = google_analytics_tool_source(
        configuration_provider=lambda: {
            "client_id": "id",
            "client_secret": "secret",
            "refresh_token": secret,
        },
        request_post=post,
    )
    result = _binding(source, "ga4_list_properties").executor.execute(None, {})

    assert result.success is False
    assert secret not in result.error
