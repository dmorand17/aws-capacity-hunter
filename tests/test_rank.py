# tests/test_rank.py
from capacity_hunter.scoring import ScoreRecord
from capacity_hunter.rank import rank_scores


def _records():
    return [
        ScoreRecord("us-east-1", "use1-az1", 9),
        ScoreRecord("us-east-1", "use1-az1", 5),
        ScoreRecord("us-east-1", "use1-az4", 7),
        ScoreRecord("us-west-2", "usw2-az1", 2),
    ]


def test_top_n_per_group():
    out = rank_scores(_records(), top_n=1)
    az1 = [r for r in out if r.availability_zone_id == "use1-az1"]
    assert len(az1) == 1
    assert az1[0].score == 9


def test_sorted_by_region_az_then_score_desc():
    out = rank_scores(_records(), top_n=3)
    keys = [(r.region, r.availability_zone_id, r.score) for r in out]
    assert keys == sorted(
        keys, key=lambda k: (k[0], k[1], -k[2])
    )


def test_az_filter_limits_results():
    out = rank_scores(_records(), az_filter=["use1-az1"])
    assert {r.availability_zone_id for r in out} == {"use1-az1"}


def test_empty_input_returns_empty():
    assert rank_scores([]) == []
