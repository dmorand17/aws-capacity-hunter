# reserve-capacity.sh

Poll EC2 across multiple Availability Zones to create an On-Demand Capacity
Reservation, retrying on a fixed interval until it succeeds or a deadline is
reached.

Requires `ec2:CreateCapacityReservation`.

## Usage

```
reserve-capacity.sh --type <type> [OPTIONS]
```

`--type` is **required**. Running with no arguments prints this usage and exits
`1` rather than running with defaults.

| Option | Argument | Default | Description |
|---|---|---|---|
| `-t`, `--type` | `<type>` | _(required)_ | EC2 instance type, e.g. `g6.xlarge` |
| `-z`, `--azs` | `<list>` | `us-east-1a us-east-1b us-east-1c us-east-1d us-east-1f` | Space-separated AZs to try, in order |
| `-c`, `--count` | `<n>` | `1` | Number of instances to reserve |
| `-i`, `--interval` | `<sec>` | `60` | Seconds to sleep between rounds |
| `-d`, `--duration` | `<sec>` | `21600` (6h) | Total runtime; `0` runs forever |
| `-h`, `--help` | | | Show usage and exit |

## Behavior

- Each **round** tries every AZ in order. The first AZ to return capacity wins.
- On success the script prints a summary block (AZ, reservation ID, and the
  cancel command), writes the **`CapacityReservationId` to stdout**, and exits `0`.
- AWS errors are classified rather than treated uniformly:
  - **Insufficient capacity** — expected; moves on to the next AZ.
  - **Throttling** (`RequestLimitExceeded`) — warns with a hint to raise
    `--interval`, then continues.
  - **Anything else** (invalid type, missing permissions, bad AZ) — logged and
    the script **aborts immediately** rather than looping on an unrecoverable error.
- If no AZ has capacity, the script sleeps `--interval` seconds and starts a new round.
- If `--duration` elapses with no reservation, it logs an error and exits `1`.

Logs are timestamped and written to **stderr**; only the reservation ID is
written to **stdout**, so you can capture it cleanly:

```bash
cr_id=$(reserve-capacity.sh -t g6.xlarge 2>reserve.log)
echo "Got $cr_id"
```

## Examples

```bash
# g6.xlarge across five us-east-1 AZs, 60s interval, 6h deadline
reserve-capacity.sh --type g6.xlarge

# Different region/type, faster polling
reserve-capacity.sh -z "us-west-2a us-west-2b" -t g5.xlarge -i 30

# Reserve 2x g6.12xlarge, retry forever
reserve-capacity.sh --type g6.12xlarge --count 2 --duration 0
```

## Running unattended

```bash
nohup reserve-capacity.sh -t g6.xlarge > reserve.log 2>&1 &
tail -f reserve.log
```

## Notes

- The reservation is created with `--instance-platform Linux/UNIX` and
  `--end-date-type unlimited` (no automatic expiry). Release it with
  `aws ec2 cancel-capacity-reservation --capacity-reservation-id <id>` when done
  — **an unlimited ODCR bills for the reserved capacity until cancelled, whether
  or not instances are running.**
- Polling too aggressively across many AZs can trigger `RequestLimitExceeded`
  throttling; the default 60s interval stays well clear.
- For more sophisticated capacity strategies, see
  [Capacity Reservation Fleets](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/work-with-cr-fleets.html).
