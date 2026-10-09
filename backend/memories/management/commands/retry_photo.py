"""Recover a failed decode after correcting storage/resource problems."""
import uuid
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from memories.models import Photo, ProcessingJob

class Command(BaseCommand):
    help = "Retry a failed photo without uploading or rewriting its original."
    def add_arguments(self, parser):
        parser.add_argument("photo_id", type=uuid.UUID)
    def handle(self, *args, **options):
        with transaction.atomic():
            # Match the worker's lock order: job first, photo second.
            job = ProcessingJob.objects.select_for_update().filter(photo_id=options['photo_id']).first()
            if job is None:
                raise CommandError('No processing job found.')
            photo = Photo.objects.select_for_update().get(pk=job.photo_id)
            if photo.status != Photo.Status.FAILED:
                raise CommandError('Only failed photos can be retried.')
            photo.status = Photo.Status.PENDING
            photo.save(update_fields=['status'])
            job.attempts, job.error_code, job.available_at = 0, '', timezone.now()
            job.save()
        self.stdout.write('Photo queued again; the original is unchanged.')
