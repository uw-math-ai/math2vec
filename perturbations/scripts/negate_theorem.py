import subprocess  # Runs external commands, here Lean through Lake.
import os  # Provides filesystem path helpers and file cleanup checks.
import re  # Lets the script search the Lean output with a regex.
import tempfile  # Imported for temporary-file utilities, though not used below.

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # Lake project root (one level up from scripts/).

LEAN_CODE = """\
import Wiggle

-- Nat.gcd_eq_zero_iffp: negated
lemma to_negate {i j : Nat} : gcd i j = 0 ↔ i = 0 ∧ j = 0 := by
  negate_state
  extract_goal
  sorry
"""  # Lean source that the script writes to a temporary file and executes.

tmp_path = os.path.join(PROJECT_DIR, "_negate_tmp.lean")  # Temporary Lean file path.
try:  # Ensure the temporary file is removed even if Lean fails.
    with open(tmp_path, "w", encoding="utf-8") as f:  # Create the temporary Lean file.
        f.write(LEAN_CODE)  # Write the Lean snippet into that file.

    result = subprocess.run(  # Invoke Lean in the project environment.
        ["lake", "env", "lean", tmp_path],  # Run Lean on the temporary file.
        cwd=PROJECT_DIR,  # Run from the project root so imports resolve correctly.
        capture_output=True,  # Collect stdout and stderr instead of printing directly.
        text=True,  # Decode the captured output as text.
        timeout=300,  # Stop the process if it takes longer than five minutes.
    )

    output = result.stdout + result.stderr  # Combine Lean's standard output and error streams.

    # extract_goal emits a "Try this:" info message with the negated goal
    match = re.search(r"^theorem .*extracted.*$", output, re.MULTILINE)  # Look for the extracted theorem line.
    if match:  # If the regex found a matching negated goal.
        print("Negated goal:")  # Print a label for the extracted result.
        print(match.group(0))  # Print the exact matched line.
    else:  # If the expected line was not found in the Lean output.
        print("Could not find extracted goal. Raw Lean output:")  # Explain the fallback output.
        print(output)  # Print the full Lean output for debugging.
finally:  # Always clean up the temporary file.
    if os.path.exists(tmp_path):  # Check whether the temporary file still exists.
        os.remove(tmp_path)  # Delete the temporary Lean file.

