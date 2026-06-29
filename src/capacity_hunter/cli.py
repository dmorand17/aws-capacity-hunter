"""click CLI: interactive wizard plus flag-driven non-interactive use."""

import json
from dataclasses import asdict

import boto3
import click

from capacity_hunter.history import load_runs, save_reservation, save_run
from capacity_hunter.presets import describe_preset, list_presets, resolve_preset
from capacity_hunter.rank import rank_scores
from capacity_hunter.render import (
    build_compare_table,
    build_heatmap_table,
    build_presets_table,
    build_reservation_list_table,
    build_reservation_summary,
    render_table,
    render_table_err,
)
from capacity_hunter.reserve import (
    ReserveError,
    _region_from_az,
    azs_by_score,
    cancel_reservation,
    list_reservations,
    poll_for_reservation,
)
from capacity_hunter.scoring import (
    ScoringError,
    build_request,
    get_scores,
)

DEFAULT_AZS = "us-east-1a,us-east-1b,us-east-1c,us-east-1d,us-east-1f"


def _make_client(profile, region):
    """Build a boto3 EC2 client from an optional profile/region."""
    session = boto3.Session(profile_name=profile, region_name=region)
    return session.client("ec2")


def _split(value):
    """Split a comma-separated option into a clean list, or None."""
    if not value:
        return None
    return [part.strip() for part in value.split(",") if part.strip()]


def _selection(preset, instance_types):
    """Resolve a selection from flags or interactive prompts."""
    if preset:
        return resolve_preset(preset)
    if instance_types:
        return {"instance_types": _split(instance_types)}

    names = list_presets()
    rows = [(i, name, describe_preset(name)) for i, name in enumerate(names, 1)]
    custom_number = len(names) + 1
    rows.append((custom_number, "custom", "enter your own instance types"))
    render_table(build_presets_table(rows))

    choice = click.prompt(
        "Select a preset by number",
        type=click.Choice([str(n) for n, _, _ in rows]),
        default="1",
        show_choices=False,
    )
    if int(choice) == custom_number:
        types = click.prompt("Instance types (comma-separated)")
        return {"instance_types": _split(types)}
    return resolve_preset(names[int(choice) - 1])


def _resolve_label(token):
    """Resolve a compare token to a selection: preset name or single type."""
    try:
        return resolve_preset(token)
    except KeyError:
        return {"instance_types": [token]}


@click.group()
def main():
    """Hunt scarce EC2 capacity: Spot scores and capacity reservations."""


@main.command()
@click.option("--preset", help="Named instance-family preset.")
@click.option("--instance-types", help="Comma-separated instance types.")
@click.option("--compare", help="Comma-separated presets/types to compare "
              "side-by-side.")
@click.option("--regions", help="Comma-separated region names.")
@click.option("-n", "--top", default=3, show_default=True,
              help="Top N results per AZ.")
@click.option("--az", help="Comma-separated AZ IDs to filter output.")
@click.option("--profile", help="AWS profile name.")
@click.option("--region", help="AWS region for the API call.")
@click.option("--save", is_flag=True, help="Append this run to history.")
@click.option("--output", type=click.Choice(["table", "json"]),
              default="table", show_default=True)
def scores(preset, instance_types, compare, regions, top, az, profile,
           region, save, output):
    """Query Spot Placement Scores and render results."""
    region_list = _split(regions)
    if not region_list:
        region_list = _split(
            click.prompt("Regions (comma-separated)", default="us-east-1")
        )

    if compare:
        _compare(_split(compare), region_list, top, az, profile, region,
                 output)
        return

    selection = _selection(preset, instance_types)
    request = build_request(selection, regions=region_list)
    try:
        client = _make_client(profile, region or region_list[0])
        records = get_scores(client, request)
    except ScoringError as err:
        raise click.ClickException(str(err))

    ranked = rank_scores(records, top_n=top, az_filter=_split(az))

    if output == "json":
        click.echo(json.dumps([asdict(r) for r in ranked], indent=2))
    else:
        render_table(build_heatmap_table(ranked))

    if save:
        meta = {"preset": preset, "regions": ",".join(region_list)}
        save_run(ranked, meta, _now())


def _compare(labels, region_list, top, az, profile, region, output):
    """Score each label and render a side-by-side comparison."""
    try:
        client = _make_client(profile, region or region_list[0])
        records_by_label = {}
        for label in labels:
            request = build_request(_resolve_label(label), regions=region_list)
            records = get_scores(client, request)
            records_by_label[label] = rank_scores(
                records, top_n=top, az_filter=_split(az)
            )
    except ScoringError as err:
        raise click.ClickException(str(err))

    if output == "json":
        click.echo(json.dumps(
            {label: [asdict(r) for r in recs]
             for label, recs in records_by_label.items()},
            indent=2,
        ))
    else:
        render_table(build_compare_table(records_by_label))


def _now():
    """Return an ISO timestamp; isolated for testability."""
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def _reserve_logger():
    """Return an on_event callback that logs progress to stderr."""
    def log(event):
        kind = event["type"]
        if kind == "trying":
            click.echo(f"Trying {event['az']}...", err=True)
        elif kind == "insufficient":
            click.echo(f"No capacity in {event['az']}", err=True)
        elif kind == "throttled":
            click.echo(
                f"Throttled by EC2 in {event['az']}; "
                "consider a longer --interval",
                err=True,
            )
        elif kind == "sleeping":
            remaining = event["remaining"]
            left = "forever" if remaining is None else f"{int(remaining)}s left"
            click.echo(
                f"No capacity this round ({left}); "
                f"sleeping {int(event['interval'])}s...",
                err=True,
            )
    return log


@main.group(invoke_without_command=True)
@click.option("-t", "--instance-type", help="Instance type, e.g. g6.xlarge.")
@click.option("--azs", default=DEFAULT_AZS, show_default=True,
              help="Comma-separated AZs to try, in order.")
@click.option("-c", "--count", default=1, show_default=True,
              help="Instance count.")
@click.option("-i", "--interval", default=60, show_default=True,
              help="Seconds between rounds.")
@click.option("-d", "--duration", default=21600, show_default=True,
              help="Total runtime in seconds; 0 = forever.")
@click.option("--by-score", is_flag=True,
              help="Order AZ attempts by Spot placement score (best first).")
@click.option("--profile", help="AWS profile name.")
@click.option("--region", help="AWS region (derived from AZs if omitted).")
@click.option("--save", is_flag=True, help="Append the reservation to history.")
@click.option("--dry-run", is_flag=True, help="Print the plan and exit.")
@click.option("--output", type=click.Choice(["table", "json"]),
              default="table", show_default=True)
@click.pass_context
def reserve(ctx, instance_type, azs, count, interval, duration, by_score,
            profile, region, save, dry_run, output):
    """Poll across AZs to create an On-Demand Capacity Reservation.

    Run with no subcommand to start polling; use the 'list' and 'cancel'
    subcommands to manage existing reservations.
    """
    if ctx.invoked_subcommand is not None:
        return

    if not instance_type:
        instance_type = click.prompt("Instance type (e.g. g6.xlarge)")
    az_list = _split(azs)
    region = region or _region_from_az(az_list[0])

    if dry_run:
        forever = "forever" if duration == 0 else f"{duration}s"
        click.echo(
            f"[dry-run] Would poll {region} every {interval}s for {forever}:\n"
            f"  type={instance_type} count={count}\n"
            f"  azs={', '.join(az_list)}"
            + (" (ordered by score)" if by_score else ""),
            err=True,
        )
        return

    try:
        client = _make_client(profile, region)
        if by_score:
            az_list = _order_azs_by_score(
                client, region, instance_type, az_list
            )
        result = poll_for_reservation(
            client, az_list, instance_type, instance_count=count,
            interval=interval, duration=duration, on_event=_reserve_logger(),
        )
    except (ReserveError, ScoringError) as err:
        raise click.ClickException(str(err))

    if output == "json":
        click.echo(json.dumps(asdict(result)))
    else:
        click.echo(result.reservation_id)
        render_table_err(build_reservation_summary(result))

    if save:
        meta = {"instance_type": instance_type, "count": count,
                "availability_zone": result.availability_zone}
        save_reservation(result, meta, _now())


def _order_azs_by_score(client, region, instance_type, az_list):
    """Score the instance type and reorder az_list best-first."""
    request = build_request(
        {"instance_types": [instance_type]}, regions=[region]
    )
    records = get_scores(client, request)
    az_scores = [(r.availability_zone_id, r.score) for r in records]
    return azs_by_score(client, region, az_scores, az_list)


@reserve.command(name="list")
@click.option("--state", default="active", show_default=True,
              help="Filter by reservation state (empty for all).")
@click.option("--profile", help="AWS profile name.")
@click.option("--region", required=True, help="AWS region.")
@click.option("--output", type=click.Choice(["table", "json"]),
              default="table", show_default=True)
def list_(state, profile, region, output):
    """List existing capacity reservations."""
    try:
        client = _make_client(profile, region)
        reservations = list_reservations(client, state=state)
    except ReserveError as err:
        raise click.ClickException(str(err))

    if output == "json":
        click.echo(json.dumps([asdict(r) for r in reservations], indent=2))
    elif not reservations:
        click.echo("No capacity reservations found.")
    else:
        render_table(build_reservation_list_table(reservations))


@reserve.command()
@click.argument("reservation_id")
@click.option("--profile", help="AWS profile name.")
@click.option("--region", required=True, help="AWS region.")
@click.option("--yes", is_flag=True, help="Skip the confirmation prompt.")
def cancel(reservation_id, profile, region, yes):
    """Cancel a capacity reservation by id."""
    if not yes:
        click.confirm(
            f"Cancel capacity reservation {reservation_id}?", abort=True
        )
    try:
        client = _make_client(profile, region)
        cancel_reservation(client, reservation_id)
    except ReserveError as err:
        raise click.ClickException(str(err))
    click.echo(f"Cancelled {reservation_id}")


@main.command()
@click.option("--preset", help="Filter history by preset.")
@click.option("--region", help="Filter history by region.")
@click.option("--kind", type=click.Choice(["scores", "reserve"]),
              help="Filter by entry kind.")
def history(preset, region, kind):
    """Show saved history (score trends and reservations)."""
    meta_filter = {}
    if preset:
        meta_filter["preset"] = preset
    runs = load_runs(meta_filter=meta_filter or None, kind=kind)
    if not runs:
        click.echo("No history yet. Run a query with --save first.")
        return
    for run in runs:
        click.echo(f"{run['timestamp']}  {run['meta']}")
        if run.get("kind") == "reserve":
            res = run["reservation"]
            click.echo(
                f"  reserved {res['reservation_id']} in "
                f"{res['availability_zone']} ({res['instance_type']})"
            )
            continue
        for score in run.get("scores", []):
            click.echo(
                f"  {score['region']} {score['availability_zone_id']} "
                f"-> {score['score']}"
            )
