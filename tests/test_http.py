"""robots.txt handling in the Fetcher, without touching the network."""
from scraper.http import Fetcher


class FakeResponse:
    def __init__(self, status_code=200, text=""):
        self.status_code = status_code
        self.text = text
        self.encoding = "utf-8"

    def raise_for_status(self):
        pass


def make_fetcher(robots_status=200, robots_text=""):
    """A Fetcher whose session answers robots.txt with the given response
    and every other URL with a tiny HTML page. Records which URLs were requested."""
    fetcher = Fetcher(delay=0)
    fetcher.requested = []

    def fake_get(url, timeout):
        fetcher.requested.append(url)
        if url.endswith("/robots.txt"):
            return FakeResponse(robots_status, robots_text)
        return FakeResponse(200, "<html>ok</html>")

    fetcher.session.get = fake_get
    return fetcher


def test_disallowed_page_is_skipped():
    fetcher = make_fetcher(robots_text="User-agent: *\nDisallow: /private/")
    assert fetcher.get("https://example.com/private/page") is None
    assert fetcher.get("https://example.com/tours/x") == "<html>ok</html>"
    assert "https://example.com/private/page" not in fetcher.requested


def test_robots_txt_is_fetched_once_per_site():
    fetcher = make_fetcher(robots_text="User-agent: *\nDisallow:")
    fetcher.get("https://example.com/a")
    fetcher.get("https://example.com/b")
    assert fetcher.requested.count("https://example.com/robots.txt") == 1


def test_missing_robots_txt_allows_everything():
    fetcher = make_fetcher(robots_status=404)
    assert fetcher.get("https://example.com/tours/x") == "<html>ok</html>"


def test_forbidden_robots_txt_blocks_everything():
    fetcher = make_fetcher(robots_status=403)
    assert fetcher.get("https://example.com/tours/x") is None


def test_crawl_delay_slows_us_down():
    fetcher = make_fetcher(robots_text="User-agent: *\nCrawl-delay: 5")
    assert fetcher.allowed("https://example.com/tours/x")   # reads the rules, no page download
    assert fetcher.delay == 5
