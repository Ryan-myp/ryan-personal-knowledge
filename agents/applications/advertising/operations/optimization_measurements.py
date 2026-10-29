"""Mature, comparable observational metrics; no causal claims from before/after."""

from datetime import date, timedelta
import math
from zoneinfo import ZoneInfo


def validate_measurement(value, today):
    start, end = date.fromisoformat(value["start_date"]), date.fromisoformat(value["end_date"])
    lag = value["attribution_days"]
    number = value["value"]
    if type(lag) is not int or not 0 <= lag <= 90:
        raise ValueError("归因天数必须为 0 至 90 的整数")
    if type(number) not in (float, int) or not math.isfinite(number) or number < 0:
        raise ValueError("指标值必须为有限非负数")
    ZoneInfo(value["timezone"])
    if start > end or (end - start).days > 366:
        raise ValueError("指标日期窗口无效")
    if end + timedelta(days=lag + 7) > today:
        raise ValueError("归因窗口和 7 天延迟尚未成熟，暂不复盘效果")
    return start, end


def compare_measurements(baseline, outcome, *, executed_at, observation_days, today):
    start, end = validate_measurement(outcome, today)
    old_start, old_end = validate_measurement(baseline, today)
    for key in ("metric", "unit", "currency", "timezone", "attribution_days"):
        if baseline[key] != outcome[key]:
            raise ValueError(f"指标口径不一致：{key}")
    execution_day = executed_at.astimezone(ZoneInfo(outcome["timezone"])).date()
    if old_end >= execution_day:
        raise ValueError("基线窗口必须完全在实际执行日期之前")
    if start <= execution_day or start <= old_end:
        raise ValueError("观察窗口必须在实际执行后，且不能与基线重叠")
    if (end - start).days != (old_end - old_start).days:
        raise ValueError("观察与基线的窗口长度不同")
    if (end - start).days + 1 < observation_days:
        raise ValueError("观察窗口长度不足")
    delta = outcome["value"] - baseline["value"]
    return {
        "absolute_change": delta,
        "relative_change": delta / baseline["value"] if baseline["value"] else None,
        "causal_claim": False,
        "evidence_status": "user_supplied_observations",
        "interpretation": "仅为同口径前后变化；未经随机实验或增量测量，不能归因于本次调整。",
    }
