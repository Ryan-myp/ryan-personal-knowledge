#!/usr/bin/env python3
"""
全面测试四平台查询 API
"""
import sys
import json
import time
from datetime import datetime

sys.path.insert(0, 'scripts')
from ad_platform_api import AdPlatformClient

def test_tiktok_api(client):
    """测试 TikTok API"""
    print("=" * 70)
    print("🎵 TIKTOK API 测试")
    print("=" * 70)
    
    results = []
    account_id = "7397068114548195329"
    campaign_id = "1836521788460274"
    
    # 1. List Accounts
    print("\n1. list_accounts:")
    try:
        result = client.tiktok_list_accounts()
        if isinstance(result, list):
            print(f"   ✅ Success: {len(result)} accounts")
            results.append({"method": "list_accounts", "status": "✅", "count": len(result)})
        else:
            print(f"   ⚠️ Response type: {type(result)}")
            results.append({"method": "list_accounts", "status": "⚠️", "note": f"Type: {type(result)}"})
    except Exception as e:
        print(f"   ❌ Error: {e}")
        results.append({"method": "list_accounts", "status": "❌", "error": str(e)})
    
    # 2. List Campaigns
    print("\n2. list_campaigns:")
    try:
        result = client.tiktok_list_campaigns(account_id=account_id, page_size=5)
        if isinstance(result, list):
            print(f"   ✅ Success: {len(result)} campaigns")
            results.append({"method": "list_campaigns", "status": "✅", "count": len(result)})
        elif isinstance(result, dict):
            campaigns = result.get('data', {}).get('list', []) if 'data' in result else result.get('list', [])
            print(f"   ✅ Success: {len(campaigns)} campaigns")
            results.append({"method": "list_campaigns", "status": "✅", "count": len(campaigns)})
        else:
            print(f"   ⚠️ Unexpected response")
            results.append({"method": "list_campaigns", "status": "⚠️", "note": f"Type: {type(result)}"})
    except Exception as e:
        print(f"   ❌ Error: {e}")
        results.append({"method": "list_campaigns", "status": "❌", "error": str(e)})
    
    # 3. Get Campaign
    print("\n3. get_campaign:")
    try:
        result = client.tiktok_get_campaign(campaign_id=campaign_id, account_id=account_id)
        if result:
            print(f"   ✅ Success: {result.get('campaign_name', 'N/A')}")
            results.append({"method": "get_campaign", "status": "✅", "name": result.get('campaign_name')})
        else:
            print(f"   ⚠️ Empty result")
            results.append({"method": "get_campaign", "status": "⚠️", "note": "Empty result"})
    except Exception as e:
        print(f"   ❌ Error: {e}")
        results.append({"method": "get_campaign", "status": "❌", "error": str(e)})
    
    # 4. List Ad Groups
    print("\n4. list_adgroups:")
    try:
        result = client.tiktok_list_adgroups(campaign_id=campaign_id)
        if isinstance(result, list):
            print(f"   ✅ Success: {len(result)} ad groups")
            results.append({"method": "list_adgroups", "status": "✅", "count": len(result)})
        else:
            print(f"   ⚠️ Response type: {type(result)}")
            results.append({"method": "list_adgroups", "status": "⚠️", "note": f"Type: {type(result)}"})
    except Exception as e:
        print(f"   ❌ Error: {e}")
        results.append({"method": "list_adgroups", "status": "❌", "error": str(e)})
    
    # 5. Get Ad Group
    print("\n5. get_adgroup:")
    try:
        if result and len(result) > 0:
            adgroup_id = result[0].get('adgroup_id', '')
            result = client.tiktok_get_adgroup(adgroup_id=adgroup_id)
            if result:
                print(f"   ✅ Success: {result.get('name', 'N/A')}")
                results.append({"method": "get_adgroup", "status": "✅", "name": result.get('name')})
            else:
                print(f"   ⚠️ Empty result")
                results.append({"method": "get_adgroup", "status": "⚠️", "note": "Empty result"})
        else:
            print(f"   ⏭️ Skip (no ad groups)")
            results.append({"method": "get_adgroup", "status": "⏭️", "note": "Skipped - no ad groups"})
    except Exception as e:
        print(f"   ❌ Error: {e}")
        results.append({"method": "get_adgroup", "status": "❌", "error": str(e)})
    
    # 6. List Ads
    print("\n6. list_ads:")
    try:
        # 获取第一个 adgroup 的 ads
        ag_result = client.tiktok_list_adgroups(campaign_id=campaign_id)
        if isinstance(ag_result, list) and len(ag_result) > 0:
            adgroup_id = ag_result[0].get('adgroup_id', '')
            result = client.tiktok_list_ads(adgroup_id=adgroup_id)
            if isinstance(result, list):
                print(f"   ✅ Success: {len(result)} ads")
                results.append({"method": "list_ads", "status": "✅", "count": len(result)})
            else:
                print(f"   ⚠️ Response type: {type(result)}")
                results.append({"method": "list_ads", "status": "⚠️", "note": f"Type: {type(result)}"})
        else:
            print(f"   ⏭️ Skip (no ad groups)")
            results.append({"method": "list_ads", "status": "⏭️", "note": "Skipped - no ad groups"})
    except Exception as e:
        print(f"   ❌ Error: {e}")
        results.append({"method": "list_ads", "status": "❌", "error": str(e)})
    
    # 7. Get Ad
    print("\n7. get_ad:")
    try:
        # 获取第一个 ad
        ads_result = client.tiktok_list_ads(adgroup_id=ag_result[0].get('adgroup_id', '') if isinstance(ag_result, list) and len(ag_result) > 0 else '')
        if isinstance(ads_result, list) and len(ads_result) > 0:
            ad_id = ads_result[0].get('ad_id', '')
            result = client.tiktok_get_ad(ad_id=ad_id)
            if result:
                print(f"   ✅ Success: {result.get('name', 'N/A')}")
                results.append({"method": "get_ad", "status": "✅", "name": result.get('name')})
            else:
                print(f"   ⚠️ Empty result")
                results.append({"method": "get_ad", "status": "⚠️", "note": "Empty result"})
        else:
            print(f"   ⏭️ Skip (no ads)")
            results.append({"method": "get_ad", "status": "⏭️", "note": "Skipped - no ads"})
    except Exception as e:
        print(f"   ❌ Error: {e}")
        results.append({"method": "get_ad", "status": "❌", "error": str(e)})
    
    # 8. List Audiences
    print("\n8. list_audiences:")
    try:
        result = client.tiktok_list_audiences(account_id=account_id)
        if isinstance(result, list):
            print(f"   ✅ Success: {len(result)} audiences")
            results.append({"method": "list_audiences", "status": "✅", "count": len(result)})
        else:
            print(f"   ⚠️ Response type: {type(result)}")
            results.append({"method": "list_audiences", "status": "⚠️", "note": f"Type: {type(result)}"})
    except Exception as e:
        print(f"   ❌ Error: {e}")
        results.append({"method": "list_audiences", "status": "❌", "error": str(e)})
    
    # 9. List Videos
    print("\n9. list_videos:")
    try:
        result = client.tiktok_list_videos(account_id=account_id)
        if isinstance(result, list):
            print(f"   ✅ Success: {len(result)} videos")
            results.append({"method": "list_videos", "status": "✅", "count": len(result)})
        else:
            print(f"   ⚠️ Response type: {type(result)}")
            results.append({"method": "list_videos", "status": "⚠️", "note": f"Type: {type(result)}"})
    except Exception as e:
        print(f"   ❌ Error: {e}")
        results.append({"method": "list_videos", "status": "❌", "error": str(e)})
    
    # 10. Query Report
    print("\n10. query_report:")
    try:
        result = client.tiktok_query_report(account_id=account_id, start_date='2025-01-01', end_date='2025-01-31')
        if result:
            print(f"   ✅ Success")
            results.append({"method": "query_report", "status": "✅"})
        else:
            print(f"   ⚠️ Empty result")
            results.append({"method": "query_report", "status": "⚠️", "note": "Empty result"})
    except Exception as e:
        print(f"   ❌ Error: {e}")
        results.append({"method": "query_report", "status": "❌", "error": str(e)})
    
    return results


def test_meta_api(client):
    """测试 Meta API"""
    print("\n" + "=" * 70)
    print("📘 META API 测试")
    print("=" * 70)
    
    results = []
    account_id = "2806375919473667"
    campaign_id = "120250706434530251"
    
    # 1. List Accounts
    print("\n1. list_accounts:")
    try:
        result = client.meta_list_accounts()
        if isinstance(result, list):
            print(f"   ✅ Success: {len(result)} accounts")
            results.append({"method": "list_accounts", "status": "✅", "count": len(result)})
        else:
            print(f"   ⚠️ Response type: {type(result)}")
            results.append({"method": "list_accounts", "status": "⚠️", "note": f"Type: {type(result)}"})
    except Exception as e:
        print(f"   ❌ Error: {e}")
        results.append({"method": "list_accounts", "status": "❌", "error": str(e)})
    
    # 2. List Campaigns
    print("\n2. list_campaigns:")
    try:
        result = client.meta_list_campaigns(account_id=account_id, limit=5)
        campaigns = result.get('data', []) if isinstance(result, dict) else result
        if isinstance(campaigns, list):
            print(f"   ✅ Success: {len(campaigns)} campaigns")
            results.append({"method": "list_campaigns", "status": "✅", "count": len(campaigns)})
        else:
            print(f"   ⚠️ Unexpected response")
            results.append({"method": "list_campaigns", "status": "⚠️", "note": f"Type: {type(campaigns)}"})
    except Exception as e:
        print(f"   ❌ Error: {e}")
        results.append({"method": "list_campaigns", "status": "❌", "error": str(e)})
    
    # 3. Get Campaign
    print("\n3. get_campaign:")
    try:
        result = client.meta_get_campaign(campaign_id=campaign_id)
        if result and 'name' in result:
            print(f"   ✅ Success: {result.get('name', 'N/A')}")
            results.append({"method": "get_campaign", "status": "✅", "name": result.get('name')})
        else:
            print(f"   ⚠️ Invalid response")
            results.append({"method": "get_campaign", "status": "⚠️", "note": f"Invalid: {result}"})
    except Exception as e:
        print(f"   ❌ Error: {e}")
        results.append({"method": "get_campaign", "status": "❌", "error": str(e)})
    
    # 4. List Ad Sets
    print("\n4. list_adsets:")
    try:
        result = client.meta_list_adsets(campaign_id=campaign_id)
        if isinstance(result, list):
            print(f"   ✅ Success: {len(result)} ad sets")
            results.append({"method": "list_adsets", "status": "✅", "count": len(result)})
        else:
            print(f"   ⚠️ Response type: {type(result)}")
            results.append({"method": "list_adsets", "status": "⚠️", "note": f"Type: {type(result)}"})
    except Exception as e:
        print(f"   ❌ Error: {e}")
        results.append({"method": "list_adsets", "status": "❌", "error": str(e)})
    
    # 5. Get Ad Set
    print("\n5. get_adset:")
    try:
        adsets = client.meta_list_adsets(campaign_id=campaign_id)
        if isinstance(adsets, list) and len(adsets) > 0:
            adset_id = adsets[0].get('id', '')
            result = client.meta_get_adset(adset_id=adset_id)
            if result and 'name' in result:
                print(f"   ✅ Success: {result.get('name', 'N/A')}")
                results.append({"method": "get_adset", "status": "✅", "name": result.get('name')})
            else:
                print(f"   ⚠️ Invalid response")
                results.append({"method": "get_adset", "status": "⚠️", "note": "Invalid"})
        else:
            print(f"   ⏭️ Skip (no ad sets)")
            results.append({"method": "get_adset", "status": "⏭️", "note": "Skipped"})
    except Exception as e:
        print(f"   ❌ Error: {e}")
        results.append({"method": "get_adset", "status": "❌", "error": str(e)})
    
    # 6. List Ads
    print("\n6. list_ads:")
    try:
        result = client.meta_list_ads(adset_id=adset_id if 'adset_id' in dir() else '')
        if isinstance(result, list):
            print(f"   ✅ Success: {len(result)} ads")
            results.append({"method": "list_ads", "status": "✅", "count": len(result)})
        else:
            print(f"   ⚠️ Response type: {type(result)}")
            results.append({"method": "list_ads", "status": "⚠️", "note": f"Type: {type(result)}"})
    except Exception as e:
        print(f"   ❌ Error: {e}")
        results.append({"method": "list_ads", "status": "❌", "error": str(e)})
    
    # 7. Get Ad
    print("\n7. get_ad:")
    try:
        ads = client.meta_list_ads(adset_id=adset_id if 'adset_id' in dir() else '')
        if isinstance(ads, list) and len(ads) > 0:
            ad_id = ads[0].get('id', '')
            result = client.meta_get_ad(ad_id=ad_id)
            if result and 'name' in result:
                print(f"   ✅ Success: {result.get('name', 'N/A')}")
                results.append({"method": "get_ad", "status": "✅", "name": result.get('name')})
            else:
                print(f"   ⚠️ Invalid response")
                results.append({"method": "get_ad", "status": "⚠️", "note": "Invalid"})
        else:
            print(f"   ⏭️ Skip (no ads)")
            results.append({"method": "get_ad", "status": "⏭️", "note": "Skipped"})
    except Exception as e:
        print(f"   ❌ Error: {e}")
        results.append({"method": "get_ad", "status": "❌", "error": str(e)})
    
    # 8. List Audiences
    print("\n8. list_audiences:")
    try:
        result = client.meta_list_audiences(account_id=account_id)
        if isinstance(result, list):
            print(f"   ✅ Success: {len(result)} audiences")
            results.append({"method": "list_audiences", "status": "✅", "count": len(result)})
        else:
            print(f"   ⚠️ Response type: {type(result)}")
            results.append({"method": "list_audiences", "status": "⚠️", "note": f"Type: {type(result)}"})
    except Exception as e:
        print(f"   ❌ Error: {e}")
        results.append({"method": "list_audiences", "status": "❌", "error": str(e)})
    
    # 9. List Catalogs
    print("\n9. list_catalogs:")
    try:
        result = client.meta_list_catalogs(account_id=account_id)
        if isinstance(result, list):
            print(f"   ✅ Success: {len(result)} catalogs")
            results.append({"method": "list_catalogs", "status": "✅", "count": len(result)})
        else:
            print(f"   ⚠️ Response type: {type(result)}")
            results.append({"method": "list_catalogs", "status": "⚠️", "note": f"Type: {type(result)}"})
    except Exception as e:
        print(f"   ❌ Error: {e}")
        results.append({"method": "list_catalogs", "status": "❌", "error": str(e)})
    
    # 10. Query Insights
    print("\n10. query_insights:")
    try:
        result = client.meta_query_insights(account_id=account_id, since='2025-01-01', until='2025-01-31')
        if result:
            print(f"   ✅ Success")
            results.append({"method": "query_insights", "status": "✅"})
        else:
            print(f"   ⚠️ Empty result")
            results.append({"method": "query_insights", "status": "⚠️", "note": "Empty"})
    except Exception as e:
        print(f"   ❌ Error: {e}")
        results.append({"method": "query_insights", "status": "❌", "error": str(e)})
    
    return results


def test_google_api(client):
    """测试 Google Ads API"""
    print("\n" + "=" * 70)
    print("📊 GOOGLE ADS API 测试")
    print("=" * 70)
    
    results = []
    customer_id = "2493002626"  # MCC
    campaign_id = "53544223001"  # 示例 campaign ID
    
    # 1. List Customers
    print("\n1. list_customers:")
    try:
        result = client.google_list_customers(limit=5)
        if isinstance(result, list):
            print(f"   ✅ Success: {len(result)} customers")
            results.append({"method": "list_customers", "status": "✅", "count": len(result)})
        else:
            print(f"   ⚠️ Response type: {type(result)}")
            results.append({"method": "list_customers", "status": "⚠️", "note": f"Type: {type(result)}"})
    except Exception as e:
        print(f"   ❌ Error: {e}")
        results.append({"method": "list_customers", "status": "❌", "error": str(e)})
    
    # 2. List Campaigns
    print("\n2. list_campaigns:")
    try:
        result = client.google_list_campaigns(customer_id=customer_id, limit=5)
        if isinstance(result, list):
            print(f"   ✅ Success: {len(result)} campaigns")
            results.append({"method": "list_campaigns", "status": "✅", "count": len(result)})
        else:
            print(f"   ⚠️ Response type: {type(result)}")
            results.append({"method": "list_campaigns", "status": "⚠️", "note": f"Type: {type(result)}"})
    except Exception as e:
        print(f"   ❌ Error: {e}")
        results.append({"method": "list_campaigns", "status": "❌", "error": str(e)})
    
    # 3. Get Campaign
    print("\n3. get_campaign:")
    try:
        campaigns = client.google_list_campaigns(customer_id=customer_id, limit=1)
        if isinstance(campaigns, list) and len(campaigns) > 0:
            camp = campaigns[0]
            result = client.google_get_campaign(customer_id=customer_id, campaign_id=camp.get('resource_name', '').split('/')[-1])
            if result:
                print(f"   ✅ Success: {result.get('resource_name', 'N/A')}")
                results.append({"method": "get_campaign", "status": "✅", "name": result.get('resource_name')})
            else:
                print(f"   ⚠️ Empty result")
                results.append({"method": "get_campaign", "status": "⚠️", "note": "Empty"})
        else:
            print(f"   ⏭️ Skip (no campaigns)")
            results.append({"method": "get_campaign", "status": "⏭️", "note": "Skipped"})
    except Exception as e:
        print(f"   ❌ Error: {e}")
        results.append({"method": "get_campaign", "status": "❌", "error": str(e)})
    
    # 4. List Ad Groups
    print("\n4. list_ad_groups:")
    try:
        result = client.google_list_ad_groups(customer_id=customer_id, campaign_id=campaign_id, limit=5)
        if isinstance(result, list):
            print(f"   ✅ Success: {len(result)} ad groups")
            results.append({"method": "list_ad_groups", "status": "✅", "count": len(result)})
        else:
            print(f"   ⚠️ Response type: {type(result)}")
            results.append({"method": "list_ad_groups", "status": "⚠️", "note": f"Type: {type(result)}"})
    except Exception as e:
        print(f"   ❌ Error: {e}")
        results.append({"method": "list_ad_groups", "status": "❌", "error": str(e)})
    
    # 5. List Keywords
    print("\n5. list_keywords:")
    try:
        result = client.google_list_keywords(customer_id=customer_id, ad_group_id=campaign_id, limit=5)
        if isinstance(result, list):
            print(f"   ✅ Success: {len(result)} keywords")
            results.append({"method": "list_keywords", "status": "✅", "count": len(result)})
        else:
            print(f"   ⚠️ Response type: {type(result)}")
            results.append({"method": "list_keywords", "status": "⚠️", "note": f"Type: {type(result)}"})
    except Exception as e:
        print(f"   ❌ Error: {e}")
        results.append({"method": "list_keywords", "status": "❌", "error": str(e)})
    
    # 6. List Ads
    print("\n6. list_ads:")
    try:
        result = client.google_list_ads(customer_id=customer_id, ad_group_id=campaign_id, limit=5)
        if isinstance(result, list):
            print(f"   ✅ Success: {len(result)} ads")
            results.append({"method": "list_ads", "status": "✅", "count": len(result)})
        else:
            print(f"   ⚠️ Response type: {type(result)}")
            results.append({"method": "list_ads", "status": "⚠️", "note": f"Type: {type(result)}"})
    except Exception as e:
        print(f"   ❌ Error: {e}")
        results.append({"method": "list_ads", "status": "❌", "error": str(e)})
    
    # 7. Download Report
    print("\n7. download_report:")
    try:
        result = client.google_download_report(customer_id=customer_id, date='2025-01-01')
        if result:
            print(f"   ✅ Success")
            results.append({"method": "download_report", "status": "✅"})
        else:
            print(f"   ⚠️ Empty result")
            results.append({"method": "download_report", "status": "⚠️", "note": "Empty"})
    except Exception as e:
        print(f"   ❌ Error: {e}")
        results.append({"method": "download_report", "status": "❌", "error": str(e)})
    
    # 8. Get Customer Info
    print("\n8. get_customer_info:")
    try:
        result = client.google_get_customer_info(customer_id=customer_id)
        if result:
            print(f"   ✅ Success: {result.get('descriptive_name', 'N/A')}")
            results.append({"method": "get_customer_info", "status": "✅", "name": result.get('descriptive_name')})
        else:
            print(f"   ⚠️ Empty result")
            results.append({"method": "get_customer_info", "status": "⚠️", "note": "Empty"})
    except Exception as e:
        print(f"   ❌ Error: {e}")
        results.append({"method": "get_customer_info", "status": "❌", "error": str(e)})
    
    return results


def test_dv360_api(client):
    """测试 DV360 API"""
    print("\n" + "=" * 70)
    print("📺 DV360 API 测试")
    print("=" * 70)
    
    results = []
    advertiser_id = "5110831"
    
    # 1. List Advertisers
    print("\n1. list_advertisers:")
    try:
        result = client.dv360_list_advertisers(partner_id="4659631")
        advertisers = result.get('advertisers', []) if isinstance(result, dict) else result
        if isinstance(advertisers, list):
            print(f"   ✅ Success: {len(advertisers)} advertisers")
            results.append({"method": "list_advertisers", "status": "✅", "count": len(advertisers)})
        else:
            print(f"   ⚠️ Response type: {type(advertisers)}")
            results.append({"method": "list_advertisers", "status": "⚠️", "note": f"Type: {type(advertisers)}"})
    except Exception as e:
        print(f"   ❌ Error: {e}")
        results.append({"method": "list_advertisers", "status": "❌", "error": str(e)})
    
    # 2. Get Advertiser
    print("\n2. get_advertiser:")
    try:
        result = client.dv360_get_advertiser(advertiser_id=advertiser_id)
        if result and 'displayName' in result:
            print(f"   ✅ Success: {result.get('displayName', 'N/A')}")
            results.append({"method": "get_advertiser", "status": "✅", "name": result.get('displayName')})
        else:
            print(f"   ⚠️ Invalid response")
            results.append({"method": "get_advertiser", "status": "⚠️", "note": "Invalid"})
    except Exception as e:
        print(f"   ❌ Error: {e}")
        results.append({"method": "get_advertiser", "status": "❌", "error": str(e)})
    
    # 3. List Line Items
    print("\n3. list_line_items:")
    try:
        result = client.dv360_list_line_items(advertiser_id=advertiser_id, limit=5)
        line_items = result.get('lineItems', []) if isinstance(result, dict) else result
        if isinstance(line_items, list):
            print(f"   ✅ Success: {len(line_items)} line items")
            results.append({"method": "list_line_items", "status": "✅", "count": len(line_items)})
        else:
            print(f"   ⚠️ Response type: {type(line_items)}")
            results.append({"method": "list_line_items", "status": "⚠️", "note": f"Type: {type(line_items)}"})
    except Exception as e:
        print(f"   ❌ Error: {e}")
        results.append({"method": "list_line_items", "status": "❌", "error": str(e)})
    
    # 4. Get Line Item
    print("\n4. get_line_item:")
    try:
        items = client.dv360_list_line_items(advertiser_id=advertiser_id, limit=1)
        if isinstance(items, list) and len(items) > 0:
            item = items[0]
            result = client.dv360_get_line_item(line_item_id=item.get('lineItemId', ''))
            if result:
                print(f"   ✅ Success: {result.get('displayName', 'N/A')}")
                results.append({"method": "get_line_item", "status": "✅", "name": result.get('displayName')})
            else:
                print(f"   ⚠️ Empty result")
                results.append({"method": "get_line_item", "status": "⚠️", "note": "Empty"})
        else:
            print(f"   ⏭️ Skip (no line items)")
            results.append({"method": "get_line_item", "status": "⏭️", "note": "Skipped"})
    except Exception as e:
        print(f"   ❌ Error: {e}")
        results.append({"method": "get_line_item", "status": "❌", "error": str(e)})
    
    # 5. List Flights
    print("\n5. list_flights:")
    try:
        result = client.dv360_list_flights(advertiser_id=advertiser_id, limit=5)
        flights = result.get('flights', []) if isinstance(result, dict) else result
        if isinstance(flights, list):
            print(f"   ✅ Success: {len(flights)} flights")
            results.append({"method": "list_flights", "status": "✅", "count": len(flights)})
        else:
            print(f"   ⚠️ Response type: {type(flights)}")
            results.append({"method": "list_flights", "status": "⚠️", "note": f"Type: {type(flights)}"})
    except Exception as e:
        print(f"   ❌ Error: {e}")
        results.append({"method": "list_flights", "status": "❌", "error": str(e)})
    
    # 6. List Creatives
    print("\n6. list_creatives:")
    try:
        result = client.dv360_list_creatives(advertiser_id=advertiser_id, limit=5)
        creatives = result.get('creatives', []) if isinstance(result, dict) else result
        if isinstance(creatives, list):
            print(f"   ✅ Success: {len(creatives)} creatives")
            results.append({"method": "list_creatives", "status": "✅", "count": len(creatives)})
        else:
            print(f"   ⚠️ Response type: {type(creatives)}")
            results.append({"method": "list_creatives", "status": "⚠️", "note": f"Type: {type(creatives)}"})
    except Exception as e:
        print(f"   ❌ Error: {e}")
        results.append({"method": "list_creatives", "status": "❌", "error": str(e)})
    
    # 7. List Audiences
    print("\n7. list_audiences:")
    try:
        result = client.dv360_list_audiences(advertiser_id=advertiser_id, limit=5)
        audiences = result.get('audiences', []) if isinstance(result, dict) else result
        if isinstance(audiences, list):
            print(f"   ✅ Success: {len(audiences)} audiences")
            results.append({"method": "list_audiences", "status": "✅", "count": len(audiences)})
        else:
            print(f"   ⚠️ Response type: {type(audiences)}")
            results.append({"method": "list_audiences", "status": "⚠️", "note": f"Type: {type(audiences)}"})
    except Exception as e:
        print(f"   ❌ Error: {e}")
        results.append({"method": "list_audiences", "status": "❌", "error": str(e)})
    
    # 8. Get Report
    print("\n8. get_report:")
    try:
        result = client.dv360_get_report(advertiser_id=advertiser_id, start_date='2025-01-01', end_date='2025-01-31')
        if result:
            print(f"   ✅ Success")
            results.append({"method": "get_report", "status": "✅"})
        else:
            print(f"   ⚠️ Empty result")
            results.append({"method": "get_report", "status": "⚠️", "note": "Empty"})
    except Exception as e:
        print(f"   ❌ Error: {e}")
        results.append({"method": "get_report", "status": "❌", "error": str(e)})
    
    # 9. List Targetings
    print("\n9. list_targetings:")
    try:
        result = client.dv360_list_targetings(advertiser_id=advertiser_id, limit=5)
        targetings = result.get('targetings', []) if isinstance(result, dict) else result
        if isinstance(targetings, list):
            print(f"   ✅ Success: {len(targetings)} targetings")
            results.append({"method": "list_targetings", "status": "✅", "count": len(targetings)})
        else:
            print(f"   ⚠️ Response type: {type(targetings)}")
            results.append({"method": "list_targetings", "status": "⚠️", "note": f"Type: {type(targetings)}"})
    except Exception as e:
        print(f"   ❌ Error: {e}")
        results.append({"method": "list_targetings", "status": "❌", "error": str(e)})
    
    # 10. List Bidding Strategies
    print("\n10. list_bidding_strategies:")
    try:
        result = client.dv360_list_bidding_strategies(advertiser_id=advertiser_id)
        strategies = result.get('biddingStrategies', []) if isinstance(result, dict) else result
        if isinstance(strategies, list):
            print(f"   ✅ Success: {len(strategies)} strategies")
            results.append({"method": "list_bidding_strategies", "status": "✅", "count": len(strategies)})
        else:
            print(f"   ⚠️ Response type: {type(strategies)}")
            results.append({"method": "list_bidding_strategies", "status": "⚠️", "note": f"Type: {type(strategies)}"})
    except Exception as e:
        print(f"   ❌ Error: {e}")
        results.append({"method": "list_bidding_strategies", "status": "❌", "error": str(e)})
    
    return results


def main():
    print("""
╔════════════════════════════════════════════════════════════════════╗
║              四平台查询 API 全面测试                                ║
╚════════════════════════════════════════════════════════════════════╝
""")
    
    client = AdPlatformClient()
    all_results = {}
    
    # 测试 TikTok
    tiktok_results = test_tiktok_api(client)
    all_results['TikTok'] = tiktok_results
    
    # 测试 Meta
    meta_results = test_meta_api(client)
    all_results['Meta'] = meta_results
    
    # 测试 Google Ads
    google_results = test_google_api(client)
    all_results['Google Ads'] = google_results
    
    # 测试 DV360
    dv360_results = test_dv360_api(client)
    all_results['DV360'] = dv360_results
    
    # 汇总统计
    print("\n" + "=" * 70)
    print("📊 测试汇总")
    print("=" * 70)
    
    total = 0
    success = 0
    warning = 0
    error = 0
    skipped = 0
    
    for platform, results in all_results.items():
        plat_success = sum(1 for r in results if r['status'] == '✅')
        plat_warning = sum(1 for r in results if r['status'] == '⚠️')
        plat_error = sum(1 for r in results if r['status'] == '❌')
        plat_skipped = sum(1 for r in results if r['status'] == '⏭️')
        
        total += len(results)
        success += plat_success
        warning += plat_warning
        error += plat_error
        skipped += plat_skipped
        
        print(f"\n{platform}:")
        print(f"   ✅ Success: {plat_success}/{len(results)}")
        if plat_warning > 0:
            print(f"   ⚠️ Warning: {plat_warning}")
        if plat_error > 0:
            print(f"   ❌ Error: {plat_error}")
        if plat_skipped > 0:
            print(f"   ⏭️ Skipped: {plat_skipped}")
    
    print("\n" + "-" * 70)
    print(f"总计: {total} 个接口")
    print(f"   ✅ 成功: {success} ({success/total*100:.1f}%)")
    print(f"   ⚠️ 警告: {warning}")
    print(f"   ❌ 错误: {error}")
    print(f"   ⏭️ 跳过: {skipped}")
    print("=" * 70)
    
    # 保存详细结果
    with open('docs/api-test-detailed-results.json', 'w') as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    print(f"\n📄 详细结果已保存: docs/api-test-detailed-results.json")


if __name__ == '__main__':
    main()
