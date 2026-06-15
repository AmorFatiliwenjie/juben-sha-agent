from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


class ConfigError(RuntimeError):
    """Raised when runtime configuration is incomplete."""


def load_dotenv(path: Path) -> list[str]:
    """Load simple KEY=VALUE pairs without overriding existing environment."""
    if not path.exists():
        return []

    loaded: list[str] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value
            loaded.append(key)
    return loaded


def first_env(names: Iterable[str], default: str | None = None) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return default


@dataclass(frozen=True)
class RuntimeConfig:
    api_key: str
    base_url: str
    model: str
    temperature: float
    max_tokens: int | None
    timeout: int
    json_mode: bool

    @classmethod
    def from_args(cls, args, require_key: bool) -> "RuntimeConfig":
        api_key = args.api_key or first_env(
            ["LLM_API_KEY", "OPENAI_API_KEY", "DASHSCOPE_API_KEY", "MOONSHOT_API_KEY"], ""
        )
        base_url = args.base_url or first_env(["LLM_BASE_URL", "OPENAI_BASE_URL"], "https://api.openai.com/v1")
        model = args.model or first_env(["LLM_MODEL", "OPENAI_MODEL"], "")

        if require_key and not api_key:
            raise ConfigError("缺少 API key。请在 .env 里填写 LLM_API_KEY，或用 --api-key 传入。")
        if require_key and not model:
            raise ConfigError("缺少模型名。请在 .env 里填写 LLM_MODEL，或用 --model 传入。")

        return cls(
            api_key=api_key or "dry-run",
            base_url=base_url or "https://api.openai.com/v1",
            model=model or "dry-run-model",
            temperature=args.temperature,
            max_tokens=args.max_tokens,
            timeout=args.timeout,
            json_mode=args.json_mode,
        )
