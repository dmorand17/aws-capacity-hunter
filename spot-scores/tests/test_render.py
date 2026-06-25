# tests/test_render.py
from rich.table import Table

from spot_scores.scoring import ScoreRecord
from spot_scores.render import build_heatmap_table, score_band


def test_score_band_thresholds():
    assert score_band(2) == "red"
    assert score_band(5) == "yellow"
    assert score_band(9) == "green"


def test_heatmap_table_has_rows():
    records = [ScoreRecord("us-east-1", "use1-az1", 9)]
    table = build_heatmap_table(records)
    assert isinstance(table, Table)
    assert table.row_count == 1
