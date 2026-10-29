"""Explicit, dry-run-first recovery of capture dates from retained originals."""
import json
import uuid
from PIL import Image
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from memories.models import Photo
from memories.services.archive import verified_source
from memories.services.metadata import image_capture, video_capture
from memories.services.videos import command


class Command(BaseCommand):
    help = 'Inspect explicit missing-date or legacy upload-fallback memory IDs. Add --apply to save recovered capture dates.'

    def add_arguments(self, parser):
        parser.add_argument('ids', nargs='+', type=uuid.UUID)
        parser.add_argument('--apply', action='store_true')

    def handle(self, *args, **options):
        if len(options['ids']) > 500:
            raise CommandError('Inspect at most 500 explicit memory IDs per invocation.')
        failures = 0
        for identifier in dict.fromkeys(options['ids']):
            photo = Photo.objects.filter(pk=identifier, status='ready', trashed_at__isnull=True, date_source__in=['upload', 'missing']).first()
            if photo is None:
                self.stdout.write(f'{identifier}: skipped (unavailable or already has a capture/manual date)')
                continue
            try:
                with verified_source(photo, 'original') as source:
                    if photo.media_kind == 'video':
                        probe = command('ffprobe', source, ['-show_streams', '-show_format', '-of', 'json', f'/proc/self/fd/{source.fileno()}'], 30)
                        capture = video_capture(json.loads(probe.stdout))
                    else:
                        with Image.open(source) as image:
                            capture = image_capture(image)
                if not capture:
                    self.stdout.write(f'{identifier}: no trustworthy capture date found')
                    continue
                if options['apply']:
                    with transaction.atomic():
                        current = Photo.objects.select_for_update().filter(pk=identifier, status='ready', trashed_at__isnull=True, date_source__in=['upload', 'missing']).first()
                        if current is None:
                            self.stdout.write(f'{identifier}: skipped (changed since inspection)')
                            continue
                        Photo.objects.filter(pk=identifier).update(**capture)
                self.stdout.write(f"{identifier}: {'applied' if options['apply'] else 'dry-run'} {capture['display_date'].isoformat()}")
            except Exception as exc:
                # Continue other explicit IDs; do not print source paths or embedded GPS.
                failures += 1
                self.stderr.write(f'{identifier}: could not read capture metadata ({type(exc).__name__})')
        if failures:
            raise CommandError(f'{failures} original(s) could not be inspected; review the errors before retrying.')
