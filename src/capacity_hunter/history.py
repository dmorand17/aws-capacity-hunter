"""Optional thin local persistence of runs as JSONL, for trend lookup."""

import json
from dataclasses import asdict
from pathlib import Path

from capacity_hunter.reserve import ReservationResult
from capacity_hunter.scoring import ScoreRecord

DEFAULT_PATH = Path.home() / ".capacity-hunter" / "history.jsonl"
LEGACY_PATH = Path.home() / ".spot-scores" / "history.jsonl"


def _append(entry: dict, path: Path | None) -> None:
    """Write one entry as a JSON line, creating the directory if needed."""
    path = path or DEFAULT_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry) + "\n")


def _read_jsonl(
    path: Path,
    meta_filter: dict | None,
    kind: str | None,
) -> list[dict]:
    """Read run dicts from one JSONL file, applying kind/meta filters.

    Entries written before the "kind" field are treated as "scores".
    """
    if not path.exists():
        return []
    runs = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            run = json.loads(line)
            if kind and run.get("kind", "scores") != kind:
                continue
            if meta_filter:
                meta = run.get("meta", {})
                if any(meta.get(k) != v for k, v in meta_filter.items()):
                    continue
            runs.append(run)
    return runs


def save_run(
    records: list[ScoreRecord],
    meta: dict,
    timestamp: str,
    path: Path | None = None,
) -> None:
    """Append one score run as a JSON line."""
    _append(
        {
            "kind": "scores",
            "timestamp": timestamp,
            "meta": meta,
            "scores": [asdict(r) for r in records],
        },
        path,
    )


def save_reservation(
    result: ReservationResult,
    meta: dict,
    timestamp: str,
    path: Path | None = None,
) -> None:
    """Append one successful reservation as a JSON line."""
    _append(
        {
            "kind": "reserve",
            "timestamp": timestamp,
            "meta": meta,
            "reservation": asdict(result),
        },
        path,
    )


def load_runs(
    meta_filter: dict | None = None,
    kind: str | None = None,
    path: Path | None = None,
) -> list[dict]:
    """Read run dicts, optionally filtered by kind and a meta subset match.

    When no explicit ``path`` is given, the legacy ``~/.spot-scores`` history
    is read first (so older runs still show up), followed by the current
    ``~/.capacity-hunter`` history. An explicit ``path`` reads only that file.
    """
    if path is not None:
        return _read_jsonl(path, meta_filter, kind)
    return _read_jsonl(LEGACY_PATH, meta_filter, kind) + _read_jsonl(
        DEFAULT_PATH, meta_filter, kind
    )
