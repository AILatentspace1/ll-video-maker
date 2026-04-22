"""运行时配置 — 支持 DeepSeek / ZhipuAI(Anthropic-compatible) 两个 provider。"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    LLM_PROVIDER: str = "deepseek"
    PRODUCER_MODEL: str = "deepseek-reasoner"
    SUBAGENT_MODEL: str = "deepseek-chat"
    JUDGE_MODEL: str = "deepseek-chat"
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com/v1"
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_BASE_URL: str = "https://api.anthropic.com"
    ZHIPU_API_KEY: str = ""
    ZHIPU_OPENAI_BASE_URL: str = "https://open.bigmodel.cn/api/paas/v4"
    SKILL_PATH: str = "E:/workspace/orchestrator_skills/.claude/skills/video-maker"
    POSTGRES_URL: str = ""
    LANGCHAIN_PROJECT: str = "ll-video-maker"

    def __post_init__(self) -> None:
        _env = os.getenv
        self.LLM_PROVIDER = _env("LLM_PROVIDER", self.LLM_PROVIDER)
        self.PRODUCER_MODEL = _env("PRODUCER_MODEL", self.PRODUCER_MODEL)
        self.SUBAGENT_MODEL = _env("SUBAGENT_MODEL", self.SUBAGENT_MODEL)
        self.JUDGE_MODEL = _env("JUDGE_MODEL", self.JUDGE_MODEL)
        self.DEEPSEEK_API_KEY = _env("DEEPSEEK_API_KEY", self.DEEPSEEK_API_KEY)
        self.DEEPSEEK_BASE_URL = _env("DEEPSEEK_BASE_URL", self.DEEPSEEK_BASE_URL)
        self.ANTHROPIC_API_KEY = _env("ANTHROPIC_API_KEY", self.ANTHROPIC_API_KEY)
        self.ANTHROPIC_BASE_URL = _env("ANTHROPIC_BASE_URL", self.ANTHROPIC_BASE_URL)
        self.ZHIPU_API_KEY = _env("ZHIPU_API_KEY", self.ZHIPU_API_KEY)
        self.ZHIPU_OPENAI_BASE_URL = _env("ZHIPU_OPENAI_BASE_URL", self.ZHIPU_OPENAI_BASE_URL)
        self.SKILL_PATH = _env("VIDEO_MAKER_SKILL_PATH", self.SKILL_PATH)
        self.POSTGRES_URL = _env("POSTGRES_URL", self.POSTGRES_URL)
        self.LANGCHAIN_PROJECT = _env("LANGCHAIN_PROJECT", self.LANGCHAIN_PROJECT)


cfg = Config()
