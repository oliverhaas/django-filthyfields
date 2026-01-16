# Minimum settings needed to run the Django test suite
import secrets
import tempfile

USE_TZ = True
SECRET_KEY = secrets.token_hex()

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    },
}

INSTALLED_APPS = ("tests",)

MEDIA_ROOT = tempfile.mkdtemp(prefix="django-filthyfields-test-media-root-")
