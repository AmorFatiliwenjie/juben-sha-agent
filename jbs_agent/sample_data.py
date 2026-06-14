from __future__ import annotations

from typing import Any

from .length_profiles import get_profile
from .prompts import PLAYER_BOOK_SECTIONS, player_depth_target_chars


def sample_auto_brief(seed: str = "", length_profile: str = "standard") -> dict[str, Any]:
    profile = get_profile(length_profile)
    seed_note = seed.strip() or "dry-run 自动生成示例"
    return {
        "title": "雾港回声",
        "players": 6,
        "duration_minutes": max(180, int(profile.get("rounds", 3)) * 55),
        "genre": "本格推理 / 情感沉浸",
        "difficulty": "medium",
        "setting": "一座常年起雾的海边旧港，核心场景是停用多年的灯塔与旁边的海事档案馆。",
        "era": "近现代架空",
        "tone": "悬疑、克制、带一点遗憾和救赎",
        "target_audience": "有 1-3 次剧本杀经验的成年人玩家",
        "must_have": [
            "每个角色都有动机，但只有一个真凶",
            "必须有可复盘的时间线诡计",
            "不要使用超自然万能解释",
            "线索要能公平推出真相",
            "玩家个人本不能互相泄露最终答案",
            "DM 新手也能按手册主持",
        ],
        "avoid": [
            "真实案件改编",
            "露骨血腥描写",
            "未成年人性内容",
            "现实犯罪操作教程",
            "仇恨歧视",
            "真实个人隐私",
            "抄袭现成影视、小说或游戏 IP",
            "超自然万能解释",
        ],
        "content_rating": "15+",
        "output_language": "zh-CN",
        "custom_notes": f"这是根据种子“{seed_note}”生成的 {length_profile} dry-run 示例 brief；正式运行时会由模型自动创作。",
    }


def sample_bible(brief: dict[str, Any]) -> dict[str, Any]:
    players = int(brief.get("players") or 6)
    profile = get_profile(str(brief.get("output_scale") or "standard"))
    title = brief.get("title") or "雾港回声"
    names = ["沈知微", "陆青衡", "白砚", "周澜", "秦望", "许棠", "林岫", "陈未"]
    cast = []
    for index in range(players):
        pid = f"P{index + 1:02d}"
        name = names[index % len(names)]
        cast.append(
            {
                "id": pid,
                "name": name,
                "public_identity": f"雾港旧案相关人 {index + 1}",
                "private_secret": f"{name} 曾在案发前隐瞒一段十分钟行踪。",
                "personal_goal": "洗清自己的嫌疑，同时保护一个不愿公开的秘密。",
                "motive": "与受害者存在利益或情感纠葛。",
                "alibi": "案发时声称在大厅附近，但缺少完整证明。",
                "key_relationships": ["与受害者有旧怨", "与另一名玩家互相隐瞒"],
                "knows_before_game": ["旧灯塔停电并非意外"],
                "can_reveal": ["自己曾见过一枚裂纹怀表"],
            }
        )

    clue_count = max(players * int(profile.get("clues_per_player", 3)), 12)
    clues = []
    for index in range(clue_count):
        cid = f"C{index + 1:02d}"
        round_no = index % 3 + 1
        holder = cast[index % players]["id"]
        clues.append(
            {
                "id": cid,
                "title": f"测试线索 {index + 1}",
                "type": "物证",
                "round": round_no,
                "visibility": "private" if index % 2 else "public",
                "holder": holder,
                "text": f"这是一张 dry-run 测试线索卡，用于验证导出格式。编号 {cid}。",
                "truth_value": "true" if index % 3 else "partial",
                "points_to": [cast[(index + 1) % players]["id"]],
                "misleads_to": [holder],
                "reveals": "帮助还原停电、怀表和案发时间的关系。",
                "fairness_note": "此线索会在复盘前发放，不作为最终突兀证据。",
            }
        )

    game_flow = []
    for index in range(int(profile.get("rounds", 3))):
        round_no = index + 1
        released = [clue["id"] for clue in clues if clue["round"] == ((index % 3) + 1)][:4]
        game_flow.append(
            {
                "round": round_no,
                "title": ["雾起", "潮声", "回声", "旧档", "终灯"][index % 5],
                "duration_minutes": 45 + index * 5,
                "dm_goal": "推进关系网、时间线和关键物证。",
                "public_event": "旧灯塔出现新的可疑记录。",
                "player_tasks": ["盘问行踪", "交换线索", "重建时间线"],
                "release_clues": released,
            }
        )

    return {
        "metadata": {
            "title": title,
            "subtitle": "dry-run 示例",
            "players": players,
            "duration_minutes": int(brief.get("duration_minutes") or 180),
            "genre": brief.get("genre") or "本格推理",
            "difficulty": brief.get("difficulty") or "medium",
            "content_rating": "15+",
            "one_sentence_pitch": "一场雾港旧灯塔下的失踪案，把多年沉默推回众人面前。",
        },
        "quality_targets": ["公平线索", "角色平衡", "主持可执行"],
        "world": {
            "setting": brief.get("setting") or "海边小镇旧灯塔",
            "era": brief.get("era") or "近现代架空",
            "tone": brief.get("tone") or "悬疑、克制、情感余韵",
            "core_question": "受害者为何在停电的十分钟内消失？",
            "themes": ["旧案", "记忆", "选择"],
        },
        "cast": cast,
        "truth": {
            "victim": "顾闻潮",
            "culprit": cast[min(2, players - 1)]["id"],
            "method": "利用停电制造时间差并转移关键物证。",
            "core_trick": "怀表裂纹记录了真实摔落时间。",
            "motive_truth": "凶手为了掩盖多年前的替罪真相。",
            "timeline": [
                {"time": "20:10", "event": "众人抵达旧灯塔", "visible_to": "all", "truth_note": "公开开场"},
                {"time": "20:40", "event": "灯塔停电", "visible_to": "partial", "truth_note": "关键时间窗"},
                {"time": "20:50", "event": "受害者失踪", "visible_to": "all", "truth_note": "表象时间"},
            ],
            "why_only_culprit": "只有凶手同时拥有钥匙、停电知识和怀表接触机会。",
            "innocent_clearance": ["其他角色的动机成立，但缺少三要素闭合。"],
        },
        "game_flow": game_flow,
        "clues": clues,
        "red_herrings": ["每个人都隐瞒十分钟，但只有凶手的十分钟与物证闭合。"],
        "expanded_design": {
            "act_structure": ["关系建立", "时间线拆解", "物证反转", "终局指认"],
            "relationship_web": ["每位角色都与受害者有旧怨，也与至少一位玩家互相保护。"],
            "character_arcs": ["从自保到面对旧案真相。"],
            "mechanics": ["分轮发线索", "最终三问投票", "DM 分级提示"],
            "dm_pacing_notes": ["长篇模式下每轮保留 10 分钟自由讨论。"],
        },
        "ending": {
            "final_vote_questions": ["谁是真凶？", "真实作案时间是什么？", "关键物证是什么？"],
            "solution_reveal_order": ["时间线", "怀表", "钥匙", "动机"],
            "possible_endings": ["真相公开", "情感和解", "秘密继续沉没"],
        },
        "safety_review": {
            "rating": "15+",
            "sensitive_elements": ["虚构死亡事件", "旧案创伤"],
            "mitigations": ["不描写血腥细节", "不提供现实犯罪教程"],
            "forbidden_content_check": ["无未成年人性内容", "无仇恨歧视", "无真实隐私"],
        },
    }


def sample_review() -> dict[str, Any]:
    return {
        "pass": True,
        "scores": {
            "fair_play": 8,
            "clue_density": 8,
            "character_balance": 8,
            "dm_playability": 8,
            "safety": 9,
            "originality": 7,
        },
        "issues": [],
        "mandatory_fixes": [],
        "optional_enhancements": ["正式生成时可增加更细腻的个人本情感线。"],
        "review_summary": "dry-run 示例通过基础结构验证。",
    }


def sample_package(bible: dict[str, Any], length_profile: str = "standard") -> dict[str, Any]:
    profile = get_profile(length_profile)
    title = bible["metadata"]["title"]
    section_min = profile["section_min_chars"]
    public_intro = pad_to_length(
        f"# {title}\n\n欢迎来到 dry-run 示例。这里会保存公开导入、角色公开表和游玩须知。\n\n",
        section_min["public_intro"],
    )
    dm_manual = pad_to_length(
        "# DM 手册\n\n按轮次发放线索。不要提前透露 truth 字段中的凶手、手法和关键时间线。\n\n",
        section_min["dm_manual"],
    )
    truth = pad_to_length(
        "# 真相复盘\n\n关键推理链：C01-C12 共同指向停电十分钟、裂纹怀表与钥匙机会。\n\n",
        section_min["truth_and_solution"],
    )
    clue_cards = "# 线索卡\n\n" + "\n\n".join(
        f"## {clue['id']} {clue['title']}\n\n轮次：{clue['round']}\n\n{clue['text']}" for clue in bible["clues"]
    )
    return {
        "public_intro": public_intro,
        "dm_manual": dm_manual,
        "truth_and_solution": truth,
        "clue_cards": pad_to_length(clue_cards, section_min["clue_cards"]),
        "production_notes": pad_to_length("# 制作说明\n\n准备怀表、旧信封、灯塔照片说明和三段背景音乐。\n\n", section_min["production_notes"]),
        "safety_and_compliance": pad_to_length("# 内容安全\n\n本故事为虚构推理娱乐，建议 15+，避免沉浸式演绎中过度惊吓。\n\n", section_min["safety_and_compliance"]),
        "handouts": [
            {
                "filename": f"handout_{index + 1:02d}_lighthouse_note.md",
                "title": f"旧灯塔便签 {index + 1}",
                "content": pad_to_length("# 旧灯塔便签\n\n停电不是第一次发生，但这一次有人提前知道。\n\n", profile["handout_min_chars"]),
            }
            for index in range(int(profile.get("handout_count", 2)))
        ],
    }


def sample_player_docs(
    bible: dict[str, Any],
    length_profile: str = "standard",
    player_depth: str = "normal",
) -> list[dict[str, Any]]:
    profile = get_profile(length_profile)
    target_chars = profile["player_min_chars"]
    if player_depth != "normal":
        target_chars = player_depth_target_chars(length_profile, player_depth)
    docs = []
    for player in bible["cast"]:
        if player_depth == "normal":
            content = (
                f"# {player['name']}\n\n"
                f"公开身份：{player['public_identity']}\n\n"
                f"私人秘密：{player['private_secret']}\n\n"
                "你来到旧灯塔并不是偶然。受害者顾闻潮曾握有一份与你有关的旧档案，"
                "你希望在真相公开前确认档案内容，同时避免自己的隐瞒被其他人误解成杀人动机。\n\n"
                "## 可公开的信息\n\n"
                "你可以承认自己与受害者有过争执，也可以透露你见过裂纹怀表，"
                "但暂时不要主动说明停电十分钟内你真正去过哪里。\n\n"
                "## 三轮行动建议\n\n"
                "第一轮建立关系并观察谁在回避时间线；第二轮交换线索，重点追问钥匙和停电；"
                "第三轮给出自己的推理，说明你为什么不具备完整作案条件。\n\n"
            )
        else:
            content = f"# {player['name']}\n\n"
            for section in PLAYER_BOOK_SECTIONS:
                content += f"## {section['title']}\n\n"
                content += (
                    "这是 dry-run 的章节式玩家本占位内容，用于验证商业长本式个人故事体量。"
                    "正式运行时，本章会由大模型写成具体场景、人物关系、个人记忆、可盘问信息和情绪线。"
                    "每个章节都会保持角色信息边界，避免非凶手提前知道完整真相。\n\n"
                )
        docs.append(
            {
                "role_id": player["id"],
                "role_name": player["name"],
                "filename": f"{player['id']}_{player['name']}.md",
                "content": pad_to_length(content, target_chars),
            }
        )
    return docs


def pad_to_length(text: str, min_chars: int) -> str:
    if len(text) >= min_chars:
        return text
    filler = (
        "这是 dry-run 的占位扩写段落，用于验证长篇输出结构、文件长度检查和保存规范。"
        "正式运行时，这部分会由大模型写成角色记忆、线索文本、主持话术或复盘推理链。"
        "占位内容不会作为最终剧本文学质量示例，只用于本地自动化测试。\n\n"
    )
    while len(text) < min_chars:
        text += filler
    return text
