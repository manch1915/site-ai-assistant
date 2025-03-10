from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from typing import Protocol, cast

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam

from app.config import Settings
from app.domain.prompting import ChatMessage


@dataclass(frozen=True, slots=True)
class Usage:
    tokens_in: int
    tokens_out: int


@dataclass(frozen=True, slots=True)
class Delta:
    text: str = ""
    usage: Usage | None = None


class ChatModel(Protocol):
    def stream(self, messages: Sequence[ChatMessage]) -> AsyncIterator[Delta]: ...


class OpenAIChatModel:
    def __init__(
        self, client: AsyncOpenAI, model: str, max_tokens: int, temperature: float
    ) -> None:
        self.client = client
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature

    async def stream(self, messages: Sequence[ChatMessage]) -> AsyncIterator[Delta]:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=cast(
                list[ChatCompletionMessageParam],
                [{"role": m.role, "content": m.content} for m in messages],
            ),
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            stream=True,
            stream_options={"include_usage": True},
        )
        async for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield Delta(text=chunk.choices[0].delta.content)
            if chunk.usage:
                yield Delta(usage=Usage(chunk.usage.prompt_tokens, chunk.usage.completion_tokens))


def build_chat_model(settings: Settings) -> ChatModel | None:
    if not settings.llm_enabled:
        return None
    client = AsyncOpenAI(base_url=settings.llm_base_url, api_key=settings.llm_api_key, timeout=30)
    return OpenAIChatModel(
        client, settings.llm_model, settings.llm_max_tokens, settings.llm_temperature
    )
