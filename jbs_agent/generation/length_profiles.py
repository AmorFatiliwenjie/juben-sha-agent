from __future__ import annotations

from typing import Any


LENGTH_PROFILES: dict[str, dict[str, Any]] = {
    "standard": {
        "label": "标准",
        "description": "适合快速生成和朋友小聚试玩。",
        "rounds": 3,
        "clues_per_player": 3,
        "handout_count": 2,
        "handout_min_chars": 300,
        "player_min_chars": 900,
        "player_deep_min_chars": 2400,
        "default_max_tokens": None,
        "default_timeout": 240,
        "section_min_chars": {
            "public_intro": 500,
            "dm_manual": 800,
            "truth_and_solution": 800,
            "clue_cards": 800,
            "production_notes": 400,
            "safety_and_compliance": 300,
        },
    },
    "long": {
        "label": "长篇",
        "description": "适合 4 小时左右、内容更丰满的聚会本。",
        "rounds": 4,
        "clues_per_player": 5,
        "handout_count": 5,
        "handout_min_chars": 600,
        "player_min_chars": 3000,
        "player_deep_min_chars": 10000,
        "default_max_tokens": 8000,
        "default_timeout": 600,
        "section_min_chars": {
            "public_intro": 1800,
            "dm_manual": 3600,
            "truth_and_solution": 3200,
            "clue_cards": 3200,
            "production_notes": 1400,
            "safety_and_compliance": 900,
        },
    },
    "epic": {
        "label": "超长篇",
        "description": "适合 5-6 小时、接近商用素材量的长本草案。",
        "rounds": 5,
        "clues_per_player": 7,
        "handout_count": 8,
        "handout_min_chars": 900,
        "player_min_chars": 5000,
        "player_deep_min_chars": 16000,
        "default_max_tokens": 12000,
        "default_timeout": 900,
        "section_min_chars": {
            "public_intro": 3000,
            "dm_manual": 5600,
            "truth_and_solution": 5000,
            "clue_cards": 5200,
            "production_notes": 2200,
            "safety_and_compliance": 1400,
        },
    },
}


def available_profiles() -> list[str]:
    return list(LENGTH_PROFILES.keys())


def get_profile(name: str) -> dict[str, Any]:
    return LENGTH_PROFILES.get(name, LENGTH_PROFILES["standard"])


def is_expanded_profile(name: str) -> bool:
    return name in {"long", "epic"}


def default_max_tokens(name: str) -> int | None:
    value = get_profile(name).get("default_max_tokens")
    return int(value) if value else None


def default_timeout(name: str) -> int:
    return int(get_profile(name).get("default_timeout", 240))


def profile_brief_note(name: str) -> str:
    profile = get_profile(name)
    section_targets = profile["section_min_chars"]
    return "\n".join(
        [
            f"当前长度模式：{profile['label']}（{name}）。{profile['description']}",
            f"- 建议轮次：至少 {profile['rounds']} 轮。",
            f"- 线索密度：至少每名玩家 {profile['clues_per_player']} 条线索。",
            f"- 玩家个人本：每人至少约 {profile['player_min_chars']} 个中文字符。",
            f"- 道具/handouts：至少 {profile['handout_count']} 份。",
            "- 公共文件最低长度参考："
            f"公开导入 {section_targets['public_intro']}，"
            f"DM 手册 {section_targets['dm_manual']}，"
            f"真相复盘 {section_targets['truth_and_solution']}，"
            f"线索卡 {section_targets['clue_cards']}，"
            f"制作说明 {section_targets['production_notes']}，"
            f"安全合规 {section_targets['safety_and_compliance']}。",
        ]
    )
