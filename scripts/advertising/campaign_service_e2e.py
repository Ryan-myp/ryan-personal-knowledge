"""Explicitly authorized, paused-only test-account checks through the HTTP Agent."""

from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import threading
import time
from urllib.parse import parse_qs, urlsplit

import requests
import yaml

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.agent_harness.redaction import redact_for_persistence
from agents.deployments.advertising.local_config import load_default_local_env
from agents.tools.advertising.providers.source_factory import create_tool_source

PROVIDERS = ("google-ads", "meta", "tiktok")
CONFIRMED_ACCOUNTS = {
    "google-ads": ["9055507554"],
    "meta": ["2806375919473667"],
    "tiktok": ["7397068114548195329"],
}
HOSTS = {
    "google-ads": "googleads.googleapis.com",
    "meta": "graph.facebook.com",
    "tiktok": "business-api.tiktok.com",
}
RESOURCES = {"campaign", "ad_group", "ad_set", "ad", "creative", "asset_group"}
SENSITIVE = re.compile(
    r"token|secret|api[_-]?key|private_key|password|bc_id|partner_id|perter_id|mcc",
    re.I,
)


def paused_payload(provider, values):
    status = "DISABLE" if provider == "tiktok" else "PAUSED"
    result = {**values, "status": status}
    if isinstance(values.get("updates"), dict):
        result["updates"] = {**values["updates"], "status": status}
    return result


def summarize_chat(payload, expected_tool):
    rows = payload.get("results") or payload.get("data", {}).get("tool_results") or []
    matched = [
        row
        for row in rows
        if (row.get("tool_name") or row.get("tool") or row.get("name")) == expected_tool
    ]
    passed = any(
        (row.get("result") or row).get("success") is True
        and not (row.get("result") or row).get("simulated")
        and not any(
            node.get("mode") == "dry_run"
            or node.get("execution_status") == "planned"
            or node.get("simulated") is True
            or str(node.get("data_status") or "").startswith("offline")
            for node in _walk((row.get("result") or row).get("data") or {})
        )
        for row in matched
    )
    return {
        "passed": passed,
        "status": payload.get("status"),
        "matched_results": matched,
    }


def safe_evidence(value):
    return _scrub_evidence(redact_for_persistence(value))


def _scrub_evidence(value):
    if isinstance(value, dict):
        return {
            key: "<redacted>"
            if key in {"confirmation_payload", "selection_tokens"}
            or SENSITIVE.search(key)
            else _scrub_evidence(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_scrub_evidence(item) for item in value]
    if isinstance(value, str):
        return re.sub(
            r"ps1\.[A-Za-z0-9_.-]+", "<redacted>", redact_for_persistence(value)
        )
    return value


def compact_summary(payload, tool):
    summary = summarize_chat(payload, tool)
    records = []
    for row in summary["matched_results"]:
        result = row.get("result") or row
        data = result.get("data") or {}
        records.append(
            {
                "success": result.get("success"),
                "error": result.get("error"),
                "data_status": data.get("data_status"),
                "ids": {
                    k: v
                    for k, v in data.items()
                    if k.endswith("_id") or k in {"id", "resource_name"}
                },
                "counts": {k: len(v) for k, v in data.items() if isinstance(v, list)},
            }
        )
    return safe_evidence(
        {
            "passed": summary["passed"],
            "status": summary["status"],
            "records": records,
            "needs_input": payload.get("needs_input"),
            "needs_confirmation": payload.get("needs_confirmation"),
            "reply": str(payload.get("reply") or "")[:1600],
        }
    )


def classify_evidence(case, events, *, write):
    summary = summarize_chat(case.get("response") or {}, case["tool"])
    if not summary["passed"]:
        return "failed" if summary["matched_results"] else "blocked"
    successful = [
        row
        for row in events
        if row.get("http_status") is not None
        and 200 <= row["http_status"] < 300
        and row.get("provider_code") in (None, 0)
    ]
    if write:
        successful = [
            row
            for row in successful
            if row.get("method") in {"POST", "PATCH", "PUT"}
            and not str(row.get("path") or "").endswith(
                ("googleAds:search", "googleAds:searchStream")
            )
        ]
    return "verified" if successful else "no_provider_evidence"


def readback_checks(read_case, resource_id, expected):
    fields = (
        "id",
        "campaign_id",
        "adgroup_id",
        "adset_id",
        "ad_id",
        "creative_id",
        "asset_group_id",
    )
    record = None
    summary = summarize_chat(read_case.get("response") or {}, read_case["tool"])
    if not summary["passed"]:
        return {}
    for row in summary["matched_results"]:
        result = row.get("result") or row
        if not result.get("success"):
            continue
        record = next(
            (
                node
                for node in _walk(result.get("data") or {})
                if any(
                    str(node.get(field) or "") == str(resource_id) for field in fields
                )
            ),
            None,
        )
        if record is not None:
            break
    if record is None:
        return {}
    aliases = {
        "name": ("name", "ad_name", "adgroup_name", "campaign_name"),
        "status": ("operation_status", "status"),
        "daily_budget": ("daily_budget", "budget"),
        "budget": ("budget", "daily_budget"),
        "final_url": ("final_urls",),
    }
    checks = {}
    for field, value in expected.items():
        observed = next(
            (
                record[key]
                for key in aliases.get(field, (field,))
                if record.get(key) is not None
            ),
            None,
        )
        if observed is None and field in {"headlines", "descriptions"}:
            observed = record.get("responsive_search_ad", {}).get(field)
        if observed is None and field == "creative_id":
            observed = (record.get("creative") or {}).get("id")
        target = value
        if observed is None:
            checks[field] = {"expected": target, "observed": None, "passed": None}
            continue
        if field == "status":
            states = dict.fromkeys(("0", "PAUSED", "DISABLE"), "PAUSED")
            states.update(dict.fromkeys(("1", "ACTIVE", "ENABLE", "ENABLED"), "ACTIVE"))
            normalize = lambda item: states.get(str(item).upper(), str(item))
            observed, target = normalize(observed), normalize(value)
        elif field in {"daily_budget", "budget"} and observed is not None:
            observed, target = float(observed), float(value)
            if read_case["provider"] == "meta":
                target *= 100
        elif field in {"headlines", "descriptions"} and isinstance(observed, list):
            observed = [
                item.get("text") if isinstance(item, dict) else item
                for item in observed
            ]
        elif field == "final_url" and isinstance(observed, list):
            observed = observed[0] if observed else None
        checks[field] = {
            "expected": target,
            "observed": observed,
            "passed": observed == target if observed is not None else None,
        }
    return checks


def report(directory):
    root = Path(directory).resolve()
    definitions = {
        binding.definition.name: binding.definition
        for provider in PROVIDERS
        for binding in create_tool_source(provider).list_bindings()
    }
    events = [
        json.loads(line)
        for line in (root / "provider-http.jsonl").read_text().splitlines()
        if line.strip()
    ]
    cases = []
    documents = [
        (path, json.loads(path.read_text())) for path in (root / "cases").glob("*.json")
    ]
    completion_times = {path: path.stat().st_mtime for path, _ in documents}
    events_by_case = {}
    for event in events:
        events_by_case.setdefault(event.get("case_id"), []).append(event)
    for path, case in sorted(documents, key=lambda item: item[0].name):
        tool = definitions.get(case["tool"])
        scoped_events = events_by_case.get(path.stem, [])
        outcome = classify_evidence(
            case, scoped_events, write=bool(tool and tool.is_write_tool)
        )
        summary = summarize_chat(case.get("response") or {}, case["tool"])
        errors = [
            (item.get("result") or item).get("error")
            for item in summary["matched_results"]
            if (item.get("result") or item).get("error")
        ]
        row = {
            "case_id": path.stem,
            "provider": case["provider"],
            "tool": case["tool"],
            "resource": tool.resource_type if tool else None,
            "action": tool.action if tool else None,
            "outcome": outcome,
            "agent_status": summary["status"],
            "error": errors[0] if errors else (case.get("response") or {}).get("error"),
            "transport": scoped_events,
            "matching_result_count": len(summary["matched_results"]),
        }
        if tool and tool.action == "update" and outcome == "verified":
            resource_id = case["params"].get(tool.resource_id_field)
            candidates = [
                (read_path, read_case)
                for read_path, read_case in documents
                if definitions.get(read_case["tool"])
                and definitions[read_case["tool"]].action == "get"
                and definitions[read_case["tool"]].resource_type == tool.resource_type
                and resource_id is not None
                and read_case["params"].get(tool.resource_id_field) == resource_id
                and completion_times[read_path] > completion_times[path]
                and classify_evidence(
                    read_case, events_by_case.get(read_path.stem, []), write=False
                )
                == "verified"
            ]
            checks = {}
            if candidates:
                read_path, read_case = min(
                    candidates, key=lambda item: completion_times[item[0]]
                )
                checks = readback_checks(
                    read_case, resource_id, case["params"].get("updates") or {}
                )
                row["readback_case"] = read_path.stem
            row["readback_checks"] = checks
            states = [check["passed"] for check in checks.values()]
            row["functional_status"] = (
                "failed"
                if False in states
                else "passed"
                if states and all(states)
                else "unverified"
            )
        cases.append(row)
    tested = {case["tool"] for case in cases if case["outcome"] == "verified"}
    unverified = [
        tool.name
        for tool in definitions.values()
        if tool.resource_type in RESOURCES
        and tool.action in {"create", "update", "get", "list"}
        and tool.name not in tested
    ]
    document = {
        "accounts": CONFIRMED_ACCOUNTS,
        "cases": cases,
        "unverified_tools": sorted(unverified),
    }
    _json_write(root / "report.json", document)
    lines = [
        "# Test-account service execution evidence",
        "",
        "All cases use the real /chat endpoint, model, Harness and registered Tools.",
        "Verified means matching non-simulated Tool success plus successful provider transport.",
        "It does not mean every advertising type, update field, or conversation workflow has passed.",
        "Writes are paused-only; updates are restricted to resources created in this test.",
        "",
        "Transport success alone is not functional success. Updates are also checked against subsequent reads.",
        "| Case | Provider | Tool | Transport Evidence | Update Readback | Agent Status |",
        "|---|---|---|---|---|---|",
    ]
    lines.extend(
        f"| [{case['case_id']}](cases/{case['case_id']}.json) | {case['provider']} | "
        f"`{case['tool']}` | {case['outcome']} | {case.get('functional_status', '-')} | {case['agent_status']} |"
        for case in cases
    )
    lines.extend(["", "## Not Verified In This Run", ""])
    lines.extend(f"- `{name}`" for name in sorted(unverified))
    (root / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "cases": len(cases),
                "verified": sum(case["outcome"] == "verified" for case in cases),
                "unverified_tools": len(unverified),
            }
        )
    )


def _json_write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(safe_evidence(value), ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _load_state(directory):
    root = Path(directory).resolve()
    state = json.loads((root / "state.json").read_text())
    key = Path(state["private_auth_file"]).read_text()
    return root, state, {"X-API-Key": key}


def _approved_tools():
    names = []
    for provider in PROVIDERS:
        for binding in create_tool_source(provider).list_bindings():
            tool = binding.definition
            if (
                tool.action not in {"create", "update"}
                or tool.resource_type not in RESOURCES
                or not tool.live_support
            ):
                continue
            fields = tool.input_schema.properties
            if (
                tool.action == "create"
                and tool.resource_type != "creative"
                and not ({"status", "operation_status"} & set(fields))
            ):
                continue
            names.append(tool.name)
    return sorted(names)


def start(directory, port):
    load_default_local_env()
    root = Path(directory).resolve()
    root.mkdir(parents=True, exist_ok=True)
    original = yaml.safe_load((ROOT / "agents/ad_agent/config.yaml").read_text()) or {}
    accounts = {p: original["allowed_accounts"][p] for p in PROVIDERS}
    if accounts != CONFIRMED_ACCOUNTS:
        raise ValueError(
            "configured accounts differ from the user-confirmed test accounts"
        )
    config = {
        "execution_mode": "dry_run",
        "allow_live_writes": True,
        "allowed_accounts": accounts,
        "live_approved_tools": _approved_tools(),
        "granted_permissions": [
            "ads.read",
            "ads.plan",
            "ads.write",
            "ads.reconcile",
            "knowledge.read",
        ],
    }
    config_path = root / "test-config.yaml"
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")
    private_root = _private_directory(root)
    auth_file = private_root / "key"
    key = secrets.token_urlsafe(32)
    auth_file.write_text(key)
    auth_file.chmod(0o600)
    env = {
        **os.environ,
        "AD_AGENT_API_KEY": key,
        "AD_AGENT_ENABLE_LIVE": "1",
        "AD_AGENT_CONFIG_PATH": str(config_path),
        "AD_AGENT_DB_PATH": str(private_root / "test.db"),
        "AD_AGENT_SERVICE_PRINCIPAL": "campaign-e2e",
        "AD_AGENT_SERVICE_TENANT": "campaign-e2e",
    }
    process = subprocess.Popen(
        [
            sys.executable,
            str(Path(__file__).resolve()),
            "serve",
            "--directory",
            str(root),
            "--port",
            str(port),
        ],
        cwd=ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    state = {
        "pid": process.pid,
        "base_url": f"http://127.0.0.1:{port}",
        "private_auth_file": str(auth_file),
        "accounts": accounts,
    }
    _json_write(root / "state.json", state)
    for _ in range(120):
        if process.poll() is not None:
            raise RuntimeError("test service exited; inspect the sanitized service log")
        try:
            response = requests.get(state["base_url"] + "/readyz", timeout=2)
            if response.status_code == 200:
                print(
                    json.dumps(
                        {
                            "ready": True,
                            "pid": process.pid,
                            "base_url": state["base_url"],
                        }
                    )
                )
                return
        except requests.RequestException:
            time.sleep(1)
            continue
        time.sleep(1)
    raise TimeoutError("test service did not become ready")


def _private_directory(root):
    import tempfile

    state_file = root / "state.json"
    if state_file.is_file():
        previous = json.loads(state_file.read_text())
        private = Path(previous["private_auth_file"]).parent
        if private.is_dir():
            return private
    return Path(tempfile.mkdtemp(prefix="ad-crud-auth-"))


def _credential_values(value):
    found = []
    if isinstance(value, dict):
        for key, item in value.items():
            if (
                SENSITIVE.search(key)
                and isinstance(item, (str, int))
                and len(str(item)) >= 4
            ):
                found.append(str(item))
            found.extend(_credential_values(item))
    elif isinstance(value, list):
        for item in value:
            found.extend(_credential_values(item))
    return found


class SafeFormatter(logging.Formatter):
    def __init__(self):
        super().__init__("%(asctime)s %(levelname)s %(name)s %(message)s")
        credential_file = ROOT / "config/ad_platform_credentials.json"
        credentials = (
            json.loads(credential_file.read_text()) if credential_file.is_file() else {}
        )
        self.secrets = _credential_values(credentials) + [
            v for k, v in os.environ.items() if SENSITIVE.search(k) and len(v) >= 4
        ]

    def format(self, record):
        text = super().format(record)
        for value in self.secrets:
            text = text.replace(value, "<redacted>")
        return redact_for_persistence(text)


def _request_data(request):
    body = request.body or b""
    text = body.decode() if isinstance(body, bytes) else str(body)
    if not text:
        return {}
    try:
        return json.loads(text)
    except ValueError:
        return {key: values[0] for key, values in parse_qs(text).items()}


def _walk(value):
    if isinstance(value, dict):
        yield value
        for item in value.values():
            yield from _walk(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk(item)


class ProviderRecorder:
    """Observe real transport, with extra safety restrictions for this test deployment."""

    def __init__(self, directory):
        self.root = Path(directory)
        self.case = {}
        owned_path = self.root / "created-resource-ids.json"
        self.created = (
            set(json.loads(owned_path.read_text())) if owned_path.is_file() else set()
        )
        self.lock = threading.RLock()
        self.original = requests.Session.send

    def install(self):
        recorder = self

        def send(session, request, **kwargs):
            return recorder.send(session, request, **kwargs)

        requests.Session.send = send

    def _guard(self, request, provider, data):
        if not self.case or self.case.get("provider") != provider:
            raise PermissionError("Provider request outside the selected test channel")
        account = self.case["account"]
        path = urlsplit(request.url).path
        if provider == "google-ads" and f"/customers/{account}/" not in path:
            raise PermissionError("Google request outside the test account")
        if provider == "meta":
            account_path = re.search(r"/act_(\d+)(?:/|$)", path)
            if account_path and account_path.group(1) != account:
                raise PermissionError("Meta request outside the test account")
        target = data.get("advertiser_id") or data.get("account_id")
        if target and str(target).removeprefix("act_") != account:
            raise PermissionError("Provider request outside the test account")
        if request.method != "POST":
            return
        for node in _walk(data):
            for field in ("status", "operation_status"):
                if str(node.get(field, "")).upper() in {"ENABLED", "ENABLE", "ACTIVE"}:
                    raise PermissionError("test resources must not be activated")
        if provider == "meta" and path.rstrip("/").endswith(
            ("/campaigns", "/adsets", "/ads")
        ):
            if data.get("status") != "PAUSED":
                raise PermissionError("Meta creation must explicitly be PAUSED")
        if provider == "google-ads":
            self._guard_google(data, path)
        if provider == "meta" and re.fullmatch(r"/v[\d.]+/\d+/?", path):
            if path.rstrip("/").rsplit("/", 1)[-1] not in self.created:
                raise PermissionError("update is not a resource created by this test")
        if provider == "tiktok" and "/update/" in path:
            self._guard_tiktok_update(data)

    def _guard_google(self, data, path):
        serving = any(
            name in path
            for name in ("campaigns:", "adGroups:", "adGroupAds:", "assetGroups:")
        )
        for node in _walk(data):
            if serving and isinstance(node.get("create"), dict):
                if node["create"].get("status") != "PAUSED":
                    raise PermissionError("Google creation must explicitly be PAUSED")
            update = node.get("update")
            if isinstance(update, dict):
                resource = update.get("resourceName", "")
                numeric_ad = resource.rsplit("/", 1)[-1] if "/ads/" in resource else ""
                owned_ad = bool(numeric_ad) and any(
                    "/adGroupAds/" in owned and owned.endswith("~" + numeric_ad)
                    for owned in self.created
                )
                if resource and resource not in self.created and not owned_ad:
                    raise PermissionError(
                        "update is not a resource created by this test"
                    )

    def _guard_tiktok_update(self, data):
        fields = (
            "campaign_id",
            "adgroup_id",
            "ad_id",
            "campaign_ids",
            "adgroup_ids",
            "ad_ids",
        )
        ids = []
        for field in fields:
            value = data.get(field)
            ids.extend(value if isinstance(value, list) else [value] if value else [])
        if not ids or any(str(item) not in self.created for item in ids):
            raise PermissionError("update is not a resource created by this test")

    def send(self, session, request, **kwargs):
        host = urlsplit(request.url).hostname
        provider = next((p for p, domain in HOSTS.items() if host == domain), None)
        if provider is None:
            return self.original(session, request, **kwargs)
        data = _request_data(request)
        self._guard(request, provider, data)
        case = dict(self.case)
        started = time.monotonic()
        try:
            response = self.original(session, request, **kwargs)
        except requests.RequestException as error:
            self._record_transport(
                case, provider, request, started, transport_error=type(error).__name__
            )
            raise
        try:
            document = response.json()
        except ValueError:
            document = {}
        path = urlsplit(request.url).path
        creates = (
            "/create/" in path
            or (
                provider == "meta"
                and path.rstrip("/").endswith(
                    ("/campaigns", "/adsets", "/adcreatives", "/ads")
                )
            )
            or (
                provider == "google-ads"
                and ":mutate" in path
                and any("create" in node for node in _walk(data))
            )
        )
        if (
            request.method == "POST"
            and response.ok
            and creates
            and isinstance(document, dict)
            and not document.get("error")
            and document.get("code") in (None, 0)
        ):
            self._capture_ids(document)
        payload = document.get("data") if isinstance(document, dict) else None
        payload = payload if isinstance(payload, dict) else {}
        self._record_transport(
            case,
            provider,
            request,
            started,
            http_status=response.status_code,
            provider_code=document.get("code") if isinstance(document, dict) else None,
            request_id=response.headers.get("request-id")
            or response.headers.get("x-fb-trace-id")
            or (document.get("request_id") if isinstance(document, dict) else None),
            data_keys=sorted(payload),
            collection_counts={key: len(value) for key, value in payload.items() if isinstance(value, list)},
        )
        return response

    def _record_transport(self, case, provider, request, started, **details):
        row = {
            "case_id": case.get("case_id"),
            "provider": provider,
            "method": request.method,
            "path": re.sub(r"\d{6,}", "[resource]", urlsplit(request.url).path),
            "elapsed_seconds": round(time.monotonic() - started, 3),
            **details,
        }
        with (
            self.lock,
            (self.root / "provider-http.jsonl").open("a", encoding="utf-8") as handle,
        ):
            handle.write(json.dumps(row) + "\n")

    def _capture_ids(self, document):
        fields = {
            "id",
            "campaign_id",
            "adgroup_id",
            "adset_id",
            "ad_id",
            "ad_ids",
            "creative_id",
            "asset_group_id",
            "resourceName",
        }
        for node in _walk(document):
            for field in fields:
                value = node.get(field)
                if isinstance(value, (str, int)):
                    self.created.add(str(value))
                elif isinstance(value, list):
                    self.created.update(str(item) for item in value)
        _json_write(self.root / "created-resource-ids.json", sorted(self.created))


def serve(directory, port):
    import uvicorn

    root = Path(directory)
    handler = logging.FileHandler(root / "service.log", encoding="utf-8")
    handler.setFormatter(SafeFormatter())
    logging.basicConfig(handlers=[handler], level=logging.INFO, force=True)
    recorder = ProviderRecorder(root)
    recorder.install()
    from agents.deployments.advertising.api_server import app

    @app.middleware("http")
    async def scope(request, call_next):
        if request.url.path == "/chat":
            recorder.case = {
                "case_id": request.headers.get("x-e2e-case", ""),
                "provider": request.headers.get("x-e2e-provider", ""),
                "account": request.headers.get("x-e2e-account", ""),
            }
        return await call_next(request)

    uvicorn.run(app, host="127.0.0.1", port=port, log_config=None)


def chat(directory, provider, tool, params, case_id, write=False):
    root, state, headers = _load_state(directory)
    account = str(state["accounts"][provider][0])
    headers = {
        **headers,
        "X-E2E-Case": case_id,
        "X-E2E-Provider": provider,
        "X-E2E-Account": account,
    }
    body = {
        "user_input": (
            f"这是受控测试。仅使用 {provider} 测试账户 {account}。请执行工具 {tool} 一次，"
            "不得执行其他渠道工具，不得启用广告。严格原样使用下方 JSON 作为工具参数，"
            "不能额外添加 JSON 里没有的字段（尤其 customer_id、account_id）；账户范围已由请求上下文提供。"
            "账号所有者已授权本轮暂停资源功能测试。需要确认时先调用工具，让平台返回结构化确认凭证，"
            "不要只用文字询问确认；平台门禁仍必须完整执行。"
            "缺少必需参数时明确指出，不得猜测。参数："
            + json.dumps(params, ensure_ascii=False)
        ),
        "session_id": f"qa-{provider}-{case_id}",
        "account_id": account,
        "platform_params": {provider: params},
        "execution_mode": "live" if write else "dry_run",
    }
    evidence = {"provider": provider, "tool": tool, "params": params, "phases": []}
    case_path = root / "cases" / f"{case_id}.json"

    def request_phase(phase):
        try:
            response = requests.post(
                state["base_url"] + "/chat", json=body, headers=headers, timeout=180
            )
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as error:
            evidence["phases"].append(
                {"phase": phase, "transport_error": type(error).__name__}
            )
            _json_write(case_path, evidence)
            raise
        evidence["phases"].append(
            {"phase": phase, "http_status": response.status_code, "response": payload}
        )
        evidence.update(response=payload, summary=summarize_chat(payload, tool))
        _json_write(case_path, evidence)
        return payload

    payload = request_phase("initial")
    if (
        write
        and payload.get("needs_confirmation")
        and payload.get("confirmation_payload")
    ):
        body.update(
            confirmed=True, confirmation_payload=payload["confirmation_payload"]
        )
        body["user_input"] += (
            " 已明确确认刚才平台返回的计划：confirmed=true。"
            "HTTP 外层已携带平台签名的 confirmation_payload，不是豁免门禁。"
            "请实际再次调用同一工具和原参数，由平台验证审批签名、权限和幂等。"
            "不要向工具参数添加 confirm/confirmed 字段，不要停留在文字询问确认。"
        )
        payload = request_phase("confirmed")
    print(json.dumps(compact_summary(payload, tool), ensure_ascii=False))
    return payload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=("start", "serve", "chat", "catalog", "stop", "report")
    )
    parser.add_argument("--directory", required=True)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--provider", choices=PROVIDERS)
    parser.add_argument("--tool")
    parser.add_argument("--params", default="{}")
    parser.add_argument("--case-id", default="probe")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    if args.command == "start":
        start(args.directory, args.port)
    elif args.command == "serve":
        serve(args.directory, args.port)
    elif args.command == "chat":
        chat(
            args.directory,
            args.provider,
            args.tool,
            json.loads(args.params),
            args.case_id,
            args.write,
        )
    elif args.command == "report":
        report(args.directory)
    else:
        root, state, headers = _load_state(args.directory)
        if args.command == "catalog":
            response = requests.get(
                state["base_url"] + "/tools", headers=headers, timeout=30
            )
            response.raise_for_status()
            tools = [
                item
                for item in response.json()["tools"]
                if not args.provider or item["platform"] == args.provider
            ]
            _json_write(root / "tools.json", tools)
            print(json.dumps(tools, ensure_ascii=False))
        else:
            import signal

            os.kill(state["pid"], signal.SIGTERM)
            Path(state["private_auth_file"]).unlink(missing_ok=True)


if __name__ == "__main__":
    main()
