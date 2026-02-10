from __future__ import annotations

import csv
from pathlib import Path
from typing import Final

from src.metrics import normalize_result

REQUIRED_COLUMNS: Final[list[str]] = [
    "date",
    "sport",
    "book",
    "type",
    "team_or_player",
    "odds_american",
    "stake",
    "result",
    "notes",
]


def _validate_columns(fieldnames: list[str]) -> None:
    missing = [column for column in REQUIRED_COLUMNS if column not in fieldnames]
    extra = [column for column in fieldnames if column not in REQUIRED_COLUMNS]
    if missing or extra:
        message_parts: list[str] = []
        if missing:
            message_parts.append(f"missing columns: {', '.join(missing)}")
        if extra:
            message_parts.append(f"unexpected columns: {', '.join(extra)}")
        raise ValueError(f"Invalid CSV schema; {'; '.join(message_parts)}")


def _coerce_numeric(value: str | None, field: str, row_index: int) -> float:
    text_value = "" if value is None else value.strip()
    try:
        return float(text_value)
    except ValueError as exc:
        raise ValueError(f"Invalid {field} value {value!r} on row {row_index}.") from exc


def load_bets(path: str | Path) -> list[dict[str, object]]:
    path = Path(path)
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError("CSV header row is required.")
        _validate_columns(reader.fieldnames)

        bets: list[dict[str, object]] = []
        for row_index, row in enumerate(reader, start=2):
            stake = _coerce_numeric(row.get("stake"), "stake", row_index)
            odds = _coerce_numeric(row.get("odds_american"), "odds_american", row_index)
            result = normalize_result(row.get("result", ""))

            normalized = dict(row)
            normalized["stake"] = stake
            normalized["odds_american"] = odds
            normalized["result"] = result
            bets.append(normalized)

    return bets
