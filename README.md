# 剧本杀 Agent 项目

这个项目用于调用大模型 API 自动创作并规范保存剧本杀：先生成 `story_bible`，再做公平性/安全性审稿，必要时修订，最后分别导出 DM 手册、真相复盘、线索卡、玩家个人本、道具文本和质量报告。

## 目录结构

```text
jbs_agent/
  core/        配置、环境加载、模型客户端
  generation/  提示词、长度档位、生成流水线、LangGraph 工作流
  memory/      分层记忆与长上下文检索
  output/      导出、Word 生成、投稿版整理
  quality/     审稿与结构校验
  reference/   研究约束与资料来源
  cli.py       命令行入口
```

更详细的代码结构说明见 `docs/ARCHITECTURE.md`。

## 快速开始

1. 准备 Python 3.7+。
2. 复制 `.env.example` 为 `.env`，填写你的 API key、base URL 和模型名。
3. 运行：

```powershell
python writing.py --brief configs/example_brief.json --out outputs
```

也可以完全不手写 brief，直接让大模型先自动生成需求，再继续生成完整剧本：

```powershell
python writing.py --auto-brief --out outputs
```

如果你觉得默认生成太短，使用长篇模式：

```powershell
python writing.py --auto-brief --length long --out outputs
```

想要更厚的草案，使用超长篇模式：

```powershell
python writing.py --auto-brief --length epic --out outputs
```

如果重点是“每个人的个人本像商业长本一样厚”，加玩家本深度：

```powershell
python writing.py --auto-brief --length long --player-depth novel --temperature 0.65 --timeout 1200 --out outputs
```

如果你只想给一句方向：

```powershell
python writing.py --auto-brief --brief-seed "6人，本格推理，海岛暴风雪山庄，不要超自然" --out outputs
```

也可以把想法写在 `configs/brief_seed.txt`，再运行：

```powershell
python writing.py --auto-brief --brief-seed-file configs/brief_seed.txt --out outputs
```

如果想把自动生成的 brief 单独保存下来，方便下次手动修改：

```powershell
python writing.py --auto-brief --save-brief configs/generated_brief.json --out outputs
```

如果只是想检查项目能不能导出文件，不调用模型：

```powershell
python writing.py --dry-run --brief configs/example_brief.json --out outputs
```

全自动模式也支持 dry-run：

```powershell
python writing.py --dry-run --auto-brief --out outputs
```

## LangGraph 多 Agent 版本

如果你想用多 Agent + 分层记忆版本，请单独建 conda 环境：

```powershell
conda env create -f environment.yml
conda activate jbs-langgraph
python writing.py --engine langgraph --auto-brief --length long --player-depth deep --out outputs
```

这个版本会把记忆和检查点写入 `outputs/.memory/`，并生成 `review/langgraph_memory_report.md`。

## API 配置

默认使用 OpenAI-compatible Chat Completions 接口：

```env
LLM_API_KEY=sk-your-api-key
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=your-model-name
```

兼容服务只要提供 `/chat/completions` 即可。若你的服务不支持 `response_format={"type":"json_object"}`，运行时加：

```powershell
python writing.py --no-json-mode
```

## 输出规范

每次生成会在 `outputs/时间戳_标题/` 下保存完整项目：

- `00_manifest.json`：文件清单、哈希、输出标准、资料来源。
- `00_README_FIRST.md`：本次生成结果的阅读顺序。
- `01_public_intro.md`：玩家公共开场和公开角色信息。
- `02_dm_manual.md`：主持人流程、每轮话术、线索发放和信息边界。
- `03_truth_and_solution.md`：仅 DM 可见的完整真相与复盘。
- `04_clue_cards.md`：按轮次整理的全部线索卡。
- `05_production_notes.md`：道具、场地、音乐、时长建议。
- `06_safety_and_compliance.md`：适龄提示、触发提醒、AI 生成声明建议。
- `players/`：每个角色一份玩家个人本，单独分发。
- `handouts/`：可打印或可复制的道具文本。
- `source/`：brief、story bible、审稿 JSON、完整资料包 JSON。
- `review/quality_report.md`：模型审稿结果和本地结构检查。
- `submission/`：按本地投稿要求整理的 Word 投稿版目录。
- `剧本名+人数+题材+作者微信号.zip`：可进一步人工复核后投稿的压缩包。

## 投稿版

项目会自动生成通用投稿版结构。投稿要求原文和整理稿默认仅本地保存，不提交到 GitHub；如需调整格式，请参考本地 `docs/投稿要求.md` 和 `docs/submission_format.md`。

投稿版包含：

- `01_简介、角色、区域.docx`
- `02_规则说明.docx`
- `03_亮点、作者阐述.docx`
- `04_结局.docx`
- `人物剧本/角色名_第一幕人物剧本.docx`
- `线索/第几幕线索.docx`
- `地图/地图与房间示意图需求.docx`
- `投票/第一幕投票.docx`
- `真相/第一幕真相.docx` 和 `真相/故事还原.docx`

给已有输出重新生成投稿版：

```powershell
python build_submissions.py --all --outputs outputs
```

投稿前仍需人工补：作者微信号、地图图片或手绘草稿、投票红字答案复核、任务与投票强关联检查、原创性和撞梗检查。

## 创作流水线

0. 可选自动 brief：根据一句话种子或空白需求自动生成完整创作 brief。
1. 生成 `story_bible`：世界观、角色、真相、时间线、线索矩阵、轮次流程。
2. 模型审稿：检查公平推理、线索密度、角色平衡、主持可执行性、内容安全和原创性。
3. 自动修订：若审稿不通过或有强制修复项，会重新修订并复审。
4. 生成公共资料包：公共导入、DM 手册、复盘、线索卡、制作说明。
5. 逐个生成玩家本：按角色信息边界生成，降低泄露完整真相的概率。
6. 本地结构检查：检查角色数、线索数量、线索引用、玩家本数量、潜在泄露等。
7. 规范导出：统一命名、UTF-8 保存、生成 manifest 和质量报告。

## 长度模式

- `--length standard`：默认模式，生成速度快，适合先看创意方向。
- `--length long`：长篇模式，至少 4 轮、线索更密、每名玩家个人本约 3000 字符以上；公共资料会拆成多次调用生成，明显更长。
- `--length epic`：超长篇模式，至少 5 轮、更多 handouts 和线索、每名玩家个人本约 5000 字符以上；更适合拿来做长本草案。

玩家本深度单独控制：

- `--player-depth normal`：默认，每个玩家本一次生成，速度快。
- `--player-depth deep`：每个玩家先生成大纲，再按 7 个章节扩写；`long` 模式下每人目标约 10000 中文字符。
- `--player-depth novel`：商业长本式个人故事量；`long` 模式下每人目标约 18000 中文字符，`epic` 模式下每人目标约 28800 中文字符。

`deep/novel` 会显著增加 API 调用次数。6 人本的 `novel` 模式大约会多调用 48 次左右，耗时和费用都会明显上升。

长篇和超长篇会自动设置更大的 `max_tokens` 默认值。若你的模型上下文或输出额度较小，可以手动降低，例如：

```powershell
python writing.py --auto-brief --length long --max-tokens 8000 --out outputs
```

## 调参建议

- 复杂本格推理：`--temperature 0.55`，更稳。
- 情感沉浸或欢乐机制：`--temperature 0.8`，更有变化。
- 输出被截断：优先用 `--length long`，并增加服务端 max token，或运行时传 `--max-tokens 12000`。
- JSON 解析失败：先试 `--no-json-mode`，再降低 temperature。
- 长篇生成超时：加 `--timeout 600` 或 `--timeout 900` 后重试；`long/epic` 默认也会自动使用更长超时。
- `story_bible 不是可解析的 JSON`：通常是模型在蓝图阶段写太长导致 JSON 中途截断。重试时可用 `--temperature 0.55 --max-tokens 8000 --timeout 900`。
- `truth.culprit=P05 (...)` 警告：这是模型把真凶字段写成“id + 姓名/身份”的格式，新版本会自动识别并标准化为纯 `P05`。

## 注意

模型生成的剧本必须人工复核，尤其是非凶手玩家本是否泄露答案、线索是否真的公平、内容是否适合目标玩家。商用、门店投放、未成年人参与或公开发布前，请按所在地要求做内容自审、版权原创性检查和适龄提示。
