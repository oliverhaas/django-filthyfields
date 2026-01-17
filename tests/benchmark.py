"""Benchmark comparing plain Django, django-dirtyfields, and django-filthyfields.

This benchmark measures performance overhead for:
- Initialization: Loading model instances from the database
- Writes: Setting field values on instances
- Reads: Accessing field values on instances
- Dirty checks: Calling is_dirty() and get_dirty_fields()

Run with django-filthyfields (this package):
    uv run python tests/benchmark.py

Run with django-dirtyfields (upstream) for comparison:
    uv venv --python 3.12 /tmp/bench-upstream
    source /tmp/bench-upstream/bin/activate
    pip install django django-dirtyfields
    python tests/benchmark.py
"""

import gc
import os
import statistics
import sys
import time
from contextlib import contextmanager
from pathlib import Path

# Add project root to path so Django can find settings
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

# Setup Django before importing models
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tests.benchmark_settings")

import django

django.setup()

from django.db import connection, models

from dirtyfields import DirtyFieldsMixin


def detect_package():
    """Detect which dirty tracking package is installed."""
    # django-filthyfields uses _DirtyMeta metaclass
    # django-dirtyfields uses signals and _original_state
    if type(DirtyFieldsMixin).__name__ == "_DirtyMeta":
        return "filthyfields"
    # Check if it's descriptor-based by looking at module
    import importlib.util

    if importlib.util.find_spec("dirtyfields.dirtyfields") is not None:
        return "filthyfields"
    return "dirtyfields"


PACKAGE_NAME = detect_package()
PACKAGE_LABEL = "Filthy" if PACKAGE_NAME == "filthyfields" else "Dirty"


# Define test models
class PlainModel(models.Model):
    """Plain Django model without dirty tracking (baseline)."""

    field1 = models.CharField(max_length=100, default="")
    field2 = models.CharField(max_length=100, default="")
    field3 = models.CharField(max_length=100, default="")
    field4 = models.CharField(max_length=100, default="")
    field5 = models.CharField(max_length=100, default="")
    field6 = models.IntegerField(default=0)
    field7 = models.IntegerField(default=0)
    field8 = models.IntegerField(default=0)
    field9 = models.BooleanField(default=False)
    field10 = models.BooleanField(default=False)

    class Meta:
        app_label = "benchmark"


class DirtyModel(DirtyFieldsMixin, models.Model):
    """Model using DirtyFieldsMixin (whichever package is installed)."""

    field1 = models.CharField(max_length=100, default="")
    field2 = models.CharField(max_length=100, default="")
    field3 = models.CharField(max_length=100, default="")
    field4 = models.CharField(max_length=100, default="")
    field5 = models.CharField(max_length=100, default="")
    field6 = models.IntegerField(default=0)
    field7 = models.IntegerField(default=0)
    field8 = models.IntegerField(default=0)
    field9 = models.BooleanField(default=False)
    field10 = models.BooleanField(default=False)

    class Meta:
        app_label = "benchmark"


# Benchmark utilities
@contextmanager
def timer():
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


def run_benchmark(func, iterations=10):
    """Run a benchmark function multiple times and return statistics."""
    # Warmup
    for _ in range(3):
        func()

    times = []
    for _ in range(iterations):
        with timer() as t:
            func()
        times.append(t["elapsed"])

    return {
        "mean": statistics.mean(times),
        "stdev": statistics.stdev(times) if len(times) > 1 else 0,
        "min": min(times),
        "max": max(times),
    }


def run_paired_benchmark(func_a, func_b, iterations=10):
    """Run two benchmark functions interleaved to avoid caching bias."""
    # Warmup both
    for _ in range(3):
        func_a()
        func_b()

    times_a = []
    times_b = []
    for _ in range(iterations):
        # Alternate which goes first to balance any effects
        with timer() as t:
            func_a()
        times_a.append(t["elapsed"])

        with timer() as t:
            func_b()
        times_b.append(t["elapsed"])

    return (
        {"mean": statistics.mean(times_a), "stdev": statistics.stdev(times_a) if len(times_a) > 1 else 0},
        {"mean": statistics.mean(times_b), "stdev": statistics.stdev(times_b) if len(times_b) > 1 else 0},
    )


def setup_database():
    """Create tables and populate with test data."""
    with connection.schema_editor() as schema_editor:
        schema_editor.create_model(PlainModel)
        schema_editor.create_model(DirtyModel)

    # Create test instances
    n_instances = 1000
    for model_cls in (PlainModel, DirtyModel):
        model_cls.objects.bulk_create(
            [
                model_cls(
                    field1=f"value{i}",
                    field2=f"value{i}",
                    field3=f"value{i}",
                    field4=f"value{i}",
                    field5=f"value{i}",
                    field6=i,
                    field7=i,
                    field8=i,
                    field9=i % 2 == 0,
                    field10=i % 3 == 0,
                )
                for i in range(n_instances)
            ],
        )


# Benchmark functions for plain model (baseline)
def bench_init_plain():
    """Benchmark loading instances from DB (plain)."""
    list(PlainModel.objects.all())


def bench_write_few_plain():
    """Benchmark writing 1 field per instance (plain)."""
    instances = list(PlainModel.objects.all())
    for inst in instances:
        inst.field1 = "new_value"


def bench_write_many_plain():
    """Benchmark writing all 10 fields per instance (plain)."""
    instances = list(PlainModel.objects.all())
    for inst in instances:
        inst.field1 = "new"
        inst.field2 = "new"
        inst.field3 = "new"
        inst.field4 = "new"
        inst.field5 = "new"
        inst.field6 = 999
        inst.field7 = 999
        inst.field8 = 999
        inst.field9 = True
        inst.field10 = True


def bench_read_plain():
    """Benchmark reading all fields per instance (plain)."""
    instances = list(PlainModel.objects.all())
    for inst in instances:
        _ = inst.field1
        _ = inst.field2
        _ = inst.field3
        _ = inst.field4
        _ = inst.field5
        _ = inst.field6
        _ = inst.field7
        _ = inst.field8
        _ = inst.field9
        _ = inst.field10


# Benchmark functions for dirty model (whichever package is installed)
def bench_init_dirty():
    """Benchmark loading instances from DB (dirty tracking)."""
    list(DirtyModel.objects.all())


def bench_write_few_dirty():
    """Benchmark writing 1 field per instance (dirty tracking)."""
    instances = list(DirtyModel.objects.all())
    for inst in instances:
        inst.field1 = "new_value"


def bench_write_many_dirty():
    """Benchmark writing all 10 fields per instance (dirty tracking)."""
    instances = list(DirtyModel.objects.all())
    for inst in instances:
        inst.field1 = "new"
        inst.field2 = "new"
        inst.field3 = "new"
        inst.field4 = "new"
        inst.field5 = "new"
        inst.field6 = 999
        inst.field7 = 999
        inst.field8 = 999
        inst.field9 = True
        inst.field10 = True


def bench_read_dirty():
    """Benchmark reading all fields per instance (dirty tracking)."""
    instances = list(DirtyModel.objects.all())
    for inst in instances:
        _ = inst.field1
        _ = inst.field2
        _ = inst.field3
        _ = inst.field4
        _ = inst.field5
        _ = inst.field6
        _ = inst.field7
        _ = inst.field8
        _ = inst.field9
        _ = inst.field10


def bench_dirty_check_clean():
    """Benchmark is_dirty() on clean instances."""
    instances = list(DirtyModel.objects.all())
    for inst in instances:
        inst.is_dirty()


def bench_dirty_check_dirty():
    """Benchmark is_dirty() on dirty instances."""
    instances = list(DirtyModel.objects.all())
    for inst in instances:
        inst.field1 = "changed"
    for inst in instances:
        inst.is_dirty()


def bench_get_dirty_fields():
    """Benchmark get_dirty_fields() on dirty instances."""
    instances = list(DirtyModel.objects.all())
    for inst in instances:
        inst.field1 = "changed"
        inst.field2 = "changed"
    for inst in instances:
        inst.get_dirty_fields()


def format_result(name, dirty_stats, plain_stats):
    """Format benchmark results for display."""
    dirty_ms = dirty_stats["mean"] * 1000
    plain_ms = plain_stats["mean"] * 1000
    overhead_ms = dirty_ms - plain_ms
    overhead_pct = ((dirty_ms / plain_ms) - 1) * 100 if plain_ms > 0 else 0

    return f"{name:30} | {plain_ms:8.2f} ms | {dirty_ms:8.2f} ms | {overhead_ms:+7.2f} ms ({overhead_pct:+5.1f}%)"


def format_result_single(name, stats):
    """Format single benchmark result."""
    ms = stats["mean"] * 1000
    return f"{name:30} | {ms:8.2f} ms"


def main():
    print("=" * 80)
    print(f"Dirty Field Tracking Benchmark - {PACKAGE_NAME}")
    print("=" * 80)
    print()
    if PACKAGE_NAME == "filthyfields":
        print("Testing: django-filthyfields (descriptor-based, lazy tracking)")
    else:
        print("Testing: django-dirtyfields (signal-based, eager state capture)")
    print()
    print("Comparing dirty tracking overhead vs plain Django models.")
    print("Each benchmark runs 10 iterations on 1000 model instances with 10 fields.")
    print()

    print("Setting up database...")
    setup_database()
    print(f"Created {DirtyModel.objects.count()} test instances per model")
    print()

    print("Running benchmarks...")
    print()
    print(f"{'Operation':30} | {'Plain':>11} | {PACKAGE_LABEL:>11} | Overhead")
    print("-" * 80)

    # Initialization benchmark
    plain, dirty = run_paired_benchmark(bench_init_plain, bench_init_dirty)
    print(format_result("Load from DB", dirty, plain))

    # Write benchmarks
    plain, dirty = run_paired_benchmark(bench_write_few_plain, bench_write_few_dirty)
    print(format_result("Write 1 field", dirty, plain))

    plain, dirty = run_paired_benchmark(bench_write_many_plain, bench_write_many_dirty)
    print(format_result("Write 10 fields", dirty, plain))

    # Read benchmark
    plain, dirty = run_paired_benchmark(bench_read_plain, bench_read_dirty)
    print(format_result("Read 10 fields", dirty, plain))

    print()
    print("Dirty tracking operations:")
    print("-" * 80)

    stats = run_benchmark(bench_dirty_check_clean)
    print(format_result_single("is_dirty() (clean)", stats))

    stats = run_benchmark(bench_dirty_check_dirty)
    print(format_result_single("is_dirty() (dirty)", stats))

    stats = run_benchmark(bench_get_dirty_fields)
    print(format_result_single("get_dirty_fields()", stats))

    print()
    print("=" * 80)
    print("Notes")
    print("=" * 80)
    print()
    if PACKAGE_NAME == "filthyfields":
        print("django-filthyfields (this package) uses descriptor-based tracking:")
        print("  - Overhead comes from custom descriptors on field access")
        print("  - No post_init signal (no eager state capture on load)")
        print("  - Only tracks fields that actually change")
        print()
        print("To compare with django-dirtyfields (signal-based), run:")
        print("  uv venv --python 3.12 /tmp/bench-upstream")
        print("  source /tmp/bench-upstream/bin/activate")
        print("  pip install django django-dirtyfields")
        print("  python tests/benchmark.py")
    else:
        print("django-dirtyfields (upstream) uses signal-based tracking:")
        print("  - post_init signal captures all field values on every load")
        print("  - post_save signal resets state after save")
        print("  - Overhead is primarily on model instantiation")
        print()
        print("To compare with django-filthyfields (descriptor-based), run:")
        print("  uv run python tests/benchmark.py")
    print()


if __name__ == "__main__":
    main()
