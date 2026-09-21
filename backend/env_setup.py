import os
import sys
import glob
import site
import importlib
import subprocess

def add_all_site_packages():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Dynamically resolve Python's official user site-packages directory
    user_site = site.getusersitepackages()
    
    explicit_paths = [
        os.path.join(base_dir, "site-packages"),
        base_dir,
        "/tmp/site-packages",
        "/catalyst",
        user_site,
        "/catalyst/.local/lib/python3.12/site-packages",
        "/catalyst/.local/lib/python3.11/site-packages",
        "/catalyst/.local/lib/python3.10/site-packages",
        "/catalyst/.local/lib/python3/site-packages",
    ]
    for p in explicit_paths:
        if p and os.path.exists(p):
            site.addsitedir(p)
            if p not in sys.path:
                sys.path.insert(0, p)

    patterns = [
        "/.local/lib/python*/site-packages",
        "/catalyst/.local/lib/python*/site-packages",
        os.path.expanduser("~/.local/lib/python*/site-packages"),
        "/catalyst/env/lib/python*/site-packages",
        "/catalyst/.venv/lib/python*/site-packages",
        "/catalyst/venv/lib/python*/site-packages",
        "/usr/local/lib/python*/site-packages",
    ]
    for pattern in patterns:
        for p in glob.glob(pattern):
            if os.path.exists(p):
                site.addsitedir(p)
                if p not in sys.path:
                    sys.path.insert(0, p)

    importlib.invalidate_caches()

def search_and_add_site_packages():
    # Common search roots on Catalyst Linux containers
    search_roots = ["/catalyst", "/var/lang", "/usr", "/tmp", "/root"]
    found_paths = set()

    for root_dir in search_roots:
        if not os.path.exists(root_dir):
            continue
        try:
            for root, dirs, files in os.walk(root_dir):
                if "site-packages" in dirs or "dist-packages" in dirs or "django" in dirs:
                    if "site-packages" in dirs:
                        p = os.path.join(root, "site-packages")
                        found_paths.add(p)
                    if "dist-packages" in dirs:
                        p = os.path.join(root, "dist-packages")
                        found_paths.add(p)
                # Limit depth to avoid scanning millions of files
                if root.count(os.sep) - root_dir.count(os.sep) > 4:
                    dirs.clear()
        except Exception:
            pass

    for p in found_paths:
        if p and os.path.exists(p):
            site.addsitedir(p)
            if p not in sys.path:
                sys.path.insert(0, p)
                print(f"[env_setup] Discovered and added site-packages: {p}", flush=True)

def ensure_env():
    tmp_site = "/tmp/site-packages"
    if os.path.exists(tmp_site):
        site.addsitedir(tmp_site)
        if tmp_site not in sys.path:
            sys.path.insert(0, tmp_site)

    add_all_site_packages()

    try:
        import django
        print(f"[env_setup] Found existing Django {django.__version__} - instant boot!", flush=True)
    except ImportError:
        print("[env_setup] Django not found in standard paths. Searching filesystem for site-packages...", flush=True)
        search_and_add_site_packages()
        importlib.invalidate_caches()
        try:
            import django
            print(f"[env_setup] Discovered Django {django.__version__} after filesystem search!", flush=True)
            return
        except ImportError:
            print("[env_setup] Django still not found. Installing requirements to /tmp/site-packages...", flush=True)

        req_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "requirements.txt")
        if os.path.exists(req_file):
            try:
                os.makedirs(tmp_site, exist_ok=True)
                print(f"[env_setup] Installing packages into {tmp_site}...", flush=True)
                subprocess.check_call([sys.executable, "-m", "pip", "install", "--target", tmp_site, "--no-cache-dir", "-r", req_file])
                print("[env_setup] Pip install finished into /tmp/site-packages.", flush=True)
                site.addsitedir(tmp_site)
                if tmp_site not in sys.path:
                    sys.path.insert(0, tmp_site)
                importlib.invalidate_caches()
                import django
                print(f"[env_setup] Successfully installed and loaded Django {django.__version__}", flush=True)
            except Exception as e:
                print(f"[env_setup] pip install / django import failed: {e}", flush=True)
                print(f"[env_setup] Current sys.path: {sys.path}", flush=True)

ensure_env()