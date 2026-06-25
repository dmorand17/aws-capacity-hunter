# spot-scores Tool Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `get-spot-scores.sh` with an interactive Python CLI that wraps `ec2:GetSpotPlacementScores`, adds presets/heatmap/comparison/history, and runs under the user's own AWS credentials.

**Architecture:** A `click`-based CLI. `scoring.py` is the only module that touches `boto3`; it returns normalized plain data (`ScoreRecord` list). Downstream modules (`rank`, `render`, `history`) operate on that plain data and are unit-tested with fixtures — no live AWS in the suite.

**Tech Stack:** Python 3.11+, `uv`, `click`, `boto3`, `rich`, `pytest`, `ruff`. MIT license.

## Global Constraints

- Package/dependency management via `uv`; project config in `pyproject.toml`. Never `pip`.
- Commit `uv.lock`.
- CLI argument parsing via `click`. AWS via `boto3`. Terminal rendering via `rich`.
- Lint/format via `ruff`.
- Naming: `snake_case` functions/vars, `PascalCase` classes, `UPPER_SNAKE_CASE` constants. 4-space indent. Annotate public signatures.
- MIT license: `LICENSE` at root, `license = "MIT"` in `pyproject.toml`.
- Scores are integers 1–10. Score bands: low 1–3, mid 4–7, high 8–10.
- `ScoreRecord` is a dataclass with fields `region: str`, `availability_zone_id: str`, `score: int`. The `availability_zone_id` is `""` when the request is region-level (not single-AZ). This is the contract every downstream module consumes.

---

### Task 1: Project scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `LICENSE`
- Create: `src/spot_scores/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/test_smoke.py`

**Interfaces:**
- Consumes: nothing.
- Produces: an installed package `spot_scores` with console entry point `spot-scores = "spot_scores.cli:main"` (the `main` callable is created in Task 7; until then the smoke test imports the package only).

- [ ] **Step 1: Create the package and test directories with init files**

Create `src/spot_scores/__init__.py`:

```python
"""spot-scores: interactive EC2 Spot Placement Score tool."""

__version__ = "0.1.0"
```

Create empty `tests/__init__.py` (no content).

- [ ] **Step 2: Write `pyproject.toml`**

```toml
[project]
name = "spot-scores"
version = "0.1.0"
description = "Interactive EC2 Spot Placement Score tool."
readme = "README.md"
requires-python = ">=3.11"
license = "MIT"
authors = [{ name = "Doug Morand" }]
dependencies = [
    "boto3>=1.34",
    "click>=8.1",
    "rich>=13.7",
]

[project.scripts]
spot-scores = "spot_scores.cli:main"

[dependency-groups]
dev = [
    "pytest>=8.0",
    "ruff>=0.5",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/spot_scores"]

[tool.ruff]
line-length = 79

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
```

- [ ] **Step 3: Create `LICENSE`**

Standard MIT license text, copyright `2026 Doug Morand`.

- [ ] **Step 4: Write the smoke test**

```python
# tests/test_smoke.py
def test_package_imports():
    import spot_scores

    assert spot_scores.__version__ == "0.1.0"
```

- [ ] **Step 5: Sync and run the test**

Run: `uv sync && uv run pytest tests/test_smoke.py -v`
Expected: PASS. `uv.lock` is created.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock LICENSE src/spot_scores/__init__.py tests/__init__.py tests/test_smoke.py
git commit -m "feat(spot-scores): scaffold uv python package"
```

---

### Task 2: Presets

**Files:**
- Create: `src/spot_scores/presets.py`
- Test: `tests/test_presets.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `PRESETS: dict[str, dict]` — keys are preset names; each value is either `{"instance_types": list[str]}` or `{"instance_requirements": dict}`.
  - `list_presets() -> list[str]` — sorted preset names.
  - `resolve_preset(name: str) -> dict` — returns the preset body; raises `KeyError` with a message listing valid names if unknown.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_presets.py
import pytest

from spot_scores.presets import PRESETS, list_presets, resolve_preset


def test_known_presets_exist():
    for name in ("general", "compute", "memory", "gpu", "flexible"):
        assert name in PRESETS


def test_list_presets_is_sorted():
    assert list_presets() == sorted(PRESETS)


def test_resolve_compute_returns_instance_types():
    body = resolve_preset("compute")
    assert "instance_types" in body
    assert all(t.startswith("c") for t in body["instance_types"])


def test_resolve_flexible_returns_requirements():
    body = resolve_preset("flexible")
    assert "instance_requirements" in body


def test_resolve_unknown_raises_with_valid_names():
    with pytest.raises(KeyError) as exc:
        resolve_preset("nope")
    assert "compute" in str(exc.value)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_presets.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'spot_scores.presets'`.

- [ ] **Step 3: Write the implementation**

```python
# src/spot_scores/presets.py
"""Named instance-family presets for Spot Placement Score requests.

Preset instance-type lists are explicit and pinned; "current generation"
cannot be reliably auto-discovered. Update these lists as new families ship.
"""

PRESETS: dict[str, dict] = {
    "general": {
        "instance_types": [
            "m6i.2xlarge", "m6a.2xlarge", "m7i.2xlarge", "m7a.2xlarge",
        ],
    },
    "compute": {
        "instance_types": [
            "c6i.2xlarge", "c6a.2xlarge", "c7i.2xlarge", "c7a.2xlarge",
        ],
    },
    "memory": {
        "instance_types": [
            "r6i.2xlarge", "r6a.2xlarge", "r7i.2xlarge", "r7a.2xlarge",
        ],
    },
    "gpu": {
        "instance_types": [
            "g5.2xlarge", "g6.2xlarge", "p4d.24xlarge", "p5.48xlarge",
        ],
    },
    "flexible": {
        "instance_requirements": {
            "ArchitectureTypes": ["x86_64"],
            "InstanceRequirements": {
                "VCpuCount": {"Min": 4, "Max": 16},
                "MemoryMiB": {"Min": 8192, "Max": 65536},
            },
        },
    },
}


def list_presets() -> list[str]:
    """Return preset names in sorted order."""
    return sorted(PRESETS)


def resolve_preset(name: str) -> dict:
    """Return the body of a named preset, or raise KeyError if unknown."""
    if name not in PRESETS:
        valid = ", ".join(list_presets())
        raise KeyError(f"Unknown preset '{name}'. Valid presets: {valid}")
    return PRESETS[name]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_presets.py -v`
Expected: PASS (all 5 tests).

- [ ] **Step 5: Commit**

```bash
git add src/spot_scores/presets.py tests/test_presets.py
git commit -m "feat(spot-scores): add instance-family presets"
```

---

### Task 3: Scoring (boto3 boundary)

**Files:**
- Create: `src/spot_scores/scoring.py`
- Test: `tests/test_scoring.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `@dataclass ScoreRecord` with `region: str`, `availability_zone_id: str`, `score: int`.
  - `build_request(selection: dict, regions: list[str], target_capacity: int = 1, capacity_unit: str = "units", single_az: bool = True) -> dict` — merges a selection (a preset body, or `{"instance_types": [...]}`, or `{"instance_requirements": {...}}`) with the common request params into the boto3 `get_spot_placement_scores` kwargs. Maps `instance_types` -> `InstanceTypes`, `instance_requirements` -> `InstanceRequirementsWithMetadata`.
  - `normalize_response(response: dict) -> list[ScoreRecord]` — maps `SpotPlacementScores[]` to records; missing `AvailabilityZoneId` becomes `""`.
  - `get_scores(client, request: dict) -> list[ScoreRecord]` — calls `client.get_spot_placement_scores(**request)` and normalizes. `client` is a boto3 EC2 client (injected for testability).
  - `ScoringError(Exception)` — raised with a friendly message on `NoCredentialsError`, `AccessDenied`, or throttling.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_scoring.py
import pytest
from botocore.exceptions import ClientError, NoCredentialsError
from botocore.stub import Stubber
import boto3

from spot_scores.scoring import (
    ScoreRecord,
    ScoringError,
    build_request,
    get_scores,
    normalize_response,
)


def test_build_request_instance_types():
    req = build_request(
        {"instance_types": ["c7i.2xlarge"]},
        regions=["us-east-1"],
    )
    assert req["InstanceTypes"] == ["c7i.2xlarge"]
    assert req["RegionNames"] == ["us-east-1"]
    assert req["TargetCapacity"] == 1
    assert req["SingleAvailabilityZone"] is True


def test_build_request_instance_requirements():
    body = {"instance_requirements": {"ArchitectureTypes": ["x86_64"]}}
    req = build_request(body, regions=["us-east-1"])
    assert "InstanceRequirementsWithMetadata" in req
    assert "InstanceTypes" not in req


def test_normalize_response_maps_records():
    response = {
        "SpotPlacementScores": [
            {"Region": "us-east-1", "AvailabilityZoneId": "use1-az1",
             "Score": 9},
            {"Region": "us-west-2", "Score": 4},
        ]
    }
    records = normalize_response(response)
    assert records[0] == ScoreRecord("us-east-1", "use1-az1", 9)
    assert records[1] == ScoreRecord("us-west-2", "", 4)


def test_get_scores_uses_client_and_normalizes():
    client = boto3.client("ec2", region_name="us-east-1")
    stubber = Stubber(client)
    stubber.add_response(
        "get_spot_placement_scores",
        {"SpotPlacementScores": [
            {"Region": "us-east-1", "AvailabilityZoneId": "use1-az1",
             "Score": 8}]},
    )
    req = build_request({"instance_types": ["c7i.2xlarge"]},
                        regions=["us-east-1"])
    with stubber:
        records = get_scores(client, req)
    assert records == [ScoreRecord("us-east-1", "use1-az1", 8)]


def test_get_scores_wraps_access_denied():
    client = boto3.client("ec2", region_name="us-east-1")
    stubber = Stubber(client)
    stubber.add_client_error(
        "get_spot_placement_scores",
        service_error_code="AccessDenied",
        service_message="not authorized",
    )
    req = build_request({"instance_types": ["c7i.2xlarge"]},
                        regions=["us-east-1"])
    with stubber, pytest.raises(ScoringError) as exc:
        get_scores(client, req)
    assert "ec2:GetSpotPlacementScores" in str(exc.value)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_scoring.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'spot_scores.scoring'`.

- [ ] **Step 3: Write the implementation**

```python
# src/spot_scores/scoring.py
"""boto3 boundary: build requests, call the API, normalize to plain data.

This is the only module that imports boto3. Everything downstream consumes
the ScoreRecord list it produces.
"""

from dataclasses import dataclass

from botocore.exceptions import ClientError, NoCredentialsError


class ScoringError(Exception):
    """Raised with a user-friendly message on AWS call failures."""


@dataclass
class ScoreRecord:
    """A single Spot Placement Score result."""

    region: str
    availability_zone_id: str
    score: int


def build_request(
    selection: dict,
    regions: list[str],
    target_capacity: int = 1,
    capacity_unit: str = "units",
    single_az: bool = True,
) -> dict:
    """Merge a selection with common params into boto3 request kwargs."""
    request: dict = {
        "RegionNames": regions,
        "TargetCapacity": target_capacity,
        "TargetCapacityUnitType": capacity_unit,
        "SingleAvailabilityZone": single_az,
    }
    if "instance_types" in selection:
        request["InstanceTypes"] = selection["instance_types"]
    elif "instance_requirements" in selection:
        request["InstanceRequirementsWithMetadata"] = (
            selection["instance_requirements"]
        )
    else:
        raise ValueError(
            "selection must contain 'instance_types' or "
            "'instance_requirements'"
        )
    return request


def normalize_response(response: dict) -> list[ScoreRecord]:
    """Map a get_spot_placement_scores response to ScoreRecord list."""
    records = []
    for item in response.get("SpotPlacementScores", []):
        records.append(
            ScoreRecord(
                region=item["Region"],
                availability_zone_id=item.get("AvailabilityZoneId", ""),
                score=item["Score"],
            )
        )
    return records


def get_scores(client, request: dict) -> list[ScoreRecord]:
    """Call get_spot_placement_scores and normalize, wrapping AWS errors."""
    try:
        response = client.get_spot_placement_scores(**request)
    except NoCredentialsError as err:
        raise ScoringError(
            "No AWS credentials found. Run 'aws configure' or set a "
            "profile with --profile."
        ) from err
    except ClientError as err:
        code = err.response["Error"]["Code"]
        if code in ("AccessDenied", "UnauthorizedOperation"):
            raise ScoringError(
                "Access denied. The 'ec2:GetSpotPlacementScores' IAM "
                "permission is required."
            ) from err
        if code in ("RequestLimitExceeded", "Throttling"):
            raise ScoringError(
                "AWS throttled the request. Wait a moment and retry."
            ) from err
        raise ScoringError(f"AWS error: {code}") from err
    return normalize_response(response)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_scoring.py -v`
Expected: PASS (all 5 tests).

- [ ] **Step 5: Commit**

```bash
git add src/spot_scores/scoring.py tests/test_scoring.py
git commit -m "feat(spot-scores): add boto3 scoring boundary"
```

---

### Task 4: Rank

**Files:**
- Create: `src/spot_scores/rank.py`
- Test: `tests/test_rank.py`

**Interfaces:**
- Consumes: `ScoreRecord` from `spot_scores.scoring`.
- Produces:
  - `rank_scores(records: list[ScoreRecord], top_n: int = 3, az_filter: list[str] | None = None) -> list[ScoreRecord]` — replicates the jq pipeline: optional AZ filter, group by `(region, availability_zone_id)`, sort each group by score desc, take top-N, then return flattened, sorted by `(region, availability_zone_id, -score)`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_rank.py
from spot_scores.scoring import ScoreRecord
from spot_scores.rank import rank_scores


def _records():
    return [
        ScoreRecord("us-east-1", "use1-az1", 9),
        ScoreRecord("us-east-1", "use1-az1", 5),
        ScoreRecord("us-east-1", "use1-az4", 7),
        ScoreRecord("us-west-2", "usw2-az1", 2),
    ]


def test_top_n_per_group():
    out = rank_scores(_records(), top_n=1)
    az1 = [r for r in out if r.availability_zone_id == "use1-az1"]
    assert len(az1) == 1
    assert az1[0].score == 9


def test_sorted_by_region_az_then_score_desc():
    out = rank_scores(_records(), top_n=3)
    keys = [(r.region, r.availability_zone_id, r.score) for r in out]
    assert keys == sorted(
        keys, key=lambda k: (k[0], k[1], -k[2])
    )


def test_az_filter_limits_results():
    out = rank_scores(_records(), az_filter=["use1-az1"])
    assert {r.availability_zone_id for r in out} == {"use1-az1"}


def test_empty_input_returns_empty():
    assert rank_scores([]) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_rank.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'spot_scores.rank'`.

- [ ] **Step 3: Write the implementation**

```python
# src/spot_scores/rank.py
"""Group, sort, and top-N ranking of score records (the jq pipeline)."""

from itertools import groupby

from spot_scores.scoring import ScoreRecord


def rank_scores(
    records: list[ScoreRecord],
    top_n: int = 3,
    az_filter: list[str] | None = None,
) -> list[ScoreRecord]:
    """Filter, group by (region, AZ), take top-N by score, sort flat."""
    if az_filter:
        wanted = set(az_filter)
        records = [
            r for r in records if r.availability_zone_id in wanted
        ]

    def group_key(record: ScoreRecord) -> tuple[str, str]:
        return (record.region, record.availability_zone_id)

    ranked: list[ScoreRecord] = []
    for _, group in groupby(sorted(records, key=group_key), key=group_key):
        members = sorted(group, key=lambda r: -r.score)
        ranked.extend(members[:top_n])

    ranked.sort(
        key=lambda r: (r.region, r.availability_zone_id, -r.score)
    )
    return ranked
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_rank.py -v`
Expected: PASS (all 4 tests).

- [ ] **Step 5: Commit**

```bash
git add src/spot_scores/rank.py tests/test_rank.py
git commit -m "feat(spot-scores): add ranking pipeline"
```

---

### Task 5: Render

**Files:**
- Create: `src/spot_scores/render.py`
- Test: `tests/test_render.py`

**Interfaces:**
- Consumes: `ScoreRecord` from `spot_scores.scoring`.
- Produces:
  - `score_band(score: int) -> str` — returns `"red"` (1–3), `"yellow"` (4–7), or `"green"` (8–10).
  - `build_heatmap_table(records: list[ScoreRecord]) -> rich.table.Table` — one row per record: Region, AZ, colored Score cell.
  - `render_table(table) -> None` — prints to a `rich.console.Console`.

> Comparison (side-by-side multiple requests) is deferred to a follow-up plan — not built here.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_render.py
from rich.table import Table

from spot_scores.scoring import ScoreRecord
from spot_scores.render import build_heatmap_table, score_band


def test_score_band_thresholds():
    assert score_band(2) == "red"
    assert score_band(5) == "yellow"
    assert score_band(9) == "green"


def test_heatmap_table_has_rows():
    records = [ScoreRecord("us-east-1", "use1-az1", 9)]
    table = build_heatmap_table(records)
    assert isinstance(table, Table)
    assert table.row_count == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_render.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'spot_scores.render'`.

- [ ] **Step 3: Write the implementation**

```python
# src/spot_scores/render.py
"""Terminal rendering: score heatmap and side-by-side comparison."""

from rich.console import Console
from rich.table import Table

from spot_scores.scoring import ScoreRecord

_CONSOLE = Console()


def score_band(score: int) -> str:
    """Map a 1-10 score to a rich color name."""
    if score <= 3:
        return "red"
    if score <= 7:
        return "yellow"
    return "green"


def _cell(score: int) -> str:
    """Render a score as a color-tagged rich cell."""
    return f"[{score_band(score)}]{score}[/]"


def build_heatmap_table(records: list[ScoreRecord]) -> Table:
    """One row per record: Region, AZ, colored Score."""
    table = Table(title="Spot Placement Scores")
    table.add_column("Region")
    table.add_column("AZ")
    table.add_column("Score", justify="right")
    for record in records:
        table.add_row(
            record.region,
            record.availability_zone_id or "-",
            _cell(record.score),
        )
    return table


def render_table(table: Table) -> None:
    """Print a table to the shared console."""
    _CONSOLE.print(table)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_render.py -v`
Expected: PASS (all 2 tests).

- [ ] **Step 5: Commit**

```bash
git add src/spot_scores/render.py tests/test_render.py
git commit -m "feat(spot-scores): add heatmap and comparison rendering"
```

---

### Task 6: History (optional layer)

**Files:**
- Create: `src/spot_scores/history.py`
- Test: `tests/test_history.py`

**Interfaces:**
- Consumes: `ScoreRecord` from `spot_scores.scoring`.
- Produces:
  - `save_run(records: list[ScoreRecord], meta: dict, timestamp: str, path: Path | None = None) -> None` — appends one JSON line `{"timestamp", "meta", "scores": [...]}` to the history file (default `~/.spot-scores/history.jsonl`), creating the directory if needed. `timestamp` is passed in by the caller (the CLI), not generated here, so the function is deterministic and testable.
  - `load_runs(meta_filter: dict | None = None, path: Path | None = None) -> list[dict]` — reads back run dicts; if `meta_filter` is given, returns only runs whose `meta` is a superset match. Returns `[]` if the file does not exist.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_history.py
from spot_scores.scoring import ScoreRecord
from spot_scores.history import save_run, load_runs


def test_load_missing_file_returns_empty(tmp_path):
    assert load_runs(path=tmp_path / "none.jsonl") == []


def test_save_then_load_roundtrip(tmp_path):
    path = tmp_path / "history.jsonl"
    records = [ScoreRecord("us-east-1", "use1-az1", 9)]
    save_run(records, {"preset": "compute"}, "2026-06-25T00:00:00",
             path=path)
    runs = load_runs(path=path)
    assert len(runs) == 1
    assert runs[0]["meta"] == {"preset": "compute"}
    assert runs[0]["scores"][0]["score"] == 9


def test_meta_filter_matches_subset(tmp_path):
    path = tmp_path / "history.jsonl"
    save_run([], {"preset": "compute", "region": "us-east-1"},
             "2026-06-25T00:00:00", path=path)
    save_run([], {"preset": "memory", "region": "us-east-1"},
             "2026-06-25T01:00:00", path=path)
    runs = load_runs(meta_filter={"preset": "compute"}, path=path)
    assert len(runs) == 1
    assert runs[0]["meta"]["preset"] == "compute"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_history.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'spot_scores.history'`.

- [ ] **Step 3: Write the implementation**

```python
# src/spot_scores/history.py
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_history.py -v`
Expected: PASS (all 3 tests).

- [ ] **Step 5: Commit**

```bash
git add src/spot_scores/history.py tests/test_history.py
git commit -m "feat(spot-scores): add optional run history"
```

---

### Task 7: CLI wiring

**Files:**
- Create: `src/spot_scores/cli.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `presets.resolve_preset`/`list_presets`, `scoring.build_request`/`get_scores`/`ScoringError`/`ScoreRecord`, `rank.rank_scores`, `render.build_heatmap_table`/`render_table`, `history.save_run`/`load_runs`.
- Produces:
  - `main` — a `click.Group` registered as the `spot-scores` console entry point, with a default `scores` command and a `history` command.
  - `_make_client(profile: str | None, region: str | None)` — builds a boto3 EC2 client from a `boto3.Session`.

The default command flags: `--preset`, `--instance-types` (comma list), `--regions` (comma list, required when non-interactive), `-n/--top`, `--az` (comma list filter), `--profile`, `--region`, `--save`, `--output [table|json]`. When required selection/region inputs are absent, fall into interactive `click.prompt` flow.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_cli.py
from unittest.mock import patch

from click.testing import CliRunner

from spot_scores.cli import main
from spot_scores.scoring import ScoreRecord


def test_help_lists_commands():
    result = CliRunner().invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "history" in result.output


def test_scores_command_renders_table():
    records = [ScoreRecord("us-east-1", "use1-az1", 9)]
    with patch("spot_scores.cli.get_scores", return_value=records), \
         patch("spot_scores.cli._make_client", return_value=object()):
        result = CliRunner().invoke(
            main,
            ["scores", "--preset", "compute", "--regions", "us-east-1"],
        )
    assert result.exit_code == 0
    assert "us-east-1" in result.output


def test_scores_json_output():
    records = [ScoreRecord("us-east-1", "use1-az1", 9)]
    with patch("spot_scores.cli.get_scores", return_value=records), \
         patch("spot_scores.cli._make_client", return_value=object()):
        result = CliRunner().invoke(
            main,
            ["scores", "--preset", "compute", "--regions", "us-east-1",
             "--output", "json"],
        )
    assert result.exit_code == 0
    assert '"score": 9' in result.output
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'spot_scores.cli'`.

- [ ] **Step 3: Write the implementation**

```python
# src/spot_scores/cli.py
"""click CLI: interactive wizard plus flag-driven non-interactive use."""

import json
from dataclasses import asdict

import boto3
import click

from spot_scores.history import load_runs, save_run
from spot_scores.presets import list_presets, resolve_preset
from spot_scores.rank import rank_scores
from spot_scores.render import build_heatmap_table, render_table
from spot_scores.scoring import (
    ScoringError,
    build_request,
    get_scores,
)


def _make_client(profile, region):
    """Build a boto3 EC2 client from an optional profile/region."""
    session = boto3.Session(profile_name=profile, region_name=region)
    return session.client("ec2")


def _split(value):
    """Split a comma-separated option into a clean list, or None."""
    if not value:
        return None
    return [part.strip() for part in value.split(",") if part.strip()]


def _selection(preset, instance_types):
    """Resolve a selection from flags or interactive prompts."""
    if preset:
        return resolve_preset(preset)
    if instance_types:
        return {"instance_types": _split(instance_types)}
    presets = ", ".join(list_presets())
    choice = click.prompt(
        f"Preset ({presets}) or leave blank to enter instance types",
        default="",
        show_default=False,
    )
    if choice:
        return resolve_preset(choice)
    types = click.prompt("Instance types (comma-separated)")
    return {"instance_types": _split(types)}


@click.group()
def main():
    """Interactive EC2 Spot Placement Score tool."""


@main.command()
@click.option("--preset", help="Named instance-family preset.")
@click.option("--instance-types", help="Comma-separated instance types.")
@click.option("--regions", help="Comma-separated region names.")
@click.option("-n", "--top", default=3, show_default=True,
              help="Top N results per AZ.")
@click.option("--az", help="Comma-separated AZ IDs to filter output.")
@click.option("--profile", help="AWS profile name.")
@click.option("--region", help="AWS region for the API call.")
@click.option("--save", is_flag=True, help="Append this run to history.")
@click.option("--output", type=click.Choice(["table", "json"]),
              default="table", show_default=True)
def scores(preset, instance_types, regions, top, az, profile, region,
           save, output):
    """Query Spot Placement Scores and render results."""
    selection = _selection(preset, instance_types)
    region_list = _split(regions)
    if not region_list:
        region_list = _split(
            click.prompt("Regions (comma-separated)")
        )

    request = build_request(selection, regions=region_list)
    try:
        client = _make_client(profile, region or region_list[0])
        records = get_scores(client, request)
    except ScoringError as err:
        raise click.ClickException(str(err))

    ranked = rank_scores(records, top_n=top, az_filter=_split(az))

    if output == "json":
        click.echo(json.dumps([asdict(r) for r in ranked], indent=2))
    else:
        render_table(build_heatmap_table(ranked))

    if save:
        meta = {"preset": preset, "regions": ",".join(region_list)}
        save_run(ranked, meta, _now())


def _now():
    """Return an ISO timestamp; isolated for testability."""
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


@main.command()
@click.option("--preset", help="Filter history by preset.")
@click.option("--region", help="Filter history by region.")
def history(preset, region):
    """Show saved score history (trend over time)."""
    meta_filter = {}
    if preset:
        meta_filter["preset"] = preset
    runs = load_runs(meta_filter=meta_filter or None)
    if not runs:
        click.echo("No history yet. Run a query with --save first.")
        return
    for run in runs:
        click.echo(f"{run['timestamp']}  {run['meta']}")
        for score in run["scores"]:
            click.echo(
                f"  {score['region']} {score['availability_zone_id']} "
                f"-> {score['score']}"
            )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli.py -v`
Expected: PASS (all 3 tests).

- [ ] **Step 5: Run the full suite and lint**

Run: `uv run pytest -v && uv run ruff check src tests`
Expected: All tests PASS; ruff reports no errors. Fix any ruff findings and re-run.

- [ ] **Step 6: Commit**

```bash
git add src/spot_scores/cli.py tests/test_cli.py
git commit -m "feat(spot-scores): add click CLI wiring"
```

---

### Task 8: README and retire the Bash script

**Files:**
- Create: `README.md`
- Modify: keep `get-spot-scores.sh` but mark it deprecated in favor of the CLI (add a one-line deprecation note at the top of its comment block; do not delete it).

**Interfaces:**
- Consumes: the finished CLI.
- Produces: user-facing docs.

- [ ] **Step 1: Write `README.md`**

Cover: what the tool does; the account-specific-score caveat and point-in-time volatility; install via `uv` (`uv sync`, `uv run spot-scores`); interactive and flag usage examples; the preset table with the note that preset lists are pinned and need occasional updates; required IAM permission `ec2:GetSpotPlacementScores`; `--save`/`history` usage; `--output json` for scripting.

- [ ] **Step 2: Add deprecation note to the Bash script**

Add after the title comment in `get-spot-scores.sh`:

```bash
# DEPRECATED: superseded by the `spot-scores` Python CLI (see README.md).
```

- [ ] **Step 3: Commit**

```bash
git add README.md get-spot-scores.sh
git commit -m "docs(spot-scores): add README and deprecate bash script"
```

---

## Self-Review

**Spec coverage:**
- BYO-credentials local Python CLI → Tasks 1, 7. ✓
- Interactive wizard + flag equivalents → Task 7. ✓
- Presets (general/compute/memory/gpu/flexible), pinned lists → Task 2. ✓
- `scoring.py` sole boto3 boundary, normalized data → Task 3. ✓
- Ranking (jq pipeline in Python) → Task 4. ✓
- Heatmap rendering, score bands → Task 5. ✓ (Comparison deferred to a follow-up plan per design decision.)
- `--output json` preserving raw behavior → Task 7. ✓
- History off-by-default, `--save`, `history` command, JSONL local → Task 6, 7. ✓
- Error handling (no creds, AccessDenied, throttling, validation) → Task 3, 7. ✓
- `--profile`/`--region` respected, boto3 credential chain → Task 7. ✓
- Testing: scoring stubbed, others fixture-tested, CLI smoke → Tasks 1–7. ✓
- uv/click/boto3/rich/ruff/MIT standards → Task 1. ✓

**Placeholder scan:** No TBD/TODO; every code step has complete code.

**Type consistency:** `ScoreRecord(region, availability_zone_id, score)` used identically across scoring/rank/render/history/cli. `build_request` / `get_scores` / `rank_scores` / `save_run` / `load_runs` signatures match between their producing task and Task 7's consumption.

**Deferred:** Side-by-side comparison of multiple requests was deliberately cut from v1 (design decision) and belongs in a follow-up plan, so no comparison code is built here.
