"""Tests for agent.py — no real LLM calls (mocked)."""

from __future__ import annotations

import unittest.mock as mock

import pytest

from clawlippytm_bots.agent import Agent, AgentResult
from clawlippytm_bots.llm import LLMClient, LLMConfig, Message, Role
from clawlippytm_bots.tools import tool


def _mock_llm_with_responses(*responses: str) -> LLMClient:
    """Build an LLMClient whose complete() cycles through canned responses."""
    client = LLMClient.__new__(LLMClient)
    client.config = LLMConfig()
    client._openai_client = None
    client._anthropic_client = None
    side_effects = [Message(role=Role.ASSISTANT, content=r) for r in responses]
    client.complete = mock.Mock(side_effect=side_effects)
    return client


class TestAgentDirectAnswer:
    def test_single_step_no_tools(self):
        llm = _mock_llm_with_responses("The answer is 42.")
        agent = Agent(llm=llm, tools=[])
        result = agent.run("What is the answer?")
        assert result.answer == "The answer is 42."
        assert result.steps == 1
        assert result.tool_calls == []

    def test_result_type(self):
        llm = _mock_llm_with_responses("Done.")
        agent = Agent(llm=llm, tools=[])
        result = agent.run("Do something.")
        assert isinstance(result, AgentResult)
        assert isinstance(result.messages, list)


class TestAgentToolUse:
    def test_tool_call_and_follow_up(self):
        @tool(description="Return a constant")
        def constant_tool() -> str:
            return "CONSTANT_VALUE"

        llm = _mock_llm_with_responses(
            '<tool_call>\n{"name": "constant_tool", "arguments": {}}\n</tool_call>',
            "The constant value is CONSTANT_VALUE.",
        )
        agent = Agent(llm=llm, tools=[constant_tool])
        result = agent.run("What is the constant?")
        assert "CONSTANT_VALUE" in result.answer
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0]["result"] == "CONSTANT_VALUE"

    def test_unknown_tool_returns_error(self):
        llm = _mock_llm_with_responses(
            '<tool_call>\n{"name": "ghost_tool", "arguments": {}}\n</tool_call>',
            "I could not find the tool.",
        )
        agent = Agent(llm=llm, tools=[])
        result = agent.run("Call ghost_tool.")
        # The tool result message should contain an error
        tool_result_msgs = [
            m for m in result.messages if "<tool_result>" in m.content
        ]
        assert len(tool_result_msgs) == 1
        assert "ERROR" in tool_result_msgs[0].content


class TestAgentMaxSteps:
    def test_max_steps_reached(self):
        # LLM always returns a tool call → agent should hit max_steps
        @tool(description="Loop forever")
        def looping_tool() -> str:
            return "keep going"

        responses = ['<tool_call>\n{"name": "looping_tool", "arguments": {}}\n</tool_call>'] * 3
        llm = _mock_llm_with_responses(*responses)
        agent = Agent(llm=llm, tools=[looping_tool], max_steps=3)
        result = agent.run("Loop forever.")
        assert result.steps == 3


class TestAgentParseToolCall:
    def test_valid_tool_call_block(self):
        agent = Agent(llm=mock.MagicMock(), tools=[])
        call = agent._parse_tool_call(
            '<tool_call>\n{"name": "foo", "arguments": {"x": 1}}\n</tool_call>'
        )
        assert call == {"name": "foo", "arguments": {"x": 1}}

    def test_no_tool_call_returns_none(self):
        agent = Agent(llm=mock.MagicMock(), tools=[])
        assert agent._parse_tool_call("Plain text response.") is None

    def test_malformed_json_returns_none(self):
        agent = Agent(llm=mock.MagicMock(), tools=[])
        assert agent._parse_tool_call("<tool_call>not json</tool_call>") is None
