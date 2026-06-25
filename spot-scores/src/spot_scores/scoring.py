"""boto3 boundary: build requests, call the API, normalize to plain data.

This is the only module that imports boto3. Everything downstream consumes
the ScoreRecord list it produces.
"""

from dataclasses import dataclass

from botocore.exceptions import ClientError, NoCredentialsError


class ScoringError(Exception):
    """Raised with a user-friendly message on AWS call failures."""


@dataclass
class ScoreRecord:
    """A single Spot Placement Score result."""

    region: str
    availability_zone_id: str
    score: int


def build_request(
    selection: dict,
    regions: list[str],
    target_capacity: int = 1,
    capacity_unit: str = "units",
    single_az: bool = True,
) -> dict:
    """Merge a selection with common params into boto3 request kwargs."""
    request: dict = {
        "RegionNames": regions,
        "TargetCapacity": target_capacity,
        "TargetCapacityUnitType": capacity_unit,
        "SingleAvailabilityZone": single_az,
    }
    if "instance_types" in selection:
        request["InstanceTypes"] = selection["instance_types"]
    elif "instance_requirements" in selection:
        request["InstanceRequirementsWithMetadata"] = (
            selection["instance_requirements"]
        )
    else:
        raise ValueError(
            "selection must contain 'instance_types' or "
            "'instance_requirements'"
        )
    return request


def normalize_response(response: dict) -> list[ScoreRecord]:
    """Map a get_spot_placement_scores response to ScoreRecord list."""
    records = []
    for item in response.get("SpotPlacementScores", []):
        records.append(
            ScoreRecord(
                region=item["Region"],
                availability_zone_id=item.get("AvailabilityZoneId", ""),
                score=item["Score"],
            )
        )
    return records


def get_scores(client, request: dict) -> list[ScoreRecord]:
    """Call get_spot_placement_scores and normalize, wrapping AWS errors."""
    try:
        response = client.get_spot_placement_scores(**request)
    except NoCredentialsError as err:
        raise ScoringError(
            "No AWS credentials found. Run 'aws configure' or set a "
            "profile with --profile."
        ) from err
    except ClientError as err:
        code = err.response["Error"]["Code"]
        if code in ("AccessDenied", "UnauthorizedOperation"):
            raise ScoringError(
                "Access denied. The 'ec2:GetSpotPlacementScores' IAM "
                "permission is required."
            ) from err
        if code in ("RequestLimitExceeded", "Throttling"):
            raise ScoringError(
                "AWS throttled the request. Wait a moment and retry."
            ) from err
        raise ScoringError(f"AWS error: {code}") from err
    return normalize_response(response)
