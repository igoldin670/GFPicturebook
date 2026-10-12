#!/usr/bin/env python3
"""Explicit, one-time host setup for the three approved empty Storage Spaces partitions.

Default is read-only inspection. Never invoked by the app, Docker or its workers.
Only --apply plus the exact interactive confirmation permits filesystem creation.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT_UUID = '62fba36b-4bd5-46be-8e8e-b20149db4e02'
PARTITIONS = (
    '8a8b6407-2c9b-11f1-b0cd-0cc47ac53747',
    '8a8b6404-2c9b-11f1-b0cd-0cc47ac53747',
    '8a8b6406-2c9b-11f1-b0cd-0cc47ac53747',
)
REPO = Path(__file__).resolve().parent.parent


def run(*args):
    return subprocess.check_output(args, text=True).strip()


def inventory():
    raw = json.loads(run('lsblk', '--json', '--bytes', '--paths', '--output',
                         'NAME,TYPE,SIZE,FSTYPE,UUID,PARTUUID,MOUNTPOINTS,PKNAME,RO'))
    rows = []
    def walk(items, disk=None):
        for item in items:
            if item['type'] == 'disk':
                disk = item['name']
            row = {k: v for k, v in item.items() if k != 'children'}
            row['physical_disk'] = disk
            rows.append(row)
            walk(item.get('children', []), disk)
    walk(raw['blockdevices'])
    return rows


def inspect(rows):
    if run('findmnt', '--noheadings', '--output', 'UUID', '/') != ROOT_UUID:
        raise RuntimeError('OS filesystem UUID differs from the supplied server inventory; refusing setup.')
    roots = [r for r in rows if r.get('uuid') == ROOT_UUID and '/' in (r.get('mountpoints') or [])]
    if len(roots) != 1 or not roots[0]['physical_disk']:
        raise RuntimeError('Cannot establish the physical OS disk safely.')
    root_disk = roots[0]['physical_disk']
    selected, disks = [], set()
    for identifier in PARTITIONS:
        matches = [r for r in rows if r.get('partuuid') == identifier]
        if len(matches) != 1:
            raise RuntimeError(f'Expected exactly one partition with PARTUUID {identifier}.')
        row = matches[0]
        disk = row['physical_disk']
        if row['type'] != 'part' or not disk or disk == root_disk or disk in disks:
            raise RuntimeError('Targets must be partitions on three distinct physical disks, excluding the OS disk.')
        if not 1_500_000_000_000 <= int(row['size']) <= 2_200_000_000_000:
            raise RuntimeError(f'Target {identifier} is not the expected approximately 2 TB partition.')
        if row.get('ro'):
            raise RuntimeError(f'Target {identifier} is read-only.')
        for sibling in rows:
            if sibling['physical_disk'] != disk:
                continue
            if any(sibling.get('mountpoints') or []):
                raise RuntimeError(f'A filesystem or swap on {disk} is in use; refusing to format any partition on it.')
            holders = Path('/sys/class/block') / Path(sibling['name']).name / 'holders'
            if not holders.is_dir() or any(holders.iterdir()):
                raise RuntimeError(f'Device {sibling["name"]} has active/unverifiable block-device holders.')
        stable = Path('/dev/disk/by-partuuid') / identifier
        if not stable.exists() or stable.resolve() != Path(row['name']).resolve():
            raise RuntimeError(f'Persistent partition identity does not match {identifier}.')
        # Fail closed on already-initialized filesystems; this is not a rerunnable
        # formatter and must never erase a later healthy archive filesystem.
        if row.get('fstype') not in {None, '', 'isw_raid_member', 'windows_storage_spaces'}:
            raise RuntimeError(f'{identifier} already has filesystem/type {row["fstype"]}; do not reformat it.')
        disks.add(disk)
        selected.append(row)
    return selected


def preflight():
    for executable in ['lsblk', 'findmnt', 'mkfs.ext4', 'blkid', 'mount', 'udevadm']:
        if not shutil.which(executable):
            raise RuntimeError(f'Required host tool is missing: {executable}.')
    for path in [REPO / 'config/drives.json', REPO / 'compose.archive.yaml']:
        if path.exists() or path.is_symlink():
            raise RuntimeError(f'{path} already exists; preserve it and configure mounted drives manually.')
    fstab = Path('/etc/fstab').read_text()
    for n in range(1, 4):
        mount = Path(f'/mnt/album-drive-{n}')
        if str(mount) in fstab:
            raise RuntimeError(f'{mount} is already mentioned in fstab; inspect that configuration first.')
        if mount.is_symlink() or mount.exists() and (not mount.is_dir() or any(mount.iterdir())):
            raise RuntimeError(f'{mount} must be absent or an empty, unmounted directory.')
    return fstab


def write_new(path, text, mode=0o640, app_readable=False):
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode), 'w') as output:
        output.write(text)
        os.fchmod(output.fileno(), mode)  # Ensure group read even under a restrictive sudo umask.
        output.flush()
        os.fsync(output.fileno())
    owner = REPO.stat()
    # The container runs as group 10001. Preserve the host owner while granting
    # that group read access; do not make storage configuration world-readable.
    os.chown(path, owner.st_uid, 10001 if app_readable else owner.st_gid)


def apply(selected, fstab):
    if os.geteuid() != 0:
        raise RuntimeError('--apply requires sudo; the inspection-only mode does not change anything.')
    confirmation = input('Type FORMAT THREE ARCHIVE PARTITIONS to proceed: ')
    if confirmation != 'FORMAT THREE ARCHIVE PARTITIONS':
        raise RuntimeError('Confirmation did not match; nothing was changed.')
    # Save read-only inventory and existing fstab BEFORE any formatting.
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup = Path('/var/backups') / f'album-drive-setup-{stamp}'
    backup.mkdir(mode=0o700, parents=False, exist_ok=False)
    (backup / 'inventory.json').write_text(json.dumps(inventory(), indent=2) + '\n')
    shutil.copy2('/etc/fstab', backup / 'fstab')
    manifests, records = [], []
    for n, identifier in enumerate(PARTITIONS, 1):
        # Reinspect identities, mounts, holders and OS protection before EACH
        # destructive operation. Previously formatted targets are allowed only
        # for this process's next checks, without ever selecting them again.
        current = inventory()
        for finished in records:
            for row in current:
                if row.get('partuuid') == finished['partuuid']:
                    if row.get('uuid') != finished['uuid'] or row.get('fstype') != 'ext4':
                        raise RuntimeError('A just-created filesystem changed unexpectedly; stop and inspect.')
                    row['fstype'] = None
            # Keep ALL mount/holder checks active, including on finished disks.
        inspect(current)
        device = f'/dev/disk/by-partuuid/{identifier}'
        print(f'Creating ext4 only on approved large partition {identifier}…', flush=True)
        subprocess.run(['mkfs.ext4', '-L', f'album-archive-{n}', '-m', '1', device], check=True)
        subprocess.run(['udevadm', 'settle'], check=True)
        filesystem_uuid = run('blkid', '-p', '-s', 'UUID', '-o', 'value', device)
        if not filesystem_uuid or run('blkid', '-p', '-s', 'TYPE', '-o', 'value', device) != 'ext4':
            raise RuntimeError('New filesystem identity verification failed. Stop and inspect; do not rerun --apply.')
        records.append({'partuuid': identifier, 'uuid': filesystem_uuid, 'mount': f'/mnt/album-drive-{n}'})
        (backup / 'new-filesystems.json').write_text(json.dumps(records, indent=2) + '\n')
    # Format all three before mounting, so subsequent checks never have to ignore
    # active filesystems. All mounts below select persistent filesystem UUIDs.
    for n, record in enumerate(records, 1):
        mount = Path(record['mount'])
        mount.mkdir(mode=0o755, exist_ok=True)
        subprocess.run(['mount', '-t', 'ext4', '-o', 'nodev,nosuid', f'UUID={record["uuid"]}', str(mount)], check=True)
        if run('findmnt', '--noheadings', '--output', 'UUID', '--mountpoint', str(mount)) != record['uuid']:
            raise RuntimeError('Mounted UUID did not match; refusing application-directory creation.')
        archive = mount / 'album-archive'
        archive.mkdir(mode=0o750, exist_ok=False)
        os.chown(archive, 10001, 10001)  # Only this newly created application directory.
        manifests.append({'uuid': record['uuid'], 'label': f'Archive {n}', 'path': ['/drives/one','/drives/two','/drives/three'][n-1]})
    monitor = Path('/var/lib/album-os-monitor')
    if monitor.is_symlink():
        raise RuntimeError('OS monitoring directory must not be a symlink.')
    monitor.mkdir(mode=0o755, exist_ok=True)
    if monitor.stat().st_dev != Path('/').stat().st_dev:
        raise RuntimeError('OS monitoring directory must be on the OS filesystem.')
    manifests.append({'uuid': ROOT_UUID, 'label': 'Linux system disk (monitor only)', 'path': '/drives/os', 'excluded': True})
    # Preserve the original file and append only the three verified UUID mounts.
    if Path('/etc/fstab').read_text() != fstab:
        raise RuntimeError('fstab changed during setup. Its backup and new-filesystems.json are available; finish manually.')
    additions = '\n# Our little album: three approved archive filesystems; OS disk excluded\n'
    additions += ''.join(f'UUID={r["uuid"]} {r["mount"]} ext4 defaults,nodev,nosuid,nofail,x-systemd.device-timeout=10s 0 2\n' for r in records)
    fd, name = tempfile.mkstemp(prefix='.album-fstab-', dir='/etc')
    try:
        with os.fdopen(fd, 'w') as output:
            output.write(fstab.rstrip('\n') + '\n' + additions)
            output.flush()
            os.fsync(output.fileno())
        original_stat = Path('/etc/fstab').stat()
        os.chmod(name, original_stat.st_mode & 0o777)
        os.chown(name, original_stat.st_uid, original_stat.st_gid)
        os.replace(name, '/etc/fstab')
        directory = os.open('/etc', os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        Path(name).unlink(missing_ok=True)
    write_new(REPO / 'config/drives.json', json.dumps(manifests, indent=2) + '\n', app_readable=True)
    write_new(REPO / 'compose.archive.yaml', (REPO / 'compose.archive.example.yaml').read_text())
    print(f'Setup complete. Recovery inventory and original fstab: {backup}')
    print('Existing .env and data/ were untouched. No partition tables or OS-disk filesystems were changed.')
    print('Start: docker compose -f compose.yaml -f compose.archive.yaml up --build -d')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='Format ONLY the three approved large partitions and configure mounts; requires exact typed confirmation.')
    options = parser.parse_args()
    try:
        fstab = preflight()
        selected = inspect(inventory())
        print('OS filesystem protected:', ROOT_UUID)
        print('Selected targets (large partitions only; partition tables and 128 MB partitions are preserved):')
        for row in selected:
            print(f'  PARTUUID={row["partuuid"]} size={int(row["size"])/10**12:.2f} TB current_type={row.get("fstype") or "unknown"} physical_disk={row["physical_disk"]}')
        if not options.apply:
            print('Inspection only: NOTHING changed. Review these three targets before using --apply.')
            return 0
        apply(selected, fstab)
        return 0
    except (RuntimeError, OSError, subprocess.CalledProcessError) as exc:
        print(f'STOP: {exc}', file=sys.stderr)
        print('If formatting had already started, preserve the recovery records and finish manually; do not blindly rerun.', file=sys.stderr)
        return 1

if __name__ == '__main__':
    raise SystemExit(main())
