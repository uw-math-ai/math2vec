# Tests

Unit tests for the Wiggle library. Two layers:

- **Fast suite** — pure Python, mocks Lean, runs in under 5 seconds. This is what CI / day-to-day development sees.
- **Live suite** — spawns `lake env lean --server` against real Mathlib. Gated behind an env var because each cold run takes 2-3 minutes.

## What's tested where

| File | Module under test | Touches Lean? |
|---|---|---|
| `conftest.py` | sys.path bootstrap so `import wiggle` works without installing | n/a |
| `test_registry.py` | `wiggle.registry` (perturbation dataclass, canonical list, name uniqueness, propagation-rule sanity) | no |
| `test_propagation.py` | `wiggle.propagation` (symbolic `is_true` / `compose_truth` over chains) | no |
| `test_de_morgan.py` | `wiggle.transforms.connectives.de_morgan_rewrite` (no-op detection, whitespace canonicalisation) | no (mocks `extract_goal`) |
| `test_inverse.py` | `wiggle.transforms.logical.inverse` (delegation, None propagation) | no (mocks `extract_goal`) |
| `test_quantifier_swap.py` | `wiggle.transforms.quantifiers.quantifier_swap` (∀∃→∃∀ rewrite, top-level comma scanning) | no (mocks `compile_lean`) |
| `test_lean_server.py` | `wiggle.lean_server` (LSP framing, handshake, didChange round-trip, fatal/timeout paths) | mostly no — one gated class spawns real Lean |
| `test_typeclass_mutate.py` | `src/typeclass_mutate.py` — **print-based smoke script, not pytest** | yes, slow (spawns Lean) |

`test_typeclass_mutate.py` is the odd one out. It runs at module-import time, calls real Lean, and prints results to stdout. It's a manual sanity check, not part of the mocked suite — `pytest tests/` collects it but the test body executes during import (typically taking a minute or two against a warm cache). If you want a deterministic CI run, exclude it explicitly:

```bash
python -m pytest tests/ --ignore=tests/test_typeclass_mutate.py
```

## How to run

```bash
# Fast suite (recommended for day-to-day):
python -m pytest tests/ --ignore=tests/test_typeclass_mutate.py

# Single file with verbose progress:
python -m pytest tests/test_lean_server.py -v

# Single test:
python -m pytest tests/test_lean_server.py::TestFormatDiagnostics::test_compile_lean_substring_check_works -v

# Live Lean (spawns lake env lean --server, ~2 min cold, ~10s warm):
WIGGLE_RUN_LEAN_INTEGRATION=1 python -m pytest tests/test_lean_server.py::TestRealLeanServer -v
```

Expected fast-suite output: `57 passed, 3 skipped`. The 3 skipped are the
`TestRealLeanServer` cases inside `test_lean_server.py`.

## The mocking pattern

Every fast perturbation test monkey-patches the *one* Lean entry-point it cares
about — usually `wiggle.lean_runner.run_lean`, sometimes `extract_goal` or
`compile_lean` if the wrapper does its own no-op detection on top. The pattern
from `tests/test_de_morgan.py` lines 18-23 is the canonical example:

```python
from unittest import mock
from wiggle.transforms import connectives

def test_de_morgan_calls_extract_goal_with_correct_tactic_name() -> None:
    fake = ("theorem ... extracted_1_1 : ¬a ∨ b", "¬a ∨ b")
    with mock.patch.object(connectives, "extract_goal", return_value=fake) as eg:
        out = connectives.de_morgan_rewrite("sig", "a → b")
    eg.assert_called_once_with("de_morgan_rewrite", "a → b")
    assert out == fake
```

Why this works: the wrapper functions in `src/wiggle/transforms/*.py` import
`extract_goal` / `compile_lean` at module scope, so patching the attribute on
the wrapper module replaces it for the duration of the `with` block. Each test
file does its own `sys.path.insert(0, ".../src")` plus a few mocks — there's no
global fixture magic.

For the LSP server tests in `test_lean_server.py`, the fake transport is more
elaborate (custom `_BlockingStream` + `_AutoRespondingStdin` classes that
auto-respond to JSON-RPC requests). That's still the same pattern at the
top — `mock.patch("subprocess.Popen", return_value=fake_proc)` swaps the
subprocess out for an in-memory fake — but the fake itself implements the
parts of `subprocess.Popen` the LSP reader thread actually touches.

## When to run the live suite

Flip `WIGGLE_RUN_LEAN_INTEGRATION=1` on whenever you:

- change `Wiggle.lean` (added/edited a tactic),
- change `src/wiggle/lean_server.py` or `src/wiggle/lean_runner.py`,
- bump `lean-toolchain` or pull a new Mathlib,
- merge a PR that touches any of the above.

It's slow (~2 min cold). Don't add it to a default `pytest` invocation.

## How to add a test for a new perturbation

Three steps. The transform lives under `src/wiggle/transforms/<layer>.py`:

1. **Create `tests/test_<perturbation>.py`** with the boilerplate header (same
   four lines every existing test uses):

   ```python
   import sys
   from pathlib import Path
   from unittest import mock

   sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
   ```

2. **Mock the Lean entry-point** the transform uses (`extract_goal` for tactic
   transforms; `compile_lean` for ones that do Python-side rewriting + Lean
   validity oracle) and write tests like the de_morgan ones above. Cover at
   minimum: happy path, Lean-failed (`None` return), and no-op detection.

3. **Verify it's hooked in** — `python -m pytest tests/test_<perturbation>.py -v`
   should run cleanly, and `python tests/test_registry.py` should still pass
   (the registry test checks that every name in `PERTURBATIONS` has a unique
   propagation rule).

You shouldn't need to register the transform in the registry from the test —
that's a separate `src/wiggle/registry.py` edit. The test file is purely about
exercising the function in isolation.

## Layout summary

```
tests/
├── conftest.py                 # sys.path bootstrap
├── test_registry.py            # registry shape + uniqueness
├── test_propagation.py         # truth propagation
├── test_lean_server.py         # LSP transport + format + (gated) live Lean
├── test_de_morgan.py           # connectives.de_morgan_rewrite wrapper
├── test_inverse.py             # logical.inverse wrapper
├── test_quantifier_swap.py     # quantifiers.quantifier_swap wrapper
├── test_typeclass_mutate.py    # MANUAL: print-based smoke script (spawns Lean)
├── test_shards.py              # ShardWriter atomicity + resume scan        (added in Phase 2)
└── test_parallel.py            # ProcessPoolExecutor orchestrator + drain   (added in Phase 2)
```
