"""跨渠道统一 Campaign 与指标模型。

平台 API 的字段、货币和报表结构不同。本模块只做无副作用的规范化与
聚合，不发起任何平台请求，也不把缺失指标填成 0。
"""

from dataclasses import dataclass, field
import csv
import io
from typing import Any, Iterable, Optional
from .platform import normalize_platform


def _number(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class CampaignRef:
    """Unambiguous Campaign identity across provider boundaries."""

    platform: str
    account_id: str
    campaign_id: str

    def __post_init__(self) -> None:
        platform = str(self.platform or "").strip().lower()
        account_id = str(self.account_id or "").strip()
        campaign_id = str(self.campaign_id or "").strip()
        if not platform or not account_id or not campaign_id:
            raise ValueError("CampaignRef requires platform, account_id and campaign_id")
        object.__setattr__(self, "platform", platform)
        object.__setattr__(self, "account_id", account_id)
        object.__setattr__(self, "campaign_id", campaign_id)

    def to_dict(self) -> dict[str, str]:
        return {
            "platform": self.platform,
            "account_id": self.account_id,
            "campaign_id": self.campaign_id,
        }


@dataclass
class MetricSnapshot:
    impressions: Optional[float] = None
    clicks: Optional[float] = None
    spend: Optional[float] = None
    conversions: Optional[float] = None
    revenue: Optional[float] = None
    currency: Optional[str] = None
    source: str = "unknown"
    available_fields: set[str] = field(default_factory=set)

    def add(self, other: "MetricSnapshot") -> None:
        for field_name in ("impressions", "clicks", "spend", "conversions", "revenue"):
            value = getattr(other, field_name)
            if value is None:
                continue
            current = getattr(self, field_name)
            setattr(self, field_name, value if current is None else current + value)
            self.available_fields.add(field_name)
        if not self.currency:
            self.currency = other.currency
        if self.source == "unknown" and other.source != "unknown":
            self.source = other.source
        self.available_fields.update(other.available_fields)

    def to_dict(self) -> dict[str, Any]:
        values: dict[str, Any] = {
            name: getattr(self, name)
            for name in ("impressions", "clicks", "spend", "conversions", "revenue")
            if getattr(self, name) is not None
        }
        # Derived metrics are emitted only when their denominator exists.
        if self.clicks is not None and self.impressions:
            values["ctr"] = self.clicks / self.impressions
            self.available_fields.add("ctr")
        if self.spend is not None and self.clicks:
            values["cpc"] = self.spend / self.clicks
            self.available_fields.add("cpc")
        if self.spend is not None and self.conversions:
            values["cpa"] = self.spend / self.conversions
            self.available_fields.add("cpa")
        if self.revenue is not None and self.spend:
            values["roas"] = self.revenue / self.spend
            self.available_fields.add("roas")
        values["currency"] = self.currency
        values["source"] = self.source
        return values


@dataclass
class CampaignRecord:
    """跨渠道展示用的规范化 Campaign 记录。"""

    platform: str
    account_id: Optional[str]
    campaign_id: Optional[str]
    name: Optional[str]
    status: Optional[str]
    objective: Optional[str]
    budget: Optional[float]
    currency: Optional[str]
    metrics: MetricSnapshot = field(default_factory=MetricSnapshot)
    data_status: str = "unknown"
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "platform": self.platform,
            "account_id": self.account_id,
            "campaign_id": self.campaign_id,
            "name": self.name,
            "status": self.status,
            "objective": self.objective,
            "budget": self.budget,
            "currency": self.currency,
            "metrics": self.metrics.to_dict(),
            "data_status": self.data_status,
        }


@dataclass(frozen=True)
class BatchOperation:
    """One platform-scoped Campaign operation in a batch plan.

    This is a planning model only.  It intentionally contains no Client or
    credential reference, which makes it safe to preview and persist before a
    later, explicitly approved execution step.
    """

    platform: str
    account_id: str
    campaign_id: str
    action: str
    updates: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Validate the complete scope at construction time. The operation
        # remains a provider-neutral plan and contains no client or secret.
        campaign_ref = CampaignRef(self.platform, self.account_id, self.campaign_id)
        object.__setattr__(self, "platform", campaign_ref.platform)
        object.__setattr__(self, "account_id", campaign_ref.account_id)
        object.__setattr__(self, "campaign_id", campaign_ref.campaign_id)
        action = str(self.action or "").strip().lower()
        if not action:
            raise ValueError("BatchOperation requires action")
        if action not in {"pause", "resume", "update_budget", "delete"}:
            raise ValueError(f"Unsupported BatchOperation action: {action}")
        object.__setattr__(self, "action", action)

    @property
    def campaign_ref(self) -> CampaignRef:
        return CampaignRef(self.platform, self.account_id, self.campaign_id)

    def to_dict(self) -> dict[str, Any]:
        return {
            "platform": self.platform,
            "account_id": self.account_id,
            "campaign_id": self.campaign_id,
            "campaign_ref": self.campaign_ref.to_dict(),
            "action": self.action,
            "updates": dict(self.updates),
        }


def build_batch_operations(
    intent: Any,
    accounts: dict[str, str],
    *,
    supported_platforms: Optional[set[str]] = None,
    blocked_platforms: Optional[set[str]] = None,
) -> tuple[list[BatchOperation], list[str]]:
    """Build validated platform-scoped batch operations from ParsedIntent.

    The function deliberately does not infer an ID from another platform.  A
    missing platform-specific ID is reported as an error instead of risking an
    operation against the wrong Campaign.
    """
    action_map = {
        "cross_channel_batch_pause": "pause",
        "cross_channel_batch_resume": "resume",
        "cross_channel_batch_update_budget": "update_budget",
        "cross_channel_batch_delete": "delete",
    }
    action = action_map.get(getattr(intent, "intent_type", ""))
    if not action:
        return [], ["unsupported batch intent"]

    operations: list[BatchOperation] = []
    errors: list[str] = []
    supported = (
        {normalize_platform(platform) for platform in supported_platforms}
        if supported_platforms is not None else None
    )
    blocked = {
        normalize_platform(platform) for platform in (blocked_platforms or set())
    }
    for platform in getattr(intent, "platforms", []) or []:
        actual_platform = normalize_platform(platform)
        # Tool discovery is authoritative for whether a provider can take
        # part in this batch. The Runtime reports the unsupported platform;
        # the core planner must not manufacture an account/id error for it.
        if supported is not None and actual_platform not in supported:
            continue
        if actual_platform in blocked:
            continue

        platform_params = getattr(intent, "platform_params", {}) or {}
        params = platform_params.get(platform, {})
        if not isinstance(params, dict):
            params = platform_params.get(actual_platform, {})
        if not isinstance(params, dict):
            params = {}
        # Accept both platform-level arguments and a Tool-scoped argument
        # object. This keeps the planner compatible with provider-owned
        # schemas without adding provider names to Core.
        parameter_sources = [params]
        parameter_sources.extend(
            value for value in params.values() if isinstance(value, dict)
        )
        raw_ids = next(
            (
                source.get("campaign_ids", source.get("campaign_id"))
                for source in parameter_sources
                if source.get("campaign_ids", source.get("campaign_id")) is not None
            ),
            None,
        )
        if isinstance(raw_ids, str):
            raw_ids = [value.strip() for value in raw_ids.replace("，", ",").split(",")]
        elif raw_ids is None:
            raw_ids = []
        elif not isinstance(raw_ids, (list, tuple, set)):
            raw_ids = [raw_ids]
        campaign_ids = [str(value).strip() for value in raw_ids if str(value).strip()]
        campaign_ids = list(dict.fromkeys(campaign_ids))
        if not campaign_ids:
            errors.append(f"{actual_platform}: 缺少 campaign_id/campaign_ids")
            continue
        account_id = accounts.get(actual_platform) or accounts.get(platform)
        if not account_id:
            errors.append(f"{actual_platform}: 缺少账户ID")
            continue

        if action == "pause":
            # Keep the cross-channel model provider-neutral.  The selected
            # Capability's update contract owns the wire field/value mapping.
            updates = {"status": "PAUSED"}
        elif action == "resume":
            updates = {"status": "ACTIVE"}
        elif action == "delete":
            # Deletion has no provider-neutral update payload.  The selected
            # Capability's delete Tool owns the actual provider operation;
            # this layer only carries the scoped identity into the dry-run
            # plan.
            updates = {}
        else:
            supplied = next(
                (
                    source.get("updates")
                    for source in parameter_sources
                    if isinstance(source.get("updates"), dict)
                ),
                {},
            )
            supplied = dict(supplied) if isinstance(supplied, dict) else {}
            budget = supplied.get(
                "daily_budget",
                supplied.get(
                    "budget",
                    next(
                        (
                            source.get("budget", source.get("daily_budget"))
                            for source in parameter_sources
                            if source.get("budget", source.get("daily_budget")) is not None
                        ),
                        None,
                    ),
                ),
            )
            if budget is None:
                budget = getattr(intent, "budget", None)
            try:
                budget = float(budget)
            except (TypeError, ValueError):
                budget = None
            if budget is None or budget <= 0:
                errors.append(f"{actual_platform}: 预算必须是大于 0 的数字")
                continue
            updates = {**supplied, "daily_budget": budget}

        operations.extend(
            BatchOperation(actual_platform, str(account_id), campaign_id, action, updates)
            for campaign_id in campaign_ids
        )
    return operations, errors


class CrossChannelAggregator:
    """把 Runtime 工具结果汇总为可比较的跨渠道结构。"""

    METRIC_ALIASES = {
        "impressions": ("impressions", "total_impressions"),
        "clicks": ("clicks", "total_clicks"),
        "spend": ("spend", "cost", "cost_micros", "total_spend"),
        "conversions": ("conversions", "total_conversions"),
        "revenue": ("revenue", "conversion_value", "total_revenue"),
    }

    def _metrics_from(self, data: Any, source: str = "unknown") -> MetricSnapshot:
        if not isinstance(data, dict):
            return MetricSnapshot(source=source)
        values: dict[str, Optional[float]] = {}
        available: set[str] = set()
        for metric, aliases in self.METRIC_ALIASES.items():
            for alias in aliases:
                if alias in data:
                    value = _number(data.get(alias))
                    if value is not None:
                        if alias == "cost_micros":
                            value /= 1_000_000
                        values[metric] = value
                        available.add(metric)
                        break
        # Meta returns conversion data as action arrays rather than a scalar
        # ``conversions`` field. Only count well-defined conversion actions;
        # do not treat every action (for example, link clicks) as a conversion.
        if "conversions" not in values:
            conversion_types = {
                "purchase", "omni_purchase", "offsite_conversion",
                "offsite_conversion.purchase", "lead", "complete_registration",
            }
            action_values = []
            for action in data.get("actions", []) or []:
                if not isinstance(action, dict):
                    continue
                action_type = str(action.get("action_type", "")).lower()
                if action_type in conversion_types:
                    value = _number(action.get("value"))
                    if value is not None:
                        action_values.append(value)
            if action_values:
                values["conversions"] = sum(action_values)
                available.add("conversions")
        if "revenue" not in values:
            revenue_types = {"purchase", "omni_purchase", "offsite_conversion.purchase"}
            revenue_values = []
            for action in data.get("action_values", []) or []:
                if not isinstance(action, dict):
                    continue
                action_type = str(action.get("action_type", "")).lower()
                if action_type in revenue_types:
                    value = _number(action.get("value"))
                    if value is not None:
                        revenue_values.append(value)
            if revenue_values:
                values["revenue"] = sum(revenue_values)
                available.add("revenue")
        currency = data.get("currency") or data.get("currency_code")
        return MetricSnapshot(
            **values,
            currency=str(currency) if currency else None,
            source=source,
            available_fields=available,
        )

    def _campaigns_from_result(self, platform: str, result: dict) -> list[CampaignRecord]:
        data = result.get("data") if isinstance(result, dict) else {}
        if not isinstance(data, dict):
            return []
        data_status = data.get("data_status")
        if not data_status:
            data_status = "simulated" if data.get("simulated") else "unknown"
        campaigns = data.get("campaigns") or []
        if not campaigns:
            report = data.get("report")
            if isinstance(report, list):
                campaigns = report
            elif isinstance(report, dict):
                for key in ("data", "results", "rows", "list"):
                    if isinstance(report.get(key), list):
                        campaigns = report[key]
                        break
                if not campaigns and ("metrics" in report or "campaign" in report):
                    campaigns = [report]
        records = []
        for item in campaigns if isinstance(campaigns, list) else []:
            if not isinstance(item, dict):
                continue
            nested_campaign = item.get("campaign") if isinstance(item.get("campaign"), dict) else {}
            metric_payload = item.get("metrics") or nested_campaign.get("metrics") or item
            if isinstance(metric_payload, dict) and item.get("currency") and "currency" not in metric_payload:
                metric_payload = {**metric_payload, "currency": item["currency"]}
            metrics = self._metrics_from(metric_payload, data_status)
            budget = _number(item.get("budget", item.get("daily_budget")))
            campaign_id = (
                item.get("id") or item.get("campaign_id") or item.get("campaign_group_id")
                or item.get("campaignGroupId") or nested_campaign.get("id")
                or nested_campaign.get("campaign_id")
            )
            campaign_name = (
                item.get("name") or item.get("campaign_name") or item.get("campaign_group_name")
                or nested_campaign.get("name") or nested_campaign.get("campaign_name")
            )
            records.append(CampaignRecord(
                platform=platform,
                account_id=(
                    item.get("account_id") or item.get("advertiser_id")
                    or item.get("customer_id") or data.get("account_id")
                    or data.get("advertiser_id") or data.get("customer_id")
                    or result.get("account_id")
                ),
                campaign_id=str(campaign_id) if campaign_id else None,
                name=campaign_name,
                status=item.get("status") or item.get("operation_status"),
                objective=item.get("objective") or item.get("objective_type") or nested_campaign.get("objective"),
                budget=budget,
                currency=metrics.currency or item.get("currency") or nested_campaign.get("currency"),
                metrics=metrics,
                data_status=data_status,
                raw=item,
            ))
        return records

    @staticmethod
    def _merge_record_metrics(
        target: CampaignRecord, incoming: CampaignRecord
    ) -> tuple[bool, bool]:
        """Merge rows without assigning an unknown currency to money fields.

        Returns ``(unknown_monetary_value, currency_conflict)`` so aggregate
        totals can remain fail-closed even when the unsafe amount is omitted
        from the coalesced Campaign row.
        """
        target_currency = str(target.currency or target.metrics.currency or "").upper()
        incoming_currency = str(incoming.currency or incoming.metrics.currency or "").upper()
        money_fields = ("spend", "revenue")
        non_money_fields = ("impressions", "clicks", "conversions")

        for field_name in non_money_fields:
            value = getattr(incoming.metrics, field_name)
            if value is not None:
                current = getattr(target.metrics, field_name)
                setattr(target.metrics, field_name, value if current is None else current + value)
                target.metrics.available_fields.add(field_name)

        incoming_has_money = any(getattr(incoming.metrics, name) is not None for name in money_fields)
        target_has_money = any(getattr(target.metrics, name) is not None for name in money_fields)
        currencies_match = bool(target_currency and incoming_currency and target_currency == incoming_currency)

        if incoming_has_money and not incoming_currency:
            if target_has_money:
                for field_name in money_fields:
                    setattr(target.metrics, field_name, None)
                    target.metrics.available_fields.discard(field_name)
                target.currency = None
                target.metrics.currency = None
            return True, False

        if incoming_has_money and (target_has_money or incoming_currency):
            if not currencies_match:
                # Existing and incoming amounts cannot be safely compared. A
                # listing currency is not evidence for a report row that
                # omitted its currency, so clear both monetary fields.
                for field_name in money_fields:
                    setattr(target.metrics, field_name, None)
                    target.metrics.available_fields.discard(field_name)
                target.currency = None
                target.metrics.currency = None
                return False, True
            else:
                for field_name in money_fields:
                    value = getattr(incoming.metrics, field_name)
                    if value is not None:
                        current = getattr(target.metrics, field_name)
                        setattr(target.metrics, field_name, value if current is None else current + value)
                        target.metrics.available_fields.add(field_name)
                target.currency = target.currency or incoming.currency
                target.metrics.currency = target.metrics.currency or incoming.metrics.currency

        target.metrics.source = (
            target.metrics.source
            if target.metrics.source != "unknown"
            else incoming.metrics.source
        )
        return False, False

    def aggregate(self, results: Iterable[dict]) -> dict[str, Any]:
        # A comparison has at least two result rows per platform (campaign
        # listing followed by campaign-scoped report).  Accumulate them before
        # rendering; assigning ``by_platform[platform]`` for every row used to
        # overwrite the listing and made the final Campaign count/name vanish.
        grouped: dict[str, dict[str, Any]] = {}
        for result in results:
            if not isinstance(result, dict):
                continue
            platform = str(result.get("platform") or "unknown")
            data = result.get("data") if isinstance(result.get("data"), dict) else {}
            bucket = grouped.setdefault(
                platform,
                {
                    "records": {}, "anonymous_records": [], "standalone_metrics": [],
                    "statuses": [], "unknown_monetary": False, "currency_conflict": False,
                },
            )
            status = data.get("data_status") or ("simulated" if data.get("simulated") else "unknown")
            bucket["statuses"].append(status)
            records = self._campaigns_from_result(platform, result)
            for record in records:
                # Campaign listing and report rows should coalesce by ID.  If
                # an adapter cannot provide an ID, retain the row separately
                # rather than silently dropping it.
                key = record.campaign_id
                if key is None:
                    bucket["anonymous_records"].append(record)
                    continue
                existing = bucket["records"].get(key)
                if existing is None:
                    bucket["records"][key] = record
                    continue
                if not existing.name and record.name:
                    existing.name = record.name
                if not existing.status and record.status:
                    existing.status = record.status
                if not existing.objective and record.objective:
                    existing.objective = record.objective
                if existing.budget is None and record.budget is not None:
                    existing.budget = record.budget
                if not existing.currency and record.currency:
                    existing.currency = record.currency
                existing.data_status = self._merge_data_status(
                    existing.data_status, record.data_status
                )
                unknown_monetary, currency_conflict = self._merge_record_metrics(existing, record)
                bucket["unknown_monetary"] = bucket["unknown_monetary"] or unknown_monetary
                bucket["currency_conflict"] = bucket["currency_conflict"] or currency_conflict

            # Report handlers may return aggregate metrics without campaign
            # rows. Keep these separate so they are counted once and do not
            # erase the Campaign listing.
            if not records:
                aggregate_metrics = self._metrics_from(
                    data.get("metrics"), status
                )
                summary = data.get("summary")
                if isinstance(summary, dict):
                    aggregate_metrics.add(self._metrics_from(summary, status))
                if aggregate_metrics.available_fields:
                    bucket["standalone_metrics"].append(aggregate_metrics)

        by_platform: dict[str, dict[str, Any]] = {}
        totals = MetricSnapshot()
        currency_metrics: dict[str, MetricSnapshot] = {}
        monetary_without_currency = False
        mixed_currency = False
        currency_conflict = False
        total_campaigns = 0
        currencies: set[str] = set()
        metric_platform_counts: dict[str, int] = {}
        for platform, bucket in grouped.items():
            records = list(bucket["records"].values()) + bucket["anonymous_records"]
            platform_metrics = MetricSnapshot()
            # A known-currency row must never absorb a monetary value from a
            # different row whose currency is absent.  The coalescing path
            # catches same-Campaign conflicts; this catches independent rows.
            if any(
                any(getattr(record.metrics, name) is not None for name in ("spend", "revenue"))
                and not (record.currency or record.metrics.currency)
                for record in records
            ):
                bucket["unknown_monetary"] = True
            record_currencies = {
                str(record.currency).upper()
                for record in records
                if record.currency
            }
            for record in records:
                platform_metrics.add(record.metrics)
            for metric in bucket["standalone_metrics"]:
                platform_metrics.add(metric)
                if (
                    any(getattr(metric, name) is not None for name in ("spend", "revenue"))
                    and not metric.currency
                ):
                    bucket["unknown_monetary"] = True

            total_campaigns += len(records)
            # A provider can return rows in inconsistent/unknown currencies.
            # Never add those monetary values together, even within one
            # platform bucket.
            if len(record_currencies) > 1:
                bucket["currency_conflict"] = True
                platform_metrics.spend = None
                platform_metrics.revenue = None
                platform_metrics.available_fields.discard("spend")
                platform_metrics.available_fields.discard("revenue")
                platform_metrics.currency = None
            for field_name in ("impressions", "clicks", "spend", "conversions", "revenue"):
                if field_name in platform_metrics.available_fields:
                    metric_platform_counts[field_name] = metric_platform_counts.get(field_name, 0) + 1
            if any(field_name in platform_metrics.available_fields for field_name in ("spend", "revenue")):
                currency = str(platform_metrics.currency or "").upper()
                if not currency:
                    monetary_without_currency = True
                else:
                    # Add one platform snapshot to its currency bucket.  A
                    # loop over spend and revenue would add both monetary
                    # fields twice when a platform returns both.
                    currency_metrics.setdefault(currency, MetricSnapshot(currency=currency)).add(platform_metrics)
            # Add only non-monetary fields to the cross-channel totals here;
            # monetary fields are selected from one currency bucket below.
            for field_name in ("impressions", "clicks", "conversions"):
                value = getattr(platform_metrics, field_name)
                if value is not None:
                    setattr(totals, field_name, (getattr(totals, field_name) or 0) + value)
                    totals.available_fields.add(field_name)
            if platform_metrics.currency:
                currencies.add(str(platform_metrics.currency).upper())
            statuses = bucket["statuses"]
            data_status = "live" if "live" in statuses else next(
                (value for value in statuses if value != "unknown"), "unknown"
            )
            by_platform[platform] = {
                "campaigns": len(records),
                "records": [record.to_dict() for record in records],
                "metrics": platform_metrics.to_dict(),
                "metric_availability": sorted(platform_metrics.available_fields),
                "currency": platform_metrics.currency,
                "data_status": data_status,
            }

            if bucket["unknown_monetary"]:
                monetary_without_currency = True
            if bucket["currency_conflict"]:
                mixed_currency = True
                currency_conflict = True

        mixed_currency = mixed_currency or len(currency_metrics) > 1 or monetary_without_currency
        if len(currency_metrics) == 1 and not monetary_without_currency:
            only_currency = next(iter(currency_metrics.values()))
            totals.spend = only_currency.spend
            totals.revenue = only_currency.revenue
            totals.currency = only_currency.currency
            for field_name in ("spend", "revenue"):
                if getattr(totals, field_name) is not None:
                    totals.available_fields.add(field_name)
        else:
            # Never add monetary values expressed in different or unknown
            # currencies.
            totals.spend = None
            totals.revenue = None
            totals.available_fields.discard("spend")
            totals.available_fields.discard("revenue")
            totals.currency = None

        platform_count = len(by_platform)
        incomplete_metrics = bool(
            platform_count and any(
                count < platform_count for count in metric_platform_counts.values()
            )
        )

        return {
            "schema_version": "1.0",
            "total_campaigns": total_campaigns,
            "totals": totals.to_dict(),
            "platforms": by_platform,
            "metric_availability": sorted(totals.available_fields),
            "comparability": {
                "status": "partial" if (
                    by_platform and (
                        not totals.available_fields or mixed_currency or incomplete_metrics
                    )
                ) else "available",
                "reason": (
                    "平台货币不同或同一 Campaign 存在币种冲突，未汇总 spend/revenue"
                    if mixed_currency and (len(currency_metrics) > 1 or currency_conflict)
                    else "存在未知货币，未汇总 spend/revenue"
                    if monetary_without_currency
                    else "平台未返回统一报表指标"
                    if by_platform and (not totals.available_fields or incomplete_metrics)
                    else None
                ),
            },
        }

    @staticmethod
    def _merge_data_status(current: str, incoming: str) -> str:
        """Prefer live evidence, then explicit offline states."""
        priority = {"unknown": 0, "simulated": 1, "offline_no_client": 1,
                    "offline_mock": 2, "live": 3}
        return incoming if priority.get(incoming, 0) > priority.get(current, 0) else current

    def format_markdown(self, aggregate: dict[str, Any], title: str) -> str:
        lines = [f"📊 {title}:", "", "| 平台 | Campaign 数 | Spend | Impressions | Clicks | Conversions | CTR | Data |", "|---|---:|---:|---:|---:|---:|---:|---|"]
        for platform, data in aggregate.get("platforms", {}).items():
            metrics = data.get("metrics", {})
            def display(key: str) -> str:
                value = metrics.get(key)
                if value is None:
                    return "N/A"
                if key == "ctr":
                    return f"{value:.2%}"
                if isinstance(value, float):
                    return f"{value:.2f}"
                return str(value)
            lines.append(
                f"| {platform} | {data.get('campaigns', 0)} | {display('spend')} | "
                f"{display('impressions')} | {display('clicks')} | {display('conversions')} | "
                f"{display('ctr')} | {data.get('data_status', 'unknown')} |"
            )
        availability = ", ".join(aggregate.get("metric_availability", [])) or "无统一指标"
        lines.extend(["", f"可比较指标: {availability}"])
        if aggregate.get("comparability", {}).get("status") == "partial":
            reason = aggregate.get("comparability", {}).get("reason") or "指标不完整"
            lines.append(f"⚠️ 跨渠道结果部分可比：{reason}。")
        return "\n".join(lines)


class CrossChannelAnalyzer:
    """Generate local, read-only recommendations from an aggregate snapshot.

    This class deliberately has no Runtime, Client, credential, or persistence
    dependency.  It turns already collected provider data into explainable
    insights and a budget proposal; applying that proposal remains a separate
    explicit Campaign update workflow.
    """

    @staticmethod
    def performance_insights(aggregate: dict[str, Any]) -> dict[str, Any]:
        """Return explainable per-platform observations without inventing data."""
        insights: list[dict[str, Any]] = []
        for platform, bucket in (aggregate.get("platforms") or {}).items():
            metrics = bucket.get("metrics") if isinstance(bucket, dict) else {}
            metrics = metrics if isinstance(metrics, dict) else {}
            recommendations: list[str] = []
            if metrics.get("roas") is not None:
                roas = float(metrics["roas"])
                if roas < 1:
                    recommendations.append("ROAS 低于 1，建议检查转化追踪、素材与受众，并暂缓扩大预算")
                elif roas >= 3:
                    recommendations.append("ROAS 较高，可在验证边际回报后逐步增加预算")
            if metrics.get("ctr") is not None and float(metrics["ctr"]) < 0.01:
                recommendations.append("CTR 偏低，建议优先测试素材、标题和定向")
            if metrics.get("cpa") is not None:
                recommendations.append(f"当前 CPA 为 {float(metrics['cpa']):.2f} {metrics.get('currency') or ''}".strip())
            if bucket.get("data_status") not in {"live", "unknown"}:
                recommendations.append("当前数据为离线或模拟数据，不应据此执行线上预算变更")
            if not recommendations:
                recommendations.append("当前指标不足以形成明确动作，建议补充转化价值或更长观察窗口")
            insights.append({
                "platform": platform,
                "data_status": bucket.get("data_status", "unknown"),
                "currency": bucket.get("currency"),
                "metrics": metrics,
                "recommendations": recommendations,
            })

        return {
            "schema_version": "1.0",
            "status": aggregate.get("comparability", {}).get("status", "partial"),
            "insights": insights,
            "comparability": aggregate.get("comparability", {}),
        }

    @staticmethod
    def budget_plan(
        aggregate: dict[str, Any],
        total_budget: Any,
        minimum_budget: Any = None,
        maximum_budget: Any = None,
    ) -> dict[str, Any]:
        """Build a deterministic budget proposal from available metrics.

        The proposal is advisory only.  It never calls a provider or mutates a
        Campaign.  Platforms without usable metrics receive a neutral score;
        the response explicitly records the evidence and comparability state.
        """
        try:
            total = float(total_budget)
        except (TypeError, ValueError):
            return {"schema_version": "1.0", "status": "blocked", "error": "total_budget 必须是大于 0 的数字"}
        if total <= 0:
            return {"schema_version": "1.0", "status": "blocked", "error": "total_budget 必须是大于 0 的数字"}

        try:
            minimum = float(minimum_budget) if minimum_budget is not None else 0.0
        except (TypeError, ValueError):
            return {"schema_version": "1.0", "status": "blocked", "error": "minimum_budget 必须是数字"}
        try:
            maximum = float(maximum_budget) if maximum_budget is not None else None
        except (TypeError, ValueError):
            return {"schema_version": "1.0", "status": "blocked", "error": "maximum_budget 必须是数字"}
        if minimum < 0 or (maximum is not None and maximum < minimum):
            return {"schema_version": "1.0", "status": "blocked", "error": "预算上下限不合法"}

        platform_rows: list[dict[str, Any]] = []
        for platform, bucket in (aggregate.get("platforms") or {}).items():
            metrics = bucket.get("metrics") if isinstance(bucket, dict) else {}
            metrics = metrics if isinstance(metrics, dict) else {}
            score = None
            evidence = "无足够指标"
            if metrics.get("roas") is not None:
                score = max(float(metrics["roas"]), 0.0)
                evidence = "roas"
            elif metrics.get("conversions") is not None and metrics.get("spend"):
                score = max(float(metrics["conversions"]) / float(metrics["spend"]), 0.0)
                evidence = "conversions_per_spend"
            elif metrics.get("clicks") is not None and metrics.get("spend"):
                score = max(float(metrics["clicks"]) / float(metrics["spend"]), 0.0)
                evidence = "clicks_per_spend"
            else:
                score = 1.0
            platform_rows.append({
                "platform": platform,
                "score": score,
                "evidence": evidence,
                "data_status": bucket.get("data_status", "unknown"),
                "currency": bucket.get("currency"),
            })

        if not platform_rows:
            return {"schema_version": "1.0", "status": "blocked", "error": "没有可分配预算的平台数据"}
        if minimum * len(platform_rows) > total:
            return {"schema_version": "1.0", "status": "blocked", "error": "minimum_budget 总和超过 total_budget"}

        # Reserve the floor, then distribute the remainder by score.  The
        # stable platform sort makes the result reproducible for confirmation
        # and audit purposes.
        rows = sorted(platform_rows, key=lambda row: row["platform"])
        remainder = total - minimum * len(rows)
        score_sum = sum(row["score"] for row in rows) or float(len(rows))
        allocations = {row["platform"]: minimum + remainder * row["score"] / score_sum for row in rows}
        if maximum is not None:
            allocations = {platform: min(value, maximum) for platform, value in allocations.items()}
            capped_total = sum(allocations.values())
            # Do not silently manufacture spend after capping.  Surface the
            # unallocated remainder for an operator to decide.
            unallocated = max(total - capped_total, 0.0)
        else:
            unallocated = 0.0

        recommendations = []
        for row in rows:
            recommendation = dict(row)
            recommendation["recommended_budget"] = round(allocations[row["platform"]], 2)
            recommendations.append(recommendation)
        return {
            "schema_version": "1.0",
            "status": "partial" if aggregate.get("comparability", {}).get("status") == "partial" else "available",
            "total_budget": round(total, 2),
            "unallocated_budget": round(unallocated, 2),
            "recommendations": recommendations,
            "comparability": aggregate.get("comparability", {}),
            "disclaimer": "这是只读预算建议；不会自动修改任何平台 Campaign。",
        }

    @staticmethod
    def export_csv(aggregate: dict[str, Any]) -> str:
        """Serialize the normalized aggregate as deterministic CSV text."""
        output = io.StringIO(newline="")
        columns = [
            "platform", "account_id", "campaign_id", "name", "status",
            "objective", "budget", "currency", "impressions", "clicks",
            "spend", "conversions", "revenue", "data_status",
        ]
        writer = csv.DictWriter(output, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for platform, bucket in sorted((aggregate.get("platforms") or {}).items()):
            for record in bucket.get("records", []) if isinstance(bucket, dict) else []:
                metrics = record.get("metrics") if isinstance(record, dict) else {}
                metrics = metrics if isinstance(metrics, dict) else {}
                row = {
                    "platform": platform,
                    "account_id": record.get("account_id"),
                    "campaign_id": record.get("campaign_id"),
                    "name": record.get("name"),
                    "status": record.get("status"),
                    "objective": record.get("objective"),
                    "budget": record.get("budget"),
                    "currency": record.get("currency") or metrics.get("currency"),
                    "impressions": metrics.get("impressions"),
                    "clicks": metrics.get("clicks"),
                    "spend": metrics.get("spend"),
                    "conversions": metrics.get("conversions"),
                    "revenue": metrics.get("revenue"),
                    "data_status": record.get("data_status") or bucket.get("data_status", "unknown"),
                }
                writer.writerow(row)
        return output.getvalue()
