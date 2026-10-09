# Private access and security

## Recommended: Tailscale + application login

Install Tailscale on the Linux server and both people's phones/computers using its official instructions. Invite your partner to your tailnet; restrict ACLs/grants to these two identities and this server's HTTPS service. Use MFA on the identity provider. Review Tailscale's identity/control-plane dependency and available plans; WireGuard is an alternative if you prefer managing VPN keys and routing yourself.

Do not forward router ports. Keep Docker's proxy publication at `127.0.0.1:8080`; database/web ports remain unexposed. On a fresh server:

```sh
python3 scripts/init-env.py
# Edit .env locally; do not paste its contents into chat or source control.
# DJANGO_DEBUG=0
# DJANGO_ALLOWED_HOSTS=album.<your-tailnet>.ts.net
# CSRF_TRUSTED_ORIGINS=https://album.<your-tailnet>.ts.net
docker compose up --build -d
docker compose exec web python manage.py createsuperuser
docker compose exec web python manage.py create_member your-partners-username
sudo tailscale serve --bg http://127.0.0.1:8080
sudo tailscale serve status
```

Use the hostname returned by Tailscale, with HTTPS enabled for the tailnet. Tailscale Serve terminates TLS, sends HTTP to loopback Caddy, and Caddy supplies the trusted HTTPS header to Django. Do not enable **Tailscale Funnel**, which exposes a service publicly. Tailscale clients must be connected on both devices. Tailscale HTTPS certificate names may appear in public certificate transparency logs; use a neutral server hostname.

In an existing `.env`, set production options explicitly; the generator will not overwrite it. Recreate services after environment edits: `docker compose up -d --force-recreate`. HTTP-only browser testing with DEBUG=0 will not establish a session because cookies require HTTPS; that is intentional. Verify a fresh browser can sign in over HTTPS, cookie flags include Secure/HttpOnly/SameSite, and a device outside your tailnet cannot reach the site. Keep application authentication even behind the VPN.

```sh
docker compose exec web python manage.py check --deploy
```

The app has seven-day fixed-expiry server-side sessions, session-key rotation on login, CSRF verification including Origin checking, and Argon2 password hashing. Schedule `python manage.py clearsessions` daily once adding the scheduler. Disabling a user blocks subsequent requests through Django's authentication backend; changing a password invalidates their existing sessions. Use `changepassword username` from a trusted shell for recovery. There is no public registration. Give only your administrator account staff/superuser status; your partner can use a normal member account.

The Django admin supplies user and album management. Photo records are read-only and cannot be hard-deleted through admin in this increment. Future admin changes must call the same validation/Trash services as the main API.

## Alternative: public Caddy + application login

Public ingress is more convenient without a VPN client, but anyone can reach your login page and exercise your HTTP server. It does not meet strict network invisibility. Use it only if that tradeoff is desired, after the hardening milestone.

1. Point a domain to the server and replace the Caddy site address `:80` with your domain. Caddy automatically obtains and renews Let's Encrypt certificates when DNS and inbound ports permit it.
2. Publish proxy ports 80 and 443 and persist Caddy's data; remove the loopback port mapping. Leave PostgreSQL and Gunicorn on the internal Docker network.
3. Remove the hardcoded `header_up X-Forwarded-Proto https`; Caddy sets this correctly from the incoming TLS connection. Do not accept arbitrary forwarding headers from external proxies. Configure trusted proxies explicitly if adding one.
4. Set DEBUG=0, exact allowed hostnames and HTTPS CSRF origins. Retain secure cookies, HSTS, CSP, and same-origin requests.
5. Before exposing: add properly configured per-client edge request/upload limits and preferably app MFA/passkeys; keep Axes account lockout, patch dependencies, firewall other ports, and monitor failure/backup/storage alerts. Caddy core does not supply a general rate-limiting directive: use a maintained configured gateway/module if needed.

Current Axes settings independently lock usernames and the direct peer IP after five failed logins for 15 minutes. Behind the private proxy the IP bucket is shared, which is conservative for two users but can temporarily block both. This is not a complete internet-scale anti-abuse layer. Do not trust user-supplied X-Forwarded-For to fix it.

## Other protections and operational limits

- No media directory is exposed by the proxy, Django, or static-asset middleware. Frontend assets contain no secrets; API/auth responses are `private, no-store`.
- Only generated `.env` values hold credentials; its permissions are 0600, it is ignored by Git and excluded from image builds. Encrypt a recovery copy separately. Docker administrators/root can read container environments; Docker host access is privileged.
- The application container runs as UID 10001 with a read-only root filesystem, dropped Linux capabilities, no-new-privileges, and a bounded temporary filesystem. Its photo mount is read-only until ingestion is implemented. Future worker/upload mounts need scoped write access and owned host directories.
- Current request size is 64 KiB; uploads are unavailable. Future ingestion must add both streamed byte counting and decoded-pixel limits before raising it. File type validation is not implemented by merely listing accepted browser MIME types.
- Original downloads may contain GPS; derivatives should strip metadata. Do not log passwords, cookies, binary data, captions, GPS, or raw EXIF. Restrict and rotate operational logs.
- Database encryption at rest comes from encrypted server disks. Restic encrypts backups independently. A VPN and login do not protect against a compromised server or malicious browser on an authorized device.
- Django's default superuser/password management commands may offer to bypass validators: do not bypass them. Use a password manager and unique long passwords.
- Pin exact deployment image digests after qualification, keep an update schedule, and test restore after major upgrades. A PostgreSQL major upgrade requires a supported migration/dump-restore procedure; changing the image tag alone is insufficient.

No real-server DNS, Tailscale configuration, certificate issuance, or offsite backup has been performed by this source implementation.
