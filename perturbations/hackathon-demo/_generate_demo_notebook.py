"""Generates demo.ipynb — run once, then delete this script."""
import json, uuid

def cell(cell_type, source, **extra):
    c = {"cell_type": cell_type, "id": str(uuid.uuid4())[:8], "metadata": {}, "source": source}
    if cell_type == "code":
        c.update({"outputs": [], "execution_count": None})
    c.update(extra)
    return c

md  = lambda src: cell("markdown", src)
cod = lambda src: cell("code", src)

# ---------------------------------------------------------------------------
# Cell sources — docstrings inside code cells are written as # comments to
# avoid triple-quote collision with the outer Python string delimiters.
# ---------------------------------------------------------------------------

CELL_TITLE = """\
# Lean Statement Perturbation — Demo Notebook

**Goal:** Apply all implemented wiggle-perturbations to a curated set of 10 Lean 4
theorems, then save every result (single and chained) as a structured JSONL dataset.

| Layer | What it does |
|---|---|
| **Lean tactics** | `negate`, `contrapose`, `converse`, `drop_unused_hyp` — run via `lake env lean` |
| **Typeclass mutations** | `tc_weaken_hyp`, `tc_strengthen_hyp`, `tc_weaken_conc`, `tc_strengthen_conc` — Python text substitution verified by Lean. Each name describes what happens to the typeclass at that position. |
| **Bound perturbations** | `flip_bound`, `bound_tighter` — regex-based inequality/constant manipulation |

Each output record tracks: original statement · perturbations applied (in order) ·
perturbed statement · `is_true` flag.

---"""

CELL_IMPORTS = """\
# ── Imports & configuration ───────────────────────────────────────────────────
import os, re, sys, json, subprocess
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter

# Walk up from the current working directory until we find Wiggle.lean (the
# Lake project root). This keeps the notebook portable across machines.
NOTEBOOK_DIR = Path.cwd()
PROJECT_DIR = NOTEBOOK_DIR
while PROJECT_DIR != PROJECT_DIR.parent and not (PROJECT_DIR / "Wiggle.lean").exists():
    PROJECT_DIR = PROJECT_DIR.parent

DEMO_DIR    = PROJECT_DIR / "hackathon-demo"
OUTPUT_FILE = DEMO_DIR / "demo_perturbations.jsonl"

# Put src/ on the path so we can `import typeclass_mutate, bounds`.
sys.path.insert(0, str(PROJECT_DIR / "src"))

print(f"Project root : {PROJECT_DIR}")
print(f"Demo dir     : {DEMO_DIR}")
print(f"Output file  : {OUTPUT_FILE}")
print(f"Lean project : {'OK' if (PROJECT_DIR / 'Wiggle.lean').exists() else 'NOT FOUND'}")"""

CELL_DATASET_MD = """\
## 1 · Toy Dataset — 10 Curated Theorems

Theorems are chosen to showcase every perturbation type:

* **Equalities** (`comm_ring_mul_comm`) — good for `negate`
* **iff / implications** (`nat_gcd_iff`, `nat_lt_cancel_left`, `field_mul_inv_cancel`) — `contrapose` / `converse`
* **Typeclass hypotheses** (`add_comm_monoid`, `comm_ring_mul_comm`, `linear_order_le_or_ge`) — `tc_*`
* **Typeclass conclusion** (`polynomial_is_domain`) — `tc_strengthen_conc` / `tc_weaken_conc`
* **Unused hypothesis** (`exp_deriv_unused_hyp`) — `drop_unused_hyp`
* **Numeric bound** (`nat_pos_of_ne_zero`, `nat_ge_one_of_pos`) — `flip_bound` / `bound_tighter`"""

CELL_THEOREMS = r"""# ── 10 curated Lean 4 theorems ───────────────────────────────────────────────
# Fields:
#   id          – snake_case identifier, key in output records
#   binders     – everything between the lemma name and ":" (vars + typeclasses)
#   body        – the Prop / Type after ":"  (what we perturb)
#   type_str    – full forall-quantified form used by typeclass_mutate functions
#   description – plain-English gloss
#   notes       – which perturbations are most interesting here

TOY_THEOREMS = [
    {
        "id": "nat_pos_of_ne_zero",
        "binders": "(n : ℕ)",
        "body": "n ≠ 0 → n > 0",
        "type_str": "∀ (n : ℕ), n ≠ 0 → n > 0",
        "description": "A nonzero natural number is positive.",
        "notes": "Has > 0: flip_bound gives n < 0 (False for ℕ); bound_tighter gives n > 1 (False for n=1).",
    },
    {
        "id": "nat_gcd_iff",
        "binders": "{i j : ℕ}",
        "body": "Nat.gcd i j = 0 ↔ i = 0 ∧ j = 0",
        "type_str": "∀ {i j : ℕ}, Nat.gcd i j = 0 ↔ i = 0 ∧ j = 0",
        "description": "gcd(i,j)=0 iff both arguments are zero.",
        "notes": "Iff form: contrapose and converse both well-defined.",
    },
    {
        "id": "add_comm_monoid",
        "binders": "{α : Type*} [inst : AddCommMonoid α] (a b : α)",
        "body": "a + b = b + a",
        "type_str": "∀ {α : Type*} [inst : AddCommMonoid α] (a b : α), a + b = b + a",
        "description": "Addition commutes in any AddCommMonoid.",
        "notes": "Hierarchy: AddMonoid <- AddCommMonoid <- AddCommGroup.",
    },
    {
        "id": "field_mul_inv_cancel",
        "binders": "{α : Type*} [inst : Field α] (a : α)",
        "body": "a ≠ 0 → a * a⁻\xb9 = 1",
        "type_str": "∀ {α : Type*} [inst : Field α] (a : α), a ≠ 0 → a * a⁻\xb9 = 1",
        "description": "In a field, a * a⁻\xb9 = 1 for any nonzero a.",
        "notes": "Implication. converse is unknown; Field can be generalised.",
    },
    {
        "id": "polynomial_is_domain",
        "binders": "{R : Type*} [inst : CommRing R] [inst_1 : IsDomain R]",
        "body": "IsDomain (Polynomial R)",
        "type_str": "∀ {R : Type*} [inst : CommRing R] [inst_1 : IsDomain R], IsDomain (Polynomial R)",
        "description": "Polynomials over an integral domain form an integral domain.",
        "notes": "IsDomain in conclusion: tc_strengthen_conc and tc_weaken_conc apply.",
    },
    {
        "id": "nat_lt_cancel_left",
        "binders": "{k : ℕ} (m n : ℕ)",
        "body": "k + m < k + n → m < n",
        "type_str": "∀ {k : ℕ} (m n : ℕ), k + m < k + n → m < n",
        "description": "Strict inequality preserved after cancelling left summand.",
        "notes": "Pure implication. contrapose gives (m >= n) -> (k+m >= k+n).",
    },
    {
        "id": "exp_deriv_unused_hyp",
        "binders": "(x : ℝ) (h_unused : True)",
        "body": "HasDerivAt Real.exp (Real.exp x) x",
        "type_str": "∀ (x : ℝ) (h_unused : True), HasDerivAt Real.exp (Real.exp x) x",
        "description": "Derivative of exp at x is exp(x). Has a dummy True hypothesis.",
        "notes": "drop_unused_hyp (clear_unused_props) removes h_unused. Canonical test case.",
    },
    {
        "id": "comm_ring_mul_comm",
        "binders": "{α : Type*} [inst : CommRing α] (a b : α)",
        "body": "a * b = b * a",
        "type_str": "∀ {α : Type*} [inst : CommRing α] (a b : α), a * b = b * a",
        "description": "Multiplication commutes in any commutative ring.",
        "notes": "Hierarchy: Ring <- CommRing. Statement holds even in CommSemiring.",
    },
    {
        "id": "nat_ge_one_of_pos",
        "binders": "(n : ℕ)",
        "body": "n > 0 → n ≥ 1",
        "type_str": "∀ (n : ℕ), n > 0 → n ≥ 1",
        "description": "A positive natural number is at least 1.",
        "notes": "Has ≥ 1 and > 0: flip_bound on ≥ gives ≤ 1 (False for n=2); bound_tighter on ≥ 1 gives ≥ 2 (False for n=1).",
    },
    {
        "id": "linear_order_le_or_ge",
        "binders": "{α : Type*} [inst : LinearOrder α] (a b : α)",
        "body": "a ≤ b ∨ b ≤ a",
        "type_str": "∀ {α : Type*} [inst : LinearOrder α] (a b : α), a ≤ b ∨ b ≤ a",
        "description": "Any two elements of a linear order are comparable.",
        "notes": "Disjunction. negate gives not(a<=b) and not(b<=a), which is false.",
    },
]

assert len(TOY_THEOREMS) == 10, "Expected exactly 10 theorems"
print(f"Loaded {len(TOY_THEOREMS)} theorems:\n")
for t in TOY_THEOREMS:
    print(f"  [{t['id']:<30s}]  {t['body'][:55]}")"""

CELL_RUNNER_MD = """\
## 2 · Lean Runner Utilities

All tactic-based perturbations work by:
1. Writing a small Lean snippet to a temp file
2. Running `lake env lean <file>` in the project root
3. Parsing the `theorem ... _extracted ...` line that `extract_goal` emits

`make_lemma` builds the snippet; `run_lean` executes it; `extract_theorem` parses the output."""

CELL_RUNNER = r"""# ── Lean runner utilities ─────────────────────────────────────────────────────

# extract_goal can emit MULTI-LINE theorems; match just the start of the line.
_EXTRACTED_START_RE = re.compile(r"^theorem \S*extracted\S*", re.MULTILINE)


def run_lean(lean_code: str, tmp_name: str = "_demo_tmp.lean", timeout: int = 120) -> str:
    # Write lean_code to a temp file, invoke lake env lean, return combined output.
    # Returns the string "TIMEOUT" if Lean takes longer than timeout seconds.
    tmp_path = PROJECT_DIR / tmp_name
    try:
        tmp_path.write_text(lean_code, encoding="utf-8")
        result = subprocess.run(
            ["lake", "env", "lean", str(tmp_path)],
            cwd=PROJECT_DIR,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return "TIMEOUT"
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def extract_theorem(output: str) -> str | None:
    # Return a single-line theorem string, or None on error / not applicable.
    # Handles multi-line extract_goal output: collects lines until ":= sorry".
    if "error:" in output or "TIMEOUT" in output:
        return None
    m = _EXTRACTED_START_RE.search(output)
    if not m:
        return None
    rest = output[m.start():]
    end_m = re.search(r":=\s*(?:sorry|by)\b", rest)
    if end_m:
        raw = rest[: end_m.end()].strip()
    else:
        raw = rest.split("\n")[0]
    # Collapse newlines/indentation into a single space
    return re.sub(r"\s+", " ", raw)


def make_lemma(theorem: dict, tactic_body: str) -> str:
    # Build the minimal Lean snippet that applies tactic_body then extract_goal.
    return (
        "import Wiggle\n\n"
        f"lemma wiggle_demo {theorem['binders']} : {theorem['body']} := by\n"
        f"  {tactic_body}\n"
        f"  extract_goal\n"
        f"  sorry\n"
    )


def normalize_statement(stmt: str | None) -> str | None:
    # Tactic perturbations emit extract_goal output of the form:
    #   theorem wiggle_demo.extracted_1_1 {binders} : <type> := sorry
    # Typeclass and bounds perturbations already emit a clean type string.
    # This function strips the wrapper so every perturbed_statement is a bare type.
    if stmt is None or not re.match(r"^theorem\s+\S*extracted", stmt):
        return stmt
    # Strip ":= sorry/by ..." suffix
    m = re.match(r"^theorem\s+\S+\s*(.*?)\s*:=\s*(?:sorry|by)\b", stmt, re.DOTALL)
    if not m:
        return stmt
    sig_part = m.group(1).strip()
    # Find first top-level ":" that is not "::" (namespace separator)
    depth = 0
    i = 0
    while i < len(sig_part):
        c = sig_part[i]
        if c in "({[":
            depth += 1
        elif c in ")}]":
            depth = max(0, depth - 1)
        elif c == ":" and depth == 0:
            if i + 1 < len(sig_part) and sig_part[i + 1] == ":":
                i += 2
                continue
            binders = sig_part[:i].strip()
            body    = re.sub(r"\s+", " ", sig_part[i + 1:].strip())
            return (f"∀ {binders}, {body}" if binders else body)
        i += 1
    return re.sub(r"\s+", " ", sig_part)


# Confirm lake is available
_check = subprocess.run(["lake", "--version"], capture_output=True, text=True)
print("lake:", _check.stdout.strip() or _check.stderr.strip())"""

CELL_PERTURB_MD = """\
## 3 · Perturbation Functions

### Return convention
Every perturbation function accepts a `theorem` dict and returns:
```python
{"perturbed_statement": str | None, "is_true": bool | str}
```

### `is_true` semantics

| Perturbation | `is_true` | Reason |
|---|---|---|
| `negate` | `False` | Negation of a true theorem |
| `contrapose` | `True` | Logically equivalent to original |
| `converse` | `"unknown"` | May or may not hold |
| `drop_unused_hyp` | `True` | Removing unused hyps keeps provability |
| `tc_weaken_hyp` | `"unknown"` | Weaker TC in hypothesis = stronger statement (must hold for more types); original proof no longer applies |
| `tc_strengthen_hyp` | `True` | Stronger TC in hypothesis = narrower domain; conclusion still holds for those types |
| `tc_strengthen_conc` | `"unknown"` | Claiming more — may fail |
| `tc_weaken_conc` | `True` | Claiming less — follows from original |
| `flip_bound` | `"unknown"` | Flipping `<`/`>` or `≤`/`≥` changes meaning; may or may not hold |
| `bound_tighter` | `"unknown"` | Tightening the numeric bound; may falsify or preserve truth |"""

CELL_TACTIC_PERTURBS = r"""# ── Lean-tactic perturbations ─────────────────────────────────────────────────
# Each function calls a Wiggle tactic through lake env lean.

def perturb_negate(theorem: dict) -> dict:
    # Negate the entire goal (not P). Result is mathematically FALSE.
    lean = make_lemma(theorem, "negate_state")
    output = run_lean(lean)
    stmt = extract_theorem(output)
    return {"perturbed_statement": stmt, "is_true": False}


def perturb_contrapose(theorem: dict) -> dict:
    # Take the contrapositive (not Q -> not P). Logically EQUIVALENT, still True.
    # Returns None for bare equalities where contrapose is not applicable.
    lean = make_lemma(theorem, "contrapositive")
    output = run_lean(lean)
    stmt = extract_theorem(output)
    return {"perturbed_statement": stmt, "is_true": True if stmt else "unknown"}


def perturb_converse(theorem: dict) -> dict:
    # Take the converse (Q -> P). Truth is UNKNOWN in general.
    lean = make_lemma(theorem, "converse")
    output = run_lean(lean)
    stmt = extract_theorem(output)
    return {"perturbed_statement": stmt, "is_true": "unknown"}


def perturb_drop_unused_hyp(theorem: dict) -> dict:
    # Remove all unused Prop-valued hypotheses (clear_unused_props tactic).
    # Classic case: theorem with a dummy h : True. Result is still True.
    lean = make_lemma(theorem, "drop_unused_hyp")
    output = run_lean(lean)
    stmt = extract_theorem(output)
    return {"perturbed_statement": stmt, "is_true": True if stmt else "unknown"}


print("Lean-tactic perturbation functions defined.")"""

CELL_TC_PERTURBS = r"""# ── Typeclass-level perturbations ─────────────────────────────────────────────
# Names describe what happens to the TYPECLASS at that position.
# These use typeclass_mutate: Python text substitution guided by the Mathlib
# typeclass hierarchy, then Lean compilation to confirm type-checking.

from typeclass_mutate import (
    weaken_hypothesis_typeclass     as _tc_weaken_hyp,
    strengthen_hypothesis_typeclass as _tc_strengthen_hyp,
    strengthen_conclusion_typeclass as _tc_strengthen_conc,
    weaken_conclusion_typeclass     as _tc_weaken_conc,
)


def perturb_tc_weaken_hyp(theorem: dict) -> dict:
    # Replace typeclass in hypothesis with a WEAKER parent class.
    # Example: [AddCommMonoid a] -> [AddMonoid a]
    # Less restrictive hypothesis = more general claim; the variant must
    # hold for a STRICTLY LARGER class of types. The original proof used
    # the stronger structure (e.g. commutativity) and no longer applies,
    # so the variant may be true or false.
    result = _tc_weaken_hyp(theorem["id"], theorem["type_str"])
    stmt = result[1] if result else None
    return {"perturbed_statement": stmt, "is_true": "unknown"}


def perturb_tc_strengthen_hyp(theorem: dict) -> dict:
    # Replace typeclass in hypothesis with a STRONGER child class.
    # Example: [AddCommMonoid a] -> [AddCommGroup a]
    # More restrictive hypothesis = narrower domain. Any type satisfying
    # the stronger class also satisfied the original, so the conclusion
    # still holds.
    result = _tc_strengthen_hyp(theorem["id"], theorem["type_str"])
    stmt = result[1] if result else None
    return {"perturbed_statement": stmt, "is_true": True if stmt else "unknown"}


def perturb_tc_strengthen_conc(theorem: dict) -> dict:
    # Replace typeclass in conclusion with a STRONGER child class.
    # Example: IsDomain -> EuclideanDomain in the conclusion.
    # The variant claims a stronger structural property and may not be true.
    result = _tc_strengthen_conc(theorem["id"], theorem["type_str"])
    stmt = result[1] if result else None
    return {"perturbed_statement": stmt, "is_true": "unknown"}


def perturb_tc_weaken_conc(theorem: dict) -> dict:
    # Replace typeclass in conclusion with a WEAKER parent class.
    # Example: IsDomain -> Nontrivial in the conclusion.
    # The variant claims a weaker property; follows from the original by
    # definition of the hierarchy.
    result = _tc_weaken_conc(theorem["id"], theorem["type_str"])
    stmt = result[1] if result else None
    return {"perturbed_statement": stmt, "is_true": True if stmt else "unknown"}


print("Typeclass perturbation functions defined.")"""

CELL_BOUNDS_PERTURBS = r"""# ── Bound perturbations ────────────────────────────────────────────────────────
# These use bounds.py: pure regex substitution on the type_str, no Lean calls.
# flip_bound   – reverses the first inequality found (< ↔ >, ≤ ↔ ≥)
# bound_tighter – shifts the first numeric literal by ±1 in the tighter direction
#                 (≥n → ≥n+1, ≤n → ≤n-1, >n → >n+1, <n → <n-1)
#
# is_true = "unknown" for both: flip_bound on `a ≤ b ∨ b ≤ a` gives a *True*
# result (≥ is equivalent here), so we cannot blanket-label these False.

from bounds import flip_bound, perturb_bound


def perturb_flip_bound(theorem: dict) -> dict:
    # Flip the direction of the first inequality in type_str.
    result = flip_bound(theorem["id"], theorem["type_str"])
    stmt = result[1] if result else None
    return {"perturbed_statement": stmt, "is_true": "unknown"}


def perturb_bound_tighter(theorem: dict) -> dict:
    # Tighten the first numeric bound by ±1.
    result = perturb_bound(theorem["id"], theorem["type_str"])
    stmt = result[1] if result else None
    return {"perturbed_statement": stmt, "is_true": "unknown"}


print("Bound perturbation functions defined.")"""

CELL_REGISTRY_MD = """\
## 4 · Perturbation Registry

A single list-of-dicts is the single source of truth for all perturbation types.
**To add a new perturbation:** append one entry here — no other code needs to change."""

CELL_REGISTRY = r"""# ── Perturbation registry ─────────────────────────────────────────────────────
# Each entry:
#   name        – identifier used in output JSON records
#   fn          – callable(theorem: dict) -> {"perturbed_statement", "is_true"}
#   description – one-line human-readable description

PERTURBATION_REGISTRY = [
    # ── Lean-tactic perturbations ──────────────────────────────────────────────
    {
        "name": "negate",
        "fn": perturb_negate,
        "description": "Negate the full statement (not P). Always False.",
    },
    {
        "name": "contrapose",
        "fn": perturb_contrapose,
        "description": "Contrapositive (not Q -> not P). Logically equivalent, True.",
    },
    {
        "name": "converse",
        "fn": perturb_converse,
        "description": "Converse (Q -> P). Truth unknown.",
    },
    {
        "name": "drop_unused_hyp",
        "fn": perturb_drop_unused_hyp,
        "description": "Remove unused Prop hypotheses. Statement stays True.",
    },
    # ── Typeclass-level perturbations ──────────────────────────────────────────
    # Names describe what happens to the typeclass at that position.
    {
        "name": "tc_weaken_hyp",
        "fn": perturb_tc_weaken_hyp,
        "description": "Weaken typeclass in hypothesis (parent class). Unknown.",
    },
    {
        "name": "tc_strengthen_hyp",
        "fn": perturb_tc_strengthen_hyp,
        "description": "Strengthen typeclass in hypothesis (child class). True.",
    },
    {
        "name": "tc_strengthen_conc",
        "fn": perturb_tc_strengthen_conc,
        "description": "Strengthen typeclass in conclusion (child class). Unknown.",
    },
    {
        "name": "tc_weaken_conc",
        "fn": perturb_tc_weaken_conc,
        "description": "Weaken typeclass in conclusion (parent class). True.",
    },
    # ── Bound perturbations ────────────────────────────────────────────────────
    {
        "name": "flip_bound",
        "fn": perturb_flip_bound,
        "description": "Flip inequality direction (< <-> >, <= <-> >=). Truth unknown.",
    },
    {
        "name": "bound_tighter",
        "fn": perturb_bound_tighter,
        "description": "Tighten numeric bound by +-1 (>=n->>=n+1, <=n-><=n-1). Truth unknown.",
    },
]

print(f"Registry: {len(PERTURBATION_REGISTRY)} perturbation types (8 original + 2 bounds)\n")
print(f"  {'Name':<25}  Description")
print(f"  {'-'*25}  {'-'*50}")
for p in PERTURBATION_REGISTRY:
    print(f"  {p['name']:<25}  {p['description']}")"""

CELL_SINGLE_MD = """\
## 5 · Single Perturbations — All Theorems × All Perturbation Types

Runs every registered perturbation on every theorem.
Perturbations that do not apply (e.g. `contrapose` on a bare equality)
return `perturbed_statement: null` — this is recorded, not an error.

Expected runtime: ~5–30 s per Lean call × 80 calls = several minutes."""

CELL_SINGLE_RUN = r"""# ── Apply one named perturbation to one theorem ──────────────────────────────

def apply_perturbation(theorem: dict, perturbation_name: str) -> dict:
    # Look up the perturbation, call it, return a fully-formatted output record.
    entry = next(
        (p for p in PERTURBATION_REGISTRY if p["name"] == perturbation_name), None
    )
    if entry is None:
        raise ValueError(f"Unknown perturbation: {perturbation_name!r}")

    result = entry["fn"](theorem)

    return {
        "source_id":                 theorem["id"],
        "original_statement":        theorem["body"],
        "original_type_str":         theorem["type_str"],
        "perturbations_applied":     [perturbation_name],
        "perturbed_statement":       normalize_statement(result["perturbed_statement"]),
        "is_true":                   result["is_true"],
        "perturbation_description":  entry["description"],
        "timestamp":                 datetime.now(timezone.utc).isoformat(),
    }


# ── Run all 10 theorems x 8 perturbations ────────────────────────────────────
print("Running single perturbations on all 10 theorems...\n")
single_results = []

for theorem in TOY_THEOREMS:
    print(f"\n{'─'*65}")
    print(f"  [{theorem['id']}]  {theorem['body']}")
    for pert in PERTURBATION_REGISTRY:
        print(f"  {pert['name']:<25}", end="", flush=True)
        record = apply_perturbation(theorem, pert["name"])
        single_results.append(record)
        stmt = record["perturbed_statement"]
        if stmt:
            preview = stmt[:60] + "..." if len(stmt) > 60 else stmt
            print(f"  is_true={str(record['is_true']):<8}  {preview}")
        else:
            print("  (not applicable / no output)")

print(f"\n{'='*65}")
print(f"Single-perturbation pass complete: {len(single_results)} records")"""

CELL_CHAIN_MD = """\
## 6 · Chained (Combination) Perturbations

Each chain applies perturbations in sequence: the output of step *i* becomes the
input to step *i+1*. If a step returns `None` the chain is marked `chain_broken`.

| Chain | Expected behaviour |
|---|---|
| `negate -> negate` | Double negation — recovers something close to original |
| `drop_unused_hyp -> negate` | Negate a more general form |
| `tc_weaken_hyp -> tc_weaken_hyp` | Two steps up the typeclass hierarchy |
| `tc_weaken_hyp -> negate` | Generalise then negate — always False |
| `contrapose -> converse` | Gives the *inverse* (not P -> not Q) |
| `converse -> negate` | Negate the converse |
| `flip_bound -> negate` | Flip inequality then negate — False by dominance rule |
| `bound_tighter -> negate` | Tighten bound then negate — False by dominance rule |

> **`is_true` composition rule:** `False + False = unknown` (two false-labelled steps
> may cancel, e.g. `negate -> negate` recovers something close to the original).
> Otherwise `False` dominates `unknown` dominates `True`. Semantic truth verification
> for chains requires a theorem prover and is left as a future enhancement."""

CELL_CHAIN_RUN = r"""# ── Parse an extracted Lean theorem string ────────────────────────────────────
# extract_goal emits lines like:
#   theorem wiggle_demo.extracted_1_1 {i j : N} : body := by exact?
# parse_extracted_lean splits that into (binders, body) so the next chained
# perturbation receives a well-formed theorem dict instead of a raw string.

def parse_extracted_lean(extracted: str) -> dict | None:
    # Remove ":= ..." suffix first
    m = re.match(r"^(theorem\s+\S+.*?)\s*:=", extracted, re.DOTALL)
    if not m:
        return None
    before_assign = m.group(1)
    # Strip "theorem <name>" prefix, leaving optional binders + ":" + body
    m2 = re.match(r"^theorem\s+\S+\s*(.*)", before_assign, re.DOTALL)
    if not m2:
        return None
    sig_part = m2.group(1).strip()  # e.g. "{i j : N} : ∃ i j, ..."

    # Walk sig_part to find the first top-level ":" (not "::")
    depth = 0
    i = 0
    colon_pos = -1
    while i < len(sig_part):
        c = sig_part[i]
        if c in "({[":   depth += 1
        elif c in ")}]": depth = max(0, depth - 1)
        elif c == ":" and depth == 0:
            if i + 1 < len(sig_part) and sig_part[i + 1] == ":":
                i += 2   # skip "::" (namespace separator)
                continue
            colon_pos = i
            break
        i += 1

    if colon_pos == -1:
        binders, body = "", sig_part
    else:
        binders = sig_part[:colon_pos].strip()
        body    = sig_part[colon_pos + 1:].strip()

    # Reconstruct a ∀-type for typeclass_mutate compatibility
    type_str = f"∀ {binders}, {body}" if binders else body
    return {"binders": binders, "body": body, "type_str": type_str}


# ── Apply a chain of perturbations ────────────────────────────────────────────

def _compose_truth(so_far: bool | str, new_val: bool | str) -> bool | str:
    # False + False = unknown: two consecutive false-labelled steps may cancel
    # (e.g. negate -> negate recovers a statement close to the original).
    # Otherwise False dominates, then unknown dominates True.
    if so_far is False and new_val is False:
        return "unknown"
    if so_far is False or new_val is False:
        return False
    if so_far == "unknown" or new_val == "unknown":
        return "unknown"
    return True


def apply_chain(theorem: dict, perturbation_names: list[str]) -> dict:
    # Apply perturbation_names[0], feed its output to [1], etc.
    # Uses parse_extracted_lean to properly separate binders from body when
    # the previous step was a tactic-based perturbation.
    current = dict(theorem)
    is_true_acc: bool | str = True

    for step_i, name in enumerate(perturbation_names):
        entry = next((p for p in PERTURBATION_REGISTRY if p["name"] == name), None)
        if entry is None:
            raise ValueError(f"Unknown perturbation: {name!r}")

        result = entry["fn"](current)

        if result["perturbed_statement"] is None:
            return {
                "source_id":                 theorem["id"],
                "original_statement":        theorem["body"],
                "original_type_str":         theorem["type_str"],
                "perturbations_applied":     perturbation_names[: step_i + 1],
                "perturbed_statement":       None,
                "is_true":                   "chain_broken",
                "perturbation_description":  f"Broke at step {step_i + 1}: {name}",
                "timestamp":                 datetime.now(timezone.utc).isoformat(),
            }

        stmt = result["perturbed_statement"]

        # Tactic perturbations emit "theorem ... := by exact?" — parse it.
        # Typeclass mutations emit a clean "∀ ..." type string — use directly.
        parsed = parse_extracted_lean(stmt)
        if parsed:
            current = {**theorem, **parsed}         # inherit id/description, override statement
        else:
            clean = normalize_statement(stmt)
            current = {**theorem, "body": clean, "type_str": clean, "binders": ""}

        is_true_acc = _compose_truth(is_true_acc, result["is_true"])

    return {
        "source_id":                 theorem["id"],
        "original_statement":        theorem["body"],
        "original_type_str":         theorem["type_str"],
        "perturbations_applied":     perturbation_names,
        "perturbed_statement":       normalize_statement(current["body"]),
        "is_true":                   is_true_acc,
        "perturbation_description":  " -> ".join(perturbation_names),
        "timestamp":                 datetime.now(timezone.utc).isoformat(),
    }


# ── Chains to run ──────────────────────────────────────────────────────────────
CHAINS = [
    ["negate", "negate"],
    ["drop_unused_hyp", "negate"],
    ["tc_weaken_hyp", "tc_weaken_hyp"],
    ["tc_weaken_hyp", "negate"],
    ["contrapose", "converse"],
    ["converse", "negate"],
    # Bounds chains
    ["flip_bound", "negate"],
    ["bound_tighter", "negate"],
]

print(f"Running {len(CHAINS)} chains x {len(TOY_THEOREMS)} theorems...\n")
chain_results = []

for theorem in TOY_THEOREMS:
    print(f"\n{'─'*65}")
    print(f"  [{theorem['id']}]  {theorem['body'][:50]}")
    for chain in CHAINS:
        label = " -> ".join(chain)
        print(f"  [{label:<38}]", end="", flush=True)
        record = apply_chain(theorem, chain)
        chain_results.append(record)
        stmt = record["perturbed_statement"]
        if stmt:
            preview = stmt[:55] + "..." if len(stmt) > 55 else stmt
            print(f"  is_true={str(record['is_true']):<8}  {preview}")
        else:
            print(f"  BROKEN at step {len(record['perturbations_applied'])}")

print(f"\n{'='*65}")
print(f"Chain pass complete: {len(chain_results)} records")"""

CELL_SAVE_MD = """\
## 7 · Save Output & Summary

All records (single + chained) are written to `demo_perturbations.jsonl`.

### Output record schema
```json
{
  "source_id":                "nat_add_comm",
  "original_statement":       "m + n = n + m",
  "original_type_str":        "forall {m n : N}, m + n = n + m",
  "perturbations_applied":    ["negate"],
  "perturbed_statement":      "theorem wiggle_demo_extracted ...",
  "is_true":                  false,
  "perturbation_description": "Negate the full statement (not P). Always False.",
  "timestamp":                "2026-05-10T..."
}
```"""

CELL_SAVE = r"""# ── Combine all records and write JSONL ──────────────────────────────────────

all_results = single_results + chain_results

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    for record in all_results:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

print(f"Wrote {len(all_results)} records to {OUTPUT_FILE}\n")

# ── Summary ────────────────────────────────────────────────────────────────────
produced = [r for r in all_results if r["perturbed_statement"] is not None]
failed   = [r for r in all_results if r["perturbed_statement"] is None]
truth_counts = Counter(r["is_true"] for r in produced)

print(f"{'='*65}")
print(f"  Total records             : {len(all_results)}")
print(f"  Produced output           : {len(produced)}  ({100*len(produced)//len(all_results)}%)")
print(f"  No output (not applicable): {len(failed)}")
print()
print("  Truth-status breakdown (produced records):")
for status in [True, False, "unknown", "chain_broken"]:
    n = truth_counts.get(status, 0)
    if n:
        print(f"    {str(status):<14}  {n:3d} records")
print()

# Show five sample records with output
print(f"{'='*65}")
print("  Sample records (first 5 with output):\n")
for r in produced[:5]:
    chain_label = " -> ".join(r["perturbations_applied"])
    print(f"  [{r['source_id']}]  +  [{chain_label}]")
    print(f"    original  : {r['original_statement'][:65]}")
    stmt = r["perturbed_statement"]
    print(f"    perturbed : {stmt[:65]}" + ("..." if len(stmt) > 65 else ""))
    print(f"    is_true   : {r['is_true']}")
    print()"""

# ---------------------------------------------------------------------------
# Assemble notebook
# ---------------------------------------------------------------------------

cells = [
    md(CELL_TITLE),
    cod(CELL_IMPORTS),
    md(CELL_DATASET_MD),
    cod(CELL_THEOREMS),
    md(CELL_RUNNER_MD),
    cod(CELL_RUNNER),
    md(CELL_PERTURB_MD),
    cod(CELL_TACTIC_PERTURBS),
    cod(CELL_TC_PERTURBS),
    cod(CELL_BOUNDS_PERTURBS),
    md(CELL_REGISTRY_MD),
    cod(CELL_REGISTRY),
    md(CELL_SINGLE_MD),
    cod(CELL_SINGLE_RUN),
    md(CELL_CHAIN_MD),
    cod(CELL_CHAIN_RUN),
    md(CELL_SAVE_MD),
    cod(CELL_SAVE),
]

notebook = {
    "nbformat": 4,
    "nbformat_minor": 5,
    "metadata": {
        "kernelspec": {
            "display_name": "Python 3",
            "language": "python",
            "name": "python3",
        },
        "language_info": {"name": "python", "version": "3.14.4"},
    },
    "cells": cells,
}

from pathlib import Path
out = Path(__file__).parent / "demo.ipynb"
out.write_text(json.dumps(notebook, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"Wrote {out}  ({len(cells)} cells, {out.stat().st_size} bytes)")
