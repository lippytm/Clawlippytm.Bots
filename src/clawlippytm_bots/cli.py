"""
Command-line interface for Clawlippytm.Bots.

Provides the ``clawbot`` command with three sub-commands:

``scrape``
    Scrape a single URL and print / save structured data as JSON.

``clone``
    Clone an entire website to a local directory.

``connections``
    Build a URL connection graph and export it in JSON, CSV, or DOT format.

Usage examples::

    clawbot scrape https://example.com
    clawbot scrape https://example.com --output result.json

    clawbot clone https://example.com --output ./clone --depth 2

    clawbot connections https://example.com --output graph.json
    clawbot connections https://example.com --format csv --output edges.csv
    clawbot connections https://example.com --format dot --output graph.dot
"""

from __future__ import annotations

import json
import sys

import click
import colorama

from clawlippytm_bots import Scraper, SiteCloner, ConnectionsBuilder

colorama.init(autoreset=True)

_BANNER = (
    colorama.Fore.CYAN
    + r"""
  ___  _                 _   _         _
 / __|| |  __ _ __ __ | | (_)  _ __  | |_  _  _  _ __
| (__ | | / _` |\ V / | |_| | | '_ \ | __|| || || '  \
 \___||_| \__,_| \_/   \__|_| | .__/  \__| \_, ||_|_|_|
                               |_|          |__/
"""
    + colorama.Style.RESET_ALL
    + colorama.Fore.YELLOW
    + "  Clawlippytm.Bots v1.0.0 — The Ultimate Scraper Cloner & Connections Builder\n"
    + colorama.Style.RESET_ALL
)


@click.group()
def main() -> None:
    """Clawlippytm.Bots — scrape, clone, and map the web."""
    click.echo(_BANNER)


# ---------------------------------------------------------------------------
# scrape
# ---------------------------------------------------------------------------


@main.command("scrape")
@click.argument("url")
@click.option(
    "--output",
    "-o",
    default=None,
    metavar="FILE",
    help="Save results as JSON to FILE instead of printing to stdout.",
)
@click.option(
    "--rate-limit",
    default=0.0,
    metavar="SECONDS",
    show_default=True,
    help="Minimum seconds between requests.",
)
@click.option(
    "--timeout",
    default=30,
    metavar="SECONDS",
    show_default=True,
    help="Per-request timeout in seconds.",
)
@click.option(
    "--retries",
    default=3,
    show_default=True,
    help="Number of retry attempts on transient errors.",
)
def scrape_cmd(
    url: str,
    output: str | None,
    rate_limit: float,
    timeout: int,
    retries: int,
) -> None:
    """Scrape URL and extract page metadata, links, and assets.

    Outputs structured JSON data to stdout or to an output file.

    \b
    Examples:
      clawbot scrape https://example.com
      clawbot scrape https://example.com -o result.json
    """
    click.echo(
        colorama.Fore.GREEN + f"[scrape] Fetching {url}" + colorama.Style.RESET_ALL
    )
    scraper = Scraper(rate_limit=rate_limit, timeout=timeout, retries=retries)
    try:
        result = scraper.scrape(url)
    except Exception as exc:
        click.echo(
            colorama.Fore.RED + f"[error] {exc}" + colorama.Style.RESET_ALL,
            err=True,
        )
        sys.exit(1)

    payload = json.dumps(result, indent=2, ensure_ascii=False)

    if output:
        with open(output, "w", encoding="utf-8") as fh:
            fh.write(payload)
        click.echo(
            colorama.Fore.GREEN
            + f"[scrape] Saved to {output}"
            + colorama.Style.RESET_ALL
        )
    else:
        click.echo(payload)

    click.echo(
        colorama.Fore.CYAN
        + f"[scrape] Done — found {len(result['links'])} link(s), "
        f"{len(result['images'])} image(s)."
        + colorama.Style.RESET_ALL
    )


# ---------------------------------------------------------------------------
# clone
# ---------------------------------------------------------------------------


@main.command("clone")
@click.argument("url")
@click.option(
    "--output",
    "-o",
    default="./clone",
    show_default=True,
    metavar="DIR",
    help="Directory to write the cloned site into.",
)
@click.option(
    "--depth",
    default=2,
    show_default=True,
    help="Maximum crawl depth.  Use -1 for unlimited.",
)
@click.option(
    "--rate-limit",
    default=0.5,
    metavar="SECONDS",
    show_default=True,
    help="Minimum seconds between requests.",
)
@click.option(
    "--no-robots",
    is_flag=True,
    default=False,
    help="Ignore robots.txt restrictions.",
)
@click.option(
    "--timeout",
    default=30,
    metavar="SECONDS",
    show_default=True,
    help="Per-request timeout in seconds.",
)
def clone_cmd(
    url: str,
    output: str,
    depth: int,
    rate_limit: float,
    no_robots: bool,
    timeout: int,
) -> None:
    """Clone an entire website to a local directory.

    Crawls the site starting from URL, downloads all pages and assets, and
    rewrites internal links so the clone is browsable offline.

    \b
    Examples:
      clawbot clone https://example.com -o ./mysite
      clawbot clone https://example.com --depth 3 --no-robots
    """
    effective_depth: int | None = None if depth < 0 else depth
    click.echo(
        colorama.Fore.GREEN
        + f"[clone] Cloning {url} → {output} (depth={depth})"
        + colorama.Style.RESET_ALL
    )
    cloner = SiteCloner(
        depth=effective_depth,
        rate_limit=rate_limit,
        timeout=timeout,
        respect_robots=not no_robots,
    )
    try:
        stats = cloner.clone(url, output_dir=output)
    except Exception as exc:
        click.echo(
            colorama.Fore.RED + f"[error] {exc}" + colorama.Style.RESET_ALL,
            err=True,
        )
        sys.exit(1)

    click.echo(
        colorama.Fore.CYAN
        + f"[clone] Done — {stats['pages_cloned']} page(s), "
        f"{stats['assets_cloned']} asset(s), {stats['errors']} error(s)."
        + colorama.Style.RESET_ALL
    )
    click.echo(
        colorama.Fore.CYAN
        + f"[clone] Output: {stats['output_dir']}"
        + colorama.Style.RESET_ALL
    )


# ---------------------------------------------------------------------------
# connections
# ---------------------------------------------------------------------------


@main.command("connections")
@click.argument("url")
@click.option(
    "--output",
    "-o",
    default="connections.json",
    show_default=True,
    metavar="FILE",
    help="Destination file for the exported graph.",
)
@click.option(
    "--format",
    "fmt",
    default="json",
    type=click.Choice(["json", "csv", "dot"], case_sensitive=False),
    show_default=True,
    help="Export format.",
)
@click.option(
    "--depth",
    default=3,
    show_default=True,
    help="Maximum crawl depth.  Use -1 for unlimited.",
)
@click.option(
    "--rate-limit",
    default=0.5,
    metavar="SECONDS",
    show_default=True,
    help="Minimum seconds between requests.",
)
@click.option(
    "--no-external",
    is_flag=True,
    default=False,
    help="Exclude edges to external domains.",
)
@click.option(
    "--timeout",
    default=30,
    metavar="SECONDS",
    show_default=True,
    help="Per-request timeout in seconds.",
)
def connections_cmd(
    url: str,
    output: str,
    fmt: str,
    depth: int,
    rate_limit: float,
    no_external: bool,
    timeout: int,
) -> None:
    """Build a URL connection graph starting from URL.

    Crawls the site and maps hyperlink relationships between pages, then
    exports the result in the chosen format.

    \b
    Examples:
      clawbot connections https://example.com
      clawbot connections https://example.com --format csv -o edges.csv
      clawbot connections https://example.com --format dot -o graph.dot
    """
    effective_depth: int | None = None if depth < 0 else depth
    click.echo(
        colorama.Fore.GREEN
        + f"[connections] Building graph for {url} (depth={depth})"
        + colorama.Style.RESET_ALL
    )
    builder = ConnectionsBuilder(
        depth=effective_depth,
        rate_limit=rate_limit,
        timeout=timeout,
        include_external=not no_external,
    )
    try:
        graph = builder.build(url)
    except Exception as exc:
        click.echo(
            colorama.Fore.RED + f"[error] {exc}" + colorama.Style.RESET_ALL,
            err=True,
        )
        sys.exit(1)

    if fmt == "json":
        builder.export_json(graph, output)
    elif fmt == "csv":
        builder.export_csv(graph, output)
    elif fmt == "dot":
        builder.export_dot(graph, output)

    stats = graph["stats"]
    click.echo(
        colorama.Fore.CYAN
        + f"[connections] Done — {stats['node_count']} node(s), "
        f"{stats['edge_count']} edge(s) "
        f"({stats['internal_edges']} internal, {stats['external_edges']} external)."
        + colorama.Style.RESET_ALL
    )
    if stats["top_pages"]:
        click.echo(
            colorama.Fore.CYAN
            + "[connections] Top pages by degree:"
            + colorama.Style.RESET_ALL
        )
        for page in stats["top_pages"][:5]:
            nd = graph["nodes"][page]
            click.echo(
                f"  {page}  (in={nd['in_degree']}, out={nd['out_degree']})"
            )
    click.echo(
        colorama.Fore.CYAN
        + f"[connections] Saved to {output}"
        + colorama.Style.RESET_ALL
    )


if __name__ == "__main__":
    main()
