#!/usr/bin/env python3
"""CLI for session resolution and event recording."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _common as c


def cmd_ensure(args: argparse.Namespace) -> int:
    cwd = Path(args.cwd) if args.cwd else None
    print(c.resolve_session_id(cwd))
    return c.EXIT_OK


def cmd_record(args: argparse.Namespace) -> int:
    if args.mechanism not in c.MECHANISMS:
        print(f"illegal mechanism: {args.mechanism}", file=sys.stderr)
        return c.EXIT_USAGE
    try:
        if args.payload_file:
            payload = json.loads(Path(args.payload_file).read_text(encoding="utf-8"))
        elif args.payload:
            payload = json.loads(args.payload)
        else:
            payload = {}
    except (OSError, json.JSONDecodeError) as e:
        print(str(e), file=sys.stderr)
        return c.EXIT_USAGE if isinstance(e, json.JSONDecodeError) else c.EXIT_CALL
    sid = args.session or c.resolve_session_id()
    try:
        c.ensure_runtime()
        c.append_event(sid, args.mechanism, payload)
    except OSError as e:
        print(str(e), file=sys.stderr)
        return c.EXIT_IO
    return c.EXIT_OK


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Token-saver session recorder")
    sub = parser.add_subparsers(dest="command", required=True)

    p_ensure = sub.add_parser("ensure-session", help="Resolve or create session id")
    p_ensure.add_argument("--cwd", help="Project directory for session file lookup")
    p_ensure.set_defaults(func=cmd_ensure)

    p_record = sub.add_parser("record", help="Append an event to a session")
    p_record.add_argument("mechanism", help="Mechanism name")
    p_record.add_argument("--session", help="Session id (default: resolve from cwd/env)")
    p_record.add_argument("--payload", help="JSON payload string")
    p_record.add_argument("--payload-file", help="Path to JSON payload file")
    p_record.set_defaults(func=cmd_record)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
