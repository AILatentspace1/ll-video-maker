"""LLM 工厂 — 根据 provider 返回对应的 ChatModel。"""
from __future__ import annotations

from langchain_core.language_models import BaseChatModel

from .config import cfg


def _is_reasoning_model(model_name: str) -> bool:
    """识别需要避免显式 temperature 的 reasoning 模型。"""
    normalized = model_name.strip().lower()
    return "reasoner" in normalized or "reasoning" in normalized


def get_llm(model_name: str, temperature: float = 0.3) -> BaseChatModel:
    """根据 LLM_PROVIDER 返回对应 ChatModel。"""
    provider = cfg.LLM_PROVIDER
    model_kwargs = {"model": model_name}

    # DeepSeek reasoning 模型通常不需要显式 temperature；保留 chat 模型现有行为。
    if not _is_reasoning_model(model_name):
        model_kwargs["temperature"] = temperature

    if provider == "deepseek":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            api_key=cfg.DEEPSEEK_API_KEY,
            base_url=cfg.DEEPSEEK_BASE_URL,
            **model_kwargs,
        )

    if provider == "zhipu_openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            api_key=cfg.ZHIPU_API_KEY,
            base_url=cfg.ZHIPU_OPENAI_BASE_URL,
            **model_kwargs,
        )

    if provider in ("zhipu", "anthropic"):
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            anthropic_api_key=cfg.ANTHROPIC_API_KEY,
            anthropic_api_url=cfg.ANTHROPIC_BASE_URL,
            **model_kwargs,
        )

    raise ValueError(f"不支持的 LLM_PROVIDER: {provider}")
