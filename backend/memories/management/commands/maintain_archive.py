"""Separate supervised repair/integrity worker; no media decoding."""
import subprocess
import sys
import time
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.db import close_old_connections, transaction
from django.utils import timezone
from django.conf import settings
from memories.models import StorageJob

class Command(BaseCommand):
    help = 'Continuously check drives, migrate legacy assets, verify and repair replicas.'
    def add_arguments(self, parser):
        parser.add_argument('--once', action='store_true')
        parser.add_argument('--job', type=int)
    def handle(self, *args, **options):
        from memories.services.archive import inventory, run_one
        if options['job']:
            run_one(options['job'])
            return
        last_inventory = 0
        while True:
            close_old_connections()
            if time.monotonic() - last_inventory >= 10:
                inventory()
                last_inventory = time.monotonic()
            with transaction.atomic():
                job = StorageJob.objects.select_for_update(skip_locked=True).filter(available_at__lte=timezone.now()).order_by('available_at', 'id').first()
                if job:
                    # Prevent a second supervisor from claiming the same job
                    # before the child obtains its long-lived row lock. If either
                    # process dies before that, the short lease expires safely.
                    job.status = 'running'
                    job.started_at = timezone.now()
                    job.available_at = timezone.now() + timedelta(seconds=30)
                    job.save(update_fields=['status','started_at','available_at'])
            if not job:
                if options['once']:
                    return
                time.sleep(2)
                continue
            # Parent records running state outside the child transaction so admin
            # can observe it. A restarted supervisor retries interrupted work.
            command = [sys.executable, str(settings.BASE_DIR / 'manage.py'), 'maintain_archive', '--job', str(job.pk)]
            process = subprocess.Popen(command)
            deadline = time.monotonic() + 21600
            try:
                while process.poll() is None:
                    if time.monotonic() >= deadline:
                        process.kill()
                        process.wait()
                        break
                    if time.monotonic() - last_inventory >= 10:
                        inventory()
                        last_inventory = time.monotonic()
                    time.sleep(1)
                failed = process.returncode != 0
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()
            if failed:
                StorageJob.objects.filter(pk=job.pk).update(status='retry', error_code='worker_interrupted',
                    available_at=timezone.now() + timedelta(seconds=settings.STORAGE_RETRY_SECONDS))
