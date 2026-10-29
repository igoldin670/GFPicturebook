# Version 1.1: dates and little moments

Built on feature branch baseline `0bf530d`, retaining the centered serif title, Inter controls, quiet cream/sage design, existing video polaroids, and archive protections. No schema migration, new application dependency, drive operation, or automatic historical-date rewrite is introduced.

## Selecting and dating memories

Choose **Select** in Memories or a Dates chapter, then tick checkboxes or click polaroids. **Select loaded** includes the media already loaded in that view; it does not silently select the whole archive. Selection survives loading another cursor page. **Clear**, **Change date**, and **Done** are available in the toolbar. Up to 500 memories can be selected in one operation. Leaving selection mode, switching sections, or changing chapter clears the selection.

**Change date** assigns one shared calendar date to the selection, including videos. The confirmation shows the number of memories. Captions, embedded capture facts, unchanged originals, and replica manifests remain intact. A failed save retains the chosen date and selection so it can be retried. If an update empties the current chapter, Dates opens the nearest populated month, choosing the earlier month on a tie.

`POST /api/photos/bulk-date/` accepts JSON `{ "ids": ["memory-uuid"], "date": "2026-10-29" }` and returns `{ "updated": 1, "date": "2026-10-29" }`. It uses the same member authorization as single-memory editing and requires CSRF. Malformed dates/IDs or oversized selections return 400. Missing, non-ready, or trashed IDs return a generic 404 and no selected record is changed. Row locks and one transaction protect the batch. Explicit bulk assignments are marked manual even if the calendar date matches the previous value.

Descriptions remain editable in the lightbox and available in accessible names. Polaroid faces now display dates only. Rendering treats these as literal calendar dates, including camera-local dates, rather than converting them into the viewer's time zone.

## Browsing and uploading

Dates expands a **Browse dates** subsection beneath its sidebar item: a year dropdown and populated month buttons. Selecting another year opens its latest populated month. These controls, book arrows, and keyboard navigation all use the same page-turn action. Left/Right Arrow skips empty months. Shortcuts ignore typing fields, dropdowns, editable content, dialogs, selection mode, held-key repeats, modifiers, and in-flight page turns. Sidebar controls collapse on small screens.

The main page now has one centered **Add memories** panel with a small local polaroid illustration. Drag-and-drop, batch selection, file restrictions, progress, retry controls, and background processing retain their existing behavior. Formats/limits remain in the optional disclosure.

Five small decorative polaroids flutter for approximately two seconds after successful interactive sign-in. They use local artwork, do not intercept clicks or expose private media, disappear afterward, and do not replay on refresh or navigation. Reduced motion skips the animation.

## Capture metadata and Android diagnosis

The previous decoder already supported nested EXIF capture dates. This release additionally accepts ISO 8601 capture timestamps, respects separate EXIF offset tags for those timestamps, reads explicit XMP original/creation date fields when EXIF capture data is absent, and reads embedded video creation timestamps. Metadata-free files retain their upload-date fallback. No filename or filesystem timestamp is treated as a capture date. Reprocessing preserves manually assigned calendar dates while retaining useful embedded capture facts.

**The exact reported Android failure remains unconfirmed:** no affected Android originals or corresponding exported/shared copies were supplied. Regression fixtures are synthetic JPEG/HEIC/XMP/video examples, not claimed reproductions of a particular phone. Sharing/exporting can strip metadata; a capture date absent from the uploaded bytes cannot be recovered by this parser. Compare an untouched camera original with the affected uploaded version to complete that diagnosis.

### Explicit recovery for existing upload-fallback records

Use the memory UUID from its API record or admin URL. Inspect first:

```sh
docker compose -f compose.yaml -f compose.archive.yaml exec web \
  python manage.py reread_capture_dates MEMORY_UUID [ANOTHER_MEMORY_UUID]
```

This defaults to dry-run. After reviewing recovered dates, apply only those explicit IDs:

```sh
docker compose -f compose.yaml -f compose.archive.yaml exec web \
  python manage.py reread_capture_dates MEMORY_UUID [ANOTHER_MEMORY_UUID] --apply
```

Up to 500 IDs may be inspected per invocation. Manual dates, other non-fallback records, non-ready media, and trashed media are skipped. Reads use verified original descriptors, including surviving archive copies. A failed read reports an error and causes a nonzero exit status; successfully applied records are not rolled back across unrelated IDs. Originals and derivatives are never rewritten. Normal archive integrity observations may still be recorded while verifying a source.

## Upgrade

Keep the existing `.env`, drives configuration, database, and media directories:

```sh
git switch feature/redundant-media-archive
git pull --ff-only origin feature/redundant-media-archive
docker compose -f compose.yaml -f compose.archive.yaml up -d --build
```

Refresh the website. Existing dates are retained until explicitly edited or recovered with the command above.
