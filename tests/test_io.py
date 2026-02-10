import csv

import pytest

from src.io import REQUIRED_COLUMNS, load_bets


def _write_csv(path, headers, rows) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def test_loader_rejects_missing_required_columns(tmp_path) -> None:
    path = tmp_path / "bets.csv"
    headers = [column for column in REQUIRED_COLUMNS if column != "notes"]
    _write_csv(path, headers, [])

    with pytest.raises(ValueError, match="missing columns"):
        load_bets(path)


def test_loader_coerces_numeric(tmp_path) -> None:
    path = tmp_path / "bets.csv"
    row = {
        "date": "2026-02-01",
        "sport": "NBA",
        "book": "DK",
        "type": "spread",
        "team_or_player": "Knicks -3.5",
        "odds_american": "-110",
        "stake": "50",
        "result": "w",
        "notes": "",
    }
    _write_csv(path, REQUIRED_COLUMNS, [row])

    bets = load_bets(path)

    assert isinstance(bets[0]["stake"], float)
    assert bets[0]["stake"] == 50.0
    assert isinstance(bets[0]["odds_american"], float)
    assert bets[0]["odds_american"] == -110.0
    assert bets[0]["result"] == "W"
