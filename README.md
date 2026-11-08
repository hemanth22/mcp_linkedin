# LinkedIn Jobs MCP Server

A [FastMCP](https://gofastmcp.com) server that lets an AI assistant (Claude Code, Claude Desktop, or any MCP client) look up the **latest public LinkedIn job posts**.

It uses LinkedIn's public, no-login "guest" jobs endpoints. No API key or LinkedIn account is needed.

> **Note:** This does not read your personal LinkedIn feed. LinkedIn offers no official API for that. The server only returns publicly listed jobs.

## Tools

| Tool | Purpose |
|------|---------|
| `search_job(keyword)` | Quick search. Returns up to 10 jobs matching the keyword posted in the last week. |
| `search_latest_jobs(keywords, ...)` | Full search, newest first, with filters and paging. |
| `search_jobs_last_hour(job_title, ...)` | Jobs posted in the last hour (`posted_text` like "1 hour ago" or "N minutes ago"). Defaults to "site reliability engineer"; set `exact_one_hour=true` to keep only "1 hour ago". |
| `get_job_details(job_id)` | Full description, seniority, employment type and industry for one job. |
| `search_feed_job_posts(keyword, limit=10)` | Finds public LinkedIn **posts** announcing hiring for the keyword (past month). Free, no key. |

### Prompts

| Prompt | Purpose |
|--------|---------|
| `sre_jobs_last_hour(location="")` | Site Reliability Engineer jobs posted in the last hour. |
| `latest_jobs(job_title, location="", time_posted="day")` | Latest jobs for any title. |
| `job_deep_dive(job_id)` | Summarise one job and its requirements. |

### Feed post search (free, no key, no LinkedIn login)

`search_feed_job_posts` uses the free [`ddgs`](https://pypi.org/project/ddgs/) package (DuckDuckGo search) to look for `site:linkedin.com/posts hiring "<keyword>"` over the past month. It returns each post's title, link and snippet. No API key, LinkedIn account, cookies or browser are used.

Only public posts that DuckDuckGo has indexed appear, so results are not a live feed. DuckDuckGo may rate-limit your IP after many searches; the tool then reports the error and you can retry in a few minutes.

### `search_latest_jobs` parameters

| Parameter | Values | Default |
|-----------|--------|---------|
| `keywords` | Job title or skills, e.g. `"python developer"` | required |
| `location` | City, region or country, e.g. `"India"` | `""` |
| `time_posted` | `day`, `week`, `month` | `day` |
| `job_type` | `full-time`, `part-time`, `contract`, `temporary`, `internship` | any |
| `experience_level` | `internship`, `entry`, `associate`, `mid-senior`, `director`, `executive` | any |
| `work_mode` | `onsite`, `remote`, `hybrid` | any |
| `limit` | 1 to 25 | 25 |
| `start` | Paging offset (0, 25, 50, ...) | 0 |

### Example result

```json
{
  "job_id": "4486331786",
  "title": "Senior Backend Engineer (Python)",
  "company": "MaxIQ",
  "location": "Pune District, Maharashtra, India",
  "posted": "2026-11-04",
  "posted_text": "3 hours ago",
  "url": "https://in.linkedin.com/jobs/view/senior-backend-engineer-python-at-maxiq-4486331786"
}
```

Pass a result's `job_id` to `get_job_details` to read the full description.

## Setup

Requires Python 3.10+.

```bash
pip install -r requirements.txt
```

### Register with Claude Code

```bash
claude mcp add linkedin-jobs -- python C:\Users\hemanth\mcp_linkedin\main.py
```

### Register with Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "linkedin-jobs": {
      "command": "python",
      "args": ["C:\\Users\\hemanth\\mcp_linkedin\\main.py"]
    }
  }
}
```

### Try it without a client

```bash
fastmcp dev inspector main.py
```

This opens the MCP Inspector, where you can call each tool by hand. It needs Node.js installed. On older FastMCP versions the command is `fastmcp dev main.py`.

## Example prompts

- "Find the latest remote Python developer jobs in India posted today."
- "Search LinkedIn for entry-level data analyst internships this week."
- "Show me details for job 4486331786."
- "Search for the latest Site Reliability Engineer jobs posted in the last hour."
- "Find Site Reliability Engineer jobs in India where posted_text is '1 hour ago'." (uses `exact_one_hour=true`)
- "Any remote SRE jobs posted in the last hour? Show details for the first one."
- "Use search_latest_jobs to find the newest 'AI Ops' jobs in india posted within the last . Summarise the top results in a table (title, company, location, posted_text, url)."  

## Limitations

- LinkedIn rate-limits guest endpoints. If you get a rate-limit error, wait a few minutes and retry.
- Results depend on LinkedIn's public page markup, which can change and break parsing.
- Only public listings are returned. Applying, saved jobs and personalised recommendations are not available.
- Scraping may conflict with LinkedIn's Terms of Service. Use it for light, personal job searching.
