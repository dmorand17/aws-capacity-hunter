# Flatten project to repo root and rename package to `capacity_hunter`

## Context

After unifying the two tools into one CLI (PR #3), the project still lives in a
`spot-scores/` subfolder and the Python package is still `src/spot_scores/` —
both misleading now that the command is `capacity-hunter` and the repo only
contains one project. This plan flattens the project to the repo root and
renames the internal package to `capacity_hunter`.

**Decisions (made with the user):**
- **Layout:** flatten the project to the repo root (no nested
  `aws-capacity-hunter/capacity-hunter/`).
- **Package:** rename `src/spot_scores/` → `src/capacity_hunter/`.
- **History path:** write new history to `~/.capacity-hunter/history.jsonl`,
  but still read the legacy `~/.spot-scores/` path if it exists (no data loss).
- **Entry points:** keep both `capacity-hunter` and `spot-scores` (alias) —
  unchanged from PR #3.

Do this on a fresh branch off `main` **after PR #3 merges** (it shares the same
files; doing it before would compound conflicts).

---

## Part 1 — Move the project to the repo root

The repo root currently has: `README.md`, `.gitignore`, `docs/img/`, `legacy/`,
`.claude/`. The project subfolder `spot-scores/` has: `pyproject.toml`,
`uv.lock`, `LICENSE`, `README.md`, `src/spot_scores/`, `tests/`, `docs/specs/`,
`docs/plans/`, `.venv/`, `.python-version` (if present).

Use `git mv` to preserve history. Watch the two **collisions**:

- **`README.md`** — root and `spot-scores/` both have one. The root README is
  the umbrella overview (banner, tagline, command table); the `spot-scores/`
  README is the full usage doc. After flattening there should be **one**
  README at root. Recommended: keep the root README as the canonical one and
  fold any usage detail still only in the project README into it (or keep the
  detailed usage and drop the thin umbrella intro — decide when merging). Do
  **not** silently lose the `reserve`/`scores`/`compare` usage sections.
- **`docs/`** — root has `docs/img/`; project has `docs/specs/` and
  `docs/plans/`. Merge into a single root `docs/` (`docs/img/`, `docs/specs/`,
  `docs/plans/`). This plan file already lives at the target
  `docs/plans/` location.

Concrete moves (from repo root, after PR #3 merge):

```bash
git mv spot-scores/pyproject.toml .
git mv spot-scores/uv.lock .
git mv spot-scores/LICENSE .            # only if root has none; PR #3 added root LICENSE — if so, rm spot-scores/LICENSE instead
git mv spot-scores/src src
git mv spot-scores/tests tests
git mv spot-scores/docs/specs docs/specs
git mv spot-scores/docs/plans/* docs/plans/   # merge, don't clobber this file
git mv spot-scores/.python-version .          # if it exists
# README: merge by hand, then remove the project one
git rm spot-scores/README.md            # after folding its content into root README
rmdir spot-scores/docs/plans spot-scores/docs spot-scores 2>/dev/null
rm -rf spot-scores/.venv                # not tracked; recreated by uv sync
```

Verify nothing is left: `ls spot-scores 2>/dev/null` should be empty/absent and
`git status` should show only renames + the README/docs edits.

---

## Part 2 — Rename the package `spot_scores` → `capacity_hunter`

```bash
git mv src/spot_scores src/capacity_hunter
```

Then rewrite every internal import. Modules with `from spot_scores...` /
`import spot_scores`: `cli.py`, `scoring.py`, `presets.py`, `rank.py`,
`render.py`, `history.py`, `reserve.py` (and `__init__.py` if it references the
name). Tests: `test_cli.py`, `test_scoring.py`, `test_rank.py`, `test_render.py`,
`test_history.py`, `test_presets.py`, `test_reserve.py`, `test_smoke.py`.

Find them all:

```bash
grep -rn 'spot_scores' src tests
```

Two flavors to replace:
- **Imports:** `from spot_scores.X import ...` → `from capacity_hunter.X import ...`
- **Test patch targets:** `patch("spot_scores.cli._make_client")` →
  `patch("capacity_hunter.cli._make_client")` (and `...cli.get_scores`,
  `...cli.poll_for_reservation`, `...cli.list_reservations`,
  `...cli.cancel_reservation`). These are the easy-to-miss ones; the suite will
  fail loudly if any are wrong.

A bulk replace is safe here (the token `spot_scores` is unambiguous):

```bash
grep -rl 'spot_scores' src tests | xargs sed -i '' 's/spot_scores/capacity_hunter/g'
```

(Then eyeball `git diff` — confirm no stray match in a string literal that
shouldn't change.)

---

## Part 3 — Update `pyproject.toml`

- `[project.scripts]` — repoint both entry points to the new module path:
  ```toml
  capacity-hunter = "capacity_hunter.cli:main"
  spot-scores     = "capacity_hunter.cli:main"   # backwards-compat alias
  ```
- `[tool.hatch.build.targets.wheel]` — `packages = ["src/capacity_hunter"]`.
- `[tool.pytest.ini_options]` — `pythonpath = ["src"]` stays correct (still
  `src/`), `testpaths = ["tests"]` stays correct (tests now at root).
- `[project].name` — optionally rename `"spot-scores"` → `"capacity-hunter"`.
  If changed, note `uv tool upgrade/uninstall` now use `capacity-hunter`.

---

## Part 4 — History path migration (`history.py`)

Currently `DEFAULT_PATH = Path.home() / ".spot-scores" / "history.jsonl"`.

- Add `LEGACY_PATH = Path.home() / ".spot-scores" / "history.jsonl"` and set
  `DEFAULT_PATH = Path.home() / ".capacity-hunter" / "history.jsonl"`.
- **Writes** (`save_run`, `save_reservation` via `_append`) always use the new
  `DEFAULT_PATH`.
- **Reads** (`load_runs`) should read the new path **and** the legacy path if it
  exists, concatenating entries (legacy first, or merged) so old history still
  shows up. Keep the `path=` injection for tests; only the default-path branch
  consults the legacy location.
- Add a test: when only the legacy file exists, `load_runs()` still returns its
  entries; when both exist, entries from both are returned.

---

## Part 5 — Docs

- **Root `README.md`** — already references `capacity-hunter` (from PR #3).
  After flattening, fix any paths that pointed into `spot-scores/`:
  - `uv tool install ./spot-scores` → `uv tool install .`
  - `cd spot-scores && uv run capacity-hunter ...` → `uv run capacity-hunter ...`
  - `[spot-scores/README.md](spot-scores/README.md)` link → point at the merged
    usage section in the same README (or wherever usage lives now).
- **`legacy/README.md`** — fix the relative link `../spot-scores/` →
  `../` (or the new usage doc location).
- **`legacy/reserve-capacity/reserve-capacity.sh`** banner — the deprecation
  comment references `../../spot-scores/README.md`; update to the new path.
- **`legacy/spot-scores/get-spot-scores.sh`** banner — references `../README.md`;
  re-point if needed.
- Grep the whole repo for leftover path references:
  ```bash
  grep -rn 'spot-scores/' --include='*.md' --include='*.sh' . | grep -v '^./legacy/spot-scores/'
  ```

---

## Verification

1. `uv sync` from the repo root (no longer `cd spot-scores`).
2. `uv run pytest` — all tests pass (the 53 from PR #3; patch-target renames are
   the main risk — a miss shows as `ModuleNotFoundError` or a failed patch).
3. `uv run ruff check src tests` — clean (line-length 79).
4. `uv run capacity-hunter --help` lists `scores`, `reserve`, `history`;
   `uv run spot-scores --help` (alias) still works.
5. `uv run capacity-hunter reserve -t g6.xlarge --dry-run` prints the plan.
6. History migration: with an existing `~/.spot-scores/history.jsonl`,
   `uv run capacity-hunter history` still shows old entries; a new
   `--save` run writes to `~/.capacity-hunter/history.jsonl`.
7. `uv tool install . && capacity-hunter --help` (global install from root).

## Notes / gotchas

- `.gitignore` at root already covers `.venv/`, `__pycache__/`, etc. — no change
  needed, but confirm the patterns aren't anchored to `spot-scores/`.
- `uv.lock` moves with `pyproject.toml`; `uv sync` will reconcile it.
- Do the move and the rename in **one branch/PR** but consider **two commits**
  (`refactor: flatten project to repo root` then
  `refactor: rename package spot_scores -> capacity_hunter`) so the diff is
  reviewable — git rename detection keeps each step legible.
