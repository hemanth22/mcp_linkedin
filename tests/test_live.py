"""Live smoke test against real LinkedIn. Skipped unless RUN_LIVE_TESTS=1.

LinkedIn often rate-limits cloud IPs, so a rate-limit response is a skip,
not a failure.
"""

import os

import pytest
from fastmcp import Client

import main

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_TESTS") != "1", reason="set RUN_LIVE_TESTS=1 to hit LinkedIn"
)


async def test_live_search_job():
    async with Client(main.mcp) as client:
        result = await client.call_tool("search_job", {"keyword": "python developer"}, raise_on_error=False)
    if result.is_error:
        text = result.content[0].text
        if "rate-limited" in text or "429" in text or "999" in text:
            pytest.skip(f"LinkedIn blocked this runner: {text[:120]}")
        pytest.fail(text)
    jobs = result.data
    assert isinstance(jobs, list)
    if jobs:
        assert {"job_id", "title", "company", "url"} <= jobs[0].keys()
