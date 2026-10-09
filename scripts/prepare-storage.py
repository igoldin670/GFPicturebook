"""One-shot container initialization for a bind mount, without recursive chown."""
import os
from pathlib import Path
root = Path('/photos')
for path in [root, *(root / name for name in ('originals', 'previews', 'thumbnails', 'staging'))]:
    path.mkdir(parents=True, exist_ok=True)
    os.chown(path, 10001, 10001)
    path.chmod(0o750)
print('Photo directories ready for the non-root application and worker.')
