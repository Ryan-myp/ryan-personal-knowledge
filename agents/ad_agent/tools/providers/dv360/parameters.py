"""DV360 provider parameter contracts owned by the DV360 Tool Source.

The API has several resource levels (Campaign -> IO -> Line Item).  These
schemas keep the fields that can be selected in a plan explicit while leaving
provider/account IDs to the trusted account context.
"""

from __future__ import annotations

from typing import Any


DV360_CAMPAIGN_TYPES = ["DISPLAY", "VIDEO", "AUDIO", "CONNECTED_TV", "DOOH"]
DV360_GOAL_TYPES = [
    "IMPRESSIONS", "CLICKS", "CONVERSIONS", "REVENUE",
    "VIEWABLE_IMPRESSIONS", "VIDEO_COMPLETIONS",
]
DV360_LINE_ITEM_TYPES = [
    "DISPLAY_DEFAULT", "VIDEO_DEFAULT", "AUDIO_DEFAULT",
    "CONNECTED_TV_DEFAULT", "YOUTUBE_AND_PARTNERS_VIDEO",
]
DV360_BID_STRATEGIES = [
    "MANUAL_CPM", "MANUAL_CPC", "MAXIMIZE_CONVERSIONS",
    "TARGET_CPA", "TARGET_ROAS",
]
DV360_STATUSES = ["DRAFT", "ACTIVE", "PAUSED", "ARCHIVED"]
DV360_PACING_TYPES = ["ASAP", "EVEN"]


def _field(field_type: Any, description: str = "", **kwargs: Any) -> dict[str, Any]:
    value = {"type": field_type, "description": description}
    value.update(kwargs)
    return value


def _object(properties: dict[str, Any], description: str, *, additional_properties: bool = False) -> dict[str, Any]:
    return {
        "type": "object",
        "description": description,
        "properties": properties,
        "additionalProperties": additional_properties,
    }


def dv360_campaign_schema() -> dict[str, Any]:
    return {
        "required": ["advertiser_id", "name"],
        "requires": ["campaign_type", "objective", "start_date", "end_date"],
        "properties": {
            "advertiser_id": _field("string", "DV360 advertiser ID"),
            "name": _field("string", "Campaign display name", minLength=1, maxLength=255),
            "campaign_type": _field("string", "Campaign channel type", enum=DV360_CAMPAIGN_TYPES),
            "objective": _field("string", "Campaign objective", enum=DV360_GOAL_TYPES),
            "start_date": _field("string", "ISO date YYYY-MM-DD"),
            "end_date": _field("string", "ISO date YYYY-MM-DD"),
            "status": _field("string", "Initial status", enum=DV360_STATUSES),
        },
        "conditional_rules": [],
    }


def dv360_io_schema() -> dict[str, Any]:
    return {
        "required": ["advertiser_id", "campaign_id", "name"],
        "requires": ["budget", "start_date", "end_date"],
        "properties": {
            "advertiser_id": _field("string", "DV360 advertiser ID"),
            "campaign_id": _field("string", "Parent Campaign ID"),
            "name": _field("string", "Insertion Order name", minLength=1, maxLength=255),
            "budget": _field("number", "Spend cap in account currency", minimum=0),
            "spend_cap_micros": _field("integer", "Spend cap in micros", minimum=0),
            "start_date": _field("string", "ISO date YYYY-MM-DD"),
            "end_date": _field("string", "ISO date YYYY-MM-DD"),
            "status": _field("string", "Entity status", enum=DV360_STATUSES),
            "pacing_type": _field("string", "Budget pacing", enum=DV360_PACING_TYPES),
            "frequency_cap": _object({
                "time_unit": _field("string", "Frequency cap unit", enum=["MINUTE", "HOUR", "DAY", "WEEK", "MONTH"]),
                "max_impressions": _field("integer", "Maximum impressions", minimum=1),
            }, "Frequency cap"),
        },
    }


def dv360_line_item_schema() -> dict[str, Any]:
    return {
        "required": ["io_id", "name"],
        "requires": ["type", "goal", "targeting", "budget", "start_date", "end_date"],
        "properties": {
            "io_id": _field("string", "Parent insertion order ID"),
            "name": _field("string", "Line item name", minLength=1, maxLength=255),
            "type": _field("string", "Line item type", enum=DV360_LINE_ITEM_TYPES),
            "goal": _object({
                "goal_type": _field("string", "Goal type", enum=DV360_GOAL_TYPES),
                "target_cpa": _field("number", "Target CPA", minimum=0),
                "target_roas": _field("number", "Target ROAS", minimum=0.01),
            }, "Line item performance goal", additional_properties=True),
            "targeting": _object({}, "Targeting expression", additional_properties=True),
            "budget": _field("number", "Line item budget", minimum=0),
            "start_date": _field("string", "ISO date YYYY-MM-DD"),
            "end_date": _field("string", "ISO date YYYY-MM-DD"),
            "status": _field("string", "Entity status", enum=DV360_STATUSES),
            "bid_strategy": _field("string", "Bid strategy", enum=DV360_BID_STRATEGIES),
            "bid_amount": _field("number", "Manual bid amount", minimum=0),
        },
        "conditional_rules": [
            {
                "id": "target_cpa_requires_goal",
                "if": {"bid_strategy": "TARGET_CPA"},
                "required": ["goal"],
                "message": "TARGET_CPA requires a goal object",
            },
            {
                "id": "target_roas_requires_goal",
                "if": {"bid_strategy": "TARGET_ROAS"},
                "required": ["goal"],
                "message": "TARGET_ROAS requires a goal object",
            },
        ],
    }
