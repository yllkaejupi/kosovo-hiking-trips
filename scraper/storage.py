"""Removing duplicates and saving events to JSON / CSV."""
import csv
import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)


def load_json(path: str | Path) -> list[dict]:
    """Read a list of events. A missing file just means 'no events yet'."""
    path = Path(path)
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        log.error("%s is not valid JSON (%s), ignoring it", path, error)
        return []


def _dedupe_key(event: dict) -> tuple:
    """Two events are 'the same trip' if they have the same title and start date,
    even if they come from different sources (e.g. scraped + added manually)."""
    # Without a date we can't tell two trips apart by title alone
    # (a club can repeat "Gjeravica Hike" many times), so fall back to the unique id.
    if not event.get("start_date"):
        return ("id", event["id"])
    title = (event.get("title") or "").lower().strip()
    return (title, event.get("start_date"))


def dedupe(events: list[dict]) -> tuple[list[dict], int]:
    """Remove duplicates. If two events match, the LATER one in the list wins,
    so fresh scraped data replaces older saved data.

    Returns (unique_events, number_of_duplicates_removed).
    """
    by_id: dict[str, dict] = {}
    for event in events:
        by_id[event["id"]] = event          # same id -> overwritten (dict keys are unique)

    by_key: dict[tuple, dict] = {}
    for event in by_id.values():
        by_key[_dedupe_key(event)] = event  # same title+date -> overwritten

    unique = list(by_key.values())
    return unique, len(events) - len(unique)


def sort_by_date(events: list[dict]) -> list[dict]:
    # Events without a date go to the end ("9999" sorts after any real date).
    return sorted(events, key=lambda e: e.get("start_date") or "9999")


def save_json(events: list[dict], path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    # ensure_ascii=False keeps "ë" readable instead of writing "ë"
    Path(path).write_text(json.dumps(events, ensure_ascii=False, indent=2), encoding="utf-8")


def save_csv(events: list[dict], path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    # Collect every field that appears in any event, keeping first-seen order.
    fieldnames: list[str] = []
    for event in events:
        for key in event:
            if key not in fieldnames:
                fieldnames.append(key)
    # "utf-8-sig" adds a marker so Excel shows Albanian letters (ë, ç) correctly.
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(events)