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

## Lint and tests

```bash
ruff check .
pytest -q
```
