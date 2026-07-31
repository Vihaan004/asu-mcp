# Development notes

Everything behind [the README](README.md): where the data comes from, how it
breaks, and how to work on it.

## Running from a checkout

```bash
uv sync
uv run pytest
```

Point a client at your working copy instead of GitHub, so edits take effect on
the next restart with no fetch at all:

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

Tests are fixture-based and never touch the network: a captured class-search
response for CSE 310, Fall 2026 (11 sections mixing full and open, in-person
and online, some with no scheduled meeting time) plus trimmed real markup for
the events and news parsers. Several of them pin behaviour that only showed up
when a model drove the connector as a real client: the surname-fuzz filter, the
query relaxation that must not reach `works on`, and the abbreviation
expansion.

To see what a model actually receives, and to catch a source that has changed
shape, run every tool against live ASU data:

```bash
uv run python samples.py
```

## Shipping an update

Restarting a client re-runs `uvx`, which revalidates the archive against
GitHub. That is normally all it takes.

**But bump `version` in `pyproject.toml` for every change you want to ship.**
uv keys its build cache on package name and version, so a new commit that
reuses the same version number can be served from an existing cached build and
never reach anyone.

`asu` reports its own version in the MCP handshake, so a client can always be
asked what it is actually running.

## Hosting it for claude.ai

claude.ai talks to remote MCP servers over HTTP, so it needs to be running
somewhere reachable. There is no public hosted instance yet. Host it yourself
and it works today:

```bash
docker build -t asu-mcp . && docker run -p 8000:8000 asu-mcp
```

Then point Settings → Connectors → **Add custom connector** at
`https://your-host/mcp`. Custom connectors are available on Free, Pro, Max,
Team and Enterprise plans, with Free limited to one.

Plain Docker on purpose: the same image runs on Railway, Render, Fly, Koyeb or
your own box. `GET /health` is there for platform health checks, and
`ASU_MCP_TRANSPORT=stdio` switches back to the local behaviour.

## Why one connector, not four

Four areas, deliberately not four connectors. Making students install one thing
per campus system would recreate the fragmentation this exists to remove.

## How it works, and how it breaks

ASU's public class search is a React SPA over an undocumented JSON API at
`eadvs-cscc-catalog-api.apps.asu.edu`. This calls that API directly.

**Authentication is a frontend accident.** The SPA builds its header as
`"Bearer " + sessionStorage.getItem("catalog.jwt.token")`. For a visitor who is
not signed in, that returns JavaScript `null`, so the literal string
`Bearer null` goes over the wire, and the backend accepts it as the anonymous
principal. We send the same. Only that exact string works; `Bearer x` gets a
401.

That is the likeliest way this breaks. When it does, the server raises
`AnonymousAuthRejected` saying so, rather than quietly returning nothing.

**The other three sources.** People come from the iSearch directory API
(`search.asu.edu/api/v1/webdir-profiles/faculty-staff`), a de facto public JSON
API. Events are parsed from the rendered calendar listing. The site does expose
Drupal JSON:API, but its event index only holds 2021 to 2023 content and its
date filtering is broken (a `> 2099` filter still returns rows), so it is an
archive, not the calendar. News reads `news.asu.edu`'s own search rather than a
paid web-search API, so there is no API key to supply and no per-user cost.

Two other things worth knowing if you build on this:

- **`searchType=open` is a no-op.** The API accepts it and returns full
  sections anyway. `open_only` filters client-side on the registrar's
  `ENRLSTAT` flag. Anything that trusts the API parameter will report full
  classes as open.
- **Term codes are opaque.** Fall 2026 is `2267`. Every tool accepts
  `"Fall 2026"` and defaults to the current term. Nothing should hardcode one.

## Known rough edges

- **The sources disagree about abbreviations, in opposite directions.** The
  catalog indexes official course titles, which are spelled out: in Fall 2026
  `artificial intelligence` matches 30 sections and `AI` matches none. The
  events calendar indexes what an organiser typed, which is where the
  abbreviation lives: `AI` matches nine events and `artificial intelligence`
  matches zero. Whichever form a student thinks in, one of the two would return
  nothing. Every search now tries both and says which one matched.
- **The directory fuzzy-matches surnames.** Searching `robotics` returns people
  named Root, Rootes and Root before anyone who does robotics. Results are
  over-fetched, re-ranked, and dropped entirely when no query word appears
  anywhere in the row, because sorting cannot fix a result set that is all
  noise. A direct name lookup still wins outright.
- **Conversational phrasing is stripped, not rejected.** The directory
  AND-matches every token, so "someone who works on quantum computing at ASU"
  used to relax to the literal words `works on` and return people surnamed
  Works. Filler is removed server-side. A tool description asking the caller to
  phrase queries carefully does not survive contact with a real student.
- **Event keyword search is client-side, over titles only.** The calendar
  listing ignores a `search` parameter and returns the same 24 cards whatever
  you pass, so filtering happens locally across roughly the next two months.
  Results say how many events were scanned and over what dates: "no engineering
  events in the next 141" is a real answer, and a model needs to be able to
  tell it apart from a failure.

Two things this deliberately does **not** do:

- **Search event descriptions.** It looks like the obvious fix for titles-only
  matching, and the numbers say otherwise: only 40 of 141 upcoming events carry
  a description at all, crawling every detail page costs about 30s, and for the
  query that motivated it, `artificial intelligence`, it surfaced zero extra
  events. Matching on body text also matched `ai` inside *available* and
  *training*, returning all 141. Expanding abbreviations fixed the real case
  for one extra request.
- **Answer topic questions the directory cannot.** `quantum computing` returns
  nobody, and the four rows `quantum` returns are all fuzzy surname matches.
  Relaxing to `computing` produces a plausible, confidently wrong answer (a
  security architecture director), so it stops and says the directory has
  nobody indexed under those words.

## Dependencies

**Pinned below `mcp` 2.0.** 2.0 removed `mcp.server.fastmcp`, since FastMCP is
now `mcp.server.mcpserver`, so an unpinned install resolves to 2.x and the
server raises `ModuleNotFoundError` on import before it can serve anything. A
lockfile hides this from anyone developing on it: the first person to feel it
is a new user installing fresh, which is the worst possible place to find out.
Lift the pin with a real 2.x migration.

## Caching

Responses are cached in memory: term and subject lists for six hours, searches
for ten to thirty minutes. Long enough to be a good neighbour to ASU's servers,
short enough that seat counts stay honest.
