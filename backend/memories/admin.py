from django.contrib import admin
from .models import Album, AlbumPhoto, BackupRun, Photo

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
    # Captions/dates are edited through the validated API; originals stay read-only here.
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
