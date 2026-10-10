from agents.tools.advertising.clients.google_ads_client import GoogleAdsAPIClient


def test_google_ad_readback_exposes_creative_content_and_association_identity():
    client = GoogleAdsAPIClient({})
    client._search = lambda query: {
        "results": [
            {
                "adGroupAd": {
                    "resourceName": "customers/test/adGroupAds/123~456",
                    "status": "PAUSED",
                    "ad": {
                        "id": "456",
                        "resourceName": "customers/test/ads/456",
                        "type": "RESPONSIVE_SEARCH_AD",
                        "finalUrls": ["https://example.com"],
                        "responsiveSearchAd": {
                            "headlines": [{"text": "Updated headline"}],
                            "descriptions": [{"text": "Updated description"}],
                        },
                    },
                },
            }
        ]
    }
    result = client.get_ad("123~456")
    assert result["id"] == "123~456"
    assert result["responsive_search_ad"]["headlines"][0]["text"] == "Updated headline"
    assert result["final_urls"] == ["https://example.com"]


def test_google_creative_update_uses_proto_field_mask_paths():
    client = GoogleAdsAPIClient({})
    operation = client._build_google_ad_content_operation(
        "456",
        {
            "headlines": ["First headline", "Second headline", "Third headline"],
            "descriptions": ["First description", "Second description"],
            "final_url": "https://example.com",
        },
    )
    paths = operation["adOperation"]["updateMask"]["paths"]
    assert set(paths) == {
        "responsive_search_ad.headlines",
        "responsive_search_ad.descriptions",
        "final_urls",
    }


def test_campaign_details_include_type_specific_settings_for_verified_fixtures():
    client = GoogleAdsAPIClient({})
    queries = []
    client._search = lambda query: (
        queries.append(query)
        or {
            "results": [
                {
                    "campaign": {
                        "id": "123",
                        "status": "PAUSED",
                        "appCampaignSetting": {
                            "appId": "verified.app",
                            "appStore": "GOOGLE_APP_STORE",
                            "biddingStrategyGoalType": "OPTIMIZE_INSTALLS_TARGET_INSTALL_COST",
                        },
                        "shoppingSetting": {
                            "merchantId": "456",
                            "feedLabel": "US",
                            "campaignPriority": 0,
                        },
                    }
                }
            ]
        }
    )
    result = client.get_campaign("123")
    assert result["app_campaign_setting"] == {
        "app_id": "verified.app",
        "app_store": "GOOGLE_APP_STORE",
        "bidding_strategy_goal_type": "OPTIMIZE_INSTALLS_TARGET_INSTALL_COST",
    }
    assert result["shopping_setting"] == {
        "merchant_id": "456",
        "feed_label": "US",
        "campaign_priority": 0,
    }
    assert "campaign.app_campaign_setting.app_id" in queries[0]
    assert "campaign.shopping_setting.merchant_id" in queries[0]
