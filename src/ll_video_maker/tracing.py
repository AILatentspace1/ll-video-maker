"""Tracing helpers — OTel span attributes + optional LangSmith feedback.

All tracing side-effects are isolated here.  Two backends:

* **OTel** (LANGSMITH_OTEL_ENABLED=true): writes span attributes/events
  via ``opentelemetry.trace.get_current_span()``.  Works with any OTel
  collector backend.
* **LangSmith** (LANGCHAIN_TRACING_V2=true): writes feedback via
  ``langsmith.Client.create_feedback()`` on top of OTel spans.
  Falls back to OTel-only when langsmith client is unavailable.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ── Backend detection ──────────────────────────────────────────────

_OTEL_AVAILABLE = False
try:
    from opentelemetry import trace as otel_trace  # type: ignore[import-untyped]
    _OTEL_AVAILABLE = True
except ImportError:
    otel_trace = None  # type: ignore[assignment,misc]

_LANGSMITH_AVAILABLE = False
try:
    from langsmith.run_trees import get_current_run_tree  # type: ignore[import-untyped]
    _LANGSMITH_AVAILABLE = True
except ImportError:
    get_current_run_tree = None  # type: ignore[assignment,misc]

_TRACING_ENABLED = (
    os.getenv("LANGSMITH_OTEL_ENABLED", "").lower() in ("true", "1", "yes")
    or os.getenv("LANGCHAIN_TRACING_V2", "").lower() in ("true", "1", "yes")
)


# ── Internal helpers ───────────────────────────────────────────────


def _otel_span():
    """Return the current OTel span, or None."""
    if not _OTEL_AVAILABLE:
        return None
    span = otel_trace.get_current_span()
    if span and span.is_recording():
        return span
    return None


def _ls_client():
    from langsmith import Client as LSClient  # type: ignore[import-untyped]
    return LSClient()


# ── Pipeline config builders ────────────────────────────────────────


def build_run_config(
    *,
    thread_id: str,
    run_id: str,
    topic: str,
    duration: str,
    style: str,
    eval_mode: str,
) -> dict:
    """Build a LangGraph RunnableConfig with tracing metadata/tags."""
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
    """Record an L1 ratify check result."""
    if not _TRACING_ENABLED:
        return

    # OTel: span attributes (works with any backend)
    span = _otel_span()
    if span:
        try:
            span.set_attribute(f"ratify.{target}.passed", passed)
            span.set_attribute(f"ratify.{target}.attempt", attempt)
            comment = "\n".join(errors) if errors else ("pass" if passed else "fail")
            span.add_event(
                f"ratify.{target}",
                attributes={"passed": passed, "attempt": attempt, "comment": comment},
            )
        except Exception as exc:
            logger.debug("otel ratify feedback failed: %s", exc)

    # LangSmith feedback (optional, on top of OTel)
    if not _LANGSMITH_AVAILABLE:
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
    """Record weighted eval scores."""
    if not _TRACING_ENABLED:
        return

    # OTel: span attributes
    span = _otel_span()
    if span:
        try:
            weighted_total = eval_result.get("weighted_total")
            if isinstance(weighted_total, (int, float)):
                span.set_attribute("eval.weighted_total", float(weighted_total) / 100.0)
            for dim_key in ("narrative_flow", "contract_compliance", "data_accuracy", "pacing", "visual_variety"):
                dim_scores = eval_result.get("dimension_scores") or eval_result.get("scores") or {}
                raw = dim_scores.get(dim_key)
                if isinstance(raw, (int, float)):
                    span.set_attribute(f"eval.dim.{dim_key}", float(raw) / 100.0)
        except Exception as exc:
            logger.debug("otel eval feedback failed: %s", exc)

    # LangSmith feedback (optional)
    if not _LANGSMITH_AVAILABLE:
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


def attach_production_feedback(run_id: str, output_dir: str) -> None:
    """Post-run: read script-eval.json and attach scores to the trace.

    Inside LangGraph context, writes OTel attributes.
    With LangSmith, also writes feedback using the explicit run_id.
    """
    if not _TRACING_ENABLED:
        return

    eval_path = Path(output_dir) / "script-eval.json"
    if not eval_path.exists():
        return

    try:
        eval_result = json.loads(eval_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return

    # OTel: try current span (may or may not be available post-run)
    span = _otel_span()
    if span:
        try:
            weighted_total = eval_result.get("weighted_total", 0)
            span.set_attribute("eval.weighted_total", float(weighted_total) / 100.0)
            for dim_key in ("narrative_flow", "contract_compliance", "data_accuracy", "pacing", "visual_variety"):
                dim_scores = eval_result.get("dimension_scores") or eval_result.get("scores") or {}
                raw = dim_scores.get(dim_key)
                if isinstance(raw, (int, float)):
                    span.set_attribute(f"eval.dim.{dim_key}", float(raw) / 100.0)
        except Exception as exc:
            logger.debug("otel production feedback failed: %s", exc)

    # LangSmith feedback via explicit run_id
    if not _LANGSMITH_AVAILABLE or not run_id:
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
        logger.info("[OK] production feedback attached (run_id=%s)", run_id[:8])
    except Exception as exc:
        logger.debug("langsmith production feedback failed: %s", exc)
