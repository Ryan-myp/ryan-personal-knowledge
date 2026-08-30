"""DV360 current baseline; deeper construction is intentionally deferred."""

API_SURFACE = [
    {"resource": "advertiser", "action": "list", "method": "list_advertisers", "status": "implemented"},
    {"resource": "advertiser", "action": "get", "method": "get_advertiser", "status": "implemented"},
    {"resource": "campaign", "action": "crud", "method": "get_campaign", "status": "implemented"},
    {"resource": "insertion_order", "action": "crud", "method": "create_io", "status": "implemented"},
    {"resource": "line_item", "action": "crud", "method": "create_line_item", "status": "implemented"},
    {"resource": "creative", "action": "crud", "method": "create_creative", "status": "implemented"},
    {"resource": "targeting", "action": "assignment", "method": "create_line_item_assigned_targeting_option", "status": "implemented"},
    {"resource": "report", "action": "async", "method": "create_report", "status": "implemented"},
    {"resource": "targeting", "action": "catalog", "method": "list_targeting_options", "status": "implemented"},
    {"resource": "audience", "action": "crud", "status": "planned", "gap": "DV360 受众与定向深度建设按计划暂缓"},
    {"resource": "inventory_source", "action": "crud", "status": "planned", "gap": "库存来源与品牌安全资源尚无完整 Tool"},
]
