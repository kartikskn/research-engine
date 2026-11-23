"""Command-line helper for checking each build step before the UI exists.

Usage:  python scripts/try_paper.py meta <arxiv link or id>

More commands (source, record, add) are added in later steps.
"""

import argparse
import sys
import urllib.error

from research_engine.arxiv import fetch_metadata, parse_links


def first_id(link: str) -> str:
    ids, _ = parse_links(link)
    if not ids:
        sys.exit(f"Could not find an arXiv id in: {link!r}")
    return ids[0]


def cmd_meta(link: str) -> None:
    try:
        meta = fetch_metadata(first_id(link))
    except (ValueError, urllib.error.URLError) as error:  # not found, or no network / bad certificates
        sys.exit(f"Could not fetch metadata: {error}")
    print(f"id:       {meta.arxiv_id}")
    print(f"title:    {meta.title}")
    print(f"authors:  {', '.join(meta.authors)}")
    print(f"date:     {meta.published}")
    print(f"category: {meta.primary_category}")
    print(f"url:      {meta.arxiv_url}")
    print(f"abstract: {meta.abstract[:300]}...")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    meta = commands.add_parser("meta", help="fetch and print a paper's metadata")
    meta.add_argument("link", help="an arXiv link or id")
    args = parser.parse_args()

    if args.command == "meta":
        cmd_meta(args.link)


if __name__ == "__main__":
    main()
