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

## The CLI

Everything lives in one Python CLI, [`capacity-hunter`](spot-scores/) (also
installed as `spot-scores` for backwards compatibility):

| Command | Purpose |
|---|---|
| `capacity-hunter scores` | EC2 Spot placement scores across regions/AZs — presets, color heatmap, side-by-side `--compare`, and optional trend history. |
| `capacity-hunter reserve` | Poll EC2 across multiple AZs to create an On-Demand Capacity Reservation, retrying until success or deadline. `--by-score` orders AZ attempts by placement score. |
| `capacity-hunter reserve list` / `cancel` | List or cancel existing capacity reservations. |
| `capacity-hunter history` | Show saved score trends and reservations. |

See [`spot-scores/README.md`](spot-scores/README.md) for full usage details.

The original standalone bash scripts now live in [`legacy/`](legacy/), kept for
reference only.

## Quick start

Install the CLI globally with uv, then use it from anywhere:

```bash
uv tool install ./spot-scores
```

**Reserve capacity** — poll for a `g6.xlarge` across the default us-east-1 AZs
until one has capacity:

```bash
capacity-hunter reserve --type g6.xlarge
```

**Check Spot placement scores** — launch the interactive wizard:

```bash
capacity-hunter scores
```

(Or run from source without installing: `cd spot-scores && uv run capacity-hunter scores`.)

## Requirements

- [`uv`](https://docs.astral.sh/uv/) and Python 3.11+
- AWS credentials configured for the relevant EC2 actions

### IAM permissions

| Command | Permission |
|---|---|
| `capacity-hunter scores` | `ec2:GetSpotPlacementScores` |
| `capacity-hunter reserve` | `ec2:CreateCapacityReservation` |
| `capacity-hunter reserve list` | `ec2:DescribeCapacityReservations` |
| `capacity-hunter reserve cancel` | `ec2:CancelCapacityReservation` |

## License

[MIT](LICENSE) © Doug Morand
