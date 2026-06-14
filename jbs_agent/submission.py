from __future__ import annotations

import json
import re
import shutil
import zipfile
from pathlib import Path
from typing import Any

from .docx_writer import markdown_to_docx_blocks, paragraph_xml, rich_paragraph_xml, table_xml, write_docx
from .exporter import safe_filename, write_json, write_text


SUBMISSION_GUIDE = """# 投稿版目录说明

本目录按《百变大侦探》投稿要求整理，可作为打包投稿前的工作目录。

注意事项：

- 已生成 Word 文档（.docx），正文使用宋体并设置首行缩进。
- 地图文件夹内提供了文字版地图需求说明；如平台需要图片，请后续补手绘草稿或正式图片。
- 投票与真相文档由现有 story_bible 自动整理，投稿前建议人工检查正确选项、每名角色题量均衡和推理链完整性。
- 请投稿前补齐作者微信号，并按平台要求命名邮件主题：剧本名+人数+题材+作者微信号。
- 所有内容仍需人工复核原创性、线索公平性、红字答案和信息边界。
"""


def build_submission_for_run(run_dir: Path, *, force: bool = True) -> Path:
    source_dir = run_dir / "source"
    bible = read_json(source_dir / "story_bible.json")
    brief = read_json(source_dir / "brief.json") if (source_dir / "brief.json").exists() else {}
    package = read_json(source_dir / "full_package.json") if (source_dir / "full_package.json").exists() else {}
    review = read_json(source_dir / "quality_review.json") if (source_dir / "quality_review.json").exists() else {}
    players = read_player_docs(run_dir / "players")
    handouts = read_handouts(run_dir / "handouts")

    metadata = bible.get("metadata", {})
    title = str(metadata.get("title") or brief.get("title") or run_dir.name)
    players_count = int(metadata.get("players") or brief.get("players") or len(players) or 0)
    genre = str(metadata.get("genre") or brief.get("genre") or "剧本杀")

    submission_dir = run_dir / "submission"
    if force and submission_dir.exists():
        shutil.rmtree(submission_dir)
    submission_dir.mkdir(parents=True, exist_ok=True)

    write_text(submission_dir / "00_投稿版目录说明.md", SUBMISSION_GUIDE)
    write_docx(
        submission_dir / "01_简介、角色、区域.docx",
        build_intro_blocks(bible, brief),
    )
    write_docx(
        submission_dir / "02_规则说明.docx",
        markdown_to_docx_blocks(package.get("dm_manual") or make_rules_markdown(bible)),
    )
    write_docx(
        submission_dir / "03_亮点、作者阐述.docx",
        build_highlight_blocks(bible, brief, review),
    )
    write_docx(
        submission_dir / "04_结局.docx",
        build_ending_blocks(bible, package),
    )

    build_player_folder(submission_dir, bible, players)
    build_clue_folder(submission_dir, bible, package, handouts)
    build_vote_folder(submission_dir, bible)
    build_truth_folder(submission_dir, bible, package)
    build_map_folder(submission_dir, bible)

    manifest = {
        "title": title,
        "players": players_count,
        "genre": genre,
        "source_run": str(run_dir),
        "email_subject_template": f"{title}+{players_count}人+{genre}+作者微信号",
        "submission_requirements_source": "docs/投稿要求.md",
        "generated_files": sorted(path.relative_to(submission_dir).as_posix() for path in submission_dir.rglob("*") if path.is_file()),
    }
    write_json(submission_dir / "00_submission_manifest.json", manifest)
    make_submission_zip(run_dir, submission_dir, title, players_count, genre)
    return submission_dir


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_player_docs(players_dir: Path) -> list[dict[str, str]]:
    docs = []
    if not players_dir.exists():
        return docs
    for path in sorted(players_dir.glob("*.md")):
        stem = path.stem
        match = re.match(r"(P\d+)[_\-\s]*(.*)", stem, flags=re.IGNORECASE)
        role_id = match.group(1) if match else stem
        role_name = match.group(2) if match and match.group(2) else stem
        docs.append(
            {
                "role_id": role_id,
                "role_name": role_name,
                "filename": path.name,
                "content": path.read_text(encoding="utf-8"),
            }
        )
    return docs


def read_handouts(handouts_dir: Path) -> list[dict[str, str]]:
    docs = []
    if not handouts_dir.exists():
        return docs
    for path in sorted(handouts_dir.glob("*.md")):
        docs.append({"filename": path.name, "content": path.read_text(encoding="utf-8")})
    return docs


def build_intro_blocks(bible: dict[str, Any], brief: dict[str, Any]) -> list[str]:
    metadata = bible.get("metadata", {})
    world = bible.get("world", {})
    cast = bible.get("cast", [])
    game_flow = bible.get("game_flow", [])
    blocks = [
        paragraph_xml("简介、角色、区域", heading=1),
        paragraph_xml("故事简介", heading=2),
        paragraph_xml(str(metadata.get("one_sentence_pitch") or brief.get("custom_notes") or "")),
        paragraph_xml(f"题材：{metadata.get('genre', brief.get('genre', ''))}"),
        paragraph_xml(f"人数：{metadata.get('players', brief.get('players', ''))}人"),
        paragraph_xml(f"预计时长：{metadata.get('duration_minutes', brief.get('duration_minutes', ''))}分钟"),
        paragraph_xml(f"时代/背景：{world.get('era', '')}；{world.get('setting', '')}"),
        paragraph_xml("角色简介", heading=2),
    ]
    rows = [["角色", "公开身份", "动机/关系摘要", "头像或外貌需求"]]
    for player in cast:
        rows.append(
            [
                f"{player.get('id', '')} {player.get('name', '')}",
                str(player.get("public_identity", "")),
                "; ".join(str(item) for item in player.get("key_relationships", [])) or str(player.get("motive", "")),
                "可按角色气质制作头像；投稿前可人工补充外貌细节。",
            ]
        )
    blocks.append(table_xml(rows))
    blocks.append(paragraph_xml("区域", heading=2))
    area_rows = [["流程/幕", "主要场所", "说明"]]
    for flow in game_flow:
        area_rows.append(
            [
                f"第{flow.get('round', '')}幕/轮：{flow.get('title', '')}",
                infer_area(flow, world),
                str(flow.get("public_event", "")),
            ]
        )
    if len(area_rows) == 1:
        area_rows.append(["全剧", str(world.get("setting", "")), "以 story_bible 为准。"])
    blocks.append(table_xml(area_rows))
    blocks.append(paragraph_xml("开局提示/作者的话", heading=2))
    blocks.append(paragraph_xml("本剧本为原创生成草案，投稿前请人工复核原创性、信息边界、线索公平性和平台适配。"))
    return blocks


def build_highlight_blocks(bible: dict[str, Any], brief: dict[str, Any], review: dict[str, Any]) -> list[str]:
    metadata = bible.get("metadata", {})
    expanded = bible.get("expanded_design", {})
    blocks = [
        paragraph_xml("亮点、作者阐述", heading=1),
        paragraph_xml("剧本亮点", heading=2),
    ]
    highlights = [
        metadata.get("one_sentence_pitch"),
        *bible.get("quality_targets", []),
        *expanded.get("mechanics", []),
        *expanded.get("character_arcs", []),
    ]
    for item in highlights:
        if item:
            blocks.append(paragraph_xml(f"· {item}", first_line_indent=False))
    blocks.extend(
        [
            paragraph_xml("作者阐述", heading=2),
            paragraph_xml(str(brief.get("custom_notes") or "本作重视玩家视角推理链、角色信息均衡和多幕流程体验。")),
            paragraph_xml("编辑复核提示", heading=2),
            paragraph_xml(str(review.get("review_summary") or "投稿前建议组织一次完整测本，检查任务、投票与真相解释是否一一对应。")),
        ]
    )
    return blocks


def build_ending_blocks(bible: dict[str, Any], package: dict[str, Any]) -> list[str]:
    ending = bible.get("ending", {})
    blocks = [paragraph_xml("结局", heading=1)]
    for item in ending.get("possible_endings", []):
        blocks.append(paragraph_xml(f"· {item}", first_line_indent=False))
    blocks.append(paragraph_xml("角色最后去向", heading=2))
    for player in bible.get("cast", []):
        blocks.append(paragraph_xml(f"{player.get('name', player.get('id'))}：根据玩家投票与真相公开程度，走向公开、和解或继续隐瞒的结局。投稿前可进一步细化。"))
    if package.get("truth_and_solution"):
        blocks.append(paragraph_xml("参考完整复盘", heading=2))
        blocks.extend(markdown_to_docx_blocks(str(package.get("truth_and_solution"))[:3000]))
    return blocks


def build_player_folder(submission_dir: Path, bible: dict[str, Any], players: list[dict[str, str]]) -> None:
    root = submission_dir / "人物剧本"
    root.mkdir(parents=True, exist_ok=True)
    player_lookup = {doc["role_id"].upper(): doc for doc in players}
    for player in bible.get("cast", []):
        role_id = str(player.get("id") or "").upper()
        role_name = str(player.get("name") or role_id)
        doc = player_lookup.get(role_id)
        content = doc["content"] if doc else make_missing_player_content(player)
        blocks = [
            paragraph_xml(f"{role_name} 第一幕人物剧本", heading=1),
            paragraph_xml("当幕任务", heading=2),
        ]
        tasks = build_player_tasks(player, bible)
        for task in tasks:
            blocks.append(rich_paragraph_xml([("任务：", True, None), (task, False, None)]))
        blocks.append(paragraph_xml("人物剧本正文", heading=2))
        blocks.extend(markdown_to_docx_blocks(content))
        filename = f"{safe_filename(role_name)}_第一幕人物剧本.docx"
        write_docx(root / filename, blocks)


def build_clue_folder(submission_dir: Path, bible: dict[str, Any], package: dict[str, Any], handouts: list[dict[str, str]]) -> None:
    root = submission_dir / "线索"
    root.mkdir(parents=True, exist_ok=True)
    clues_by_round: dict[int, list[dict[str, Any]]] = {}
    for clue in bible.get("clues", []):
        try:
            round_no = int(clue.get("round") or 1)
        except (TypeError, ValueError):
            round_no = 1
        clues_by_round.setdefault(round_no, []).append(clue)
    for round_no in sorted(clues_by_round):
        rows = [["搜证地点", "线索名", "线索内容", "备注"]]
        for index, clue in enumerate(clues_by_round[round_no], start=1):
            rows.append(
                [
                    str(clue.get("holder") or clue.get("visibility") or "公共区域"),
                    f"{index}/{len(clues_by_round[round_no])} {clue.get('id', '')} {clue.get('title', '')}",
                    str(clue.get("text") or clue.get("reveals") or ""),
                    build_clue_note(clue),
                ]
            )
        blocks = [
            paragraph_xml(f"第{round_no}幕线索", heading=1),
            paragraph_xml("线索表", heading=2),
            table_xml(rows),
        ]
        write_docx(root / f"{round_no:02d}_第{round_no}幕线索.docx", blocks)
    if handouts:
        blocks = [paragraph_xml("道具文本与特殊线索附件", heading=1)]
        for handout in handouts:
            blocks.append(paragraph_xml(handout["filename"], heading=2))
            blocks.extend(markdown_to_docx_blocks(handout["content"]))
        write_docx(root / "99_道具文本与特殊线索附件.docx", blocks)
    elif package.get("clue_cards"):
        write_docx(root / "99_线索卡原文.docx", markdown_to_docx_blocks(package.get("clue_cards", "")))


def build_vote_folder(submission_dir: Path, bible: dict[str, Any]) -> None:
    root = submission_dir / "投票"
    root.mkdir(parents=True, exist_ok=True)
    cast = bible.get("cast", [])
    culprit = str(bible.get("truth", {}).get("culprit") or "")
    final_questions = bible.get("ending", {}).get("final_vote_questions", [])
    rows = [["角色", "题型", "投票问题", "备选选项", "正确选项"]]
    for player in cast:
        role_name = str(player.get("name") or player.get("id"))
        rows.append(
            [
                role_name,
                "单选",
                "谁是真凶？（凶手可投自己，按平台规则可人工调整）",
                "；".join(str(p.get("name") or p.get("id")) for p in cast),
                (culprit, "FF0000"),
            ]
        )
        for question in final_questions[1:2]:
            rows.append([role_name, "填空", str(question), "玩家自由填写，DM 依据真相判定", ("见真相文档", "FF0000")])
    blocks = [
        paragraph_xml("第一幕投票", heading=1),
        paragraph_xml("每个角色题目数量保持一致；投稿前请人工复核私人任务与投票强关联。"),
        table_xml(rows),
    ]
    write_docx(root / "01_第一幕投票.docx", blocks)


def build_truth_folder(submission_dir: Path, bible: dict[str, Any], package: dict[str, Any]) -> None:
    root = submission_dir / "真相"
    root.mkdir(parents=True, exist_ok=True)
    blocks = [paragraph_xml("第一幕真相", heading=1)]
    blocks.extend(markdown_to_docx_blocks(package.get("truth_and_solution") or ""))
    blocks.append(paragraph_xml("玩家视角推理链", heading=2))
    for clue in bible.get("clues", []):
        blocks.append(
            paragraph_xml(
                f"根据线索 {clue.get('id')}《{clue.get('title', '')}》：{clue.get('reveals', clue.get('text', ''))}，可推出：{clue.get('fairness_note', '')}"
            )
        )
    blocks.append(paragraph_xml("任务与投票说明", heading=2))
    for player in bible.get("cast", []):
        blocks.append(paragraph_xml(f"{player.get('name', player.get('id'))}：其任务围绕“{player.get('personal_goal', '')}”，投票时应结合个人本行动线与线索表判断。"))
    write_docx(root / "01_第一幕真相.docx", blocks)

    story_blocks = [paragraph_xml("故事还原", heading=1)]
    truth = bible.get("truth", {})
    story_blocks.append(paragraph_xml(f"受害者：{truth.get('victim', '')}"))
    story_blocks.append(paragraph_xml(f"真凶：{truth.get('culprit', '')}"))
    story_blocks.append(paragraph_xml(f"动机：{truth.get('motive_truth', '')}"))
    story_blocks.append(paragraph_xml(f"手法：{truth.get('method', '')}"))
    story_blocks.append(paragraph_xml(f"核心诡计：{truth.get('core_trick', '')}"))
    story_blocks.append(paragraph_xml("真实时间线", heading=2))
    rows = [["时间", "事件", "玩家可见性", "真相备注"]]
    for item in truth.get("timeline", []):
        rows.append([str(item.get("time", "")), str(item.get("event", "")), str(item.get("visible_to", "")), str(item.get("truth_note", ""))])
    story_blocks.append(table_xml(rows))
    write_docx(root / "02_故事还原.docx", story_blocks)


def build_map_folder(submission_dir: Path, bible: dict[str, Any]) -> None:
    root = submission_dir / "地图"
    root.mkdir(parents=True, exist_ok=True)
    world = bible.get("world", {})
    blocks = [
        paragraph_xml("地图与房间示意图需求", heading=1),
        paragraph_xml("当前自动生成的是文字版地图需求。投稿前如有推理必需地图信息，请补充手绘草稿图或正式图片。"),
        paragraph_xml("主要区域", heading=2),
        paragraph_xml(str(world.get("setting", ""))),
        paragraph_xml("按幕区域", heading=2),
    ]
    rows = [["幕/轮", "区域", "说明"]]
    for flow in bible.get("game_flow", []):
        rows.append([f"第{flow.get('round', '')}幕", infer_area(flow, world), str(flow.get("public_event", ""))])
    blocks.append(table_xml(rows))
    write_docx(root / "01_地图与房间示意图需求.docx", blocks)
    write_text(root / "README_地图补图说明.txt", "如图片中含有推理必需信息，投稿前必须补充图片或手绘草稿图。\n")


def make_submission_zip(run_dir: Path, submission_dir: Path, title: str, players: int, genre: str) -> Path:
    zip_name = f"{safe_filename(title)}+{players}人+{safe_filename(genre)}+作者微信号.zip"
    zip_path = run_dir / zip_name
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(submission_dir.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(submission_dir.parent))
    return zip_path


def infer_area(flow: dict[str, Any], world: dict[str, Any]) -> str:
    title = str(flow.get("title", ""))
    event = str(flow.get("public_event", ""))
    setting = str(world.get("setting", ""))
    if title:
        return title
    if event:
        return event[:30]
    return setting[:40] or "主要场景"


def build_player_tasks(player: dict[str, Any], bible: dict[str, Any]) -> list[str]:
    tasks = [
        str(player.get("personal_goal") or "完成个人目标，并在投票中给出自洽推理。"),
        f"围绕自己的动机“{player.get('motive', '')}”进行解释或隐藏。",
        "结合本幕线索判断最终投票问题，避免边缘化。",
    ]
    return [task for task in tasks if task.strip()]


def build_clue_note(clue: dict[str, Any]) -> str:
    notes = [
        f"可见性：{clue.get('visibility', '')}",
        f"真伪：{clue.get('truth_value', '')}",
        f"指向：{', '.join(str(x) for x in clue.get('points_to', []))}",
    ]
    if clue.get("misleads_to"):
        notes.append(f"误导：{', '.join(str(x) for x in clue.get('misleads_to', []))}")
    return "；".join(note for note in notes if note)


def make_rules_markdown(bible: dict[str, Any]) -> str:
    lines = ["# 规则说明", "", "## 游戏流程"]
    for flow in bible.get("game_flow", []):
        lines.append(f"- 第{flow.get('round')}幕：{flow.get('title')}。{flow.get('dm_goal', '')}")
    return "\n".join(lines) + "\n"


def make_missing_player_content(player: dict[str, Any]) -> str:
    return (
        f"# {player.get('name', player.get('id', '角色'))}\n\n"
        f"公开身份：{player.get('public_identity', '')}\n\n"
        f"私人秘密：{player.get('private_secret', '')}\n\n"
        f"个人目标：{player.get('personal_goal', '')}\n"
    )
