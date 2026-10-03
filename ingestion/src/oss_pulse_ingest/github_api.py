"""A small, well-behaved GitHub REST API client.

Why not just call requests.get() everywhere? Because a real connector has to:
* authenticate on every call,
* follow pagination (GitHub returns at most 100 items per page),
* respect rate limits instead of crashing when they run out,
* retry temporary server errors.
Putting all of that in one class means the rest of the code stays simple.
"""

from __future__ import annotations

import logging
import os
import time
from collections.abc import Callable, Iterator

import requests

log = logging.getLogger(__name__)

API_URL = "https://api.github.com"
RETRYABLE_STATUS = {500, 502, 503, 504}


class GitHubAPIError(Exception):
    pass


class GitHubClient:
    def __init__(
        self,
        token: str | None = None,
        *,
        session: requests.Session | None = None,
        max_retries: int = 5,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        token = token or os.getenv("GITHUB_TOKEN")
        if not token:
            raise GitHubAPIError("GITHUB_TOKEN is not set (did you load .env?)")
        self.session = session or requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "oss-pulse-ingestion",
            }
        )
        self.max_retries = max_retries
        self.sleep = sleep  # injectable so tests don't actually wait

    def get(self, url: str, params: dict | None = None) -> requests.Response:
        """GET with retries. Redirects (renamed repos) are followed automatically."""
        if not url.startswith("http"):
            url = f"{API_URL}/{url.lstrip('/')}"

        for attempt in range(1, self.max_retries + 1):
            resp = self.session.get(url, params=params, timeout=30)

            if resp.status_code in (403, 429) and self._is_rate_limited(resp):
                wait = self._seconds_until_allowed(resp)
                log.warning("Rate limited; sleeping %.0fs (attempt %d)", wait, attempt)
                self.sleep(wait)
                continue

            if resp.status_code in RETRYABLE_STATUS:
                wait = 2**attempt  # exponential backoff: 2, 4, 8, 16...
                log.warning("GitHub %d; retrying in %ds", resp.status_code, wait)
                self.sleep(wait)
                continue

            return resp

        raise GitHubAPIError(f"Gave up on {url} after {self.max_retries} attempts")

    def paginate(self, url: str, params: dict | None = None) -> Iterator[dict]:
        """Yield every item across all pages by following GitHub's `Link: next` header."""
        params = {"per_page": 100, **(params or {})}
        while url:
            resp = self.get(url, params=params)
            resp.raise_for_status()
            yield from resp.json()
            url = resp.links.get("next", {}).get("url")
            params = None  # the "next" URL already contains all query parameters

    def get_repo(self, full_name: str) -> dict | None:
        """Repo metadata, or None if it doesn't exist (deleted, or never existed)."""
        resp = self.get(f"repos/{full_name}")
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()

    @staticmethod
    def _is_rate_limited(resp: requests.Response) -> bool:
        return resp.headers.get("x-ratelimit-remaining") == "0" or "retry-after" in resp.headers

    @staticmethod
    def _seconds_until_allowed(resp: requests.Response) -> float:
        if "retry-after" in resp.headers:
            return float(resp.headers["retry-after"])
        reset = float(resp.headers.get("x-ratelimit-reset", time.time() + 60))
        return max(reset - time.time(), 0) + 1
