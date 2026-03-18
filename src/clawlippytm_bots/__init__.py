"""
Clawlippytm Bots — Full Stack AI Toolkits.

Exports the primary public surface:
  - LLMClient       multi-provider LLM wrapper (OpenAI, Anthropic)
  - Agent           task-based agent loop with tool use
  - Tool / tool     decorator for registering custom tools
  - Memory          conversation context manager
  - PromptTemplate  reusable / parameterised prompt templates
"""

from .agent import Agent
from .llm import LLMClient, LLMConfig, Message, Role
from .memory import Memory
from .prompts import PromptTemplate
from .tools import Tool, tool

__all__ = [
    "Agent",
    "LLMClient",
    "LLMConfig",
    "Message",
    "Role",
    "Memory",
    "PromptTemplate",
    "Tool",
    "tool",
]
