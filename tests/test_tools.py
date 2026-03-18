"""Tests for tools.py."""

from __future__ import annotations

import json
import unittest.mock as mock

import pytest

from clawlippytm_bots.tools import (
    BUILTIN_TOOLS,
    Tool,
    ToolParameter,
    fetch_url,
    get_current_time,
    read_file,
    run_shell,
    tool,
    write_file,
)


class TestToolDecorator:
    def test_basic_decoration(self):
        @tool(description="Add two numbers")
        def add(a: int, b: int) -> int:
            return a + b

        assert isinstance(add, Tool)
        assert add.name == "add"
        assert add.description == "Add two numbers"
        assert len(add.parameters) == 2

    def test_custom_name(self):
        @tool(description="Noop", name="my_noop")
        def noop() -> None:
            pass

        assert noop.name == "my_noop"

    def test_call_executes_function(self):
        @tool(description="Greet someone")
        def greet(name: str) -> str:
            return f"Hello, {name}!"

        assert greet(name="Alice") == "Hello, Alice!"

    def test_execute_from_json_string_args(self):
        @tool(description="Double a number")
        def double(n: int) -> int:
            return n * 2

        result = double.execute_from_json('{"n": 5}')
        assert result == "10"

    def test_execute_from_json_dict_args(self):
        @tool(description="Noop")
        def noop(x: str) -> str:
            return x

        assert noop.execute_from_json({"x": "hi"}) == "hi"

    def test_execute_from_json_bad_json(self):
        @tool(description="Noop")
        def noop(x: str) -> str:
            return x

        result = noop.execute_from_json("not json {{{")
        assert "ERROR" in result

    def test_execute_from_json_exception_in_func(self):
        @tool(description="Always fails")
        def fail_tool() -> None:
            raise RuntimeError("boom")

        result = fail_tool.execute_from_json("{}")
        assert "ERROR" in result and "boom" in result


class TestOpenAISchema:
    def test_schema_structure(self):
        @tool(description="Say hello")
        def hello(name: str) -> str:
            return f"Hello, {name}"

        schema = hello.to_openai_schema()
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "hello"
        assert "name" in schema["function"]["parameters"]["properties"]
        assert "name" in schema["function"]["parameters"]["required"]


class TestAnthropicSchema:
    def test_schema_structure(self):
        @tool(description="Say hello")
        def hello(name: str) -> str:
            return f"Hello, {name}"

        schema = hello.to_anthropic_schema()
        assert "input_schema" in schema
        assert schema["name"] == "hello"


class TestBuiltinTools:
    def test_get_current_time_returns_iso(self):
        result = get_current_time()
        assert isinstance(result, str)
        # Basic ISO check: contains "T" between date and time
        assert "T" in result

    def test_read_file_nonexistent(self):
        result = read_file(path="/tmp/nonexistent_clawbots_file_12345.txt")
        assert "ERROR" in result

    def test_write_and_read_file(self, tmp_path):
        p = str(tmp_path / "test.txt")
        write_result = write_file(path=p, content="hello world")
        assert "Wrote" in write_result
        read_result = read_file(path=p)
        assert read_result == "hello world"

    def test_run_shell_echo(self):
        result = run_shell(command="echo clawbots")
        assert "clawbots" in result

    def test_run_shell_invalid_command(self):
        result = run_shell(command="__nonexistent_command_clawbots__")
        # Should return stderr output or empty, but not raise
        assert isinstance(result, str)

    def test_fetch_url_bad_host(self):
        result = fetch_url(url="http://this-does-not-exist-clawbots.invalid/")
        assert "ERROR" in result

    def test_builtin_tools_list(self):
        names = [t.name for t in BUILTIN_TOOLS]
        assert "get_current_time" in names
        assert "fetch_url" in names
        assert "read_file" in names
        assert "write_file" in names
        assert "run_shell" in names
