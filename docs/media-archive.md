# Redundant photo and video archive

The existing cream/sage photo polaroids remain. Video polaroids use generated thumbnails, a small play control, film indicator and duration. Their lightbox uses native browser controls for playback, seeking and fullscreen. Original downloads are unchanged. Storage details appear only in Django admin at `/admin/storage/`; `/api/admin/storage/` independently requires an active staff account. Ordinary members and anonymous requests cannot read it.

## Important server-specific drive limitation

The supplied Linux inventory identifies four physical disks. The 1 TB disk contains the OS (filesystem UUID `62fba36b-4bd5-46be-8e8e-b20149db4e02`). The three 2 TB partitions currently report only `PARTLABEL="Storage pool"` and PARTUUIDs, with no recognized filesystem types, filesystem UUIDs or mountpoints. A partition ID is not an existing filesystem UUID. These may be members of an existing pool; do not format or change them to make this application work.

The application cannot currently claim redundancy on those server drives. The owner subsequently confirmed that the three pool disks contain no needed files and authorized preparing those three storage disks, while preserving the Linux OS disk. A separate, manually invoked host helper is provided below. The application and its workers still never format or mount anything. Real host formatting/mounting has not been executed or validated from this cloud task.

The provided manifest excludes the OS disk from archive writes. It can be monitored alongside the three archive disks. If four writable archive disks are required, an additional filesystem or an explicitly authorized OS-disk allocation is needed. Two healthy writable disks suffice for protection; a third permits rebuilding after a failure. No real disks were used for failure/corruption tests.

## Approved one-time setup of these three empty partitions

The helper is specific to the supplied server, identified by its OS filesystem UUID and the three existing large-partition PARTUUIDs. It is **not** a general-purpose formatter. It leaves partition tables, the 128 MB partitions and the OS filesystem intact, while creating ext4 on the three approximately 2 TB partitions. This destroys their old Storage Spaces contents; the owner explicitly approved that change after confirming no needed files.

First check out the feature branch, then inspect only:

```sh
git fetch origin
git switch feature/redundant-media-archive
git pull --ff-only
sudo python3 scripts/setup-archive-drives.py
```

The first script invocation only reads information. Confirm it identifies exactly the three expected large storage partitions and excludes the 1 TB Linux disk. It refuses mounted partitions, swap, mounted siblings, block-device holders, duplicate/incorrect identities, unexpected capacities, existing recognizable filesystems, existing app drive configuration or conflicting mountpoints. Existing `.env` and `data/` are preserved.

After reviewing that output, run the explicitly destructive mode:

```sh
sudo python3 scripts/setup-archive-drives.py --apply
```

Type `FORMAT THREE ARCHIVE PARTITIONS` only when the printed targets are correct. The helper creates ext4 filesystems on those three approved partitions, records their new filesystem UUIDs, mounts `/mnt/album-drive-1`, `-2` and `-3`, and appends UUID-based entries to `/etc/fstab`. It saves the original fstab and recovery inventory under `/var/backups/album-drive-setup-*`. Only each newly created `album-archive` directory is owned by container UID/GID 10001. It generates the ignored `config/drives.json` and `compose.archive.yaml`, with the OS disk monitor-only/excluded.

If an error occurs after formatting starts, **stop and share the error**. Do not blindly rerun the formatter: it deliberately refuses already-created filesystems. Use its `new-filesystems.json` recovery record to finish mounts/configuration without formatting again. No formatting commands are automatically executed by installations, startup or workers.

Start the app and verify:

```sh
docker compose -f compose.yaml -f compose.archive.yaml up --build -d
docker compose -f compose.yaml -f compose.archive.yaml logs --tail=100 archive worker
```

Open the admin storage dashboard. The three archive drives should be online; the OS disk should be excluded. Upload a test photo/video and confirm every asset reaches two verified copies on different drives. Legacy photos migrate gradually while their OS-disk originals remain intact. New originals go onto archive drives. Future general-storage programs can use separate directories outside `album-archive`; preserve the filesystem UUIDs and app directory permissions.

## Safe upgrade

Keep your existing `.env`, accounts, database and `data/`. Make an independent database/metadata backup before applying migrations. The added tables/fields do not delete or rewrite existing photos. Until drive configuration is activated, the original local layout continues working, and videos can be used; storage jobs report incomplete protection rather than pretending replicas exist.

```sh
git pull --ff-only
docker compose up --build -d
docker compose exec web python manage.py test memories --verbosity 2
docker compose exec web python manage.py makemigrations --check --dry-run
```

Log in as administrator, open Settings, then the Media archive storage dashboard. The separate `archive` service handles integrity/replication; the `worker` service handles image/video derivatives. Neither relies on web requests to finish jobs.

## Activate mounted drives

Only after three existing independent filesystems are safely mounted on the Linux host:

1. Copy `config/drives.example.json` to `config/drives.json`. Replace the three placeholder **filesystem UUIDs**. Labels are for administrators. Paths name the container bind targets, not `/dev/sdX`. The fourth entry is the OS filesystem, marked `excluded: true`.
2. Copy `compose.archive.example.yaml` to `compose.archive.yaml`. Set each host `source` to its existing mount directory. The monitoring bind source must be an existing directory on the OS filesystem. If needed, create just that empty monitoring directory; do not mount the whole system disk inside the application.
3. Pre-create `album-archive` on each archive mount and give only that application-owned directory write access for container UID/GID `10001:10001`. Do not recursively change ownership of the disk, other applications' directories, or existing files. The containers have no formatting tools or privileged disk access.
4. Ensure `/dev/disk/by-uuid` and read-only sysfs topology are visible as shown in the override. UUID resolution checks mount device numbers; partition-parent/serial/WWN checks ensure two filesystems on one physical disk cannot count as two drives. LVM, multi-device RAID/pools, network filesystems and unverifiable device topology fail closed. They need a separate topology implementation before use.
5. Keep unrelated general-storage programs outside `album-archive`. Raise `STORAGE_FREE_RESERVE_MIB` (for example `102400` for 100 GiB per drive) in the existing `.env` to reserve headroom for shared storage. This is a minimum free-space reserve, not a quota for the other program.
6. Start using both Compose files consistently:

```sh
docker compose -f compose.yaml -f compose.archive.yaml up --build -d
docker compose -f compose.yaml -f compose.archive.yaml logs --tail=100 archive worker
docker compose -f compose.yaml -f compose.archive.yaml exec web python manage.py maintain_archive --once
```

Docker bind sources must exist (`create_host_path: false`). A missing mount is not an empty storage directory: the UUID/device check refuses it. File operations pin an opened mount descriptor, preventing an unmount from redirecting writes onto the underlying OS directory. After unplugging/reconnecting host-mounted drives, recreate affected containers if their bind mounts retain the old mount. The worker detects unavailable sources and repairs onto another usable drive without requiring the disconnected one to return.

## Durability and recovery

New configured uploads land directly on one eligible archive drive. The upload is streamed through SHA-256, fsynced, published without overwriting an existing original, then read back for verification before its database record is committed. This first copy is **degraded**, never protected. The background archive worker creates the second copy on a different physical drive. It also replicates generated thumbnails, photo previews and compatible video previews, each with its own immutable checksum manifest.

Replication writes a uniquely named temporary file next to its destination, fsyncs it, verifies a read-back SHA-256, atomically publishes it, syncs directories and checks both published copies before marking protection complete. It verifies its source against the recorded checksum, so corrupted bytes cannot replace a healthy copy. Good destination files are adopted without rewriting. Damaged files may be atomically replaced only from a verified source. If every known source is corrupt or unavailable, the worker retains the files and retries; it never invents a new trusted original hash.

An interrupted upload may leave a durable unreferenced original; retry with the same upload identifier safely adopts matching bytes. An interrupted replication may leave a private `.part` or a fully published copy whose DB transaction rolled back. Retries ignore partials and adopt verified final files. Unknown partials/orphans are retained rather than deleted automatically. Database transactions/row locks serialize replication; OS process death releases locks. Native decoder/FFmpeg subprocesses are bounded, and the supervisor kills their process group on crashes/timeouts.

Legacy files remain in their original location while jobs gradually adopt them, checking original bytes against their already recorded SHA-256. Their extra legacy copy is retained. A reconnected drive may also bring back an additional healthy replica: the app maintains **at least two verified copies**, and never deletes a healthy extra copy to enforce exactly two. The database, UUID configuration, `.env` and metadata must still be backed up separately; replicated media is not a versioned/offsite backup or database redundancy.

File serving rehashes opened originals/videos and tries surviving verified replicas first; the same verified descriptor is used to serve data. Small generated-image responses have a bounded RAM cache. All media routes require a session, including HTTP Range requests; there are no public disk URLs.

## Video and memory settings

FFmpeg/ffprobe are installed in the Docker image. MP4, MOV, MKV, WebM, AVI and MP4-container M4V uploads are accepted based on file contents, not a claimed MIME type. Supported originals remain byte-identical. By default the worker generates a metadata-stripped H.264/AAC MP4 preview (maximum 1920×1080, faststart), plus a still WebP thumbnail. Seeking uses authenticated single HTTP byte ranges (206), and invalid/unsatisfiable ranges return 416. Disabling `VIDEO_TRANSCODE` keeps thumbnails and allows native H.264/AAC MP4 playback; unsupported browser formats remain downloadable.

Defaults can be added to your existing `.env` (never regenerate its secrets):

| Setting | Default | Purpose |
| --- | --- | --- |
| `STORAGE_FREE_RESERVE_MIB` | 1024 | Minimum headroom on each drive |
| `STORAGE_CHECK_SECONDS` | 86400 | Full checksum/repair interval per file |
| `MEDIA_CACHE_MIB` | 256 | Strict RAM cache budget per web process |
| `MEDIA_WORKER_MEMORY_MIB` | 8192 | Video decoder/encoder address-space ceiling |
| `VIDEO_MAX_MIB` | 20480 | Video upload ceiling (20 GiB) |
| `VIDEO_TRANSCODE` | 1 | Generate browser-compatible previews |
| `VIDEO_TIMEOUT_SECONDS` | 21600 | Six-hour encoder limit |

The proxy also caps upload requests at 20 GiB. If changing that limit, update `deploy/Caddyfile` consistently. Photo uploads remain capped at 50 MiB and decompression at 50 million pixels. One decoder/encoder runs at a time with two FFmpeg threads; Compose limits the worker to 10 GiB, archive repair to 1 GiB, and the configured web service to 8 GiB. The web service has two processes, so a 256 MiB cache setting means at most 512 MiB of retained response data across them. Copy/hash buffers are 8 MiB; large videos always stream. Photo decoding loads pixels into memory within its bound. Linux uses remaining RAM as its filesystem page cache, which benefits large repeated video reads without unbounded Python allocations. On a 64 GB server this leaves substantial room for PostgreSQL, the OS, page cache and your other program. Do not increase worker counts without adjusting the total memory budget.

Drive observations update about every 10 seconds. Integrity checks are periodic and dated; a status is an observation, not proof against future bit rot. The dashboard records checksum failures and I/O error dates. Hardware SMART diagnostics are explicitly shown as not measured; use read-only host SMART diagnostics for hardware failure prediction. This container only claims filesystem availability and observed integrity, never a clean hardware bill of health.

## Tests and safe manual verification

Automated tests use temporary simulated drives; the simulation flag cannot be enabled by an environment variable in production. Tests cover two distinct verified copies, same-physical-drive rejection, all six containers/real FFmpeg previews, byte-range seeking and downloads, offline failover, rebuilds, corrupt sources/destinations, full drives, I/O failures, failed read-back verification, publication-before-commit recovery, original upload/decoder rollback, guest/admin/CSRF enforcement, and existing-photo adoption. PostgreSQL-only tests exercise simultaneous replication workers and cross-member upload UUID collisions; they are explicitly skipped on SQLite.

For a manual UI check, upload synthetic/test media, open a video polaroid, play and seek it, use fullscreen, edit its caption/date and download the original. Check a phone-sized viewport and keyboard navigation. In admin, confirm two verified physical replicas for each asset. Disconnects/corruption/full-disk scenarios should be run only with temporary simulated storage, not by damaging real media or filling your actual drives.


## Website startup after host setup

A permission correction was added to the setup helper: the generated drive manifest must be readable by container group 10001. If you already ran the older helper, **do not rerun formatting**. Correct only the existing configuration file and restart:

```sh
sudo chgrp 10001 config/drives.json
sudo chmod 640 config/drives.json
docker compose -f compose.yaml -f compose.archive.yaml up -d
docker compose -f compose.yaml -f compose.archive.yaml ps -a
curl -I http://127.0.0.1:8080/
```

The website listens only on the server's loopback interface. In a remote desktop browser running on the server, use `http://localhost:8080`. In your own computer's browser, use the configured Tailscale HTTPS address or an SSH tunnel (`ssh -L 8080:127.0.0.1:8080 basement@SERVER_IP`), then browse `http://localhost:8080`. A refusal/blank page must be diagnosed using container status and logs before changing network exposure. Do not regenerate `.env`, delete `data/`, or format any drives as a website-startup fix.
