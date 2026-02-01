from __future__ import annotations

from dataclasses import dataclass
import os

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    discord_token: str
    channel_id: int
    allowed_author_ids: set[int]
    db_path: str


def load_config() -> Config:
    load_dotenv()
    token = os.getenv("DISCORD_TOKEN")
    channel_id = os.getenv("CHANNEL_ID")
    allowed_ids = os.getenv("ALLOWED_AUTHOR_IDS", "")
    db_path = os.getenv("DB_PATH", "picks.db")

    if not token:
        raise ValueError("DISCORD_TOKEN is required")
    if not channel_id:
        raise ValueError("CHANNEL_ID is required")

    allowed_set: set[int] = set()
    for raw in allowed_ids.split(","):
        value = raw.strip()
        if value:
            allowed_set.add(int(value))

    return Config(
        discord_token=token,
        channel_id=int(channel_id),
        allowed_author_ids=allowed_set,
        db_path=db_path,
    )
