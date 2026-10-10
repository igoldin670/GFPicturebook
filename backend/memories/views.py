import json
from django.contrib.auth import authenticate, login, logout
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.views.decorators.http import require_GET, require_POST
from .models import Album, Favorite, Photo

def locked_out(request, credentials=None, *args, **kwargs):
    response = JsonResponse({"error": "Too many attempts. Try again in 15 minutes."}, status=429)
    response["Retry-After"] = "900"
    return response

@require_GET
def session(request):
    user = request.user
    return JsonResponse({"csrfToken": get_token(request), "user": {"username": user.username, "isAdmin": user.is_staff} if user.is_authenticated else None})

@require_POST
def sign_in(request):
    if request.content_type != "application/json":
        return JsonResponse({"error": "Expected JSON."}, status=415)
    try:
        data = json.loads(request.body)
        username, password = data["username"], data["password"]
        if not isinstance(username, str) or not isinstance(password, str) or not 1 <= len(username) <= 150 or not 1 <= len(password) <= 1024:
            raise ValueError()
    except (ValueError, KeyError, TypeError):
        return JsonResponse({"error": "Enter a username and password."}, status=400)
    user = authenticate(request, username=username, password=password)
    if user is None:
        return JsonResponse({"error": "Unable to sign in with those details."}, status=401)
    # Django rotates the session key and CSRF token on login.
    login(request, user)
    return JsonResponse({"csrfToken": get_token(request), "user": {"username": user.username, "isAdmin": user.is_staff}})

@require_POST
def sign_out(request):
    logout(request)
    return JsonResponse({"ok": True})

@require_GET
def summary(request):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Sign in required."}, status=401)
    visible = Photo.objects.filter(trashed_at__isnull=True, status=Photo.Status.READY)
    return JsonResponse({"photos": visible.count(), "albums": Album.objects.count(), "favorites": Favorite.objects.filter(user=request.user, photo__in=visible).count()})

@require_GET
def health(request):
    return JsonResponse({"status": "ok"})


def csrf_failure(request, reason=""):
    if request.path.startswith("/api/"):
        return JsonResponse({"error": "Your session changed. Refresh the page and try again."}, status=403)
    from django.views.csrf import csrf_failure as django_csrf_failure
    return django_csrf_failure(request, reason=reason)
