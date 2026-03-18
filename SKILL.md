---
name: codex-export
description: Export a Codex CLI or Codex Desktop (App) session to a Markdown transcript. Use when the user asks to export, save, share, or review a past chat, session, or transcript. Supports --brief mode (user + assistant only, no tool calls) and --list to browse recent sessions. Works with both Codex CLI and Codex Desktop app sessions (unlike similar tools that only support CLI).
---

# codex-export

Export any Codex session (`~/.codex/sessions/**/*.jsonl`) to a clean Markdown file.

## Usage

```bash
# List recent sessions (pick by number or copy the ID)
python3 scripts/export.py --list

# Export by session ID
python3 scripts/export.py <session-id> output.md

# Brief mode: user + assistant only, no tool calls
python3 scripts/export.py <session-id> output.md --brief
```

## Notes

- Works with **Codex Desktop** (`source=vscode`) and **Codex CLI** (`source=cli/exec`)
- Session IDs come from `~/.codex/state_5.sqlite` or the rollout filename
- System/developer messages and `<environment_context>` blocks are filtered automatically
- Tool call outputs are included by default; use `--brief` to strip them
