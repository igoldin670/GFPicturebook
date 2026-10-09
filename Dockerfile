# syntax=docker/dockerfile:1
FROM node:24-bookworm-slim AS frontend
WORKDIR /build
COPY frontend/package*.json ./
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export NODE_EXTRA_CA_CERTS=/run/secrets/proxy_ca; fi; npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY backend/requirements.lock ./
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export PIP_CERT=/run/secrets/proxy_ca; fi; pip install --no-cache-dir -r requirements.lock
COPY backend/ ./
COPY --from=frontend /build/dist ./web
# A temporary key is used only to collect public static assets, never for runtime.
RUN python -c 'import os,secrets; os.environ["DJANGO_SECRET_KEY"]=secrets.token_urlsafe(64); os.environ["DJANGO_SETTINGS_MODULE"]="config.settings"; from django.core.management import execute_from_command_line; execute_from_command_line(["manage.py","collectstatic","--noinput"])' \
    && chmod -R a+rX /app \
    && groupadd --gid 10001 album && useradd --uid 10001 --gid album --no-create-home album
USER 10001:10001
EXPOSE 8000
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "30", "--access-logfile", "-", "--error-logfile", "-"]
