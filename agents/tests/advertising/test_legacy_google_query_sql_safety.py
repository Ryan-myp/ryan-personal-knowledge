"""Input boundaries for the legacy Google Ads GAQL adapter."""

import importlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.ad_platform_api import AdPlatformClient


class _GoogleQueryRecorder:
    def __init__(self):
        self.calls = []
        self.error = None
        self.stream_batches = []

    def search(self, *, customer_id, query):
        if self.error:
            raise self.error
        self.calls.append((customer_id, query))
        return []

    def search_stream(self, *, customer_id, query):
        if self.error:
            raise self.error
        self.calls.append((customer_id, query))
        return self.stream_batches


def _client_with_query_recorder():
    recorder = _GoogleQueryRecorder()
    api = AdPlatformClient.__new__(AdPlatformClient)
    api.get_client = lambda _platform: SimpleNamespace(
        get_service=lambda _service: recorder
    )
    return api, recorder


@pytest.mark.parametrize(
    ("method_name", "kwargs"),
    [
        ("google_list_campaigns", {"customer_id": "123 OR 1=1"}),
        ("google_list_campaigns", {"customer_id": "0"}),
        ("google_list_campaigns", {"customer_id": "9" * 100}),
        ("google_get_campaign", {"customer_id": "123", "campaign_id": "7 OR 1=1"}),
        ("google_list_campaign_budgets", {"customer_id": "123", "limit": "1 LIMIT 9999"}),
        ("google_list_campaign_budgets", {"customer_id": "123", "limit": -1}),
        ("google_list_bidding_strategies", {"customer_id": "123", "limit": "1 UNION SELECT"}),
        ("google_list_ad_groups", {"customer_id": "123", "campaign_id": "7\" OR \"x\"=\"x"}),
        ("google_list_keywords", {"customer_id": "123", "campaign_id": "7 OR 1=1"}),
        ("google_list_ads", {"customer_id": "123", "ad_group_id": "9 OR 1=1"}),
    ],
)
def test_legacy_google_queries_reject_untrusted_gaql_fragments(method_name, kwargs):
    api, recorder = _client_with_query_recorder()

    with pytest.raises(ValueError):
        getattr(api, method_name)(**kwargs)

    assert recorder.calls == []


def test_legacy_google_query_limit_is_bounded_before_gaql_construction():
    api, recorder = _client_with_query_recorder()

    api.google_list_campaign_budgets(customer_id="1234567890", limit=5000)

    assert len(recorder.calls) == 1
    customer_id, query = recorder.calls[0]
    assert customer_id == "1234567890"
    assert "LIMIT 1000" in query


def test_legacy_keyword_query_uses_supported_resource_and_checked_filters():
    api, recorder = _client_with_query_recorder()

    assert api.google_list_keywords(
        customer_id="1234567890", campaign_id="7654321", limit=2000
    ) == []

    customer_id, query = recorder.calls[0]
    assert customer_id == "1234567890"
    assert "FROM ad_group_criterion" in query
    assert "ad_group_criterion.type = KEYWORD" in query
    assert "AND campaign.id = 7654321" in query
    assert "LIMIT 1000" in query


def test_legacy_keyword_query_normalizes_provider_rows():
    api, recorder = _client_with_query_recorder()
    keyword = SimpleNamespace(
        criterion_id=77,
        keyword=SimpleNamespace(text="shoes", match_type="PHRASE"),
    )
    recorder.stream_batches = [
        SimpleNamespace(
            results=[
                SimpleNamespace(
                    ad_group_criterion=keyword,
                    campaign=SimpleNamespace(id=7654321),
                )
            ]
        )
    ]

    result = api.google_list_keywords(customer_id="1234567890")

    assert result == [{
        "id": 77,
        "text": "shoes",
        "match_type": "PHRASE",
        "campaign_id": 7654321,
    }]


@pytest.mark.parametrize(
    ("method_name", "kwargs"),
    [
        ("google_list_campaign_budgets", {"customer_id": "1234567890"}),
        ("google_list_bidding_strategies", {"customer_id": "1234567890"}),
        (
            "google_list_ad_groups",
            {"customer_id": "1234567890", "campaign_id": "7654321"},
        ),
        ("google_list_keywords", {"customer_id": "1234567890"}),
        ("google_list_ads", {"customer_id": "1234567890", "ad_group_id": "88"}),
    ],
)
def test_legacy_google_query_propagates_provider_failure_instead_of_returning_empty(
    method_name, kwargs
):
    api, recorder = _client_with_query_recorder()
    recorder.error = RuntimeError("provider unavailable")

    with pytest.raises(RuntimeError, match="provider unavailable"):
        getattr(api, method_name)(**kwargs)


def _legacy_rest_client(monkeypatch):
    script_dir = Path(__file__).resolve().parents[3] / "scripts"
    monkeypatch.syspath_prepend(str(script_dir))
    module = importlib.import_module("google_ads_api")
    return module.GoogleAdsClient({"google_ads": {"access_token": "test-token"}})


@pytest.mark.parametrize(
    ("method_name", "args", "kwargs"),
    [
        ("get_campaign", ("123", "1 OR 1=1"), {}),
        ("list_ad_groups", ("123", "1 UNION SELECT"), {}),
        ("list_keywords", ("123", "1 OR 1=1"), {}),
        ("list_ads", ("123", "1 OR 1=1"), {}),
        ("get_bid_suggestion", ("123", "1 OR 1=1"), {}),
        ("list_campaigns", ("123",), {"filter": "campaign.status = 'ENABLED' OR 1=1"}),
        (
            "generate_report",
            ("123", {"start": "2026-01-01' OR 'x'='x", "end": "2026-01-31"}),
            {},
        ),
    ],
)
def test_legacy_rest_queries_reject_untrusted_gaql_values(
    monkeypatch, method_name, args, kwargs
):
    client = _legacy_rest_client(monkeypatch)
    requests = []
    client.request = lambda *call_args, **call_kwargs: requests.append(
        (call_args, call_kwargs)
    )

    with pytest.raises(ValueError):
        getattr(client, method_name)(*args, **kwargs)

    assert requests == []


def test_legacy_rest_search_validates_customer_and_campaign_status_filter(monkeypatch):
    client = _legacy_rest_client(monkeypatch)
    calls = []
    client.request = lambda *args, **kwargs: calls.append((args, kwargs))

    client.list_campaigns("1234567890", filter="campaign.status = 'PAUSED'")

    assert len(calls) == 1
    assert calls[0][0] == ("POST", "customers/1234567890:search")
    assert "campaign.status = 'PAUSED'" in calls[0][1]["data"]["query"]

    with pytest.raises(ValueError):
        client.search("123/../../customers", "SELECT campaign.id FROM campaign")

    with pytest.raises(ValueError):
        client.list_campaigns("1234567890", filter=object())


def test_legacy_rest_report_rejects_reversed_date_range_before_request(monkeypatch):
    client = _legacy_rest_client(monkeypatch)
    calls = []
    client.request = lambda *args, **kwargs: calls.append((args, kwargs))

    with pytest.raises(ValueError, match="start must not be later than end"):
        client.generate_report(
            "1234567890", {"start": "2026-02-01", "end": "2026-01-31"}
        )

    assert calls == []


def test_legacy_rest_request_converts_transport_failure_to_api_response(monkeypatch):
    module = importlib.import_module("google_ads_api")
    client = _legacy_rest_client(monkeypatch)

    def fail_request(*_args, **_kwargs):
        raise module.requests.Timeout("request timed out")

    monkeypatch.setattr(module.requests, "post", fail_request)

    response = client.request("POST", "customers/1234567890:search", data={})

    assert not response.success
    assert "request timed out" in response.error


def test_legacy_rest_request_rejects_non_object_provider_payload(monkeypatch):
    module = importlib.import_module("google_ads_api")
    client = _legacy_rest_client(monkeypatch)
    monkeypatch.setattr(
        module.requests,
        "post",
        lambda *_args, **_kwargs: SimpleNamespace(
            status_code=200, json=lambda: ["unexpected"]
        ),
    )

    response = client.request("POST", "customers/1234567890:search", data={})

    assert not response.success
    assert response.error == "Invalid Google Ads API response payload"
