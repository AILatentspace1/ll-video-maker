from __future__ import annotations

from .script_contract import check_script_contract
from .script_plan import check_script_plan
from .script_plan_consistency import check_script_plan_consistency


def validate_script_artifacts(output_dir: str) -> dict[str, list[str]]:
    plan_errors = check_script_plan(output_dir)
    contract_errors = check_script_contract(output_dir)
    consistency_errors = check_script_plan_consistency(output_dir)
    return {
        "plan": plan_errors,
        "contract": contract_errors,
        "consistency": consistency_errors,
        "all": [*plan_errors, *contract_errors, *consistency_errors],
    }


__all__ = [
    "check_script_contract",
    "check_script_plan",
    "check_script_plan_consistency",
    "validate_script_artifacts",
]
