"""boto3 boundary for On-Demand Capacity Reservations (ODCR).

Like scoring.py, this is the only reservation module that imports boto3.
It exposes single-attempt and polling helpers that return plain dataclasses,
so the CLI and tests never touch boto3 directly.
"""

import time
from dataclasses import dataclass

from botocore.exceptions import ClientError, NoCredentialsError

# AWS error codes that mean "try again", mirroring the bash classifier.
_INSUFFICIENT = {"InsufficientInstanceCapacity", "InsufficientCapacity"}
_THROTTLING = {"RequestLimitExceeded", "Throttling", "ThrottlingException"}


class ReserveError(Exception):
    """Raised with a user-friendly message on a fatal ODCR failure."""


@dataclass
class ReservationResult:
    """A created On-Demand Capacity Reservation."""

    reservation_id: str
    availability_zone: str
    instance_type: str
    instance_count: int
    platform: str = "Linux/UNIX"


@dataclass
class AttemptOutcome:
    """The classified result of one create_reservation attempt.

    status is one of "success" | "insufficient" | "throttled". Fatal errors
    are raised as ReserveError, not returned as a status.
    """

    status: str
    result: ReservationResult | None = None
    message: str = ""


@dataclass
class ReservationInfo:
    """A summary of an existing capacity reservation (for list)."""

    reservation_id: str
    availability_zone: str
    instance_type: str
    instance_count: int
    available_count: int
    state: str


def _region_from_az(az: str) -> str:
    """Strip the trailing AZ letter: 'us-east-1a' -> 'us-east-1'."""
    return az.rstrip("abcdefghijklmnopqrstuvwxyz")


def _raise_fatal(err: ClientError) -> None:
    """Translate a non-retryable ClientError into a ReserveError."""
    code = err.response["Error"]["Code"]
    if code in ("AccessDenied", "UnauthorizedOperation"):
        raise ReserveError(
            "Access denied. The 'ec2:CreateCapacityReservation' IAM "
            "permission is required."
        ) from err
    raise ReserveError(f"AWS error: {code}") from err


def create_reservation(
    client,
    availability_zone: str,
    instance_type: str,
    instance_count: int = 1,
    platform: str = "Linux/UNIX",
) -> AttemptOutcome:
    """Attempt one create_capacity_reservation call and classify it.

    Returns an AttemptOutcome for success/insufficient/throttled. Raises
    ReserveError for fatal errors (bad type, auth, invalid AZ, no creds).
    """
    try:
        response = client.create_capacity_reservation(
            AvailabilityZone=availability_zone,
            InstanceType=instance_type,
            InstancePlatform=platform,
            InstanceCount=instance_count,
            EndDateType="unlimited",
        )
    except NoCredentialsError as err:
        raise ReserveError(
            "No AWS credentials found. Run 'aws configure' or set a "
            "profile with --profile."
        ) from err
    except ClientError as err:
        code = err.response["Error"]["Code"]
        if code in _INSUFFICIENT:
            return AttemptOutcome("insufficient", message=code)
        if code in _THROTTLING:
            return AttemptOutcome("throttled", message=code)
        _raise_fatal(err)

    reservation = response["CapacityReservation"]
    return AttemptOutcome(
        "success",
        result=ReservationResult(
            reservation_id=reservation["CapacityReservationId"],
            availability_zone=availability_zone,
            instance_type=instance_type,
            instance_count=instance_count,
            platform=platform,
        ),
    )


def poll_for_reservation(
    client,
    availability_zones: list[str],
    instance_type: str,
    instance_count: int = 1,
    interval: float = 60.0,
    duration: float = 21600.0,
    on_event=None,
    sleep=time.sleep,
    monotonic=time.monotonic,
) -> ReservationResult:
    """Rotate through AZs each round until success or deadline.

    duration of 0 means poll forever. sleep and monotonic are injected so
    tests can drive the clock without real waiting. on_event(event) is an
    optional callback for progress logging; event is a dict with a "type".

    Returns the ReservationResult on success; raises ReserveError on a fatal
    error or when the deadline passes.
    """

    def emit(event: dict) -> None:
        if on_event is not None:
            on_event(event)

    deadline = None if duration == 0 else monotonic() + duration

    while deadline is None or monotonic() < deadline:
        for az in availability_zones:
            emit({"type": "trying", "az": az})
            outcome = create_reservation(
                client, az, instance_type, instance_count
            )
            if outcome.status == "success":
                emit({"type": "success", "result": outcome.result})
                return outcome.result
            emit({"type": outcome.status, "az": az})

        remaining = None if deadline is None else deadline - monotonic()
        emit({"type": "sleeping", "interval": interval,
              "remaining": remaining})
        sleep(interval)

    raise ReserveError(
        f"Deadline reached after {duration}s without securing a "
        f"reservation for {instance_type}."
    )


def list_reservations(client, state: str = "active") -> list[ReservationInfo]:
    """Return capacity reservations, optionally filtered by state."""
    filters = []
    if state:
        filters.append({"Name": "state", "Values": [state]})
    try:
        response = client.describe_capacity_reservations(
            Filters=filters or []
        )
    except NoCredentialsError as err:
        raise ReserveError(
            "No AWS credentials found. Run 'aws configure' or set a "
            "profile with --profile."
        ) from err
    except ClientError as err:
        _raise_fatal(err)

    infos = []
    for item in response.get("CapacityReservations", []):
        infos.append(
            ReservationInfo(
                reservation_id=item["CapacityReservationId"],
                availability_zone=item.get("AvailabilityZone", ""),
                instance_type=item.get("InstanceType", ""),
                instance_count=item.get("TotalInstanceCount", 0),
                available_count=item.get("AvailableInstanceCount", 0),
                state=item.get("State", ""),
            )
        )
    return infos


def cancel_reservation(client, reservation_id: str) -> None:
    """Cancel one capacity reservation, wrapping AWS errors."""
    try:
        client.cancel_capacity_reservation(
            CapacityReservationId=reservation_id
        )
    except NoCredentialsError as err:
        raise ReserveError(
            "No AWS credentials found. Run 'aws configure' or set a "
            "profile with --profile."
        ) from err
    except ClientError as err:
        _raise_fatal(err)


def azs_by_score(client, region: str, az_scores: list[tuple[str, int]],
                 candidate_azs: list[str]) -> list[str]:
    """Order candidate AZ names by descending placement score.

    az_scores is a list of (availability_zone_id, score). Maps AZ IDs to
    names via describe_availability_zones, then returns candidate_azs sorted
    by score (highest first); AZs without a score keep their original order
    at the end.
    """
    try:
        response = client.describe_availability_zones(
            Filters=[{"Name": "region-name", "Values": [region]}]
        )
    except ClientError as err:
        _raise_fatal(err)

    id_to_name = {
        z["ZoneId"]: z["ZoneName"]
        for z in response.get("AvailabilityZones", [])
    }
    name_to_score = {}
    for az_id, score in az_scores:
        name = id_to_name.get(az_id)
        if name is not None:
            name_to_score[name] = score

    scored = [az for az in candidate_azs if az in name_to_score]
    unscored = [az for az in candidate_azs if az not in name_to_score]
    scored.sort(key=lambda az: -name_to_score[az])
    return scored + unscored
