"""Small verified-media RAM cache with a strict per-process byte budget.

Large originals/videos stream. Linux's page cache can use the remaining RAM.
Replica repair never trusts this cache: it rehashes disk descriptors.
"""
import io
import threading
from collections import OrderedDict
from django.conf import settings

_lock = threading.Lock()
_items = OrderedDict()
_bytes = 0


def media_source(photo, variant):
    from .archive import verified_source
    # Cache only generated still images, not originals or large video streams.
    if variant not in {'thumbnail', 'preview'} or photo.media_kind == 'video' and variant == 'preview':
        return None
    from memories.models import StoredAsset
    asset = StoredAsset.objects.filter(photo=photo, variant=variant).first()
    # Before a manifest exists, bypass cache rather than trust untracked bytes.
    if not asset or asset.byte_size > settings.MEDIA_CACHE_FILE_BYTES:
        return None
    # Expire each generation every minute; accesses remain session-authorized.
    import time
    key = (asset.pk, asset.sha256, int(time.monotonic() // 60))
    with _lock:
        value = _items.get(key)
        if value is not None:
            _items.move_to_end(key)
            return io.BytesIO(value)
    with verified_source(photo, variant) as source:
        value = source.read(settings.MEDIA_CACHE_FILE_BYTES + 1)
    if len(value) > settings.MEDIA_CACHE_FILE_BYTES or len(value) > settings.MEDIA_CACHE_BYTES:
        return None
    global _bytes
    with _lock:
        if key not in _items:
            while _items and (_bytes + len(value) > settings.MEDIA_CACHE_BYTES or len(_items) >= 4096):
                _, old = _items.popitem(last=False)
                _bytes -= len(old)
            _items[key] = value
            _bytes += len(value)
    return io.BytesIO(value)
