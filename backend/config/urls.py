from django.contrib import admin
from django.urls import path
from django.views.generic import TemplateView
from memories import views, photo_views, storage_views
urlpatterns = [path("admin/storage/", storage_views.dashboard), path("admin/storage/check/", storage_views.check_now), path("api/admin/storage/", storage_views.api), path("admin/", admin.site.urls), path("api/session/", views.session), path("api/login/", views.sign_in), path("api/logout/", views.sign_out), path("api/summary/", views.summary), path("health/", views.health), path("", TemplateView.as_view(template_name="index.html"))]

urlpatterns += [
    path("api/photos/", photo_views.gallery),
    path("api/photos/upload/", photo_views.upload),
    path("api/photos/limits/", photo_views.upload_limits),
    path("api/photos/uploads/", photo_views.upload_status),
    path("api/photos/<uuid:identifier>/edit/", photo_views.edit),
    path("api/photos/<uuid:identifier>/<str:variant>/", photo_views.media),
]
