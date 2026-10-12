"""Storage metadata is restricted on the server, not merely hidden in React."""
from functools import wraps
from django.contrib import admin
from django.db.models import Count
from django.http import JsonResponse
from django.template.response import TemplateResponse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
from memories.models import StoredAsset, StorageJob, Photo
from memories.services.drives import refresh_drives


def administrator(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'Sign in required.'}, status=401)
        if not request.user.is_active or not request.user.is_staff:
            return JsonResponse({'error': 'Administrator access required.'}, status=403)
        return view(request, *args, **kwargs)
    return wrapped


def snapshot(request):
    drives = refresh_drives()
    from memories.services.archive import update_protection
    update_protection()
    try:
        page = max(1, min(int(request.GET.get('page', 1)), 1000000))
    except ValueError:
        page = 1
    assets = StoredAsset.objects.select_related('photo').prefetch_related('replicas__drive').order_by('pk')
    rows = []
    for asset in assets[(page-1)*100:page*100]:
        replicas = list(asset.replicas.all())
        identities = {r.drive.physical_id for r in replicas if r.state == 'verified' and r.drive.status in {'online', 'full'}}
        protection = 'protected' if len(identities) >= 2 else 'degraded' if identities else 'unprotected'
        if asset.protection != protection:
            StoredAsset.objects.filter(pk=asset.pk).update(protection=protection)
        rows.append({'id': asset.pk, 'filename': asset.photo.original_filename, 'variant': asset.variant,
            'sha256': asset.sha256, 'bytes': asset.byte_size, 'protection': protection, 'checkedAt': asset.checked_at,
            'replicas': [{'drive': r.drive.label, 'uuid': r.drive_id, 'state': r.state if r.drive.status in {'online', 'full'} else r.drive.status,
                          'verifiedAt': r.verified_at} for r in replicas if r.state != 'missing']})
    counts = dict(StoredAsset.objects.values_list('protection').annotate(count=Count('pk')).values_list('protection', 'count'))
    return {'drives': [{'uuid': d.uuid, 'label': d.label, 'path': d.path, 'physicalId': d.physical_id,
                       'status': d.status, 'health': d.health, 'lastIoErrorAt': d.last_io_error_at, 'integrityFailures': d.integrity_failures, 'total': d.total_bytes, 'free': d.free_bytes, 'checkedAt': d.checked_at} for d in drives],
            'assets': rows, 'counts': counts, 'page': page, 'hasNext': assets.count() > page*100,
            'unmigrated': Photo.objects.filter(storage_job__isnull=True).count(),
            'jobs': list(StorageJob.objects.exclude(status='idle').select_related('photo').order_by('available_at').values('id', 'photo__original_filename', 'status', 'attempts', 'error_code', 'started_at', 'available_at')[:50])}


@require_GET
@administrator
def api(request):
    return JsonResponse(snapshot(request))


@require_GET
@administrator
def dashboard(request):
    context = {**admin.site.each_context(request), 'title': 'Media archive storage', 'storage': snapshot(request)}
    return TemplateResponse(request, 'admin/storage_dashboard.html', context)


@require_POST
@administrator
def check_now(request):
    from django.shortcuts import redirect
    StorageJob.objects.exclude(status='running').update(status='pending', available_at=timezone.now())
    from memories.services.archive import inventory
    inventory()
    return redirect('/admin/storage/')
