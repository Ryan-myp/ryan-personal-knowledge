from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
import requests

from agents.agent_harness.core.interfaces import ReplayPolicy, RiskLevel, ToolEffect
from agents.applications.advertising.composition.ad_application import (
    AdvertisingComposition,
)
from agents.applications.advertising.integrations.mcp.runtime_mcp import (
    RuntimeMCPServers,
)
from agents.agent_platform.tools.public_data import (
    MAX_RESPONSE_BYTES,
    public_data_tool_source,
)
from agents.agent_platform.governance.identity.principal import RequestPrincipal


class FakeResponse:
    def __init__(self, payload=None, *, status_code=200, headers=None, body=None):
        self.status_code = status_code
        self.headers = headers or {}
        self.body = (
            body if body is not None
            else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        )
        self.closed = False

    def iter_content(self, chunk_size):
        for offset in range(0, len(self.body), chunk_size):
            yield self.body[offset:offset + chunk_size]

    def close(self):
        self.closed = True


def _bindings(request_get=None):
    source = public_data_tool_source(
        required_permission="ads.read",
        request_get=request_get,
    )
    return source, {
        binding.definition.name: binding
        for binding in source.list_bindings()
    }


def _execute(binding, arguments):
    context = SimpleNamespace(
        request=SimpleNamespace(
            principal=SimpleNamespace(
                user_id="user-a",
                tenant_id="tenant-a",
                permissions=frozenset({"ads.read"}),
            ),
        ),
    )
    return binding.executor.execute(context, arguments)


def test_public_data_tools_are_read_only_bounded_and_categorized():
    source, bindings = _bindings()

    assert source.source_id == "agent-platform:public-data"
    assert set(bindings) == {
        "public_calendar_bank_holidays",
        "public_economics_country_indicator",
        "public_finance_exchange_rate",
    }
    expected_namespaces = {
        "public_calendar_bank_holidays": "public-calendar",
        "public_economics_country_indicator": "public-economics",
        "public_finance_exchange_rate": "public-finance",
    }
    for name, binding in bindings.items():
        definition = binding.definition
        assert definition.namespace == expected_namespaces[name]
        assert definition.effect_class is ToolEffect.READ
        assert definition.risk_level is RiskLevel.LOW
        assert definition.replay_policy is ReplayPolicy.SAFE
        assert definition.skill_refs == ["web-research"]
        assert definition.required_permissions == ["ads.read"]
        assert definition.scope_required is False
        assert definition.timeout_seconds <= 15
        assert definition.max_output_bytes <= 32_000
        assert definition.input_schema.additional_properties is False
        assert "public_data" in definition.traits
    assert bindings["public_finance_exchange_rate"].definition.contract_version == "1.1.0"


def test_exchange_rate_uses_fixed_endpoint_and_projects_public_data():
    response = FakeResponse({
        "date": "2026-10-21",
        "base": "USD",
        "quote": "EUR",
        "rate": 0.89,
        "extra": "must not leak",
    })
    calls = []

    def request_get(url, **kwargs):
        calls.append((url, kwargs))
        return response

    _, bindings = _bindings(request_get)
    result = _execute(bindings["public_finance_exchange_rate"], {
        "base_currency": "USD",
        "quote_currency": "EUR",
        "date": "2026-10-21",
    })

    assert result.success is True
    assert result.data["base"] == "USD"
    assert result.data["quote"] == "EUR"
    assert result.data["rate"] == 0.89
    assert result.data["source"] == "Frankfurter"
    assert (
        result.data["source_url"]
        == "https://api.frankfurter.dev/v2/rate/USD/EUR?date=2026-10-21"
    )
    assert "extra" not in result.data
    url, options = calls[0]
    assert url == "https://api.frankfurter.dev/v2/rate/USD/EUR"
    assert options["params"] == {"date": "2026-10-21"}
    assert options["timeout"] == (3, 8)
    assert options["allow_redirects"] is False
    assert options["stream"] is True
    assert response.closed is True


def test_exchange_rate_supports_bounded_date_range_for_trend_charts():
    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=1)
    start_text, end_text = start.isoformat(), today.isoformat()
    response = FakeResponse([
        {"date": end_text, "base": "USD", "quote": "CNY", "rate": 7.12},
        {
            "date": start_text, "base": "USD", "quote": "CNY",
            "rate": 7.11, "provider_payload": "must not leak",
        },
    ])
    calls = []

    def request_get(url, **kwargs):
        calls.append((url, kwargs))
        return response

    _, bindings = _bindings(request_get)
    result = _execute(bindings["public_finance_exchange_rate"], {
        "base_currency": "USD",
        "quote_currency": "CNY",
        "start_date": start_text,
        "end_date": end_text,
    })

    assert result.success is True
    assert result.data["count"] == 2
    assert result.data["records"] == [
        {"date": start_text, "rate": 7.11},
        {"date": end_text, "rate": 7.12},
    ]
    assert result.data["source_url"] == (
        "https://api.frankfurter.dev/v2/rates?base=USD&quotes=CNY"
        f"&from={start_text}&to={end_text}"
    )
    assert calls[0][0] == "https://api.frankfurter.dev/v2/rates"
    assert calls[0][1]["params"] == {
        "base": "USD", "quotes": "CNY",
        "from": start_text, "to": end_text,
    }
    assert response.closed is True


def test_exchange_rate_lookback_days_uses_inclusive_bounded_window():
    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=29)
    response = FakeResponse([
        {"date": today.isoformat(), "base": "USD", "quote": "CNY", "rate": 7.1},
    ])
    calls = []
    _, bindings = _bindings(
        lambda url, **kwargs: calls.append((url, kwargs)) or response
    )

    result = _execute(bindings["public_finance_exchange_rate"], {
        "base_currency": "USD",
        "quote_currency": "CNY",
        "lookback_days": 30,
    })

    assert result.success is True
    assert result.data["start_date"] == start.isoformat()
    assert result.data["end_date"] == today.isoformat()
    assert calls[0][1]["params"]["from"] == start.isoformat()
    assert calls[0][1]["params"]["to"] == today.isoformat()


@pytest.mark.parametrize("arguments", [
    {"start_date": "2000-01-01"},
    {"start_date": "2000-01-01", "end_date": "2000-01-02", "date": "2000-01-01"},
    {"lookback_days": 93},
    {"start_date": "2000-01-03", "end_date": "2000-01-01"},
])
def test_exchange_rate_rejects_invalid_or_unbounded_date_ranges(arguments):
    calls = []
    _, bindings = _bindings(
        lambda url, **kwargs: calls.append((url, kwargs))
    )

    result = _execute(bindings["public_finance_exchange_rate"], {
        "base_currency": "USD",
        "quote_currency": "CNY",
        **arguments,
    })

    assert result.success is False
    assert calls == []


def test_exchange_rate_rejects_path_injection_before_network_call():
    calls = []
    _, bindings = _bindings(
        lambda url, **kwargs: calls.append((url, kwargs))
    )

    result = _execute(bindings["public_finance_exchange_rate"], {
        "base_currency": "USD/../../internal",
        "quote_currency": "EUR",
    })

    assert result.success is False
    assert calls == []


def test_world_bank_indicator_is_bounded_and_projects_rows():
    response = FakeResponse([
        {"page": 1, "pages": 1, "total": 2, "lastupdated": "2026-10-08"},
        [
            {
                "indicator": {"id": "SP.POP.TOTL", "value": "Population, total"},
                "country": {"id": "US", "value": "United States"},
                "countryiso3code": "USA",
                "date": "2024",
                "value": 340003797,
                "unit": "",
                "decimal": 0,
                "secret": "must not leak",
            },
            {
                "indicator": {"id": "SP.POP.TOTL", "value": "Population, total"},
                "country": {"id": "US", "value": "United States"},
                "countryiso3code": "USA",
                "date": "2023",
                "value": 336755052,
                "unit": "",
                "decimal": 0,
            },
        ],
    ])
    calls = []

    def request_get(url, **kwargs):
        calls.append((url, kwargs))
        return response

    _, bindings = _bindings(request_get)
    result = _execute(bindings["public_economics_country_indicator"], {
        "country_code": "USA",
        "indicator_code": "SP.POP.TOTL",
        "year_from": 2023,
        "year_to": 2024,
    })

    assert result.success is True
    assert result.data["count"] == 2
    assert result.data["country_code"] == "USA"
    assert result.data["indicator_code"] == "SP.POP.TOTL"
    assert (
        result.data["source_url"]
        == "https://api.worldbank.org/v2/country/USA/indicator/"
        "SP.POP.TOTL?format=json&per_page=20&date=2023%3A2024"
    )
    assert result.data["records"][0] == {
        "year": "2024",
        "value": 340003797,
        "country": "United States",
        "indicator": "Population, total",
        "unit": "",
    }
    assert "secret" not in repr(result.data)
    url, options = calls[0]
    assert url == (
        "https://api.worldbank.org/v2/country/USA/"
        "indicator/SP.POP.TOTL"
    )
    assert options["params"] == {
        "format": "json",
        "per_page": 20,
        "date": "2023:2024",
    }


@pytest.mark.parametrize(
    "arguments",
    [
        {"country_code": "US/../../", "indicator_code": "SP.POP.TOTL"},
        {"country_code": "USA", "indicator_code": "../secret"},
        {
            "country_code": "USA",
            "indicator_code": "SP.POP.TOTL",
            "year_from": 2025,
            "year_to": 2020,
        },
        {
            "country_code": "USA",
            "indicator_code": "SP.POP.TOTL",
            "year_from": 2000,
            "year_to": 2025,
        },
    ],
)
def test_world_bank_rejects_invalid_codes_and_unbounded_years(arguments):
    calls = []
    _, bindings = _bindings(
        lambda url, **kwargs: calls.append((url, kwargs))
    )

    result = _execute(bindings["public_economics_country_indicator"], arguments)

    assert result.success is False
    assert calls == []


def test_uk_bank_holidays_filters_official_response_by_region_and_year():
    response = FakeResponse({
        "england-and-wales": {
            "events": [
                {
                    "title": "Early May bank holiday",
                    "date": "2026-05-04",
                    "notes": "",
                    "bunting": True,
                },
                {
                    "title": "Old holiday",
                    "date": "2025-05-05",
                    "notes": "",
                    "bunting": True,
                },
            ],
        },
        "scotland": {"events": []},
    })
    calls = []

    def request_get(url, **kwargs):
        calls.append((url, kwargs))
        return response

    _, bindings = _bindings(request_get)
    result = _execute(bindings["public_calendar_bank_holidays"], {
        "division": "england-and-wales",
        "year": 2026,
    })

    assert result.success is True
    assert result.data["division"] == "england-and-wales"
    assert result.data["source_url"] == "https://www.gov.uk/bank-holidays.json"
    assert result.data["count"] == 1
    assert result.data["events"] == [{
        "title": "Early May bank holiday",
        "date": "2026-05-04",
        "notes": "",
        "bunting": True,
    }]
    assert calls[0][0] == "https://www.gov.uk/bank-holidays.json"
    assert calls[0][1]["params"] is None


def test_public_api_errors_are_sanitized_and_response_is_closed():
    response = FakeResponse(
        {"message": "private-token-value"},
        status_code=429,
    )
    _, bindings = _bindings(lambda _url, **_kwargs: response)

    result = _execute(bindings["public_finance_exchange_rate"], {
        "base_currency": "USD",
        "quote_currency": "EUR",
    })

    assert result.success is False
    assert "429" in result.error
    assert "private-token-value" not in result.error
    assert response.closed is True


def test_public_api_response_size_limit_stops_streaming():
    response = FakeResponse(
        body=b"x" * (MAX_RESPONSE_BYTES + 1),
    )
    _, bindings = _bindings(lambda _url, **_kwargs: response)

    result = _execute(bindings["public_finance_exchange_rate"], {
        "base_currency": "USD",
        "quote_currency": "EUR",
    })

    assert result.success is False
    assert "256 kb" in result.error.lower()
    assert response.closed is True


def test_network_errors_do_not_leak_upstream_exception_text():
    def request_get(_url, **_kwargs):
        raise requests.Timeout("private-upstream-detail")

    _, bindings = _bindings(request_get)
    result = _execute(bindings["public_finance_exchange_rate"], {
        "base_currency": "USD",
        "quote_currency": "EUR",
    })

    assert result.success is False
    assert "private-upstream-detail" not in result.error


def test_registered_public_data_tools_are_exposed_as_category_mcp_servers():
    runtime = AdvertisingComposition(require_llm=False, features=[])
    runtime.register_tool_source(public_data_tool_source(
        required_permission="ads.read",
        request_get=lambda *_args, **_kwargs: None,
    ))
    principal = RequestPrincipal(
        user_id="operator",
        tenant_id="tenant-a",
        permissions=frozenset({"ads.read"}),
    )
    gateway = RuntimeMCPServers(lambda: runtime, lambda *_args, **_kwargs: principal)

    try:
        gateway.refresh(runtime)
        servers = {
            item["server_id"]: item
            for item in gateway.list_servers(runtime, principal)
        }
        assert "namespace-public_calendar" in servers
        assert "namespace-public_economics" in servers
        assert "namespace-public_finance" in servers
        assert [
            item["tool_id"]
            for item in servers["namespace-public_finance"]["tools"]
        ] == ["public_finance_exchange_rate"]
        assert (
            servers["namespace-public_calendar"]["tools"][0]["read_only"]
            is True
        )
    finally:
        runtime.close(wait=True)
