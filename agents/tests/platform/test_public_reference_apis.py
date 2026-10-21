from __future__ import annotations

import json
from types import SimpleNamespace

from agents.agent_harness.core.interfaces import ReplayPolicy, RiskLevel, ToolEffect
from agents.applications.advertising.composition.ad_application import (
    AdvertisingComposition,
)
from agents.applications.advertising.integrations.mcp.runtime_mcp import (
    RuntimeMCPServers,
)
from agents.agent_platform.tools.public_reference_apis import (
    public_environment_tool_source,
    public_research_tool_source,
)
from agents.agent_platform.governance.identity.principal import RequestPrincipal


class FakeResponse:
    def __init__(self, payload=None, *, body=None, status_code=200):
        self.status_code = status_code
        self.headers = {}
        self.body = (
            body if body is not None
            else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        )
        self.closed = False

    def iter_content(self, chunk_size):
        for offset in range(0, len(self.body), chunk_size):
            yield self.body[offset:offset + chunk_size]

    def close(self):
        self.closed = True


def _source_bindings(source_factory, request_get=None, **kwargs):
    source = source_factory(
        required_permission="ads.read",
        request_get=request_get,
        **kwargs,
    )
    return source, {
        binding.definition.name: binding
        for binding in source.list_bindings()
    }


def _execute(binding, arguments):
    context = SimpleNamespace(
        request=SimpleNamespace(
            principal=SimpleNamespace(
                user_id="operator",
                tenant_id="tenant-a",
                permissions=frozenset({"ads.read"}),
            ),
        ),
    )
    return binding.executor.execute(context, arguments)


def test_public_reference_tools_are_read_only_bounded_and_mcp_categorized():
    definitions = {}
    for source_factory in (
        public_environment_tool_source,
        public_research_tool_source,
    ):
        source, bindings = _source_bindings(source_factory)
        definitions.update({
            name: binding.definition for name, binding in bindings.items()
        })
        assert source.source_id.startswith("agent-platform:")

    assert set(definitions) == {
        "public_weather_lookup",
        "public_environment_earthquakes",
        "public_environment_7timer_forecast",
        "public_knowledge_wikipedia_search",
        "public_knowledge_open_library_search",
        "public_research_crossref_search",
        "public_research_arxiv_search",
        "public_trends_hackernews_search",
    }
    expected_namespaces = {
        "public_weather_lookup": "public-weather",
        "public_environment_earthquakes": "public-environment",
        "public_environment_7timer_forecast": "public-environment",
        "public_knowledge_wikipedia_search": "public-knowledge",
        "public_knowledge_open_library_search": "public-knowledge",
        "public_research_crossref_search": "public-research",
        "public_research_arxiv_search": "public-research",
        "public_trends_hackernews_search": "public-trends",
    }
    for name, definition in definitions.items():
        assert definition.namespace == expected_namespaces[name]
        assert definition.effect_class is ToolEffect.READ
        assert definition.risk_level is RiskLevel.LOW
        assert definition.replay_policy is ReplayPolicy.SAFE
        assert definition.required_permissions == ["ads.read"]
        assert definition.scope_required is False
        assert definition.input_schema.additional_properties is False
        assert definition.max_output_bytes <= 32_000
        assert definition.timeout_seconds <= 30
        assert "external_public_data" in definition.traits


def test_public_reference_tools_appear_in_runtime_mcp_category_listing():
    runtime = AdvertisingComposition(require_llm=False, features=[])
    runtime.register_tool_source(public_environment_tool_source(
        required_permission="ads.read",
        request_get=lambda *_args, **_kwargs: None,
    ))
    runtime.register_tool_source(public_research_tool_source(
        required_permission="ads.read",
        request_get=lambda *_args, **_kwargs: None,
    ))
    principal = RequestPrincipal(
        user_id="operator",
        tenant_id="tenant-a",
        permissions=frozenset({"ads.read"}),
    )
    gateway = RuntimeMCPServers(lambda: runtime, lambda *_args, **_kwargs: principal)

    try:
        gateway.refresh(runtime)
        servers = {
            item["server_id"]: item
            for item in gateway.list_servers(runtime, principal)
        }
        assert {
            "namespace-public_environment",
            "namespace-public_knowledge",
            "namespace-public_research",
            "namespace-public_trends",
            "namespace-public_weather",
        } <= set(servers)
        assert {
            item["tool_id"]
            for item in servers["namespace-public_research"]["tools"]
        } == {
            "public_research_crossref_search",
            "public_research_arxiv_search",
        }
        assert servers["namespace-public_research"]["source"] == "runtime_registry"
    finally:
        runtime.close(wait=True)


def test_weather_lookup_encodes_location_and_projects_limited_forecast():
    response = FakeResponse({
        "nearest_area": [{
            "areaName": [{"value": "Shenzhen"}],
            "country": [{"value": "China"}],
        }],
        "current_condition": [{
            "temp_C": "25",
            "FeelsLikeC": "26",
            "humidity": "72",
            "windspeedKmph": "10",
            "weatherDesc": [{"value": "Partly cloudy"}],
        }],
        "weather": [{
            "date": "2026-10-21",
            "maxtempC": "28",
            "mintempC": "22",
            "hourly": [{"weatherDesc": [{"value": "Cloudy"}]}],
        }],
    })
    calls = []

    def request_get(url, **kwargs):
        calls.append((url, kwargs))
        return response

    _, bindings = _source_bindings(public_environment_tool_source, request_get)
    result = _execute(bindings["public_weather_lookup"], {
        "location": "Shenzhen/../../internal",
    })

    assert result.success is True
    assert result.data["location"] == "Shenzhen/../../internal"
    assert result.data["current"]["temperature_c"] == 25
    assert result.data["forecast"][0]["date"] == "2026-10-21"
    assert len(result.data["forecast"]) <= 3
    assert calls[0][0].startswith("https://wttr.in/Shenzhen%2F..%2F..%2Finternal")
    assert calls[0][1]["params"] == {"format": "j1"}


def test_earthquake_search_bounds_query_and_projects_geojson():
    response = FakeResponse({
        "features": [{
            "id": "us7000abcd",
            "properties": {
                "mag": 4.2,
                "place": "10 km NW of Example",
                "time": 1792540000000,
                "url": "https://earthquake.usgs.gov/example",
                "type": "earthquake",
                "tsunami": 0,
                "status": "reviewed",
            },
            "geometry": {"coordinates": [-122.1, 38.2, 5.0]},
        }],
    })
    calls = []
    _, bindings = _source_bindings(
        public_environment_tool_source,
        lambda url, **kwargs: calls.append((url, kwargs)) or response,
    )
    result = _execute(bindings["public_environment_earthquakes"], {
        "start_date": "2026-10-20",
        "end_date": "2026-10-21",
        "min_magnitude": 2.5,
        "limit": 10,
        "orderby": "magnitude",
    })

    assert result.success is True
    assert result.data["count"] == 1
    assert result.data["events"][0]["magnitude"] == 4.2
    assert result.data["events"][0]["coordinates"] == [-122.1, 38.2, 5.0]
    assert calls[0][0] == "https://earthquake.usgs.gov/fdsnws/event/1/query"
    assert calls[0][1]["params"]["format"] == "geojson"
    assert calls[0][1]["params"]["limit"] == 10


def test_7timer_forecast_validates_coordinates_and_projects_bounded_points():
    response = FakeResponse({
        "product": "civil",
        "init": "2026102018",
        "dataseries": [
            {
                "timepoint": 3,
                "cloudcover": 1,
                "prec_type": "none",
                "prec_amount": 0,
                "temp2m": 27,
                "rh2m": "66%",
                "wind10m": {"direction": "NW", "speed": 2},
                "weather": "clearnight",
                "unrelated": "must not leak",
            },
            {
                "timepoint": 6,
                "cloudcover": 3,
                "prec_type": "rain",
                "prec_amount": 2,
                "temp2m": 24,
                "rh2m": "72%",
                "wind10m": {"direction": "N", "speed": 3},
                "weather": "lightrain",
            },
            {
                "timepoint": 9,
                "temp2m": 20,
                "weather": "cloudy",
            },
        ],
    })
    calls = []
    _, bindings = _source_bindings(
        public_environment_tool_source,
        lambda url, **kwargs: calls.append((url, kwargs)) or response,
    )

    result = _execute(bindings["public_environment_7timer_forecast"], {
        "latitude": 23.0908,
        "longitude": 113.1707,
        "limit": 2,
    })

    assert result.success is True
    assert result.data["source"] == "7Timer"
    assert result.data["latitude"] == 23.091
    assert result.data["longitude"] == 113.171
    assert result.data["forecast"][0] == {
        "forecast_at": "2026-10-20T21:00:00+00:00",
        "temperature_c": 27,
        "humidity_percent": 66,
        "cloud_cover": 1,
        "precipitation_type": "none",
        "precipitation_amount": 0,
        "weather_code": "clearnight",
        "wind_direction": "NW",
        "wind_speed_mps": 2,
    }
    assert len(result.data["forecast"]) == 2
    assert "unrelated" not in repr(result.data)
    assert calls[0][0] == "https://www.7timer.info/bin/api.pl"
    assert calls[0][1]["params"] == {
        "lon": 113.171,
        "lat": 23.091,
        "product": "civil",
        "output": "json",
    }


def test_7timer_forecast_rejects_invalid_coordinates_before_network_call():
    calls = []
    _, bindings = _source_bindings(
        public_environment_tool_source,
        lambda url, **kwargs: calls.append((url, kwargs)),
    )

    result = _execute(bindings["public_environment_7timer_forecast"], {
        "latitude": 91,
        "longitude": 0,
    })

    assert result.success is False
    assert calls == []


def test_7timer_forecast_rejects_fractional_timepoints():
    _, bindings = _source_bindings(
        public_environment_tool_source,
        lambda *_args, **_kwargs: FakeResponse({
            "product": "civil",
            "init": "2026102018",
            "dataseries": [{"timepoint": 1.5}],
        }),
    )

    result = _execute(bindings["public_environment_7timer_forecast"], {
        "latitude": 23,
        "longitude": 113,
    })

    assert result.success is False
    assert "时间点" in result.error


def test_wikipedia_search_strips_html_and_returns_citable_page_url():
    response = FakeResponse({
        "query": {
            "search": [{
                "title": "Marketing",
                "snippet": "The <span class=\"searchmatch\">marketing</span> process.",
                "pageid": 123,
            }],
        },
    })
    calls = []
    _, bindings = _source_bindings(
        public_research_tool_source,
        lambda url, **kwargs: calls.append((url, kwargs)) or response,
    )
    result = _execute(bindings["public_knowledge_wikipedia_search"], {
        "query": "marketing",
        "language": "en",
        "limit": 3,
    })

    assert result.success is True
    assert result.data["results"][0]["snippet"] == "The marketing process."
    assert result.data["results"][0]["source_url"].endswith("/wiki/Marketing")
    assert calls[0][1]["params"]["list"] == "search"


def test_open_library_search_projects_bounded_book_records():
    response = FakeResponse({
        "numFound": 12,
        "docs": [{
            "key": "/works/OL123W",
            "title": "Advertising and Society",
            "author_name": ["Ada Lovelace", "Grace Hopper"],
            "first_publish_year": 2022,
            "edition_count": 3,
            "isbn": ["9780000000001"],
            "publisher": ["Example Press"],
            "large_payload": "must not leak",
        }],
    })
    calls = []
    _, bindings = _source_bindings(
        public_research_tool_source,
        lambda url, **kwargs: calls.append((url, kwargs)) or response,
    )
    result = _execute(bindings["public_knowledge_open_library_search"], {
        "query": "advertising",
        "limit": 4,
    })

    assert result.success is True
    assert result.data["results"][0]["title"] == "Advertising and Society"
    assert result.data["results"][0]["authors"] == ["Ada Lovelace", "Grace Hopper"]
    assert result.data["results"][0]["source_url"].endswith("/works/OL123W")
    assert "large_payload" not in repr(result.data)
    assert calls[0][1]["params"]["limit"] == 4


def test_crossref_search_projects_bounded_publication_metadata():
    response = FakeResponse({
        "message": {
            "items": [{
                "DOI": "10.1234/example",
                "title": ["Advertising measurement"],
                "author": [{"given": "Ada", "family": "Lovelace"}],
                "published": {"date-parts": [[2024, 5, 1]]},
                "container-title": ["Journal of Marketing"],
                "type": "journal-article",
                "URL": "https://doi.org/10.1234/example",
                "is-referenced-by-count": 12,
                "unrelated": "must not leak",
            }],
        },
    })
    calls = []
    _, bindings = _source_bindings(
        public_research_tool_source,
        lambda url, **kwargs: calls.append((url, kwargs)) or response,
    )
    result = _execute(bindings["public_research_crossref_search"], {
        "query": "advertising measurement",
        "limit": 5,
    })

    assert result.success is True
    assert result.data["results"][0]["doi"] == "10.1234/example"
    assert result.data["results"][0]["authors"] == ["Ada Lovelace"]
    assert "unrelated" not in repr(result.data)
    assert calls[0][1]["params"]["rows"] == 5


def test_arxiv_search_parses_atom_and_limits_output():
    body = b"""<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
      <entry>
        <id>https://arxiv.org/abs/2401.00001</id>
        <updated>2024-01-02T00:00:00Z</updated>
        <published>2024-01-01T00:00:00Z</published>
        <title>  Measuring Ad Effectiveness </title>
        <summary> An empirical study. </summary>
        <author><name>Ada Lovelace</name></author>
        <category term="cs.CY" />
      </entry>
    </feed>"""
    response = FakeResponse(body=body)
    calls = []
    _, bindings = _source_bindings(
        public_research_tool_source,
        lambda url, **kwargs: calls.append((url, kwargs)) or response,
    )
    result = _execute(bindings["public_research_arxiv_search"], {
        "query": "advertising attribution",
        "limit": 4,
    })

    assert result.success is True
    assert result.data["results"][0]["title"] == "Measuring Ad Effectiveness"
    assert result.data["results"][0]["authors"] == ["Ada Lovelace"]
    assert calls[0][0] == "https://export.arxiv.org/api/query"
    assert calls[0][1]["params"]["max_results"] == 4


def test_hackernews_search_filters_to_stories_and_projects_safe_fields():
    response = FakeResponse({
        "hits": [{
            "objectID": "123",
            "title": "A useful technology story",
            "url": "https://example.com/story",
            "created_at": "2026-10-21T08:00:00Z",
            "points": 31,
            "num_comments": 7,
            "author": "submitter",
            "_tags": ["story"],
            "private": "must not leak",
        }],
    })
    calls = []
    _, bindings = _source_bindings(
        public_research_tool_source,
        lambda url, **kwargs: calls.append((url, kwargs)) or response,
    )
    result = _execute(bindings["public_trends_hackernews_search"], {
        "query": "advertising technology",
        "limit": 5,
    })

    assert result.success is True
    assert result.data["results"][0]["title"] == "A useful technology story"
    assert result.data["results"][0]["discussion_url"].endswith("/item?id=123")
    assert "private" not in repr(result.data)
    assert calls[0][1]["params"]["tags"] == "story"
