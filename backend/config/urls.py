from django.contrib import admin
from django.urls import path
from django.views.generic import TemplateView
from memories import views
urlpatterns = [path("admin/", admin.site.urls), path("api/session/", views.session), path("api/login/", views.sign_in), path("api/logout/", views.sign_out), path("api/summary/", views.summary), path("health/", views.health), path("", TemplateView.as_view(template_name="index.html"))]
