from agents.ad_agent.scripts.audit_capabilities import audit_capabilities


def test_capability_audit_discovers_all_installed_channels_without_issues():
    report = audit_capabilities()

    assert report["issues"] == []
    assert report["tool_count"] == 72
    assert set(report["platforms"]) == {"meta", "google-ads", "tiktok", "dv360"}
    assert report["platforms"]["tiktok"]["actions"]["create:ad_group"] == 1
    assert report["platforms"]["dv360"]["actions"]["create:line_item"] == 1
