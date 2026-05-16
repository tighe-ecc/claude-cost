"""Parse Claude Code session transcripts (~/.claude/projects/**/*.jsonl).

Each transcript line is a JSON object. We only care about `type == "assistant"`
lines that carry a `message.usage` dict — those are the only entries that
record real token spend.

The on-disk layout is::

    ~/.claude/projects/<slug>/<session-uuid>.jsonl

where `<slug>` is the working directory with slashes replaced by dashes. We
prefer the per-line `cwd` field (always present, exact path) when available
and fall back to decoding the slug.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator

import pandas as pd


def default_claude_dir() -> Path:
    """Resolve ~/.claude (override with $CLAUDE_HOME for tests)."""
    return Path(os.environ.get("CLAUDE_HOME", str(Path.home() / ".claude")))


@dataclass(frozen=True)
class UsageRecord:
    """One assistant turn worth of token usage."""

    timestamp: datetime
    session_id: str
    request_id: str | None
    cwd: str | None
    model: str
    input_tokens: int
    output_tokens: int
    cache_creation_tokens: int
    cache_read_tokens: int
    service_tier: str | None

    @property
    def total_input_tokens(self) -> int:
        """Tokens billed as input across all cache tiers."""
        return (
            self.input_tokens + self.cache_creation_tokens + self.cache_read_tokens
        )


def _decode_slug(slug: str) -> str:
    """Best-effort inverse of the slug encoding used in ~/.claude/projects/.

    Claude Code replaces `/` with `-` and (separately) keeps existing dashes
    in the path. There's no perfect inverse, but the slug always starts with
    a single leading `-` (representing the root `/`). We turn every dash that
    sits between two path-component-looking chunks back into a slash.
    """
    if slug.startswith("-"):
        return "/" + slug[1:].replace("-", "/")
    return slug.replace("-", "/")


def _parse_line(raw: str) -> UsageRecord | None:
    """Return a record for one JSONL line, or None if the line has no usage."""
    try:
        entry = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if entry.get("type") != "assistant":
        return None
    msg = entry.get("message")
    if not isinstance(msg, dict):
        return None
    usage = msg.get("usage")
    if not isinstance(usage, dict):
        return None

    ts_raw = entry.get("timestamp")
    if not ts_raw:
        return None
    try:
        # Trailing 'Z' → +00:00 for fromisoformat
        ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
    except ValueError:
        return None

    return UsageRecord(
        timestamp=ts,
        session_id=str(entry.get("sessionId") or ""),
        request_id=entry.get("requestId"),
        cwd=entry.get("cwd"),
        model=str(msg.get("model") or "unknown"),
        input_tokens=int(usage.get("input_tokens") or 0),
        output_tokens=int(usage.get("output_tokens") or 0),
        cache_creation_tokens=int(usage.get("cache_creation_input_tokens") or 0),
        cache_read_tokens=int(usage.get("cache_read_input_tokens") or 0),
        service_tier=usage.get("service_tier"),
    )


def iter_records(
    claude_dir: Path | str | None = None,
    *,
    cwd_filter: str | None = None,
) -> Iterator[UsageRecord]:
    """Yield UsageRecord objects from every transcript under `claude_dir`.

    Args:
        claude_dir: Path to the ~/.claude directory. Defaults to default_claude_dir().
        cwd_filter: If given, only yield records whose `cwd` starts with this
            path (string prefix match after both are absolute). Useful for
            "all tokens spent inside repo X".
    """
    root = Path(claude_dir) if claude_dir else default_claude_dir()
    projects = root / "projects"
    if not projects.is_dir():
        return

    if cwd_filter:
        cwd_filter = str(Path(cwd_filter).expanduser().resolve())

    seen_request_ids: set[str] = set()

    for project_dir in sorted(projects.iterdir()):
        if not project_dir.is_dir():
            continue
        for transcript in sorted(project_dir.glob("*.jsonl")):
            try:
                with transcript.open("r", encoding="utf-8", errors="replace") as fh:
                    for line in fh:
                        rec = _parse_line(line)
                        if rec is None:
                            continue
                        if rec.request_id:
                            if rec.request_id in seen_request_ids:
                                continue
                            seen_request_ids.add(rec.request_id)
                        if cwd_filter and rec.cwd:
                            try:
                                rec_cwd = str(Path(rec.cwd).resolve())
                            except OSError:
                                rec_cwd = rec.cwd
                            if not rec_cwd.startswith(cwd_filter):
                                continue
                        elif cwd_filter and not rec.cwd:
                            continue
                        yield rec
            except OSError:
                continue


def load_dataframe(
    claude_dir: Path | str | None = None,
    *,
    cwd_filter: str | None = None,
) -> pd.DataFrame:
    """Return a pandas DataFrame of every billable assistant turn.

    Columns: timestamp (UTC), session_id, request_id, cwd, model,
    input_tokens, output_tokens, cache_creation_tokens, cache_read_tokens,
    service_tier, total_input_tokens, total_tokens.
    """
    rows: list[dict] = []
    for rec in iter_records(claude_dir, cwd_filter=cwd_filter):
        rows.append(
            {
                "timestamp": rec.timestamp,
                "session_id": rec.session_id,
                "request_id": rec.request_id,
                "cwd": rec.cwd,
                "model": rec.model,
                "input_tokens": rec.input_tokens,
                "output_tokens": rec.output_tokens,
                "cache_creation_tokens": rec.cache_creation_tokens,
                "cache_read_tokens": rec.cache_read_tokens,
                "service_tier": rec.service_tier,
            }
        )
    df = pd.DataFrame(rows)
    if df.empty:
        # Return an empty DF with the expected schema so downstream code
        # doesn't need a special case.
        df = pd.DataFrame(
            columns=[
                "timestamp",
                "session_id",
                "request_id",
                "cwd",
                "model",
                "input_tokens",
                "output_tokens",
                "cache_creation_tokens",
                "cache_read_tokens",
                "service_tier",
            ]
        )
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        df["total_input_tokens"] = 0
        df["total_tokens"] = 0
        return df

    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df["total_input_tokens"] = (
        df["input_tokens"] + df["cache_creation_tokens"] + df["cache_read_tokens"]
    )
    df["total_tokens"] = df["total_input_tokens"] + df["output_tokens"]
    df = df.sort_values("timestamp").reset_index(drop=True)
    return df


def list_repos(claude_dir: Path | str | None = None) -> list[tuple[str, int]]:
    """Distinct cwd values seen across transcripts, with record counts.

    Returns a list of (cwd, n_records) sorted descending by record count.
    Useful for `claude-cost repos` to show users what they can filter on.
    """
    counts: dict[str, int] = {}
    for rec in iter_records(claude_dir):
        key = rec.cwd or "<unknown>"
        counts[key] = counts.get(key, 0) + 1
    return sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
