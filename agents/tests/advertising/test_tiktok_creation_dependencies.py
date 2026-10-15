import json

from agents.tools.advertising.clients.tiktok_client import TikTokAPIClient


ACCOUNT = "7397068114548195329"


def test_cta_portfolio_lookup_uses_the_official_collection_and_result_bound():
    client = TikTokAPIClient({"access_token": "test"})
    calls = []

    def request(method, endpoint, params=None, **kwargs):
        calls.append((method, endpoint, params))
        return {"status_code": 200, "data": {"code": 0, "data": {
            "creative_portfolios": [
                {"creative_portfolio_id": "123", "creative_portfolio_type": "CTA"},
                {"creative_portfolio_id": "456", "creative_portfolio_type": "CTA"},
            ],
            "page_info": {"total_page": 1},
        }}}

    client.request_raw = request
    rows = client.list_creative_portfolios(ACCOUNT, portfolio_type="CTA", limit=1)
    assert [row["creative_portfolio_id"] for row in rows] == ["123"]
    assert calls[0][0] == "GET"
    assert calls[0][1].endswith("/creative/portfolio/list/")
    assert json.loads(calls[0][2]["filtering"]) == {"creative_portfolio_types": ["CTA"]}
