
from datetime import datetime, timezone
from unittest.mock import patch

import requests

from src.advisory_scraper import (
    Advisory,
    AdvisoryManager,
    parse_advisories,
)


# -----------------------------
# Sample HTML for offline tests
# -----------------------------

SAMPLE_HTML = """
<html>
<body>
    <article>
        <div class="c-teaser__date">
            <time datetime="2026-11-20T12:00:00Z">Nov 20, 2026</time>
        </div>
        <h3 class="c-teaser__title">
            <a href="/news-events/alerts/test-alert">
                Test Security Advisory
            </a>
        </h3>
    </article>

    <article>
        <h3 class="c-teaser__title">
            <a href="/news-events/alerts/second-alert">
                Second Advisory
            </a>
        </h3>
    </article>
</body>
</html>
"""


# -----------------------------
# Parser tests
# -----------------------------

def test_parse_advisory_title_date_and_url():
    advisories = parse_advisories(SAMPLE_HTML)

    assert len(advisories) == 2

    first = advisories[0]

    assert first.title == "Test Security Advisory"
    assert first.publication_date == "2026-11-20T12:00:00Z"
    assert first.url == (
        "https://www.cisa.gov/news-events/alerts/test-alert"
    )


def test_missing_date_is_handled():
    advisories = parse_advisories(SAMPLE_HTML)

    second = advisories[1]

    assert second.title == "Second Advisory"
    assert second.publication_date == ""


def test_empty_html_returns_empty_list():
    advisories = parse_advisories("")

    assert advisories == []


def test_articles_without_valid_title_or_link_are_skipped():
    html = """
    <article>
        <h3 class="c-teaser__title">
            <a href="/valid">Valid Advisory</a>
        </h3>
    </article>

    <article>
        <h3 class="c-teaser__title">
            <a href="">Invalid Link</a>
        </h3>
    </article>

    <article>
        <h3 class="c-teaser__title">
            No Link Here
        </h3>
    </article>
    """

    advisories = parse_advisories(html)

    assert len(advisories) == 1
    assert advisories[0].title == "Valid Advisory"


def test_parser_limits_results_to_10():
    articles = ""

    for number in range(12):
        articles += f"""
        <article>
            <h3 class="c-teaser__title">
                <a href="/advisory-{number}">
                    Advisory {number}
                </a>
            </h3>
        </article>
        """

    advisories = parse_advisories(articles)

    assert len(advisories) == 10


def test_absolute_urls_are_preserved():
    html = """
    <article>
        <h3 class="c-teaser__title">
            <a href="https://example.com/security/advisory">
                Example Advisory
            </a>
        </h3>
    </article>
    """

    advisories = parse_advisories(html)

    assert advisories[0].url == (
        "https://example.com/security/advisory"
    )


# -----------------------------
# AdvisoryManager tests
# -----------------------------

def test_refresh_success_updates_advisories_and_timestamp():
    sample_advisory = Advisory(
        title="New Advisory",
        publication_date="2026-11-20",
        url="https://example.com/advisory",
    )

    manager = AdvisoryManager()

    with patch(
        "src.advisory_scraper.fetch_advisories",
        return_value=[sample_advisory],
    ):
        result = manager.refresh()

    assert result is True
    assert manager.advisories == [sample_advisory]
    assert manager.last_successful_retrieval is not None
    assert manager.last_refresh_error is None


def test_refresh_failure_preserves_previous_data():
    old_advisory = Advisory(
        title="Old Advisory",
        publication_date="2026-11-19",
        url="https://example.com/old",
    )

    manager = AdvisoryManager()

    manager.advisories = [old_advisory]

    old_timestamp = datetime(
        2026, 11, 19, 12, 0, 0, tzinfo=timezone.utc
    )

    manager.last_successful_retrieval = old_timestamp

    with patch(
        "src.advisory_scraper.fetch_advisories",
        side_effect=requests.ConnectionError(
            "Internet connection failed"
        ),
    ):
        result = manager.refresh()

    assert result is False

    # Previous data must remain unchanged.
    assert manager.advisories == [old_advisory]

    # Previous successful retrieval time must remain unchanged.
    assert manager.last_successful_retrieval == old_timestamp

    # The error must be recorded.
    assert manager.last_refresh_error is not None
    assert "Internet connection failed" in manager.last_refresh_error


def test_refresh_failure_with_parsing_error_preserves_data():
    old_advisory = Advisory(
        title="Old Advisory",
        publication_date="2026-11-19",
        url="https://example.com/old",
    )

    manager = AdvisoryManager()
    manager.advisories = [old_advisory]

    with patch(
        "src.advisory_scraper.fetch_advisories",
        side_effect=ValueError("Parsing failed"),
    ):
        result = manager.refresh()

    assert result is False
    assert manager.advisories == [old_advisory]
    assert manager.last_refresh_error == "Parsing failed"


def test_refresh_success_clears_previous_error():
    manager = AdvisoryManager()

    manager.last_refresh_error = "Previous error"

    new_advisory = Advisory(
        title="Updated Advisory",
        publication_date="2026-11-20",
        url="https://example.com/new",
    )

    with patch(
        "src.advisory_scraper.fetch_advisories",
        return_value=[new_advisory],
    ):
        result = manager.refresh()

    assert result is True
    assert manager.last_refresh_error is None
    assert manager.advisories == [new_advisory]