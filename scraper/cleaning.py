"""Small pure functions that turn messy website text into clean values.

"Pure" = same input always gives the same output, no network, no files.
That makes them very easy to test.
"""
import re
from datetime import datetime

# Flag emojis like 🇬🇷 are made of two "regional indicator" characters.
FLAG_EMOJI = re.compile("[\U0001F1E6-\U0001F1FF]")

# Date formats we expect to meet on hiking sites. Add more when a new site needs them.
DATE_FORMATS = ("%b %d, %Y", "%B %d, %Y", "%d.%m.%Y", "%d/%m/%Y", "%Y-%m-%d")


def clean_text(text: str | None) -> str | None:
    """Collapse all whitespace (spaces, tabs, newlines) into single spaces."""
    if text is None:
        return None
    text = " ".join(text.split())
    return text or None          # turn "" into None


def clean_title(text: str | None) -> str | None:
    """Remove flag emojis and extra spaces: 'Olimp 🇬🇷' -> 'Olimp'."""
    if text is None:
        return None
    return clean_text(FLAG_EMOJI.sub("", text))


def parse_date(text: str | None) -> str | None:
    """'Jun 25, 2027' -> '2027-06-25' (ISO format, sorts correctly as text)."""
    text = clean_text(text)
    if not text:
        return None
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue             # wrong format, try the next one
    return None


def parse_date_range(text: str | None) -> tuple[str | None, str | None]:
    """'Jun 25, 2027 → Jun 27, 2027' -> ('2027-06-25', '2027-06-27')."""
    text = clean_text(text)
    if not text:
        return None, None
    parts = re.split(r"\s*(?:→|->|–|—)\s*", text)
    start = parse_date(parts[0])
    end = parse_date(parts[1]) if len(parts) > 1 else None
    return start, end


def parse_number(text: str | None) -> int | float | None:
    """Pull the first number out of text: '17 km' -> 17, '1,960 m' -> 1960, '2.5 km' -> 2.5."""
    if not text:
        return None
    match = re.search(r"\d[\d,.]*", text)
    if not match:
        return None
    raw = match.group().rstrip(".,")
    if re.fullmatch(r"\d{1,3}(,\d{3})+", raw):   # '1,960' is a thousands separator
        raw = raw.replace(",", "")
    else:                                          # '2,5' is a European decimal
        raw = raw.replace(",", ".")
    number = float(raw)
    return int(number) if number.is_integer() else number


def parse_minutes(text: str | None) -> int | None:
    """'5h 0m' -> 300, '45m' -> 45."""
    if not text:
        return None
    hours = re.search(r"(\d+)\s*h", text)
    minutes = re.search(r"(\d+)\s*m", text)
    if not hours and not minutes:
        return None
    return int(hours.group(1) if hours else 0) * 60 + int(minutes.group(1) if minutes else 0)


def strip_note(text: str | None) -> str | None:
    """'Intermediate (paced for the group)' -> 'Intermediate', 'Beginner · 5c-6b' -> 'Beginner'."""
    text = clean_text(text)
    if not text:
        return None
    return clean_text(re.split(r"[(·]", text)[0])