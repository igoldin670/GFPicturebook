# Living scrapbook: missing dates, filters, and flowing memories

This update builds on v1.1 and keeps originals, captions, embedded capture facts, verified replicas, authentication, and admin storage permissions intact. Python installation continues to use uv with the existing dependency lock.

## Organizing memories

**All / Photos / Videos** filters the full query before pagination in Memories, Missing dates, and Dates. The choice follows section navigation, defaults to All after interactive sign-in, and resets on refresh. Dates filters its book previews, chapter counts, years, and populated months together. It retains the current month where possible; otherwise it chooses the nearest matching month, earlier on a tie. Missing dates always shows the total across both types in the sidebar and the matching count beside its heading.

**Missing dates**, beneath Memories, contains ready photos and videos without reliable capture metadata. Upload time remains available internally, but is never displayed as the capture date. Undated memories do not appear in chronological Memories or monthly chapters. Their polaroids say “Date needed”; originals and derivatives remain stored even when users leave without assigning dates.

Use Select, Select loaded, and Change date to assign one date to up to 500 loaded memories at once. Selection survives cursor pagination, but clears on section/month/filter changes. Failed submissions preserve the date and selection. Successful assignments move records into their correct chapters and refresh counters. Caption-only edits are supported without choosing a date. Explicit assignments become manual and survive reprocessing.

The existing `reread_capture_dates UUID [UUID...]` command now supports missing-date records as well as legacy upload-fallback records. It remains dry-run by default; only `--apply` saves recovered reliable metadata for explicitly targeted IDs. Manual overrides are rechecked under lock. No historical metadata re-read is automatic. See [v1.1 metadata recovery](version-1.1.md) for parser coverage and the unconfirmed Android-specific diagnosis.

## Book and sign-in

The book uses more desktop space, with previous/next controls outside its transformed pages. Narrow screens put navigation below the book. Decorative covers, tape, binding, shadows, and animated duplicate pages cannot intercept clicks. Settled polaroids respond across their image, frame, and date caption, with selection, hover, focus, and touch feedback preserved.

Successful interactive login triggers three staggered waves of local decorative polaroids and scrapbook sheets: 48 on desktop and 28 on narrow screens. Each item has varied timing, drift, rotation, size, and flutter. The non-interactive, assistive-technology-hidden overlay disappears within four seconds; it never uses private gallery pictures. Reduced motion skips it, refresh/navigation does not replay it, and logout cleans it up.

## API changes

All media queries still require an authenticated member; mutation requests require CSRF.

- Media `date` is now `YYYY-MM-DD` or `null`; `dateSource` adds `missing`.
- `GET /api/photos/` returns dated memories; `?undated=1` selects the missing-date inbox. Undated and month filters cannot be combined.
- Gallery and chapter-index endpoints accept optional `kind=photo` or `kind=video`; omit for All. Unsupported values return 400.
- Gallery responses include `photos`, `next`, and a matching total `count` before cursor pagination. Undated records sort by descending upload timestamp and UUID. Signed cursors are isolated by media kind, month, and dated/undated mode. Old cursors expire after upgrade; refresh the gallery.
- `GET /api/summary/` includes total `undatedCount`. Its existing total still includes undated ready, non-trashed memories.
- Bulk-date payload/response and atomic authorization policy are unchanged. Single-edit requests accept `date: null` only when the record is already undated. Clearing assigned dates is not supported.

## Upgrade and rollback

**Back up PostgreSQL before upgrading.** Migration `0004` makes calendar dates nullable and clears dates whose source is the automatic `upload` fallback, including pending/failed/trashed records. Existing manual, EXIF, and trusted-file dates are preserved. Upload timestamps, captions, originals, and replica manifests are unchanged. No disks are formatted, mounted, or otherwise modified by this update.

Stop app services before migrating so old workers cannot write new upload-fallback dates during the change. For an archive deployment, from the project directory:

```sh
set -eu
git switch feature/redundant-media-archive
git pull --ff-only origin feature/redundant-media-archive
# Record the deployed commit/image and retain a verified database backup.
mkdir -p backups
chmod 700 backups
scrapbook_backup="backups/pre-missing-dates-$(date -u +%Y%m%dT%H%M%SZ).dump"
umask 077
docker compose -f compose.yaml -f compose.archive.yaml stop web worker archive
(set -C; docker compose -f compose.yaml -f compose.archive.yaml exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$scrapbook_backup")
# Confirm pg_dump exited successfully and inspect the dump before proceeding.
docker compose -f compose.yaml -f compose.archive.yaml exec -T db pg_restore --list < "$scrapbook_backup"
docker compose -f compose.yaml -f compose.archive.yaml up -d --build
```

Use the base Compose file alone if archive configuration is not enabled. Preserve `.env`, `config/drives.json`, mounted media, and storage configuration. Do not re-run environment initialization. Compose runs migrations before starting web and workers.

Migration `0004` is intentionally irreversible: the exact old fallback dates are discarded. Downgrading requires stopping the app and restoring the pre-upgrade database with the corresponding old application image, using the existing restore procedure. Do not run the old application against the nullable schema or invent dates to satisfy its constraints. Post-upgrade database edits must be accounted for before any restore.
