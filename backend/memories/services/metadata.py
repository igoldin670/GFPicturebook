"""Read explicit embedded capture dates; never guess from filenames or mtimes."""
from datetime import datetime, timezone, timedelta
import re
import xml.etree.ElementTree as ET
from memories.models import Photo


def parsed_capture(raw, source, offset=None):
    if isinstance(raw, bytes):
        raw = raw.decode('utf-8', errors='replace')
    if not isinstance(raw, str):
        return {}
    raw = raw.strip('\x00 ')
    try:
        # Reject date-only values: these are not a camera capture timestamp.
        if len(raw) < 19:
            return {}
        local = datetime.fromisoformat(raw.replace('Z', '+00:00'))
        if local.tzinfo is None and isinstance(offset, str) and re.fullmatch(r'[+-][0-9]{2}:[0-9]{2}', offset):
            hours, minutes = int(offset[1:3]), int(offset[4:6])
            if hours <= 14 and minutes < 60 and (hours < 14 or minutes == 0):
                total = (hours * 60 + minutes) * (-1 if offset[0] == '-' else 1)
                local = local.replace(tzinfo=timezone(timedelta(minutes=total)))
        result = dict(exif_date_raw=raw[:100], taken_local=local.replace(tzinfo=None).isoformat(),
                      display_date=local.date(), date_source=source)
        if local.utcoffset() is not None:
            minutes = int(local.utcoffset().total_seconds() / 60)
            if abs(minutes) > 840:
                return {}
            result.update(taken_offset_minutes=minutes, taken_at=local.astimezone(timezone.utc))
        return result
    except (ValueError, OverflowError):
        return {}


def image_capture(image):
    from .photos import capture_date
    metadata = capture_date(image.getexif())
    if metadata:
        return metadata
    raw = image.info.get('xmp')
    if not isinstance(raw, (str, bytes)) or len(raw) > 1024 * 1024:
        return {}
    try:
        root = ET.fromstring(raw)
        # Specific original-capture fields take precedence over XMP creation.
        for field in ['{http://ns.adobe.com/exif/1.0/}DateTimeOriginal', '{http://ns.adobe.com/xap/1.0/}CreateDate']:
            for node in root.iter():
                value = node.attrib.get(field) or (node.text if node.tag == field else None)
                metadata = parsed_capture(value, Photo.DateSource.EXIF)
                if metadata:
                    return metadata
    except (ET.ParseError, ValueError):
        pass
    return {}


def video_capture(metadata):
    streams = [s for s in metadata.get('streams', []) if s.get('codec_type') == 'video']
    for section in [*streams, metadata.get('format', {})]:
        tags = section.get('tags', {})
        for key in ['com.apple.quicktime.creationdate', 'creation_time']:
            capture = parsed_capture(tags.get(key), Photo.DateSource.FILE)
            if capture:
                return capture
    return {}


def apply_capture(photo, metadata):
    for key, value in metadata.items():
        if photo.date_source == Photo.DateSource.MANUAL and key in {'display_date', 'date_source'}:
            continue
        setattr(photo, key, value)
