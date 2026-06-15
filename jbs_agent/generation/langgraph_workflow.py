from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Callable

try:
    from typing import TypedDict
except ImportError:  # Python 3.7 keeps the prompt engine usable without extra deps.
    TypedDict = None  # type: ignore[assignment]

from ..core.config import RuntimeConfig
from ..core.llm import OpenAICompatibleClient
from ..memory.hierarchical_memory import HierarchicalMemory
from ..output.exporter import save_project, safe_filename
from ..quality.validator import make_quality_report, validate_all
from .pipeline import needs_revision, normalize_bible_refs, request_markdown
from .prompts import (
    PLAYER_BOOK_SECTIONS,
    SYSTEM_PROMPT,
    assemble_player_book,
    build_bible_prompt,
    build_handout_index_prompt,
    build_handout_text_prompt,
    build_package_section_text_prompt,
    build_player_outline_prompt,
    build_player_section_prompt,
    build_review_prompt,
    build_revision_prompt,
)
from .sample_data import sample_bible, sample_package, sample_player_docs, sample_review

Progress = Callable[[str], None]


if TypedDict is not None:
    class GraphState(TypedDict, total=False):
        brief: dict[str, Any]
        length_profile: str
        player_depth: str
        bible: dict[str, Any]
        review: dict[str, Any]
        package: dict[str, Any]
        player_docs: list[dict[str, Any]]
        warnings: list[str]
        run_dir: str
        dry_run: bool
        revision_count: int
else:
    GraphState = dict  # type: ignore[misc, assignment]


def run_langgraph_pipeline(
    brief: dict[str, Any],
    config: RuntimeConfig,
    output_root: Path,
    *,
    dry_run: bool = False,
    length_profile: str = "standard",
    player_depth: str = "normal",
    progress: Progress | None = None,
    memory_root: Path | None = None,
) -> tuple[Path, list[str]]:
    """Run the multi-agent LangGraph workflow.

    The implementation uses LangGraph when installed. It keeps the existing
    data contracts and exporter, while adding graph nodes, checkpoints and
    layered memory.
    """
    progress = progress or (lambda message: None)
    try:
        from langgraph.graph import END, StateGraph
    except Exception as exc:
        raise RuntimeError(
            "未安装可用的 LangGraph。请使用 Python 3.10+ 环境安装："
            "pip install langgraph langchain-core。当前 Python 3.7 环境通常不支持新版 LangGraph；"
            "你仍可使用默认 --engine prompt。"
        ) from exc

    run_id = datetime.now().strftime("%Y%m%d-%H%M%S_langgraph")
    memory = HierarchicalMemory(memory_root or (output_root / ".memory"), run_id)
    client = OpenAICompatibleClient(
        config.api_key,
        config.base_url,
        config.model,
        timeout=config.timeout,
        max_tokens=config.max_tokens,
        json_mode=config.json_mode,
    )

    base_state: GraphState = {
        "brief": dict(brief, output_scale=length_profile, player_depth=player_depth, engine="langgraph"),
        "length_profile": length_profile,
        "player_depth": player_depth,
        "dry_run": dry_run,
        "revision_count": 0,
    }
    memory.set_canonical("brief", base_state["brief"])

    def node_story_architect(state: GraphState) -> GraphState:
        progress("LG 1/7 StoryArchitect: 生成权威 story_bible。")
        if dry_run:
            bible = sample_bible(state["brief"])
        else:
            bible = client.request_json(
                "story_bible",
                [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": build_bible_prompt(state["brief"], state["length_profile"])},
                ],
                temperature=min(config.temperature, 0.55),
                compact_retry_hint="只写短蓝图 JSON，不写正文。",
            )
        normalize_bible_refs(bible)
        memory.set_canonical("story_bible", bible)
        memory.set_canonical("cast", bible.get("cast", []))
        memory.set_canonical("truth", bible.get("truth", {}))
        memory.set_canonical("clues", bible.get("clues", []))
        memory.add_working("StoryArchitect", "created canonical story bible", {"title": bible.get("metadata", {}).get("title")})
        memory.checkpoint("StoryArchitect", {**state, "bible": bible})
        return {"bible": bible}

    def node_fairness_editor(state: GraphState) -> GraphState:
        progress("LG 2/7 FairnessEditor: 审查公平推理和可主持性。")
        if dry_run:
            review = sample_review()
        else:
            review = client.request_json(
                "quality_review",
                [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": build_review_prompt(state["brief"], state["bible"])},
                ],
                temperature=0.2,
            )
        memory.set_canonical("quality_review", review)
        memory.add_working("FairnessEditor", str(review.get("review_summary", "review finished")), review)
        memory.checkpoint("FairnessEditor", {**state, "review": review})
        return {"review": review}

    def node_revision_room(state: GraphState) -> GraphState:
        revision_count = int(state.get("revision_count") or 0) + 1
        progress(f"LG 3/7 RevisionRoom: 根据审稿意见进行第 {revision_count} 轮修订。")
        if dry_run:
            memory.add_working("RevisionRoom", "dry-run revision skipped", {"revision_count": revision_count})
            return {"revision_count": revision_count}
        bible = client.request_json(
            "revised_story_bible",
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_revision_prompt(state["brief"], state["bible"], state["review"])},
            ],
            temperature=max(0.2, config.temperature - 0.2),
            compact_retry_hint="只输出修订后的紧凑 story_bible JSON。",
        )
        normalize_bible_refs(bible)
        memory.set_canonical("story_bible", bible)
        memory.set_canonical("cast", bible.get("cast", []))
        memory.set_canonical("truth", bible.get("truth", {}))
        memory.set_canonical("clues", bible.get("clues", []))
        memory.add_working("RevisionRoom", "revised story bible", {"issues": state["review"].get("mandatory_fixes", [])})
        memory.checkpoint("RevisionRoom", {**state, "bible": bible, "revision_count": revision_count})
        return {"bible": bible, "revision_count": revision_count}

    def route_after_review(state: GraphState) -> str:
        revision_count = int(state.get("revision_count") or 0)
        if needs_revision(state["review"]) and revision_count < 2:
            memory.add_working(
                "Router",
                f"review requires revision {revision_count + 1}/2",
                {"mandatory_fixes": state["review"].get("mandatory_fixes", [])},
            )
            return "revise"
        if needs_revision(state["review"]):
            memory.add_working("Router", "revision limit reached; continue with latest bible", state["review"])
        else:
            memory.add_working("Router", "review accepted; continue to package generation", {})
        return "package"

    def node_package_team(state: GraphState) -> GraphState:
        progress("LG 4/7 PackageTeam: 多 Agent 生成公共资料、DM 手册、复盘和线索。")
        if dry_run:
            package = sample_package(state["bible"], state["length_profile"])
        else:
            package: dict[str, Any] = {}
            sections = [
                "public_intro",
                "dm_manual",
                "truth_and_solution",
                "clue_cards",
                "production_notes",
                "safety_and_compliance",
            ]
            for index, section in enumerate(sections, start=1):
                progress(f"      PackageAgent {index}/{len(sections)}: {section}")
                context = retrieve_context(memory, section, state)
                prompt = build_package_section_text_prompt(
                    state["brief"],
                    state["bible"],
                    state["review"],
                    section,
                    state["length_profile"],
                )
                if context:
                    prompt += "\n\n检索到的相关记忆片段：\n" + context
                text = request_markdown(client, f"lg_{section}", prompt, temperature=config.temperature)
                package[section] = text
                memory.add_document(section, "package", text, {"section": section})

            progress("      PropAgent: 设计并生成 handouts。")
            handout_index = client.request_json(
                "handout_index",
                [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": build_handout_index_prompt(state["brief"], state["bible"], state["length_profile"])},
                ],
                temperature=config.temperature,
            )
            package["handouts"] = []
            for index, handout in enumerate(handout_index.get("handouts", []) or [], start=1):
                content = request_markdown(
                    client,
                    f"lg_handout_{index}",
                    build_handout_text_prompt(state["brief"], state["bible"], handout, state["length_profile"]),
                    temperature=config.temperature,
                )
                filename = safe_filename(str(handout.get("filename") or f"handout_{index:02d}.md"))
                if not filename.lower().endswith(".md"):
                    filename += ".md"
                package["handouts"].append(
                    {"filename": filename, "title": str(handout.get("title") or f"Handout {index:02d}"), "content": content}
                )
                memory.add_document(filename, "handout", content, {"filename": filename})
        memory.set_canonical("package_index", {key: True for key in package.keys()})
        memory.checkpoint("PackageTeam", {**state, "package": package})
        return {"package": package}

    def node_player_room(state: GraphState) -> GraphState:
        progress("LG 5/7 PlayerRoom: 多 Agent 生成玩家个人本。")
        if dry_run:
            player_docs = sample_player_docs(state["bible"], state["length_profile"], state["player_depth"])
        else:
            player_docs = []
            for index, player in enumerate(state["bible"].get("cast", []), start=1):
                role_id = str(player.get("id") or f"P{index:02d}")
                role_name = str(player.get("name") or role_id)
                progress(f"      PlayerAgent {index}/{len(state['bible'].get('cast', []))}: {role_id} {role_name}")
                if state["player_depth"] == "normal":
                    content = request_markdown(
                        client,
                        f"lg_player_{role_id}",
                        build_single_player_prompt_with_memory(state, player, memory),
                        temperature=config.temperature,
                    )
                else:
                    content = build_chaptered_player_with_memory(
                        client,
                        memory,
                        state,
                        player,
                        index,
                        config.temperature,
                        progress,
                    )
                doc = {
                    "role_id": role_id,
                    "role_name": role_name,
                    "filename": f"{safe_filename(role_id)}_{safe_filename(role_name)}.md",
                    "content": content,
                }
                player_docs.append(doc)
                memory.add_document(doc["filename"], "player", content, {"role_id": role_id, "role_name": role_name})
        memory.checkpoint("PlayerRoom", {**state, "player_docs": player_docs})
        return {"player_docs": player_docs}

    def node_consistency_auditor(state: GraphState) -> GraphState:
        progress("LG 6/7 ConsistencyAuditor: 本地结构检查和记忆报告。")
        warnings = validate_all(
            state["brief"],
            state["bible"],
            state["review"],
            state["package"],
            state["player_docs"],
            length_profile=state["length_profile"],
            player_depth=state["player_depth"],
        )
        memory.add_working("ConsistencyAuditor", f"{len(warnings)} local warnings", {"warnings": warnings})
        memory.checkpoint("ConsistencyAuditor", {**state, "warnings": warnings})
        return {"warnings": warnings}

    def node_exporter(state: GraphState) -> GraphState:
        progress("LG 7/7 Exporter: 导出标准项目和投稿版目录。")
        quality_report = make_quality_report(state["brief"], state["bible"], state["review"], state.get("warnings", []))
        run_dir = save_project(
            output_root,
            state["brief"],
            state["bible"],
            state["review"],
            state["package"],
            state["player_docs"],
            quality_report,
        )
        memory.export_report(run_dir / "review" / "langgraph_memory_report.md")
        memory.add_working("Exporter", f"exported run dir {run_dir}", {"run_dir": str(run_dir)})
        return {"run_dir": str(run_dir)}

    graph = StateGraph(GraphState)
    graph.add_node("story_architect", node_story_architect)
    graph.add_node("fairness_editor", node_fairness_editor)
    graph.add_node("revision_room", node_revision_room)
    graph.add_node("package_team", node_package_team)
    graph.add_node("player_room", node_player_room)
    graph.add_node("consistency_auditor", node_consistency_auditor)
    graph.add_node("exporter", node_exporter)
    graph.set_entry_point("story_architect")
    graph.add_edge("story_architect", "fairness_editor")
    graph.add_conditional_edges(
        "fairness_editor",
        route_after_review,
        {"revise": "revision_room", "package": "package_team"},
    )
    graph.add_edge("revision_room", "fairness_editor")
    graph.add_edge("package_team", "player_room")
    graph.add_edge("player_room", "consistency_auditor")
    graph.add_edge("consistency_auditor", "exporter")
    graph.add_edge("exporter", END)

    app = graph.compile()
    final_state = app.invoke(base_state)
    return Path(final_state["run_dir"]), final_state.get("warnings", [])


def retrieve_context(memory: HierarchicalMemory, query: str, state: GraphState, *, limit: int = 5) -> str:
    bible = state.get("bible", {})
    query_text = query + "\n" + str(bible.get("truth", {}))[:800]
    chunks = memory.retrieve(query_text, limit=limit)
    return "\n\n".join(f"[{item['kind']}:{item['doc_id']}]\n{item['text']}" for item in chunks)


def build_single_player_prompt_with_memory(
    state: GraphState,
    player: dict[str, Any],
    memory: HierarchicalMemory,
) -> str:
    from .prompts import build_player_text_prompt

    role_query = f"{player.get('id')} {player.get('name')} {player.get('private_secret')} {player.get('motive')}"
    context = retrieve_context(memory, role_query, state, limit=6)
    prompt = build_player_text_prompt(state["brief"], state["bible"], player, state["length_profile"])
    if context:
        prompt += "\n\n检索到的相关记忆片段：\n" + context
    return prompt


def build_chaptered_player_with_memory(
    client: OpenAICompatibleClient,
    memory: HierarchicalMemory,
    state: GraphState,
    player: dict[str, Any],
    index: int,
    temperature: float,
    progress: Progress,
) -> str:
    role_id = str(player.get("id") or f"P{index:02d}")
    role_name = str(player.get("name") or role_id)
    outline = client.request_json(
        f"lg_player_outline_{role_id}",
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": build_player_outline_prompt(
                    state["brief"],
                    state["bible"],
                    player,
                    state["length_profile"],
                    state["player_depth"],
                ),
            },
        ],
        temperature=min(temperature, 0.65),
        compact_retry_hint="只输出玩家本章节大纲 JSON。",
    )
    memory.add_working("PlayerOutline", f"outline for {role_id}", outline)

    rendered_sections: list[tuple[str, str]] = []
    previous_sections: list[str] = []
    for section_index, section in enumerate(PLAYER_BOOK_SECTIONS, start=1):
        progress(f"         ChapterAgent {section_index}/{len(PLAYER_BOOK_SECTIONS)}: {section['title']}")
        context = retrieve_context(memory, f"{role_id} {role_name} {section['title']} {section['focus']}", state, limit=6)
        prompt = build_player_section_prompt(
            state["brief"],
            state["bible"],
            player,
            outline,
            section,
            previous_sections,
            state["length_profile"],
            state["player_depth"],
        )
        if context:
            prompt += "\n\n检索到的相关记忆片段：\n" + context
        content = request_markdown(client, f"lg_player_{role_id}_{section['key']}", prompt, temperature=temperature)
        rendered_sections.append((section["title"], content))
        previous_sections.append(content[:1200])
        memory.add_document(
            f"{role_id}_{section['key']}",
            "player_section",
            content,
            {"role_id": role_id, "role_name": role_name, "section": section["key"]},
        )
    return assemble_player_book(role_name, rendered_sections)
