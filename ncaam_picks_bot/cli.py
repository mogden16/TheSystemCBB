from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable
from zoneinfo import ZoneInfo

from ncaam_picks_bot.bot import run_bot
from ncaam_picks_bot.config import load_config
from ncaam_picks_bot.db import (
    connect,
    fetch_stats_rows,
    init_db,
    list_pending,
    update_pick_grade,
)

LOGGER = logging.getLogger(__name__)
NY_TZ = ZoneInfo("America/New_York")


@dataclass(frozen=True)
class StatsSummary:
    total: int
    wins: int
    losses: int
    pushes: int
    win_pct: float
    net_units: float
    roi: float
    total_risk: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="NCAAM picks bot CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("run-bot", help="Run the Discord bot")

    list_parser = subparsers.add_parser("list-pending", help="List pending picks")
    list_parser.add_argument("--date", dest="date", help="YYYY-MM-DD")

    grade_parser = subparsers.add_parser("grade", help="Grade a pick")
    grade_parser.add_argument("--pick-id", type=int, required=True)
    grade_parser.add_argument("--result", choices=["win", "loss", "push", "void"], required=True)
    grade_parser.add_argument("--odds", type=int, default=-110)
    grade_parser.add_argument("--risk", type=float, default=1.0)

    stats_parser = subparsers.add_parser("stats", help="Show performance stats")
    stats_parser.add_argument("--from", dest="from_date", help="YYYY-MM-DD")
    stats_parser.add_argument("--to", dest="to_date", help="YYYY-MM-DD")

    return parser.parse_args()


def compute_units(result: str, odds: int, risk: float) -> float:
    if result == "win":
        if odds < 0:
            return risk * (100 / abs(odds))
        return risk * (odds / 100)
    if result == "loss":
        return -risk
    return 0.0


def format_pending(rows: Iterable[dict]) -> str:
    if not rows:
        return "No pending picks."
    lines = ["Pending picks:"]
    for row in rows:
        lines.append(
            f"#{row['pick_id']} {row['team']} {row['spread']} {row['relation']} {row['opponent']}"
        )
    return "\n".join(lines)


def build_stats(rows: Iterable[dict]) -> tuple[StatsSummary, dict[str, StatsSummary]]:
    per_day: dict[str, list[dict]] = {}
    for row in rows:
        per_day.setdefault(row["pick_date"], []).append(row)

    overall = calculate_stats(rows)
    breakdown = {day: calculate_stats(day_rows) for day, day_rows in per_day.items()}
    return overall, breakdown


def calculate_stats(rows: Iterable[dict]) -> StatsSummary:
    wins = losses = pushes = 0
    net_units = 0.0
    total_risk = 0.0
    graded = 0

    for row in rows:
        status = row["status"]
        if status in {"win", "loss", "push", "void"}:
            total_risk += float(row["risk"] or 0)
            net_units += float(row["units"] or 0)
            if status in {"win", "loss", "push"}:
                graded += 1
                if status == "win":
                    wins += 1
                elif status == "loss":
                    losses += 1
                else:
                    pushes += 1

    win_pct = (wins / graded) * 100 if graded else 0.0
    roi = (net_units / total_risk) if total_risk else 0.0

    return StatsSummary(
        total=graded,
        wins=wins,
        losses=losses,
        pushes=pushes,
        win_pct=win_pct,
        net_units=net_units,
        roi=roi,
        total_risk=total_risk,
    )


def render_stats(label: str, stats: StatsSummary) -> str:
    return (
        f"{label}: total={stats.total} wins={stats.wins} losses={stats.losses} pushes={stats.pushes} "
        f"win%={stats.win_pct:.1f} net_units={stats.net_units:.2f} "
        f"roi={stats.roi:.2f} risk={stats.total_risk:.2f}"
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args()

    if args.command == "run-bot":
        config = load_config()
        run_bot(config)
        return

    config = load_config()
    conn = connect(config.db_path)
    init_db(conn)

    if args.command == "list-pending":
        target_date = args.date or datetime.now(tz=NY_TZ).date().isoformat()
        rows = list_pending(conn, target_date)
        print(format_pending(rows))
        return

    if args.command == "grade":
        units = compute_units(args.result, args.odds, args.risk)
        update_pick_grade(conn, args.pick_id, args.result, args.odds, args.risk, units)
        print(
            f"Graded pick {args.pick_id} as {args.result}. Units={units:.4f} Odds={args.odds} Risk={args.risk}."
        )
        return

    if args.command == "stats":
        rows = fetch_stats_rows(conn, args.from_date, args.to_date)
        overall, breakdown = build_stats(rows)
        print(render_stats("Overall", overall))
        for day in sorted(breakdown.keys()):
            print(render_stats(day, breakdown[day]))
        return


if __name__ == "__main__":
    main()
