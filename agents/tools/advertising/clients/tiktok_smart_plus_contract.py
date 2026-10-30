"""Optional Smart+ fields from TikTok's versioned Business API SDK models.

Source: python_sdk/docs/SmartPlusAdCreateBodyCreativeInfoMusicInfo.md and
SmartPlusAdCreateBodyAdConfiguration.md in tiktok/tiktok-business-api-sdk.
Collection limits below bound our UI/Tool payload, not claimed Provider maxima.
"""

from agents.agent_harness.core.interfaces import ToolSchema
from agents.agent_harness.core.tool_registry import validate_tool_input


def music_schema():
    return {
        "type": "object", "description": "音乐配置", "presentation": "object_editor",
        "required": ["music_id"], "additionalProperties": False,
        "properties": {
            "music_id": {
                "type": "string", "minLength": 1, "maxLength": 200,
                "description": "已取得使用授权的 TikTok 音乐 ID",
                "manual_entry": {
                    "title": "音乐 ID", "source": "tiktok_authorized_music",
                    "instructions": "填写渠道提供且有使用权限的音乐 ID；当前不提供音乐目录查询。",
                },
            },
        },
    }


def product_configuration_fields():
    text = {"type": "string", "minLength": 1, "maxLength": 200}
    return {
        "product_ids": {
            "type": "array", "description": "指定商品 ID", "minItems": 1, "maxItems": 100,
            "uniqueItems": True, "items": text,
            "manual_entry": {
                "title": "商品 ID", "source": "tiktok_catalog_product_ids",
                "instructions": "填写已由渠道确认属于当前 Catalog 的商品 ID，每行一个。",
            },
        },
        "product_display_field_list": {
            "type": "array", "description": "商品展示字段", "minItems": 1, "maxItems": 20,
            "items": text, "uniqueItems": True,
            "manual_entry": {
                "title": "商品展示字段", "source": "tiktok_product_display_fields",
                "instructions": "填写当前账户支持的展示字段标识；不将未知字段假定为已支持。",
            },
        },
        "catalog_creative_toggle": {"type": "boolean", "description": "启用 Catalog 创意"},
        "utm_params": {
            "type": "array", "description": "UTM 参数", "maxItems": 50,
            "presentation": "object_editor",
            "items": {
                "type": "object", "additionalProperties": False, "required": ["key", "value"],
                "properties": {
                    "key": {"type": "string", "description": "参数名",
                            "minLength": 1, "maxLength": 200},
                    "value": {"type": "string", "description": "参数值",
                              "minLength": 1, "maxLength": 2000},
                },
            },
        },
    }


def validate_optional_blocks(ad):
    configuration = ad.get("ad_configuration") or {}
    if not isinstance(configuration, dict):
        raise ValueError("TikTok ad_configuration 必须是对象")
    for name in ("product_info", "catalog_creative_info"):
        if name in ad or name in configuration:
            raise ValueError(
                f"TikTok {name} 未接入有效合同；请使用 ad_configuration 中的 "
                "product_ids、product_set_id 或 catalog_creative_toggle"
            )
    selected = {
        key: configuration[key] for key in product_configuration_fields() if key in configuration
    }
    errors = validate_tool_input(ToolSchema(properties=product_configuration_fields()), selected)
    if errors:
        raise ValueError("TikTok 商品或 UTM 配置不符合字段合同")
    music_values = [ad["music_info"]] if "music_info" in ad else []
    for item in ad.get("creative_list") or []:
        info = item.get("creative_info") if isinstance(item, dict) else None
        if isinstance(info, dict) and "music_info" in info:
            music_values.append(info["music_info"])
    for value in music_values:
        if validate_tool_input(ToolSchema(properties={"music": music_schema()}), {"music": value}):
            raise ValueError("TikTok music_info 必须包含有效 music_id，不能包含未声明字段")
