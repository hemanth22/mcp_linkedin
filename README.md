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

Requires Python 3.10+. There are two ways to run the server:

- **Straight from GitHub with [uv](https://docs.astral.sh/uv/)** (recommended). Nothing to clone or install by hand:
  ```bash
  uvx --from git+https://github.com/hemanth22/mcp_linkedin linkedin-jobs
  ```
- **From a clone:**
  ```bash
  git clone https://github.com/hemanth22/mcp_linkedin.git
  cd mcp_linkedin
  pip install -r requirements.txt
  python main.py
  ```

The client configs below use the `uvx` form. To use a clone instead, replace the command with `python` and the args with the full path to `main.py`.

### Transports

| Mode | Command | Used by |
|------|---------|---------|
| stdio (default) | `linkedin-jobs` | Claude Code, Claude Desktop, VS Code, Antigravity |
| Streamable HTTP | `linkedin-jobs --transport http --port 8000` | ChatGPT, claude.ai custom connectors |

In HTTP mode the endpoint is `http://<host>:<port>/mcp`. The options can also be set with the `MCP_TRANSPORT`, `HOST` and `PORT` environment variables.

### Claude Code

```bash
claude mcp add linkedin-jobs -- uvx --from git+https://github.com/hemanth22/mcp_linkedin linkedin-jobs
```

Inside a clone of this repo, Claude Code also picks up the bundled `.mcp.json` automatically.

### Claude Desktop

Go to Settings → Developer → Edit Config and add:

```json
{
  "mcpServers": {
    "linkedin-jobs": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/hemanth22/mcp_linkedin", "linkedin-jobs"]
    }
  }
}
```

Restart Claude Desktop afterwards.

### VS Code (GitHub Copilot agent mode)

Add to `.vscode/mcp.json`, or run **MCP: Open User Configuration** to make it available in all workspaces:

```json
{
  "servers": {
    "linkedin-jobs": {
      "type": "stdio",
      "command": "uvx",
      "args": ["--from", "git+https://github.com/hemanth22/mcp_linkedin", "linkedin-jobs"]
    }
  }
}
```

Click **Start** above the entry, then use Copilot Chat in **Agent** mode.

### Antigravity

In the Agent panel, open **⋯ → MCP Servers → Manage MCP Servers → View raw config** (`~/.gemini/antigravity/mcp_config.json`) and add:

```json
{
  "mcpServers": {
    "linkedin-jobs": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/hemanth22/mcp_linkedin", "linkedin-jobs"]
    }
  }
}
```

Save the file, then click **Refresh**.

### ChatGPT and claude.ai (remote connectors)

These clients can only reach servers on a public HTTPS URL.

1. Run the server in HTTP mode somewhere public. Either deploy this repo to a host such as Render, Railway, Fly.io or Cloud Run with the start command `python main.py --transport http` (they set `PORT` for you), or test locally with `python main.py --transport http` plus a tunnel like `ngrok http 8000`.
2. **ChatGPT:** go to Settings → Apps & Connectors → Advanced settings, turn on **Developer mode**, then **Create** a connector with the URL `https://<your-host>/mcp` and no authentication.
3. **claude.ai:** go to Settings → Connectors → **Add custom connector** and paste the same URL.

> **Warning:** the HTTP server has no authentication. Anyone with the URL can call it and use up your LinkedIn and DuckDuckGo rate limits. Keep the URL private, or take it down when you're done.

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
