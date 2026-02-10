# Bet Tracker

A small Python project that validates bet CSVs, computes profit, and writes summary
reports grouped by sport.

## CSV schema

Columns (in any order):
`date,sport,book,type,team_or_player,odds_american,stake,result,notes`

Accepted `result` values (case-insensitive): `W`, `L`, `P`, `open`.

## Run

```bash
python src/main.py
```

Input: `data/raw/bets.csv` (falls back to `data/raw/bets.sample.csv`).
Output: `data/reports/summary.csv`.

## SQLite workflows

Import CSV into SQLite:

```bash
python src/main.py import-csv --db data/bets.db --input data/raw/bets.csv
```

Write a summary CSV from SQLite:

```bash
python src/main.py summary --db data/bets.db --group sport --output data/reports/summary.csv
```

Export a ledger CSV with profit:

```bash
python src/main.py export-ledger --db data/bets.db --output data/reports/ledger.csv
```

Add a single bet to SQLite:

```bash
python src/main.py add-bet --db data/bets.db --date 2026-02-01 --sport NBA --book DK --type spread --team-or-player "Knicks -3.5" --odds -110 --stake 50 --result W --notes ""
```

## Lint and tests

```bash
ruff check .
pytest -q
```
