"""
CLI entry-point for the Full Stack AI Toolkits.

Commands
--------
  clawbots chat       Interactive chat with an LLM.
  clawbots agent      Run an agent task from the command line.
  clawbots run-tool   Execute a single built-in tool directly.
  clawbots tools      List all available built-in tools.
"""

from __future__ import annotations

import os

import click
from dotenv import load_dotenv
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt

load_dotenv()

console = Console()


# ---------------------------------------------------------------------------
# Shared option callbacks
# ---------------------------------------------------------------------------

def _get_llm(provider: str, model: str | None, api_key: str | None):
    from .llm import LLMClient, LLMConfig, Provider

    provider_enum = Provider(provider)
    default_models = {
        Provider.OPENAI: "gpt-4o-mini",
        Provider.ANTHROPIC: "claude-3-haiku-20240307",
    }
    cfg = LLMConfig(
        provider=provider_enum,
        model=model or default_models[provider_enum],
        api_key=api_key,
    )
    return LLMClient(cfg)


# ---------------------------------------------------------------------------
# Root group
# ---------------------------------------------------------------------------

@click.group()
@click.version_option(package_name="clawlippytm-bots")
def main() -> None:
    """Clawlippytm Bots — Full Stack AI Toolkits."""


# ---------------------------------------------------------------------------
# chat command
# ---------------------------------------------------------------------------

@main.command()
@click.option("--provider", default="openai", show_default=True,
              type=click.Choice(["openai", "anthropic"]),
              help="LLM provider to use.")
@click.option("--model", default=None, help="Model name (provider-specific).")
@click.option("--api-key", default=None, envvar=["OPENAI_API_KEY", "ANTHROPIC_API_KEY"],
              help="API key (also read from env vars).")
@click.option("--system", default="You are a helpful AI assistant.",
              show_default=True, help="System prompt.")
def chat(provider: str, model: str | None, api_key: str | None, system: str) -> None:
    """Start an interactive chat session with an LLM."""
    from .llm import Message, Role
    from .memory import Memory

    llm = _get_llm(provider, model, api_key)
    llm.config.system_prompt = system
    mem = Memory()

    console.print(Panel(
        f"[bold green]Clawbots Chat[/]\n"
        f"Provider: [cyan]{provider}[/]  Model: [cyan]{llm.config.model}[/]\n"
        f"Type [bold yellow]exit[/] or [bold yellow]quit[/] to end the session.",
        title="Full Stack AI Toolkits",
    ))

    while True:
        try:
            user_input = Prompt.ask("[bold blue]You[/]")
        except (KeyboardInterrupt, EOFError):
            break

        if user_input.strip().lower() in {"exit", "quit", "q"}:
            break
        if not user_input.strip():
            continue

        mem.add_user(user_input)
        try:
            reply = llm.complete(mem.messages)
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/]")
            continue

        mem.add_assistant(reply.content)
        console.print(Panel(Markdown(reply.content), title="[bold green]Assistant[/]"))

    console.print("[dim]Session ended.[/]")


# ---------------------------------------------------------------------------
# agent command
# ---------------------------------------------------------------------------

@main.command()
@click.argument("task")
@click.option("--provider", default="openai", show_default=True,
              type=click.Choice(["openai", "anthropic"]))
@click.option("--model", default=None)
@click.option("--api-key", default=None)
@click.option("--max-steps", default=10, show_default=True, type=int)
@click.option("--verbose", is_flag=True, default=False)
@click.option("--no-builtin-tools", is_flag=True, default=False,
              help="Disable the built-in tools (shell, file I/O, fetch).")
def agent(
    task: str,
    provider: str,
    model: str | None,
    api_key: str | None,
    max_steps: int,
    verbose: bool,
    no_builtin_tools: bool,
) -> None:
    """Run an AI agent on TASK, using tools as needed."""
    from .agent import Agent
    from .tools import BUILTIN_TOOLS

    llm = _get_llm(provider, model, api_key)
    tools = [] if no_builtin_tools else BUILTIN_TOOLS
    bot = Agent(llm=llm, tools=tools, max_steps=max_steps, verbose=verbose)

    console.print(Panel(f"[bold]Task:[/] {task}", title="Agent", border_style="cyan"))
    with console.status("[bold green]Running agent…"):
        try:
            result = bot.run(task)
        except Exception as exc:
            console.print(f"[red]Agent error: {exc}[/]")
            raise SystemExit(1) from exc

    console.print(Panel(Markdown(result.answer), title="[bold green]Answer[/]"))
    console.print(
        f"[dim]Completed in {result.steps} step(s), "
        f"{len(result.tool_calls)} tool call(s).[/]"
    )


# ---------------------------------------------------------------------------
# tools command
# ---------------------------------------------------------------------------

@main.command(name="tools")
def list_tools() -> None:
    """List all available built-in tools."""
    from .tools import BUILTIN_TOOLS
    from rich.table import Table

    table = Table(title="Built-in Tools", show_lines=True)
    table.add_column("Name", style="bold cyan")
    table.add_column("Description")
    table.add_column("Parameters", style="dim")
    for t in BUILTIN_TOOLS:
        params = ", ".join(p.name for p in t.parameters) or "(none)"
        table.add_row(t.name, t.description, params)
    console.print(table)


# ---------------------------------------------------------------------------
# run-tool command
# ---------------------------------------------------------------------------

@main.command(name="run-tool")
@click.argument("tool_name")
@click.argument("args_json", default="{}")
def run_tool(tool_name: str, args_json: str) -> None:
    """Execute a single built-in tool by name with JSON arguments.

    \b
    Examples:
      clawbots run-tool get_current_time
      clawbots run-tool fetch_url '{"url": "https://example.com"}'
      clawbots run-tool read_file '{"path": "/etc/hostname"}'
    """
    from .tools import BUILTIN_TOOLS

    tool_map = {t.name: t for t in BUILTIN_TOOLS}
    t = tool_map.get(tool_name)
    if t is None:
        console.print(
            f"[red]Unknown tool {tool_name!r}. "
            f"Available: {list(tool_map)}[/]"
        )
        raise SystemExit(1)

    result = t.execute_from_json(args_json)
    console.print(result)
