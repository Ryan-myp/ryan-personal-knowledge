"""Writable Demand Gen channel controls from the Google Ads v24 proto contract."""

CHANNEL_STRATEGIES = ("ALL_CHANNELS", "ALL_OWNED_AND_OPERATED_CHANNELS")
SELECTED_CHANNELS = (
    "youtube_shorts", "youtube_in_feed", "youtube_in_stream",
    "gmail", "maps", "discover", "display",
)


def validate_group_settings(value):
    if not isinstance(value, dict) or set(value) - {"channel_controls"}:
        raise ValueError("Demand Gen settings 必须为已声明字段的对象")
    if "channel_controls" not in value:
        return
    controls = value["channel_controls"]
    if not isinstance(controls, dict):
        raise ValueError("Demand Gen channel_controls 必须为对象")
    if set(controls) - {"channel_strategy", "selected_channels"}:
        raise ValueError("Demand Gen channel_config 为只读字段；不接受未声明的频道控制字段")
    if len(controls) != 1:
        raise ValueError("Demand Gen 请选择 channel_strategy 或 selected_channels 中的一种")
    if "channel_strategy" in controls:
        if controls["channel_strategy"] not in CHANNEL_STRATEGIES:
            raise ValueError("Demand Gen channel_strategy 无效")
        return
    channels = controls["selected_channels"]
    if (not isinstance(channels, dict) or set(channels) - set(SELECTED_CHANNELS)
            or any(type(flag) is not bool for flag in channels.values())
            or not any(channels.values())):
        raise ValueError("Demand Gen selected_channels 必须至少启用一个有效频道")
