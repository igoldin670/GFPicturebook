# Dates: the memory book

Sign in and choose **Dates** in the navigation rail (a compact row on phones), or open the site's `/#dates` URL. A sage hardcover opens into monthly chapters. The subtle controls inside the book turn to the previous or next populated month; **Find a chapter** jumps directly to any month. The polaroids beneath the book show that chapter's collection, with pagination for larger months. Photos and video polaroids use the same editable lightbox and unchanged-original downloads as Memories.

Chapters are generated from every ready, non-trashed memory's existing `display_date`, including videos. Camera capture metadata supplies this date when available, otherwise the upload date is used. An explicitly edited date overrides the grouping without changing the original file or its camera metadata. Camera-local dates are preserved even when the UTC timestamp falls on a different day. New uploads automatically add chapters after processing; months without memories are skipped. No schema migration or media rewrite is needed.

The existing gallery remains mounted while browsing Dates, so switching sections does not cancel queued uploads. Date/caption edits refresh both views. Browser back/forward and reloading `#dates` work. The chapter index and filtered gallery APIs both require the same session authentication as the rest of the collection; neither returns drive or backup information. Month pagination cursors are signed and scoped to that month.

The cover has a short 420 ms arrival pause followed by a 1.75 second hinge opening. Titles fade in after opening. Forward and backward turns use two-sided paper leaves and a 1.1 second rotation; controls are temporarily disabled while fetching or turning so pages cannot overlap. A failed fetch keeps the current chapter visible and offers a retry. Textures and decoration are local CSS/SVG, with no external assets or animation dependencies. Thumbnails load lazily; only the first 48 media records of a chapter are fetched initially. The browser's reduced-motion preference opens the book immediately and updates chapters without rotation.

## Checks

- Upload memories with capture dates in different months. Check chapter names/counts and month filtering; try a month with more than 48 memories.
- Use Tab and Enter to browse chapters and open a polaroid. Escape closes the existing lightbox. Edit a date into a previously empty month and check the chapter picker and Memories gallery.
- Navigate to Dates during an upload and confirm it finishes. Test browser back/forward, a direct `#dates` URL, and reduced motion.
- Check desktop, tablet, and 320–390 px phone layouts, including the cover and page-turn animation frames. Play a video and seek in the shared lightbox.
- Signed-out requests to `/api/photos/months/` and `/api/photos/?month=YYYY-MM` must return 401. Members must still receive 403 from `/api/admin/storage/`.

Backend regressions are in `backend/memories/test_dates.py`; run `python manage.py test memories` with the project's normal test environment. Build the frontend with `npm run build --prefix frontend`.
