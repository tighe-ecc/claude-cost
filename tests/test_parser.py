"""Tests against a synthetic ~/.claude tree."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from claude_cost.parser import iter_records, load_dataframe


def _write_jsonl(path: Path, entries: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for entry in entries:
            fh.write(json.dumps(entry) + "\n")


def _make_assistant(
    *,
    ts: str,
    session: str,
    cwd: str,
    model: str = "claude-opus-4-7",
    input_tokens: int = 10,
    output_tokens: int = 100,
    cache_creation: int = 50,
    cache_read: int = 200,
    request_id: str | None = None,
) -> dict:
    return {
        "type": "assistant",
        "timestamp": ts,
        "sessionId": session,
        "cwd": cwd,
        "requestId": request_id or f"req-{session}-{ts}",
        "message": {
            "model": model,
            "id": f"msg-{ts}",
            "role": "assistant",
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cache_creation_input_tokens": cache_creation,
                "cache_read_input_tokens": cache_read,
                "service_tier": "standard",
            },
        },
    }


@pytest.fixture()
def fake_claude(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "claude"
    monkeypatch.setenv("CLAUDE_HOME", str(root))
    projects = root / "projects"
    _write_jsonl(
        projects / "-Users-alice-repo-a" / "session1.jsonl",
        [
            {"type": "permission-mode", "permissionMode": "default", "sessionId": "session1"},
            _make_assistant(ts="2026-05-01T10:00:00Z", session="session1", cwd="/Users/alice/repo-a"),
            _make_assistant(
                ts="2026-05-01T10:05:00Z", session="session1", cwd="/Users/alice/repo-a",
                model="claude-haiku-4-5", output_tokens=50,
            ),
            {"type": "user", "timestamp": "2026-05-01T10:01:00Z"},
        ],
    )
    _write_jsonl(
        projects / "-Users-alice-repo-b" / "session2.jsonl",
        [
            _make_assistant(ts="2026-05-02T12:00:00Z", session="session2", cwd="/Users/alice/repo-b"),
            _make_assistant(
                ts="2026-05-02T12:05:00Z", session="session2", cwd="/Users/alice/repo-b",
                request_id="dup-1",
            ),
            _make_assistant(
                ts="2026-05-02T12:06:00Z", session="session2", cwd="/Users/alice/repo-b",
                request_id="dup-1",  # duplicate — should be deduped
            ),
        ],
    )
    return root


def test_iter_records_collects_all_assistant_turns(fake_claude: Path) -> None:
    records = list(iter_records())
    assert len(records) == 4  # 2 from repo-a + 2 from repo-b after dedup


def test_dedup_by_request_id(fake_claude: Path) -> None:
    records = list(iter_records())
    request_ids = [r.request_id for r in records]
    assert request_ids.count("dup-1") == 1


def test_filter_by_cwd(fake_claude: Path) -> None:
    records = list(iter_records(cwd_filter="/Users/alice/repo-a"))
    assert len(records) == 2
    assert all(r.cwd == "/Users/alice/repo-a" for r in records)


def test_load_dataframe_shape_and_totals(fake_claude: Path) -> None:
    df = load_dataframe()
    assert not df.empty
    assert {"input_tokens", "output_tokens", "cache_creation_tokens",
            "cache_read_tokens", "total_tokens"}.issubset(df.columns)
    assert df["total_input_tokens"].iloc[0] == 10 + 50 + 200
    assert df["total_tokens"].iloc[0] == 10 + 50 + 200 + 100


def test_empty_when_no_projects(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLAUDE_HOME", str(tmp_path / "empty"))
    df = load_dataframe()
    assert df.empty
    assert "total_tokens" in df.columns
