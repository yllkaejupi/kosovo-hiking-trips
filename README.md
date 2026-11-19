# Kosovo Hiking Trips

Hiking clubs in Kosovo post their weekend trips in many different places: websites, Instagram, Facebook.
This project collects them into one clean feed and shows them on a simple web page.

**Live demo:** https://yllkaejupi.github.io/kosovo-hiking-trips/

![Screenshot of the hiking trips page](docs/hikingpage.png)

**Stack:** Python, Requests, BeautifulSoup, JSON/CSV, JavaScript, HTML/CSS, Git, GitHub Pages

## How it works

1. **Python scraper** visits club websites, extracts each trip, cleans the data and saves it as JSON and CSV.
2. **Manual trips** from clubs that only post on Instagram/Facebook are added by hand in `data/manual_events.json` and merged in.
3. **Web page** (`docs/`) loads the JSON and shows the trips as cards with filters.

## Features

### Scraper
- Two-step crawl: listing pages (with pagination) -> each trip page
- Reads fields by their labels, not their position, so reordered rows don't break it
- Cleans data: ISO dates, numbers from text ("1,960 m" -> 1960), "4 Hours" vs "4 Days", emoji removal
- Handles tours with no fixed date ("Dates on request")
- Removes duplicates by id and by title + date, also across sources
- Handles errors: timeouts and retries; broken pages are skipped and logged
- Polite: custom User-Agent, delay between requests, respects robots.txt
- Tested with pytest using a saved sample page

### Web page
- Trip cards with date, difficulty badge, location, distance, elevation gain and price
- Filters by difficulty and by scheduled / on-request trips
- Hides trips that are already over
- Escapes all scraped text before displaying it (protection against XSS)
- Responsive grid, works on phones without media queries

## Project structure

```
├── main.py                  # runs everything: scrape -> merge -> dedupe -> save
├── scraper/
│   ├── http.py              # downloading: delay, retries, timeouts
│   ├── cleaning.py          # turning messy text into clean values
│   ├── storage.py           # duplicates + saving