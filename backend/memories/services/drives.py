"""Read-only identity checks. Never mount, format, repair, or erase a drive."""
import os
import errno
import shutil
from contextlib import contextmanager
from pathlib import Path
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils import timezone
from memories.models import StorageDrive


def configuration():
    entries = settings.STORAGE_DRIVES
    if entries and len(entries) != 4:
        raise ImproperlyConfigured("Configure exactly four archive drives.")
    ids, paths = set(), []
    for entry in entries:
        identifier = entry.get("uuid", "")
        path = Path(entry.get("path", ""))
        if not identifier or len(identifier) > 100 or '/' in identifier or identifier in ids or not path.is_absolute():
            raise ImproperlyConfigured("Drive UUIDs must be unique and paths absolute.")
        resolved = path.resolve()
        if any(resolved == p or resolved.is_relative_to(p) or p.is_relative_to(resolved) for p in paths):
            raise ImproperlyConfigured("Archive drive paths must not overlap.")
        ids.add(identifier)
        paths.append(resolved)
    return entries


def identity(entry):
    root = Path(entry['path'])
    if not root.is_dir() or root.is_symlink():
        raise OSError("offline")
    dev = root.stat().st_dev
    if settings.STORAGE_SIMULATED:
        if (root / '.archive-test-id').read_text().strip() != entry['uuid']:
            raise OSError("offline")
        return dev, 'simulated:' + entry['uuid']
    # A missing mount falls back to the host filesystem: the UUID check rejects it.
    device = Path('/dev/disk/by-uuid') / entry['uuid']
    # Container bind mounts expose UUID symlinks but not block-device nodes.
    # Resolve the symlink's kernel name via read-only sysfs when necessary.
    try:
        expected_dev = device.stat().st_rdev
    except FileNotFoundError:
        if not device.is_symlink():
            raise OSError("Filesystem UUID unavailable")
        kernel_name = Path(os.readlink(device)).name
        number = (Path('/sys/class/block') / kernel_name / 'dev').read_text().strip()
        major, minor = map(int, number.split(':'))
        expected_dev = os.makedev(major, minor)
    if expected_dev != dev:
        raise OSError("UUID mismatch or unmounted drive")
    block = (Path('/sys/dev/block') / f'{os.major(dev)}:{os.minor(dev)}').resolve(strict=True)
    if (block / 'partition').exists():
        block = block.parent
    # Multi-device/LVM/RAID mappings need an explicit topology implementation;
    # rejecting them is safer than counting two filesystems on one physical disk.
    if not (block / 'device').exists() or list((block / 'slaves').glob('*')):
        raise OSError("Physical disk topology unavailable or unsupported")
    physical = str(block.resolve())
    for relative in ['device/wwid', 'wwid', 'device/serial']:
        candidate = block / relative
        if candidate.exists():
            physical = candidate.read_text().strip() or physical
            break
    return dev, physical


def probe(entry):
    result = dict(label=entry.get('label', entry['uuid']), path=entry['path'], checked_at=timezone.now(),
                  status='offline', health='Unavailable', total_bytes=0, free_bytes=0, physical_id='')
    try:
        _, physical = identity(entry)
        usage = shutil.disk_usage(entry['path'])
        result.update(physical_id=physical, total_bytes=usage.total, free_bytes=usage.free,
                      status='excluded' if entry.get('excluded') else 'full' if usage.free <= settings.STORAGE_FREE_RESERVE else 'online',
                      health='Filesystem accessible; SMART not measured')
    except OSError as exc:
        if exc.errno in {errno.EIO, errno.ENODEV}:
            result.update(status='failed', health='Filesystem I/O failure')
    except ValueError:
        pass
    drive, _ = StorageDrive.objects.update_or_create(uuid=entry['uuid'], defaults=result)
    return drive


def refresh_drives():
    entries = configuration()
    drives = [probe(entry) for entry in entries]
    StorageDrive.objects.exclude(uuid__in=[e['uuid'] for e in entries]).update(status='offline', health='Not configured')
    return drives


def entry_for(drive):
    for entry in configuration():
        if entry['uuid'] == drive.uuid:
            return entry
    raise OSError("Drive not configured")


@contextmanager
def drive_root(drive):
    entry = entry_for(drive)
    dev, physical = identity(entry)
    fd = os.open(entry['path'], os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        if os.fstat(fd).st_dev != dev or physical != drive.physical_id:
            raise OSError("Drive changed during operation")
        # Pin the opened mount. A concurrent unmount cannot redirect writes into
        # the now-empty mountpoint on the host's system drive.
        yield Path(f'/proc/self/fd/{fd}')
    finally:
        os.close(fd)


def asset_path(root, key):
    if not key or Path(key).is_absolute() or any(p in {'.', '..'} for p in key.split('/')):
        raise ValueError("Invalid asset key")
    path = root / 'album-archive' / key
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("Asset path escapes drive")
    return path
