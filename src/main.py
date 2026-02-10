from __future__ import annotations

import csv
from pathlib import Path

from src.io import load_bets
from src.metrics import profit


def _select_input_path() -> Path:
    primary = Path("data/raw/bets.csv")
    if primary.exists():
        return primary
    return Path("data/raw/bets.sample.csv")


def _summarize_by_sport(bets: list[dict[str, object]]) -> dict[str, dict[str, float | int]]:
    summary: dict[str, dict[str, float | int]] = {}
    for bet in bets:
        sport = str(bet["sport"]).strip()
        stake = float(bet["stake"])
        odds = float(bet["odds_american"])
        bet_profit = profit(stake, odds, str(bet["result"]))

        stats = summary.setdefault(sport, {"bets": 0, "stake": 0.0, "profit": 0.0})
        stats["bets"] = int(stats["bets"]) + 1
        stats["stake"] += stake
        stats["profit"] += bet_profit
    return summary


def _write_summary(path: Path, summary: dict[str, dict[str, float | int]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["sport", "bets", "stake", "profit"])
        writer.writeheader()
        for sport in sorted(summary):
            stats = summary[sport]
            writer.writerow(
                {
                    "sport": sport,
                    "bets": int(stats["bets"]),
                    "stake": f"{stats['stake']:.2f}",
                    "profit": f"{stats['profit']:.2f}",
                }
            )


def main() -> None:
    input_path = _select_input_path()
    bets = load_bets(input_path)
    summary = _summarize_by_sport(bets)

    output_path = Path("data/reports/summary.csv")
    _write_summary(output_path, summary)

    print(f"Loaded {len(bets)} bets from {input_path}.")
    for sport in sorted(summary):
        stats = summary[sport]
        print(
            f"{sport}: bets={int(stats['bets'])} "
            f"stake={stats['stake']:.2f} profit={stats['profit']:.2f}"
        )
    print(f"Wrote summary to {output_path}.")


if __name__ == "__main__":
    main()
