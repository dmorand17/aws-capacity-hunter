# tests/test_smoke.py
def test_package_imports():
    import spot_scores

    assert spot_scores.__version__ == "0.1.0"
