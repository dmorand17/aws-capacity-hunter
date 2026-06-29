"""Terminal rendering: score heatmap and side-by-side comparison."""

from rich.console import Console
from rich.table import Table

from spot_scores.reserve import ReservationInfo, ReservationResult
from spot_scores.scoring import ScoreRecord

_CONSOLE = Console()
# Reservation progress and summaries go to stderr so stdout stays clean
# for capturing the reservation id.
_ERR_CONSOLE = Console(stderr=True)


def score_band(score: int) -> str:
    """Map a 1-10 score to a rich color name."""
    if score <= 3:
        return "red"
    if score <= 7:
        return "yellow"
    return "green"


def _cell(score: int) -> str:
    """Render a score as a color-tagged rich cell."""
    return f"[{score_band(score)}]{score}[/]"


def build_heatmap_table(records: list[ScoreRecord]) -> Table:
    """One row per record: Region, AZ, colored Score."""
    table = Table(title="Spot Placement Scores")
    table.add_column("Region")
    table.add_column("AZ")
    table.add_column("Score", justify="right")
    for record in records:
        table.add_row(
            record.region,
            record.availability_zone_id or "-",
            _cell(record.score),
        )
    return table


def build_presets_table(presets: list[tuple[int, str, str]]) -> Table:
    """One numbered row per choice: index, name, and what it expands to."""
    table = Table(title="Available presets")
    table.add_column("#", justify="right", style="dim", no_wrap=True)
    table.add_column("Preset", style="cyan", no_wrap=True)
    table.add_column("Expands to")
    for number, name, description in presets:
        table.add_row(str(number), name, description)
    return table


def build_compare_table(
    records_by_label: dict[str, list[ScoreRecord]],
) -> Table:
    """Side-by-side score comparison: one column per label.

    Rows are (region, AZ); each label column holds the colored score for
    that AZ, or '-' when the label has no score there.
    """
    labels = list(records_by_label)
    table = Table(title="Spot Placement Score comparison")
    table.add_column("Region")
    table.add_column("AZ")
    for label in labels:
        table.add_column(label, justify="right")

    cells: dict[tuple[str, str], dict[str, int]] = {}
    for label, records in records_by_label.items():
        for record in records:
            key = (record.region, record.availability_zone_id)
            cells.setdefault(key, {})[label] = record.score

    for region, az in sorted(cells):
        scores = cells[(region, az)]
        row = [region, az or "-"]
        for label in labels:
            row.append(_cell(scores[label]) if label in scores else "-")
        table.add_row(*row)
    return table


def build_reservation_summary(result: ReservationResult) -> Table:
    """A summary of a created reservation, including the release command."""
    table = Table(title="✅ Capacity reservation created")
    table.add_column("Field", style="cyan", no_wrap=True)
    table.add_column("Value")
    table.add_row("Reservation", result.reservation_id)
    table.add_row("AZ", result.availability_zone)
    table.add_row("Type", result.instance_type)
    table.add_row("Count", str(result.instance_count))
    table.add_row("Platform", result.platform)
    table.add_row("Expiry", "unlimited (bills until cancelled)")
    table.add_row(
        "Release with",
        "aws ec2 cancel-capacity-reservation "
        f"--capacity-reservation-id {result.reservation_id}",
    )
    return table


def build_reservation_list_table(
    reservations: list[ReservationInfo],
) -> Table:
    """One row per existing capacity reservation."""
    table = Table(title="Capacity reservations")
    table.add_column("Reservation", no_wrap=True)
    table.add_column("AZ")
    table.add_column("Type")
    table.add_column("Count", justify="right")
    table.add_column("Available", justify="right")
    table.add_column("State")
    for info in reservations:
        table.add_row(
            info.reservation_id,
            info.availability_zone,
            info.instance_type,
            str(info.instance_count),
            str(info.available_count),
            info.state,
        )
    return table


def render_table(table: Table) -> None:
    """Print a table to the shared console."""
    _CONSOLE.print(table)


def render_table_err(table: Table) -> None:
    """Print a table to stderr (keeps stdout clean for piping)."""
    _ERR_CONSOLE.print(table)
