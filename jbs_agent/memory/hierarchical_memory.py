from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


class HierarchicalMemory:
    """Persistent layered memory for long script generation.

    Layers:
    - canonical: authoritative facts such as brief, story bible, truth, cast and clues.
    - working: node-by-node process notes, decisions, review results and checkpoints.
    - retrieval: chunked long-form text for player books, handouts, manuals and reviews.
    """

    def __init__(self, root: Path, run_id: str) -> None:
        self.root = root / run_id
        self.root.mkdir(parents=True, exist_ok=True)
        self.db_path = self.root / "memory.sqlite"
        self.checkpoint_dir = self.root / "checkpoints"
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS canonical (
                    key TEXT PRIMARY KEY,
                    value_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS working (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    node TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS retrieval_chunks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    doc_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    text TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )

    def set_canonical(self, key: str, value: Any) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO canonical(key, value_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json, updated_at=excluded.updated_at
                """,
                (key, json.dumps(value, ensure_ascii=False), now_iso()),
            )

    def get_canonical(self, key: str, default: Any = None) -> Any:
        with self._connect() as conn:
            row = conn.execute("SELECT value_json FROM canonical WHERE key=?", (key,)).fetchone()
        if not row:
            return default
        return json.loads(row["value_json"])

    def add_working(self, node: str, summary: str, payload: Any | None = None) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO working(node, summary, payload_json, created_at) VALUES (?, ?, ?, ?)",
                (node, summary, json.dumps(payload or {}, ensure_ascii=False), now_iso()),
            )

    def add_document(
        self,
        doc_id: str,
        kind: str,
        text: str,
        metadata: dict[str, Any] | None = None,
        *,
        chunk_size: int = 1400,
        overlap: int = 160,
    ) -> None:
        metadata = metadata or {}
        chunks = chunk_text(text, chunk_size=chunk_size, overlap=overlap)
        with self._connect() as conn:
            conn.execute("DELETE FROM retrieval_chunks WHERE doc_id=?", (doc_id,))
            for index, chunk in enumerate(chunks):
                conn.execute(
                    """
                    INSERT INTO retrieval_chunks(doc_id, kind, chunk_index, text, metadata_json, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (doc_id, kind, index, chunk, json.dumps(metadata, ensure_ascii=False), now_iso()),
                )

    def retrieve(
        self,
        query: str,
        *,
        limit: int = 6,
        kind: str | None = None,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        terms = tokenize(query)
        metadata_filter = metadata_filter or {}
        sql = "SELECT * FROM retrieval_chunks"
        params: list[Any] = []
        clauses = []
        if kind:
            clauses.append("kind=?")
            params.append(kind)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()

        scored = []
        for row in rows:
            metadata = json.loads(row["metadata_json"])
            if any(metadata.get(key) != value for key, value in metadata_filter.items()):
                continue
            score = score_text(row["text"], terms)
            if score > 0:
                scored.append(
                    {
                        "score": score,
                        "doc_id": row["doc_id"],
                        "kind": row["kind"],
                        "chunk_index": row["chunk_index"],
                        "text": row["text"],
                        "metadata": metadata,
                    }
                )
        scored.sort(key=lambda item: item["score"], reverse=True)
        return scored[:limit]

    def checkpoint(self, node: str, state: dict[str, Any]) -> None:
        safe_node = re.sub(r"[^A-Za-z0-9_.-]+", "_", node).strip("_") or "node"
        path = self.checkpoint_dir / f"{datetime.now().strftime('%Y%m%d-%H%M%S')}_{safe_node}.json"
        summary = summarize_state(state)
        path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        self.add_working(node, f"checkpoint saved: {path.name}", {"checkpoint": path.name, "state": summary})

    def export_report(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            canonical = conn.execute("SELECT key, updated_at FROM canonical ORDER BY key").fetchall()
            working = conn.execute("SELECT node, summary, created_at FROM working ORDER BY id").fetchall()
            chunks = conn.execute(
                "SELECT kind, COUNT(*) AS count FROM retrieval_chunks GROUP BY kind ORDER BY kind"
            ).fetchall()
        lines = [
            "# 分层记忆报告",
            "",
            f"- SQLite：`{self.db_path}`",
            "",
            "## Canonical Memory",
            "",
        ]
        lines.extend(f"- {row['key']}（{row['updated_at']}）" for row in canonical)
        lines.extend(["", "## Working Memory", ""])
        lines.extend(f"- [{row['created_at']}] {row['node']}：{row['summary']}" for row in working)
        lines.extend(["", "## Retrieval Memory", ""])
        lines.extend(f"- {row['kind']}：{row['count']} chunks" for row in chunks)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def chunk_text(text: str, *, chunk_size: int, overlap: int) -> list[str]:
    text = text.strip()
    if not text:
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = min(len(text), start + chunk_size)
        chunks.append(text[start:end])
        if end >= len(text):
            break
        start = max(0, end - overlap)
    return chunks


def tokenize(text: str) -> set[str]:
    text = text.lower()
    latin = re.findall(r"[a-z0-9_]{2,}", text)
    cjk = re.findall(r"[\u4e00-\u9fff]{2,}", text)
    cjk_terms = []
    for item in cjk:
        cjk_terms.extend(item[index : index + 2] for index in range(max(0, len(item) - 1)))
        if len(item) >= 4:
            cjk_terms.extend(item[index : index + 4] for index in range(max(0, len(item) - 3)))
    return set(latin + cjk_terms)


def score_text(text: str, terms: set[str]) -> int:
    if not terms:
        return 0
    haystack = text.lower()
    return sum(1 for term in terms if term and term in haystack)


def summarize_state(state: dict[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for key, value in state.items():
        if key in {"client", "memory"}:
            continue
        if isinstance(value, (str, int, float, bool)) or value is None:
            summary[key] = value
        elif isinstance(value, list):
            summary[key] = {"type": "list", "len": len(value)}
        elif isinstance(value, dict):
            summary[key] = {"type": "dict", "keys": sorted(str(item) for item in value.keys())[:20]}
        else:
            summary[key] = str(type(value))
    return summary
