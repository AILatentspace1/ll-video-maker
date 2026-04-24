---
description: "Use when modifying ratify middleware, validators, or L1 validation logic. Covers all ratify rules, validator contracts, and invariants that must be preserved."
applyTo: "**/middleware/**,**/validators/**"
---

# Ratify & Validator Rules

Reference: [`middleware/ratify_l1.py`](../../src/ll_video_maker/middleware/ratify_l1.py), [`validators/`](../../src/ll_video_maker/validators/)

## L1 Ratify — Retry Behaviour

- `MAX_RETRY = 2` (defined in `ratify_l1.py`) — do not increase without considering cascading API cost
- On failure: error messages are **appended** to the task description and the agent is retried
- `CHECKERS` dict maps validation target name → checker function; add new targets here

## `check_research` Rules

All three must pass:

| Rule | Threshold |
|------|-----------|
| File exists | `output_dir/research.md` |
| Minimum length | `> 800` characters |
| Section count | `>= 3` headings matching `^## ` |
| URL present | At least one `https?://` match |

## `check_script` Rules

Runs in order — all errors are collected before returning:

### 1. Scene Count by Duration

| Duration | Min | Max |
|----------|-----|-----|
| `1-3min` | 10 | 16 |
| `3-5min` | 18 | 27 |
| `5-10min` | 28 | 43 |

Count is `## Scene` headings via `^## Scene` multiline regex.

### 2. Consecutive Same-Type Limit

No 3+ consecutive scenes with the same `type:` value. Check uses a sliding window of 3 over `re.findall(r"^type:\s*(\w+)", ...)`.

### 3. Required Fields for Audio Types

For scenes with `type:` in `("narration", "data_card", "quote_card")`, all three must be present as literal field names (no Markdown emphasis):

- `scene_intent:`
- `content_brief:`
- `narration:`

### 4. `data_card` Extra Requirements

- `data_semantic:` must be present
- `items:` must exist and **not** be empty (`items: []` fails)

### 5. Deprecated Fields

Presence of either `layer_hint:` or `beats:` anywhere in the script fails immediately.

### 6. Downstream Validators (called by `check_script`)

`check_script` also calls all three validators in sequence:

```python
errors.extend(check_script_plan(output_dir))       # plan scene count / duration / topic mapping
errors.extend(check_script_contract(output_dir))   # script vs contract topic coverage
errors.extend(check_script_plan_consistency(output_dir))  # script.md vs script-plan.json alignment
```

## `check_script_plan` Rules (`validators/script_plan.py`)

- `scene_number` must be sequential, 1-based
- Scene count and total duration frames must match contract's `target_scene_count` and `target_duration_frames`
- `total_duration_estimate` deviation tolerance: `max(2.0, total * 0.20)`
- Every `key_topics[].topic` must map to a plan scene via exact `contract_topic` match
- `contract_topic` values are normalized by `normalize_contract_topic()` — strip quotes + strip trailing `(hook/setup/development/climax/cta)` suffixes

## `check_script_contract` Rules (`validators/script_contract.py`)

- Topic matching first tries **exact** normalized match on `contract_topic:` field
- Falls back to keyword scoring across the full scene block (needs `>= 2` keyword hits)
- A topic is considered covered if any scene's block contains it

## `check_script_plan_consistency` Rules (`validators/script_plan_consistency.py`)

For every scene, `script.md` must agree with `script-plan.json` on:

| Field | Tolerance |
|-------|-----------|
| `type` | Exact match |
| `contract_topic` | Exact (after `normalize_contract_topic`) |
| `narrative_role` | Exact |
| `duration_estimate` | `max(1.5, plan_duration * 0.35)` seconds |

## `evaluator_precheck` Rules (`validators/evaluator_precheck.py`)

Called before the Evaluator agent runs. Returns a pre-filled failure dict to skip the LLM call when:

**Phase `contract_review`** — `script-contract.json` must:
- Exist and be valid JSON
- Have `version == 1`
- Have `target_scene_count.min` and `.max` as integers with `min <= max`
- Have `target_duration_frames.min` and `.max` as integers
- Have `key_topics` as a non-empty list
- Each topic item's `narrative_role` must be in `{"hook","setup","development","climax","cta"}`

**Phase `eval`** — `script.md` must pass `check_script_plan`, `check_script_contract`, and `check_script_plan_consistency`.

## Invariants — Do Not Break

- `normalize_contract_topic()` is called in **both** `script_plan.py` and `script_contract.py`; changes must be symmetric
- `CANONICAL_NARRATIVE_ROLES` set in `evaluator_precheck.py` must stay in sync with allowed values elsewhere
- Checker functions return `list[str]` (empty = pass); never raise exceptions — add `try/except` for any new file I/O
- `check_script` is called with `duration` defaulting to `"1-3min"` if not passed; always thread it through from `ratify_l1.py`
