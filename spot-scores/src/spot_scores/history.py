"""Optional thin local persistence of runs as JSONL, for trend lookup."""

import json
from dataclasses import asdict
from pathlib import Path

from spot_scores.scoring import ScoreRecord

DEFAULT_PATH = Path.home() / ".spot-scores" / "history.jsonl"


def save_run(
    records: list[ScoreRecord],
    meta: dict,
    timestamp: str,
    path: Path | None = None,
) -> None:
    """Append one run as a JSON line, creating the directory if needed."""
    path = path or DEFAULT_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": timestamp,
        "meta": meta,
        "scores": [asdict(r) for r in records],
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry) + "\n")


def load_runs(
    meta_filter: dict | None = None,
    path: Path | None = None,
) -> list[dict]:
    """Read run dicts, optionally filtered by a meta subset match."""
    path = path or DEFAULT_PATH
    if not path.exists():
        return []
    runs = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            run = json.loads(line)
            if meta_filter:
                meta = run.get("meta", {})
                if any(meta.get(k) != v for k, v in meta_filter.items()):
                    continue
            runs.append(run)
    return runs
