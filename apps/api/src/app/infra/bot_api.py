"""Send-only Telegram client over plain HTTP.

The worker only ever sends messages. aiogram costs about 130 MB of memory just to import,
so it stays in the bot process, which reads updates.
"""

import logging
from dataclasses import dataclass
from typing import Any

import httpx

# httpx logs every request URL at INFO, and Bot API URLs carry the token.
logging.getLogger("httpx").setLevel(logging.WARNING)


class TelegramError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class SentMessage:
    message_id: int


class BotApiSender:
    def __init__(self, token: str, client: httpx.AsyncClient | None = None) -> None:
        self._url = f"https://api.telegram.org/bot{token}/sendMessage"
        self._client = client or httpx.AsyncClient(timeout=15)

    async def send_message(
        self,
        chat_id: int,
        text: str,
        *,
        reply_to_message_id: int | None = None,
        reply_markup: dict[str, Any] | None = None,
    ) -> SentMessage:
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "link_preview_options": {"is_disabled": True},
        }
        if reply_to_message_id:
            payload["reply_parameters"] = {
                "message_id": reply_to_message_id,
                "allow_sending_without_reply": True,
            }
        if reply_markup:
            payload["reply_markup"] = reply_markup
        response = await self._client.post(self._url, json=payload)
        data = response.json()
        if not data.get("ok"):
            # The description is safe to log; the URL with the token is not.
            raise TelegramError(
                f"sendMessage failed: {data.get('description', response.status_code)}"
            )
        return SentMessage(message_id=data["result"]["message_id"])
