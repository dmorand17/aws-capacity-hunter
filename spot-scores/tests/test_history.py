# tests/test_history.py
from spot_scores.scoring import ScoreRecord
from spot_scores.history import save_run, load_runs


def test_load_missing_file_returns_empty(tmp_path):
    assert load_runs(path=tmp_path / "none.jsonl") == []


def test_save_then_load_roundtrip(tmp_path):
    path = tmp_path / "history.jsonl"
    records = [ScoreRecord("us-east-1", "use1-az1", 9)]
    save_run(records, {"preset": "compute"}, "2026-06-25T00:00:00",
             path=path)
    runs = load_runs(path=path)
    assert len(runs) == 1
    assert runs[0]["meta"] == {"preset": "compute"}
    assert runs[0]["scores"][0]["score"] == 9


def test_meta_filter_matches_subset(tmp_path):
    path = tmp_path / "history.jsonl"
    save_run([], {"preset": "compute", "region": "us-east-1"},
             "2026-06-25T00:00:00", path=path)
    save_run([], {"preset": "memory", "region": "us-east-1"},
             "2026-06-25T01:00:00", path=path)
    runs = load_runs(meta_filter={"preset": "compute"}, path=path)
    assert len(runs) == 1
    assert runs[0]["meta"]["preset"] == "compute"
