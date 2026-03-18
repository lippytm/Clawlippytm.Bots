"""Tests for memory.py."""

from __future__ import annotations

from clawlippytm_bots.llm import Message, Role
from clawlippytm_bots.memory import Memory


class TestMemoryBasics:
    def test_add_and_len(self):
        mem = Memory()
        mem.add_user("hello")
        mem.add_assistant("world")
        assert len(mem) == 2

    def test_clear(self):
        mem = Memory()
        mem.add_user("hello")
        mem.clear()
        assert len(mem) == 0

    def test_last(self):
        mem = Memory()
        mem.add_user("a")
        mem.add_assistant("b")
        mem.add_user("c")
        last = mem.last(2)
        assert [m.content for m in last] == ["b", "c"]

    def test_by_role(self):
        mem = Memory()
        mem.add_user("u1")
        mem.add_user("u2")
        mem.add_assistant("a1")
        users = mem.by_role(Role.USER)
        assert len(users) == 2
        assert all(m.role == Role.USER for m in users)

    def test_messages_property_returns_list(self):
        mem = Memory()
        mem.add_user("x")
        assert isinstance(mem.messages, list)

    def test_iter(self):
        mem = Memory()
        mem.add_user("x")
        mem.add_assistant("y")
        contents = [m.content for m in mem]
        assert contents == ["x", "y"]


class TestMemoryMaxMessages:
    def test_eviction_on_overflow(self):
        mem = Memory(max_messages=3)
        for i in range(5):
            mem.add_user(str(i))
        assert len(mem) == 3
        assert [m.content for m in mem] == ["2", "3", "4"]


class TestMemoryTokenBudget:
    def test_token_budget_evicts_old_messages(self):
        mem = Memory(token_budget=20)
        # Each message content is 10 chars
        mem.add_user("a" * 10)  # total=10
        mem.add_user("b" * 10)  # total=20  (at limit)
        mem.add_user("c" * 10)  # total=30  → evict oldest
        assert mem.char_count() <= 20

    def test_system_message_preserved(self):
        mem = Memory(token_budget=20)
        mem.add_system("sys")  # 3 chars
        mem.add_user("a" * 10)
        mem.add_user("b" * 10)  # forces eviction of non-system
        # system message should still be present
        systems = mem.by_role(Role.SYSTEM)
        assert len(systems) == 1
