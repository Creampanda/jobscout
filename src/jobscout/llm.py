"""
Тонкая обёртка над anthropic SDK с роутингом на DeepSeek или Anthropic.

Ключевая идея: один и тот же код работает с обоими провайдерами благодаря
Anthropic-compatible endpoint у DeepSeek (https://api.deepseek.com/anthropic).
Меняется только base_url и API-ключ.
"""

from anthropic import Anthropic
from anthropic.types import Message

from jobscout.config import settings


def get_client() -> Anthropic:

    if settings.llm_provider == "deepseek":
        if not settings.deepseek_api_key:
            raise RuntimeError("DEEPSEEK_API_KEY is not set")
        return Anthropic(
            api_key=settings.deepseek_api_key,
            base_url="https://api.deepseek.com/anthropic",
        )

    elif settings.llm_provider == "anthropic":
        if not settings.anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set")
        return Anthropic(
            api_key=settings.anthropic_api_key,
        )
    else:
        raise ValueError(f"Unknown LLM_PROVIDER: {settings.llm_provider}")


def call_llm(
    *,
    system: str,
    messages: list[dict],
    tools: list[dict] | None = None,
    tool_choice: dict | None = None,
    max_tokens: int = 1500,
    temperature: float = 0.0,
    model: str | None = None,
) -> Message:
    client = get_client()
    kwargs = {
        "model": model or settings.llm_model,
        "system": system,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "thinking": {"type": "disabled"},
    }
    if tools is not None:
        kwargs["tools"] = tools

    if tool_choice is not None:
        kwargs["tool_choice"] = tool_choice

    return client.messages.create(**kwargs)
