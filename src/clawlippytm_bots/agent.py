"""
Agent — task-based agent loop with tool use.

The Agent repeatedly:
  1. Sends the conversation to the LLM.
  2. Checks whether the response contains a tool-call directive.
  3. Executes the requested tool and appends the result to memory.
  4. Repeats until the LLM produces a plain reply or the step limit is reached.

The tool-call protocol used here is a simple JSON block delimited by
``<tool_call>`` / ``</tool_call>`` XML-style tags, which works with any model
that can follow instructions (no function-calling API required):

    <tool_call>
    {"name": "fetch_url", "arguments": {"url": "https://example.com"}}
    </tool_call>

This keeps the agent model-agnostic and easy to extend.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from .llm import LLMClient, LLMConfig, Message, Role
from .memory import Memory
from .tools import BUILTIN_TOOLS, Tool

_TOOL_CALL_RE = re.compile(r"<tool_call>\s*(.*?)\s*</tool_call>", re.DOTALL)

_AGENT_SYSTEM_PROMPT = """\
You are a powerful AI assistant with access to a set of tools.

To call a tool, emit a block in this exact format (and nothing else in that turn):

<tool_call>
{{"name": "<tool_name>", "arguments": {{...}}}}
</tool_call>

Available tools:
{tool_list}

After receiving a tool result, use it to continue reasoning and eventually give
the user a final answer in plain text (no <tool_call> block).
"""


@dataclass
class AgentResult:
    """Captures the final output and execution trace of an agent run."""

    answer: str
    steps: int
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    messages: list[Message] = field(default_factory=list)


class Agent:
    """An LLM-powered agent that can use tools to complete tasks.

    Parameters
    ----------
    llm:
        A configured :class:`~clawlippytm_bots.llm.LLMClient`.
    tools:
        List of :class:`~clawlippytm_bots.tools.Tool` instances.
        Defaults to :data:`~clawlippytm_bots.tools.BUILTIN_TOOLS`.
    max_steps:
        Maximum number of LLM ↔ tool iterations before giving up.
    memory:
        Optional pre-seeded :class:`~clawlippytm_bots.memory.Memory`.
        A fresh one is created per ``run`` call if not provided.
    verbose:
        If ``True`` the agent prints step-by-step progress to stdout.
    """

    def __init__(
        self,
        llm: LLMClient | None = None,
        tools: list[Tool] | None = None,
        max_steps: int = 10,
        memory: Memory | None = None,
        verbose: bool = False,
    ) -> None:
        self.llm = llm or LLMClient()
        self.tools: dict[str, Tool] = {
            t.name: t for t in (tools if tools is not None else BUILTIN_TOOLS)
        }
        self.max_steps = max_steps
        self.memory = memory
        self.verbose = verbose

    # ------------------------------------------------------------------
    # Public run interface
    # ------------------------------------------------------------------

    def run(self, task: str, *, memory: Memory | None = None) -> AgentResult:
        """Run the agent synchronously on *task* and return an :class:`AgentResult`."""
        mem = memory or self.memory or Memory()
        self._configure_system(mem)
        mem.add_user(task)

        tool_calls: list[dict[str, Any]] = []
        answer = ""
        step = 0

        for step in range(1, self.max_steps + 1):
            response = self.llm.complete(mem.messages)
            mem.add_assistant(response.content)

            if self.verbose:
                print(f"[step {step}] {response.content[:120]!r}")

            tool_call = self._parse_tool_call(response.content)
            if tool_call is None:
                # No tool call → this is the final answer
                answer = response.content
                break

            result = self._execute_tool(tool_call)
            tool_calls.append({"call": tool_call, "result": result})
            mem.add(Message(role=Role.USER, content=f"<tool_result>\n{result}\n</tool_result>"))

            if step == self.max_steps:
                answer = (
                    "I reached the maximum number of steps without completing the task. "
                    f"Last response: {response.content}"
                )

        return AgentResult(
            answer=answer,
            steps=step,
            tool_calls=tool_calls,
            messages=mem.messages,
        )

    async def arun(self, task: str, *, memory: Memory | None = None) -> AgentResult:
        """Run the agent asynchronously on *task*."""
        mem = memory or self.memory or Memory()
        self._configure_system(mem)
        mem.add_user(task)

        tool_calls: list[dict[str, Any]] = []
        answer = ""

        for step in range(1, self.max_steps + 1):
            response = await self.llm.acomplete(mem.messages)
            mem.add_assistant(response.content)

            if self.verbose:
                print(f"[step {step}] {response.content[:120]!r}")

            tool_call = self._parse_tool_call(response.content)
            if tool_call is None:
                answer = response.content
                break

            result = self._execute_tool(tool_call)
            tool_calls.append({"call": tool_call, "result": result})
            mem.add(Message(role=Role.USER, content=f"<tool_result>\n{result}\n</tool_result>"))

            if step == self.max_steps:
                answer = (
                    "I reached the maximum number of steps without completing the task. "
                    f"Last response: {response.content}"
                )

        return AgentResult(
            answer=answer,
            steps=step,
            tool_calls=tool_calls,
            messages=mem.messages,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _configure_system(self, mem: Memory) -> None:
        tool_list = "\n".join(
            f"  - {t.name}: {t.description}" for t in self.tools.values()
        )
        system_content = _AGENT_SYSTEM_PROMPT.format(tool_list=tool_list)
        self.llm.config.system_prompt = system_content

    def _parse_tool_call(self, content: str) -> dict | None:
        match = _TOOL_CALL_RE.search(content)
        if not match:
            return None
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            return None

    def _execute_tool(self, call: dict) -> str:
        name = call.get("name", "")
        args = call.get("arguments", {})
        tool = self.tools.get(name)
        if tool is None:
            return f"ERROR: unknown tool {name!r}. Available: {list(self.tools)}"
        return tool.execute_from_json(args)
