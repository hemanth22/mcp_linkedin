"""FastMCP server that reads the latest public LinkedIn job posts.

Uses LinkedIn's public (no-login) guest jobs endpoints. It does not read your
personal feed. Guest endpoints are rate limited; heavy use may return 429.
"""

import asyncio
from typing import Literal, Optional
from urllib.parse import urlsplit, urlunsplit

import httpx
from bs4 import BeautifulSoup
from ddgs import DDGS
from fastmcp import FastMCP

mcp = FastMCP("linkedin-jobs")

BASE = "https://www.linkedin.com/jobs-guest/jobs/api"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

TIME_FILTER = {"hour": "r3600", "day": "r86400", "week": "r604800", "month": "r2592000"}
JOB_TYPE = {
    "full-time": "F", "part-time": "P", "contract": "C",
    "temporary": "T", "internship": "I",
}
EXPERIENCE = {
    "internship": "1", "entry": "2", "associate": "3",
    "mid-senior": "4", "director": "5", "executive": "6",
}
WORK_MODE = {"onsite": "1", "remote": "2", "hybrid": "3"}


def _clean_url(url: str) -> str:
    p = urlsplit(url)
    return urlunsplit((p.scheme, p.netloc, p.path, "", ""))


def _text(node) -> str:
    return node.get_text(" ", strip=True) if node else ""


async def _get(path: str, params: dict | None = None) -> str:
    async with httpx.AsyncClient(headers=HEADERS, timeout=20, follow_redirects=True) as client:
        r = await client.get(f"{BASE}/{path}", params=params)
    if r.status_code in (429, 999):
        raise RuntimeError("LinkedIn rate-limited this request. Wait a few minutes and retry.")
    r.raise_for_status()
    return r.text


async def _search(
    keywords: str,
    location: str = "",
    time_posted: str = "day",
    job_type: Optional[str] = None,
    experience_level: Optional[str] = None,
    work_mode: Optional[str] = None,
    limit: int = 25,
    start: int = 0,
) -> list[dict]:
    params = {
        "keywords": keywords,
        "location": location,
        "f_TPR": TIME_FILTER[time_posted],
        "sortBy": "DD",
        "start": max(start, 0),
    }
    if job_type:
        params["f_JT"] = JOB_TYPE[job_type]
    if experience_level:
        params["f_E"] = EXPERIENCE[experience_level]
    if work_mode:
        params["f_WT"] = WORK_MODE[work_mode]

    html = await _get("seeMoreJobPostings/search", params)
    soup = BeautifulSoup(html, "html.parser")

    jobs = []
    for card in soup.select("li"):
        link = card.select_one("a.base-card__full-link")
        urn = card.select_one("[data-entity-urn]")
        if not link:
            continue
        job_id = urn["data-entity-urn"].rsplit(":", 1)[-1] if urn else None
        time_tag = card.select_one("time")
        jobs.append({
            "job_id": job_id,
            "title": _text(card.select_one(".base-search-card__title")),
            "company": _text(card.select_one(".base-search-card__subtitle")),
            "location": _text(card.select_one(".job-search-card__location")),
            "posted": time_tag.get("datetime") if time_tag else None,
            "posted_text": _text(time_tag),
            "url": _clean_url(link["href"]),
        })
        if len(jobs) >= min(max(limit, 1), 25):
            break
    return jobs


@mcp.tool()
async def search_job(keyword: str) -> list[dict]:
    """Search the latest public LinkedIn jobs matching a keyword (e.g. "python developer")."""
    return await _search(keyword, time_posted="week", limit=10)


@mcp.tool
async def search_latest_jobs(
    keywords: str,
    location: str = "",
    time_posted: Literal["day", "week", "month"] = "day",
    job_type: Optional[Literal["full-time", "part-time", "contract", "temporary", "internship"]] = None,
    experience_level: Optional[Literal["internship", "entry", "associate", "mid-senior", "director", "executive"]] = None,
    work_mode: Optional[Literal["onsite", "remote", "hybrid"]] = None,
    limit: int = 25,
    start: int = 0,
) -> list[dict]:
    """Search the most recently posted public LinkedIn jobs (newest first).

    Args:
        keywords: Job title or skills, e.g. "python developer".
        location: City/region/country, e.g. "India" or "Bengaluru".
        time_posted: Only jobs posted within the last day/week/month.
        job_type: Optional employment type filter.
        experience_level: Optional seniority filter.
        work_mode: Optional onsite/remote/hybrid filter.
        limit: Max results to return (1-25).
        start: Offset for paging (0, 25, 50, ...).
    """
    return await _search(keywords, location, time_posted, job_type,
                         experience_level, work_mode, limit, start)


@mcp.tool
async def search_jobs_last_hour(
    job_title: str = "site reliability engineer",
    location: str = "",
    work_mode: Optional[Literal["onsite", "remote", "hybrid"]] = None,
    exact_one_hour: bool = False,
    limit: int = 25,
) -> list[dict]:
    """Search jobs posted in the last hour for a job title (newest first).

    Defaults to "site reliability engineer". LinkedIn's last-hour filter returns
    posts whose posted_text is "N minutes ago" or "1 hour ago".

    Args:
        job_title: Job title, e.g. "site reliability engineer".
        location: City/region/country, e.g. "India".
        work_mode: Optional onsite/remote/hybrid filter.
        exact_one_hour: If true, keep only jobs whose posted_text is "1 hour ago".
        limit: Max results to return (1-25).
    """
    jobs = await _search(job_title, location, "hour", work_mode=work_mode, limit=25)
    if exact_one_hour:
        jobs = [j for j in jobs if j["posted_text"].lower().startswith("1 hour")]
    return jobs[: min(max(limit, 1), 25)]


@mcp.tool
async def get_job_details(job_id: str) -> dict:
    """Get full details (description, seniority, type, industry) for a job id
    returned by search_latest_jobs."""
    html = await _get(f"jobPosting/{job_id}")
    soup = BeautifulSoup(html, "html.parser")

    criteria = {}
    for item in soup.select("li.description__job-criteria-item"):
        key = _text(item.select_one("h3"))
        val = _text(item.select_one("span"))
        if key:
            criteria[key] = val

    desc = soup.select_one(".show-more-less-html__markup")
    return {
        "job_id": job_id,
        "title": _text(soup.select_one("h2.top-card-layout__title")),
        "company": _text(soup.select_one("a.topcard__org-name-link, .topcard__flavor")),
        "location": _text(soup.select_one(".topcard__flavor--bullet")),
        "criteria": criteria,
        "description": desc.get_text("\n", strip=True) if desc else "",
        "url": f"https://www.linkedin.com/jobs/view/{job_id}",
    }


@mcp.tool()
async def search_feed_job_posts(keyword: str, limit: int = 10) -> list[dict]:
    """Find public LinkedIn posts announcing hiring for a keyword (free, no key, no login).

    Searches DuckDuckGo (via the ddgs package) for linkedin.com/posts from the
    past month. Only public, indexed posts appear.

    Args:
        keyword: Skill or role, e.g. "python developer".
        limit: Max posts to return (1-20).
    """
    limit = min(max(limit, 1), 20)
    query = f'site:linkedin.com/posts hiring "{keyword}"'

    def run() -> list[dict]:
        return DDGS(timeout=20).text(
            query, max_results=limit * 2, timelimit="m", backend="duckduckgo"
        )

    try:
        results = await asyncio.to_thread(run)
    except Exception as e:  # ddgs raises on rate limits, timeouts and empty results
        msg = str(e)
        if "No results" in msg:
            return []
        raise RuntimeError(
            f"DuckDuckGo search failed or is rate limiting this IP ({msg[:120]}). "
            "Retry in a few minutes."
        )

    posts = []
    for item in results:
        url = item.get("href", "")
        if "linkedin.com/posts" not in url:
            continue
        posts.append({
            "title": item.get("title", ""),
            "url": _clean_url(url),
            "snippet": item.get("body", ""),
        })
        if len(posts) >= limit:
            break
    return posts


@mcp.prompt()
def sre_jobs_last_hour(location: str = "") -> str:
    """Find Site Reliability Engineer jobs posted in the last hour."""
    where = f" in {location}" if location else ""
    return (
        f"Use the search_jobs_last_hour tool to find Site Reliability Engineer jobs{where} "
        "posted in the last hour (posted_text such as '1 hour ago'). "
        "List each job as: title, company, location, posted_text and url, newest first. "
        "If nothing is returned, say so and suggest searching the last day with search_latest_jobs."
    )


@mcp.prompt()
def latest_jobs(job_title: str, location: str = "", time_posted: str = "day") -> str:
    """Find the latest LinkedIn jobs for any job title."""
    where = f" in {location}" if location else ""
    return (
        f"Use search_latest_jobs to find the newest '{job_title}' jobs{where} "
        f"posted within the last {time_posted}. "
        "Summarise the top results in a table (title, company, location, posted_text, url)."
    )


@mcp.prompt()
def job_deep_dive(job_id: str) -> str:
    """Summarise one job posting and judge fit."""
    return (
        f"Call get_job_details for job id {job_id}. Summarise the role, required skills, "
        "seniority and employment type, then list the top 5 requirements and any red flags."
    )


if __name__ == "__main__":
    mcp.run()
