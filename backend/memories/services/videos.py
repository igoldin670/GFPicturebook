"""Local FFmpeg derivatives. Original descriptors are read-only and never modified."""
import json
import math
import os
import subprocess
import uuid
from pathlib import Path
from django.conf import settings
from .photos import InvalidImage, storage_path, fsync_directory


def is_video(source):
    source.seek(0)
    header = source.read(64)
    source.seek(0)
    if header[4:8] == b'ftyp' and header[8:12] in {b'heic', b'heix', b'hevc', b'hevx', b'mif1', b'msf1', b'avif', b'avis'}:
        return False
    return (header[4:8] in {b'ftyp', b'moov', b'mdat', b'wide', b'free'} or
            header.startswith(b'\x1aE\xdf\xa3') or header[:4] == b'RIFF' and header[8:12] == b'AVI ')


def command(program, source, args, timeout):
    # Network protocols are excluded even if a crafted media file references one.
    base = [program, '-v', 'error', '-protocol_whitelist', 'file,pipe',
            '-probesize', '10000000', '-analyzeduration', '10000000']
    return subprocess.run(base + args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, pass_fds=(source.fileno(),), timeout=timeout, check=True)


def derivative(photo, source, key, args, timeout):
    target = storage_path(key)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.parent / f'.{target.stem}.{uuid.uuid4()}{target.suffix}'
    try:
        command('ffmpeg', source, ['-nostdin', '-filter_threads', '2', '-filter_complex_threads', '2', '-threads', '2', '-i', f'/proc/self/fd/{source.fileno()}',
            '-map_metadata', '-1', '-map_chapters', '-1'] + args + ['-threads', '2', '-y', str(temporary)], timeout)
        with temporary.open('rb') as result:
            os.fsync(result.fileno())
        os.replace(temporary, target)
        fsync_directory(target.parent)
    except subprocess.CalledProcessError as exc:
        raise OSError("Video derivative failed; retry retained original") from exc
    finally:
        temporary.unlink(missing_ok=True)


def process_video(photo, source):
    try:
        probe = command('ffprobe', source, ['-show_streams', '-show_format', '-of', 'json',
            f'/proc/self/fd/{source.fileno()}'], 30)
        metadata = json.loads(probe.stdout)
        stream = next(s for s in metadata['streams'] if s.get('codec_type') == 'video' and not s.get('disposition', {}).get('attached_pic'))
        width, height = int(stream['width']), int(stream['height'])
        duration = float(metadata.get('format', {}).get('duration', stream.get('duration', 0)))
        if not 0 < width * height <= 50_000_000 or not math.isfinite(duration) or duration <= 0:
            raise ValueError()
        formats = set(metadata['format']['format_name'].split(','))
        if not formats.intersection({'mov', 'mp4', 'm4a', '3gp', '3g2', 'mj2', 'matroska', 'webm', 'avi'}):
            raise ValueError()
        photo.media_kind = 'video'
        photo.mime_type = ('video/x-msvideo' if 'avi' in formats else 'video/webm' if formats <= {'matroska', 'webm'} and stream['codec_name'] in {'vp8', 'vp9', 'av1'} else 'video/x-matroska' if 'matroska' in formats else 'video/quicktime' if Path(photo.original_filename).suffix.lower() == '.mov' else 'video/mp4')
        photo.width, photo.height, photo.duration = width, height, duration
        photo.thumbnail_key = f'thumbnails/{photo.id}.webp'
        photo.preview_key = ''
        # Frame selection/rotation is handled by FFmpeg; derivatives strip metadata.
        derivative(photo, source, photo.thumbnail_key,
            ['-ss', str(min(1, duration / 4)), '-map', '0:v:0', '-frames:v', '1',
             '-vf', 'scale=400:400:force_original_aspect_ratio=decrease', '-c:v', 'libwebp'], 60)
        audio = [s for s in metadata['streams'] if s.get('codec_type') == 'audio']
        native = bool(formats.intersection({'mov', 'mp4'})) and stream['codec_name'] == 'h264' and all(s['codec_name'] == 'aac' for s in audio)
        if settings.VIDEO_TRANSCODE:
            photo.playback_key = f'playbacks/{photo.id}.mp4'
            derivative(photo, source, photo.playback_key,
                ['-map', '0:v:0', '-map', '0:a:0?', '-vf', "scale=w='min(1920,iw)':h='min(1080,ih)':force_original_aspect_ratio=decrease:force_divisible_by=2",
                 '-c:v', 'libx264', '-preset', 'fast', '-crf', '23', '-pix_fmt', 'yuv420p',
                 '-c:a', 'aac', '-b:a', '160k', '-movflags', '+faststart'], settings.VIDEO_TIMEOUT_SECONDS)
            photo.playback_mime = 'video/mp4'
        elif native:
            photo.playback_mime = 'video/mp4'
        else:
            photo.playback_mime = ''
        photo.status = 'ready'
        photo.save()
        from .archive import schedule
        schedule(photo)
    except subprocess.TimeoutExpired as exc:
        raise OSError("Video processing timed out") from exc
    except (subprocess.CalledProcessError, ValueError, KeyError, StopIteration) as exc:
        raise InvalidImage('invalid_or_unsupported_video') from exc
