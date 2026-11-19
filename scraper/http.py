"""Downloading pages politely and safely.

Everything that touches the network lives here, so the parsers never have to
think about timeouts, retries or rate limits.
"""
import logging
import time

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

log = logging.getLogger(__name__)

# Identify yourself honestly. Put your own email/GitHub here.
USER_AGENT = "HikingEventsScraper/0.1 (learning project; contact: you@example.com)"


class Fetcher:
    def __init__(self, delay: float = 1.5, timeout: float = 15):
        self.delay = delay          # seconds to wait between requests
        self.timeout = timeout      # give up on a request after this many seconds
        self._last_request = 0.0

        # A Session reuses the same connection for many requests (faster)
        # and sends our headers every time.
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})

        # Retry automatically on temporary server problems:
        # 429 = "too many requests", 5xx = server errors.
        # backoff_factor=1 waits 1s, 2s, 4s between attempts.
        retry = Retry(total=3, backoff_factor=1,
                      status_forcelist=[429, 500, 502, 503, 504])
        self.session.mount("https://", HTTPAdapter(max_retries=retry))
        self.session.mount("http://", HTTPAdapter(max_retries=retry))

    def get(self, url: str) -> str | None:
        """Return the page HTML, or None if it could not be downloaded.

        Returning None (instead of crashing) lets the caller skip one broken
        page and keep scraping the rest.
        """
        # Rate limit: make sure at least `delay` seconds passed since last request.
        wait = self.delay - (time.time() - self._last_request)
        if wait > 0:
            time.sleep(wait)

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
