"""click CLI: interactive wizard plus flag-driven non-interactive use."""

import json
from dataclasses import asdict

import boto3
import click

from spot_scores.history import load_runs, save_run
from spot_scores.presets import describe_preset, list_presets, resolve_preset
from spot_scores.rank import rank_scores
from spot_scores.render import (
    build_heatmap_table,
    build_presets_table,
    render_table,
)
from spot_scores.scoring import (
    ScoringError,
    build_request,
    get_scores,
)


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


@click.group()
def main():
    """Interactive EC2 Spot Placement Score tool."""


@main.command()
@click.option("--preset", help="Named instance-family preset.")
@click.option("--instance-types", help="Comma-separated instance types.")
@click.option("--regions", help="Comma-separated region names.")
@click.option("-n", "--top", default=3, show_default=True,
              help="Top N results per AZ.")
@click.option("--az", help="Comma-separated AZ IDs to filter output.")
@click.option("--profile", help="AWS profile name.")
@click.option("--region", help="AWS region for the API call.")
@click.option("--save", is_flag=True, help="Append this run to history.")
@click.option("--output", type=click.Choice(["table", "json"]),
              default="table", show_default=True)
def scores(preset, instance_types, regions, top, az, profile, region,
           save, output):
    """Query Spot Placement Scores and render results."""
    selection = _selection(preset, instance_types)
    region_list = _split(regions)
    if not region_list:
        region_list = _split(
            click.prompt("Regions (comma-separated)", default="us-east-1")
        )

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


def _now():
    """Return an ISO timestamp; isolated for testability."""
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


@main.command()
@click.option("--preset", help="Filter history by preset.")
@click.option("--region", help="Filter history by region.")
def history(preset, region):
    """Show saved score history (trend over time)."""
    meta_filter = {}
    if preset:
        meta_filter["preset"] = preset
    runs = load_runs(meta_filter=meta_filter or None)
    if not runs:
        click.echo("No history yet. Run a query with --save first.")
        return
    for run in runs:
        click.echo(f"{run['timestamp']}  {run['meta']}")
        for score in run["scores"]:
            click.echo(
                f"  {score['region']} {score['availability_zone_id']} "
                f"-> {score['score']}"
            )
