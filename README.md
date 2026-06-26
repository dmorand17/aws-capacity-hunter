<p align="center">
  <img src="docs/img/aws-capacity-hunter4.png" alt="aws-capacity-hunter logo">
</p>

<p align="center">
<em>Capacity acquired.</em>
</p>

<hr/>

<p align="center">
  Hunt down scarce EC2 capacity — On-Demand Capacity Reservations (ODCR)
  and Spot placement scores — for the hard-to-get instance types that
  aren't available on the first try.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License: MIT">
  <img src="https://img.shields.io/badge/bash-4%2B-green.svg" alt="bash 4+">
  <img src="https://img.shields.io/badge/python-3.11%2B-blue.svg" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/cloud-AWS-orange.svg" alt="AWS">
</p>

---

## Why

GPU and other high-demand instance families (e.g. `g6`, `p5`) frequently return
`InsufficientInstanceCapacity` on the first request. These tools help you
**find where capacity is likely** (Spot placement scores) and **grab it the
moment it appears** (polling ODCR creation across AZs).

## Utilities

| Tool | Purpose |
|---|---|
| [`reserve-capacity/`](reserve-capacity/) | Poll EC2 across multiple AZs to create an On-Demand Capacity Reservation, retrying until success or deadline. |
| [`spot-scores/`](spot-scores/) | Interactive Python CLI for EC2 Spot placement scores across regions/AZs — presets, color heatmap, and optional trend history. |

See each tool's folder for its own README with full usage details.

## Quick start

**Reserve capacity** — poll for a `g6.xlarge` across the default us-east-1 AZs
until one has capacity:

```bash
./reserve-capacity/reserve-capacity.sh --type g6.xlarge
```

**Check Spot placement scores** — install the CLI globally with uv, then
launch the interactive wizard:

```bash
uv tool install ./spot-scores
spot-scores scores
```

(Or run it from source without installing: `cd spot-scores && uv run spot-scores scores`.)

## Requirements

- `bash` 4+
- [`aws`](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) CLI v2, configured with credentials for the relevant EC2 actions
- `date` (coreutils)
- [`uv`](https://docs.astral.sh/uv/) and Python 3.11+ (for `spot-scores/`)

### IAM permissions

| Tool | Permission |
|---|---|
| `reserve-capacity/` | `ec2:CreateCapacityReservation` |
| `spot-scores/` | `ec2:GetSpotPlacementScores` |

## License

[MIT](LICENSE) © Doug Morand
