# ASU MCP

Ask Claude about ASU classes in plain language and get answers from the live
schedule — sections, meeting times, instructors, rooms, and real seat counts.

> "Is CSE 310 open for fall?"
> "Which machine learning classes still have seats and don't meet before 10am?"
> "What is Yezhou Yang teaching this spring?"

No ASURITE, no login, nothing behind a wall. This reads the same public catalog
data as [catalog.apps.asu.edu](https://catalog.apps.asu.edu).

**Unofficial.** Built by a former ASU student. Not operated by, affiliated with,
or endorsed by Arizona State University.

## Use it

### claude.ai (no install)

Settings → Connectors → **Add custom connector**, and paste:

```
<DEPLOYED_URL>/mcp
```

Custom connectors work on Free, Pro, Max, Team and Enterprise plans (Free is
limited to one). Nothing to download, nothing to configure.

### Run it yourself

If the hosted instance is down, retired, or you would simply rather not depend
on someone else's server, everything runs locally with no code changes.

**Claude Code**

```bash
claude mcp add asu -- uvx --from git+https://github.com/Vihaan004/asu-mcp asu-mcp
```

**Claude Desktop** — add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "asu": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/Vihaan004/asu-mcp", "asu-mcp"]
    }
  }
}
```

Local runs default to stdio. The only difference from the hosted instance is
transport — same tools, same data.

### Host your own

```bash
docker build -t asu-mcp . && docker run -p 8000:8000 asu-mcp
```

Plain Docker on purpose: the same image runs on Railway, Render, Fly, Koyeb or
your own box. Set `ASU_MCP_TRANSPORT=stdio` to get the local behaviour instead.
`GET /health` is there for platform health checks.

## Tools

| Tool | |
|---|---|
| `search_classes` | Search by subject, course number, keywords, instructor, campus, days, times, level, units, honors. Optionally only sections with open seats. |
| `get_class` | One section in full: seats, room with campus map link, enrollment and drop/withdraw deadlines, consent and reserved-seat restrictions. |
| `list_terms` | Available terms and their codes. |
| `list_subjects` | The 343 subject codes for a term, so "computer science" resolves to `CSE`. |

Coming: people (faculty and researchers), events, and news — as more tools on
this same connector, not as separate ones to install.

## Try it without a client

```bash
uv run python -m asu_mcp search CSE 310 --open
```

```
5 section(s) with open seats in Fall 2026 (2267)

CSE 310 — Data Structures and Algorithms (3 credits)
  #66445  Lecture 1011  M W 4:30 PM-5:45 PM  Tempe · PSH153  Nakul Gopalan  81/150 OPEN
  #75092  Lecture 2001  no set meeting time  ASU Online  Janaka Balasooriya  118/150 OPEN
  #70381  Recitation 1012  M 1:25 PM-2:15 PM  Tempe · COOR199  Nakul Gopalan  25/75 OPEN
```

Also `terms`, `subjects`, `class 66445`.

## How it works, and how it breaks

ASU's public class search is a React SPA over an undocumented JSON API at
`eadvs-cscc-catalog-api.apps.asu.edu`. This calls that API directly.

**Authentication is a frontend accident.** The SPA builds its header as
`"Bearer " + sessionStorage.getItem("catalog.jwt.token")`. For a visitor who is
not signed in, that returns JavaScript `null`, so the literal string
`Bearer null` goes over the wire — and the backend accepts it as the anonymous
principal. We send the same. Only that exact string works; `Bearer x` gets a
401.

That is the likeliest way this breaks. When it does, the server raises
`AnonymousAuthRejected` saying so, rather than quietly returning nothing.

Two other things worth knowing if you build on this:

- **`searchType=open` is a no-op.** The API accepts it and returns full sections
  anyway. `open_only` filters client-side on the registrar's `ENRLSTAT` flag.
  Anything that trusts the API parameter will report full classes as open.
- **Term codes are opaque.** Fall 2026 is `2267`. Every tool accepts
  `"Fall 2026"` and defaults to the current term. Nothing should hardcode one.

Responses are cached in memory — term and subject lists for six hours, class
searches for ten minutes. Long enough to be a good neighbour to ASU's servers,
short enough that seat counts stay honest.

Seat counts are live but are not reservations; a class can fill between the
search and enrolling. Enrolling still happens in My ASU.

## Development

```bash
uv sync
uv run pytest
```

Tests run against a captured response for CSE 310, Fall 2026 — 11 sections
mixing full and open, in-person and online, some with no scheduled meeting
time — so they don't depend on the network or on what's offered this week.

## License

MIT
