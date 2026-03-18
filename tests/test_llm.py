"""Tests for llm.py — Message, LLMConfig, LLMClient (no real API calls)."""

from __future__ import annotations

import pytest

from clawlippytm_bots.llm import LLMClient, LLMConfig, Message, Provider, Role


class TestMessage:
    def test_to_openai_dict_basic(self):
        msg = Message(role=Role.USER, content="Hello")
        d = msg.to_openai_dict()
        assert d == {"role": "user", "content": "Hello"}

    def test_to_openai_dict_with_name(self):
        msg = Message(role=Role.TOOL, content="result", name="my_tool")
        d = msg.to_openai_dict()
        assert d["name"] == "my_tool"

    def test_to_anthropic_dict(self):
        msg = Message(role=Role.ASSISTANT, content="Hi there")
        d = msg.to_anthropic_dict()
        assert d == {"role": "assistant", "content": "Hi there"}


class TestLLMConfig:
    def test_defaults(self):
        cfg = LLMConfig()
        assert cfg.provider == Provider.OPENAI
        assert cfg.temperature == 0.7
        assert cfg.max_tokens == 2048

    def test_temperature_validation(self):
        with pytest.raises(Exception):
            LLMConfig(temperature=3.0)  # > 2.0 should fail pydantic

    def test_max_tokens_validation(self):
        with pytest.raises(Exception):
            LLMConfig(max_tokens=0)  # must be > 0


class TestLLMClientTokenCount:
    def test_count_tokens_fallback(self):
        """When tiktoken is unavailable the fallback (len//4) should still return > 0."""
        client = LLMClient(LLMConfig())
        # patch tiktoken to raise so we exercise the fallback path
        import unittest.mock as mock

        with mock.patch("builtins.__import__", side_effect=ImportError):
            count = client.count_tokens("hello world this is a test")
        # fallback: max(1, len("hello world this is a test") // 4)
        assert count >= 1

    def test_count_tokens_empty(self):
        client = LLMClient(LLMConfig())
        import unittest.mock as mock

        with mock.patch("builtins.__import__", side_effect=ImportError):
            count = client.count_tokens("")
        assert count >= 1  # max(1, ...)

    def test_build_openai_messages_includes_system(self):
        cfg = LLMConfig(system_prompt="You are a bot.")
        client = LLMClient(cfg)
        msgs = client._build_openai_messages([Message(role=Role.USER, content="hi")])
        assert msgs[0] == {"role": "system", "content": "You are a bot."}
        assert msgs[1] == {"role": "user", "content": "hi"}

    def test_build_anthropic_messages_excludes_system(self):
        client = LLMClient()
        msgs = client._build_anthropic_messages(
            [
                Message(role=Role.SYSTEM, content="system"),
                Message(role=Role.USER, content="hello"),
            ]
        )
        assert all(m["role"] != "system" for m in msgs)
        assert len(msgs) == 1
