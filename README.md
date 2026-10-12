# Our little album

A private, self-hosted picture book for two. Warm ivory, sage, quiet typography, and a focus on your photographs.

**Increment 2 is implemented:** secure accounts, single/multiple photo uploads and desktop drag-and-drop, background processing for JPEG/PNG/WebP/HEIC, unchanged originals, EXIF dates/camera/GPS/orientation, private thumbnails/previews/downloads, a paginated chronological gallery, and caption/date editing. Picture-book navigation, richer album/favorites UI, timeline/search, Trash actions, PWA installation, and automatic backups are still planned. Keep an independent copy of every photo.

**Already running increment 1? Follow [the server upgrade and photo test guide](docs/photo-uploads.md).** Keep your existing `.env` and accounts.

Read [the architecture](docs/architecture.md) first, then [the development roadmap](docs/roadmap.md). [Security and deployment](docs/deployment.md) and [backup/restore design](docs/backups.md) explain the long-term operating model.

## First installation

Prerequisites: Docker Engine with Compose v2 and Python 3 for generating local configuration. From this project directory:

```sh
python3 scripts/init-env.py --local
docker compose up --build -d
docker compose exec web python manage.py createsuperuser
docker compose exec web python manage.py create_member your-partners-username
```

Use a separate username for each person. Commands prompt for passwords; no default credentials exist. `--local` permits HTTP only for this local test. Open http://localhost:8080, sign in, and open Manage our space for the admin. A member can sign in but cannot access admin. Compose waits for PostgreSQL, applies migrations in a one-shot service, then starts the web app. The database and application ports are not published; the proxy binds only to loopback.

On a remote server, use an SSH tunnel for this local test (`ssh -L 8080:127.0.0.1:8080 user@server`), or configure the production HTTPS/Tailscale instructions before signing in. Do not expose development HTTP.

If `.env` already exists, the generator refuses to overwrite it. Keep it: changing a running PostgreSQL container's password variable does not change the database password. `docker compose down` retains bind-mounted data. Never remove `data/` casually.

## Verify the application

```sh
docker compose exec web python manage.py test memories --verbosity 2
docker compose exec web python manage.py makemigrations --check --dry-run
docker compose logs --tail=50 migrate web proxy
```

Tests create and remove a separate test database. Use development data for this command. Manual checks:

1. In a private browser window, `/api/summary/` returns 401 and `/admin/` requires login.
2. Sign in using both accounts separately. Both see the same shared photo library.
3. A regular member cannot access admin; the administrator can create/edit albums and manage users.
4. Sign out; the summary endpoint becomes inaccessible again. Login/logout without CSRF is rejected.
5. Five failed logins trigger a 15-minute cooldown. The proxy-IP bucket may temporarily lock both users. For local recovery only: `docker compose exec web python manage.py axes_reset`.
6. Test a narrow phone-sized browser and keyboard-only navigation. Upload a few test photos, wait for processing, open each preview, edit a caption/date, and download the original. Follow the detailed photo checks in `docs/photo-uploads.md`.

## Develop without Docker

Python 3.12+ and Node 24 LTS are recommended. SQLite is an explicit local development convenience; PostgreSQL is the deployment database.

```sh
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.lock
npm ci --prefix frontend
# Generate once; skip if .env already exists.
python3 scripts/init-env.py --local
set -a
. ./.env
set +a
export USE_SQLITE=1
export PHOTO_ROOT="$PWD/data/photos"
.venv/bin/python backend/manage.py migrate
.venv/bin/python backend/manage.py createsuperuser
.venv/bin/python backend/manage.py create_member your-partners-username
.venv/bin/python backend/manage.py runserver 127.0.0.1:8000
```

In another terminal: `npm run dev --prefix frontend`. Run the worker in a third terminal with the same environment loaded: `cd backend && ../.venv/bin/python manage.py process_photos`. PostgreSQL is required for concurrent workers; SQLite is only for single-worker local development. Open http://localhost:5173. Vite proxies `/api/` and `/admin/` to Django; the React page is served by Vite in development. Do not use Django's root URL in this mode: its frontend template is assembled in the production Docker build.

```sh
# With the environment loaded as above:
.venv/bin/python backend/manage.py test memories
.venv/bin/python backend/manage.py makemigrations --check --dry-run
npm run build --prefix frontend
```

## Files and responsibilities

```text
GFPicturebook/
├── backend/
│   ├── config/                 # Settings, routing, WSGI
│   ├── memories/
│   │   ├── models.py           # Photos, albums, memberships, favorites, jobs, backups
│   │   ├── migrations/        # Versioned schema
│   │   ├── views.py            # CSRF/session/login/logout/private summary APIs
│   │   ├── photo_views.py      # Upload, cursor gallery, metadata editing, private media
│   │   ├── services/photos.py  # Durable storage, EXIF, thumbnails and worker transactions
│   │   ├── middleware.py       # Private response and browser security headers
│   │   ├── admin.py            # Restricted admin (no hard photo deletion)
│   │   ├── tests.py            # Authentication and relationship regression tests
│   │   ├── test_photos.py      # Image, storage, processing and privacy regression tests
│   │   └── management/commands/create_member.py
│   ├── requirements.txt        # Direct dependency constraints
│   ├── requirements.lock       # Exact resolved Python dependencies
│   └── manage.py
├── frontend/
│   ├── src/main.tsx            # Sign-in and authenticated welcome screen
│   ├── src/Gallery.tsx         # Upload progress, gallery and editable photo details
│   ├── src/style.css           # Responsive design, local fonts, reduced motion
│   ├── package-lock.json       # Exact JS dependency resolution
│   └── vite.config.ts
├── deploy/Caddyfile            # Loopback ingress behind Tailscale Serve
├── scripts/init-env.py         # Generates private secrets without printing them
├── docs/                       # Design, deployment, roadmap, backup/restore
├── compose.yaml
├── Dockerfile                  # React build + non-root Django runtime
├── .env.example                # Names and non-secret defaults only
└── data/                       # Ignored persistent host data, created by Compose
    ├── postgres/
    ├── photos/                 # Private shared photo storage for web + worker
    │   ├── originals/
    │   ├── thumbnails/
    │   ├── previews/
    │   └── staging/
    ├── caddy-data/
    └── caddy-config/
```

`backend/web/` and `backend/staticfiles/` are assembled inside the image. Original photographs are never frontend build assets. No external font, image, analytics, or CDN service is used.

See [verification results and limits](docs/verification.md) for checks actually performed.

## Maintenance

Track this source in Git; keep `.env`, photo storage, databases, and backups outside Git. Review dependencies monthly and promptly apply security releases. Regenerate `requirements.lock` in a clean virtual environment after updating direct constraints; run the tests and image build before upgrading the server. Pin deployed image digests after testing a release. Read the backup plan before the first real import.
