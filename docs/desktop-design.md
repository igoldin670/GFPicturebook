# Desktop design refinement

The interface keeps its cream, sage, and terracotta palette and its polaroids and memory book. The desktop layout now has a wider navigation rail, a centered serif-and-italic main title, compact collection counters, a compact upload area, and an adaptive gallery inside a 1560 px maximum-width shell. Large desktops can show five polaroids per row; phones retain two. Completed upload details collapse automatically, while ongoing transfers, processing jobs, failed transfers, and retry controls remain available.

Inter Variable is the default UI font for navigation, forms, buttons, secondary headings, the lightbox, and administration. The main page titles use the original Georgia serif, with italic sage emphasis. Weights establish hierarchy without introducing extra typefaces. Georgia is intentionally retained for the physical book's chapter titles and inscriptions and the illustrated keepsake, preserving their album character. Inter is served locally, including through Django's collected static files; browsers do not contact a font CDN. The bundled file is the unmodified Latin variable font from Fontsource Variable Inter 5.2.8. Its SIL Open Font License and attribution are in `frontend/public/static/fonts/OFL.txt`.

An original orbit mark replaces the heart emblem in the header, login panel, book, admin header, and favicon. Matching SVG line icons replace text glyphs on controls, videos, and the upload area. Supporting copy uses “Our digital world” where appropriate; authored UI copy and loading placeholders contain no em dashes. User filenames, captions, dates, and original files are preserved.

The admin uses the same typography and palette, with responsive metrics, table panels that scroll independently, and a matching dark theme. Project templates take precedence over Django's stock admin branding. Direct Django development can find the shared public font/theme assets without requiring a production frontend directory.

## Online references reviewed

- [shadcn/ui's official dashboard preview](https://github.com/shadcn-ui/ui/blob/main/apps/v4/public/opengraph-image.png): distinct navigation/content regions, consistent card padding, a strong heading/value hierarchy, and restrained controls.
- [GitHub Primer Primitives](https://github.com/primer/primitives): shared spacing, typography, and color tokens rather than one-off component values.
- [Primer CSS](https://github.com/primer/css): readable component boundaries and consistent interactive states.

These informed spacing and hierarchy. No component library or remote asset service was added.

## Review checklist

Check sign-in, Memories, Dates, photo/video details, upload/retry controls, the admin home, photo list, storage dashboard, and admin light/dark themes. Review desktop widths up to 1920 px and phone widths down to 320 px; check long usernames, keyboard focus, reduced motion, font loading, and table scrolling. Confirm the Dates cover/page animations, uploads while switching sections, media playback/seeking, editing, downloads, and authorization still work.

## Quieter title-focused refinement

Main titles are centered and regain the original serif-and-italic treatment. Decorative eyebrows, sidebar/footer taglines, the welcome paragraph, the private-header slogan, and the extra statistic caption are removed. The counters keep their actual values in a compact row rather than competing cards. The upload area uses a short instruction and an optional Formats and limits disclosure, while its controls, drag-and-drop, limits, progress, processing status, and retries remain available. Programmatically focused section headings have no decorative outline; interactive controls retain visible keyboard focus.
