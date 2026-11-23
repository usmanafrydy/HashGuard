"""
HashGuard Security Advisory Scraper.

Retrieves and parses recent cybersecurity advisories from CISA.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


SOURCE_URL = "https://www.cisa.gov/news-events/cybersecurity-advisories"
MAX_ADVISORIES = 10
REQUEST_TIMEOUT = 15


@dataclass
class Advisory:
    """Represents a single security advisory."""

    title: str
    publication_date: str
    url: str


def parse_advisories(html: str) -> list[Advisory]:
    """
    Parse advisory information from HTML.

    This function does not make internet requests, making it
    independently testable using sample HTML.
    """

    soup = BeautifulSoup(html, "html.parser")
    advisories = []

    for article in soup.select("article"):
        title_element = article.select_one("h3.c-teaser__title a")
        date_element = article.select_one("div.c-teaser__date time")

        if title_element is None:
            continue

        title = title_element.get_text(" ", strip=True)
        link = title_element.get("href")

        if not title or not link:
            continue

        publication_date = ""

        if date_element:
            publication_date = (
                date_element.get("datetime")
                or date_element.get_text(" ", strip=True)
            )

        advisory_url = urljoin(SOURCE_URL, link)

        advisories.append(
            Advisory(
                title=title,
                publication_date=publication_date,
                url=advisory_url,
            )
        )

        if len(advisories) >= MAX_ADVISORIES:
            break

    return advisories


def fetch_advisories() -> list[Advisory]:
    """
    Retrieve the CISA webpage and return parsed advisories.

    Raises requests.RequestException if retrieval fails.
    Raises ValueError if no advisories can be extracted.
    """

    response = requests.get(
        SOURCE_URL,
        timeout=REQUEST_TIMEOUT,
        headers={
            "User-Agent": "HashGuard Security Advisory Monitor/1.0"
        },
    )

    response.raise_for_status()

    advisories = parse_advisories(response.text)

    if not advisories:
        raise ValueError(
            "No security advisories could be extracted from the webpage."
        )

    return advisories


class AdvisoryManager:
    """
    Maintains advisory results and retrieval information.

    Existing advisories are preserved if a refresh fails.
    """

    def __init__(self):
        self.advisories: list[Advisory] = []
        self.last_successful_retrieval: datetime | None = None
        self.last_refresh_error: str | None = None

    def refresh(self) -> bool:
        """
        Refresh advisories.

        Returns:
            True: Refresh succeeded.
            False: Refresh failed.

        Previous results and timestamps remain unchanged
        if retrieval fails.
        """

        try:
            new_advisories = fetch_advisories()

            # Update state only after retrieval succeeds.
            self.advisories = new_advisories

            self.last_successful_retrieval = datetime.now(
                timezone.utc
            )

            self.last_refresh_error = None

            return True

        except (requests.RequestException, ValueError) as error:
            self.last_refresh_error = str(error)

            # Preserve previous advisories and timestamp.
            return False