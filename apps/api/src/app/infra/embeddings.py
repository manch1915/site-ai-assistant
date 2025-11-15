import asyncio
import hashlib
import math
import re
import threading
from typing import Any, Protocol

from openai import AsyncOpenAI

from app.config import Settings

_TOKEN = re.compile(r"\w+", re.UNICODE)


class Embedder(Protocol):
    dim: int

    async def embed_passages(self, texts: list[str]) -> list[list[float]]: ...

    async def embed_query(self, text: str) -> list[float]: ...


def _l2(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in vector)) or 1.0
    return [v / norm for v in vector]


class HashEmbedder:
    """Feature hashing over words and character trigrams.

    No semantics, but deterministic and fast: good enough for tests and CI.
    """

    def __init__(self, dim: int) -> None:
        self.dim = dim

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dim
        for token in _TOKEN.findall(text.lower()):
            features = [token] + [token[i : i + 3] for i in range(max(len(token) - 2, 0))]
            for feature in features:
                digest = hashlib.blake2b(feature.encode(), digest_size=8).digest()
                index = int.from_bytes(digest[:4], "little") % self.dim
                sign = 1.0 if digest[4] & 1 else -1.0
                vector[index] += sign * (2.0 if feature == token else 1.0)
        return _l2(vector)

    async def embed_passages(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(t) for t in texts]

    async def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


class LocalEmbedder:
    """multilingual-e5 via fastembed (ONNX on CPU). Expects query:/passage: prefixes."""

    def __init__(self, model_name: str, model_file: str, dim: int) -> None:
        self.model_name = model_name
        self.model_file = model_file
        self.dim = dim
        self._model: Any = None
        self._lock = threading.Lock()

    def _load(self) -> Any:
        with self._lock:
            if self._model is None:
                from fastembed import TextEmbedding  # noqa: PLC0415  (heavy import)
                from fastembed.common.model_description import (  # noqa: PLC0415
                    ModelSource,
                    PoolingType,
                )

                supported = {m["model"] for m in TextEmbedding.list_supported_models()}
                if self.model_name not in supported:
                    TextEmbedding.add_custom_model(
                        model=self.model_name,
                        pooling=PoolingType.MEAN,
                        normalization=True,
                        sources=ModelSource(hf=self.model_name),
                        dim=self.dim,
                        model_file=self.model_file,
                    )
                # The arena keeps the peak of every batch; without it memory goes back down.
                self._model = TextEmbedding(model_name=self.model_name, enable_cpu_mem_arena=False)
        return self._model

    def _run(self, texts: list[str]) -> list[list[float]]:
        model = self._load()
        return [vector.tolist() for vector in model.embed(texts, batch_size=16)]

    async def embed_passages(self, texts: list[str]) -> list[list[float]]:
        return await asyncio.to_thread(self._run, [f"passage: {t}" for t in texts])

    async def embed_query(self, text: str) -> list[float]:
        vectors = await asyncio.to_thread(self._run, [f"query: {text}"])
        return vectors[0]


class OpenAIEmbedder:
    def __init__(self, client: AsyncOpenAI, model: str, dim: int) -> None:
        self.client = client
        self.model = model
        self.dim = dim

    async def _embed(self, texts: list[str]) -> list[list[float]]:
        response = await self.client.embeddings.create(
            model=self.model, input=texts, dimensions=self.dim
        )
        return [_l2(list(item.embedding)) for item in response.data]

    async def embed_passages(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for start in range(0, len(texts), 64):
            out.extend(await self._embed(texts[start : start + 64]))
        return out

    async def embed_query(self, text: str) -> list[float]:
        return (await self._embed([text]))[0]


def build_embedder(settings: Settings) -> Embedder:
    if settings.embeddings_provider == "hash":
        return HashEmbedder(settings.embedding_dim)
    if settings.embeddings_provider == "openai":
        client = AsyncOpenAI(
            base_url=settings.embeddings_base_url or settings.llm_base_url,
            api_key=settings.embeddings_api_key or settings.llm_api_key,
        )
        return OpenAIEmbedder(client, settings.embeddings_model, settings.embedding_dim)
    return LocalEmbedder(
        settings.embeddings_model, settings.embeddings_model_file, settings.embedding_dim
    )
