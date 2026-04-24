from __future__ import annotations

from ll_video_maker.config import Config


def test_evaluator_model_defaults_to_judge_model_when_unset(monkeypatch) -> None:
    monkeypatch.delenv("EVALUATOR_MODEL", raising=False)
    monkeypatch.setenv("JUDGE_MODEL", "judge-fast")
    cfg = Config()
    assert cfg.EVALUATOR_MODEL == "judge-fast"


def test_evaluator_model_can_be_overridden(monkeypatch) -> None:
    monkeypatch.setenv("JUDGE_MODEL", "judge-fast")
    monkeypatch.setenv("EVALUATOR_MODEL", "eval-mini")
    cfg = Config()
    assert cfg.EVALUATOR_MODEL == "eval-mini"
