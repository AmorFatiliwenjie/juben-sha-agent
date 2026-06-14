from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from .config import RuntimeConfig
from .exporter import save_project
from .llm import OpenAICompatibleClient
from .prompts import (
    SYSTEM_PROMPT,
    build_auto_brief_prompt,
    build_bible_prompt,
    build_handout_index_prompt,
    build_handout_text_prompt,
    build_package_prompt,
    build_package_section_text_prompt,
    build_player_outline_prompt,
    build_player_prompt,
    build_player_section_prompt,
    build_player_text_prompt,
    build_review_prompt,
    build_revision_prompt,
    assemble_player_book,
    PLAYER_BOOK_SECTIONS,
)
from .exporter import safe_filename
from .length_profiles import is_expanded_profile
from .sample_data import sample_auto_brief, sample_bible, sample_package, sample_player_docs, sample_review
from .validator import make_quality_report, normalize_role_ref, validate_all

Progress = Callable[[str], None]


def load_brief(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"找不到 brief 文件: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def generate_auto_brief(
    config: RuntimeConfig,
    *,
    seed: str = "",
    length_profile: str = "standard",
    dry_run: bool = False,
    progress: Progress | None = None,
) -> dict[str, Any]:
    progress = progress or (lambda message: None)
    if dry_run:
        progress("auto-brief dry-run: 使用内置示例 brief。")
        return sample_auto_brief(seed, length_profile)

    progress("0/5 自动生成创作 brief。")
    client = OpenAICompatibleClient(
        config.api_key,
        config.base_url,
        config.model,
        timeout=config.timeout,
        max_tokens=config.max_tokens,
        json_mode=config.json_mode,
    )
    return client.request_json(
        "auto_brief",
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_auto_brief_prompt(seed, length_profile)},
        ],
        temperature=max(0.75, config.temperature),
    )


def run_pipeline(
    brief: dict[str, Any],
    config: RuntimeConfig,
    output_root: Path,
    *,
    dry_run: bool = False,
    length_profile: str = "standard",
    player_depth: str = "normal",
    progress: Progress | None = None,
) -> tuple[Path, list[str]]:
    progress = progress or (lambda message: None)
    brief = dict(brief)
    brief["output_scale"] = length_profile
    brief["player_depth"] = player_depth

    if dry_run:
        progress("dry-run: 使用内置示例数据验证导出结构。")
        bible = sample_bible(brief)
        normalize_bible_refs(bible)
        review = sample_review()
        package = sample_package(bible, length_profile)
        player_docs = sample_player_docs(bible, length_profile, player_depth)
    else:
        client = OpenAICompatibleClient(
            config.api_key,
            config.base_url,
            config.model,
            timeout=config.timeout,
            max_tokens=config.max_tokens,
            json_mode=config.json_mode,
        )

        progress("1/5 生成 story bible、角色关系和线索矩阵。")
        bible = client.request_json(
            "story_bible",
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_bible_prompt(brief, length_profile)},
            ],
            temperature=min(config.temperature, 0.55),
            compact_retry_hint=(
                "必须压缩 story_bible：每个字符串不超过 80 个中文字符，"
                "clue.text 不超过 70 个中文字符，只写蓝图，不写长篇正文。"
            ),
        )
        normalize_bible_refs(bible)

        progress("2/5 审稿：检查公平推理、角色平衡和内容安全。")
        review = client.request_json(
            "quality_review",
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_review_prompt(brief, bible)},
            ],
            temperature=0.2,
        )

        if needs_revision(review):
            progress("3/5 根据审稿意见修订 story bible。")
            bible = client.request_json(
                "revised_story_bible",
                [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": build_revision_prompt(brief, bible, review)},
                ],
                temperature=max(0.2, config.temperature - 0.2),
            )
            normalize_bible_refs(bible)
            progress("3/5 复审修订结果。")
            review = client.request_json(
                "quality_review_after_revision",
                [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": build_review_prompt(brief, bible)},
                ],
                temperature=0.2,
            )
        else:
            progress("3/5 初稿通过审稿，跳过修订。")

        progress("4/5 生成公共资料包、DM 手册、复盘和线索卡。")
        if is_expanded_profile(length_profile):
            package = generate_expanded_package(client, brief, bible, review, length_profile, config.temperature, progress)
        else:
            package = client.request_json(
                "script_package",
                [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": build_package_prompt(brief, bible, review, length_profile)},
                ],
                temperature=config.temperature,
            )

        progress("5/5 逐个生成玩家个人本，控制信息边界。")
        player_docs = []
        for index, player in enumerate(bible.get("cast", []), start=1):
            progress(f"   生成玩家本 {index}/{len(bible.get('cast', []))}: {player.get('id', '')} {player.get('name', '')}")
            if player_depth != "normal":
                player_doc = generate_chaptered_player_doc(
                    client,
                    brief,
                    bible,
                    player,
                    index,
                    length_profile,
                    player_depth,
                    config.temperature,
                    progress,
                )
            elif is_expanded_profile(length_profile):
                content = request_markdown(
                    client,
                    f"player_doc_{player.get('id', index)}",
                    build_player_text_prompt(brief, bible, player, length_profile),
                    temperature=config.temperature,
                )
                role_id = str(player.get("id") or f"P{index:02d}")
                role_name = str(player.get("name") or f"role_{index:02d}")
                player_doc = {
                    "role_id": role_id,
                    "role_name": role_name,
                    "filename": f"{safe_filename(role_id)}_{safe_filename(role_name)}.md",
                    "content": content,
                }
            else:
                player_doc = client.request_json(
                    f"player_doc_{player.get('id', index)}",
                    [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": build_player_prompt(brief, bible, player, length_profile)},
                    ],
                    temperature=config.temperature,
                )
            player_docs.append(player_doc)

    warnings = validate_all(brief, bible, review, package, player_docs, length_profile=length_profile, player_depth=player_depth)
    quality_report = make_quality_report(brief, bible, review, warnings)
    run_dir = save_project(output_root, brief, bible, review, package, player_docs, quality_report)
    return run_dir, warnings


def needs_revision(review: dict[str, Any]) -> bool:
    if review.get("pass") is False:
        return True
    mandatory = review.get("mandatory_fixes", [])
    return isinstance(mandatory, list) and len(mandatory) > 0


def normalize_bible_refs(bible: dict[str, Any]) -> None:
    cast = bible.get("cast", [])
    truth = bible.get("truth", {})
    if isinstance(cast, list) and isinstance(truth, dict):
        culprit = truth.get("culprit")
        normalized = normalize_role_ref(str(culprit or ""), cast)
        if normalized:
            truth["culprit"] = normalized


def generate_expanded_package(
    client: OpenAICompatibleClient,
    brief: dict[str, Any],
    bible: dict[str, Any],
    review: dict[str, Any],
    length_profile: str,
    temperature: float,
    progress: Progress,
) -> dict[str, Any]:
    package: dict[str, Any] = {}
    section_keys = [
        "public_intro",
        "dm_manual",
        "truth_and_solution",
        "clue_cards",
        "production_notes",
        "safety_and_compliance",
    ]
    for index, section_key in enumerate(section_keys, start=1):
        progress(f"   长篇资料 {index}/{len(section_keys)}: {section_key}")
        package[section_key] = request_markdown(
            client,
            f"expanded_{section_key}",
            build_package_section_text_prompt(brief, bible, review, section_key, length_profile),
            temperature=temperature,
        )

    progress("   长篇资料 handouts: 设计道具清单。")
    handout_index = client.request_json(
        "handout_index",
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_handout_index_prompt(brief, bible, length_profile)},
        ],
        temperature=temperature,
    )
    package["handouts"] = []
    handouts = handout_index.get("handouts", [])
    if not isinstance(handouts, list):
        handouts = []
    for index, handout in enumerate(handouts, start=1):
        progress(f"   生成 handout {index}/{len(handouts)}: {handout.get('title', '')}")
        filename = safe_filename(str(handout.get("filename") or f"handout_{index:02d}.md"))
        if not filename.lower().endswith(".md"):
            filename += ".md"
        content = request_markdown(
            client,
            f"handout_{index:02d}",
            build_handout_text_prompt(brief, bible, handout, length_profile),
            temperature=temperature,
        )
        package["handouts"].append(
            {
                "filename": filename,
                "title": str(handout.get("title") or f"Handout {index:02d}"),
                "content": content,
            }
        )
    return package


def generate_chaptered_player_doc(
    client: OpenAICompatibleClient,
    brief: dict[str, Any],
    bible: dict[str, Any],
    player: dict[str, Any],
    index: int,
    length_profile: str,
    player_depth: str,
    temperature: float,
    progress: Progress,
) -> dict[str, str]:
    role_id = str(player.get("id") or f"P{index:02d}")
    role_name = str(player.get("name") or f"role_{index:02d}")

    progress(f"      生成个人本大纲: {role_id} {role_name}")
    outline = client.request_json(
        f"player_outline_{role_id}",
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_player_outline_prompt(brief, bible, player, length_profile, player_depth)},
        ],
        temperature=min(temperature, 0.65),
        compact_retry_hint="只输出章节大纲 JSON，每个数组项使用短句，不写正文。",
    )

    rendered_sections: list[tuple[str, str]] = []
    previous_sections: list[str] = []
    for section_index, section in enumerate(PLAYER_BOOK_SECTIONS, start=1):
        progress(f"      扩写章节 {section_index}/{len(PLAYER_BOOK_SECTIONS)}: {section['title']}")
        content = request_markdown(
            client,
            f"player_{role_id}_{section['key']}",
            build_player_section_prompt(
                brief,
                bible,
                player,
                outline,
                section,
                previous_sections,
                length_profile,
                player_depth,
            ),
            temperature=temperature,
        )
        rendered_sections.append((section["title"], content))
        previous_sections.append(content[:1200])

    return {
        "role_id": role_id,
        "role_name": role_name,
        "filename": f"{safe_filename(role_id)}_{safe_filename(role_name)}.md",
        "content": assemble_player_book(role_name, rendered_sections),
    }


def request_markdown(
    client: OpenAICompatibleClient,
    label: str,
    prompt: str,
    *,
    temperature: float,
) -> str:
    text = client.complete(
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=temperature,
        json_object=False,
    )
    cleaned = clean_markdown(text)
    if not cleaned.strip():
        raise RuntimeError(f"{label} 返回了空内容。")
    return cleaned


def clean_markdown(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    return cleaned + "\n"
