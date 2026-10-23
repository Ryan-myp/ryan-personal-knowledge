from types import SimpleNamespace
import ast

import pytest

from scripts.advertising import check_quality_delta as gate
from scripts.advertising.check_quality_delta import compare_findings


def issue(rule="security.sql_injection", line=1, severity="critical"):
    return SimpleNamespace(rule_id=rule, line=line, severity=SimpleNamespace(value=severity))


def test_unchanged_finding_survives_line_movement_without_becoming_new():
    before = "danger()\n"
    after = "\n\ndanger()\n"
    assert compare_findings(before, [issue()], after, [issue(line=3)]) == []


def test_new_or_duplicated_finding_is_not_hidden_by_existing_debt():
    rows = compare_findings(
        "danger()\n", [issue()], "danger()\ndanger()\n",
        [issue(), issue(line=2)],
    )
    assert len(rows) == 1
    assert rows[0]["rule_id"] == "security.sql_injection"
    assert rows[0]["line"] == 2


def test_finding_report_never_contains_source_text_or_credentials():
    source = 'access_token = "must-not-be-printed"\n'
    rows = compare_findings("", [], source, [issue("security.hardcoded_secret")])
    assert rows
    assert "must-not-be-printed" not in repr(rows)
    assert "source_hash" in rows[0]


def test_git_delta_covers_new_files_and_does_not_hide_existing_debt(tmp_path):
    gate._git(tmp_path, "init")
    source = tmp_path / "source.py"
    source.write_text("old_risk()\n", encoding="utf-8")
    gate._git(tmp_path, "add", "source.py")
    gate._git(
        tmp_path, "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
        "commit", "-m", "test baseline",
    )
    source.write_text("\nold_risk()\nnew_risk()\n", encoding="utf-8")
    (tmp_path / "new.py").write_text("new_risk()\n", encoding="utf-8")
    (tmp_path / "test_ignored.py").write_text("invalid code", encoding="utf-8")

    class Analyzer:
        def analyze(self, text, _path):
            ast.parse(text)
            return [
                issue(line=index)
                for index, line in enumerate(text.splitlines(), 1) if "risk" in line
            ]

    result = gate.analyze_delta(tmp_path, Analyzer(), ["test_*.py"])
    assert result["files_scanned"] == 2
    assert result["baseline_findings"] == 1
    assert result["current_findings"] == 3
    assert len(result["new_findings"]) == 2
    assert not result["gate_passed"]
    assert result["whole_repository_gate"] == "not_assessed_by_delta_gate"


def test_delta_refuses_a_source_symlink_outside_the_project(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    gate._git(root, "init")
    (root / "safe.py").write_text("pass\n", encoding="utf-8")
    gate._git(root, "add", ".")
    gate._git(
        root, "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
        "commit", "-m", "test baseline",
    )
    outside = tmp_path / "outside.py"
    outside.write_text("pass\n", encoding="utf-8")
    (root / "linked.py").symlink_to(outside)
    with pytest.raises(ValueError):
        gate.analyze_delta(root, SimpleNamespace(analyze=lambda *_: []), [])


def test_delta_cli_fails_closed_when_scanner_is_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(gate.sys, "argv", ["quality-delta", "--qguard-home", str(tmp_path)])
    assert gate.main() == 2
