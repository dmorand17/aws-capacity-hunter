# tests/test_scoring.py
import pytest
from botocore.stub import Stubber
import boto3

from capacity_hunter.scoring import (
    ScoreRecord,
    ScoringError,
    build_request,
    get_scores,
    normalize_response,
)


def test_build_request_instance_types():
    req = build_request(
        {"instance_types": ["c7i.2xlarge"]},
        regions=["us-east-1"],
    )
    assert req["InstanceTypes"] == ["c7i.2xlarge"]
    assert req["RegionNames"] == ["us-east-1"]
    assert req["TargetCapacity"] == 1
    assert req["SingleAvailabilityZone"] is True


def test_build_request_instance_requirements():
    body = {"instance_requirements": {"ArchitectureTypes": ["x86_64"]}}
    req = build_request(body, regions=["us-east-1"])
    assert "InstanceRequirementsWithMetadata" in req
    assert "InstanceTypes" not in req


def test_normalize_response_maps_records():
    response = {
        "SpotPlacementScores": [
            {"Region": "us-east-1", "AvailabilityZoneId": "use1-az1",
             "Score": 9},
            {"Region": "us-west-2", "Score": 4},
        ]
    }
    records = normalize_response(response)
    assert records[0] == ScoreRecord("us-east-1", "use1-az1", 9)
    assert records[1] == ScoreRecord("us-west-2", "", 4)


def test_get_scores_uses_client_and_normalizes():
    client = boto3.client("ec2", region_name="us-east-1")
    stubber = Stubber(client)
    stubber.add_response(
        "get_spot_placement_scores",
        {"SpotPlacementScores": [
            {"Region": "us-east-1", "AvailabilityZoneId": "use1-az1",
             "Score": 8}]},
    )
    req = build_request({"instance_types": ["c7i.2xlarge"]},
                        regions=["us-east-1"])
    with stubber:
        records = get_scores(client, req)
    assert records == [ScoreRecord("us-east-1", "use1-az1", 8)]


def test_get_scores_wraps_access_denied():
    client = boto3.client("ec2", region_name="us-east-1")
    stubber = Stubber(client)
    stubber.add_client_error(
        "get_spot_placement_scores",
        service_error_code="AccessDenied",
        service_message="not authorized",
    )
    req = build_request({"instance_types": ["c7i.2xlarge"]},
                        regions=["us-east-1"])
    with stubber, pytest.raises(ScoringError) as exc:
        get_scores(client, req)
    assert "ec2:GetSpotPlacementScores" in str(exc.value)
