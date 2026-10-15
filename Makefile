.PHONY: ad-agent-python-version ad-agent-install ad-agent-dependency-check ad-agent-run ad-agent-run-test ad-agent-test ad-agent-compile ad-agent-audit ad-agent-validate ad-agent-knowledge-check ad-agent-reliability-evidence ad-agent-reliability-evidence-mysql ad-agent-check

AD_AGENT_PYTHON_WRAPPER := ./scripts/ad-agent-python
AD_AGENT_TEST_ENV := PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=.
AD_AGENT_BOOTSTRAP_PYTHON ?= python3.13
AD_AGENT_VENV_PYTHON := .venv/bin/python

ad-agent-python-version:
	@$(AD_AGENT_PYTHON_WRAPPER) --version

ad-agent-install:
	@if [ ! -x "$(AD_AGENT_VENV_PYTHON)" ]; then \
		bootstrap="$(AD_AGENT_BOOTSTRAP_PYTHON)"; \
		if ! command -v "$$bootstrap" >/dev/null 2>&1; then \
			echo "Python 3.13 was not found ($$bootstrap). Install it or set AD_AGENT_BOOTSTRAP_PYTHON." >&2; \
			exit 127; \
		fi; \
		bootstrap_version="$$( "$$bootstrap" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null )" || { \
			echo "Could not run the bootstrap interpreter ($$bootstrap)." >&2; \
			exit 2; \
		}; \
		if [ "$$bootstrap_version" != "3.13" ]; then \
			echo "ad-agent requires Python 3.13 to create .venv; found Python $$bootstrap_version ($$bootstrap)." >&2; \
			echo "Install Python 3.13 or set AD_AGENT_BOOTSTRAP_PYTHON to its executable." >&2; \
			exit 2; \
		fi; \
		"$$bootstrap" -m venv .venv || { \
			echo "Could not create .venv with $$bootstrap; verify that Python 3.13 includes venv/ensurepip." >&2; \
			exit 1; \
		}; \
	fi
	@.venv/bin/python -c 'import sys; print(f"Using project environment: Python {sys.version_info.major}.{sys.version_info.minor} ({sys.executable})") if sys.version_info[:2] == (3, 13) else sys.exit("The existing .venv must use Python 3.13. It was not modified; move it aside (for example: mv .venv .venv.backup), then rerun make ad-agent-install.")'
	@.venv/bin/python -m pip install -r requirements.txt
	@.venv/bin/python -m pip check

ad-agent-dependency-check:
	@$(AD_AGENT_PYTHON_WRAPPER) scripts/check_ad_agent_dependencies.py --requirements requirements.txt

ad-agent-run:
	@$(AD_AGENT_PYTHON_WRAPPER) -m uvicorn agents.deployments.advertising.api_server:app --host 127.0.0.1 --port 8765

ad-agent-run-test:
	@AD_AGENT_ENABLE_LIVE=1 AD_AGENT_CONFIG_PATH=agents/ad_agent/config.test-live.yaml $(AD_AGENT_PYTHON_WRAPPER) -m uvicorn agents.deployments.advertising.api_server:app --host 127.0.0.1 --port 8765

ad-agent-test:
	@$(AD_AGENT_TEST_ENV) $(AD_AGENT_PYTHON_WRAPPER) -m pytest agents/tests -q

ad-agent-compile:
	@$(AD_AGENT_PYTHON_WRAPPER) -m compileall -q agents scripts/advertising

ad-agent-audit:
	@$(AD_AGENT_PYTHON_WRAPPER) scripts/advertising/audit_provider_tools.py

ad-agent-validate:
	@$(AD_AGENT_PYTHON_WRAPPER) scripts/advertising/validate_contracts.py --check-snapshot agents/tools/advertising/contracts/builtin_tools.json

ad-agent-knowledge-check:
	@$(AD_AGENT_PYTHON_WRAPPER) scripts/advertising/validate_knowledge_quality.py
	@$(AD_AGENT_PYTHON_WRAPPER) scripts/advertising/audit_knowledge_base.py

ad-agent-reliability-evidence:
	@$(AD_AGENT_PYTHON_WRAPPER) scripts/advertising/production_reliability_evidence.py

ad-agent-reliability-evidence-mysql:
	@$(AD_AGENT_PYTHON_WRAPPER) scripts/advertising/production_reliability_evidence.py --backend mysql

ad-agent-check: ad-agent-python-version ad-agent-compile ad-agent-audit ad-agent-validate ad-agent-test
	@git diff --check
