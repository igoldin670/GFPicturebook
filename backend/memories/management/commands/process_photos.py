"""One supervisor, one bounded decoder subprocess at a time."""
import os
import subprocess
import sys
import time
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.db import close_old_connections, transaction
from django.utils import timezone
from memories.models import Photo, ProcessingJob

class Command(BaseCommand):
    help = "Process queued photos; --once drains currently available jobs and exits."
    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true")
        parser.add_argument("--job", type=int, help="Internal: decode one job with resource limits")
    def handle(self, *args, **options):
        if options["job"]:
            # Resource limits are applied before native image libraries are imported.
            import resource
            resource.setrlimit(resource.RLIMIT_AS, (1536 * 1024**2, 1536 * 1024**2))
            resource.setrlimit(resource.RLIMIT_CPU, (60, 60))
            from memories.services.photos import process_one
            process_one(options["job"])
            return
        while True:
            close_old_connections()
            job_id = ProcessingJob.objects.filter(photo__status=Photo.Status.PENDING, available_at__lte=timezone.now()).order_by("available_at", "id").values_list("id", flat=True).first()
            if job_id is None:
                if options["once"]:
                    return
                time.sleep(2)
                continue
            try:
                result = subprocess.run([sys.executable, "manage.py", "process_photos", "--job", str(job_id)], timeout=90, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                crashed = result.returncode != 0
            except subprocess.TimeoutExpired:
                crashed = True
            if crashed:
                # Native decoder crashes roll back their transaction. Bound retries here.
                with transaction.atomic():
                    job = ProcessingJob.objects.select_for_update().get(pk=job_id)
                    photo = Photo.objects.select_for_update().get(pk=job.photo_id)
                    if photo.status == Photo.Status.PENDING:
                        job.attempts += 1
                        job.error_code = "decoder_interrupted"
                        job.available_at = timezone.now() + timedelta(seconds=30)
                        if job.attempts >= 3:
                            photo.status = Photo.Status.FAILED
                            photo.save(update_fields=["status"])
                        job.save()
                self.stderr.write(f"Photo job {job_id}: decoder interrupted; retry bounded to three attempts.")
