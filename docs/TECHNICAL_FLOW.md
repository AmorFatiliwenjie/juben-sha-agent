# 多 Agent 与分层记忆技术流图

本文档说明 LangGraph 生成引擎中，多 Agent 如何协作、Memory 如何分层，以及二者如何交互。

## 1. 总体架构

```mermaid
flowchart LR
    User[用户命令<br/>writing.py --engine langgraph] --> CLI[cli.py<br/>解析参数/读取 .env]
    CLI --> Config[RuntimeConfig<br/>API Key/Base URL/Model]
    CLI --> Brief{brief 来源}
    Brief -->|--brief| BriefFile[configs/*.json]
    Brief -->|--auto-brief| AutoBrief[模型生成 brief]

    Config --> LG[LangGraph Workflow]
    BriefFile --> LG
    AutoBrief --> LG

    LG --> Memory[(HierarchicalMemory<br/>SQLite + checkpoints)]
    LG --> Export[output.exporter<br/>标准项目导出]
    Export --> RunDir[outputs/时间戳_剧本名]
    RunDir --> Review[review/quality_report.md]
    RunDir --> MemReport[review/langgraph_memory_report.md]
    RunDir --> Submission[submission/ Word 投稿版]
```

## 2. 多 Agent 协作图

```mermaid
flowchart TD
    Start([Start]) --> StoryArchitect[StoryArchitect<br/>生成 story_bible]
    StoryArchitect --> FairnessEditor[FairnessEditor<br/>公平性/可主持性审稿]

    FairnessEditor --> Router{审稿是否通过?}
    Router -->|通过| PackageTeam[PackageTeam<br/>公共资料/DM手册/复盘/线索/道具]
    Router -->|不通过且修订小于2轮| RevisionRoom[RevisionRoom<br/>修订 story_bible]
    RevisionRoom --> FairnessEditor
    Router -->|仍未通过但达到上限| PackageTeam

    PackageTeam --> PlayerRoom[PlayerRoom<br/>逐角色生成玩家本]
    PlayerRoom --> PlayerDepth{player-depth}
    PlayerDepth -->|normal| SingleBook[单次生成个人本]
    PlayerDepth -->|deep/novel| Outline[生成章节大纲]
    Outline --> ChapterAgents[章节扩写 Agent x7]
    SingleBook --> ConsistencyAuditor[ConsistencyAuditor<br/>本地结构检查]
    ChapterAgents --> ConsistencyAuditor

    ConsistencyAuditor --> Exporter[Exporter<br/>保存文件/投稿版/记忆报告]
    Exporter --> End([END])
```

## 3. 分层 Memory 设计

```mermaid
flowchart TB
    subgraph Memory["HierarchicalMemory: outputs/.memory/<run_id>/memory.sqlite"]
        Canonical[(canonical<br/>权威事实层)]
        Working[(working<br/>过程决策层)]
        Retrieval[(retrieval_chunks<br/>长文本检索层)]
    end

    subgraph Files["outputs/.memory/<run_id>/"]
        Checkpoints[checkpoints/*.json<br/>节点状态摘要]
    end

    Canonical --> C1[brief]
    Canonical --> C2[story_bible]
    Canonical --> C3[cast/truth/clues]
    Canonical --> C4[quality_review]
    Canonical --> C5[package_index]

    Working --> W1[节点摘要]
    Working --> W2[审稿结论]
    Working --> W3[路由决策]
    Working --> W4[导出路径]

    Retrieval --> R1[package section chunks]
    Retrieval --> R2[handout chunks]
    Retrieval --> R3[player book chunks]
    Retrieval --> R4[player chapter chunks]

    Working --> Checkpoints
```

三层含义：

- `canonical`：只放权威事实，后续生成必须以它为准。
- `working`：记录节点做过什么、为什么返工、什么时候继续。
- `retrieval_chunks`：把长文本切块，后续按关键词检索回来，避免把所有正文塞进 prompt。

## 4. Agent 与 Memory 的交互

```mermaid
sequenceDiagram
    participant A as StoryArchitect
    participant F as FairnessEditor
    participant R as RevisionRoom
    participant P as PackageTeam
    participant U as PlayerRoom
    participant M as HierarchicalMemory
    participant E as Exporter

    A->>M: set_canonical(brief)
    A->>M: set_canonical(story_bible/cast/truth/clues)
    A->>M: add_working("created canonical story bible")
    A->>M: checkpoint("StoryArchitect")

    F->>M: set_canonical(quality_review)
    F->>M: add_working(review_summary)
    F->>M: checkpoint("FairnessEditor")

    alt 审稿不通过
        R->>M: set_canonical(revised story_bible)
        R->>M: add_working("revised story bible")
        R->>M: checkpoint("RevisionRoom")
        R-->>F: 回到审稿节点复审
    end

    P->>M: retrieve(section + truth)
    M-->>P: 相关 package/handout/player 片段
    P->>M: add_document(package sections)
    P->>M: add_document(handouts)
    P->>M: checkpoint("PackageTeam")

    U->>M: retrieve(role_id + role_name + secret + motive)
    M-->>U: 相关长文片段
    U->>M: add_document(player book/chapter)
    U->>M: checkpoint("PlayerRoom")

    E->>M: export_report(review/langgraph_memory_report.md)
```

## 5. 长篇生成时的上下文控制

```mermaid
flowchart LR
    Bible[短而结构化的 story_bible] --> Prompt[当前节点 Prompt]
    CurrentTask[当前任务<br/>section/role/chapter] --> Prompt
    MemoryQuery[关键词检索<br/>truth/role/section] --> Retrieval[(retrieval_chunks)]
    Retrieval --> Context[少量相关片段]
    Context --> Prompt
    Prompt --> LLM[大模型调用]
    LLM --> Output[Markdown/JSON 输出]
    Output --> Store[写入 retrieval memory]
    Output --> Files[保存到 outputs/]
```

这个设计的关键是：`story_bible` 负责全局一致性，`retrieval memory` 负责长文本连续性。每次调用只带“当前任务需要的上下文”，而不是把所有已生成内容全部塞回模型。

## 6. 当前实现中的 Agent/Memory 对应关系

| 节点 | 主要代码 | Memory 读 | Memory 写 |
| --- | --- | --- | --- |
| StoryArchitect | `node_story_architect` | 无 | `brief`, `story_bible`, `cast`, `truth`, `clues`, checkpoint |
| FairnessEditor | `node_fairness_editor` | `bible` state | `quality_review`, checkpoint |
| RevisionRoom | `node_revision_room` | `review`, `bible` state | revised `story_bible`, checkpoint |
| Router | `route_after_review` | `review`, `revision_count` | 路由决策 working memory |
| PackageTeam | `node_package_team` | `retrieve_context()` | package sections, handouts, checkpoint |
| PlayerRoom | `node_player_room` | `retrieve_context()` | player docs/chapters, checkpoint |
| ConsistencyAuditor | `node_consistency_auditor` | state | warnings, checkpoint |
| Exporter | `node_exporter` | memory summary | `langgraph_memory_report.md` |

## 7. 与默认 prompt pipeline 的区别

```mermaid
flowchart TB
    subgraph PromptPipeline["默认 prompt pipeline"]
        P1[线性步骤]
        P2[最多一次修订]
        P3[无持久 memory]
        P4[适合快速生成/兼容旧 Python]
    end

    subgraph LangGraphPipeline["LangGraph multi-agent pipeline"]
        L1[显式图节点]
        L2[条件路由与复审循环]
        L3[SQLite 分层记忆]
        L4[长文本切块检索]
        L5[适合 long/deep/novel 长篇生成]
    end
```

