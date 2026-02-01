from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

HEADER_LINES = {"BREAKING", "BREAKING:", "CORRECTION", "CORRECTION:"}

PICK_PATTERN = re.compile(
    r"^(?P<team>.+?)\s+(?P<spread>[+-]?\d+(?:\.\d+)?)\s+(?P<relation>at|over)\s+(?P<opponent>.+)$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ParsedPick:
    line_no: int
    team: str
    opponent: str
    spread: float
    relation: str
    raw_line: str
    matchup_key: str


@dataclass(frozen=True)
class RejectedLine:
    line_no: int
    raw_line: str
    reason: str


def normalize_matchup_piece(value: str) -> str:
    cleaned = re.sub(r"[^\w\s]", "", value.lower())
    collapsed = re.sub(r"\s+", " ", cleaned).strip()
    return collapsed


def build_matchup_key(team: str, opponent: str, relation: str) -> str:
    return f"{normalize_matchup_piece(team)}{normalize_matchup_piece(opponent)}{relation}"


def is_header_line(line: str) -> bool:
    return line.strip().upper() in HEADER_LINES


def has_correction_header(lines: Iterable[str]) -> bool:
    for line in lines:
        if is_header_line(line) and "CORRECTION" in line.upper():
            return True
    return False


def parse_message_lines(lines: list[str]) -> tuple[list[ParsedPick], list[RejectedLine]]:
    picks: list[ParsedPick] = []
    rejected: list[RejectedLine] = []

    for index, raw_line in enumerate(lines, start=1):
        stripped = raw_line.strip()
        if not stripped:
            continue
        if is_header_line(stripped):
            continue

        match = PICK_PATTERN.match(stripped)
        if not match:
            rejected.append(
                RejectedLine(
                    line_no=index,
                    raw_line=raw_line,
                    reason="Line does not match pick format",
                )
            )
            continue

        team = match.group("team").strip()
        opponent = match.group("opponent").strip()
        relation = match.group("relation").lower()
        spread = float(match.group("spread"))
        matchup_key = build_matchup_key(team, opponent, relation)
        picks.append(
            ParsedPick(
                line_no=index,
                team=team,
                opponent=opponent,
                spread=spread,
                relation=relation,
                raw_line=raw_line,
                matchup_key=matchup_key,
            )
        )

    return picks, rejected
