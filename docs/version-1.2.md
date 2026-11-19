# Version 1.2: the handbound photo journal

The member frontend now feels like an ink-blue clothbound album: locally hosted Bodoni Moda lettering, warm paper, a compact title and upload surface, tactile photo/video Polaroids, and a matching physical Dates book. Sign-in is a journal cover opening onto the login form. Missing dates, selection, bulk edits, upload progress/retries, media filters and lightboxes share the new controls. Administration keeps its layout and authorization with matching typography and light/dark colours.

The old placeholder album/favourite counters and repeated dates above individual Polaroids are removed. Date-only Polaroid captions and stored descriptions remain. The orbit emblem, main title wording, short sign-in cascade, populated-month navigation and reduced-motion support remain.

## Compatibility

No new schema migration or API change. No original media, metadata or replicas are rewritten. No storage configuration, drive operation, hostname or server deployment is included. The existing feature branch remains the release target; main is unchanged.

Vite now serves its own `/static/` assets in development and preview instead of forwarding them to Django. API and admin requests still proxy to Django in development. Docker production static serving is unchanged.

The PostgreSQL concurrency test closes its thread-local connections explicitly so a successful suite can cleanly remove its temporary database. Application database behaviour is unchanged.

## Update your server

From the existing installation, retain `.env`, drive configuration and mounted storage. Take your usual database backup first. Then:

```bash
cd ~/GFPicturebook
git switch feature/redundant-media-archive
git pull --ff-only origin feature/redundant-media-archive
docker compose -f compose.yaml -f compose.archive.yaml up -d --build
docker compose -f compose.yaml -f compose.archive.yaml ps
```

Use only `compose.yaml` if archive mode was never configured. Do not rerun initialization. If upgrading from before the Missing dates release, follow [its required database-backup and migration procedure](living-scrapbook.md#upgrade-and-rollback) first. This version adds no further migration.

Refresh the browser after the update. Existing Tailscale addresses, users, originals and archive configuration stay in place. Roll back a v1.2-only update by rebuilding the prior v1.1 application commit; do not downgrade across the earlier nullable-date migration without its documented database restore.

## Repeatable browser checks

```bash
cd frontend
npm ci
npx playwright install chromium
npm run test:e2e
```

A system Chromium can be selected with `PLAYWRIGHT_EXECUTABLE_PATH=/usr/bin/chromium`. The suite starts a production Vite preview and uses synthetic API/media fixtures for viewport and failure-state coverage. `JOURNAL_SCREENSHOTS=/absolute/output/path npm run test:e2e` additionally captures desktop/phone review images. Generated reports, traces and screenshots remain untracked. Fonts are local even in previews.

The optional `tests/live.spec.ts` runs against an explicitly provided **fresh isolated backend and database**, a running media worker, and synthetic JPEG/PNG/MP4 files. Never point it at your personal archive. It needs `ALBUM_BASE_URL`, `ALBUM_LIVE_FIXTURES` (containing `camera-original.jpg` with an October 2021 embedded capture date, `undated.png` without metadata, and a playable three-second `camera-video.mp4` with an October 2021 creation date), `ALBUM_LIVE_MEMBER`, `ALBUM_LIVE_ADMIN`, and `ALBUM_LIVE_PASSWORD`. It uploads three files, assigns a missing date, checks unchanged downloads, plays/seeks video, and verifies member/admin permissions. Set these through your local test runner, never commit or paste real passwords. Without this configuration it is skipped.

The expected live fixture accounts are a member and superuser with the same synthetic test-only password. The backend must start with no media. Run only the live test against it: `npm run test:e2e -- tests/live.spec.ts`.

## Validation

See the final release verification record below for the checks actually completed. Browser mocks verify UI behaviour; real backend checks verify authenticated integration. Neither demonstrates real physical-drive failures or every mobile browser's hardware video codec support.

### Completed release checks

- **108 PostgreSQL backend tests passed**, including media formats, metadata/manual dates, filtering, bulk edits, storage integrity/replication and admin authorization. Database teardown now completes successfully. Migration dry-run reports no changes.
- **16 browser checks passed** in the final preview run: 15 interaction/layout tests plus screenshot capture. The live-backend test is intentionally skipped in that run and passed separately against the isolated Docker deployment.
- The live workflow uploaded an EXIF-dated JPEG, undated PNG and three-second MP4; processed them through the real worker; verified original download SHA-256 equality; played and sought the video; checked a byte-range response; assigned a missing date; and checked anonymous/member/admin storage authorization.
- Screenshots reviewed at 320, 390, 768, 1440 and 1920px include gallery and Dates; additional captures cover sign-in, Missing dates, lightboxes and admin light/dark themes. Complete cards fit within the first 900px-high desktop viewport. No horizontal overflow was found at those widths.
- The non-reduced-motion book test passed under 4x CPU throttling. Reduced-motion login/book states and cascade cleanup passed separately. This is a functional animation check, not a measured frame-rate benchmark.
- Normal/muted text, copper chapter ink and cloth labels were checked against their surface colours; measured contrast ratios range from 4.93:1 to 11.52:1 for those pairs.
- Independent finishing review: **ship**, with no material fixes requested within the supplied screenshot and sampled-source scope. This is separate from the automated runtime checks.
- TypeScript/Vite production build and the production Docker build passed. Docker used the existing pinned uv dependency installation and session CA build secret.
- Impeccable's written design/review guidance was applied. Its engine could not create the cache directory in the sandbox, so its context/detector commands did not run; no automated Impeccable detector pass is claimed.

Checks used temporary databases, containers, accounts and synthetic media. No personal server deployment or physical drive operation was performed. Real iPhone/Safari acceptance and actual drive-disconnection tests remain outside this frontend release's verification.
