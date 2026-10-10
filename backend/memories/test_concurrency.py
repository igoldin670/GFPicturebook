"""Real PostgreSQL concurrency checks for the two members' shared upload queue."""
import io
import tempfile
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from types import SimpleNamespace
from unittest import skipUnless
from django.contrib.auth import get_user_model
from django.db import connection, close_old_connections
from django.test import TransactionTestCase, override_settings
from memories.models import Photo
from memories.services.photos import receive, InvalidImage, storage_path
from memories.test_photos import picture


@skipUnless(connection.vendor == "postgresql", "PostgreSQL admission locking")
@override_settings(PHOTO_FREE_RESERVE=0)
class AdmissionConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.override = override_settings(PHOTO_ROOT=Path(self.temp.name))
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.users = [get_user_model().objects.create_user(name) for name in ('me', 'partner')]

    def simultaneous(self, ids):
        start = Barrier(2)
        data = picture()
        def attempt(user, identifier):
            close_old_connections()
            try:
                start.wait(timeout=10)
                stream = io.BytesIO(data)
                request = SimpleNamespace(read=stream.read, user=user)
                try:
                    photo = receive(request, identifier, 'test.jpg')
                    return ('accepted', photo.id, user.pk)
                except InvalidImage:
                    return ('rejected', identifier, user.pk)
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(attempt, user, identifier) for user, identifier in zip(self.users, ids)]
            return [future.result(timeout=20) for future in futures]

    @override_settings(PHOTO_QUEUE_LIMIT=1)
    def test_two_members_cannot_exceed_the_shared_queue_limit(self):
        outcomes = self.simultaneous([uuid.uuid4(), uuid.uuid4()])
        self.assertCountEqual([row[0] for row in outcomes], ['accepted', 'rejected'])
        self.assertEqual(Photo.objects.count(), 1)

    def test_simultaneous_cross_member_uuid_collision_is_rejected_without_overwrite(self):
        identifier = uuid.uuid4()
        outcomes = self.simultaneous([identifier, identifier])
        self.assertCountEqual([row[0] for row in outcomes], ['accepted', 'rejected'])
        photo = Photo.objects.get()
        accepted = next(row for row in outcomes if row[0] == 'accepted')
        self.assertEqual(photo.uploaded_by_id, accepted[2])
        self.assertEqual(storage_path(photo.original_key).read_bytes(), picture())
