"""Run with:  python -m pytest"""
from pathlib import Path

from scraper import cleaning, storage
from scraper.sources import shtegtimi

FIXTURE = (Path(__file__).parent / "fixtures" / "shtegtimi_tour.html").read_text(encoding="utf-8")
URL = "https://shtegtimi.com/tours/ekspedita-ne-olimp-mytikas"


def test_parse_tour_reads_overview_box():
    event = shtegtimi.parse_tour(FIXTURE, URL)
    assert event["id"] == "shtegtimi:ekspedita-ne-olimp-mytikas"
    assert event["title"] == "Ekspedita në Olimp - Mytikas"      # flag emoji removed
    assert event["start_date"] == "2027-06-25"
    assert event["end_date"] == "2027-06-27"
    assert event["difficulty"] == "Intermediate"
    assert event["location"] == "Prishtinë"                       # from the description template
    assert event["category"] == "Hiking"
    assert event["duration_days"] == 3
    assert event["distance_km"] == 17
    assert event["elevation_gain_m"] == 1960
    assert event["avg_minutes_per_day"] == 300
    assert event["spots_left"] == 19
    assert event["price_eur"] is None                              # missing -> None, no crash


def test_extract_tour_links_dedupes_and_filters():
    links = shtegtimi.extract_tour_links(FIXTURE)
    assert links == [
        "https://shtegtimi.com/tours/ekspedita-ne-olimp-mytikas",
        "https://shtegtimi.com/tours/rock-climbing",
    ]


def test_cleaning_helpers():
    assert cleaning.parse_date("18.01.2026") == "2026-01-18"
    assert cleaning.parse_date("not a date") is None
    assert cleaning.parse_number("From €795 pp") == 795
    assert cleaning.parse_number("1,960 m") == 1960
    assert cleaning.parse_number("2,5 km") == 2.5
    assert cleaning.clean_text("  a \n  b ") == "a b"


def test_dedupe_keeps_latest():
    old = {"id": "a", "title": "Gjeravica", "start_date": "2027-05-01", "spots_left": 10}
    new = {"id": "a", "title": "Gjeravica", "start_date": "2027-05-01", "spots_left": 4}
    manual = {"id": "manual:1", "title": "gjeravica ", "start_date": "2027-05-01"}
    events, removed = storage.dedupe([manual, old, new])
    assert removed == 2
    assert events == [new]


def test_summary_regex_with_comma_location():
    match = shtegtimi.SUMMARY.search(
        "6-day trekking adventure with local guides in Theth, Albania. Advanced difficulty.")
    assert match.group(1) == "trekking"
    assert match.group(2) == "Theth, Albania"


def test_dates_on_request_and_cost():
    # Same page, but like the Rock Climbing tour: no date, a cost row, a climbing grade.
    html = (FIXTURE
            .replace("Jun 25, 2027 → Jun 27, 2027", "Dates on request")
            .replace(">Meet in<", ">Start location<")
            .replace(">Spots left<", ">Cost<").replace(">19<", ">From 25 EUR<")
            .replace("Intermediate <span>(paced for the group)</span>", "Beginner · 5c-6b"))
    event = shtegtimi.parse_tour(html, URL)
    assert event["date_status"] == "on_request"
    assert event["start_date"] is None
    assert event["price_eur"] == 25
    assert event["difficulty"] == "Beginner"


def test_events_without_date_are_not_merged():
    a = {"id": "shtegtimi:rock-climbing", "title": "Rock Climbing", "start_date": None}
    b = {"id": "shtegtimi:other", "title": "Rock Climbing", "start_date": None}
    events, removed = storage.dedupe([a, b])
    assert removed == 0