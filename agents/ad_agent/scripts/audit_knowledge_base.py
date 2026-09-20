"""CLI for auditing the repository Markdown LLM Wiki."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.ad_agent.knowledge_audit import audit_knowledge_base


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--knowledge-root", default="agents/ad_agent/knowledge_base")
    parser.add_argument(
        "--cases", default="agents/ad_agent/evals/knowledge_retrieval_cases.json"
    )
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()

    report = audit_knowledge_base(
        args.knowledge_root,
        cases_path=args.cases,
        today=date.today(),
    )
    if args.as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(
            f"pages={report['pages']} published={report['published_pages']} "
            f"errors={report['errors']} warnings={report['warnings']}"
        )
        print(f"coverage={json.dumps(report['coverage'], ensure_ascii=False, sort_keys=True)}")
        print(f"cases={json.dumps(report['cases'], ensure_ascii=False, sort_keys=True)}")
        counts = {}
        for issue in report["issues"]:
            key = (issue["severity"], issue["code"])
            counts[key] = counts.get(key, 0) + 1
        for (severity, code), count in sorted(counts.items()):
            print(f"{severity.upper()} {code}: {count}")
        if report["errors"]:
            print("Use --json to inspect every issue.")
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
