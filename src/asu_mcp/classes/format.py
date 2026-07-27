"""Turn ASU's raw class records into something a model can actually read.

A single section comes back with ~110 fields, most of them internal PeopleSoft
plumbing (SUBJECTFORSORTING, KEYWORDSEARCHSTRNOINSTRUCTOR, CRSEATTEFFDT...).
Handing that to a model burns context and buries the answer. We keep the ~20
fields a student would care about and render them densely.
"""

from __future__ import annotations

from typing import Any

# Session codes students actually see on the schedule.
SESSIONS = {
    "C": "full semester",
    "A": "first half",
    "B": "second half",
    "DYN": "dynamic dates",
}

INSTRUCTION_MODES = {
    "P": "in person",
    "O": "online",
    "H": "hybrid",
    "ISESSION": "iCourse",
}

DAY_ORDER = ["M", "T", "W", "Th", "F", "S", "Su"]


def _clean_date(value: Any) -> str:
    """'2026-08-20 00:00:00.0' -> '2026-08-20'."""
    text = str(value or "").strip()
    return text.split(" ")[0] if text else ""


def _int(value: Any) -> int | None:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def normalize(record: dict[str, Any]) -> dict[str, Any]:
    """Flatten one raw search hit into the fields worth showing."""
    clas = record.get("CLAS") or {}

    seat_info = record.get("seatInfo") or {}
    enrolled = _int(seat_info.get("ENRL_TOT"))
    capacity = _int(seat_info.get("ENRL_CAP"))
    if enrolled is None:
        enrolled = _int(clas.get("ENRLTOT"))
    if capacity is None:
        capacity = _int(clas.get("ENRLCAP"))

    seats_open = None
    if enrolled is not None and capacity is not None:
        seats_open = max(capacity - enrolled, 0)

    # ENRLSTAT is the registrar's own flag; seat math is the fallback.
    status = str(clas.get("ENRLSTAT") or "").strip().upper()
    if status in {"O", "C"}:
        is_open = status == "O"
    else:
        is_open = bool(seats_open)

    days = record.get("DAYLIST") or clas.get("DAYLIST") or ""
    if isinstance(days, list):
        days = " ".join(str(d).strip() for d in days if str(d).strip())
    days = " ".join(str(days).split())

    buildings = record.get("LOCATIONBUILDING") or []
    room = ""
    map_url = ""
    if isinstance(buildings, list) and buildings and isinstance(buildings[0], dict):
        room = str(buildings[0].get("NAME") or "").strip()
        map_url = str(buildings[0].get("URL") or "").strip()
    if not room:
        room = str(clas.get("DESCR1") or "").strip()

    campus = str(clas.get("CAMPUS") or "").strip()
    location = str(clas.get("LOCATION") or "").strip()
    is_online = location.upper() == "ASUONLINE" or campus.upper() == "ASUONLINE"

    units_min = str(clas.get("UNITSMINIMUM") or "").strip()
    units_max = str(clas.get("UNITSMAXIMUM") or "").strip()
    units = units_min if units_min == units_max else f"{units_min}-{units_max}"

    instructors = clas.get("INSTRUCTORSLIST") or []
    if not isinstance(instructors, list):
        instructors = [str(instructors)]
    instructors = [str(i).strip() for i in instructors if str(i).strip()]

    session_code = str(clas.get("SESSIONCODE") or "").strip().upper()
    mode_code = str(clas.get("INSTRUCTIONMODE") or "").strip().upper()

    offered_by = record.get("OFFEREDBY") or {}
    gs = " ".join(
        x for x in [str(record.get("GSGOLD") or "").strip(), str(record.get("GSMAROON") or "").strip()] if x
    )

    return {
        "class_number": str(clas.get("CLASSNBR") or "").strip(),
        "course": str(record.get("SUBJECTNUMBER") or "").strip()
        or f"{clas.get('SUBJECT', '')} {clas.get('CATALOGNBR', '')}".strip(),
        "subject": str(clas.get("SUBJECT") or "").strip(),
        "catalog_number": str(clas.get("CATALOGNBR") or "").strip(),
        "title": str(clas.get("COURSETITLELONG") or clas.get("TITLE") or "").strip(),
        "section": str(clas.get("CLASSSECTION") or "").strip(),
        "component": str(clas.get("DESCR2") or clas.get("COMPONENTPRIMARY") or "").strip(),
        "units": units,
        "instructors": instructors,
        "days": days,
        "start_time": str(clas.get("STARTTIME") or "").strip(),
        "end_time": str(clas.get("ENDTIME") or "").strip(),
        "campus": "ASU Online" if is_online else campus.title(),
        "room": "" if is_online else room,
        "map_url": "" if is_online else map_url,
        "enrolled": enrolled,
        "capacity": capacity,
        "seats_open": seats_open,
        "is_open": is_open,
        "waitlist": _int(clas.get("WAITTOT")),
        "waitlist_capacity": _int(clas.get("WAITCAP")),
        "session": session_code,
        "session_label": SESSIONS.get(session_code, ""),
        "instruction_mode": INSTRUCTION_MODES.get(mode_code, mode_code.lower()),
        "start_date": _clean_date(clas.get("STARTDATE")),
        "end_date": _clean_date(clas.get("ENDDATE")),
        "enroll_deadline": _clean_date(clas.get("ENROLLDEADLINE")),
        "drop_deadline": _clean_date(clas.get("DROPRETAINRECORD")),
        "withdraw_deadline": _clean_date(clas.get("DROPWITHPENALTY")),
        "consent_required": str(clas.get("CONSENT") or "N").strip().upper() != "N",
        "career": str(clas.get("ACADCAREER") or "").strip(),
        "offered_by": str(offered_by.get("DEPARTMENT") or "").strip()
        if isinstance(offered_by, dict)
        else "",
        "general_studies": gs,
        "has_syllabus": bool(record.get("HASSYLLABUS")),
        "notes": str(record.get("NOTES") or "").strip(),
        "reserved_seats": str(clas.get("HASACTIVERESERVEDSEATS") or "N").strip().upper() == "Y",
    }


def _when(row: dict[str, Any]) -> str:
    days = row["days"]
    if row["start_time"] and row["end_time"]:
        times = f"{row['start_time']}-{row['end_time']}"
    else:
        times = ""
    if days and times:
        return f"{days} {times}"
    if times:
        return times
    return days or "no set meeting time"


def _seats(row: dict[str, Any]) -> str:
    if row["enrolled"] is None or row["capacity"] is None:
        return "seats unknown"
    state = "OPEN" if row["is_open"] else "FULL"
    text = f"{row['enrolled']}/{row['capacity']} {state}"
    if not row["is_open"] and row["waitlist_capacity"]:
        text += f", waitlist {row['waitlist']}/{row['waitlist_capacity']}"
    return text


def _where(row: dict[str, Any]) -> str:
    if row["campus"] == "ASU Online":
        return "ASU Online"
    campus, room = row["campus"], row["room"]
    # LOCATIONBUILDING names already carry the campus ("Tempe - PSH153"),
    # so print it once rather than "Tempe · Tempe - PSH153".
    prefix = f"{campus} - "
    if campus and room.lower().startswith(prefix.lower()):
        room = room[len(prefix) :]
    parts = [p for p in [campus, room] if p]
    return " · ".join(parts) or "location TBA"


def format_search_results(
    payload: dict[str, Any],
    *,
    term_label: str,
    open_only: bool = False,
    max_shown: int = 60,
) -> str:
    """Render search results grouped by course, densest useful form."""
    rows = [normalize(r) for r in payload.get("classes", [])]
    total_matched = payload.get("total", len(rows))

    if open_only:
        rows = [r for r in rows if r["is_open"]]

    if not rows:
        if open_only and total_matched:
            return (
                f"No sections with open seats in {term_label}. "
                f"({total_matched} section(s) matched, all full.)"
            )
        return f"No classes matched in {term_label}."

    # Group by course so 40 sections of 6 courses read as 6 blocks, not 40 lines.
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(f"{row['course']}|{row['title']}", []).append(row)

    lines: list[str] = []
    shown = 0
    hit_cap = False
    for key, sections in grouped.items():
        if shown >= max_shown:
            hit_cap = True
            break
        course, title = key.split("|", 1)
        units = sections[0]["units"]
        lines.append(f"\n{course} — {title} ({units} credits)")
        for row in sections:
            if shown >= max_shown:
                hit_cap = True
                break
            who = ", ".join(row["instructors"]) or "instructor TBA"
            bits = [
                f"  #{row['class_number']}",
                f"{row['component'] or 'Class'} {row['section']}".strip(),
                _when(row),
                _where(row),
                who,
                _seats(row),
            ]
            if row["session_label"] and row["session"] != "C":
                bits.append(row["session_label"])
            if row["consent_required"]:
                bits.append("consent required")
            lines.append("  ".join(b for b in bits if b))
            shown += 1

    header = f"{len(rows)} section(s)"
    if open_only:
        header += " with open seats"
    header += f" in {term_label}"
    if payload.get("truncated") or hit_cap:
        header += f" (showing {shown} of {total_matched} matched)"

    footer = "\n\nEnroll with the # class number in My ASU."
    return header + "\n" + "\n".join(lines) + footer


def format_class_detail(record: dict[str, Any], *, term_label: str) -> str:
    """Full detail for one section."""
    row = normalize(record)
    out = [
        f"{row['course']} — {row['title']}",
        f"Class number {row['class_number']} · section {row['section']} · "
        f"{row['component']} · {row['units']} credits · {term_label}",
        "",
        f"Meets:      {_when(row)}",
        f"Where:      {_where(row)}" + (f"  ({row['map_url']})" if row["map_url"] else ""),
        f"Instructor: {', '.join(row['instructors']) or 'TBA'}",
        f"Seats:      {_seats(row)}",
        f"Format:     {row['instruction_mode'] or 'n/a'}",
    ]
    session = row["session_label"] or row["session"]
    if session:
        out.append(f"Session:    {session} ({row['start_date']} to {row['end_date']})")
    if row["offered_by"]:
        out.append(f"Offered by: {row['offered_by']}")
    if row["general_studies"]:
        out.append(f"Gen studies: {row['general_studies']}")

    deadlines = [
        ("Last day to enroll", row["enroll_deadline"]),
        ("Drop (no record)", row["drop_deadline"]),
        ("Withdraw", row["withdraw_deadline"]),
    ]
    known = [f"{label}: {value}" for label, value in deadlines if value]
    if known:
        out += ["", "Deadlines:  " + " · ".join(known)]

    flags = []
    if row["consent_required"]:
        flags.append("instructor/department consent required to enroll")
    if row["reserved_seats"]:
        flags.append("some seats are reserved for specific groups")
    if flags:
        out += ["", "Note: " + "; ".join(flags)]
    if row["notes"]:
        out += ["", f"Notes: {row['notes']}"]

    return "\n".join(out)
