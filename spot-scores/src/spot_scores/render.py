"""Terminal rendering: score heatmap and side-by-side comparison."""

from rich.console import Console
from rich.table import Table

from spot_scores.scoring import ScoreRecord

_CONSOLE = Console()


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


def render_table(table: Table) -> None:
    """Print a table to the shared console."""
    _CONSOLE.print(table)
