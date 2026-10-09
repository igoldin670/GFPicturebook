# Backup and restore design

This is the design for increment 3. **No automatic backups are running in increment 2 either.** BackupRun is only the status schema. Do not treat an empty status table, a local copy, or a successful database dump as a verified full backup.

## 3–2–1 plan

Maintain three recoverable copies: the live server, an encrypted backup on a physically separate local disk/NAS, and an encrypted offsite repository on another provider/location. Use at least two independent storage systems/media and one offsite copy. A different directory, Docker volume, RAID mirror, or second partition on the same disk is not an independent backup. Keep an offline or provider-immutable copy where practical to resist ransomware and accidental deletion.

Restic is a suitable backend: encrypted, content-addressed, incremental, widely supported, with integrity checking and simple restore. Use separate repositories/credentials for local and offsite destinations. Protect the repository password/recovery key outside the server (password manager plus offline emergency copy); losing it loses the backup. Prefer append-only/offsite permissions and separate credentials for pruning if the destination supports them.

## What and when

Back up originals, a consistent PostgreSQL logical dump, a manifest of original paths/checksums and schema/app version, configuration needed for recovery, and optionally previews/thumbnails. Derivatives are reproducible, but retaining them speeds recovery. Exclude scratch uploads, database live files from ordinary file backups, caches, and transient exports. Save `.env` encrypted with tightly controlled recovery access; keep source/dependency locks and a known image version too.

Target an initial recovery point objective of 24 hours and recovery time measured by a real restore drill (likely hours, depending on library size and offsite bandwidth). Run nightly and after important imports. Initial retention: 7 daily, 5 weekly, 12 monthly snapshots, adjusted for storage and personal requirements. Retention must run only after a verified new snapshot; fail closed and alert when backup freshness exceeds 26 hours. Do not claim a backup is healthy from its last start time.

The backup service should:

1. Acquire a database advisory backup lock shared with import finalization and permanent purge, or briefly put writes into maintenance mode and pause worker finalization. For a two-person app a short maintenance interval is acceptable and simpler to audit.
2. Produce `pg_dump --format=custom --no-owner` into a temporary backup staging location using credentials via environment/secret files. Verify process success; atomically finalize the dump. Never copy a running PostgreSQL data directory as an ordinary file backup.
3. Snapshot the dump and originals together. Immutable originals plus blocked purge ensure a database reference cannot point to a file deleted mid-backup. If relaxing the write lock later, document and test the ordering/consistency proof; orphaned newer files are acceptable, missing referenced files are not.
4. Run Restic for the local and offsite repositories. Record the snapshot ID and successful completion only after repository confirmation. Propagate failures and release locks safely; do not overwrite the last successful status with a fabricated success.
5. Check repository integrity on a schedule; read a rotating data subset weekly and perform a full check periodically. Restore sample originals and compare SHA-256 against the manifest. Only then advance verified_at for the relevant verification scope. Model per-destination backup status when the service is added.
6. Send an operator alert on failure/staleness/low disk space. A dashboard unseen for a month is not alerting. Notification destination is an operator configuration choice, not implemented here.

## Straightforward restore procedure

Implement this as a tested script/runbook in increment 3; commands below illustrate the required sequence, not an existing automated recovery service.

1. Pick a completed, verified snapshot, preserve the damaged system unchanged, and use a clean isolated host or fresh empty recovery directories. Do not overwrite the live library during a drill.
2. Install Docker and recover the matching source/app version, encrypted config and repository credentials. Restore with `restic restore SNAPSHOT_ID --target /srv/album-recovery` using `RESTIC_REPOSITORY` and a protected `RESTIC_PASSWORD_FILE` configured for the selected repository. Do not put passwords on command lines.
3. Verify the manifest and original SHA-256 values. Mount restored photos with correct UID ownership; recover the database into a freshly initialized PostgreSQL instance of a compatible version.
4. Before starting the application, restore the custom dump into the empty database. For the current service names: `docker compose up -d db`, then `docker compose exec -T db sh -c 'pg_restore --exit-on-error --no-owner -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < /srv/album-recovery/database.dump`. Use a fresh database with no migrated application tables, and stop on any failure.
5. Start the version matching the backup, apply only required forward migrations, and rotate sessions/credentials if recovering from compromise. Reconcile original paths, photo counts, album memberships, date/caption values, favorites and backup status. Regenerate missing derivatives with the future worker.
6. Sign in as both users, sample old/new photos and original downloads, verify checksums again, and check Trash. Keep the recovery site isolated until the checks pass. Point Tailscale/DNS to it only after operator review.
7. Resume backup schedules, record duration/data recovered, and retain the prior server/snapshot until recovery is confirmed. Practice this quarterly and after major storage/schema changes.

## Protection from accidental deletion

Trash is a database marker; originals remain intact and are excluded from normal browsing. Planned retention is at least 30 days, with no automatic permanent purge by default. Restore should preserve memberships and favorites. An eventual permanent purge must be admin-only, explicitly confirmed, audit logged, coordinated with backups, and require an independent verified snapshot. Backup retention can preserve deleted photos longer; document this clearly. A backup on the same server cannot prove that the only copy is safe.
