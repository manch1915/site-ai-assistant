from typing import Any

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardMarkup, Message, ReplyParameters


def build_bot(token: str) -> Bot:
    return Bot(
        token=token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML, link_preview_is_disabled=True),
    )


class AiogramSender:
    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    async def send_message(
        self,
        chat_id: int,
        text: str,
        *,
        reply_to_message_id: int | None = None,
        reply_markup: dict[str, Any] | None = None,
    ) -> Message:
        reply = (
            ReplyParameters(message_id=reply_to_message_id, allow_sending_without_reply=True)
            if reply_to_message_id
            else None
        )
        markup = InlineKeyboardMarkup.model_validate(reply_markup) if reply_markup else None
        return await self.bot.send_message(
            chat_id, text, reply_parameters=reply, reply_markup=markup
        )
