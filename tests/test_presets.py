# tests/test_presets.py
import pytest

from capacity_hunter.presets import (
    PRESETS,
    describe_preset,
    list_presets,
    resolve_preset,
)


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


def test_gpu_preset_includes_current_generation():
    types = resolve_preset("gpu")["instance_types"]
    for t in ("g6e.2xlarge", "g7.2xlarge", "g7e.2xlarge"):
        assert t in types


def test_describe_preset_lists_instance_types():
    assert "c7i.2xlarge" in describe_preset("compute")


def test_describe_preset_handles_requirements():
    assert "requirements" in describe_preset("flexible")


def test_resolve_unknown_raises_with_valid_names():
    with pytest.raises(KeyError) as exc:
        resolve_preset("nope")
    assert "compute" in str(exc.value)
