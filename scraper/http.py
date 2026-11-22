"""Downloading pages politely and safely.

Everything that touches the network lives here, so the parsers never have to
think about timeouts, retries, rate limits or robots.txt.
"""
import logging
import time
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

log = logging.getLogger(__name__)

# Identifying myself so site owners know who is visiting and how to reach me.
USER_AGENT = "HikingEventsScraper/0.1 (+https://github.com/yllkaejupi/kosovo-hiking-trips)"


class Fetcher:
    def __init__(self, delay: float = 1.5, timeout: float = 15, obey_robots: bool = True):
        self.delay = delay          # seconds to wait between requests
        self.timeout = timeout      # give up on a request after this many seconds
        self.obey_robots = obey_robots
        self._last_request = 0.0
        self._robots: dict[str, RobotFileParser] = {}   # one robots.txt per site, fetched once

        # A Session reuses the same connection for many requests (faster)
        # and sends our headers every time.
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})

        # Retry automatically on temporary server problems.
        # backoff_factor=1 waits 1s, 2s, 4s between attempts.
        retry = Retry(total=3, backoff_factor=1,
                      status_forcelist=[429, 500, 502, 503, 504])
        self.session.mount("https://", HTTPAdapter(max_retries=retry))
        self.session.mount("http://", HTTPAdapter(max_retries=retry))

    # ---------- robots.txt ----------

    def _robots_for(self, url: str) -> RobotFileParser:
        """Download and cache the robots.txt of the site that `url` belongs to."""
        parsed = urlparse(url)
        site = f"{parsed.scheme}://{parsed.netloc}"
        if site in self._robots:
            return self._robots[site]

        robots = RobotFileParser(site + "/robots.txt")
        try:
            self._wait_for_turn()
            response = self.session.get(robots.url, timeout=self.timeout)
            if response.status_code in (401, 403):
                robots.disallow_all = True          # the site says "keep out"
            elif response.status_code >= 400:
                robots.allow_all = True             # no robots.txt = no rules
            else:
                robots.parse(response.text.splitlines())
        except requests.RequestException as error:
            # Can't read the rules right now: don't block the whole run, but say so.
            log.warning("Could not read %s (%s), assuming everything is allowed", robots.url, error)
            robots.allow_all = True
        finally:
            self._last_request = time.time()

        crawl_delay = robots.crawl_delay(USER_AGENT)
        if crawl_delay and float(crawl_delay) > self.delay:
            log.info("%s asks for %ss between requests, slowing down", site, crawl_delay)
            self.delay = float(crawl_delay)

        self._robots[site] = robots
        return robots

    def allowed(self, url: str) -> bool:
        """True if robots.txt lets us download this URL."""
        return not self.obey_robots or self._robots_for(url).can_fetch(USER_AGENT, url)

    # ---------- downloading ----------

    def _wait_for_turn(self) -> None:
        """Rate limit: make sure at least `delay` seconds passed since the last request."""
        wait = self.delay - (time.time() - self._last_request)
        if wait > 0:
            time.sleep(wait)

    def get(self, url: str) -> str | None:
        """Return the page HTML, or None if it could not (or may not) be downloaded.

        Returning None (instead of crashing) lets the caller skip one broken
        page and keep scraping the rest.
        """
        if not self.allowed(url):
            log.warning("robots.txt disallows %s, skipping it", url)
            return None

        self._wait_for_turn()
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()   # turns 404/500 into an exception
            response.encoding = response.encoding or "utf-8"
            return response.text
        except requests.RequestException as error:
            log.warning("Could not fetch %s: %s", url, error)
            return None
        finally:
            self._last_request = time.time()
