"""Minimal Django settings for the netbox-ping unit test suite.

No NetBox apps — just enough for django.utils.timezone to work.
"""

SECRET_KEY = "test-secret-key-not-for-production"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
]

USE_TZ = True
TIME_ZONE = "Europe/Copenhagen"

# Silence Django's system checks — we have no full app stack
SILENCED_SYSTEM_CHECKS = ["models.W042"]

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
