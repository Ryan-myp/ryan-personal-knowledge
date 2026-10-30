import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from agents.tools.advertising.providers.source_factory import create_tool_source


ROOT = Path(__file__).resolve().parents[3]


def test_test_live_profile_preserves_default_preview_and_test_account_scope():
    default = yaml.safe_load((ROOT / "agents/ad_agent/config.yaml").read_text())
    profile = yaml.safe_load((ROOT / "agents/ad_agent/config.test-live.yaml").read_text())
    assert default["execution_mode"] == profile["execution_mode"] == "dry_run"
    assert default["allow_live_writes"] is False
    assert profile["allow_live_writes"] is True
    assert profile["execution_timeout_seconds"] == 500
    assert profile["allowed_accounts"] == {
        "google-ads": ["9055507554", "7574609568"],
        "meta": ["2806375919473667"],
        "tiktok": ["7397068114548195329"],
    }
    assert all(
        set(accounts) <= set(default["allowed_accounts"][provider])
        for provider, accounts in profile["allowed_accounts"].items()
    )
    assert "ads.write" in profile["granted_permissions"]
    assert "mcp.write" not in profile["granted_permissions"]
    approved = set(profile["live_approved_tools"])
    assert {
        "google_create_campaign", "google_create_ad_group",
        "google_create_product_group", "google_create_shopping_product_ad",
        "meta_create_campaign", "tiktok_smart_plus_create_campaign",
    } <= approved
    definitions = {
        binding.definition.name: binding.definition
        for namespace in profile["allowed_accounts"]
        for binding in create_tool_source(namespace).list_bindings()
    }
    assert approved <= definitions.keys()
    for name in approved:
        definition = definitions[name]
        assert definition.is_write_tool and definition.live_support
        assert definition.action in {"create", "update", "delete"}
        assert definition.namespace in profile["allowed_accounts"]
        assert definition.resource_type in {
            "campaign", "ad_group", "ad_set", "ad", "creative",
            "asset_group", "listing_group_filter", "product_group",
            "creative_portfolio",
        }


def test_workspace_execution_mode_javascript_regressions():
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for browser state contract tests")
    result = subprocess.run(
        [
            node,
            "--test",
            str(Path(__file__).parent / "static/test_workspace_mode.js"),
            str(Path(__file__).parent / "static/test_chat_workbench.js"),
        ],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
