<p align="center">
  <img src="docs/img/aws-capacity-hunter3.png" alt="aws-capacity-hunter logo" width="240">
</p>

# aws-capacity-hunter

A small collection of utilities for **finding and securing scarce EC2
capacity** — On-Demand Capacity Reservations (ODCR) and Spot placement scores.
Built for grabbing hard-to-get instance types (e.g. GPU families like `g6`)
that aren't available on the first try.

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

## Requirements

- [`uv`](https://docs.astral.sh/uv/) and Python 3.11+
- AWS credentials configured for the relevant EC2 actions
  (`ec2:GetSpotPlacementScores`, `ec2:CreateCapacityReservation`,
  `ec2:DescribeCapacityReservations`, `ec2:CancelCapacityReservation`)
