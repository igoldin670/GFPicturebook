"""Verified, crash-recoverable replication. No operation deletes originals."""
import hashlib
import os
import shutil
import uuid
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path
from django.conf import settings
from django.db import transaction
from django.db.models import Count, Q, F
from django.utils import timezone
from memories.models import Photo, StoredAsset, FileReplica, StorageJob, StorageDrive
from .drives import refresh_drives, drive_root, asset_path


class IntegrityError(OSError):
    pass


def record_drive_error(drive, integrity=False):
    changes = dict(last_io_error_at=timezone.now())
    if integrity:
        changes['integrity_failures'] = F('integrity_failures') + 1
    StorageDrive.objects.filter(pk=drive.pk).update(**changes)


def checksum(source):
    digest = hashlib.sha256()
    while chunk := source.read(settings.MEDIA_BUFFER_BYTES):
        digest.update(chunk)
    source.seek(0)
    return digest.hexdigest()


def verify(source, expected, size):
    if os.fstat(source.fileno()).st_size != size or checksum(source) != expected:
        raise IntegrityError("Checksum mismatch")
    return source


def register_assets(photo):
    from .photos import storage_path
    keys = [('original', photo.original_key), ('thumbnail', photo.thumbnail_key),
            ('preview', photo.preview_key), ('playback', photo.playback_key)]
    for variant, key in keys:
        if not key or StoredAsset.objects.filter(photo=photo, variant=variant).exists():
            continue
        if variant == 'original':
            expected, size = photo.sha256, photo.byte_size
        else:
            # Initial manifest for generated derivatives; subsequent checks must
            # match this hash rather than accepting changed/corrupt bytes.
            with storage_path(key).open('rb') as source:
                expected, size = checksum(source), os.fstat(source.fileno()).st_size
        StoredAsset.objects.get_or_create(photo=photo, variant=variant,
            defaults=dict(key=key, sha256=expected, byte_size=size))


@contextmanager
def verified_source(photo, variant, drives=None):
    """Hash an opened descriptor, then serve/copy that same descriptor."""
    from .photos import storage_path
    asset = StoredAsset.objects.filter(photo=photo, variant=variant).first()
    key = {'original': photo.original_key, 'thumbnail': photo.thumbnail_key,
           'preview': photo.preview_key, 'playback': photo.playback_key}.get(variant)
    if not key:
        raise FileNotFoundError()
    expected = asset.sha256 if asset else photo.sha256 if variant == 'original' else None
    size = asset.byte_size if asset else photo.byte_size if variant == 'original' else None
    # Drive verification is performed even when its last observation said offline;
    # a reconnected good copy becomes available immediately.
    replicas = asset.replicas.select_related('drive').all() if asset else []
    for replica in replicas:
        try:
            with drive_root(replica.drive) as root:
                source = asset_path(root, key).open('rb')
                try:
                    verify(source, expected, size)
                except BaseException:
                    source.close()
                    raise
        except IntegrityError:
            record_drive_error(replica.drive, integrity=True)
            FileReplica.objects.filter(pk=replica.pk).update(state='corrupt')
            continue
        except (OSError, ValueError):
            FileReplica.objects.filter(pk=replica.pk).update(state='missing')
            continue
        try:
            yield source
        finally:
            source.close()
        return
    # Legacy/staging files remain as a non-destructive fallback, never counted
    # as physical-drive replicas. Existing photos keep working before migration.
    source = storage_path(key).open('rb')
    try:
        if expected:
            verify(source, expected, size)
        yield source
    finally:
        source.close()


def sync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def write_replica(asset, drive, source):
    with drive_root(drive) as root:
        target = asset_path(root, asset.key)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            try:
                with target.open('rb') as present:
                    verify(present, asset.sha256, asset.byte_size)
                return  # Never rewrite a healthy copy.
            except IntegrityError:
                pass
        if shutil.disk_usage(root).free < asset.byte_size + settings.STORAGE_FREE_RESERVE:
            raise OSError("Drive full")
        temporary = target.parent / f'.{target.name}.{uuid.uuid4()}.part'
        try:
            source.seek(0)
            digest, written = hashlib.sha256(), 0
            with temporary.open('xb') as output:
                while chunk := source.read(settings.MEDIA_BUFFER_BYTES):
                    written += len(chunk)
                    output.write(chunk)
                    digest.update(chunk)
                output.flush()
                os.fsync(output.fileno())
            if written != asset.byte_size or digest.hexdigest() != asset.sha256:
                raise IntegrityError("Source changed during copy")
            # Read-back verification catches bad writes before publication.
            with temporary.open('rb') as check:
                verify(check, asset.sha256, asset.byte_size)
            # All archive writers serialize on the Photo row. A crash leaves only
            # a private .part, or a complete file which the retry can adopt.
            os.replace(temporary, target)
            parent = target.parent
            while parent != root:
                sync_directory(parent)
                parent = parent.parent
            sync_directory(root)
            with target.open('rb') as check:
                verify(check, asset.sha256, asset.byte_size)
        finally:
            temporary.unlink(missing_ok=True)


def reconcile_asset(asset, drives):
    healthy = []
    for drive in drives:
        replica, _ = FileReplica.objects.get_or_create(asset=asset, drive=drive)
        state = 'missing'
        if drive.status in {'online', 'full'}:
            try:
                with drive_root(drive) as root, asset_path(root, asset.key).open('rb') as source:
                    verify(source, asset.sha256, asset.byte_size)
                state = 'verified'
            except IntegrityError:
                record_drive_error(drive, integrity=True)
                state = 'corrupt'
            except (OSError, ValueError):
                state = 'missing'
        else:
            state = 'offline'
        replica.state = state
        if state == 'verified':
            replica.verified_at = timezone.now()
            healthy.append(drive)
        replica.save()
    physical = {d.physical_id for d in healthy}
    if len(physical) < 2:
        try:
            with verified_source(asset.photo, asset.variant) as source:
                for drive in sorted(drives, key=lambda d: -d.free_bytes):
                    if len(physical) >= 2:
                        break
                    if drive.status != 'online' or drive.physical_id in physical:
                        continue
                    try:
                        write_replica(asset, drive, source)
                    except (OSError, ValueError):
                        record_drive_error(drive)
                        FileReplica.objects.filter(asset=asset, drive=drive).update(state='write_failed')
                        continue
                    FileReplica.objects.filter(asset=asset, drive=drive).update(state='verified', verified_at=timezone.now())
                    physical.add(drive.physical_id)
        except (OSError, ValueError):
            pass
    # Recheck availability and both published files at completion. A drive may
    # disconnect or a source may change while a large replication is running.
    physical = set()
    by_uuid = {d.uuid: d for d in drives}
    for replica in asset.replicas.filter(state='verified').select_related('drive'):
        drive = by_uuid.get(replica.drive_id)
        if not drive or drive.status not in {'online', 'full'}:
            replica.state = 'offline'
        else:
            try:
                with drive_root(drive) as root, asset_path(root, asset.key).open('rb') as source:
                    verify(source, asset.sha256, asset.byte_size)
                physical.add(drive.physical_id)
                replica.verified_at = timezone.now()
            except IntegrityError:
                replica.state = 'corrupt'
            except (OSError, ValueError):
                replica.state = 'missing'
        replica.save()
    asset.protection = 'protected' if len(physical) >= 2 else 'degraded' if physical else 'unprotected'
    asset.checked_at = timezone.now()
    asset.save(update_fields=['protection', 'checked_at'])
    return len(physical) >= 2


def schedule(photo):
    # Run after the decoding transaction releases Photo: archive jobs lock
    # StorageJob then Photo, so updating a job while holding Photo would invert
    # that order and deadlock concurrent decoders/replication.
    transaction.on_commit(lambda: StorageJob.objects.update_or_create(photo_id=photo.pk,
        defaults=dict(status='pending', available_at=timezone.now(), error_code='')))


def run_one(job_id=None, drives=None):
    if drives is None:
        drives = refresh_drives()
    with transaction.atomic():
        jobs = StorageJob.objects.filter(pk=job_id) if job_id else StorageJob.objects.all()
        # An explicit job ID is a supervisor claim with a short restart lease.
        if not job_id:
            jobs = jobs.filter(available_at__lte=timezone.now())
        job = jobs.select_for_update(skip_locked=True).order_by('available_at', 'id').first()
        if not job:
            return False
        photo = Photo.objects.select_for_update().get(pk=job.photo_id)
        job.attempts += 1
        job.started_at = timezone.now()
        job.status = 'running'
        job.save()
        try:
            register_assets(photo)
            results = [reconcile_asset(asset, drives) for asset in photo.assets.all()]
            complete = bool(results) and all(results)
            job.error_code = '' if complete else 'awaiting_verified_replicas'
        except (OSError, ValueError):
            complete = False
            job.error_code = 'source_unavailable'
        job.completed_at = timezone.now()
        job.status = 'idle' if complete else 'retry'
        job.available_at = timezone.now() + timedelta(seconds=settings.STORAGE_CHECK_SECONDS if complete else settings.STORAGE_RETRY_SECONDS)
        job.save()
        return True


def update_protection():
    # Recompute live availability across the entire library, including assets
    # outside the current dashboard page. Offline/excluded copies cannot count.
    counts = StoredAsset.objects.annotate(copies=Count('replicas__drive__physical_id',
        filter=Q(replicas__state='verified', replicas__drive__status__in=['online','full']) & ~Q(replicas__drive__physical_id=''), distinct=True))
    for state, query in [('protected', counts.filter(copies__gte=2)),
                         ('degraded', counts.filter(copies=1)), ('unprotected', counts.filter(copies=0))]:
        StoredAsset.objects.filter(pk__in=query.values('pk')).exclude(protection=state).update(protection=state)


def inventory():
    """Gradual legacy adoption and urgent repair when a drive's state changes."""
    previous = list(StorageDrive.objects.values_list('uuid', 'status', 'physical_id'))
    drives = refresh_drives()
    current = [(d.uuid, d.status, d.physical_id) for d in drives]
    if sorted(previous) != sorted(current):
        StorageJob.objects.exclude(status='running').update(available_at=timezone.now(), status='pending')
        update_protection()
    for photo in Photo.objects.filter(storage_job__isnull=True).order_by('uploaded_at')[:100]:
        StorageJob.objects.get_or_create(photo=photo)
    return drives
