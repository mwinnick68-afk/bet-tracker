from __future__ import annotations

import argparse
import csv
import sqlite3
from datetime import date
from pathlib import Path
from typing import Final, Iterable, Sequence

from src.db import connect, get_db_path, init_db, now_iso
from src.io import load_bets
from src.metrics import normalize_result, profit

SUMMARY_DEFAULT_OUTPUT: Final[Path] = Path("data/reports/summary.csv")
INPUT_DEFAULT_PRIMARY: Final[Path] = Path("data/raw/bets.csv")
INPUT_DEFAULT_FALLBACK: Final[Path] = Path("data/raw/bets.sample.csv")


def select_input_path(requested: str | Path | None) -> Path:
    if requested is None:
        if INPUT_DEFAULT_PRIMARY.exists():
            return INPUT_DEFAULT_PRIMARY
        return INPUT_DEFAULT_FALLBACK
    requested_path = Path(requested)
    return requested_path if requested_path.exists() else INPUT_DEFAULT_FALLBACK


def parse_iso_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Invalid date: {value!r} (expected YYYY-MM-DD).") from exc


def parse_american_odds(value: str) -> int:
    try:
        odds = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Invalid odds: {value!r} (expected an integer).") from exc
    if odds == 0:
        raise argparse.ArgumentTypeError("Invalid odds: 0 is not allowed.")
    return odds


def parse_positive_stake(value: str) -> float:
    try:
        stake = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Invalid stake: {value!r} (expected a number).") from exc
    if stake <= 0:
        raise argparse.ArgumentTypeError("Invalid stake: must be > 0.")
    return stake


def parse_result(value: str) -> str:
    try:
        return normalize_result(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def filter_bets_by_date(
    bets: Iterable[dict[str, object]],
    from_date: date | None,
    to_date: date | None,
) -> list[dict[str, object]]:
    if from_date is None and to_date is None:
        return list(bets)

    filtered: list[dict[str, object]] = []
    for bet in bets:
        bet_date = date.fromisoformat(str(bet["date"]))
        if from_date is not None and bet_date < from_date:
            continue
        if to_date is not None and bet_date > to_date:
            continue
        filtered.append(bet)
    return filtered


def insert_bets(conn: sqlite3.Connection, bets: Iterable[dict[str, object]]) -> tuple[int, int]:
    rows: list[tuple[object, ...]] = []
    created_at = now_iso()
    for bet in bets:
        rows.append(
            (
                str(bet["date"]),
                str(bet["sport"]),
                str(bet["book"]),
                str(bet["type"]),
                str(bet["team_or_player"]),
                float(bet["odds_american"]),
                float(bet["stake"]),
                str(bet["result"]),
                str(bet.get("notes", "")),
                created_at,
            )
        )

    before_changes = conn.total_changes
    conn.executemany(
        """
        INSERT OR IGNORE INTO bets (
            date,
            sport,
            book,
            type,
            team_or_player,
            odds_american,
            stake,
            result,
            notes,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    conn.commit()
    inserted = conn.total_changes - before_changes
    skipped = len(rows) - inserted
    return inserted, skipped


def load_bets_from_db(
    conn: sqlite3.Connection,
    from_date: date | None,
    to_date: date | None,
) -> list[dict[str, object]]:
    query = """
        SELECT date, sport, book, type, team_or_player, odds_american, stake, result, notes
        FROM bets
    """
    conditions: list[str] = []
    params: list[str] = []
    if from_date is not None:
        conditions.append("date >= ?")
        params.append(from_date.isoformat())
    if to_date is not None:
        conditions.append("date <= ?")
        params.append(to_date.isoformat())
    if conditions:
        query = f"{query} WHERE {' AND '.join(conditions)}"
    query = f"{query} ORDER BY date, id"

    rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def summarize_bets(
    bets: Iterable[dict[str, object]],
    group_key: str,
) -> dict[str, dict[str, float | int]]:
    summary: dict[str, dict[str, float | int]] = {}
    for bet in bets:
        group_value = str(bet[group_key]).strip()
        stake = float(bet["stake"])
        odds = float(bet["odds_american"])
        bet_profit = profit(stake, odds, str(bet["result"]))

        stats = summary.setdefault(group_value, {"bets": 0, "stake": 0.0, "profit": 0.0})
        stats["bets"] = int(stats["bets"]) + 1
        stats["stake"] += stake
        stats["profit"] += bet_profit
    return summary


def write_summary(
    path: Path,
    group_key: str,
    summary: dict[str, dict[str, float | int]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=[group_key, "bets", "stake", "profit"])
        writer.writeheader()
        for group_value in sorted(summary):
            stats = summary[group_value]
            writer.writerow(
                {
                    group_key: group_value,
                    "bets": int(stats["bets"]),
                    "stake": f"{stats['stake']:.2f}",
                    "profit": f"{stats['profit']:.2f}",
                }
            )


def export_ledger(path: Path, bets: Iterable[dict[str, object]]) -> None:
    from src.io import REQUIRED_COLUMNS

    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [*REQUIRED_COLUMNS, "profit"]
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for bet in bets:
            stake = float(bet["stake"])
            odds = float(bet["odds_american"])
            bet_profit = profit(stake, odds, str(bet["result"]))

            row = {name: bet.get(name, "") for name in REQUIRED_COLUMNS}
            row["profit"] = f"{bet_profit:.2f}"
            writer.writerow(row)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m src.main", description="Bet tracker CLI")
    parser.add_argument(
        "--input",
        default=str(INPUT_DEFAULT_PRIMARY),
        help=(
            "Path to bets CSV (default: data/raw/bets.csv). "
            "If missing, falls back to data/raw/bets.sample.csv."
        ),
    )
    parser.add_argument(
        "--group",
        choices=("sport", "book", "type"),
        default="sport",
        help="Group summary by this column.",
    )
    parser.add_argument(
        "--from", dest="from_date", type=parse_iso_date, help="Start date YYYY-MM-DD."
    )
    parser.add_argument("--to", dest="to_date", type=parse_iso_date, help="End date YYYY-MM-DD.")
    parser.add_argument(
        "--output", help="Summary CSV output path (default: data/reports/summary.csv)."
    )
    parser.add_argument("--export", help="Export ledger CSV (all rows + profit column).")

    subparsers = parser.add_subparsers(dest="command")

    import_parser = subparsers.add_parser("import-csv", help="Import bets from CSV into SQLite.")
    import_parser.add_argument(
        "--db",
        default=str(get_db_path(None)),
        help="SQLite DB path (default: data/bets.db).",
    )
    import_parser.add_argument(
        "--input",
        help=(
            "Path to bets CSV (default: data/raw/bets.csv). "
            "If missing, falls back to data/raw/bets.sample.csv."
        ),
    )

    summary_parser = subparsers.add_parser("summary", help="Write a summary CSV from SQLite.")
    summary_parser.add_argument(
        "--db",
        default=str(get_db_path(None)),
        help="SQLite DB path (default: data/bets.db).",
    )
    summary_parser.add_argument(
        "--group",
        choices=("sport", "book", "type"),
        default="sport",
        help="Group summary by this column.",
    )
    summary_parser.add_argument(
        "--from", dest="from_date", type=parse_iso_date, help="Start date YYYY-MM-DD."
    )
    summary_parser.add_argument(
        "--to", dest="to_date", type=parse_iso_date, help="End date YYYY-MM-DD."
    )
    summary_parser.add_argument(
        "--output", help="Summary CSV output path (default: data/reports/summary.csv)."
    )

    export_parser = subparsers.add_parser("export-ledger", help="Export a ledger CSV from SQLite.")
    export_parser.add_argument(
        "--db",
        default=str(get_db_path(None)),
        help="SQLite DB path (default: data/bets.db).",
    )
    export_parser.add_argument(
        "--from", dest="from_date", type=parse_iso_date, help="Start date YYYY-MM-DD."
    )
    export_parser.add_argument(
        "--to", dest="to_date", type=parse_iso_date, help="End date YYYY-MM-DD."
    )
    export_parser.add_argument(
        "--output",
        required=True,
        help="Ledger CSV output path (all rows + profit column).",
    )

    add_bet_parser = subparsers.add_parser("add-bet", help="Insert a single bet into SQLite.")
    add_bet_parser.add_argument(
        "--db",
        default=str(get_db_path(None)),
        help="SQLite DB path (default: data/bets.db).",
    )
    add_bet_parser.add_argument(
        "--date", required=True, type=parse_iso_date, help="Bet date YYYY-MM-DD."
    )
    add_bet_parser.add_argument("--sport", required=True, help="Sport name.")
    add_bet_parser.add_argument("--book", required=True, help="Book name.")
    add_bet_parser.add_argument("--type", required=True, help="Bet type.")
    add_bet_parser.add_argument(
        "--team-or-player", required=True, help="Team or player descriptor."
    )
    add_bet_parser.add_argument(
        "--odds",
        required=True,
        type=parse_american_odds,
        help="American odds integer (e.g. -110, +120).",
    )
    add_bet_parser.add_argument(
        "--stake", required=True, type=parse_positive_stake, help="Stake (> 0)."
    )
    add_bet_parser.add_argument(
        "--result",
        required=True,
        type=parse_result,
        help="Result (W, L, P, open). Case-insensitive.",
    )
    add_bet_parser.add_argument("--notes", default="", help="Optional notes (default empty).")
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "import-csv":
        input_path = select_input_path(args.input)
        bets = load_bets(input_path)
        db_path = get_db_path(args.db)
        with connect(db_path) as conn:
            init_db(conn)
            inserted, skipped = insert_bets(conn, bets)
        print(f"Imported {len(bets)} bets from {input_path}.")
        print(f"Inserted {inserted} bets; skipped {skipped} duplicates.")
        return

    if args.command == "summary":
        db_path = get_db_path(args.db)
        with connect(db_path) as conn:
            init_db(conn)
            bets = load_bets_from_db(conn, args.from_date, args.to_date)
        summary = summarize_bets(bets, args.group)
        output_path = SUMMARY_DEFAULT_OUTPUT if args.output is None else Path(args.output)
        write_summary(output_path, args.group, summary)
        print(f"Loaded {len(bets)} bets from {db_path}.")
        print(f"Wrote summary to {output_path}.")
        return

    if args.command == "export-ledger":
        db_path = get_db_path(args.db)
        with connect(db_path) as conn:
            init_db(conn)
            bets = load_bets_from_db(conn, args.from_date, args.to_date)
        output_path = Path(args.output)
        export_ledger(output_path, bets)
        print(f"Wrote ledger to {output_path} for {len(bets)} bets.")
        return

    if args.command == "add-bet":
        bet = {
            "date": args.date.isoformat(),
            "sport": args.sport,
            "book": args.book,
            "type": args.type,
            "team_or_player": args.team_or_player,
            "odds_american": args.odds,
            "stake": args.stake,
            "result": args.result,
            "notes": args.notes,
        }
        db_path = get_db_path(args.db)
        with connect(db_path) as conn:
            init_db(conn)
            inserted, skipped = insert_bets(conn, [bet])
        descriptor = (
            f"{bet['date']} {bet['sport']} {bet['book']} {bet['type']} "
            f"{bet['team_or_player']} odds={bet['odds_american']} stake={bet['stake']} result={bet['result']}"
        )
        if inserted == 1:
            print(f"Inserted bet {descriptor}.")
        else:
            print(f"Skipped duplicate bet {descriptor}.")
        return

    requested_input = Path(args.input)
    input_path = requested_input if requested_input.exists() else INPUT_DEFAULT_FALLBACK
    bets = load_bets(input_path)
    bets = filter_bets_by_date(bets, args.from_date, args.to_date)
    summary = summarize_bets(bets, args.group)

    output_path = SUMMARY_DEFAULT_OUTPUT if args.output is None else Path(args.output)
    write_summary(output_path, args.group, summary)
    if args.export is not None:
        export_ledger(Path(args.export), bets)

    print(f"Loaded {len(bets)} bets from {input_path}.")
    for group_value in sorted(summary):
        stats = summary[group_value]
        print(
            f"{group_value}: bets={int(stats['bets'])} "
            f"stake={stats['stake']:.2f} profit={stats['profit']:.2f}"
        )
    print(f"Wrote summary to {output_path}.")


if __name__ == "__main__":
    main()
