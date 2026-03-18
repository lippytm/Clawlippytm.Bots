"""
Tools — define, register, and execute callable tools for AI agents.

Usage
-----
Use the ``@tool`` decorator (or subclass ``Tool``) to create tools:

    from clawlippytm_bots.tools import tool

    @tool(description="Return the current UTC date and time as ISO-8601.")
    def get_current_time() -> str:
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()

Then pass the tool to an Agent:

    agent = Agent(llm=client, tools=[get_current_time])
"""

from __future__ import annotations

import inspect
import json
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class ToolParameter:
    name: str
    type: str  # JSON Schema type string
    description: str
    required: bool = True


@dataclass
class Tool:
    """Wraps a Python callable so it can be described to an LLM and executed."""

    name: str
    description: str
    func: Callable[..., Any]
    parameters: list[ToolParameter] = field(default_factory=list)

    def __call__(self, **kwargs: Any) -> Any:
        return self.func(**kwargs)

    def to_openai_schema(self) -> dict:
        """Return an OpenAI function-calling schema dict."""
        props: dict[str, dict] = {}
        required: list[str] = []
        for p in self.parameters:
            props[p.name] = {"type": p.type, "description": p.description}
            if p.required:
                required.append(p.name)
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": props,
                    "required": required,
                },
            },
        }

    def to_anthropic_schema(self) -> dict:
        """Return an Anthropic tool definition dict."""
        props: dict[str, dict] = {}
        required: list[str] = []
        for p in self.parameters:
            props[p.name] = {"type": p.type, "description": p.description}
            if p.required:
                required.append(p.name)
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": {
                "type": "object",
                "properties": props,
                "required": required,
            },
        }

    def execute_from_json(self, arguments: str | dict) -> str:
        """Parse JSON arguments and call the tool; always returns a string."""
        if isinstance(arguments, str):
            try:
                kwargs = json.loads(arguments)
            except json.JSONDecodeError:
                return f"ERROR: invalid JSON arguments: {arguments!r}"
        else:
            kwargs = arguments
        try:
            result = self.func(**kwargs)
            return str(result) if result is not None else ""
        except Exception as exc:
            return f"ERROR: {exc}"


# ---------------------------------------------------------------------------
# Decorator helpers
# ---------------------------------------------------------------------------

_PY_TO_JSON: dict[str, str] = {
    "str": "string",
    "int": "integer",
    "float": "number",
    "bool": "boolean",
    "list": "array",
    "dict": "object",
    "None": "null",
}


def _py_type_to_json(annotation: Any) -> str:
    """Best-effort conversion of a Python annotation to a JSON Schema type."""
    if annotation is inspect.Parameter.empty:
        return "string"
    name = getattr(annotation, "__name__", str(annotation))
    return _PY_TO_JSON.get(name, "string")


def tool(description: str, name: str | None = None) -> Callable[[Callable], Tool]:
    """Decorator that wraps a plain Python function as a ``Tool``.

    Parameters from the function signature are introspected automatically.
    Docstrings for each parameter can be provided in Google-style format, but
    the decorator does not require them.
    """

    def decorator(func: Callable) -> Tool:
        tool_name = name or func.__name__
        sig = inspect.signature(func)
        params: list[ToolParameter] = []
        for param_name, param in sig.parameters.items():
            annotation = param.annotation
            json_type = _py_type_to_json(annotation)
            params.append(
                ToolParameter(
                    name=param_name,
                    type=json_type,
                    description=param_name.replace("_", " "),
                    required=param.default is inspect.Parameter.empty,
                )
            )
        return Tool(
            name=tool_name,
            description=description,
            func=func,
            parameters=params,
        )

    return decorator


# ---------------------------------------------------------------------------
# Built-in tools
# ---------------------------------------------------------------------------


@tool(description="Return the current UTC date and time as an ISO-8601 string.")
def get_current_time() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


@tool(description="Fetch the plain-text content of a URL (GET request, no JavaScript).")
def fetch_url(url: str) -> str:
    try:
        import httpx

        resp = httpx.get(url, follow_redirects=True, timeout=15)
        resp.raise_for_status()
        return resp.text[:8000]  # truncate to avoid overwhelming the context
    except Exception as exc:
        return f"ERROR fetching {url!r}: {exc}"


@tool(description="Read the contents of a local file and return them as a string.")
def read_file(path: str) -> str:
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except Exception as exc:
        return f"ERROR reading {path!r}: {exc}"


@tool(description="Write text to a local file (overwrites if it already exists).")
def write_file(path: str, content: str) -> str:
    try:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content)
        return f"Wrote {len(content)} characters to {path!r}."
    except Exception as exc:
        return f"ERROR writing {path!r}: {exc}"


@tool(description=(
    "Run a shell command and return its stdout+stderr (max 4 KB). "
    "WARNING: only pass trusted commands — arbitrary shell injection is possible."
))
def run_shell(command: str) -> str:
    import subprocess

    try:
        result = subprocess.run(
            command,
            shell=True,  # noqa: S602 — intentional; callers must sanitise input
            capture_output=True,
            text=True,
            timeout=30,
        )
        output = result.stdout + result.stderr
        return output[:4096] or "(no output)"
    except Exception as exc:
        return f"ERROR: {exc}"


BUILTIN_TOOLS: list[Tool] = [get_current_time, fetch_url, read_file, write_file, run_shell]
