"""Helpers for parsing native enhancer CLI output.

Native coding agents are chatty and often wrap the requested enhancement in
logs, markdown fences, or JSON.  These helpers keep parsing strict enough to
avoid accepting raw logs as an enhancement, while supporting the output shapes
we intentionally ask agents to produce.
"""

from __future__ import annotations

import json
import re
from typing import Any


def clean_title(text: str) -> str:
    title = (text or "").strip()
    title = re.sub(r"^[|`\s]+", "", title)
    title = re.sub(r"[|`\s]+$", "", title)
    return re.sub(r"\s+", " ", title).strip()


def clean_body(text: str) -> str:
    body = (text or "").strip()
    fence = re.fullmatch(r"```(?:markdown|md|text)?\s*([\s\S]*?)\s*```", body)
    if fence:
        body = fence.group(1).strip()
    return body


def is_placeholder_title(title: str) -> bool:
    value = (title or "").strip().lower()
    return not value or any(
        token in value
        for token in (
            "<improved single-line title>",
            "improved single-line title",
            "<improved single line title>",
            "improved single line title",
            "<title>",
            "enhanced_title:",
        )
    )


def is_placeholder_body(body: str) -> bool:
    value = (body or "").strip().lower()
    return not value or any(
        token in value
        for token in (
            "<improved body as markdown>",
            "improved body as markdown",
            "enhanced_body:",
        )
    )


def _score(title: str, body: str, fallback_title: str, fallback_body: str) -> int:
    score = 0
    if is_placeholder_title(title):
        score -= 3
    else:
        score += 1
        if title.strip() != fallback_title.strip():
            score += 2

    if is_placeholder_body(body):
        score -= 3
    else:
        score += 2
        if body.strip() != fallback_body.strip():
            score += 4
        if len(body.strip()) >= 80:
            score += 1
    return score


def _pick_best(
    candidates: list[tuple[str, str, str]], fallback_title: str, fallback_body: str
) -> tuple[str, str, str]:
    best = (fallback_title, fallback_body, "fallback")
    best_score = _score(best[0], best[1], fallback_title, fallback_body)

    for raw_title, raw_body, source in candidates:
        title = clean_title(raw_title)
        body = clean_body(raw_body)
        if is_placeholder_title(title):
            title = fallback_title
        if is_placeholder_body(body):
            body = fallback_body
        score = _score(title, body, fallback_title, fallback_body)
        if score > best_score:
            best = (title, body, source)
            best_score = score

    return best


def _candidate_from_mapping(obj: Any, source: str) -> tuple[str, str, str] | None:
    if not isinstance(obj, dict):
        return None
    title = (
        obj.get("enhanced_title")
        or obj.get("ENHANCED_TITLE")
        or obj.get("title")
        or obj.get("improved_title")
    )
    body = (
        obj.get("enhanced_body")
        or obj.get("ENHANCED_BODY")
        or obj.get("body")
        or obj.get("improved_body")
        or obj.get("problem_statement")
    )
    if isinstance(title, str) and isinstance(body, str):
        return title, body, source
    return None


def _json_candidates(text: str) -> list[tuple[str, str, str]]:
    candidates: list[tuple[str, str, str]] = []
    decoder = json.JSONDecoder()

    snippets = re.findall(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
    snippets.append(text)
    for snippet in snippets:
        for idx, char in enumerate(snippet):
            if char != "{":
                continue
            try:
                obj, _ = decoder.raw_decode(snippet[idx:])
            except json.JSONDecodeError:
                continue
            candidate = _candidate_from_mapping(obj, "json")
            if candidate:
                candidates.append(candidate)
    return candidates


def parse_enhanced_output(
    text: str, fallback_title: str, fallback_body: str
) -> tuple[str, str, str]:
    """Return ``(title, body, source)`` parsed from native enhancer output."""
    if not text:
        return fallback_title, fallback_body, "empty"

    candidates: list[tuple[str, str, str]] = []
    title_marker = r"ENHANCED[_\s-]*TITLE\s*[:=]\s*"
    body_marker = r"ENHANCED[_\s-]*BODY\s*[:=]\s*"

    strict = re.compile(
        rf"---\s*{title_marker}(.*?)\s*{body_marker}\r?\n([\s\S]*?)\s*---",
        re.IGNORECASE,
    )
    loose = re.compile(
        rf"{title_marker}(.*?)\s*{body_marker}\r?\n"
        r"([\s\S]*?)(?=(?:\r?\n){0,2}---\s*(?:\r?\n|$)|ENHANCED[_\s-]*TITLE\s*[:=]|$)",
        re.IGNORECASE,
    )

    for match in strict.finditer(text):
        candidates.append((match.group(1), match.group(2), "strict_markers"))
    for match in loose.finditer(text):
        candidates.append((match.group(1), match.group(2), "loose_markers"))
    candidates.extend(_json_candidates(text))

    return _pick_best(candidates, fallback_title, fallback_body)
