from __future__ import annotations

import json

from ll_video_maker.validators import check_script_contract


def test_check_script_contract_pass(tmp_path):
    output_dir = tmp_path
    (output_dir / "script-contract.json").write_text(
        json.dumps(
            {
                "target_scene_count": {"min": 3, "max": 5},
                "target_duration_frames": {"min": 300, "max": 600},
                "narrative_structure": {"opening_type": "hook", "closing_type": "cta"},
                "key_topics": [
                    {"topic": "AI Agent市场爆发", "narrative_role": "hook"},
                    {"topic": "企业部署策略", "narrative_role": "climax"},
                    {"topic": "行动号召", "narrative_role": "cta"},
                ],
                "constraints": {"max_consecutive_same_type": 2},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (output_dir / "script.md").write_text(
        """```style_spine
lut_style: tech_cool
```

## Scene 1: AI Agent市场爆发
type: narration
contract_topic: \"AI Agent市场爆发\"
narrative_role: hook
narration: |
  AI Agent市场爆发正在发生。
scene_intent:
  story_beat: hook
content_brief: |
  ...
duration_estimate: 4

## Scene 2: 企业部署策略
type: data_card
contract_topic: \"企业部署策略\"
narrative_role: climax
narration: |
  企业部署策略决定落地速度。
scene_intent:
  story_beat: climax
content_brief: |
  ...
data_semantic:
  claim: \"...\"
  anchor_number: 1
  comparison_axis: \"...\"
  items:
    - { label: \"A\", value: 1, unit: \"%\" }
duration_estimate: 5

## Scene 3: 行动号召
type: narration
contract_topic: \"行动号召\"
narrative_role: cta
narration: |
  现在就开始行动。
scene_intent:
  story_beat: cta
content_brief: |
  ...
duration_estimate: 4
""",
        encoding="utf-8",
    )

    assert check_script_contract(str(output_dir)) == []


def test_check_script_contract_catches_role_and_coverage_issues(tmp_path):
    output_dir = tmp_path
    (output_dir / "script-contract.json").write_text(
        json.dumps(
            {
                "target_scene_count": {"min": 3, "max": 4},
                "target_duration_frames": {"min": 300, "max": 450},
                "narrative_structure": {"opening_type": "hook", "closing_type": "cta"},
                "key_topics": [
                    {"topic": "AI Agent市场爆发", "narrative_role": "hook"},
                    {"topic": "主要竞争格局和参与者", "narrative_role": "climax"},
                    {"topic": "行动号召", "narrative_role": "cta"},
                ],
                "constraints": {"max_consecutive_same_type": 2},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (output_dir / "script.md").write_text(
        """## Scene 1: AI Agent市场爆发
type: narration
contract_topic: \"AI Agent市场爆发\"
narrative_role: hook
duration_estimate: 4

## Scene 2: 竞争格局概览
type: narration
contract_topic: \"主要竞争格局和参与者\"
narrative_role: development
narration: |
  当前竞争格局快速变化，参与者持续增加。
duration_estimate: 4

## Scene 3: 收尾
type: narration
narrative_role: development
narration: |
  这里没有真正的结束行动。
duration_estimate: 4
""",
        encoding="utf-8",
    )

    errors = check_script_contract(str(output_dir))
    assert any("topic role 不匹配" in err for err in errors)
    assert any("closing_type 不匹配" in err for err in errors)
