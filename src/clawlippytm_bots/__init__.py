"""
Clawlippytm.Bots — The ultimate Scraper Cloner Bot and Connections Builder.

Modules:
    scraper     — Scrape web pages: extract links, text, images, assets.
    cloner      — Clone entire websites to local disk with asset rewriting.
    connections — Build and export URL connection graphs.
    cli         — Unified command-line interface (``clawbot`` command).
    utils       — Shared helpers: sessions, URL normalisation, file I/O.
"""

__version__ = "1.0.0"
__author__ = "lippytm"

from clawlippytm_bots.scraper import Scraper
from clawlippytm_bots.cloner import SiteCloner
from clawlippytm_bots.connections import ConnectionsBuilder

__all__ = ["Scraper", "SiteCloner", "ConnectionsBuilder"]
