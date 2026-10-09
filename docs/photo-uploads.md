# Increment 2: upload and keep your first photos

This increment preserves the received original bytes and generates metadata, a thumbnail (up to 400 px), and a preview (up to 2048 px). Supported still formats: JPEG, PNG, WebP and HEIC/HEIF. Animated/multi-frame images, videos and Live Photo video components are not supported. Browser/iOS export may convert a selected image before upload; the server preserves the exact bytes it receives, not an unavailable on-device version.

## Upgrade your existing Ubuntu server

From the account you used before:

```bash
cd ~/GFPicturebook
git pull --ff-only origin main
# Build before the brief restart, so a failed build does not stop the old app.
docker compose build web
# Recreate the network: processing/database now use an internal-only network.
docker compose down
docker compose up -d --no-build
docker compose ps -a
```

Keep your existing `.env`. Do not rerun the secret generator or recreate your accounts. The bind-mounted database/photos survive `compose down`; never delete `data/`. The new one-shot `storage` service assigns the photo directories to container UID 10001. `storage` and `migrate` should exit with code 0. `db`, `web`, `worker`, and `proxy` should remain running. The worker is configured with a 2 GiB memory ceiling; allow roughly 4 GiB total host RAM for the stack. Architecture-specific wheels must be available for Pillow/HEIF on your server.

Optionally set `LIBRARY_TIME_ZONE=America/New_York` (or your actual IANA timezone) in `.env` before restarting. Default is UTC. This affects fallback dates for future uploads lacking EXIF; camera-local EXIF dates stay unchanged. For initial testing, UTC is fine and a photo's date can be corrected in the detail view.

From your own computer, keep the SSH tunnel open:

```bash
ssh -N -L 8080:127.0.0.1:8080 basement@YOUR_SERVER_IP
```

Open http://localhost:8080 and refresh. You should now see **Add photos**. For direct phone access, use the HTTPS/Tailscale setup in `deployment.md`; do not expose development HTTP on the LAN or internet.

## Test the increment

Keep a separate copy of every test image; automated backups are the next milestone.

1. Sign in and select one JPEG. Watch the received/processing status. A thumbnail should appear after a few seconds; a large HEIC may take longer.
2. Upload multiple photos, including a PNG and HEIC if available. Drag a few onto the drop zone on desktop. The picker also supports mobile photo-library selection; it does not force camera capture.
3. Open a photo. Check its date, caption field, dimensions, and camera/GPS if present. Edit its date and caption and save. Its gallery position should follow the new date; the original file stays unchanged.
4. Upload an older camera photo with EXIF DateTimeOriginal. It should appear on the original local calendar date, not today. Missing timezone offsets never shift the day to UTC.
5. Upload a screenshot or image without EXIF. Its source should say upload date, and you can correct it. Browser file `lastModified` is deliberately not treated as capture time.
6. Check a portrait image: the thumbnail/preview should have the correct orientation. Download **unchanged original**, compare it with your selected source file using `sha256sum` on Linux, and confirm equal hashes. Originals may retain GPS; generated previews should not.
7. Copy a preview URL, sign out, then request it in a fresh private browser window. It should return sign-in required, not photo bytes. Both authorized members should see ready photos.
8. Try an invalid image, such as a text file renamed `.jpg`, and an image above 50 MiB. The first should fail processing without being displayed; the second should be refused. Failed originals remain private for inspection/recovery and continue to use disk space.
9. To verify durable queuing, stop the worker with `docker compose stop worker`, upload a test photo, then run `docker compose start worker`. It should process without reuploading. Do not stop PostgreSQL during a real import.
10. Run automated checks:

```bash
docker compose exec web python manage.py test memories --verbosity 2
docker compose exec web python manage.py makemigrations --check --dry-run
docker compose exec web python manage.py check_photo_storage
```

Expected: **40 tests pass**. The tests use a separate test database and temporary image directories. They do not delete production originals. Database credentials currently permit creating the test database; run tests during development, not heavy use.

## Troubleshooting

```bash
docker compose logs --tail=100 storage migrate web worker proxy
```

- **Too many login attempts:** `docker compose exec web python manage.py axes_reset`, then use the current password.
- **Permission denied connecting to Docker:** reconnect after joining the Docker group, or temporarily prefix the command with `sudo`.
- **Received but still processing:** confirm worker is running; inspect logs. Processing retries transient errors three times with a 30-second delay. A single job has a 90-second wall-time limit and 60-second CPU limit. The worker never rewrites the original.
- **Storage unavailable:** the uploader preserves at least 512 MiB of free-space reserve plus the maximum incoming file size. Free space on the photo volume and check the storage service. Disk failure after admission can still fail derivative creation; there is no promise that a preliminary space check guarantees success.
- **Unable to process:** invalid/unsupported files stay out of the gallery. For a transient storage issue, find the photo UUID from `/api/photos/uploads/` while signed in, correct the cause, then run `docker compose exec web python manage.py retry_photo PHOTO_UUID`. Do not repeatedly retry a corrupt file.
- **Connection dropped during upload:** use Retry unsuccessful uploads. It reuses the same UUID, so a completed server receipt is not duplicated. Selecting the file again creates a new upload; full content deduplication is not implemented.
- **Staged/unreferenced files:** `check_photo_storage` is read-only. A crash between file persistence and database commit may leave an original without a row. Retrying with the same upload UUID can recover it. Never run an indiscriminate cleanup command against originals. Inspect interrupted staging files during downtime; automatic orphan removal is intentionally deferred.

The gallery uses 48-photo cursor pages and lazy thumbnails. Upload batches are capped at 100 selected files; the client uploads sequentially. Admission limits are 60 accepted uploads per member per minute and approximately 100 queued photos, plus the free-space check. If a batch hits a limit, wait and retry its unsuccessful items. These are private-library limits, not a substitute for public edge abuse controls.

Still pending: automatic/verified backups, Trash, dedicated album/favorites editing, richer filtering/timeline, picture-book pages, and installable PWA. There is no permanent-delete action in this release.
