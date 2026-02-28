from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import yaml

DAYS_DIR = Path(__file__).parent / "TouhouCalendarBot" / "days"
OUTPUT_FILE = Path(__file__).parent / "touhou_calendar.ics"
REFERENCE_YEAR = 2024  # Must be a leap year (Feb 29 Miyako Day)


@dataclass
class CalendarEvent:
    month: int
    day: int
    name: str
    message: str
    explanation: str
    explanation_short: str | None = None
    characters: list[str] = field(default_factory=list)
    citations: list[dict] = field(default_factory=list)


def parse_event(doc: dict) -> CalendarEvent:
    raw_citations = doc.get("citations")
    if not isinstance(raw_citations, list):
        raw_citations = []

    raw_characters = doc.get("characters")
    if not isinstance(raw_characters, list):
        raw_characters = []

    return CalendarEvent(
        month=doc["month"],
        day=doc["day"],
        name=doc["name"],
        message=doc["message"],
        explanation=doc["explanation"],
        explanation_short=doc.get("explanation_short"),
        characters=raw_characters,
        citations=raw_citations,
    )


def load_events() -> list[CalendarEvent]:
    events: list[CalendarEvent] = []
    for month_num in range(1, 13):
        yaml_path = DAYS_DIR / f"{month_num}.yaml"
        with yaml_path.open(encoding="utf-8") as f:
            for doc in yaml.safe_load_all(f):
                if doc is None:
                    continue
                events.append(parse_event(doc))
    events.sort(key=lambda e: (e.month, e.day, e.name))
    return events


def ics_escape(text: str) -> str:
    """Escape text for ICS fields per RFC 5545."""
    text = text.replace("\\", "\\\\")
    text = text.replace(";", "\\;")
    text = text.replace(",", "\\,")
    text = text.replace("\n", "\\n")
    return text


def ics_fold_line(line: str) -> str:
    """Fold long lines per RFC 5545 (max 75 octets)."""
    encoded = line.encode("utf-8")
    if len(encoded) <= 75:
        return line
    result = []
    while len(encoded) > 75:
        # Find safe split point that doesn't break multi-byte chars
        split_at = 75
        while split_at > 0 and (encoded[split_at] & 0xC0) == 0x80:
            split_at -= 1
        result.append(encoded[:split_at].decode("utf-8"))
        encoded = encoded[split_at:]
    result.append(encoded.decode("utf-8"))
    return "\r\n ".join(result)


def generate_uid(event: CalendarEvent) -> str:
    unique_string = f"{event.month:02d}-{event.day:02d}-{event.name}"
    hash_hex = hashlib.sha256(unique_string.encode("utf-8")).hexdigest()[:16]
    return f"{hash_hex}@touhou-calendar"


def build_vevent(event: CalendarEvent) -> str:
    dt = date(REFERENCE_YEAR, event.month, event.day)
    dtstart = dt.strftime("%Y%m%d")

    description_parts = [event.message]
    explanation = event.explanation_short or event.explanation
    description_parts.append(explanation.strip())
    if event.characters:
        description_parts.append(f"Characters: {', '.join(event.characters)}")
    description = "\\n\\n".join(ics_escape(part.strip()) for part in description_parts)

    summary = ics_escape(event.name)
    uid = generate_uid(event)

    lines = [
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTART;VALUE=DATE:{dtstart}",
        f"SUMMARY:{summary}",
        f"DESCRIPTION:{description}",
        "RRULE:FREQ=YEARLY",
        "TRANSP:TRANSPARENT",
        "END:VEVENT",
    ]
    return "\r\n".join(ics_fold_line(line) for line in lines)


def build_ics(events: list[CalendarEvent]) -> str:
    header = "\r\n".join([
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Touhou Calendar//Touhou Calendar//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Touhou Calendar",
    ])
    vevents = "\r\n".join(build_vevent(e) for e in events)
    footer = "END:VCALENDAR"
    return f"{header}\r\n{vevents}\r\n{footer}\r\n"


def print_event_summary(events: list[CalendarEvent]) -> None:
    print(f"Parsed {len(events)} events:\n")
    for event in events:
        print(f"  {event.month:02d}/{event.day:02d} - {event.name}")
    print()


def main() -> None:
    events = load_events()
    print_event_summary(events)

    ics_content = build_ics(events)
    OUTPUT_FILE.write_text(ics_content, encoding="utf-8", newline="")

    print(f"Written {OUTPUT_FILE.name} with {len(events)} events.")


if __name__ == "__main__":
    main()
