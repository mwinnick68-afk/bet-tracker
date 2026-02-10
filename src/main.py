from __future__ import annotations

import argparse
import csv
from datetime import date
from pathlib import Path
from typing import Final, Iterable

from src.io import load_bets
from src.metrics import profit

SUMMARY_DEFAULT_OUTPUT: Final[Path] = Path("data/reports/summary.csv")
INPUT_DEFAULT_PRIMARY: Final[Path] = Path("data/raw/bets.csv")
INPUT_DEFAULT_FALLBACK: Final[Path] = Path("data/raw/bets.sample.csv")


def select_input_path(requested: str | Path | None) -> Path:
    if requested is not None:
        return Path(requested)
    if INPUT_DEFAULT_PRIMARY.exists():
        return INPUT_DEFAULT_PRIMARY
    return INPUT_DEFAULT_FALLBACK


def parse_iso_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Invalid date: {value!r} (expected YYYY-MM-DD).") from exc


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
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

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
