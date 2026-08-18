import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).parents[1] / "scripts" / "export.py"
SPEC = importlib.util.spec_from_file_location("codex_export", SCRIPT)
codex_export = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(codex_export)


def write_rollout(path, entries):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as f:
        for entry in entries:
            f.write(json.dumps(entry).encode("utf-8") + b"\n")
    return path.stat().st_size


def meta(session_id, history_base=None):
    return {
        "type": "session_meta",
        "payload": {"session_id": session_id, "history_base": history_base},
    }


def message(role, text):
    content_type = "input_text" if role == "user" else "output_text"
    return {
        "type": "response_item",
        "payload": {
            "type": "message",
            "role": role,
            "content": [{"type": content_type, "text": text}],
        },
    }


class LoadHistoryTest(unittest.TestCase):
    def test_reconstructs_nested_history_base_chain(self):
        with tempfile.TemporaryDirectory() as home:
            sessions = Path(home) / ".codex" / "sessions" / "2026" / "01" / "02"

            root_path = sessions / "rollout-root.jsonl"
            root_size = write_rollout(
                root_path, [meta("root"), message("user", "from root")]
            )

            parent_path = sessions / "rollout-parent.jsonl"
            parent_size = write_rollout(
                parent_path,
                [
                    meta(
                        "parent",
                        {"thread_id": "root", "end_byte_offset": root_size},
                    ),
                    message("assistant", "from parent"),
                ],
            )

            child_path = sessions / "rollout-child.jsonl"
            write_rollout(
                child_path,
                [
                    meta(
                        "child",
                        {"thread_id": "parent", "end_byte_offset": parent_size},
                    ),
                    message("user", "from child"),
                ],
            )

            with mock.patch.dict(os.environ, {"HOME": home}):
                entries, paths = codex_export.load_history("child")

            texts = [
                item["payload"]["content"][0]["text"]
                for item in entries
                if item.get("type") == "response_item"
            ]
            self.assertEqual(texts, ["from root", "from parent", "from child"])
            self.assertEqual(paths, [str(root_path), str(parent_path), str(child_path)])

    def test_rejects_offset_that_splits_a_record(self):
        with tempfile.TemporaryDirectory() as home:
            path = Path(home) / "rollout.jsonl"
            write_rollout(path, [meta("root")])
            with self.assertRaisesRegex(ValueError, "splits a JSONL record"):
                codex_export.read_entries(str(path), 1)


if __name__ == "__main__":
    unittest.main()
