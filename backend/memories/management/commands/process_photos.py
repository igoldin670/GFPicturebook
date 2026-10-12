"""Fair, memory-bounded media supervisor: up to two photos and one video."""
import os
import signal
import subprocess
import sys
import time
from datetime import timedelta
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import close_old_connections, transaction
from django.db.models import Q
from django.utils import timezone
from memories.models import Photo, ProcessingJob


def claim_job(kinds=None):
    with transaction.atomic():
        jobs = ProcessingJob.objects.select_for_update(skip_locked=True).filter(
            photo__status=Photo.Status.PENDING, available_at__lte=timezone.now()).filter(
                Q(lease_until__isnull=True) | Q(lease_until__lte=timezone.now()))
        if kinds:
            jobs = jobs.filter(photo__media_kind__in=kinds)
        job = jobs.order_by('available_at', 'id').first()
        if job:
            # Bridge the gap between parent admission and the child's row lock.
            # Crashes before decoding simply release this claim after 30 seconds.
            job.lease_until = timezone.now() + timedelta(seconds=30)
            job.save(update_fields=['lease_until'])
        return job


def kill_group(process):
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait()


def record_crash(job_id):
    with transaction.atomic():
        job = ProcessingJob.objects.select_for_update().filter(pk=job_id).first()
        if not job:
            return
        photo = Photo.objects.select_for_update().get(pk=job.photo_id)
        if photo.status == Photo.Status.PENDING:
            job.attempts += 1
            job.error_code = 'decoder_interrupted'
            job.lease_until = None
            job.available_at = timezone.now() + timedelta(seconds=30)
            if job.attempts >= 3:
                photo.status = Photo.Status.FAILED
                photo.save(update_fields=['status'])
            job.save()


class Command(BaseCommand):
    help = 'Process photos/videos with bounded parallelism; --once drains claimable jobs and exits.'
    def add_arguments(self, parser):
        parser.add_argument('--once', action='store_true')
        parser.add_argument('--job', type=int, help='Internal: decode one claimed job with resource limits')
    def handle(self, *args, **options):
        if options['job']:
            import resource
            video = ProcessingJob.objects.get(pk=options['job']).photo.media_kind == 'video'
            memory = (settings.MEDIA_WORKER_MEMORY_MIB if video else 2048) * 1024**2
            cpu = settings.VIDEO_TIMEOUT_SECONDS if video else 60
            resource.setrlimit(resource.RLIMIT_AS, (memory, memory))
            resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu))
            from memories.services.photos import process_one
            process_one(options['job'])
            return
        active = {}
        previous_handler = signal.getsignal(signal.SIGTERM)
        def stop(*unused):
            raise SystemExit(0)
        signal.signal(signal.SIGTERM, stop)
        try:
            while True:
                close_old_connections()
                for job_id, (process, video, deadline) in list(active.items()):
                    expired = time.monotonic() >= deadline
                    if process.poll() is None and not expired:
                        continue
                    if expired:
                        kill_group(process)
                    crashed = process.returncode != 0
                    # Kill orphaned FFmpeg descendants even after the Python
                    # decoder was killed by an OOM/CPU limit.
                    kill_group(process)
                    del active[job_id]
                    if crashed:
                        record_crash(job_id)
                        self.stderr.write(f'Media job {job_id}: decoder interrupted; retry bounded to three attempts.')
                while len(active) < settings.MEDIA_PARALLEL_JOBS:
                    if settings.MEDIA_PARALLEL_JOBS == 1:
                        kinds = None
                    else:
                        photos = sum(not value[1] for value in active.values())
                        videos = sum(value[1] for value in active.values())
                        photo_slots = settings.MEDIA_PARALLEL_JOBS - 1
                        kinds = (['photo'] if photos < photo_slots else []) + (['video'] if videos < 1 else [])
                        if not kinds:
                            break
                    job = claim_job(kinds)
                    if job is None:
                        break
                    video = job.photo.media_kind == 'video'
                    try:
                        process = subprocess.Popen([sys.executable, str(settings.BASE_DIR / 'manage.py'),
                            'process_photos', '--job', str(job.pk)], stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, start_new_session=True)
                    except OSError:
                        record_crash(job.pk)
                        continue
                    timeout = settings.VIDEO_TIMEOUT_SECONDS + 120 if video else 90
                    active[job.pk] = (process, video, time.monotonic() + timeout)
                if options['once'] and not active:
                    return
                time.sleep(0.25 if active else 2)
        finally:
            for process, _, _ in active.values():
                kill_group(process)
            signal.signal(signal.SIGTERM, previous_handler)
