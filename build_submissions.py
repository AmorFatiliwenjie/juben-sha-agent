from __future__ import annotations

import argparse
import sys
from pathlib import Path

from jbs_agent.submission import build_submission_for_run


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="为已有剧本杀输出目录生成百变大侦探投稿版文件夹和 zip。")
    parser.add_argument("--outputs", default="outputs", help="outputs 根目录。")
    parser.add_argument("--all", action="store_true", help="处理 outputs 下所有含 source/story_bible.json 的目录。")
    parser.add_argument("runs", nargs="*", help="指定一个或多个剧本目录。")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    targets: list[Path] = []
    if args.all:
        outputs = Path(args.outputs)
        targets.extend(path for path in outputs.iterdir() if (path / "source" / "story_bible.json").exists())
    targets.extend(Path(item) for item in args.runs)
    if not targets:
        print("ERROR: 请传入 --all 或指定剧本目录。", file=sys.stderr)
        return 2

    for target in sorted(set(targets)):
        try:
            submission_dir = build_submission_for_run(target, force=True)
            print(f"生成投稿版：{submission_dir}")
        except Exception as exc:
            print(f"ERROR: {target}: {exc}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
