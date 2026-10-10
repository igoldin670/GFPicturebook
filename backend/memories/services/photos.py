"""Durable byte storage and bounded decoding. Originals are never rewritten."""
import hashlib
import io
import os
import re
import shutil
import struct
import uuid
import warnings
from datetime import datetime, timedelta, timezone as dt_timezone
from pathlib import Path
from django.conf import settings
from django.db import connection, transaction
from django.utils import timezone
from PIL import Image, ImageOps, ImageCms, UnidentifiedImageError
from pillow_heif import register_heif_opener
from memories.models import Photo, ProcessingJob
from .failures import safe_code

register_heif_opener()
Image.MAX_IMAGE_PIXELS = 50_000_000
FORMATS = {"JPEG": "image/jpeg", "MPO": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp", "HEIF": "image/heic"}

class InvalidImage(Exception):
    pass


def storage_path(key):
    root = settings.PHOTO_ROOT.resolve()
    path = (root / key).resolve()
    if not path.is_relative_to(root) or path == root:
        raise ValueError("Invalid storage path")
    return path


def fsync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def receive(request, identifier, filename):
    """Persist and fsync bytes before committing the database reference.

    Interrupted pre-commit files can be reconciled later; never delete originals
    just because the database commit outcome is uncertain.
    """
    root = settings.PHOTO_ROOT
    staging = root / "staging"
    staging.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(root).free < settings.UPLOAD_MAX_BYTES + settings.PHOTO_FREE_RESERVE:
        raise OSError("Insufficient storage reserve")
    temporary = staging / f"{uuid.uuid4()}.part"
    digest, size = hashlib.sha256(), 0
    try:
        with temporary.open("xb") as output:
            while chunk := request.read(1024 * 1024):
                size += len(chunk)
                if size > settings.UPLOAD_MAX_BYTES:
                    raise InvalidImage("Photo exceeds the 50 MiB limit.")
                digest.update(chunk)
                output.write(chunk)
            if not size:
                raise InvalidImage("The file is empty.")
            output.flush()
            os.fsync(output.fileno())
        with transaction.atomic():
            # Both members share a queue and UUID namespace. Lock the short
            # admission transaction across the library, after streaming the bytes.
            # SQLite is only for single-process local development.
            if connection.vendor == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute("SELECT pg_advisory_xact_lock(%s)", [0x414C42554D])
            existing = Photo.objects.filter(pk=identifier).first()
            if existing:
                if existing.uploaded_by_id != request.user.pk or existing.sha256 != digest.hexdigest():
                    raise InvalidImage("Upload identifier is already used for a different file.")
                return existing
            if Photo.objects.filter(uploaded_by=request.user, uploaded_at__gte=timezone.now()-timedelta(minutes=1)).count() >= 60:
                raise InvalidImage("Upload limit reached. Wait a minute before retrying.")
            if Photo.objects.filter(status=Photo.Status.PENDING).count() >= settings.PHOTO_QUEUE_LIMIT:
                raise InvalidImage("Processing queue is full. Wait before uploading more.")
            # Extension is deliberately absent: only the decoder decides the MIME type.
            key = f"originals/{str(identifier)[:2]}/{identifier}"
            target = storage_path(key)
            target.parent.mkdir(parents=True, exist_ok=True)
            # Hard-link is atomic and refuses to overwrite an existing original.
            try:
                os.link(temporary, target)
            except FileExistsError:
                with target.open("rb") as stored:
                    if hashlib.file_digest(stored, "sha256").hexdigest() != digest.hexdigest():
                        raise InvalidImage("An interrupted upload uses this identifier. Select the file again.")
            fsync_directory(target.parent)
            fsync_directory(target.parent.parent)
            photo = Photo.objects.create(id=identifier, original_filename=filename, original_key=key,
                sha256=digest.hexdigest(), byte_size=size, mime_type="application/octet-stream",
                uploaded_by=request.user, display_date=timezone.localdate(), date_source=Photo.DateSource.UPLOAD)
            ProcessingJob.objects.create(photo=photo, available_at=timezone.now())
            return photo
    finally:
        temporary.unlink(missing_ok=True)


def clean_text(value, limit=150):
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    return str(value or "").strip("\x00 ")[:limit]


def capture_date(exif):
    """Keep local calendar dates without inventing a missing camera timezone."""
    try:
        detail = exif.get_ifd(34665)
    except (KeyError, ValueError, TypeError, SyntaxError, AttributeError, struct.error):
        detail = {}
    merged = {**dict(exif), **detail}
    for tag, offset_tag, subsecond_tag in [(36867, 36881, 37521), (36868, 36882, 37522)]:
        raw = clean_text(merged.get(tag), 100)
        try:
            local = datetime.strptime(raw, "%Y:%m:%d %H:%M:%S")
        except ValueError:
            continue
        fraction = clean_text(merged.get(subsecond_tag), 12)
        if fraction.isdigit():
            local = local.replace(microsecond=int((fraction + "000000")[:6]))
        result = dict(exif_date_raw=raw, taken_local=local.isoformat(), display_date=local.date(), date_source=Photo.DateSource.EXIF)
        offset = clean_text(merged.get(offset_tag), 20)
        if re.fullmatch(r"[+-]\d{2}:\d{2}", offset):
            hours, minutes = int(offset[1:3]), int(offset[4:6])
            if hours <= 14 and minutes < 60 and (hours < 14 or minutes == 0):
                total = (hours * 60 + minutes) * (-1 if offset[0] == "-" else 1)
                try:
                    instant = local.replace(tzinfo=dt_timezone(timedelta(minutes=total))).astimezone(dt_timezone.utc)
                except OverflowError:
                    # A corrupt boundary date must not prevent otherwise valid decoding.
                    pass
                else:
                    result.update(taken_offset_minutes=total, taken_at=instant)
        return result
    return {}


def gps_coordinates(exif):
    try:
        gps = exif.get_ifd(34853)
        def decimal(tag, ref_tag, positive, negative, bound):
            parts = [float(p) for p in gps[tag]]
            ref = clean_text(gps[ref_tag])
            if len(parts) != 3 or ref not in (positive, negative) or not 0 <= parts[0] <= bound or not 0 <= parts[1] < 60 or not 0 <= parts[2] < 60:
                return None
            value = (parts[0] + parts[1]/60 + parts[2]/3600) * (-1 if ref == negative else 1)
            return round(value, 7) if -bound <= value <= bound else None
        return dict(latitude=decimal(2, 1, "N", "S", 90), longitude=decimal(4, 3, "E", "W", 180))
    except (KeyError, ValueError, TypeError, ZeroDivisionError, OverflowError, SyntaxError, AttributeError, struct.error):
        return {}


def save_derivative(image, key, bound):
    path = storage_path(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    resized = image.copy()
    resized.thumbnail((bound, bound), Image.Resampling.LANCZOS)
    # Reconstruct pixels so no EXIF/ICC/GPS metadata leaks into the derivative.
    clean = Image.frombytes(resized.mode, resized.size, resized.tobytes())
    try:
        with temporary.open("wb") as output:
            clean.save(output, "WEBP", quality=85, method=4)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
        fsync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)
        resized.close()
        clean.close()


def process(photo):
    path = storage_path(photo.original_key)
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        try:
            with Image.open(path) as check:
                # MPO is a JPEG container that can include an auxiliary image (e.g.
                # an iPhone gain map). Render its first/main image, not the auxiliary.
                # Other multi-frame formats remain unsupported.
                if check.format not in FORMATS:
                    raise InvalidImage("unsupported_format")
                if check.format != "MPO" and getattr(check, "n_frames", 1) != 1:
                    raise InvalidImage("animated_image")
                check.verify()
            with Image.open(path) as original:
                if original.format == "MPO":
                    original.seek(0)
                original.load()
                photo.mime_type = FORMATS[original.format]
                exif = original.getexif()
                photo.width, photo.height = original.size
                orientation = exif.get(274)
                photo.orientation = orientation if isinstance(orientation, int) and 1 <= orientation <= 8 else None
                photo.camera_make = clean_text(exif.get(271))
                photo.camera_model = clean_text(exif.get(272))
                # Upload-time fallback was recorded at admission and never shifts on retry.
                for key, value in {**capture_date(exif), **gps_coordinates(exif)}.items():
                    setattr(photo, key, value)
                oriented = ImageOps.exif_transpose(original)
                profile = original.info.get("icc_profile")
                try:
                    pixels = ImageCms.profileToProfile(oriented, ImageCms.ImageCmsProfile(io.BytesIO(profile)), ImageCms.createProfile("sRGB"), outputMode="RGB") if profile else oriented.convert("RGB")
                except (ImageCms.PyCMSError, OSError, ValueError):
                    pixels = oriented.convert("RGB")
                photo.thumbnail_key = f"thumbnails/{photo.id}.webp"
                photo.preview_key = f"previews/{photo.id}.webp"
                save_derivative(pixels, photo.thumbnail_key, 400)
                save_derivative(pixels, photo.preview_key, 2048)
                pixels.close()
                oriented.close()
        except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
            raise InvalidImage("image_too_large") from exc
        except FileNotFoundError as exc:
            raise InvalidImage("missing_original") from exc
        except (UnidentifiedImageError, SyntaxError, ValueError) as exc:
            raise InvalidImage("invalid_image") from exc
        except OSError as exc:
            # Pillow uses errno-less OSError for corrupt compressed data. Actual
            # filesystem errors should retain their bounded retry behavior.
            if exc.errno is None:
                raise InvalidImage("invalid_image") from exc
            raise
    photo.status = Photo.Status.READY
    photo.save()


def process_one(job_id=None):
    """Hold a PostgreSQL row lock while decoding: a crash releases it automatically.

    No committed 'processing' state can strand a job. Worker subprocess timeouts
    also release the transaction; the parent records bounded crash attempts.
    """
    with transaction.atomic():
        jobs = ProcessingJob.objects.filter(pk=job_id) if job_id else ProcessingJob.objects.all()
        job = (jobs.select_for_update(skip_locked=True)
               .filter(photo__status=Photo.Status.PENDING, available_at__lte=timezone.now())
               .order_by("available_at", "id").first())
        if not job:
            return False
        photo = Photo.objects.select_for_update().get(pk=job.photo_id)
        job.attempts += 1
        try:
            process(photo)
            job.error_code = ""
        except InvalidImage as exc:
            photo.status = Photo.Status.FAILED
            job.error_code = safe_code(str(exc))
            photo.save(update_fields=["status"])
        except (OSError, MemoryError):
            job.error_code = "storage_unavailable"
            if job.attempts >= 3:
                photo.status = Photo.Status.FAILED
                photo.save(update_fields=["status"])
            job.available_at = timezone.now() + timedelta(seconds=30)
        job.save()
        return True
