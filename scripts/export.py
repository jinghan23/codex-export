#!/usr/bin/env python3
"""
Export a Codex app/CLI session to Markdown.
Usage: python3 scripts/export.py --list
       python3 scripts/export.py <session-id> [output.md] [--brief]
"""

import json
import sys
import glob
import os
import sqlite3
from datetime import datetime, timezone

def find_rollout(session_id):
    pattern = os.path.expanduser(f"~/.codex/sessions/**/*{session_id}*.jsonl")
    matches = glob.glob(pattern, recursive=True)
    if not matches:
        # also check archived
        pattern2 = os.path.expanduser(f"~/.codex/archived_sessions/**/*{session_id}*.jsonl")
        matches = glob.glob(pattern2, recursive=True)
    return matches[0] if matches else None

def get_text(content):
    """Extract readable text from content list."""
    if not isinstance(content, list):
        return ""
    parts = []
    for c in content:
        t = c.get("type", "")
        if t in ("input_text", "output_text", "text"):
            text = c.get("text", "").strip()
            # skip system-injected blocks (permissions, AGENTS.md instructions)
            if (text.startswith("<permissions instructions>")
                    or text.startswith("# AGENTS.md instructions")
                    or text.startswith("<environment_context>")):
                continue
            if text:
                parts.append(text)
    return "\n\n".join(parts)

def format_tool_call(payload):
    name = payload.get("name", "tool")
    args = payload.get("arguments", "")
    try:
        args_fmt = json.dumps(json.loads(args), ensure_ascii=False, indent=2)
    except Exception:
        args_fmt = args
    return f"`{name}`\n```json\n{args_fmt}\n```"

def format_tool_output(payload):
    output = payload.get("output", "")
    try:
        out_fmt = json.dumps(json.loads(output), ensure_ascii=False, indent=2)
    except Exception:
        out_fmt = output
    # truncate long outputs
    if len(out_fmt) > 2000:
        out_fmt = out_fmt[:2000] + "\n... (truncated)"
    return f"```\n{out_fmt}\n```"

def export(session_id, out_path=None, brief=False):
    path = find_rollout(session_id)
    if not path:
        print(f"ERROR: session {session_id} not found in ~/.codex/sessions/", file=sys.stderr)
        sys.exit(1)

    entries = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))

    # pull session meta
    meta = next((e for e in entries if e.get("type") == "session_meta"), {})
    meta_p = meta.get("payload", {})
    title = meta_p.get("first_user_message") or session_id
    cwd = meta_p.get("cwd", "")
    model = meta_p.get("model_provider", "")
    originator = meta_p.get("originator", "")
    ts_raw = meta_p.get("timestamp", "")
    try:
        ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00")).astimezone().strftime("%Y-%m-%d %H:%M %Z")
    except Exception:
        ts = ts_raw

    lines = []
    lines.append(f"# Codex Session Export\n")
    lines.append(f"- **Session ID:** `{session_id}`")
    lines.append(f"- **Time:** {ts}")
    if originator: lines.append(f"- **Source:** {originator}")
    if cwd: lines.append(f"- **Workspace:** `{cwd}`")
    if model: lines.append(f"- **Model:** {model}")
    lines.append("")
    lines.append("---\n")

    pending_user_text = []
    first_user_done = False

    for entry in entries:
        etype = entry.get("type")

        if etype == "response_item":
            p = entry["payload"]
            role = p.get("role")
            ptype = p.get("type")
            content = p.get("content")

            if role == "user" and ptype == "message":
                text = get_text(content)
                if text:
                    if not first_user_done:
                        # first user message = the actual task prompt
                        lines.append(f"## 👤 User\n\n{text}\n")
                        first_user_done = True
                    else:
                        lines.append(f"## 👤 User\n\n{text}\n")

            elif role == "assistant" and ptype == "message":
                text = get_text(content)
                if text:
                    lines.append(f"## 🤖 Codex\n\n{text}\n")

            elif ptype == "function_call" and not brief:
                text = format_tool_call(p)
                lines.append(f"### 🔧 Tool Call\n\n{text}\n")

            elif ptype == "function_call_output" and not brief:
                text = format_tool_output(p)
                lines.append(f"### 📤 Tool Output\n\n{text}\n")

            # skip reasoning, developer system messages

    result = "\n".join(lines)

    if out_path:
        with open(out_path, "w") as f:
            f.write(result)
        print(f"Exported to: {out_path}")
    else:
        print(result)

def list_sessions(limit=15):
    db = os.path.expanduser("~/.codex/state_5.sqlite")
    if not os.path.exists(db):
        print("No ~/.codex/state_5.sqlite found.")
        return
    con = sqlite3.connect(db)
    rows = con.execute(
        "SELECT id, title, source, created_at FROM threads ORDER BY created_at DESC LIMIT ?",
        (limit,)
    ).fetchall()
    con.close()
    print(f"{'#':<3} {'Source':<8} {'Date':<17} Title")
    print("-" * 80)
    for i, (sid, title, source, ts) in enumerate(rows):
        try:
            dt = datetime.fromtimestamp(ts / 1000).strftime("%m-%d %H:%M")
        except Exception:
            dt = "?"
        short_title = (title or "")[:55].replace("\n", " ")
        if len(title or "") > 55:
            short_title += "…"
        print(f"{i+1:<3} {source:<8} {dt:<17} {short_title}")
        print(f"    id: {sid}")


if __name__ == "__main__":
    flags = [a for a in sys.argv[1:] if a.startswith("-")]
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    brief = "--brief" in flags or "-b" in flags

    if "--list" in flags or "-l" in flags:
        list_sessions()
        sys.exit(0)

    if len(args) < 1:
        print("Usage:")
        print("  python3 scripts/export.py --list")
        print("  python3 scripts/export.py <session-id> [output.md] [--brief]")
        sys.exit(1)

    session_id = args[0]
    out_path = args[1] if len(args) > 1 else None
    export(session_id, out_path, brief=brief)
