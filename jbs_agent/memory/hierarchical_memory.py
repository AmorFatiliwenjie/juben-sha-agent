from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime
from contextlib import contextmanager
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
    - summaries: compressed global/public/DM memory for long-context control.
    - role_memories: per-role knowledge boundary and private/public facts.
    - round_memories: per-round released clues, public events and DM goals.
    - fact_index: permission-aware semantic facts extracted from the bible.
    - memory_events/context_audits: traceability for what each agent wrote and read.
    """

    def __init__(self, root: Path, run_id: str) -> None:
        self.root = root / run_id
        self.root.mkdir(parents=True, exist_ok=True)
        self.db_path = self.root / "memory.sqlite"
        self.checkpoint_dir = self.root / "checkpoints"
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

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
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS summaries (
                    key TEXT PRIMARY KEY,
                    scope TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS role_memories (
                    role_id TEXT PRIMARY KEY,
                    role_name TEXT NOT NULL,
                    public_json TEXT NOT NULL,
                    private_json TEXT NOT NULL,
                    can_know_json TEXT NOT NULL,
                    must_hide_json TEXT NOT NULL,
                    relationships_json TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS round_memories (
                    round_no INTEGER PRIMARY KEY,
                    title TEXT NOT NULL,
                    public_json TEXT NOT NULL,
                    dm_json TEXT NOT NULL,
                    release_clues_json TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS fact_index (
                    fact_id TEXT PRIMARY KEY,
                    scope TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    predicate TEXT NOT NULL,
                    object TEXT NOT NULL,
                    source TEXT NOT NULL,
                    visibility TEXT NOT NULL,
                    allowed_roles_json TEXT NOT NULL,
                    denied_roles_json TEXT NOT NULL,
                    tags_json TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    agent TEXT NOT NULL,
                    node TEXT NOT NULL,
                    doc_id TEXT NOT NULL,
                    role_id TEXT NOT NULL,
                    audience TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS context_audits (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent TEXT NOT NULL,
                    audience TEXT NOT NULL,
                    role_id TEXT NOT NULL,
                    query TEXT NOT NULL,
                    selected_json TEXT NOT NULL,
                    skipped_json TEXT NOT NULL,
                    total_chars INTEGER NOT NULL,
                    budget_chars INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            ensure_columns(
                conn,
                "retrieval_chunks",
                {
                    "visibility": "TEXT NOT NULL DEFAULT 'dm_only'",
                    "allowed_roles_json": "TEXT NOT NULL DEFAULT '[]'",
                    "denied_roles_json": "TEXT NOT NULL DEFAULT '[]'",
                    "tags_json": "TEXT NOT NULL DEFAULT '[]'",
                    "round_no": "INTEGER",
                    "summary": "TEXT NOT NULL DEFAULT ''",
                },
            )

    def set_canonical(self, key: str, value: Any) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO canonical(key, value_json, updated_at)
                VALUES (?, ?, ?)
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

    def add_event(
        self,
        event_type: str,
        agent: str,
        node: str = "",
        *,
        doc_id: str = "",
        role_id: str = "",
        audience: str = "",
        summary: str = "",
        payload: Any | None = None,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO memory_events(
                    event_type, agent, node, doc_id, role_id, audience, summary, payload_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_type,
                    agent,
                    node,
                    doc_id,
                    role_id,
                    audience,
                    summary,
                    json.dumps(payload or {}, ensure_ascii=False),
                    now_iso(),
                ),
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
        visibility: str = "dm_only",
        allowed_roles: list[str] | None = None,
        denied_roles: list[str] | None = None,
        tags: list[str] | None = None,
        round_no: int | None = None,
        summary: str = "",
        agent: str = "",
        node: str = "",
    ) -> None:
        metadata = metadata or {}
        allowed_roles = normalize_role_list(allowed_roles)
        denied_roles = normalize_role_list(denied_roles)
        tags = normalize_tags(tags)
        chunks = chunk_text(text, chunk_size=chunk_size, overlap=overlap)
        with self._connect() as conn:
            conn.execute("DELETE FROM retrieval_chunks WHERE doc_id=?", (doc_id,))
            for index, chunk in enumerate(chunks):
                conn.execute(
                    """
                    INSERT INTO retrieval_chunks(
                        doc_id, kind, chunk_index, text, metadata_json, created_at,
                        visibility, allowed_roles_json, denied_roles_json, tags_json, round_no, summary
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        doc_id,
                        kind,
                        index,
                        chunk,
                        json.dumps(metadata, ensure_ascii=False),
                        now_iso(),
                        visibility,
                        json.dumps(allowed_roles, ensure_ascii=False),
                        json.dumps(denied_roles, ensure_ascii=False),
                        json.dumps(tags, ensure_ascii=False),
                        round_no,
                        summary,
                    ),
                )
        self.add_event(
            "document_indexed",
            agent or kind,
            node,
            doc_id=doc_id,
            audience=visibility,
            summary=summary or f"{kind} indexed",
            payload={
                "kind": kind,
                "chunks": len(chunks),
                "chars": len(text),
                "visibility": visibility,
                "allowed_roles": allowed_roles,
                "denied_roles": denied_roles,
                "tags": tags,
                "round_no": round_no,
            },
        )

    def retrieve(
        self,
        query: str,
        *,
        limit: int = 6,
        kind: str | None = None,
        metadata_filter: dict[str, Any] | None = None,
        audience: str = "dm",
        role_id: str | None = None,
        include_public: bool = True,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
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
        skipped = []
        for row in rows:
            metadata = json.loads(row["metadata_json"])
            if any(metadata.get(key) != value for key, value in metadata_filter.items()):
                continue
            if not is_visible_to(row, audience=audience, role_id=role_id, include_public=include_public):
                skipped.append(
                    {
                        "doc_id": row["doc_id"],
                        "kind": row["kind"],
                        "chunk_index": row["chunk_index"],
                        "visibility": row["visibility"],
                        "reason": "visibility",
                    }
                )
                continue
            tags_text = " ".join(load_json(row["tags_json"], []))
            score = score_text(f"{row['text']}\n{row['summary']}\n{tags_text}", terms)
            if score > 0:
                scored.append(
                    {
                        "score": score,
                        "doc_id": row["doc_id"],
                        "kind": row["kind"],
                        "chunk_index": row["chunk_index"],
                        "text": row["text"],
                        "metadata": metadata,
                        "visibility": row["visibility"],
                        "allowed_roles": load_json(row["allowed_roles_json"], []),
                        "tags": load_json(row["tags_json"], []),
                        "summary": row["summary"],
                    }
                )
        scored.sort(key=lambda item: item["score"], reverse=True)
        return scored[:limit], skipped

    def set_summary(self, key: str, scope: str, summary: str, payload: Any | None = None) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO summaries(key, scope, summary, payload_json, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (key, scope, summary, json.dumps(payload or {}, ensure_ascii=False), now_iso()),
            )

    def get_summary(self, key: str, default: Any = None) -> dict[str, Any] | Any:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM summaries WHERE key=?", (key,)).fetchone()
        if not row:
            return default
        return {
            "key": row["key"],
            "scope": row["scope"],
            "summary": row["summary"],
            "payload": json.loads(row["payload_json"]),
            "updated_at": row["updated_at"],
        }

    def set_fact(
        self,
        fact_id: str,
        scope: str,
        subject: str,
        predicate: str,
        obj: str,
        *,
        source: str,
        visibility: str = "dm_only",
        allowed_roles: list[str] | None = None,
        denied_roles: list[str] | None = None,
        tags: list[str] | None = None,
        payload: Any | None = None,
    ) -> None:
        allowed_roles = normalize_role_list(allowed_roles)
        denied_roles = normalize_role_list(denied_roles)
        tags = normalize_tags(tags)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO fact_index(
                    fact_id, scope, subject, predicate, object, source, visibility,
                    allowed_roles_json, denied_roles_json, tags_json, payload_json, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    fact_id,
                    scope,
                    subject,
                    predicate,
                    obj,
                    source,
                    visibility,
                    json.dumps(allowed_roles, ensure_ascii=False),
                    json.dumps(denied_roles, ensure_ascii=False),
                    json.dumps(tags, ensure_ascii=False),
                    json.dumps(payload or {}, ensure_ascii=False),
                    now_iso(),
                ),
            )

    def retrieve_facts(
        self,
        query: str,
        *,
        audience: str = "dm",
        role_id: str | None = None,
        limit: int = 8,
    ) -> list[dict[str, Any]]:
        terms = tokenize(query)
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM fact_index ORDER BY fact_id").fetchall()
        scored = []
        for row in rows:
            if not is_visible_to(row, audience=audience, role_id=role_id, include_public=True):
                continue
            tags = load_json(row["tags_json"], [])
            text = f"{row['subject']} {row['predicate']} {row['object']} {' '.join(tags)}"
            score = score_text(text, terms)
            if score > 0 or not terms:
                scored.append(
                    {
                        "score": score,
                        "fact_id": row["fact_id"],
                        "scope": row["scope"],
                        "subject": row["subject"],
                        "predicate": row["predicate"],
                        "object": row["object"],
                        "source": row["source"],
                        "visibility": row["visibility"],
                        "tags": tags,
                    }
                )
        scored.sort(key=lambda item: item["score"], reverse=True)
        return scored[:limit]

    def set_role_memory(
        self,
        role_id: str,
        role_name: str,
        *,
        public: Any | None = None,
        private: Any | None = None,
        can_know: Any | None = None,
        must_hide: Any | None = None,
        relationships: Any | None = None,
        payload: Any | None = None,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO role_memories(
                    role_id, role_name, public_json, private_json, can_know_json,
                    must_hide_json, relationships_json, payload_json, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    role_id,
                    role_name,
                    json.dumps(public or {}, ensure_ascii=False),
                    json.dumps(private or {}, ensure_ascii=False),
                    json.dumps(can_know or [], ensure_ascii=False),
                    json.dumps(must_hide or [], ensure_ascii=False),
                    json.dumps(relationships or [], ensure_ascii=False),
                    json.dumps(payload or {}, ensure_ascii=False),
                    now_iso(),
                ),
            )

    def get_role_memory(self, role_id: str, default: Any = None) -> dict[str, Any] | Any:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM role_memories WHERE role_id=?", (role_id,)).fetchone()
        if not row:
            return default
        return {
            "role_id": row["role_id"],
            "role_name": row["role_name"],
            "public": json.loads(row["public_json"]),
            "private": json.loads(row["private_json"]),
            "can_know": json.loads(row["can_know_json"]),
            "must_hide": json.loads(row["must_hide_json"]),
            "relationships": json.loads(row["relationships_json"]),
            "payload": json.loads(row["payload_json"]),
            "updated_at": row["updated_at"],
        }

    def set_round_memory(
        self,
        round_no: int,
        title: str,
        *,
        public: Any | None = None,
        dm: Any | None = None,
        release_clues: Any | None = None,
        payload: Any | None = None,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO round_memories(round_no, title, public_json, dm_json, release_clues_json, payload_json, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    round_no,
                    title,
                    json.dumps(public or {}, ensure_ascii=False),
                    json.dumps(dm or {}, ensure_ascii=False),
                    json.dumps(release_clues or [], ensure_ascii=False),
                    json.dumps(payload or {}, ensure_ascii=False),
                    now_iso(),
                ),
            )

    def get_round_memories(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM round_memories ORDER BY round_no").fetchall()
        return [
            {
                "round_no": row["round_no"],
                "title": row["title"],
                "public": json.loads(row["public_json"]),
                "dm": json.loads(row["dm_json"]),
                "release_clues": json.loads(row["release_clues_json"]),
                "payload": json.loads(row["payload_json"]),
                "updated_at": row["updated_at"],
            }
            for row in rows
        ]

    def clear_derived_memory(self) -> None:
        """Reset bible-derived layers before re-indexing a revised story bible."""
        with self._connect() as conn:
            conn.execute("DELETE FROM summaries")
            conn.execute("DELETE FROM role_memories")
            conn.execute("DELETE FROM round_memories")
            conn.execute("DELETE FROM fact_index")

    def index_story_bible(self, brief: dict[str, Any], bible: dict[str, Any]) -> None:
        """Build enhanced memory indexes from the current authoritative bible."""
        self.clear_derived_memory()
        metadata = bible.get("metadata", {})
        world = bible.get("world", {})
        truth = bible.get("truth", {})
        cast = bible.get("cast", []) if isinstance(bible.get("cast"), list) else []
        clues = bible.get("clues", []) if isinstance(bible.get("clues"), list) else []
        game_flow = bible.get("game_flow", []) if isinstance(bible.get("game_flow"), list) else []
        culprit = str(truth.get("culprit") or "")

        global_summary = "\n".join(
            compact_line(line)
            for line in [
                f"标题：{metadata.get('title') or brief.get('title', '')}",
                f"类型：{metadata.get('genre') or brief.get('genre', '')}",
                f"世界：{world.get('era', '')}；{world.get('setting', '')}",
                f"核心问题：{world.get('core_question', '')}",
                "主题：" + "；".join(str(item) for item in world.get("themes", [])),
            ]
            if line
        )
        self.set_summary("global_story", "global", global_summary, {"metadata": metadata, "world": world})

        public_summary = "\n".join(
            compact_line(line)
            for line in [
                f"公开背景：{world.get('setting', '')}",
                "公开角色：" + "；".join(f"{p.get('id')} {p.get('name')}：{p.get('public_identity', '')}" for p in cast),
            ]
        )
        self.set_summary("public_story", "public", public_summary, {"cast_count": len(cast)})

        dm_summary = "\n".join(
            compact_line(line)
            for line in [
                f"DM 真相：真凶 {culprit}；动机 {truth.get('motive_truth', '')}",
                f"唯一性：{truth.get('why_only_culprit', '')}",
                "时间线：" + "；".join(f"{item.get('time', '')} {item.get('event', '')}" for item in truth.get("timeline", [])),
            ]
        )
        self.set_summary("dm_truth", "dm_only", dm_summary, truth)
        self.set_fact(
            "world.setting",
            "world",
            str(metadata.get("title") or brief.get("title") or "story"),
            "setting",
            str(world.get("setting") or ""),
            source="story_bible.world",
            visibility="public",
            tags=["world", "setting"],
            payload=world,
        )
        self.set_fact(
            "world.core_question",
            "world",
            str(metadata.get("title") or brief.get("title") or "story"),
            "core_question",
            str(world.get("core_question") or ""),
            source="story_bible.world",
            visibility="public",
            tags=["world", "core_question"],
        )
        self.set_fact(
            "truth.culprit",
            "truth",
            "case",
            "culprit",
            culprit,
            source="story_bible.truth",
            visibility="dm_only",
            tags=["truth", "culprit"],
            payload={"culprit": culprit, "victim": truth.get("victim", "")},
        )
        self.set_fact(
            "truth.method",
            "truth",
            "case",
            "method",
            str(truth.get("method") or ""),
            source="story_bible.truth",
            visibility="dm_only",
            tags=["truth", "method"],
            payload=truth,
        )

        for player in cast:
            role_id = str(player.get("id") or "").strip()
            if not role_id:
                continue
            role_name = str(player.get("name") or role_id)
            is_culprit = role_id == culprit
            must_hide = [
                "不得透露其他角色未公开的内心、秘密和完整复盘信息。",
                "不得把 DM 复盘、全部线索答案或最终推理链直接写进玩家本。",
            ]
            if not is_culprit:
                must_hide.append("非凶手不得知道真凶身份、完整作案手法和真相复盘。")
            else:
                must_hide.append("凶手可以知道自己的行动与自保目标，但不要知道其他角色不该公开的全部内心。")
            self.set_role_memory(
                role_id,
                role_name,
                public={
                    "id": role_id,
                    "name": role_name,
                    "public_identity": player.get("public_identity", ""),
                    "can_reveal": player.get("can_reveal", []),
                },
                private={
                    "private_secret": player.get("private_secret", ""),
                    "personal_goal": player.get("personal_goal", ""),
                    "motive": player.get("motive", ""),
                    "alibi": player.get("alibi", ""),
                    "knows_before_game": player.get("knows_before_game", []),
                },
                can_know=player.get("knows_before_game", []) + player.get("can_reveal", []),
                must_hide=must_hide,
                relationships=player.get("key_relationships", []),
                payload={"player": player, "is_culprit": is_culprit},
            )
            self.set_fact(
                f"role.{role_id}.public_identity",
                "role",
                role_id,
                "public_identity",
                str(player.get("public_identity") or ""),
                source="story_bible.cast",
                visibility="public",
                tags=["role", role_id.lower(), "public"],
                payload={"name": role_name},
            )
            self.set_fact(
                f"role.{role_id}.private_secret",
                "role",
                role_id,
                "private_secret",
                str(player.get("private_secret") or ""),
                source="story_bible.cast",
                visibility="role_private",
                allowed_roles=[role_id],
                tags=["role", role_id.lower(), "private"],
                payload={"name": role_name},
            )
            self.set_fact(
                f"role.{role_id}.goal",
                "role",
                role_id,
                "personal_goal",
                str(player.get("personal_goal") or ""),
                source="story_bible.cast",
                visibility="role_private",
                allowed_roles=[role_id],
                tags=["role", role_id.lower(), "goal"],
                payload={"name": role_name},
            )
            self.set_fact(
                f"role.{role_id}.alibi",
                "role",
                role_id,
                "alibi",
                str(player.get("alibi") or ""),
                source="story_bible.cast",
                visibility="role_private",
                allowed_roles=[role_id],
                tags=["role", role_id.lower(), "alibi"],
                payload={"name": role_name},
            )

        clue_lookup = {str(clue.get("id")): clue for clue in clues}
        for clue in clues:
            clue_id = str(clue.get("id") or "").strip()
            if not clue_id:
                continue
            clue_visibility = clue_fact_visibility(clue)
            holder = str(clue.get("holder") or "").strip()
            allowed_roles = [holder] if clue_visibility == "role_private" and holder.upper().startswith("P") else None
            self.set_fact(
                f"clue.{clue_id}",
                "clue",
                clue_id,
                str(clue.get("title") or "clue"),
                str(clue.get("text") or ""),
                source="story_bible.clues",
                visibility=clue_visibility,
                allowed_roles=allowed_roles,
                tags=["clue", clue_id.lower(), f"round:{clue.get('round', '')}", str(clue.get("truth_value") or "")],
                payload=clue,
            )

        for flow in game_flow:
            try:
                round_no = int(flow.get("round") or 0)
            except (TypeError, ValueError):
                continue
            release_ids = [str(item) for item in flow.get("release_clues", [])]
            release_clues = [clue_lookup.get(item, {"id": item}) for item in release_ids]
            self.set_round_memory(
                round_no,
                str(flow.get("title") or f"Round {round_no}"),
                public={
                    "public_event": flow.get("public_event", ""),
                    "player_tasks": flow.get("player_tasks", []),
                },
                dm={
                    "dm_goal": flow.get("dm_goal", ""),
                    "duration_minutes": flow.get("duration_minutes", ""),
                },
                release_clues=release_clues,
                payload=flow,
            )
            self.set_fact(
                f"round.{round_no}.public_event",
                "round",
                f"round {round_no}",
                str(flow.get("title") or ""),
                str(flow.get("public_event") or ""),
                source="story_bible.game_flow",
                visibility="public",
                tags=["round", f"round:{round_no}", "public_event"],
                payload=flow,
            )
            self.set_fact(
                f"round.{round_no}.dm_goal",
                "round",
                f"round {round_no}",
                "dm_goal",
                str(flow.get("dm_goal") or ""),
                source="story_bible.game_flow",
                visibility="dm_only",
                tags=["round", f"round:{round_no}", "dm_goal"],
                payload=flow,
            )

        self.add_working(
            "EnhancedMemory",
            "indexed story bible into summaries, facts, role memories and round memories",
            {"roles": len(cast), "rounds": len(game_flow), "clues": len(clues)},
        )
        self.add_event(
            "story_bible_indexed",
            "EnhancedMemory",
            "index_story_bible",
            summary="story bible indexed into enhanced memory",
            payload={"roles": len(cast), "rounds": len(game_flow), "clues": len(clues)},
        )

    def build_context_text(
        self,
        query: str,
        *,
        audience: str = "dm",
        role_id: str | None = None,
        limit: int = 6,
        kind: str | None = None,
        agent: str = "",
        budget_chars: int = 9000,
        include_rounds: bool = True,
    ) -> str:
        parts: list[str] = []
        selected: list[dict[str, Any]] = []
        global_summary = self.get_summary("global_story")
        if global_summary:
            parts.append("[summary:global_story]\n" + global_summary["summary"])
            selected.append({"type": "summary", "id": "global_story", "scope": global_summary["scope"]})

        if audience == "public":
            public_summary = self.get_summary("public_story")
            if public_summary:
                parts.append("[summary:public_story]\n" + public_summary["summary"])
                selected.append({"type": "summary", "id": "public_story", "scope": public_summary["scope"]})
        elif audience == "role":
            public_summary = self.get_summary("public_story")
            if public_summary:
                parts.append("[summary:public_story]\n" + public_summary["summary"])
                selected.append({"type": "summary", "id": "public_story", "scope": public_summary["scope"]})
        elif audience == "dm":
            dm_summary = self.get_summary("dm_truth")
            if dm_summary:
                parts.append("[summary:dm_truth]\n" + dm_summary["summary"])
                selected.append({"type": "summary", "id": "dm_truth", "scope": dm_summary["scope"]})

        if role_id:
            role_memory = self.get_role_memory(role_id)
            if role_memory:
                parts.append("[role_memory]\n" + json.dumps(role_memory, ensure_ascii=False, indent=2))
                selected.append({"type": "role_memory", "id": role_id})

        facts = self.retrieve_facts(query, audience=audience, role_id=role_id, limit=limit)
        if facts:
            fact_lines = [
                f"- {fact['fact_id']}：{fact['subject']} / {fact['predicate']} / {fact['object']}"
                for fact in facts
            ]
            parts.append("[fact_index]\n" + "\n".join(fact_lines))
            selected.extend(
                {
                    "type": "fact",
                    "id": fact["fact_id"],
                    "visibility": fact["visibility"],
                    "score": fact["score"],
                }
                for fact in facts
            )

        if include_rounds:
            round_lines = []
            for item in self.get_round_memories():
                if audience == "dm":
                    round_lines.append(
                        f"- 第 {item['round_no']} 轮 {item['title']}：公开事件={item['public'].get('public_event', '')}；DM目标={item['dm'].get('dm_goal', '')}"
                    )
                else:
                    round_lines.append(
                        f"- 第 {item['round_no']} 轮 {item['title']}：公开事件={item['public'].get('public_event', '')}"
                    )
            if round_lines:
                parts.append("[round_memory]\n" + "\n".join(round_lines))
                selected.append({"type": "round_memory", "count": len(round_lines), "audience": audience})

        chunks, skipped = self.retrieve(query, limit=limit, kind=kind, audience=audience, role_id=role_id)
        for item in chunks:
            parts.append(
                f"[{item['kind']}:{item['doc_id']} visibility={item['visibility']} tags={','.join(item['tags'])}]\n"
                f"{item['text']}"
            )
            selected.append(
                {
                    "type": "chunk",
                    "doc_id": item["doc_id"],
                    "kind": item["kind"],
                    "chunk_index": item["chunk_index"],
                    "visibility": item["visibility"],
                    "score": item["score"],
                }
            )

        context = clamp_context("\n\n".join(parts), budget_chars)
        self.add_context_audit(
            agent=agent or "unknown",
            audience=audience,
            role_id=role_id or "",
            query=query,
            selected=selected,
            skipped=skipped,
            total_chars=len(context),
            budget_chars=budget_chars,
        )
        return context

    def add_context_audit(
        self,
        *,
        agent: str,
        audience: str,
        role_id: str,
        query: str,
        selected: list[dict[str, Any]],
        skipped: list[dict[str, Any]],
        total_chars: int,
        budget_chars: int,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO context_audits(
                    agent, audience, role_id, query, selected_json, skipped_json,
                    total_chars, budget_chars, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    agent,
                    audience,
                    role_id,
                    compact_line(query, limit=1200),
                    json.dumps(selected, ensure_ascii=False),
                    json.dumps(skipped[:30], ensure_ascii=False),
                    total_chars,
                    budget_chars,
                    now_iso(),
                ),
            )

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
                "SELECT kind, visibility, COUNT(*) AS count FROM retrieval_chunks GROUP BY kind, visibility ORDER BY kind, visibility"
            ).fetchall()
            summaries = conn.execute("SELECT key, scope, updated_at FROM summaries ORDER BY key").fetchall()
            roles = conn.execute("SELECT role_id, role_name, updated_at FROM role_memories ORDER BY role_id").fetchall()
            rounds = conn.execute("SELECT round_no, title, updated_at FROM round_memories ORDER BY round_no").fetchall()
            facts = conn.execute(
                "SELECT scope, visibility, COUNT(*) AS count FROM fact_index GROUP BY scope, visibility ORDER BY scope, visibility"
            ).fetchall()
            events = conn.execute(
                "SELECT event_type, COUNT(*) AS count FROM memory_events GROUP BY event_type ORDER BY event_type"
            ).fetchall()
            audits = conn.execute(
                """
                SELECT agent, audience, role_id, COUNT(*) AS count, MAX(total_chars) AS max_chars
                FROM context_audits
                GROUP BY agent, audience, role_id
                ORDER BY agent, audience, role_id
                """
            ).fetchall()
        lines = [
            "# 增强版分层记忆报告",
            "",
            f"- SQLite：`{self.db_path}`",
            "",
            "## Canonical Memory",
            "",
        ]
        lines.extend(f"- {row['key']}（{row['updated_at']}）" for row in canonical)
        lines.extend(["", "## Working Memory", ""])
        lines.extend(f"- [{row['created_at']}] {row['node']}：{row['summary']}" for row in working)
        lines.extend(["", "## Summary Memory", ""])
        lines.extend(f"- {row['key']}（{row['scope']}，{row['updated_at']}）" for row in summaries)
        lines.extend(["", "## Role Memory", ""])
        lines.extend(f"- {row['role_id']} {row['role_name']}（{row['updated_at']}）" for row in roles)
        lines.extend(["", "## Round Memory", ""])
        lines.extend(f"- 第 {row['round_no']} 轮：{row['title']}（{row['updated_at']}）" for row in rounds)
        lines.extend(["", "## Fact Index", ""])
        lines.extend(f"- {row['scope']} / {row['visibility']}：{row['count']} facts" for row in facts)
        lines.extend(["", "## Retrieval Memory", ""])
        lines.extend(f"- {row['kind']} / {row['visibility']}：{row['count']} chunks" for row in chunks)
        lines.extend(["", "## Memory Events", ""])
        lines.extend(f"- {row['event_type']}：{row['count']} events" for row in events)
        lines.extend(["", "## Context Audits", ""])
        lines.extend(
            f"- {row['agent']} / {row['audience']} / {row['role_id'] or '-'}：{row['count']} calls，max {row['max_chars']} chars"
            for row in audits
        )
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def ensure_columns(conn: sqlite3.Connection, table: str, columns: dict[str, str]) -> None:
    existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    for name, definition in columns.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")


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


def load_json(value: str, default: Any) -> Any:
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


def normalize_role_list(values: list[str] | None) -> list[str]:
    if not values:
        return []
    return sorted({str(item).strip().upper() for item in values if str(item).strip()})


def normalize_tags(values: list[str] | None) -> list[str]:
    if not values:
        return []
    return sorted({str(item).strip().lower() for item in values if str(item).strip()})


def compact_line(value: str, *, limit: int = 500) -> str:
    value = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(value) <= limit:
        return value
    return value[: limit - 1] + "…"


def clamp_context(value: str, budget_chars: int) -> str:
    value = str(value or "")
    budget_chars = max(0, int(budget_chars or 0))
    if not budget_chars:
        return value
    if len(value) <= budget_chars:
        return value
    tail = "\n\n[context_truncated]\n" + f"truncated to {budget_chars} chars"
    head_budget = max(0, budget_chars - len(tail))
    return value[:head_budget] + tail


def clue_fact_visibility(clue: dict[str, Any]) -> str:
    raw_visibility = str(clue.get("visibility") or "").lower()
    holder = str(clue.get("holder") or "").strip().upper()
    if "dm" in raw_visibility or "主持" in raw_visibility:
        return "dm_only"
    if "private" in raw_visibility or "私" in raw_visibility or holder.startswith("P"):
        return "role_private"
    return "public"


def is_visible_to(
    row: sqlite3.Row,
    *,
    audience: str,
    role_id: str | None,
    include_public: bool,
) -> bool:
    visibility = str(row["visibility"] or "dm_only")
    role_id = str(role_id or "").upper()
    allowed_roles = normalize_role_list(load_json(row["allowed_roles_json"], []))
    denied_roles = normalize_role_list(load_json(row["denied_roles_json"], []))

    if audience == "dm":
        return True
    if role_id and role_id in denied_roles:
        return False
    if visibility == "public":
        return include_public
    if visibility == "role_private":
        return bool(role_id and role_id in allowed_roles)
    if visibility == "culprit_only":
        return bool(role_id and role_id in allowed_roles)
    if visibility == "dm_only":
        return False
    return False


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
