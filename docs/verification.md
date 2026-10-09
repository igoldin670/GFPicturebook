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
