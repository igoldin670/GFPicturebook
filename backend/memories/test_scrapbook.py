"""Nullable dates and server-side filtering, with synthetic records only."""
import importlib
import json
import uuid
from datetime import date
from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase, Client, override_settings
from django.utils import timezone
from memories.models import Photo


@override_settings(SECURE_SSL_REDIRECT=False, ALLOWED_HOSTS=['testserver'])
class ScrapbookTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('scrapbook-member')
        self.client = Client(enforce_csrf_checks=True)
        self.client.force_login(self.user)
        self.token = self.client.get('/api/session/').json()['csrfToken']

    def memory(self, **fields):
        defaults = dict(original_filename='synthetic.jpg', original_key=f'originals/{uuid.uuid4()}',
                        sha256='1'*64, byte_size=123, mime_type='image/jpeg', uploaded_by=self.user,
                        display_date=None, date_source='missing', status='ready')
        defaults.update(fields)
        return Photo.objects.create(**defaults)

    def post(self, url, data):
        return self.client.post(url, json.dumps(data), content_type='application/json', HTTP_X_CSRFTOKEN=self.token)

    def test_null_dates_counted_but_not_chaptered(self):
        p = self.memory(); v = self.memory(media_kind='video')
        dated = self.memory(display_date='2020-05-03', date_source='manual')
        self.memory(status='pending'); self.memory(trashed_at=timezone.now())
        self.assertEqual(self.client.get('/api/photos/').json()['count'], 1)
        self.assertEqual(self.client.get('/api/photos/months/').json()['months'], [{'month':'2020-05','count':1}])
        data = self.client.get('/api/photos/?undated=1').json()
        self.assertEqual(data['count'], 2)
        self.assertEqual({x['id'] for x in data['photos']}, {str(p.pk),str(v.pk)})
        self.assertTrue(all(x['date'] is None and x['dateSource'] == 'missing' for x in data['photos']))
        summary = self.client.get('/api/summary/').json()
        self.assertEqual((summary['photos'],summary['undatedCount']), (3,2))

    def test_filter_applies_to_results_and_chapters(self):
        self.memory(); self.memory(media_kind='video')
        self.memory(display_date='2020-01-02', date_source='exif')
        self.memory(media_kind='video', display_date='2021-02-03',date_source='file')
        for kind, month in [('photo','2020-01'), ('video','2021-02')]:
            data = self.client.get(f'/api/photos/?kind={kind}').json()
            self.assertEqual(data['count'],1); self.assertEqual(data['photos'][0]['kind'],kind)
            self.assertEqual(self.client.get(f'/api/photos/months/?kind={kind}').json()['months'],[{'month':month,'count':1}])
            self.assertEqual(self.client.get(f'/api/photos/?undated=1&kind={kind}').json()['count'],1)

    def test_undated_pagination_and_cursor_isolation(self):
        for _ in range(51): self.memory()
        first=self.client.get('/api/photos/?undated=1').json()
        second=self.client.get('/api/photos/',{'undated':'1','cursor':first['next']}).json()
        self.assertEqual((len(first['photos']),len(second['photos']),second['count']),(48,3,51))
        self.assertFalse({p['id'] for p in first['photos']} & {p['id'] for p in second['photos']})
        self.assertIsNone(second['next'])
        for query in [{'cursor':first['next']},{'undated':'1','kind':'photo','cursor':first['next']},{'month':'2020-01','cursor':first['next']}]:
            self.assertEqual(self.client.get('/api/photos/',query).status_code,400)

    def test_dated_cursor_cannot_cross_kind_or_month(self):
        for _ in range(49): self.memory(display_date='2020-01-01',date_source='manual')
        cursor=self.client.get('/api/photos/?kind=photo&month=2020-01').json()['next']
        for query in [{'cursor':cursor,'kind':'video','month':'2020-01'},{'cursor':cursor,'kind':'photo','month':'2020-02'},{'cursor':cursor}]:
            self.assertEqual(self.client.get('/api/photos/',query).status_code,400)

    def test_validation_and_authorization(self):
        for url in ['/api/photos/?kind=all','/api/photos/months/?kind=gif','/api/photos/?undated=0','/api/photos/?undated=1&month=2020-01']:
            self.assertEqual(self.client.get(url).status_code,400)
        self.client.logout()
        for url in ['/api/photos/?undated=1','/api/photos/months/?kind=video','/api/summary/']:
            self.assertEqual(self.client.get(url).status_code,401)

    def test_caption_only_and_manual_assignment(self):
        p=self.memory(caption='original'); url=f'/api/photos/{p.pk}/edit/'
        self.assertEqual(self.post(url,{'caption':'new caption','date':None}).status_code,200)
        p.refresh_from_db(); self.assertIsNone(p.display_date); self.assertEqual(p.date_source,'missing')
        self.assertEqual(self.post(url,{'caption':'new caption','date':'2001-02-03'}).status_code,200)
        p.refresh_from_db(); self.assertEqual(p.date_source,'manual')
        self.assertEqual(self.post(url,{'caption':'erase','date':None}).status_code,400)
        p.refresh_from_db();self.assertEqual(p.caption,'new caption')

    def test_caption_edit_preserves_existing_capture_source(self):
        p=self.memory(display_date='2000-01-02',date_source='exif')
        self.assertEqual(self.post(f'/api/photos/{p.pk}/edit/',{'caption':'changed caption','date':'2000-01-02'}).status_code,200)
        p.refresh_from_db();self.assertEqual(p.date_source,'exif')

    def test_bulk_assignment_moves_mixed_media_and_preserves_facts(self):
        media=[self.memory(caption='keep'), self.memory(media_kind='video')]
        self.assertEqual(self.post('/api/photos/bulk-date/',{'ids':[str(p.pk) for p in media],'date':'1999-12-31'}).json()['updated'],2)
        self.assertEqual(self.client.get('/api/photos/?undated=1').json()['count'],0)
        self.assertEqual(self.client.get('/api/photos/?month=1999-12').json()['count'],2)
        self.assertEqual(self.client.get('/api/summary/').json()['undatedCount'],0)
        for p in media:
            old=(p.original_key,p.sha256,p.caption,p.uploaded_at)
            p.refresh_from_db();self.assertEqual((p.original_key,p.sha256,p.caption,p.uploaded_at),old)
            self.assertEqual(p.date_source,'manual')

    def test_bulk_unavailable_record_leaves_missing_records_unchanged(self):
        p=self.memory()
        response=self.post('/api/photos/bulk-date/',{'ids':[str(p.pk),str(uuid.uuid4())],'date':'2020-01-01'})
        self.assertEqual(response.status_code,404)
        p.refresh_from_db();self.assertIsNone(p.display_date);self.assertEqual(p.date_source,'missing')

    def test_migration_changes_only_legacy_upload_dates(self):
        records=[self.memory(display_date='2025-01-01',date_source=source) for source in ['upload','manual','exif','file']]
        pending=self.memory(display_date='2025-01-01',date_source='upload',status='pending')
        trashed=self.memory(display_date='2025-01-01',date_source='upload',trashed_at=timezone.now())
        module=importlib.import_module('memories.migrations.0004_alter_photo_date_source_alter_photo_display_date')
        class Schema: pass
        schema=Schema();schema.connection=connection
        module.remove_upload_fallbacks(apps,schema)
        for p in [records[0],pending,trashed]:
            before=(p.original_key,p.sha256,p.uploaded_at,p.trashed_at)
            p.refresh_from_db();self.assertIsNone(p.display_date);self.assertEqual(p.date_source,'missing')
            self.assertEqual((p.original_key,p.sha256,p.uploaded_at,p.trashed_at),before)
        for p in records[1:]:
            p.refresh_from_db();self.assertEqual(p.display_date,date(2025,1,1))
