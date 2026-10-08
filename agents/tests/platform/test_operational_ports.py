"""Tests for application-neutral deployment health and operational ports."""

from agents.agent_harness.observability import (
    DeploymentHealth,
    HealthCheck,
)


def test_deployment_health_is_not_ready_when_a_required_check_is_unconfigured():
    report = DeploymentHealth.from_checks([
        HealthCheck("runtime", "healthy", required=True),
        HealthCheck("credentials", "unconfigured", required=True),
        HealthCheck("quota", "disabled", required=False),
    ])

    assert report.status == "not_ready"
    assert report.ready is False
    assert report.blocking_checks == ("credentials",)
    assert report.to_dict()["checks"]["quota"]["status"] == "disabled"


def test_deployment_health_preserves_non_blocking_degraded_checks():
    report = DeploymentHealth.from_checks([
        HealthCheck("runtime", "healthy"),
        HealthCheck("metrics", "degraded", required=False),
    ])

    assert report.status == "ready"
    assert report.ready is True
    assert report.blocking_checks == ()
    assert report.to_dict()["checks"]["metrics"]["status"] == "degraded"
