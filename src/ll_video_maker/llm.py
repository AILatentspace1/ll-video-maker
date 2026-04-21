"""LLM 工厂 — 根据 provider 返回对应的 ChatModel。"""
from __future__ import annotations

from langchain_core.language_models import BaseChatModel

from .config import cfg


def get_llm(model_name: str, temperature: float = 0.3) -> BaseChatModel:
    """根据 LLM_PROVIDER 返回对应 ChatModel。"""
    provider = cfg.LLM_PROVIDER

    if provider == "deepseek":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model_name,
            api_key=cfg.DEEPSEEK_API_KEY,
            base_url=cfg.DEEPSEEK_BASE_URL,
            temperature=temperature,
        )

    if provider in ("zhipu", "anthropic"):
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=model_name,
            anthropic_api_key=cfg.ANTHROPIC_API_KEY,
            anthropic_api_url=cfg.ANTHROPIC_BASE_URL,
            temperature=temperature,
        )

    raise ValueError(f"不支持的 LLM_PROVIDER: {provider}")
