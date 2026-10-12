import hashlib
import io
import subprocess
import tempfile
import uuid
from pathlib import Path
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.utils import timezone
from memories.models import Photo, StorageJob
from memories.services.photos import process_one, storage_path
from memories.services.archive import run_one


@override_settings(SECURE_SSL_REDIRECT=False, ALLOWED_HOSTS=['testserver'], PHOTO_FREE_RESERVE=0,
                   STORAGE_FREE_RESERVE=0, STORAGE_SIMULATED=True)
class VideoTests(TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        drives = []
        for n in range(4):
            path = self.root / f'drive{n}'; path.mkdir()
            (path/'.archive-test-id').write_text(f'video-drive-{n}')
            drives.append({'uuid':f'video-drive-{n}', 'path':str(path)})
        self.override = override_settings(PHOTO_ROOT=self.root/'legacy', STORAGE_DRIVES=drives)
        self.override.enable(); self.addCleanup(self.override.disable)
        self.user = get_user_model().objects.create_user('video-member')
        self.client = Client(enforce_csrf_checks=True); self.client.force_login(self.user)
        self.token = self.client.get('/api/session/').json()['csrfToken']
    def video(self, extension='mp4', codec='libx264'):
        path = self.root / f'synthetic.{extension}'
        subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=c=pink:s=64x48:r=10',
            '-t','0.5','-c:v',codec,'-threads','1','-pix_fmt','yuv420p','-y',str(path)], check=True)
        return path.read_bytes()
    def upload(self, data, name='clip.mp4'):
        with override_settings(STORAGE_DRIVES=[]):
            return self._upload(data, name)
    def _upload(self, data, name):
        response = self.client.post('/api/photos/upload/', data, content_type='application/octet-stream',
            HTTP_X_CSRFTOKEN=self.token,HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),HTTP_X_FILENAME=name)
        self.assertEqual(response.status_code,202)
        self.assertTrue(process_one())
        return Photo.objects.get(pk=response.json()['id'])
    def test_all_requested_video_containers_create_compatible_polaroid_assets(self):
        for extension, codec in [('mp4','libx264'),('mov','libx264'),('mkv','ffv1'),('webm','libvpx-vp9'),('avi','mpeg4'),('m4v','mpeg4')]:
            with self.subTest(extension=extension):
                # M4V is an MP4 container for browser workflows, not raw MPEG4.
                if extension == 'm4v':
                    data = self.video('mp4')
                else:
                    data = self.video(extension, codec)
                photo = self.upload(data, f'clip.{extension}')
                self.assertEqual(photo.status,'ready')
                self.assertEqual(photo.media_kind,'video')
                self.assertGreater(photo.duration,0)
                self.assertEqual((photo.width,photo.height),(64,48))
                self.assertEqual(photo.sha256,hashlib.sha256(data).hexdigest())
                self.assertEqual(storage_path(photo.original_key).read_bytes(),data)
                self.assertTrue(storage_path(photo.thumbnail_key).exists())
                self.assertTrue(storage_path(photo.playback_key).exists())
                # Probe the generated MP4 rather than merely checking a PID/file.
                probe = subprocess.run(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=codec_name',
                    '-of','default=nw=1:nk=1',str(storage_path(photo.playback_key))],capture_output=True,check=True)
                self.assertEqual(probe.stdout.strip(),b'h264')
                self.assertTrue(run_one(photo.storage_job.pk))
                self.assertFalse(photo.assets.exclude(protection='protected').exists())
    def test_playback_seeking_download_and_authentication(self):
        original = self.video(); photo = self.upload(original)
        playback = storage_path(photo.playback_key).read_bytes()
        url = f'/api/photos/{photo.id}/stream/'
        for header, start, end in [('bytes=0-99',0,99),('bytes=100-',100,len(playback)-1),('bytes=-40',len(playback)-40,len(playback)-1)]:
            response = self.client.get(url,HTTP_RANGE=header)
            self.assertEqual(response.status_code,206)
            self.assertEqual(response['Accept-Ranges'],'bytes')
            self.assertEqual(response['Content-Range'],f'bytes {start}-{end}/{len(playback)}')
            self.assertEqual(b''.join(response.streaming_content),playback[start:end+1])
        for invalid in ['bytes=999999999-','bytes=0-1,4-5','bytes=-0','broken']:
            self.assertEqual(self.client.get(url,HTTP_RANGE=invalid).status_code,416)
        response = self.client.get(f'/api/photos/{photo.id}/original/')
        self.assertEqual(b''.join(response.streaming_content),original)
        self.assertIn('attachment',response['Content-Disposition'])
        self.client.logout()
        self.assertEqual(self.client.get(url,HTTP_RANGE='bytes=0-10').status_code,401)
    def test_gallery_metadata_contains_no_storage_information(self):
        photo = self.upload(self.video())
        item = self.client.get('/api/photos/').json()['photos'][0]
        self.assertEqual(item['kind'],'video')
        self.assertEqual(item['byteSize'],photo.byte_size)
        self.assertGreater(item['duration'],0)
        self.assertTrue(item['playback'].endswith('/stream/'))
        self.assertNotIn('sha256',item)
    def test_transcoding_can_be_disabled_without_changing_original(self):
        data = self.video('mkv','ffv1')
        with override_settings(VIDEO_TRANSCODE=False):
            photo = self.upload(data,'clip.mkv')
        self.assertEqual(photo.status,'ready')
        self.assertEqual(photo.playback_key,'')
        self.assertEqual(photo.playback_mime,'')
        self.assertEqual(storage_path(photo.original_key).read_bytes(),data)
    def test_video_size_limit_is_enforced(self):
        with override_settings(VIDEO_MAX_BYTES=10):
            response = self.client.post('/api/photos/upload/', b'x'*11, content_type='application/octet-stream',
                HTTP_X_CSRFTOKEN=self.token,HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),HTTP_X_FILENAME='clip.mov')
        self.assertEqual(response.status_code,413)
        self.assertEqual(Photo.objects.count(),0)
    def test_invalid_video_original_is_retained_and_not_playable(self):
        photo = self.upload(b'\x00\x00\x00\x18ftyp' + b'invalid'*10)
        self.assertEqual(photo.status,'failed')
        self.assertTrue(storage_path(photo.original_key).exists())
        self.assertEqual(self.client.get(f'/api/photos/{photo.id}/stream/').status_code,404)

    def test_video_cap_can_be_disabled_without_disabling_shared_ceiling(self):
        data = self.video()
        with override_settings(VIDEO_MAX_BYTES=10):
            response = self.client.post('/api/photos/upload/',data,content_type='application/octet-stream',
                HTTP_X_CSRFTOKEN=self.token,HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),HTTP_X_FILENAME='clip.mp4')
            self.assertEqual(response.status_code,413)
        with override_settings(VIDEO_MAX_BYTES=0):
            photo = self.upload(data)
        self.assertEqual(photo.status,'ready')
        self.assertEqual(storage_path(photo.original_key).read_bytes(),data)
        with override_settings(VIDEO_MAX_BYTES=0,MEDIA_REQUEST_MAX_BYTES=10):
            response = self.client.post('/api/photos/upload/',data,content_type='application/octet-stream',
                HTTP_X_CSRFTOKEN=self.token,HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),HTTP_X_FILENAME='clip.mp4')
            self.assertEqual(response.status_code,413)
