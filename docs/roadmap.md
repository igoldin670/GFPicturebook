# Incremental development roadmap

Every increment should include source changes, updated commands, automated regression coverage for its risks, and a manual phone/desktop acceptance checklist. Complete each gate before depending on it. The first increment is built; remaining items below are specifications, not implemented features.

| Step | Build and files | How to verify before continuing |
|---|---|---|
| 1 — Foundation (implemented) | `backend/config`, `memories/models.py`, `views.py`, migrations, tests; React login/welcome; Docker/Caddy; documentation | Run README commands. Tests reject anonymous access, missing/cross-origin CSRF, inactive users and brute force; verify two-account login, logout and admin separation. Build frontend and run against PostgreSQL. |
| 2 — Durable ingestion | `memories/services/ingest.py`, `metadata.py`, `management/commands/process_photos.py`; upload API/UI and worker service; Pillow/HEIC dependencies | Upload JPEG/PNG/WebP/HEIC from phone and desktop, single/multiple/drop. Verify exact original checksum, all orientations, GPS and EXIF-offset cases, absent/malformed metadata, date fallback, oversize/fake files and pixel bombs. Kill/restart worker and retry without duplicate photos; test full-disk failure. |
| 3 — Recovery before real imports | Backup service/scripts, scheduled DB dump + Restic, verification/status API; `docs/backups.md` operational commands | Back up test photos and metadata; restore on a blank isolated host; compare checksums, users, albums and derivatives. Fail a backup and show stale/failed status. Prove interrupted backup never reports success. No irreplaceable imports before this gate. |
| 4 — Everyday library | Private media routes, cursor queries, React thumbnail gallery/detail dialog, metadata editing | Browse 10,000 synthetic records with EXPLAIN and a bounded response size. Scroll on phone, change dates across month/year boundaries, edit captions, reject invalid fields and verify trashed/private image access rules. |
| 5 — Shared chapters | Album CRUD/memberships/cover selection; favorites; filters and indexed text search | Same photo in two albums without extra file; remove one membership without affecting another; each account has independent favorites. Search caption/location and combine date/album/favorite filters. |
| 6 — Picture book and timeline | Paginated date grouping, book layout, swipe/keyboard/fullscreen, loading/error states | Navigate single/multiple-photo pages on iOS/Android/desktop; reduced motion, screen-reader labels, touch scroll and image preloading. Clicking a timeline day selects the right calendar date. |
| 7 — Safe administration | Storage usage/recent uploads, audited metadata edits, Trash/restore, explicit protected purge and account controls | Trash removes from all normal views but preserves originals; restore returns memberships; permanent deletion is admin-only, confirmed and requires a recent verified independent backup. Default: no automatic purge. |
| 8 — Operational hardening and PWA | Manifest/icons, shell-only service worker, dependency update workflow, monitoring, disk alerts, backup alerts, deployment checks | HTTPS/cookie checks, restart/recovery drills, offsite restore, disk exhaustion alerts, installation on mobile, no private data in service-worker caches, clear state after logout. Review before normal daily use. |
| 9 — Optional additions | Video, comments, on-this-day, maps, opt-in local tagging, imports, exports | Add one at a time with separate migrations and processing jobs; retain unchanged original bytes and existing backup compatibility. |

## Current API contract

- `GET /api/session/` returns user identity (or null) and a CSRF token.
- `POST /api/login/` expects JSON `{username, password}` and `X-CSRFToken`; rotates session and CSRF token.
- `POST /api/logout/` requires CSRF and invalidates the session.
- `GET /api/summary/` requires a member session and returns actual photo, album and personal-favorite counts.
- `GET /health/` is liveness only, with no private data. It is not a database/backup health assertion.
- `/admin/` requires staff; no public signup or password-reset email service exists.

Future endpoints should remain same-origin and session-authenticated. Add a common API authorization decorator/service before introducing gallery and media endpoints. Keep error responses bounded and avoid leaking original paths or raw EXIF into logs. The current database tables reserve future features, but their write endpoints deliberately do not exist yet.
