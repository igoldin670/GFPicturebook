from django.contrib import admin
from .models import Album, AlbumPhoto, BackupRun, Photo, StorageDrive, StoredAsset, FileReplica, StorageJob

class MembershipInline(admin.TabularInline):
    model = AlbumPhoto
    extra = 0
    autocomplete_fields = ["photo"]

@admin.register(Album)
class AlbumAdmin(admin.ModelAdmin):
    list_display = ["name", "created_by", "created_at"]
    search_fields = ["name"]
    inlines = [MembershipInline]

@admin.register(Photo)
class PhotoAdmin(admin.ModelAdmin):
    list_display = ["original_filename", "display_date", "date_source", "status", "trashed_at"]
    search_fields = ["original_filename", "caption"]
    list_filter = ["status", "date_source"]
    # Ingestion and date editing arrive with the validated services in later steps.
    readonly_fields = [f.name for f in Photo._meta.fields]
    def has_add_permission(self, request):
        return False
    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(BackupRun)
class BackupAdmin(admin.ModelAdmin):
    list_display = ["started_at", "completed_at", "status", "verified_at"]
    readonly_fields = [f.name for f in BackupRun._meta.fields]
    def has_add_permission(self, request):
        return False
    def has_delete_permission(self, request, obj=None):
        return False


class ObservationAdmin(admin.ModelAdmin):
    def get_readonly_fields(self, request, obj=None):
        return [f.name for f in self.model._meta.fields]
    def has_add_permission(self, request):
        return False
    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(StorageDrive)
class DriveAdmin(ObservationAdmin):
    list_display = ['label', 'uuid', 'status', 'health', 'free_bytes', 'checked_at']

@admin.register(StoredAsset)
class AssetAdmin(ObservationAdmin):
    list_display = ['photo', 'variant', 'protection', 'checked_at']
    list_filter = ['protection', 'variant']
    search_fields = ['photo__original_filename', 'sha256']

@admin.register(FileReplica)
class ReplicaAdmin(ObservationAdmin):
    list_display = ['asset', 'drive', 'state', 'verified_at']
    list_filter = ['state', 'drive']

@admin.register(StorageJob)
class ArchiveJobAdmin(ObservationAdmin):
    list_display = ['photo', 'status', 'attempts', 'available_at', 'error_code']
    list_filter = ['status']

admin.site.index_template = 'admin/archive_index.html'
