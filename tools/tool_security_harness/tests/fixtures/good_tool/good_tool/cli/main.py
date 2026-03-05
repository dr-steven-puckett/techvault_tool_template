"""CLI entrypoint for good_tool.

All output to stdout is JSON.
All errors go to stderr WITHOUT Python tracebacks.
"""
from __future__ import annotations

import argparse
import json
import sys


def _cmd_health(_args: argparse.Namespace) -> int:
    print(json.dumps({"status": "ok", "tool": "good_tool"}))
    return 0


def _cmd_search(args: argparse.Namespace) -> int:
    print(json.dumps({"results": [], "query": args.query}))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="good_tool",
        description="good_tool CLI",
    )
    parser.add_argument("--catalog-file", default=None, help="Path to catalog file")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("health", help="Return health status as JSON")

    search_cmd = sub.add_parser("search", help="Search the catalog")
    search_cmd.add_argument("--query", required=True, help="Search query")

    args = parser.parse_args()

    if args.command == "health":
        return _cmd_health(args)
    elif args.command == "search":
        return _cmd_search(args)
    else:
        print(
            json.dumps({"error": "No command specified. Use 'health' or 'search'."}),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
