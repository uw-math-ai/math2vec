"""
Tests for ``pipeline/run_benchmark_review.py``'s Lean probes (no Lean needed).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest import mock

import typeclass_mutate

_SCRIPT = Path(__file__).resolve().parents[1] / "pipeline" / "run_benchmark_review.py"


def _load_review_module():
    spec = importlib.util.spec_from_file_location("run_benchmark_review", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_install_probes_wraps_the_original_oracle_once() -> None:
    review = _load_review_module()
    calls: list[str] = []

    def fake_tc_compile(type_str: str) -> bool:
        calls.append(type_str)
        return True

    with mock.patch.object(typeclass_mutate, "_compile_lean", fake_tc_compile):
        first, second = review.LeanProbe(), review.LeanProbe()
        review.install_probes(first)
        review.install_probes(second)

        assert typeclass_mutate._compile_lean("P") is True

    # Only the latest probe records the call, and the real oracle ran once:
    # the second wrapper sits directly on the original, not on the first.
    assert calls == ["P"]
    assert len(second.calls) == 1
    assert first.calls == []
