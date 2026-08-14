#!/usr/bin/env python3
"""
四平台 API 连通性测试脚本 v4.0
- 测试账号：config/ad_platform_credentials.json
- 所有创建的操作都以 PAUSED 状态进行
- 查询限制数量 ≤ 5
"""
import sys, json, time, os
sys.path.insert(0, '/Users/yanping.ma/ryan-personal-knowledge/scripts')

from api_common import ApiResponse
from google_ads_api import GoogleAdsClient
from meta_api import MetaClient
from tiktok_api import TikTokClient
from dv360_api import DV360Client

CONFIG_PATH = '/Users/yanping.ma/ryan-personal-knowledge/config/ad_platform_credentials.json'

def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)

def run_test(name, fn):
    try:
        result = fn()
        print(f"  ✅ {name}: {result}")
        return True
    except Exception as e:
        print(f"  ❌ {name}: {e}")
        return False

# ─────────────────────────────────────────────
# 1. Google Ads
# ─────────────────────────────────────────────
def test_google_ads(cfg):
    print("\n=== Google Ads API ===")
    client = GoogleAdsClient(cfg['google'])
    results = []
    mcc = cfg['google']['login_customer_id']
    sub = cfg['test_accounts']['google']['customer_id']

    # 1.1 Token
    results.append(run_test("Token 获取", lambda: f"{client.get_token()[:12]}..."))

    # 1.2 MCC 账户信息
    r = client.get_customer(mcc)
    results.append(run_test("MCC 账户查询", lambda: f"success={r.success}, name={str(r.data)[:80] if r.data else 'N/A'}"))

    # 1.3 子账户列表
    r = client.list_customers()
    results.append(run_test("子账户列表", lambda: f"success={r.success}, count={len(r.data.get('customers',[])) if isinstance(r.data,dict) else 0}"))

    # 1.4 Campaigns (limit 3)
    r = client.list_campaigns(sub)
    camps = []
    if isinstance(r.data, dict):
        camps = r.data.get('campaigns', [])[:3] if 'campaigns' in r.data else []
    results.append(run_test(f"Campaign 列表 (≤3)", lambda: f"success={r.success}, found={len(camps)} campaigns"))

    # 1.5 Bid Strategy Options (本地数据)
    opts = client.get_bid_strategy_options()
    results.append(run_test("Bid Strategy Options", lambda: f"{len(opts)} 种策略"))

    # 1.6 Campaign Type Options
    opts = client.get_campaign_type_options()
    results.append(run_test("Campaign Type Options", lambda: f"{len(opts)} 种类型"))

    # 1.7 创建 PAUSED Campaign
    def create_paused():
        resp = client.create_campaign(sub, {
            'resource_name': f'customers/{sub}/campaigns/-',
            'name': f'[TEST] Agent-Skill-Test-{int(time.time())}',
            'status': 'PAUSED',
            'advertising_channel_type': 'SEARCH',
            'manual_cpc_bid_ceiling_micros': 500000,
        })
        return f"success={resp.success}, msg={str(resp.error or resp.data)[:100]}"
    results.append(run_test("创建 PAUSED Campaign", create_paused))

    # 1.8 列出 Ad Groups (limit 3)
    def list_adgroups():
        camp_ids = [c.get('resource_name', '').split('/')[-1] for c in camps] if camps else []
        if not camp_ids:
            return "no campaigns to query"
        cid = camp_ids[0]
        r = client.list_ad_groups(sub, cid)
        return f"success={r.success}, ad_groups={len(r.data.get('adGroups',[])) if isinstance(r.data,dict) else 0}"
    results.append(run_test("Ad Group 列表 (≤3)", list_adgroups))

    print(f"  → Google Ads: {'全部通过 ✅' if all(results) else '部分失败 ⚠️'}")
    return all(results)

# ─────────────────────────────────────────────
# 2. Meta
# ─────────────────────────────────────────────
def test_meta(cfg):
    print("\n=== Meta Marketing API ===")
    client = MetaClient(cfg['meta'])
    results = []
    account_id = cfg['test_accounts']['meta']['ad_account_id']

    # 2.1 Token
    results.append(run_test("Token 获取", lambda: f"{client.get_token()[:12]}..."))

    # 2.2 Account 信息
    r = client.get_account(account_id, ['id', 'name', 'account_status'])
    results.append(run_test("Account 查询", lambda: f"success={r.success}, data={str(r.data)[:150] if r.data else 'N/A'}"))

    # 2.3 Campaigns (limit 5)
    r = client.list_campaigns(account_id, ['id', 'name', 'status'])
    camps = r.data.get('data', [])[:5] if isinstance(r.data, dict) else []
    results.append(run_test("Campaign 列表 (≤5)", lambda: f"success={r.success}, found={len(camps)} campaigns"))

    # 2.4 Ad Sets (limit 3)
    r = client.list_adsets(account_id)
    adsets = r.data.get('data', [])[:3] if isinstance(r.data, dict) else []
    results.append(run_test("Ad Set 列表 (≤3)", lambda: f"success={r.success}, found={len(adsets)} adsets"))

    # 2.5 创建 PAUSED Campaign
    def create_paused():
        resp = client.create_campaign(account_id, {
            'name': f'[TEST] Agent-Skill-Test-{int(time.time())}',
            'status': 'PAUSED',
            'objective': 'TRAFFIC',
            'daily_budget': 100,
        })
        d = resp.data if isinstance(resp.data, dict) else {}
        cid = d.get('id', 'unknown')
        return f"success={resp.success}, campaign_id={cid}"
    results.append(run_test("创建 PAUSED Campaign", create_paused))

    # 2.6 Insights (last_7d, limited)
    r = client.get_insights(account_id, ['campaign'], fields=['impressions', 'clicks', 'spend'])
    rows = r.data.get('data', []) if isinstance(r.data, dict) else []
    results.append(run_test("Insights (last_7d)", lambda: f"success={r.success}, rows={len(rows)}"))

    # 2.7 选项数据
    opts = client.get_bid_strategy_options()
    results.append(run_test("Bid Strategy Options", lambda: f"{len(opts)} 种策略"))

    objs = client.get_campaign_objective_options()
    results.append(run_test("Campaign Objective Options", lambda: f"{len(objs)} 种目标"))

    placements = client.get_placement_options()
    results.append(run_test("Placement Options", lambda: f"{len(placements)} 种位置"))

    print(f"  → Meta: {'全部通过 ✅' if all(results) else '部分失败 ⚠️'}")
    return all(results)

# ─────────────────────────────────────────────
# 3. TikTok
# ─────────────────────────────────────────────
def test_tiktok(cfg):
    print("\n=== TikTok Marketing API ===")
    client = TikTokClient(cfg['tiktok'])
    results = []
    adv_id = cfg['test_accounts']['tiktok']['advertiser_id']

    # 3.1 Token
    results.append(run_test("Token 获取", lambda: f"{client.get_token()[:12]}..."))

    # 3.2 Advertiser 查询
    r = client.list_accounts(adv_id)
    results.append(run_test("Advertiser 查询", lambda: f"success={r.success}, data={str(r.data)[:150] if r.data else 'N/A'}"))

    # 3.3 Campaigns (limit 5)
    r = client.list_campaigns(adv_id)
    camps = r.data.get('list', r.data.get('data', []))[:5] if isinstance(r.data, dict) else []
    results.append(run_test("Campaign 列表 (≤5)", lambda: f"success={r.success}, found={len(camps)} campaigns"))

    # 3.4 创建 PAUSED Campaign
    def create_paused():
        resp = client.create_campaign(adv_id, {
            'name': f'[TEST] Agent-Skill-Test-{int(time.time())}',
            'status': 'PAUSED',
            'promotion_type': 'APP_PROMOTION',
            'budget_relevance_preference': 'NONE',
        })
        d = resp.data if isinstance(resp.data, dict) else {}
        cid = d.get('id', d.get('campaign_id', 'unknown'))
        return f"success={resp.success}, campaign_id={cid}"
    results.append(run_test("创建 PAUSED Campaign", create_paused))

    # 3.5 Ad Groups (limit 3)
    def list_adgroups():
        camp_ids = [c.get('id') for c in camps] if camps else []
        if not camp_ids:
            return "no campaigns to query"
        r = client.list_adgroups(adv_id, camp_ids[0])
        ags = r.data.get('list', r.data.get('data', []))[:3] if isinstance(r.data, dict) else []
        return f"success={r.success}, adgroups={len(ags)}"
    results.append(run_test("Ad Group 列表 (≤3)", list_adgroups))

    # 3.6 选项数据
    opts = client.get_bid_strategy_options() or []
    results.append(run_test("Bid Strategy Options", lambda: f"{len(opts)} 种策略"))

    objs = client.get_campaign_objective_options() or []
    results.append(run_test("Campaign Objective Options", lambda: f"{len(objs)} 种目标"))

    placements = client.get_placement_options() or []
    results.append(run_test("Placement Options", lambda: f"{len(placements)} 种位置"))

    print(f"  → TikTok: {'全部通过 ✅' if all(results) else '部分失败 ⚠️'}")
    return all(results)

# ─────────────────────────────────────────────
# 4. DV360
# ─────────────────────────────────────────────
def test_dv360(cfg):
    print("\n=== DV360 API ===")
    client = DV360Client(cfg['dv360'])
    results = []
    partner = cfg['dv360'].get('partner_id', '4659631')
    adv_id = cfg['test_accounts']['dv360']['advertiser_id']

    # 4.1 Token
    results.append(run_test("Token 获取", lambda: f"{client.get_token()[:12]}..."))

    # 4.2 Advertisers
    r = client.list_advertisers(partner)
    results.append(run_test("Advertiser 列表", lambda: f"success={r.success}, data={str(r.data)[:200] if r.data else 'N/A'}"))

    # 4.3 Campaigns (limit 5)
    r = client.list_campaigns(adv_id)
    camps = r.data.get('campaigns', r.data.get('data', []))[:5] if isinstance(r.data, dict) else []
    results.append(run_test("Campaign 列表 (≤5)", lambda: f"success={r.success}, found={len(camps)} campaigns"))

    # 4.4 创建 PAUSED Campaign
    def create_paused():
        resp = client.create_campaign(adv_id, {
            'name': f'[TEST] Agent-Skill-Test-{int(time.time())}',
            'state': 'PAUSED',
            'start_date': {'day': 1, 'month': 1, 'year': 2026},
            'end_date': {'day': 1, 'month': 1, 'year': 2027},
        })
        d = resp.data if isinstance(resp.data, dict) else {}
        cid = d.get('id', d.get('campaignId', 'unknown'))
        return f"success={resp.success}, campaign_id={cid}"
    results.append(run_test("创建 PAUSED Campaign", create_paused))

    # 4.5 Insertion Orders (limit 3)
    r = client.list_insertion_orders(adv_id)
    ios = r.data.get('insertionOrders', r.data.get('data', []))[:3] if isinstance(r.data, dict) else []
    results.append(run_test("Insertion Order 列表 (≤3)", lambda: f"success={r.success}, found={len(ios)} IOs"))

    # 4.6 选项数据
    opts = client.get_bid_strategy_options() or []
    results.append(run_test("Bid Strategy Options", lambda: f"{len(opts)} 种策略"))

    formats = client.get_creative_format_options() or []
    results.append(run_test("Creative Format Options", lambda: f"{len(formats)} 种格式"))

    targets = client.get_targeting_dimension_options() or []
    results.append(run_test("Targeting Dimension Options", lambda: f"{len(targets)} 种定向维度"))

    print(f"  → DV360: {'全部通过 ✅' if all(results) else '部分失败 ⚠️'}")
    return all(results)

# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────
if __name__ == '__main__':
    print("=" * 60)
    print("  四平台 API 连通性测试 v4.0")
    print("  测试账号见 config/ad_platform_credentials.json")
    print("=" * 60)

    cfg = load_config()
    google_ok = test_google_ads(cfg)
    meta_ok = test_meta(cfg)
    tiktok_ok = test_tiktok(cfg)
    dv360_ok = test_dv360(cfg)

    print("\n" + "=" * 60)
    print("  测试结果汇总")
    print("=" * 60)
    print(f"  Google Ads : {'✅ 通过' if google_ok else '❌ 失败'}")
    print(f"  Meta       : {'✅ 通过' if meta_ok else '❌ 失败'}")
    print(f"  TikTok     : {'✅ 通过' if tiktok_ok else '❌ 失败'}")
    print(f"  DV360      : {'✅ 通过' if dv360_ok else '❌ 失败'}")
    all_ok = google_ok and meta_ok and tiktok_ok and dv360_ok
    print(f"\n  总结果: {'✅ 全部通过' if all_ok else '⚠️ 部分失败，请查看上方日志'}")
    sys.exit(0 if all_ok else 1)
