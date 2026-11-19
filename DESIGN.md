---
name: Our little album
description: A handbound photo journal for personal memories
colors:
  primary: "#203B50"
  paper: "#F4EFE5"
  surface: "#FFFDF8"
  text: "#23323B"
  muted: "#596770"
  line: "#D6D3C9"
  accent-soft: "#E3E9EB"
  copper-ink: "#8B5E45"
  foil: "#D2B895"
typography:
  display:
    fontFamily: "Bodoni Moda, Georgia, serif"
    fontSize: "clamp(36px, 3.55vw, 54px)"
    fontWeight: 400
    lineHeight: 1.08
    letterSpacing: "-0.025em"
  body:
    fontFamily: "Inter, system-ui, sans-serif"
    fontSize: "14px"
    fontWeight: 400
  control:
    fontFamily: "Inter, system-ui, sans-serif"
    fontSize: "12px"
    fontWeight: 550
rounded:
  paper: "2px"
  control: "6px"
  dialog: "10px"
spacing:
  small: "8px"
  medium: "16px"
  section: "24px"
  gutter: "40px"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.surface}"
    rounded: "{rounded.control}"
    padding: "11px 16px"
    height: "44px"
  button-primary-hover:
    backgroundColor: "#34566E"
---
# Handbound photo journal

## Overview

Picturebook v1.2 replaces the sage dashboard shell with the approved ink-blue photo journal. Member browsing is an experience; date assignment, upload handling and administration are working screens with quieter controls.

## Colors

- Bookcloth ink: `#203B50`, used for navigation, the sign-in cover, the physical Dates cover, primary buttons and links.
- Paper: `#F4EFE5`; Polaroid and input surface: `#FFFDF8`.
- Text: `#23323B`; secondary text: `#596770`; border: `#D6D3C9`.
- Copper ink: `#8B5E45` for small inscriptions; `#A8785E` is decorative copper only, not small body text. Gold foil on dark cloth: `#D2B895`.
- Semantic errors use a distinct pale red surface and dark red text. They never share the decorative copper palette.
- `bookcloth.svg` is an original 6px geometric warp-and-weft tile, not a photograph or generated raster. Texture is confined to cloth surfaces. Page curvature uses static shaded gradients; the stacked page edges retain their physical ruled construction.

## Typography

Bodoni Moda variable roman/italic (Fontsource 5.3.0, unmodified Latin WOFF2) is locally served for page titles, chapters, inscriptions and Polaroid dates. Its high-contrast lettering makes the book feel typeset rather than a SaaS dashboard. The optical-size/weight variable files are bundled with their SIL Open Font License.

Inter variable remains the readable UI voice for navigation, controls, file facts and administration. It is served locally with its existing license. No remote font service is contacted by visitors. Georgia and system sans stacks are fallbacks.

The centered main title retains “The little things. The everything things.” at 36–54px on desktop and 31–42px on phones. Body controls use 11–14px, with at least 44px control heights. Display tracking stays at or above -0.035em. Small Polaroid dates use the display face in italic, and stay on one line.

## Layout

The 1440px-wide application shell has a 202px cloth navigation rail and 40px gutter on desktop. The title is followed by one shallow upload surface, then a collection/filter/selection toolbar and photographs. Complete Polaroids appear inside a 900px-high desktop viewport. Counts are contextual rather than dashboard metrics; there are no album/favourite placeholder counters.

At 800px and below, navigation becomes a compact horizontal cloth strip; Dates controls expand beneath it. Media uses two columns below 560px, three on tablets and laptops, and up to five on wide desktops. Every cell has a real button covering its image, frame and caption. Small deterministic rotations never overlap adjacent cards. Selection straightens the chosen cards and adds an outline and accessible checkbox.

The sign-in screen is one physical journal object: cloth cover and pale endpaper form, stacked vertically on phones. Admin retains Django's layouts, permissions and theme switcher, with matching blue/paper light and blue dark tokens.

## Elevation & Depth

Photographs use the shared `--shadow`: `0 3px 5px #122b3a08, 0 12px 24px #122b3a12`, lifting softly on hover. Inputs and upload controls use borders rather than ornamental shadows. Physical page depth, center binding and shade stay localized to the actual book. Native dialogs use `0 20px 80px #0c223866` with a dark blue backdrop.

## Shapes

Polaroids retain 2px paper corners; forms and navigation use 5–8px radii; dialogs use 10px. Buttons have 6px corners and 44px minimum height. Rounded pills are reserved for small counters and the play icon. Full borders define controls; avoid decorative accent bars.

## Components

The Dates cover retains a 1.75s perspective opening and 1.1s page turns. Navigation occupies its own gutters on large desktops or a separate row below the book at narrower widths. Decorative faces, tape, binding, ribbon and duplicate leaves never receive clicks. Settled pages alone enable media controls.

The once-per-interactive-login cascade keeps three waves (48 desktop / 28 small-screen items), now with blue, copper and muted green abstract paper artwork. It ends within four seconds and is removed from the DOM. It is non-interactive and hidden from assistive technology. Reduced motion removes the cascade, card rotations, movement and book transitions.

Hover lifts are restrained. Focus rings, selection colour, caret and scrollbars belong to the same palette. Dialogs retain native keyboard trapping and Escape dismissal. Background upload state stays mounted across section changes.

### Asset provenance

The orbit SVG and cloth geometry are project-authored vector assets. Bodoni Moda and Inter carry their source and licenses under `frontend/public/static/fonts/`. No new raster image ships in production. Browser fixtures and review screenshots use synthetic sample memories, never private gallery media.

## Do's and Don'ts

The existing API, nullable dates, pagination cursors, CSRF checks, 500-item bulk edits, originals and replication backend are unchanged. Storage status and identifiers stay in authorized administration. Product and design contracts are development documents, not browser-delivered UI copy.
