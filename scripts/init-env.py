#!/usr/bin/env python3
"""Create a private .env without printing secrets or overwriting existing settings."""
import argparse
import os
import secrets
from pathlib import Path
parser = argparse.ArgumentParser()
parser.add_argument("--local", action="store_true", help="Allow local HTTP development only")
args = parser.parse_args()
root = Path(__file__).resolve().parent.parent
text = (root / ".env.example").read_text().replace("DJANGO_SECRET_KEY=\n", "DJANGO_SECRET_KEY=" + secrets.token_urlsafe(64) + "\n").replace("POSTGRES_PASSWORD=\n", "POSTGRES_PASSWORD=" + secrets.token_urlsafe(48) + "\n")
if args.local:
    text = text.replace("DJANGO_DEBUG=0", "DJANGO_DEBUG=1").replace("CSRF_TRUSTED_ORIGINS=\n", "CSRF_TRUSTED_ORIGINS=http://localhost:8080,http://127.0.0.1:8080,http://localhost:5173,http://127.0.0.1:5173\n")
with os.fdopen(os.open(root / ".env", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as f:
    f.write(text)
print("Created .env with mode 0600. Configure hostname and HTTPS before deployment.")
