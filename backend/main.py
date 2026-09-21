import os
import sys
import traceback

print("[main.py] Bootstrapping AppSail Python application with Gunicorn...", flush=True)

try:
    import env_setup
except Exception as e:
    print(f"[main.py] Warning/Error during env_setup: {e}", flush=True)

try:
    port = os.environ.get("X_ZOHO_CATALYST_LISTEN_PORT", os.environ.get("PORT", "9000"))
    print(f"[main.py] Starting Gunicorn on 0.0.0.0:{port}...", flush=True)
    
    from gunicorn.app.wsgiapp import run
    sys.argv = [
        "gunicorn",
        "config.wsgi:application",
        "--bind", f"0.0.0.0:{port}",
        "--workers", "2",
        "--timeout", "120",
        "--access-logfile", "-",
        "--error-logfile", "-"
    ]
    run()
except Exception as e:
    print(f"[main.py] Fatal error launching Gunicorn: {e}", flush=True)
    traceback.print_exc()
    sys.exit(1)


