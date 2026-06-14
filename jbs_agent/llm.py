from __future__ import annotations

import json
import re
import socket
import time
import urllib.error
import urllib.request
from typing import Any


class LLMError(RuntimeError):
    """Raised when the remote model call fails or returns unusable content."""


class OpenAICompatibleClient:
    """Minimal OpenAI-compatible chat completions client using only stdlib."""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        *,
        timeout: int = 180,
        max_tokens: int | None = None,
        json_mode: bool = True,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.max_tokens = max_tokens
        self.json_mode = json_mode

    @property
    def endpoint(self) -> str:
        if self.base_url.endswith("/chat/completions"):
            return self.base_url
        return f"{self.base_url}/chat/completions"

    def complete(self, messages: list[dict[str, str]], *, temperature: float = 0.7, json_object: bool = False) -> str:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if self.max_tokens:
            body["max_tokens"] = self.max_tokens
        if json_object and self.json_mode:
            body["response_format"] = {"type": "json_object"}

        request = urllib.request.Request(
            self.endpoint,
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise LLMError(f"模型接口返回 HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise LLMError(f"无法连接模型接口: {exc.reason}") from exc
        except (TimeoutError, socket.timeout) as exc:
            raise LLMError(
                f"模型接口请求超时（当前 timeout={self.timeout}s）。"
                "长篇模式输出较大，可以重试，或运行时加 --timeout 600/900；"
                "如果服务端输出额度较小，也可以降低 --max-tokens 或使用 --length standard。"
            ) from exc
        except OSError as exc:
            if "timed out" in str(exc).lower():
                raise LLMError(
                    f"模型接口读取超时（当前 timeout={self.timeout}s）。"
                    "长篇模式建议使用 --timeout 600 或更高。"
                ) from exc
            raise

        try:
            return payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError(f"模型接口响应格式异常: {payload}") from exc

    def request_json(
        self,
        label: str,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.7,
        retries: int = 2,
        compact_retry_hint: str = "",
    ) -> dict[str, Any]:
        last_text = ""
        original_messages = list(messages)
        for attempt in range(retries + 1):
            text = self.complete(messages, temperature=temperature, json_object=True)
            last_text = text
            try:
                parsed = extract_json_object(text)
                if isinstance(parsed, dict):
                    return parsed
                raise ValueError("JSON root is not an object")
            except ValueError:
                if attempt >= retries:
                    break
                time.sleep(0.8)
                if compact_retry_hint:
                    messages = original_messages + [
                        {
                            "role": "user",
                            "content": (
                                f"上一版 {label} 不是合法 JSON，可能因为输出过长被截断。"
                                "请重新生成一份更短、更紧凑、完整闭合的合法 JSON 对象。"
                                f"{compact_retry_hint}"
                                "只输出 JSON，不要 Markdown。"
                            ),
                        }
                    ]
                else:
                    messages = [
                        {
                            "role": "system",
                            "content": "你是 JSON 修复器。只输出合法 JSON 对象，不要解释，不要 Markdown。",
                        },
                        {
                            "role": "user",
                            "content": f"把下面的 {label} 修复为合法 JSON 对象，保留原意：\n\n{last_text}",
                        },
                    ]
        hint = ""
        if looks_truncated_json(last_text):
            hint = " 看起来模型输出在 JSON 中途被截断；请降低 --max-tokens、使用 --length standard，或重试。"
        raise LLMError(f"{label} 不是可解析的 JSON。{hint}模型最后输出片段：{last_text[:1000]}")


def extract_json_object(text: str) -> Any:
    text = text.strip()
    if not text:
        raise ValueError("empty response")

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.IGNORECASE | re.DOTALL)
    if fence:
        return json.loads(fence.group(1))

    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return json.loads(text[start : end + 1])

    raise ValueError("no JSON object found")


def looks_truncated_json(text: str) -> bool:
    stripped = text.rstrip()
    if not stripped:
        return False
    if stripped.endswith("}") or stripped.endswith("```"):
        return False
    return "{" in stripped and stripped.count("{") >= stripped.count("}")
