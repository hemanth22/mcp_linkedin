"""Offline tests for the LinkedIn Jobs MCP server.

Network calls are replaced with fixtures so CI is deterministic and never
hits LinkedIn or DuckDuckGo (both rate-limit GitHub runner IPs).
"""

import pytest
from fastmcp import Client

import main

SEARCH_HTML = """
<ul>
  <li>
    <div data-entity-urn="urn:li:jobPosting:111">
      <a class="base-card__full-link" href="https://www.linkedin.com/jobs/view/sre-111?trk=abc&refId=x"></a>
      <h3 class="base-search-card__title">Site Reliability Engineer</h3>
      <h4 class="base-search-card__subtitle">Acme</h4>
      <span class="job-search-card__location">Bengaluru, India</span>
      <time datetime="2026-11-09">1 hour ago</time>
    </div>
  </li>
  <li>
    <div data-entity-urn="urn:li:jobPosting:222">
      <a class="base-card__full-link" href="https://www.linkedin.com/jobs/view/dev-222?trk=def"></a>
      <h3 class="base-search-card__title">Python Developer</h3>
      <h4 class="base-search-card__subtitle">Globex</h4>
      <span class="job-search-card__location">Remote</span>
      <time datetime="2026-11-09">12 minutes ago</time>
    </div>
  </li>
  <li><span>card without a link is skipped</span></li>
</ul>
"""

DETAIL_HTML = """
<h2 class="top-card-layout__title">Site Reliability Engineer</h2>
<a class="topcard__org-name-link">Acme</a>
<span class="topcard__flavor--bullet">Bengaluru, India</span>
<ul>
  <li class="description__job-criteria-item"><h3>Seniority level</h3><span>Mid-Senior level</span></li>
  <li class="description__job-criteria-item"><h3>Employment type</h3><span>Full-time</span></li>
</ul>
<div class="show-more-less-html__markup"><p>Run Kubernetes.</p><p>Be on call.</p></div>
"""


@pytest.fixture
def calls(monkeypatch):
    """Replace the HTTP layer and record every request."""
    recorded = []

    async def fake_get(path, params=None):
        recorded.append((path, params))
        return DETAIL_HTML if path.startswith("jobPosting/") else SEARCH_HTML

    monkeypatch.setattr(main, "_get", fake_get)
    return recorded


async def call(tool, args):
    async with Client(main.mcp) as client:
        result = await client.call_tool(tool, args)
    return result.data


async def test_lists_tools_and_prompts():
    async with Client(main.mcp) as client:
        tools = {t.name for t in await client.list_tools()}
        prompts = {p.name for p in await client.list_prompts()}
    assert tools == {
        "search_job", "search_latest_jobs", "search_jobs_last_hour",
        "get_job_details", "search_feed_job_posts",
    }
    assert prompts == {"sre_jobs_last_hour", "latest_jobs", "job_deep_dive"}


async def test_search_job_parses_cards(calls):
    jobs = await call("search_job", {"keyword": "sre"})
    assert len(jobs) == 2
    assert jobs[0] == {
        "job_id": "111",
        "title": "Site Reliability Engineer",
        "company": "Acme",
        "location": "Bengaluru, India",
        "posted": "2026-11-09",
        "posted_text": "1 hour ago",
        "url": "https://www.linkedin.com/jobs/view/sre-111",  # tracking params stripped
    }
    assert calls[0][1]["f_TPR"] == "r604800"  # week


async def test_search_latest_jobs_maps_filters(calls):
    await call("search_latest_jobs", {
        "keywords": "python", "location": "India", "time_posted": "month",
        "job_type": "contract", "experience_level": "entry", "work_mode": "remote",
        "limit": 1, "start": 25,
    })
    path, params = calls[0]
    assert path == "seeMoreJobPostings/search"
    assert params == {
        "keywords": "python", "location": "India", "f_TPR": "r2592000",
        "sortBy": "DD", "start": 25, "f_JT": "C", "f_E": "2", "f_WT": "2",
    }


async def test_limit_is_respected(calls):
    jobs = await call("search_latest_jobs", {"keywords": "x", "limit": 1})
    assert len(jobs) == 1


async def test_last_hour_exact_filter(calls):
    jobs = await call("search_jobs_last_hour", {"exact_one_hour": True})
    assert [j["job_id"] for j in jobs] == ["111"]
    assert calls[0][1]["f_TPR"] == "r3600"


async def test_invalid_enum_is_rejected(calls):
    async with Client(main.mcp) as client:
        result = await client.call_tool(
            "search_latest_jobs", {"keywords": "x", "work_mode": "moon"},
            raise_on_error=False,
        )
    assert result.is_error
    assert calls == []


async def test_get_job_details(calls):
    job = await call("get_job_details", {"job_id": "111"})
    assert job["title"] == "Site Reliability Engineer"
    assert job["company"] == "Acme"
    assert job["criteria"] == {"Seniority level": "Mid-Senior level", "Employment type": "Full-time"}
    assert job["description"] == "Run Kubernetes.\nBe on call."
    assert job["url"] == "https://www.linkedin.com/jobs/view/111"


async def test_rate_limit_surfaces_as_tool_error(monkeypatch):
    async def limited(path, params=None):
        raise RuntimeError("LinkedIn rate-limited this request. Wait a few minutes and retry.")

    monkeypatch.setattr(main, "_get", limited)
    async with Client(main.mcp) as client:
        result = await client.call_tool("search_job", {"keyword": "x"}, raise_on_error=False)
    assert result.is_error
    assert "rate-limited" in result.content[0].text


async def test_feed_posts_filters_non_post_urls(monkeypatch):
    class FakeDDGS:
        def __init__(self, timeout):
            pass

        def text(self, query, **kwargs):
            assert 'site:linkedin.com/posts hiring "sre"' == query
            return [
                {"href": "https://www.linkedin.com/posts/alice_hiring-sre?utm=1", "title": "Hiring", "body": "SRE role"},
                {"href": "https://example.com/not-linkedin", "title": "x", "body": "y"},
            ]

    monkeypatch.setattr(main, "DDGS", FakeDDGS)
    posts = await call("search_feed_job_posts", {"keyword": "sre"})
    assert posts == [{
        "title": "Hiring",
        "url": "https://www.linkedin.com/posts/alice_hiring-sre",
        "snippet": "SRE role",
    }]


async def test_feed_posts_no_results_returns_empty(monkeypatch):
    class EmptyDDGS:
        def __init__(self, timeout):
            pass

        def text(self, *a, **k):
            raise Exception("No results found.")

    monkeypatch.setattr(main, "DDGS", EmptyDDGS)
    assert await call("search_feed_job_posts", {"keyword": "sre"}) == []


async def test_prompt_renders():
    async with Client(main.mcp) as client:
        result = await client.get_prompt("sre_jobs_last_hour", {"location": "India"})
    assert "in India" in result.messages[0].content.text
