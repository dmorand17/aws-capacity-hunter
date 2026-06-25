# aws-capacity-hunter

A small collection of shell utilities for **finding and securing scarce EC2
capacity** — On-Demand Capacity Reservations (ODCR) and Spot placement scores.
Built for grabbing hard-to-get instance types (e.g. GPU families like `g6`)
that aren't available on the first try.

## Utilities

| Script | Purpose |
|---|---|
| [`scripts/reserve-capacity.sh`](scripts/reserve-capacity.sh) | Poll EC2 across multiple AZs to create an On-Demand Capacity Reservation, retrying until success or deadline. |
| _spot-scores (planned)_ | Check EC2 Spot placement scores across regions/AZs to find where capacity is most likely available. |

## Requirements

- `bash` 4+
- [`aws`](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) CLI v2, configured with credentials for the relevant EC2 actions
- `date` (coreutils)

---

## reserve-capacity.sh

Poll EC2 across multiple Availability Zones to create an On-Demand Capacity
Reservation, retrying on a fixed interval until it succeeds or a deadline is
reached.

Requires `ec2:CreateCapacityReservation`.

### Usage

```
scripts/reserve-capacity.sh [OPTIONS]
```

| Option | Argument | Default | Description |
|---|---|---|---|
| `-z`, `--azs` | `<list>` | `us-east-1a us-east-1b us-east-1c us-east-1d us-east-1f` | Space-separated AZs to try, in order |
| `-t`, `--type` | `<type>` | `g6.xlarge` | EC2 instance type |
| `-c`, `--count` | `<n>` | `1` | Number of instances to reserve |
| `-i`, `--interval` | `<sec>` | `60` | Seconds to sleep between rounds |
| `-d`, `--duration` | `<sec>` | `21600` (6h) | Total runtime; `0` runs forever |
| `-h`, `--help` | | | Show usage and exit |

### Behavior

- Each **round** tries every AZ in order. The first AZ to return capacity wins.
- On success the script logs the AZ and reservation ID, prints the
  **`CapacityReservationId` to stdout**, and exits `0`.
- If no AZ has capacity, the script sleeps `--interval` seconds and starts a new round.
- If `--duration` elapses with no reservation, it logs an error and exits `1`.

Logs are timestamped and written to **stderr**; only the reservation ID is
written to **stdout**, so you can capture it cleanly:

```bash
cr_id=$(scripts/reserve-capacity.sh -t g6.xlarge 2>reserve.log)
echo "Got $cr_id"
```

### Examples

```bash
# Defaults: g6.xlarge across five us-east-1 AZs, 60s interval, 6h deadline
scripts/reserve-capacity.sh

# Different region/type, faster polling
scripts/reserve-capacity.sh -z "us-west-2a us-west-2b" -t g5.xlarge -i 30

# Reserve 2x g6.12xlarge, retry forever
scripts/reserve-capacity.sh --type g6.12xlarge --count 2 --duration 0
```

### Running unattended

```bash
nohup scripts/reserve-capacity.sh -t g6.xlarge > reserve.log 2>&1 &
tail -f reserve.log
```

### Notes

- The reservation is created with `--instance-platform Linux/UNIX` and
  `--end-date-type unlimited` (no automatic expiry). Release it with
  `aws ec2 cancel-capacity-reservation --capacity-reservation-id <id>` when done
  — **an unlimited ODCR bills for the reserved capacity until cancelled, whether
  or not instances are running.**
- Polling too aggressively across many AZs can trigger `RequestLimitExceeded`
  throttling; the default 60s interval stays well clear.
- For more sophisticated capacity strategies, see
  [Capacity Reservation Fleets](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/work-with-cr-fleets.html).
