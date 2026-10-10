import hashlib
import io
import json
import tempfile
import uuid
from datetime import date
from pathlib import Path
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.utils import timezone
from PIL import Image
from memories.models import Photo, ProcessingJob
from memories.services.photos import process_one, capture_date, gps_coordinates, storage_path


def picture(format='JPEG', exif=None):
    output = io.BytesIO()
    image = Image.new('RGB', (80, 40), (120, 160, 110))
    image.save(output, format=format, **({'exif': exif} if exif else {}))
    return output.getvalue()


@override_settings(SECURE_SSL_REDIRECT=False, ALLOWED_HOSTS=['testserver'], PHOTO_FREE_RESERVE=0)
class PhotoTests(TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.settings_override = override_settings(PHOTO_ROOT=Path(self.temp.name))
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.user = get_user_model().objects.create_user('photo-member')
        self.other = get_user_model().objects.create_user('partner')
        self.client = Client(enforce_csrf_checks=True)
        self.client.force_login(self.user)
        self.token = self.client.get('/api/session/').json()['csrfToken']
    def upload(self, data=None, key=None, **headers):
        return self.client.post('/api/photos/upload/', data if data is not None else picture(), content_type='application/octet-stream', HTTP_X_CSRFTOKEN=self.token, HTTP_IDEMPOTENCY_KEY=str(key or uuid.uuid4()), HTTP_X_FILENAME='holiday.jpg', **headers)
    def ready(self, data=None):
        response = self.upload(data)
        self.assertEqual(response.status_code, 202)
        self.assertTrue(process_one())
        return Photo.objects.get(pk=response.json()['id'])
    def test_preserve_original_and_generate_private_derivatives(self):
        data = picture()
        photo = self.ready(data)
        self.assertEqual(photo.status, 'ready')
        self.assertEqual(storage_path(photo.original_key).read_bytes(), data)
        self.assertEqual(photo.sha256, hashlib.sha256(data).hexdigest())
        with Image.open(storage_path(photo.thumbnail_key)) as thumb:
            self.assertEqual(thumb.size, (80, 40))
            self.assertFalse(thumb.getexif())
        response = self.client.get(f'/api/photos/{photo.id}/original/')
        self.assertIn('attachment', response['Content-Disposition'])
        self.assertEqual(b''.join(response.streaming_content), data)
        self.assertIn('no-store', response['Cache-Control'])
    def test_missing_exif_falls_back_to_upload_calendar_date(self):
        with override_settings(TIME_ZONE='Pacific/Kiritimati'):
            photo = self.ready()
            self.assertEqual(photo.display_date, timezone.localdate(photo.uploaded_at))
            self.assertEqual(photo.date_source, 'upload')
            self.assertIsNone(photo.taken_at)
    def test_exif_original_date_and_orientation(self):
        exif = Image.Exif()
        exif[274] = 6
        exif[271] = 'Example camera'
        exif[34665] = {36867:'2020:12:31 23:30:00',36881:'-05:00',37521:'123'}
        photo = self.ready(picture(exif=exif))
        self.assertEqual(photo.display_date, date(2020,12,31))
        self.assertEqual(photo.taken_at.isoformat(), '2021-01-01T04:30:00.123000+00:00')
        self.assertEqual(photo.camera_make,'Example camera')
        self.assertEqual(photo.orientation,6)
        with Image.open(storage_path(photo.preview_key)) as preview:
            self.assertEqual(preview.size,(40,80))
            self.assertFalse(preview.getexif())
    def test_offset_missing_does_not_invent_utc(self):
        exif = Image.Exif(); exif[36867] = '2021:01:02 03:04:05'
        self.assertNotIn('taken_at', capture_date(exif))
        self.assertEqual(capture_date(exif)['display_date'],date(2021,1,2))
    def test_malformed_exif_falls_back(self):
        exif = Image.Exif(); exif[36867] = 'not a date'
        self.assertEqual(capture_date(exif), {})
    def test_gps_coordinates_and_invalid_values(self):
        exif = Image.Exif(); exif[34853] = {1:'S',2:(33,30,0),3:'E',4:(151,12,0)}
        with Image.open(io.BytesIO(picture(exif=exif))) as source:
            self.assertEqual(gps_coordinates(source.getexif()),{'latitude':-33.5,'longitude':151.2})
        exif[34853] = {1:'N',2:(333,0,0),3:'E',4:(151,0,0)}
        with Image.open(io.BytesIO(picture(exif=exif))) as source:
            self.assertIsNone(gps_coordinates(source.getexif())['latitude'])
    def test_png_webp_and_heic_decode(self):
        for format in ['PNG','WEBP','HEIF']:
            with self.subTest(format=format):
                photo = self.ready(picture(format))
                self.assertEqual(photo.status,'ready')
    def test_svg_disguised_as_jpeg_fails_closed(self):
        photo = self.ready(b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>')
        self.assertEqual(photo.status,'failed')
        self.assertTrue(storage_path(photo.original_key).exists())
        self.assertEqual(self.client.get(f'/api/photos/{photo.id}/original/').status_code,404)
        self.assertEqual(self.client.get('/api/photos/').json()['photos'],[])
    def test_animation_rejected(self):
        output=io.BytesIO()
        Image.new('RGB',(10,10),'red').save(output,format='WEBP',save_all=True,append_images=[Image.new('RGB',(10,10),'blue')],duration=100,loop=0)
        self.assertEqual(self.ready(output.getvalue()).status,'failed')
    def test_decoded_pixel_limit(self):
        with patch.object(Image,'MAX_IMAGE_PIXELS',100):
            self.assertEqual(self.ready().status,'failed')
    def test_upload_requires_auth_and_csrf(self):
        self.assertEqual(self.client.post('/api/photos/upload/',b'test',content_type='application/octet-stream').status_code,403)
        self.client.logout()
        self.token=self.client.get('/api/session/').json()['csrfToken']
        self.assertEqual(self.upload().status_code,401)
        self.assertEqual(self.client.get('/api/photos/').status_code,401)
        self.assertEqual(self.client.get('/api/photos/uploads/').status_code,401)
    def test_media_requires_auth_and_excludes_trash(self):
        photo=self.ready()
        self.client.force_login(self.other)
        response=self.client.get(f'/api/photos/{photo.id}/thumbnail/')
        self.assertEqual(response.status_code,200)
        b''.join(response.streaming_content)
        photo.trashed_at=timezone.now();photo.save()
        self.assertEqual(self.client.get(f'/api/photos/{photo.id}/preview/').status_code,404)
        self.client.logout()
        self.assertEqual(self.client.get(f'/api/photos/{photo.id}/thumbnail/').status_code,401)
    def test_byte_limit_and_low_disk(self):
        with override_settings(UPLOAD_MAX_BYTES=10):
            self.assertEqual(self.upload().status_code,413)
        with patch('memories.services.photos.shutil.disk_usage') as usage:
            usage.return_value.free=0
            self.assertEqual(self.upload().status_code,507)
        self.assertEqual(Photo.objects.count(),0)
    def test_repeated_identifier_does_not_duplicate_original(self):
        key=uuid.uuid4()
        self.assertEqual(self.upload(key=key).status_code,202)
        self.assertEqual(self.upload(key=key).status_code,202)
        self.assertEqual(Photo.objects.count(),1)
        self.assertEqual(ProcessingJob.objects.count(),1)
        self.assertEqual(self.upload(b'different',key=key).status_code,400)
    def test_other_user_cannot_reuse_identifier(self):
        key=uuid.uuid4();self.upload(key=key)
        self.client.force_login(self.other)
        self.token=self.client.get('/api/session/').json()['csrfToken']
        self.assertEqual(self.upload(key=key).status_code,400)
        self.assertEqual(self.client.get('/api/photos/uploads/').json()['uploads'],[])
    def test_edit_date_caption_without_modifying_exif_or_original(self):
        photo=self.ready();before=storage_path(photo.original_key).read_bytes()
        response=self.client.post(f'/api/photos/{photo.id}/edit/', json.dumps({'caption':'Our first trip','date':'2019-06-01'}),content_type='application/json',HTTP_X_CSRFTOKEN=self.token)
        self.assertEqual(response.status_code,200)
        photo.refresh_from_db();self.assertEqual(photo.date_source,'manual')
        self.assertEqual(photo.caption,'Our first trip')
        self.assertEqual(storage_path(photo.original_key).read_bytes(),before)
    def test_invalid_edit_and_csrf_rejected(self):
        photo=self.ready()
        self.assertEqual(self.client.post(f'/api/photos/{photo.id}/edit/', '{}',content_type='application/json').status_code,403)
        self.assertEqual(self.client.post(f'/api/photos/{photo.id}/edit/', json.dumps({'caption':'x','date':'bad'}),content_type='application/json',HTTP_X_CSRFTOKEN=self.token).status_code,400)
    def test_database_failure_keeps_original_and_retry_recovers(self):
        key=uuid.uuid4()
        with patch.object(ProcessingJob.objects,'create',side_effect=RuntimeError('interrupted')):
            with self.assertRaises(RuntimeError):self.upload(key=key)
        self.assertEqual(Photo.objects.count(),0)
        self.assertEqual(len(list(Path(self.temp.name).glob('originals/*/*'))),1)
        self.assertEqual(self.upload(key=key).status_code,202)
        self.assertTrue(process_one())
    def test_worker_failure_retries_and_then_fails_without_losing_original(self):
        response=self.upload();job=ProcessingJob.objects.get(photo_id=response.json()['id'])
        with patch('memories.services.photos.process',side_effect=OSError('disk full')):
            for _ in range(3):
                job.available_at=timezone.now();job.save()
                self.assertTrue(process_one());job.refresh_from_db()
        job.photo.refresh_from_db()
        self.assertEqual(job.attempts,3);self.assertEqual(job.photo.status,'failed')
        self.assertTrue(storage_path(job.photo.original_key).exists())
    def test_interrupted_worker_rolls_back_and_can_resume(self):
        self.upload()
        with patch('memories.services.photos.process',side_effect=RuntimeError('worker died')):
            with self.assertRaises(RuntimeError):process_one()
        self.assertEqual(Photo.objects.get().status,'pending')
        self.assertTrue(process_one());self.assertEqual(Photo.objects.get().status,'ready')
    def test_pagination_and_bad_cursor(self):
        Photo.objects.bulk_create([Photo(original_filename=f'{n}.jpg',original_key=f'originals/{n}',sha256='a'*64,byte_size=10,mime_type='image/jpeg',uploaded_by=self.user,display_date=date(2020,1,1),date_source='upload',status='ready') for n in range(51)])
        page=self.client.get('/api/photos/').json();self.assertEqual(len(page['photos']),48)
        second=self.client.get('/api/photos/',{'cursor':page['next']}).json()
        self.assertEqual(len(second['photos']),3)
        self.assertFalse(set(p['id'] for p in page['photos']) & set(p['id'] for p in second['photos']))
        self.assertEqual(self.client.get('/api/photos/',{'cursor':'tampered'}).status_code,400)
    def test_path_traversal_rejected(self):
        with self.assertRaises(ValueError):storage_path('../private')

    def test_all_eight_exif_orientations(self):
        for orientation in range(1,9):
            with self.subTest(orientation=orientation):
                exif=Image.Exif();exif[274]=orientation
                photo=self.ready(picture(exif=exif))
                with Image.open(storage_path(photo.preview_key)) as preview:
                    self.assertEqual(preview.size,(40,80) if orientation >= 5 else (80,40))
    def test_stream_limit_even_without_declared_length(self):
        from memories.services.photos import receive, InvalidImage
        from types import SimpleNamespace
        stream=io.BytesIO(b'x'*20)
        with override_settings(UPLOAD_MAX_BYTES=10):
            with self.assertRaises(InvalidImage):
                receive(SimpleNamespace(read=stream.read,user=self.user),uuid.uuid4(),'large.jpg')
        self.assertEqual(Photo.objects.count(),0)
        self.assertEqual(list(Path(self.temp.name).glob('staging/*')),[])
    def test_received_gps_is_not_in_preview(self):
        exif=Image.Exif();exif[34853]={1:'N',2:(51,30,0),3:'W',4:(0,7,0)}
        photo=self.ready(picture(exif=exif))
        self.assertEqual(float(photo.latitude),51.5)
        with Image.open(storage_path(photo.preview_key)) as preview:
            self.assertFalse(preview.getexif())

    def test_retry_command_preserves_failed_original(self):
        from django.core.management import call_command
        photo=self.ready(b'invalid image')
        before=storage_path(photo.original_key).read_bytes()
        call_command('retry_photo',str(photo.id),stdout=io.StringIO())
        photo.refresh_from_db()
        self.assertEqual(photo.status,'pending')
        self.assertEqual(photo.processingjob.attempts,0)
        self.assertEqual(storage_path(photo.original_key).read_bytes(),before)
    def test_reconciliation_reports_orphans_without_deleting(self):
        from django.core.management import call_command
        self.ready()
        orphan=storage_path('originals/ab/unreferenced')
        orphan.parent.mkdir(parents=True,exist_ok=True);orphan.write_bytes(b'keep this')
        output=io.StringIO();call_command('check_photo_storage',stdout=output)
        self.assertIn('1 unreferenced originals',output.getvalue())
        self.assertTrue(orphan.exists())

    def test_iphone_mpo_uses_primary_image_and_preserves_whole_original(self):
        output = io.BytesIO()
        exif = Image.Exif()
        exif[274] = 6
        exif[34665] = {36867: '2022:03:04 12:30:00'}
        # Deliberately different auxiliary dimensions/color detect wrong-frame decoding.
        Image.new('RGB', (80, 40), 'red').save(
            output, format='MPO', save_all=True,
            append_images=[Image.new('RGB', (20, 10), 'blue')], exif=exif)
        data = output.getvalue()
        with Image.open(io.BytesIO(data)) as source:
            self.assertEqual(source.format, 'MPO')
            self.assertEqual(source.n_frames, 2)
        photo = self.ready(data)
        self.assertEqual(photo.status, 'ready')
        self.assertEqual(photo.mime_type, 'image/jpeg')
        self.assertEqual((photo.width, photo.height), (80, 40))
        self.assertEqual(photo.display_date, date(2022, 3, 4))
        self.assertEqual(storage_path(photo.original_key).read_bytes(), data)
        self.assertEqual(photo.sha256, hashlib.sha256(data).hexdigest())
        with Image.open(storage_path(photo.preview_key)) as preview:
            self.assertEqual(preview.size, (40, 80))
            red, green, blue = preview.convert('RGB').getpixel((10, 10))
            self.assertGreater(red, 200)
            self.assertLess(blue, 40)
            self.assertFalse(preview.getexif())

    def test_processing_status_distinguishes_failure_reasons_without_private_paths(self):
        photo = self.ready(b'not a photo')
        self.assertEqual(photo.processingjob.error_code, 'invalid_image')
        response = self.client.get('/api/photos/uploads/').json()['uploads'][0]
        self.assertIn('damaged', response['message'])
        self.assertNotIn(str(self.temp.name), response['message'])
        photo.processingjob.error_code = 'raw private exception text'
        photo.processingjob.save()
        response = self.client.get('/api/photos/uploads/').json()['uploads'][0]
        self.assertNotIn('raw private', response['message'])
    def test_pixel_limit_has_an_actionable_processing_reason(self):
        with patch.object(Image, 'MAX_IMAGE_PIXELS', 100):
            photo = self.ready()
        self.assertEqual(photo.processingjob.error_code, 'image_too_large')
        self.assertIn('50-megapixel', self.client.get('/api/photos/uploads/').json()['uploads'][0]['message'])
    def test_exif_boundary_offset_does_not_crash_processing(self):
        exif = Image.Exif()
        exif[36867] = '0001:01:01 00:00:00'
        exif[36881] = '+14:00'
        result = capture_date(exif)
        self.assertEqual(result['display_date'], date(1, 1, 1))
        self.assertNotIn('taken_at', result)
    def test_missing_original_is_reported_without_claiming_it_is_retained(self):
        response = self.upload()
        photo = Photo.objects.get(pk=response.json()['id'])
        storage_path(photo.original_key).unlink()
        self.assertTrue(process_one())
        photo.refresh_from_db()
        self.assertEqual(photo.status, 'failed')
        self.assertEqual(photo.processingjob.error_code, 'missing_original')
        self.assertNotIn('retained', self.client.get('/api/photos/uploads/').json()['uploads'][0]['message'])
