from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import ConfigError, RuntimeConfig, load_dotenv
from .length_profiles import available_profiles, default_max_tokens, default_timeout
from .pipeline import generate_auto_brief, load_brief, run_pipeline
from .prompts import available_player_depths


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="使用 OpenAI-compatible 大模型 API 生成规范保存的剧本杀项目。",
    )
    parser.add_argument("--brief", default="configs/example_brief.json", help="创作需求 JSON 文件。")
    parser.add_argument("--auto-brief", action="store_true", help="先让大模型自动生成 brief，再继续生成完整剧本。")
    parser.add_argument("--brief-seed", default="", help="自动生成 brief 时的一句话种子想法，可留空。")
    parser.add_argument("--brief-seed-file", default="", help="自动生成 brief 时读取的种子文本文件。")
    parser.add_argument("--save-brief", default="", help="把自动生成的 brief 另存为 JSON 文件，便于下次手动复用。")
    parser.add_argument(
        "--length",
        choices=available_profiles(),
        default="standard",
        help="输出长度：standard 标准，long 长篇，epic 超长篇。",
    )
    parser.add_argument(
        "--player-depth",
        choices=available_player_depths(),
        default="normal",
        help="玩家个人本深度：normal 单次生成，deep 章节式厚本，novel 章节式超厚本。",
    )
    parser.add_argument("--out", default="outputs", help="输出目录。")
    parser.add_argument("--env", default=".env", help="环境变量文件，默认读取 .env。")
    parser.add_argument("--api-key", default="", help="API key。也可用 LLM_API_KEY/OPENAI_API_KEY。")
    parser.add_argument("--base-url", default="", help="OpenAI-compatible base URL，例如 https://api.openai.com/v1。")
    parser.add_argument("--model", default="", help="模型名，例如 gpt-4o-mini 或你的兼容服务模型名。")
    parser.add_argument("--temperature", type=float, default=0.75, help="创作温度。")
    parser.add_argument("--max-tokens", type=int, default=None, help="单次调用最大输出 token，默认不传。")
    parser.add_argument("--timeout", type=int, default=None, help="单次 API 请求超时秒数；默认随 --length 自动调整。")
    parser.add_argument("--dry-run", action="store_true", help="不调用 API，用内置示例验证导出规范。")
    json_group = parser.add_mutually_exclusive_group()
    json_group.add_argument(
        "--json-mode",
        dest="json_mode",
        action="store_true",
        help="向兼容接口传 response_format=json_object。",
    )
    json_group.add_argument(
        "--no-json-mode",
        dest="json_mode",
        action="store_false",
        help="不传 response_format=json_object，适合不支持 JSON mode 的兼容服务。",
    )
    parser.set_defaults(json_mode=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    env_path = Path(args.env)
    load_dotenv(env_path)

    try:
        if args.max_tokens is None:
            args.max_tokens = default_max_tokens(args.length)
        if args.timeout is None:
            args.timeout = default_timeout(args.length)
        config = RuntimeConfig.from_args(args, require_key=not args.dry_run)
        if args.auto_brief:
            seed = args.brief_seed
            if args.brief_seed_file:
                seed_path = Path(args.brief_seed_file)
                if not seed_path.exists():
                    raise FileNotFoundError(f"找不到 brief seed 文件: {seed_path}")
                file_seed = seed_path.read_text(encoding="utf-8").strip()
                seed = f"{seed}\n\n{file_seed}".strip()
            brief = generate_auto_brief(
                config,
                seed=seed,
                length_profile=args.length,
                dry_run=args.dry_run,
                progress=lambda message: print(message, flush=True),
            )
            if args.save_brief:
                save_path = Path(args.save_brief)
                save_path.parent.mkdir(parents=True, exist_ok=True)
                save_path.write_text(json.dumps(brief, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                print(f"自动 brief 已保存：{save_path}", flush=True)
        else:
            brief = load_brief(Path(args.brief))
        run_dir, warnings = run_pipeline(
            brief,
            config,
            Path(args.out),
            dry_run=args.dry_run,
            length_profile=args.length,
            player_depth=args.player_depth,
            progress=lambda message: print(message, flush=True),
        )
    except (ConfigError, FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"\n生成完成：{run_dir}")
    if warnings:
        print("\n本地结构检查发现警告，请查看 review/quality_report.md：")
        for item in warnings:
            print(f"- {item}")
    else:
        print("本地结构检查未发现警告。")
    return 0
