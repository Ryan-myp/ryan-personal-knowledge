"""Regression tests for provider-owned API version contracts.

These tests are intentionally provider-package oriented: an API upgrade must
be represented by Client metadata and an adapter (when needed), not by
changing a Runtime string or silently changing a Tool payload.
"""

from __future__ import annotations

import pytest

from agents.ad_agent.api_clients.base import BasePlatformClient, ProviderVersionAdapter
from agents.ad_agent.api_clients.dv360_client import DV360APIClient
from agents.ad_agent.api_clients.google_ads_client import GoogleAdsAPIClient
from agents.ad_agent.api_clients.meta_client import MetaAPIClient
from agents.ad_agent.api_clients.tiktok_client import TikTokAPIClient
from agents.ad_agent.capabilities.dv360.capability import DV360Capability
from agents.ad_agent.capabilities.google.capability import GoogleCapability
from agents.ad_agent.capabilities.meta.capability import MetaCapability
from agents.ad_agent.capabilities.tiktok.capability import TikTokCapability


@pytest.mark.parametrize(
    ("client_class", "capability_class"),
    [
        (MetaAPIClient, MetaCapability),
        (GoogleAdsAPIClient, GoogleCapability),
        (TikTokAPIClient, TikTokCapability),
        (DV360APIClient, DV360Capability),
    ],
)
def test_builtin_provider_and_capability_versions_are_consistent(
    client_class, capability_class
):
    contract = client_class.version_contract()

    assert contract["issues"] == []
    assert contract["api_version"] in contract["supported_api_versions"]
    assert capability_class.integration_api_version in {
        *contract["supported_api_versions"],
        *contract["adapter_versions"],
    }


class _Adapter(ProviderVersionAdapter):
    pass


class _InvalidVersionClient(BasePlatformClient):
    API_VERSION = "v2"
    SUPPORTED_API_VERSIONS = ("v1",)

    def _do_request(self, method, url, **kwargs):
        return {"status_code": 200, "data": {}, "headers": {}}

    def _extract_data(self, response):
        return response.get("data", {})

    def _handle_error(self, response, status_code):
        return None


class _AdapterVersionClient(BasePlatformClient):
    API_VERSION = "v2"
    SUPPORTED_API_VERSIONS = ("v2", "v1")
    VERSION_ADAPTERS = {"v1": _Adapter}

    def _do_request(self, method, url, **kwargs):
        return {"status_code": 200, "data": {}, "headers": {}}

    def _extract_data(self, response):
        return response.get("data", {})

    def _handle_error(self, response, status_code):
        return None


def test_version_contract_rejects_partial_client_declarations():
    errors = _InvalidVersionClient.validate_version_contract()

    assert "API_VERSION 'v2' is missing from SUPPORTED_API_VERSIONS" in errors


def test_version_contract_accepts_adapter_as_a_supported_tool_version():
    contract = _AdapterVersionClient.version_contract()

    assert contract["issues"] == []
    assert contract["adapter_versions"] == ["v1"]
    assert _AdapterVersionClient({}, "adapter-version-test").supports_tool_api_version("v1") is True
