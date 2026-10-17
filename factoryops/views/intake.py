"""Raw material intake, MTC verification, lab sampling and supplier SNCRs."""
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from ..models import IntakeLot, SNCR
from ..services import current_employee, log_audit


@login_required
def intake(request):
    lots = IntakeLot.objects.all().select_related("sncr")
    ctx = {
        "page_title": "Raw Material Intake & MTC Verification",
        "nav_group": "Quality Engineering",
        "active": "intake",
        "lots": lots,
        "sncrs": SNCR.objects.all(),
        "awaiting": lots.filter(status=IntakeLot.Status.AWAITING).count(),
        "lab": lots.filter(status=IntakeLot.Status.LAB).count(),
        "released": lots.filter(status=IntakeLot.Status.RELEASED).count(),
        "open_sncr": SNCR.objects.filter(status="Open").count(),
        "can_release": bool(current_employee(request) and current_employee(request).can_release_intake),
        "sample": lots.filter(status=IntakeLot.Status.RELEASED).first() or lots.first(),
    }
    return render(request, "portal/intake.html", ctx)


def _require_release_role(request):
    emp = current_employee(request)
    if not emp or not emp.can_release_intake:
        messages.error(request, "Only a Quality Engineer, Quality Manager or Plant Manager can release or reject material.")
        return False
    return True


@login_required
def verify_lot(request, pk):
    lot = get_object_or_404(IntakeLot, pk=pk)
    if request.method != "POST":
        return redirect("factoryops:intake")
    if not _require_release_role(request):
        return redirect("factoryops:intake")
    if not (request.POST.get("ack_mtc") and request.POST.get("ack_heat")):
        messages.error(request, "Both verification statements must be ticked before the lot can be released.")
        return redirect("factoryops:intake")
    if not lot.mtc_file:
        messages.error(request, "No readable mill test certificate is attached — the lot cannot be released.")
        return redirect("factoryops:intake")
    if not lot.chemistry_ok:
        bad = [row for row in lot.chemistry if not row[3]]
        messages.error(request, "Chemistry is outside the grade specification "
                                f"({bad[0][0]} {bad[0][1]} vs {bad[0][2]}). Release is refused — reject the lot instead.")
        return redirect("factoryops:intake")
    lot.status = IntakeLot.Status.RELEASED
    lot.released_at = "just now"
    lot.released_by = current_employee(request).name
    lot.save(update_fields=["status", "released_at", "released_by"])
    log_audit(request, "Intake released to stores", f"{lot.no} · {lot.heat_no} · {lot.grade}",
              f"MTC {lot.mtc_file} cross-checked · barcode labels issued · store bin R-{lot.pk:03d}")
    messages.success(request, f"{lot.no} released — barcode labels printed and stock issued to the store room.")
    return redirect("factoryops:intake")


@login_required
def send_lab(request, pk):
    lot = get_object_or_404(IntakeLot, pk=pk)
    if request.method != "POST":
        return redirect("factoryops:intake")
    if not _require_release_role(request):
        return redirect("factoryops:intake")
    lot.status = IntakeLot.Status.LAB
    lot.note = f"Lab sample tagged LAB-{str(lot.pk).zfill(4)} · spectro analysis in progress."
    lot.save(update_fields=["status", "note"])
    log_audit(request, "Intake sample sent to lab", f"{lot.no} · {lot.heat_no}",
              "Spectro / mechanical testing requested · stock cannot be issued until cleared")
    messages.success(request, f"{lot.no} sample sent to the lab — stock stays locked until the result is entered.")
    return redirect("factoryops:intake")


@login_required
def lab_result(request, pk):
    lot = get_object_or_404(IntakeLot, pk=pk)
    if request.method != "POST":
        return redirect("factoryops:intake")
    if not _require_release_role(request):
        return redirect("factoryops:intake")
    passed = request.POST.get("result") == "pass"
    detail = request.POST.get("detail", "").strip() or (
        "Spectro: all elements within grade specification" if passed else "Spectro: chemistry outside specification")
    if passed:
        lot.status = IntakeLot.Status.RELEASED
        lot.released_at = "just now"
        lot.released_by = current_employee(request).name
        lot.lab_result = detail
        lot.save()
        log_audit(request, "Lab result accepted", f"{lot.no} · {lot.heat_no}", detail)
        messages.success(request, f"Lab result accepted — {lot.no} released to stores.")
        return redirect("factoryops:intake")
    sncr = SNCR.objects.create(
        no=f"SNCR-{str(SNCR.objects.count() + 42).zfill(4)}", supplier=lot.supplier, heat=lot.heat_no,
        issue=f"Lab result outside specification — {detail}"[:160], status="Open",
        action="Stock quarantined · Purchasing notified", raised_on=date.today().strftime("%d %b %Y"),
    )
    lot.status = IntakeLot.Status.QUARANTINED
    lot.lab_result = detail
    lot.sncr = sncr
    lot.note = "Lab result failed — stock frozen in supplier quarantine."
    lot.save()
    log_audit(request, "Lab result rejected · SNCR raised", f"{sncr.no} · {lot.heat_no}", detail)
    messages.error(request, f"{sncr.no} raised — {lot.no} moved to supplier quarantine.")
    return redirect("factoryops:intake")


@login_required
def reject_lot(request, pk):
    lot = get_object_or_404(IntakeLot, pk=pk)
    if request.method != "POST":
        return redirect("factoryops:intake")
    if not _require_release_role(request):
        return redirect("factoryops:intake")
    if not request.POST.get("ack"):
        messages.error(request, "Confirm the quarantine acknowledgement before rejecting the intake.")
        return redirect("factoryops:intake")
    reason = request.POST.get("reason", "No valid MTC supplied").strip()
    sncr = SNCR.objects.create(
        no=f"SNCR-{str(SNCR.objects.count() + 42).zfill(4)}", supplier=lot.supplier, heat=lot.heat_no,
        issue=reason[:160], status="Open", action="Stock quarantined · purchasing notified",
        raised_on=date.today().strftime("%d %b %Y"),
    )
    lot.status = IntakeLot.Status.QUARANTINED
    lot.sncr = sncr
    lot.note = reason[:160]
    lot.save()
    log_audit(request, "Intake rejected · SNCR raised", f"{sncr.no} · {lot.heat_no}", reason)
    messages.error(request, f"{lot.no} rejected — {sncr.no} raised and the stock is frozen in quarantine.")
    return redirect("factoryops:intake")
