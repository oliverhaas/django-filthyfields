"""Benchmark comparing plain Django, django-dirtyfields, and django-filthyfields.

Scenarios tested:
1. Load 10k rows with .only(1 field), read that field
2. Load 10k rows (20 fields), read all 20 fields
3. Load 10k rows with .only(1 field), write that field
4. Load 10k rows (20 fields), write all 20 fields
5. Load 10k rows with .only(1 field), read+write that field
6. Load 10k rows (20 fields), read+write all 20 fields

Run with django-filthyfields (this package):
    uv run python tests/benchmark.py

Run comparison between both implementations:
    uv run python tests/benchmark.py --compare

Run with JSON output:
    uv run python tests/benchmark.py --json
"""

import argparse
import gc
import json
import os
import statistics
import subprocess
import sys
import time
from contextlib import contextmanager
from datetime import UTC
from pathlib import Path

# Add project root to path so Django can find settings
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def run_comparison(python_version: str | None = None):
    """Run benchmarks for both implementations and display side-by-side comparison."""

    upstream_venv = Path("/tmp/bench-upstream")  # noqa: S108

    print("=" * 100)
    print("Dirty Field Tracking Benchmark - Comparison Mode")
    print("=" * 100)
    print()

    # Run filthyfields benchmark
    print("Running filthyfields benchmark...")
    filthy_cmd = ["uv", "run"]
    if python_version:
        filthy_cmd.extend(["--python", python_version])
    filthy_cmd.extend(["python", "tests/benchmark.py", "--json"])

    filthy_result = subprocess.run(  # noqa: S603
        filthy_cmd,
        capture_output=True,
        text=True,
        cwd=project_root,
        check=False,
    )
    if filthy_result.returncode != 0:
        print(f"Error running filthyfields benchmark: {filthy_result.stderr}")
        sys.exit(1)
    filthy_data = json.loads(filthy_result.stdout)

    # Setup upstream venv if needed
    print("Setting up upstream django-dirtyfields environment...")
    venv_cmd = ["uv", "venv"]
    if python_version:
        venv_cmd.extend(["--python", python_version])
    venv_cmd.extend(["--quiet", str(upstream_venv)])
    subprocess.run(venv_cmd, check=True)  # noqa: S603

    # Install dependencies
    pip_cmd = [
        "uv",
        "pip",
        "install",
        "--quiet",
        "--python",
        str(upstream_venv / "bin" / "python"),
        "django",
        "django-dirtyfields",
    ]
    subprocess.run(pip_cmd, check=True)  # noqa: S603

    # Run upstream benchmark
    print("Running upstream django-dirtyfields benchmark...")
    upstream_python = upstream_venv / "bin" / "python"
    upstream_result = subprocess.run(  # noqa: S603
        [str(upstream_python), "tests/benchmark.py", "--json"],
        capture_output=True,
        text=True,
        cwd=project_root,
        check=False,
    )
    if upstream_result.returncode != 0:
        print(f"Error running upstream benchmark: {upstream_result.stderr}")
        sys.exit(1)
    upstream_data = json.loads(upstream_result.stdout)

    # Display comparison
    print()
    print(f"Python: {filthy_data['python_version']}")
    print(f"Instances: {filthy_data['n_instances']:,} | Fields: 20 | Iterations: 5")
    print()
    print(f"{'Scenario':40} | {'Plain':>10} | {'Filthy':>10} | {'Dirty':>10} | {'Winner':>12}")
    print("-" * 100)

    scenarios = [
        ("only1_read1", ".only(1 field) + read 1 field"),
        ("all_read20", "Load 20 fields + read 20 fields"),
        ("only1_write1", ".only(1 field) + write 1 field"),
        ("all_write20", "Load 20 fields + write 20 fields"),
        ("only1_readwrite1", ".only(1 field) + read+write 1 field"),
        ("all_readwrite20", "Load 20 fields + read+write 20 fields"),
    ]

    for key, name in scenarios:
        plain_ms = filthy_data["results"][key]["plain_ms"]
        filthy_ms = filthy_data["results"][key]["dirty_ms"]
        dirty_ms = upstream_data["results"][key]["dirty_ms"]

        filthy_overhead = filthy_ms - plain_ms
        dirty_overhead = dirty_ms - plain_ms

        if filthy_overhead < dirty_overhead:
            winner = f"Filthy {dirty_overhead / filthy_overhead:.1f}x"
        else:
            winner = f"Dirty {filthy_overhead / dirty_overhead:.1f}x"

        print(f"{name:40} | {plain_ms:>7.1f} ms | {filthy_ms:>7.1f} ms | {dirty_ms:>7.1f} ms | {winner:>12}")

    print()
    print("=" * 100)
    print("Overhead Comparison (lower is better)")
    print("=" * 100)
    print()
    print(f"{'Scenario':40} | {'Base':>12} | {'Filthy':>12} | {'Dirty':>12} | {'Improvement':>12}")
    print("-" * 115)

    for key, name in scenarios:
        plain_ms = filthy_data["results"][key]["plain_ms"]
        filthy_ms = filthy_data["results"][key]["dirty_ms"]
        dirty_ms = upstream_data["results"][key]["dirty_ms"]

        filthy_overhead = filthy_ms - plain_ms
        dirty_overhead = dirty_ms - plain_ms

        improvement = dirty_overhead / filthy_overhead if filthy_overhead > 0 else float("inf")
        print(
            f"{name:40} | {plain_ms:>9.1f} ms | {filthy_overhead:>+9.1f} ms | {dirty_overhead:>+9.1f} ms | {improvement:>10.1f}x",
        )

    print()


def run_single_benchmark(json_output: bool = False):
    """Run benchmark for the currently installed implementation."""
    # Only add src/ to path if dirtyfields isn't already importable (i.e., not using upstream)
    # We check using importlib.util to avoid triggering Django setup
    import importlib.util

    if importlib.util.find_spec("dirtyfields") is None:
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
        if type(DirtyFieldsMixin).__name__ == "_DirtyMeta":
            return "filthyfields"
        # django-dirtyfields uses signals - check for _original_state method pattern
        if hasattr(DirtyFieldsMixin, "FIELDS_TO_CHECK") and hasattr(DirtyFieldsMixin, "ENABLE_M2M_CHECK"):
            return "dirtyfields"
        # Fallback: check module location
        module = DirtyFieldsMixin.__module__
        if "dirtyfields.dirtyfields" in module:
            return "filthyfields"
        return "dirtyfields"

    PACKAGE_NAME = detect_package()
    PACKAGE_LABEL = "Filthy" if PACKAGE_NAME == "filthyfields" else "Dirty"
    N_INSTANCES = 10000

    # Define test models with 20 diverse fields
    class PlainModel(models.Model):
        """Plain Django model without dirty tracking (baseline)."""

        # CharField (4 fields)
        char1 = models.CharField(max_length=100, default="")
        char2 = models.CharField(max_length=100, default="")
        char3 = models.CharField(max_length=100, default="")
        char4 = models.CharField(max_length=100, default="")
        # TextField (2 fields)
        text1 = models.TextField(default="")
        text2 = models.TextField(default="")
        # IntegerField (3 fields)
        int1 = models.IntegerField(default=0)
        int2 = models.IntegerField(default=0)
        int3 = models.IntegerField(default=0)
        # FloatField (2 fields)
        float1 = models.FloatField(default=0.0)
        float2 = models.FloatField(default=0.0)
        # DecimalField (2 fields)
        decimal1 = models.DecimalField(max_digits=10, decimal_places=2, default=0)
        decimal2 = models.DecimalField(max_digits=10, decimal_places=2, default=0)
        # BooleanField (3 fields)
        bool1 = models.BooleanField(default=False)
        bool2 = models.BooleanField(default=False)
        bool3 = models.BooleanField(default=False)
        # DateTimeField (2 fields)
        datetime1 = models.DateTimeField(null=True, default=None)
        datetime2 = models.DateTimeField(null=True, default=None)
        # JSONField (2 fields)
        json1 = models.JSONField(default=dict)
        json2 = models.JSONField(default=dict)

        class Meta:
            app_label = "benchmark"

    class DirtyModel(DirtyFieldsMixin, models.Model):
        """Model using DirtyFieldsMixin (whichever package is installed)."""

        # CharField (4 fields)
        char1 = models.CharField(max_length=100, default="")
        char2 = models.CharField(max_length=100, default="")
        char3 = models.CharField(max_length=100, default="")
        char4 = models.CharField(max_length=100, default="")
        # TextField (2 fields)
        text1 = models.TextField(default="")
        text2 = models.TextField(default="")
        # IntegerField (3 fields)
        int1 = models.IntegerField(default=0)
        int2 = models.IntegerField(default=0)
        int3 = models.IntegerField(default=0)
        # FloatField (2 fields)
        float1 = models.FloatField(default=0.0)
        float2 = models.FloatField(default=0.0)
        # DecimalField (2 fields)
        decimal1 = models.DecimalField(max_digits=10, decimal_places=2, default=0)
        decimal2 = models.DecimalField(max_digits=10, decimal_places=2, default=0)
        # BooleanField (3 fields)
        bool1 = models.BooleanField(default=False)
        bool2 = models.BooleanField(default=False)
        bool3 = models.BooleanField(default=False)
        # DateTimeField (2 fields)
        datetime1 = models.DateTimeField(null=True, default=None)
        datetime2 = models.DateTimeField(null=True, default=None)
        # JSONField (2 fields)
        json1 = models.JSONField(default=dict)
        json2 = models.JSONField(default=dict)

        class Meta:
            app_label = "benchmark"

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

    def run_paired_benchmark(func_a, func_b, iterations=5):
        """Run two benchmark functions interleaved to avoid caching bias."""
        # Warmup both
        for _ in range(2):
            func_a()
            func_b()

        times_a = []
        times_b = []
        for _ in range(iterations):
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
        from datetime import datetime
        from decimal import Decimal

        with connection.schema_editor() as schema_editor:
            schema_editor.create_model(PlainModel)
            schema_editor.create_model(DirtyModel)

        base_dt = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)

        # Create test instances
        for model_cls in (PlainModel, DirtyModel):
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
                        float1=float(i) * 1.5,
                        float2=float(i) * 2.5,
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

    # Scenario 1: Load with .only(1 field), read that field
    def bench_only1_read1_plain():
        instances = list(PlainModel.objects.only("char1"))
        for inst in instances:
            _ = inst.char1

    def bench_only1_read1_dirty():
        instances = list(DirtyModel.objects.only("char1"))
        for inst in instances:
            _ = inst.char1

    # Scenario 2: Load all 20 fields, read all 20 fields
    def bench_all_read20_plain():
        instances = list(PlainModel.objects.all())
        for inst in instances:
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

    def bench_all_read20_dirty():
        instances = list(DirtyModel.objects.all())
        for inst in instances:
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

    # Scenario 3: Load with .only(1 field), write that field
    def bench_only1_write1_plain():
        instances = list(PlainModel.objects.only("char1"))
        for inst in instances:
            inst.char1 = "changed"

    def bench_only1_write1_dirty():
        instances = list(DirtyModel.objects.only("char1"))
        for inst in instances:
            inst.char1 = "changed"

    # Scenario 4: Load all 20 fields, write all 20 fields
    def bench_all_write20_plain():
        from datetime import datetime
        from decimal import Decimal

        new_dt = datetime(2025, 6, 15, 10, 30, 0, tzinfo=UTC)
        instances = list(PlainModel.objects.all())
        for inst in instances:
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

    def bench_all_write20_dirty():
        from datetime import datetime
        from decimal import Decimal

        new_dt = datetime(2025, 6, 15, 10, 30, 0, tzinfo=UTC)
        instances = list(DirtyModel.objects.all())
        for inst in instances:
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

    # Scenario 5: Load with .only(1 field), read+write that field
    def bench_only1_readwrite1_plain():
        instances = list(PlainModel.objects.only("char1"))
        for inst in instances:
            _ = inst.char1
            inst.char1 = "changed"

    def bench_only1_readwrite1_dirty():
        instances = list(DirtyModel.objects.only("char1"))
        for inst in instances:
            _ = inst.char1
            inst.char1 = "changed"

    # Scenario 6: Load all 20 fields, read+write all 20 fields
    def bench_all_readwrite20_plain():
        from datetime import datetime
        from decimal import Decimal

        new_dt = datetime(2025, 6, 15, 10, 30, 0, tzinfo=UTC)
        instances = list(PlainModel.objects.all())
        for inst in instances:
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

    def bench_all_readwrite20_dirty():
        from datetime import datetime
        from decimal import Decimal

        new_dt = datetime(2025, 6, 15, 10, 30, 0, tzinfo=UTC)
        instances = list(DirtyModel.objects.all())
        for inst in instances:
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

    def format_result(name, dirty_stats, plain_stats):
        """Format benchmark results for display."""
        dirty_ms = dirty_stats["mean"] * 1000
        plain_ms = plain_stats["mean"] * 1000
        overhead_ms = dirty_ms - plain_ms

        return f"{name:40} | {plain_ms:9.1f} ms | {dirty_ms:9.1f} ms | {overhead_ms:+8.1f} ms"

    # Run benchmarks
    setup_database()

    results = {}

    # Scenario 1: .only(1 field), read 1 field
    plain, dirty = run_paired_benchmark(bench_only1_read1_plain, bench_only1_read1_dirty)
    results["only1_read1"] = {
        "plain_ms": plain["mean"] * 1000,
        "dirty_ms": dirty["mean"] * 1000,
    }

    # Scenario 2: all fields, read 20 fields
    plain, dirty = run_paired_benchmark(bench_all_read20_plain, bench_all_read20_dirty)
    results["all_read20"] = {
        "plain_ms": plain["mean"] * 1000,
        "dirty_ms": dirty["mean"] * 1000,
    }

    # Scenario 3: .only(1 field), write 1 field
    plain, dirty = run_paired_benchmark(bench_only1_write1_plain, bench_only1_write1_dirty)
    results["only1_write1"] = {
        "plain_ms": plain["mean"] * 1000,
        "dirty_ms": dirty["mean"] * 1000,
    }

    # Scenario 4: all fields, write 20 fields
    plain, dirty = run_paired_benchmark(bench_all_write20_plain, bench_all_write20_dirty)
    results["all_write20"] = {
        "plain_ms": plain["mean"] * 1000,
        "dirty_ms": dirty["mean"] * 1000,
    }

    # Scenario 5: .only(1 field), read+write 1 field
    plain, dirty = run_paired_benchmark(bench_only1_readwrite1_plain, bench_only1_readwrite1_dirty)
    results["only1_readwrite1"] = {
        "plain_ms": plain["mean"] * 1000,
        "dirty_ms": dirty["mean"] * 1000,
    }

    # Scenario 6: all fields, read+write 20 fields
    plain, dirty = run_paired_benchmark(bench_all_readwrite20_plain, bench_all_readwrite20_dirty)
    results["all_readwrite20"] = {
        "plain_ms": plain["mean"] * 1000,
        "dirty_ms": dirty["mean"] * 1000,
    }

    if json_output:
        output = {
            "package": PACKAGE_NAME,
            "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "n_instances": N_INSTANCES,
            "results": results,
        }
        print(json.dumps(output))
    else:
        print("=" * 85)
        print(f"Dirty Field Tracking Benchmark - {PACKAGE_NAME}")
        print("=" * 85)
        print()
        if PACKAGE_NAME == "filthyfields":
            print("Testing: django-filthyfields (descriptor-based, lazy tracking)")
        else:
            print("Testing: django-dirtyfields (signal-based, eager state capture)")
        print()
        print(f"Each scenario: {N_INSTANCES:,} model instances, 20 fields per model, 5 iterations")
        print()

        print(f"{'Scenario':40} | {'Plain':>12} | {PACKAGE_LABEL:>12} | {'Overhead':>11}")
        print("-" * 85)

        scenarios = [
            ("only1_read1", ".only(1 field) + read 1 field"),
            ("all_read20", "Load 20 fields + read 20 fields"),
            ("only1_write1", ".only(1 field) + write 1 field"),
            ("all_write20", "Load 20 fields + write 20 fields"),
            ("only1_readwrite1", ".only(1 field) + read+write 1 field"),
            ("all_readwrite20", "Load 20 fields + read+write 20 fields"),
        ]

        for key, name in scenarios:
            plain_ms = results[key]["plain_ms"]
            dirty_ms = results[key]["dirty_ms"]
            overhead_ms = dirty_ms - plain_ms
            print(f"{name:40} | {plain_ms:9.1f} ms | {dirty_ms:9.1f} ms | {overhead_ms:+8.1f} ms")

        print()
        print("=" * 85)
        print("Notes")
        print("=" * 85)
        print()
        if PACKAGE_NAME == "filthyfields":
            print("django-filthyfields uses descriptor-based tracking:")
            print("  - Overhead on field access (read/write) via custom descriptors")
            print("  - No signal overhead on model instantiation")
            print("  - Only tracks fields that actually change")
            print()
            print("To compare with django-dirtyfields, run:")
            print("  uv run python tests/benchmark.py --compare")
        else:
            print("django-dirtyfields uses signal-based tracking:")
            print("  - post_init signal copies ALL field values on every model load")
            print("  - Minimal overhead on field access (no custom descriptors)")
            print("  - post_save signal resets state after save")
            print()
            print("To compare with django-filthyfields, run:")
            print("  uv run python tests/benchmark.py --compare")
        print()


def main():
    parser = argparse.ArgumentParser(description="Benchmark dirty field tracking implementations")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    parser.add_argument("--compare", action="store_true", help="Compare filthyfields vs upstream dirtyfields")
    parser.add_argument("--python", type=str, help="Python version to use (e.g., 3.14)")
    args = parser.parse_args()

    if args.compare:
        run_comparison(args.python)
    else:
        run_single_benchmark(args.json)


if __name__ == "__main__":
    main()
