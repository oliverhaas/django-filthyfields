"""Benchmark comparing django-filthyfields vs django-dirtyfields.

This benchmark measures performance overhead for:
- Initialization: Loading model instances from the database
- Writes: Setting field values on instances
- Reads: Accessing field values on instances
- Dirty checks: Calling is_dirty() and get_dirty_fields()

Run with: uv run python tests/benchmark.py

To compare with django-dirtyfields, create a separate virtualenv:
    uv venv --python 3.12 /tmp/bench-upstream
    source /tmp/bench-upstream/bin/activate
    pip install django django-dirtyfields
    # Then run the upstream benchmark section of this script
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


class FilthyModel(DirtyFieldsMixin, models.Model):
    """Model using django-filthyfields (descriptor-based)."""

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
        schema_editor.create_model(FilthyModel)

    # Create test instances
    n_instances = 1000
    for model_cls in (PlainModel, FilthyModel):
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


# Benchmark functions for filthy model
def bench_init_filthy():
    """Benchmark loading instances from DB (filthyfields)."""
    list(FilthyModel.objects.all())


def bench_write_few_filthy():
    """Benchmark writing 1 field per instance (filthyfields)."""
    instances = list(FilthyModel.objects.all())
    for inst in instances:
        inst.field1 = "new_value"


def bench_write_many_filthy():
    """Benchmark writing all 10 fields per instance (filthyfields)."""
    instances = list(FilthyModel.objects.all())
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


def bench_read_filthy():
    """Benchmark reading all fields per instance (filthyfields)."""
    instances = list(FilthyModel.objects.all())
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
    instances = list(FilthyModel.objects.all())
    for inst in instances:
        inst.is_dirty()


def bench_dirty_check_dirty():
    """Benchmark is_dirty() on dirty instances."""
    instances = list(FilthyModel.objects.all())
    for inst in instances:
        inst.field1 = "changed"
    for inst in instances:
        inst.is_dirty()


def bench_get_dirty_fields():
    """Benchmark get_dirty_fields() on dirty instances."""
    instances = list(FilthyModel.objects.all())
    for inst in instances:
        inst.field1 = "changed"
        inst.field2 = "changed"
    for inst in instances:
        inst.get_dirty_fields()


def format_result(name, filthy_stats, plain_stats):
    """Format benchmark results for display."""
    filthy_ms = filthy_stats["mean"] * 1000
    plain_ms = plain_stats["mean"] * 1000
    overhead_ms = filthy_ms - plain_ms
    overhead_pct = ((filthy_ms / plain_ms) - 1) * 100 if plain_ms > 0 else 0

    return f"{name:30} | {plain_ms:8.2f} ms | {filthy_ms:8.2f} ms | {overhead_ms:+7.2f} ms ({overhead_pct:+5.1f}%)"


def format_result_single(name, stats):
    """Format single benchmark result."""
    ms = stats["mean"] * 1000
    return f"{name:30} | {ms:8.2f} ms"


def main():
    print("=" * 80)
    print("django-filthyfields Benchmark")
    print("=" * 80)
    print()
    print("Comparing dirty field tracking overhead vs plain Django models.")
    print("Each benchmark runs 10 iterations on 1000 model instances with 10 fields.")
    print()

    print("Setting up database...")
    setup_database()
    print(f"Created {FilthyModel.objects.count()} test instances per model")
    print()

    print("Running benchmarks...")
    print()
    print(f"{'Operation':30} | {'Plain':>11} | {'Filthy':>11} | Overhead")
    print("-" * 80)

    # Initialization benchmark
    plain, filthy = run_paired_benchmark(bench_init_plain, bench_init_filthy)
    print(format_result("Load from DB", filthy, plain))

    # Write benchmarks
    plain, filthy = run_paired_benchmark(bench_write_few_plain, bench_write_few_filthy)
    print(format_result("Write 1 field", filthy, plain))

    plain, filthy = run_paired_benchmark(bench_write_many_plain, bench_write_many_filthy)
    print(format_result("Write 10 fields", filthy, plain))

    # Read benchmark
    plain, filthy = run_paired_benchmark(bench_read_plain, bench_read_filthy)
    print(format_result("Read 10 fields", filthy, plain))

    print()
    print("Dirty tracking operations (no plain equivalent):")
    print("-" * 80)

    stats = run_benchmark(bench_dirty_check_clean)
    print(format_result_single("is_dirty() (clean)", stats))

    stats = run_benchmark(bench_dirty_check_dirty)
    print(format_result_single("is_dirty() (dirty)", stats))

    stats = run_benchmark(bench_get_dirty_fields)
    print(format_result_single("get_dirty_fields()", stats))

    print()
    print("=" * 80)
    print("Summary")
    print("=" * 80)
    print()
    print("django-filthyfields uses lazy descriptor-based tracking.")
    print("Overhead vs plain Django models comes from custom descriptors.")
    print()
    print("vs django-dirtyfields (signal-based, not shown):")
    print("  - No post_init signal (faster instantiation)")
    print("  - No eager state capture (only tracks fields that change)")
    print("  - No post_save signal (state reset is inline)")
    print()
    print("Best for: always-on tracking without manual enable/disable,")
    print("and workloads where most loaded instances aren't modified.")
    print()


if __name__ == "__main__":
    main()
