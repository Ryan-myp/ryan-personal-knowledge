.PHONY: ad-agent-python-version ad-agent-install ad-agent-run ad-agent-test ad-agent-compile ad-agent-audit ad-agent-validate ad-agent-knowledge-check ad-agent-reliability-evidence ad-agent-reliability-evidence-mysql ad-agent-check

AD_AGENT_PYTHON := ./scripts/ad-agent-python
AD_AGENT_TEST_ENV := PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=.

ad-agent-python-version:
	@$(AD_AGENT_PYTHON) --version

ad-agent-install:
	@$(AD_AGENT_PYTHON) -m pip install -r requirements.txt

ad-agent-run:
	@$(AD_AGENT_PYTHON) -m uvicorn agents.deployments.advertising.api_server:app --host 127.0.0.1 --port 8765

ad-agent-test:
	@$(AD_AGENT_TEST_ENV) $(AD_AGENT_PYTHON) -m pytest agents/tests -q

ad-agent-compile:
	@$(AD_AGENT_PYTHON) -m compileall -q agents scripts/advertising

ad-agent-audit:
	@$(AD_AGENT_PYTHON) scripts/advertising/audit_provider_tools.py

ad-agent-validate:
	@$(AD_AGENT_PYTHON) scripts/advertising/validate_contracts.py --check-snapshot agents/tools/advertising/contracts/builtin_tools.json

ad-agent-knowledge-check:
	@$(AD_AGENT_PYTHON) scripts/advertising/validate_knowledge_quality.py
	@$(AD_AGENT_PYTHON) scripts/advertising/audit_knowledge_base.py

ad-agent-reliability-evidence:
	@$(AD_AGENT_PYTHON) scripts/advertising/production_reliability_evidence.py

ad-agent-reliability-evidence-mysql:
	@$(AD_AGENT_PYTHON) scripts/advertising/production_reliability_evidence.py --backend mysql

ad-agent-check: ad-agent-python-version ad-agent-compile ad-agent-audit ad-agent-validate ad-agent-test
	@git diff --check
