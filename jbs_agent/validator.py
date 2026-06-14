from __future__ import annotations

import json
import re
from typing import Any

from .length_profiles import get_profile, is_expanded_profile
from .prompts import player_depth_target_chars


def validate_all(
    brief: dict[str, Any],
    bible: dict[str, Any],
    review: dict[str, Any],
    package: dict[str, Any],
    player_docs: list[dict[str, Any]],
    *,
    length_profile: str = "standard",
    player_depth: str = "normal",
) -> list[str]:
    warnings: list[str] = []
    warnings.extend(validate_bible(brief, bible, length_profile))
    warnings.extend(validate_review(review))
    warnings.extend(validate_package(package, length_profile))
    warnings.extend(validate_players(bible, player_docs, length_profile, player_depth))
    return warnings


def validate_bible(brief: dict[str, Any], bible: dict[str, Any], length_profile: str = "standard") -> list[str]:
    warnings: list[str] = []
    profile = get_profile(length_profile)
    metadata = bible.get("metadata", {})
    cast = bible.get("cast", [])
    clues = bible.get("clues", [])
    game_flow = bible.get("game_flow", [])
    expected_players = int(brief.get("players") or metadata.get("players") or 0)

    required_top = ["metadata", "world", "cast", "truth", "game_flow", "clues", "ending", "safety_review"]
    for key in required_top:
        if key not in bible:
            warnings.append(f"story_bible 缺少顶层字段: {key}")

    if expected_players and len(cast) != expected_players:
        warnings.append(f"角色数量 {len(cast)} 与 brief.players {expected_players} 不一致。")

    cast_ids = {str(item.get("id")).strip() for item in cast if item.get("id")}
    cast_names = {str(item.get("name")).strip() for item in cast if item.get("name")}
    culprit = str(bible.get("truth", {}).get("culprit", ""))
    normalized_culprit = normalize_role_ref(culprit, cast)
    if culprit and normalized_culprit not in cast_ids and normalized_culprit not in cast_names:
        warnings.append(f"truth.culprit={culprit} 没有匹配 cast 中的 id 或 name。")

    for player in cast:
        for key in ["id", "name", "public_identity", "private_secret", "personal_goal", "motive", "alibi"]:
            if not player.get(key):
                warnings.append(f"角色 {player.get('id', '?')} 缺少字段: {key}")

    clue_ids = [str(clue.get("id")) for clue in clues if clue.get("id")]
    if len(clue_ids) != len(set(clue_ids)):
        warnings.append("线索 id 存在重复。")
    expected_clues = expected_players * int(profile.get("clues_per_player", 3)) if expected_players else 0
    if expected_clues and len(clues) < expected_clues:
        warnings.append(f"线索数量 {len(clues)} 少于 {length_profile} 模式建议值 {expected_clues}。")
    if is_expanded_profile(length_profile) and len(game_flow) < int(profile.get("rounds", 3)):
        warnings.append(f"game_flow 轮次数量 {len(game_flow)} 少于 {length_profile} 模式建议值 {profile.get('rounds')}。")

    known_clues = set(clue_ids)
    for flow in game_flow:
        for clue_id in flow.get("release_clues", []):
            if str(clue_id) not in known_clues:
                warnings.append(f"game_flow 第 {flow.get('round')} 轮引用不存在的线索: {clue_id}")

    for clue in clues:
        for key in ["id", "title", "round", "visibility", "holder", "text", "truth_value", "fairness_note"]:
            if not clue.get(key):
                warnings.append(f"线索 {clue.get('id', '?')} 缺少字段: {key}")

    return warnings


def validate_review(review: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    if "pass" not in review:
        warnings.append("quality_review 缺少 pass 字段。")
    scores = review.get("scores")
    if not isinstance(scores, dict):
        warnings.append("quality_review 缺少 scores 对象。")
    return warnings


def validate_package(package: dict[str, Any], length_profile: str = "standard") -> list[str]:
    warnings: list[str] = []
    profile = get_profile(length_profile)
    required = [
        "public_intro",
        "dm_manual",
        "truth_and_solution",
        "clue_cards",
        "production_notes",
        "safety_and_compliance",
    ]
    for key in required:
        value = package.get(key)
        if not isinstance(value, str) or len(value.strip()) < 20:
            warnings.append(f"资料包字段 {key} 为空或过短。")
        elif is_expanded_profile(length_profile):
            min_chars = int(profile["section_min_chars"].get(key, 0) * 0.75)
            if len(value.strip()) < min_chars:
                warnings.append(f"{length_profile} 模式下 {key} 长度偏短：{len(value.strip())} 字符，建议至少 {min_chars}。")
    if not isinstance(package.get("handouts", []), list):
        warnings.append("handouts 必须是数组。")
    elif is_expanded_profile(length_profile):
        expected_handouts = int(profile.get("handout_count", 0))
        if len(package.get("handouts", [])) < expected_handouts:
            warnings.append(f"{length_profile} 模式下 handouts 数量偏少：{len(package.get('handouts', []))}，建议至少 {expected_handouts}。")
    return warnings


def validate_players(
    bible: dict[str, Any],
    player_docs: list[dict[str, Any]],
    length_profile: str = "standard",
    player_depth: str = "normal",
) -> list[str]:
    warnings: list[str] = []
    profile = get_profile(length_profile)
    cast = bible.get("cast", [])
    if len(player_docs) != len(cast):
        warnings.append(f"玩家本数量 {len(player_docs)} 与角色数量 {len(cast)} 不一致。")

    culprit_id = normalize_role_ref(str(bible.get("truth", {}).get("culprit", "")), cast)
    culprit_name = culprit_id
    for player in cast:
        if str(player.get("id")) == culprit_id:
            culprit_name = str(player.get("name") or culprit_id)

    sensitive_words = ["真凶", "凶手", "杀害", "作案", "完整手法"]
    for doc in player_docs:
        role_id = str(doc.get("role_id", ""))
        content = str(doc.get("content", ""))
        if role_id != culprit_id and culprit_name and culprit_name in content:
            if any(word in content for word in sensitive_words):
                warnings.append(f"玩家本 {role_id} 可能泄露真凶信息，请人工复核。")
        min_chars = 100
        if player_depth != "normal":
            min_chars = int(player_depth_target_chars(length_profile, player_depth) * 0.75)
        elif is_expanded_profile(length_profile):
            min_chars = int(profile.get("player_min_chars", 100) * 0.75)
        if len(content.strip()) < min_chars:
            warnings.append(f"玩家本 {role_id} 内容偏短：{len(content.strip())} 字符，建议至少 {min_chars}。")

    return warnings


def normalize_role_ref(value: str, cast: list[dict[str, Any]]) -> str:
    value = str(value or "").strip()
    if not value:
        return ""

    for player in cast:
        role_id = str(player.get("id") or "").strip()
        role_name = str(player.get("name") or "").strip()
        if role_id and value == role_id:
            return role_id
        if role_name and value == role_name:
            return role_name

    # Accept common model outputs such as "P05 (Name, Butler)" or "P05：Name".
    leading_id = re.match(r"^\s*([A-Za-z]\d{1,3})\b", value)
    if leading_id:
        candidate = leading_id.group(1)
        if any(str(player.get("id") or "").strip() == candidate for player in cast):
            return candidate

    for player in cast:
        role_id = str(player.get("id") or "").strip()
        role_name = str(player.get("name") or "").strip()
        if role_id and role_id in value:
            return role_id
        if role_name and role_name in value:
            return role_name

    return value


def make_quality_report(
    brief: dict[str, Any],
    bible: dict[str, Any],
    review: dict[str, Any],
    warnings: list[str],
) -> str:
    lines = [
        "# 质量与合规检查报告",
        "",
        "## Brief 摘要",
        "",
        f"- 标题：{brief.get('title') or bible.get('metadata', {}).get('title', '')}",
        f"- 玩家数：{brief.get('players') or bible.get('metadata', {}).get('players', '')}",
        f"- 时长：{brief.get('duration_minutes') or bible.get('metadata', {}).get('duration_minutes', '')} 分钟",
        f"- 输出长度模式：{brief.get('output_scale', 'standard')}",
        f"- 玩家本深度：{brief.get('player_depth', 'normal')}",
        "",
        "## 模型审稿结果",
        "",
        f"- 是否通过：{review.get('pass')}",
        f"- 摘要：{review.get('review_summary', '')}",
        "",
        "```json",
        json.dumps(review.get("scores", {}), ensure_ascii=False, indent=2),
        "```",
        "",
        "## 本地结构检查",
        "",
    ]
    if warnings:
        lines.extend(f"- WARNING: {item}" for item in warnings)
    else:
        lines.append("- 未发现结构性警告。")

    lines.extend(
        [
            "",
            "## 人工复核建议",
            "",
            "- 重点检查非凶手玩家本是否泄露最终真相。",
            "- 试玩一次 30 分钟快速盘，确认线索发放顺序和节奏。",
            "- 商用、线下门店或未成年人参与场景，请按所在地要求做内容自审和适龄提示。",
        ]
    )
    return "\n".join(lines) + "\n"
