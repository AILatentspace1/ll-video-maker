---
description: "Use when writing or editing script.md files. Covers the exact field syntax, scene type requirements, and structural constraints enforced by L1 ratify and the evaluator."
applyTo: "**/script*.md"
---

# script.md Format Rules

Full validation logic: [`middleware/ratify_l1.py`](../../src/ll_video_maker/middleware/ratify_l1.py)

## File Structure

Every script starts with an optional `style_spine` fenced block, then a sequence of `## Scene N: Title` sections:

~~~markdown
```style_spine
lut_style: professional
aspect_ratio: 16:9
```

## Scene 1: Scene Title
type: title_card
contract_topic: "Exact topic text from contract"
narrative_role: hook
duration_estimate: 4

## Scene 2: Another Scene
type: narration
...
~~~

## Field Syntax Rules

- Field names are **literal plain text** — never use Markdown emphasis
  - ✅ `type: narration`
  - ❌ `**type:** narration`
  - ❌ `- type: narration`
- Every scene must have a `## Scene N: Title` heading where `N` is sequential from 1
- `contract_topic` value must **exactly match** a topic string from `script-contract.json`
  - ✅ `contract_topic: "AI Agent市场规模"`
  - ❌ `contract_topic: "AI Agent市场规模 (hook)"` — suffixes fail validation
- `narrative_role` must be one of: `hook` | `setup` | `development` | `climax` | `cta`

## Scene Types & Required Fields

### `title_card` / `transition`
Minimum required fields:
```
type: title_card
contract_topic: "..."
narrative_role: hook
duration_estimate: 4
```

### `narration` / `quote_card`
All three fields **must** be present:
```
type: narration
contract_topic: "..."
narrative_role: development
duration_estimate: 8
scene_intent: |
  ...
content_brief: |
  ...
narration: |
  Spoken text without Markdown formatting.
```

### `data_card`
Same as `narration`, plus `data_semantic:` and non-empty `items:`:
```
type: data_card
contract_topic: "..."
narrative_role: development
duration_estimate: 6
scene_intent: |
  ...
content_brief: |
  ...
narration: |
  ...
data_semantic:
  claim: "..."
  anchor_number: 52.9
  comparison_axis: "..."
  items:
    - { label: "2024", value: 52.9, unit: "亿美元" }
    - { label: "2030", value: 471,  unit: "亿美元" }
```
- `items:` must not be empty (`items: []` fails ratify)
- Every number in `items` must be grounded in `research.md` — no invented data

### `diagram_walkthrough`
Minimum required fields (no `scene_intent`/`content_brief`/`narration` enforced by ratify, but include for quality):
```
type: diagram_walkthrough
contract_topic: "..."
narrative_role: setup
excalidraw_file: filename.excalidraw
narration: |
  ...
duration_estimate: 12
```

## Scene Count by Duration

| `--duration` | Min scenes | Max scenes |
|---|---|---|
| `1-3min` | 10 | 16 |
| `3-5min` | 18 | 27 |
| `5-10min` | 28 | 43 |

Counted by `## Scene` headings.

## Structural Constraints

- **No 3+ consecutive scenes of the same `type`** — insert a `title_card` or `transition` as a visual break
- **Forbidden fields** (L1 ratify hard-fail): `layer_hint:`, `beats:`
- `duration_estimate` in `script.md` must stay within `max(1.5, plan_duration × 0.35)` seconds of `script-plan.json`
- Scene order and `contract_topic` must match `script-plan.json` exactly

## script-plan.json Structure (for reference)

```json
{
  "target_audience": "technical|general",
  "opening_type": "hook|story",
  "closing_type": "cta",
  "total_duration_estimate": 120,
  "scenes": [
    {
      "scene_number": 1,
      "title": "Scene title",
      "type": "narration",
      "contract_topic": "Exact contract topic",
      "narrative_role": "hook",
      "duration_estimate": 6,
      "purpose": "Why this scene exists"
    }
  ]
}
```

- `scene_number` must be sequential from 1
- `total_duration_estimate` ≈ sum of scene `duration_estimate` values (tolerance: `max(2.0, total × 0.20)`)
