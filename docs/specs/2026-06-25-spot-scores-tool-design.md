# Design: `spot-scores` — interactive Spot Placement Score tool

**Date:** 2026-06-25
**Status:** Approved (design); pending implementation plan

## Problem

`get-spot-scores.sh` helps users understand where they can get EC2 Spot
capacity by wrapping `ec2:GetSpotPlacementScores`. It works, but is hard for
external AWS customers to use:

1. Requires hand-authoring AWS CLI YAML (knowing the API schema:
   `InstanceRequirementsWithMetadata`, `TargetCapacityUnitType`, etc.).
2. Requires local tooling (AWS CLI v2, `jq`) and configured credentials.
3. Output is one-shot flat text; no comparison, no visualization, no trend.
4. No discovery — the user must already know which instance types/attributes
   to ask about.

## Key constraint: scores are account-specific

`GetSpotPlacementScores` returns scores tailored to the **calling account** —
it factors in that account's configuration and history, not a generic regional
view. A meaningful score therefore cannot be computed without acting under the
customer's own credentials. This rules out a hosted multi-tenant web app
(would require sharing/assuming customer credentials, a security and
trust-boundary non-starter) and points to a **bring-your-own-credentials local
tool** — the same trust model as today's script.

Scores are also **volatile and point-in-time**; AWS explicitly states they are
not a capacity guarantee. The tool's value-add over the raw API is therefore
*presentation*: discovery (presets), ranking, visualization (heatmap),
comparison, and optional trend tracking.

## Decision

Replace the Bash script with a polished **interactive Python CLI**, running
under the user's own AWS credentials. Same trust model as today; large
usability gain.

## Standards

- Packaged with `uv` + `pyproject.toml`.
- CLI via `click`. AWS calls via `boto3`. Terminal rendering via `rich`.
- Lint/format via `ruff`. MIT licensed (`LICENSE` at root, declared in
  `pyproject.toml`). Commit `uv.lock`.

`rich` is the one notable third-party dependency beyond `boto3`/`click`,
chosen for color heatmaps/tables and to keep `render.py` small.

## Architecture

Each module has one clear job and is independently testable. The critical
boundary: `scoring.py` is the only module that touches `boto3`; it returns a
normalized list of plain score records. Everything downstream (`rank`,
`render`, `history`) operates on plain data and never touches `boto3` — so all
interesting logic is unit-testable with fixtures, no live AWS required.

```
spot_scores/
  cli.py         # click entrypoint: interactive wizard + flag equivalents
  presets.py     # named instance-family presets -> type sets / attribute reqs
  scoring.py     # boto3 call + response normalization (pure data out)
  rank.py        # group/sort/top-N logic (the jq pipeline, in Python)
  render.py      # heatmap + comparison table output (rich)
  history.py     # optional timestamped persistence + trend lookup
pyproject.toml
LICENSE
README.md
```

### Data model

`scoring.py` normalizes the API response into a list of records, each:
`{region, availability_zone_id, score}`. This is the contract every downstream
module consumes.

## Interaction model

**Invocation:**

- `spot-scores` (no args) -> interactive wizard.
- `spot-scores --preset compute --regions us-east-1,us-west-2 -n 3` ->
  non-interactive for power users.
- Every prompt has a flag equivalent; supplying a flag skips its prompt.

**Interactive wizard flow** (plain `click` prompts — no extra interactive-prompt
dependency):

1. Region(s) — default to configured region; accept comma-separated list.
2. Mode — `by-preset` | `by-instance-type` | `by-attributes`.
3. Selection — preset name, or instance-type list, or vCPU/memory min-max.
4. Target capacity + unit (default `1` / `units`); single-AZ toggle.
5. Top-N (default 3).

## Presets

`presets.py` holds named sets that solve the discovery problem. Each maps to
either an instance-type list or an attribute requirement block. Presets are
plain data (dict/TOML) so adding one is a one-line change and trivially
testable.

| Preset     | Expands to |
|------------|------------|
| `general`  | m-family current-gen (e.g. m6i/m6a/m7i/m7a) |
| `compute`  | c-family current-gen |
| `memory`   | r-family current-gen |
| `gpu`      | g/p current-gen |
| `flexible` | attribute-based: vCPU/mem range, lets EC2 pick types |

**Note:** "current-gen" cannot be reliably auto-discovered, so presets are
**explicit pinned instance-type lists**. The README documents that preset
lists need occasional manual updates as new families ship.

## Output

**`rank.py`** reimplements today's `jq` pipeline as a pure function
(`list[ScoreRecord] -> list[ScoreRecord]`): group by `(region, az)`, sort by
score descending, take top-N, with optional AZ filter.

**`render.py`** — two `rich` views:

1. **Heatmap** (default) — grid colored by score, green (high, 8–10) ->
   yellow (mid, 4–7) -> red (low, 1–3). Scores are 1–10 per the API.

   ```
   Region      AZ        Score
   us-east-1   use1-az1  ████ 9
   us-east-1   use1-az4  ███  7
   us-west-2   usw2-az1  █    2
   ```

2. **Comparison table** (when multiple presets/type-sets are given) —
   columns = each requested set, rows = region/AZ, cells = score. Answers
   "where is c7i easier than c7a?" at a glance. **Deferred to a follow-up
   after v1** (see implementation plan) — v1 ships heatmap-only to avoid
   shipping unreachable product code; comparison gets its own plan.

**`--output json`** preserves today's raw-JSON behavior (and still writes the
result file) for scripting.

## History (optional layer)

Deliberately thin so it never becomes a core dependency:

- Off by default. `--save` appends the run (timestamp, request params, scores)
  as one line to `~/.spot-scores/history.jsonl`.
- `spot-scores history --preset compute --region us-east-1` reads back matching
  runs and renders a small trend (score over time per AZ).
- JSONL + local file only — no DB, no cloud. Directory/file created on write;
  on read with no data, a friendly "no history yet" message.

## Error handling

- Missing/invalid credentials -> clear message pointing at `aws configure` /
  profile, not a `boto3` traceback.
- `AccessDenied` on `GetSpotPlacementScores` -> name the exact IAM action
  required (`ec2:GetSpotPlacementScores`).
- Invalid region / empty instance-type set / impossible attribute range ->
  validated before the API call with a specific message.
- API throttling -> single `boto3` retry via standard retry config; clean
  message if it still fails.
- `--profile` and `--region` flags respected; otherwise fall back to the
  standard `boto3` credential chain.

## Testing

- `scoring.py` mocked via `botocore` stubber / fixtures.
- `rank.py`, `presets.py`, `render.py`, `history.py` unit-tested with fixture
  data — no live AWS in the suite.
- A smoke test confirms the CLI wires together end-to-end.

## Out of scope (YAGNI)

- Hosted multi-tenant web app (ruled out by credential model).
- Self-deploy CloudFormation/CDK template — viable future phase; the
  `scoring`/`rank`/`render` core could later become a Lambda, but not now.
- Any database or cloud persistence for history.
