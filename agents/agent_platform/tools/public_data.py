"""Fixed-endpoint, read-only public data Tools."""

from __future__ import annotations

import json
import math
import re
import threading
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable, Mapping
from urllib.parse import urlencode, urlsplit

import requests

from agents.agent_harness import StaticToolSource, ToolBinding
from agents.agent_harness.core.interfaces import (
    ReplayPolicy,
    RiskLevel,
    ToolDefinition,
    ToolEffect,
    ToolResult,
    ToolSchema,
)


MAX_RESPONSE_BYTES = 256_000
MAX_OUTPUT_BYTES = 32_000
MAX_EXCHANGE_RANGE_DAYS = 92
MAX_EXCHANGE_OBSERVATIONS = 100
REQUEST_TIMEOUT = (3, 8)
_ALLOWED_HOSTS = frozenset({
    "api.frankfurter.dev",
    "api.worldbank.org",
    "api.crossref.org",
    "earthquake.usgs.gov",
    "de.wikipedia.org",
    "en.wikipedia.org",
    "es.wikipedia.org",
    "export.arxiv.org",
    "fr.wikipedia.org",
    "hn.algolia.com",
    "ja.wikipedia.org",
    "itunes.apple.com",
    "openlibrary.org",
    "wttr.in",
    "www.gov.uk",
    "www.7timer.info",
    "www.googleapis.com",
    "zh.wikipedia.org",
})
_HOST_MIN_INTERVAL_SECONDS = {
    "api.crossref.org": 1.0,
    "export.arxiv.org": 3.1,
    "openlibrary.org": 1.0,
    "itunes.apple.com": 3.1,
    "www.googleapis.com": 1.0,
}
_CURRENCIES = re.compile(r"^[A-Z]{3}$")
_COUNTRY_CODES = re.compile(r"^[A-Z]{3}$")
_INDICATOR_CODES = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{1,31}$")
_UK_DIVISIONS = frozenset({
    "england-and-wales",
    "scotland",
    "northern-ireland",
})


class _PublicDataError(ValueError):
    pass


class _PublicDataHttpClient:
    """HTTP client constrained to reviewed hosts and bounded JSON responses."""

    def __init__(
        self,
        request_get: Callable[..., Any] | None = None,
        *,
        contact_email: str | None = None,
    ) -> None:
        self._request_get = request_get or requests.get
        email = str(contact_email or "").strip()
        if len(email) > 254 or any(char in email for char in "\r\n"):
            raise ValueError("contact_email is invalid")
        user_agent = "AdsAgentPublicData/1.0"
        if email:
            user_agent += f" (contact: {email})"
        self._user_agent = user_agent
        self._rate_lock = threading.Lock()
        self._host_locks: dict[str, threading.Lock] = {}
        self._last_request_started: dict[str, float] = {}

    def get_json(
        self,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        timeout: tuple[float, float] = REQUEST_TIMEOUT,
    ) -> Any:
        body = self._get_body(
            url,
            params=params,
            accept="application/json",
            timeout=timeout,
        )
        try:
            return json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise _PublicDataError("公共数据服务返回了无效 JSON") from error

    def get_xml(
        self,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
    ) -> ET.Element:
        body = self._get_body(
            url,
            params=params,
            accept="application/atom+xml, application/xml;q=0.9",
        )
        try:
            return ET.fromstring(body)
        except ET.ParseError as error:
            raise _PublicDataError("公共数据服务返回了无效 XML") from error

    def _get_body(
        self,
        url: str,
        *,
        params: Mapping[str, Any] | None,
        accept: str,
        timeout: tuple[float, float] = REQUEST_TIMEOUT,
    ) -> bytes:
        parsed = urlsplit(url)
        if (
            parsed.scheme != "https"
            or parsed.hostname not in _ALLOWED_HOSTS
            or parsed.username
            or parsed.password
            or parsed.port not in (None, 443)
        ):
            raise _PublicDataError("公共数据请求目标不在允许范围内")

        host = parsed.hostname
        lock = self._host_lock(host)
        with lock:
            self._wait_for_host_interval(host)
            response = None
            try:
                response = self._request_get(
                    url,
                    params=dict(params) if params else None,
                    headers={
                        "Accept": accept,
                        "User-Agent": self._user_agent,
                    },
                    timeout=timeout,
                    allow_redirects=False,
                    stream=True,
                )
                return self._read_response_body(response)
            except requests.RequestException as error:
                raise _PublicDataError("公共数据服务请求失败或超时") from error
            finally:
                close = getattr(response, "close", None)
                if callable(close):
                    close()

    def _host_lock(self, host: str) -> threading.Lock:
        with self._rate_lock:
            if host not in self._host_locks:
                self._host_locks[host] = threading.Lock()
            return self._host_locks[host]

    def _wait_for_host_interval(self, host: str) -> None:
        interval = _HOST_MIN_INTERVAL_SECONDS.get(host, 0.0)
        now = time.monotonic()
        previous = self._last_request_started.get(host)
        delay = interval - (now - previous) if previous is not None else 0.0
        if delay > 0:
            time.sleep(delay)
        self._last_request_started[host] = time.monotonic()

    @staticmethod
    def _read_response_body(response: Any) -> bytes:
        status = int(getattr(response, "status_code", 0))
        if status != 200:
            raise _PublicDataError(f"公共数据服务返回 HTTP {status}")
        return _read_limited_body(response)


def _read_limited_body(response: Any) -> bytes:
    headers = getattr(response, "headers", {}) or {}
    get_header = getattr(headers, "get", None)
    content_length = get_header("Content-Length") if callable(get_header) else None
    try:
        declared_size = int(content_length) if content_length else None
    except (TypeError, ValueError):
        declared_size = None
    if declared_size is not None and declared_size > MAX_RESPONSE_BYTES:
        raise _PublicDataError("公共数据响应超过 256 KB 限制")

    body = bytearray()
    for chunk in response.iter_content(chunk_size=16_384):
        if not chunk:
            continue
        if not isinstance(chunk, bytes):
            raise _PublicDataError("公共数据响应格式无效")
        body.extend(chunk)
        if len(body) > MAX_RESPONSE_BYTES:
            raise _PublicDataError("公共数据响应超过 256 KB 限制")
    return bytes(body)


class _PublicDataExecutor:
    def __init__(
        self,
        client: _PublicDataHttpClient,
        *,
        api_name: str,
        endpoint: str,
    ) -> None:
        self._client = client
        self._api_name = api_name
        self._endpoint = endpoint

    def _fetch(
        self,
        params: Mapping[str, Any] | None = None,
        *,
        endpoint: str | None = None,
    ) -> Any:
        return self._client.get_json(endpoint or self._endpoint, params=params)

    def _error(self, error: Exception) -> ToolResult:
        if isinstance(error, _PublicDataError):
            message = str(error)
        else:
            message = "公共数据查询失败，请稍后重试"
        return ToolResult.error(f"{self._api_name}：{message}")


class _ExchangeRateExecutor(_PublicDataExecutor):
    def execute(self, _context: Any, arguments: dict[str, Any]) -> ToolResult:
        try:
            base, quote = _exchange_currencies(arguments)
            query = _exchange_rate_query(arguments)
            if query["kind"] == "range":
                endpoint = f"{self._endpoint.rsplit('/rate', 1)[0]}/rates"
                params = {
                    "base": base,
                    "quotes": quote,
                    "from": query["start_date"],
                    "to": query["end_date"],
                }
                payload = self._fetch(params, endpoint=endpoint)
                records = _project_exchange_rate_series(
                    payload,
                    base,
                    quote,
                    date.fromisoformat(query["start_date"]),
                    date.fromisoformat(query["end_date"]),
                )
                return ToolResult.ok({
                    "source": "Frankfurter",
                    "source_url": f"{endpoint}?{urlencode(params)}",
                    "data_status": "live_external",
                    "base": base,
                    "quote": quote,
                    "start_date": query["start_date"],
                    "end_date": query["end_date"],
                    "count": len(records),
                    "records": records,
                    "retrieved_at": _now(),
                })

            params = {"date": query["date"]} if query["date"] else {}
            endpoint = f"{self._endpoint}/{base}/{quote}"
            payload = self._fetch(params, endpoint=endpoint)
            rate, observed_date = _project_exchange_rate(payload, base, quote)
            source_url = endpoint
            if params:
                source_url = f"{endpoint}?{urlencode(params)}"
            return ToolResult.ok({
                "source": "Frankfurter",
                "source_url": source_url,
                "data_status": "live_external",
                "date": observed_date,
                "base": base,
                "quote": quote,
                "rate": rate,
                "retrieved_at": _now(),
            })
        except (TypeError, ValueError, OverflowError) as error:
            return self._error(error)


def _exchange_currencies(arguments: Mapping[str, Any]) -> tuple[str, str]:
    base = str(arguments.get("base_currency") or "").strip().upper()
    quote = str(arguments.get("quote_currency") or "").strip().upper()
    if not _CURRENCIES.fullmatch(base) or not _CURRENCIES.fullmatch(quote):
        raise _PublicDataError("货币代码必须是 3 位 ISO 字母代码")
    return base, quote


def _exchange_rate_query(arguments: Mapping[str, Any]) -> dict[str, str]:
    requested_date = arguments.get("date")
    start_date = arguments.get("start_date")
    end_date = arguments.get("end_date")
    lookback_days = arguments.get("lookback_days")
    has_date = requested_date not in (None, "")
    has_start = start_date not in (None, "")
    has_end = end_date not in (None, "")
    has_lookback = lookback_days not in (None, "")
    if has_date and (has_start or has_end or has_lookback):
        raise _PublicDataError("单日日期和日期范围参数不能同时使用")
    if has_lookback and (has_start or has_end):
        raise _PublicDataError("最近 N 天与起止日期参数不能同时使用")
    if has_start != has_end:
        raise _PublicDataError("日期范围必须同时提供开始日期和结束日期")
    if has_date:
        return {
            "kind": "single",
            "date": _parse_exchange_date(requested_date).isoformat(),
        }

    today = datetime.now(timezone.utc).date()
    if has_lookback:
        if isinstance(lookback_days, bool) or not isinstance(lookback_days, int):
            raise _PublicDataError("最近天数必须是整数")
        if not 1 <= lookback_days <= MAX_EXCHANGE_RANGE_DAYS:
            raise _PublicDataError(
                f"日期范围必须在 1 到 {MAX_EXCHANGE_RANGE_DAYS} 天内"
            )
        start = today - timedelta(days=lookback_days - 1)
        return {
            "kind": "range",
            "start_date": start.isoformat(),
            "end_date": today.isoformat(),
        }
    if has_start:
        start = _parse_exchange_date(start_date)
        end = _parse_exchange_date(end_date)
        if start > end:
            raise _PublicDataError("开始日期不能晚于结束日期")
        if (end - start).days + 1 > MAX_EXCHANGE_RANGE_DAYS:
            raise _PublicDataError(
                f"日期范围不能超过 {MAX_EXCHANGE_RANGE_DAYS} 天"
            )
        return {
            "kind": "range",
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
        }
    return {"kind": "single", "date": ""}


def _parse_exchange_date(value: Any) -> date:
    if not isinstance(value, str):
        raise _PublicDataError("日期必须使用 YYYY-MM-DD 格式")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as error:
        raise _PublicDataError("日期必须使用 YYYY-MM-DD 格式") from error
    if parsed.isoformat() != value:
        raise _PublicDataError("日期必须使用 YYYY-MM-DD 格式")
    if parsed > datetime.now(timezone.utc).date():
        raise _PublicDataError("日期不能晚于今天")
    return parsed


def _project_exchange_rate(
    payload: Any,
    base: str,
    quote: str,
) -> tuple[float, str]:
    if not isinstance(payload, Mapping):
        raise _PublicDataError("公共数据服务返回了不支持的数据结构")
    rate = payload.get("rate")
    if (
        isinstance(rate, bool)
        or not isinstance(rate, (int, float))
        or not math.isfinite(float(rate))
        or float(rate) <= 0
    ):
        raise _PublicDataError("该日期没有可用的汇率数据")
    if (
        str(payload.get("base") or "").upper() != base
        or str(payload.get("quote") or "").upper() != quote
    ):
        raise _PublicDataError("公共数据服务返回的货币代码不匹配")
    return float(rate), _bounded_text(payload.get("date"), 10)


def _project_exchange_rate_series(
    payload: Any,
    base: str,
    quote: str,
    start: date,
    end: date,
) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        raise _PublicDataError("公共数据服务返回了不支持的时间序列结构")
    if len(payload) > MAX_EXCHANGE_OBSERVATIONS:
        raise _PublicDataError("汇率观测数量超过安全上限")
    records = []
    seen_dates: set[str] = set()
    for item in payload:
        if not isinstance(item, Mapping):
            raise _PublicDataError("公共数据服务返回了无效的汇率观测")
        if (
            str(item.get("base") or "").upper() != base
            or str(item.get("quote") or "").upper() != quote
        ):
            raise _PublicDataError("公共数据服务返回的货币代码不匹配")
        observed = _bounded_text(item.get("date"), 10)
        try:
            observed_date = date.fromisoformat(observed)
        except ValueError as error:
            raise _PublicDataError("公共数据服务返回了无效的观测日期") from error
        if observed_date.isoformat() != observed:
            raise _PublicDataError("公共数据服务返回了无效的观测日期")
        if observed_date < start or observed_date > end:
            raise _PublicDataError("公共数据服务返回了范围外的观测")
        rate = item.get("rate")
        if (
            isinstance(rate, bool)
            or not isinstance(rate, (int, float))
            or not math.isfinite(float(rate))
            or float(rate) <= 0
        ):
            raise _PublicDataError("公共数据服务返回了无效汇率")
        if observed in seen_dates:
            raise _PublicDataError("公共数据服务返回了重复日期观测")
        seen_dates.add(observed)
        records.append({"date": observed, "rate": float(rate)})
    if not records:
        raise _PublicDataError("该日期范围没有可用的汇率数据")
    records.sort(key=lambda item: item["date"])
    return records


class _WorldBankIndicatorExecutor(_PublicDataExecutor):
    def execute(self, _context: Any, arguments: dict[str, Any]) -> ToolResult:
        try:
            country, indicator, year_from, year_to = _world_bank_query(arguments)
            endpoint = f"{self._endpoint}/{country}/indicator/{indicator}"
            params = _world_bank_params(year_from, year_to)
            payload = self._fetch(params, endpoint=endpoint)
            meta, records = _project_world_bank_rows(payload)
            source_url = f"{endpoint}?{urlencode(params)}"
            return ToolResult.ok({
                "source": "World Bank Indicators API",
                "source_url": source_url,
                "data_status": "live_external",
                "country_code": country,
                "indicator_code": indicator,
                "year_from": year_from,
                "year_to": year_to,
                "last_updated": _bounded_text(meta.get("lastupdated"), 32),
                "count": len(records),
                "records": records,
                "retrieved_at": _now(),
            })
        except (TypeError, ValueError, OverflowError) as error:
            return self._error(error)


def _world_bank_query(
    arguments: Mapping[str, Any],
) -> tuple[str, str, int, int]:
    country = str(arguments.get("country_code") or "").strip().upper()
    indicator = str(arguments.get("indicator_code") or "").strip()
    if not _COUNTRY_CODES.fullmatch(country):
        raise _PublicDataError("国家代码必须是 3 位 ISO 3166-1 alpha-3 代码")
    if not _INDICATOR_CODES.fullmatch(indicator):
        raise _PublicDataError("World Bank 指标代码格式无效")

    current_year = datetime.now(timezone.utc).year
    year_to = _year(arguments.get("year_to"), current_year - 1)
    year_from = _year(arguments.get("year_from"), year_to - 4)
    if (
        year_from < 1960
        or year_to > current_year
        or year_from > year_to
        or year_to - year_from > 19
    ):
        raise _PublicDataError("年份范围需在 1960 年至今，且最多覆盖 20 年")
    return country, indicator, year_from, year_to


def _world_bank_params(year_from: int, year_to: int) -> dict[str, Any]:
    return {
        "format": "json",
        "per_page": 20,
        "date": f"{year_from}:{year_to}",
    }


def _project_world_bank_rows(
    payload: Any,
) -> tuple[Mapping[str, Any], list[dict[str, Any]]]:
    if (
        not isinstance(payload, list)
        or len(payload) < 2
        or not isinstance(payload[1], list)
    ):
        raise _PublicDataError("World Bank 返回了不支持的数据结构")
    meta = payload[0] if isinstance(payload[0], Mapping) else {}
    records = [
        record
        for item in payload[1][:20]
        if isinstance(item, Mapping)
        if (record := _world_bank_record(item)) is not None
    ]
    return meta, records


class _UKBankHolidayExecutor(_PublicDataExecutor):
    def execute(self, _context: Any, arguments: dict[str, Any]) -> ToolResult:
        try:
            division = str(arguments.get("division") or "").strip().lower()
            if division not in _UK_DIVISIONS:
                raise _PublicDataError(
                    "division 必须是 england-and-wales、scotland 或 northern-ireland"
                )
            year = _year(
                arguments.get("year"),
                datetime.now(timezone.utc).year,
            )
            if year < 2000 or year > datetime.now(timezone.utc).year + 1:
                raise _PublicDataError("年份需在 2000 年至明年之间")

            payload = self._fetch()
            if not isinstance(payload, Mapping):
                raise _PublicDataError("GOV.UK 返回了不支持的数据结构")
            division_data = payload.get(division)
            if not isinstance(division_data, Mapping):
                raise _PublicDataError("GOV.UK 没有返回所选地区的数据")
            raw_events = division_data.get("events")
            if not isinstance(raw_events, list):
                raise _PublicDataError("GOV.UK 假日数据格式无效")
            events = [
                event
                for item in raw_events
                if isinstance(item, Mapping)
                if (event := _uk_holiday_event(item, year)) is not None
            ]
            events.sort(key=lambda item: item["date"])
            return ToolResult.ok({
                "source": "GOV.UK bank holidays API",
                "source_url": self._endpoint,
                "data_status": "live_external",
                "division": division,
                "year": year,
                "count": len(events),
                "events": events[:50],
                "retrieved_at": _now(),
            })
        except (TypeError, ValueError, OverflowError) as error:
            return self._error(error)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _year(value: Any, default: int) -> int:
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, int):
        raise _PublicDataError("年份必须是整数")
    return value


def _bounded_text(value: Any, limit: int) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()[:limit]


def _world_bank_record(item: Mapping[str, Any]) -> dict[str, Any] | None:
    indicator = item.get("indicator")
    country = item.get("country")
    if not isinstance(indicator, Mapping) or not isinstance(country, Mapping):
        return None
    year = _bounded_text(item.get("date"), 4)
    if not year.isdigit():
        return None
    value = item.get("value")
    if isinstance(value, bool) or not (value is None or isinstance(value, (int, float))):
        value = None
    elif isinstance(value, float) and not math.isfinite(value):
        value = None
    return {
        "year": year,
        "value": value,
        "country": _bounded_text(country.get("value"), 100),
        "indicator": _bounded_text(indicator.get("value"), 160),
        "unit": _bounded_text(item.get("unit"), 80),
    }


def _uk_holiday_event(
    item: Mapping[str, Any],
    requested_year: int,
) -> dict[str, Any] | None:
    event_date = _bounded_text(item.get("date"), 10)
    try:
        parsed_date = date.fromisoformat(event_date)
    except ValueError:
        return None
    if parsed_date.year != requested_year:
        return None
    return {
        "title": _bounded_text(item.get("title"), 120),
        "date": parsed_date.isoformat(),
        "notes": _bounded_text(item.get("notes"), 240),
        "bunting": item.get("bunting") if isinstance(item.get("bunting"), bool) else None,
    }


def _schema(properties: dict[str, Any], required: list[str]) -> ToolSchema:
    return ToolSchema(
        properties=properties,
        required=required,
        additional_properties=False,
    )


@dataclass(frozen=True)
class _PublicDataToolSpec:
    name: str
    skill: str
    namespace: str
    description: str
    action: str
    resource_type: str
    intent_type: str
    intent_aliases: tuple[str, ...]
    schema: ToolSchema
    result_items_key: str
    timeout_seconds: float = 12
    contract_version: str = "1.0.0"


def _definition(spec: _PublicDataToolSpec, permission: str) -> ToolDefinition:
    return ToolDefinition(
        name=spec.name,
        skill=spec.skill,
        namespace=spec.namespace,
        description=spec.description,
        input_schema=spec.schema,
        action=spec.action,
        resource_type=spec.resource_type,
        intent_types=[spec.intent_type],
        intent_aliases=list(spec.intent_aliases),
        skill_refs=["web-research"],
        risk_level=RiskLevel.LOW,
        effect_class=ToolEffect.READ,
        replay_policy=ReplayPolicy.SAFE,
        traits=["public_data", "external_public_data", "read_only", "bounded_output"],
        timeout_seconds=spec.timeout_seconds,
        max_output_bytes=MAX_OUTPUT_BYTES,
        required_permissions=[permission],
        scope_required=False,
        result_items_key=spec.result_items_key,
        contract_version=spec.contract_version,
    )


def _exchange_rate_spec() -> _PublicDataToolSpec:
    return _PublicDataToolSpec(
        name="public_finance_exchange_rate",
        skill="public-finance",
        namespace="public_finance",
        description=(
            "Look up a current or historical daily currency exchange rate from "
            "the no-key Frankfurter API. Use for currency conversion or comparing "
            "advertising budgets across currencies, or a historical time series "
            "for a date-based trend. Input uses three-letter currency codes; "
            "choose one of a single date or a range up to 92 calendar days, "
            "using a complete start/end date pair or lookback_days from 1 to 92. "
            "Date ranges return actual published "
            "observations only; weekends and holidays are not interpolated. "
            "This is an external reference rate, not a trading quote."
        ),
        action="lookup",
        resource_type="exchange_rate",
        intent_type="exchange_rate_lookup",
        intent_aliases=(
            "查汇率",
            "查询汇率",
            "货币汇率",
            "美元兑人民币",
            "exchange rate",
            "currency conversion",
            "历史汇率时间序列",
            "汇率趋势图",
            "date-based exchange rate trend",
        ),
        schema=_exchange_rate_schema(),
        result_items_key="records",
        contract_version="1.1.0",
    )


def _exchange_rate_schema() -> ToolSchema:
    return _schema(
        {
            "base_currency": {
                "type": "string",
                "minLength": 3,
                "maxLength": 3,
                "description": "Base currency ISO 4217 code, e.g. USD",
            },
            "quote_currency": {
                "type": "string",
                "minLength": 3,
                "maxLength": 3,
                "description": "Quote currency ISO 4217 code, e.g. CNY",
            },
            "date": {
                "type": "string",
                "format": "date",
                "description": "Optional historical date in YYYY-MM-DD",
            },
            "start_date": {
                "type": "string",
                "format": "date",
                "description": "Inclusive start date for a historical time series",
            },
            "end_date": {
                "type": "string",
                "format": "date",
                "description": "Inclusive end date for a historical time series",
            },
            "lookback_days": {
                "type": "integer",
                "minimum": 1,
                "maximum": MAX_EXCHANGE_RANGE_DAYS,
                "description": (
                    "Inclusive number of calendar days ending today, for example 30"
                ),
            },
        },
        ["base_currency", "quote_currency"],
    )


def _world_bank_spec() -> _PublicDataToolSpec:
    return _PublicDataToolSpec(
        name="public_economics_country_indicator",
        skill="public-economics",
        namespace="public_economics",
        description=(
            "Retrieve bounded annual country data from the no-key World Bank "
            "Indicators API. Useful for market context such as population "
            "(SP.POP.TOTL), GDP (NY.GDP.MKTP.CD), GDP per capita "
            "(NY.GDP.PCAP.CD), internet use (IT.NET.USER.ZS), or urban "
            "population (SP.URB.TOTL.IN.ZS). Requires an ISO alpha-3 country code "
            "and World Bank indicator code; defaults to the last five completed "
            "years and allows at most 20 years. Data may be delayed and should "
            "support, not replace, current market research."
        ),
        action="lookup",
        resource_type="country_indicator",
        intent_type="country_economic_indicator_lookup",
        intent_aliases=(
            "查询国家经济指标",
            "查询某国GDP",
            "查询国家人口数据",
            "查询市场宏观数据",
            "World Bank country indicator",
            "country economic statistics",
        ),
        schema=_world_bank_schema(),
        result_items_key="records",
    )


def _world_bank_schema() -> ToolSchema:
    return _schema(
        {
            "country_code": {
                "type": "string",
                "minLength": 3,
                "maxLength": 3,
                "description": "ISO 3166-1 alpha-3 country code, e.g. USA",
            },
            "indicator_code": {
                "type": "string",
                "minLength": 2,
                "maxLength": 32,
                "description": (
                    "World Bank indicator code, e.g. SP.POP.TOTL "
                    "or NY.GDP.MKTP.CD"
                ),
            },
            "year_from": {
                "type": "integer",
                "minimum": 1960,
                "description": "Optional first year, inclusive",
            },
            "year_to": {
                "type": "integer",
                "description": "Optional last year, inclusive",
            },
        },
        ["country_code", "indicator_code"],
    )


def _bank_holiday_spec() -> _PublicDataToolSpec:
    return _PublicDataToolSpec(
        name="public_calendar_bank_holidays",
        skill="public-calendar",
        namespace="public_calendar",
        description=(
            "List official UK bank holidays from GOV.UK by region and year. "
            "This endpoint only covers England and Wales, Scotland, and Northern "
            "Ireland; it does not provide worldwide public holidays. Useful for "
            "UK campaign calendar planning."
        ),
        action="list",
        resource_type="bank_holiday",
        intent_type="public_holiday_lookup",
        intent_aliases=(
            "查询英国公共假期",
            "英国银行假日",
            "英国节假日",
            "UK bank holidays",
            "UK public holidays",
        ),
        schema=_bank_holiday_schema(),
        result_items_key="events",
    )


def _bank_holiday_schema() -> ToolSchema:
    return _schema(
        {
            "division": {
                "type": "string",
                "enum": sorted(_UK_DIVISIONS),
                "description": "One of the three GOV.UK bank holiday regions",
            },
            "year": {
                "type": "integer",
                "minimum": 2000,
                "description": "Optional calendar year; defaults to current year",
            },
        },
        ["division"],
    )


def public_data_tool_source(
    *,
    required_permission: str,
    request_get: Callable[..., Any] | None = None,
) -> StaticToolSource:
    """Publish reviewed public data endpoints as ordinary Runtime Tools."""
    permission = str(required_permission or "").strip()
    if not permission:
        raise ValueError("required_permission is required")
    client = _PublicDataHttpClient(request_get)
    bindings = [
        ToolBinding(
            _definition(_exchange_rate_spec(), permission),
            _ExchangeRateExecutor(
                client,
                api_name="Frankfurter",
                endpoint="https://api.frankfurter.dev/v2/rate",
            ),
        ),
        ToolBinding(
            _definition(_world_bank_spec(), permission),
            _WorldBankIndicatorExecutor(
                client,
                api_name="World Bank",
                endpoint="https://api.worldbank.org/v2/country",
            ),
        ),
        ToolBinding(
            _definition(_bank_holiday_spec(), permission),
            _UKBankHolidayExecutor(
                client,
                api_name="GOV.UK",
                endpoint="https://www.gov.uk/bank-holidays.json",
            ),
        ),
    ]
    return StaticToolSource("agent-platform:public-data", bindings)


__all__ = [
    "MAX_RESPONSE_BYTES",
    "public_data_tool_source",
]
