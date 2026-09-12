#!/usr/bin/env python3
"""CLI for observation pack archive, recall, and list."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _common as c

_TYPE_HINTS = {
    ".txt": " 文本",
    ".log": " 日志",
    ".md": " Markdown",
    ".json": " JSON",
    ".py": " Python",
    ".yaml": " YAML",
    ".yml": " YAML",
    ".xml": " XML",
    ".csv": " CSV",
    ".html": " HTML",
    ".js": " JavaScript",
    ".ts": " TypeScript",
}


def _type_hint(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in _TYPE_HINTS:
        return _TYPE_HINTS[ext]
    return f" {ext}" if ext else ""


def build_summary(text: str, path: Path) -> str:
    lines = text.splitlines()
    first_three = "\n".join(lines[:3])
    n = len(lines) if text else 0
    return f"{first_three}\n(共 {n} 行){_type_hint(path)}"


def cmd_archive(args: argparse.Namespace) -> int:
    file_path = Path(args.file_path)
    if not file_path.is_file():
        return c.EXIT_CALL

    c.ensure_runtime()
    cfg = c.load_config()
    op_cfg = cfg.get("observationPack", {})
    if not op_cfg.get("enabled", True):
        return c.EXIT_DECLINE

    try:
        text = file_path.read_text(encoding="utf-8")
    except OSError:
        return c.EXIT_CALL

    tokens = c.approx_tokens(text)
    threshold = (
        args.threshold
        if args.threshold is not None
        else op_cfg.get("tokenThreshold", 2000)
    )
    if tokens < threshold:
        return c.EXIT_DECLINE

    sid = args.session or c.resolve_session_id()
    handle = c.new_handle()
    archived_path = c.session_dir(sid) / f"{handle}.txt"
    try:
        archived_path.write_text(text, encoding="utf-8")
    except OSError as e:
        print(str(e), file=sys.stderr)
        return c.EXIT_IO

    summary = build_summary(text, file_path)
    source_path = str(file_path.resolve())
    try:
        c.append_event(
            sid,
            "observation_pack",
            {
                "action": "archive",
                "handle": handle,
                "source_path": source_path,
                "approx_tokens": tokens,
            },
        )
    except OSError as e:
        print(str(e), file=sys.stderr)
        return c.EXIT_IO

    print(
        json.dumps(
            {
                "handle": handle,
                "approx_tokens": tokens,
                "archived_path": str(archived_path),
                "summary": summary,
            },
            ensure_ascii=False,
        )
    )
    return c.EXIT_OK


def _slice_by_tokens(text: str, offset_tokens: int, max_tokens: int) -> str:
    words = text.split()
    return " ".join(words[offset_tokens : offset_tokens + max_tokens])


def _archive_event_meta(session_id: str) -> dict[str, dict]:
    """Latest observation_pack archive event per handle."""
    events_path = c.session_dir(session_id) / "events.jsonl"
    if not events_path.is_file():
        return {}
    meta: dict[str, dict] = {}
    for line in events_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("mechanism") != "observation_pack":
            continue
        payload = event.get("payload") or {}
        if payload.get("action") != "archive":
            continue
        handle = payload.get("handle")
        if not handle:
            continue
        meta[handle] = {
            "source_path": payload.get("source_path", ""),
            "approx_tokens": payload.get("approx_tokens", 0),
        }
    return meta


def cmd_recall(args: argparse.Namespace) -> int:
    sid = args.session or c.resolve_session_id()
    archived_path = c.session_dir(sid) / f"{args.handle}.txt"
    if not archived_path.is_file():
        return c.EXIT_STATE

    try:
        text = archived_path.read_text(encoding="utf-8")
    except OSError as e:
        print(str(e), file=sys.stderr)
        return c.EXIT_IO

    slice_text = _slice_by_tokens(text, args.offset_tokens, args.max_tokens)
    print(slice_text, end="")
    return c.EXIT_OK


def cmd_list(args: argparse.Namespace) -> int:
    sid = args.session or c.resolve_session_id()
    session_path = c.session_dir(sid)
    meta = _archive_event_meta(sid)

    rows = []
    for path in session_path.glob("*.txt"):
        handle = path.stem
        if not c.HANDLE_RE.fullmatch(handle):
            continue
        info = meta.get(handle, {})
        rows.append(
            {
                "handle": handle,
                "approx_tokens": info.get("approx_tokens", c.approx_tokens(path.read_text(encoding="utf-8"))),
                "source_path": info.get("source_path", ""),
            }
        )

    rows.sort(key=lambda row: row["handle"])
    print(json.dumps(rows, ensure_ascii=False))
    return c.EXIT_OK


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Token-saver observation pack")
    sub = parser.add_subparsers(dest="command", required=True)

    p_archive = sub.add_parser("archive", help="Archive a large observation file")
    p_archive.add_argument("file_path", help="Path to the file to archive")
    p_archive.add_argument("--session", help="Session id (default: resolve from cwd/env)")
    p_archive.add_argument(
        "--threshold",
        type=int,
        help="Token threshold override (default: config observationPack.tokenThreshold)",
    )
    p_archive.set_defaults(func=cmd_archive)

    p_recall = sub.add_parser("recall", help="Recall archived content by handle")
    p_recall.add_argument("handle", help="Archive handle")
    p_recall.add_argument("--session", help="Session id")
    p_recall.add_argument("--max-tokens", type=int, default=500)
    p_recall.add_argument("--offset-tokens", type=int, default=0)
    p_recall.set_defaults(func=cmd_recall)

    p_list = sub.add_parser("list", help="List archived handles")
    p_list.add_argument("--session", help="Session id")
    p_list.set_defaults(func=cmd_list)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
