# Clawlippytm.Bots

> The ultimate Scraper Cloner Bot and Connections Builder — out-does ClawBot and OpenClaw combined, and you own it!

Built and maintained with GitHub Copilot and full-stack AI toolkits.

---

## Features

| Feature | Description |
|---|---|
| **Web Scraper** | Fetches any URL and extracts title, meta tags, Open Graph data, links, images, scripts, and stylesheets. |
| **Site Cloner** | Mirrors an entire website to a local directory — downloads all pages and assets, rewrites links for offline browsing. |
| **Connections Builder** | Crawls a site and builds a directed URL connection graph; exports to JSON, CSV, or Graphviz DOT. |
| **Unified CLI** | Single `clawbot` command with `scrape`, `clone`, and `connections` sub-commands. |
| **Rate Limiting** | Configurable request throttle to avoid overloading servers. |
| **Retry Logic** | Automatic retries with exponential back-off on transient HTTP errors. |
| **robots.txt** | Respects `robots.txt` by default (can be disabled). |

---

## Installation

```bash
pip install -e .
```

Or install with dev dependencies for testing:

```bash
pip install -e ".[dev]"
# or
pip install -r requirements-dev.txt
pip install -e .
```

---

## Quick Start

### Scrape a page

```bash
clawbot scrape https://example.com
clawbot scrape https://example.com --output result.json
```

### Clone a website

```bash
# Clone up to depth 2 (default)
clawbot clone https://example.com --output ./mysite

# Deeper clone, ignore robots.txt
clawbot clone https://example.com --depth 4 --no-robots --output ./mysite
```

### Build a connection graph

```bash
# JSON export (default)
clawbot connections https://example.com --output graph.json

# CSV edge list
clawbot connections https://example.com --format csv --output edges.csv

# Graphviz DOT (render with: dot -Tpng graph.dot -o graph.png)
clawbot connections https://example.com --format dot --output graph.dot
```

---

## Python API

```python
from clawlippytm_bots import Scraper, SiteCloner, ConnectionsBuilder

# --- Scraper ---
scraper = Scraper(rate_limit=1.0)
result = scraper.scrape("https://example.com")
print(result["title"])
print(result["links"][:5])

# Scrape multiple URLs
results = scraper.scrape_many(["https://example.com/a", "https://example.com/b"])

# --- Site Cloner ---
cloner = SiteCloner(depth=2, rate_limit=0.5)
stats = cloner.clone("https://example.com", output_dir="./clone")
print(stats)  # {'pages_cloned': N, 'assets_cloned': N, 'errors': 0, 'output_dir': '...'}

# --- Connections Builder ---
builder = ConnectionsBuilder(depth=3, rate_limit=0.5)
graph = builder.build("https://example.com")

builder.export_json(graph, "connections.json")
builder.export_csv(graph, "edges.csv")
builder.export_dot(graph, "graph.dot")

print(graph["stats"]["top_pages"][:3])
```

---

## Development

```bash
# Install dev dependencies
pip install -r requirements-dev.txt && pip install -e .

# Run tests
pytest

# Lint
flake8 src tests
```

---

## Project Structure

```
Clawlippytm.Bots/
├── pyproject.toml
├── requirements.txt
├── requirements-dev.txt
├── src/
│   └── clawlippytm_bots/
│       ├── __init__.py       # Package exports
│       ├── cli.py            # clawbot CLI (scrape / clone / connections)
│       ├── scraper.py        # Web page scraper
│       ├── cloner.py         # Full-site cloner
│       ├── connections.py    # URL connection graph builder
│       └── utils.py          # Shared helpers
└── tests/
    ├── test_utils.py
    ├── test_scraper.py
    ├── test_cloner.py
    └── test_connections.py
```

---

## License

See [LICENSE](LICENSE).
