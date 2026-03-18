"""
LLM client — thin, unified wrapper around OpenAI and Anthropic APIs.

Supports:
 - Chat completions (sync and async)
 - Streaming responses
 - Automatic retries via tenacity
 - Token counting helpers (via tiktoken for OpenAI models)
"""

from __future__ import annotations

import os
from enum import Enum
from typing import AsyncIterator, Iterator

from pydantic import BaseModel, Field
from tenacity import retry, stop_after_attempt, wait_exponential


class Role(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class Message(BaseModel):
    role: Role
    content: str
    name: str | None = None  # used for tool result messages

    def to_openai_dict(self) -> dict:
        d: dict = {"role": self.role.value, "content": self.content}
        if self.name:
            d["name"] = self.name
        return d

    def to_anthropic_dict(self) -> dict:
        return {"role": self.role.value, "content": self.content}


class Provider(str, Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


class LLMConfig(BaseModel):
    provider: Provider = Provider.OPENAI
    model: str = "gpt-4o-mini"
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=2048, gt=0)
    api_key: str | None = None
    base_url: str | None = None
    system_prompt: str = "You are a helpful AI assistant."


class LLMClient:
    """Unified LLM client supporting OpenAI and Anthropic providers."""

    def __init__(self, config: LLMConfig | None = None) -> None:
        self.config = config or LLMConfig()
        self._openai_client = None
        self._anthropic_client = None

    # ------------------------------------------------------------------
    # Lazy client initialisation
    # ------------------------------------------------------------------

    def _get_openai(self):
        if self._openai_client is None:
            try:
                from openai import OpenAI  # type: ignore[import-untyped]
            except ImportError as exc:
                raise ImportError("Install 'openai' to use the OpenAI provider.") from exc
            api_key = self.config.api_key or os.getenv("OPENAI_API_KEY")
            kwargs: dict = {"api_key": api_key}
            if self.config.base_url:
                kwargs["base_url"] = self.config.base_url
            self._openai_client = OpenAI(**kwargs)
        return self._openai_client

    def _get_anthropic(self):
        if self._anthropic_client is None:
            try:
                import anthropic  # type: ignore[import-untyped]
            except ImportError as exc:
                raise ImportError("Install 'anthropic' to use the Anthropic provider.") from exc
            api_key = self.config.api_key or os.getenv("ANTHROPIC_API_KEY")
            self._anthropic_client = anthropic.Anthropic(api_key=api_key)
        return self._anthropic_client

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def complete(self, messages: list[Message]) -> Message:
        """Return a single assistant reply (sync, non-streaming)."""
        if self.config.provider == Provider.OPENAI:
            return self._complete_openai(messages)
        return self._complete_anthropic(messages)

    def stream(self, messages: list[Message]) -> Iterator[str]:
        """Yield response text chunks as they arrive (sync streaming)."""
        if self.config.provider == Provider.OPENAI:
            yield from self._stream_openai(messages)
        else:
            yield from self._stream_anthropic(messages)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def acomplete(self, messages: list[Message]) -> Message:
        """Return a single assistant reply (async, non-streaming)."""
        if self.config.provider == Provider.OPENAI:
            return await self._acomplete_openai(messages)
        return await self._acomplete_anthropic(messages)

    async def astream(self, messages: list[Message]) -> AsyncIterator[str]:
        """Yield response text chunks as they arrive (async streaming)."""
        if self.config.provider == Provider.OPENAI:
            async for chunk in self._astream_openai(messages):
                yield chunk
        else:
            async for chunk in self._astream_anthropic(messages):
                yield chunk

    def count_tokens(self, text: str) -> int:
        """Approximate token count for a string (OpenAI tiktoken when available)."""
        try:
            import tiktoken  # type: ignore[import-untyped]

            enc = tiktoken.encoding_for_model(self.config.model)
            return len(enc.encode(text))
        except Exception:
            # Fallback: ~4 chars per token
            return max(1, len(text) // 4)

    # ------------------------------------------------------------------
    # OpenAI internals
    # ------------------------------------------------------------------

    def _build_openai_messages(self, messages: list[Message]) -> list[dict]:
        result = [{"role": "system", "content": self.config.system_prompt}]
        result.extend(m.to_openai_dict() for m in messages)
        return result

    def _complete_openai(self, messages: list[Message]) -> Message:
        client = self._get_openai()
        resp = client.chat.completions.create(
            model=self.config.model,
            messages=self._build_openai_messages(messages),
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
        )
        return Message(role=Role.ASSISTANT, content=resp.choices[0].message.content or "")

    def _stream_openai(self, messages: list[Message]) -> Iterator[str]:
        client = self._get_openai()
        with client.chat.completions.stream(
            model=self.config.model,
            messages=self._build_openai_messages(messages),
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
        ) as stream:
            for text in stream.text_stream:
                yield text

    async def _acomplete_openai(self, messages: list[Message]) -> Message:
        try:
            from openai import AsyncOpenAI  # type: ignore[import-untyped]
        except ImportError as exc:
            raise ImportError("Install 'openai' to use the OpenAI provider.") from exc
        api_key = self.config.api_key or os.getenv("OPENAI_API_KEY")
        kwargs: dict = {"api_key": api_key}
        if self.config.base_url:
            kwargs["base_url"] = self.config.base_url
        client = AsyncOpenAI(**kwargs)
        resp = await client.chat.completions.create(
            model=self.config.model,
            messages=self._build_openai_messages(messages),
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
        )
        return Message(role=Role.ASSISTANT, content=resp.choices[0].message.content or "")

    async def _astream_openai(self, messages: list[Message]) -> AsyncIterator[str]:
        try:
            from openai import AsyncOpenAI  # type: ignore[import-untyped]
        except ImportError as exc:
            raise ImportError("Install 'openai' to use the OpenAI provider.") from exc
        api_key = self.config.api_key or os.getenv("OPENAI_API_KEY")
        kwargs: dict = {"api_key": api_key}
        if self.config.base_url:
            kwargs["base_url"] = self.config.base_url
        client = AsyncOpenAI(**kwargs)
        async with client.chat.completions.stream(
            model=self.config.model,
            messages=self._build_openai_messages(messages),
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
        ) as stream:
            async for text in stream.text_stream:
                yield text

    # ------------------------------------------------------------------
    # Anthropic internals
    # ------------------------------------------------------------------

    def _build_anthropic_messages(self, messages: list[Message]) -> list[dict]:
        return [m.to_anthropic_dict() for m in messages if m.role != Role.SYSTEM]

    def _complete_anthropic(self, messages: list[Message]) -> Message:
        client = self._get_anthropic()
        resp = client.messages.create(
            model=self.config.model,
            system=self.config.system_prompt,
            messages=self._build_anthropic_messages(messages),
            max_tokens=self.config.max_tokens,
        )
        content = resp.content[0].text if resp.content else ""
        return Message(role=Role.ASSISTANT, content=content)

    def _stream_anthropic(self, messages: list[Message]) -> Iterator[str]:
        client = self._get_anthropic()
        with client.messages.stream(
            model=self.config.model,
            system=self.config.system_prompt,
            messages=self._build_anthropic_messages(messages),
            max_tokens=self.config.max_tokens,
        ) as stream:
            yield from stream.text_stream

    async def _acomplete_anthropic(self, messages: list[Message]) -> Message:
        try:
            import anthropic  # type: ignore[import-untyped]
        except ImportError as exc:
            raise ImportError("Install 'anthropic' to use the Anthropic provider.") from exc
        api_key = self.config.api_key or os.getenv("ANTHROPIC_API_KEY")
        client = anthropic.AsyncAnthropic(api_key=api_key)
        resp = await client.messages.create(
            model=self.config.model,
            system=self.config.system_prompt,
            messages=self._build_anthropic_messages(messages),
            max_tokens=self.config.max_tokens,
        )
        content = resp.content[0].text if resp.content else ""
        return Message(role=Role.ASSISTANT, content=content)

    async def _astream_anthropic(self, messages: list[Message]) -> AsyncIterator[str]:
        try:
            import anthropic  # type: ignore[import-untyped]
        except ImportError as exc:
            raise ImportError("Install 'anthropic' to use the Anthropic provider.") from exc
        api_key = self.config.api_key or os.getenv("ANTHROPIC_API_KEY")
        client = anthropic.AsyncAnthropic(api_key=api_key)
        async with client.messages.stream(
            model=self.config.model,
            system=self.config.system_prompt,
            messages=self._build_anthropic_messages(messages),
            max_tokens=self.config.max_tokens,
        ) as stream:
            async for text in stream.text_stream:
                yield text
