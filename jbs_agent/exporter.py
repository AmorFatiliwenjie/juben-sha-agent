from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from . import __version__
from .knowledge import SOURCE_NOTES


WINDOWS_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}


def safe_filename(value: str, fallback: str = "untitled") -> str:
    value = value.strip().replace(" ", "_")
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value)
    value = re.sub(r"_+", "_", value).strip("._")
    if not value:
        value = fallback
    if value.upper() in WINDOWS_RESERVED:
        value = f"{value}_file"
    return value[:80]


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.replace("\r\n", "\n"), encoding="utf-8")


def write_json(path: Path, data: Any) -> None:
    write_text(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def unique_run_dir(output_root: Path, title: str) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    base = output_root / f"{timestamp}_{safe_filename(title)}"
    if not base.exists():
        return base
    for index in range(2, 100):
        candidate = output_root / f"{base.name}_{index}"
        if not candidate.exists():
            return candidate
    raise RuntimeError("无法创建唯一输出目录。")


def save_project(
    output_root: Path,
    brief: dict[str, Any],
    bible: dict[str, Any],
    review: dict[str, Any],
    package: dict[str, Any],
    player_docs: list[dict[str, Any]],
    quality_report: str,
) -> Path:
    title = str(bible.get("metadata", {}).get("title") or brief.get("title") or "剧本杀项目")
    run_dir = unique_run_dir(output_root, title)
    run_dir.mkdir(parents=True, exist_ok=False)

    write_text(run_dir / "00_README_FIRST.md", build_run_readme(brief, bible))
    write_text(run_dir / "01_public_intro.md", package.get("public_intro", ""))
    write_text(run_dir / "02_dm_manual.md", package.get("dm_manual", ""))
    write_text(run_dir / "03_truth_and_solution.md", package.get("truth_and_solution", ""))
    write_text(run_dir / "04_clue_cards.md", package.get("clue_cards", ""))
    write_text(run_dir / "05_production_notes.md", package.get("production_notes", ""))
    write_text(run_dir / "06_safety_and_compliance.md", package.get("safety_and_compliance", ""))

    players_dir = run_dir / "players"
    for index, doc in enumerate(player_docs, start=1):
        role_id = safe_filename(str(doc.get("role_id") or f"P{index:02d}"))
        role_name = safe_filename(str(doc.get("role_name") or doc.get("filename") or f"role_{index:02d}"))
        filename = safe_filename(str(doc.get("filename") or f"{role_id}_{role_name}.md"))
        if not filename.lower().endswith(".md"):
            filename += ".md"
        write_text(players_dir / filename, str(doc.get("content", "")))

    handouts_dir = run_dir / "handouts"
    for index, handout in enumerate(package.get("handouts", []) or [], start=1):
        filename = safe_filename(str(handout.get("filename") or f"handout_{index:02d}.md"))
        if not filename.lower().endswith(".md"):
            filename += ".md"
        content = str(handout.get("content") or "")
        if handout.get("title") and not content.lstrip().startswith("#"):
            content = f"# {handout['title']}\n\n{content}"
        write_text(handouts_dir / filename, content)

    write_json(run_dir / "source" / "brief.json", brief)
    write_json(run_dir / "source" / "story_bible.json", bible)
    write_json(run_dir / "source" / "quality_review.json", review)
    write_json(run_dir / "source" / "full_package.json", package)
    write_text(run_dir / "review" / "quality_report.md", quality_report)

    manifest = build_manifest(run_dir, brief, bible)
    write_json(run_dir / "00_manifest.json", manifest)
    try:
        from .submission import build_submission_for_run

        build_submission_for_run(run_dir, force=True)
    except Exception as exc:
        write_text(run_dir / "submission_error.txt", f"投稿版目录生成失败：{exc}\n")
    return run_dir


def build_run_readme(brief: dict[str, Any], bible: dict[str, Any]) -> str:
    metadata = bible.get("metadata", {})
    return f"""# {metadata.get("title", brief.get("title", "剧本杀项目"))}

本目录是一次完整生成结果。建议阅读顺序：

1. `01_public_intro.md`：发给所有玩家的公开导入。
2. `players/`：每名玩家的个人本，单独分发。
3. `02_dm_manual.md`：主持人流程和信息边界。
4. `04_clue_cards.md` 与 `handouts/`：可打印线索和道具文本。
5. `03_truth_and_solution.md`：仅 DM 可见的完整真相和复盘。
6. `review/quality_report.md`：模型审稿与本地结构检查。

基础信息：

- 玩家数：{metadata.get("players", brief.get("players", ""))}
- 预计时长：{metadata.get("duration_minutes", brief.get("duration_minutes", ""))} 分钟
- 类型：{metadata.get("genre", brief.get("genre", ""))}
- 难度：{metadata.get("difficulty", brief.get("difficulty", ""))}
- 适龄：{metadata.get("content_rating", "")}

注意：商用、门店投放、未成年人参与或公开发布前，请人工复核内容安全、版权原创性和所在地管理要求。
"""


def build_manifest(run_dir: Path, brief: dict[str, Any], bible: dict[str, Any]) -> dict[str, Any]:
    files = []
    for path in sorted(run_dir.rglob("*")):
        if path.is_file() and path.name != "00_manifest.json":
            rel = path.relative_to(run_dir).as_posix()
            files.append(
                {
                    "path": rel,
                    "bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )

    return {
        "project": "jbs-agent",
        "version": __version__,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "title": bible.get("metadata", {}).get("title") or brief.get("title"),
        "players": bible.get("metadata", {}).get("players") or brief.get("players"),
        "output_standard": {
            "public_files": ["01_public_intro.md"],
            "dm_only_files": ["02_dm_manual.md", "03_truth_and_solution.md", "source/story_bible.json"],
            "player_private_dir": "players/",
            "printable_assets": ["04_clue_cards.md", "handouts/"],
            "audit_files": ["00_manifest.json", "review/quality_report.md", "source/"],
        },
        "research_sources": SOURCE_NOTES,
        "files": files,
    }
