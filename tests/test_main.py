from main import add


def test_add() -> None:
    """Verifies that add correctly sums integers."""
    assert add(5, 7) == 12
    assert add(-1, 1) == 0
    assert add(0, 0) == 0
