# spot-scores

Interactive CLI for the EC2 **Spot Placement Score** API
(`ec2:GetSpotPlacementScores`). It helps you discover *where* you're likely to
get EC2 Spot capacity — by region and Availability Zone — for a given set of
instance types or attribute requirements, then ranks and color-codes the
results as a heatmap.

It runs under **your own AWS credentials** and replaces the older
`get-spot-scores.sh` shell script.

## Important caveats

- **Scores are account-specific.** `GetSpotPlacementScores` returns scores
  tailored to the *calling account* — its configuration and history — not a
  generic regional view. Results from another account won't match yours. This
  is why the tool runs under your credentials locally rather than as a hosted
  service.
- **Scores are volatile and point-in-time.** A score (1–10, higher is better)
  is *not* a capacity guarantee. It can change between calls. Use `--save` and
  the `history` command to track trends over time.

## Requirements

- Python 3.11+
- [`uv`](https://docs.astral.sh/uv/)
- AWS credentials (via `aws configure`, a named profile, or the standard
  environment/instance credential chain)
- IAM permission: **`ec2:GetSpotPlacementScores`**

## Install

```bash
uv sync
```

Run via `uv run`:

```bash
uv run spot-scores --help
```

## Usage

### Interactive (no args)

```bash
uv run spot-scores scores
```

You'll see a numbered table of presets (each showing the instance types it
expands to, plus a "custom" option) and pick one by number, then enter the
region(s) — defaulting to `us-east-1`.

### Non-interactive (flags)

```bash
# Use a preset across two regions, top 3 AZs each
uv run spot-scores scores --preset compute --regions us-east-1,us-west-2 -n 3

# Explicit instance types
uv run spot-scores scores --instance-types c7i.2xlarge,c7a.2xlarge \
  --regions us-east-1

# Filter output to specific AZ IDs
uv run spot-scores scores --preset general --regions us-east-1 \
  --az use1-az1,use1-az4

# Use a named profile / specific API region
uv run spot-scores scores --preset memory --regions eu-west-1 \
  --profile my-profile
```

Every prompt has a flag equivalent; supplying a flag skips its prompt.

### Options

| Flag | Description |
|------|-------------|
| `--preset` | Named instance-family preset (see below). |
| `--instance-types` | Comma-separated instance types. |
| `--regions` | Comma-separated region names to score. |
| `-n`, `--top` | Top N results per AZ (default `3`). |
| `--az` | Comma-separated AZ IDs to filter output. |
| `--profile` | AWS profile name. |
| `--region` | AWS region used for the API call itself. |
| `--save` | Append this run to local history. |
| `--output` | `table` (default, color heatmap) or `json`. |

## Presets

Presets solve the discovery problem — named instance-family sets so you don't
have to know exact type names.

| Preset | Expands to |
|--------|------------|
| `general` | m-family current-gen (m6i/m6a/m7i/m7a) |
| `compute` | c-family current-gen (c6i/c6a/c7i/c7a) |
| `memory` | r-family current-gen (r6i/r6a/r7i/r7a) |
| `gpu` | g/p current-gen (g5/g6/g6e/g7/g7e/p4d/p5) |
| `flexible` | attribute-based: vCPU/memory range, lets EC2 pick types |

**Note:** "current generation" cannot be reliably auto-discovered, so preset
type lists are **explicit and pinned** in `src/spot_scores/presets.py`. They
need occasional manual updates as new families ship.

## Score bands

The heatmap colors scores by band:

- **Red** — low (1–3)
- **Yellow** — mid (4–7)
- **Green** — high (8–10)

## JSON output (scripting)

```bash
uv run spot-scores scores --preset compute --regions us-east-1 --output json
```

Emits the ranked records as JSON for piping into other tools.

## History

History is **off by default**. Add `--save` to append a run (timestamp,
request metadata, scores) as one line to `~/.spot-scores/history.jsonl`:

```bash
uv run spot-scores scores --preset compute --regions us-east-1 --save
```

Read back saved runs (optionally filtered) with the `history` command:

```bash
uv run spot-scores history --preset compute
```

It's JSONL on local disk only — no database, no cloud.

## Development

```bash
uv run pytest        # run the test suite
uv run ruff check src tests
```

`scoring.py` is the only module that touches `boto3`; everything downstream
operates on plain `ScoreRecord` data and is unit-tested with fixtures (no live
AWS).

## Legacy

The original `get-spot-scores.sh` shell script and its `cli-input-yaml` config
files live in [`legacy/`](legacy/). They are **deprecated** — the Python CLI
fully supersedes them — and kept only for reference.

## License

MIT — see [LICENSE](LICENSE).
