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
    print(f"{'Scenario':40} | {'Filthy':>12} | {'Dirty':>12} | {'Improvement':>12}")
    print("-" * 100)

    for key, name in scenarios:
        plain_ms = filthy_data["results"][key]["plain_ms"]
        filthy_ms = filthy_data["results"][key]["dirty_ms"]
        dirty_ms = upstream_data["results"][key]["dirty_ms"]

        filthy_overhead = filthy_ms - plain_ms
        dirty_overhead = dirty_ms - plain_ms

        improvement = dirty_overhead / filthy_overhead if filthy_overhead > 0 else float("inf")
        print(f"{name:40} | {filthy_overhead:>+9.1f} ms | {dirty_overhead:>+9.1f} ms | {improvement:>10.1f}x")

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

    # Define test models with 20 fields
    class PlainModel(models.Model):
        """Plain Django model without dirty tracking (baseline)."""

        f01 = models.CharField(max_length=100, default="")
        f02 = models.CharField(max_length=100, default="")
        f03 = models.CharField(max_length=100, default="")
        f04 = models.CharField(max_length=100, default="")
        f05 = models.CharField(max_length=100, default="")
        f06 = models.CharField(max_length=100, default="")
        f07 = models.CharField(max_length=100, default="")
        f08 = models.CharField(max_length=100, default="")
        f09 = models.CharField(max_length=100, default="")
        f10 = models.CharField(max_length=100, default="")
        f11 = models.IntegerField(default=0)
        f12 = models.IntegerField(default=0)
        f13 = models.IntegerField(default=0)
        f14 = models.IntegerField(default=0)
        f15 = models.IntegerField(default=0)
        f16 = models.BooleanField(default=False)
        f17 = models.BooleanField(default=False)
        f18 = models.BooleanField(default=False)
        f19 = models.BooleanField(default=False)
        f20 = models.BooleanField(default=False)

        class Meta:
            app_label = "benchmark"

    class DirtyModel(DirtyFieldsMixin, models.Model):
        """Model using DirtyFieldsMixin (whichever package is installed)."""

        f01 = models.CharField(max_length=100, default="")
        f02 = models.CharField(max_length=100, default="")
        f03 = models.CharField(max_length=100, default="")
        f04 = models.CharField(max_length=100, default="")
        f05 = models.CharField(max_length=100, default="")
        f06 = models.CharField(max_length=100, default="")
        f07 = models.CharField(max_length=100, default="")
        f08 = models.CharField(max_length=100, default="")
        f09 = models.CharField(max_length=100, default="")
        f10 = models.CharField(max_length=100, default="")
        f11 = models.IntegerField(default=0)
        f12 = models.IntegerField(default=0)
        f13 = models.IntegerField(default=0)
        f14 = models.IntegerField(default=0)
        f15 = models.IntegerField(default=0)
        f16 = models.BooleanField(default=False)
        f17 = models.BooleanField(default=False)
        f18 = models.BooleanField(default=False)
        f19 = models.BooleanField(default=False)
        f20 = models.BooleanField(default=False)

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
        with connection.schema_editor() as schema_editor:
            schema_editor.create_model(PlainModel)
            schema_editor.create_model(DirtyModel)

        # Create test instances
        for model_cls in (PlainModel, DirtyModel):
            model_cls.objects.bulk_create(
                [
                    model_cls(
                        f01=f"val{i}",
                        f02=f"val{i}",
                        f03=f"val{i}",
                        f04=f"val{i}",
                        f05=f"val{i}",
                        f06=f"val{i}",
                        f07=f"val{i}",
                        f08=f"val{i}",
                        f09=f"val{i}",
                        f10=f"val{i}",
                        f11=i,
                        f12=i,
                        f13=i,
                        f14=i,
                        f15=i,
                        f16=i % 2 == 0,
                        f17=i % 3 == 0,
                        f18=i % 5 == 0,
                        f19=i % 7 == 0,
                        f20=i % 11 == 0,
                    )
                    for i in range(N_INSTANCES)
                ],
            )

    # Scenario 1: Load with .only(1 field), read that field
    def bench_only1_read1_plain():
        instances = list(PlainModel.objects.only("f01"))
        for inst in instances:
            _ = inst.f01

    def bench_only1_read1_dirty():
        instances = list(DirtyModel.objects.only("f01"))
        for inst in instances:
            _ = inst.f01

    # Scenario 2: Load all 20 fields, read all 20 fields
    def bench_all_read20_plain():
        instances = list(PlainModel.objects.all())
        for inst in instances:
            _ = inst.f01
            _ = inst.f02
            _ = inst.f03
            _ = inst.f04
            _ = inst.f05
            _ = inst.f06
            _ = inst.f07
            _ = inst.f08
            _ = inst.f09
            _ = inst.f10
            _ = inst.f11
            _ = inst.f12
            _ = inst.f13
            _ = inst.f14
            _ = inst.f15
            _ = inst.f16
            _ = inst.f17
            _ = inst.f18
            _ = inst.f19
            _ = inst.f20

    def bench_all_read20_dirty():
        instances = list(DirtyModel.objects.all())
        for inst in instances:
            _ = inst.f01
            _ = inst.f02
            _ = inst.f03
            _ = inst.f04
            _ = inst.f05
            _ = inst.f06
            _ = inst.f07
            _ = inst.f08
            _ = inst.f09
            _ = inst.f10
            _ = inst.f11
            _ = inst.f12
            _ = inst.f13
            _ = inst.f14
            _ = inst.f15
            _ = inst.f16
            _ = inst.f17
            _ = inst.f18
            _ = inst.f19
            _ = inst.f20

    # Scenario 3: Load with .only(1 field), write that field
    def bench_only1_write1_plain():
        instances = list(PlainModel.objects.only("f01"))
        for inst in instances:
            inst.f01 = "changed"

    def bench_only1_write1_dirty():
        instances = list(DirtyModel.objects.only("f01"))
        for inst in instances:
            inst.f01 = "changed"

    # Scenario 4: Load all 20 fields, write all 20 fields
    def bench_all_write20_plain():
        instances = list(PlainModel.objects.all())
        for inst in instances:
            inst.f01 = "new"
            inst.f02 = "new"
            inst.f03 = "new"
            inst.f04 = "new"
            inst.f05 = "new"
            inst.f06 = "new"
            inst.f07 = "new"
            inst.f08 = "new"
            inst.f09 = "new"
            inst.f10 = "new"
            inst.f11 = 999
            inst.f12 = 999
            inst.f13 = 999
            inst.f14 = 999
            inst.f15 = 999
            inst.f16 = True
            inst.f17 = True
            inst.f18 = True
            inst.f19 = True
            inst.f20 = True

    def bench_all_write20_dirty():
        instances = list(DirtyModel.objects.all())
        for inst in instances:
            inst.f01 = "new"
            inst.f02 = "new"
            inst.f03 = "new"
            inst.f04 = "new"
            inst.f05 = "new"
            inst.f06 = "new"
            inst.f07 = "new"
            inst.f08 = "new"
            inst.f09 = "new"
            inst.f10 = "new"
            inst.f11 = 999
            inst.f12 = 999
            inst.f13 = 999
            inst.f14 = 999
            inst.f15 = 999
            inst.f16 = True
            inst.f17 = True
            inst.f18 = True
            inst.f19 = True
            inst.f20 = True

    # Scenario 5: Load with .only(1 field), read+write that field
    def bench_only1_readwrite1_plain():
        instances = list(PlainModel.objects.only("f01"))
        for inst in instances:
            _ = inst.f01
            inst.f01 = "changed"

    def bench_only1_readwrite1_dirty():
        instances = list(DirtyModel.objects.only("f01"))
        for inst in instances:
            _ = inst.f01
            inst.f01 = "changed"

    # Scenario 6: Load all 20 fields, read+write all 20 fields
    def bench_all_readwrite20_plain():
        instances = list(PlainModel.objects.all())
        for inst in instances:
            _ = inst.f01
            _ = inst.f02
            _ = inst.f03
            _ = inst.f04
            _ = inst.f05
            _ = inst.f06
            _ = inst.f07
            _ = inst.f08
            _ = inst.f09
            _ = inst.f10
            _ = inst.f11
            _ = inst.f12
            _ = inst.f13
            _ = inst.f14
            _ = inst.f15
            _ = inst.f16
            _ = inst.f17
            _ = inst.f18
            _ = inst.f19
            _ = inst.f20
            inst.f01 = "new"
            inst.f02 = "new"
            inst.f03 = "new"
            inst.f04 = "new"
            inst.f05 = "new"
            inst.f06 = "new"
            inst.f07 = "new"
            inst.f08 = "new"
            inst.f09 = "new"
            inst.f10 = "new"
            inst.f11 = 999
            inst.f12 = 999
            inst.f13 = 999
            inst.f14 = 999
            inst.f15 = 999
            inst.f16 = True
            inst.f17 = True
            inst.f18 = True
            inst.f19 = True
            inst.f20 = True

    def bench_all_readwrite20_dirty():
        instances = list(DirtyModel.objects.all())
        for inst in instances:
            _ = inst.f01
            _ = inst.f02
            _ = inst.f03
            _ = inst.f04
            _ = inst.f05
            _ = inst.f06
            _ = inst.f07
            _ = inst.f08
            _ = inst.f09
            _ = inst.f10
            _ = inst.f11
            _ = inst.f12
            _ = inst.f13
            _ = inst.f14
            _ = inst.f15
            _ = inst.f16
            _ = inst.f17
            _ = inst.f18
            _ = inst.f19
            _ = inst.f20
            inst.f01 = "new"
            inst.f02 = "new"
            inst.f03 = "new"
            inst.f04 = "new"
            inst.f05 = "new"
            inst.f06 = "new"
            inst.f07 = "new"
            inst.f08 = "new"
            inst.f09 = "new"
            inst.f10 = "new"
            inst.f11 = 999
            inst.f12 = 999
            inst.f13 = 999
            inst.f14 = 999
            inst.f15 = 999
            inst.f16 = True
            inst.f17 = True
            inst.f18 = True
            inst.f19 = True
            inst.f20 = True

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
