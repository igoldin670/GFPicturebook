"""v1.1 date updates and synthetic capture metadata, without real media/drives."""
import hashlib
import io
import json
import tempfile
import uuid
from datetime import date, datetime, timezone as tz
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, Client, override_settings
from django.utils import timezone
from memories.models import Photo
from memories.services.photos import process_image, capture_date
from memories.services.metadata import image_capture, video_capture, apply_capture


@override_settings(SECURE_SSL_REDIRECT=False, ALLOWED_HOSTS=['testserver'])
class BulkDateTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('bulk-member')
        self.partner = get_user_model().objects.create_user('bulk-partner')
        self.client = Client(enforce_csrf_checks=True)
        self.client.force_login(self.user)
        self.token = self.client.get('/api/session/').json()['csrfToken']

    def memory(self, **fields):
        return Photo.objects.create(original_filename='a memory.jpg', original_key=f'original/{uuid.uuid4()}',
            sha256='1'*64, byte_size=100, mime_type='image/jpeg', uploaded_by=self.partner,
            display_date=date(2026,10,1), date_source='upload', caption='Keep this caption',
            status=fields.pop('status', 'ready'), **fields)

    def send(self, ids, calendar='2024-02-29', **headers):
        return self.client.post('/api/photos/bulk-date/', json.dumps({'ids':ids,'date':calendar}),
            content_type='application/json', HTTP_X_CSRFTOKEN=self.token, **headers)

    def test_shared_members_can_atomically_edit_mixed_media_and_preserve_original_facts(self):
        photos = [self.memory(taken_local='2020-01-01T23:00:00'), self.memory(media_kind='video')]
        before = [(p.original_key,p.sha256,p.caption,p.taken_local) for p in photos]
        response = self.send([str(p.pk) for p in photos])
        self.assertEqual(response.json(), {'updated':2,'date':'2024-02-29'})
        for i,p in enumerate(photos):
            p.refresh_from_db()
            self.assertEqual((p.original_key,p.sha256,p.caption,p.taken_local), before[i])
            self.assertEqual(p.display_date, date(2024,2,29))
            self.assertEqual(p.date_source,'manual')
        self.assertEqual(self.client.get('/api/photos/months/').json()['months'],[{'month':'2024-02','count':2}])

    def test_matching_date_is_manual_and_duplicate_ids_update_once(self):
        p = self.memory()
        self.assertEqual(self.send([str(p.pk),str(p.pk)],'2026-10-01').json()['updated'],1)
        p.refresh_from_db(); self.assertEqual(p.date_source,'manual')

    def test_unavailable_selection_changes_nothing(self):
        p = self.memory()
        bad = [str(uuid.uuid4()), str(self.memory(status='pending').pk), str(self.memory(trashed_at=timezone.now()).pk)]
        for identifier in bad:
            self.assertEqual(self.send([str(p.pk),identifier]).status_code,404)
            p.refresh_from_db(); self.assertEqual(p.date_source,'upload')
            self.assertEqual(p.display_date,date(2026,10,1))

    def test_validation_authentication_csrf_and_no_partial_edits(self):
        p = self.memory()
        for ids, calendar in [([], '2026-01-01'), ([str(p.pk)],'2026-02-30'),([str(p.pk)],'2026-W01-1'),(['bad'],'2026-01-01'),([[]],'2026-01-01'),([3],'2026-01-01'),([str(uuid.uuid4()) for _ in range(501)],'2026-01-01')]:
            self.assertEqual(self.send(ids,calendar).status_code,400)
        self.assertEqual(self.client.post('/api/photos/bulk-date/',json.dumps({'ids':[str(p.pk)],'date':'2026-01-01'}),content_type='application/json').status_code,403)
        self.client.logout();self.token=self.client.get('/api/session/').json()['csrfToken'];self.assertEqual(self.send([str(p.pk)]).status_code,401)
        p.refresh_from_db();self.assertEqual(p.date_source,'upload')

    def test_full_500_selection_across_gallery_pages(self):
        photos = [self.memory() for _ in range(500)]
        self.assertIsNotNone(self.client.get('/api/photos/').json()['next'])
        self.assertEqual(self.send([str(p.pk) for p in photos]).json()['updated'],500)
        self.assertEqual(Photo.objects.filter(display_date='2024-02-29',date_source='manual').count(),500)

    def test_database_failure_rolls_back_batch(self):
        p = self.memory()
        with patch('django.db.models.query.QuerySet.update',side_effect=RuntimeError('simulated failure')):
            with self.assertRaises(RuntimeError):self.send([str(p.pk)])
        p.refresh_from_db();self.assertEqual(p.date_source,'upload')


@override_settings(PHOTO_FREE_RESERVE=0)
class CaptureMetadataTests(TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.settings_override = override_settings(PHOTO_ROOT=self.root, STORAGE_DRIVES=[])
        self.settings_override.enable();self.addCleanup(self.settings_override.disable)
        self.user = get_user_model().objects.create_user('capture-member')

    def memory(self, data, source='upload'):
        key=f'originals/{uuid.uuid4()}'
        (self.root/key).parent.mkdir(parents=True,exist_ok=True);(self.root/key).write_bytes(data)
        return Photo.objects.create(original_filename='synthetic-android.jpg',original_key=key,sha256=hashlib.sha256(data).hexdigest(),byte_size=len(data),mime_type='image/jpeg',uploaded_by=self.user,display_date='2026-10-01',date_source=source,status='ready')

    def jpeg(self, exif=None, xmp=None, format='JPEG'):
        output=io.BytesIO();Image.new('RGB',(32,24),'pink').save(output,format,**({'exif':exif} if exif else {}),**({'xmp':xmp} if xmp else {}));return output.getvalue()

    def test_nested_exif_offsets_and_null_terminated_iso_dates(self):
        exif=Image.Exif();exif[34665]={36867:'2020:12:31 23:30:00',36881:'-05:00'}
        with Image.open(io.BytesIO(self.jpeg(exif))) as image:
            result=image_capture(image)
        self.assertEqual(result['display_date'],date(2020,12,31))
        self.assertEqual(result['taken_at'],datetime(2021,1,1,4,30,tzinfo=tz.utc))
        result=capture_date({36867:b'2024-02-29T23:15:02+05:30\x00'})
        self.assertEqual(result['display_date'],date(2024,2,29))
        self.assertEqual(result['taken_offset_minutes'],330)
        self.assertEqual(capture_date({36867:'2024-02-29T23:15:02',36881:'+05:30'})['taken_offset_minutes'],330)

    def test_xmp_fallback_and_exif_precedence(self):
        xmp=b'<x:xmpmeta xmlns:x="adobe:ns:meta/" xmlns:e="http://ns.adobe.com/exif/1.0/"><e:DateTimeOriginal>2023-04-05T23:00:00-04:00</e:DateTimeOriginal></x:xmpmeta>'
        with Image.open(io.BytesIO(self.jpeg(xmp=xmp))) as image:
            self.assertEqual(image_capture(image)['display_date'],date(2023,4,5))
        exif=Image.Exif();exif[36867]='2022:03:04 12:00:00'
        with Image.open(io.BytesIO(self.jpeg(exif,xmp))) as image:
            self.assertEqual(image_capture(image)['display_date'],date(2022,3,4))
        self.assertEqual(capture_date({36867:'bad',306:'2022:03:04 12:00:00'}),{})

    def test_supported_heic_capture_and_stripped_metadata(self):
        exif=Image.Exif();exif[34665]={36867:'2021:06:07 08:09:10'}
        with Image.open(io.BytesIO(self.jpeg(exif,format='HEIF'))) as image:
            self.assertEqual(image_capture(image)['display_date'],date(2021,6,7))
        with Image.open(io.BytesIO(self.jpeg())) as image:self.assertEqual(image_capture(image),{})

    def test_video_creation_date_and_manual_preservation(self):
        capture=video_capture({'streams':[{'codec_type':'video','tags':{'creation_time':'2021-12-31T23:30:00-05:00'}}]})
        self.assertEqual(capture['display_date'],date(2021,12,31))
        p=self.memory(self.jpeg(),'manual');apply_capture(p,capture)
        self.assertEqual(p.display_date,'2026-10-01');self.assertEqual(p.date_source,'manual')
        self.assertEqual(video_capture({'format':{'tags':{'date':'2020-01-01'}}}),{})

    def test_reprocessing_keeps_manual_date_and_original_bytes(self):
        exif=Image.Exif();exif[36867]='2020:01:02 03:04:05'
        data=self.jpeg(exif);p=self.memory(data,'manual')
        with (self.root/p.original_key).open('rb') as source:process_image(p,source)
        p.refresh_from_db();self.assertEqual(p.display_date,date(2026,10,1));self.assertEqual(p.date_source,'manual')
        self.assertEqual(p.taken_local,'2020-01-02T03:04:05')
        self.assertEqual((self.root/p.original_key).read_bytes(),data)

    def test_reread_command_defaults_dry_run_and_skips_manual_records(self):
        exif=Image.Exif();exif[36867]='2020:01:02 03:04:05'
        data=self.jpeg(exif);p=self.memory(data);manual=self.memory(data,'manual')
        output=io.StringIO();call_command('reread_capture_dates',str(p.pk),str(manual.pk),stdout=output)
        self.assertIn('dry-run 2020-01-02',output.getvalue())
        p.refresh_from_db();self.assertEqual(p.date_source,'upload')
        call_command('reread_capture_dates',str(p.pk),str(manual.pk),apply=True,stdout=io.StringIO())
        p.refresh_from_db();manual.refresh_from_db();self.assertEqual(p.display_date,date(2020,1,2));self.assertEqual(manual.date_source,'manual')
        self.assertEqual((self.root/p.original_key).read_bytes(),data)


    def test_reread_missing_dates_stays_null_until_explicit_apply(self):
        exif=Image.Exif();exif[36867]='2020:01:02 03:04:05'
        data=self.jpeg(exif);p=self.memory(data,'missing')
        Photo.objects.filter(pk=p.pk).update(display_date=None)
        call_command('reread_capture_dates',str(p.pk),stdout=io.StringIO())
        p.refresh_from_db();self.assertIsNone(p.display_date);self.assertEqual(p.date_source,'missing')
        call_command('reread_capture_dates',str(p.pk),apply=True,stdout=io.StringIO())
        p.refresh_from_db();self.assertEqual(p.display_date,date(2020,1,2));self.assertEqual(p.date_source,'exif')
        self.assertEqual((self.root/p.original_key).read_bytes(),data)


    def test_recovery_reports_corrupted_sources_and_preserves_dates(self):
        from django.core.management.base import CommandError
        p=self.memory(self.jpeg());(self.root/p.original_key).write_bytes(b'corrupted synthetic original')
        with self.assertRaises(CommandError):
            call_command('reread_capture_dates',str(p.pk),apply=True,stdout=io.StringIO(),stderr=io.StringIO())
        p.refresh_from_db();self.assertEqual(p.date_source,'upload')

    def test_recovery_rechecks_manual_override_after_inspection(self):
        p=self.memory(self.jpeg())
        def capture(_):
            Photo.objects.filter(pk=p.pk).update(date_source='manual',display_date='2022-01-01')
            return {'display_date':date(2020,1,1),'date_source':'exif'}
        with patch('memories.management.commands.reread_capture_dates.image_capture',side_effect=capture):
            call_command('reread_capture_dates',str(p.pk),apply=True,stdout=io.StringIO())
        p.refresh_from_db();self.assertEqual(p.date_source,'manual');self.assertEqual(p.display_date,date(2022,1,1))


from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless
from django.db import connection, close_old_connections
from django.test import TransactionTestCase


@skipUnless(connection.vendor == 'postgresql', 'PostgreSQL row-lock concurrency check')
@override_settings(SECURE_SSL_REDIRECT=False, ALLOWED_HOSTS=['testserver'])
class BulkDateConcurrencyTests(TransactionTestCase):
    def test_overlapping_bulk_edits_finish_as_whole_batches(self):
        user=get_user_model().objects.create_user('concurrent-bulk')
        photos=[Photo.objects.create(original_filename='memory.jpg',original_key=f'original/{uuid.uuid4()}',sha256='1'*64,
            byte_size=1,mime_type='image/jpeg',uploaded_by=user,display_date='2026-10-01',date_source='upload',status='ready') for _ in range(2)]
        clients=[Client(),Client()]
        for client in clients:client.force_login(user)
        barrier=Barrier(2)
        def send(item):
            close_old_connections()
            try:
                client,calendar=item;barrier.wait(timeout=10)
                return client.post('/api/photos/bulk-date/',{'ids':[str(p.pk) for p in photos],'date':calendar},content_type='application/json').status_code
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(list(pool.map(send,zip(clients,['2024-02-29','2025-01-01']))),[200,200])
        dates=set(Photo.objects.filter(pk__in=[p.pk for p in photos]).values_list('display_date',flat=True))
        self.assertEqual(len(dates),1)
        self.assertTrue(dates <= {date(2024,2,29),date(2025,1,1)})
