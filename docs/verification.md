# Dates memory book — 2026-10-13

- **All 82 backend tests passed on PostgreSQL**, including seven new calendar tests. Coverage includes capture-local dates across UTC month boundaries, upload/manual date sources, videos, hidden/failed/trashed media, leap years, year rollover, four-digit calendar extremes, invalid filters, complete month pagination, scoped signed cursors, manual chapter changes, and session authorization.
- TypeScript/Vite production build, migration drift check, and Git whitespace check passed. No schema migration or dependency was added.
- Chromium tested the production-built frontend with real Caddy/Gunicorn APIs and supervised media processing. Six synthetic photos and a video uploaded successfully while Dates stayed open. Generated media and temporary accounts were removed afterward, with the local archive worker briefly paused for cleanup and then resumed.
- Browser checks passed for the empty library, delayed 3D cover opening, forward/backward page turns, keyboard navigation, chapter counts and filtering, empty-month skipping, direct chapter selection, manual edits creating a new month, video playback/seeking in the existing lightbox, failed-request recovery, back/forward/hash reload, reduced motion, and member/admin separation. No JavaScript page errors were recorded.
- Layouts at 1440, 1024, 768, 390, and 320 px had no horizontal overflow, including phone cover-opening and page-turn frames. Desktop/phone layouts and animation-frame screenshots were inspected; the phone book shows one keepsake to keep the controls clear, with the full collection below.

Scope of verification: Chromium on Linux, including emulated screen sizes and reduced motion. Safari/iOS and physical touch devices were not exercised. Calendar aggregation and pagination are covered, but a large-library performance benchmark was not run.

# Configurable limits and larger upload batches — 2026-10-12

- **All 75 backend tests passed on PostgreSQL**, including a JPEG original over 50 MiB with its separate cap disabled, independently disabled video caps, the shared ceiling, decoder claim expiry/recovery and simultaneous member admission into a bounded queue.
- TypeScript/Vite build passed. The validation image reused the previously verified FFmpeg/dependency layers and loaded the updated backend and built frontend. Caddy adaptation confirmed its configurable 100 GiB upload ceiling and retained 64 KB non-upload ceiling.
- Real Chromium UI upload of a photo over 50 MiB succeeded. Twelve simultaneous authenticated upload requests were accepted and processed by the bounded photo/video supervisor. The UI/backend reported the configured ceiling and 1,000-file batch limit.
- Native video playback, seeking/fullscreen, unchanged original download, caption editing, member/admin storage authorization and phone viewport checks remained successful, with no JavaScript page errors.
- Browser functional assertions completed successfully; synthetic cleanup initially raced with the archive worker's job creation. The local archive worker was paused only for cleanup, all synthetic accounts/media were removed, then it was restarted.
- SQLite storage/queue checks passed (21 checks; three PostgreSQL-only tests skipped). An earlier full SQLite run passed all 72 non-PostgreSQL tests. No schema migration or new dependency was needed.

Limits: the 100 GiB ceiling was validated as configuration, not by uploading an actual 100 GiB file. Twelve concurrent requests are not a sustained many-user throughput benchmark. Encoders remain bounded to protect RAM; large batches take time to finish. Existing decoded-image pixel limits and supported formats remain in effect.

# Approved host drive-setup helper — 2026-10-12

After the owner confirmed no needed data on the three Storage Spaces partitions and approved their preparation, a separate one-time host helper was added. **All 14 safety tests passed** using mocked device metadata; no real formatting, mounting, system-file modification or drive erasure was performed. Tests cover OS exclusion, distinct disks, target/sibling mounts and swap, active holders, existing filesystems, partition sizes, persistent-ID mismatch, missing/duplicate IDs, read-only devices, default inspection-only behavior and rejected destructive confirmation. Real host execution remains the owner's next step; see [the approved setup instructions](media-archive.md#approved-one-time-setup-of-these-three-empty-partitions).

# Redundant media archive — 2026-10-12

- Final source: **all 68 backend tests passed on PostgreSQL**, including simultaneous archive workers and cross-member UUID upload collisions; the test database was removed successfully.
- SQLite: 66 tests passed, with the two PostgreSQL-only row-lock tests explicitly skipped.
- TypeScript/Vite production build and migration drift check passed. Updated FFmpeg-enabled Docker image built, migrations completed, and web, decoder, archive worker, PostgreSQL and Caddy started. Final container source hashes matched the checkout.
- Chromium against the real Caddy/Gunicorn stack uploaded synthetic photo/video files through the UI; the actual supervised worker processed them. Native video decoding, playback, seeking and fullscreen passed. Original video download was byte-identical; caption editing worked.
- Member storage API/dashboard access returned 403; administrator access succeeded. The guest gallery contained no storage details. A 390 px phone viewport had no horizontal overflow. Desktop gallery, video lightbox, phone gallery and admin dashboard screenshots were inspected/generated. No JavaScript page errors were recorded.
- Temporary-storage tests cover verified two-copy placement, same-physical-drive rejection, offline failover/rebuild, corrupted replicas and sources, full drives, write/read-back errors, incomplete uploads, primary/replication publication before a database crash, gradual existing-photo adoption, all requested video containers with real FFmpeg conversion, and byte-range authorization.
- Synthetic browser accounts/media were removed after validation; real media was not accessed or modified.

**Deployment limits:** the supplied server's three archive partitions report “Storage pool” partition labels but no recognized filesystem UUIDs/mounts. Real physical-drive redundancy is not active or validated. No disks were formatted, repartitioned or erased. SMART diagnostics, actual host unplug/remount behavior, very large-video throughput and offsite/database backup restoration were not tested. The OS disk is excluded in the example configuration. See [media archive deployment](media-archive.md).

Earlier verification follows for history.

---

# iPhone MPO compatibility fix

Docker rebuild/startup succeeded and all 41 tests passed on PostgreSQL and SQLite.

Added a generated two-image MPO regression fixture matching the reported container type. It verifies primary-image selection, EXIF date/orientation, metadata-free previews, and byte-for-byte preservation of the complete original. Animated WebP rejection remains covered. The user's private source images were not accessed; confirm the fix on the server by retrying the retained uploads.

# Increment 2 verification

Verified in the supplied Linux workspace on 2026-10-09:

- TypeScript and production Vite build passed; the updated multi-stage Docker image built successfully.
- Upgraded the existing Compose installation without deleting its persistent data. Storage initialization and migrations exited 0; web, worker, database, and proxy started.
- All **40 backend tests passed against PostgreSQL** in the final image. An earlier 38-test version also passed SQLite; PostgreSQL remains the production target.
- Tests cover all original authentication checks, original-byte preservation, JPEG/PNG/WebP/HEIC decoding, all eight EXIF orientations, offset-aware and missing-offset dates, date fallback, GPS extraction/removal from derivatives, malformed/animated/oversized images, streamed byte limits, low disk, CSRF/media authorization, metadata editing, cursor pagination, idempotent retries, database/worker failure recovery, retry command, and non-destructive storage reconciliation.
- HTTP integration through the real Caddy/Gunicorn stack uploaded synthetic JPEG and HEIC files. The actual bounded worker subprocess processed both; EXIF calendar dates matched, downloaded originals matched SHA-256, previews contained no EXIF, caption/date edits succeeded, and preview requests after logout returned 401. Synthetic records/files/accounts were removed afterward.
- Migration drift check passed: no new schema migration is needed for this increment.
- Read-only storage reconciliation after integration testing reported zero missing originals, zero unreferenced originals, and zero staged files.
- Git whitespace checks passed. Generated secrets, data, dependencies and build output remain ignored.

Not verified: visual rendering/interaction in a browser, actual iPhone/Android library selection, every real camera's HEIC variant, a 10,000-photo performance benchmark, production Tailscale/TLS, or backup/restore (not implemented yet). No browser automation tool was available. Keep independent originals while testing.

The development stack remains running in this workspace. No real photos or permanent test user credentials were added. The earlier foundation verification is retained below.

---

# Increment 1 verification

Verified in the supplied Linux workspace on 2026-10-09:

- TypeScript checking and Vite production build passed.
- Multi-stage Docker image built; non-root runtime can read packaged source/assets.
- Compose started PostgreSQL 17, ran migrations successfully, and started Gunicorn/Caddy.
- All 13 backend tests passed on SQLite and PostgreSQL. The final PostgreSQL run includes independent account/peer-IP Axes throttling and reports no system-check issues.
- Migration drift check passed: no changes detected.
- HTTP smoke test through Caddy passed for the compiled page and assets, unauthenticated 401 response, CSRF-protected login with a real browser Origin header, authenticated summary, and logout. Its temporary account was removed.
- Production `check --deploy` has two intentional warnings: HSTS includeSubDomains and preload are unset. HTTPS redirect, secure cookies and one-year host-only HSTS are configured in production. Choose broader HSTS only after confirming hostname ownership/use.
- Git whitespace check passed; generated `.env`, runtime data, dependencies, and build output are ignored.

Not verified: real phone/desktop rendering or accessibility with a browser, actual Tailscale routing, DNS/certificate issuance, public internet deployment, offsite backup/restore, or future photo features. No browser automation tool was available for visual QA. The app was tested over local HTTP development settings; this is not evidence of a production TLS deployment.

The development stack and generated private local configuration remain in the workspace. No permanent user account or default password was created. Follow README to create your administrator and member. Real photos have not been imported, and no automatic backup service exists yet.
