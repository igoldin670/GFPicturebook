"""Same-origin, session-authenticated photo endpoints. No public media URLs."""
import json
import uuid
import re
from pathlib import Path
from datetime import date
from functools import wraps
from urllib.parse import unquote
from django.conf import settings
from django.core import signing
from django.db.models import Q
from django.http import FileResponse, JsonResponse, Http404, StreamingHttpResponse, HttpResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET, require_POST
from memories.models import Photo
from memories.services.photos import receive, storage_path, InvalidImage


def member(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Sign in required."}, status=401)
        return view(request, *args, **kwargs)
    return wrapped


def visible():
    return Photo.objects.filter(status=Photo.Status.READY, trashed_at__isnull=True)


def serialize(photo):
    return {"id": str(photo.id), "filename": photo.original_filename, "date": photo.display_date.isoformat(),
            "dateSource": photo.date_source, "caption": photo.caption, "width": photo.width, "height": photo.height,
            "kind": photo.media_kind, "duration": photo.duration, "byteSize": photo.byte_size,
            "playback": f"/api/photos/{photo.id}/stream/" if photo.playback_mime else None,
            "camera": " ".join(filter(None, [photo.camera_make, photo.camera_model])),
            "latitude": str(photo.latitude) if photo.latitude is not None else None,
            "longitude": str(photo.longitude) if photo.longitude is not None else None,
            "thumbnail": f"/api/photos/{photo.id}/thumbnail/", "preview": f"/api/photos/{photo.id}/preview/",
            "original": f"/api/photos/{photo.id}/original/", "status": photo.status}


@require_POST
@member
def upload(request):
    if request.content_type != "application/octet-stream":
        return JsonResponse({"error": "Send one binary media file per request."}, status=415)
    try:
        identifier = uuid.UUID(request.headers.get("Idempotency-Key", ""))
        length = int(request.headers.get("Content-Length", "0"))
    except (ValueError, TypeError):
        return JsonResponse({"error": "Invalid upload identifier or length."}, status=400)
    filename = unquote(request.headers.get("X-Filename", "photo"))
    filename = filename.replace("\\", "/").split("/")[-1]
    filename = "".join(c for c in filename if c.isprintable())[:255] or "photo"
    maximum = settings.VIDEO_MAX_BYTES if Path(filename).suffix.lower() in {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"} else settings.UPLOAD_MAX_BYTES
    if length < 0 or length > maximum:
        return JsonResponse({"error": "File exceeds the upload limit."}, status=413)
    try:
        photo = receive(request, identifier, filename)
    except InvalidImage as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    except OSError:
        return JsonResponse({"error": "Storage is unavailable or running low. Try again later."}, status=507)
    return JsonResponse({"id": str(photo.id), "status": photo.status}, status=202)


@require_GET
@member
def gallery(request):
    query = visible()
    cursor = request.GET.get("cursor")
    if cursor:
        try:
            calendar, identifier = signing.loads(cursor, salt="photo-page", max_age=86400)
            calendar, identifier = date.fromisoformat(calendar), uuid.UUID(identifier)
        except (signing.BadSignature, ValueError, TypeError):
            return JsonResponse({"error": "This page has expired. Refresh the gallery."}, status=400)
        query = query.filter(Q(display_date__lt=calendar) | Q(display_date=calendar, id__lt=identifier))
    rows = list(query.order_by("-display_date", "-id")[:49])
    page = rows[:48]
    next_cursor = signing.dumps([page[-1].display_date.isoformat(), str(page[-1].id)], salt="photo-page") if len(rows) > 48 else None
    return JsonResponse({"photos": [serialize(photo) for photo in page], "next": next_cursor})


@require_GET
@member
def upload_status(request):
    rows = Photo.objects.filter(uploaded_by=request.user, trashed_at__isnull=True).exclude(status=Photo.Status.READY).order_by("-uploaded_at")[:100]
    return JsonResponse({"uploads": [{"id": str(p.id), "filename": p.original_filename, "status": p.status,
        "message": "Unable to process this file. Unsupported, damaged, oversized, or a processing failure; your uploaded bytes are retained." if p.status == Photo.Status.FAILED else "Preparing this memory…"} for p in rows]})


def byte_range(value, size):
    match = re.fullmatch(r"bytes=(\d*)-(\d*)", value)
    if not match or not any(match.groups()) or size <= 0:
        raise ValueError()
    first, last = match.groups()
    if not first:
        suffix = int(last)
        if suffix <= 0:
            raise ValueError()
        return max(0, size - suffix), size - 1
    start = int(first)
    end = min(int(last), size - 1) if last else size - 1
    if start >= size or end < start:
        raise ValueError()
    return start, end


@require_GET
@member
def media(request, identifier, variant):
    photo = get_object_or_404(visible(), pk=identifier)
    if variant not in {"thumbnail", "preview", "original", "stream"}:
        raise Http404
    if variant == "stream" and (photo.media_kind != "video" or not photo.playback_mime):
        raise Http404
    actual = ("playback" if photo.playback_key else "original") if variant == "stream" else variant
    from memories.services.archive import verified_source
    from memories.services.cache import media_source
    context = None
    try:
        source = media_source(photo, actual)
        if source is None:
            context = verified_source(photo, actual)
            source = context.__enter__()
        source.seek(0, 2)
        size = source.tell()
        source.seek(0)
    except (OSError, ValueError):
        raise Http404
    def release():
        source.close()
        if context is not None:
            context.__exit__(None, None, None)
    content_type = photo.playback_mime if variant == "stream" else photo.mime_type if variant == "original" else "image/webp"
    if variant == "stream" and request.headers.get("Range"):
        try:
            start, end = byte_range(request.headers["Range"], size)
        except ValueError:
            release()
            response = HttpResponse(status=416)
            response["Content-Range"] = f"bytes */{size}"
            return response
        source.seek(start)
        def chunks():
            remaining = end - start + 1
            try:
                while remaining:
                    chunk = source.read(min(1024 * 1024, remaining))
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    yield chunk
            finally:
                release()
        response = StreamingHttpResponse(chunks(), status=206, content_type=content_type)
        response._resource_closers.append(release)
        response["Content-Range"] = f"bytes {start}-{end}/{size}"
        response["Content-Length"] = str(end - start + 1)
    else:
        response = FileResponse(source, content_type=content_type, as_attachment=variant == "original",
            filename=photo.original_filename if variant == "original" else f"{photo.id}.mp4" if variant == "stream" else f"{photo.id}.webp")
        response._resource_closers.append(release)
    response["Accept-Ranges"] = "bytes" if variant == "stream" else "none"
    return response


@require_POST
@member
def edit(request, identifier):
    if request.content_type != "application/json":
        return JsonResponse({"error": "Expected JSON."}, status=415)
    try:
        payload = json.loads(request.body)
        caption = payload["caption"]
        calendar = date.fromisoformat(payload["date"])
        if not isinstance(caption, str) or len(caption) > 5000:
            raise ValueError()
    except (KeyError, ValueError, TypeError):
        return JsonResponse({"error": "Provide a valid date and a caption of at most 5,000 characters."}, status=400)
    photo = get_object_or_404(visible(), pk=identifier)
    photo.caption = caption
    if photo.display_date != calendar:
        photo.display_date = calendar
        photo.date_source = Photo.DateSource.MANUAL
    # Original EXIF facts and bytes remain untouched by a calendar-date correction.
    photo.save(update_fields=["caption", "display_date", "date_source"])
    return JsonResponse(serialize(photo))
