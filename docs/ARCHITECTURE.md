# 项目结构说明

`jbs_agent` 按职责拆成六个子包：

```text
jbs_agent/
  core/        运行配置、.env 加载、OpenAI-compatible HTTP 客户端
  generation/  生成流程、提示词、长度档位、示例数据、LangGraph 工作流
  memory/      SQLite 分层记忆、检查点、长文本检索
  output/      标准项目导出、Word 写入、通用投稿版整理
  quality/     本地结构校验、质量报告
  reference/   创作硬约束、资料来源说明
  cli.py       命令行参数解析和引擎分发
```

## 两种生成引擎

- `--engine prompt`：默认引擎，只依赖 Python 标准库，兼容当前 Python 3.7 环境。
- `--engine langgraph`：可选多 Agent 图工作流，需要 `environment.yml` 中的 Python 3.11 conda 环境。

## 主要数据流

1. `cli.py` 读取参数和 `.env`。
2. `generation.pipeline` 或 `generation.langgraph_workflow` 生成 `brief -> story_bible -> review -> package -> player_docs`。
3. `quality.validator` 做本地结构检查。
4. `output.exporter` 保存标准目录，并调用 `output.submission` 生成投稿版。
5. LangGraph 引擎额外通过 `memory.hierarchical_memory` 保存 canonical、working、retrieval 三层记忆。

多 Agent 与 Memory 的详细流图见 `docs/TECHNICAL_FLOW.md`。
