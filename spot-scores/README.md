# capacity-hunter

The CLI that hunts scarce EC2 capacity. It pairs two complementary tools:

- **`scores`** — query the EC2 **Spot Placement Score** API
  (`ec2:GetSpotPlacementScores`) to discover *where* you're likely to get Spot
  capacity, ranked and color-coded as a heatmap.
- **`reserve`** — poll across AZs to create an **On-Demand Capacity
  Reservation** (`ec2:CreateCapacityReservation`), retrying until success or a
  deadline — built for grabbing hard-to-get types like GPU `g6` families.

It runs under **your own AWS credentials**. It is installed as both
`capacity-hunter` and `spot-scores` (a backwards-compatible alias), and
replaces the older `get-spot-scores.sh` and `reserve-capacity.sh` shell
scripts (now in [`../legacy/`](../legacy/)).

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
- IAM permissions: **`ec2:GetSpotPlacementScores`** (scores) and
  **`ec2:CreateCapacityReservation`** / **`ec2:DescribeCapacityReservations`** /
  **`ec2:CancelCapacityReservation`** (reserve)

## Install

```bash
uv sync
```

Run via `uv run`:

```bash
uv run capacity-hunter --help     # or: uv run spot-scores --help
```

## `scores` — Spot placement scores

### Interactive (no args)

```bash
uv run capacity-hunter scores
```

You'll see a numbered table of presets (each showing the instance types it
expands to, plus a "custom" option) and pick one by number, then enter the
region(s) — defaulting to `us-east-1`.

### Non-interactive (flags)

```bash
# Use a preset across two regions, top 3 AZs each
uv run capacity-hunter scores --preset compute --regions us-east-1,us-west-2 -n 3

# Explicit instance types
uv run capacity-hunter scores --instance-types c7i.2xlarge,c7a.2xlarge \
  --regions us-east-1

# Side-by-side comparison ("where is c7i easier than c7a?")
uv run capacity-hunter scores --compare c7i.2xlarge,c7a.2xlarge \
  --regions us-east-1

# Filter output to specific AZ IDs
uv run capacity-hunter scores --preset general --regions us-east-1 \
  --az use1-az1,use1-az4

# Use a named profile / specific API region
uv run capacity-hunter scores --preset memory --regions eu-west-1 \
  --profile my-profile
```

Every prompt has a flag equivalent; supplying a flag skips its prompt.

### Options

| Flag | Description |
|------|-------------|
| `--preset` | Named instance-family preset (see below). |
| `--instance-types` | Comma-separated instance types. |
| `--compare` | Comma-separated presets/types to score side-by-side. |
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
uv run capacity-hunter scores --preset compute --regions us-east-1 --output json
```

Emits the ranked records as JSON for piping into other tools.

## `reserve` — On-Demand Capacity Reservations

Poll across AZs to create an ODCR, retrying until success or a deadline. Each
**round** tries every AZ in order; the first AZ with capacity wins. Insufficient
capacity moves to the next AZ; throttling keeps trying; anything else (bad type,
auth, invalid AZ) aborts immediately. If a round finds nothing, it sleeps
`--interval` and starts again; if `--duration` elapses, it exits non-zero.

```bash
# g6.xlarge across the default five us-east-1 AZs, 60s interval, 6h deadline
uv run capacity-hunter reserve --type g6.xlarge

# Different region/type, faster polling
uv run capacity-hunter reserve --azs us-west-2a,us-west-2b -t g5.xlarge -i 30

# Reserve 2x g6.12xlarge, retry forever
uv run capacity-hunter reserve --type g6.12xlarge --count 2 --duration 0

# Order AZ attempts by Spot placement score (best first)
uv run capacity-hunter reserve --type g6.xlarge --by-score

# Preview the plan without calling AWS
uv run capacity-hunter reserve --type g6.xlarge --dry-run
```

The **reservation id is written to stdout**; progress logs and the success
summary (including the cancel command) go to **stderr**, so you can capture the
id cleanly:

```bash
cr_id=$(uv run capacity-hunter reserve -t g6.xlarge 2>reserve.log)
```

### `reserve` options

| Flag | Description |
|------|-------------|
| `-t`, `--instance-type` | Instance type, e.g. `g6.xlarge` (prompted if omitted). |
| `--azs` | Comma-separated AZs to try, in order (default five us-east-1 AZs). |
| `-c`, `--count` | Instance count (default `1`). |
| `-i`, `--interval` | Seconds between rounds (default `60`). |
| `-d`, `--duration` | Total runtime in seconds; `0` = forever (default `21600`). |
| `--by-score` | Order AZ attempts by Spot placement score (best first). |
| `--profile` | AWS profile name. |
| `--region` | AWS region (derived from the first AZ if omitted). |
| `--save` | Append the reservation to local history. |
| `--dry-run` | Print the resolved plan and exit without calling AWS. |
| `--output` | `table` (default summary) or `json`. |

> **An unlimited ODCR bills for the reserved capacity until cancelled**, whether
> or not instances are running. Release it when done.

### Managing reservations

```bash
# List active reservations in a region
uv run capacity-hunter reserve list --region us-east-1

# Cancel one (prompts for confirmation; --yes to skip)
uv run capacity-hunter reserve cancel cr-0123456789abcdef0 --region us-east-1
```

## History

History is **off by default**. Add `--save` to a `scores` or `reserve` run to
append it (timestamp, metadata, results) as one line to
`~/.spot-scores/history.jsonl`:

```bash
uv run capacity-hunter scores --preset compute --regions us-east-1 --save
uv run capacity-hunter reserve --type g6.xlarge --save
```

Read back saved runs (optionally filtered) with the `history` command:

```bash
uv run capacity-hunter history --preset compute   # score runs
uv run capacity-hunter history --kind reserve      # reservations
```

It's JSONL on local disk only — no database, no cloud.

## Development

```bash
uv run pytest        # run the test suite
uv run ruff check src tests
```

`scoring.py` and `reserve.py` are the only modules that touch `boto3`;
everything downstream operates on plain dataclasses and is unit-tested with
`botocore` stubs and fixtures (no live AWS).

## Legacy

The original `get-spot-scores.sh` and `reserve-capacity.sh` shell scripts (and
the `cli-input-yaml` config files) live in [`../legacy/`](../legacy/). They are
**deprecated** — this CLI fully supersedes them — and kept only for reference.

## License

MIT — see [LICENSE](LICENSE).
