"""
Lean execution backend.

Wraps Lean elaboration in a single function, ``run_lean(code) -> str``, that
every higher-level Wiggle helper (``compile_lean``, ``extract_goal``,
``src/typeclass_mutate._run_lean``) goes through.

Two backends are available, selected by the ``WIGGLE_LEAN_BACKEND`` env var:

  * ``"server"`` (default) — keep one persistent ``lake env lean --server``
    process alive and reuse it via LSP. Amortises Mathlib's ~13s import cost
    across an arbitrary number of calls. See :mod:`wiggle.lean_server`.
  * ``"subprocess"`` — spawn a fresh ``lake env lean <file>`` per call. The
    original behaviour; kept for debugging and as an automatic fallback when
    the LSP server fails to start or crashes mid-call.

The string returned by ``run_lean`` is the same shape regardless of backend:
each diagnostic on its own block, prefixed by ``error:`` / ``warning:`` /
``info:`` followed by a newline and the message body. Existing parsers
(``compile_lean`` looks for the ``error:`` substring; ``extract_goal`` uses
a multi-line ``^theorem`` regex) work identically against either backend.
"""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
from functools import lru_cache
from pathlib import Path

__all__ = [
    "get_project_root",
    "run_lean",
    "compile_lean",
    "extract_goal",
]


@lru_cache(maxsize=1)
def get_project_root() -> Path:
    """Return the Lake project root (directory containing ``Wiggle.lean``).

    Walks up from this file. Cached because the answer never changes within a
    single process.
    """
    cur = Path(__file__).resolve()
    while cur != cur.parent:
        if (cur / "Wiggle.lean").exists():
            return cur
        cur = cur.parent
    raise RuntimeError(
        "Could not locate Wiggle.lean walking up from " + str(Path(__file__))
    )


def _current_backend() -> str:
    """Read ``WIGGLE_LEAN_BACKEND`` each call so tests can flip it at runtime."""
    return os.environ.get("WIGGLE_LEAN_BACKEND", "server").lower()


def run_lean(code: str, timeout: int = 300) -> str:
    """Elaborate ``code`` with Lean and return diagnostics as a string.

    Backend selection:

      * If ``WIGGLE_LEAN_BACKEND`` is ``"subprocess"``, always use the
        one-shot ``lake env lean <file>`` path.
      * Otherwise (``"server"`` or unset), try the persistent LSP server.
        On crash we restart it once and retry; if that also fails we fall
        through to the subprocess backend so the pipeline never hard-stops
        on a transient server issue.
    """
    if _current_backend() == "subprocess":
        return _run_lean_subprocess(code, timeout)

    # Imported lazily so that environments without the LSP module (or where
    # `lake env lean --server` is missing) can still use the subprocess path.
    from wiggle.lean_server import LeanServerCrash, get_server, reset_server

    try:
        srv = get_server()
        if srv is not None:
            return srv.run(code, timeout=float(timeout))
    except LeanServerCrash:
        reset_server()
        try:
            srv = get_server()
            if srv is not None:
                return srv.run(code, timeout=float(timeout))
        except LeanServerCrash:
            pass

    # Either the server never started or both attempts crashed. Subprocess
    # is the slow-but-correct safety net.
    return _run_lean_subprocess(code, timeout)


def _run_lean_subprocess(code: str, timeout: int) -> str:
    """One-shot ``lake env lean <file>`` backend.

    Each call writes a unique temp file under the project root so concurrent
    callers don't clobber each other. The file is removed on the way out.
    """
    project_root = get_project_root()
    fd, path = tempfile.mkstemp(
        prefix="_wiggle_", suffix=".lean", dir=project_root
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(code)
        result = subprocess.run(
            ["lake", "env", "lean", path],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.stdout + result.stderr
    finally:
        try:
            os.remove(path)
        except FileNotFoundError:
            pass


def compile_lean(variant_sig: str, variant_type: str) -> bool:
    """Return True iff ``example : <variant_type> := by sorry`` type-checks.

    Used as a validity oracle: we accept any well-formed Lean statement
    regardless of provability. ``variant_sig`` is currently unused but kept
    in the signature so the call site reads naturally.
    """
    del variant_sig  # reserved for future per-theorem context
    output = run_lean(
        "import Mathlib\n\nexample : " + variant_type + " := by sorry\n"
    )
    return "error:" not in output


# extract_goal scrapes lines that look like:
#   theorem wiggle_demo.extracted_1_1 {i j : N} : body := sorry
_EXTRACTED_RE = re.compile(r"^theorem .*extracted.*$", re.MULTILINE)


def extract_goal(tactic: str, type_str: str) -> tuple[str, str] | None:
    """Run a Lean snippet that applies ``tactic`` then ``extract_goal``.

    Returns ``(variant_sig, variant_type)`` if the goal extraction succeeded,
    otherwise ``None``.

    ``pp.funBinderTypes`` is essential, not cosmetic. Without it Lean prints
    ``∃ a b, a + b ≠ b + a``, dropping the binder types because they are
    recoverable *from the surrounding proof context*. Lifted out into a
    standalone ``example`` those types are no longer inferable and the
    statement fails to elaborate — so every ``negate`` variant was silently
    unusable. With the option on we get ``∃ (a : ℕ) (b : ℕ), …`` instead.

    The snippet shape:

        import Mathlib
        import Wiggle

        set_option pp.funBinderTypes true in
        example : <type_str> := by
          <tactic>
          extract_goal
          sorry
    """
    code = (
        "import Mathlib\n"
        "import Wiggle\n\n"
        "set_option pp.funBinderTypes true in\n"
        f"example : {type_str} := by\n"
        f"  {tactic}\n"
        "  extract_goal\n"
        "  sorry\n"
    )
    output = run_lean(code)
    m = _EXTRACTED_RE.search(output)
    if m is None:
        return None

    # The extracted theorem may span multiple lines when the goal is large
    # (e.g. after `unfold_defs`). Take everything from the `theorem …extracted`
    # match up to the `:= sorry` terminator, then collapse whitespace so the
    # rest of the pipeline sees a single-line statement. Matching only
    # ``m.group(0)`` (one line) would silently truncate such statements.
    tail = output[m.start():]
    end = tail.find(":= sorry")
    if end == -1:
        end = tail.find(":=")
    if end == -1:
        return None
    block = " ".join(tail[:end].split())  # collapse newlines/runs of spaces

    # Split `theorem <name> <binders> : <type>` at the first top-level colon
    # (depth-aware, skipping `::`), so a `:` inside binders/type doesn't fool us.
    depth = 0
    i = 0
    colon = -1
    while i < len(block):
        c = block[i]
        if c in "([{":
            depth += 1
        elif c in ")]}":
            depth = max(0, depth - 1)
        elif c == ":" and depth == 0:
            if i + 1 < len(block) and block[i + 1] == ":":
                i += 2
                continue
            colon = i
            break
        i += 1
    if colon == -1:
        return None
    variant_sig = block[:colon].strip()
    variant_type = block[colon + 1:].strip()
    if not variant_type:
        return None
    return variant_sig, variant_type
