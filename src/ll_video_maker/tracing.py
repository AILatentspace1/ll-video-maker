"""LangSmith tracing helpers — all langsmith imports isolated here.

Every function gracefully degrades when LANGCHAIN_TRACING_V2 is unset
or the langsmith package is missing.

Key design: LangGraph (LANGCHAIN_TRACING_V2=true) creates the root trace
automatically.  We do NOT wrap ``producer.ainvoke()`` with ``tracing_context``
—that would create a competing, disconnected trace.  Instead we pass
``metadata`` and ``tags`` via LangGraph config so they attach to the
automatic trace.  Feedback functions use ``get_current_run_tree()``
inside the LangGraph execution context.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Union
from uuid import UUID

logger = logging.getLogger(__name__)

_LANGSMITH_AVAILABLE = False
try:
    from langsmith.run_trees import get_current_run_tree  # type: ignore[import-untyped]
    _LANGSMITH_AVAILABLE = True
except ImportError:
    get_current_run_tree = None  # type: ignore[assignment,misc]

_TRACING_ENABLED = os.getenv("LANGCHAIN_TRACING_V2", "").lower() in ("true", "1", "yes")


# ── Pipeline config builders ────────────────────────────────────────


def build_run_config(
    *,
    thread_id: str,
    run_id: UUID,
    topic: str,
    duration: str,
    style: str,
    eval_mode: str,
) -> dict:
    """Build a LangGraph RunnableConfig with tracing metadata/tags.

    Pass the returned dict directly to ``producer.ainvoke(..., config=config)``.
    LangGraph will attach metadata and tags to its automatic root trace.
    """
    return {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": 50,
        "run_id": run_id,
        "tags": [
            "pipeline:video-maker",
            f"eval_mode:{eval_mode}",
        ],
        "metadata": {
            "topic": topic,
            "duration": duration,
            "style": style,
            "eval_mode": eval_mode,
        },
    }


# ── L1 ratify feedback ────────────────────────────────────────────


def attach_ratify_feedback(
    *,
    target: str,
    passed: bool,
    attempt: int,
    errors: list[str] | None = None,
) -> None:
    """Record an L1 ratify check result as LangSmith feedback.

    Call after every ``checker(output_dir)`` invocation inside the middleware.
    Runs inside LangGraph context, so ``get_current_run_tree()`` returns
    the correct run.
    """
    if not _TRACING_ENABLED or not get_current_run_tree:
        return

    try:
        rt = get_current_run_tree()
        if rt is None:
            return
        _ls_client().create_feedback(
            run_id=rt.id,
            key=f"l1_{target}_pass",
            score=1 if passed else 0,
            comment="\n".join(errors) if errors else ("pass" if passed else "fail"),
            metadata={"target": target, "attempt": attempt},
        )
    except Exception as exc:
        logger.debug("langsmith ratify feedback failed: %s", exc)


# ── Evaluator feedback ─────────────────────────────────────────────


def attach_eval_feedback(eval_result: dict[str, Any]) -> None:
    """Record weighted eval scores as LangSmith feedback.

    Call when evaluator subagent returns ``script-eval.json`` content.
    Expected keys: ``weighted_total``, ``dimension_scores``.
    """
    if not _TRACING_ENABLED or not get_current_run_tree:
        return

    try:
        rt = get_current_run_tree()
        if rt is None:
            return
        client = _ls_client()

        weighted_total = eval_result.get("weighted_total")
        if isinstance(weighted_total, (int, float)):
            client.create_feedback(
                run_id=rt.id,
                key="script_weighted_score",
                score=float(weighted_total) / 100.0,
                comment=f"weighted_total={weighted_total}",
            )

        for dim_key, weight in [
            ("narrative_flow", 0.30),
            ("contract_compliance", 0.25),
            ("data_accuracy", 0.20),
            ("pacing", 0.15),
            ("visual_variety", 0.10),
        ]:
            dim_scores = eval_result.get("dimension_scores") or eval_result.get("scores") or {}
            raw = dim_scores.get(dim_key)
            if isinstance(raw, (int, float)):
                client.create_feedback(
                    run_id=rt.id,
                    key=f"dim_{dim_key}",
                    score=float(raw) / 100.0,
                    metadata={"weight": weight},
                )
    except Exception as exc:
        logger.debug("langsmith eval feedback failed: %s", exc)


# ── Production feedback hook ───────────────────────────────────────


def attach_production_feedback(run_id: Union[str, UUID], output_dir: str) -> None:
    """Post-run: read script-eval.json and upload all dimension scores.

    Called from ``main.py`` after ``producer.ainvoke()`` returns.
    Uses the explicit ``run_id`` (from config) because we're outside
    the LangGraph execution context at this point.
    """
    if not _TRACING_ENABLED or not run_id:
        return

    eval_path = Path(output_dir) / "script-eval.json"
    if not eval_path.exists():
        return

    try:
        eval_result = json.loads(eval_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return

    try:
        client = _ls_client()
        client.create_feedback(
            run_id=run_id,
            key="script_weighted_score",
            score=float(eval_result.get("weighted_total", 0)) / 100.0,
            metadata={"source": "production_hook"},
        )
        for dim_key in ("narrative_flow", "contract_compliance", "data_accuracy", "pacing", "visual_variety"):
            dim_scores = eval_result.get("dimension_scores") or eval_result.get("scores") or {}
            raw = dim_scores.get(dim_key)
            if isinstance(raw, (int, float)):
                client.create_feedback(
                    run_id=run_id,
                    key=f"dim_{dim_key}",
                    score=float(raw) / 100.0,
                )
        logger.info("[OK] langsmith production feedback attached (run_id=%s)", str(run_id)[:8])
    except Exception as exc:
        logger.debug("langsmith production feedback failed: %s", exc)


# ── Internal ───────────────────────────────────────────────────────


def _ls_client():
    from langsmith import Client as LSClient  # type: ignore[import-untyped]
    return LSClient()
