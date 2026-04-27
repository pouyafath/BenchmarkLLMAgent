"""
Thread-safe GitHub multi-token client.

Rotates through multiple GitHub personal access tokens to avoid
API rate limits during data collection and benchmark execution.
"""

import time
import threading
from typing import List, Optional

import requests


class GitHubMultiTokenClient:
    """Round-robin GitHub API client with automatic token rotation on rate limits."""

    def __init__(self, tokens: List[str]):
        self.tokens = tokens
        self.idx = 0
        self._lock = threading.Lock()

    def _get_headers(self) -> dict:
        with self._lock:
            return {
                "Accept": "application/vnd.github+json",
                "Authorization": f"token {self.tokens[self.idx]}",
            }

    def switch(self):
        with self._lock:
            self.idx = (self.idx + 1) % len(self.tokens)

    def get(self, url: str, extra_headers: Optional[dict] = None) -> Optional[requests.Response]:
        for attempt in range(len(self.tokens) * 2):
            h = {**self._get_headers(), **(extra_headers or {})}
            try:
                r = requests.get(url, headers=h, timeout=30)
                if r.status_code in (403, 429):
                    self.switch()
                    with self._lock:
                        if self.idx == 0:
                            time.sleep(60)
                    continue
                return r
            except Exception:
                self.switch()
        return None

    def get_json(self, url: str, extra_headers: Optional[dict] = None) -> Optional[dict]:
        r = self.get(url, extra_headers)
        if r and r.status_code == 200:
            return r.json()
        return None
