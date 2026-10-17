
from .models import Hold, Inspection, IntakeLot

NAV = [
    ("dashboard", "Dashboard", "grid", "Operations", "/portal/"),
    ("flow", "Flow & Bottlenecks", "route", "Operations", "/portal/flow/"),
    ("jobs", "Job Travelers", "clipboard", "Operations", "/portal/jobs/"),
    ("approvals", "Approvals", "shield", "Operations", "/portal/approvals/"),
    ("holds", "Quality Holds", "lock", "Operations", "/portal/holds/"),
    ("dispatch", "Dispatch Gates", "truck", "Operations", "/portal/dispatch/"),
    ("intake", "Material Intake", "package", "Quality Engineering", "/portal/intake/"),
    ("studio", "Template Studio", "layers", "Quality Engineering", "/portal/studio/"),
    ("trace", "Traceability", "branch", "Quality Engineering", "/portal/trace/"),
    ("master", "Master Data", "db", "System", "/portal/master/"),
    ("audit", "Audit Trail", "history", "System", "/portal/audit/"),
    ("team", "Team & Roles", "users", "System", "/portal/team/"),
    ("rollout", "Rollout Plan", "calendar", "System", "/portal/rollout/"),
    ("demo", "Client Demo Script", "play", "Project", "/portal/demo/"),
]


def badges():
    return {
        "approvals": Inspection.objects.filter(status=Inspection.Status.PENDING).count(),
        "holds": Hold.objects.filter(status="open").count(),
        "intake": IntakeLot.objects.filter(status=IntakeLot.Status.AWAITING).count(),
    }


URL_TO_KEY = {
    "dashboard": "dashboard", "flow": "flow", "jobs": "jobs", "job_detail": "jobs",
    "approvals": "approvals", "holds": "holds", "dispatch": "dispatch", "gate_pass": "dispatch",
    "intake": "intake", "studio": "studio", "template_detail": "studio", "trace": "trace",
    "master": "master", "audit": "audit", "team": "team", "rollout": "rollout", "demo": "demo",
    "tablet_home": "dashboard", "tablet_station": "dashboard", "tablet_inspect": "dashboard",
    "tablet_handover": "dashboard",
}


def nav_context(request):
    emp = getattr(request.user, "employee", None) if request.user.is_authenticated else None
    b = badges() if request.user.is_authenticated else {}
    groups = []
    for key, label, icon, group, url in NAV:
        if not groups or groups[-1]["name"] != group:
            groups.append({"name": group, "items": []})
        groups[-1]["items"].append({
            "key": key, "label": label, "icon": icon, "url": url,
            "badge": b.get(key, 0) if key in ("approvals", "holds", "intake") else 0,
        })
    match = request.resolver_match
    return {
        "active": URL_TO_KEY.get(match.url_name, "") if match else "",
        "nav_groups": groups,
        "employee": emp,
        "pending_approvals": b.get("approvals", 0),
        "open_holds": b.get("holds", 0),
    }
