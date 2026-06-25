# aws-capacity-hunter

A small collection of shell utilities for **finding and securing scarce EC2
capacity** — On-Demand Capacity Reservations (ODCR) and Spot placement scores.
Built for grabbing hard-to-get instance types (e.g. GPU families like `g6`)
that aren't available on the first try.

## Utilities

| Script | Purpose |
|---|---|
| [`scripts/reserve-capacity/`](scripts/reserve-capacity/) | Poll EC2 across multiple AZs to create an On-Demand Capacity Reservation, retrying until success or deadline. |
| _spot-scores (planned)_ | Check EC2 Spot placement scores across regions/AZs to find where capacity is most likely available. |

See each script's folder for its own README with full usage details.

## Requirements

- `bash` 4+
- [`aws`](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) CLI v2, configured with credentials for the relevant EC2 actions
- `date` (coreutils)
