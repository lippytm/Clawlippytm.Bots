# Clawlippytm.Bots

> The ultimate ClawBot and OpenClaw solution is better than both of them combined and Usually free

## Full Stack AI Toolkits

A comprehensive Python toolkit for building LLM-powered bots and agents.  
Supports **OpenAI** and **Anthropic** out of the box, works with any model that
can follow instructions, and ships with a ready-to-use CLI.

---

### Features

| Module | Purpose |
|--------|---------|
| `llm.py` | Thin, unified wrapper around OpenAI & Anthropic chat APIs — sync, async, streaming |
| `agent.py` | Task-based agent loop with model-agnostic tool use (no function-calling API required) |
| `tools.py` | `@tool` decorator + built-in tools: `fetch_url`, `read_file`, `write_file`, `run_shell`, `get_current_time` |
| `memory.py` | Sliding-window conversation manager with optional token budget |
| `prompts.py` | Reusable `{placeholder}` templates — includes SUMMARISE, QA, CODE_REVIEW, EXTRACT_JSON, TRANSLATE |
| `cli.py` | `clawbots` CLI — `chat`, `agent`, `tools`, `run-tool` commands |

---

### Installation

```bash
pip install -e ".[dev]"
```

Requires Python ≥ 3.10.

Set your API key in the environment (or a `.env` file):

```bash
export OPENAI_API_KEY=sk-...
# or
export ANTHROPIC_API_KEY=sk-ant-...
```

---

### Quick Start

#### Python API

```python
from clawlippytm_bots import LLMClient, LLMConfig, Provider, Message, Role

# --- Chat completion ---
client = LLMClient(LLMConfig(provider=Provider.OPENAI, model="gpt-4o-mini"))
reply = client.complete([Message(role=Role.USER, content="Hello!")])
print(reply.content)

# --- Agent with tools ---
from clawlippytm_bots import Agent
from clawlippytm_bots.tools import BUILTIN_TOOLS

agent = Agent(llm=client, tools=BUILTIN_TOOLS)
result = agent.run("What is the current UTC time?")
print(result.answer)

# --- Prompt templates ---
from clawlippytm_bots.prompts import SUMMARISE
prompt = SUMMARISE.render(text="Long article...", max_words="100")
print(prompt)

# --- Custom tools ---
from clawlippytm_bots import tool

@tool(description="Return the square of a number")
def square(n: int) -> int:
    return n * n

agent = Agent(llm=client, tools=[square])
result = agent.run("What is 7 squared?")
print(result.answer)
```

#### CLI

```bash
# Interactive chat
clawbots chat --provider openai --model gpt-4o-mini

# Run a one-shot agent task
clawbots agent "Fetch https://example.com and summarise it in 3 bullet points"

# List all built-in tools
clawbots tools

# Execute a single tool directly
clawbots run-tool get_current_time
clawbots run-tool fetch_url '{"url": "https://example.com"}'
```

---

### Running Tests

```bash
pytest tests/ -v
```

---

### Project Structure

```
src/clawlippytm_bots/
├── __init__.py    # public re-exports
├── llm.py         # LLMClient, LLMConfig, Message, Role
├── agent.py       # Agent, AgentResult
├── tools.py       # Tool, @tool decorator, BUILTIN_TOOLS
├── memory.py      # Memory
├── prompts.py     # PromptTemplate, built-in templates
└── cli.py         # clawbots CLI

tests/
├── test_agent.py
├── test_llm.py
├── test_memory.py
├── test_prompts.py
└── test_tools.py
```

