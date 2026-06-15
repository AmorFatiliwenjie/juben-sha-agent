from __future__ import annotations

from typing import Any


STYLE_PROFILES: dict[str, dict[str, Any]] = {
    "none": {
        "label": "无指定风格",
        "note": "按 brief 自然生成，不额外套用类型气质。",
    },
    "snowbound-horror": {
        "label": "雪地封闭微恐",
        "note": (
            "原创方向参考：偏雪乡式封闭空间、严寒压迫、熟人社会秘密、民俗传闻与现实罪恶互相遮蔽。"
            "重点是风雪孤岛、村镇关系网、微恐氛围、旧案还原；不要复制任何现成作品的人名、案件、反转或桥段。"
        ),
    },
    "obsessive-love": {
        "label": "偏执依恋心理悬疑",
        "note": (
            "原创方向参考：偏病娇式执念、占有、错认、记忆偏差和危险亲密关系。"
            "重点是心理悬疑、扭曲情感、 unreliable memory、互相拯救或互相毁灭；避免美化现实伤害和精神疾病污名化。"
        ),
    },
    "stray-dog-noir": {
        "label": "边缘人黑暗情感",
        "note": (
            "原创方向参考：偏野狗式边缘人命运、底层困境、全员带伤、互相背叛又互相取暖。"
            "重点是黑暗现实、强情绪冲突、群像命运、脏乱但有生命力的场景；不要写真实犯罪教程。"
        ),
    },
    "dark-cn-emotion": {
        "label": "国产黑暗情感长本",
        "note": (
            "原创组合方向：雪地/封闭空间的压迫感，偏执依恋的心理悬疑，边缘人群像的黑暗情感。"
            "适合写成高强度情感长本：每个角色都有烂在心里的秘密、可恨处和可怜处，"
            "关系要互相撕扯，真相要能反复改写玩家对角色的判断。必须原创，不复刻《雪乡》《病娇》《野狗》等现成剧本。"
        ),
    },
}


def available_style_profiles() -> list[str]:
    return list(STYLE_PROFILES.keys())


def get_style_profile(name: str) -> dict[str, Any]:
    return STYLE_PROFILES.get(name, STYLE_PROFILES["none"])


def style_profile_note(name: str) -> str:
    profile = get_style_profile(name)
    return f"当前风格预设：{profile['label']}（{name}）。{profile['note']}"
