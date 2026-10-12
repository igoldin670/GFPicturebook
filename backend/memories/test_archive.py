"""All disconnect/full/corruption/crash tests operate only in TemporaryDirectory."""
import hashlib
import io
import tempfile
import uuid
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.utils import timezone
from PIL import Image
from memories.models import Photo, StoredAsset, FileReplica, StorageJob, StorageDrive
from memories.services.archive import inventory, run_one, verified_source, write_replica
from memories.services.drives import configuration, refresh_drives
from memories.services.photos import process_one, storage_path


@override_settings(SECURE_SSL_REDIRECT=False, ALLOWED_HOSTS=['testserver'], PHOTO_FREE_RESERVE=0,
                   STORAGE_FREE_RESERVE=0, STORAGE_SIMULATED=True)
class ArchiveTests(TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.entries = []
        for index in range(4):
            root = self.root / f'drive-{index}'
            root.mkdir()
            (root / '.archive-test-id').write_text(f'uuid-{index}')
            self.entries.append({'uuid': f'uuid-{index}', 'label': f'Drive {index}', 'path': str(root)})
        self.override = override_settings(PHOTO_ROOT=self.root / 'legacy', STORAGE_DRIVES=self.entries)
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.user = get_user_model().objects.create_user('member')
        self.admin = get_user_model().objects.create_user('admin', is_staff=True)
        self.client = Client(enforce_csrf_checks=True)
        self.client.force_login(self.user)
        self.token = self.client.get('/api/session/').json()['csrfToken']
        out = io.BytesIO()
        Image.new('RGB', (80, 40), 'pink').save(out, 'JPEG')
        self.data = out.getvalue()
    def upload(self, direct=False):
        with override_settings(STORAGE_DRIVES=self.entries if direct else []):
            return self._upload()
    def _upload(self):
        response = self.client.post('/api/photos/upload/', self.data, content_type='application/octet-stream',
            HTTP_X_CSRFTOKEN=self.token, HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()), HTTP_X_FILENAME='memory.jpg')
        self.assertEqual(response.status_code, 202)
        self.assertTrue(process_one())
        return Photo.objects.get(pk=response.json()['id'])
    def replicate(self, photo):
        StorageJob.objects.filter(photo=photo).update(available_at=timezone.now())
        self.assertTrue(run_one(photo.storage_job.pk))
        return photo.assets.get(variant='original')
    def path(self, replica):
        return Path(replica.drive.path) / 'album-archive' / replica.asset.key
    def healthy(self, asset):
        return list(asset.replicas.select_related('drive', 'asset').filter(state='verified'))
    def test_photo_has_two_verified_copies_and_all_derivatives(self):
        photo = self.upload()
        asset = self.replicate(photo)
        copies = self.healthy(asset)
        self.assertEqual(len(copies), 2)
        self.assertEqual(len({r.drive.physical_id for r in copies}), 2)
        for replica in copies:
            self.assertEqual(self.path(replica).read_bytes(), self.data)
            self.assertEqual(hashlib.sha256(self.path(replica).read_bytes()).hexdigest(), asset.sha256)
        self.assertEqual(set(photo.assets.values_list('variant', flat=True)), {'original','thumbnail','preview'})
        self.assertFalse(photo.assets.exclude(protection='protected').exists())
    def test_offline_drive_failover_and_automatic_rebuild(self):
        photo = self.upload(); asset = self.replicate(photo)
        dead, survivor = self.healthy(asset)
        (Path(dead.drive.path) / '.archive-test-id').unlink()
        storage_path(photo.original_key).unlink()  # Exercise surviving archive copy.
        inventory()
        asset.refresh_from_db(); self.assertEqual(asset.protection, 'degraded')
        response = self.client.get(f'/api/photos/{photo.id}/original/')
        self.assertEqual(b''.join(response.streaming_content), self.data)
        asset = self.replicate(photo)
        self.assertEqual(asset.protection, 'protected')
        self.assertEqual(len(self.healthy(asset)), 2)
        self.assertNotIn(dead.drive_id, {r.drive_id for r in self.healthy(asset)})
        self.assertIn(survivor.drive_id, {r.drive_id for r in self.healthy(asset)})
    def test_corrupt_copy_repaired_from_healthy_and_healthy_never_rewritten(self):
        photo = self.upload(); asset = self.replicate(photo)
        damaged, survivor = self.healthy(asset)
        healthy_path = self.path(survivor)
        before = healthy_path.stat().st_mtime_ns
        self.path(damaged).write_bytes(b'corrupted')
        storage_path(photo.original_key).write_bytes(b'also corrupt')
        asset = self.replicate(photo)
        self.assertEqual(asset.protection, 'protected')
        self.assertEqual(healthy_path.stat().st_mtime_ns, before)
        self.assertEqual(self.path(damaged).read_bytes(), self.data)
    def test_all_corrupt_never_accepted_or_propagated(self):
        photo = self.upload(); asset = self.replicate(photo)
        copies = self.healthy(asset)
        for replica in copies:
            self.path(replica).write_bytes(b'corrupt')
        storage_path(photo.original_key).write_bytes(b'corrupt')
        asset = self.replicate(photo)
        self.assertEqual(asset.protection, 'unprotected')
        self.assertEqual(self.healthy(asset), [])
        for replica in copies:
            self.assertEqual(self.path(replica).read_bytes(), b'corrupt')
        self.assertEqual(self.client.get(f'/api/photos/{photo.id}/original/').status_code, 404)
    def test_full_drive_is_skipped(self):
        photo = self.upload()
        real = __import__('shutil').disk_usage
        def usage(path):
            result = real(path)
            if str(path) == self.entries[0]['path']:
                return result._replace(free=0)
            return result
        with patch('memories.services.drives.shutil.disk_usage', side_effect=usage):
            asset = self.replicate(photo)
        self.assertEqual(asset.protection, 'protected')
        self.assertNotIn('uuid-0', {r.drive_id for r in self.healthy(asset)})
    def test_one_available_drive_is_never_fully_protected(self):
        for entry in self.entries[1:]:
            (Path(entry['path']) / '.archive-test-id').unlink()
        photo = self.upload(); asset = self.replicate(photo)
        self.assertEqual(asset.protection, 'degraded')
        self.assertEqual(len(self.healthy(asset)), 1)
        photo.storage_job.refresh_from_db()
        self.assertEqual(photo.storage_job.status, 'retry')
    def test_two_filesystems_on_same_physical_disk_do_not_count_twice(self):
        photo = self.upload()
        from memories.services.drives import identity
        def same(entry):
            dev, _ = identity(entry)
            return dev, 'one-physical-disk'
        with patch('memories.services.drives.identity', side_effect=same):
            asset = self.replicate(photo)
        self.assertEqual(asset.protection, 'degraded')
        self.assertEqual(len(self.healthy(asset)), 1)
    def test_restart_after_publication_before_database_commit_adopts_file(self):
        photo = self.upload()
        calls = []
        def interrupted(asset, drive, source):
            write_replica(asset, drive, source)
            calls.append(drive.uuid)
            raise RuntimeError('worker killed before DB commit')
        with patch('memories.services.archive.write_replica', side_effect=interrupted):
            with self.assertRaises(RuntimeError):
                self.replicate(photo)
        self.assertTrue(calls)
        self.assertFalse(StoredAsset.objects.filter(photo=photo).exists())
        asset = self.replicate(photo)
        self.assertEqual(asset.protection, 'protected')
        self.assertEqual(len(self.healthy(asset)), 2)
    def test_write_failure_leaves_other_drives_usable(self):
        photo = self.upload()
        def failing(asset, drive, source):
            if drive.uuid == 'uuid-0':
                raise OSError('EIO')
            return write_replica(asset, drive, source)
        with patch('memories.services.archive.write_replica', side_effect=failing):
            asset = self.replicate(photo)
        self.assertEqual(asset.protection, 'protected')
        self.assertNotIn('uuid-0', {r.drive_id for r in self.healthy(asset)})
    def test_failed_readback_never_publishes_corrupt_copy(self):
        photo = self.upload()
        from memories.services.archive import verify, IntegrityError
        def fail_parts(source, digest, size):
            if str(source.name).endswith('.part'):
                raise IntegrityError('bad write')
            return verify(source, digest, size)
        with patch('memories.services.archive.verify', side_effect=fail_parts):
            asset = self.replicate(photo)
        self.assertEqual(asset.protection, 'unprotected')
        self.assertFalse(any((Path(e['path']) / 'album-archive' / asset.key).exists() for e in self.entries))
        self.assertEqual(storage_path(photo.original_key).read_bytes(), self.data)
    def test_admin_only_storage_api_dashboard_and_csrf(self):
        photo = self.upload(); self.replicate(photo)
        for path in ['/api/admin/storage/', '/admin/storage/']:
            self.assertEqual(self.client.get(path).status_code, 403)
        self.assertEqual(self.client.post('/admin/storage/check/', HTTP_X_CSRFTOKEN=self.token).status_code,403)
        gallery = self.client.get('/api/photos/').content.decode()
        for field in ['sha256','uuid-0','protection','replicas','physicalId',str(self.root)]:
            self.assertNotIn(field, gallery)
        self.client.force_login(self.admin)
        response = self.client.get('/api/admin/storage/')
        self.assertEqual(response.status_code,200)
        self.assertEqual(len(response.json()['drives']),4)
        self.assertEqual(self.client.get('/admin/storage/').status_code,200)
        self.assertContains(self.client.get('/admin/'), 'Media archive storage dashboard')
        self.assertEqual(self.client.post('/admin/storage/check/').status_code,403)
        self.client.logout()
        self.assertEqual(self.client.get('/api/admin/storage/').status_code,401)
    def test_existing_media_works_before_and_after_gradual_adoption(self):
        photo = self.upload()
        photo.storage_job.delete()
        response = self.client.get(f'/api/photos/{photo.id}/original/')
        self.assertEqual(b''.join(response.streaming_content), self.data)
        inventory()
        self.assertTrue(StorageJob.objects.filter(photo=photo).exists())
        self.replicate(photo)
        self.assertEqual(storage_path(photo.original_key).read_bytes(), self.data)
    def test_unmounted_directories_fail_closed_in_production(self):
        with override_settings(STORAGE_SIMULATED=False):
            self.assertTrue(all(d.status == 'offline' for d in refresh_drives()))
        self.assertFalse(any((Path(e['path']) / 'album-archive').exists() for e in self.entries))
    def test_os_drive_can_be_monitored_but_excluded(self):
        self.entries[0]['excluded'] = True
        photo = self.upload(); asset = self.replicate(photo)
        self.assertEqual(StorageDrive.objects.get(pk='uuid-0').status,'excluded')
        self.assertNotIn('uuid-0', {r.drive_id for r in self.healthy(asset)})
    def test_invalid_duplicate_drive_config_rejected(self):
        from django.core.exceptions import ImproperlyConfigured
        with override_settings(STORAGE_DRIVES=[self.entries[0]]*4):
            with self.assertRaises(ImproperlyConfigured):
                configuration()

    def test_new_upload_writes_primary_to_drive_and_second_in_background(self):
        photo = self.upload(direct=True)
        self.assertFalse(storage_path(photo.original_key).exists())
        asset = photo.assets.get(variant='original')
        self.assertEqual(asset.protection, 'degraded')
        self.assertEqual(len(self.healthy(asset)), 1)
        asset = self.replicate(photo)
        self.assertEqual(asset.protection, 'protected')
        self.assertEqual(len(self.healthy(asset)), 2)
        self.assertFalse(storage_path(photo.original_key).exists())
        response = self.client.get(f'/api/photos/{photo.id}/original/')
        self.assertEqual(b''.join(response.streaming_content), self.data)

    def test_incomplete_upload_is_not_admitted(self):
        from types import SimpleNamespace
        from memories.services.photos import receive, InvalidImage
        stream = io.BytesIO(self.data[:100])
        request = SimpleNamespace(read=stream.read,user=self.user,headers={'Content-Length':str(len(self.data))})
        with self.assertRaises(InvalidImage):
            receive(request,uuid.uuid4(),'partial.jpg')
        self.assertFalse(Photo.objects.exists())
        self.assertFalse(any(list(Path(e['path']).rglob('*.part')) for e in self.entries))

    def test_primary_publication_survives_database_failure_and_safe_retry(self):
        identifier = uuid.uuid4()
        def send():
            return self.client.post('/api/photos/upload/',self.data,content_type='application/octet-stream',
                HTTP_X_CSRFTOKEN=self.token,HTTP_IDEMPOTENCY_KEY=str(identifier),HTTP_X_FILENAME='retry.jpg')
        from memories.models import ProcessingJob
        with patch.object(ProcessingJob.objects,'create',side_effect=RuntimeError('restart')):
            with self.assertRaises(RuntimeError): send()
        self.assertFalse(Photo.objects.exists())
        found = list(self.root.glob('drive-*/album-archive/originals/*/*'))
        self.assertTrue(found)
        self.assertEqual(found[0].read_bytes(),self.data)
        self.assertEqual(send().status_code,202)
        self.assertTrue(process_one())
        asset = self.replicate(Photo.objects.get())
        self.assertEqual(asset.protection,'protected')

    def test_no_online_archive_drive_does_not_fall_back_to_system_disk(self):
        for entry in self.entries:
            (Path(entry['path'])/'.archive-test-id').unlink()
        response = self.client.post('/api/photos/upload/',self.data,content_type='application/octet-stream',
            HTTP_X_CSRFTOKEN=self.token,HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),HTTP_X_FILENAME='memory.jpg')
        self.assertEqual(response.status_code,507)
        self.assertFalse(Photo.objects.exists())
        self.assertFalse((self.root/'legacy'/'originals').exists())

    def test_configurable_queue_capacity_rejects_only_after_limit(self):
        with override_settings(MEDIA_PENDING_LIMIT=1):
            response = self.client.post('/api/photos/upload/',self.data,content_type='application/octet-stream',
                HTTP_X_CSRFTOKEN=self.token,HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),HTTP_X_FILENAME='first.jpg')
            self.assertEqual(response.status_code,202)
            second = self.client.post('/api/photos/upload/',self.data,content_type='application/octet-stream',
                HTTP_X_CSRFTOKEN=self.token,HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),HTTP_X_FILENAME='second.jpg')
            self.assertEqual(second.status_code,400)
        self.assertEqual(Photo.objects.count(),1)

    def test_decoder_claim_is_exclusive_and_recovers_after_expiry(self):
        from memories.management.commands.process_photos import claim_job
        from memories.models import ProcessingJob
        response = self.client.post('/api/photos/upload/',self.data,content_type='application/octet-stream',
            HTTP_X_CSRFTOKEN=self.token,HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),HTTP_X_FILENAME='queued.jpg')
        self.assertEqual(response.status_code,202)
        job = claim_job(['photo'])
        self.assertIsNotNone(job)
        self.assertIsNone(claim_job(['photo']))
        self.assertIsNone(claim_job(['video']))
        ProcessingJob.objects.filter(pk=job.pk).update(lease_until=timezone.now()-timedelta(seconds=1))
        self.assertEqual(claim_job(['photo']).pk,job.pk)

from django.db import connection, close_old_connections, connections
from django.test import TransactionTestCase
from unittest import skipUnless
import threading

@skipUnless(connection.vendor == 'postgresql', 'Real row-lock tests require PostgreSQL')
@override_settings(SECURE_SSL_REDIRECT=False, ALLOWED_HOSTS=['testserver'], PHOTO_FREE_RESERVE=0,
                   STORAGE_FREE_RESERVE=0, STORAGE_SIMULATED=True)
class ArchiveConcurrencyTests(TransactionTestCase):
    setUp = ArchiveTests.setUp
    upload = ArchiveTests.upload
    _upload = ArchiveTests._upload
    def test_two_workers_do_not_publish_conflicting_replicas(self):
        photo = self.upload()
        barrier = threading.Barrier(2)
        errors, results = [], []
        def worker():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                results.append(run_one(photo.storage_job.pk))
            except BaseException as exc:
                errors.append(exc)
            finally:
                connections.close_all()
        threads = [threading.Thread(target=worker) for _ in range(2)]
        for thread in threads: thread.start()
        for thread in threads: thread.join(timeout=15)
        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertEqual(errors, [])
        self.assertIn(True, results)
        asset = photo.assets.get(variant='original')
        self.assertEqual(asset.protection,'protected')
        self.assertEqual(asset.replicas.filter(state='verified').count(),2)
    def test_simultaneous_member_uuid_collision_keeps_first_original(self):
        other = get_user_model().objects.create_user('second-member')
        identifier = str(uuid.uuid4())
        barrier = threading.Barrier(2)
        responses, errors = [], []
        def upload(user):
            close_old_connections()
            try:
                client = Client(enforce_csrf_checks=True)
                client.force_login(user)
                token = client.get('/api/session/').json()['csrfToken']
                barrier.wait(timeout=10)
                response = client.post('/api/photos/upload/',self.data,content_type='application/octet-stream',
                    HTTP_X_CSRFTOKEN=token,HTTP_IDEMPOTENCY_KEY=identifier,HTTP_X_FILENAME='shared.jpg')
                responses.append(response.status_code)
            except BaseException as exc: errors.append(exc)
            finally: connections.close_all()
        threads = [threading.Thread(target=upload,args=(u,)) for u in [self.user, other]]
        for thread in threads: thread.start()
        for thread in threads: thread.join(timeout=15)
        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertEqual(errors,[])
        self.assertEqual(sorted(responses),[202,400])
        self.assertEqual(Photo.objects.count(),1)

    @override_settings(MEDIA_PENDING_LIMIT=1)
    def test_simultaneous_members_cannot_overfill_pending_queue(self):
        other = get_user_model().objects.create_user('queue-member')
        barrier = threading.Barrier(2)
        responses, errors = [], []
        def upload(user):
            close_old_connections()
            try:
                client = Client(enforce_csrf_checks=True)
                client.force_login(user)
                token = client.get('/api/session/').json()['csrfToken']
                barrier.wait(timeout=10)
                response = client.post('/api/photos/upload/',self.data,content_type='application/octet-stream',
                    HTTP_X_CSRFTOKEN=token,HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),HTTP_X_FILENAME='queued.jpg')
                responses.append(response.status_code)
            except BaseException as exc: errors.append(exc)
            finally: connections.close_all()
        threads = [threading.Thread(target=upload,args=(user,)) for user in [self.user,other]]
        for thread in threads: thread.start()
        for thread in threads: thread.join(timeout=15)
        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertEqual(errors,[])
        self.assertEqual(sorted(responses),[202,400])
        self.assertEqual(Photo.objects.filter(status='pending').count(),1)
