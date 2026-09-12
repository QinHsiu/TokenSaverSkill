#!/usr/bin/env python3
"""Post-session token savings audit from events.jsonl."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _common as c


def _session_events_path(session_id: str) -> Path:
    return c.runtime_root() / "archive" / session_id / "events.jsonl"


def _load_events(session_id: str) -> list[dict]:
    path = _session_events_path(session_id)
    if not path.is_file():
        return []
    events: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            events.append(json.loads(line))
    return events


def compute_audit(session_id: str) -> dict:
    fusion_count = 0
    pack_archive_count = 0
    pack_archive_tokens = 0
    compact_estimated_count = 0
    compact_unestimated_count = 0
    compact_tokens_saved = 0

    for event in _load_events(session_id):
        mechanism = event.get("mechanism")
        payload = event.get("payload") or {}
        if mechanism == "action_fusion":
            fusion_count += 1
        elif mechanism == "observation_pack":
            if payload.get("action") == "archive":
                pack_archive_count += 1
                pack_archive_tokens += int(payload.get("approx_tokens") or 0)
        elif mechanism == "online_compact":
            saved = payload.get("approx_tokens_saved")
            if saved is not None:
                compact_estimated_count += 1
                compact_tokens_saved += int(saved)
            else:
                compact_unestimated_count += 1

    fusion_tokens = fusion_count * 700
    pack_tokens = int(pack_archive_tokens * 0.85)
    total = fusion_tokens + pack_tokens + compact_tokens_saved
    cost = total / 1_000_000 * 15

    return {
        "session_id": session_id,
        "action_fusion": {"count": fusion_count, "tokens_saved": fusion_tokens},
        "observation_pack": {"archive_count": pack_archive_count, "tokens_saved": pack_tokens},
        "online_compact": {
            "count": compact_estimated_count + compact_unestimated_count,
            "estimated_count": compact_estimated_count,
            "unestimated_count": compact_unestimated_count,
            "tokens_saved": compact_tokens_saved,
        },
        "total_tokens_saved": total,
        "cost_usd_estimate": cost,
    }


def format_text(report: dict) -> str:
    af = report["action_fusion"]
    op = report["observation_pack"]
    oc = report["online_compact"]
    lines = [
        f"Session: {report['session_id']}",
        "",
        f"Action fusion: {af['count']} events, ~{af['tokens_saved']} tokens saved",
        f"Observation pack: {op['archive_count']} archives, ~{op['tokens_saved']} tokens saved",
    ]
    compact_line = (
        f"Online compact: {oc['count']} events, ~{oc['tokens_saved']} tokens saved"
    )
    if oc["unestimated_count"]:
        compact_line += f" ({oc['unestimated_count']} times unestimated)"
    lines.append(compact_line)
    lines.extend(
        [
            "",
            f"Total tokens saved: ~{report['total_tokens_saved']}",
            f"Cost estimate (illustrative): ${report['cost_usd_estimate']:.6f} USD",
        ]
    )
    return "\n".join(lines) + "\n"


def cmd_audit(args: argparse.Namespace) -> int:
    session_id = args.session
    session_dir = c.runtime_root() / "archive" / session_id
    if not session_dir.is_dir():
        print(f"session not found: {session_id}", file=sys.stderr)
        return c.EXIT_STATE

    c.ensure_runtime()
    report = compute_audit(session_id)

    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False))
    else:
        print(format_text(report), end="")
    return c.EXIT_OK


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Token-saver session audit")
    parser.add_argument("--session", required=True, help="Session id to audit")
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format (default: text)",
    )
    args = parser.parse_args(argv)
    return cmd_audit(args)


if __name__ == "__main__":
    raise SystemExit(main())
