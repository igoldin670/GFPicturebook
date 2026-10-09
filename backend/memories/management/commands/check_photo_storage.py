"""Report storage discrepancies without automatically deleting any bytes."""
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand
from memories.models import Photo

class Command(BaseCommand):
    help = "Read-only reconciliation of original files and database references."
    def handle(self, *args, **options):
        root = settings.PHOTO_ROOT
        expected = set(Photo.objects.values_list('original_key', flat=True))
        actual = {str(path.relative_to(root)) for path in (root/'originals').glob('*/*') if path.is_file()}
        missing, orphaned = expected - actual, actual - expected
        self.stdout.write(f'{len(missing)} missing originals; {len(orphaned)} unreferenced originals; {len(list((root/"staging").glob("*.part")))} staged files.')
        for key in sorted(missing):
            self.stdout.write(f'MISSING {key}')
        for key in sorted(orphaned):
            self.stdout.write(f'UNREFERENCED {key}')
        self.stdout.write('No files deleted. Run during a quiet period; active uploads may briefly appear unreferenced.')
