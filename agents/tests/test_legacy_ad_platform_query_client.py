import requests
import pytest

from scripts.ad_platform_query_client import AdPlatformQueryClient


class _Response:
    def __init__(self, payload, error=None):
        self.payload = payload
        self.error = error

    def raise_for_status(self):
        if self.error:
            raise self.error

    def json(self):
        return self.payload


def test_tiktok_query_propagates_http_failures_instead_of_returning_empty(monkeypatch):
    monkeypatch.setattr(
        requests,
        "get",
        lambda *_args, **_kwargs: _Response(
            {}, requests.HTTPError("403 Forbidden")
        ),
    )
    client = AdPlatformQueryClient({"tiktok": {"access_token": "test-token"}})

    with pytest.raises(requests.HTTPError, match="403"):
        client.tiktok_list_devices("advertiser-1")


def test_tiktok_query_rejects_malformed_list_payload(monkeypatch):
    monkeypatch.setattr(
        requests,
        "get",
        lambda *_args, **_kwargs: _Response({"data": "unexpected"}),
    )
    client = AdPlatformQueryClient({"tiktok": {"access_token": "test-token"}})

    with pytest.raises(ValueError, match="data"):
        client.tiktok_list_devices("advertiser-1")


def test_tiktok_provider_error_code_is_not_returned_as_empty_data(monkeypatch):
    monkeypatch.setattr(
        requests,
        "get",
        lambda *_args, **_kwargs: _Response({"code": 40002, "data": {"list": []}}),
    )
    client = AdPlatformQueryClient({"tiktok": {"access_token": "test-token"}})

    with pytest.raises(RuntimeError, match="40002"):
        client.tiktok_list_devices("advertiser-1")


def test_meta_query_keeps_access_token_out_of_query_parameters(monkeypatch):
    calls = []
    monkeypatch.setattr(
        requests,
        "get",
        lambda *args, **kwargs: calls.append((args, kwargs))
        or _Response({"data": [{"id": "interest-1"}]}),
    )
    client = AdPlatformQueryClient({"meta": {"access_token": "private-test-token"}})

    result = client.meta_list_interests("act_123")

    assert result == [{"id": "interest-1"}]
    assert calls[0][1]["headers"]["Authorization"] == "Bearer private-test-token"
    assert calls[0][1]["params"] == {"limit": 100}
    assert "private-test-token" not in repr(calls[0][1]["params"])


def test_meta_age_ranges_cover_each_supported_age_boundary():
    client = AdPlatformQueryClient({})

    ranges = client.meta_list_age_ranges("act_123")

    assert len(ranges) == 58
    assert ranges[0] == {"code": "13", "name": "13岁", "min_age": 13, "max_age": 13}
    assert ranges[-1] == {
        "code": "70",
        "name": "70岁及以上",
        "min_age": 70,
        "max_age": 999,
    }
