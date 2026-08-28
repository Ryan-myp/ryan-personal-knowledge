#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
skill_up_bin="${SKILL_UP_BIN:-skill-up}"
export AD_AGENT_REPO_ROOT="${repo_root}"

exec "${skill_up_bin}" run "${repo_root}/agents/ad_agent/evals/skill-up/evals/eval.yaml" "$@"
