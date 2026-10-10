# Frontend refresh and backend review

The interface now uses a light-purple palette, a compact account header, photos grouped by calendar day, and a simpler photo editor. The promotional slogans, dashboard counts for unused features, and decorative placeholder artwork have been removed. Uploads, original downloads, captions, dates, and the administrator link remain available. Account management is still Django admin, under Settings.

The frontend also cancels superseded requests, clears private UI on logout/session expiry, groups dates consistently across pages, includes a refresh control, and handles failed thumbnails/previews. The source is split into readable components and shared request/types/date helpers. No third-party font, image service, analytics, or new frontend runtime dependency was added. Small text colors were checked for a minimum 4.5:1 contrast against their intended surfaces; native dialogs, focus indicators, large controls and reduced-motion styles are retained.

## Backend changes

- **Shared upload admission:** PostgreSQL now takes a transaction-level advisory lock before checking shared queue capacity and UUID ownership. The previous per-user lock could allow two members to race on queue capacity or a conflicting upload UUID. Streaming remains outside this short transaction; file/record durability and unchanged originals are preserved. SQLite remains a local single-process convenience.
- **Concurrent metadata edits:** read/update of a ready photo uses a row lock in one transaction. Normal last-write behavior remains; there is no new version history or guest permission system.
- **Processing diagnostics:** fixed safe error codes distinguish unsupported/animated formats, pixel limits, corrupt images, missing originals, storage problems and interrupted decoders. The supervisor logs only job IDs, codes and attempt counts. The UI does not receive private paths, exception traces or metadata. Legacy generic job codes remain understood.
- **Decoder limits:** the processing command skips URL system checks so native image libraries load after the child applies its CPU/memory limits, rather than importing through API URLs in the supervisor.
- **Metadata edge cases:** extreme EXIF offsets cannot crash conversion at the datetime boundary; invalid negative GPS degrees are rejected.
- **API/session handling:** CSRF failures return safe JSON for API requests; admin keeps Django's normal CSRF failure page. Configuration lists tolerate surrounding whitespace. Deactivated accounts still lose access on their next request.

Reviewed the existing member checks, CSRF/Origin protection, Argon2 hashing, login lockout, session rotation, secure production cookies, private/no-store media delivery, storage-path validation, decoded/streamed image limits, worker isolation, original preservation, pagination/indexes, admin deletion restrictions, and Compose persistence. The app continues to share one library between two trusted accounts; no guest role or extra account-access layer was introduced.

## Validation and limits

The TypeScript/Vite build and Docker rebuild passed. All 49 backend tests passed on PostgreSQL, including real simultaneous admission requests from two accounts. The SQLite run passes with the two PostgreSQL concurrency checks skipped. Existing MPO/HEIC, EXIF, orientation, original checksums, corrupt/animated/large images, failure recovery, session and private-media tests remain covered. The HTTP integration check exercised JPEG/HEIC upload, the actual decoder subprocess, original checksums, preview metadata stripping, caption/date editing, and logout authorization. No migration drift was found.

Production Django checks retain the two existing intentional warnings for HSTS includeSubDomains and preload. The site has host-only HSTS and HTTPS settings; broader HSTS should depend on ownership/use of the actual hostname. This review is not a production penetration test. Actual phone/desktop browser rendering was not automated because no browser-control tool was available. Automatic backups and Trash remain outstanding milestones; the review did not implement them.

## Update the Ubuntu server

```bash
cd ~/GFPicturebook
git pull --ff-only origin main
docker compose build web
docker compose up -d --no-build
docker compose exec web python manage.py test memories --verbosity 2
```

Keep `.env` and `data/`. No new secrets, network changes, accounts, or schema migration are needed. Refresh the existing HTTPS address in your phone browser.

Check the day headings, multiple uploads, portrait/HEIC/MPO previews, caption/date saving, original download, and sign-out/sign-in. Use Settings for admin. When a file fails processing, expand the upload list to see the reason and inspect `docker compose logs --tail=80 worker` for its fixed job code.
