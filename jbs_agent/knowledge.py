from __future__ import annotations


RESEARCH_CONSTRAINTS = """
剧本杀创作硬约束：
1. 结构必须可主持：公开导入、角色分发、分幕/分轮推进、线索发放、盘问讨论、投票/指认、真相复盘、彩蛋或多结局。
2. 公平推理：关键嫌疑人必须早出现；定罪线索必须在复盘前发给玩家；不可依赖未铺垫的巧合、神谕、超自然万能解释、临时新科技或最终才出现的秘密通道。
3. 线索矩阵：每条线索要标明轮次、持有人、真伪、指向、误导对象、能排除谁、与时间线/动机/手法的关系。
4. 玩家平衡：每个玩家都要有公开身份、私人秘密、个人目标、可被怀疑的动机、可盘问的行动线，以及至少一条主动推进剧情的线索。
5. 信息边界：玩家本只能包含该角色可知道的信息；凶手本可以写自保目标，但不能把所有复盘答案直接泄给非凶手玩家。
6. 复盘闭环：真相必须解释作案动机、手法、时间线、误导线索、无辜者排除理由、玩家如何凭已发线索推理到答案。
7. 内容安全：避免露骨色情、未成年人性内容、真实违法操作指南、自伤诱导、恐怖主义、仇恨歧视、过度血腥细节、现实个人隐私；必要时给出适龄和触发提醒。
8. 生成式 AI 使用：保留 brief、story bible、质量报告和 manifest，便于追溯；不要把用户真实隐私写入故事。
"""


SOURCE_NOTES = [
    {
        "title": "Murder mystery game",
        "url": "https://en.wikipedia.org/wiki/Murder_mystery_game",
        "use": "参考其关于角色本、线索、分轮、互动/桌面玩法和 6-20 人常见规模的概述。",
    },
    {
        "title": "Detection Club / Knox fair-play guidelines",
        "url": "https://en.wikipedia.org/wiki/Detection_Club",
        "use": "参考公平推理传统：读者/玩家应有机会通过已呈现线索推断真相。",
    },
    {
        "title": "The Challenge and Reward of Fair Play in Narrative",
        "url": "https://arxiv.org/abs/2507.13841",
        "use": "参考 LLM 生成侦探叙事时“惊奇性、连贯性、公平性”难以同时满足，因此加入批评修订流程。",
    },
    {
        "title": "Piecing Together Clues",
        "url": "https://arxiv.org/abs/2307.05113",
        "use": "参考先识别线索再推理的思路，因此要求模型产出线索矩阵和复盘闭环。",
    },
    {
        "title": "生成式人工智能服务管理暂行办法",
        "url": "https://www.cac.gov.cn/2023-07/13/c_1690898326795531.htm",
        "use": "参考生成内容治理中的安全、隐私、未成年人保护和违法内容处置原则。",
    },
]
