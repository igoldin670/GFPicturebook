"""Calendar chapters use the existing effective date, without exposing archive data."""
import uuid
from datetime import date, datetime, timezone as dt_timezone
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from memories.models import Photo


@override_settings(SECURE_SSL_REDIRECT=False, ALLOWED_HOSTS=['testserver'])
class DateChapterTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user('chapter-member')

    def setUp(self):
        self.client.force_login(self.user)

    def memory(self, calendar, **fields):
        return Photo.objects.create(original_filename='a memory.jpg', original_key=f'original/{uuid.uuid4()}',
            sha256='1' * 64, byte_size=10, mime_type='image/jpeg', uploaded_by=self.user,
            display_date=date.fromisoformat(calendar), date_source=fields.pop('date_source', 'upload'),
            status=fields.pop('status', 'ready'), **fields)

    def test_months_group_effective_dates_and_skip_empty_months(self):
        self.memory('2026-09-30', date_source='exif', taken_at=datetime(2026, 10, 1, 2, tzinfo=dt_timezone.utc))
        self.memory('2026-09-04', date_source='manual')
        self.memory('2026-11-12', media_kind='video')
        self.memory('2026-11-17')
        self.memory('2026-10-02', status='processing')
        self.memory('2026-10-03', status='failed')
        self.memory('2026-10-04', trashed_at=timezone.now())
        self.assertEqual(self.client.get('/api/photos/months/').json(), {'months': [
            {'month': '2026-09', 'count': 2}, {'month': '2026-11', 'count': 2}]})
        rows = self.client.get('/api/photos/?month=2026-09').json()['photos']
        self.assertEqual([row['date'] for row in rows], ['2026-09-30', '2026-09-04'])
        for row in rows:
            self.assertFalse({'sha256', 'original_key', 'replicas', 'drives', 'path'} & row.keys())

    def test_month_boundaries_leap_year_and_year_rollover(self):
        leap = self.memory('2024-02-29')
        self.memory('2024-03-01')
        december = self.memory('2025-12-31')
        self.memory('2026-01-01')
        for month, expected in [('2024-02', leap), ('2025-12', december)]:
            self.assertEqual([row['id'] for row in self.client.get('/api/photos/', {'month': month}).json()['photos']], [str(expected.id)])
        self.assertEqual(self.client.get('/api/photos/?month=2024-01').json(), {'photos': [], 'next': None})

    def test_invalid_months_and_unsigned_cursor_rejected(self):
        for month in ['2026-13', '2026-00', '0000-10', '26-10', '2026-1', '2026-10-01', '', '../', '٢٠٢٦-١٠']:
            with self.subTest(month=month):
                self.assertEqual(self.client.get('/api/photos/', {'month': month}).status_code, 400)
        self.assertEqual(self.client.get('/api/photos/?month=2026-10&cursor=bad').status_code, 400)

    def test_supported_calendar_extremes_keep_four_digit_years(self):
        self.memory('0001-01-01')
        self.memory('9999-12-31')
        self.assertEqual([row['month'] for row in self.client.get('/api/photos/months/').json()['months']], ['0001-01', '9999-12'])
        self.assertEqual(len(self.client.get('/api/photos/?month=9999-12').json()['photos']), 1)

    def test_pagination_is_complete_and_cursors_are_scoped_to_month(self):
        for _ in range(53):
            self.memory('2026-10-01')
        self.memory('2026-09-30')
        first = self.client.get('/api/photos/?month=2026-10').json()
        self.assertEqual(len(first['photos']), 48)
        second = self.client.get('/api/photos/', {'month': '2026-10', 'cursor': first['next']}).json()
        self.assertEqual(len(second['photos']), 5)
        self.assertIsNone(second['next'])
        ids = [row['id'] for row in first['photos'] + second['photos']]
        self.assertEqual(len(set(ids)), 53)
        self.assertEqual(self.client.get('/api/photos/', {'month': '2026-09', 'cursor': first['next']}).status_code, 400)
        self.assertEqual(self.client.get('/api/photos/', {'cursor': first['next']}).status_code, 400)
        global_page = self.client.get('/api/photos/').json()
        self.assertEqual(len(self.client.get('/api/photos/', {'cursor': global_page['next']}).json()['photos']), 6)
        self.assertEqual(self.client.get('/api/photos/months/').json()['months'][-1]['count'], 53)

    def test_manual_edit_moves_chapter_without_changing_capture_metadata(self):
        photo = self.memory('2026-10-31', date_source='exif', taken_local='2026-10-31T23:00:00')
        response = self.client.post(f'/api/photos/{photo.id}/edit/', {'caption': 'Our day', 'date': '2026-12-01'}, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get('/api/photos/months/').json()['months'], [{'month': '2026-12', 'count': 1}])
        photo.refresh_from_db()
        self.assertEqual(photo.taken_local, '2026-10-31T23:00:00')
        self.assertEqual(photo.date_source, 'manual')

    def test_empty_archive_and_authentication(self):
        self.assertEqual(self.client.get('/api/photos/months/').json(), {'months': []})
        self.client.logout()
        for path in ['/api/photos/months/', '/api/photos/?month=2026-10']:
            self.assertEqual(self.client.get(path).status_code, 401)
