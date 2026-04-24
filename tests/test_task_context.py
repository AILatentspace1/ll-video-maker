from __future__ import annotations

from types import SimpleNamespace

from ll_video_maker.task_context import infer_milestone, infer_phase, infer_validation_target


def test_infer_milestone_prefers_description() -> None:
    state = SimpleNamespace(current_milestone="script")
    assert infer_milestone("milestone: research\nphase: eval", state) == "research"


def test_infer_milestone_falls_back_to_state() -> None:
    state = SimpleNamespace(current_milestone="script")
    assert infer_milestone("phase: eval", state) == "script"


def test_infer_phase_parses_explicit_field() -> None:
    assert infer_phase("milestone: script\nphase: contract_review") == "contract_review"


def test_infer_validation_target_namespaces_evaluator_targets() -> None:
    state = SimpleNamespace(current_milestone="script")
    assert infer_validation_target("evaluator", "milestone: script\nphase: eval", state) == "script_eval"
    assert infer_validation_target("evaluator", "milestone: research\nphase: contract_review", state) == "research_contract_review"
