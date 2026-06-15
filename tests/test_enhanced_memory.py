from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from jbs_agent.generation.langgraph_workflow import player_visible_bible
from jbs_agent.memory.hierarchical_memory import HierarchicalMemory


class EnhancedMemoryTests(unittest.TestCase):
    def test_role_context_only_reads_public_and_own_private_chunks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            memory = HierarchicalMemory(Path(tmp), "run")
            memory.set_summary("global_story", "global", "public-world", {})
            memory.add_document("public", "note", "PUBLIC_TOKEN lighthouse", visibility="public", agent="ACLTest")
            memory.add_document(
                "p01",
                "note",
                "P01_SECRET watch",
                visibility="role_private",
                allowed_roles=["P01"],
                agent="ACLTest",
            )
            memory.add_document(
                "p02",
                "note",
                "P02_SECRET key",
                visibility="role_private",
                allowed_roles=["P02"],
                agent="ACLTest",
            )

            role_context = memory.build_context_text(
                "PUBLIC_TOKEN P01_SECRET P02_SECRET",
                audience="role",
                role_id="P01",
                agent="ACLTest",
                budget_chars=4000,
            )
            dm_context = memory.build_context_text(
                "PUBLIC_TOKEN P01_SECRET P02_SECRET",
                audience="dm",
                agent="ACLTest",
                budget_chars=4000,
            )

            self.assertIn("PUBLIC_TOKEN", role_context)
            self.assertIn("P01_SECRET", role_context)
            self.assertNotIn("P02_SECRET", role_context)
            self.assertIn("P02_SECRET", dm_context)

            with closing(sqlite3.connect(str(Path(tmp) / "run" / "memory.sqlite"))) as conn:
                audit_count = conn.execute("SELECT COUNT(*) FROM context_audits").fetchone()[0]
            self.assertEqual(audit_count, 2)

    def test_player_visible_bible_hides_dm_truth_for_non_culprit(self) -> None:
        bible = {
            "metadata": {"title": "Case"},
            "world": {"setting": "Island"},
            "cast": [
                {
                    "id": "P01",
                    "name": "A",
                    "public_identity": "doctor",
                    "private_secret": "A_SECRET",
                    "personal_goal": "clear self",
                    "motive": "motive A",
                    "alibi": "alibi A",
                    "knows_before_game": ["A_KNOWS"],
                    "can_reveal": ["A_REVEAL"],
                    "key_relationships": ["A-B"],
                },
                {
                    "id": "P02",
                    "name": "B",
                    "public_identity": "captain",
                    "private_secret": "B_SECRET",
                    "personal_goal": "hide method",
                    "motive": "motive B",
                    "alibi": "alibi B",
                    "knows_before_game": ["B_KNOWS"],
                    "can_reveal": ["B_REVEAL"],
                    "key_relationships": ["B-A"],
                },
            ],
            "truth": {
                "victim": "V",
                "culprit": "P02",
                "method": "FULL_METHOD",
                "motive_truth": "TRUE_MOTIVE",
            },
            "game_flow": [{"round": 1, "title": "R1", "dm_goal": "DM_ONLY", "public_event": "PUBLIC_EVENT"}],
            "clues": [
                {"id": "C01", "title": "Public", "visibility": "public", "holder": "", "text": "PUBLIC_CLUE"},
                {"id": "C02", "title": "B private", "visibility": "private", "holder": "P02", "text": "B_CLUE"},
            ],
            "expanded_design": {"dm_pacing_notes": ["DM_NOTE"], "act_structure": ["ACT"]},
            "ending": {"solution_reveal_order": ["DM_SOLUTION"], "possible_endings": ["END"]},
        }

        p01_bible = player_visible_bible(bible, "P01")
        self.assertEqual(p01_bible["truth"], {})
        self.assertEqual(p01_bible["cast"][1]["private_secret"], "")
        self.assertEqual(p01_bible["clues"][1]["text"], "")
        self.assertNotIn("dm_goal", p01_bible["game_flow"][0])
        self.assertNotIn("solution_reveal_order", p01_bible["ending"])

        p02_bible = player_visible_bible(bible, "P02")
        self.assertEqual(p02_bible["truth"]["culprit"], "P02")
        self.assertEqual(p02_bible["truth"]["own_method_hint"], "FULL_METHOD")
        self.assertEqual(p02_bible["clues"][1]["text"], "B_CLUE")


if __name__ == "__main__":
    unittest.main()
