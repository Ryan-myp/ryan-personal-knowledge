"""Weather and earthquake Tools backed by reviewed public APIs."""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable, Mapping
from urllib.parse import quote, urlencode

from agents.agent_harness import StaticToolSource, ToolBinding
from agents.agent_harness.core.interfaces import (
    ToolDefinition,
    ToolResult,
    ToolSchema,
)
from agents.agent_platform.tools.public_data import (
    _PublicDataError,
    _PublicDataExecutor,
    _PublicDataHttpClient,
    _PublicDataToolSpec,
    _schema,
)
from agents.agent_platform.tools.public_reference_common import (
    MAX_RESULTS,
    clean_text,
    first_text,
    number,
    require_list,
    result_metadata,
    safe_https_url,
    string_schema,
    tool_definition,
    validate_limit,
    validate_query,
)


MAX_LOCATION_CHARS = 100
_SEVEN_TIMER_MAX_HOURS = 192


class _WeatherExecutor(_PublicDataExecutor):
    def execute(self, _context: Any, arguments: dict[str, Any]) -> ToolResult:
        try:
            location = validate_query(arguments.get("location"), "location")
            if len(location) > MAX_LOCATION_CHARS:
                raise _PublicDataError("地点名称过长")
            endpoint = f"{self._endpoint}/{quote(location, safe='')}"
            payload = self._fetch({"format": "j1"}, endpoint=endpoint)
            current_items = require_list(payload, "current_condition", "wttr.in")
            if not current_items or not isinstance(current_items[0], Mapping):
                raise _PublicDataError("wttr.in 没有返回当前天气")
            current = current_items[0]
            area_items = payload.get("nearest_area")
            area = area_items[0] if isinstance(area_items, list) and area_items else {}
            if not isinstance(area, Mapping):
                area = {}
            weather_items = payload.get("weather")
            forecast = []
            if isinstance(weather_items, list):
                for item in weather_items[:3]:
                    if not isinstance(item, Mapping):
                        continue
                    forecast.append({
                        "date": clean_text(item.get("date"), 10),
                        "high_c": number(item.get("maxtempC")),
                        "low_c": number(item.get("mintempC")),
                        "summary": self._forecast_summary(item),
                    })
            return ToolResult.ok(result_metadata(
                source="wttr.in",
                source_url=f"{endpoint}?format=j1",
                data={
                    "location": location,
                    "resolved_area": first_text(area.get("areaName")),
                    "country": first_text(area.get("country")),
                    "current": {
                        "temperature_c": number(current.get("temp_C")),
                        "feels_like_c": number(current.get("FeelsLikeC")),
                        "humidity_percent": number(
                            current.get("humidity"), integer=True
                        ),
                        "wind_kph": number(current.get("windspeedKmph")),
                        "summary": first_text(current.get("weatherDesc")),
                    },
                    "forecast": forecast,
                },
            ))
        except (TypeError, ValueError, OverflowError) as error:
            return self._error(error)

    @staticmethod
    def _forecast_summary(item: Mapping[str, Any]) -> str:
        hourly = item.get("hourly")
        if not isinstance(hourly, list) or not hourly:
            return ""
        first_hour = hourly[0]
        if not isinstance(first_hour, Mapping):
            return ""
        return first_text(first_hour.get("weatherDesc"))


def _weather_definition(permission: str) -> ToolDefinition:
    spec = _PublicDataToolSpec(
        name="public_weather_lookup",
        skill="web-research",
        namespace="public_weather",
        description=(
            "Look up current weather and a short forecast for a named location "
            "using the no-key wttr.in JSON endpoint. Useful for campaign timing "
            "and local context. Weather is approximate, may be unavailable for "
            "some places, and is not a substitute for an official warning."
        ),
        action="lookup",
        resource_type="weather",
        intent_type="weather_lookup",
        intent_aliases=(
            "查天气",
            "查询天气",
            "天气预报",
            "当地天气",
            "weather forecast",
            "current weather",
        ),
        schema=_schema({
            "location": string_schema(
                "City, region, or place name; e.g. Shenzhen or New York",
                maximum=MAX_LOCATION_CHARS,
            ),
        }, ["location"]),
        result_items_key="forecast",
    )
    return tool_definition(spec, permission)


def _date_input(value: Any, field: str, default: date) -> date:
    if value is None or value == "":
        return default
    if not isinstance(value, str):
        raise _PublicDataError(f"{field} 必须使用 YYYY-MM-DD 格式")
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise _PublicDataError(f"{field} 必须使用 YYYY-MM-DD 格式") from error


def _earthquake_params(
    arguments: Mapping[str, Any],
) -> tuple[dict[str, Any], date, date, int]:
    today = datetime.now(timezone.utc).date()
    start = _date_input(
        arguments.get("start_date"),
        "start_date",
        today - timedelta(days=7),
    )
    end = _date_input(arguments.get("end_date"), "end_date", today)
    if start > end or end > today or (end - start).days > 30:
        raise _PublicDataError(
            "日期范围必须在过去 30 天内，且开始日期不能晚于结束日期"
        )
    limit = validate_limit(arguments.get("limit"), default=10)
    orderby = str(arguments.get("orderby") or "time").strip().lower()
    if orderby not in {"time", "magnitude", "significance"}:
        raise _PublicDataError("orderby 仅支持 time、magnitude 或 significance")
    params: dict[str, Any] = {
        "format": "geojson",
        "starttime": f"{start.isoformat()}T00:00:00",
        "endtime": (
            f"{end.isoformat()}T23:59:59"
            if end < today else datetime.now(timezone.utc).isoformat()
        ),
        "limit": limit,
        "orderby": orderby,
    }
    min_magnitude = arguments.get("min_magnitude")
    if min_magnitude is not None:
        if (
            isinstance(min_magnitude, bool)
            or not isinstance(min_magnitude, (int, float))
            or not math.isfinite(float(min_magnitude))
            or not -1 <= float(min_magnitude) <= 10
        ):
            raise _PublicDataError("min_magnitude 必须在 -1 至 10 之间")
        params["minmagnitude"] = float(min_magnitude)
    return params, start, end, limit


class _EarthquakeExecutor(_PublicDataExecutor):
    def execute(self, _context: Any, arguments: dict[str, Any]) -> ToolResult:
        try:
            params, start, end, limit = _earthquake_params(arguments)
            payload = self._fetch(params)
            features = require_list(payload, "features", "USGS")
            events = [
                event
                for feature in features[:limit]
                if isinstance(feature, Mapping)
                if (event := self._project_feature(feature)) is not None
            ]
            return ToolResult.ok(result_metadata(
                source="USGS Earthquake Hazards Program",
                source_url=f"{self._endpoint}?{urlencode(params)}",
                data={
                    "start_date": start.isoformat(),
                    "end_date": end.isoformat(),
                    "count": len(events),
                    "events": events,
                },
            ))
        except (TypeError, ValueError, OverflowError) as error:
            return self._error(error)

    @staticmethod
    def _project_feature(feature: Mapping[str, Any]) -> dict[str, Any] | None:
        properties = feature.get("properties")
        geometry = feature.get("geometry")
        if not isinstance(properties, Mapping):
            return None
        if not isinstance(geometry, Mapping):
            geometry = {}
        coordinates = geometry.get("coordinates")
        normalized_coordinates = None
        if (
            isinstance(coordinates, list)
            and 2 <= len(coordinates) <= 3
            and all(number(value) is not None for value in coordinates)
        ):
            normalized_coordinates = [number(value) for value in coordinates]
        timestamp = number(properties.get("time"), integer=True)
        occurred_at = ""
        if timestamp is not None:
            try:
                occurred_at = datetime.fromtimestamp(
                    timestamp / 1000,
                    tz=timezone.utc,
                ).isoformat()
            except (OverflowError, OSError, ValueError):
                occurred_at = ""
        tsunami = properties.get("tsunami")
        return {
            "id": clean_text(feature.get("id"), 64),
            "magnitude": number(properties.get("mag")),
            "place": clean_text(properties.get("place"), 200),
            "occurred_at": occurred_at,
            "depth_km": (
                normalized_coordinates[2]
                if normalized_coordinates and len(normalized_coordinates) == 3
                else None
            ),
            "coordinates": normalized_coordinates,
            "url": safe_https_url(properties.get("url")),
            "type": clean_text(properties.get("type"), 60),
            "tsunami": bool(tsunami) if isinstance(tsunami, (bool, int)) else None,
        }

def _earthquake_schema() -> ToolSchema:
    properties = {
        "start_date": {
            "type": "string",
            "format": "date",
            "description": "Optional first UTC date, inclusive",
        },
        "end_date": {
            "type": "string",
            "format": "date",
            "description": "Optional last UTC date, inclusive",
        },
        "min_magnitude": {
            "type": "number",
            "minimum": -1,
            "maximum": 10,
            "description": "Optional minimum magnitude",
        },
        "limit": {
            "type": "integer",
            "minimum": 1,
            "maximum": MAX_RESULTS,
            "default": 10,
        },
        "orderby": {
            "type": "string",
            "enum": ["time", "magnitude", "significance"],
            "default": "time",
        },
    }
    return _schema(properties, [])


def _earthquake_definition(permission: str) -> ToolDefinition:
    spec = _PublicDataToolSpec(
        name="public_environment_earthquakes",
        skill="web-research",
        namespace="public_environment",
        description=(
            "Search recent earthquakes from the official USGS GeoJSON API. "
            "This provides earthquake observations, not a general climate or "
            "environment feed. Defaults to the last seven days; date windows "
            "are limited to 30 days and at most ten results."
        ),
        action="search",
        resource_type="earthquake",
        intent_type="earthquake_search",
        intent_aliases=(
            "查询地震",
            "最近地震",
            "地震活动",
            "USGS earthquakes",
            "recent earthquakes",
        ),
        schema=_earthquake_schema(),
        result_items_key="events",
    )
    return tool_definition(spec, permission)


def _coordinate(arguments: Mapping[str, Any], field: str) -> float:
    value = number(arguments.get(field))
    lower, upper = (-90, 90) if field == "latitude" else (-180, 180)
    if value is None or not lower <= value <= upper:
        raise _PublicDataError(
            f"{field} 必须是 {lower} 至 {upper} 之间的有效坐标"
        )
    return round(float(value), 3)


def _seven_timer_forecast_time(init: Any, timepoint: Any) -> str:
    if not isinstance(init, str) or len(init) != 10:
        raise _PublicDataError("7Timer 返回了无效的预报起始时间")
    if (
        isinstance(timepoint, bool)
        or not isinstance(timepoint, (int, float))
        or not math.isfinite(float(timepoint))
        or not float(timepoint).is_integer()
    ):
        raise _PublicDataError("7Timer 返回了无效的预报时间点")
    hours = int(timepoint)
    if not 0 <= hours <= _SEVEN_TIMER_MAX_HOURS:
        raise _PublicDataError("7Timer 返回了无效的预报时间点")
    try:
        initialized_at = datetime.strptime(init, "%Y%m%d%H").replace(
            tzinfo=timezone.utc
        )
        return (initialized_at + timedelta(hours=hours)).isoformat()
    except (OverflowError, ValueError) as error:
        raise _PublicDataError("7Timer 返回了无效的预报时间点") from error


def _seven_timer_humidity(value: Any) -> int | None:
    if not isinstance(value, str):
        return None
    humidity = number(value.strip().removesuffix("%"), integer=True)
    return humidity if humidity is not None and 0 <= humidity <= 100 else None


def _project_seven_timer_forecast(
    payload: Any,
    limit: int,
) -> list[dict[str, Any]]:
    if not isinstance(payload, Mapping) or payload.get("product") != "civil":
        raise _PublicDataError("7Timer 返回了不支持的数据结构")
    series = payload.get("dataseries")
    if not isinstance(series, list):
        raise _PublicDataError("7Timer 返回了不支持的数据结构")

    forecast = []
    for item in series[:limit]:
        if not isinstance(item, Mapping):
            continue
        wind = item.get("wind10m")
        if not isinstance(wind, Mapping):
            wind = {}
        forecast.append({
            "forecast_at": _seven_timer_forecast_time(
                payload.get("init"),
                item.get("timepoint"),
            ),
            "temperature_c": number(item.get("temp2m"), integer=True),
            "humidity_percent": _seven_timer_humidity(item.get("rh2m")),
            "cloud_cover": number(item.get("cloudcover"), integer=True),
            "precipitation_type": clean_text(item.get("prec_type"), 24),
            "precipitation_amount": number(item.get("prec_amount")),
            "weather_code": clean_text(item.get("weather"), 40),
            "wind_direction": clean_text(wind.get("direction"), 16),
            "wind_speed_mps": number(wind.get("speed")),
        })
    return forecast


class _SevenTimerExecutor(_PublicDataExecutor):
    def execute(self, _context: Any, arguments: dict[str, Any]) -> ToolResult:
        try:
            latitude = _coordinate(arguments, "latitude")
            longitude = _coordinate(arguments, "longitude")
            limit = validate_limit(arguments.get("limit"))
            params = {
                "lon": longitude,
                "lat": latitude,
                "product": "civil",
                "output": "json",
            }
            payload = self._fetch(params)
            forecast = _project_seven_timer_forecast(payload, limit)
            return ToolResult.ok(result_metadata(
                source="7Timer",
                source_url=f"{self._endpoint}?{urlencode(params)}",
                data={
                    "latitude": latitude,
                    "longitude": longitude,
                    "forecast": forecast,
                    "count": len(forecast),
                },
            ))
        except (TypeError, ValueError, OverflowError) as error:
            return self._error(error)


def _seven_timer_definition(permission: str) -> ToolDefinition:
    spec = _PublicDataToolSpec(
        name="public_environment_7timer_forecast",
        skill="web-research",
        namespace="public_environment",
        description=(
            "Get a bounded 7Timer civil weather forecast for explicit latitude "
            "and longitude coordinates. Unlike public_weather_lookup, this "
            "Tool does not geocode place names. Forecast timepoints are UTC; "
            "use as approximate planning context, not as an official warning."
        ),
        action="forecast",
        resource_type="weather_forecast",
        intent_type="coordinate_weather_forecast",
        intent_aliases=(
            "按经纬度查天气",
            "查询坐标天气预报",
            "7Timer天气预报",
            "weather forecast for coordinates",
        ),
        schema=_schema({
            "latitude": {
                "type": "number",
                "minimum": -90,
                "maximum": 90,
            },
            "longitude": {
                "type": "number",
                "minimum": -180,
                "maximum": 180,
            },
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": MAX_RESULTS,
                "default": 5,
            },
        }, ["latitude", "longitude"]),
        result_items_key="forecast",
    )
    return tool_definition(spec, permission)


def public_environment_tool_source(
    *,
    required_permission: str,
    request_get: Callable[..., Any] | None = None,
) -> StaticToolSource:
    permission = str(required_permission or "").strip()
    if not permission:
        raise ValueError("required_permission is required")
    client = _PublicDataHttpClient(request_get)
    weather_endpoint = "https://wttr.in"
    earthquake_endpoint = "https://earthquake.usgs.gov/fdsnws/event/1/query"
    seven_timer_endpoint = "https://www.7timer.info/bin/api.pl"
    return StaticToolSource(
        "agent-platform:public-environment",
        [
            ToolBinding(
                _weather_definition(permission),
                _WeatherExecutor(
                    client,
                    api_name="wttr.in",
                    endpoint=weather_endpoint,
                ),
            ),
            ToolBinding(
                _earthquake_definition(permission),
                _EarthquakeExecutor(
                    client,
                    api_name="USGS",
                    endpoint=earthquake_endpoint,
                ),
            ),
            ToolBinding(
                _seven_timer_definition(permission),
                _SevenTimerExecutor(
                    client,
                    api_name="7Timer",
                    endpoint=seven_timer_endpoint,
                ),
            ),
        ],
    )


__all__ = ["public_environment_tool_source"]
