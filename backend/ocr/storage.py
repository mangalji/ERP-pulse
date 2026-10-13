"""
Host-agnostic file storage for OCR documents.

Where uploaded files live is chosen by ``OCR_STORAGE_BACKEND``:

auto   (default) local disk when ``MEDIA_ROOT`` is writable, otherwise
       PostgreSQL - so a read-only / stateless host still works.
local  ``MEDIA_ROOT`` on disk (needs a persistent, shared volume when
       several app instances or a separate worker are used).
db     PostgreSQL (no extra service, works on stateless hosts and with
       several instances; best for moderate file sizes).
s3     Any S3-compatible bucket (AWS S3, GCS interoperability, R2, MinIO).
       Requires ``pip install django-storages boto3``.

The OCR engine never assumes a local path: ``local_file_path`` materialises
any stored file into a scratch directory when the backend has no filesystem
path, and ``resolve_scratch_dir`` falls back to the system temp directory
when ``MEDIA_ROOT`` is not writable.
"""

from __future__ import annotations

import logging
import os
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage, Storage
from django.utils.deconstruct import deconstructible

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Scratch directories
# ---------------------------------------------------------------------------


def _is_writable_dir(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=path):
            pass
        return True
    except OSError:
        return False


def resolve_scratch_dir(sub: str) -> Path:
    """
    A writable scratch directory for temporary OCR work (page images ...).

    ``OCR_SCRATCH_DIR`` (if set) or ``MEDIA_ROOT/ocr/<sub>``; falls back to the
    system temp directory when that location is read-only.
    """
    base = (getattr(settings, "OCR_SCRATCH_DIR", "") or "").strip()
    preferred = Path(base) / sub if base else Path(settings.MEDIA_ROOT) / "ocr" / sub
    fallback = Path(tempfile.gettempdir()) / "erp-pulse-ocr" / sub

    if _is_writable_dir(preferred):
        return preferred

    logger.warning(
        "OCR scratch directory %s is not writable; using %s instead",
        preferred,
        fallback,
    )
    _is_writable_dir(fallback)
    return fallback


# ---------------------------------------------------------------------------
# PostgreSQL-backed storage
# ---------------------------------------------------------------------------


@deconstructible
class DatabaseStorage(Storage):
    """Stores file contents in PostgreSQL (``OCRStoredFile``)."""

    @staticmethod
    def _model():
        from ocr.models import OCRStoredFile

        return OCRStoredFile

    @staticmethod
    def _norm(name: str) -> str:
        return str(name).replace("\\", "/").lstrip("/")

    def _open(self, name, mode="rb"):
        if any(flag in mode for flag in ("w", "a", "+")):
            raise NotImplementedError("DatabaseStorage files are opened read-only.")

        name = self._norm(name)
        try:
            row = self._model().objects.get(name=name)
        except self._model().DoesNotExist as exc:
            raise FileNotFoundError(name) from exc
        return ContentFile(bytes(row.content), name=name)

    def _save(self, name, content):
        name = self._norm(name)
        if hasattr(content, "seek"):
            content.seek(0)
        data = b"".join(content.chunks()) if hasattr(content, "chunks") else content.read()
        self._model().objects.update_or_create(
            name=name,
            defaults={"content": data, "size": len(data)},
        )
        return name

    def exists(self, name):
        return self._model().objects.filter(name=self._norm(name)).exists()

    def delete(self, name):
        self._model().objects.filter(name=self._norm(name)).delete()

    def size(self, name):
        row = self._model().objects.filter(name=self._norm(name)).values_list("size", flat=True).first()
        if row is None:
            raise FileNotFoundError(name)
        return row

    def url(self, name):
        raise NotImplementedError("Database storage has no public URL.")

    def listdir(self, path):
        return [], []


# ---------------------------------------------------------------------------
# Backend selection
# ---------------------------------------------------------------------------

_storage = None


def _build_s3():
    from storages.backends.s3 import S3Storage  # optional dependency

    options = {
        "bucket_name": getattr(settings, "OCR_S3_BUCKET", ""),
        "region_name": getattr(settings, "OCR_S3_REGION", "") or None,
        "endpoint_url": getattr(settings, "OCR_S3_ENDPOINT_URL", "") or None,
        "access_key": getattr(settings, "OCR_S3_ACCESS_KEY_ID", "") or None,
        "secret_key": getattr(settings, "OCR_S3_SECRET_ACCESS_KEY", "") or None,
        "querystring_auth": True,
        "file_overwrite": False,
        "default_acl": None,
    }
    if not options["bucket_name"]:
        raise ValueError("OCR_S3_BUCKET is not set")
    return S3Storage(**{k: v for k, v in options.items() if v is not None})


def _build_local() -> FileSystemStorage:
    return FileSystemStorage(
        location=str(settings.MEDIA_ROOT),
        base_url=settings.MEDIA_URL,
    )


def _build_storage() -> Storage:
    backend = (getattr(settings, "OCR_STORAGE_BACKEND", "auto") or "auto").strip().lower()

    if backend == "s3":
        try:
            return _build_s3()
        except Exception as exc:  # noqa: BLE001 - never crash the app on boot
            logger.warning(
                "OCR_STORAGE_BACKEND=s3 is not usable (%s: %s); storing OCR "
                "files in PostgreSQL instead",
                type(exc).__name__,
                exc,
            )
            return DatabaseStorage()

    if backend == "db":
        return DatabaseStorage()

    if backend not in ("auto", "local"):
        logger.warning("Unknown OCR_STORAGE_BACKEND=%r; using 'auto'", backend)
        backend = "auto"

    local = _build_local()

    if backend == "local" or _is_writable_dir(Path(settings.MEDIA_ROOT)):
        return local

    logger.warning(
        "MEDIA_ROOT %s is not writable; storing OCR files in PostgreSQL instead "
        "(set OCR_STORAGE_BACKEND explicitly to silence this)",
        settings.MEDIA_ROOT,
    )
    return DatabaseStorage()


def get_storage() -> Storage:
    global _storage
    if _storage is None:
        _storage = _build_storage()
    return _storage


def ocr_file_storage() -> Storage:
    """Callable used as ``FileField(storage=...)`` for every OCR file field."""
    return get_storage()


def storage_backend_name(storage: Storage | None = None) -> str:
    storage = storage or get_storage()
    if isinstance(storage, DatabaseStorage):
        return "db"
    if isinstance(storage, FileSystemStorage):
        return "local"
    return "s3" if "S3" in type(storage).__name__ else type(storage).__name__.lower()


def storage_self_test() -> tuple[bool, str]:
    """Write, read back and delete a tiny probe file (used by the health check)."""
    storage = get_storage()
    name = f"ocr/.healthcheck-{os.getpid()}.txt"
    try:
        saved = storage.save(name, ContentFile(b"ok"))
        try:
            with storage.open(saved, "rb") as handle:
                if handle.read() != b"ok":
                    return False, "read-back mismatch"
        finally:
            storage.delete(saved)
        return True, ""
    except Exception as exc:  # noqa: BLE001
        return False, f"{type(exc).__name__}"


# ---------------------------------------------------------------------------
# Local path for the engine
# ---------------------------------------------------------------------------


@contextmanager
def local_file_path(field_file):
    """
    Yield a local filesystem path for a stored file.

    Backends with real paths (local disk) are used in place; others (database,
    S3) are copied into a scratch directory that is removed afterwards.
    """
    from ocr.exceptions import DocumentProcessingException

    storage = field_file.storage
    name = field_file.name

    try:
        path = storage.path(name)
    except NotImplementedError:
        path = None

    if path and os.path.exists(path):
        yield path
        return

    tmpdir = None
    try:
        tmpdir = tempfile.mkdtemp(prefix="ocr-src-", dir=resolve_scratch_dir("src"))
        target = os.path.join(tmpdir, Path(name).name)
        with storage.open(name, "rb") as src, open(target, "wb") as dst:
            shutil.copyfileobj(src, dst)
    except (FileNotFoundError, OSError) as exc:
        if tmpdir:
            shutil.rmtree(tmpdir, ignore_errors=True)
        raise DocumentProcessingException(
            "The uploaded file is no longer available on the server."
        ) from exc

    try:
        yield target
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)