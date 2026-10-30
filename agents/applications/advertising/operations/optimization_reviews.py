"""Durable proposal/readback/outcome bookkeeping within the existing Tool gates."""

from datetime import datetime, timedelta, timezone
import hashlib
import json

from agents.agent_harness.core.interfaces import ToolResult
from agents.agent_harness.core.namespace import normalize_namespace
from agents.agent_harness.redaction import redact_for_persistence
from .optimization_measurements import validate_measurement, compare_measurements
from .optimization_evidence import load_evidence, utc_time, value_at, same_value
from .optimization_report_evidence import measurement_provenance


class OptimizationReviewService:
    def __init__(self, store, registry, *, now=None):
        self.store, self.registry = store, registry
        self.now = now or (lambda: datetime.now(timezone.utc))

    def _principal(self, context):
        if self.store is None:
            raise ValueError("复盘存储尚未配置，无法保存或读取记录")
        principal = getattr(context, "principal", None)
        if principal is None or not principal.user_id or not principal.tenant_id:
            raise ValueError("需要可信身份")
        return principal

    @staticmethod
    def _scope(principal, row):
        scopes = principal.account_scope
        normalized = {normalize_namespace(key): value for key, value in (scopes or {}).items()}
        allowed = normalized.get(normalize_namespace(row["namespace"]), ())
        if row["account_id"] not in allowed:
            raise ValueError("目标账户不在当前身份授权范围内")

    def create(self, context, arguments):
        try:
            arguments = {**arguments, "namespace": normalize_namespace(arguments["namespace"])}
            principal = self._principal(context)
            self._scope(principal, arguments)
            if redact_for_persistence(arguments) != arguments:
                raise ValueError("复盘记录不能包含凭证")
            validate_measurement(arguments["baseline"], self.now().date())
            provenance = measurement_provenance(
                self.store, self.registry, principal, arguments, arguments["baseline"],
                arguments.get("baseline_evidence"),
            )
            key = [principal.tenant_id, principal.user_id] + [
                arguments[field]
                for field in ("namespace", "account_id", "resource_type", "resource_id", "field")
            ]
            review_id = hashlib.sha256(json.dumps(key).encode()).hexdigest()
            old = self.store.get_optimization_review(
                review_id, principal.tenant_id, principal.user_id
            )
            if old:
                return self._existing(old, arguments)
            row = {
                **arguments,
                "id": review_id,
                "status": "proposed",
                "version": 1,
                "created_at": self.now().isoformat(),
                "source_run_id": context.metadata.get("run_id"),
                "history": [{"status": "proposed", "at": self.now().isoformat()}],
                "approval_status": "not_approved",
                "external_write_performed": False,
                "baseline_provenance": provenance,
            }
            return self._save(principal, row, 0)
        except (ValueError, KeyError, TypeError) as error:
            return ToolResult.error(str(error))

    @staticmethod
    def _existing(old, arguments):
        if all(old.get(key) == value for key, value in arguments.items()):
            return ToolResult.ok({"review": old, "deduplicated": True})
        raise ValueError("该资源字段已有优化记录，请先完成回读和复盘；新一轮使用显式 reopen 操作")

    def read(self, context, arguments):
        try:
            principal = self._principal(context)
            if arguments.get("review_id"):
                row = self._owned(principal, arguments["review_id"])
                return ToolResult.ok({"review": row})
            limit = min(20, max(1, arguments.get("limit", 10)))
            rows = self.store.list_optimization_reviews(
                principal.tenant_id, principal.user_id, limit + 1, arguments.get("offset", 0)
            )
            visible = [
                {
                    key: row.get(key)
                    for key in (
                        "id",
                        "version",
                        "status",
                        "namespace",
                        "account_id",
                        "resource_type",
                        "resource_id",
                        "created_at",
                        "proposal",
                        "result",
                    )
                }
                for row in rows[:limit]
                if self._visible(principal, row)
            ]
            return ToolResult.ok(
                {
                    "reviews": visible,
                    "has_more": len(rows) > limit,
                    "next_offset": arguments.get("offset", 0) + len(rows[:limit]),
                }
            )
        except (ValueError, KeyError, TypeError) as error:
            return ToolResult.error(str(error))

    def _visible(self, principal, row):
        try:
            self._scope(principal, row)
            return True
        except ValueError:
            return False

    def _owned(self, principal, review_id):
        row = self.store.get_optimization_review(review_id, principal.tenant_id, principal.user_id)
        if not row:
            raise ValueError("复盘记录不存在或不属于当前身份")
        self._scope(principal, row)
        return row

    def _save(self, principal, row, version):
        if not self.store.save_optimization_review(
            row["id"], principal.tenant_id, principal.user_id, row, expected_version=version
        ):
            raise ValueError("记录版本已变化，请重新读取后再修改")
        return ToolResult.ok({"review": {**row, "version": version + 1}})

    def update(self, context, arguments):
        try:
            principal = self._principal(context)
            row = self._owned(principal, arguments["review_id"])
            version = arguments["expected_version"]
            if row["version"] != version:
                raise ValueError("记录版本已变化")
            if redact_for_persistence(arguments) != arguments:
                raise ValueError("复盘记录不能包含凭证")
            action = arguments["action"]
            if action == "review":
                self._review(principal, row, arguments)
            elif action == "reopen":
                self._reopen(principal, row, arguments)
            elif action in {"link_execution", "verify_readback"}:
                self._link(principal, row, arguments)
            else:
                raise ValueError("不支持的复盘操作")
            row["history"] = (
                row["history"] + [{"status": row["status"], "at": self.now().isoformat()}]
            )[-20:]
            return self._save(principal, row, version)
        except (ValueError, KeyError, TypeError) as error:
            return ToolResult.error(str(error))

    def _link(self, principal, row, arguments):
        writing = arguments["action"] == "link_execution"
        required_status = "proposed" if writing else "executed"
        if row["status"] != required_status:
            raise ValueError("执行与回读必须按顺序登记")
        record, definition = load_evidence(
            self.store, self.registry, principal, arguments["evidence"], row, writing=writing
        )
        if writing:
            if not same_value(value_at(record.input_data, row["field"]), row["expected_value"]):
                raise ValueError("执行参数与建议变更不一致")
            if utc_time(record.ended_at) < utc_time(row["created_at"]):
                raise ValueError("执行证据早于本次建议")
            row.update(
                status="executed",
                executed_at=record.ended_at,
                execution=arguments["evidence"],
                readback_tool=definition.readback_tool,
                approval_status="verified_runtime_gates",
            )
        else:
            if record.tool_name != row["readback_tool"] or utc_time(record.ended_at) < utc_time(
                row["executed_at"]
            ):
                raise ValueError("回读工具或时间与执行证据不一致")
            if not same_value(
                value_at(record.output_data, arguments["readback_path"]), row["expected_value"]
            ):
                raise ValueError("回读结果未确认预期变更")
            row.update(status="verified", readback=arguments["evidence"])

    def _review(self, principal, row, arguments):
        if row["status"] != "verified":
            raise ValueError("尚未验证实际执行及回读，不能宣称优化效果")
        row["result"] = compare_measurements(
            row["baseline"],
            arguments["outcome"],
            executed_at=utc_time(row["executed_at"]),
            observation_days=row["observation_days"],
            today=self.now().date(),
        )
        provenance = measurement_provenance(
            self.store, self.registry, principal, row, arguments["outcome"],
            arguments.get("outcome_evidence"),
        )
        row["outcome_provenance"] = provenance
        statuses = {row.get("baseline_provenance", {}).get("status"), provenance["status"]}
        if statuses <= {"audited_report", "audited_value_declared_context"}:
            row["result"]["evidence_status"] = "audited_values_with_context_gaps"
        row["result"]["context_gaps"] = sorted(set(
            row.get("baseline_provenance", {}).get("unverified_context_fields", [])
            + provenance["unverified_context_fields"]
        ))
        row.update(
            status="reviewed", outcome=arguments["outcome"], reviewed_at=self.now().isoformat()
        )

    def _reopen(self, principal, row, arguments):
        if row["status"] != "reviewed":
            raise ValueError("上一轮尚未完成复盘")
        if self.now() < utc_time(row["executed_at"]) + timedelta(days=row["cooldown_days"]):
            raise ValueError("仍在冷却期")
        baseline = arguments["outcome"]
        validate_measurement(baseline, self.now().date())
        provenance = measurement_provenance(
            self.store, self.registry, principal, row, baseline, arguments.get("outcome_evidence"),
        )
        previous = {
            key: row.get(key)
            for key in (
                "version",
                "proposal",
                "baseline",
                "outcome",
                "result",
                "execution",
                "readback",
                "baseline_provenance", "outcome_provenance",
            )
        }
        row.update(
            previous_cycle=previous,
            baseline=baseline,
            baseline_provenance=provenance,
            expected_value=arguments["expected_value"],
            proposal=arguments["proposal"],
            status="proposed",
            created_at=self.now().isoformat(),
            approval_status="not_approved",
        )
        for key in (
            "outcome",
            "result",
            "executed_at",
            "execution",
            "readback",
            "reviewed_at",
            "readback_tool",
            "outcome_provenance", "baseline_evidence",
        ):
            row.pop(key, None)
