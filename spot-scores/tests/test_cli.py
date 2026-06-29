# tests/test_cli.py
from unittest.mock import patch

from click.testing import CliRunner

from spot_scores.cli import main
from spot_scores.reserve import ReservationResult, ReserveError
from spot_scores.scoring import ScoreRecord


def test_help_lists_commands():
    result = CliRunner().invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "history" in result.output
    assert "reserve" in result.output


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


def test_scores_compare_renders_columns():
    def fake_scores(client, request):
        # Distinct score per call so the compare table has data.
        return [ScoreRecord("us-east-1", "use1-az1", 7)]

    with patch("spot_scores.cli.get_scores", side_effect=fake_scores), \
         patch("spot_scores.cli._make_client", return_value=object()):
        result = CliRunner().invoke(
            main,
            ["scores", "--compare", "c7i.2xlarge,c7a.2xlarge",
             "--regions", "us-east-1"],
        )
    assert result.exit_code == 0
    assert "comparison" in result.output


def test_reserve_prints_id_to_stdout():
    result = ReservationResult("cr-9", "us-east-1a", "g6.xlarge", 1)
    with patch("spot_scores.cli.poll_for_reservation", return_value=result), \
         patch("spot_scores.cli._make_client", return_value=object()):
        out = CliRunner().invoke(
            main, ["reserve", "-t", "g6.xlarge"]
        )
    assert out.exit_code == 0
    assert "cr-9" in out.output


def test_reserve_json_output():
    result = ReservationResult("cr-9", "us-east-1a", "g6.xlarge", 1)
    with patch("spot_scores.cli.poll_for_reservation", return_value=result), \
         patch("spot_scores.cli._make_client", return_value=object()):
        out = CliRunner().invoke(
            main, ["reserve", "-t", "g6.xlarge", "--output", "json"]
        )
    assert out.exit_code == 0
    assert '"reservation_id": "cr-9"' in out.output


def test_reserve_dry_run_makes_no_aws_call():
    with patch("spot_scores.cli.poll_for_reservation") as poll, \
         patch("spot_scores.cli._make_client") as mk:
        out = CliRunner().invoke(
            main, ["reserve", "-t", "g6.xlarge", "--dry-run"]
        )
    assert out.exit_code == 0
    poll.assert_not_called()
    mk.assert_not_called()
    assert "dry-run" in out.output


def test_reserve_fatal_is_clickexception():
    with patch("spot_scores.cli.poll_for_reservation",
               side_effect=ReserveError("Access denied.")), \
         patch("spot_scores.cli._make_client", return_value=object()):
        out = CliRunner().invoke(main, ["reserve", "-t", "g6.xlarge"])
    assert out.exit_code != 0
    assert "Access denied." in out.output


def test_reserve_prompts_for_type_when_missing():
    result = ReservationResult("cr-1", "us-east-1a", "g6.xlarge", 1)
    with patch("spot_scores.cli.poll_for_reservation", return_value=result), \
         patch("spot_scores.cli._make_client", return_value=object()):
        out = CliRunner().invoke(
            main, ["reserve"], input="g6.xlarge\n"
        )
    assert out.exit_code == 0
    assert "Instance type" in out.output


def test_reserve_list_renders_table():
    from spot_scores.reserve import ReservationInfo
    infos = [ReservationInfo("cr-1", "us-east-1a", "g6.xlarge", 2, 1, "active")]
    with patch("spot_scores.cli.list_reservations", return_value=infos), \
         patch("spot_scores.cli._make_client", return_value=object()):
        out = CliRunner().invoke(
            main, ["reserve", "list", "--region", "us-east-1"]
        )
    assert out.exit_code == 0
    assert "cr-1" in out.output


def test_reserve_cancel_confirms_and_calls():
    with patch("spot_scores.cli.cancel_reservation") as cancel, \
         patch("spot_scores.cli._make_client", return_value=object()):
        out = CliRunner().invoke(
            main, ["reserve", "cancel", "cr-1", "--region", "us-east-1"],
            input="y\n",
        )
    assert out.exit_code == 0
    cancel.assert_called_once()
    assert "Cancelled cr-1" in out.output
