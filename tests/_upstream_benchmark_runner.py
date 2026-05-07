"""Standalone benchmark runner invoked by ``test_benchmark_vs_upstream``.

Not a pytest file. Runs in a separate venv that has Django and upstream
``django-dirtyfields`` installed (and nothing from this fork). Imports the
scenarios from :mod:`tests._benchmark_common` via PYTHONPATH/cwd, defines
its own Plain + Dirty benchmark models, creates tables, populates data,
runs the paired scenarios, and prints a single-line JSON result to stdout:

    {"package": "django-dirtyfields", "python_version": "...", "n_instances": 10000,
     "results": {"only1_read1": {"plain_ms": ..., "dirty_ms": ...}, ...}}
"""
# ruff: noqa: T201, E402

from __future__ import annotations

import json
import sys

import django
from django.conf import settings

settings.configure(
    SECRET_KEY="benchmark-runner",  # noqa: S106
    DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}},
    INSTALLED_APPS=["django.contrib.contenttypes"],
    USE_TZ=True,
    DEFAULT_AUTO_FIELD="django.db.models.BigAutoField",
)
django.setup()

from django.db import connection, models

from dirtyfields import DirtyFieldsMixin
from tests._benchmark_common import ITERATIONS, N_INSTANCES, SCENARIOS, populate, run_paired


class PlainBenchmarkModel(models.Model):
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
        app_label = "benchmark"


class DirtyBenchmarkModel(DirtyFieldsMixin, models.Model):
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
        app_label = "benchmark"


def main() -> None:
    with connection.schema_editor() as editor:
        editor.create_model(PlainBenchmarkModel)
        editor.create_model(DirtyBenchmarkModel)

    populate(PlainBenchmarkModel)
    populate(DirtyBenchmarkModel)

    results: dict[str, dict[str, float]] = {}
    for key, _name, func in SCENARIOS:
        plain_ms, dirty_ms = run_paired(
            lambda f=func: f(PlainBenchmarkModel),
            lambda f=func: f(DirtyBenchmarkModel),
        )
        results[key] = {"plain_ms": plain_ms, "dirty_ms": dirty_ms}

    print(
        json.dumps(
            {
                "package": "django-dirtyfields",
                "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
                "n_instances": N_INSTANCES,
                "iterations": ITERATIONS,
                "results": results,
            },
        ),
    )


if __name__ == "__main__":
    main()
