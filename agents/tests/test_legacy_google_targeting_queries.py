import pytest
from types import SimpleNamespace

from scripts.ad_platform_query_client import AdPlatformQueryClient


class _GoogleAdsRecorder:
    def __init__(self):
        self.calls = []
        self.batches = []
        self.error = None

    def get_service(self, _name):
        return self

    def search_stream(self, *, customer_id, query):
        self.calls.append((customer_id, query))
        if self.error:
            raise self.error
        return self.batches


def _client_with_google_recorder():
    recorder = _GoogleAdsRecorder()
    client = AdPlatformQueryClient({}, google_ads_client=recorder)
    return client, recorder


def test_google_sdk_client_requires_credentials_before_initialization():
    client = AdPlatformQueryClient({})

    with pytest.raises(ValueError, match="credentials"):
        client.get_client("google_ads")


@pytest.mark.parametrize(
    ("customer_id", "limit"),
    [
        ("123 OR 1=1", 10),
        ("0", 10),
        ("9" * 100, 10),
        ("1234567890", "1 LIMIT 9999"),
        ("1234567890", -1),
    ],
)
def test_google_targeting_queries_reject_invalid_customer_and_limit(customer_id, limit):
    client, recorder = _client_with_google_recorder()

    with pytest.raises(ValueError):
        client.google_list_locations(customer_id, limit=limit)

    assert recorder.calls == []


def test_google_location_query_uses_bounded_limit_and_provider_fields():
    client, recorder = _client_with_google_recorder()
    recorder.batches = [
        SimpleNamespace(
            results=[
                SimpleNamespace(
                    geo_target_constant=SimpleNamespace(
                        id=21167, name="California", target_type="State"
                    )
                )
            ]
        )
    ]

    result = client.google_list_locations("1234567890", limit=5000)

    assert result == [{"id": 21167, "name": "California", "type": "State"}]
    assert recorder.calls[0][0] == "1234567890"
    assert "FROM geo_target_constant" in recorder.calls[0][1]
    assert "LIMIT 1000" in recorder.calls[0][1]


def test_google_audience_query_reads_user_lists_instead_of_returning_placeholder():
    client, recorder = _client_with_google_recorder()
    recorder.batches = [
        SimpleNamespace(
            results=[
                SimpleNamespace(
                    user_list=SimpleNamespace(id=42, name="Test audience", type="CRM_BASED")
                )
            ]
        )
    ]

    result = client.google_list_audiences("1234567890", limit=20)

    assert result == [{"id": 42, "name": "Test audience", "type": "CRM_BASED"}]
    assert "FROM user_list" in recorder.calls[0][1]
    assert "LIMIT 20" in recorder.calls[0][1]


def test_google_targeting_query_propagates_provider_failure():
    client, recorder = _client_with_google_recorder()
    recorder.error = RuntimeError("provider unavailable")

    with pytest.raises(RuntimeError, match="provider unavailable"):
        client.google_list_locations("1234567890")
