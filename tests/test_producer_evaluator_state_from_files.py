from __future__ import annotations

import json
from types import SimpleNamespace

from ll_video_maker.producer import _extract_eval_state_updates


def test_contract_review_state_updates_fall_back_to_result_file(tmp_path) -> None:
    review_path = tmp_path / "contract-review.json"
    payload = {
        "phase": "contract_review",
        "milestone": "script",
        "pass": True,
        "issues": [],
    }
    review_path.write_text(json.dumps(payload), encoding="utf-8")
    state = SimpleNamespace(current_milestone="script")

    updates = _extract_eval_state_updates(
        "evaluator",
        "milestone: script\nphase: contract_review",
        "已写入 contract-review.json",
        state,
        {"contract_review_file": str(review_path)},
    )

    assert updates["last_contract_review"] == payload


def test_eval_state_updates_fall_back_to_result_file(tmp_path) -> None:
    eval_path = tmp_path / "script-eval.json"
    payload = {
        "phase": "eval",
        "milestone": "script",
        "pass": True,
        "weighted_total": 86.5,
        "iteration_fixes": [],
        "contract_violations": [],
    }
    eval_path.write_text(json.dumps(payload), encoding="utf-8")
    state = SimpleNamespace(current_milestone="script", eval_best_score=0.0, eval_round=0)

    updates = _extract_eval_state_updates(
        "evaluator",
        "milestone: script\nphase: eval",
        "已写入 script-eval.json",
        state,
        {"script_eval_file": str(eval_path)},
    )

    assert updates["last_eval_result"] == payload
    assert updates["eval_best_score"] == 86.5
    assert updates["eval_round"] == 1
