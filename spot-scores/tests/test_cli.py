# tests/test_cli.py
from unittest.mock import patch

from click.testing import CliRunner

from spot_scores.cli import main
from spot_scores.scoring import ScoreRecord


def test_help_lists_commands():
    result = CliRunner().invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "history" in result.output


def test_scores_command_renders_table():
    records = [ScoreRecord("us-east-1", "use1-az1", 9)]
    with patch("spot_scores.cli.get_scores", return_value=records), \
         patch("spot_scores.cli._make_client", return_value=object()):
        result = CliRunner().invoke(
            main,
            ["scores", "--preset", "compute", "--regions", "us-east-1"],
        )
    assert result.exit_code == 0
    assert "us-east-1" in result.output


def test_scores_defaults_region_to_us_east_1():
    records = [ScoreRecord("us-east-1", "use1-az1", 9)]
    with patch("spot_scores.cli.get_scores", return_value=records), \
         patch("spot_scores.cli._make_client", return_value=object()) as mk:
        # No --regions and blank prompt input -> default us-east-1.
        result = CliRunner().invoke(
            main,
            ["scores", "--preset", "compute"],
            input="\n",
        )
    assert result.exit_code == 0
    assert mk.call_args.args[1] == "us-east-1"


def test_scores_interactive_preset_by_number():
    records = [ScoreRecord("us-east-1", "use1-az1", 9)]
    with patch("spot_scores.cli.get_scores", return_value=records), \
         patch("spot_scores.cli._make_client", return_value=object()):
        # No --preset/--instance-types: pick preset #1, accept default region.
        result = CliRunner().invoke(
            main,
            ["scores"],
            input="1\n\n",
        )
    assert result.exit_code == 0
    assert "Available presets" in result.output


def test_scores_json_output():
    records = [ScoreRecord("us-east-1", "use1-az1", 9)]
    with patch("spot_scores.cli.get_scores", return_value=records), \
         patch("spot_scores.cli._make_client", return_value=object()):
        result = CliRunner().invoke(
            main,
            ["scores", "--preset", "compute", "--regions", "us-east-1",
             "--output", "json"],
        )
    assert result.exit_code == 0
    assert '"score": 9' in result.output
