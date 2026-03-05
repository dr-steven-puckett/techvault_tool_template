"""CLI entrypoint for bad_tool — leaks tracebacks to stderr on error."""
from __future__ import annotations

import argparse
import json
import sys


def main() -> int:
    parser = argparse.ArgumentParser(prog="bad_tool")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("health")
    search_cmd = sub.add_parser("search")
    search_cmd.add_argument("--catalog-file", required=True)
    search_cmd.add_argument("--query", required=True)

    args = parser.parse_args()

    if args.command == "health":
        # Intentionally raise an unhandled exception so Python prints a traceback
        raise RuntimeError("bad_tool health: intentional unhandled exception (security test fixture)")

    print(json.dumps({"error": "No command specified."}), file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
