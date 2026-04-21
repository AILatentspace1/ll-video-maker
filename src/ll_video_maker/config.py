"""运行时配置 — 支持 DeepSeek / ZhipuAI(Anthropic-compatible) 两个 provider。"""
from __future__ import annotations
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # Provider: deepseek | zhipu | anthropic
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "deepseek")

    # 模型名
    PRODUCER_MODEL: str = os.getenv("PRODUCER_MODEL", "deepseek-chat")
    SUBAGENT_MODEL: str = os.getenv("SUBAGENT_MODEL", "deepseek-chat")
    JUDGE_MODEL: str = os.getenv("JUDGE_MODEL", "deepseek-chat")

    # DeepSeek
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_BASE_URL: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")

    # ZhipuAI (Anthropic-compatible proxy)
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    ANTHROPIC_BASE_URL: str = os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com")

    # video-maker skill 根目录
    SKILL_PATH: str = os.getenv(
        "VIDEO_MAKER_SKILL_PATH",
        "E:/workspace/orchestrator_skills/.claude/skills/video-maker",
    )

    POSTGRES_URL: str = os.getenv("POSTGRES_URL", "")
    LANGCHAIN_PROJECT: str = os.getenv("LANGCHAIN_PROJECT", "ll-video-maker")


cfg = Config()
