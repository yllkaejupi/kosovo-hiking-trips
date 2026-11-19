"""Run the hiking events scraper.

    python main.py              # scrape everything
    python main.py --limit 2    # only 2 tours (quick test while developing)
"""
import argparse
import logging

from scraper import storage
from scraper.http import Fetcher
from scraper.sources import shtegtimi

DATA_DIR = "data"


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect hiking trips from club websites")
    parser.add_argument("--limit", type=int, help="max tours per source (for testing)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    fetcher = Fetcher(delay=1.5)

    # 1. Scrape every source (add more sources to this list later)
    scraped = []
    for source in [shtegtimi]:
        scraped += source.scrape(fetcher, limit=args.limit)

    # 2. Combine: previously saved events + manually added ones + fresh scrape.
    #    Fresh data goes LAST so it wins when duplicates are removed.
    previous = [
        event for event in storage.load_json(f"{DATA_DIR}/events.json")
        if not event["id"].startswith("manual:")
    ]
    manual = storage.load_json(f"{DATA_DIR}/manual_events.json")
    events, removed = storage.dedupe(previous + manual + scraped)
    events = storage.sort_by_date(events)

    # 3. Save
    storage.save_json(events, f"{DATA_DIR}/events.json")
    storage.save_csv(events, f"{DATA_DIR}/events.csv")
    storage.save_json(events, "docs/hikes.json")

    print(f"\nScraped {len(scraped)} | removed {removed} duplicates | saved {len(events)} events")


if __name__ == "__main__":
    main()