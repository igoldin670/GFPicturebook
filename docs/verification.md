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
