"""
Memory — conversation context manager.

Stores and manages message history with optional token-budget enforcement.
"""

from __future__ import annotations

from collections import deque
from typing import Iterable

from .llm import Message, Role


class Memory:
    """Manages a sliding window of conversation messages.

    Parameters
    ----------
    max_messages:
        Hard cap on the number of messages kept in memory.
        Oldest messages are evicted when the limit is reached.
    token_budget:
        Soft cap on total characters stored (proxy for token budget).
        ``None`` disables the check.
    """

    def __init__(self, max_messages: int = 100, token_budget: int | None = None) -> None:
        self._messages: deque[Message] = deque(maxlen=max_messages)
        self.token_budget = token_budget

    # ------------------------------------------------------------------
    # Mutation helpers
    # ------------------------------------------------------------------

    def add(self, message: Message) -> None:
        """Append a message, evicting old messages if necessary."""
        self._messages.append(message)
        if self.token_budget is not None:
            self._enforce_token_budget()

    def add_user(self, content: str) -> None:
        self.add(Message(role=Role.USER, content=content))

    def add_assistant(self, content: str) -> None:
        self.add(Message(role=Role.ASSISTANT, content=content))

    def add_system(self, content: str) -> None:
        self.add(Message(role=Role.SYSTEM, content=content))

    def extend(self, messages: Iterable[Message]) -> None:
        for m in messages:
            self.add(m)

    def clear(self) -> None:
        self._messages.clear()

    # ------------------------------------------------------------------
    # Access
    # ------------------------------------------------------------------

    @property
    def messages(self) -> list[Message]:
        return list(self._messages)

    def __len__(self) -> int:
        return len(self._messages)

    def __iter__(self):
        return iter(self._messages)

    def last(self, n: int = 1) -> list[Message]:
        """Return the last *n* messages."""
        msgs = list(self._messages)
        return msgs[-n:]

    def by_role(self, role: Role) -> list[Message]:
        """Return all messages with the given role."""
        return [m for m in self._messages if m.role == role]

    def char_count(self) -> int:
        return sum(len(m.content) for m in self._messages)

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _enforce_token_budget(self) -> None:
        """Evict oldest messages (other than system messages at position 0) until
        char_count is within budget."""
        while self.char_count() > self.token_budget and len(self._messages) > 1:  # type: ignore[operator]
            # Pop from left (oldest); preserve a leading system message
            if self._messages[0].role == Role.SYSTEM and len(self._messages) > 2:
                # rotate: remove second message
                system = self._messages.popleft()
                self._messages.popleft()
                self._messages.appendleft(system)
            else:
                self._messages.popleft()
