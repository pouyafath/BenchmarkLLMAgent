"""
Thread-safe GitHub multi-token client.

Rotates through multiple GitHub personal access tokens to avoid
API rate limits during data collection and benchmark execution.
"""

import os
import time
import threading
from pathlib import Path
from typing import List, Optional

import requests

ROOT = Path(__file__).resolve().parents[2]
TOKEN_FILE = ROOT / ".secrets" / "github_tokens.txt"


def load_github_tokens() -> List[str]:
    """Read GitHub tokens from the environment or .secrets/, never from source.

    Four scripts previously carried their token lists inline, which put live
    credentials in the repository and in every clone of its history. Tokens now come
    from GITHUB_TOKENS (comma-separated) or .secrets/github_tokens.txt, one per line,
    blank lines and # comments ignored. .secrets/ is gitignored.
    """
    env = os.environ.get("GITHUB_TOKENS", "")
    toks = [t.strip() for t in env.split(",") if t.strip()]
    if toks:
        return toks
    if TOKEN_FILE.exists():
        toks = [l.strip() for l in TOKEN_FILE.read_text().splitlines()
                if l.strip() and not l.startswith("#")]
    if not toks:
        raise RuntimeError(
            f"No GitHub tokens available. Set GITHUB_TOKENS=tok1,tok2 or write one per "
            f"line to {TOKEN_FILE} (gitignored). Tokens must never be hard-coded."
        )
    return toks


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
