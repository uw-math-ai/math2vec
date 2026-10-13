import os
import re
import subprocess

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXTRACTED_THEOREM_RE = re.compile(r"^theorem .*extracted.*$", re.MULTILINE)


def run_lean_and_extract(lean_code: str, tmp_filename: str, label: str) -> None:
    tmp_path = os.path.join(PROJECT_DIR, tmp_filename)
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(lean_code)

        result = subprocess.run(
            ["lake", "env", "lean", tmp_path],
            cwd=PROJECT_DIR,
            capture_output=True,
            text=True,
            timeout=300,
        )

        output = result.stdout + result.stderr
        match = EXTRACTED_THEOREM_RE.search(output)
        if match:
            print(f"{label} goal:")
            print(match.group(0))
        else:
            print(f"Could not find extracted {label.lower()} goal. Raw Lean output:")
            print(output)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def _run_lean(code: str) -> str:
    tmp_path = os.path.join(PROJECT_DIR, "_generalize_api_tmp.lean")
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(code)
        result = subprocess.run(
            ["lake", "env", "lean", tmp_path],
            cwd=PROJECT_DIR,
            capture_output=True,
            text=True,
            timeout=300,
        )
        return result.stdout + result.stderr
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def _extract_goal_or_none(output: str) -> str | None:
    if "error:" in output:
        return None
    match = EXTRACTED_THEOREM_RE.search(output)
    return match.group(0) if match else None


def generalize_theorem(sig: str, type_str: str) -> str | None:
    output = _run_lean(
        f"import Wiggle\n\nexample : {type_str} := by\n"
        f"  drop_unused_hyp\n"
        f"  extract_goal\n"
        f"  sorry\n"
    )
    return _extract_goal_or_none(output)


def weaken_statement_by_strengthening_hypotheses_theorem(
    sig: str,
    type_str: str,
    hypothesis_prop: str,
) -> str | None:
    output = _run_lean(
        f"import Wiggle\n\nexample : {type_str} := by\n"
        f"  weaken_statement_by_strengthening_hypotheses ({hypothesis_prop})\n"
        f"  extract_goal\n"
        f"  sorry\n"
    )
    return _extract_goal_or_none(output)


def strengthen_statement_by_strengthening_conclusion_theorem(
    sig: str,
    type_str: str,
    stronger_conclusion: str,
) -> str | None:
    output = _run_lean(
        f"import Wiggle\n\nexample : {type_str} := by\n"
        f"  strengthen_statement_by_strengthening_conclusion ({stronger_conclusion})\n"
        f"  extract_goal\n"
        f"  sorry\n"
    )
    return _extract_goal_or_none(output)


def weaken_statement_by_weakening_conclusion_theorem(
    sig: str,
    type_str: str,
    weaker_conclusion: str,
) -> str | None:
    output = _run_lean(
        f"import Wiggle\n\nexample : {type_str} := by\n"
        f"  weaken_statement_by_weakening_conclusion ({weaker_conclusion})\n"
        f"  extract_goal\n"
        f"  sorry\n"
    )
    return _extract_goal_or_none(output)


LEAN_CODE = """\
import Wiggle

-- Drop unused Prop hypotheses from the statement.
lemma to_generalize (x : ℝ) (h_unused : True) :
    HasDerivAt Real.exp (Real.exp x) x := by
  drop_unused_hyp
  extract_goal
  sorry
"""


if __name__ == "__main__":
    run_lean_and_extract(
        LEAN_CODE,
        "_generalize_tmp.lean",
        "Generalized",
    )
