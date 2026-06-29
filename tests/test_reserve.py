# tests/test_reserve.py
from unittest.mock import Mock

import boto3
import pytest
from botocore.exceptions import ClientError
from botocore.stub import Stubber

from capacity_hunter.reserve import (
    AttemptOutcome,
    ReservationResult,
    ReserveError,
    _region_from_az,
    azs_by_score,
    create_reservation,
    list_reservations,
    poll_for_reservation,
)


# --- _region_from_az ---------------------------------------------------------

def test_region_from_az():
    assert _region_from_az("us-east-1a") == "us-east-1"
    assert _region_from_az("us-west-2b") == "us-west-2"


# --- create_reservation (Stubber against a real client) ----------------------

def _client():
    return boto3.client("ec2", region_name="us-east-1")


def test_create_reservation_success():
    client = _client()
    stubber = Stubber(client)
    stubber.add_response(
        "create_capacity_reservation",
        {"CapacityReservation": {"CapacityReservationId": "cr-123"}},
    )
    with stubber:
        outcome = create_reservation(client, "us-east-1a", "g6.xlarge")
    assert outcome.status == "success"
    assert outcome.result.reservation_id == "cr-123"
    assert outcome.result.availability_zone == "us-east-1a"


def test_create_reservation_insufficient():
    client = _client()
    stubber = Stubber(client)
    stubber.add_client_error(
        "create_capacity_reservation",
        service_error_code="InsufficientInstanceCapacity",
    )
    with stubber:
        outcome = create_reservation(client, "us-east-1a", "g6.xlarge")
    assert outcome.status == "insufficient"


def test_create_reservation_throttled():
    client = _client()
    stubber = Stubber(client)
    stubber.add_client_error(
        "create_capacity_reservation",
        service_error_code="RequestLimitExceeded",
    )
    with stubber:
        outcome = create_reservation(client, "us-east-1a", "g6.xlarge")
    assert outcome.status == "throttled"


def test_create_reservation_fatal_access_denied():
    client = _client()
    stubber = Stubber(client)
    stubber.add_client_error(
        "create_capacity_reservation",
        service_error_code="AccessDenied",
    )
    with stubber, pytest.raises(ReserveError) as exc:
        create_reservation(client, "us-east-1a", "g6.xlarge")
    assert "ec2:CreateCapacityReservation" in str(exc.value)


# --- poll_for_reservation (Mock client + injected clock) ---------------------

class FakeClock:
    """A monotonic clock that only advances when sleep is called."""

    def __init__(self):
        self.t = 0.0
        self.sleeps = []

    def monotonic(self):
        return self.t

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.t += seconds


def _mock_client(side_effect):
    client = Mock()
    client.create_capacity_reservation = Mock(side_effect=side_effect)
    return client


def _success(cr_id="cr-1"):
    return {"CapacityReservation": {"CapacityReservationId": cr_id}}


def _client_error(code):
    return ClientError({"Error": {"Code": code, "Message": code}},
                       "CreateCapacityReservation")


def test_success_on_second_az():
    clock = FakeClock()
    client = _mock_client([
        _client_error("InsufficientInstanceCapacity"),
        _success("cr-2"),
    ])
    result = poll_for_reservation(
        client, ["us-east-1a", "us-east-1b", "us-east-1c"], "g6.xlarge",
        sleep=clock.sleep, monotonic=clock.monotonic,
    )
    assert result.reservation_id == "cr-2"
    assert result.availability_zone == "us-east-1b"
    assert clock.sleeps == []  # success within the first round
    assert client.create_capacity_reservation.call_count == 2  # 3rd untried


def test_all_insufficient_then_success_next_round():
    clock = FakeClock()
    client = _mock_client([
        _client_error("InsufficientInstanceCapacity"),
        _client_error("InsufficientInstanceCapacity"),
        _success("cr-9"),
    ])
    result = poll_for_reservation(
        client, ["us-east-1a", "us-east-1b"], "g6.xlarge",
        interval=30, sleep=clock.sleep, monotonic=clock.monotonic,
    )
    assert result.reservation_id == "cr-9"
    assert clock.sleeps == [30]  # exactly one sleep between rounds


def test_throttling_keeps_trying():
    clock = FakeClock()
    client = _mock_client([
        _client_error("RequestLimitExceeded"),
        _success("cr-3"),
    ])
    result = poll_for_reservation(
        client, ["us-east-1a", "us-east-1b"], "g6.xlarge",
        sleep=clock.sleep, monotonic=clock.monotonic,
    )
    assert result.reservation_id == "cr-3"
    assert clock.sleeps == []


def test_fatal_aborts_immediately():
    clock = FakeClock()
    client = _mock_client([_client_error("AccessDenied")])
    with pytest.raises(ReserveError):
        poll_for_reservation(
            client, ["us-east-1a", "us-east-1b"], "g6.xlarge",
            sleep=clock.sleep, monotonic=clock.monotonic,
        )
    assert clock.sleeps == []
    assert client.create_capacity_reservation.call_count == 1  # no 2nd AZ


def test_deadline_reached_raises():
    clock = FakeClock()
    client = _mock_client(
        lambda **kw: (_ for _ in ()).throw(
            _client_error("InsufficientInstanceCapacity")
        )
    )
    with pytest.raises(ReserveError) as exc:
        poll_for_reservation(
            client, ["us-east-1a"], "g6.xlarge",
            interval=10, duration=30,
            sleep=clock.sleep, monotonic=clock.monotonic,
        )
    assert "Deadline reached" in str(exc.value)
    # 30s deadline, 10s sleeps: rounds at t=0,10,20 then t=30 stops.
    assert clock.sleeps == [10, 10, 10]


def test_duration_zero_is_forever():
    clock = FakeClock()
    client = _mock_client([
        _client_error("InsufficientInstanceCapacity"),
        _client_error("InsufficientInstanceCapacity"),
        _success("cr-7"),
    ])
    result = poll_for_reservation(
        client, ["us-east-1a"], "g6.xlarge", duration=0,
        sleep=clock.sleep, monotonic=clock.monotonic,
    )
    assert result.reservation_id == "cr-7"
    assert clock.sleeps == [60, 60]  # two empty rounds, never deadlined


def test_on_event_emits_progress():
    clock = FakeClock()
    events = []
    client = _mock_client([
        _client_error("InsufficientInstanceCapacity"),
        _success("cr-5"),
    ])
    poll_for_reservation(
        client, ["us-east-1a", "us-east-1b"], "g6.xlarge",
        on_event=events.append,
        sleep=clock.sleep, monotonic=clock.monotonic,
    )
    types = [e["type"] for e in events]
    assert "trying" in types
    assert "insufficient" in types
    assert "success" in types


# --- list_reservations -------------------------------------------------------

def test_list_reservations_maps_records():
    client = _client()
    stubber = Stubber(client)
    stubber.add_response(
        "describe_capacity_reservations",
        {"CapacityReservations": [{
            "CapacityReservationId": "cr-1",
            "AvailabilityZone": "us-east-1a",
            "InstanceType": "g6.xlarge",
            "TotalInstanceCount": 2,
            "AvailableInstanceCount": 1,
            "State": "active",
        }]},
        {"Filters": [{"Name": "state", "Values": ["active"]}]},
    )
    with stubber:
        infos = list_reservations(client, state="active")
    assert infos[0].reservation_id == "cr-1"
    assert infos[0].instance_count == 2
    assert infos[0].available_count == 1


# --- azs_by_score ------------------------------------------------------------

def test_azs_by_score_orders_best_first():
    client = Mock()
    client.describe_availability_zones = Mock(return_value={
        "AvailabilityZones": [
            {"ZoneId": "use1-az1", "ZoneName": "us-east-1a"},
            {"ZoneId": "use1-az2", "ZoneName": "us-east-1b"},
            {"ZoneId": "use1-az4", "ZoneName": "us-east-1d"},
        ]
    })
    az_scores = [("use1-az1", 3), ("use1-az2", 9)]
    ordered = azs_by_score(
        client, "us-east-1", az_scores,
        ["us-east-1a", "us-east-1b", "us-east-1d"],
    )
    # az2 (score 9) first, az1 (score 3) next, unscored az4 last.
    assert ordered == ["us-east-1b", "us-east-1a", "us-east-1d"]


# --- dataclass sanity --------------------------------------------------------

def test_attempt_outcome_defaults():
    outcome = AttemptOutcome("insufficient")
    assert outcome.result is None
    assert outcome.message == ""


def test_reservation_result_default_platform():
    result = ReservationResult("cr-1", "us-east-1a", "g6.xlarge", 1)
    assert result.platform == "Linux/UNIX"
