from __future__ import annotations

import logging
from datetime import datetime

import discord

from ncaam_picks_bot.config import Config
from ncaam_picks_bot.db import (
    build_message_record,
    connect,
    init_db,
    insert_message,
    insert_picks,
    insert_rejected_lines,
    pick_date_from_created,
)
from ncaam_picks_bot.parser import has_correction_header, parse_message_lines

LOGGER = logging.getLogger(__name__)


class PicksBot(discord.Client):
    def __init__(self, config: Config) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        self.config = config
        self.conn = connect(config.db_path)
        init_db(self.conn)

    async def on_ready(self) -> None:
        LOGGER.info("Logged in as %s", self.user)

    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return
        if message.channel.id != self.config.channel_id:
            return
        if self.config.allowed_author_ids and message.author.id not in self.config.allowed_author_ids:
            return

        content = message.content or ""
        lines = content.splitlines()
        is_correction = has_correction_header(lines)
        created_at = message.created_at

        record = build_message_record(
            message_id=str(message.id),
            author_id=str(message.author.id),
            channel_id=str(message.channel.id),
            created_at=created_at,
            is_correction=is_correction,
            raw_content=content,
        )
        if not insert_message(self.conn, record):
            return

        picks, rejected = parse_message_lines(lines)
        pick_date = pick_date_from_created(created_at)

        inserted, replaced = insert_picks(
            self.conn,
            message_id=str(message.id),
            pick_date=pick_date,
            picks=picks,
            is_correction=is_correction,
        )
        rejected_count = insert_rejected_lines(
            self.conn, message_id=str(message.id), rejected_lines=rejected
        )

        LOGGER.info(
            "Processed message %s: picks=%s replaced=%s rejected=%s",
            message.id,
            inserted,
            replaced,
            rejected_count,
        )


def run_bot(config: Config) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    bot = PicksBot(config)
    bot.run(config.discord_token)
