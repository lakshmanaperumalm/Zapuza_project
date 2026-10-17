from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.shortcuts import redirect, render

from ..models import Employee


def cover(request):
    if request.user.is_authenticated:
        return redirect("factoryops:dashboard")
    return render(request, "portal/cover.html", {"people": Employee.objects.select_related("user")})


def login_view(request):
    if request.user.is_authenticated:
        return redirect("factoryops:dashboard")
    next_url = request.GET.get("next") or request.POST.get("next") or "/portal/"
    if request.method == "POST":
        username = request.POST.get("username", "")
        user = authenticate(request, username=username, password=settings.DEMO_PASSWORD)
        if user is None:
            messages.error(request, "That demo user could not be signed in.")
        else:
            login(request, user)
            return redirect(next_url)
    return render(request, "portal/login.html", {
        "people": Employee.objects.select_related("user"),
        "next": next_url,
    })


def logout_view(request):
    logout(request)
    return redirect("factoryops:cover")
