import pytest

from src.metrics import american_to_decimal, profit


def test_american_to_decimal() -> None:
    assert american_to_decimal(100) == 2.0
    assert american_to_decimal(-110) == pytest.approx(1 + (100 / 110))


def test_profit_outcomes() -> None:
    assert profit(50, 100, "W") == 50.0
    assert profit(50, 100, "L") == -50.0
    assert profit(50, 100, "P") == 0.0
    assert profit(50, 100, "open") == 0.0
