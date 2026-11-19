# Our little album

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

A couple revisiting and collecting personal photos and videos. The application began as a birthday gift for the owner's girlfriend. Other people can self-host their own installation.

## Product Purpose

A private digital picture book that makes everyday memories feel worth keeping. Browsing should feel like revisiting a personal album, while organizing large uploads stays practical.

## Operating Context

Self-hosted Linux/Docker deployment, with private Tailscale access on the owner's server. Desktop and phone browsers share the same authenticated gallery. Administrators manage users and archive health separately.

## Capabilities and Constraints

- Photo/video uploads, private originals, thumbnails, compatible video playback, seeking, and downloads.
- Memories, Dates, and Missing dates share media filters. Missing capture metadata stays undated until explicitly assigned or reliably recovered.
- Bulk date editing supports up to 500 selected memories, including selections across loaded pages. Captions and manually assigned dates are preserved.
- Dates uses real populated months, sidebar year/month navigation, scoped keyboard shortcuts, and a 3D opening/page-turn book.
- Uploads continue during section changes. Original bytes, verified replicas, checksums, and backend authorization must remain intact.
- Storage names, paths, identifiers, and health information appear only in the authorized admin interface.

## Brand Commitments

Preserve the scrapbook idea, photo/video Polaroids, physical book, orbit emblem, and “The little things. The everything things.” title. The approved v1.2 direction is a handbound photo journal with ink-blue bookcloth, warm pages, and elegant lettering. Keep the copy personal and restrained, with no authored em dashes.

## Evidence on Hand

The existing React frontend, Django backend, release documents, and backend regression suite establish current behaviour. Development screenshots and fixtures use synthetic memories; no private gallery media ships with source or tests.

## Product Principles

- Let the memories lead; controls support rather than compete.
- Make organizing reliable without making browsing feel administrative.
- Preserve private originals and explicit user decisions.
- Keep the distinctive book experience usable on phones and with a keyboard.

## Accessibility & Inclusion

Visible focus, semantic controls, accessible dialogs, readable contrast, reduced-motion alternatives, and responsive layouts down to 320px.
