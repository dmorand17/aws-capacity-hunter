# tests/test_presets.py
import pytest

from spot_scores.presets import PRESETS, list_presets, resolve_preset


def test_known_presets_exist():
    for name in ("general", "compute", "memory", "gpu", "flexible"):
        assert name in PRESETS


def test_list_presets_is_sorted():
    assert list_presets() == sorted(PRESETS)


def test_resolve_compute_returns_instance_types():
    body = resolve_preset("compute")
    assert "instance_types" in body
    assert all(t.startswith("c") for t in body["instance_types"])


def test_resolve_flexible_returns_requirements():
    body = resolve_preset("flexible")
    assert "instance_requirements" in body


def test_resolve_unknown_raises_with_valid_names():
    with pytest.raises(KeyError) as exc:
        resolve_preset("nope")
    assert "compute" in str(exc.value)
