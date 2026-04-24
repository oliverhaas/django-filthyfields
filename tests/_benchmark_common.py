"""Shared benchmark helpers.

Used by both :mod:`tests.test_benchmark` (in-process, compares plain Django vs this
fork) and :mod:`tests._upstream_benchmark_runner` (runs in a separate venv with
upstream ``django-dirtyfields`` installed, for the 3-way comparison test).

Must not import anything that only exists in this package's env — the upstream
runner invokes it from a venv that only has Django and upstream django-dirtyfields.
"""

from __future__ import annotations

import gc
import statistics
import time
from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from django.db import models

N_INSTANCES = 10_000
ITERATIONS = 5


@contextmanager
def timer() -> Iterator[dict[str, float]]:
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


def run_paired(func_a: Callable[[], None], func_b: Callable[[], None]) -> tuple[float, float]:
    """Run two benchmark functions interleaved to avoid caching bias. Returns (a_ms, b_ms)."""
    for _ in range(2):
        func_a()
        func_b()

    times_a: list[float] = []
    times_b: list[float] = []
    for _ in range(ITERATIONS):
        with timer() as t:
            func_a()
        times_a.append(t["elapsed"])
        with timer() as t:
            func_b()
        times_b.append(t["elapsed"])

    return statistics.mean(times_a) * 1000, statistics.mean(times_b) * 1000


def populate(model_cls: type[models.Model], n_instances: int = N_INSTANCES) -> None:
    """Populate a model with `n_instances` rows of diverse data."""
    base_dt = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
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
            for i in range(n_instances)
        ],
    )


def bench_only1_read1(model_cls: type[models.Model]) -> None:
    for inst in model_cls.objects.only("char1"):
        _ = inst.char1


def bench_all_read20(model_cls: type[models.Model]) -> None:
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


def bench_only1_write1(model_cls: type[models.Model]) -> None:
    for inst in model_cls.objects.only("char1"):
        inst.char1 = "changed"


def bench_all_write20(model_cls: type[models.Model]) -> None:
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


def bench_only1_readwrite1(model_cls: type[models.Model]) -> None:
    for inst in model_cls.objects.only("char1"):
        _ = inst.char1
        inst.char1 = "changed"


def bench_all_readwrite20(model_cls: type[models.Model]) -> None:
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
    ("only1_read1", ".only(1 field) + read 1 field", bench_only1_read1),
    ("all_read20", "Load 20 fields + read 20 fields", bench_all_read20),
    ("only1_write1", ".only(1 field) + write 1 field", bench_only1_write1),
    ("all_write20", "Load 20 fields + write 20 fields", bench_all_write20),
    ("only1_readwrite1", ".only(1 field) + read+write 1 field", bench_only1_readwrite1),
    ("all_readwrite20", "Load 20 fields + read+write 20 fields", bench_all_readwrite20),
]
