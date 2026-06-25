<p align="center">
  <img src="docs/img/aws-capacity-hunter3.png" alt="aws-capacity-hunter logo" width="240">
</p>

# aws-capacity-hunter

A small collection of utilities for **finding and securing scarce EC2
capacity** — On-Demand Capacity Reservations (ODCR) and Spot placement scores.
Built for grabbing hard-to-get instance types (e.g. GPU families like `g6`)
that aren't available on the first try.

## Utilities

| Tool | Purpose |
|---|---|
| [`reserve-capacity/`](reserve-capacity/) | Poll EC2 across multiple AZs to create an On-Demand Capacity Reservation, retrying until success or deadline. |
| [`spot-scores/`](spot-scores/) | Interactive Python CLI for EC2 Spot placement scores across regions/AZs — presets, color heatmap, and optional trend history. |

See each tool's folder for its own README with full usage details.

## Requirements

- `bash` 4+
- [`aws`](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) CLI v2, configured with credentials for the relevant EC2 actions
- `date` (coreutils)
- [`uv`](https://docs.astral.sh/uv/) and Python 3.11+ (for `spot-scores/`)
