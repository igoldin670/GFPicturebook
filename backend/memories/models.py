import uuid
from django.conf import settings
from django.db import models
from django.db.models import Q

class Photo(models.Model):
    class DateSource(models.TextChoices):
        EXIF = "exif", "EXIF"
        FILE = "file", "Trusted import file date"
        UPLOAD = "upload", "Upload time"
        MANUAL = "manual", "Manually edited"
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        READY = "ready", "Ready"
        FAILED = "failed", "Failed"
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    original_filename = models.CharField(max_length=255)
    # Relative, server-generated opaque keys, never user-provided filesystem paths.
    original_key = models.CharField(max_length=255, unique=True)
    thumbnail_key = models.CharField(max_length=255, blank=True)
    preview_key = models.CharField(max_length=255, blank=True)
    sha256 = models.CharField(max_length=64, db_index=True)
    byte_size = models.PositiveBigIntegerField()
    mime_type = models.CharField(max_length=80)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    taken_at = models.DateTimeField(null=True, blank=True)
    # Calendar date is explicit: unknown EXIF timezones must not shift a memory's day.
    taken_local = models.CharField(max_length=32, blank=True)
    taken_offset_minutes = models.SmallIntegerField(null=True, blank=True)
    display_date = models.DateField(db_index=True)
    date_source = models.CharField(max_length=10, choices=DateSource.choices)
    exif_date_raw = models.CharField(max_length=100, blank=True)
    caption = models.TextField(blank=True, max_length=5000)
    width = models.PositiveIntegerField(null=True, blank=True)
    height = models.PositiveIntegerField(null=True, blank=True)
    orientation = models.PositiveSmallIntegerField(null=True, blank=True)
    camera_make = models.CharField(max_length=150, blank=True)
    camera_model = models.CharField(max_length=150, blank=True)
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    location_label = models.CharField(max_length=250, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    trashed_at = models.DateTimeField(null=True, blank=True)
    class Meta:
        indexes = [models.Index(fields=["-display_date", "-id"], name="photo_visible_date", condition=Q(trashed_at__isnull=True, status="ready")), models.Index(fields=["-uploaded_at"])]
        constraints = [models.CheckConstraint(condition=Q(latitude__isnull=True) | Q(latitude__gte=-90, latitude__lte=90), name="valid_latitude"), models.CheckConstraint(condition=Q(longitude__isnull=True) | Q(longitude__gte=-180, longitude__lte=180), name="valid_longitude"), models.CheckConstraint(condition=Q(orientation__isnull=True) | Q(orientation__gte=1, orientation__lte=8), name="valid_orientation")]
    def __str__(self):
        return self.original_filename

class Album(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True, max_length=5000)
    cover_photo = models.ForeignKey(Photo, null=True, blank=True, on_delete=models.SET_NULL, related_name="cover_for")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    photos = models.ManyToManyField(Photo, through="AlbumPhoto", related_name="albums")
    def __str__(self):
        return self.name

class AlbumPhoto(models.Model):
    album = models.ForeignKey(Album, on_delete=models.CASCADE)
    photo = models.ForeignKey(Photo, on_delete=models.CASCADE)
    position = models.PositiveIntegerField(default=0)
    class Meta:
        constraints = [models.UniqueConstraint(fields=["album", "photo"], name="unique_album_photo")]
        indexes = [models.Index(fields=["album", "position"])]

class Favorite(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    photo = models.ForeignKey(Photo, on_delete=models.CASCADE, related_name="favorites")
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "photo"], name="unique_user_favorite")]

class ProcessingJob(models.Model):
    photo = models.OneToOneField(Photo, on_delete=models.CASCADE)
    attempts = models.PositiveSmallIntegerField(default=0)
    available_at = models.DateTimeField()
    lease_until = models.DateTimeField(null=True, blank=True)
    error_code = models.CharField(max_length=80, blank=True)
    class Meta:
        indexes = [models.Index(fields=["available_at", "lease_until"])]

class BackupRun(models.Model):
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=[("running", "Running"), ("success", "Success"), ("failed", "Failed")])
    snapshot_id = models.CharField(max_length=100, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
