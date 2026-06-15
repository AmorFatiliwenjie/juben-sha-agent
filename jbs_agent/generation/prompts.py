from __future__ import annotations

import json
from typing import Any

from ..reference.knowledge import RESEARCH_CONSTRAINTS
from .length_profiles import get_profile, profile_brief_note
from .style_profiles import style_profile_note


SYSTEM_PROMPT = """你是一个专业剧本杀创作工作室的总编剧、推理公平性审稿人和主持人手册编辑。
你的目标不是写散文，而是产出可被 DM 主持、可被玩家游玩、可复盘的剧本杀项目文件。
所有输出必须原创，不套用现成影视/小说/游戏 IP，不照搬真实案件细节。
除非用户 brief 另有要求，默认使用中文创作。"""


def brief_block(brief: dict[str, Any]) -> str:
    return json.dumps(brief, ensure_ascii=False, indent=2)


def build_auto_brief_prompt(
    seed: str = "",
    length_profile: str = "standard",
    style_profile: str = "none",
) -> str:
    seed = seed.strip() or "无。请你自主选择一个适合朋友聚会、可主持、可复盘的原创剧本杀方向。"
    profile = get_profile(length_profile)
    return f"""
请先自动生成一份“剧本杀创作 brief”，供后续 agent 继续创作完整剧本杀项目。

用户给出的种子想法：
{seed}

长度目标：
{profile_brief_note(length_profile)}

风格目标：
{style_profile_note(style_profile)}

必须遵守的资料化约束：
{RESEARCH_CONSTRAINTS}

只输出合法 JSON 对象，不要 Markdown，不要解释。JSON 结构必须包含：
{{
  "title": "",
  "players": 6,
  "duration_minutes": 180,
  "genre": "",
  "difficulty": "easy|medium|hard",
  "setting": "",
  "era": "",
  "tone": "",
  "target_audience": "",
  "must_have": [],
  "avoid": [],
  "content_rating": "",
  "output_language": "zh-CN",
  "custom_notes": ""
}}

要求：
- title 必须原创，不套用现成影视、小说、游戏或真实案件名称。
- players 默认 6；如果种子想法强烈指向其他规模，可在 4-8 之间选择。
- duration_minutes 必须匹配长度模式；{profile["label"]}模式建议不要低于 {profile["rounds"] * 55} 分钟。
- genre 要明确，如“本格推理 / 情感沉浸 / 欢乐机制 / 阵营博弈”的组合。
- must_have 至少 6 条，包含公平推理、线索矩阵、玩家信息边界、DM 新手可主持。
- avoid 至少 8 条，包含真实案件改编、露骨血腥、未成年人性内容、现实犯罪教程、仇恨歧视、真实隐私、抄袭现成 IP、超自然万能解释。
- custom_notes 要写清楚本次创作最应该追求的体验。
- 如果指定了风格预设，要把它转化为原创题材、人物关系和情绪强度；不得复刻现成剧本的人名、案件、反转或具体桥段。
"""


def build_bible_prompt(
    brief: dict[str, Any],
    length_profile: str = "standard",
    style_profile: str = "none",
) -> str:
    profile = get_profile(length_profile)
    max_clues = int(brief.get("players") or 6) * int(profile["clues_per_player"]) + 4
    return f"""
请根据用户 brief 创作一份“剧本杀真相圣经 story bible”。
注意：这一步只写结构蓝图，不写长篇正文。长篇玩家本、DM 手册、线索卡正文会在后续步骤单独扩写。

用户 brief：
{brief_block(brief)}

长度目标：
{profile_brief_note(length_profile)}

风格目标：
{style_profile_note(style_profile)}

必须遵守的资料化约束：
{RESEARCH_CONSTRAINTS}

只输出合法 JSON 对象，不要 Markdown，不要解释。JSON 结构必须包含：
{{
  "metadata": {{
    "title": "",
    "subtitle": "",
    "players": 0,
    "duration_minutes": 0,
    "genre": "",
    "difficulty": "",
    "content_rating": "",
    "one_sentence_pitch": ""
  }},
  "quality_targets": [],
  "world": {{
    "setting": "",
    "era": "",
    "tone": "",
    "core_question": "",
    "themes": []
  }},
  "cast": [
    {{
      "id": "P01",
      "name": "",
      "public_identity": "",
      "private_secret": "",
      "personal_goal": "",
      "motive": "",
      "alibi": "",
      "key_relationships": [],
      "knows_before_game": [],
      "can_reveal": []
    }}
  ],
  "truth": {{
    "victim": "",
    "culprit": "P01",
    "method": "",
    "core_trick": "",
    "motive_truth": "",
    "timeline": [
      {{"time": "", "event": "", "visible_to": "", "truth_note": ""}}
    ],
    "why_only_culprit": "",
    "innocent_clearance": []
  }},
  "game_flow": [
    {{
      "round": 1,
      "title": "",
      "duration_minutes": 0,
      "dm_goal": "",
      "public_event": "",
      "player_tasks": [],
      "release_clues": ["C01"]
    }}
  ],
  "clues": [
    {{
      "id": "C01",
      "title": "",
      "type": "",
      "round": 1,
      "visibility": "",
      "holder": "",
      "text": "",
      "truth_value": "true|partial|false",
      "points_to": [],
      "misleads_to": [],
      "reveals": "",
      "fairness_note": ""
    }}
  ],
  "red_herrings": [],
  "expanded_design": {{
    "act_structure": [],
    "relationship_web": [],
    "character_arcs": [],
    "mechanics": [],
    "dm_pacing_notes": []
  }},
  "ending": {{
    "final_vote_questions": [],
    "solution_reveal_order": [],
    "possible_endings": []
  }},
  "safety_review": {{
    "rating": "",
    "sensitive_elements": [],
    "mitigations": [],
    "forbidden_content_check": []
  }}
}}

额外要求：
- cast 数量必须等于 brief.players。
- game_flow 至少 {profile["rounds"]} 轮，每轮都要有明确目标、公共事件和玩家任务。
- clues 数量建议为玩家数的 {profile["clues_per_player"]} 倍，最多不要超过 {max_clues} 条，且每轮都有线索。
- culprit 必须只填写 cast 中的纯角色 id，例如 "P05"；不要写姓名、身份、括号或解释。
- 所有关键真相都必须能被 clues 与 timeline 共同推出。
- expanded_design 必须写清角色弧光、关系网、节奏控制和机制设计，供后续扩写长篇正文使用。
- 所有字符串都要短：普通字段不超过 80 个中文字符；clue.text 不超过 70 个中文字符；timeline.event 不超过 60 个中文字符。
- 数组元素使用短句，不要写长段落，不要写 Markdown，不要写完整正文。
- 不要在 story_bible 中展开玩家本、DM 话术、长篇世界观、完整线索卡正文或复盘长文。
- 如果指定了风格预设，只学习类型气质，不要借用现成剧本的角色名、案件核心、关键反转或标志性桥段。
"""


def build_review_prompt(brief: dict[str, Any], bible: dict[str, Any]) -> str:
    return f"""
你是剧本杀推理公平性和可主持性审稿人。请审查下面 story bible。

用户 brief：
{brief_block(brief)}

story bible：
{json.dumps(bible, ensure_ascii=False, indent=2)}

只输出合法 JSON 对象，不要 Markdown。结构：
{{
  "pass": true,
  "scores": {{
    "fair_play": 0,
    "clue_density": 0,
    "character_balance": 0,
    "dm_playability": 0,
    "safety": 0,
    "originality": 0
  }},
  "issues": [
    {{"severity": "high|medium|low", "area": "", "problem": "", "fix": ""}}
  ],
  "mandatory_fixes": [],
  "optional_enhancements": [],
  "review_summary": ""
}}

评分 0-10。只要存在以下任一问题，pass 必须为 false：
- 真凶、手法、动机无法由已发线索推出。
- 存在最终才出现的决定性线索。
- 玩家角色明显不平衡，某角色无目标或无可盘问信息。
- 玩家本必然泄露非本角色不该知道的真相。
- 存在明显违法违规、隐私、未成年人或过度露骨内容风险。
"""


def build_revision_prompt(brief: dict[str, Any], bible: dict[str, Any], review: dict[str, Any]) -> str:
    return f"""
请根据审稿意见修订 story bible。保持原主题和核心卖点，但必须修复 mandatory_fixes。

用户 brief：
{brief_block(brief)}

原 story bible：
{json.dumps(bible, ensure_ascii=False, indent=2)}

审稿意见：
{json.dumps(review, ensure_ascii=False, indent=2)}

只输出修订后的合法 JSON 对象，结构必须与 story bible 一致。
"""


def build_package_prompt(
    brief: dict[str, Any],
    bible: dict[str, Any],
    review: dict[str, Any],
    length_profile: str = "standard",
) -> str:
    return f"""
请把 story bible 扩写成可保存的剧本杀公共资料包。玩家个人本稍后单独生成，因此这里不要写玩家个人本。

用户 brief：
{brief_block(brief)}

story bible：
{json.dumps(bible, ensure_ascii=False, indent=2)}

审稿意见：
{json.dumps(review, ensure_ascii=False, indent=2)}

长度目标：
{profile_brief_note(length_profile)}

只输出合法 JSON 对象，不要 Markdown 代码围栏。结构：
{{
  "public_intro": "Markdown，给所有玩家阅读的开场、世界观、角色公开表、游玩须知。",
  "dm_manual": "Markdown，主持人流程、每轮话术、发线索顺序、节奏控制、答疑边界。",
  "truth_and_solution": "Markdown，完整真相、时间线、线索如何推理、每个无辜者如何排除。",
  "clue_cards": "Markdown，按轮次列出全部线索卡，可直接打印或复制。",
  "production_notes": "Markdown，道具清单、场地建议、音乐灯光建议、时长控制。",
  "safety_and_compliance": "Markdown，适龄、触发提醒、内容安全检查、AI 生成声明建议。",
  "handouts": [
    {{"filename": "handout_01.md", "title": "", "content": "Markdown，可打印的报纸/信件/聊天记录/照片说明等"}}
  ]
}}

要求：
- DM 手册必须包含“不可提前透露的信息边界”。
- truth_and_solution 必须逐条引用 clue id 说明推理链。
- clue_cards 中每张线索卡必须包含 id、标题、轮次、公开/私有、正文。
- handouts 文件名只能使用英文字母、数字、下划线和连字符。
"""


PACKAGE_SECTION_INSTRUCTIONS = {
    "public_intro": {
        "title": "公开导入",
        "focus": "给所有玩家阅读的开场文件，包含故事氛围、世界观、公开事件、公开角色表、基础规则、开场前可公开的信息和玩家入戏提示。",
    },
    "dm_manual": {
        "title": "DM 手册",
        "focus": "给主持人的完整执行手册，包含准备、开场话术、逐轮流程、每轮发线索顺序、节奏控制、玩家卡住时的提示、答疑边界和不可提前透露的信息。",
    },
    "truth_and_solution": {
        "title": "真相复盘",
        "focus": "仅 DM 可见的完整真相，包含真实时间线、凶手动机、作案手法、核心诡计、每条关键线索如何推出答案、红鲱鱼如何排除、无辜者排除理由和最终复盘话术。",
    },
    "clue_cards": {
        "title": "线索卡",
        "focus": "可打印线索卡合集。按轮次整理，每张线索卡必须包含 id、标题、轮次、公开/私有、持有人、正文、可追问方向。玩家可见文本不要泄露 DM 注释。",
    },
    "production_notes": {
        "title": "制作说明",
        "focus": "制作与落地说明，包含道具清单、打印建议、场地布置、音乐灯光、时长控制、难度调节、玩家人数微调和 DM 备忘。",
    },
    "safety_and_compliance": {
        "title": "安全合规",
        "focus": "内容安全与发布前复核，包含适龄、触发提醒、禁忌内容检查、隐私与版权原创性检查、AI 生成声明建议、线下游玩安全提示。",
    },
}


def build_package_section_text_prompt(
    brief: dict[str, Any],
    bible: dict[str, Any],
    review: dict[str, Any],
    section_key: str,
    length_profile: str = "long",
    style_profile: str = "none",
) -> str:
    profile = get_profile(length_profile)
    spec = PACKAGE_SECTION_INSTRUCTIONS[section_key]
    min_chars = profile["section_min_chars"][section_key]
    return f"""
请根据 story bible 单独扩写《{spec["title"]}》文件。

用户 brief：
{brief_block(brief)}

story bible：
{json.dumps(bible, ensure_ascii=False, indent=2)}

审稿意见：
{json.dumps(review, ensure_ascii=False, indent=2)}

长度目标：
{profile_brief_note(length_profile)}

风格目标：
{style_profile_note(style_profile)}

本文件重点：
{spec["focus"]}

输出要求：
- 只输出 Markdown 正文，不要 JSON，不要代码围栏，不要解释生成过程。
- 至少约 {min_chars} 个中文字符；内容要完整、可直接保存为独立文件。
- 使用清晰的一级/二级标题，必要时使用表格。
- 必须保持 story bible 中的真相、线索 id、轮次和角色信息一致。
- 不要抄袭现成 IP，不要写真实案件细节，不要加入现实违法操作教程。
"""


def build_handout_index_prompt(
    brief: dict[str, Any],
    bible: dict[str, Any],
    length_profile: str = "long",
) -> str:
    profile = get_profile(length_profile)
    return f"""
请为这个剧本杀设计可打印 handouts/道具文本清单。

用户 brief：
{brief_block(brief)}

story bible：
{json.dumps(bible, ensure_ascii=False, indent=2)}

长度目标：
{profile_brief_note(length_profile)}

只输出合法 JSON 对象，不要 Markdown。结构：
{{
  "handouts": [
    {{
      "filename": "handout_01_example.md",
      "title": "",
      "round": 1,
      "purpose": "",
      "visible_to": "",
      "source_clues": ["C01"]
    }}
  ]
}}

要求：
- handouts 数量至少 {profile["handout_count"]} 份。
- filename 只能使用英文字母、数字、下划线和连字符，必须以 .md 结尾。
- 每份 handout 要服务于线索、氛围或角色关系，不要只是装饰。
"""


def build_handout_text_prompt(
    brief: dict[str, Any],
    bible: dict[str, Any],
    handout: dict[str, Any],
    length_profile: str = "long",
) -> str:
    profile = get_profile(length_profile)
    return f"""
请根据下面的 handout 设计，写出可直接打印或分发的 Markdown 道具文本。

用户 brief：
{brief_block(brief)}

story bible：
{json.dumps(bible, ensure_ascii=False, indent=2)}

handout 设计：
{json.dumps(handout, ensure_ascii=False, indent=2)}

输出要求：
- 只输出 Markdown 正文，不要 JSON，不要代码围栏。
- 至少约 {profile["handout_min_chars"]} 个中文字符。
- 文本要像真实道具：例如信件、报纸、聊天记录、档案摘录、账本、便签、录音转写等。
- 玩家可见文本不要直接泄露最终真相；必须与 handout 的轮次和可见范围匹配。
"""


def build_player_prompt(
    brief: dict[str, Any],
    bible: dict[str, Any],
    player: dict[str, Any],
    length_profile: str = "standard",
) -> str:
    return f"""
请为指定角色生成玩家个人本。你能看到完整 story bible，但必须严格遵守角色信息边界。

用户 brief：
{brief_block(brief)}

完整 story bible：
{json.dumps(bible, ensure_ascii=False, indent=2)}

要生成的角色：
{json.dumps(player, ensure_ascii=False, indent=2)}

长度目标：
{profile_brief_note(length_profile)}

只输出合法 JSON 对象，不要 Markdown 代码围栏。结构：
{{
  "role_id": "{player.get("id", "")}",
  "role_name": "{player.get("name", "")}",
  "filename": "Pxx_role_name.md",
  "content": "Markdown 玩家本正文"
}}

玩家本正文必须包含：
- 封面信息：角色名、公开身份、建议演绎风格。
- 公开背景：所有人可知道的关系和事件。
- 私人记忆：只限该角色亲历或合理知道的信息。
- 个人目标：主目标、隐藏目标、可选情感目标。
- 三轮行动建议：每轮可主动询问谁、可抛出什么信息、应隐瞒什么。
- 可公开线索与私密线索。
- 结局独白：不泄露非本角色不该知道的完整真相。

禁止：
- 非凶手角色不得知道“谁是真凶/完整作案手法”。
- 不要把 truth_and_solution 复盘直接塞进玩家本。
- 不要出现真实个人隐私或现实违法操作教程。
"""


def build_player_text_prompt(
    brief: dict[str, Any],
    bible: dict[str, Any],
    player: dict[str, Any],
    length_profile: str = "long",
) -> str:
    profile = get_profile(length_profile)
    return f"""
请为指定角色生成一份长篇玩家个人本。你能看到创作参考 bible，但必须严格遵守角色信息边界。

用户 brief：
{brief_block(brief)}

创作参考 bible：
{json.dumps(bible, ensure_ascii=False, indent=2)}

要生成的角色：
{json.dumps(player, ensure_ascii=False, indent=2)}

长度目标：
{profile_brief_note(length_profile)}

输出要求：
- 只输出 Markdown 正文，不要 JSON，不要代码围栏，不要解释生成过程。
- 至少约 {profile["player_min_chars"]} 个中文字符。
- 必须可直接作为该角色的个人本分发。
- 非凶手角色不得知道“谁是真凶/完整作案手法”；凶手角色可以知道自己的行为，但也要保留可演绎的自保目标。
- 不要把 DM 复盘、全部线索答案或其他角色内心直接塞进玩家本。

玩家本必须包含这些章节：
1. 封面信息：角色名、公开身份、年龄/职业可虚构、建议演绎风格。
2. 公开背景：所有人可知道的关系和事件。
3. 私人过往：该角色亲历的过去，用多个场景写出情绪和细节。
4. 关键关系：逐一写与其他玩家角色的关系、可说信息、应隐瞒信息。
5. 案发前后记忆：按时间线写该角色看到、听到、做过的事。
6. 个人目标：主目标、隐藏目标、情感目标、底线。
7. 分轮行动建议：至少 {profile["rounds"]} 轮，每轮写可主动询问谁、可公开什么、应回避什么。
8. 线索处理：该角色持有或会接触的线索、可如何解读、可能误判什么。
9. 盘问话术：给出可直接使用的提问和回应。
10. 结局独白：只基于本角色视角，不泄露非本角色不该知道的完整真相。
"""


PLAYER_BOOK_SECTIONS = [
    {
        "key": "cover_public",
        "title": "封面与公开身份",
        "focus": "角色封面、公开身份、外在气质、玩家演绎提示、所有人可知道的公开关系。写得可直接放在玩家本开头。",
        "weight": 0.08,
    },
    {
        "key": "private_past",
        "title": "私人过往与性格底色",
        "focus": "用多个具体场景写角色成长经历、创伤或执念、与受害者/核心事件的过往联系。要像故事，不要像履历表。",
        "weight": 0.22,
    },
    {
        "key": "relationship_web",
        "title": "关系网与秘密",
        "focus": "逐一写与其他玩家角色的关系：表面关系、真实情绪、欠债/恩怨/误会、可公开的信息、必须隐瞒的信息。",
        "weight": 0.18,
    },
    {
        "key": "case_memory",
        "title": "案发前后的记忆",
        "focus": "按时间线写案发前、案发时、案发后的个人经历。必须只写该角色能知道的内容，加入感官细节和心理活动。",
        "weight": 0.18,
    },
    {
        "key": "goals_actions",
        "title": "个人目标与分轮行动",
        "focus": "写主目标、隐藏目标、情感目标、底线、每轮具体行动建议、可问谁、可撒什么烟雾、应回避什么。",
        "weight": 0.14,
    },
    {
        "key": "clues_dialogue",
        "title": "线索解读与盘问话术",
        "focus": "写该角色会接触的线索、可能的误判、可向他人提出的问题、被质疑时的回应话术、可主动抛出的信息。",
        "weight": 0.13,
    },
    {
        "key": "ending_monologue",
        "title": "结局独白与情感落点",
        "focus": "写投票前自白、真相后反应和结局独白。只能基于本角色视角，不泄露非本角色不该知道的完整真相。",
        "weight": 0.07,
    },
]


PLAYER_DEPTH_MULTIPLIERS = {
    "normal": 1.0,
    "deep": 1.0,
    "novel": 1.8,
}


def available_player_depths() -> list[str]:
    return list(PLAYER_DEPTH_MULTIPLIERS.keys())


def player_depth_target_chars(length_profile: str, player_depth: str) -> int:
    profile = get_profile(length_profile)
    if player_depth == "normal":
        return int(profile["player_min_chars"])
    base = int(profile.get("player_deep_min_chars", profile["player_min_chars"]))
    return int(base * PLAYER_DEPTH_MULTIPLIERS.get(player_depth, 1.0))


def build_player_outline_prompt(
    brief: dict[str, Any],
    bible: dict[str, Any],
    player: dict[str, Any],
    length_profile: str = "long",
    player_depth: str = "deep",
    style_profile: str = "none",
) -> str:
    target_chars = player_depth_target_chars(length_profile, player_depth)
    section_titles = [section["title"] for section in PLAYER_BOOK_SECTIONS]
    return f"""
请为指定角色生成“玩家个人本章节大纲”。这是后续逐章扩写的蓝图，不是正文。

用户 brief：
{brief_block(brief)}

创作参考 bible：
{json.dumps(bible, ensure_ascii=False, indent=2)}

要生成的角色：
{json.dumps(player, ensure_ascii=False, indent=2)}

目标：
- 玩家本总长度约 {target_chars} 个中文字符。
- 章节包括：{json.dumps(section_titles, ensure_ascii=False)}
- 只写该角色能知道或合理相信的信息，严格控制信息边界。
- 风格目标：{style_profile_note(style_profile)}

只输出合法 JSON 对象，不要 Markdown。结构：
{{
  "role_id": "{player.get("id", "")}",
  "role_name": "{player.get("name", "")}",
  "tone": "",
  "spoiler_boundary": "",
  "chapter_plan": [
    {{
      "key": "cover_public",
      "title": "封面与公开身份",
      "must_include": [],
      "must_hide": [],
      "emotional_goal": "",
      "scene_seeds": []
    }}
  ],
  "continuity_notes": []
}}

要求：
- chapter_plan 必须包含上述全部章节 key，顺序一致。
- scene_seeds 要给可扩写成故事的具体场景，不要空泛概括。
- 非凶手角色不得知道谁是真凶或完整作案手法。
- 凶手角色可以知道自己的行为，但不得知道其他角色不该透露的全部内心。
"""


def build_player_section_prompt(
    brief: dict[str, Any],
    bible: dict[str, Any],
    player: dict[str, Any],
    outline: dict[str, Any],
    section: dict[str, Any],
    previous_sections: list[str],
    length_profile: str = "long",
    player_depth: str = "deep",
    style_profile: str = "none",
) -> str:
    total_target = player_depth_target_chars(length_profile, player_depth)
    section_target = max(600, int(total_target * float(section["weight"])))
    previous_digest = "\n\n".join(previous_sections[-2:])
    return f"""
请逐章扩写玩家个人本的《{section["title"]}》章节。

用户 brief：
{brief_block(brief)}

创作参考 bible：
{json.dumps(bible, ensure_ascii=False, indent=2)}

要生成的角色：
{json.dumps(player, ensure_ascii=False, indent=2)}

章节大纲：
{json.dumps(outline, ensure_ascii=False, indent=2)}

本章重点：
{section["focus"]}

风格目标：
{style_profile_note(style_profile)}

上一两章摘要/正文片段，用于保持连续：
{previous_digest or "无，本章是开头。"}

输出要求：
- 只输出 Markdown 正文，不要 JSON，不要代码围栏。
- 本章至少约 {section_target} 个中文字符。
- 必须写成“可读的角色故事 + 可执行的玩家信息”，不要只列设定表。
- 多写具体场景、动作、对话片段、心理活动和可盘问细节。
- 允许写长段落，但每一段都要服务于玩家可演绎、可盘问、可隐瞒的信息。
- 严格保持该角色信息边界；非凶手不得知道真凶和完整手法。
- 不要泄露 DM 复盘，不要写现实违法操作教程，不要抄袭现成 IP。
"""


def assemble_player_book(role_name: str, sections: list[tuple[str, str]]) -> str:
    parts = [f"# {role_name}\n"]
    for title, content in sections:
        cleaned = content.strip()
        if not cleaned.startswith("#"):
            parts.append(f"\n## {title}\n\n{cleaned}\n")
        else:
            parts.append(f"\n{cleaned}\n")
    return "\n".join(parts).strip() + "\n"
