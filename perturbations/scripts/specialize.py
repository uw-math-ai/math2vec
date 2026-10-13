import os
import re
import subprocess

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

LEAN_SNIPPET = r"""
import Wiggle

lemma to_specialize (x : ℕ) : x = x := by
  specialize_state
  extract_goal
  sorry
"""

def main() -> None:
    tmp_path = os.path.join(PROJECT_DIR, "_specialize_tmp.lean")

    try:
        # Write temporary Lean file
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(LEAN_SNIPPET)

        # Run Lean
        result = subprocess.run(
            ["lake", "env", "lean", tmp_path],
            cwd=PROJECT_DIR,
            capture_output=True,
            text=True,
            timeout=300,
        )

        output = result.stdout + result.stderr

        # Look for the extracted theorem line
        m = re.search(r"^theorem .*extracted.*$", output, re.MULTILINE)
        if m:
            print("Specialized theorem:")
            print(m.group(0))
        else:
            print("No extracted theorem found. Raw Lean output:")
            print(output)

    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


if __name__ == "__main__":
    main()
