# ASU MCP

Ask Claude about ASU in plain language and get answers from live university
data instead of a search engine's guess.

> "Which machine learning classes still have seats and don't meet before 10am?"
> "Who at ASU works on robotics, and how do I reach them?"
> "Any research workshops on campus next week?"
> "What has ASU published about semiconductors lately?"
> "What does ASU actually do in sustainability?"

No ASURITE, no login, nothing behind a wall. Only data ASU already publishes
openly.

**Unofficial.** Built by a former ASU student, not affiliated with or endorsed
by Arizona State University. Please read the [disclaimer](#disclaimer) before
relying on anything it tells you.

## Setup

You need [uv](https://docs.astral.sh/uv/getting-started/installation/), a small
tool that runs the connector for you. That is the only thing to install.

### Claude Desktop

Open **Settings → Developer → Edit Config**, then add the `asu` block to
`claude_desktop_config.json`:

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

Save the file, then fully quit Claude Desktop and open it again. Closing the
window is not enough on Windows, since the app keeps running in the system
tray. Quit it from the tray icon.

### Claude Code

```bash
claude mcp add asu -- uvx --from https://github.com/Vihaan004/asu-mcp/archive/refs/heads/main.tar.gz asu-mcp
```

### claude.ai in the browser

Not available yet. The web app can only talk to a connector that is hosted
online, and there is no public instance running. You can host your own, see
[DEV.md](DEV.md).

## Updating

Quit Claude Desktop and open it again. It picks up the newest version on its
own, so there is nothing to reinstall. To check which version is running, just
ask Claude what version of the ASU connector it is connected to.

## Features

Nine tools on one connector, covering four parts of ASU. When a search comes
back empty, it says so instead of guessing.

**Everything at once**

| Tool | |
|---|---|
| `search_asu` | One topic across all four sources at once: courses, researchers, upcoming events and news. Good for "what does ASU do in robotics". |

**Classes**, from ASU's live class schedule

| Tool | |
|---|---|
| `search_classes` | Search by subject, course number, topic, instructor, campus, days, times, level, units or honors. Can show only sections with open seats. |
| `get_class` | One section in full: seats, room with a campus map link, enrollment and drop deadlines, and any restrictions. |
| `list_terms` | The current term and a few either side. |
| `list_subjects` | Every subject code for a term, so "computer science" turns into `CSE`. |

**People**, from the public faculty and staff directory

| Tool | |
|---|---|
| `search_people` | Find who works on a topic, or look up one person. Returns titles, departments, published contact details and research interests. |

**Events**, from the university calendar

| Tool | |
|---|---|
| `search_events` | Upcoming talks, workshops, info sessions and exhibitions, filtered by keyword, campus or date. |
| `get_event` | Full description and registration link for one event. |

**News**, from ASU's newsroom

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

## Disclaimer

Provided as is, which is lawyer for "works on my machine." No warranty:
express, implied, or vibed. This tool is not responsible for enrollment chaos. 
Use at your own risk, but do have fun :)

This is an independent, unofficial project. It is not operated by, affiliated
with, endorsed by, or approved by Arizona State University. ASU's name and
marks belong to ASU. Nothing here speaks for the university.

**Treat everything it returns as a starting point, not a source of truth.** It
reads ASU's public pages and passes on what it finds, so anything that is
missing, stale or wrong at the source will be missing, stale or wrong here too.
It can also break without warning if ASU changes how those pages work.

Seat counts deserve their own warning. They are live at the moment of the
search, but they are not reservations and they change constantly. A class shown
as open can be full seconds later. Enrollment happens in My ASU, and that is
the only place a seat becomes real.

Before you act on anything from this connector, whether that is registering,
counting on a deadline, showing up to an event or emailing someone, confirm it
against the official source: My ASU, ASU's class search, the department, or the
event page itself.

## DIY

[DEV.md](DEV.md) covers how it works, where the data comes from, the known
rough edges, running the tests and hosting your own copy.

## License

MIT
