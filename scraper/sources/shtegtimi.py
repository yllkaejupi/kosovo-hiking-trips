"""Scraper for https://shtegtimi.com

Two steps:
  1. Listing pages (/tours?page=1, 2, ...) -> collect every /tours/<slug> link
  2. Each tour page -> read the overview box and build one clean event dict
"""
import logging
import re
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from scraper import cleaning

log = logging.getLogger(__name__)

SOURCE = "shtegtimi"
BASE_URL = "https://shtegtimi.com"
LISTING_URL = BASE_URL + "/tours"
TOUR_PATH = re.compile(r"^/tours/([a-z0-9-]+)/?$")   # matches /tours/ekspedita-ne-olimp-mytikas

# Shtegtimi's descriptions follow a template:
#   "6-day trekking adventure with local guides in Theth, Albania. Advanced difficulty."
#        (\w+) = category               ([^.]+) = location (everything up to the dot)
SUMMARY = re.compile(r"\d+-day (\w+) adventure with local guides in ([^.]+)\.", re.IGNORECASE)


# ---------- Step 1: find all tour links ----------

def extract_tour_links(html: str) -> list[str]:
    """Return every tour URL found in one listing page (no duplicates, page order kept)."""
    soup = BeautifulSoup(html, "html.parser")
    links: dict[str, None] = {}          # a dict keeps insertion order AND removes duplicates
    for a in soup.find_all("a", href=True):
        url = urljoin(BASE_URL, a["href"])       # turns "/tours/x" into a full URL
        parsed = urlparse(url)
        if parsed.netloc.endswith("shtegtimi.com") and TOUR_PATH.match(parsed.path):
            links[f"{BASE_URL}{parsed.path.rstrip('/')}"] = None
    return list(links)


def get_all_tour_links(fetcher, max_pages: int = 20) -> list[str]:
    """Walk through ?page=1, ?page=2, ... until a page brings no new links."""
    all_links: dict[str, None] = {}
    for page in range(1, max_pages + 1):
        html = fetcher.get(f"{LISTING_URL}?page={page}")
        if html is None:
            break
        new = [link for link in extract_tour_links(html) if link not in all_links]
        log.info("Listing page %d: %d new tours", page, len(new))
        if not new:                       # past the last page
            break
        all_links.update(dict.fromkeys(new))
    return list(all_links)


# ---------- Step 2: parse one tour page ----------

def read_overview(soup: BeautifulSoup) -> dict[str, str]:
    """Read the overview box into {label: value}.

    Each row in the HTML looks like:
        <div class="flex items-baseline ...">
          <span class="tour-overview-label">Next departure</span>
          <span class="... border-dotted"></span>          (the dotted line)
          <span class="... text-right">Jun 25, 2027 → Jun 27, 2027</span>
        </div>
    So: find each label, go up to its row, and take the LAST span as the value.
    Using labels (not positions) means the parser still works if rows get reordered.
    """
    overview = {}
    for label in soup.select("span.tour-overview-label"):
        row = label.parent
        spans = row.find_all("span", recursive=False)
        if len(spans) < 2:
            continue
        key = cleaning.clean_text(label.get_text(" ")).lower()
        overview[key] = cleaning.clean_text(spans[-1].get_text(" "))
    return overview


def first_of(overview: dict, *labels: str) -> str | None:
    """Return the value of the first label that exists (sites rename things)."""
    for label in labels:
        if overview.get(label):
            return overview[label]
    return None


def meta_content(soup: BeautifulSoup, **attrs) -> str | None:
    tag = soup.find("meta", attrs=attrs)
    return cleaning.clean_text(tag.get("content")) if tag else None


def parse_tour(html: str, url: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    overview = read_overview(soup)

    h1 = soup.find("h1")
    title = h1.get_text(" ") if h1 else (meta_content(soup, property="og:title") or "").split("|")[0]

    date_text = first_of(overview, "next departure", "date", "dates")
    start, end = cleaning.parse_date_range(date_text)
    # Some tours have no fixed date: "Dates on request". That's real data, not an error.
    if start:
        date_status = "scheduled"
    elif date_text and "request" in date_text.lower():
        date_status = "on_request"
    else:
        date_status = "unknown"

    slug = urlparse(url).path.rstrip("/").split("/")[-1]

    description = meta_content(soup, name="description") or meta_content(soup, property="og:description")
    match = SUMMARY.search(description or "")
    category = match.group(1).capitalize() if match else None      # "trekking" -> "Trekking"
    location = cleaning.clean_text(match.group(2)) if match else None
    
    duration_text = first_of(overview, "duration", "days") or ""
    is_hours = "hour" in duration_text.lower()

    return {
        "id": f"{SOURCE}:{slug}",
        "source": SOURCE,
        "title": cleaning.clean_title(title),
        "category": first_of(overview, "category", "type", "activity") or category,
        "difficulty": cleaning.strip_note(first_of(overview, "difficulty")),
        "date_status": date_status,
        "start_date": start,
        "end_date": end,
        "duration_days": None if is_hours else cleaning.parse_number(duration_text),
        "location": first_of(overview, "start location", "start", "meeting point", "location") or location,
        "duration_hours": cleaning.parse_number(duration_text) if is_hours else None,
        "distance_km": cleaning.parse_number(first_of(overview, "distance")),
        "elevation_gain_m": cleaning.parse_number(first_of(overview, "elevation gain", "ascent")),
        "avg_minutes_per_day": cleaning.parse_minutes(first_of(overview, "avg time / day", "avg time")),
        "spots_left": cleaning.parse_number(first_of(overview, "spots left")),
        "price_eur": cleaning.parse_number(first_of(overview, "cost", "price")),
        "description": description,
        "url": url,
        "scraped_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


# ---------- Put it together ----------

def scrape(fetcher, limit: int | None = None) -> list[dict]:
    links = get_all_tour_links(fetcher)
    log.info("Found %d tours on %s", len(links), SOURCE)
    if limit:
        links = links[:limit]

    events = []
    for url in links:
        html = fetcher.get(url)
        if html is None:
            continue                      # already logged by the fetcher; skip this tour
        try:
            event = parse_tour(html, url)
        except Exception:                 # a layout change on ONE page shouldn't stop the run
            log.exception("Could not parse %s", url)
            continue
        # Only warn when something is unexpected. "Dates on request" is expected.
        if not event["title"] or event["date_status"] == "unknown":
            log.warning("Missing title or date on %s (layout changed?)", url)
        events.append(event)
    return events