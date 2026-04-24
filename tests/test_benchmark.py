"""Benchmarks for dirty-field tracking overhead.

Skipped by default. To run:

    uv run pytest tests/test_benchmark.py -m benchmark -s

The ``-s`` flag disables output capture so the result table is visible.

Two tests live here:

* ``test_benchmark_suite`` — in-process, compares plain Django vs this fork.
* ``test_benchmark_vs_upstream`` — 3-way comparison against upstream
  ``django-dirtyfields``. Spins up a throw-away venv via ``uv``, runs
  :mod:`tests._upstream_benchmark_runner` there, and merges its numbers with
  the in-process ones. First run is slow (venv setup); subsequent runs reuse
  the cached venv under ``/tmp/dirtyfields-bench-upstream``.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from django.db import models

from dirtyfields import DirtyFieldsMixin
from tests._benchmark_common import (
    ITERATIONS,
    N_INSTANCES,
    SCENARIOS,
    populate,
    run_paired,
)

pytestmark = [pytest.mark.benchmark, pytest.mark.django_db]


class PlainBenchmarkModel(models.Model):
    """Plain Django model without dirty tracking (baseline)."""

    char1 = models.CharField(max_length=100, default="")
    char2 = models.CharField(max_length=100, default="")
    char3 = models.CharField(max_length=100, default="")
    char4 = models.CharField(max_length=100, default="")
    text1 = models.TextField(default="")
    text2 = models.TextField(default="")
    int1 = models.IntegerField(default=0)
    int2 = models.IntegerField(default=0)
    int3 = models.IntegerField(default=0)
    float1 = models.FloatField(default=0.0)
    float2 = models.FloatField(default=0.0)
    decimal1 = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    decimal2 = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    bool1 = models.BooleanField(default=False)
    bool2 = models.BooleanField(default=False)
    bool3 = models.BooleanField(default=False)
    datetime1 = models.DateTimeField(null=True, default=None)
    datetime2 = models.DateTimeField(null=True, default=None)
    json1 = models.JSONField(default=dict)
    json2 = models.JSONField(default=dict)

    class Meta:
        app_label = "tests"


class DirtyBenchmarkModel(DirtyFieldsMixin, models.Model):
    """Model using DirtyFieldsMixin."""

    char1 = models.CharField(max_length=100, default="")
    char2 = models.CharField(max_length=100, default="")
    char3 = models.CharField(max_length=100, default="")
    char4 = models.CharField(max_length=100, default="")
    text1 = models.TextField(default="")
    text2 = models.TextField(default="")
    int1 = models.IntegerField(default=0)
    int2 = models.IntegerField(default=0)
    int3 = models.IntegerField(default=0)
    float1 = models.FloatField(default=0.0)
    float2 = models.FloatField(default=0.0)
    decimal1 = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    decimal2 = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    bool1 = models.BooleanField(default=False)
    bool2 = models.BooleanField(default=False)
    bool3 = models.BooleanField(default=False)
    datetime1 = models.DateTimeField(null=True, default=None)
    datetime2 = models.DateTimeField(null=True, default=None)
    json1 = models.JSONField(default=dict)
    json2 = models.JSONField(default=dict)

    class Meta:
        app_label = "tests"


@pytest.fixture
def populated_benchmark_db():
    """Populate both benchmark models with N_INSTANCES rows of diverse data."""
    populate(PlainBenchmarkModel)
    populate(DirtyBenchmarkModel)


def _run_in_process() -> dict[str, tuple[float, float]]:
    """Run all scenarios in-process, returning ``{key: (plain_ms, fork_ms)}``."""
    results: dict[str, tuple[float, float]] = {}
    for key, _name, func in SCENARIOS:
        results[key] = run_paired(
            lambda f=func: f(PlainBenchmarkModel),
            lambda f=func: f(DirtyBenchmarkModel),
        )
    return results


def _py() -> str:
    return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"


def test_benchmark_suite(populated_benchmark_db, capsys):
    """Run all benchmark scenarios and print a summary table (plain vs fork)."""
    results = _run_in_process()

    with capsys.disabled():
        print()
        print("=" * 85)
        print(f"Dirty Field Tracking Benchmark — Python {_py()}")
        print("=" * 85)
        print(f"Instances: {N_INSTANCES:,} | Fields: 20 | Iterations: {ITERATIONS}")
        print()
        print(f"{'Scenario':40} | {'Plain':>12} | {'Dirty':>12} | {'Overhead':>11}")
        print("-" * 85)
        for key, name, _func in SCENARIOS:
            plain_ms, dirty_ms = results[key]
            overhead = dirty_ms - plain_ms
            print(f"{name:40} | {plain_ms:9.1f} ms | {dirty_ms:9.1f} ms | {overhead:+8.1f} ms")
        print()


_UPSTREAM_VENV = Path("/tmp/dirtyfields-bench-upstream")  # noqa: S108


def _ensure_upstream_venv() -> Path:
    """Create (or reuse) a venv containing Django + upstream django-dirtyfields. Returns its python."""
    python = _UPSTREAM_VENV / "bin" / "python"
    marker = _UPSTREAM_VENV / ".installed"
    if python.exists() and marker.exists():
        return python

    if shutil.which("uv") is None:
        pytest.skip("`uv` not on PATH; can't set up the upstream comparison venv")

    if _UPSTREAM_VENV.exists():
        shutil.rmtree(_UPSTREAM_VENV)

    try:
        subprocess.run(  # noqa: S603
            ["uv", "venv", "--quiet", "--python", _py(), str(_UPSTREAM_VENV)],
            check=True,
        )
        subprocess.run(  # noqa: S603
            [
                "uv",
                "pip",
                "install",
                "--quiet",
                "--python",
                str(python),
                "Django",
                "django-dirtyfields",
            ],
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        pytest.skip(f"Failed to set up upstream venv: {exc}")

    marker.write_text("ok")
    return python


def _run_upstream(upstream_python: Path) -> dict[str, tuple[float, float]]:
    """Invoke the standalone upstream runner and parse its JSON output."""
    project_root = Path(__file__).parent.parent
    try:
        result = subprocess.run(  # noqa: S603
            [str(upstream_python), "-m", "tests._upstream_benchmark_runner"],
            capture_output=True,
            text=True,
            check=True,
            cwd=str(project_root),
        )
    except subprocess.CalledProcessError as exc:
        pytest.skip(f"Upstream benchmark runner failed:\n{exc.stderr}")

    data = json.loads(result.stdout)
    return {key: (row["plain_ms"], row["dirty_ms"]) for key, row in data["results"].items()}


def test_benchmark_vs_upstream(populated_benchmark_db, capsys):
    """3-way comparison: plain Django vs this fork vs upstream django-dirtyfields."""
    upstream_python = _ensure_upstream_venv()
    fork_results = _run_in_process()
    upstream_results = _run_upstream(upstream_python)

    with capsys.disabled():
        print()
        print("=" * 100)
        print(f"3-way Benchmark — Python {_py()}")
        print("=" * 100)
        print(f"Instances: {N_INSTANCES:,} | Fields: 20 | Iterations: {ITERATIONS}")
        print()
        print(
            f"{'Scenario':40} | {'Plain':>10} | {'Fork':>10} | {'Upstream':>10} | {'Fork Δ':>10} | {'Upstream Δ':>12}",
        )
        print("-" * 110)
        for key, name, _func in SCENARIOS:
            plain_ms, fork_ms = fork_results[key]
            _up_plain_ms, upstream_ms = upstream_results[key]
            fork_overhead = fork_ms - plain_ms
            upstream_overhead = upstream_ms - plain_ms
            print(
                f"{name:40} | {plain_ms:7.1f} ms | {fork_ms:7.1f} ms | {upstream_ms:7.1f} ms "
                f"| {fork_overhead:+7.1f} ms | {upstream_overhead:+9.1f} ms",
            )
        print()
