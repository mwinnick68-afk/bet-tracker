from __future__ import annotations

from typing import Final

VALID_RESULTS: Final[set[str]] = {"W", "L", "P", "OPEN"}


def american_to_decimal(odds_american: float) -> float:
    if odds_american == 0:
        raise ValueError("American odds cannot be 0.")
    if odds_american > 0:
        return 1 + (odds_american / 100)
    return 1 + (100 / abs(odds_american))


def normalize_result(result: str) -> str:
    normalized = result.strip().upper()
    if normalized in VALID_RESULTS:
        return normalized
    raise ValueError(f"Invalid result value: {result!r}. Expected W, L, P, or open.")


def profit(stake: float, odds_american: float, result: str) -> float:
    normalized = normalize_result(result)
    if normalized == "W":
        return stake * (american_to_decimal(odds_american) - 1)
    if normalized == "L":
        return -stake
    return 0.0
