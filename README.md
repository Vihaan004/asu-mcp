# ASU MCP

Ask Claude about ASU in plain language — classes, people, events and news — and
get answers from live university data instead of a search engine's guess.

> "Which machine learning classes still have seats and don't meet before 10am?"
> "Who at ASU works on robotics, and how do I reach them?"
> "Any research workshops on campus next week?"
> "What has ASU published about semiconductors lately?"
> "What does ASU actually do in sustainability?"

No ASURITE, no login, nothing behind a wall — only data ASU already publishes
openly.

**Unofficial.** Built by a former ASU student. Not operated by, affiliated with,
or endorsed by Arizona State University.

## Use it

### Claude Desktop or Claude Code

You need [uv](https://docs.astral.sh/uv/getting-started/installation/). You do
**not** need git — the install below fetches a source archive over plain HTTPS,
because most students do not have git installed and a `git+` URL fails with a
message that does not mention it.

**Claude Code**

```bash
claude mcp add asu -- uvx --from https://github.com/Vihaan004/asu-mcp/archive/refs/heads/main.tar.gz asu-mcp
```

**Claude Desktop** — add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "asu": {
      "command": "uvx",
      "args": [
        "--from",
        "https://github.com/Vihaan004/asu-mcp/archive/refs/heads/main.tar.gz",
        "asu-mcp"
      ]
    }
  }
}
```

Restart the client afterwards; the server is a long-lived process started when
the app launches.

**Working on it?** Point the client at your checkout instead, so edits take
effect on the next restart with no fetch at all:

```json
{
  "mcpServers": {
    "asu": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/asu-mcp", "asu-mcp"]
    }
  }
}
```

### claude.ai as a custom connector

claude.ai talks to remote MCP servers over HTTP, so this has to be running
somewhere reachable first. There is **no public hosted instance yet** — host it
yourself and it works today:

```bash
docker build -t asu-mcp . && docker run -p 8000:8000 asu-mcp
```

Then point Settings → Connectors → **Add custom connector** at
`https://your-host/mcp`. Custom connectors are available on Free, Pro, Max,
Team and Enterprise plans (Free is limited to one).

Plain Docker on purpose: the same image runs on Railway, Render, Fly, Koyeb or
your own box. `GET /health` is there for platform health checks, and
`ASU_MCP_TRANSPORT=stdio` switches back to the local behaviour.

## Tools

Nine tools on one connector. Four areas, deliberately not four connectors —
making students install one thing per campus system would recreate the
fragmentation this exists to remove.

**Everything at once**

| Tool | |
|---|---|
| `search_asu` | One topic across all four sources in parallel: courses, researchers, upcoming events and news. For "what does ASU do in robotics" — one call instead of four. |

**Classes** — ASU's live class schedule

| Tool | |
|---|---|
| `search_classes` | Search by subject, course number, free-text query, instructor, campus, days, times, level, units, honors. Optionally only sections with open seats. |
| `get_class` | One section in full: seats, room with campus map link, enrollment and drop/withdraw deadlines, consent and reserved-seat restrictions. |
| `list_terms` | The current term and a few either side; `include_all` for all 71. |
| `list_subjects` | The 343 subject codes for a term, so "computer science" resolves to `CSE`. |

**People** — the public faculty and staff directory

| Tool | |
|---|---|
| `search_people` | Find who works on a topic, or look up one person. Returns titles, departments, published contact details, expertise and research interests. |

**Events** — the university-wide calendar

| Tool | |
|---|---|
| `search_events` | Upcoming talks, workshops, info sessions and exhibitions, filtered by keyword, campus or date. |
| `get_event` | Full description and registration link for one event. |

**News** — ASU's own newsroom

| Tool | |
|---|---|
| `search_news` | Research announcements and university stories, by topic or latest. |

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

**The other three sources.** People come from the iSearch directory API
(`search.asu.edu/api/v1/webdir-profiles/faculty-staff`), a de facto public JSON
API. Events are parsed from the rendered calendar listing — the site does expose
Drupal JSON:API, but its event index only holds 2021–2023 content and its date
filtering is broken (a `> 2099` filter still returns rows), so it is an archive,
not the calendar. News reads `news.asu.edu`'s own search rather than a paid
web-search API, so there is no API key to supply and no per-user cost.

Two other things worth knowing if you build on this:

- **`searchType=open` is a no-op.** The API accepts it and returns full sections
  anyway. `open_only` filters client-side on the registrar's `ENRLSTAT` flag.
  Anything that trusts the API parameter will report full classes as open.
- **Term codes are opaque.** Fall 2026 is `2267`. Every tool accepts
  `"Fall 2026"` and defaults to the current term. Nothing should hardcode one.

- **The sources disagree about abbreviations, in opposite directions.** The
  catalog indexes official course titles, which are spelled out: in Fall 2026
  `artificial intelligence` matches 30 sections and `AI` matches none. The
  events calendar indexes what an organiser typed, which is where the
  abbreviation lives: `AI` matches nine events and `artificial intelligence`
  matches zero. Whichever form a student thinks in, one of the two would return
  nothing. Every search now tries both and says which one matched.
- **The directory fuzzy-matches surnames.** Searching `robotics` returns people
  named Root, Rootes and Root before anyone who does robotics. Results are
  over-fetched, re-ranked, and — new — dropped entirely when no query word
  appears anywhere in the row, because sorting cannot fix a result set that is
  all noise. A direct name lookup still wins outright.
- **Conversational phrasing is stripped, not rejected.** The directory
  AND-matches every token, so "someone who works on quantum computing at ASU"
  used to relax to the literal words `works on` and return people surnamed
  Works. Filler is removed server-side; a tool description asking the caller to
  phrase queries carefully does not survive contact with a real student.
- **Event keyword search is client-side, over titles only.** The calendar
  listing ignores a `search` parameter — it returns the same 24 cards whatever
  you pass — so filtering happens locally across roughly the next two months.
  Results say how many events were scanned and over what dates: "no engineering
  events in the next 141" is a real answer, and a model needs to be able to
  tell it apart from a failure.

Two things this deliberately does **not** do:

- **Search event descriptions.** It looks like the obvious fix for titles-only
  matching, and the numbers say otherwise: only 40 of 141 upcoming events carry
  a description at all, crawling every detail page costs ~30s, and for the
  query that motivated it — `artificial intelligence` — it surfaced zero extra
  events. Matching on body text also matched `ai` inside *available* and
  *training*, returning all 141. Expanding abbreviations fixed the real case
  for one extra request.
- **Answer topic questions the directory cannot.** `quantum computing` returns
  nobody, and the four rows `quantum` returns are all fuzzy surname matches.
  Relaxing to `computing` produces a plausible, confidently wrong answer — a
  security architecture director — so it stops and says the directory has
  nobody indexed under those words.

**Dependencies are pinned below `mcp` 2.0.** 2.0 removed
`mcp.server.fastmcp` — FastMCP is now `mcp.server.mcpserver` — so an unpinned
install resolves to 2.x and the server raises `ModuleNotFoundError` on import
before it can serve anything. A lockfile hides this from anyone developing on
it: the first person to feel it is a new user installing fresh, which is the
worst possible place to find out. Lift the pin with a real 2.x migration.

Responses are cached in memory — term and subject lists for six hours, searches
for ten to thirty minutes. Long enough to be a good neighbour to ASU's servers,
short enough that seat counts stay honest.

Seat counts are live but are not reservations; a class can fill between the
search and enrolling. Enrolling still happens in My ASU.

## Development

```bash
uv sync
uv run pytest
```

Tests are fixture-based and never touch the network — a captured class-search
response for CSE 310, Fall 2026 (11 sections mixing full and open, in-person and
online, some with no scheduled meeting time) plus trimmed real markup for the
events and news parsers. Several pin behaviour that only showed up when a model
drove the connector as a real client: the surname-fuzz filter, the query
relaxation that must not reach `works on`, and the abbreviation expansion.

To see what a model actually receives, and to catch a source that has changed
shape, run every tool against live ASU data:

```bash
uv run python samples.py
```

## License

MIT
