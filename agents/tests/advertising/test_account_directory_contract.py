from agents.agent_harness.core.interfaces import ToolContext
from agents.tools.advertising.providers.source_factory import create_tool_source
from agents.tools.advertising.clients.tiktok_client import TikTokAPIClient
from agents.agent_harness.core.tool_registry import validate_tool_input
import pytest


def test_account_directory_tools_declare_their_record_ids():
    for provider, name, expected in (
        ("meta", "meta_list_accounts", "account_id"),
        ("tiktok", "tiktok_list_accounts", "advertiser_id"),
    ):
        binding = next(
            item for item in create_tool_source(provider).list_bindings()
            if item.definition.name == name
        )
        assert binding.definition.result_items_key == "accounts"
        assert expected in binding.definition.result_id_fields


def test_tiktok_account_lookup_rejects_ids_outside_the_authorized_scope():
    calls = []
    class Client:
        def list_accounts(self, ids):
            calls.append(ids)
            return [{"advertiser_id": value} for value in ids]

    handler = next(
        handler for definition, handler in create_tool_source("tiktok", Client()).register_tools()
        if definition.name == "tiktok_list_accounts"
    )
    context = ToolContext(
        "directory", "actor", account_id="7397068114548195329",
        metadata={"authorized_account_ids": ["7397068114548195329"]},
    )
    rejected = handler.execute(context, {"advertiser_ids": ["outside"]})
    assert rejected.success is False
    assert calls == []
    accepted = handler.execute(context, {"advertiser_ids": ["7397068114548195329"]})
    assert accepted.success is True
    assert calls == [["7397068114548195329"]]


def test_tiktok_creative_id_is_a_numeric_ad_id_not_a_media_id():
    tool = next(
        item.definition for item in create_tool_source("tiktok").list_bindings()
        if item.definition.name == "tiktok_get_creative"
    )
    assert "Ad ID" in tool.description
    assert validate_tool_input(tool.input_schema, {
        "account_id": "7397068114548195329", "creative_id": "v10033g50000media",
    })
    calls = []
    client = TikTokAPIClient({})
    client.list_creatives = lambda *_args, **kwargs: (
        calls.append(kwargs) or [{"creative_id": "123"}]
    )
    with pytest.raises(ValueError):
        client.get_creative("7397068114548195329", "v10033g50000media")
    assert calls == []
    assert client.get_creative("7397068114548195329", "123")["creative_id"] == "123"
