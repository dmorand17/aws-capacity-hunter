# tests/test_smoke.py
def test_package_imports():
    import capacity_hunter

    assert capacity_hunter.__version__ == "0.1.0"
