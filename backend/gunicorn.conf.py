"""
Gunicorn configuration (env-driven, host-agnostic).

Gunicorn picks this file up automatically when started from this directory
(Docker WORKDIR=/app), and main.py passes it explicitly for Catalyst AppSail.
Command-line flags still override anything set here.

Environment variables (all optional):
    GUNICORN_BIND         full bind address (default 0.0.0.0:$PORT or :8000)
    GUNICORN_WORKERS      worker processes (default: $WEB_CONCURRENCY or 2)
    GUNICORN_THREADS      threads per worker; >1 switches to the gthread class
    GUNICORN_TIMEOUT      seconds before a silent worker is killed (default 300)

NOTE: this only controls gunicorn. Hosting platforms have their own request
limits (e.g. Catalyst AppSail ends requests after 30s) that no gunicorn setting
can raise; long OCR jobs must therefore run in the background there.
"""

import os


def _int_env(name, default):
    try:
        return max(1, int(os.environ.get(name, default)))
    except (TypeError, ValueError):
        return int(default)


_port = (
    os.environ.get("X_ZOHO_CATALYST_LISTEN_PORT")
    or os.environ.get("PORT")
    or "8000"
)

bind = os.environ.get("GUNICORN_BIND", f"0.0.0.0:{_port}")
workers = _int_env("GUNICORN_WORKERS", _int_env("WEB_CONCURRENCY", 2))
threads = _int_env("GUNICORN_THREADS", 1)
worker_class = "gthread" if threads > 1 else "sync"
timeout = _int_env("GUNICORN_TIMEOUT", 300)
graceful_timeout = _int_env("GUNICORN_GRACEFUL_TIMEOUT", 30)
accesslog = "-"
errorlog = "-"