"""Django settings for benchmark script."""

SECRET_KEY = "benchmark-secret-key"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    },
}

INSTALLED_APPS = [
    "django.contrib.contenttypes",
]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

USE_TZ = True
