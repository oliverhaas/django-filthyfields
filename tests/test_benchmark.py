"""Benchmarks for dirty-field tracking overhead.

Skipped by default. To run:

    uv run pytest tests/test_benchmark.py -m benchmark -s

The ``-s`` flag disables output capture so the result table is visible.
"""

from __future__ import annotations

import gc
import statistics
import sys
import time
from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

import pytest
from django.db import models

from dirtyfields import DirtyFieldsMixin

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

pytestmark = [pytest.mark.benchmark, pytest.mark.django_db]

N_INSTANCES = 10_000
ITERATIONS = 5


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


@contextmanager
def _timer() -> Iterator[dict[str, float]]:
    """Context manager that yields elapsed time in seconds."""
    gc.collect()
    gc.disable()
    try:
        start = time.perf_counter()
        result = {"elapsed": 0.0}
        yield result
        result["elapsed"] = time.perf_counter() - start
    finally:
        gc.enable()


def _run_paired(func_plain: Callable[[], None], func_dirty: Callable[[], None]) -> tuple[float, float]:
    """Run two benchmark functions interleaved to avoid caching bias. Returns (plain_ms, dirty_ms)."""
    for _ in range(2):
        func_plain()
        func_dirty()

    times_plain: list[float] = []
    times_dirty: list[float] = []
    for _ in range(ITERATIONS):
        with _timer() as t:
            func_plain()
        times_plain.append(t["elapsed"])
        with _timer() as t:
            func_dirty()
        times_dirty.append(t["elapsed"])

    return statistics.mean(times_plain) * 1000, statistics.mean(times_dirty) * 1000


@pytest.fixture
def populated_benchmark_db():
    """Populate both benchmark models with N_INSTANCES rows of diverse data."""
    base_dt = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
    for model_cls in (PlainBenchmarkModel, DirtyBenchmarkModel):
        model_cls.objects.bulk_create(
            [
                model_cls(
                    char1=f"val{i}",
                    char2=f"val{i}",
                    char3=f"val{i}",
                    char4=f"val{i}",
                    text1=f"long text value {i}",
                    text2=f"another text {i}",
                    int1=i,
                    int2=i * 2,
                    int3=i * 3,
                    float1=i * 1.5,
                    float2=i * 2.5,
                    decimal1=Decimal(f"{i}.99"),
                    decimal2=Decimal(f"{i * 2}.50"),
                    bool1=i % 2 == 0,
                    bool2=i % 3 == 0,
                    bool3=i % 5 == 0,
                    datetime1=base_dt,
                    datetime2=base_dt,
                    json1={"key": i},
                    json2={"nested": {"value": i}},
                )
                for i in range(N_INSTANCES)
            ],
        )


def _bench_only1_read1(model_cls: type[models.Model]) -> None:
    for inst in model_cls.objects.only("char1"):
        _ = inst.char1


def _bench_all_read20(model_cls: type[models.Model]) -> None:
    for inst in model_cls.objects.all():
        _ = inst.char1
        _ = inst.char2
        _ = inst.char3
        _ = inst.char4
        _ = inst.text1
        _ = inst.text2
        _ = inst.int1
        _ = inst.int2
        _ = inst.int3
        _ = inst.float1
        _ = inst.float2
        _ = inst.decimal1
        _ = inst.decimal2
        _ = inst.bool1
        _ = inst.bool2
        _ = inst.bool3
        _ = inst.datetime1
        _ = inst.datetime2
        _ = inst.json1
        _ = inst.json2


def _bench_only1_write1(model_cls: type[models.Model]) -> None:
    for inst in model_cls.objects.only("char1"):
        inst.char1 = "changed"


def _bench_all_write20(model_cls: type[models.Model]) -> None:
    new_dt = datetime(2025, 6, 15, 10, 30, 0, tzinfo=UTC)
    for inst in model_cls.objects.all():
        inst.char1 = "new"
        inst.char2 = "new"
        inst.char3 = "new"
        inst.char4 = "new"
        inst.text1 = "new long text"
        inst.text2 = "new text"
        inst.int1 = 999
        inst.int2 = 999
        inst.int3 = 999
        inst.float1 = 99.9
        inst.float2 = 99.9
        inst.decimal1 = Decimal("99.99")
        inst.decimal2 = Decimal("99.99")
        inst.bool1 = True
        inst.bool2 = True
        inst.bool3 = True
        inst.datetime1 = new_dt
        inst.datetime2 = new_dt
        inst.json1 = {"new": True}
        inst.json2 = {"new": True}


def _bench_only1_readwrite1(model_cls: type[models.Model]) -> None:
    for inst in model_cls.objects.only("char1"):
        _ = inst.char1
        inst.char1 = "changed"


def _bench_all_readwrite20(model_cls: type[models.Model]) -> None:
    new_dt = datetime(2025, 6, 15, 10, 30, 0, tzinfo=UTC)
    for inst in model_cls.objects.all():
        _ = inst.char1
        _ = inst.char2
        _ = inst.char3
        _ = inst.char4
        _ = inst.text1
        _ = inst.text2
        _ = inst.int1
        _ = inst.int2
        _ = inst.int3
        _ = inst.float1
        _ = inst.float2
        _ = inst.decimal1
        _ = inst.decimal2
        _ = inst.bool1
        _ = inst.bool2
        _ = inst.bool3
        _ = inst.datetime1
        _ = inst.datetime2
        _ = inst.json1
        _ = inst.json2
        inst.char1 = "new"
        inst.char2 = "new"
        inst.char3 = "new"
        inst.char4 = "new"
        inst.text1 = "new long text"
        inst.text2 = "new text"
        inst.int1 = 999
        inst.int2 = 999
        inst.int3 = 999
        inst.float1 = 99.9
        inst.float2 = 99.9
        inst.decimal1 = Decimal("99.99")
        inst.decimal2 = Decimal("99.99")
        inst.bool1 = True
        inst.bool2 = True
        inst.bool3 = True
        inst.datetime1 = new_dt
        inst.datetime2 = new_dt
        inst.json1 = {"new": True}
        inst.json2 = {"new": True}


SCENARIOS: list[tuple[str, str, Callable[[type[models.Model]], None]]] = [
    ("only1_read1", ".only(1 field) + read 1 field", _bench_only1_read1),
    ("all_read20", "Load 20 fields + read 20 fields", _bench_all_read20),
    ("only1_write1", ".only(1 field) + write 1 field", _bench_only1_write1),
    ("all_write20", "Load 20 fields + write 20 fields", _bench_all_write20),
    ("only1_readwrite1", ".only(1 field) + read+write 1 field", _bench_only1_readwrite1),
    ("all_readwrite20", "Load 20 fields + read+write 20 fields", _bench_all_readwrite20),
]


def test_benchmark_suite(populated_benchmark_db, capsys):
    """Run all benchmark scenarios and print a summary table."""
    results: dict[str, tuple[float, float]] = {}

    for key, _name, func in SCENARIOS:
        results[key] = _run_paired(
            lambda f=func: f(PlainBenchmarkModel),
            lambda f=func: f(DirtyBenchmarkModel),
        )

    with capsys.disabled():
        py = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        print()
        print("=" * 85)
        print(f"Dirty Field Tracking Benchmark — Python {py}")
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
